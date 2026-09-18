#!/usr/bin/env python3
"""Insert accepted candidate rows from verdicts.csv into the awesome-shizuku README.

Idempotent: skips URLs already present, and re-sorts each affected section
alphabetically by entry name. Handles the maintainer-note overrides.
"""
import argparse
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import REPO_ROOT  # noqa: E402

AWESOME_README = Path("/home/tim/Development/awesome-shizuku/README.md")
VERDICTS = REPO_ROOT / "triage_tools" / "verdicts.csv"

# category -> exact heading line in README.md
CATEGORY_HEADING = {
    "AI agents": "### AI agents",
    "Android TV": "### Android TV",
    "Audio": "### Audio",
    "Automation": "### Automation",
    "Communication": "### Communication",
    "Customization": "### Customization",
    "Development utilities": "### Development utilities",
    "Development libraries": "### Development libraries",
    "Device owner (DPM)": "### Device owner (DPM)",
    "Display management": "### Display management",
    "Entertainment": "### Entertainment",
    "File management": "### File management",
    "Games": "### Games",
    "Input methods": "### Input methods",
    "Installer & app stores": "### Installer & app stores",
    "Miscellaneous": "### Miscellaneous",
    "Network": "### Network",
    "Patching": "### Patching",
    "Power management": "### Power management",
    "Privacy": "### Privacy",
    "Productivity": "### Productivity",
    "Quick settings": "### Quick settings",
    "Software management": "### Software management",
    "Task manager": "### Task manager",
    "Terminals": "### Terminals",
    # vendor-specific subsections
    "Google Pixel": "#### Google Pixel",
    "Samsung OneUI": "#### Samsung OneUI",
    "MIUI": "#### MIUI",
    "Other": "#### Other",
}

# maintainer-note overrides
LINK_OVERRIDES = {
    "HyperOS-MTZ-Studio": "https://github.com/GloriousApps/HyperOS-MTZ-Studio/blob/main/readme_en.md",
    "MemorySnapshot": "https://github.com/RyensX/MemorySnapshot/blob/master/docs/README_EN.md",
    "Appslim": "https://github.com/Horizen5/Appslim/blob/master/docs/README_en.md",
    "Buge-Files": "https://bugestudio.website/files/",
}
SOURCE_OVERRIDES = {
    "Buge-Files": "https://github.com/BugeStudioTeam/Buge-Files",
}
DESC_OVERRIDES = {
    "AppManagerNG": "Fork of [AppManager](https://github.com/muntashirakon/appmanager) to inspect, debloat, back up, freeze and control Android apps; works with Shizuku, ADB, Dhizuku or root.",
    "magicdesk": "Open-source Android 15+ workstation with native windows, external displays, desktops and Termux integration via Shizuku",
}

HEADING_RE = re.compile(r"^#{2,4} ")
NAME_RE = re.compile(r"^\* \[([^\]]+)\]")


def find_block(lines, heading):
    start = None
    for i, line in enumerate(lines):
        if line.strip() == heading:
            start = i
            break
    if start is None:
        raise SystemExit(f"heading not found: {heading!r}")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if HEADING_RE.match(lines[j]):
            end = j
            break
    return start, end


def sort_key(entry_line):
    m = NAME_RE.match(entry_line)
    return (m.group(1) if m else entry_line).lower()


def format_entry(name, url, desc, license_, source=None):
    line = f"* [{name}]({url}) - {desc} `{license_}`"
    if source and source != url:
        line += f" [(Source code)]({source})"
    return line


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--readme", default=str(AWESOME_README))
    ap.add_argument("--verdicts", default=str(VERDICTS))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    readme = Path(args.readme)
    lines = readme.read_text().splitlines()
    text = "\n".join(lines)

    rows = [r for r in csv.DictReader(open(args.verdicts)) if r["verdict"] == "candidate"]

    additions = {}
    skipped_present = []
    for r in rows:
        name, url = r["name"], r["url"]
        link = LINK_OVERRIDES.get(name, url)
        source = SOURCE_OVERRIDES.get(name)
        desc = DESC_OVERRIDES.get(name, r["en_desc"])
        # idempotency: URL (or override link / source) already in README
        if url in text or link in text or (source and source in text):
            skipped_present.append(name)
            continue
        heading = CATEGORY_HEADING.get(r["category"])
        if not heading:
            raise SystemExit(f"unknown category {r['category']!r} for {name}")
        additions.setdefault(heading, []).append(
            format_entry(name, link, desc, r["license"], source)
        )

    # apply per block: remove existing entries, reinsert merged sorted list
    for heading, new_lines in additions.items():
        start, end = find_block(lines, heading)
        block = lines[start + 1 : end]
        entry_idx = [i for i, ln in enumerate(block) if ln.startswith("* [")]
        existing = [block[i] for i in entry_idx]
        if entry_idx:
            first, last = entry_idx[0], entry_idx[-1]
            leading = block[:first]
            trailing = block[last + 1 :]
        else:
            leading = [ln for ln in block if ln.strip() == ""]
            leading = leading[:1] or [""]
            trailing = [""]
        merged = sorted(existing + new_lines, key=sort_key)
        new_block = leading + merged + trailing
        lines[start + 1 : end] = new_block

    out = "\n".join(lines)
    if not out.endswith("\n"):
        out += "\n"

    print(f"additions: {sum(len(v) for v in additions.values())} across {len(additions)} sections")
    for h in sorted(additions):
        print(f"  {h}: +{len(additions[h])}")
    if skipped_present:
        print(f"skipped (already present): {len(skipped_present)} -> {', '.join(sorted(skipped_present))}")

    if args.dry_run:
        print("\n--- DRY RUN, not writing ---")
        for h in sorted(additions):
            print(f"\n{h}")
            for ln in sorted(additions[h], key=sort_key):
                print("  " + ln)
        return

    readme.write_text(out)
    print(f"wrote {readme}")


if __name__ == "__main__":
    main()
