import os
import csv
import time
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import importlib

import requests
from requests.utils import parse_header_links
from dotenv import load_dotenv

# Import flat list of "owner/repo" slugs

# --- Adapter for flat slugs ---
def _parse_slug(slug: str) -> tuple[str, str]:
    """
    Validate and normalize an 'owner/repo' slug.
    Returns (owner, repo_name).
    """
    s = slug.strip().strip("/")
    if "/" not in s:
        raise ValueError(f"Invalid repo slug '{slug}'. Expected 'owner/repo'.")
    owner, repo = s.split("/", 1)
    owner = owner.strip()
    repo = repo.strip()
    if not owner or not repo:
        raise ValueError(f"Invalid repo slug '{slug}'. Expected 'owner/repo'.")
    return owner, repo

def _to_project_dicts(slugs: list[str]) -> list[dict]:
    """
    Convert flat 'owner/repo' strings into dicts compatible with this script:
    { "owner": <owner>, "name": <repo_name>, "repo": <owner/repo_slug> }
    """
    seen = set()
    out = []
    for slug in slugs:
        try:
            owner, repo_name = _parse_slug(slug)
            full_slug = f"{owner}/{repo_name}"
            key = full_slug.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append({"owner": owner, "name": repo_name, "repo": full_slug})
        except ValueError as e:
            print(f"[warn] Skipping invalid slug: {e}")
    return out

# =========================
# Setup
# =========================
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GH_REST = "https://api.github.com"
GH_GQL  = f"{GH_REST}/graphql"

DEFAULT_TIMEOUT = (5, 30)  # connect, read
MAX_RETRIES = 4
BACKOFF_BASE = 1.7

def make_session() -> requests.Session:
    s = requests.Session()
    if GITHUB_TOKEN:
        s.headers.update({"Authorization": f"Bearer {GITHUB_TOKEN}"})  # works for REST & GraphQL
    s.headers.update({
        "Accept": "application/vnd.github+json",
        "User-Agent": "ci-foundation-stats-script"
    })
    adapter = requests.adapters.HTTPAdapter(pool_connections=16, pool_maxsize=32)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s

session = make_session()

# =========================
# Global rate limiter
# =========================
class RateLimiter:
    """
    Thread-safe limiter that sleeps *before* requests when remaining calls are low,
    and updates itself from response headers.
    """
    def __init__(self, min_remaining: int = 50):
        self._lock = threading.Lock()
        self.remaining: Optional[int] = None
        self.reset_epoch: Optional[int] = None
        self.min_remaining = min_remaining

    def preflight(self):
        with self._lock:
            if self.remaining is not None and self.reset_epoch:
                now = int(time.time())
                if self.remaining <= self.min_remaining and self.reset_epoch > now:
                    sleep_for = min(120, self.reset_epoch - now + 1)
                    if sleep_for > 0:
                        print(f"⏸️  Rate limit guard: sleeping {sleep_for}s (remaining={self.remaining})")
                        time.sleep(sleep_for)

    def update_from_resp(self, resp: requests.Response):
        with self._lock:
            try:
                rem = resp.headers.get("X-RateLimit-Remaining")
                rst = resp.headers.get("X-RateLimit-Reset")
                if rem is not None:
                    self.remaining = int(rem)
                if rst is not None:
                    self.reset_epoch = int(rst)
            except Exception:
                pass

RATE = RateLimiter(min_remaining=50)

