#!/usr/bin/env python3
"""
Fetch test presence + CI execution + coverage signals for a list of GitHub repos.

Outputs CSV:
  name,
  Has Tests (static),
  Tests in CI (configured),
  Tests in CI (recent runs),
  Test Tool (guess),
  Test Evidence,
  Coverage Latest (%),
  Coverage Mean (%),
  Coverage Best (%),
  Coverage Samples,
  Method,
  Latest Run ID,
  Latest Run Date

Requirements:
  pip install requests python-dotenv tabulate

Env:
  GITHUB_TOKEN=<token with repo/public_repo as needed>

Input:
  from ci_rust_projects import projects
  # projects = [{"owner": "org_or_user", "name": "repo"}, ...]
"""

import os
import io
import re
import csv
import time
import math
import base64
import threading
import zipfile
import xml.etree.ElementTree as ET
from statistics import mean
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import importlib
from typing import Optional, Tuple, List, Dict, Set

import requests
from tabulate import tabulate
from dotenv import load_dotenv

# ---------- Config ----------
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise RuntimeError("GITHUB_TOKEN is required. Unauthenticated requests are limited to 60/hour.")

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "User-Agent": "ci-coverage-and-tests/3.0",
}

# --- Adapter for flat slugs ---
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

def _to_project_dicts(slugs: list[str]) -> list[dict]:
    """
    Convert flat 'owner/repo' strings into dicts compatible with this script:
    { "owner": <owner>, "name": <repo> }
    """
    seen = set()
    out = []
    for slug in slugs:
        try:
            owner, repo = _parse_slug(slug)
            full = f"{owner}/{repo}"
            key = full.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append({"owner": owner, "name": repo})
        except ValueError as e:
            print(f"[warn] Skipping invalid slug: {e}")
    return out

# Tunables (kept conservative to avoid rate limits)
WORKERS       = 4            # concurrent repos (raise slowly if stable)
PER_PAGE_RUNS = 100          # max density per page
RUNS_PER_REPO = 30           # only the latest few runs
CUTOFF_DAYS   = 365          # up to ~6 months
PAGE_SLEEP    = 0.10         # throttle between pages
TIMEOUT_S     = 25

# Debugging
DEBUG = True

# Optional: only download artifacts whose names contain these tokens (speeds things up)
ARTIFACT_NAME_ALLOWLIST = re.compile(r"(cover|lcov|cobertura|jacoco)", re.IGNORECASE)

COVERAGE_TOOL_HINTS = [
    (re.compile(r"\bcargo\s+llvm-cov\b", re.IGNORECASE), "llvm-cov"),
    (re.compile(r"\bgrcov\b", re.IGNORECASE), "grcov"),
    (re.compile(r"\bcargo\s+tarpaulin\b", re.IGNORECASE), "tarpaulin"),
    (re.compile(r"\bllvm-cov\b", re.IGNORECASE), "llvm-cov"),
    (re.compile(r"RUSTFLAGS\s*[:=].*-C\s*instrument-coverage", re.IGNORECASE), "instrument-coverage"),
    (re.compile(r"LLVM_PROFILE_FILE", re.IGNORECASE), "instrument-coverage"),
    (re.compile(r"codecov(?:\.yml|\.yaml)?", re.IGNORECASE), "codecov"),
    (re.compile(r"coveralls", re.IGNORECASE), "coveralls"),
    (re.compile(r"actions\/upload-artifact@", re.IGNORECASE), "upload-artifact"),
    (re.compile(r"(lcov\.info|\.lcov|cobertura\.xml|jacoco\.xml|coverage\.xml)", re.IGNORECASE), "report-file"),
]

WORKFLOW_ACTION_HINTS = [
    (re.compile(r"codecov\/codecov-action@", re.IGNORECASE), "codecov"),
    (re.compile(r"coverallsapp\/github-action@", re.IGNORECASE), "coveralls"),
    (re.compile(r"actions-rs\/cargo@", re.IGNORECASE), "cargo"),
    (re.compile(r"taiki-e\/install-action@", re.IGNORECASE), "llvm-tools"),
]

# ---------- Thread-local Session ----------
_thread_local = threading.local()

def get_session() -> requests.Session:
    s = getattr(_thread_local, "session", None)
    if s is None:
        s = requests.Session()
        s.headers.update(HEADERS)
        adapter = requests.adapters.HTTPAdapter(pool_connections=WORKERS * 2, pool_maxsize=WORKERS * 4)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        _thread_local.session = s
    return s

