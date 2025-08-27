#!/usr/bin/env python3
"""
Polyglot analysis for Rust projects using a similar framework to your prior script.

What it does
- Clones each repo (shallow, depth=1)
- Runs `cloc --json` across the whole repo
- Filters out non-programming/aux filetypes (config, docs, data) via IGNORED_LANGS
- Keeps ONLY repos that are BOTH:
    * Rust-present (Rust SLOC > 0)
    * Polyglot in programming languages (>=2 languages after filtering)
- Produces:
    1) Console table summary
    2) CSV: per-repo summary (name, total_sloc, rust_sloc, num_langs, top_langs)
    3) CSV: long format per-repo per-language breakdown

Notes
- Adjust IGNORED_LANGS below as you prefer.
- Requires: cloc, GitPython, tabulate
"""
import os
import re
import json
import csv
import time
import subprocess
from collections import defaultdict
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor, as_completed

from git import Repo, GitCommandError
from tabulate import tabulate

from ci_rust_projects import projects  # expects projects = [{name, owner, repo}, ...]

# ----------------------- Config -----------------------
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
    i = s.find("{")
    if i > 0:
        s = s[i:]
    try:
        return json.loads(s)
    except json.JSONDecodeError as je:
        preview = "\n".join(s.splitlines()[:20])
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


def is_polyglot_rust(lang_sloc: dict) -> bool:
    return (lang_sloc.get("Rust", 0) > 0) and (len(lang_sloc) >= 2)


def shallow_clone(url: str, dest: str) -> None:
    """Shallow clone with GitPython; retries once on transient errors."""
    try:
        Repo.clone_from(url, dest, multi_options=["--depth=1", "--no-tags"])  # fast
    except GitCommandError:
        time.sleep(1.5)
        Repo.clone_from(url, dest, multi_options=["--depth=1", "--no-tags"])  # retry


def summarize_top_langs(lang_sloc: dict, n: int = TOP_LANGS_N) -> str:
    items = sorted(lang_sloc.items(), key=lambda kv: kv[1], reverse=True)[:n]
    return ", ".join([f"{k} ({v})" for k, v in items])


def categorize_project(total_sloc: int) -> str:
    if total_sloc < 1_000:
        return "Very Small"
    elif total_sloc < 10_000:
        return "Small"
    elif total_sloc < 100_000:
        return "Medium"
    elif total_sloc < 1_000_000:
        return "Large"
    else:
        return "Very Large"


def process_one(project: dict, base_tmpdir: str) -> dict | None:
    name = project.get("name") or project.get("repo")
    repo_full = project["repo"]  # e.g. owner/name
    url = f"https://github.com/{repo_full}"

    try:
        with TemporaryDirectory(dir=base_tmpdir) as tmpdir:
            dest = os.path.join(tmpdir, safe_dirname(repo_full))
            print(f"[clone] {repo_full}")
            shallow_clone(url, dest)

            cloc_data = run_cloc(dest)
            lang_sloc = extract_lang_sloc(cloc_data)

            if not is_polyglot_rust(lang_sloc):
                return None  # drop non-Rust or mono-language repos

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

    except Exception as e:
        print(f"[error] {name}: {e}")
        return None


# ---------------------- Main flow ---------------------
def main():
    repo_rows = []
    long_rows = []  # repo, language, sloc

    with TemporaryDirectory() as base_tmpdir:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futs = [pool.submit(process_one, proj, base_tmpdir) for proj in projects]
            for fut in as_completed(futs):
                r = fut.result()
                if r:
                    repo_rows.append(r)
                    # explode the json per language for the long CSV
                    lang_sloc = json.loads(r["languages_json"]) if r.get("languages_json") else {}
                    for lang, sloc in lang_sloc.items():
                        long_rows.append({
                            "name": r["name"],
                            "repo": r["repo"],
                            "language": lang,
                            "sloc": sloc,
                        })

    # Sort by total_sloc desc
    repo_rows.sort(key=lambda x: (-int(x["total_sloc"]), x["name"]))

    # Console table
    if repo_rows:
        print(tabulate(repo_rows, headers="keys", tablefmt="grid"))
    else:
        print("No polyglot Rust repos found under current filters.")

    # Ensure data dir exists
    os.makedirs("data", exist_ok=True)

    # Write summary CSV
    out_csv_summary = "data/polyglot_rust_repo_summary.csv"
    with open(out_csv_summary, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "name", "repo", "total_sloc", "rust_sloc", "rust_share_pct",
                "num_langs", "top_langs", "languages_json"
            ],
        )
        writer.writeheader()
        writer.writerows(repo_rows)

    # Write long/melted CSV
    #out_csv_long = "data/29_ci_theater_polyglot_rust.csv"
    #with open(out_csv_long, "w", newline="", encoding="utf-8") as f:
    #    writer = csv.DictWriter(f, fieldnames=["name", "repo", "language", "sloc"])
    #    writer.writeheader()
    #    writer.writerows(long_rows)

    #print(f"\nWrote:\n - {out_csv_summary}\n - {out_csv_long}")


if __name__ == "__main__":
    main()
