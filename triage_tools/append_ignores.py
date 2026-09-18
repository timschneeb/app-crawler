#!/usr/bin/env python3
"""Append ignore verdicts to ignore/*.lst as `URL # reason`.

Inserts each URL at the end of its target `# subsection` (before the next
`# ` header or EOF). Skips URLs already present (normalized comparison).
Refuses unknown files/subsections.

Usage:
  python3 append_ignores.py --verdicts verdicts.csv [--ignore-dir ../ignore] [--dry-run]
"""
import argparse
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import normalize_url  # noqa: E402


def load_ignore_urls(text):
    urls = set()
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        urls.add(normalize_url(s.split()[0]))
    return urls


def insert_into_section(text, subsection, entry):
    lines = text.splitlines()
    head = f"# {subsection}"
    try:
        start = next(i for i, l in enumerate(lines) if l.strip() == head)
    except StopIteration:
        raise ValueError(f"subsection header not found: {head!r}")
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("# "):
            end = i
            break
    # trim trailing blank lines of the section
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    lines.insert(end, entry)
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verdicts", default=str(HERE / "verdicts.csv"))
    ap.add_argument("--ignore-dir", default=str(HERE.parent / "ignore"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ignore_dir = Path(args.ignore_dir)
    rows = [r for r in csv.DictReader(open(args.verdicts, encoding="utf-8"))
            if (r.get("verdict") or "").strip() == "ignore"]

    # group per file to read/write once
    by_file = {}
    for r in rows:
        by_file.setdefault(r["ignore_file"].strip(), []).append(r)

    total_added, total_skipped = 0, 0
    for fname, rs in sorted(by_file.items()):
        p = ignore_dir / fname
        if not p.is_file():
            print(f"ERROR: unknown ignore file {fname}", file=sys.stderr)
            sys.exit(1)
        text = p.read_text(encoding="utf-8")
        present = load_ignore_urls(text)
        added = skipped = 0
        for r in rs:
            url = r["url"].strip()
            reason = " ".join((r.get("reason") or "").split())
            if normalize_url(url) in present:
                skipped += 1
                continue
            entry = f"{url} # {reason}" if reason else url
            try:
                text = insert_into_section(text, r["subsection"].strip(), entry)
            except ValueError as e:
                print(f"ERROR: {fname}: {e}", file=sys.stderr)
                sys.exit(1)
            present.add(normalize_url(url))
            added += 1
        if not args.dry_run and added:
            p.write_text(text, encoding="utf-8")
        print(f"{fname}: +{added} skipped-already-present={skipped}")
        total_added += added
        total_skipped += skipped
    print(f"total added={total_added} already-present={total_skipped} (dry_run={args.dry_run})")


if __name__ == "__main__":
    main()
