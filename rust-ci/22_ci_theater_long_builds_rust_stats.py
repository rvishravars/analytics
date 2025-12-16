#!/usr/bin/env python3
import os
import csv
import time
import argparse
import importlib
import base64
import re
from datetime import datetime, timezone, timedelta
from collections import defaultdict

import requests
from tabulate import tabulate
from dotenv import load_dotenv

# --- Setup & Authentication ---
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise RuntimeError(
        "A GITHUB_TOKEN environment variable is required. Please create a .env file "
        "or export the variable. Unauthenticated requests are severely rate-limited."
    )
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

# --- Configuration ---
MAX_RUNS_TO_CHECK = 25
PER_PAGE = 50
PAGE_SLEEP = 0.1
CUTOFF_DAYS = 90
TIMEOUT_S = 20

# --- Reusable Session for Performance ---
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

def _maybe_sleep_for_ratelimit(resp: requests.Response):
    """If near the API rate limit, sleep until it resets."""
    if int(resp.headers.get("X-RateLimit-Remaining", 1)) <= 5:
        reset_time = int(resp.headers.get("X-RateLimit-Reset", 0))
        wait_duration = max(0, reset_time - int(time.time())) + 5
        print(f"⚠️  Rate limit approaching. Sleeping for {wait_duration}s...")
        time.sleep(wait_duration)

def _format_duration(seconds: float) -> str:
    """Formats seconds into a human-readable 'Xm Ys' string."""
    if seconds < 0:
        return "N/A"
    minutes, seconds = divmod(int(seconds), 60)
    return f"{minutes}m {seconds}s"

# --- NEW FUNCTION ---
def get_submodules(owner: str, repo: str) -> list[str]:
    """
    Fetches the list of submodule paths from the .gitmodules file.
    Returns an empty list if not found or on error.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/.gitmodules"
    try:
        resp = SESSION.get(url, timeout=TIMEOUT_S)
        _maybe_sleep_for_ratelimit(resp)

        if resp.status_code == 404:
            return []  # No .gitmodules file, so no submodules.

        resp.raise_for_status()
        content_b64 = resp.json().get("content")
        if not content_b64:
            return []

        # Decode from base64 and then from bytes to string
        decoded_content = base64.b64decode(content_b64).decode("utf-8")

        # Find all submodule paths using regex. Looks for [submodule "path/here"]
        submodule_paths = re.findall(r'\[submodule "([^"]+)"\]', decoded_content)
        return submodule_paths

    except requests.RequestException as e:
        print(f" [warn] Could not fetch .gitmodules for {owner}/{repo}: {e}")
        return []
    except (UnicodeDecodeError, TypeError):
        print(f" [warn] Could not decode .gitmodules for {owner}/{repo}.")
        return []

def get_job_timings(owner: str, repo: str) -> list[dict]:
    """Fetches job timings for a repository's recent workflow runs."""
    runs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs"
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=CUTOFF_DAYS)
    
    runs_checked = 0
    all_jobs = []

    for page in range(1, 10):
        if runs_checked >= MAX_RUNS_TO_CHECK:
            break
            
        try:
            runs_resp = SESSION.get(runs_url, params={"per_page": PER_PAGE, "page": page}, timeout=TIMEOUT_S)
            _maybe_sleep_for_ratelimit(runs_resp)
            runs_resp.raise_for_status()
            runs = runs_resp.json().get("workflow_runs", [])
            if not runs: break

            for run in runs:
                if runs_checked >= MAX_RUNS_TO_CHECK: break
                
                created_at = datetime.fromisoformat(run["created_at"])
                if created_at < cutoff_date: return all_jobs

                jobs_url = run["jobs_url"]
                try:
                    jobs_resp = SESSION.get(jobs_url, timeout=TIMEOUT_S)
                    _maybe_sleep_for_ratelimit(jobs_resp)
                    if jobs_resp.status_code == 404: continue
                    jobs_resp.raise_for_status()
                    
                    jobs = jobs_resp.json().get("jobs", [])
                    for job in jobs:
                        if job["status"] == "completed" and job["started_at"] and job["completed_at"]:
                            start = datetime.fromisoformat(job["started_at"])
                            end = datetime.fromisoformat(job["completed_at"])
                            duration = (end - start).total_seconds()
                            all_jobs.append({
                                "name": job["name"],
                                "duration_s": duration,
                                "run_url": run["html_url"],
                            })
                except requests.RequestException as e:
                    print(f" [warn] Could not fetch jobs for run {run['id']}: {e}")
                    continue

                runs_checked += 1
            time.sleep(PAGE_SLEEP)
        
        except requests.RequestException as e:
            print(f" [error] Failed to fetch runs for {owner}/{repo}: {e}")
            return []

    return all_jobs