# =========================
# Unified request: retries + rate limit handling
# =========================
def _request_with_retries(method: str, url: str, **kwargs) -> requests.Response:
    """
    Handles:
      - Core rate limit (preflight sleep using X-RateLimit headers)
      - Retry-After on 403/429
      - Secondary rate limit / abuse detection (backoff)
      - 5xx retries with exponential backoff
    """
    for attempt in range(1, MAX_RETRIES + 1):
        RATE.preflight()
        try:
            kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
            resp = session.request(method, url, **kwargs)

            # Always update limiter state from headers
            RATE.update_from_resp(resp)

            # Retryable server errors
            if resp.status_code >= 500:
                wait = min(60, int(BACKOFF_BASE ** (attempt - 1)))
                print(f"🔁 {resp.status_code} retry in {wait}s … {url}")
                time.sleep(wait)
                continue

            # Handle throttling
            if resp.status_code in (403, 429):
                # Retry-After honored if present
                ra = resp.headers.get("Retry-After")
                body = (resp.text or "").lower()
                # If core rate limit reached, preflight will sleep next time; give it a moment
                if ra and ra.isdigit():
                    wait = min(180, int(ra))
                    print(f"⏳ Throttled ({resp.status_code}): sleeping {wait}s (Retry-After)")
                    time.sleep(wait)
                    continue
                if "secondary rate limit" in body or "abuse detection" in body:
                    wait = min(120, int(BACKOFF_BASE ** (attempt - 1)) * 3)
                    print(f"⏳ Secondary limit: backoff {wait}s …")
                    time.sleep(wait)
                    continue
                if resp.headers.get("X-RateLimit-Remaining") == "0":
                    reset = resp.headers.get("X-RateLimit-Reset")
                    if reset and reset.isdigit():
                        wait = max(0, int(reset) - int(time.time())) + 2
                        wait = min(wait, 180)
                        print(f"⏳ Core rate limit: sleeping {wait}s until reset …")
                        time.sleep(wait)
                        continue
                # Generic short backoff
                wait = min(60, int(BACKOFF_BASE ** (attempt - 1)))
                print(f"⏳ Throttled ({resp.status_code}): retry in {wait}s …")
                time.sleep(wait)
                continue

            # Also cover explicit 429/503 branch already done above; if not in those, return
            return resp

        except requests.RequestException as e:
            if attempt == MAX_RETRIES:
                raise
            wait = min(60, int(BACKOFF_BASE ** (attempt - 1)))
            print(f"🔁 Network error retry in {wait}s … {e}")
            time.sleep(wait)

    return resp  # type: ignore

# =========================
# REST helpers (only where GraphQL lacks coverage)
# =========================
def _parse_last_page(resp: requests.Response) -> Optional[int]:
    link = resp.headers.get("Link")
    if not link:
        return None
    try:
        links = parse_header_links(link.rstrip('>').replace('>,', ','))
        for l in links:
            if l.get("rel") == "last":
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(l.get("url", "")).query)
                if "page" in qs and qs["page"]:
                    return int(qs["page"][0])
    except Exception:
        pass
    return None

def fast_count(endpoint: str, params: Dict[str, str]) -> int:
    local = dict(params)
    local["per_page"] = "1"
    resp = _request_with_retries("GET", endpoint, params=local)
    if resp.status_code != 200:
        print(f"Count error {endpoint} → {resp.status_code}: {resp.text[:200]}")
        return 0
    last = _parse_last_page(resp)
    if last:
        return last
    try:
        data = resp.json()
        # endpoints like /contributors may return a JSON array when <=1
        return len(data) if isinstance(data, list) else 0
    except Exception:
        return 0

