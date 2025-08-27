#!/usr/bin/env python3
import os
import csv
import re
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor, as_completed

from git import Repo, GitCommandError
from tabulate import tabulate

from ci_rust_projects import projects  # expects projects = [{name, owner, repo}, ...]

# ---------------------- Config ----------------------
MAX_WORKERS = 3
DAYS_WINDOW = 90
INFREQUENT_THRESHOLD = 2.36  # avg commits/weekday threshold

# -------------------- Helpers -----------------------
def safe_dirname(s: str) -> str:
    s = s.strip().replace(" ", "_")
    return re.sub(r"[^A-Za-z0-9._-]", "_", s)

def detect_default_branch(repo: Repo) -> str:
    """
    Determine the default branch reliably:
    - origin/HEAD symbolic-ref (preferred)
    - fall back to 'main' or 'master' if present
    - else fall back to the current HEAD's branch name (if any)
    """
    try:
        sym = repo.git.symbolic_ref("refs/remotes/origin/HEAD")
        # sym looks like: refs/remotes/origin/main
        br = sym.rsplit("/", 1)[-1]
        return br
    except Exception:
        pass

    # look for main/master among remote branches
    remote_branches = [h.name for h in repo.remotes.origin.refs]
    for candidate in ("main", "master"):
        if any(rb.endswith("/" + candidate) for rb in remote_branches):
            return candidate

    # fallback to HEAD reference if available
    try:
        return repo.head.reference.name
    except Exception:
        return "HEAD"

def get_commit_frequency(repo_path: str, branch: str | None = None):
    repo = Repo(repo_path)

    # pick branch if not supplied
    if not branch:
        branch = detect_default_branch(repo)

    # if branch isn't available (shallow oddities), try master/main/HEAD
    candidates = [branch, "main", "master", "HEAD"]
    chosen = None
    for cand in candidates:
        try:
            # Validate we can iterate on it
            next(repo.iter_commits(cand, max_count=1), None)
            chosen = cand
            break
        except Exception:
            continue

    if not chosen:
        # nothing workable
        return 0, 0.0, {}, "Unknown"

    # Time window
    now = datetime.now(timezone.utc)
    since_dt = now - timedelta(days=DAYS_WINDOW)

    # GitPython accepts ISO8601 strings for since/until
    since_iso = since_dt.isoformat()
    until_iso = now.isoformat()

    commits = list(repo.iter_commits(chosen, since=since_iso, until=until_iso))

    weekday_counts = defaultdict(int)
    for c in commits:
        # committed_date is POSIX timestamp (UTC)
        day = datetime.fromtimestamp(c.committed_date, tz=timezone.utc).strftime("%A")
        weekday_counts[day] += 1

    total_commits = len(commits)
    # 13 weeks × 5 weekdays = 65 weekdays
    avg_weekday = round(total_commits / 65.0, 2)

    # last commit on that branch (may be older than window)
    last_commit = next(repo.iter_commits(chosen, max_count=1), None)
    last_date_str = (
        datetime.fromtimestamp(last_commit.committed_date, tz=timezone.utc).strftime("%Y-%m-%d")
        if last_commit else "Unknown"
    )

    return total_commits, avg_weekday, dict(weekday_counts), last_date_str

def shallow_clone_for_history(repo_full: str, dest: str):
    url = f"https://github.com/{repo_full}"
    since_dt = datetime.utcnow() - timedelta(days=DAYS_WINDOW + 10)
    shallow_since = since_dt.strftime("%Y-%m-%d")

    opts = ["--filter=blob:none", f"--shallow-since={shallow_since}"]
    try:
        Repo.clone_from(url, dest, multi_options=opts)
    except GitCommandError:
        # fallback: just get tip commit
        print(f"[warn] shallow-since failed for {repo_full}, falling back to --depth=1")
        Repo.clone_from(url, dest, multi_options=["--depth=1", "--no-tags"])

def process_one(project: dict, base_tmpdir: str) -> dict:  # base_tmpdir kept for API compatibility; not used
    name = project["name"]
    repo_full = project["repo"]

    try:
        # Create a per-repo ephemeral workspace that auto-cleans after use
        with TemporaryDirectory() as tmpdir:
            dest = os.path.join(tmpdir, safe_dirname(repo_full))

            # Shallow history-only clone (with your internal fallbacks, if any)
            shallow_clone_for_history(repo_full, dest)

            # Analyse commit frequency over the last window
            total, avg_weekday, dist, last_date = get_commit_frequency(dest)

            infrequent = "Yes" if avg_weekday < INFREQUENT_THRESHOLD else "No"

            return {
                "name": name,
                "Last Commit Date": last_date,
                "Total Commits (Last 90d)": total,
                "Avg Commits/Weekday (Mon–Fri)": avg_weekday,
                "Infrequent (<2.36)": infrequent,
            }

    except Exception as e:
        print(f"[error] {name}: {e}")
        return {
            "name": name,
            "Last Commit Date": "Error",
            "Total Commits (Last 90d)": "Error",
            "Avg Commits/Weekday (Mon–Fri)": "Error",
            "Infrequent (<2.36)": "Error",
        }

# ---------------------- Main ------------------------
def main():
    results = []

    with TemporaryDirectory() as tmpdir:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futs = [pool.submit(process_one, proj, tmpdir) for proj in projects]
            for fut in as_completed(futs):
                results.append(fut.result())

    # Sort by date (errors at bottom)
    def sort_key(r):
        return (1, "") if r["Last Commit Date"] in ("Error", "Unknown") else (0, r["Last Commit Date"])
    results.sort(key=sort_key, reverse=True)

    # Display table
    print(tabulate(results, headers="keys", tablefmt="grid"))

    # Save to CSV
    os.makedirs("data", exist_ok=True)
    csv_path = "data/20_ci_theater_commit_frequency_rust.csv"
    fieldnames = [
        "name",
        "Last Commit Date",
        "Total Commits (Last 90d)",
        "Avg Commits/Weekday (Mon–Fri)",
        "Infrequent (<2.36)",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n✅ Results saved to {csv_path}")

if __name__ == "__main__":
    main()
