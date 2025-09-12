#!/usr/bin/env python3
"""
Analyzer for Rust repositories based on language share:
- Clones each repo (shallow, depth=1)
- Runs `cloc --json` on the whole repo
- Filters non-programming/aux types via IGNORED_LANGS
- Produces cohorts based on Rust's share of SLOC:
    1) ALL Rust repos (Rust detected at all)
    2) Polyglot Rust repos (50% <= Rust SLOC < 100%)
    3) Monoglot Rust repos (100% Rust SLOC)
- Writes summary CSVs for each, plus long per-language breakdowns
- Prints a quick console table for the polyglot subset

Outputs (in ./data):
- 29a_all_rust_repos_summary.csv
- 29a_all_rust_repos_by_language.csv
- 29a_polyglot_rust_repos_summary.csv
- 29a_polyglot_rust_repos_by_language.csv
- 29a_monoglot_rust_repos_summary.csv
- 29a_monoglot_rust_repos_by_language.csv

Requires: cloc, GitPython, tabulate
"""
import os
import re
import json
import csv
import time
import shutil
import subprocess
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor, as_completed

from git import Repo, GitCommandError
from tabulate import tabulate
from dotenv import load_dotenv

from ci_rust_projects import projects  # expects projects = [{name, owner, repo}, ...]

# ----------------------- Config -----------------------
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    print("⚠️  GITHUB_TOKEN not found in .env file. Git operations will be unauthenticated and may be rate-limited.")

MAX_WORKERS = 5
CLOC_TIMEOUT_SEC = 150  # per repo

# Treat these as non-programming or not useful for polyglot signal
# (tweak to your taste)
IGNORED_LANGS = {
    "Markdown", "RMarkdown", "XML", "HTML", "SVG", "TeX", "LaTeX",
    "Org", "AsciiDoc", "Text", "Plain Text", "JSON", "YAML", "TOML", "INI",
    "CSV", "TSV", "Properties", "Dos Batch", "DOS Batch", "PowerShell Profile",
    "CMake", "CMakeLists.txt", "Git Attributes", "Git Config", "Dockerfile",
    "Makefile", "Ninja", "Bourne Shell", "BASH", "Zsh", "Fish",
    "Protocol Buffers", "Protobuf", "GraphQL", "Thrift", "Cap'n Proto",
    "reStructuredText", "Sphinx", "Doxygen", "RobotFramework",
    # add anything noisy you want excluded
}

TOP_LANGS_N = 5  # how many top languages to show in summary column

# --------------------- Helpers ------------------------
def safe_dirname(s: str) -> str:
    s = s.strip().replace(" ", "_")
    return re.sub(r"[^A-Za-z0-9._-]", "_", s)


def run_cloc(path: str, timeout=CLOC_TIMEOUT_SEC) -> dict:
    """Run cloc and return parsed JSON (all languages)."""
    try:
        out = subprocess.check_output(
            ["cloc", "--json", path],
            text=True,
            timeout=timeout,
            stderr=subprocess.STDOUT,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"cloc timeout after {timeout}s")
    except subprocess.CalledProcessError as e:
        out = e.output

    s = out.strip()
    start_idx = s.find("{")
    end_idx = s.rfind("}")

    if start_idx == -1 or end_idx == -1 or end_idx < start_idx:
        raise RuntimeError(f"Could not find a valid JSON object in cloc output.\n--- preview ---\n{s[:1000]}\n--------------")

    json_str = s[start_idx : end_idx + 1]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as je:
        preview = "".join(json_str.splitlines()[:20])
        raise RuntimeError(f"cloc JSON parse error: {je}\n--- preview ---\n{preview}\n--------------")


def extract_lang_sloc(cloc_data: dict) -> dict:
    """Return {language: sloc} after filtering out IGNORED_LANGS."""
    lang_sloc = {}
    for lang, stats in cloc_data.items():
        if lang in ("header", "SUM"):
            continue
        if lang in IGNORED_LANGS:
            continue
        if not isinstance(stats, dict):
            continue
        code = int(stats.get("code", 0))
        if code > 0:
            lang_sloc[lang] = code
    return lang_sloc


def is_rust_present(lang_sloc: dict) -> bool:
    return lang_sloc.get("Rust", 0) > 0


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


def summarize_top_langs(lang_sloc: dict, n: int = TOP_LANGS_N) -> str:
    items = sorted(lang_sloc.items(), key=lambda kv: kv[1], reverse=True)[:n]
    return ", ".join([f"{k} ({v})" for k, v in items])