# ---------- Global Rate Limiter ----------
class RateLimiter:
    def __init__(self, min_remaining: int = 50):
        self._lock = threading.Lock()
        self.remaining: Optional[int] = None
        self.reset_epoch: Optional[int] = None
        self.min_remaining = min_remaining  # sleep if we dip below this

    def preflight(self):
        with self._lock:
            if self.remaining is not None and self.reset_epoch:
                now = int(time.time())
                if self.remaining <= self.min_remaining and self.reset_epoch > now:
                    sleep_for = min(120, self.reset_epoch - now + 1)
                    if sleep_for > 0:
                        print(f"⏸️  Rate limit guard: sleeping {sleep_for}s (remaining={self.remaining})")
                        time.sleep(sleep_for)

    def update_from_resp(self, resp):
        with self._lock:
            try:
                self.remaining = int(resp.headers.get("X-RateLimit-Remaining", self.remaining or 0))
                self.reset_epoch = int(resp.headers.get("X-RateLimit-Reset", self.reset_epoch or 0))
            except Exception:
                pass

RATE = RateLimiter(min_remaining=50)

# ---------- Allow List Handler ----------
class AllowList:
    def __init__(self, file_path: str):
        self.allowed: Set[str] = self._parse_slugs_to_set(file_path)

    def _parse_slugs_to_set(self, file_path: str) -> Set[str]:
        slugs = set()
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    try:
                        owner, repo = _parse_slug(line)
                        slugs.add(f"{owner.lower()}/{repo.lower()}")
                        slugs.add(owner.lower())  # Allow by owner too
                    except ValueError as e:
                        print(f"[warn] Skipping invalid allow-list slug '{line}': {e}")
        except FileNotFoundError:
            raise RuntimeError(f"Allow list file not found: {file_path}")
        return slugs

    def is_allowed(self, owner: str, name: str) -> bool:
        full_slug = f"{owner.lower()}/{name.lower()}"
        return full_slug in self.allowed or owner.lower() in self.allowed

# ---------- Unified request with retries + global limiting ----------
def http_request(method: str, url: str, session: requests.Session, **kwargs) -> requests.Response:
    MAX_RETRIES = 4
    BACKOFF = 1.7
    for attempt in range(1, MAX_RETRIES + 1):
        RATE.preflight()
        try:
            resp = session.request(method, url, timeout=TIMEOUT_S, **kwargs)
            RATE.update_from_resp(resp)

            # Secondary/abuse throttling
            if resp.status_code in (403, 429):
                ra = resp.headers.get("Retry-After")
                body = (resp.text or "").lower()
                if ra and ra.isdigit():
                    wait = min(120, int(ra))
                    print(f"⏳ Secondary limit: sleeping {wait}s (Retry-After)")
                    time.sleep(wait)
                    continue
                if "secondary rate limit" in body or "abuse detection" in body:
                    wait = min(120, int(BACKOFF ** (attempt - 1)) * 3)
                    print(f"⏳ Secondary limit: backoff {wait}s…")
                    time.sleep(wait)
                    continue
                if "rate limit" in body:
                    time.sleep(2)
                    continue

            if resp.status_code >= 500:
                wait = min(60, int(BACKOFF ** (attempt - 1)))
                print(f"🔁 {resp.status_code} retry in {wait}s … {url}")
                time.sleep(wait)
                continue

            return resp
        except requests.RequestException as e:
            if attempt == MAX_RETRIES:
                raise
            wait = min(60, int(BACKOFF ** (attempt - 1)))
            print(f"🔁 Network error retry in {wait}s … {e}")
            time.sleep(wait)
    return resp  # type: ignore

# ---------- Coverage patterns (logs fallback) ----------
COVERAGE_PATTERNS = [
    re.compile(r"TOTAL\s+\d+\s+\d+\s+\d+\s+(\d+)%", re.IGNORECASE),                 # pytest-cov TOTAL
    re.compile(r"\bCoverage:\s*(\d+(?:\.\d+)?)\s*%", re.IGNORECASE),                # generic "Coverage: 78%"
    re.compile(r"\bcoverage:\s*(\d+(?:\.\d+)?)%\s+of statements", re.IGNORECASE),   # go test
    re.compile(r"\b(All files|Statements|Lines)\s*[:|]\s*(\d+(?:\.\d+)?)\s*%", re.IGNORECASE),  # jest/nyc
    re.compile(r"\blines\.*:\s*(\d+(?:\.\d+)?)\s*%", re.IGNORECASE),                # lcov/genhtml
    re.compile(r"\bOverall coverage:\s*(\d+(?:\.\d+)?)\s*%", re.IGNORECASE),        # JaCoCo
    re.compile(r"\bCoverage:\s*(\d+(?:\.\d+)?)\s*%\b", re.IGNORECASE),              # rust tarpaulin
    re.compile(r"\bTotal\s+Line:\s*(\d+(?:\.\d+)?)\s*%", re.IGNORECASE),            # .NET coverlet
    re.compile(r"\b(\d+(?:\.\d+)?)\s*%\s*(lines|line|statements|stmts)", re.IGNORECASE),  # generic
]

