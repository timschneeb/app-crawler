"""Shared helpers for the SUMMARY.md triage pipeline.

All paths default to locations relative to the app-crawler repo root
(parent directory of triage_tools/), but can be overridden via arguments.
Only stdlib dependencies.
"""

import csv
import json
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SUMMARY = REPO_ROOT / "SUMMARY.md"
DEFAULT_IGNORE_DIR = REPO_ROOT / "ignore"
DEFAULT_AWESOME_DIR = Path("/home/tim/Development/awesome-shizuku")
DEFAULT_QUEUE_JSON = Path(__file__).resolve().parent / "triage_queue.json"
DEFAULT_QUEUE_CSV = Path(__file__).resolve().parent / "triage_queue.csv"

# Matches SUMMARY.md list items:
#   * [Name](https://github.com/owner/repo) `fdroid` - optional description
ENTRY_RE = re.compile(
    r"^\s*\*\s*\[([^\]]+)\]\(([^)]+)\)\s*(`fdroid`)?\s*(?:-\s*(.*))?\s*$"
)

GITHUB_RE = re.compile(
    r"github\.com/([^/\s#?]+)/([^/\s#?]+?)(\.git)?(?:[/#?]|$)", re.IGNORECASE
)

# Ordered awesome-shizuku categories (README.md TOC) for grouping candidates.
AWESOME_CATEGORIES = [
    "AI agents",
    "Android TV",
    "Audio",
    "Automation",
    "Communication",
    "Customization",
    "Development utilities",
    "Development libraries",
    "Device Owner (DPM)",
    "Display management",
    "Entertainment",
    "File management",
    "Games",
    "Input methods",
    "Installer & app stores",
    "Miscellaneous",
    "Network",
    "Patching",
    "Power management",
    "Privacy",
    "Productivity",
    "Quick settings",
    "Software management",
    "Task manager",
    "Terminals",
    "Google Pixel",
    "Samsung OneUI",
    "MIUI",
    "Other",
    "Closed-source",
]


def parse_summary_recent(summary_path=DEFAULT_SUMMARY):
    """Parse the 'Apps with releases / Updated in the last 3 months' slice.

    Returns a list of dicts: {name, url, fdroid, desc, group} where group is
    one of 'main', 'non-original', 'no-stars'. Order is preserved.
    """
    return parse_summary_releases(summary_path, recent_only=True)


def parse_summary_releases(summary_path=DEFAULT_SUMMARY, recent_only=False):
    """Parse '### Apps with releases' (both recency subsections unless
    recent_only=True).

    Returns a list of dicts: {name, url, fdroid, desc, group, recency} where
    group is one of 'main', 'non-original', 'no-stars' and recency is one of
    'recent', 'older'. Order is preserved (recent section first).
    """
    return _parse_summary_section(summary_path, "### Apps with releases", recent_only)


def parse_summary_no_releases(summary_path=DEFAULT_SUMMARY, recent_only=False):
    """Parse '### Apps with no releases' (both recency subsections unless
    recent_only=True).

    Returns the same shape as parse_summary_releases.
    """
    return _parse_summary_section(summary_path, "### Apps with no releases", recent_only)


def _parse_summary_section(summary_path, section_header, recent_only=False):
    text = Path(summary_path).read_text(encoding="utf-8")
    lines = text.splitlines()

    start = None
    for i, line in enumerate(lines):
        if line.strip() == section_header:
            start = i
            break
    if start is None:
        raise ValueError(f"Could not find '{section_header}' in {summary_path}")

    # Section ends at the next level-2/level-3 heading after the header.
    section_end = len(lines)
    for i in range(start + 1, len(lines)):
        s = lines[i].strip()
        if s.startswith("### ") or s.startswith("## "):
            section_end = i
            break

    recent = None
    for i in range(start + 1, section_end):
        if lines[i].strip() == "#### Updated in the last 3 months":
            recent = i
            break
    if recent is None:
        raise ValueError(
            f"Could not find '#### Updated in the last 3 months' in '{section_header}'"
        )

    older = None
    for i in range(recent + 1, section_end):
        if lines[i].strip() == "#### Updated more than 3 months ago":
            older = i
            break

    if recent_only or older is None:
        end = older if older is not None else section_end
        items = []
        group = "main"
        for line in lines[recent + 1 : end]:
            if "<summary>Non-original content</summary>" in line:
                group = "non-original"
                continue
            if "<summary>No GitHub stars</summary>" in line:
                group = "no-stars"
                continue
            if "</details>" in line:
                group = "main"
                continue
            m = ENTRY_RE.match(line)
            if m:
                name, url = m.group(1).strip(), m.group(2).strip()
                items.append(
                    {
                        "name": name,
                        "url": url,
                        "fdroid": bool(m.group(3)),
                        "desc": (m.group(4) or "").strip(),
                        "group": group,
                        "recency": "recent",
                    }
                )
        return items

    items = []
    group = "main"
    recency = "recent"
    for line in lines[recent + 1 : section_end]:
        s = line.strip()
        if s == "#### Updated more than 3 months ago":
            recency = "older"
            group = "main"
            continue
        if "<summary>Non-original content</summary>" in line:
            group = "non-original"
            continue
        if "<summary>No GitHub stars</summary>" in line:
            group = "no-stars"
            continue
        if "</details>" in line:
            group = "main"
            continue
        m = ENTRY_RE.match(line)
        if m:
            name, url = m.group(1).strip(), m.group(2).strip()
            items.append(
                {
                    "name": name,
                    "url": url,
                    "fdroid": bool(m.group(3)),
                    "desc": (m.group(4) or "").strip(),
                    "group": group,
                    "recency": recency,
                }
            )
    return items


