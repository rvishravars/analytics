#!/usr/bin/env python3
"""
Fetch test presence + CI execution + coverage signals for a list of GitHub repos.

Outputs CSV:
  name,
  Has Tests (static),
  Tests in CI (configured),
  Tests in CI (recent runs),
  Test Tool (guess),
  Test Evidence,
  Coverage Latest (%),
  Coverage Mean (%),
  Coverage Best (%),
  Coverage Samples,
  Method,
  Latest Run ID,
  Latest Run Date

Requirements:
  pip install requests python-dotenv tabulate

Env:
  GITHUB_TOKEN=<token with repo/public_repo as needed>

Input:
  from ci_rust_projects import projects
  # projects = [{"owner": "org_or_user", "name": "repo"}, ...]
"""

import os
import io
import re
import csv
import time
import math
import base64
import threading
from statistics import mean
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Tuple, List, Dict, Set

import requests
from tabulate import tabulate
from dotenv import load_dotenv

# ---------- Config ----------
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise RuntimeError("GITHUB_TOKEN is required. Unauthenticated requests are limited to 60/hour.")

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "User-Agent": "ci-coverage-and-tests/2.0",
}

# Project list: [{"owner": "org_or_user", "name": "repo"}]
from ci_rust_projects import projects
import zipfile
import xml.etree.ElementTree as ET

# Tunables (kept conservative to avoid rate limits)
WORKERS       = 4           # concurrent repos (raise slowly if stable)
PER_PAGE_RUNS = 100         # max density per page
RUNS_PER_REPO = 10           # only the latest few runs
CUTOFF_DAYS   = 180         # up to ~6 months
PAGE_SLEEP    = 0.10        # throttle between pages
TIMEOUT_S     = 25
DATA_DIR      = "data"
CSV_FILE      = os.path.join(DATA_DIR, "24_ci_theater_coverage_rust.csv")

# ---------- Thread-local Session ----------
_thread_local = threading.local()

def get_session() -> requests.Session:
    s = getattr(_thread_local, "session", None)
    if s is None:
        s = requests.Session()
        s.headers.update(HEADERS)
        adapter = requests.adapters.HTTPAdapter(pool_connections=WORKERS * 2, pool_maxsize=WORKERS * 4)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        _thread_local.session = s
    return s

# ---------- Global Rate Limiter ----------
class RateLimiter:
    def __init__(self, min_remaining: int = 50):
        self._lock = threading.Lock()
        self.remaining: Optional[int] = None
        self.reset_epoch: Optional[int] = None
        self.min_remaining = min_remaining  # sleep if we dip below this

    def preflight(self):
        with self._lock:
            if self.remaining is not None and self.reset_epoch:
                now = int(time.time())
                if self.remaining <= self.min_remaining and self.reset_epoch > now:
                    sleep_for = min(120, self.reset_epoch - now + 1)
                    if sleep_for > 0:
                        print(f"⏸️  Rate limit guard: sleeping {sleep_for}s (remaining={self.remaining})")
                        time.sleep(sleep_for)

    def update_from_resp(self, resp):
        with self._lock:
            try:
                self.remaining = int(resp.headers.get("X-RateLimit-Remaining", self.remaining or 0))
                self.reset_epoch = int(resp.headers.get("X-RateLimit-Reset", self.reset_epoch or 0))
            except Exception:
                pass

RATE = RateLimiter(min_remaining=50)

# ---------- Unified request with retries + global limiting ----------
def http_request(method: str, url: str, session: requests.Session, **kwargs) -> requests.Response:
    MAX_RETRIES = 4
    BACKOFF = 1.7
    for attempt in range(1, MAX_RETRIES + 1):
        RATE.preflight()
        try:
            resp = session.request(method, url, timeout=TIMEOUT_S, **kwargs)
            RATE.update_from_resp(resp)

            # Secondary/abuse throttling
            if resp.status_code in (403, 429):
                ra = resp.headers.get("Retry-After")
                body = (resp.text or "").lower()
                if ra and ra.isdigit():
                    wait = min(120, int(ra))
                    print(f"⏳ Secondary limit: sleeping {wait}s (Retry-After)")
                    time.sleep(wait)
                    continue
                if "secondary rate limit" in body or "abuse detection" in body:
                    wait = min(120, int(BACKOFF ** (attempt - 1)) * 3)
                    print(f"⏳ Secondary limit: backoff {wait}s…")
                    time.sleep(wait)
                    continue
                if "rate limit" in body:
                    # core limit; headers will guide preflight next loop
                    time.sleep(2)
                    continue

            if resp.status_code >= 500:
                wait = min(60, int(BACKOFF ** (attempt - 1)))
                print(f"🔁 {resp.status_code} retry in {wait}s … {url}")
                time.sleep(wait)
                continue

            return resp
        except requests.RequestException as e:
            if attempt == MAX_RETRIES:
                raise
            wait = min(60, int(BACKOFF ** (attempt - 1)))
            print(f"🔁 Network error retry in {wait}s … {e}")
            time.sleep(wait)
    return resp  # type: ignore

