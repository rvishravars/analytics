#!/usr/bin/env python3
import os, json, time, random, requests, datetime, re
from dotenv import load_dotenv

# ========================= Paths =========================
INPUT_FILE   = "rust_repos_over500.json"       # input: [{ "repo": "owner/name", ... }, ...]
OUTPUT_FILE  = "repos_not_demo.json"           # output: projects = [...]

# ====================== GitHub API =======================
GQL_ENDPOINT = "https://api.github.com/graphql"
USER_AGENT   = "repo-demo-filter/1.0"

# ===================== Performance =======================
BATCH_SIZE = 40                 # 20–50 is a good range
REQUEST_TIMEOUT = 60
POOL_CONN = 50
POOL_MAX  = 50
PER_BATCH_SLEEP_RANGE = (0.0, 0.0)  # keep 0 for speed
CHECKPOINT_EVERY = 500
PRINT_EVERY = 100

# =================== Demo/Example Filter =================
# 1) Terms to flag as demo/example (case-insensitive)
DEMO_TERMS = [
    "demo", "example", "examples", "sample", "samples", "tutorial",
    "tutorials", "guide", "guides", "boilerplate", "template",
    "templates", "playground", "starter", "starter-kit", "skeleton",
    "cookbook", "showcase", "reference-implementation", "ref-impl"
]
# Regex built from the above (word-ish boundaries; also allow hyphen/underscore)
DEMO_RE = re.compile(r"(?:^|[\W_])(" + "|".join(map(re.escape, DEMO_TERMS)) + r")(?:$|[\W_])", re.IGNORECASE)

# 2) Top-level dirs that strongly indicate examples/demos
DEMO_DIRS = {"examples", "example", "demo", "demos", "sample", "samples", "tutorial", "tutorials", "starter"}

# 3) Cargo.toml signals
CARGO_NAME_DEMO_RE = re.compile(r'^\s*name\s*=\s*"(?:[^"]*(?:demo|example|sample|starter|template)[^"]*)"\s*$', re.IGNORECASE | re.MULTILINE)

# 4) Optional “tiny activity” heuristic (off by default)
USE_TINY_ACTIVITY_HEURISTIC = False
MAX_COMMITS_FOR_TINY = 10      # if default branch has <= this many commits
REQUIRE_NO_RELEASES   = True   # and no releases

# 5) Keep workflow criterion (set False to ignore)
REQUIRE_WORKFLOWS = False

# 6) Other quality filters (optional, modest defaults)
SKIP_ARCHIVED = True
SKIP_DISABLED = True

# ===================== IO Helpers =======================
def load_projects(path):
    with open(path, "r", encoding="utf-8") as f:
        txt = f.read().strip()
        if txt.startswith("projects ="):
            txt = txt[len("projects ="):].strip()
        return json.loads(txt)

def load_checkpoint(path):
    if not os.path.exists(path):
        return [], set()
    with open(path, "r", encoding="utf-8") as f:
        txt = f.read().strip()
        if txt.startswith("projects ="):
            txt = txt[len("projects ="):].strip()
        kept = json.loads(txt)
    done = {p.get("repo") for p in kept if p.get("repo")}
    return kept, done

def write_projects(path, projects_list):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("projects = ")
        json.dump(projects_list, f, indent=4)

# =================== HTTP Session =======================
def gql_session():
    load_dotenv()
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN not found. Put it in .env")
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
    })
    adapter = requests.adapters.HTTPAdapter(pool_connections=POOL_CONN, pool_maxsize=POOL_MAX)
    s.mount("https://", adapter)
    return s

def _sleep_until_reset(reset_at_iso, min_secs=5, jitter=3):
    try:
        reset_at = datetime.datetime.fromisoformat(reset_at_iso.replace("Z", "+00:00"))
        now = datetime.datetime.now(datetime.timezone.utc)
        wait = max(min_secs, int((reset_at - now).total_seconds())) + random.randint(0, jitter)
        if wait > 0:
            print(f"[rateLimit] Sleeping {wait}s until {reset_at_iso}")
            time.sleep(wait)
    except Exception:
        time.sleep(min_secs + random.randint(0, jitter))

