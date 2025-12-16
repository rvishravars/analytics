#!/usr/bin/env python3
"""
Analyze foundation model repositories to determine which ones run training in CI.
Checks GitHub Actions workflows, Travis CI, and other CI configurations for training commands.
"""

import os
import json
import re
import base64
from typing import Dict, List, Tuple
from collections import defaultdict

import requests
from dotenv import load_dotenv
from tqdm import tqdm

# Load environment variables
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN not found in .env file")

headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}


def get_workflow_content(owner: str, repo: str, workflow_path: str, timeout: int = 10) -> str:
    """Get the content of a workflow file."""
    try:
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{workflow_path}"
        response = requests.get(url, headers=headers, timeout=timeout)
        
        if response.status_code == 200:
            content = response.json().get("content", "")
            if content:
                try:
                    return base64.b64decode(content).decode('utf-8', errors='ignore')
                except:
                    return ""
        return ""
    except Exception as e:
        return ""


def get_github_workflows(owner: str, repo: str, timeout: int = 10) -> List[Dict]:
    """Get all GitHub Actions workflow files."""
    try:
        url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/main?recursive=1"
        response = requests.get(url, headers=headers, timeout=timeout)
        
        if response.status_code == 404:
            url = url.replace("/main?", "/master?")
            response = requests.get(url, headers=headers, timeout=timeout)
        
        workflows = []
        if response.status_code == 200:
            data = response.json()
            for item in data.get("tree", []):
                if ".github/workflows" in item["path"] and item["path"].endswith((".yml", ".yaml")):
                    workflows.append({
                        "path": item["path"],
                        "url": item.get("url")
                    })
        
        return workflows
    except Exception as e:
        return []


def check_training_in_workflow(workflow_content: str) -> Tuple[bool, List[str], List[str]]:
    """Check if a workflow file contains training commands."""
    
    # Keywords that indicate training is happening
    training_keywords = [
        r"python.*train",
        r"python.*\.py\s+--train",
        r"python\s+train\.py",
        r"python\s+-m.*train",
        r"python.*finetune",
        r"python.*fine-tune",
        r"python.*pretrain",
        r"torchrun.*train",
        r"torch\.distributed",
        r"accelerate.*launch.*train",
        r"deepspeed.*train",
        r"python\s+.*trainer",
        r"python.*fit\(",
        r"model\.train\(",
    ]
    
    # Keywords that indicate testing/inference (not training)
    test_keywords = [
        r"pytest",
        r"python.*test",
        r"python.*eval",
        r"python.*inference",
        r"python.*predict",
    ]
    
    has_training = False
    training_commands = []
    test_commands = []
    
    # Look for training patterns
    for keyword_pattern in training_keywords:
        matches = re.findall(f".*{keyword_pattern}.*", workflow_content, re.IGNORECASE | re.MULTILINE)
        if matches:
            has_training = True
            for match in matches[:3]:  # Get top 3 matches
                clean_match = match.strip()
                if clean_match and len(clean_match) < 200:
                    training_commands.append(clean_match)
    
    # Look for test patterns
    for keyword_pattern in test_keywords:
        matches = re.findall(f".*{keyword_pattern}.*", workflow_content, re.IGNORECASE | re.MULTILINE)
        if matches:
            for match in matches[:2]:
                clean_match = match.strip()
                if clean_match and len(clean_match) < 200:
                    test_commands.append(clean_match)
    
    return has_training, training_commands, test_commands


def check_travis_ci(owner: str, repo: str, timeout: int = 10) -> Tuple[bool, List[str]]:
    """Check .travis.yml for training commands."""
    try:
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/.travis.yml"
        response = requests.get(url, headers=headers, timeout=timeout)
        
        if response.status_code == 200:
            content = response.json().get("content", "")
            if content:
                try:
                    travis_content = base64.b64decode(content).decode('utf-8', errors='ignore')
                    
                    training_patterns = [
                        r"python.*train",
                        r"python\s+train\.py",
                        r"python.*finetune",
                        r"torchrun.*train",
                    ]
                    
                    has_training = False
                    commands = []
                    
                    for pattern in training_patterns:
                        matches = re.findall(f".*{pattern}.*", travis_content, re.IGNORECASE | re.MULTILINE)
                        if matches:
                            has_training = True
                            commands.extend([m.strip() for m in matches[:2]])
                    
                    return has_training, commands
                except:
                    pass
        
        return False, []
    except:
        return False, []


