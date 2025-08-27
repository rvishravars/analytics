import requests
import os
import csv
from dotenv import load_dotenv
from ci_foundation_projects import projects

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

def fetch_repo_files(owner, repo):
    for branch in ["main", "master", "ernie-kit-open-v1.0"]:
        url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=10"
        r = requests.get(url, headers=HEADERS)
        if r.status_code == 200:
            return r.json().get("tree", [])
    print(f"⚠️ Failed to fetch files for {owner}/{repo}")
    return []

def fetch_text_file(owner, repo, path):
    for branch in ["main", "master"]:
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
        r = requests.get(url)
        if r.status_code == 200:
            return r.text.lower()
    return ""

def scan_python_files_for_keywords(owner, repo, files, keywords):
    matched_deps = set()
    for f in files:
        path = f["path"]
        if not path.endswith(".py"):
            continue

        # Try fetching raw content
        for branch in ["main", "master"]:
            url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
            try:
                r = requests.get(url)
                if r.status_code == 200:
                    content = r.text.lower()
                    for key in keywords:
                        if key in content:
                            matched_deps.add(key)
                break  # Stop after first successful fetch
            except Exception:
                continue
            
    return list(matched_deps)

def analyze_training_signals(owner, repo, files, requirements_text):
    filepaths = [f["path"].lower() for f in files if f["type"] == "blob"]
    folderpaths = [f["path"].lower() for f in files if "/" in f["path"]]

    training_deps = ["torch", "torch.nn", "deepspeed", "megatron", "fsdp", "fairscale", "apex", "flash_attn",
    "transformers", "accelerate", "trl", "t5x", "flax", "jax",
    "mesh_tensorflow", "gin", "tensorflow", "tensorflow_datasets", "tensorflow_text", "mtf"]

    deps_found = [dep for dep in training_deps if dep in requirements_text.lower()]
    
        # Add code-level signals if requirements were incomplete
    if not deps_found:
        code_matches = scan_python_files_for_keywords(owner, repo, files, training_deps)
        if code_matches:
            deps_found = code_matches

    # Check for Gin config files or TensorFlow training scripts
    #has_gin = any(p.endswith(".gin") for p in filepaths)
    #has_mtf_train_script = any("train_mtf.py" in p or "t5/scripts" in p or "mesh_transformer.py" in p for p in filepaths)
    has_finetune = any("finetune" in p for p in filepaths + folderpaths)

    #training_signal = bool(deps_found or has_gin or has_mtf_train_script)
    training_signal = bool(deps_found)

    return {
        "Training Dependencies": ", ".join(deps_found) if deps_found else "None",
        "Has FineTune Folder/File": "Yes" if has_finetune else "No",
        "Has Training Signal": "Yes" if training_signal else "No"
    }

# Example loop
results = []
for proj in projects:
    print(f"🔍 Checking {proj['owner']}/{proj['repo']}...")
    files = fetch_repo_files(proj["owner"], proj["repo"])
    requirements_text = fetch_text_file(proj["owner"], proj["repo"], "requirements.txt")
    result = analyze_training_signals(proj["owner"], proj["repo"], files, requirements_text)
    results.append({
        "Repo": f"{proj['owner']}/{proj['repo']}",
        "Training Dependencies": result["Training Dependencies"],
        "Has FineTune Folder/File": result["Has FineTune Folder/File"],
        "Has Training Signal": result["Has Training Signal"]
    })

# Save to CSV
with open("data/13_repo_training_signals.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=results[0].keys())
    writer.writeheader()
    writer.writerows(results)

print("\n✅ Saved to repo_training_signals.csv")