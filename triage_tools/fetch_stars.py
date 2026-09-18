#!/usr/bin/env python3
"""Fetch GitHub star counts from public repo HTML pages (NOT the GitHub API).

Parses the stargazers link/aria-label from https://github.com/{owner}/{repo}.
Polite sequential fetching with resume cache. Unparseable pages -> stars null
(they sort last; nothing fails).

Usage:
  python3 fetch_stars.py [--verdicts verdicts.csv] [--verdict ignore]
                         [--out stars.json] [--sleep 1.0] [--timeout 25] [--limit N]
"""
import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import parse_github_owner_repo  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}


def parse_stars(html_text):
    m = re.search(r'aria-label="([0-9,.]+[kKmM]?)\s+users?\s+starred', html_text)
    if m:
        return m.group(1)
    m = re.search(r'href="/[^"]+/stargazers"[^>]*>\s*(?:<[a-z][^>]*>\s*)*([0-9][0-9,.]*[kKmM]?)',
                  html_text)
    return m.group(1) if m else None


def to_int(raw):
    if raw is None:
        return None
    s = raw.replace(",", "").strip()
    try:
        if s[-1:] in "kK":
            return int(float(s[:-1]) * 1000)
        if s[-1:] in "mM":
            return int(float(s[:-1]) * 1000000)
        return int(float(s))
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verdicts", default=str(HERE / "verdicts.csv"))
    ap.add_argument("--verdict", default="ignore", help="only fetch stars for this verdict")
    ap.add_argument("--out", default=str(HERE / "stars.json"))
    ap.add_argument("--sleep", type=float, default=1.0)
    ap.add_argument("--timeout", type=int, default=25)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    import csv
    urls = []
    for r in csv.DictReader(open(args.verdicts, encoding="utf-8")):
        if (r.get("verdict") or "").strip() == args.verdict:
            u = (r.get("url") or "").strip()
            if parse_github_owner_repo(u):
                urls.append(u)
    print(f"targets: {len(urls)}")
    if args.limit:
        urls = urls[:args.limit]

    out_path = Path(args.out)
    stars = json.loads(out_path.read_text(encoding="utf-8")) if out_path.is_file() else {}
    todo = [u for u in urls if u not in stars]
    print(f"already cached: {len(urls) - len(todo)}, to fetch: {len(todo)}")

    done = 0
    try:
        for u in todo:
            owner, repo = parse_github_owner_repo(u)
            try:
                req = urllib.request.Request(f"https://github.com/{owner}/{repo}", headers=UA)
                with urllib.request.urlopen(req, timeout=args.timeout) as resp:
                    html_text = resp.read().decode("utf-8", errors="replace")
                n = to_int(parse_stars(html_text))
                stars[u] = {"stars": n, "status": "ok" if n is not None else "unparsed"}
            except Exception as e:  # noqa: BLE001 - record and continue
                stars[u] = {"stars": None, "status": f"error: {type(e).__name__}"}
            done += 1
            if done % 25 == 0:
                out_path.write_text(json.dumps(stars, indent=1), encoding="utf-8")
                print(f"  {done}/{len(todo)}", flush=True)
            time.sleep(args.sleep)
    finally:
        out_path.write_text(json.dumps(stars, indent=1), encoding="utf-8")
    ok = sum(1 for v in stars.values() if v.get("stars") is not None)
    print(f"done: {len(stars)} entries, {ok} with star counts -> {out_path}")


if __name__ == "__main__":
    main()
