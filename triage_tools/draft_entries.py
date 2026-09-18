#!/usr/bin/env python3
"""Generate CANDIDATES_REVIEW.md + NEW_IGNORES.md from a verdicts CSV.

Verdicts CSV columns:
  url,name,verdict,ignore_file,subsection,category,license,en_desc,reason,
  findings,download,license_source,shizuku_proof,en_status
verdict is one of: candidate | ignore | skip (skip rows produce no output).
  candidate requires: name, category (in AWESOME_CATEGORIES), license, en_desc (<=250 chars)
  ignore requires: ignore_file, subsection, reason

Usage:
  python3 draft_entries.py --init-from-enriched triage_enriched.json [--dedup dedup_report.json]
      [--out-verdicts verdicts.csv]
  python3 draft_entries.py --verdicts verdicts.csv [--candidates-out ../CANDIDATES_REVIEW.md]
      [--ignores-out ../NEW_IGNORES.md] [--check-only]
"""

import argparse
import csv
import html
import sys
from collections import OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import AWESOME_CATEGORIES, read_json

FIELDS = ["url", "name", "verdict", "ignore_file", "subsection", "category",
          "license", "en_desc", "reason", "findings", "download",
          "license_source", "shizuku_proof", "en_status",
          "vibe_score", "vibe_reasons", "alternatives", "recency"]

CAT_ORDER = {c: i for i, c in enumerate(AWESOME_CATEGORIES)}


def clean(s):
    return " ".join((s or "").split())


def validate(rows):
    errors = []
    for i, r in enumerate(rows, start=2):
        v = (r.get("verdict") or "").strip()
        if not v:
            continue  # unreviewed, skipped silently
        if v not in ("candidate", "ignore", "skip"):
            errors.append(f"row {i} ({r.get('url')}): bad verdict {v!r}")
            continue
        if v == "candidate":
            for col in ("name", "category", "license", "en_desc"):
                if not clean(r.get(col)):
                    errors.append(f"row {i} ({r.get('url')}): candidate missing {col}")
            if r.get("category") and r["category"].strip() not in CAT_ORDER:
                errors.append(f"row {i}: unknown category {r['category']!r}")
            if len(clean(r.get("en_desc"))) > 250:
                errors.append(f"row {i} ({r.get('url')}): en_desc is {len(clean(r.get('en_desc')))} chars (>250)")
            if not (r.get("url") or "").startswith("http"):
                errors.append(f"row {i}: bad url {r.get('url')!r}")
        elif v == "ignore":
            for col in ("ignore_file", "subsection", "reason"):
                if not clean(r.get(col)):
                    errors.append(f"row {i} ({r.get('url')}): ignore missing {col}")
    return errors


def candidate_entry(r):
    name, url = clean(r["name"]), clean(r["url"])
    desc, lic = clean(r["en_desc"]), clean(r["license"])
    summary = (f'<a href="{html.escape(url, quote=True)}">{html.escape(name)}</a>'
               f' - {html.escape(desc)} <code>{html.escape(lic)}</code>')
    # Reasoning only: no license/download/EN-docs/category repeats, those are
    # either in the summary above or not important for the decision.
    body = f"Findings: {clean(r.get('findings')) or clean(r.get('reason')) or '-'}"
    if clean(r.get("shizuku_proof")):
        body += f"\n\nShizuku usage: {clean(r['shizuku_proof'])}"
    if lic == "Proprietary":
        body += "\n\nNote: closed-source → target is CLOSED_SOURCE.md, not the main list."
    return f"<details><summary>{summary}</summary>\n\n{body}\n</details>\n"


