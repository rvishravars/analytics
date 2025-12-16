#!/usr/bin/env python3
"""
Search GitHub for open-source foundation model projects with training and testing.
Filters out example projects and finds truly open-source foundation models.
Uses GitHub token from .env file.
"""

import os
import json
import csv
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin

import requests
from dotenv import load_dotenv
from tqdm import tqdm

# Load environment variables
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN not found in .env file")

headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

# Keywords to identify foundation models
FOUNDATION_MODEL_KEYWORDS = [
    "foundation model",
    "large language model",
    "llm",
    "transformer",
    "diffusion model",
    "vision transformer",
    "vit",
    "bert",
    "gpt",
    "t5",
    "roberta",
    "xlnet",
    "electra",
    "albert",
]

# Keywords to identify training code
TRAINING_KEYWORDS = [
    "train",
    "training",
    "fine-tune",
    "finetune",
    "fine-tuning",
    "finetuning",
    "pretrain",
    "pretraining",
]

# Keywords to identify testing code
TESTING_KEYWORDS = [
    "test",
    "testing",
    "evaluate",
    "evaluation",
    "benchmark",
    "metrics",
]

# Keywords to exclude (example/demo/tutorial projects)
EXCLUDE_KEYWORDS = [
    "example",
    "demo",
    "tutorial",
    "starter",
    "template",
    "boilerplate",
    "sample",
    "playground",
    "sandbox",
    "test-project",
    "toy",
]

# Additional exclusion patterns in repo name
EXCLUDE_PATTERNS = [
    "-example",
    "-demo",
    "-tutorial",
    "_example",
    "_demo",
    "_tutorial",
]


def get_repo_files(owner: str, repo: str, timeout: int = 10) -> List[str]:
    """Get list of files in the repository."""
    try:
        url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/main?recursive=1"
        response = requests.get(url, headers=headers, timeout=timeout)
        
        if response.status_code == 404:
            # Try master branch
            url = url.replace("/main?", "/master?")
            response = requests.get(url, headers=headers, timeout=timeout)
        
        if response.status_code == 200:
            data = response.json()
            files = [item["path"].lower() for item in data.get("tree", []) if item["type"] == "blob"]
            return files
        return []
    except Exception as e:
        print(f"Error fetching files for {owner}/{repo}: {e}")
        return []


def check_for_training_code(files: List[str]) -> Tuple[bool, List[str]]:
    """Check if repository contains training code."""
    training_files = []
    for file in files:
        # Check for common training file patterns
        if any(keyword in file for keyword in TRAINING_KEYWORDS):
            training_files.append(file)
        # Check for specific training patterns
        if any(pattern in file for pattern in ["train.py", "train_", "training_"]):
            training_files.append(file)
    
    return len(training_files) > 0, training_files[:5]  # Return top 5


def check_for_testing_code(files: List[str]) -> Tuple[bool, List[str]]:
    """Check if repository contains testing code."""
    testing_files = []
    for file in files:
        # Check for test directories and files
        if "test" in file:
            testing_files.append(file)
        # Check for evaluation patterns
        if any(pattern in file for pattern in ["eval.py", "evaluate_", "benchmark_"]):
            testing_files.append(file)
    
    return len(testing_files) > 0, testing_files[:5]  # Return top 5


def is_example_project(repo_data: Dict) -> bool:
    """Check if this is an example/demo project to be filtered out."""
    name = repo_data.get("name", "").lower()
    description = (repo_data.get("description") or "").lower()
    topics = [topic.lower() for topic in repo_data.get("topics", [])]
    
    # Check name for exclusion patterns
    for pattern in EXCLUDE_PATTERNS + EXCLUDE_KEYWORDS:
        if pattern.lower() in name:
            return True
    
    # Check description for exclusion keywords
    for keyword in EXCLUDE_KEYWORDS:
        if keyword.lower() in description:
            return True
    
    # Check topics for exclusion keywords
    for keyword in EXCLUDE_KEYWORDS:
        if keyword.lower() in topics:
            return True
    
    return False


def is_foundation_model_project(repo_data: Dict, files: List[str]) -> bool:
    """Check if this is a foundation model project."""
    name = repo_data.get("name", "").lower()
    description = (repo_data.get("description") or "").lower()
    topics = [topic.lower() for topic in repo_data.get("topics", [])]
    
    # Check name, description, or topics for foundation model keywords
    text_to_search = f"{name} {description} {' '.join(topics)}"
    
    for keyword in FOUNDATION_MODEL_KEYWORDS:
        if keyword.lower() in text_to_search:
            return True
    
    # Check if there are common DL framework files (indicates ML project)
    ml_frameworks = ["pytorch", "tensorflow", "transformers", "huggingface"]
    for file in files:
        for framework in ml_frameworks:
            if framework in file:
                return True
    
    return False