def analyze_training_in_ci(repo_data: Dict) -> Dict:
    """Analyze if training is run in CI for a repository."""
    owner = repo_data["owner"]
    name = repo_data["name"]
    repo_key = f"{owner}/{name}"
    
    result = {
        "repo": repo_key,
        "stars": repo_data["stars"],
        "has_github_actions": False,
        "runs_training_in_ga": False,
        "training_workflows": [],
        "training_commands_ga": [],
        "has_travis_ci": False,
        "runs_training_in_travis": False,
        "training_commands_travis": [],
        "has_ci": False,
    }
    
    # Check GitHub Actions workflows
    workflows = get_github_workflows(owner, name)
    if workflows:
        result["has_github_actions"] = True
        result["has_ci"] = True
        
        for workflow in workflows:
            content = get_workflow_content(owner, name, workflow["path"])
            if content:
                has_training, training_cmds, test_cmds = check_training_in_workflow(content)
                if has_training:
                    result["runs_training_in_ga"] = True
                    result["training_workflows"].append(workflow["path"].split("/")[-1])
                    result["training_commands_ga"].extend(training_cmds[:2])
    
    # Check Travis CI
    has_travis, travis_cmds = check_travis_ci(owner, name)
    if has_travis:
        result["has_travis_ci"] = True
        result["has_ci"] = True
        result["runs_training_in_travis"] = True
        result["training_commands_travis"] = travis_cmds
    
    return result


def main():
    """Main function to analyze training in CI."""
    
    # Load true foundation models
    with open("foundation_models_true_only.json", "r") as f:
        foundation_models = json.load(f)
    
    print("\n" + "="*80)
    print("ANALYZING TRAINING IN CI FOR 71 FOUNDATION MODELS")
    print("="*80)
    print()
    
    ci_analysis_results = []
    
    for repo_data in tqdm(foundation_models, desc="Analyzing CI training"):
        try:
            result = analyze_training_in_ci(repo_data)
            ci_analysis_results.append(result)
        except Exception as e:
            print(f"  Error analyzing {repo_data['owner']}/{repo_data['name']}: {e}")
            continue
    
    # Save results
    with open("training_ci_analysis.json", "w") as f:
        json.dump(ci_analysis_results, f, indent=2)
    
    # Calculate statistics
    has_ci = sum(1 for r in ci_analysis_results if r["has_ci"])
    runs_training = sum(1 for r in ci_analysis_results if r["runs_training_in_ga"] or r["runs_training_in_travis"])
    has_ga = sum(1 for r in ci_analysis_results if r["has_github_actions"])
    runs_training_ga = sum(1 for r in ci_analysis_results if r["runs_training_in_ga"])
    has_travis = sum(1 for r in ci_analysis_results if r["has_travis_ci"])
    runs_training_travis = sum(1 for r in ci_analysis_results if r["runs_training_in_travis"])
    
    print(f"\n✓ Analyzed {len(ci_analysis_results)} repositories")
    print(f"✓ Saved to training_ci_analysis.json")
    
    # Print summary
    print("\n" + "="*80)
    print("TRAINING IN CI ANALYSIS SUMMARY")
    print("="*80)
    
    print(f"\n📊 OVERALL STATISTICS:")
    print(f"  Total foundation models: {len(ci_analysis_results)}")
    print(f"  Have CI configured: {has_ci}/71 ({100*has_ci/71:.1f}%)")
    print(f"  Run training in CI: {runs_training}/71 ({100*runs_training/71:.1f}%)")
    
    print(f"\n🔧 CI SYSTEM BREAKDOWN:")
    print(f"  GitHub Actions:")
    print(f"    - Have workflows: {has_ga}/71 ({100*has_ga/71:.1f}%)")
    print(f"    - Run training: {runs_training_ga}/71 ({100*runs_training_ga/71:.1f}%)")
    print(f"  Travis CI:")
    print(f"    - Configured: {has_travis}/71 ({100*has_travis/71:.1f}%)")
    print(f"    - Run training: {runs_training_travis}/71 ({100*runs_training_travis/71:.1f}%)")
    
    # Top repos with training in CI
    training_repos = sorted(
        [r for r in ci_analysis_results if r["runs_training_in_ga"] or r["runs_training_in_travis"]],
        key=lambda x: x["stars"],
        reverse=True
    )
    
    print(f"\n⭐ TOP REPOS RUNNING TRAINING IN CI:")
    print("-"*80)
    for i, repo in enumerate(training_repos[:15], 1):
        ci_type = "GA" if repo["runs_training_in_ga"] else "Travis"
        print(f"{i:2d}. {repo['repo']:45s} {repo['stars']:8,} stars ({ci_type})")
    
    if len(training_repos) > 15:
        print(f"    ... and {len(training_repos) - 15} more")
    
    # Repos with CI but no training
    no_training_repos = sorted(
        [r for r in ci_analysis_results if r["has_ci"] and not (r["runs_training_in_ga"] or r["runs_training_in_travis"])],
        key=lambda x: x["stars"],
        reverse=True
    )
    
    print(f"\n⚠️  REPOS WITH CI BUT NO TRAINING ({len(no_training_repos)}):")
    print("-"*80)
    for i, repo in enumerate(no_training_repos[:10], 1):
        print(f"{i:2d}. {repo['repo']:45s} {repo['stars']:8,} stars")
    
    if len(no_training_repos) > 10:
        print(f"    ... and {len(no_training_repos) - 10} more")
    
    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    main()
