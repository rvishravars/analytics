import os
import csv
from git import Repo
from datetime import datetime, timedelta
from collections import defaultdict
from tabulate import tabulate

from ci_foundation_projects import projects

def get_commit_frequency(repo_path, branch="main"):
    repo = Repo(repo_path)

    # Fallback branch if 'main' not available
    if branch not in repo.refs:
        if "master" in repo.refs:
            branch = "master"
        else:
            branch = repo.head.reference.name

    last_commit = next(repo.iter_commits(branch, max_count=1), None)
    if not last_commit:
        return 0, 0.0, 0.0, {}, "Unknown"

    last_date = datetime.fromtimestamp(last_commit.committed_date)
    since = last_date - timedelta(days=90)
    commits = list(repo.iter_commits(branch, since=since.isoformat(), until=last_date.isoformat()))

    weekday_counts = defaultdict(int)
    for commit in commits:
        day = datetime.fromtimestamp(commit.committed_date).strftime('%A')
        weekday_counts[day] += 1

    total_commits = len(commits)
    avg_weekday = total_commits / 65.0  # 13 weeks × 5 weekdays

    return total_commits, round(avg_weekday, 2), weekday_counts, last_date.strftime("%Y-%m-%d")


# Run for all projects
results = []
workspace = "ci_projects_commits"
os.makedirs(workspace, exist_ok=True)

for project in projects:
    name = project["name"]
    url = f"https://github.com/{project['owner']}/{project['repo']}.git"
    local_path = os.path.join(workspace, name)

    try:
        if not os.path.exists(local_path):
            print(f"Cloning {name}...")
            Repo.clone_from(url, local_path)

        total, avg_weekday, dist, last_date = get_commit_frequency(local_path)

        infrequent = "Yes" if avg_weekday < 2.36 else "No"

        results.append({
            "name": name,
            "Last Commit Date": last_date,
            "Total Commits (Last 90d)": total,
            "Avg Commits/Weekday (Mon–Fri)": avg_weekday,
            "Infrequent (<2.36)": infrequent
        })

    except Exception as e:
        print(f"Failed {name}: {e}")
        results.append({
            "name": name,
            "Last Commit Date": "Error",
            "Total Commits (Last 90d)": "Error",
            "Avg Commits/Weekday (Mon–Fri)": "Error",
            "Infrequent (<2.36)": "Error"
        })

# Display table
print(tabulate(results, headers="keys", tablefmt="grid"))

# Save to CSV
csv_path = "data/3_ci_theater_commit_frequency.csv"
with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
    fieldnames = [
        "name",
        "Last Commit Date",
        "Total Commits (Last 90d)",
        "Avg Commits/Weekday (Mon–Fri)",
        "Infrequent (<2.36)"
    ]
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    for row in results:
        writer.writerow(row)

print(f"\n✅ Results saved to {csv_path}")