# ---------- Test command patterns ----------
TEST_CMD_PATTERNS = [
    (re.compile(r"\bcargo\s+test\b", re.IGNORECASE), "cargo"),
    (re.compile(r"\bpytest(\s|$)|\bpython\s+-m\s+pytest\b", re.IGNORECASE), "pytest"),
    (re.compile(r"\bgo\s+test\b", re.IGNORECASE), "go"),
    (re.compile(r"\bmvn\b.*\btest\b", re.IGNORECASE), "maven"),
    (re.compile(r"\bgradle\b.*\btest\b|\bgradlew\b.*\btest\b", re.IGNORECASE), "gradle"),
    (re.compile(r"\bnpm\s+test\b|\byarn\s+test\b|\bpnpm\s+test\b|\bjest\b", re.IGNORECASE), "jest"),
    (re.compile(r"\bdotnet\s+test\b", re.IGNORECASE), ".net"),
    (re.compile(r"\bctest\b", re.IGNORECASE), "ctest"),
    (re.compile(r"\btox\b|\bnox\b", re.IGNORECASE), "pytest"),
    (re.compile(r"actions-rs/cargo.*\bcommand:\s*test\b", re.IGNORECASE | re.DOTALL), "cargo"),
]

RUST_TEST_FILE = re.compile(r".*(_test\.rs|/tests?/|/benches?/)", re.IGNORECASE)

# ---------- Helpers: runs, jobs, logs ----------
def list_recent_runs(owner: str, name: str, per_page: int, max_runs: int, cutoff_days: int) -> List[Dict]:
    """Return up to `max_runs` recent workflow runs within cutoff."""
    s = get_session()
    out = []
    page = 1
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=cutoff_days)

    while len(out) < max_runs:
        url = f"https://api.github.com/repos/{owner}/{name}/actions/runs"
        params = {"per_page": min(100, per_page), "page": page}
        resp = http_request("GET", url, s, params=params)
        if resp.status_code == 404:
            break
        resp.raise_for_status()
        runs = resp.json().get("workflow_runs", [])
        if not runs:
            break

        for run in runs:
            try:
                created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
            except Exception:
                created = None
            if created and created < cutoff_date:
                return out  # stop early, older than cutoff
            out.append(run)
            if len(out) >= max_runs:
                return out

        page += 1
        time.sleep(PAGE_SLEEP)

    return out

def list_run_jobs(owner: str, name: str, run_id: int) -> List[Dict]:
    """Return jobs (with steps) for a run (few pages max)."""
    s = get_session()
    url = f"https://api.github.com/repos/{owner}/{name}/actions/runs/{run_id}/jobs"
    jobs = []
    page = 1
    while True:
        resp = http_request("GET", url, s, params={"per_page": 100, "page": page})
        if resp.status_code == 404:
            break
        resp.raise_for_status()
        chunk = resp.json().get("jobs", [])
        if not chunk:
            break
        jobs.extend(chunk)
        if len(chunk) < 100:
            break
        page += 1
    return jobs

def fetch_run_logs(owner: str, name: str, run_id: int) -> Optional[bytes]:
    """Download ZIP logs for a run, following single redirect."""
    s = get_session()
    url = f"https://api.github.com/repos/{owner}/{name}/actions/runs/{run_id}/logs"
    resp = http_request("GET", url, s)
    if resp.status_code == 302:
        loc = resp.headers.get("Location")
        if loc:
            resp = http_request("GET", loc, s)
    if resp.status_code >= 400:
        return None
    return resp.content

# ---------- Check Runs (e.g., Codecov) ----------
def parse_checks_for_coverage(owner: str, name: str, sha: str) -> Optional[float]:
    """Extract coverage percentage from Check Runs (e.g., Codecov)."""
    s = get_session()
    url = f"https://api.github.com/repos/{owner}/{name}/commits/{sha}/check-runs"
    resp = http_request("GET", url, s)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    checks = (resp.json() or {}).get("check_runs", []) or []
    best = None

    def find_pct(text: str) -> Optional[float]:
        if not text:
            return None
        if "cover" not in text.lower():
            return None
        m = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                return None
        return None

    for chk in checks:
        parts = [
            chk.get("name") or "",
            (chk.get("output") or {}).get("title") or "",
            (chk.get("output") or {}).get("summary") or "",
            (chk.get("output") or {}).get("text") or "",
        ]
        for p in parts:
            val = find_pct(p)
            if val is not None:
                best = max(best, val) if best is not None else val

    return best

