#!/usr/bin/env python3
"""Feature-(sub-)set overlap check: nearest awesome-shizuku neighbors per queue item.

Parses the awesome list entries per category, then scores every triage queue
item against all awesome entries by keyword overlap (name + description).
Writes awesome_neighbors.json: {queue_url: [{name, url, category, desc,
overlap_terms, score}]} with the top-N neighbors.

Policy is lenient: overlap never auto-ignores. Reviewers paste the neighbors
into the verdict's "alternatives considered" field and note whether the
candidate's feature (sub-)set is novel enough to list anyway.

Usage:
  python3 feature_overlap.py [--queue triage_queue.json]
      [--awesome-dir /home/tim/Development/awesome-shizuku]
      [--out awesome_neighbors.json] [--top 3]
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DEFAULT_AWESOME_DIR, DEFAULT_QUEUE_JSON, read_json, write_json

ENTRY_RE = re.compile(r"^\s*\*\s*\[([^\]]+)\]\(([^)]+)\)\s*(.*)$")
HEADING_RE = re.compile(r"^(#{3,4})\s+(.+?)\s*$")

STOPWORDS = frozenset("""
a an the and or of to in on for with via from by is are was were be been
it its this that these those as at into out over under app apps android
your you use using used free open source new all more most other some such
one two also can just will simple easy powerful best top your my our their
""".split())


def tokenize(text):
    toks = re.findall(r"[a-z0-9]{3,}", (text or "").lower())
    return {t for t in toks if t not in STOPWORDS}


def parse_awesome(awesome_dir):
    """Return list of {name, url, desc, category} from README + sub-pages."""
    awesome_dir = Path(awesome_dir)
    paths = [awesome_dir / "README.md",
             awesome_dir / "pages" / "CLOSED_SOURCE.md",
             awesome_dir / "pages" / "ARCHIVED.md",
             awesome_dir / "pages" / "UNLISTED.md"]
    entries = []
    for p in paths:
        if not p.is_file():
            continue
        category = f"({p.stem})"
        for line in p.read_text(encoding="utf-8").splitlines():
            hm = HEADING_RE.match(line)
            if hm and p.name == "README.md":
                level = len(hm.group(1))
                if level in (3, 4):
                    category = hm.group(2).strip()
                continue
            m = ENTRY_RE.match(line)
            if m:
                name, url, rest = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
                # strip license `SPDX` and [(Source code)](...) suffixes for desc
                desc = re.sub(r"\[(?:Source code|Homepage|Website)\]\([^)]+\)", "", rest)
                desc = re.sub(r"`[^`]+`", "", desc).strip(" -")
                entries.append({"name": name, "url": url, "desc": desc,
                                "category": category,
                                "tokens": sorted(tokenize(name + " " + desc))})
    return entries


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--queue", default=str(DEFAULT_QUEUE_JSON))
    ap.add_argument("--awesome-dir", default=str(DEFAULT_AWESOME_DIR))
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "awesome_neighbors.json"))
    ap.add_argument("--top", type=int, default=3)
    args = ap.parse_args()

    queue = read_json(args.queue)
    awesome = parse_awesome(args.awesome_dir)
    print(f"awesome entries: {len(awesome)}, queue: {len(queue)}")

    out = {}
    for it in queue:
        qtoks = tokenize(it.get("name", "") + " " + it.get("desc", ""))
        scored = []
        for a in awesome:
            atoks = set(a["tokens"])
            shared = sorted(qtoks & atoks)
            if not shared:
                continue
            # Jaccard-ish: shared / sqrt(|q|*|a|) to avoid favoring long descs
            denom = (len(qtoks) * len(atoks)) ** 0.5 or 1
            scored.append((len(shared) / denom, len(shared), a, shared))
        scored.sort(key=lambda t: (-t[0], -t[1], t[2]["name"].lower()))
        out[it["url"]] = [
            {"name": a["name"], "url": a["url"], "category": a["category"],
             "desc": a["desc"][:220], "overlap_terms": shared[:12],
             "score": round(s, 3)}
            for s, _, a, shared in scored[: args.top]
        ]

    write_json(args.out, out)
    with_hits = sum(1 for v in out.values() if v)
    print(f"neighbors for {with_hits}/{len(out)} queue items -> {args.out}")


if __name__ == "__main__":
    main()
