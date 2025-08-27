#!/usr/bin/env python3
import os
import re
import json
import csv
import time
import subprocess
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor, as_completed

from git import Repo, GitCommandError
from tabulate import tabulate

from ci_rust_projects import projects  # expects projects = [{name, owner, repo}, ...]

# ----------------------- Config -----------------------
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

def compute_sloc_and_langs(cloc_data: dict) -> tuple[int, list[str]]:
    rust = cloc_data.get("Rust", {})
    code = int(rust.get("code", 0)) if isinstance(rust, dict) else 0
    return code, ([f"Rust ({code})"] if code else [])

def shallow_clone(url: str, dest: str) -> None:
    """
    Shallow clone with GitPython, with options to reduce data.
    Retries once on transient errors.
    """
    try:
        Repo.clone_from(url, dest, multi_options=["--depth=1", "--no-tags"])
        return
    except GitCommandError as e:
        # Retry once after small delay
        time.sleep(1.5)
        Repo.clone_from(url, dest, multi_options=["--depth=1", "--no-tags"])

def process_one(project: dict, base_tmpdir: str) -> dict:
    name = project["name"]
    repo_full = project["repo"]
    url = f"https://github.com/{repo_full}"

    try:
        with TemporaryDirectory() as tmpdir:
            dest = os.path.join(tmpdir, safe_dirname(repo_full))
            print(f"[clone] {repo_full}")
            shallow_clone(url, dest)

            cloc_data = run_cloc(dest)
            sloc, languages_list = compute_sloc_and_langs(cloc_data)

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
    results = []

    with TemporaryDirectory() as tmpdir:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futs = [pool.submit(process_one, proj, tmpdir) for proj in projects]
            for fut in as_completed(futs):
                r = fut.result()
                if r:
                    results.append(r)

    # Stable sort by SLOC (errors at bottom)
    def sort_key(r):
        return (1, 0) if r["SLOC"] == "N/A" else (0, -int(r["SLOC"]))
    results.sort(key=sort_key)

    # Console table
    print(tabulate(results, headers="keys", tablefmt="grid"))

    # Ensure data dir exists
    os.makedirs("data", exist_ok=True)

    # Write CSV
    out_csv = "data/19_ci_theater_project_sizes_rust.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["name", "SLOC", "Category", "Languages"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nResults written to {out_csv}")

if __name__ == "__main__":
    main()
