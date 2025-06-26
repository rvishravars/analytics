import os
import csv
from git import Repo
from datetime import datetime, timedelta
from ci_foundation_projects import projects  # Assumed to be a list of dicts with 'name', 'owner', 'repo'

# === CONFIG ===
WORKSPACE = "ci_projects_commits"
CSV_OUTPUT = "../pushes_to_main_without_pr.csv"
DAYS = 90

os.makedirs(WORKSPACE, exist_ok=True)

def is_direct_push(commit):
    """Check if the commit was a direct push (not from PR)"""
    is_merge = len(commit.parents) > 1
    msg = commit.message.lower()
    mentions_pr = "pull request" in msg or "merge pull request" in msg
    return not is_merge and not mentions_pr

def get_default_branch(repo):
    if "main" in repo.refs:
        return "main"
    elif "master" in repo.refs:
        return "master"
    else:
        return repo.head.reference.name

def collect_direct_pushes(repo_path, project_name, days=90):
    repo = Repo(repo_path)
    branch = get_default_branch(repo)

    last_commit = next(repo.iter_commits(branch, max_count=1), None)
    if not last_commit:
        return []

    last_date = datetime.fromtimestamp(last_commit.committed_date)
    since = last_date - timedelta(days=days)

    commits = list(repo.iter_commits(branch, since=since.isoformat(), until=last_date.isoformat()))
    return [
        {
            "project": project_name,
            "commit_hash": c.hexsha[:10],
            "author": c.author.name,
            "date": datetime.fromtimestamp(c.committed_date).strftime("%Y-%m-%d"),
            "message": c.message.strip()
        }
        for c in commits if is_direct_push(c)
    ]

# === MAIN LOOP ===
results = []

for project in projects:
    name = project["name"]
    url = f"https://github.com/{project['owner']}/{project['repo']}.git"
    local_path = os.path.join(WORKSPACE, name)

    try:
        if not os.path.exists(local_path):
            print(f"Cloning {name}...")
            Repo.clone_from(url, local_path)
        else:
            print(f"Using local clone of {name}")

        direct_pushes = collect_direct_pushes(local_path, name)
        results.extend(direct_pushes)
        print(f"{name}: found {len(direct_pushes)} direct pushes to main")

    except Exception as e:
        print(f"Failed {name}: {e}")

# === WRITE TO CSV ===
with open(CSV_OUTPUT, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["project", "commit_hash", "author", "date", "message"])
    writer.writeheader()
    writer.writerows(results)

print(f"\n✅ Results saved to: {CSV_OUTPUT}")
