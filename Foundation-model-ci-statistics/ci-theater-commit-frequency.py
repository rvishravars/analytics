import os
import csv
from git import Repo
from datetime import datetime, timedelta
from collections import defaultdict
from tabulate import tabulate

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
    {"name": "ChatGlm-6B", "owner": "THUDM", "repo": "ChatGLM-6B"}
]

def get_commit_frequency(repo_path, branch="main"):
    repo = Repo(repo_path)
    # Try fallback to master if main is missing
    if branch not in repo.refs:
        branch = "master" if "master" in repo.refs else repo.head.reference.name

    since = datetime.now() - timedelta(days=90)
    commits = list(repo.iter_commits(branch, since=since.isoformat()))

    weekday_counts = defaultdict(int)
    for commit in commits:
        day = datetime.fromtimestamp(commit.committed_date).strftime('%A')
        weekday_counts[day] += 1

    total_commits = len(commits)
    avg_per_weekday = total_commits / 65.0  # ~13 weeks * 5 weekdays

    return total_commits, round(avg_per_weekday, 2), weekday_counts

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

        total, avg, dist = get_commit_frequency(local_path)
        results.append({
            "name": name,
            "Total Commits (90d)": total,
            "Avg Commits/Weekday": avg,
            "Infrequent (<2.36/day)": "Yes" if avg < 2.36 else "No"
        })
    except Exception as e:
        print(f"Failed {name}: {e}")
        results.append({
            "name": name,
            "Total Commits (90d)": "Error",
            "Avg Commits/Weekday": "Error",
            "Infrequent (<2.36/day)": "Error"
        })

# Print table
print(tabulate(results, headers="keys", tablefmt="grid"))

# Write to CSV
csv_path = "ci_theater_commit_frequency.csv"
with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
    fieldnames = ["name", "Total Commits (90d)", "Avg Commits/Weekday", "Infrequent (<2.36/day)"]
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    for row in results:
        writer.writerow(row)

print(f"\n✅ Results saved to {csv_path}")
