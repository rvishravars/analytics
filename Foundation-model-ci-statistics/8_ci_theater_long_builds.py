import os
import requests
import csv
import time
from datetime import datetime
from tabulate import tabulate
from dotenv import load_dotenv

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

from ci_foundation_projects import projects

def get_workflow_durations(owner, repo, max_runs=5000):
    durations = []
    page = 1
    per_page = 100
    try:
        while len(durations) < max_runs:
            url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs?per_page={per_page}&page={page}"
            r = requests.get(url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            runs = r.json().get("workflow_runs", [])
            if not runs:
                break  # no more pages

            for run in runs:
                try:
                    start = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
                    end = datetime.fromisoformat(run["updated_at"].replace("Z", "+00:00"))
                    duration_min = (end - start).total_seconds() / 60.0
                    if 0 <= duration_min <= 240:  # only accept durations up to 4 hours
                        durations.append(duration_min)
                except Exception:
                    continue  # skip malformed runs

                if len(durations) >= max_runs:
                    break

            page += 1
            time.sleep(0.5)  # avoid rate limits

        return durations, len(durations)

    except Exception as e:
        print(f"Error fetching {owner}/{repo}: {e}")
        return None, 0

results = []
for p in projects:
    print(f"Checking {p['name']}...")
    durations, run_count = get_workflow_durations(p["owner"], p["repo"])
    if durations is None or run_count == 0:
        results.append({
            "name": p["name"],
            "Avg Duration (min)": "",
            "Max Duration (min)": "",
            "Long Builds >10min": "",
            "Runs Counted": 0
        })
        continue

    avg = round(sum(durations) / run_count, 2)
    max_dur = round(max(durations), 2)
    long_count = sum(1 for d in durations if d > 10)
    long_pct = round(100 * long_count / run_count, 1)

    results.append({
        "name": p["name"],
        "Avg Duration (min)": avg,
        "Max Duration (min)": max_dur,
        "Long Builds >10min": f"{long_pct}%",
        "Runs Counted": run_count
    })
    time.sleep(1)  # optional: avoid rate limits

# Display results in table format
print(tabulate(results, headers="keys", tablefmt="grid"))

# Write to CSV
csv_file = "data/8_ci_theater_long_builds.csv"
with open(csv_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=results[0].keys())
    writer.writeheader()
    writer.writerows(results)

print(f"\n✅ Results saved to {csv_file}")