def normalize_url(url):
    """Lowercase, strip scheme-agnostic trailing slash and .git suffix."""
    u = (url or "").strip().lower()
    u = u.rstrip("/")
    if u.endswith(".git"):
        u = u[: -len(".git")]
    return u


def normalize_name(name):
    return (name or "").strip().lower()


def url_key(url):
    """Match key mirroring util.py logic: url without https:// scheme, lowercased."""
    return normalize_url(url).replace("https://", "").replace("http://", "")


def parse_github_owner_repo(url):
    m = GITHUB_RE.search(url or "")
    if not m:
        return None
    owner = m.group(1)
    repo = m.group(2)
    if repo.lower().endswith(".git"):
        repo = repo[: -len(".git")]
    return (owner, repo)


def is_github_url(url):
    return parse_github_owner_repo(url) is not None


def split_inline_comment(raw_line):
    """Split 'URL # reason' into (url_part, reason). URLs never contain ' # '."""
    line = raw_line.strip()
    if " #" in line or "\t#" in line:
        parts = re.split(r"\s+#\s*", line, maxsplit=1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
    if "#" in line and "://" not in line.split("#", 1)[0]:
        # bare-name entry with comment, e.g. 'Shizuku # reason'
        head, _, tail = line.partition("#")
        return head.strip(), tail.strip()
    return line, ""


def load_ignore_with_sections(ignore_dir=DEFAULT_IGNORE_DIR):
    """Load all ignore/*.lst files preserving file + subsection per entry.

    Returns (entries, by_file) where each entry is a dict:
    {raw, url, url_norm, name_norm, is_bare_name, file, subsection,
     lineno, reason, has_inline_reason}
    """
    ignore_dir = Path(ignore_dir)
    entries = []
    by_file = {}
    for path in sorted(ignore_dir.glob("*.lst")):
        subsection = "(no subsection)"
        file_entries = []
        with open(path, encoding="utf-8") as f:
            for lineno, raw in enumerate(f, start=1):
                line = raw.strip()
                if not line or line.startswith("#"):
                    if line.startswith("#"):
                        subsection = line.lstrip("#").strip() or "(no subsection)"
                    continue
                url_part, reason = split_inline_comment(line)
                is_bare = "://" not in url_part
                e = {
                    "raw": line,
                    "url": url_part,
                    "url_norm": None if is_bare else normalize_url(url_part),
                    "url_key": None if is_bare else url_key(url_part),
                    "name_norm": normalize_name(url_part) if is_bare else None,
                    "is_bare_name": is_bare,
                    "file": path.name,
                    "subsection": subsection,
                    "lineno": lineno,
                    "reason": reason,
                    "has_inline_reason": bool(reason),
                }
                entries.append(e)
                file_entries.append(e)
        by_file[path.name] = file_entries
    return entries, by_file


def load_awesome_text(awesome_dir=DEFAULT_AWESOME_DIR):
    """Load awesome README + closed-source/archived/unlisted pages as one blob."""
    awesome_dir = Path(awesome_dir)
    candidates = [
        awesome_dir / "README.md",
        awesome_dir / "pages" / "CLOSED_SOURCE.md",
        awesome_dir / "pages" / "ARCHIVED.md",
        awesome_dir / "pages" / "UNLISTED.md",
    ]
    blob = ""
    found = []
    for p in candidates:
        if p.is_file():
            blob += p.read_text(encoding="utf-8").lower() + "\n"
            found.append(str(p))
    return {"text": blob, "files": found}


def awesome_match(name, urls, blob):
    """Mirror util.is_known_app: url-without-scheme in text, or '[name]' in text."""
    for u in urls or []:
        key = u.replace("https://", "").replace("http://", "").lower()
        if key and key in blob:
            return f"url:{u}"
    if name and ("[" + name.lower() + "]") in blob:
        return f"name:{name}"
    return None


def ensure_parent(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def write_json(path, obj):
    ensure_parent(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_queue_csv(path, items):
    ensure_parent(path)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["name", "url", "fdroid", "desc", "group", "recency"])
        w.writeheader()
        for it in items:
            w.writerow({k: it.get(k, "") for k in ("name", "url", "fdroid", "desc", "group", "recency")})
