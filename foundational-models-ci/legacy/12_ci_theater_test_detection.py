import os
import re
import csv
import subprocess
from git import Repo
from pathlib import Path
from tempfile import TemporaryDirectory

from ci_foundation_projects import projects  # Assumes you have a 'projects' list with 'owner', 'repo', 'name'

# Detection keywords
TEST_KEYWORDS = ["pytest", "unittest", "nose", "mocha", "jest", "go test", "cargo test", "ctest"]
COVERAGE_KEYWORDS = ["coverage", "--cov", "lcov", "gcov", "codecov", "coveralls", "nyc", "pytest-cov", "tarpaulin", "cargo tarpaulin", "kcov"]
CONFIG_FILES = [".coveragerc", ".codecov.yml", ".coveralls.yml", "coverage.xml", "lcov.info"]
TEST_CONFIG_FILES = ["Makefile", "tox.ini", "setup.cfg", "pyproject.toml", "package.json", "Cargo.toml"]
README_BADGE_PATTERN = re.compile(r"(codecov|coveralls|github\.com/.+/actions)")
TEST_DIR_NAMES = {"test", "tests"}

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
        "CI System": "None",
        "Tests in Workflow": "No",
        "Test Tools": set(),
        "Coverage Tools": set(),
        "Test Config Files": set(),
        "Extra Test Tools": set(),
        "Coverage Config Found": "No",
        "Coverage Badges": []
    }

    # Check for test folders
    for subdir in Path(path).rglob("*"):
        if subdir.is_dir() and subdir.name.lower() in TEST_DIR_NAMES:
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

    ci_detected = []

    # GitHub Actions
    workflow_path = Path(path) / ".github" / "workflows"
    if workflow_path.exists():
        ci_detected.append("GitHub Actions")
        results["CI Workflows Used"] = "Yes"
        for wf_file in workflow_path.glob("*.yml"):
            results["Test Tools"].update(extract_keywords_from_file(wf_file, TEST_KEYWORDS))
            results["Coverage Tools"].update(extract_keywords_from_file(wf_file, COVERAGE_KEYWORDS))
        if results["Test Tools"]:
            results["Tests in Workflow"] = "Yes"

    # Travis CI
    travis_file = Path(path) / ".travis.yml"
    if travis_file.exists():
        ci_detected.append("Travis CI")
        results["CI Workflows Used"] = "Yes"
        results["Test Tools"].update(extract_keywords_from_file(travis_file, TEST_KEYWORDS))
        results["Coverage Tools"].update(extract_keywords_from_file(travis_file, COVERAGE_KEYWORDS))
        if results["Test Tools"]:
            results["Tests in Workflow"] = "Yes"

    # CircleCI
    circleci_config = Path(path) / ".circleci" / "config.yml"
    if circleci_config.exists():
        ci_detected.append("CircleCI")
        results["CI Workflows Used"] = "Yes"
        results["Test Tools"].update(extract_keywords_from_file(circleci_config, TEST_KEYWORDS))
        results["Coverage Tools"].update(extract_keywords_from_file(circleci_config, COVERAGE_KEYWORDS))
        if results["Test Tools"]:
            results["Tests in Workflow"] = "Yes"

    # GitLab CI
    gitlab_ci_file = Path(path) / ".gitlab-ci.yml"
    if gitlab_ci_file.exists():
        ci_detected.append("GitLab CI")
        results["CI Workflows Used"] = "Yes"
        results["Test Tools"].update(extract_keywords_from_file(gitlab_ci_file, TEST_KEYWORDS))
        results["Coverage Tools"].update(extract_keywords_from_file(gitlab_ci_file, COVERAGE_KEYWORDS))
        if results["Test Tools"]:
            results["Tests in Workflow"] = "Yes"

    results["CI System"] = " + ".join(ci_detected) if ci_detected else "None"

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
                "Has Tests": analysis["Has Tests"],
                "CI Workflows Used": analysis["CI Workflows Used"],
                "CI System": analysis["CI System"],
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
                "Has Tests": "Error",
                "CI Workflows Used": "Error",
                "CI System": "Error",
                "Tests in Workflow": "Error",
                "Test Tools": "Error",
                "Coverage Tools": "Error",
                "Test Config Files": "Error",
                "Extra Test Tools": "Error",
                "Coverage Config Found": "Error",
                "Coverage Badges": "Error"
            })

# Save to CSV
output_path = "data/12_ci_theater_test_tool_detection_report.csv"
os.makedirs("data", exist_ok=True)
with open(output_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=summary[0].keys())
    writer.writeheader()
    writer.writerows(summary)

print(f"\n✅ Report saved to {output_path}")
