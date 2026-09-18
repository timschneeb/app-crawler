#!/usr/bin/env python3
"""Re-sync ignore verdict rows from the current ignore/*.lst files.

The maintainer hand-edits ignore lists (moves entries between subsections,
rewrites reasons, deletes lines). This script makes verdicts.csv reflect the
files: for every verdict==ignore row, update ignore_file/subsection/reason
from the file; rows whose URL is no longer in any file flip to skip.

Usage:
  python3 sync_verdicts_from_ignores.py [--verdicts verdicts.csv]
                                        [--ignore-dir ../ignore] [--dry-run]
"""
import argparse
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import normalize_url  # noqa: E402


def parse_ignore_dir(ignore_dir):
    """Return {norm_url: (fname, subsection, reason)}."""
    found = {}
    for p in sorted(Path(ignore_dir).glob("*.lst")):
        section = None
        for line in p.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s:
                continue
            if s.startswith("# "):
                section = s[2:].strip()
                continue
            if s.startswith("#"):
                continue
            if " #" in s:
                url, reason = s.split(" #", 1)
                url, reason = url.strip(), reason.strip()
            else:
                url, reason = s.split()[0], ""
            found[normalize_url(url)] = (p.name, section or "", reason, url)
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verdicts", default=str(HERE / "verdicts.csv"))
    ap.add_argument("--ignore-dir", default=str(HERE.parent / "ignore"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    found = parse_ignore_dir(args.ignore_dir)
    rows = list(csv.DictReader(open(args.verdicts, encoding="utf-8")))
    updated, moved, removed = 0, 0, []
    for r in rows:
        if r["verdict"].strip() != "ignore":
            continue
        key = normalize_url(r["url"].strip())
        if key not in found:
            r["verdict"] = "skip"
            r["reason"] = ("Manually removed from ignore/*.lst by maintainer; "
                           "left in SUMMARY.md")
            r["ignore_file"] = ""
            r["subsection"] = ""
            removed.append(r["url"].strip())
            continue
        fname, section, reason, _ = found[key]
        if r["subsection"].strip() != section or r["reason"].strip() != reason:
            moved += 1
        if r["ignore_file"].strip() != fname:
            updated += 1
        r["ignore_file"], r["subsection"], r["reason"] = fname, section, reason
    print(f"ignore rows re-synced; file/section/reason drift fixed: {moved + updated}")
    print(f"flipped to skip (gone from files): {len(removed)}")
    for u in removed:
        print(f"  SKIP {u}")
    if not args.dry_run:
        with open(args.verdicts, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(rows)
        print("verdicts.csv updated")


if __name__ == "__main__":
    main()
