#!/usr/bin/env python3
import os
import time
import csv
import math
import random
import argparse
import importlib
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
from tabulate import tabulate

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
    { "owner": <owner>, "name": <repo> }
    """
    seen = set()
    out = []
    for slug in slugs:
        try:
            owner, repo = _parse_slug(slug)
            full = f"{owner}/{repo}"
            key = full.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append({"owner": owner, "name": repo})
        except ValueError as e:
            print(f"[warn] Skipping invalid slug: {e}")
    return out

# --------------------------
# Config
# --------------------------
MAX_WORKERS = 4
PER_PAGE = 100
MAX_RUNS_PER_REPO = 100
BASE_BACKOFF = 1.0          # seconds
MAX_BACKOFF = 60.0          # seconds
PER_REQUEST_PAUSE = 0.2     # gentle pacing between requests
USER_AGENT = "ci-theater-broken-builds/1.0"

# --------------------------
# Auth & session
# --------------------------
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
if not GITHUB_TOKEN:
    print("⚠️  No GITHUB_TOKEN found. You will be heavily rate limited by GitHub.")
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}" if GITHUB_TOKEN else "",
    "Accept": "application/vnd.github+json",
    "User-Agent": USER_AGENT,
}

session = requests.Session()
# Robust retry for transient errors (NOT for 403 rate-limit)
retry = Retry(
    total=5,
    read=5,
    connect=5,
    backoff_factor=0.8,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=frozenset(["GET"]),
    raise_on_status=False,
)
adapter = HTTPAdapter(max_retries=retry, pool_connections=MAX_WORKERS, pool_maxsize=MAX_WORKERS)
session.mount("https://", adapter)
session.mount("http://", adapter)

# --------------------------
# Helpers
# --------------------------
def _sleep_with_jitter(seconds: float):
    # Add small jitter to avoid synchronized hammering
    jitter = seconds * 0.1 * random.random()
    time.sleep(seconds + jitter)

def _handle_rate_limit(resp: requests.Response, attempt: int) -> bool:
    """
    Returns True if caller should retry after sleeping, False if not handled here.
    Handles:
      - Primary rate limit (X-RateLimit-Remaining == 0) with X-RateLimit-Reset
      - Secondary/abuse rate limits (403 with message hints)
      - 429 Too Many Requests with Retry-After
    """
    status = resp.status_code
    # 429: respect Retry-After if present
    if status == 429:
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                wait = float(retry_after)
            except ValueError:
                wait = min(MAX_BACKOFF, BASE_BACKOFF * (2 ** attempt))
        else:
            wait = min(MAX_BACKOFF, BASE_BACKOFF * (2 ** attempt))
        print(f"🕒 429 Too Many Requests. Sleeping {wait:.1f}s…")
        _sleep_with_jitter(wait)
        return True

    if status == 403:
        remaining = resp.headers.get("X-RateLimit-Remaining")
        reset = resp.headers.get("X-RateLimit-Reset")
        # Primary rate limit exhausted
        if remaining == "0" and reset:
            try:
                reset_epoch = int(reset)
            except ValueError:
                reset_epoch = math.ceil(time.time()) + int(min(MAX_BACKOFF, BASE_BACKOFF * (2 ** attempt)))
            now = math.ceil(time.time())
            wait = max(1, reset_epoch - now) + 1  # add 1s cushion
            # Cap the sleep to avoid excessively long pauses; still informative
            capped = min(wait, 120)
            print(f"🕒 Primary rate limit hit. Reset in ~{wait}s. Sleeping {capped}s…")
            _sleep_with_jitter(capped)
            return True

        # Secondary/abuse rate limit (GitHub returns 403 with specific message)
        try:
            msg = resp.json().get("message", "").lower()
        except Exception:
            msg = ""
        if "abuse detection" in msg or "secondary rate limit" in msg:
            wait = min(MAX_BACKOFF, BASE_BACKOFF * (2 ** (attempt + 1)))
            print(f"🛡️  Secondary/abuse limit. Backing off {wait:.1f}s…")
            _sleep_with_jitter(wait)
            return True

    return False  # not handled here

def github_get(url: str, params=None, max_attempts: int = 8):
    """
    GET with robust handling for rate limits and transient errors.
    Returns JSON on success; raises on non-retryable failure.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            resp = session.get(url, headers=HEADERS, params=params, timeout=30)
        except requests.RequestException as e:
            if attempt >= max_attempts:
                raise
            wait = min(MAX_BACKOFF, BASE_BACKOFF * (2 ** attempt))
            print(f"🌐 Network error {e}. Retry {attempt}/{max_attempts} in {wait:.1f}s…")
            _sleep_with_jitter(wait)
            continue

        # Successful
        if 200 <= resp.status_code < 300:
            _sleep_with_jitter(PER_REQUEST_PAUSE)
            return resp.json()

        # Rate limit handler may sleep & retry
        if _handle_rate_limit(resp, attempt) and attempt < max_attempts:
            continue

        # If still here and retriable status, do backoff
        if resp.status_code in (500, 502, 503, 504):
            if attempt < max_attempts:
                wait = min(MAX_BACKOFF, BASE_BACKOFF * (2 ** attempt))
                print(f"🔁 {resp.status_code} from GitHub. Retry {attempt}/{max_attempts} in {wait:.1f}s…")
                _sleep_with_jitter(wait)
                continue

        # Not retriable / maxed out
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text
        raise requests.HTTPError(f"GitHub GET failed: {resp.status_code} {detail}")

