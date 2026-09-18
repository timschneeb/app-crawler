#!/usr/bin/env python3
"""Apply maintainer_decisions.json (exported from review.html) to verdicts.csv.

decisions:
  accept -> verdict=candidate (keep it)
  skip   -> verdict=skip (drop from both outputs)
  deny   -> verdict=ignore with deny_file / deny_subsection (+reason/note)

Also rewrites user-facing en_desc so that "Shizuku UserService" / "user service"
wording is shown simply as "Shizuku".

Usage:
  python3 apply_maintainer_decisions.py [--decisions maintainer_decisions.json]
      [--verdicts triage_tools/verdicts.csv] [--dry-run]
"""

import argparse
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import read_json
from draft_entries import FIELDS

ROOT = Path(__file__).resolve().parent.parent

CATEGORY_OVERRIDES = {
    "https://github.com/JarJarBlinkz/Evolve_Launcher_v2": "Other",
    "https://github.com/Dinico414/MindControl": "Other",
}

EN_DESC_OVERRIDES = {
    "https://github.com/mekhontsev/magicdesk":
        "Open-source Android 15+ workstation with native windows, external displays, "
        "desktops and Termux integration via Shizuku",
}

FINDINGS_PREFIX = {
    "https://github.com/SysAdminDoc/AppManagerNG":
        "Fork of AppManager (https://github.com/muntashirakon/appmanager). ",
}

FINDINGS_APPEND = {
    "https://github.com/GloriousApps/HyperOS-MTZ-Studio":
        " Link to English readme: https://github.com/GloriousApps/HyperOS-MTZ-Studio/blob/main/readme_en.md",
    "https://github.com/RyensX/MemorySnapshot":
        " Link to English readme: https://github.com/RyensX/MemorySnapshot/blob/master/docs/README_EN.md",
    "https://github.com/Horizen5/Appslim":
        " Link to English readme: https://github.com/Horizen5/Appslim/blob/master/docs/README_en.md",
    "https://github.com/BugeStudioTeam/Buge-Files":
        " Main link: https://bugestudio.website/files/ ; source code: https://github.com/BugeStudioTeam/Buge-Files",
}

DENY_REASONS = {
    "https://github.com/Bodo121/S22-Updater":
        "Single-firmware KernelSU/root payload updater; equivalent tuning tools already listed.",
    "https://github.com/kavastore/nothing-dot":
        "Device-specific Glyph/AOD toolkit; equivalent alternatives already listed.",
    "https://github.com/peakSee/Wanxiang":
        "On-device AI agent/Linux sandbox overlapping existing AI-agent listings.",
    "https://github.com/Soodok/Deepseek-Harness-Local-Android":
        "Another on-device DeepSeek harness; AI-agent space already crowded.",
    "https://github.com/colonelpanic8/eva":
        "AI voice assistant overlapping existing agent/assistant apps.",
    "https://github.com/meatcar/split-voice":
        "Experimental and not working or useful enough to list.",
    "https://github.com/nowa277/OpenConverter":
        "Protected-key extraction relies on root/Xposed-class privileged access.",
    "https://github.com/markvoronin354/WheelReels":
        "Shizuku used only for input injection; insufficient Shizuku application.",
    "https://github.com/Alisuuu/Crossset":
        "System/secure/global settings editor of low quality; debug-only builds.",
}

# "a privileged Shizuku user service", "Shizuku-bound shell UserService", etc.
USER_SERVICE_RE = re.compile(
    r"(?i)\b(?:a\s+|an\s+)?(?:privileged\s+)?Shizuku(?:-backed|-bound)?"
    r"(?:[\s/]+Sui)?[\s/-]*(?:shell[\s-]+)?user[\s-]?service\b")
LEFTOVER_RE = re.compile(r"(?i)\buser[\s-]?service\b")


def fix_desc(s):
    if not s:
        return s
    s = USER_SERVICE_RE.sub("Shizuku", s)
    s = LEFTOVER_RE.sub("Shizuku", s)
    s = re.sub(r"\bShizuku(?:\s+Shizuku)+\b", "Shizuku", s)
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--decisions", default=str(ROOT / "maintainer_decisions.json"))
    ap.add_argument("--verdicts", default=str(ROOT / "triage_tools" / "verdicts.csv"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    decisions = read_json(args.decisions)
    with open(args.verdicts, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    by = {r["url"]: r for r in rows}

    missing = [u for u in decisions if u not in by]
    counts = {"accept": 0, "skip": 0, "deny": 0}
    for url, v in decisions.items():
        r = by.get(url)
        if r is None:
            continue
        dec = v["decision"]
        if dec == "accept":
            r["verdict"] = "candidate"
            r["ignore_file"] = ""
            r["subsection"] = ""
        elif dec == "skip":
            r["verdict"] = "skip"
            r["ignore_file"] = ""
            r["subsection"] = ""
            r["reason"] = ""
        elif dec == "deny":
            r["verdict"] = "ignore"
            r["ignore_file"] = v.get("deny_file", "")
            r["subsection"] = v.get("deny_subsection", "")
            r["reason"] = (v.get("reason") or v.get("note")
                           or DENY_REASONS.get(url, ""))
        else:
            raise SystemExit(f"unknown decision {dec!r} for {url}")
        counts[dec] += 1

        if url in CATEGORY_OVERRIDES:
            r["category"] = CATEGORY_OVERRIDES[url]
        if url in EN_DESC_OVERRIDES:
            r["en_desc"] = EN_DESC_OVERRIDES[url]
        if url in FINDINGS_PREFIX:
            r["findings"] = FINDINGS_PREFIX[url] + (r.get("findings") or "")
        if url in FINDINGS_APPEND:
            r["findings"] = (r.get("findings") or "") + FINDINGS_APPEND[url]

    leftover = []
    for r in rows:
        r["en_desc"] = fix_desc(r.get("en_desc") or "")
        if LEFTOVER_RE.search(r["en_desc"]):
            leftover.append(r["url"])

    print(f"decisions: {len(decisions)}  applied: {counts}")
    if missing:
        print(f"WARNING: {len(missing)} decision URL(s) not in verdicts.csv:")
        for u in missing:
            print("  -", u)
    if leftover:
        print(f"WARNING: leftover user-service wording in {len(leftover)} en_desc")

    if args.dry_run:
        print("(dry-run: verdicts.csv not written)")
        return

    with open(args.verdicts, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    print(f"wrote {len(rows)} rows -> {args.verdicts}")


if __name__ == "__main__":
    main()