# ---------- Coverage patterns (logs) ----------
COVERAGE_PATTERNS = [
    re.compile(r"TOTAL\s+\d+\s+\d+\s+\d+\s+(\d+)%", re.IGNORECASE),                 # pytest-cov TOTAL
    re.compile(r"\bCoverage:\s*(\d+(?:\.\d+)?)\s*%", re.IGNORECASE),                # generic "Coverage: 78%"
    re.compile(r"\bcoverage:\s*(\d+(?:\.\d+)?)%\s+of statements", re.IGNORECASE),   # go test
    re.compile(r"\b(All files|Statements|Lines)\s*[:|]\s*(\d+(?:\.\d+)?)\s*%", re.IGNORECASE),  # jest/nyc
    re.compile(r"\blines\.*:\s*(\d+(?:\.\d+)?)\s*%", re.IGNORECASE),                # lcov/genhtml
    re.compile(r"\bOverall coverage:\s*(\d+(?:\.\d+)?)\s*%", re.IGNORECASE),        # JaCoCo
    re.compile(r"\bCoverage:\s*(\d+(?:\.\d+)?)\s*%\b", re.IGNORECASE),              # rust tarpaulin
    re.compile(r"\bTotal\s+Line:\s*(\d+(?:\.\d+)?)\s*%", re.IGNORECASE),            # .NET coverlet
    re.compile(r"\b(\d+(?:\.\d+)?)\s*%\s*(lines|line|statements|stmts)", re.IGNORECASE),  # generic
]

# ---------- Test command patterns ----------
TEST_CMD_PATTERNS = [
    (re.compile(r"\bcargo\s+test\b", re.IGNORECASE), "cargo"),
    (re.compile(r"\bpytest(\s|$)|\bpython\s+-m\s+pytest\b", re.IGNORECASE), "pytest"),
    (re.compile(r"\bgo\s+test\b", re.IGNORECASE), "go"),
    (re.compile(r"\bmvn\b.*\btest\b", re.IGNORECASE), "maven"),
    (re.compile(r"\bgradle\b.*\btest\b|\bgradlew\b.*\btest\b", re.IGNORECASE), "gradle"),
    (re.compile(r"\bnpm\s+test\b|\byarn\s+test\b|\bpnpm\s+test\b|\bjest\b", re.IGNORECASE), "jest"),
    (re.compile(r"\bdotnet\s+test\b", re.IGNORECASE), ".net"),
    (re.compile(r"\bctest\b", re.IGNORECASE), "ctest"),
    (re.compile(r"\btox\b|\bnox\b", re.IGNORECASE), "pytest"),
    (re.compile(r"actions-rs/cargo.*\bcommand:\s*test\b", re.IGNORECASE | re.DOTALL), "cargo"),
]

RUST_TEST_FILE = re.compile(r".*(_test\.rs|/tests?/|/benches?/)", re.IGNORECASE)

# ---------- Helpers to fetch runs, checks, logs ----------
def list_recent_runs(owner: str, name: str, per_page: int, max_runs: int, cutoff_days: int) -> List[Dict]:
    """Return up to `max_runs` recent workflow runs within cutoff."""
    s = get_session()
    out = []
    page = 1
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=cutoff_days)

    while len(out) < max_runs:
        url = f"https://api.github.com/repos/{owner}/{name}/actions/runs"
        params = {"per_page": min(100, per_page), "page": page}
        resp = http_request("GET", url, s, params=params)
        if resp.status_code == 404:
            break
        resp.raise_for_status()
        runs = resp.json().get("workflow_runs", [])
        if not runs:
            break

        for run in runs:
            try:
                created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
            except Exception:
                created = None
            if created and created < cutoff_date:
                return out  # stop early, older than cutoff
            out.append(run)
            if len(out) >= max_runs:
                return out

        page += 1
        time.sleep(PAGE_SLEEP)

    return out

