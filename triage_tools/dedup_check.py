#!/usr/bin/env python3
"""Dedup the triage queue against the awesome list and all ignore lists.

For each queue item reports one of:
  already_in_awesome / already_ignored / needs_triage

URL matching is normalized (case/trailing-slash/.git insensitive) and also
mirrors util.py's scheme-stripped substring rule for the awesome list.
Bare-name ignore entries (e.g. 'Shizuku' in forks-duplicates-mirrors.lst)
match on exact repo name.

Usage:
  python3 dedup_check.py [--queue triage_queue.json]
      [--awesome-dir /home/tim/Development/awesome-shizuku]
      [--ignore-dir ../ignore] [--out dedup_report.json]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (
    DEFAULT_AWESOME_DIR,
    DEFAULT_IGNORE_DIR,
    DEFAULT_QUEUE_JSON,
    awesome_match,
    load_awesome_text,
    load_ignore_with_sections,
    normalize_name,
    normalize_url,
    read_json,
    url_key,
    write_json,
)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--queue", default=str(DEFAULT_QUEUE_JSON))
    ap.add_argument("--awesome-dir", default=str(DEFAULT_AWESOME_DIR))
    ap.add_argument("--ignore-dir", default=str(DEFAULT_IGNORE_DIR))
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "dedup_report.json"))
    args = ap.parse_args()

    queue = read_json(args.queue)
    awesome = load_awesome_text(args.awesome_dir)
    ignore_entries, _ = load_ignore_with_sections(args.ignore_dir)

    url_map = {}
    bare_map = {}
    for e in ignore_entries:
        if e["is_bare_name"]:
            bare_map.setdefault(e["name_norm"], e)
        else:
            url_map.setdefault(e["url_norm"], e)

    report = []
    counts = {}
    for it in queue:
        name, url = it["name"], it["url"]
        status, detail = "needs_triage", ""
        m = awesome_match(name, [url], awesome["text"])
        if m:
            status, detail = "already_in_awesome", m
        else:
            hit = url_map.get(normalize_url(url))
            if hit:
                status = "already_ignored"
                detail = f"{hit['file']} / {hit['subsection']}"
            else:
                bare = bare_map.get(normalize_name(name))
                if bare:
                    status = "already_ignored"
                    detail = f"{bare['file']} / {bare['subsection']} (bare-name match)"
                else:
                    # fallback: util.py-style substring on scheme-stripped key
                    key = url_key(url)
                    for e in ignore_entries:
                        if not e["is_bare_name"] and e["url_key"] and e["url_key"] in key:
                            status = "already_ignored"
                            detail = f"{e['file']} / {e['subsection']} (substring match)"
                            break
        counts[status] = counts.get(status, 0) + 1
        report.append({**it, "status": status, "match": detail})

    write_json(args.out, report)
    print(f"checked {len(report)} items -> {args.out}")
    print(f"status counts: {counts}")


if __name__ == "__main__":
    main()
