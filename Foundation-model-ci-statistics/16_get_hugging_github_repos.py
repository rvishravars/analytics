#!/usr/bin/env python3
import argparse
import csv
import itertools
import logging
import re
from pathlib import Path
from typing import Iterable, Tuple, Dict, List

import frontmatter
from huggingface_hub import HfApi, hf_hub_download
try:
    # Available in huggingface_hub >= 0.22
    from huggingface_hub.repocard import RepoCard
    HAS_REPOCARD = True
except Exception:
    HAS_REPOCARD = False

from tqdm import tqdm


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Dump <hf_repo, github_url> to CSV",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--org",
        default="",
        help="Hugging Face organisation / user (leave blank for all public repos)",
    )
    p.add_argument(
        "--type",
        choices=("model", "dataset", "space"),
        default="model",
        help="Kind of repository to list",
    )
    p.add_argument(
        "-o",
        "--output",
        default="hf_to_github.csv",
        help="Path to output CSV",
    )
    p.add_argument(
        "--keep-all-links",
        action="store_true",
        help="Store *all* GitHub links found, joined by ';' (default: first match only)",
    )
    p.add_argument(
        "--max-repos",
        type=int,
        default=100,
        help="Maximum number of repos to scan (by likes)",
    )
    p.add_argument(
        "--log-level",
        default="WARNING",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Logging verbosity",
    )
    return p.parse_args()


def compatible_list_repos(api: HfApi, org: str, repo_type: str) -> Iterable:
    """
    Wrapper that chooses the right listing call depending on huggingface_hub version.
    Returns an iterable of objects that always expose some form of repo id.
    """
    # Newer hubs expose list_repos (generic)
    if hasattr(api, "list_repos"):
        return api.list_repos(author=org, repo_type=repo_type, sort="likes", direction=-1)

    # Some in-between versions used list_repositories
    if hasattr(api, "list_repositories"):
        return api.list_repositories(author=org, repo_type=repo_type, sort="likes", direction=-1)

    # Legacy calls
    if repo_type == "model":
        return api.list_models(author=org, sort="likes", direction=-1)
    if repo_type == "dataset":
        return api.list_datasets(author=org, sort="likes", direction=-1)
    if repo_type == "space":
        return api.list_spaces(author=org, sort="likes", direction=-1)

    raise ValueError(f"Unknown repo_type: {repo_type}")


def resolve_repo_id(repo) -> str:
    """
    Normalize repo id across HF Hub versions and entity types.
    """
    return (
        getattr(repo, "repo_id", "")
        or getattr(repo, "modelId", "")
        or getattr(repo, "id", "")
        or ""
    )


GITHUB_RE = re.compile(r"https?://github\.com/[^\s)\"'>]+", re.I)


def extract_github_links(readme_text: str, front_matter: Dict) -> List[str]:
    """Return *all* GitHub URLs in YAML front-matter + Markdown body."""
    blob = " ".join(str(v) for v in front_matter.values()) + " " + (readme_text or "")
    return GITHUB_RE.findall(blob)


def get_card_text(repo_id: str, repo_type: str) -> Tuple[str, Dict]:
    """
    Return (markdown_body, front_matter_dict) for the repo's card,
    or ("", {}) if not available / not supported.
    """
    if not HAS_REPOCARD:
        return "", {}

    try:
        card: RepoCard = RepoCard.load(repo_id=repo_id, repo_type=repo_type)
        md = card.text or ""
        fm = card.data or {}
        return md, fm
    except Exception as e:
        logging.debug("Repocard load failed for %s (%s): %s", repo_id, repo_type, e)
        return "", {}


def fallback_scan_files(repo_id: str, repo_type: str) -> List[str]:
    """
    Try a few common README-like filenames as a fallback.
    """
    candidates = (
        "README.md",
        "README.MD",
        "README.rst",
        "index.md",
        "ModelCard.md",
    )
    for candidate in candidates:
        try:
            p = hf_hub_download(repo_id, candidate, repo_type=repo_type, local_dir=None)
            post = frontmatter.load(p)
            links = extract_github_links(post.content, post.metadata)
            if links:
                return links
        except Exception as e:
            logging.debug("Fallback download failed %s:%s -> %s", repo_id, candidate, e)
            continue
    return []


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level))
    api = HfApi()

    repos = compatible_list_repos(api, args.org, args.type)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    top_repos = itertools.islice(repos, args.max_repos)

    for repo in tqdm(top_repos, desc="scraping", unit="repo", total=args.max_repos):
        repo_id = resolve_repo_id(repo)
        if not repo_id:
            logging.debug("Skipping repo with no identifiable ID: %r", repo)
            continue

        # Prefer the canonical repocard (handles storage/filename differences)
        md, fm = get_card_text(repo_id, args.type)
        links = extract_github_links(md, fm)

        # Fallback to scanning a few likely files
        if not links:
            links = fallback_scan_files(repo_id, args.type)

        if args.keep_all_links:
            github_url = ";".join(sorted(set(links))) if links else ""
        else:
            github_url = links[0] if links else ""

        if not github_url:
            logging.info("No GitHub URL found for %s", repo_id)

        rows.append({"hf_repo": repo_id, "github_url": github_url})

    # Write CSV
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["hf_repo", "github_url"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone! {len(rows)} rows written to {output_path.resolve()}")


if __name__ == "__main__":
    main()
