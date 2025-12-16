import os
import requests
import pandas as pd
from datetime import datetime
from urllib.parse import urlparse
from dotenv import load_dotenv
from time import sleep
import matplotlib.pyplot as plt

# Load token
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}

# Heuristic: does the issue sound like a bug?
def is_likely_bug(issue):
    keywords = ['error', 'crash', 'fail', 'bug', 'broken', 'exception', 'hang', 'freeze', 'not working', 'does not work']
    text = (issue.get("title", "") + " " + issue.get("body", "")).lower()
    return any(k in text for k in keywords)

# Pull all issues and filter bug-like ones
def get_bug_issues(owner, repo, ci_date):
    url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    params = {"state": "all", "per_page": 100, "page": 1}
    
    result = {"before": 0, "after": 0}
    
    while True:
        resp = requests.get(url, headers=HEADERS, params=params)
        if resp.status_code != 200:
            print(f"Failed to fetch {owner}/{repo}: {resp.status_code}")
            break
        issues = resp.json()
        if not issues:
            break
        for issue in issues:
            if 'pull_request' in issue:
                continue
            created = datetime.strptime(issue['created_at'], "%Y-%m-%dT%H:%M:%SZ")
            if is_likely_bug(issue):
                if created < ci_date:
                    result["before"] += 1
                else:
                    result["after"] += 1
        params["page"] += 1
        sleep(0.1)
    
    return result

# Load project list
df = pd.read_csv("data/1_github_projects_stats.csv")
results = []

for _, row in df.iterrows():
    project = row["Project"]
    repo_url = row["Repo URL"]
    ci_str = row["First CI Run Date"]
    if pd.isna(ci_str):
        continue
    try:
        ci_date = datetime.strptime(ci_str, "%Y-%m-%d")
        path = urlparse(repo_url).path.strip("/").split("/")
        if len(path) < 2:
            continue
        owner, repo = path[0], path[1]
        print(f"Processing {owner}/{repo}...")

        stats = get_bug_issues(owner, repo, ci_date)
        results.append({
            "Project": project,
            "Bug Issues Before CI": stats["before"],
            "Bug Issues After CI": stats["after"]
        })

    except Exception as e:
        print(f"Error processing {project}: {e}")

# Convert to DataFrame and plot
bug_df = pd.DataFrame(results)
print("\nGenerating filtered box plot...")

plt.figure(figsize=(8, 6))
bug_df[["Bug Issues Before CI", "Bug Issues After CI"]].plot.box()
plt.title("Filtered Bug-Like Issues Before vs After CI")
plt.ylabel("Number of Inferred Bug Issues")
plt.ylim(0, 100)  # y-axis capped as requested
plt.grid(True)
plt.tight_layout()
plt.show()
