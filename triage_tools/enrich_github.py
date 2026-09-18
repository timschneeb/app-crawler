#!/usr/bin/env python3
"""Fetch per-repo evidence from the GitHub API (one pack per queue item).

For each GitHub URL collects: README (language signals), license SPDX,
releases (APK asset check), stars, fork parent, archived flag, activity
dates, topics. Non-GitHub URLs (F-Droid/GitLab) are marked skipped_non_github.

Auth: --token or GITHUB_AUTH env. Without a token the unauthenticated
rate limit (60 req/hour) applies; each repo costs ~3 requests.
Raw responses are cached in cache/triage/<owner>__<repo>.json for resume.

Usage:
  python3 enrich_github.py [--queue triage_queue.json] [--dedup dedup_report.json]
      [--out triage_enriched.json] [--cache-dir ../cache/triage]
      [--limit 10] [--refresh] [--sleep 0.5] [--timeout 30]
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (
    DEFAULT_QUEUE_JSON,
    REPO_ROOT,
    parse_github_owner_repo,
    read_json,
    write_json,
)

try:
    import requests
except ImportError:
    print("error: 'requests' is required (see triage_tools/requirements.txt)", file=sys.stderr)
    sys.exit(2)

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

API = "https://api.github.com"
CJK_RE = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")
LATIN_RE = re.compile(r"[A-Za-z]{2,}")


def analyze_readme(text):
    text = text or ""
    cjk = len(CJK_RE.findall(text))
    latin = len(LATIN_RE.findall(text))
    return {
        "has_english": latin >= 20,
        "has_chinese": cjk >= 20,
        "latin_words": latin,
        "cjk_chars": cjk,
    }


def cache_path(cache_dir, owner, repo):
    safe = f"{owner}__{repo}.json".replace("/", "_")
    return Path(cache_dir) / safe


class GitHub:
    def __init__(self, token, timeout=30):
        self.s = requests.Session()
        self.s.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "User-Agent": "app-crawler-triage",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )
        if token:
            self.s.headers["Authorization"] = f"Bearer {token}"
        self.timeout = timeout

    def get(self, url, raw=False):
        headers = {}
        if raw:
            headers["Accept"] = "application/vnd.github.raw"
        r = self.s.get(url, headers=headers or None, timeout=self.timeout)
        if r.status_code == 403 and r.headers.get("X-RateLimit-Remaining") == "0":
            reset = int(r.headers.get("X-RateLimit-Reset", "0"))
            wait = max(reset - int(time.time()) + 5, 60)
            raise RuntimeError(f"GitHub rate limit hit; retry after {wait}s (reset={reset})")
        return r


def enrich_one(gh, owner, repo, cache_dir, refresh, errors):
    cp = cache_path(cache_dir, owner, repo)
    if cp.is_file() and not refresh:
        try:
            cached = json.loads(cp.read_text(encoding="utf-8"))
            if isinstance(cached, dict) and cached.get("full_name", "").lower() == f"{owner}/{repo}".lower():
                return cached, True
        except Exception as e:
            errors.append(f"cache unreadable, refetching: {e}")

    repo_json, readme_text, releases = {}, "", []
    r = gh.get(f"{API}/repos/{owner}/{repo}")
    if r.status_code != 200:
        errors.append(f"repo API {r.status_code}: {r.text[:200]}")
    else:
        repo_json = r.json()

    r = gh.get(f"{API}/repos/{owner}/{repo}/readme", raw=True)
    if r.status_code == 200:
        readme_text = r.text
    elif r.status_code == 404:
        readme_text = ""
    else:
        errors.append(f"readme API {r.status_code}: {r.text[:200]}")

    r = gh.get(f"{API}/repos/{owner}/{repo}/releases?per_page=30")
    if r.status_code == 200:
        try:
            releases = r.json()
        except Exception as e:
            errors.append(f"releases JSON error: {e}")
    elif r.status_code == 404:
        releases = []
    else:
        errors.append(f"releases API {r.status_code}: {r.text[:200]}")

    apk_assets = []
    for rel in releases if isinstance(releases, list) else []:
        for a in rel.get("assets", []) or []:
            name = a.get("name", "") or ""
            if name.lower().endswith(".apk"):
                apk_assets.append(name)

    lang = analyze_readme(readme_text)
    lic = (repo_json.get("license") or {}).get("spdx_id") or ""
    latest = releases[0] if isinstance(releases, list) and releases else {}
    pack = {
        "full_name": repo_json.get("full_name", f"{owner}/{repo}"),
        "github_description": repo_json.get("description", "") or "",
        "stars": repo_json.get("stargazers_count", 0),
        "fork": bool(repo_json.get("fork", False)),
        "parent": ((repo_json.get("parent") or {}).get("full_name", "")) or "",
        "archived": bool(repo_json.get("archived", False)),
        "disabled": bool(repo_json.get("disabled", False)),
        "pushed_at": repo_json.get("pushed_at", "") or "",
        "created_at": repo_json.get("created_at", "") or "",
        "default_branch": repo_json.get("default_branch", "") or "",
        "topics": repo_json.get("topics", []) or [],
        "open_issues": repo_json.get("open_issues_count", 0),
        "repo_url": repo_json.get("html_url", f"https://github.com/{owner}/{repo}"),
        "readme_present": bool(readme_text),
        "readme_size": len(readme_text),
        "readme_snippet": readme_text[:500].replace("\n", " ").strip(),
        **lang,
        "license_spdx": lic,
        "suggested_spdx": lic if lic and lic != "NOASSERTION" else "Proprietary",
        "releases_count": len(releases) if isinstance(releases, list) else 0,
        "has_apk_asset": bool(apk_assets),
        "apk_asset_names": sorted(set(apk_assets))[:10],
        "latest_release": {
            "name": (latest.get("name") or "") if isinstance(latest, dict) else "",
            "tag": (latest.get("tag_name") or "") if isinstance(latest, dict) else "",
            "url": (latest.get("html_url") or "") if isinstance(latest, dict) else "",
            "published_at": (latest.get("published_at") or "") if isinstance(latest, dict) else "",
        },
        "fetch_errors": errors,
    }
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text(json.dumps({"_readme_truncated": readme_text[:50000], **pack}, ensure_ascii=False, indent=2), encoding="utf-8")
    return pack, False


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--queue", default=str(DEFAULT_QUEUE_JSON))
    ap.add_argument("--dedup", default=None, help="Optional dedup_report.json; skips already-handled items")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "triage_enriched.json"))
    ap.add_argument("--cache-dir", default=str(REPO_ROOT / "cache" / "triage"))
    ap.add_argument("--token", default=os.getenv("GITHUB_AUTH", ""), help="Defaults to $GITHUB_AUTH")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--sleep", type=float, default=0.5)
    ap.add_argument("--timeout", type=int, default=30)
    args = ap.parse_args()

    queue = read_json(args.queue)
    skip = set()
    if args.dedup and Path(args.dedup).is_file():
        for row in read_json(args.dedup):
            if row.get("status") in ("already_in_awesome", "already_ignored"):
                skip.add(row["url"])
    items = [it for it in queue if it["url"] not in skip]
    if args.limit and args.limit > 0:
        items = items[: args.limit]

    gh = GitHub(args.token or "", timeout=args.timeout)
    out = []
    it_iter = tqdm(items, desc="enrich") if tqdm else items
    for it in it_iter:
        pr = parse_github_owner_repo(it["url"])
        if not pr:
            out.append({**it, "skipped": "skipped_non_github", "enriched": {}})
            continue
        owner, repo = pr
        errors = []
        try:
            pack, from_cache = enrich_one(gh, owner, repo, args.cache_dir, args.refresh, errors)
            out.append({**it, "skipped": "", "from_cache": from_cache, "enriched": pack})
        except RuntimeError as e:
            print(f"\nSTOPPING: {e}", file=sys.stderr)
            write_json(args.out, out)
            print(f"partial: wrote {len(out)} records -> {args.out}")
            sys.exit(3)
        except Exception as e:
            out.append({**it, "skipped": "", "enriched": {"fetch_errors": [f"exception: {e}"]}})
        if args.sleep:
            time.sleep(args.sleep)

    write_json(args.out, out)
    n_cache = sum(1 for r in out if r.get("from_cache"))
    n_skip = sum(1 for r in out if r.get("skipped"))
    print(f"enriched {len(out)} items ({n_cache} from cache, {n_skip} non-github) -> {args.out}")


if __name__ == "__main__":
    main()
