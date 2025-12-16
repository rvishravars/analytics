import os
import csv
from git import Repo
from datetime import datetime, timedelta
from statistics import mean, stdev

from ci_foundation_projects import projects  # Your list of GitHub repos

def get_commit_sizes(repo_path, branch="main"):
    repo = Repo(repo_path)
    if branch not in repo.refs:
        branch = "master" if "master" in repo.refs else repo.head.reference.name

    last_commit = next(repo.iter_commits(branch, max_count=1), None)
    if not last_commit:
        return None

    last_date = datetime.fromtimestamp(last_commit.committed_date)
    since = last_date - timedelta(days=90)

    sizes = []
    for commit in repo.iter_commits(branch, since=since.isoformat(), until=last_date.isoformat()):
        stats = commit.stats.total
        size = stats["insertions"] + stats["deletions"]
        sizes.append(size)

    if not sizes:
        return {
            "Total Commits": 0,
            "Avg Commit Size": 0,
            "Max Commit Size": 0,
            "Min Commit Size": 0,
            "Std Dev": 0
        }

    return {
        "Total Commits": len(sizes),
        "Avg Commit Size": round(mean(sizes), 2),
        "Max Commit Size": max(sizes),
        "Min Commit Size": min(sizes),
        "Std Dev": round(stdev(sizes), 2) if len(sizes) > 1 else 0
    }

# Analyze all projects
results = []
workspace = "ci_projects_commit_sizes"
os.makedirs(workspace, exist_ok=True)

for project in projects:
    name = project["name"]
    url = f"https://github.com/{project['owner']}/{project['repo']}.git"
    local_path = os.path.join(workspace, name)

    try:
        if not os.path.exists(local_path):
            print(f"Cloning {name}...")
            Repo.clone_from(url, local_path)

        stats = get_commit_sizes(local_path)
        if stats is None:
            raise Exception("No commits found")

        results.append({"name": name, **stats})

    except Exception as e:
        print(f"Failed {name}: {e}")
        results.append({
            "name": name,
            "Total Commits": "Error",
            "Avg Commit Size": "Error",
            "Max Commit Size": "Error",
            "Min Commit Size": "Error",
            "Std Dev": "Error"
        })

# Write to CSV
csv_path = "data/5_ci_theater_commit_sizes.csv"
with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
    fieldnames = ["name", "Total Commits", "Avg Commit Size", "Max Commit Size", "Min Commit Size", "Std Dev"]
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(results)

print(f"\n✅ Commit size statistics saved to {csv_path}")
