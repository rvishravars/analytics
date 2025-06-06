import os
import requests
import csv
from datetime import datetime
from dotenv import load_dotenv

projects = [
    {"name": "t5", "owner": "google-research", "repo": "text-to-text-transfer-transformer"},
    {"name": "Qwen", "owner": "QwenLM", "repo": "Qwen"},
    {"name": "Qwen3", "owner": "QwenLM", "repo": "Qwen3"},
    {"name": "RWKV-LM", "owner": "BlinkDL", "repo": "RWKV-LM"},
    {"name": "gpt-neox", "owner": "EleutherAI", "repo": "gpt-neox"},
    {"name": "OpenAI-CLIP", "owner": "openai", "repo": "CLIP"},
    {"name": "Yalm", "owner": "yandex", "repo": "YaLM-100B"},
    {"name": "Dbrx", "owner": "databricks", "repo": "dbrx"},
    {"name": "Yi", "owner": "01-ai", "repo": "Yi"},
    {"name": "Deepseek-V3", "owner": "deepseek-ai", "repo": "DeepSeek-V3"},
    {"name": "Deepseek-Janus", "owner": "deepseek-ai", "repo": "Janus"},
    {"name": "YuE", "owner": "multimodal-art-projection", "repo": "YuE"},
    {"name": "ChronosForecasting", "owner": "amazon-science", "repo": "chronos-forecasting"},
    {"name": "InternVideo", "owner": "OpenGVLab", "repo": "InternVideo"},
    {"name": "lag-llama", "owner": "time-series-foundation-models", "repo": "lag-llama"},
    {"name": "Otter", "owner": "EvolvingLMMs-Lab", "repo": "Otter"},
    {"name": "Clay-foundation-model", "owner": "Clay-foundation", "repo": "model"},
    {"name": "whisper", "owner": "openai", "repo": "whisper"},
    {"name": "microsoft-industrial-foundation-models", "owner": "microsoft", "repo": "Industrial-Foundation-Models"},
    {"name": "microsoft-BioGPT", "owner": "microsoft", "repo": "BioGPT"},
    {"name": "RadFM", "owner": "chaoyi-wu", "repo": "RadFM"},
    {"name": "roberta_zh", "owner": "brightmart", "repo": "roberta_zh"},
    {"name": "Ernie", "owner": "PaddlePaddle", "repo": "ERNIE"},
    {"name": "ChatGlm-6B", "owner": "THUDM", "repo": "ChatGLM-6B"},
    {"name": "R1-Omni", "owner": "HumanMLLM", "repo": "R1-Omni"},
    {"name": "Hibiki", "owner": "kyutai-labs", "repo": "hibiki"}

]

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

def paginate_count(url):
    count = 0
    while url:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Error fetching {url} → {response.status_code}: {response.text}")
            break
        count += len(response.json())
        links = response.headers.get('Link', '')
        url = None
        for link in links.split(','):
            if 'rel="next"' in link:
                url = link[link.find("<")+1:link.find(">")]
                break
    return count

def get_first_workflow_run_date(owner, repo):
    """Find the true earliest GitHub Actions workflow run (by created_at)."""
    earliest = None
    page = 1
    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs?per_page=100&page={page}"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            break
        runs = response.json().get("workflow_runs", [])
        if not runs:
            break
        for run in runs:
            created = datetime.strptime(run["created_at"], "%Y-%m-%dT%H:%M:%SZ")
            if earliest is None or created < earliest:
                earliest = created
        page += 1
    return earliest

def count_workflow_outcomes(owner, repo):
    success = 0
    failure = 0
    page = 1
    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs?per_page=100&page={page}"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            break
        runs = response.json().get("workflow_runs", [])
        if not runs:
            break
        for run in runs:
            conclusion = run.get("conclusion")
            if conclusion == "success":
                success += 1
            elif conclusion == "failure":
                failure += 1
        page += 1
    return success, failure

def get_repo_stats(owner, repo, name):
    base_url = f"https://api.github.com/repos/{owner}/{repo}"
    response = requests.get(base_url, headers=headers)
    if response.status_code != 200:
        print(f"Repo fetch error for {owner}/{repo} → {response.status_code}")
        return {
            "Project": name,
            "Repo URL": f"https://github.com/{owner}/{repo}",
            "Error": f"Repo fetch failed with {response.status_code}"
        }

    repo_data = response.json()
    repo_created_at_str = repo_data.get("created_at", "")
    repo_created_at = datetime.strptime(repo_created_at_str, "%Y-%m-%dT%H:%M:%SZ") if repo_created_at_str else None

    active_period_months = ""
    if repo_created_at:
        delta = datetime.now() - repo_created_at
        active_period_months = round(delta.days / 30.44)

    first_workflow_run_at = get_first_workflow_run_date(owner, repo)
    months_to_first_workflow = ""
    if repo_created_at and first_workflow_run_at:
        delta = first_workflow_run_at - repo_created_at
        months_to_first_workflow = round(delta.days / 30.44)

    issues_url = f"{base_url}/issues?state=all&per_page=100"
    prs_url = f"{base_url}/pulls?state=all&per_page=100"
    contributors_url = f"{base_url}/contributors?per_page=100&anon=true"

    success_runs, failed_runs = count_workflow_outcomes(owner, repo)

    return {
        "Project": name,
        "Repo URL": f"https://github.com/{owner}/{repo}",
        "Active Period (Months)": active_period_months,
        "Total PRs": paginate_count(prs_url),
        "Total Issues": paginate_count(issues_url),
        "Contributors": paginate_count(contributors_url),
        "Workflows Used": "Yes" if (success_runs + failed_runs) > 0 else "No",
        "Months to First Workflow Run": months_to_first_workflow,
        "Workflow Runs (Success)": success_runs,
        "Workflow Runs (Failure)": failed_runs
    }

# Collect all stats
all_stats = []
for p in projects:
    print(f"📦 Processing {p['owner']}/{p['repo']}...")
    stats = get_repo_stats(p["owner"], p["repo"], p["name"])
    all_stats.append(stats)

# Write to CSV
if all_stats:
    with open("github_projects_stats.csv", "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=all_stats[0].keys())
        writer.writeheader()
        writer.writerows(all_stats)
    print("✅ CSV export complete: github_project_stats.csv")
else:
    print("⚠️ No data written.")