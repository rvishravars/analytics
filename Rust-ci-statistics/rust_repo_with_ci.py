#!/usr/bin/env python3
import os, json, time, random, requests, datetime
from dotenv import load_dotenv

INPUT_FILE = "rust_repos_over500.json"
OUTPUT_FILE = "repos_with_workflows.json"
GQL_ENDPOINT = "https://api.github.com/graphql"
USER_AGENT = "workflow-checker/1.1"

# pacing knobs
PER_REPO_SLEEP_RANGE = (0.2, 0.6)     # small delay between repos
CHECKPOINT_EVERY = 100                # write partial results every N repos
REQUEST_TIMEOUT = 60                  # seconds for each POST

def load_projects(path):
    with open(path, "r", encoding="utf-8") as f:
        txt = f.read().strip()
        if txt.startswith("projects ="):
            txt = txt[len("projects ="):].strip()
        return json.loads(txt)

def load_checkpoint(path):
    """If OUTPUT_FILE already exists, load and resume."""
    if not os.path.exists(path):
        return [], set()
    with open(path, "r", encoding="utf-8") as f:
        txt = f.read().strip()
        if txt.startswith("projects ="):
            txt = txt[len("projects ="):].strip()
        kept = json.loads(txt)
    done = {p["repo"] for p in kept}
    return kept, done

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
    # Optional: larger connection pool (quiet the "pool is full" warnings)
    adapter = requests.adapters.HTTPAdapter(pool_connections=50, pool_maxsize=50)
    s.mount("https://", adapter)
    return s

def build_query(owner, name):
    return f"""
    query {{
      rateLimit {{ remaining resetAt cost }}
      repo: repository(owner: "{owner}", name: "{name}") {{
        object(expression: "HEAD:.github/workflows") {{
          __typename
          ... on Tree {{
            entries {{ name type }}
          }}
        }}
      }}
    }}
    """

def has_workflows(repo_node):
    obj = repo_node.get("object")
    if not obj or obj.get("__typename") != "Tree":
        return False
    return any((e.get("name") or "").lower().endswith((".yml", ".yaml"))
               for e in (obj.get("entries") or []))

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
    """
    Robust GraphQL POST:
    - Retries on network errors, 5xx, 403 secondary limits, and payloads that only contain 'errors'
    - Observes rateLimit.resetAt when remaining is very low
    - Loops until success (no hard max), but backs off exponentially with jitter
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            resp = session.post(GQL_ENDPOINT, json={"query": query, "variables": variables or {}},
                                timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            # Network hiccup: back off and retry
            sleep = min(60, (2 ** min(attempt, 6)) + random.random() * 2)
            print(f"[retry] Network error: {e}. Sleeping {sleep:.1f}s")
            time.sleep(sleep)
            continue

        # 5xx → backoff & retry
        if resp.status_code >= 500:
            sleep = min(60, (2 ** min(attempt, 6)) + random.random() * 2)
            print(f"[retry] {resp.status_code} from API. Sleeping {sleep:.1f}s")
            time.sleep(sleep)
            continue

        # 403 often = secondary limit
        if resp.status_code == 403:
            # Try to parse and honor reset if present
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

        # Parse JSON
        try:
            payload = resp.json()
        except ValueError:
            sleep = min(60, (2 ** min(attempt, 6)) + random.random() * 2)
            print(f"[retry] Non-JSON response. Sleeping {sleep:.1f}s")
            time.sleep(sleep)
            continue

        # GraphQL errors without data → retry
        if "errors" in payload and not payload.get("data"):
            msgs = " | ".join(e.get("message", "") for e in payload["errors"])
            sleep = min(90, (2 ** min(attempt, 6)) + random.random() * 3)
            print(f"[retry] GraphQL errors only: {msgs}. Sleeping {sleep:.1f}s")
            time.sleep(sleep)
            continue

        data = payload.get("data", {})
        # Rate limit awareness
        rl = data.get("rateLimit")
        if rl and isinstance(rl.get("remaining"), int) and rl["remaining"] <= 1 and rl.get("resetAt"):
            # We got the response, but we're nearly out—sleep to avoid immediate 403 on next call
            _sleep_until_reset(rl["resetAt"])

        return data  # success!

def write_projects(path, projects_list):
    with open(path, "w", encoding="utf-8") as f:
        f.write("projects = ")
        json.dump(projects_list, f, indent=4)

def main():
    projects = load_projects(INPUT_FILE)

    # Resume support if output already exists
    kept, already_done = load_checkpoint(OUTPUT_FILE)
    print(f"[init] Loaded {len(projects)} input repos. Resuming with {len(kept)} kept / {len(already_done)} done.")

    session = gql_session()

    processed = 0
    for proj in projects:
        repo_full = proj["repo"]
        if repo_full in already_done:
            processed += 1
            continue

        owner, name = repo_full.split("/", 1)
        q = build_query(owner, name)
        data = gql_post_with_retry(session, q)

        node = data.get("repo")
        if node and has_workflows(node):
            kept.append(proj)

        already_done.add(repo_full)
        processed += 1

        if processed % 50 == 0:
            print(f"[progress] Checked {processed}/{len(projects)}; kept {len(kept)}")
        if processed % CHECKPOINT_EVERY == 0:
            write_projects(OUTPUT_FILE, kept)
            print(f"[checkpoint] Wrote checkpoint with {len(kept)} repos to {OUTPUT_FILE}")

        # gentle pacing
        time.sleep(random.uniform(*PER_REPO_SLEEP_RANGE))

    # final write
    write_projects(OUTPUT_FILE, kept)
    print(f"[done] Wrote {len(kept)} repos with workflows to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
