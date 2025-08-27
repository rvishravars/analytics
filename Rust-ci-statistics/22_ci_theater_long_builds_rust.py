#!/usr/bin/env python3
import os
import csv
import time
import math
from datetime import datetime, timezone, timedelta

import requests
from tabulate import tabulate
from dotenv import load_dotenv

# --- Setup & Auth ---
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise RuntimeError(
        "GITHUB_TOKEN is required. Unauthenticated requests are limited to 60/hour "
        "and will make this script take many days."
    )
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}

# Your project list module should provide a list like:
# projects = [{"owner": "org_or_user", "name": "repo_name"}, ...]
from ci_rust_projects import projects  # keep as in your original code

# --- Tunables for ~2-day runtime target ---
PER_PAGE     = 50              # GitHub max per_page
MAX_RUNS     = 50             # cap runs collected per repo (was 5000)
PAGE_SLEEP   = 0.10             # pause between pages (was 0.5)
CUTOFF_DAYS  = 365              # ~1 year; stop paging once runs are older than this
DURATION_MAX = 240              # discard runs longer than 4 hours
TIMEOUT_S    = 20               # request timeout
DATA_DIR     = "data"
CSV_FILE     = os.path.join(DATA_DIR, "22_ci_theater_long_builds_rust.csv")

# --- Session (reuses TCP connections; faster & friendlier) ---
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

def _maybe_sleep_for_ratelimit(resp):
    """
    If near the rate limit, sleep until reset.
    Safe-guards long runs without hard failing on 403.
    """
    try:
        remaining = int(resp.headers.get("X-RateLimit-Remaining", "1"))
        reset     = int(resp.headers.get("X-RateLimit-Reset", "0"))
    except ValueError:
        remaining, reset = 1, 0
    if remaining <= 1:
        wait = max(0, reset - int(time.time())) + 2
        print(f"⚠️  Near rate limit. Sleeping {wait}s until reset…")
        time.sleep(wait)

def get_workflow_durations(
    owner: str,
    name: str,
    *,
    max_runs: int = MAX_RUNS,
    per_page: int = PER_PAGE,
    page_sleep: float = PAGE_SLEEP,
    cutoff_days: int = CUTOFF_DAYS,
    timeout_s: int = TIMEOUT_S,
) -> tuple[list[float], int]:
    """
    Fetch workflow run durations (in minutes) for a given repo, with runtime-bounding:
      - cap total collected runs to `max_runs`
      - early-stop when run.created_at < now - cutoff_days
      - small sleep between pages
      - reuse a Session and respect rate-limit headers

    Returns (durations, count).
    """
    durations: list[float] = []
    page = 1
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=cutoff_days)

    try:
        while len(durations) < max_runs:
            url = f"https://api.github.com/repos/{owner}/{name}/actions/runs"
            params = {"per_page": per_page, "page": page}
            resp = SESSION.get(url, params=params, timeout=timeout_s)

            # Handle rate-limit gently
            if resp.status_code == 403 and "rate limit" in resp.text.lower():
                _maybe_sleep_for_ratelimit(resp)
                continue

            resp.raise_for_status()
            runs = resp.json().get("workflow_runs", [])
            if not runs:
                break  # no more pages

            stop_due_to_cutoff = False
            for run in runs:
                try:
                    start = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
                    if start < cutoff_date:
                        stop_due_to_cutoff = True
                        break

                    end = datetime.fromisoformat(run["updated_at"].replace("Z", "+00:00"))
                    duration_min = (end - start).total_seconds() / 60.0
                    if 0 <= duration_min <= DURATION_MAX:
                        durations.append(duration_min)
                        if len(durations) >= max_runs:
                            break
                except Exception:
                    # Skip malformed run
                    continue

            if stop_due_to_cutoff or len(durations) >= max_runs:
                break

            page += 1
            time.sleep(page_sleep)
            _maybe_sleep_for_ratelimit(resp)

        return durations, len(durations)

    except Exception as e:
        print(f"Error fetching {owner}/{name}: {e}")
        return None, 0

def summarize_durations(name: str, durations: list[float] | None) -> dict:
    if not durations:
        return {
            "name": name,
            "Avg Duration (min)": "",
            "Max Duration (min)": "",
            "Long Builds >10min": "",
            "Runs Counted": 0,
        }
    run_count = len(durations)
    avg = round(sum(durations) / run_count, 2)
    mx = round(max(durations), 2)
    long_pct = round(100 * sum(1 for d in durations if d > 10) / run_count, 1)
    return {
        "name": name,
        "Avg Duration (min)": avg,
        "Max Duration (min)": mx,
        "Long Builds >10min": f"{long_pct}%",
        "Runs Counted": run_count,
    }

def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    results: list[dict] = []
    total = len(projects)
    for i, p in enumerate(projects, start=1):
        owner, name = p["owner"], p["name"]
        print(f"[{i}/{total}] Checking {owner}/{name}…")
        durations, run_count = get_workflow_durations(owner, name)
        row = summarize_durations(name, durations)
        results.append(row)

    # Display results in table format
    if results:
        print("\n" + tabulate(results, headers="keys", tablefmt="grid"))

        # Write to CSV
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)

        print(f"\n✅ Results saved to {CSV_FILE}")
    else:
        print("No results to write.")

if __name__ == "__main__":
    main()
