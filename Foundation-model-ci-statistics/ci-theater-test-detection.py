import os
import re
import csv
import subprocess
from git import Repo
from pathlib import Path
from tempfile import TemporaryDirectory

# Known indicators
TEST_KEYWORDS = ["pytest", "unittest", "nose", "mocha", "jest", "go test", "cargo test", "ctest"]
COVERAGE_KEYWORDS = ["coverage", "--cov", "lcov", "gcov", "codecov", "coveralls", "nyc", "pytest-cov"]

CONFIG_FILES = [".coveragerc", ".codecov.yml", ".coveralls.yml", "coverage.xml", "lcov.info"]
TEST_DIR_NAMES = {"test", "tests"}
WORKFLOW_DIR = ".github/workflows"

README_BADGE_PATTERN = re.compile(r"(codecov|coveralls|github\.com/.+/actions)")

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
    {"name": "Hibiki", "owner": "kyutai-labs", "repo": "hibiki"}
]

# Detection keywords
TEST_KEYWORDS = ["pytest", "unittest", "nose", "mocha", "jest", "go test", "cargo test", "ctest"]
COVERAGE_KEYWORDS = ["coverage", "--cov", "lcov", "gcov", "codecov", "coveralls", "nyc", "pytest-cov", "tarpaulin", "cargo tarpaulin", "kcov"]
CONFIG_FILES = [".coveragerc", ".codecov.yml", ".coveralls.yml", "coverage.xml", "lcov.info"]
TEST_CONFIG_FILES = ["Makefile", "tox.ini", "setup.cfg", "pyproject.toml", "package.json", "Cargo.toml"]
README_BADGE_PATTERN = re.compile(r"(codecov|coveralls|github\.com/.+/actions)")

def extract_keywords_from_file(file_path, keywords):
    found = set()
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read().lower()
            for key in keywords:
                if key.lower() in content:
                    found.add(key)
    except Exception:
        pass
    return found

def check_readme_for_badges(repo_path):
    readme_files = list(Path(repo_path).glob("README*"))
    for file in readme_files:
        try:
            content = file.read_text(encoding="utf-8", errors="ignore").lower()
            matches = README_BADGE_PATTERN.findall(content)
            return list(set(matches))
        except Exception:
            continue
    return []

def analyze_repo(path):
    results = {
        "Has Tests": "No",
        "CI Workflows Used": "No",
        "Tests in Workflow": "No",
        "Test Tools": set(),
        "Coverage Tools": set(),
        "Test Config Files": set(),
        "Extra Test Tools": set(),
        "Coverage Config Found": "No",
        "Coverage Badges": [],
        "Rust Project": "Yes" if list(Path(path).rglob("Cargo.toml")) else "No"
    }

    # Check for test folders
    for subdir in Path(path).rglob("*"):
        if subdir.is_dir() and subdir.name.lower() in {"test", "tests"}:
            results["Has Tests"] = "Yes"
            break

    # Coverage config files
    for file_name in CONFIG_FILES:
        if (Path(path) / file_name).exists():
            results["Coverage Config Found"] = "Yes"
            break

    # Test config-based inference
    for file_name in TEST_CONFIG_FILES:
        file_path = Path(path) / file_name
        if file_path.exists():
            results["Test Config Files"].add(file_name)
            results["Extra Test Tools"].update(extract_keywords_from_file(file_path, TEST_KEYWORDS + COVERAGE_KEYWORDS))

    # Check GitHub Actions workflows
    workflow_path = Path(path) / ".github" / "workflows"
    if workflow_path.exists():
        results["CI Workflows Used"] = "Yes"
        for wf_file in workflow_path.glob("*.yml"):
            results["Test Tools"].update(extract_keywords_from_file(wf_file, TEST_KEYWORDS))
            results["Coverage Tools"].update(extract_keywords_from_file(wf_file, COVERAGE_KEYWORDS))
        if results["Test Tools"]:
            results["Tests in Workflow"] = "Yes"

    # README badge detection
    results["Coverage Badges"] = check_readme_for_badges(path)
    return results

# Process all repos
summary = []
with TemporaryDirectory() as tmpdir:
    for p in projects:
        url = f"https://github.com/{p['owner']}/{p['repo']}.git"
        path = os.path.join(tmpdir, p["name"])
        try:
            print(f"🔍 Cloning {p['name']}...")
            Repo.clone_from(url, path)
            analysis = analyze_repo(path)
            summary.append({
                "Project": p["name"],
                "Repo URL": f"https://github.com/{p['owner']}/{p['repo']}",
                "Rust Project": analysis["Rust Project"],
                "Has Tests": analysis["Has Tests"],
                "CI Workflows Used": analysis["CI Workflows Used"],
                "Tests in Workflow": analysis["Tests in Workflow"],
                "Test Tools": ", ".join(analysis["Test Tools"]) or "None",
                "Coverage Tools": ", ".join(analysis["Coverage Tools"]) or "None",
                "Test Config Files": ", ".join(analysis["Test Config Files"]) or "None",
                "Extra Test Tools": ", ".join(analysis["Extra Test Tools"]) or "None",
                "Coverage Config Found": analysis["Coverage Config Found"],
                "Coverage Badges": ", ".join(analysis["Coverage Badges"]) or "None"
            })
        except Exception as e:
            print(f"❌ Failed {p['name']}: {e}")
            summary.append({
                "Project": p["name"],
                "Repo URL": url,
                "Rust Project": "Error",
                "Has Tests": "Error",
                "CI Workflows Used": "Error",
                "Tests in Workflow": "Error",
                "Test Tools": "Error",
                "Coverage Tools": "Error",
                "Test Config Files": "Error",
                "Extra Test Tools": "Error",
                "Coverage Config Found": "Error",
                "Coverage Badges": "Error"
            })

# Save to CSV
with open("ci_theater_test_tool_detection_report.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=summary[0].keys())
    writer.writeheader()
    writer.writerows(summary)

print("\n✅ Rust-aware test report saved to ci_theater_test_tool_detection_report.csv")