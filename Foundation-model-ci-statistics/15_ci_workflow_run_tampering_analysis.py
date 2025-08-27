#!/usr/bin/env python3
"""
sdk_ci_discovery.py

Analyze SDK repositories for CI adoption and recent commit activity.

Modes:
  1) CORE-ALLOWLIST (--core-only): Official core language SDK/stdlib repos.
  2) SEARCH (default): Discover SDK repos via GitHub search (topic/keywords).

Outputs:
  - CSV with metrics
  - JSON `projects` array: [{name, owner, repo}]

Usage:
  pip install python-dotenv requests
  echo "GITHUB_TOKEN=ghp_..." > .env
  # Core language SDKs only:
  python sdk_ci_discovery.py --core-only --csv core_lang_sdk_ci.csv --verbose
  # Search SDKs (broad):
  python sdk_ci_discovery.py --min-stars 500 --topic sdk --max-repos 800 --csv sdk_ci.csv --verbose
"""

import os
import time
import csv
import json
import base64
import argparse
from typing import List, Dict, Any, Optional, Tuple
import os.path as op

import requests
from dotenv import load_dotenv

# ----------------------------
# CLI
# ----------------------------
def parse_args():
    p = argparse.ArgumentParser(
        description="Analyze SDK repos (core allow-list or GitHub search): CI adoption + commits/year.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    # Mode control
    p.add_argument("--core-only", action="store_true",
                   help="Analyze only core language SDK/stdlib repos (fixed allow-list; no search).")
    p.add_argument("--include", nargs="*", default=[],
                   help="When --core-only, restrict to a subset by short name (e.g., python go rust).")
    # Search mode options (ignored in --core-only)
    p.add_argument("--topic", action="append", default=["sdk"],
                   help="GitHub topic(s) to include (repeatable).")
    p.add_argument("--q-extra", default="",
                   help='Extra query terms (e.g., "in:readme client").')
    p.add_argument("--min-stars", type=int, default=200,
                   help="Minimum stars to include (search mode).")
    p.add_argument("--language", default="",
                   help="Optional language filter (e.g., go, python, javascript, java, ruby, rust, csharp, php).")
    p.add_argument("--max-repos", type=int, default=800,
                   help="Max repositories to fetch (GitHub Search caps at ~1000).")
    p.add_argument("--per-page", type=int, default=100,
                   help="Search page size (max 100).")
    # Outputs
    p.add_argument("--csv", default="sdk_ci.csv", help="Output CSV path.")
    p.add_argument("--verbose", action="store_true", help="Print progress.")
    return p.parse_args()

# ----------------------------
# Auth
# ----------------------------
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
HEADERS["Accept"] = "application/vnd.github+json"
HEADERS["X-GitHub-Api-Version"] = "2022-11-28"

# ----------------------------
# Core language allow-list
# ----------------------------
CORE_LANG_PROJECTS: List[Dict[str, str]] = [
    {"name": "cpython",         "repo": "python/cpython"},
    {"name": "go",              "repo": "golang/go"},
    {"name": "rust",            "repo": "rust-lang/rust"},
    {"name": "swift",           "repo": "apple/swift"},
    {"name": "jdk",             "repo": "openjdk/jdk"},
    {"name": "kotlin",          "repo": "JetBrains/kotlin"},
    {"name": "scala-2",         "repo": "scala/scala"},
    {"name": "scala-3",         "repo": "lampepfl/dotty"},
    {"name": "node",            "repo": "nodejs/node"},
    {"name": "typescript",      "repo": "microsoft/TypeScript"},
    {"name": "dotnet-runtime",  "repo": "dotnet/runtime"},
    {"name": "dotnet-sdk",      "repo": "dotnet/sdk"},
    {"name": "fsharp",          "repo": "dotnet/fsharp"},
    {"name": "dart",            "repo": "dart-lang/sdk"},
    {"name": "julia",           "repo": "JuliaLang/julia"},
    {"name": "ghc",             "repo": "ghc/ghc"},
    {"name": "ocaml",           "repo": "ocaml/ocaml"},
    {"name": "elixir",          "repo": "elixir-lang/elixir"},
    {"name": "erlang",          "repo": "erlang/otp"},
    {"name": "ruby",            "repo": "ruby/ruby"},
    {"name": "php",             "repo": "php/php-src"},
    {"name": "perl",            "repo": "Perl/perl5"},
    {"name": "zig",             "repo": "ziglang/zig"},
    {"name": "nim",             "repo": "nim-lang/Nim"},
    {"name": "crystal",         "repo": "crystal-lang/crystal"},
    {"name": "dmd",             "repo": "dlang/dmd"},      # D compiler
    {"name": "phobos",          "repo": "dlang/phobos"},   # D stdlib
    # Mirrors omitted by default (R/Lua). Add if needed:
    # {"name": "r",    "repo": "wch/r-source"},
    # {"name": "lua",  "repo": "lua/lua"},
]

# ----------------------------
# HTTP helpers
# ----------------------------
def gh_get(url: str, params: Optional[dict] = None, retries: int = 6, sleep_s: float = 1.5) -> requests.Response:
    for i in range(retries):
        r = requests.get(url, headers=HEADERS, params=params, timeout=60)
        if r.status_code == 403 and "rate limit" in r.text.lower():
            reset = r.headers.get("X-RateLimit-Reset")
            wait = max(60, int(reset) - int(time.time()) + 1) if reset and str(reset).isdigit() else 90
            time.sleep(min(wait, 180))
            continue
        if r.status_code >= 500:
            time.sleep((i + 1) * sleep_s)
            continue
        if r.status_code == 422:
            try:
                msg = r.json().get("message", r.text)
            except Exception:
                msg = r.text
            raise requests.HTTPError(f"422 Unprocessable Entity: {msg}", response=r)
        r.raise_for_status()
        return r
    r.raise_for_status()
    return r  # not reached

# ----------------------------
# Search mode helpers
# ----------------------------
def gh_search_repos(query: str, per_page: int, max_repos: int, verbose: bool = False) -> List[Dict[str, Any]]:
    def _fetch(q: str) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        page = 1
        while len(items) < max_repos:
            params = {"q": q, "sort": "stars", "order": "desc", "per_page": per_page, "page": page}
            r = gh_get("https://api.github.com/search/repositories", params)
            data = r.json()
            batch = data.get("items", [])
            if not batch:
                break
            items.extend(batch)
            if verbose:
                print(f"Fetched {len(items)} / {max_repos} repos so far...")
            page += 1
            if len(batch) < per_page:
                break
        return items[:max_repos]

    try:
        return _fetch(query)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 422:
            if verbose:
                print("Query 422. Retrying with simplified qualifiers only...")
            simplified = " ".join([p for p in query.split() if ":" in p])
            if "in:name,description,readme" not in simplified:
                simplified += " in:name,description,readme"
            return _fetch(simplified)
        raise

def build_query(args) -> str:
    parts = []
    for t in args.topic:
        parts.append(f"topic:{t}")
    parts.append(f"stars:>={args.min_stars}")
    if args.language:
        parts.append(f"language:{args.language}")
    parts.append("in:name,description,readme")
    if args.q_extra:
        parts.append(args.q_extra)
    # Gentle bias words (no parentheses to avoid 422)
    parts.append('sdk OR client OR bindings OR wrapper OR library')
    return " ".join(parts)

# ----------------------------
# Repo metadata + CI detection
# ----------------------------
def get_repo_meta(owner: str, name: str) -> Dict[str, Any]:
    r = gh_get(f"https://api.github.com/repos/{owner}/{name}")
    return r.json()

CI_PATHS: List[Tuple[str, str]] = [
    ("GitHub Actions", ".github/workflows"),
    ("Jenkins", "Jenkinsfile"),
    ("CircleCI", ".circleci/config.yml"),
    ("Travis CI", ".travis.yml"),
    ("Azure Pipelines", "azure-pipelines.yml"),
    ("Drone", ".drone.yml"),
    ("AppVeyor", "appveyor.yml"),
]

def repo_path_exists(owner: str, name: str, path: str) -> bool:
    url = f"https://api.github.com/repos/{owner}/{name}/contents/{path}"
    try:
        r = gh_get(url)
        return r.status_code == 200
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return False
        raise

def detect_ci(owner: str, name: str) -> Tuple[List[str], int]:
    found: List[str] = []
    workflows_count = 0
    for label, path in CI_PATHS:
        if repo_path_exists(owner, name, path):
            if label == "GitHub Actions":
                url = f"https://api.github.com/repos/{owner}/{name}/contents/.github/workflows"
                try:
                    r = gh_get(url)
                    data = r.json()
                    if isinstance(data, list):
                        workflows_count = len([x for x in data if x.get("type") == "file"])
                except requests.HTTPError:
                    workflows_count = 0
            found.append(label)
    return found, workflows_count

# ----------------------------
# Commit activity (last 52 weeks)
# ----------------------------
def get_commits_last_year(owner: str, repo: str, retries: int = 10, sleep_s: float = 3.0) -> int:
    url = f"https://api.github.com/repos/{owner}/{repo}/stats/commit_activity"
    for i in range(retries):
        r = requests.get(url, headers=HEADERS, timeout=60)
        if r.status_code == 202:
            time.sleep((i + 1) * sleep_s)
            continue
        r.raise_for_status()
        arr = r.json()
        if isinstance(arr, list):
            return sum(week.get("total", 0) for week in arr)
        time.sleep((i + 1) * sleep_s)
    return 0

def size_bucket(commits_year: int) -> str:
    if commits_year < 500:
        return "Small"
    if commits_year < 2000:
        return "Medium"
    return "Large"

# ----------------------------
# Main
# ----------------------------
def main():
    args = parse_args()

    if args.verbose:
        print("MODE:", "CORE-ALLOWLIST" if args.core_only else "SEARCH")
    if not GITHUB_TOKEN:
        print("WARNING: GITHUB_TOKEN not set — you may hit rate limits.", flush=True)

    # Build repo list
    repos: List[Dict[str, Any]] = []
    if args.core_only:
        # Filter allow-list if --include provided
        selected = CORE_LANG_PROJECTS
        if args.include:
            inc = set(x.lower() for x in args.include)
            selected = [p for p in CORE_LANG_PROJECTS if p["name"].lower() in inc]
            if not selected:
                print("No projects matched --include filters.")
                return
        if args.verbose:
            print("Using core-language allow-list (no search).")
        for p in selected:
            owner, name = p["repo"].split("/", 1)
            meta = get_repo_meta(owner, name)
            repos.append(meta)
    else:
        query = build_query(args)
        if args.verbose:
            print("GitHub search query:")
            print(query)
        repos = gh_search_repos(query, per_page=args.per_page, max_repos=args.max_repos, verbose=args.verbose)

    # Process repos
    rows: List[List[Any]] = []
    header = [
        "full_name", "html_url", "stars", "forks", "open_issues",
        "default_branch", "pushed_at", "language",
        "commits_last_52_weeks", "size_bucket",
        "ci_tools", "workflows_count"
    ]

    for idx, r in enumerate(repos, start=1):
        full_name = r["full_name"]  # owner/repo
        owner, name = full_name.split("/", 1)
        html_url = r.get("html_url", f"https://github.com/{full_name}")
        stars = r.get("stargazers_count", 0)
        forks = r.get("forks_count", 0)
        open_issues = r.get("open_issues_count", 0)
        default_branch = r.get("default_branch", "")
        pushed_at = r.get("pushed_at", "")
        language = r.get("language", "")

        if args.verbose:
            print(f"[{idx}/{len(repos)}] {full_name} — Detecting CI...")

        try:
            ci_tools, workflows_count = detect_ci(owner, name)
        except Exception as e:
            if args.verbose:
                print(f"  CI detect error: {e}")
            ci_tools, workflows_count = [], 0

        if args.verbose:
            print(f"  CI tools: {', '.join(ci_tools) if ci_tools else 'none'}; workflows: {workflows_count}")

        try:
            commits_yr = get_commits_last_year(owner, name)
        except Exception as e:
            if args.verbose:
                print(f"  Commit stats error: {e}")
            commits_yr = 0

        bucket = size_bucket(commits_yr)

        rows.append([
            full_name, html_url, stars, forks, open_issues,
            default_branch, pushed_at, language,
            commits_yr, bucket,
            ";".join(ci_tools), workflows_count
        ])

    # Write CSV
    with open(args.csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)

    # Build projects JSON array (mirrors CSV rows; CI presence not filtered here—kept as metrics)
    projects = []
    for row in rows:
        full = row[0]
        owner, name = full.split("/", 1)
        projects.append({"name": name, "owner": owner, "repo": full})

    json_path = op.splitext(args.csv)[0] + ".json"
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(projects, jf, indent=2)

    print(f"Done. Wrote {len(rows)} repos to {args.csv}")
    print(f"Wrote projects JSON to {json_path}")

if __name__ == "__main__":
    main()