def list_run_jobs(owner: str, name: str, run_id: int) -> List[Dict]:
    """Return jobs (with steps) for a run (few pages max)."""
    s = get_session()
    url = f"https://api.github.com/repos/{owner}/{name}/actions/runs/{run_id}/jobs"
    jobs = []
    page = 1
    while True:
        resp = http_request("GET", url, s, params={"per_page": 100, "page": page})
        if resp.status_code == 404:
            break
        resp.raise_for_status()
        chunk = resp.json().get("jobs", [])
        if not chunk:
            break
        jobs.extend(chunk)
        if len(chunk) < 100:
            break
        page += 1
    return jobs

def parse_checks_for_coverage(owner: str, name: str, sha: str) -> Optional[float]:
    """Extract coverage percentage from Check Runs (e.g., Codecov)."""
    s = get_session()
    url = f"https://api.github.com/repos/{owner}/{name}/commits/{sha}/check-runs"
    resp = http_request("GET", url, s)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    checks = (resp.json() or {}).get("check_runs", []) or []
    best = None

    def find_pct(text: str) -> Optional[float]:
        if not text:
            return None
        if "cover" not in text.lower():
            return None
        m = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                return None
        return None

    for chk in checks:
        parts = [
            chk.get("name") or "",
            (chk.get("output") or {}).get("title") or "",
            (chk.get("output") or {}).get("summary") or "",
            (chk.get("output") or {}).get("text") or "",
        ]
        for p in parts:
            val = find_pct(p)
            if val is not None:
                best = max(best, val) if best is not None else val

    return best

def parse_logs_zip_for_coverage(zip_bytes: bytes) -> Optional[float]:
    """Scan ZIP of run logs and return highest plausible coverage percentage found."""
    try:
        import zipfile
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except Exception:
        return None

    best = None
    for info in zf.infolist():
        if info.file_size == 0:
            continue
        try:
            with zf.open(info, "r") as f:
                chunk = f.read()
            try:
                text = chunk.decode("utf-8", errors="ignore")
            except Exception:
                text = chunk.decode("latin-1", errors="ignore")
        except Exception:
            continue

        for pat in COVERAGE_PATTERNS:
            for m in pat.finditer(text):
                if m.lastindex:
                    val = None
                    for gi in range(1, m.lastindex + 1):
                        g = m.group(gi)
                        try:
                            val = float(g)
                            break
                        except Exception:
                            continue
                    if val is not None and 0.0 <= val <= 100.0:
                        best = max(best, val) if best is not None else val
    return best

def fetch_run_logs(owner: str, name: str, run_id: int) -> Optional[bytes]:
    """Download ZIP logs for a run, following single redirect."""
    s = get_session()
    url = f"https://api.github.com/repos/{owner}/{name}/actions/runs/{run_id}/logs"
    resp = http_request("GET", url, s)
    if resp.status_code == 302:
        loc = resp.headers.get("Location")
        if loc:
            resp = http_request("GET", loc, s)
    if resp.status_code >= 400:
        return None
    return resp.content

# ---------- Repo static scanning (cheap) ----------
def detect_repo_tests_static(owner: str, name: str) -> Tuple[bool, Optional[str], Set[str]]:
    """
    Cheap heuristics first (few path probes). Only fall back to heavier checks if needed.
    Returns (has_tests, tool_guess, evidence_set)
    """
    evidence: Set[str] = set()
    tool_guess: Optional[str] = None
    s = get_session()

    # Probe a few high-signal directories
    candidate_dirs = ["tests", "test", "spec", "__tests__", "benches"]
    found = False
    for d in candidate_dirs:
        url = f"https://api.github.com/repos/{owner}/{name}/contents/{d}"
        resp = http_request("GET", url, s)
        if resp.status_code == 200:
            found = True
            evidence.add("files")
            break
        if resp.status_code == 404:
            continue
        resp.raise_for_status()

    # Fallback: look at top-level for *_test.rs (very cheap)
    if not found:
        url = f"https://api.github.com/repos/{owner}/{name}/contents"
        resp = http_request("GET", url, s)
        if resp.status_code == 200:
            for it in resp.json() or []:
                p = it.get("name", "")
                if p.endswith("_test.rs"):
                    found = True
                    evidence.add("files")
                    break

    if found:
        tool_guess = "cargo"  # rust-first default for this pass
        return True, tool_guess, evidence

    # (Optional) Full tree walk is disabled by default to save requests.
    return False, None, evidence

