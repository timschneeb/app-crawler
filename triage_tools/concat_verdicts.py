#!/usr/bin/env python3
"""Concatenate per-slice verdict CSVs into verdicts.csv with adjudication fixes.

Adjudication (systematic, minimal):
  1. Drop duplicate-URL rows (keep first occurrence).
  2. yuyu (MLBB skin injector, cheat/ToS-adjacent) -> skip for maintainer call.
Everything else keeps the reviewer agents' verdicts; unsure cases stay as
judged and are flagged for the human reviewer in the final report.

Usage:
  python3 concat_verdicts.py [--slices verdict_slices] [--out verdicts.csv]
                             [--targets triage_targets.json]
"""
import argparse
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import read_json  # noqa: E402
from draft_entries import FIELDS  # noqa: E402

CHEAT_SKIP_URLS = {
    "https://github.com/groovyrey/yuyu": "MLBB skin injector, cheat/ToS-adjacent - maintainer call",
}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--slices", default=str(HERE / "verdict_slices"))
    ap.add_argument("--out", default=str(HERE / "verdicts.csv"))
    ap.add_argument("--targets", default=str(HERE / "triage_targets.json"))
    args = ap.parse_args()

    rows = []
    for i in range(8):
        p = Path(args.slices) / f"verdicts_{i}.csv"
        with open(p, encoding="utf-8", newline="") as f:
            rows.extend(list(csv.DictReader(f)))
    print(f"read {len(rows)} slice rows")

    # Adjudication 1: yuyu -> skip
    for r in rows:
        if (r.get("url") or "").strip().rstrip("/") in CHEAT_SKIP_URLS:
            r["verdict"] = "skip"
            r["reason"] = CHEAT_SKIP_URLS[(r.get("url") or "").strip().rstrip("/")]
            print(f"adjudicated ->skip: {r['url']}")

    # Adjudication 2: drop duplicate URLs (keep first)
    seen, unique, dropped = set(), [], []
    for r in rows:
        u = (r.get("url") or "").strip().rstrip("/")
        if u in seen:
            dropped.append(f"{u} ({r.get('name')})")
            continue
        seen.add(u)
        unique.append(r)
    print(f"unique: {len(unique)}, dropped dups: {dropped}")

    # Coverage vs targets
    targets = {t["url"].rstrip("/") for t in read_json(args.targets)}
    missing = sorted(targets - seen)
    extra = sorted(seen - targets)
    print(f"targets: {len(targets)}, covered: {len(targets) - len(missing)}")
    if missing:
        print(f"MISSING ({len(missing)}): {missing}")
    if extra:
        print(f"EXTRA ({len(extra)}): {extra}")

    with open(args.out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(unique)
    print(f"wrote {len(unique)} rows -> {args.out}")

    from collections import Counter
    print("verdicts:", dict(Counter((r.get("verdict") or "").strip() for r in unique)))


if __name__ == "__main__":
    main()