# ---------- Artifact helpers ----------
def list_run_artifacts(owner: str, name: str, run_id: int) -> List[Dict]:
    s = get_session()
    url = f"https://api.github.com/repos/{owner}/{name}/actions/runs/{run_id}/artifacts"
    resp = http_request("GET", url, s, params={"per_page": 100})
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    arts = (resp.json() or {}).get("artifacts", []) or []
    if DEBUG:
        for a in arts:
            print(f"   ↳ artifact: id={a.get('id')} name='{a.get('name')}' size={a.get('size_in_bytes')} expired={a.get('expired')}")
    return arts

def download_artifact_zip(owner: str, name: str, artifact_id: int) -> Optional[bytes]:
    s = get_session()
    # GitHub returns a 302 to the storage URL
    url = f"https://api.github.com/repos/{owner}/{name}/actions/artifacts/{artifact_id}/zip"
    resp = http_request("GET", url, s)
    if resp.status_code == 302:
        loc = resp.headers.get("Location")
        if loc:
            resp = http_request("GET", loc, s)
    if resp.status_code >= 400:
        return None
    return resp.content

# ---------- Structured coverage parsers ----------
def parse_lcov_text(text: str) -> Optional[float]:
    """
    LCOV format: accumulate DA:<line>,<hits> within each file block.
    Coverage = sum(covered_lines) / sum(total_lines) * 100
    """
    total_lines = 0
    covered_lines = 0
    for line in text.splitlines():
        if line.startswith("DA:"):
            try:
                _, payload = line.split("DA:", 1)
                _lineno, hits = payload.split(",", 1)
                if int(hits) > 0:
                    covered_lines += 1
                total_lines += 1
            except Exception:
                continue
    if total_lines == 0:
        return None
    return (covered_lines / total_lines) * 100.0

def parse_cobertura_xml(xml_bytes: bytes) -> Optional[float]:
    """
    Cobertura root often has line-rate in [0,1]. If not, sum over <classes>/<class> <line hits="">
    """
    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        return None

    lr = root.attrib.get("line-rate")
    if lr is not None:
        try:
            val = float(lr) * 100.0
            if 0.0 <= val <= 100.0:
                return val
        except Exception:
            pass

    total_lines = 0
    covered_lines = 0
    for cls in root.findall(".//class"):
        for ln in cls.findall(".//line"):
            hits = ln.attrib.get("hits")
            if hits is None:
                continue
            try:
                total_lines += 1
                if int(hits) > 0:
                    covered_lines += 1
            except Exception:
                continue
    if total_lines > 0:
        return (covered_lines / total_lines) * 100.0
    return None

