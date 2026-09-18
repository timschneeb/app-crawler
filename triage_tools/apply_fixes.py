#!/usr/bin/env python3
"""Apply maintainer re-review: undo selected ignores (->skip) and promote 6 to candidate.

Usage:
  python3 apply_fixes.py [--verdicts verdicts.csv] [--ignore-dir ../ignore]
"""
import argparse
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

FORK_URLS = {
    "https://github.com/roro2239/Stellar",
    "https://github.com/yijiacloud/shizuku-next",
    "https://github.com/Leaf-lsgtky/mizuku",
    "https://github.com/kerneldroid/Nightzuku",
    "https://github.com/Itsfitts/ShizukuCrimson",
    "https://github.com/DarkmoonOnDiscord/Cinnazuku",
    "https://github.com/HmnDev-Tech/shevery",
    "https://github.com/qianyumeng0228/ShizukuX",
    "https://github.com/xm1437/Shizako",
}

PROMOTE = {
    "https://github.com/DroidUtility/DroidUtility": {
        "category": "Software management", "license": "MIT",
        "en_desc": "All-in-one non-root utility suite: debloating, system tweaks, and terminal command execution via Shizuku. Designed for mobile-only developers.",
        "findings": "Real Shizuku dep plus provider/rish source hits; EN README with APK link.",
        "download": "APK link in README", "license_source": "LICENSE file (MIT)",
        "shizuku_proof": "Shizuku API dep with provider and rish source usage",
        "en_status": "English README",
    },
    "https://github.com/MrsEWE44/easyManager": {
        "category": "Software management", "license": "Proprietary",
        "en_desc": "Lightweight and minimal Android system toolbox with EN/CN docs, using Shizuku and Dhizuku for privileged operations.",
        "findings": "EN translation (README_EN.md) plus releases; Shizuku dep and Dhizuku source hits.",
        "download": "GitHub Releases", "license_source": "No LICENSE file",
        "shizuku_proof": "Shizuku dep with Dhizuku source hits",
        "en_status": "English README_EN.md alongside Chinese main README",
    },
    "https://github.com/niki914/libterm": {
        "category": "Development utilities", "license": "Proprietary",
        "en_desc": "Kotlin-first Android terminal session library on top of libsu, Shizuku, and SSH backends behind a unified multi-session API.",
        "findings": "Terminal library over libsu/Shizuku/SSH backends; EN README with 48 dep hits.",
        "download": "Library, source/Maven (no app download)", "license_source": "No LICENSE file",
        "shizuku_proof": "Shizuku dep with provider and UserService source hits",
        "en_status": "English README (plus Chinese)",
    },
    "https://github.com/priv-kit/priv-kit": {
        "category": "Development utilities", "license": "Proprietary",
        "en_desc": "Lightweight Android library for apps to start and manage their own privileged process via root, ADB, Binder handoff, or UserService.",
        "findings": "Privileged-runtime library with 63 UserService source hits; published on Maven Central.",
        "download": "Maven Central", "license_source": "No LICENSE file",
        "shizuku_proof": "Shizuku dep with provider and UserService source hits",
        "en_status": "English README (plus Chinese)",
    },
    "https://github.com/stixez/droid-mcp": {
        "category": "AI agents", "license": "Apache-2.0",
        "en_desc": "On-device SDK giving Android AI apps structured access to the whole phone: PIM data, UI control, and shell admin via Shizuku.",
        "findings": "145 tools across 53 modules; Shizuku shell-UID admin; EN docs with APK link.",
        "download": "APK link in README", "license_source": "LICENSE file (Apache-2.0)",
        "shizuku_proof": "Shizuku dep with provider, UserService, and rish source hits",
        "en_status": "English README",
    },
    "https://github.com/soul-99/SU_IMD": {
        "category": "Automation", "license": "GPL-3.0",
        "en_desc": "Supercharged Geto fork: live-status settings/services manager and hider that toggles settings off and on around restrictive apps.",
        "findings": "Geto-based settings manager/hider with releases and EN docs; fork with substantial added features.",
        "download": "GitHub Releases", "license_source": "LICENSE file (GPL-3.0)",
        "shizuku_proof": "Shizuku dep with provider source hits",
        "en_status": "English README",
    },
}

SKIP_REASON = "Left in SUMMARY.md per maintainer decision (re-review, no verdict yet)"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verdicts", default=str(HERE / "verdicts.csv"))
    ap.add_argument("--ignore-dir", default=str(HERE.parent / "ignore"))
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.verdicts, encoding="utf-8")))
    by_url = {r["url"].strip(): r for r in rows}

    undone, promoted = [], []
    for r in rows:
        u = r["url"].strip()
        if u in PROMOTE:
            p = PROMOTE[u]
            assert r["verdict"].strip() == "ignore", f"expected ignore for {u}"
            r["verdict"] = "candidate"
            r["ignore_file"] = ""
            r["subsection"] = ""
            r["reason"] = ""
            for k in ("category", "license", "en_desc", "findings", "download",
                      "license_source", "shizuku_proof", "en_status"):
                r[k] = p[k]
            assert len(p["en_desc"]) <= 250, u
            promoted.append(u)
        elif (u in FORK_URLS or (r["ignore_file"].strip() == "out-of-scope.lst"
              and r["subsection"].strip() == "Explicitly does not provide downloads currently")):
            if r["verdict"].strip() == "ignore":
                r["verdict"] = "skip"
                r["ignore_file"] = ""
                r["subsection"] = ""
                r["reason"] = SKIP_REASON
                undone.append(u)

    print(f"promoted to candidate: {len(promoted)}")
    print(f"undone to skip: {len(undone)}")
    assert len(promoted) == 6, promoted
    assert len(undone) == 48, len(undone)

    with open(args.verdicts, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)

    # Remove their lines from ignore/*.lst (match by URL prefix; only our
    # `URL # reason` additions reference these URLs).
    targets = set(undone) | set(promoted)
    ignore_dir = Path(args.ignore_dir)
    removed_total = 0
    for p in sorted(ignore_dir.glob("*.lst")):
        lines = p.read_text(encoding="utf-8").splitlines()
        kept = [l for l in lines
                if not (l.strip() and not l.strip().startswith("#")
                        and l.strip().split()[0].rstrip("/") in {t.rstrip("/") for t in targets})]
        removed = len(lines) - len(kept)
        if removed:
            p.write_text("\n".join(kept) + "\n", encoding="utf-8")
            print(f"{p.name}: removed {removed}")
            removed_total += removed
    print(f"total lines removed: {removed_total}")
    assert removed_total == 54, removed_total


if __name__ == "__main__":
    main()
