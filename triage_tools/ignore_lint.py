#!/usr/bin/env python3
"""Lint ignore/*.lst files for the triage workflow.

Checks:
  A. cross-file duplicates (same normalized URL or bare name in >1 file)
  B. within-file duplicates
  C. inline `URL # reason` comments — reports them AND demonstrates the
     util.py gap: util._load_ignore_list() only skips lines STARTING with '#'
     and does not strip inline comments, so `url # reason` will NOT match
     `url` in main.py's remove_ignored_entries() and the entry resurfaces.
  D. entries above the first '# subsection' header
  E. malformed URL entries (not starting with http, not a known bare name)

Read-only by default. --strict exits non-zero on any warning.

Usage:
  python3 ignore_lint.py [--ignore-dir ../ignore] [--out ignore_lint.json] [--strict]
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DEFAULT_IGNORE_DIR, load_ignore_with_sections


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ignore-dir", default=str(DEFAULT_IGNORE_DIR))
    ap.add_argument("--out", default=None)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    entries, by_file = load_ignore_with_sections(args.ignore_dir)

    seen_url = defaultdict(list)
    seen_bare = defaultdict(list)
    no_section, malformed, inline = [], [], []
    for e in entries:
        loc = f"{e['file']}:{e['lineno']}"
        if e["subsection"] == "(no subsection)":
            no_section.append(f"{loc}: {e['raw']}")
        if e["has_inline_reason"]:
            inline.append(f"{loc}: {e['raw']}")
        if e["is_bare_name"]:
            seen_bare[e["name_norm"]].append(loc)
            if " " in e["url"] or "/" in e["url"]:
                malformed.append(f"{loc}: suspicious bare entry {e['raw']!r}")
        else:
            seen_url[e["url_norm"]].append(loc)
            if not e["url"].startswith("http"):
                malformed.append(f"{loc}: {e['raw']!r}")

    cross_file, within_file = [], []
    for key, locs in list(seen_url.items()) + list(seen_bare.items()):
        files = {loc.split(":")[0] for loc in locs}
        if len(files) > 1:
            cross_file.append({"entry": key, "locs": locs})
        if len(locs) > 1 and len(files) == 1:
            within_file.append({"entry": key, "locs": locs})

    print(f"scanned {len(entries)} entries in {len(by_file)} files")
    print(f"cross-file duplicates: {len(cross_file)}")
    for d in cross_file[:20]:
        print(f"  DUP {d['entry']} @ {', '.join(d['locs'])}")
    print(f"within-file duplicates: {len(within_file)}")
    for d in within_file[:20]:
        print(f"  DUP {d['entry']} @ {', '.join(d['locs'])}")
    print(f"entries with no subsection: {len(no_section)}")
    for x in no_section[:10]:
        print(f"  NOSECTION {x}")
    print(f"malformed entries: {len(malformed)}")
    for x in malformed[:10]:
        print(f"  MALFORMED {x}")
    print(f"inline 'URL # reason' comments: {len(inline)}")
    for x in inline[:10]:
        print(f"  INLINE {x}")

    print()
    # Functional check: does the real loader strip inline comments?
    # (util.py was patched to split "URL # reason" on " #".)
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        import util as _crawler_util
        import importlib as _il
        _il.reload(_crawler_util)
        _loaded = _crawler_util._load_ignore_list()
        _stripped = not any("#" in e for e in _loaded)
    except Exception as ex:  # noqa: BLE001 - lint must not crash
        _loaded, _stripped, ex = [], False, ex
        print(f"  (could not import crawler util.py: {ex})")
    if _stripped:
        print("UTIL.PY INLINE-COMMENT HANDLING: OK "
              f"({len(_loaded)} entries loaded, none contain '#').")
    else:
        print("UTIL.PY GAP (action required before writing inline comments):")
        print("  util._load_ignore_list() keeps the whole line ('url # reason') as one")
        print("  entry, so `url in ignore_list` in main.py is False and the ignored app")
        print("  reappears in the next crawl. Fix options:")
        print("    1) patch util.py to strip inline comments when loading (one-line change")
        print("       using common.split_inline_comment), or")
        print("    2) write the reason on the preceding line as '# reason' instead.")
    if inline and not _stripped:
        print(f"  There are currently {len(inline)} inline-commented line(s); with the")
        print("  current util.py NONE of them take effect.")

    result = {
        "entries": len(entries),
        "cross_file_duplicates": cross_file,
        "within_file_duplicates": within_file,
        "no_subsection": no_section,
        "malformed": malformed,
        "inline_comments": inline,
    }
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"\nwrote {args.out}")

    if args.strict and (cross_file or within_file or no_section or malformed or inline):
        sys.exit(1)


if __name__ == "__main__":
    main()
