import os
import requests
from datetime import datetime, timedelta
import csv
from dotenv import load_dotenv
from ci_foundation_projects import projects

load_dotenv()

# Use GitHub token if provided
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"token {GITHUB_TOKEN}" if GITHUB_TOKEN else None,
}

GITHUB_API = "https://api.github.com/repos"


def fetch_repo_metadata(owner, repo):
    r = requests.get(f"{GITHUB_API}/{owner}/{repo}", headers=HEADERS)
    return r.json() if r.status_code == 200 else None

def fetch_repo_files(owner, repo, branch):
    url = f"{GITHUB_API}/{owner}/{repo}/git/trees/{branch}?recursive=1"
    r = requests.get(url, headers=HEADERS)
    return r.json().get("tree", []) if r.status_code == 200 else []

def fetch_readme_text(owner, repo):
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/README.md"
    r = requests.get(url)
    if r.status_code != 200:
        url = url.replace("/main/", "/master/")
        r = requests.get(url)
    return r.text.lower() if r.status_code == 200 else ""

def includes_source_code(files):
    keywords = ["train", "inference", "model", "src", "configs"]
    extensions = [".py", ".ipynb", ".sh", ".yaml", ".yml", ".json"]
    for item in files:
        path = item.get("path", "").lower()
        if any(k in path for k in keywords) and any(path.endswith(ext) for ext in extensions):
            return "Yes"
    return "No"

def includes_training_code(files):
    # Match training folders or filenames commonly seen in FM repos
    training_keywords = [
        "train.py", "training", "finetune", "trainer", "scripts/train",
        "train_", "/train/", "/trainer/", "/training/",
        "models/", "tasks/", "t5/models", "scripts/train_", "mesh_transformer"
    ]
    training_extensions = [".py", ".sh", ".ipynb"]

    for item in files:
        path = item.get("path", "").lower()
        if any(k in path for k in training_keywords) and any(path.endswith(ext) for ext in training_extensions):
            return "Yes"
    return "No"


def includes_model_weights(files):
    weight_exts = [".bin", ".pt", ".ckpt", ".safetensors", ".h5"]
    keywords = ["weights", "checkpoints", "pretrained", "models"]
    for item in files:
        path = item.get("path", "").lower()
        if any(path.endswith(ext) for ext in weight_exts):
            return "Yes"
        if any(k in path for k in keywords):
            return "Yes"
    return "No"

def mentions_huggingface(text, files):
    if "huggingface.co" in text:
        return "Yes"
    for item in files:
        path = item.get("path", "").lower()
        if "huggingface.co" in path:
            return "Yes"
    return "No"

# Run audit
results = []
for proj in projects:
    print(f"🔍 Checking {proj['owner']}/{proj['repo']}...")
    meta = fetch_repo_metadata(proj["owner"], proj["repo"])
    if not meta:
        results.append({
            "Repo": f"{proj['owner']}/{proj['repo']}",
            "URL": "Not Found",
            "Last Push": "N/A",
            "Active in Past Year": "No",
            "Includes Source Code": "No",
            "Includes Training Code": "No",
            "Includes Model Weights": "No",
            "Mentions HuggingFace": "No",
            "Public": "No"
        })
        continue

    pushed = datetime.strptime(meta["pushed_at"], "%Y-%m-%dT%H:%M:%SZ")
    active = pushed > datetime.utcnow() - timedelta(days=365)
    branch = meta["default_branch"]
    files = fetch_repo_files(proj["owner"], proj["repo"], branch)
    readme = fetch_readme_text(proj["owner"], proj["repo"])

    results.append({
        "Repo": f"{proj['owner']}/{proj['repo']}",
        "URL": meta["html_url"],
        "Last Push": meta["pushed_at"],
        "Active in Past Year": "Yes" if active else "No",
        "Includes Source Code": includes_source_code(files),
        "Includes Training Code": includes_training_code(files),
        "Includes Model Weights": includes_model_weights(files),
        "Mentions HuggingFace": mentions_huggingface(readme, files),
        "Public": "Yes"
    })

# Save to CSV
with open("data/foundation_model_repo_audit.csv", "w", newline='', encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=results[0].keys())
    writer.writeheader()
    writer.writerows(results)

print("\n✅ Report saved to foundation_model_repo_audit.csv")
