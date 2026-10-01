#!/usr/bin/env python3
"""Build IGNORE_STARS.md: every URL in ignore/*.lst sorted by stars desc.

Covers all ignore entries with a URL, including inline-commented entries and
skipped subsections/files (out-of-scope.lst, testing-learning.lst). Bare-name
entries have no URL and are excluded. Star counts come from a fetch_stars.py
output JSON ({url: {stars, status}}); entries without a count sort last.

Usage:
  python3 build_ignore_stars_md.py [--stars stars_all.json] [--ignore-dir ../ignore]
      [--out ../IGNORE_STARS.md]
"""

import argparse
import datetime
import sys
from collections import OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DEFAULT_IGNORE_DIR, REPO_ROOT, load_ignore_with_sections, read_json


def collect(ignore_dir):
    entries, _ = load_ignore_with_sections(ignore_dir)
    urls = OrderedDict()
    bare = 0
    for e in entries:
        if e["is_bare_name"]:
            bare += 1
            continue
        rec = urls.setdefault(e["url_norm"], {"url": e["url"], "locs": []})
        loc = f"`{e['file']}` / `{e['subsection']}`"
        if e["has_inline_reason"]:
            loc += " (commented)"
        if loc not in rec["locs"]:
            rec["locs"].append(loc)
    return urls, bare


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    here = Path(__file__).resolve().parent
    ap.add_argument("--stars", default=str(here / "stars_all.json"))
    ap.add_argument("--ignore-dir", default=str(DEFAULT_IGNORE_DIR))
    ap.add_argument("--out", default=str(REPO_ROOT / "IGNORE_STARS.md"))
    args = ap.parse_args()

    stars = read_json(args.stars) if Path(args.stars).is_file() else {}
    urls, bare = collect(args.ignore_dir)

    rows = []
    for rec in urls.values():
        info = stars.get(rec["url"]) or stars.get(rec["url"].rstrip("/")) or {}
        rows.append((info.get("stars"), rec["url"], rec["locs"], info.get("status", "")))
    rows.sort(key=lambda r: (0 if isinstance(r[0], int) else 1, -(r[0] or 0), r[1].lower()))

    known = sum(1 for r in rows if isinstance(r[0], int))
    lines = [
        "# Star counts for ignore-list URLs",
        "",
        f"Generated {datetime.date.today().isoformat()} from `ignore/*.lst` "
        f"({len(rows)} unique URLs with a link, {bare} bare-name entries excluded). "
        f"{known} have a star count; entries without one sort last.",
        "",
        "Includes inline-commented entries and skipped sections "
        "(`out-of-scope.lst`, `testing-learning.lst`). Star counts come from the "
        "GitHub repo pages (the 276 re-triaged entries use the GitHub API value).",
        "",
        "| # | Stars | Link | Ignore location(s) |",
        "| ---: | ---: | --- | --- |",
    ]
    for i, (n, url, locs, status) in enumerate(rows, start=1):
        star = f"{n:,}" if isinstance(n, int) else "?"
        note = "" if isinstance(n, int) else (f" ({status})" if status else " (not GitHub)")
        lines.append(f"| {i} | {star} | <{url}>{note} | {'<br>'.join(locs)} |")
    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} rows ({known} with stars) -> {args.out}")


if __name__ == "__main__":
    main()