def create_summary_row(name: str, repo_full: str, lang_sloc: dict) -> dict:
    total = sum(lang_sloc.values())
    rust = lang_sloc.get("Rust", 0)
    return {
        "name": name,
        "repo": repo_full,
        "total_sloc": total,
        "rust_sloc": rust,
        "rust_share_pct": round(100.0 * rust / total, 2) if total else 0.0,
        "num_langs": len(lang_sloc),
        "top_langs": summarize_top_langs(lang_sloc, TOP_LANGS_N),
        "languages_json": json.dumps(lang_sloc, sort_keys=True),
    }


def process_repository(project: dict, base_tmpdir: str) -> dict | None:
    name = project.get("name") or project.get("repo")
    repo_full = project["repo"]  # e.g. owner/name
    # Use the token for authentication to avoid strict unauthenticated rate limits.
    if GITHUB_TOKEN:
        url = f"https://oauth2:{GITHUB_TOKEN}@github.com/{repo_full}"
    else:
        url = f"https://github.com/{repo_full}"

    try:
        with TemporaryDirectory(dir=base_tmpdir) as tmpdir:
            dest = os.path.join(tmpdir, safe_dirname(repo_full))
            print(f"[clone] {repo_full}")
            shallow_clone(url, dest)

            cloc_data = run_cloc(dest)
            lang_sloc = extract_lang_sloc(cloc_data)

            if not is_rust_present(lang_sloc):
                return None  # drop repos with no Rust detected

            summary_row = create_summary_row(name, repo_full, lang_sloc)
            # also return exploded language rows
            long_format_rows = [
                {"name": name, "repo": repo_full, "language": lang, "sloc": sloc}
                for lang, sloc in lang_sloc.items()
            ]
            return {"summary": summary_row, "long": long_format_rows}

    except Exception as e:
        print(f"[error] {name}: {e}")
        return None

def main():
    summary_rows = []          # all Rust repos
    long_format_all_rows = []           # per-language for all

    with TemporaryDirectory() as base_tmpdir:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = [pool.submit(process_repository, proj, base_tmpdir) for proj in projects]
            for future in as_completed(futures):
                result = future.result()
                if result:
                    summary_rows.append(result["summary"])
                    long_format_all_rows.extend(result["long"])

    if not summary_rows:
        print("No repositories with Rust detected.")
        return

    os.makedirs("data", exist_ok=True)

    # --- Partition data into cohorts based on Rust share ---
    all_summary_rows = summary_rows

    # Monoglot: 100% Rust
    monoglot_summary_rows = [
        row for row in summary_rows if row["rust_share_pct"] == 100.0
    ]

    # Polyglot: 50% <= Rust share < 100%
    polyglot_summary_rows = [
        row for row in summary_rows if 50.0 <= row["rust_share_pct"] < 100.0
    ]

    def filter_long_format_rows(summary_subset):
        repos_subset = set(row["repo"] for row in summary_subset)
        return [r for r in long_format_all_rows if r["repo"] in repos_subset]

    long_format_polyglot_rows = filter_long_format_rows(polyglot_summary_rows)
    long_format_monoglot_rows = filter_long_format_rows(monoglot_summary_rows)

    def write_csv(path, rows, fieldnames):
        if not rows:
            print(f"ℹ️ No data for {path}, skipping.")
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"✅ Wrote {len(rows)} rows to {path}")

    summary_fields = ["name", "repo", "total_sloc", "rust_sloc", "rust_share_pct", "num_langs", "top_langs", "languages_json"]
    long_fields = ["name", "repo", "language", "sloc"]

    write_csv("data/29a_all_rust_repos_summary.csv", all_summary_rows, summary_fields)
    write_csv("data/29a_all_rust_repos_by_language.csv", long_format_all_rows, long_fields)

    write_csv("data/29a_polyglot_rust_repos_summary.csv", polyglot_summary_rows, summary_fields)
    write_csv("data/29a_polyglot_rust_repos_by_language.csv", long_format_polyglot_rows, long_fields)

    write_csv("data/29a_monoglot_rust_repos_summary.csv", monoglot_summary_rows, summary_fields)
    write_csv("data/29a_monoglot_rust_repos_by_language.csv", long_format_monoglot_rows, long_fields)

    if polyglot_summary_rows:
        print("\n--- Polyglot Rust repos (50% <= Rust SLOC < 100%) ---")
        polyglot_rows_sorted = sorted(polyglot_summary_rows, key=lambda x: (-int(x["total_sloc"]), x["name"]))
        print(tabulate(polyglot_rows_sorted[:25], headers="keys", tablefmt="grid"))

    if monoglot_summary_rows:
        print("\n--- Monoglot Rust repos (100% Rust SLOC) ---")
        monoglot_rows_sorted = sorted(monoglot_summary_rows, key=lambda x: (-int(x["total_sloc"]), x["name"]))
        print(tabulate(monoglot_rows_sorted[:25], headers="keys", tablefmt="grid"))

if __name__ == "__main__":
    main()