def parse_jacoco_xml(xml_bytes: bytes) -> Optional[float]:
    """
    JaCoCo: <counter type="LINE" missed=".." covered="..">. Prefer root-level; else sum all LINE counters.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        return None

    for c in root.findall("./counter"):
        if c.attrib.get("type") == "LINE":
            try:
                missed = int(c.attrib.get("missed", "0"))
                covered = int(c.attrib.get("covered", "0"))
                total = missed + covered
                return (covered / total) * 100.0 if total > 0 else None
            except Exception:
                pass

    missed_sum = 0
    covered_sum = 0
    for c in root.findall(".//counter"):
        if c.attrib.get("type") == "LINE":
            try:
                missed_sum += int(c.attrib.get("missed", "0"))
                covered_sum += int(c.attrib.get("covered", "0"))
            except Exception:
                continue
    total = missed_sum + covered_sum
    if total > 0:
        return (covered_sum / total) * 100.0
    return None

def parse_artifact_zip_for_coverage(zip_bytes: bytes) -> Tuple[Optional[float], Optional[str]]:
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except Exception:
        return None, None

    candidates = []
    for info in zf.infolist():
        name = (info.filename or "").lower()
        if info.file_size == 0 or info.file_size > 200_000_000:
            continue
        if (
            name.endswith((".xml", ".info", ".lcov", ".json")) or
            any(x in name for x in ["lcov", "cobertura", "jacoco", "coverage", "cov", "report"])
        ):
            candidates.append(info)

    # LCOV
    for info in candidates:
        n = info.filename.lower()
        if n.endswith(".lcov") or n.endswith("lcov.info") or n.endswith(".info") or "lcov" in n:
            try:
                with zf.open(info, "r") as f:
                    text = f.read().decode("utf-8", errors="ignore")
                pct = parse_lcov_text(text)
                if pct is not None:
                    return pct, "artifacts:lcov"
            except Exception:
                continue

    # Cobertura
    for info in candidates:
        n = info.filename.lower()
        if n.endswith("cobertura.xml") or ("cobertura" in n and n.endswith(".xml")) or n.endswith("coverage.xml"):
            try:
                with zf.open(info, "r") as f:
                    xml_bytes = f.read()
                pct = parse_cobertura_xml(xml_bytes)
                if pct is not None:
                    return pct, "artifacts:cobertura"
            except Exception:
                continue

    # JaCoCo
    for info in candidates:
        n = info.filename.lower()
        if n.endswith("jacoco.xml") or ("jacoco" in n and n.endswith(".xml")):
            try:
                with zf.open(info, "r") as f:
                    xml_bytes = f.read()
                pct = parse_jacoco_xml(xml_bytes)
                if pct is not None:
                    return pct, "artifacts:jacoco"
            except Exception:
                continue

    # Optional: cargo-llvm-cov JSON summaries
    for info in candidates:
        n = info.filename.lower()
        if n.endswith(".json") and ("llvm-cov" in n or "summary" in n or "coverage" in n):
            try:
                import json
                with zf.open(info, "r") as f:
                    data = json.loads(f.read().decode("utf-8", errors="ignore"))
                pct = (
                    data.get("line", {}).get("percent") or
                    data.get("totals", {}).get("lines", {}).get("percent")
                )
                if pct is not None:
                    return float(pct), "artifacts:json"
            except Exception:
                continue

    return None, None


# ---------- Repo static scanning (cheap) ----------
def detect_repo_tests_static(owner: str, name: str) -> Tuple[bool, Optional[str], Set[str]]:
    """
    Cheap heuristics first (few path probes). Only fall back to heavier checks if needed.
    Returns (has_tests, tool_guess, evidence_set)
    """
    evidence: Set[str] = set()
    tool_guess: Optional[str] = None
    s = get_session()

    candidate_dirs = ["tests", "test", "spec", "__tests__", "benches"]
    found = False
    for d in candidate_dirs:
        url = f"https://api.github.com/repos/{owner}/{name}/contents/{d}"
        resp = http_request("GET", url, s)
        if resp.status_code == 200:
            found = True
            evidence.add("files")
            break
        if resp.status_code == 404:
            continue
        resp.raise_for_status()

    if not found:
        url = f"https://api.github.com/repos/{owner}/{name}/contents"
        resp = http_request("GET", url, s)
        if resp.status_code == 200:
            for it in resp.json() or []:
                p = it.get("name", "")
                if p.endswith("_test.rs"):
                    found = True
                    evidence.add("files")
                    break

    if found:
        tool_guess = "cargo"  # rust-first default for this pass
        return True, tool_guess, evidence

    return False, None, evidence

# ---------- Workflow scan for test commands ----------
def detect_workflow_tests_config(owner: str, name: str) -> Tuple[bool, Optional[str], Set[str]]:
    """
    Look inside .github/workflows/*.yml for test commands or steps named 'test'.
    Returns (configured, tool_guess, evidence_set)
    """
    evidence: Set[str] = set()
    tool_guess: Optional[str] = None
    s = get_session()
    url = f"https://api.github.com/repos/{owner}/{name}/contents/.github/workflows"
    resp = http_request("GET", url, s)
    if resp.status_code == 404:
        return False, None, evidence
    resp.raise_for_status()
    items = resp.json() or []
    configured = False

    for it in items:
        if it.get("type") != "file":
            continue
        if not re.search(r"\.(yml|yaml)$", it.get("name", ""), re.IGNORECASE):
            continue
        dl = it.get("download_url")
        if not dl:
            continue
        fr = http_request("GET", dl, s)
        if fr.status_code != 200:
            continue
        text = fr.text

        for pat, tool in TEST_CMD_PATTERNS:
            if pat.search(text):
                configured = True
                evidence.add("workflow")
                tool_guess = tool_guess or tool

        if re.search(r"name:\s*.*\btest\b", text, re.IGNORECASE):
            configured = True
            evidence.add("workflow")

    return configured, tool_guess, evidence

# ---------- Inspect recent runs for executed tests ----------
def detect_tests_from_runs(owner: str, name: str, runs: List[Dict]) -> Tuple[bool, Optional[str], Set[str]]:
    """
    Inspect jobs/steps of a single representative run to see if tests actually executed.
    Returns (tests_ran_recently, tool_guess, evidence_set)
    """
    evidence: Set[str] = set()
    tool_guess: Optional[str] = None

    candidate = None
    for run in runs:
        nm = (run.get("name") or "") + " " + (run.get("display_title") or "")
        if re.search(r"\btest(s)?\b|\bci\b", nm, re.IGNORECASE):
            candidate = run
            break
    if not candidate and runs:
        candidate = runs[0]
    if not candidate:
        return False, None, evidence

    jobs = list_run_jobs(owner, name, int(candidate["id"]))
    tests_seen = False
    for job in jobs:
        if re.search(r"\btest(s)?\b", job.get("name", "") or "", re.IGNORECASE):
            tests_seen = True
            evidence.add("jobs")
        for step in job.get("steps", []) or []:
            nm = step.get("name") or ""
            if re.search(r"\btest(s)?\b", nm, re.IGNORECASE):
                tests_seen = True
                evidence.add("jobs")
            uses = step.get("uses") or ""
            if "actions-rs/cargo" in uses:
                tool_guess = tool_guess or "cargo"

    if tests_seen and not tool_guess:
        blob = fetch_run_logs(owner, name, int(candidate["id"]))
        if blob:
            txt_hint = ""
            try:
                zf = zipfile.ZipFile(io.BytesIO(blob))
                for i, info in enumerate(zf.infolist()):
                    if i > 4:
                        break
                    if info.file_size and info.file_size < 1_000_000:
                        with zf.open(info, "r") as f:
                            part = f.read(15000).decode("utf-8", errors="ignore")
                            txt_hint += "\n" + part
            except Exception:
                pass
            for pat, tool in TEST_CMD_PATTERNS:
                if pat.search(txt_hint):
                    tool_guess = tool
                    evidence.add("logs")
                    break

    return tests_seen, tool_guess, evidence

def detect_coverage_integration(owner: str, name: str) -> Tuple[bool, str, Set[str]]:
    """
    Checks whether coverage tools are configured in the repo/workflows.
    Returns: (configured?, tool_label, evidence_set)
    - configured?: True if we find strong signals
    - tool_label: best-guess tool(s)
    - evidence_set: {'workflow','files','env','uploader','report-file'} etc.
    """
    s = get_session()
    evidence: Set[str] = set()
    tools: Set[str] = set()
    configured = False

    # 1) Scan workflows
    url = f"https://api.github.com/repos/{owner}/{name}/contents/.github/workflows"
    resp = http_request("GET", url, s)
    if resp.status_code == 200:
        items = resp.json() or []
        for it in items:
            if it.get("type") != "file":
                continue
            if not re.search(r"\.(yml|yaml)$", it.get("name", ""), re.IGNORECASE):
                continue
            dl = it.get("download_url")
            if not dl:
                continue
            fr = http_request("GET", dl, s)
            if fr.status_code != 200:
                continue
            text = fr.text

            # Strong signals: commands/envs/uploaders in workflow
            for pat, label in COVERAGE_TOOL_HINTS:
                if pat.search(text):
                    configured = True
                    tools.add(label)
                    evidence.add("workflow")

            for pat, label in WORKFLOW_ACTION_HINTS:
                if pat.search(text):
                    configured = True
                    tools.add(label)
                    evidence.add("workflow")

            # If steps named "coverage" or similar
            if re.search(r"name:\s*.*\bcoverage\b", text, re.IGNORECASE):
                configured = True
                evidence.add("workflow")

    # 2) Probe common repo files quickly (cheap contents calls)
    #    Note: we avoid a full tree walk to keep requests low.
    candidate_files = [
        "codecov.yml", ".codecov.yml", ".codecov.yaml", "codecov.yaml",
        ".github/codecov.yml", ".github/codecov.yaml",
        "rust-toolchain.toml", "rust-toolchain",
        ".cargo/config.toml", ".cargo/config",
        "Cargo.toml",
    ]
    for path in candidate_files:
        furl = f"https://api.github.com/repos/{owner}/{name}/contents/{path}"
        r = http_request("GET", furl, s)
        if r.status_code != 200:
            continue
        j = r.json()

        text = ""
        dl = j.get("download_url")
        if dl:
            rf = http_request("GET", dl, s)
            if rf.status_code == 200:
                text = rf.text
        else:
            # fallback: some contents responses include base64 "content"
            b64 = j.get("content")
            if b64:
                try:
                    text = base64.b64decode(b64).decode("utf-8", errors="ignore")
                except Exception:
                    text = ""
        if not text:
            continue

        # mark presence
        if os.path.basename(path).startswith("codecov"):
            configured = True
            tools.add("codecov")
            evidence.add("files")

        # light content scan
        for pat, label in COVERAGE_TOOL_HINTS:
            if pat.search(text):
                configured = True
                tools.add(label)
                evidence.add("files")

        # rust-toolchain hints (llvm-tools-preview often used with llvm-cov)
        if "llvm-tools-preview" in text:
            configured = True
            tools.add("llvm-tools")
            evidence.add("files")

    tool_label = "/".join(sorted(tools)) if tools else ""
    return configured, tool_label, evidence


# ---------- Coverage + Test detection per repo ----------
def extract_repo_coverage_and_tests(owner: str, name: str) -> Tuple[Dict, List[float]]:
    """
    A) detect tests (static, workflow, recent runs)
    B) compute coverage stats prioritizing structured reports from artifacts (LCOV/Cobertura/JaCoCo),
       then fall back to check runs, then to regex on logs.
    """
    # A) test detection
    has_tests_static, tool_from_files, ev_files = detect_repo_tests_static(owner, name)
    runs = list_recent_runs(owner, name, PER_PAGE_RUNS, RUNS_PER_REPO, CUTOFF_DAYS)
    tests_recent_runs, tool_from_runs, ev_runs = detect_tests_from_runs(owner, name, runs)
    tests_in_workflow, tool_from_wf, ev_wf = detect_workflow_tests_config(owner, name)

    cov_cfg, cov_tool_label, ev_cov = detect_coverage_integration(owner, name)

    evidence = set()
    evidence |= ev_files | ev_runs | ev_wf | ev_cov

    # Decide tool guess priority: runs > workflow > files
    tool_guess = tool_from_runs or tool_from_wf or tool_from_files

    # B) coverage (artifacts → checks → logs)
    coverages: List[float] = []
    method_flags = set()
    latest_run_id = None
    latest_run_date = None

    for idx, run in enumerate(runs):
        if latest_run_id is None:
            latest_run_id = run.get("id")
            latest_run_date = run.get("created_at")

        found_for_this_run = False

        # (1) Artifacts
        try:
            arts = list_run_artifacts(owner, name, int(run["id"]))
            for a in arts:
                if a.get("expired", False):
                    if DEBUG:
                        print(f"   ✗ skip expired artifact: {a.get('name')}")
                    continue
                blob = download_artifact_zip(owner, name, int(a["id"]))
                if not blob:
                    continue
                cov_art, tag = parse_artifact_zip_for_coverage(blob)
                if cov_art is not None:
                    coverages.append(cov_art)
                    method_flags.add(tag or "artifacts")
                    found_for_this_run = True
                    if DEBUG:
                        print(f"   ✓ coverage via artifacts ({tag}): {cov_art:.2f}%")
                    break
        except Exception as e:
            if DEBUG:
                print(f"   ! artifact error: {e}")

        if found_for_this_run:
            continue

        # (2) Check runs
        sha = run.get("head_sha")
        if sha:
            try:
                cov_check = parse_checks_for_coverage(owner, name, sha)
                if cov_check is not None:
                    coverages.append(cov_check)
                    method_flags.add("checks")
                    found_for_this_run = True
                    if DEBUG:
                        print(f"   ✓ coverage via checks: {cov_check:.2f}%")
            except Exception as e:
                if DEBUG:
                    print(f"   ! checks error: {e}")

        if found_for_this_run:
            continue

        # (3) Logs fallback (per-run now, not just once)
        try:
           blob = fetch_run_logs(owner, name, int(run["id"]))
           if blob:
            cov2 = parse_logs_zip_for_coverage(blob)
            if cov2 is not None:
                coverages.append(cov2)
                method_flags.add("logs")
                if DEBUG:
                    print(f"   ✓ coverage via logs: {cov2:.2f}%")
        except Exception as e:
            if DEBUG:
                print(f"   ! logs error: {e}")

    # Compose row (coverage + test flags)
    if coverages:
        row = {
            "name": name,
            "Coverage Latest (%)": round(coverages[0], 2),
            "Coverage Mean (%)": round(mean(coverages), 2),
            "Coverage Best (%)": round(max(coverages), 2),
            "Coverage Samples": len(coverages),
            "Method": "/".join(sorted(method_flags)) if method_flags else "",
            "Latest Run ID": latest_run_id or "",
            "Latest Run Date": latest_run_date or "",
        }
    else:
        row = {
            "name": name,
            "Coverage Latest (%)": "",
            "Coverage Mean (%)": "",
            "Coverage Best (%)": "",
            "Coverage Samples": 0,
            "Method": "",
            "Latest Run ID": latest_run_id or "",
            "Latest Run Date": latest_run_date or "",
        }

    # Add test detection fields
    row.update({
        "Has Tests (static)": "Yes" if has_tests_static else "No",
        "Tests in CI (configured)": "Yes" if tests_in_workflow else "No",
        "Tests in CI (recent runs)": "Yes" if tests_recent_runs else "No",
        "Test Tool (guess)": tool_guess or "",
        "Coverage in CI (configured)": "Yes" if cov_cfg else "No",
        "Coverage Tool (configured)": cov_tool_label,
        "Test Evidence": "/".join(sorted(evidence)) if evidence else "",
    })
    return row, coverages

def process_repo(index: int, owner: str, name: str, allow_list: Optional[AllowList]) -> Optional[Tuple[int, Dict]]:
    if allow_list and not allow_list.is_allowed(owner, name):
        print(f"[{index}] ⏭️  Skipping {owner}/{name} (not in allow list)")
        return None
    
    print(f"[{index}] {owner}/{name} …")
    row, _ = extract_repo_coverage_and_tests(owner, name)
    print(f"[{index}] {owner}/{name} → tests_static={row['Has Tests (static)']}, "
          f"ci_cfg={row['Tests in CI (configured)']}, ci_recent={row['Tests in CI (recent runs)']}, "
          f"samples={row['Coverage Samples']}")
    return index, row

# ---------- Main ----------
def main():
    parser = argparse.ArgumentParser(description="Analyze test and coverage signals for a list of GitHub repos.")
    parser.add_argument(
        "--projects-file",
        required=True,
        help="The Python module name (without .py) containing the 'projects' list of repo slugs.",
    )
    parser.add_argument(
        "--output-file",
        required=True,
        help="Path to the output CSV file.",
    )
    parser.add_argument(
        "--allow-list",
        help="Path to a text file with one 'owner/repo' or 'owner' slug per line. Only process these repos.",
    )
    args = parser.parse_args()

    try:
        projects_module = importlib.import_module(args.projects_file)
        _slug_projects = projects_module.projects
    except (ImportError, AttributeError):
        error_msg = (
            f"Could not import 'projects' list from '{args.projects_file}.py'.\n"
            f"Please ensure the file '{args.projects_file}.py' exists in the current directory.\n"
            "This file is generated by 'helper_create_cohorts.py'. You may need to run the prerequisite scripts."
        )
        raise RuntimeError(error_msg)

    projects = _to_project_dicts(_slug_projects)
    CSV_FILE = args.output_file
    os.makedirs(os.path.dirname(CSV_FILE) or ".", exist_ok=True)
    
    total = len(projects)
    
    allow_list = AllowList(args.allow_list) if args.allow_list else None
    
    print(f"📊 Processing {total} repos with {WORKERS} workers…")
    ordered: List[Optional[Dict]] = [None] * total
    processed_count = 0

    # Define fieldnames early for use in periodic writese
    fieldnames = [
        "name",
        "Has Tests (static)",
        "Tests in CI (configured)",
        "Tests in CI (recent runs)",
        "Coverage in CI (configured)",
        "Coverage Tool (configured)",
        "Test Tool (guess)",
        "Test Evidence",
        "Coverage Latest (%)",
        "Coverage Mean (%)",
        "Coverage Best (%)",
        "Coverage Samples",
        "Method",
        "Latest Run ID",
        "Latest Run Date",
    ]

    def write_results_to_csv(rows_to_write):
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows_to_write:
                writer.writerow({k: r.get(k, "") for k in fieldnames})

    start = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = []
        for i, p in enumerate(projects, start=1):
            futures.append(ex.submit(process_repo, i, p["owner"], p["name"], allow_list))

        for fut in as_completed(futures):
            result = fut.result()
            if result:
                idx, row = result
                ordered[idx - 1] = row
                processed_count += 1

                # Write to CSV every 5 repos
                if processed_count % 5 == 0 or processed_count == total:
                    current_results = [r for r in ordered if r is not None]
                    write_results_to_csv(current_results)
                    print(f"  [checkpoint] Wrote {len(current_results)}/{processed_count} results to {CSV_FILE}")

    results = [r for r in ordered if r is not None]

    if results:
        # Nice console table (best effort)
        try:
            print("\n" + tabulate(results, headers="keys", tablefmt="grid"))
        except Exception:
            pass

        # Final write to ensure all results are saved
        write_results_to_csv(results)
        dur = round(time.time() - start, 1)
        print(f"\n✅ Results saved to {CSV_FILE} in {dur}s")
    else:
        print("No results.")

# ---------- Logs fallback parser (kept from original) ----------
def parse_logs_zip_for_coverage(zip_bytes: bytes) -> Optional[float]:
    """Scan ZIP of run logs and return highest plausible coverage percentage found (fallback)."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except Exception:
        return None

    best = None
    for info in zf.infolist():
        if info.file_size == 0:
            continue
        try:
            with zf.open(info, "r") as f:
                chunk = f.read()
            try:
                text = chunk.decode("utf-8", errors="ignore")
            except Exception:
                text = chunk.decode("latin-1", errors="ignore")
        except Exception:
            continue

        for pat in COVERAGE_PATTERNS:
            for m in pat.finditer(text):
                if m.lastindex:
                    val = None
                    for gi in range(1, m.lastindex + 1):
                        g = m.group(gi)
                        try:
                            val = float(g)
                            break
                        except Exception:
                            continue
                    if val is not None and 0.0 <= val <= 100.0:
                        best = max(best, val) if best is not None else val
    return best

if __name__ == "__main__":
    main()