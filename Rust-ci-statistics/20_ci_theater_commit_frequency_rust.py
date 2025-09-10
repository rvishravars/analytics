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

# Import flat list of "owner/repo" slugs
from rust_repos_100_percent import projects as _slug_projects

# ---------------------- Config ----------------------
MAX_WORKERS = 3

# -------------------- Helpers -----------------------
def safe_dirname(s: str) -> str:
    s = s.strip().replace(" ", "_")
    return re.sub(r"[^A-Za-z0-9._-]", "_", s)


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
    Convert flat 'owner/repo' strings into dicts compatible with the old code:
    { "name": <owner/repo>, "repo": <owner/repo> }
    """
    seen = set()
    out = []
    for slug in slugs:
        owner, repo = _parse_slug(slug)
        full = f"{owner}/{repo}"
        key = full.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append({"name": full, "repo": full})
    return out

# Build the adapted projects list once
projects = _to_project_dicts(_slug_projects)

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

def get_commit_frequency(repo_path: str, branch: str | None = None) -> tuple[int, float, str]:
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
        return 0, 0.0, "Unknown"

    # Get all commits from the chosen branch
    commits = list(repo.iter_commits(chosen))

    if not commits:
        return 0, 0.0, "Unknown"

    # Last commit is the first in the list from iter_commits
    last_commit = commits[0]
    last_date_str = datetime.fromtimestamp(last_commit.committed_date, tz=timezone.utc).strftime("%Y-%m-%d")

    # First commit is the last in the list
    first_commit = commits[-1]
    first_commit_dt = datetime.fromtimestamp(first_commit.committed_date, tz=timezone.utc)
    last_commit_dt = datetime.fromtimestamp(last_commit.committed_date, tz=timezone.utc)

    # Calculate project age in days between first and last commit
    project_age_days = (last_commit_dt - first_commit_dt).days

    # Count only weekday commits
    weekday_commits = 0
    for c in commits:
        commit_dt = datetime.fromtimestamp(c.committed_date, tz=timezone.utc)
        if commit_dt.weekday() < 5:  # Monday is 0, Sunday is 6
            weekday_commits += 1

    # Estimate number of weekdays in the project's life.
    num_weeks = project_age_days / 7.0 if project_age_days > 0 else 0
    # Ensure at least one weekday to avoid division by zero for very short-lived projects
    num_weekdays = max(1.0, num_weeks * 5.0)

    total_commits = len(commits)
    avg_weekday = round(weekday_commits / num_weekdays, 2)

    return total_commits, avg_weekday, last_date_str

def shallow_clone_for_history(repo_full: str, dest: str):
    url = f"https://github.com/{repo_full}"
    # --filter=blob:none clones history without file content, which is what we need.
    # This is much more efficient than a full clone for history analysis.
    opts = ["--filter=blob:none", "--no-tags"]
    try:
        Repo.clone_from(url, dest, multi_options=opts)
    except GitCommandError as e:
        print(f"[error] Clone failed for {repo_full}: {e}. This may happen for empty repos.")
        raise

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
            total, avg_weekday, last_date = get_commit_frequency(dest)

            return {
                "name": name,
                "Last Commit Date": last_date,
                "Total Commits (since inception)": total,
                "Avg Commits/Weekday (Mon–Fri)": avg_weekday,
            }

    except Exception as e:
        print(f"[error] {name}: {e}")
        return {
            "name": name,
            "Last Commit Date": "Error",
            "Total Commits (since inception)": "Error",
            "Avg Commits/Weekday (Mon–Fri)": "Error",
        }

# ---------------------- Main ------------------------
def main():
    results = []
    total_projects = len(projects)
    processed_count = 0
    print(f"Analyzing commit frequency for {total_projects} projects...")

    with TemporaryDirectory() as tmpdir:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futs = [pool.submit(process_one, proj, tmpdir) for proj in projects]
            for fut in as_completed(futs):
                results.append(fut.result())
                processed_count += 1
                # Print progress every 10 projects or on the last one
                if processed_count % 10 == 0 or processed_count == total_projects:
                    print(f"  Progress: {processed_count}/{total_projects} projects processed.")

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
        "Total Commits (since inception)",
        "Avg Commits/Weekday (Mon–Fri)",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n✅ Results saved to {csv_path}")

if __name__ == "__main__":
    main()
