#!/usr/bin/env python3
"""Extract the triage work queue from SUMMARY.md.

Scope (default: all of '### Apps with releases', i.e. both the
'Updated in the last 3 months' and 'Updated more than 3 months ago'
subsections, including their '<details>' blocks tagged
group=main|non-original|no-stars and recency=recent|older).
Use --recent-only for just the 'last 3 months' slice, and
--no-releases to target '### Apps with no releases' instead.

Usage:
  python3 triage_extract.py [--summary ../SUMMARY.md] [--out-json triage_queue.json]
      [--out-csv triage_queue.csv] [--limit 5] [--print] [--recent-only]
      [--no-releases]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (
    DEFAULT_QUEUE_CSV,
    DEFAULT_QUEUE_JSON,
    DEFAULT_SUMMARY,
    parse_summary_no_releases,
    parse_summary_releases,
    write_json,
    write_queue_csv,
)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--summary", default=str(DEFAULT_SUMMARY))
    ap.add_argument("--out-json", default=str(DEFAULT_QUEUE_JSON))
    ap.add_argument("--out-csv", default=str(DEFAULT_QUEUE_CSV))
    ap.add_argument("--limit", type=int, default=0, help="Only take first N items (dry run)")
    ap.add_argument("--print", dest="do_print", action="store_true", help="Print items to stdout")
    ap.add_argument("--recent-only", action="store_true", help="Only the 'Updated in the last 3 months' slice")
    ap.add_argument("--no-releases", action="store_true",
                    help="Parse '### Apps with no releases' instead of '### Apps with releases'")
    args = ap.parse_args()

    parser = parse_summary_no_releases if args.no_releases else parse_summary_releases
    items = parser(args.summary, recent_only=args.recent_only)
    if args.limit and args.limit > 0:
        items = items[: args.limit]

    write_json(args.out_json, items)
    write_queue_csv(args.out_csv, items)

    groups = {}
    for it in items:
        groups[f"{it.get('recency', '?')}/{it['group']}"] = groups.get(f"{it.get('recency', '?')}/{it['group']}", 0) + 1
    print(f"wrote {len(items)} items -> {args.out_json}, {args.out_csv}")
    print(f"groups: {groups}")
    if args.do_print:
        for it in items:
            print(f"[{it.get('recency', '?')}/{it['group']}] {it['name']} {it['url']}")


if __name__ == "__main__":
    main()
