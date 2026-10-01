#!/usr/bin/env python3
"""Extract the re-triage work queue from the ignore/*.lst files.

Scope:
  - skips entries that have an inline comment ('URL # reason') because
    those were already triaged with the new tools
  - skips bare-name entries (no URL to inspect)
  - skips out-of-scope.lst and testing-learning.lst entirely
  - skips the subsections '# Deprecated or archived',
    '# Succeeded by a fork', '# Already in list from another source' and
    '# Duplicates / Detached forks with useless or no changes'

Items carry file/subsection/lineno so the regular triage pipeline
(enrich_github, clone_inspect, draft_entries) can consume them and the
final verdicts can be routed back to the original section.

Usage:
  python3 extract_ignore_queue.py [--ignore-dir ../ignore]
      [--out-json ignore_queue.json] [--out-csv ignore_queue.csv]
      [--limit N] [--print]
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DEFAULT_IGNORE_DIR, load_ignore_with_sections, write_json

SKIP_FILES = {"out-of-scope.lst", "testing-learning.lst"}
SKIP_SUBSECTIONS = {
    "Deprecated or archived",
    "Succeeded by a fork",
    "Already in list from another source",
    "Duplicates / Detached forks with useless or no changes",
}
CSV_FIELDS = ["name", "url", "file", "subsection", "lineno"]


def item_name(url):
    return url.rstrip("/").rsplit("/", 1)[-1] or url


def extract(ignore_dir):
    entries, _ = load_ignore_with_sections(ignore_dir)
    items = []
    for e in entries:
        if e["file"] in SKIP_FILES or e["subsection"] in SKIP_SUBSECTIONS:
            continue
        if e["has_inline_reason"] or e["is_bare_name"]:
            continue
        items.append({
            "name": item_name(e["url"]),
            "url": e["url"],
            "file": e["file"],
            "subsection": e["subsection"],
            "lineno": e["lineno"],
        })
    return items


def write_queue_csv(path, items):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for it in items:
            w.writerow({k: it.get(k, "") for k in CSV_FIELDS})


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    here = Path(__file__).resolve().parent
    ap.add_argument("--ignore-dir", default=str(DEFAULT_IGNORE_DIR))
    ap.add_argument("--out-json", default=str(here / "ignore_queue.json"))
    ap.add_argument("--out-csv", default=str(here / "ignore_queue.csv"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--print", dest="do_print", action="store_true")
    args = ap.parse_args()

    items = extract(args.ignore_dir)
    if args.limit and args.limit > 0:
        items = items[: args.limit]

    write_json(args.out_json, items)
    write_queue_csv(args.out_csv, items)

    counts = {}
    for it in items:
        key = f"{it['file']} / {it['subsection']}"
        counts[key] = counts.get(key, 0) + 1
    print(f"wrote {len(items)} items -> {args.out_json}, {args.out_csv}")
    for key in sorted(counts):
        print(f"  {counts[key]:4d}  {key}")
    if args.do_print:
        for it in items:
            print(f"{it['file']}:{it['lineno']}  {it['url']}")


if __name__ == "__main__":
    main()
