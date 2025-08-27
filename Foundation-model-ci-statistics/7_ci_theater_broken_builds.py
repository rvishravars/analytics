import os
import requests
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
from tabulate import tabulate
import csv

from ci_foundation_projects import projects

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

def fetch_runs(owner, repo, max_runs=5000):
    all_runs = []
    page = 1
    per_page = 100

    while len(all_runs) < max_runs:
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs?per_page={per_page}&page={page}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            runs = r.json().get("workflow_runs", [])
            if not runs:
                break
            all_runs.extend(runs)
            if len(runs) < per_page:
                break
            page += 1
            time.sleep(0.5)
        except Exception as e:
            print(f"Error fetching {owner}/{repo}: {e}")
            return []
    return all_runs[:max_runs]

def compute_broken_stretches(runs):
    runs = sorted(runs, key=lambda r: r["created_at"])
    broken_periods = []
    broken_since = None

    for run in runs:
        status = run.get("conclusion")
        created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))

        if status == "failure":
            if broken_since is None:
                broken_since = created
        elif status == "success":
            if broken_since:
                delta = (created - broken_since).days
                broken_periods.append(delta)
                broken_since = None

    # If still broken at the end of the list
    if broken_since:
        now = datetime.now(timezone.utc)
        trailing_days = (now - broken_since).days
        broken_periods.append(trailing_days)

    # Count broken stretches
    broken_gt_2 = len([d for d in broken_periods if d > 2])
    broken_gt_4 = len([d for d in broken_periods if d > 4])
    max_broken_days = max(broken_periods) if broken_periods else 0

    return broken_gt_2, broken_gt_4, max_broken_days

results = []
for p in projects:
    print(f"Checking {p['name']}...")
    runs = fetch_runs(p["owner"], p["repo"], max_runs=500)
    if not runs:
        results.append({
            "name": p["name"],
            "Runs Analyzed": 0,
            "Broken >2 Days": "",
            "Broken >4 Days": "",
            "Max Broken Days": ""
        })
        continue

    gt2, gt4, max_days = compute_broken_stretches(runs)
    results.append({
        "name": p["name"],
        "Runs Analyzed": len(runs),
        "Broken >2 Days": gt2,
        "Broken >4 Days": gt4,
        "Max Broken Days": max_days
    })
    time.sleep(1)

# Display table
print(tabulate(results, headers="keys", tablefmt="grid"))

# Save to CSV
with open("data/7_ci_theater_broken_builds.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=results[0].keys())
    writer.writeheader()
    writer.writerows(results)

print("\n✅ Results saved to 7_ci_theater_broken_builds.csv")
