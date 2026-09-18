#!/usr/bin/env python3
"""Move non-English entries from 'Insufficient documentation' to a new
'Non-English documentation' subsection of immature-undocumented.lst.

Match rule (mine only = rows present in verdicts.csv as ignore):
  en_status explicitly non-English-only, OR
  (en_status empty AND meta cjk_ratio >= 0.30)

Updates verdicts.csv, rewrites the .lst file sections, and leaves
NEW_IGNORES.md regeneration to draft_entries.py.

Usage:
  python3 move_nonenglish.py [--verdicts verdicts.csv]
                             [--ignore-file ../ignore/immature-undocumented.lst]
"""
import argparse
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

SRC_SUB = "Insufficient documentation"
DST_SUB = "Non-English documentation"
IGNORE_FNAME = "immature-undocumented.lst"

NON_EN_MARKERS = ("chinese-only", "chinese-primary", "indonesian-only",
                  "spanish-only", "portuguese-only", "vietnamese-only",
                  "japanese-only", "korean-only", "korean-dominant",
                  "russian-only")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verdicts", default=str(HERE / "verdicts.csv"))
    ap.add_argument("--ignore-file",
                    default=str(HERE.parent / "ignore" / IGNORE_FNAME))
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.verdicts, encoding="utf-8")))
    items = {}
    for line in open(HERE / "review_items.jsonl", encoding="utf-8"):
        it = json.loads(line)
        items[it["url"].rstrip("/")] = it

    moved = []
    for r in rows:
        if (r["verdict"].strip() != "ignore"
                or r["ignore_file"].strip() != IGNORE_FNAME
                or r["subsection"].strip() != SRC_SUB):
            continue
        en = (r.get("en_status") or "").lower()
        m = ((items.get(r["url"].strip().rstrip("/"), {}).get("meta")) or {})
        if (any(marker in en for marker in NON_EN_MARKERS)
                or (not en.strip() and (m.get("cjk_ratio") or 0) >= 0.30)):
            r["subsection"] = DST_SUB
            moved.append(r["url"].strip())
    print(f"moving {len(moved)} entries -> '{DST_SUB}'")
    for u in sorted(moved):
        print(f"  {u}")

    with open(args.verdicts, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)

    # Rewrite the .lst: drop moved URLs from SRC section, append new section.
    move_keys = {u.rstrip("/") for u in moved}
    p = Path(args.ignore_file)
    lines = p.read_text(encoding="utf-8").splitlines()
    head_src, head_dst = f"# {SRC_SUB}", f"# {DST_SUB}"
    assert head_src in [l.strip() for l in lines], "src header missing"
    assert head_dst not in [l.strip() for l in lines], "dst header already exists"

    kept, taken = [], []
    for line in lines:
        s = line.strip()
        if (s and not s.startswith("#") and " #" in s
                and s.split(" #", 1)[0].rstrip().rstrip("/") in move_keys):
            taken.append(line)
            continue
        kept.append(line)
    print(f"took {len(taken)} lines out of '{SRC_SUB}'")
    assert len(taken) == len(moved), (len(taken), len(moved))

    # Keep file tidy: strip trailing blank lines, then append new section.
    while kept and not kept[-1].strip():
        kept.pop()
    kept += ["", head_dst, ""] + taken + [""]
    p.write_text("\n".join(kept), encoding="utf-8")
    print(f"appended '# {DST_SUB}' with {len(taken)} entries")


if __name__ == "__main__":
    main()