# ---------- Workflow scan for test commands ----------
def detect_workflow_tests_config(owner: str, name: str) -> Tuple[bool, Optional[str], Set[str]]:
    """
    Look inside .github/workflows/*.yml for test commands or steps named 'test'.
    Returns (configured, tool_guess, evidence_set)
    """
    evidence: Set[str] = set()
    tool_guess: Optional[str] = None
    s = get_session()
    url = f"https://api.github.com/repos/{owner}/{name}/contents/.github/workflows"
    resp = http_request("GET", url, s)
    if resp.status_code == 404:
        return False, None, evidence
    resp.raise_for_status()
    items = resp.json() or []
    configured = False

    for it in items:
        if it.get("type") != "file":
            continue
        if not re.search(r"\.(yml|yaml)$", it.get("name", ""), re.IGNORECASE):
            continue
        dl = it.get("download_url")
        if not dl:
            continue
        fr = http_request("GET", dl, s)
        if fr.status_code != 200:
            continue
        text = fr.text

        # Look for test commands and popular action plugins
        for pat, tool in TEST_CMD_PATTERNS:
            if pat.search(text):
                configured = True
                evidence.add("workflow")
                tool_guess = tool_guess or tool

        # Also probe for step names that include 'test'
        if re.search(r"name:\s*.*\btest\b", text, re.IGNORECASE):
            configured = True
            evidence.add("workflow")

    return configured, tool_guess, evidence

# ---------- Inspect recent runs for executed tests ----------
def detect_tests_from_runs(owner: str, name: str, runs: List[Dict]) -> Tuple[bool, Optional[str], Set[str]]:
    """
    Inspect jobs/steps of a single representative run to see if tests actually executed.
    Returns (tests_ran_recently, tool_guess, evidence_set)
    """
    evidence: Set[str] = set()
    tool_guess: Optional[str] = None

    # Choose the first run whose title suggests tests; else the latest run
    candidate = None
    for run in runs:
        nm = (run.get("name") or "") + " " + (run.get("display_title") or "")
        if re.search(r"\btest(s)?\b|\bci\b", nm, re.IGNORECASE):
            candidate = run
            break
    if not candidate and runs:
        candidate = runs[0]
    if not candidate:
        return False, None, evidence

    jobs = list_run_jobs(owner, name, int(candidate["id"]))
    tests_seen = False
    for job in jobs:
        if re.search(r"\btest(s)?\b", job.get("name", "") or "", re.IGNORECASE):
            tests_seen = True
            evidence.add("jobs")
        for step in job.get("steps", []) or []:
            nm = step.get("name") or ""
            if re.search(r"\btest(s)?\b", nm, re.IGNORECASE):
                tests_seen = True
                evidence.add("jobs")
            uses = step.get("uses") or ""
            if "actions-rs/cargo" in uses:
                tool_guess = tool_guess or "cargo"

    # Peek logs only if we saw tests and still lack a tool hint
    if tests_seen and not tool_guess:
        blob = fetch_run_logs(owner, name, int(candidate["id"]))
        if blob:
            txt_hint = ""
            try:
                import zipfile
                zf = zipfile.ZipFile(io.BytesIO(blob))
                for i, info in enumerate(zf.infolist()):
                    if i > 4:
                        break
                    if info.file_size and info.file_size < 1_000_000:
                        with zf.open(info, "r") as f:
                            part = f.read(15000).decode("utf-8", errors="ignore")
                            txt_hint += "\n" + part
            except Exception:
                pass
            for pat, tool in TEST_CMD_PATTERNS:
                if pat.search(txt_hint):
                    tool_guess = tool
                    evidence.add("logs")
                    break

    return tests_seen, tool_guess, evidence