def gql_post_with_retry(session, query, variables=None):
    attempt = 0
    while True:
        attempt += 1
        try:
            resp = session.post(GQL_ENDPOINT, json={"query": query, "variables": variables or {}},
                                timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            sleep = min(60, (2 ** min(attempt, 6)) + random.random() * 2)
            print(f"[retry] Network error: {e}. Sleeping {sleep:.1f}s")
            time.sleep(sleep)
            continue

        if resp.status_code >= 500:
            sleep = min(60, (2 ** min(attempt, 6)) + random.random() * 2)
            print(f"[retry] {resp.status_code} from API. Sleeping {sleep:.1f}s")
            time.sleep(sleep)
            continue

        if resp.status_code == 403:
            try:
                payload = resp.json()
            except Exception:
                payload = {}
            rl = (payload.get("data") or {}).get("rateLimit") if isinstance(payload, dict) else None
            if rl and isinstance(rl.get("remaining"), int) and rl["remaining"] <= 0 and rl.get("resetAt"):
                _sleep_until_reset(rl["resetAt"])
            else:
                sleep = min(90, (2 ** min(attempt, 6)) + random.random() * 3)
                print(f"[retry] 403 (secondary limit). Sleeping {sleep:.1f}s")
                time.sleep(sleep)
            continue

        try:
            payload = resp.json()
        except ValueError:
            sleep = min(60, (2 ** min(attempt, 6)) + random.random() * 2)
            print(f"[retry] Non-JSON response. Sleeping {sleep:.1f}s")
            time.sleep(sleep)
            continue

        if "errors" in payload and not payload.get("data"):
            msgs = " | ".join(e.get("message", "") for e in payload["errors"])
            sleep = min(90, (2 ** min(attempt, 6)) + random.random() * 3)
            print(f"[retry] GraphQL errors only: {msgs}. Sleeping {sleep:.1f}s")
            time.sleep(sleep)
            continue

        data = payload.get("data", {})
        rl = data.get("rateLimit")
        if rl and isinstance(rl.get("remaining"), int) and rl["remaining"] <= 1 and rl.get("resetAt"):
            _sleep_until_reset(rl["resetAt"])
        return data

# ================= GraphQL Query/Parsing =================
def build_batch_query(pairs):
    """
    Build a GraphQL query for up to BATCH_SIZE repos.
    We fetch fields needed for demo/example heuristics.
    """
    parts = ["query {"]
    parts.append("  rateLimit { remaining resetAt cost }")
    for alias, owner, name in pairs:
        parts.append(f'''
  {alias}: repository(owner: "{owner}", name: "{name}") {{
    name
    description
    isTemplate
    isArchived
    isDisabled
    repositoryTopics(first: 20) {{ nodes {{ topic {{ name }} }} }}
    defaultBranchRef {{
      target {{
        __typename
        ... on Commit {{
          history(first: 1) {{ totalCount }}
          # top-level tree to check presence of example/demo dirs
          tree: tree {{
            entries {{
              name
              type
            }}
          }}
        }}
      }}
    }}
    releases(first: 1) {{ totalCount }}
    # check CI workflows folder
    workflows: object(expression: "HEAD:.github/workflows") {{
      __typename
      ... on Tree {{ entries {{ name type }} }}
    }}
    # Cargo.toml presence and (if small) text
    cargo: object(expression: "HEAD:Cargo.toml") {{
      __typename
      ... on Blob {{ text byteSize }}
    }}
  }}
        ''')
    parts.append("}")
    return "\n".join(parts)

def flatten_topics(node):
    names = []
    rt = node.get("repositoryTopics") if isinstance(node, dict) else None
    if isinstance(rt, dict):
        for nd in (rt.get("nodes") or []):
            tp = nd.get("topic") if isinstance(nd, dict) else None
            nm = tp.get("name") if isinstance(tp, dict) else None
            if nm:
                names.append(nm)
    return names

def has_demo_dirs(node):
    dbr = node.get("defaultBranchRef") or {}
    tgt = dbr.get("target") or {}
    if tgt.get("__typename") != "Commit":
        return False
    tree = tgt.get("tree") or {}
    for e in (tree.get("entries") or []):
        nm = (e.get("name") or "").lower()
        if nm in DEMO_DIRS:
            return True
    return False

def has_workflows(node):
    w = node.get("workflows") if isinstance(node, dict) else None
    if not isinstance(w, dict) or w.get("__typename") != "Tree":
        return False
    for e in (w.get("entries") or []):
        n = (e.get("name") or "").lower()
        if n.endswith(".yml") or n.endswith(".yaml"):
            return True
    return False

def cargo_name_indicates_demo(node):
    c = node.get("cargo") if isinstance(node, dict) else None
    if isinstance(c, dict) and c.get("__typename") == "Blob":
        # Keep a size guard (GraphQL can return text up to a limit)
        txt = c.get("text") or ""
        if txt and CARGO_NAME_DEMO_RE.search(txt):
            return True
    return False

def is_tiny_activity(node):
    if not USE_TINY_ACTIVITY_HEURISTIC:
        return False
    dbr = node.get("defaultBranchRef") or {}
    tgt = dbr.get("target") or {}
    if tgt.get("__typename") != "Commit":
        return False
    commits = int(((tgt.get("history") or {}).get("totalCount") or 0))
    rels = int((node.get("releases") or {}).get("totalCount") or 0)
    if commits <= MAX_COMMITS_FOR_TINY and (rels == 0 if REQUIRE_NO_RELEASES else True):
        return True
    return False

def looks_like_demo(node):
    """
    Core classifier for demo/example repos.
    Returns True if the repo should be EXCLUDED (i.e., looks like demo/example).
    """
    if not node:
        return True

    # Skip blatantly low-quality states (optional)
    if SKIP_ARCHIVED and node.get("isArchived"):
        return True
    if SKIP_DISABLED and node.get("isDisabled"):
        return True

    name = node.get("name") or ""
    desc = node.get("description") or ""
    topics = [t.lower() for t in flatten_topics(node)]

    # 1) Name/description/topic matches
    if DEMO_RE.search(name) or DEMO_RE.search(desc):
        return True
    if any(DEMO_RE.search(t) for t in topics):
        return True

    # 2) GitHub template repos
    if node.get("isTemplate"):
        return True

    # 3) Obvious demo dirs at repo root
    if has_demo_dirs(node):
        return True

    # 4) Cargo.toml package name hints (e.g., "crate-example", "something-demo")
    if cargo_name_indicates_demo(node):
        return True

    # 5) Tiny activity heuristic (optional)
    if is_tiny_activity(node):
        return True

    return False

# ========================= Main =========================
def main():
    projects = load_projects(INPUT_FILE)
    kept, already_done = load_checkpoint(OUTPUT_FILE)

    # Prepare worklist preserving order
    worklist = [p for p in projects if p.get("repo") and p["repo"] not in already_done]
    total = len(worklist)
    print(f"[init] Input: {len(projects)} | To process: {total} | Kept so far: {len(kept)}")

    session = gql_session()
    processed = 0

    for i in range(0, total, BATCH_SIZE):
        batch = worklist[i:i+BATCH_SIZE]

        pairs = []
        alias_map = {}
        for idx, proj in enumerate(batch):
            alias = f"r{idx}"
            owner, name = proj["repo"].split("/", 1)
            pairs.append((alias, owner, name))
            alias_map[alias] = proj

        query = build_batch_query(pairs)
        data = gql_post_with_retry(session, query)

        for alias, proj in alias_map.items():
            node = data.get(alias)  # None if repo missing/inaccessible
            processed += 1

            # PASS 1: drop demos/examples
            if looks_like_demo(node):
                continue

            # PASS 2: (optional) keep only repos that actually use CI workflows
            if REQUIRE_WORKFLOWS and not has_workflows(node):
                continue

            kept.append(proj)

            if processed % PRINT_EVERY == 0:
                print(f"[progress] {processed}/{len(projects)} processed | kept {len(kept)}")

        if processed % CHECKPOINT_EVERY == 0:
            write_projects(OUTPUT_FILE, kept)
            print(f"[checkpoint] wrote {len(kept)} repos → {OUTPUT_FILE}")

        if PER_BATCH_SLEEP_RANGE != (0.0, 0.0):
            time.sleep(random.uniform(*PER_BATCH_SLEEP_RANGE))

    write_projects(OUTPUT_FILE, kept)
    print(f"[done] processed {processed} repos | kept {len(kept)} → {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