def ignore_entry(r):
    url = clean(r["url"])
    target_file, target_sub = clean(r["ignore_file"]), clean(r["subsection"])
    n = r.get("_stars")
    prefix = f"★{n:,} " if isinstance(n, int) else "★? "
    summary = (prefix + f'<a href="{html.escape(url, quote=True)}">{html.escape(url)}</a>'
               f' → <code>{html.escape(target_file)}</code>'
               f' / <code>{html.escape(target_sub)}</code>')
    body = f"Why: {clean(r.get('reason'))}"
    extra = " ".join(x for x in [clean(r.get("findings")), clean(r.get("shizuku_proof"))] if x)
    if extra:
        body += f"\n\nEvidence: {extra}"
    return f"<details><summary>{summary}</summary>\n\n{body}\n</details>\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verdicts", default=str(Path(__file__).resolve().parent / "verdicts.csv"))
    ap.add_argument("--init-from-enriched", default=None)
    ap.add_argument("--dedup", default=None)
    ap.add_argument("--out-verdicts", default=None)
    ap.add_argument("--candidates-out", default=str(Path(__file__).resolve().parent.parent / "CANDIDATES_REVIEW.md"))
    ap.add_argument("--ignores-out", default=str(Path(__file__).resolve().parent.parent / "NEW_IGNORES.md"))
    ap.add_argument("--stars", default=None,
                    help="JSON {url: {stars: int|null}}; sorts ignores within each "
                         "file/subsection group by stars desc (unknown last)")
    ap.add_argument("--check-only", action="store_true")
    args = ap.parse_args()

    if args.init_from_enriched:
        enriched = read_json(args.init_from_enriched)
        skip = set()
        if args.dedup and Path(args.dedup).is_file():
            for row in read_json(args.dedup):
                if row.get("status") in ("already_in_awesome", "already_ignored"):
                    skip.add(row["url"])
        out_csv = args.out_verdicts or args.verdicts
        n = 0
        with open(out_csv, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            for rec in enriched:
                if rec["url"] in skip or rec.get("skipped"):
                    continue
                e = rec.get("enriched", {}) or {}
                w.writerow({
                    "url": rec["url"], "name": rec.get("name", ""), "verdict": "",
                    "ignore_file": "", "subsection": "", "category": "",
                    "license": e.get("suggested_spdx", ""), "en_desc": "",
                    "reason": "", "findings": e.get("github_description", ""),
                    "download": ("APK in releases" if e.get("has_apk_asset") else ""),
                    "license_source": "", "shizuku_proof": "",
                    "en_status": ("EN README" if e.get("has_english")
                                   else ("Chinese-only README" if e.get("has_chinese") else "")),
                })
                n += 1
        print(f"wrote {n} skeleton rows -> {out_csv}")
        return

    with open(args.verdicts, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    errors = validate(rows)
    if errors:
        print("VALIDATION ERRORS:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)
    print(f"validated {len(rows)} verdict rows: OK")
    if args.check_only:
        return

    cands = [r for r in rows if (r.get("verdict") or "").strip() == "candidate"]
    igns = [r for r in rows if (r.get("verdict") or "").strip() == "ignore"]

    by_cat = OrderedDict()
    for r in sorted(cands, key=lambda r: (CAT_ORDER.get(clean(r["category"]), 999), clean(r["name"]).lower())):
        by_cat.setdefault(clean(r["category"]), []).append(r)

    out_c = ["# Candidates for awesome-shizuku (review)\n",
             f"Source: SUMMARY.md triage. {len(cands)} candidate(s).\n"]
    for cat, rs in by_cat.items():
        out_c.append(f"\n## {cat}\n")
        for r in rs:
            out_c.append("\n" + candidate_entry(r))
    Path(args.candidates_out).write_text("\n".join(out_c), encoding="utf-8")

    by_target = OrderedDict()
    stars = {}
    if args.stars and Path(args.stars).is_file():
        stars = {u: (v or {}).get("stars") for u, v in read_json(args.stars).items()}

    def ignore_key(r):
        n = stars.get(clean(r["url"]))
        r["_stars"] = n
        return (clean(r["ignore_file"]), clean(r["subsection"]),
                0 if n is not None else 1, -(n or 0), clean(r["url"]))

    for r in sorted(igns, key=ignore_key):
        by_target.setdefault((clean(r["ignore_file"]), clean(r["subsection"])), []).append(r)

    out_i = ["# Proposed ignore additions (review)\n",
             f"{len(igns)} entr(y/ies). Each was also appended to ignore/*.lst as `URL # reason`.\n"]
    for (f_, s_), rs in by_target.items():
        out_i.append(f"\n## `{f_}` / `{s_}`\n")
        for r in rs:
            out_i.append("\n" + ignore_entry(r))
    Path(args.ignores_out).write_text("\n".join(out_i), encoding="utf-8")

    print(f"wrote {len(cands)} candidates -> {args.candidates_out}")
    print(f"wrote {len(igns)} ignores -> {args.ignores_out}")
    print(f"skipped rows: {len(rows) - len(cands) - len(igns)} (empty verdict or 'skip')")


if __name__ == "__main__":
    main()