def get_workflow_runs_summary(owner: str, name: str) -> Tuple[int, int, Optional[datetime]]:
    """REST: summarize Actions runs (GraphQL does not expose Actions)."""
    success = 0
    failure = 0
    earliest: Optional[datetime] = None
    page = 1
    while True:
        url = f"{GH_REST}/repos/{owner}/{name}/actions/runs"
        resp = _request_with_retries("GET", url, params={"per_page": "100", "page": str(page)})
        if resp.status_code != 200:
            print(f"Runs fetch error {owner}/{name} p{page} → {resp.status_code}: {resp.text[:200]}")
            break
        payload = resp.json()
        runs = payload.get("workflow_runs", [])
        if not runs:
            break
        for run in runs:
            c = run.get("conclusion")
            if c == "success":
                success += 1
            elif c == "failure":
                failure += 1
            ca = run.get("created_at")
            if ca:
                try:
                    created = datetime.strptime(ca, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                    if earliest is None or created < earliest:
                        earliest = created
                except Exception:
                    pass
        # pagination using Link header
        last = _parse_last_page(resp)
        if not last or page >= last:
            break
        page += 1
    return success, failure, earliest

# =========================
# GraphQL batching
# =========================
def build_repos_batch_query(batch: List[Dict[str, str]]) -> str:
    """
    We alias each repo lookup (r0, r1, ...) to fetch:
      - createdAt
      - issues: OPEN & CLOSED counts (sum client-side → total)
      - pullRequests: OPEN, CLOSED, MERGED counts (sum → total)
    """
    parts = []
    for i, p in enumerate(batch):
        alias = f"r{i}"
        owner = p["owner"]
        name  = p["name"]
        parts.append(f"""
  {alias}: repository(owner: "{owner}", name: "{name}") {{
    nameWithOwner
    url
    createdAt
    issuesOpen: issues(states: OPEN) {{ totalCount }}
    issuesClosed: issues(states: CLOSED) {{ totalCount }}
    prsOpen: pullRequests(states: OPEN) {{ totalCount }}
    prsClosed: pullRequests(states: CLOSED) {{ totalCount }}
    prsMerged: pullRequests(states: MERGED) {{ totalCount }}
  }}
""")
    repo_block = "\n".join(parts)
    # include rateLimit so we can see remaining
    return f"""
query RepoBatch {{
{repo_block}
  rateLimit {{ cost remaining resetAt }}
}}
""".strip()

def gql_post(query: str, variables: Optional[Dict] = None) -> Dict:
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    resp = _request_with_retries("POST", GH_GQL, json=payload)
    if resp.status_code != 200:
        raise RuntimeError(f"GraphQL HTTP {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"GraphQL errors: {data['errors']}")
    return data["data"]

def chunked(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

# =========================
# Aggregation
# =========================
def assemble_row(
    name: str,
    owner: str,
    repo: str,
    created_at_iso: str,
    issues_open: int,
    issues_closed: int,
    prs_open: int,
    prs_closed: int,
    prs_merged: int,
    contribs_count: int,
    success_runs: int,
    failed_runs: int,
    first_run_dt: Optional[datetime],
) -> Dict[str, object]:
    repo_created_at = datetime.strptime(created_at_iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) if created_at_iso else None
    now = datetime.now(timezone.utc)

    active_period_months = ""
    if repo_created_at:
        active_period_months = round((now - repo_created_at).days / 30.44)

    months_to_first_workflow = ""
    first_ci_date_str = ""
    if repo_created_at and first_run_dt:
        months_to_first_workflow = round((first_run_dt - repo_created_at).days / 30.44)
        first_ci_date_str = first_run_dt.strftime("%Y-%m-%d")

    total_issues = issues_open + issues_closed
    total_prs = prs_open + prs_closed + prs_merged

    return {
        "Project": name,
        "Repo URL": f"https://github.com/{owner}/{name}",
        "Created At": created_at_iso,
        "First CI Run Date": first_ci_date_str,
        "Time to First CI (months)": months_to_first_workflow,
        "Active Period (months)": active_period_months,
        "Total PRs": total_prs,
        "Total Issues": total_issues,
        "Contributors": contribs_count,
        "Workflows Used": "Yes" if (success_runs + failed_runs) > 0 else "No",
        "Workflow Runs (Success)": success_runs,
        "Workflow Runs (Failure)": failed_runs
    }

# =========================
# Main
# =========================
def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch GitHub project statistics for a list of repos.")
    parser.add_argument(
        "--projects-file",
        required=True,
        help="The Python module name (without .py) containing the 'projects' list of repo slugs.",
    )
    parser.add_argument(
        "--output-file",
        required=True,
        help="Path to the output CSV file.",
    )
    args = parser.parse_args()

    try:
        projects_module = importlib.import_module(args.projects_file)
        _slug_projects = projects_module.projects
    except (ImportError, AttributeError):
        error_msg = (
            f"Could not import 'projects' list from '{args.projects_file}.py'.\n"
            f"Please ensure the file '{args.projects_file}.py' exists in the current directory.\n"
            "This file is generated by 'helper_create_cohorts.py'. You may need to run the prerequisite scripts."
        )
        raise RuntimeError(error_msg)

    projects = _to_project_dicts(_slug_projects)
    out_path = args.output_file
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    projects_list = list(projects)
    print(f"📊 Starting analysis for {len(projects_list)} projects...")
    start_time = time.time()

    # 1) GraphQL in batches (e.g., 20 repos per query)
    batch_size = 20
    gql_results: Dict[str, Dict] = {}  # key: "owner/name"

    for batch_num, batch in enumerate(chunked(projects_list, batch_size), start=1):
        print(f"🔍 Fetching GraphQL batch {batch_num} ({len(batch)} repos)...")
        q = build_repos_batch_query(batch)
        try:
            data = gql_post(q)
        except Exception as e:
            print(f"❌ GraphQL batch {batch_num} failed: {e}")
            continue

        # collect per alias
        for i, p in enumerate(batch):
            alias = f"r{i}"
            node = data.get(alias)
            if not node:
                print(f"⚠️ Skipping {p['owner']}/{p['name']} (no GraphQL data)")
                continue
            key = f"{p['owner']}/{p['name']}"
            gql_results[key] = {
                "url": node["url"],
                "createdAt": node["createdAt"],
                "issuesOpen": node["issuesOpen"]["totalCount"],
                "issuesClosed": node["issuesClosed"]["totalCount"],
                "prsOpen": node["prsOpen"]["totalCount"],
                "prsClosed": node["prsClosed"]["totalCount"],
                "prsMerged": node["prsMerged"]["totalCount"],
                "name": p["name"],
                "owner": p["owner"],
                "repo": p["repo"],
            }
        print(f"✅ GraphQL batch {batch_num} complete.")

    # 2) For each repo, get Actions summary (REST) + contributors fast count (REST) in parallel
    def rest_bundle(p):
        owner, name = p["owner"], p["name"]
        print(f"   ⏳ REST fetch {owner}/{name}...")
        success_runs, failed_runs, first_run_dt = get_workflow_runs_summary(owner, name)
        contributors = fast_count(f"{GH_REST}/repos/{owner}/{name}/contributors", {"anon": "true"})
        print(f"   ✅ REST done {owner}/{name} (runs={success_runs+failed_runs}, contribs={contributors})")
        return (owner, name, success_runs, failed_runs, first_run_dt, contributors)

    all_stats = []
    # Keep concurrency reasonable to avoid secondary limits
    max_workers = min(6, (os.cpu_count() or 4))
    print(f"⚡ Starting REST fetch with {max_workers} workers...")
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(rest_bundle, p): p for p in projects_list}
        for fut in as_completed(futures):
            p = futures[fut]
            try:
                owner, name, sr, fr, frdt, contribs = fut.result()
            except Exception as e:
                print(f"❌ REST bundle failed for {p['owner']}/{p['repo']}: {e}")
                continue

            key = f"{owner}/{name}"
            g = gql_results.get(key)
            if not g:
                print(f"⚠️ No GraphQL data for {key}, writing stub row")
                all_stats.append({
                    "Project": p["name"],
                    "Repo URL": f"https://github.com/{owner}/{name}",
                    "Error": "GraphQL repo fetch failed or repo not found"
                })
                continue

            row = assemble_row(
                name=p["repo"],
                owner=owner,
                repo=name,
                created_at_iso=g["createdAt"],
                issues_open=g["issuesOpen"],
                issues_closed=g["issuesClosed"],
                prs_open=g["prsOpen"],
                prs_closed=g["prsClosed"],
                prs_merged=g["prsMerged"],
                contribs_count=contribs,
                success_runs=sr,
                failed_runs=fr,
                first_run_dt=frdt,
            )
            all_stats.append(row)

    # 3) Write CSV
    if all_stats:
        fieldnames = [
            "Project","Repo URL","Created At","First CI Run Date",
            "Time to First CI (months)","Active Period (months)",
            "Total PRs","Total Issues","Contributors",
            "Workflows Used","Workflow Runs (Success)","Workflow Runs (Failure)"
        ]
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_stats)
        elapsed = round(time.time() - start_time, 1)
        print(f"✅ CSV export complete: {out_path} ({len(all_stats)} rows, {elapsed}s)")
    else:
        print("⚠️ No data written.")

if __name__ == "__main__":
    main()
