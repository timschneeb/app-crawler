#!/usr/bin/env python3
"""Apply ignore_decisions.json (exported from review_ignores.html).

decisions:
  confirm -> keep the entry in its ignore list (no change)
  skip    -> leave undecided (no change, entry stays)
  reject  -> remove the entry from the ignore file it was proposed for

Usage:
  python3 apply_ignore_decisions.py [--decisions ignore_decisions.json]
      [--ignore-dir ignore] [--dry-run]
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from common import read_json  # noqa: E402


def normalize_url(u):
    u = (u or "").strip().lower().rstrip("/")
    if u.endswith(".git"):
        u = u[:-4]
    return u


def line_url(line):
    s = line.strip()
    if not s or s.startswith("#"):
        return ""
    return normalize_url(s.split(" # ", 1)[0].split("#", 1)[0].strip())


def load(path):
    return path.read_text(encoding="utf-8").splitlines(keepends=True)


def subsection_of(lines, idx):
    for i in range(idx, -1, -1):
        if lines[i].startswith("# "):
            return lines[i][2:].strip()
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--decisions", default=str(ROOT / "ignore_decisions.json"))
    ap.add_argument("--ignore-dir", default=str(ROOT / "ignore"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    decisions = read_json(args.decisions)
    ignore_dir = Path(args.ignore_dir)
    cache = {}
    removed = {}
    confirmed = 0
    changed_files = set()
    warnings = []

    for url, v in decisions.items():
        dec = (v.get("decision") or "").strip()
        fname = v.get("file") or ""
        sub = v.get("subsection") or ""
        if dec == "confirm":
            confirmed += 1
            continue
        if dec == "skip":
            continue
        if dec != "reject":
            warnings.append(f"unknown decision {dec!r} for {url}")
            continue
        if not fname:
            warnings.append(f"reject without file: {url}")
            continue
        p = ignore_dir / fname
        if p not in cache:
            if not p.is_file():
                warnings.append(f"missing ignore file: {fname}")
                continue
            cache[p] = load(p)
        lines = cache[p]
        nu = normalize_url(url)
        hits = [i for i, ln in enumerate(lines) if line_url(ln) == nu]
        if not hits:
            warnings.append(f"not found in {fname}: {url}")
            continue
        if len(hits) > 1:
            warnings.append(f"multiple entries in {fname}: {url}")
        idx = hits[0]
        actual_sub = subsection_of(lines, idx)
        if sub and actual_sub != sub:
            warnings.append(
                f"subsection mismatch for {url}: expected {sub!r}, found {actual_sub!r}")
        del lines[idx]
        removed[fname] = removed.get(fname, 0) + 1
        changed_files.add(p)
        for q in ignore_dir.glob("*.lst"):
            if q != p and any(line_url(ln) == nu for ln in q.read_text(
                    encoding="utf-8").splitlines()):
                warnings.append(f"also present in {q.name}: {url}")

    total = sum(removed.values())
    print(f"decisions: {len(decisions)}  confirm: {confirmed}  "
          f"skip: {len(decisions) - confirmed - total}  reject: {total}")
    for f in sorted(removed):
        print(f"  {f}: -{removed[f]}")
    if warnings:
        print(f"\nWARNING: {len(warnings)} issue(s):")
        for w in warnings:
            print("  -", w)

    if args.dry_run:
        print("(dry-run: ignore files not written)")
        return

    for p in sorted(changed_files):
        p.write_text("".join(cache[p]), encoding="utf-8")
    print(f"\nwrote {len(changed_files)} file(s)")


if __name__ == "__main__":
    main()
