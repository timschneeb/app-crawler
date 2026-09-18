#!/usr/bin/env python3
"""Fetch README + LICENSE texts via raw.githubusercontent.com (no GitHub API).

Reads targets (triage_targets.json or triage_queue.json filtered to needs_triage),
tries candidate file names under the HEAD ref, saves first hit per kind into
corpus/<owner>__<repo>__README.md and ...__LICENSE.txt, plus corpus_index.json
recording which URL hit, size, sha1.

Usage:
    ../.venv/bin/python fetch_readmes.py [--targets triage_targets.json]
        [--outdir corpus] [--sleep 0.1] [--timeout 30]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import parse_github_owner_repo as parse_repo_url, read_json, write_json  # noqa: E402

README_CANDS = ["README.md", "README.MD", "Readme.md", "readme.md",
                "README", "README.markdown", "README.mdown", "README.rst"]
LICENSE_CANDS = ["LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE",
                 "LICENCE.md", "COPYING", "COPYING.md", "LICENSE-MIT",
                 "LICENSE-APACHE", "LICENSE-GPL", "UNLICENSE", "COPYLEFT"]


def fetch(url: str, timeout: int) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": "app-crawler-triage/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status != 200:
                return None
            return r.read()
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", default="triage_targets.json")
    ap.add_argument("--outdir", default="corpus")
    ap.add_argument("--sleep", type=float, default=0.1)
    ap.add_argument("--timeout", type=int, default=30)
    args = ap.parse_args()

    base = Path(__file__).resolve().parent
    targets = read_json(str(base / args.targets))
    if isinstance(targets, dict) and "items" in targets:
        targets = targets["items"]
    outdir = base / args.outdir
    outdir.mkdir(exist_ok=True)

    index_path = outdir / "corpus_index.json"
    index: dict = (read_json(str(index_path)) if index_path.exists() else None) or {}

    todo = [t for t in targets if t.get("url") not in index]
    print(f"targets={len(targets)} already_indexed={len(index)} todo={len(todo)}", flush=True)
    try:
        for i, t in enumerate(todo, 1):
            url = t["url"]
            pr = parse_repo_url(url)
            if not pr:
                index[url] = {"error": "unparseable"}
                continue
            owner, repo = pr
            stem = f"{owner}__{repo}"
            rec: dict = {"name": t.get("name"), "readme": None, "license": None}
            for cand in README_CANDS:
                raw = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{cand}"
                body = fetch(raw, args.timeout)
                if body and len(body) >= 50:
                    p = outdir / f"{stem}__README.md"
                    p.write_bytes(body)
                    rec["readme"] = {"file": cand, "bytes": len(body),
                                     "sha1": hashlib.sha1(body).hexdigest()}
                    break
            time.sleep(args.sleep)
            for cand in LICENSE_CANDS:
                raw = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{cand}"
                body = fetch(raw, args.timeout)
                if body and len(body) >= 50:
                    p = outdir / f"{stem}__LICENSE.txt"
                    p.write_bytes(body)
                    rec["license"] = {"file": cand, "bytes": len(body),
                                      "sha1": hashlib.sha1(body).hexdigest()}
                    break
            time.sleep(args.sleep)
            index[url] = rec
            if i % 25 == 0:
                write_json(str(index_path), index)
                print(f"  {i}/{len(todo)}", flush=True)
    finally:
        write_json(str(index_path), index)
    n_readme = sum(1 for r in index.values() if isinstance(r, dict) and r.get("readme"))
    n_lic = sum(1 for r in index.values() if isinstance(r, dict) and r.get("license"))
    print(f"DONE indexed={len(index)} readme={n_readme} license={n_lic}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