def search_github_repositories() -> List[Dict]:
    """Search GitHub for foundation model projects with training and testing."""
    
    # GitHub search query for foundation model projects
    # Using separate queries to avoid license filter issues
    queries = [
        'language:python transformer stars:>50',
        'language:python "large language model" stars:>50',
        'language:python llm stars:>50',
        'language:python "diffusion model" stars:>50',
    ]
    
    for q in queries:
        print(f"  - {q}")
    
    url = "https://api.github.com/search/repositories"
    all_repos = []
    seen_repos = set()
    
    for query in queries:
        if len(all_repos) >= 500:
            break
            
        params = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": 100,
            "page": 1,
        }
        
        while len(all_repos) < 500:
            try:
                response = requests.get(url, headers=headers, params=params, timeout=10)
                
                if response.status_code != 200:
                    print(f"Error: {response.status_code} - {response.text}")
                    break
                
                data = response.json()
                repos = data.get("items", [])
                
                if not repos:
                    break
                
                for repo in tqdm(repos, desc=f"Processing query: {query[:50]}..., page {params['page']}"):
                    repo_key = f"{repo['owner']['login']}/{repo['name']}"
                    
                    if repo_key in seen_repos:
                        continue
                    seen_repos.add(repo_key)
                    
                    # Filter out example projects
                    if is_example_project(repo):
                        continue
                    
                    # Check if it's a foundation model project
                    files = get_repo_files(repo["owner"]["login"], repo["name"])
                    
                    if not is_foundation_model_project(repo, files):
                        continue
                    
                    # Check for training code
                    has_training, training_files = check_for_training_code(files)
                    
                    # Check for testing code
                    has_testing, testing_files = check_for_testing_code(files)
                    
                    # Only include if has both training and testing
                    if has_training and has_testing:
                        repo_info = {
                            "name": repo["name"],
                            "owner": repo["owner"]["login"],
                            "url": repo["html_url"],
                            "stars": repo["stargazers_count"],
                            "forks": repo["forks_count"],
                            "description": repo["description"],
                            "topics": repo.get("topics", []),
                            "language": repo["language"],
                            "created_at": repo["created_at"],
                            "updated_at": repo["updated_at"],
                            "has_training": has_training,
                            "training_files_sample": training_files,
                            "has_testing": has_testing,
                            "testing_files_sample": testing_files,
                            "open_issues": repo["open_issues_count"],
                            "license": repo.get("license", {}).get("name", "Unknown") if repo.get("license") else "Unknown",
                        }
                        all_repos.append(repo_info)
                        print(f"✓ Found: {repo['owner']['login']}/{repo['name']} ({repo['stargazers_count']} stars)")
                
                params["page"] += 1
                
                # Check if we've reached the end
                if len(repos) < 100:
                    break
                    
            except Exception as e:
                print(f"Error during search: {e}")
                break
    
    return all_repos


def save_results(repos: List[Dict], output_file: str = "foundation_models_with_training_testing.json"):
    """Save results to JSON and CSV files."""
    
    # Save as JSON
    with open(output_file, "w") as f:
        json.dump(repos, f, indent=2)
    print(f"\nSaved {len(repos)} repositories to {output_file}")
    
    # Save as CSV
    csv_file = output_file.replace(".json", ".csv")
    if repos:
        with open(csv_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=repos[0].keys())
            writer.writeheader()
            writer.writerows(repos)
        print(f"Saved {len(repos)} repositories to {csv_file}")


def print_summary(repos: List[Dict]):
    """Print summary statistics."""
    print("\n" + "="*80)
    print(f"SUMMARY: Found {len(repos)} Foundation Model Projects")
    print("="*80)
    
    if not repos:
        print("No repositories found matching the criteria.")
        return
    
    # Sort by stars
    repos_sorted = sorted(repos, key=lambda x: x["stars"], reverse=True)
    
    print("\nTop 10 by Stars:")
    print("-" * 80)
    for i, repo in enumerate(repos_sorted[:10], 1):
        print(f"{i}. {repo['owner']}/{repo['name']}")
        print(f"   Stars: {repo['stars']} | Forks: {repo['forks']} | License: {repo['license']}")
        print(f"   URL: {repo['url']}")
        print(f"   Description: {repo['description'][:80] if repo['description'] else 'N/A'}...")
        print()
    
    # Statistics
    print("\nStatistics:")
    print("-" * 80)
    total_stars = sum(repo["stars"] for repo in repos)
    total_forks = sum(repo["forks"] for repo in repos)
    avg_stars = total_stars / len(repos) if repos else 0
    avg_forks = total_forks / len(repos) if repos else 0
    
    print(f"Total repositories: {len(repos)}")
    print(f"Total stars: {total_stars:,}")
    print(f"Total forks: {total_forks:,}")
    print(f"Average stars per repo: {avg_stars:.0f}")
    print(f"Average forks per repo: {avg_forks:.0f}")
    
    # License distribution
    licenses = {}
    for repo in repos:
        license = repo["license"]
        licenses[license] = licenses.get(license, 0) + 1
    
    print("\nLicense Distribution:")
    for license, count in sorted(licenses.items(), key=lambda x: x[1], reverse=True):
        print(f"  {license}: {count}")
    
    # Topics distribution
    print("\nTop Topics:")
    topics_count = {}
    for repo in repos:
        for topic in repo["topics"]:
            topics_count[topic] = topics_count.get(topic, 0) + 1
    
    for topic, count in sorted(topics_count.items(), key=lambda x: x[1], reverse=True)[:15]:
        print(f"  {topic}: {count}")


if __name__ == "__main__":
    print("Foundation Model Project Search")
    print("=" * 80)
    print(f"GitHub Token: {GITHUB_TOKEN[:20]}...{GITHUB_TOKEN[-5:]}")
    print()
    
    # Search for repositories
    repos = search_github_repositories()
    
    # Save results
    save_results(repos)
    
    # Print summary
    print_summary(repos)
