#!/usr/bin/env python3
import os
import csv
import re
import shutil
import time
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import importlib

from git import Repo, GitCommandError
from tabulate import tabulate
from dotenv import load_dotenv

# ---------------------- Config ----------------------
MAX_WORKERS = 1

# -------------------- Auth & Setup --------------------
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    print("⚠️  GITHUB_TOKEN not found in .env file. Git operations will be unauthenticated and may be rate-limited.")

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
    branch_candidates = [branch, "main", "master", "HEAD"]
    chosen_branch = None
    for candidate_branch in branch_candidates:
        try:
            # Validate we can iterate on it
            next(repo.iter_commits(candidate_branch, max_count=1), None)
            chosen_branch = candidate_branch
            break
        except Exception:
            continue

    if not chosen_branch:
        # nothing workable
        return 0, 0.0, "Unknown"

    # Get all commits from the chosen branch
    commits = list(repo.iter_commits(chosen_branch))

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
    weekday_commit_count = 0
    for commit in commits:
        commit_dt = datetime.fromtimestamp(commit.committed_date, tz=timezone.utc)
        if commit_dt.weekday() < 5:  # Monday is 0, Sunday is 6
            weekday_commit_count += 1

    # Estimate number of weekdays in the project's life.
    num_weeks = project_age_days / 7.0 if project_age_days > 0 else 0
    # Ensure at least one weekday to avoid division by zero for very short-lived projects
    num_weekdays = max(1.0, num_weeks * 5.0)

    total_commits = len(commits)
    avg_weekday_commits = round(weekday_commit_count / num_weekdays, 2)

    return total_commits, avg_weekday_commits, last_date_str

def clone_for_history_analysis(repo_full: str, dest: str, max_retries: int = 3) -> None:
    """
    Shallow clone for history analysis, with retries on transient network errors.
    This function will clean up the destination directory on failed attempts before retrying.
    """
    if GITHUB_TOKEN:
        url = f"https://oauth2:{GITHUB_TOKEN}@github.com/{repo_full}"
    else:
        url = f"https://github.com/{repo_full}"

    # Set up Git's configuration for the clone command to handle large repos.
    git_env = os.environ.copy()
    git_env.update({
        'GIT_HTTP_POST_BUFFER': '524288000', # 500 MB
        'GIT_HTTP_LOW_SPEED_LIMIT': '1000',  # Bytes per second
        'GIT_HTTP_LOW_SPEED_TIME': '300'     # 5 minutes
    })

    # --filter=blob:none clones history without file content, which is what we need.
    # This is much more efficient than a full clone for history analysis.
    opts = ["--filter=blob:none", "--no-tags"]
    last_exception = None
    for attempt in range(max_retries):
        try:
            Repo.clone_from(url, dest, multi_options=opts, env=git_env)
            # Success
            return
        except GitCommandError as e:
            last_exception = e
            if any(err in str(e) for err in ["Failed to connect", "Could not resolve host", "Connection reset by peer", "Broken pipe"]):
                wait = 2 ** attempt  # Exponential backoff: 1, 2, 4 seconds
                print(f"  [warn] Clone failed for {repo_full} (attempt {attempt + 1}/{max_retries}), retrying in {wait}s... Reason: {str(e).splitlines()[-1].strip()}")
                time.sleep(wait)
                if os.path.exists(dest):
                    shutil.rmtree(dest)
                continue
            raise e
            
    # If all retries fail, raise the last exception
    raise last_exception

def process_repository(project: dict, base_tmpdir: str) -> dict:  # base_tmpdir kept for API compatibility; not used
    name = project["name"]
    repo_full = project["repo"]

    try:
        # Create a per-repo ephemeral workspace that auto-cleans after use
        with TemporaryDirectory() as tmpdir:
            dest = os.path.join(tmpdir, safe_dirname(repo_full))

            # Shallow history-only clone (with your internal fallbacks, if any)
            clone_for_history_analysis(repo_full, dest)

            # Analyse commit frequency over the last window
            total_commits, avg_weekday_commits, last_commit_date = get_commit_frequency(dest)

            return {
                "name": name,
                "Last Commit Date": last_commit_date,
                "Total Commits (since inception)": total_commits,
                "Avg_Commits_Weekday": avg_weekday_commits,
            }

    except Exception as e:
        print(f"[error] {name}: {e}")
        return {
            "name": name,
            "Last Commit Date": "Error",
            "Total Commits (since inception)": "Error",
            "Avg_Commits_Weekday": "Error",
        }

# ---------------------- Main ------------------------
def main():
    parser = argparse.ArgumentParser(description="Analyze commit frequency for a list of GitHub repos.")
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
        repo_slugs = projects_module.projects
    except (ImportError, AttributeError):
        error_msg = (
            f"Could not import 'projects' list from '{args.projects_file}.py'.\n"
            f"Please ensure the file '{args.projects_file}.py' exists in the current directory.\n"
            "This file is generated by 'helper_create_cohorts.py'. You may need to run the prerequisite scripts."
        )
        raise RuntimeError(error_msg)

    projects = _to_project_dicts(repo_slugs)

    results = []
    total_projects = len(projects)
    processed_count = 0
    print(f"Analyzing commit frequency for {total_projects} projects...")

    with TemporaryDirectory() as tmpdir:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = [pool.submit(process_repository, proj, tmpdir) for proj in projects]
            for future in as_completed(futures):
                results.append(future.result())
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
    csv_path = args.output_file
    fieldnames = [
        "name",
        "Last Commit Date",
        "Total Commits (since inception)",
        "Avg_Commits_Weekday",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n✅ Results saved to {csv_path}")

if __name__ == "__main__":
    main()
