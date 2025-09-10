import os
import requests
import pandas as pd
from datetime import datetime, timezone
from dotenv import load_dotenv
from time import sleep
import matplotlib.pyplot as plt

# Load token
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}

OUTPUT_DIR = "data"

# Heuristic: does the issue sound like a bug?
def is_likely_bug(issue):
    keywords = ['error', 'crash', 'fail', 'bug', 'broken', 'exception', 'hang', 'freeze', 'not working', 'does not work']
    title = issue.get("title") or ""
    body = issue.get("body") or ""
    text = (title + " " + body).lower()
    return any(k in text for k in keywords)

# Pull all issues and filter bug-like ones
def get_bug_issues(owner, repo, ci_date):
    url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    params = {"state": "all", "per_page": 100, "page": 1}
    
    result = {"before": 0, "after": 0}
    
    while True:
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=30)

            if resp.status_code == 403 and 'rate limit' in resp.text.lower():
                reset_time = int(resp.headers.get('X-RateLimit-Reset', sleep(60)))
                wait_for = max(0, reset_time - datetime.now().timestamp()) + 2
                print(f"🕒 Rate limit hit. Sleeping for {wait_for:.0f}s...")
                sleep(wait_for)
                continue

            resp.raise_for_status()
            issues = resp.json()
        except requests.RequestException as e:
            print(f"❌ Failed to fetch {owner}/{repo} page {params['page']}: {e}")
            break

        if not issues:
            break
        for issue in issues:
            if 'pull_request' in issue:
                continue
            created_at_str = issue.get('created_at')
            if not created_at_str:
                continue
            created = datetime.strptime(created_at_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if is_likely_bug(issue):
                if created < ci_date:
                    result["before"] += 1
                else:
                    result["after"] += 1
        params["page"] += 1
        sleep(0.1)
    
    return result

# Load project list
df = pd.read_csv("data/23_github_projects_stats_rust.csv")
results = []

for _, row in df.iterrows():
    project = row["Project"]
    ci_str = row["First CI Run Date"]
    if pd.isna(ci_str):
        continue
    try:
        ci_date = datetime.strptime(ci_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)

        if "/" not in project:
            print(f"⚠️ Skipping invalid project slug: '{project}'")
            continue
        owner, repo = project.split("/", 1)
        print(f"Processing {owner}/{repo}...")

        stats = get_bug_issues(owner, repo, ci_date)
        results.append({
            "Project": project,
            "Bug Issues Before CI": stats["before"],
            "Bug Issues After CI": stats["after"]
        })

    except Exception as e:
        print(f"❌ Error processing {project}: {e}")

# Convert to DataFrame and plot
bug_df = pd.DataFrame(results)
print("\nGenerating filtered box plot...")

# Save to CSV for other analyses
out_csv_path = os.path.join(OUTPUT_DIR, "31_bug_issues_before_after_ci.csv")
bug_df.to_csv(out_csv_path, index=False)
print(f"✅ Bug data saved to {out_csv_path}")

plt.figure(figsize=(8, 6))
bug_df[["Bug Issues Before CI", "Bug Issues After CI"]].plot.box()
plt.title("Filtered Bug-Like Issues Before vs After CI")
plt.ylabel("Number of Inferred Bug Issues")
plt.ylim(0, 100)  # y-axis capped as requested
plt.grid(True)
plt.tight_layout()
out_path = os.path.join(OUTPUT_DIR, "31_bugs_before_after_ci_rust.png")
plt.savefig(out_path, dpi=300, bbox_inches='tight')
print(f"✅ Plot saved to {out_path}")