def summarize_repo_jobs(repo_slug: str, jobs: list[dict]) -> dict:
    """Analyzes a list of job timings to find the slowest ones."""
    if not jobs:
        return {"Repo": repo_slug, "Runs Checked": 0}

    longest_job_instance = max(jobs, key=lambda j: j["duration_s"])
    jobs_by_name = defaultdict(list)
    for job in jobs:
        jobs_by_name[job["name"]].append(job["duration_s"])

    avg_durations = {
        name: sum(durations) / len(durations)
        for name, durations in jobs_by_name.items()
    }
    
    slowest_job_type_name = max(avg_durations, key=avg_durations.get)
    slowest_avg_duration = avg_durations[slowest_job_type_name]

    return {
        "Repo": repo_slug,
        "Slowest Job Type (Avg)": slowest_job_type_name,
        "Avg Duration": _format_duration(slowest_avg_duration),
        "Longest Single Job": longest_job_instance["name"],
        "Max Duration": _format_duration(longest_job_instance["duration_s"]),
        "Runs Checked": MAX_RUNS_TO_CHECK,
    }

def main():
    parser = argparse.ArgumentParser(
        description="Analyze GitHub Actions job durations and submodules for a list of repositories."
    )
    parser.add_argument(
        "projects_file",
        help="The Python module name (without .py) containing the 'projects' list of 'owner/repo' slugs.",
    )
    parser.add_argument(
        "--output-file",
        default="job_duration_analysis.csv",
        help="Path to the output CSV file.",
    )
    args = parser.parse_args()

    try:
        projects_module = importlib.import_module(args.projects_file)
        repo_slugs = projects_module.projects
    except (ImportError, AttributeError) as e:
        raise RuntimeError(
            f"Could not import 'projects' list from '{args.projects_file}.py'. Error: {e}"
        ) from e
    
    projects = [{"owner": s.split('/')[0], "name": s.split('/')[1]} for s in repo_slugs if '/' in s]
    
    results = []
    total = len(projects)
    
    # --- MODIFICATION START ---
    # Define headers to include the new "Submodules" column
    headers = [
        "Repo", "Submodules", "Slowest Job Type (Avg)", "Avg Duration", 
        "Longest Single Job", "Max Duration", "Runs Checked"
    ]
    
    for i, project in enumerate(projects, start=1):
        owner, repo = project["owner"], project["name"]
        slug = f"{owner}/{repo}"
        print(f"[{i}/{total}] Analyzing {slug}...")

        # Get job timings as before
        jobs = get_job_timings(owner, repo)
        summary = summarize_repo_jobs(slug, jobs)
        
        # Get submodules and add to the summary
        submodules = get_submodules(owner, repo)
        summary["Submodules"] = "|".join(submodules)
        
        results.append(summary)
        
        # Write intermediate results to the CSV file
        try:
            with open(args.output_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                for row in results:
                    writer.writerow({h: row.get(h, "") for h in headers})
        except IOError as e:
            print(f" [error] Could not write to output file: {e}")
    # --- MODIFICATION END ---

    if not results:
        print("No results to display.")
        return

    # Display final results table in the console
    print("\n--- Final Summary ---")
    # To prevent table from being too wide, we can select columns to display
    display_headers = {h: h for h in headers if h != "Submodules"}
    display_results = [{k: v for k, v in res.items() if k != "Submodules"} for res in results]
    print(tabulate(display_results, headers=display_headers, tablefmt="grid"))
    print(f"\n✅ Analysis complete. Full results, including submodules, saved to {args.output_file}")

if __name__ == "__main__":
    main()