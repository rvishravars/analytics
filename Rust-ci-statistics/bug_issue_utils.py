import os
import requests
import time
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load token
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    print("⚠️  GITHUB_TOKEN not found in .env file. API requests will be unauthenticated and may be rate-limited.")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}


def is_likely_bug(issue):
    """Heuristic: does the issue sound like a bug?"""
    keywords = ['error', 'crash', 'fail', 'bug', 'broken', 'exception', 'hang', 'freeze', 'not working', 'does not work']
    title = issue.get("title") or ""
    body = issue.get("body") or ""
    text = (title + " " + body).lower()
    return any(k in text for k in keywords)


def get_bug_issues(owner, repo, ci_date):
    """
    Pulls all issues for a repository and counts bug-like issues created
    before and after a given CI adoption date.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    params = {"state": "all", "per_page": 100, "page": 1}

    result = {"before": 0, "after": 0}

    while True:
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=30)

            if resp.status_code == 403 and 'rate limit' in resp.text.lower():
                reset_timestamp = int(resp.headers.get('X-RateLimit-Reset', time.time() + 60))
                sleep_duration = max(0, reset_timestamp - datetime.now().timestamp()) + 2
                print(f"🕒 Rate limit hit for {owner}/{repo}. Sleeping for {sleep_duration:.0f}s...")
                time.sleep(sleep_duration)
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
        time.sleep(0.1)

    return result