# ---------- Coverage + Test detection per repo ----------
def extract_repo_coverage_and_tests(owner: str, name: str) -> Tuple[Dict, List[float]]:
    """
    A) detect tests (static, workflow, recent runs)
    B) compute coverage stats (checks→logs)
    """
    # A) test detection
    has_tests_static, tool_from_files, ev_files = detect_repo_tests_static(owner, name)
    runs = list_recent_runs(owner, name, PER_PAGE_RUNS, RUNS_PER_REPO, CUTOFF_DAYS)
    tests_recent_runs, tool_from_runs, ev_runs = detect_tests_from_runs(owner, name, runs)
    tests_in_workflow, tool_from_wf, ev_wf = detect_workflow_tests_config(owner, name)

    evidence = set()
    evidence |= ev_files
    evidence |= ev_runs
    evidence |= ev_wf

    # Decide tool guess priority: runs > workflow > files (closest to execution reality)
    tool_guess = tool_from_runs or tool_from_wf or tool_from_files

    # B) coverage (checks → logs), stop early once we have at least one value
    coverages: List[float] = []
    method_flags = set()
    latest_run_id = None
    latest_run_date = None

    for idx, run in enumerate(runs):
        if latest_run_id is None:
            latest_run_id = run.get("id")
            latest_run_date = run.get("created_at")

        sha = run.get("head_sha")
        cov = None
        if sha:
            try:
                cov = parse_checks_for_coverage(owner, name, sha)
                if cov is not None:
                    method_flags.add("checks")
                    coverages.append(cov)
                    # Optional: keep scanning to compute mean/best; or break if "latest only"
            except Exception:
                pass

        # Only fetch logs if we haven't seen any coverage yet (reduce requests)
        if cov is None and (not coverages):
            try:
                blob = fetch_run_logs(owner, name, int(run["id"]))
                if blob:
                    cov2 = parse_logs_zip_for_coverage(blob)
                    if cov2 is not None:
                        method_flags.add("logs")
                        coverages.append(cov2)
            except Exception:
                pass

        # If we already captured one value and want minimum calls, uncomment:
        # if coverages:
        #     break

    # Compose row (coverage + test flags)
    if coverages:
        row = {
            "name": name,
            "Coverage Latest (%)": round(coverages[0], 2),
            "Coverage Mean (%)": round(mean(coverages), 2),
            "Coverage Best (%)": round(max(coverages), 2),
            "Coverage Samples": len(coverages),
            "Method": "/".join(sorted(method_flags)) if method_flags else "",
            "Latest Run ID": latest_run_id or "",
            "Latest Run Date": latest_run_date or "",
        }
    else:
        row = {
            "name": name,
            "Coverage Latest (%)": "",
            "Coverage Mean (%)": "",
            "Coverage Best (%)": "",
            "Coverage Samples": 0,
            "Method": "",
            "Latest Run ID": latest_run_id or "",
            "Latest Run Date": latest_run_date or "",
        }

    # Add test detection fields
    row.update({
        "Has Tests (static)": "Yes" if has_tests_static else "No",
        "Tests in CI (configured)": "Yes" if tests_in_workflow else "No",
        "Tests in CI (recent runs)": "Yes" if tests_recent_runs else "No",
        "Test Tool (guess)": tool_guess or "",
        "Test Evidence": "/".join(sorted(evidence)) if evidence else "",
    })
    return row, coverages

def process_repo(index: int, owner: str, name: str) -> Tuple[int, Dict]:
    print(f"[{index}] {owner}/{name} …")
    row, _ = extract_repo_coverage_and_tests(owner, name)
    print(f"[{index}] {owner}/{name} → tests_static={row['Has Tests (static)']}, "
          f"ci_cfg={row['Tests in CI (configured)']}, ci_recent={row['Tests in CI (recent runs)']}, "
          f"samples={row['Coverage Samples']}")
    return index, row

# ---------- Main ----------
def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    total = len(projects)
    print(f"📊 Processing {total} repos with {WORKERS} workers…")
    ordered: List[Optional[Dict]] = [None] * total

    start = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = []
        for i, p in enumerate(projects, start=1):
            futures.append(ex.submit(process_repo, i, p["owner"], p["name"]))

        for fut in as_completed(futures):
            idx, row = fut.result()
            ordered[idx - 1] = row

    results = [r for r in ordered if r is not None]

    if results:
        # Nice console table (best effort)
        try:
            print("\n" + tabulate(results, headers="keys", tablefmt="grid"))
        except Exception:
            pass

        # Ordered columns
        fieldnames = [
            "name",
            "Has Tests (static)",
            "Tests in CI (configured)",
            "Tests in CI (recent runs)",
            "Test Tool (guess)",
            "Test Evidence",
            "Coverage Latest (%)",
            "Coverage Mean (%)",
            "Coverage Best (%)",
            "Coverage Samples",
            "Method",
            "Latest Run ID",
            "Latest Run Date",
        ]
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                writer.writerow({k: r.get(k, "") for k in fieldnames})
        dur = round(time.time() - start, 1)
        print(f"\n✅ Results saved to {CSV_FILE} in {dur}s")
    else:
        print("No results.")

if __name__ == "__main__":
    main()
