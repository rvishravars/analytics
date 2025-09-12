#!/usr/bin/env python3
import os
import re
import json
import csv
import shutil
import time
import subprocess
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor, as_completed

from git import Repo, GitCommandError
from tabulate import tabulate
from dotenv import load_dotenv

# --- NEW: import flat list of "owner/repo" slugs ---
# rust_repos_100_percent.py must define: projects = ["owner/repo", ...]
from rust_repos_100_percent import projects as repo_slugs

# ----------------------- Config -----------------------
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    print("⚠️  GITHUB_TOKEN not found in .env file. Git operations will be unauthenticated and may be rate-limited.")

MAX_WORKERS = 5
CLOC_TIMEOUT_SEC = 120  # per repo
IGNORED_LANGS = set()   # e.g. {"Text","Markdown","JSON","YAML","TOML","HTML"}

# --------------------- Helpers ------------------------
def safe_dirname(s: str) -> str:
    """Make a filesystem-safe folder name."""
    s = s.strip().replace(" ", "_")
    return re.sub(r"[^A-Za-z0-9._-]", "_", s)

def categorize_project(sloc: int) -> str:
    if sloc < 1000:
        return "Very Small"
    elif sloc < 10000:
        return "Small"
    elif sloc < 100000:
        return "Medium"
    elif sloc < 1000000:
        return "Large"
    else:
        return "Very Large"

def run_cloc(path: str, timeout=CLOC_TIMEOUT_SEC) -> dict:
    """
    Run cloc and return parsed JSON. Restricted to Rust only.
    """
    try:
        out = subprocess.check_output(
            ["cloc", "--json", "--include-lang=Rust", path],  # 👈 only Rust
            text=True,
            timeout=timeout,
            stderr=subprocess.STDOUT
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"cloc timeout after {timeout}s")
    except subprocess.CalledProcessError as e:
        out = e.output

    s = out.strip()
    i = s.find("{")
    if i > 0:
        s = s[i:]
    try:
        return json.loads(s)
    except json.JSONDecodeError as je:
        preview = "\n".join(s.splitlines()[:10])
        raise RuntimeError(f"cloc JSON parse error: {je}\n--- preview ---\n{preview}\n--------------")

def extract_rust_sloc(cloc_data: dict) -> tuple[int, list[str]]:
    """Extracts Rust SLOC from cloc data and creates a summary string."""
    rust_stats = cloc_data.get("Rust", {})
    sloc = int(rust_stats.get("code", 0)) if isinstance(rust_stats, dict) else 0
    language_summary = [f"Rust ({sloc})"] if sloc else []
    return sloc, language_summary

def shallow_clone(url: str, dest: str, max_retries: int = 3) -> None:
    """
    Shallow clone with GitPython, with options to reduce data.
    Retries on transient network errors.
    """
    last_exception = None
    for attempt in range(max_retries):
        try:
            Repo.clone_from(url, dest, multi_options=["--depth=1", "--no-tags"])
            return  # Success
        except GitCommandError as e:
            last_exception = e
            # Check for common transient network errors before retrying
            if "Failed to connect" in str(e) or "Could not resolve host" in str(e):
                wait = 2 ** attempt  # Exponential backoff: 1, 2, 4 seconds
                print(f"  [warn] Clone failed for {url} (attempt {attempt + 1}/{max_retries}), retrying in {wait}s... Reason: {str(e).splitlines()[-1].strip()}")
                time.sleep(wait)
                # IMPORTANT: Clean up the failed clone directory before retrying
                if os.path.exists(dest):
                    shutil.rmtree(dest)
                continue
            raise e
    raise last_exception

# ----------------- NEW: adapter for flat slugs -----------------
def _parse_slug(slug: str) -> tuple[str, str]:
    """
    Validate and normalize an 'owner/repo' slug.
    Returns (owner, repo_name).
    """
    s = slug.strip().strip("/")
    if "/" not in s:
        raise ValueError(f"Invalid repo slug '{slug}'. Expected 'owner/repo'.")
    owner, repo = s.split("/", 1)
    owner = owner.strip()
    repo = repo.strip()
    if not owner or not repo:
        raise ValueError(f"Invalid repo slug '{slug}'. Expected 'owner/repo'.")
    return owner, repo

def convert_slugs_to_project_dicts(slugs: list[str]) -> list[dict]:
    """
    Convert flat 'owner/repo' strings into dicts compatible with the old code:
    { "name": <owner/repo>, "repo": <owner/repo> }
    (We no longer have separate owner/name fields in the input.)
    Also de-duplicates case-insensitively.
    """
    seen_slugs = set()
    project_dicts = []
    for slug in slugs:
        owner, repo_name = _parse_slug(slug)
        full_slug = f"{owner}/{repo_name}"
        normalized_slug = full_slug.lower()
        if normalized_slug in seen_slugs:
            continue
        seen_slugs.add(normalized_slug)
        project_dicts.append({
            "name": full_slug,   # keep column 'name' readable
            "repo": full_slug,   # used below to construct the URL
        })
    return project_dicts

# Build the adapted projects list once
projects = convert_slugs_to_project_dicts(repo_slugs)

# --------------------- Processing ---------------------
def process_repository(project: dict, base_tmpdir: str) -> dict | None:
    """
    project dict expects:
      - project["name"]: display name (we'll use 'owner/repo')
      - project["repo"]: 'owner/repo' slug
    """
    name = project["name"]
    repo_full = project["repo"]
    # Use the token for authentication to avoid strict unauthenticated rate limits.
    if GITHUB_TOKEN:
        url = f"https://oauth2:{GITHUB_TOKEN}@github.com/{repo_full}"
    else:
        url = f"https://github.com/{repo_full}"

    try:
        with TemporaryDirectory() as tmpdir:
            dest = os.path.join(tmpdir, safe_dirname(repo_full))
            print(f"[clone] {repo_full}")
            shallow_clone(url, dest)

            cloc_data = run_cloc(dest)
            sloc, languages_list = extract_rust_sloc(cloc_data)

            if sloc == 0:
                return None  # 👈 drop non-Rust repos

            return {
                "name": name,
                "SLOC": sloc,
                "Category": categorize_project(sloc),
                "Languages": ", ".join(languages_list),
            }

    except Exception as e:
        print(f"[error] {name}: {e}")
        return None

# ---------------------- Main flow ---------------------
def main():
    if not projects:
        print("No repositories found. Ensure rust_repos_100_percent.py defines 'projects = [\"owner/repo\", ...]'.")
        return

    results = []

    with TemporaryDirectory() as tmpdir:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = [pool.submit(process_repository, proj, tmpdir) for proj in projects]
            for future in as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)

    # Stable sort by SLOC (errors at bottom)
    def sort_key(r):
        return (1, 0) if r["SLOC"] == "N/A" else (0, -int(r["SLOC"]))
    results.sort(key=sort_key)

    # Console table
    print(tabulate(results, headers="keys", tablefmt="grid"))

    # Ensure data dir exists
    os.makedirs("data", exist_ok=True)

    # Write CSV
    output_csv_path = "data/19_rust_sloc.csv"
    with open(output_csv_path, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["name", "SLOC", "Category", "Languages"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nResults written to {output_csv_path}")

if __name__ == "__main__":
    main()