# --------------------------
# Core logic
# --------------------------
def fetch_runs(owner: str, name: str, max_runs: int = MAX_RUNS_PER_REPO):
    all_runs = []
    full_slug = f"{owner}/{name}"
    page = 1
    while len(all_runs) < max_runs:
        url = f"https://api.github.com/repos/{owner}/{name}/actions/runs"
        params = {"per_page": PER_PAGE, "page": page}
        try:
            data = github_get(url, params=params)
        except Exception as e:
            print(f"❌ Error fetching {full_slug}: {e}")
            break

        runs = data.get("workflow_runs", []) or []
        if not runs:
            break
        all_runs.extend(runs)
        if len(runs) < PER_PAGE:
            break
        page += 1
    return all_runs[:max_runs]

def compute_broken_stretches(runs):
    # Sort by creation time ascending
    runs = sorted(
        runs,
        key=lambda r: r.get("created_at") or ""
    )
    broken_periods = []
    broken_since = None
    for run in runs:
        status = run.get("conclusion")
        created_str = run.get("created_at")
        if not created_str:
            continue
        created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        if status == "failure":
            if broken_since is None:
                broken_since = created
        elif status == "success":
            if broken_since:
                delta_days = (created - broken_since).days
                broken_periods.append(delta_days)
                broken_since = None
        else:
            pass

    if broken_since:
        now = datetime.now(timezone.utc)
        trailing_days = (now - broken_since).days
        broken_periods.append(trailing_days)

    if not broken_periods:
        return 0, 0, 0, 0  # num_broken, q1, mean, q3

    broken_periods.sort()
    len_periods = len(broken_periods)

    # 1st Quartile
    index_q1 = math.ceil(0.25 * len_periods) - 1
    first_quartile = broken_periods[index_q1]

    # 3rd Quartile
    index_q3 = math.ceil(0.75 * len_periods) - 1
    third_quartile = broken_periods[index_q3]

    mean_duration = sum(broken_periods) / len_periods
    num_broken_builds = len_periods

    return num_broken_builds, first_quartile, mean_duration, third_quartile

def process_project(p):
    owner, name = p["owner"], p["name"]
    full_slug = f"{owner}/{name}"
    print(f"🔎 Checking {full_slug}…")
    runs = fetch_runs(owner, name, max_runs=MAX_RUNS_PER_REPO)
    if not runs:
        return {
            "name": full_slug,
            "Runs Analyzed": 0,
            "Number of Broken Builds": "",
            "First Quartile": "",
            "Mean Duration": "",
            "Third Quartile": "",
        }
    num_broken_builds, first_quartile, mean_duration, third_quartile = compute_broken_stretches(runs)
    return {
        "name": full_slug,
        "Runs Analyzed": len(runs),
        "Number of Broken Builds": num_broken_builds,
        "First Quartile": first_quartile,
        "Mean Duration": round(mean_duration, 2),
        "Third Quartile": third_quartile,
    }

# --------------------------
# Parallel execution (4 workers)
# --------------------------
def main():
    parser = argparse.ArgumentParser(description="Analyze broken build stretches for a list of GitHub repos.")
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
    results = []
    # Run in parallel with exactly 4 threads
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {executor.submit(process_project, p): p for p in projects}
        for fut in as_completed(future_map):
            p = future_map[fut]
            try:
                res = fut.result()
            except Exception as e:
                full_slug = f"{p['owner']}/{p['name']}"
                print(f"❌ Unhandled error on {full_slug}: {e}")
                res = {
                    "name": full_slug,
                    "Runs Analyzed": 0,
                    "Number of Broken Builds": "",
                    "First Quartile": "",
                    "Mean Duration": "",
                    "Third Quartile": "",
                }
            results.append(res)

    # Keep output stable: sort by repo name
    results.sort(key=lambda r: r["name"])

    # Display table
    if results:
        print(tabulate(results, headers="keys", tablefmt="grid"))
    else:
        print("No results to display.")

    # Save to CSV
    out_path = args.output_file
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    if results:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
        print(f"\n✅ Results saved to {out_path}")
    else:
        print(f"\n⚠️ No rows written (no results).")

if __name__ == "__main__":
    main()