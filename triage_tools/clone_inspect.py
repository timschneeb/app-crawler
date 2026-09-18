#!/usr/bin/env python3
"""Shallow-clone inspection: Shizuku-usage proof + API-independent meta harvest.

Greps a --depth 1 clone for Shizuku API/UserService/rish/Dhizuku signals and
root-ecosystem signals (to apply the stock→root-via-Shizuku vs needs-root-first rule),
plus license sniffing and README language/download-link signals (no API use),
plus git-history vibe signals (commit count/timespan/authors) and README slop
signals for the 0-3 vibecoded score.

Clones live in --workdir (default triage_tools/clones/, repo-local and
gitignored) and are NEVER deleted: existing checkouts are reused via
`git fetch --depth 1 origin HEAD` + reset (stale checkout is reused with a
flag if the fetch fails). Use --fresh to force a re-clone, --clean to wipe
a destination before cloning. A manifest.json in the workdir records
url -> {dirname, commit_sha, commit_date, cloned_at, size_bytes} so later
runs and uncertain re-reviews can find every clone on disk.

Usage:
  python3 clone_inspect.py --enriched triage_enriched.json [--mode inconclusive|all]
      [--urls https://github.com/a/b,...] [--workdir clones]
      [--out triage_proof.json] [--merge] [--timeout 120] [--fresh] [--clean]
"""

import argparse
import datetime
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import parse_github_owner_repo, read_json, write_json

DEFAULT_CLONES_DIR = str(Path(__file__).resolve().parent / "clones")

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

SHIZUKU_PATTERNS = [
    ("dep", re.compile(r"shizuku", re.IGNORECASE)),
    ("src:rikka", re.compile(r"rikka\.shizuku|moe\.shizuku\.privileged")),
    ("src:provider", re.compile(r"ShizukuProvider|Shizuku\.\w+|ShizukuApi|ShizukuClient")),
    ("src:userservice", re.compile(r"UserService|bindUserService|Shizuku\.bindUserService")),
    ("src:rish", re.compile(r"\brish\b|rish_sh|Shizuku\.newProcess")),
    ("src:dhizuku", re.compile(r"[Dd]hizuku")),
]

ROOT_PATTERNS = [
    ("cve", re.compile(r"CVE-2026-43499|GhostLock", re.IGNORECASE)),
    ("ksu-magisk", re.compile(r"KernelSU|Magisk|APatch|\bKSU\b")),
    ("rootsdk", re.compile(r"libsu|topjohnwu|requestRoot|SUPERUSER|RootUtils|\.hasRoot\(")),
]

SCAN_EXTS = {".java", ".kt", ".kts", ".gradle", ".xml", ".toml", ".md", ".txt", ".py", ".c", ".cpp", ".h"}
SKIP_DIRS = {".git", "build", ".gradle", "node_modules", ".idea"}
MAX_FILES = 4000
MAX_FILE_BYTES = 200_000

# API-independent harvest: license sniffing + README language/download signals.
# Ordered most-specific first; first matching phrase wins.
LICENSE_SNIFFS = [
    ("GNU AFFERO GENERAL PUBLIC LICENSE", "AGPL-3.0"),
    ("GNU LESSER GENERAL PUBLIC LICENSE", "LGPL"),
    ("GNU GENERAL PUBLIC LICENSE", "GPL"),
    ("Mozilla Public License 2.0", "MPL-2.0"),
    ("Apache License, Version 2.0", "Apache-2.0"),
    ("MIT License", "MIT"),
    ("ISC License", "ISC"),
    ("BSD 3-Clause", "BSD-3-Clause"),
    ("BSD 2-Clause", "BSD-2-Clause"),
    ("Eclipse Public License", "EPL"),
    ("The Unlicense", "Unlicense"),
    ("Creative Commons", "CC"),
    ("WTFPL", "WTFPL"),
]

CJK_RX = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")
LATIN_RX = re.compile(r"[A-Za-z]")
LINK_RX = {
    "apk": re.compile(r"\bapk\b|releases/download", re.IGNORECASE),
    "play": re.compile(r"play\.google\.com", re.IGNORECASE),
    "fdroid": re.compile(r"f-droid\.org|apt\.izzysoft", re.IGNORECASE),
    "releases": re.compile(r"/releases\b", re.IGNORECASE),
}

# README slop phrases typical of AI-generated ("vibecoded") repos. Each is one
# signal; the vibe score counts distinct hits, it never auto-ignores alone.
SLOP_RX = [
    re.compile(r"glassmorphic", re.IGNORECASE),
    re.compile(r"blazing[ -]?fast|blazingly", re.IGNORECASE),
    re.compile(r"cutting[ -]?edge", re.IGNORECASE),
    re.compile(r"seamless(ly)?\b", re.IGNORECASE),
    re.compile(r"premium\b.{0,20}(ui|experience|design)", re.IGNORECASE),
    re.compile(r"comprehensive\b", re.IGNORECASE),
    re.compile(r"robust\b", re.IGNORECASE),
    re.compile(r"effortless(ly)?\b", re.IGNORECASE),
    re.compile(r"supercharge", re.IGNORECASE),
    re.compile(r"unlock the (full|power|potential)", re.IGNORECASE),
    re.compile(r"take (complete|full) control", re.IGNORECASE),
    re.compile(r"state[ -]of[ -]the[ -]art", re.IGNORECASE),
    re.compile(r"liquid glass", re.IGNORECASE),
    re.compile(r"all[ -]in[ -]one", re.IGNORECASE),
]
EMOJI_RX = re.compile(
    "[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F]"
)


def git_run(dest, *args, timeout=30):
    return subprocess.run(
        ["git", "-C", str(dest), *args],
        timeout=timeout,
        check=True,
        capture_output=True,
        text=True,
    )


def git_history_stats(dest, timeout=30):
    """Commit count / timespan / author count from a (shallow) clone.

    --depth 1 clones report commit_count=1 with a shallow flag so the vibe
    scorer treats them as 'unknown history', not as single-commit dumps.
    """
    stats = {"commit_count": None, "author_count": None,
             "first_date": None, "last_date": None,
             "timespan_hours": None, "shallow": False}
    try:
        stats["shallow"] = (Path(dest) / ".git" / "shallow").is_file()
    except OSError:
        pass
    # Full history is available when the clone was made without --depth or
    # was unshallowed; otherwise counts reflect the shallow boundary.
    try:
        out = git_run(dest, "rev-list", "--count", "HEAD", timeout=timeout)
        stats["commit_count"] = int(out.stdout.strip())
    except (subprocess.SubprocessError, ValueError):
        return stats
    try:
        out = git_run(dest, "shortlog", "-sne", "HEAD", timeout=timeout)
        stats["author_count"] = len([l for l in out.stdout.splitlines() if l.strip()])
    except subprocess.SubprocessError:
        pass
    try:
        out = git_run(dest, "log", "--format=%cI", "--reverse", timeout=timeout)
        dates = [l.strip() for l in out.stdout.splitlines() if l.strip()]
        if dates:
            stats["first_date"] = dates[0]
            stats["last_date"] = dates[-1]
            try:
                first = datetime.datetime.fromisoformat(dates[0])
                last = datetime.datetime.fromisoformat(dates[-1])
                stats["timespan_hours"] = round((last - first).total_seconds() / 3600, 1)
            except ValueError:
                pass
    except subprocess.SubprocessError:
        pass
    return stats


def vibe_score(git_stats, readme_text):
    """Score 0-3 for 'how vibecoded does this repo look'. Flag, not verdict:
    the reviewer decides; the score only forces the question to be asked.
    Shallow clones (commit_count==1 + shallow) score at most 1 from slop.
    """
    score = 0
    reasons = []
    cc = git_stats.get("commit_count")
    shallow = git_stats.get("shallow")
    span = git_stats.get("timespan_hours")
    authors = git_stats.get("author_count")

    full_history = not shallow
    if cc is not None and full_history:
        if cc <= 2:
            score += 1
            reasons.append(f"only {cc} commit(s) in history")
        if span is not None and span < 24 and (cc or 0) <= 5:
            score += 1
            reasons.append(f"entire history spans {span}h (<24h burst)")
        if authors == 1 and (cc or 0) <= 3:
            # weak corroborating signal, no extra point alone
            reasons.append("single author, <=3 commits")
    elif cc == 1 and shallow:
        reasons.append("shallow clone: full history unknown (needs --full-history for commit signals)")

    text = readme_text or ""
    slop_hits = sorted({rx.pattern for rx in SLOP_RX if rx.search(text)})
    emojis = len(EMOJI_RX.findall(text))
    emoji_density = (emojis / max(len(text), 1)) * 1000  # per 1k chars
    if len(slop_hits) >= 3:
        score += 1
        reasons.append(f"README slop phrases ({len(slop_hits)}): {', '.join(p[:28] for p in slop_hits[:4])}")
    elif slop_hits:
        reasons.append(f"README slop phrases ({len(slop_hits)}): {', '.join(p[:28] for p in slop_hits[:3])}")
    if emojis >= 10 and emoji_density > 1.0:
        # corroborating only; folded into slop point if already scored
        reasons.append(f"emoji-heavy README ({emojis} emojis)")
        if len(slop_hits) >= 2 and score < 3:
            score += 1

    return {"vibe_score": min(score, 3), "vibe_reasons": reasons,
            "slop_hits": slop_hits, "emoji_count": emojis}


def sniff_license(text):
    for phrase, spdx in LICENSE_SNIFFS:
        if phrase in text:
            if spdx == "GPL":
                return "GPL-3.0" if "Version 3" in text else ("GPL-2.0" if "Version 2" in text else "GPL")
            if spdx == "LGPL":
                return "LGPL-3.0" if "Version 3" in text else ("LGPL-2.1" if "Version 2.1" in text else "LGPL")
            return spdx
    return None


def harvest_meta(root):
    """License + README language/download signals from a clone (no API needed).

    Returns (meta, readme_text): readme_text is capped at 200k chars and reused
    for vibe scoring so we never re-fetch READMEs over the network.
    """
    meta = {"license_file": None, "license_spdx_guess": None, "readme_file": None,
            "readme_bytes": 0, "latin_ratio": 0.0, "cjk_ratio": 0.0,
            "links": {k: False for k in LINK_RX}}
    readme_text = ""
    try:
        top = [p for p in root.iterdir() if p.is_file()]
    except OSError:
        return meta, readme_text
    lic_text = ""
    for p in top:
        n = p.name.upper()
        if n.startswith(("LICENSE", "LICENCE", "COPYING")) or n in ("NOTICE", "NOTICE.md", "NOTICE.txt"):
            meta["license_file"] = p.name
            try:
                if p.stat().st_size < 100_000:
                    lic_text += "\n" + p.read_text(encoding="utf-8", errors="replace")[:16_000]
            except OSError:
                pass
    if lic_text:
        meta["license_spdx_guess"] = sniff_license(lic_text)
    candidates = [p for p in top if p.name.upper().startswith("README")]
    if candidates:
        pref = sorted(candidates, key=lambda p: (p.suffix.lower() != ".md", len(p.name)))[0]
        meta["readme_file"] = pref.name
        try:
            text = pref.read_text(encoding="utf-8", errors="replace")[:200_000]
        except OSError:
            text = ""
        n = len(text)
        meta["readme_bytes"] = n
        if n:
            meta["latin_ratio"] = round(len(LATIN_RX.findall(text)) / n, 4)
            meta["cjk_ratio"] = round(len(CJK_RX.findall(text)) / n, 4)
        for k, rx in LINK_RX.items():
            meta["links"][k] = bool(rx.search(text))
    return meta, readme_text


def is_inconclusive(rec):
    e = rec.get("enriched", {}) or {}
    if rec.get("skipped"):
        return False
    if e.get("fetch_errors"):
        return True
    if not e.get("readme_present"):
        return True
    if e.get("has_chinese") and not e.get("has_english"):
        return True
    if not e.get("has_apk_asset"):
        return True
    if not e.get("license_spdx") or e.get("license_spdx") == "NOASSERTION":
        return True
    return False


def inspect_tree(root, max_snippets=20):
    hits = {label: 0 for label, _ in SHIZUKU_PATTERNS}
    root_hits = {label: 0 for label, _ in ROOT_PATTERNS}
    snippets = []
    files_scanned = 0
    dep_only_files = []
    src_files = []
    for path in sorted(root.rglob("*")):
        if files_scanned >= MAX_FILES:
            break
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix not in SCAN_EXTS and path.name not in ("AndroidManifest.xml",):
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        files_scanned += 1
        rel = str(path.relative_to(root))
        is_build_file = path.name in ("build.gradle", "build.gradle.kts", "settings.gradle",
                                      "settings.gradle.kts") or path.suffix == ".toml"
        for label, rx in SHIZUKU_PATTERNS:
            for m in rx.finditer(text):
                hits[label] += 1
                if label == "dep" and is_build_file:
                    dep_only_files.append(rel)
                else:
                    src_files.append(rel)
                if len(snippets) < max_snippets:
                    ls = text.rfind("\n", 0, m.start()) + 1
                    le = text.find("\n", m.end())
                    if le == -1:
                        le = len(text)
                    snippets.append(f"{rel}: {text[ls:le].strip()[:200]}")
                break
        for label, rx in ROOT_PATTERNS:
            if rx.search(text):
                root_hits[label] += 1
    has_dep = hits["dep"] > 0
    has_src = any(hits[k] > 0 for k in ("src:rikka", "src:provider", "src:userservice", "src:rish", "src:dhizuku"))
    return {
        "files_scanned": files_scanned,
        "has_shizuku_dep": has_dep,
        "has_shizuku_source": has_src,
        "import_only_suspect": bool(has_dep and not has_src),
        "shizuku_hits": hits,
        "root_signals": {k: v for k, v in root_hits.items() if v},
        "snippets": snippets,
        "dep_files": sorted(set(dep_only_files))[:5],
        "src_files": sorted(set(src_files))[:10],
    }


def clone_dir_name(url):
    pr = parse_github_owner_repo(url)
    if pr:
        owner, repo = pr
        return f"{owner}__{repo}"
    # Fallback for non-GitHub hosts (e.g. gitlab.com): host + path segments.
    m = re.match(r"https?://([^/]+)/(.+?)(?:\.git)?/?$", (url or "").strip())
    if m:
        host, path = m.group(1), m.group(2)
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"{host}_{path}")
        return safe[:120]
    return None


def dir_size_bytes(path):
    total = 0
    for p in Path(path).rglob("*"):
        try:
            if p.is_file() and ".git" not in p.parts:
                total += p.stat().st_size
        except OSError:
            pass
    return total


def refresh_checkout(dest, url, timeout):
    """Fetch latest HEAD into an existing checkout. Returns (ok, stale).

    ok=True means the checkout is usable (fresh or stale-but-present);
    stale=True means the fetch failed and we reuse whatever is on disk.
    """
    try:
        subprocess.run(
            ["git", "-C", str(dest), "fetch", "--depth", "1",
             "origin", "HEAD", "--quiet"],
            timeout=timeout,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(dest), "reset", "--hard", "FETCH_HEAD", "--quiet"],
            timeout=timeout,
            check=True,
            capture_output=True,
        )
        return True, False
    except (subprocess.SubprocessError, OSError):
        # Offline / renamed default branch / deleted repo: reuse on-disk state.
        if (Path(dest) / ".git").is_dir():
            return True, True
        return False, False


def head_info(dest, timeout=30):
    info = {"commit_sha": None, "commit_date": None}
    try:
        out = git_run(dest, "rev-parse", "HEAD", timeout=timeout)
        info["commit_sha"] = out.stdout.strip()
    except subprocess.SubprocessError:
        pass
    try:
        out = git_run(dest, "log", "-1", "--format=%cI", timeout=timeout)
        info["commit_date"] = out.stdout.strip()
    except subprocess.SubprocessError:
        pass
    return info


def clone_and_inspect(url, workdir, timeout, max_snippets, fresh=False,
                      full_history=False):
    """Clone (or reuse) a repo and inspect it. Clones are never deleted."""
    dirname = clone_dir_name(url)
    if not dirname:
        return {"cloned": False, "error": "unparseable url"}
    dest = Path(workdir) / dirname
    reused = False
    stale = False
    if dest.is_dir() and (dest / ".git").is_dir() and not fresh:
        ok, stale = refresh_checkout(dest, url, timeout)
        if not ok:
            return {"cloned": False, "error": "existing checkout unusable and refresh failed",
                    "clone_dir": str(dest)}
        reused = True
    else:
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        clone_cmd = ["git", "clone", "--quiet", url, str(dest)]
        if not full_history:
            clone_cmd[2:2] = ["--depth", "1"]
        try:
            subprocess.run(clone_cmd, timeout=timeout, check=True, capture_output=True)
        except subprocess.TimeoutExpired:
            return {"cloned": False, "error": f"clone timeout after {timeout}s"}
        except subprocess.CalledProcessError as e:
            err = (e.stderr or b"").decode("utf-8", "replace")[:300]
            return {"cloned": False, "error": f"clone failed: {err}"}
    meta, readme_text = harvest_meta(dest)
    gstats = git_history_stats(dest)
    vibe = vibe_score(gstats, readme_text)
    result = {"cloned": True, "clone_dir": str(dest), "reused": reused,
              "stale": stale,
              **inspect_tree(dest, max_snippets),
              "meta": meta, "git": {**gstats, **head_info(dest)}, **vibe}
    return result


def load_manifest(workdir):
    mp = Path(workdir) / "manifest.json"
    if mp.is_file():
        try:
            return json.loads(mp.read_text(encoding="utf-8")) or {}
        except (OSError, ValueError):
            return {}
    return {}


def save_manifest(workdir, manifest):
    (Path(workdir) / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--enriched", default=str(Path(__file__).resolve().parent / "triage_enriched.json"))
    ap.add_argument("--mode", choices=["inconclusive", "all"], default="inconclusive")
    ap.add_argument("--urls", default="", help="Comma-separated URLs (overrides --mode filter)")
    ap.add_argument("--workdir", default=DEFAULT_CLONES_DIR)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "triage_proof.json"))
    ap.add_argument("--merge", action="store_true", help="Merge proof back into --enriched file")
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--keep", action="store_true",
                    help="Deprecated no-op: clones are now always kept. Kept for backward compat.")
    ap.add_argument("--fresh", action="store_true",
                    help="Force re-clone even when a checkout already exists")
    ap.add_argument("--clean", action="store_true",
                    help="Wipe each destination before cloning (same as --fresh but explicit)")
    ap.add_argument("--full-history", action="store_true",
                    help="Clone full history (needed for commit-count vibe signals); "
                         "default is --depth 1, which reports history as unknown")
    ap.add_argument("--max-snippets", type=int, default=20)
    ap.add_argument("--resume", action="store_true",
                    help="Skip URLs already present in --out (safe re-run after kill)")
    ap.add_argument("--checkpoint-every", type=int, default=25,
                    help="Rewrite --out every N repos so kills lose little work")
    args = ap.parse_args()

    records = read_json(args.enriched)
    if args.urls.strip():
        wanted = {u.strip() for u in args.urls.split(",") if u.strip()}
        targets = [r for r in records if r["url"] in wanted]
    elif args.mode == "all":
        targets = [r for r in records if not r.get("skipped")]
    else:
        targets = [r for r in records if is_inconclusive(r)]

    print(f"inspecting {len(targets)} repos (mode={args.mode})")
    Path(args.workdir).mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out)
    manifest = load_manifest(args.workdir)
    proof = {}
    if args.resume and out_path.exists():
        try:
            proof = read_json(str(out_path)) or {}
            print(f"resume: {len(proof)} already done, skipping those")
        except Exception as e:
            print(f"resume: could not read {out_path} ({e}), starting fresh")
            proof = {}
    fresh = args.fresh or args.clean
    it_iter = tqdm(targets, desc="clone") if tqdm else targets
    done = 0
    for rec in it_iter:
        prev = proof.get(rec["url"])
        # Reuse proof only when it matches the current pipeline: meta + git +
        # vibe keys present and no --fresh. Old pre-persistence records (which
        # have no clone_dir on disk anymore) are redone.
        if prev and not fresh and all(k in prev for k in ("meta", "git", "vibe_score")):
            dirname = clone_dir_name(rec["url"])
            if dirname and (Path(args.workdir) / dirname).is_dir():
                continue
        proof[rec["url"]] = {"name": rec["name"], **clone_and_inspect(
            rec["url"], args.workdir, args.timeout, args.max_snippets,
            fresh=fresh, full_history=args.full_history)}
        done += 1
        v = proof[rec["url"]]
        if v.get("cloned"):
            dirname = clone_dir_name(rec["url"])
            manifest[rec["url"]] = {
                "dirname": dirname,
                "commit_sha": (v.get("git") or {}).get("commit_sha"),
                "commit_date": (v.get("git") or {}).get("commit_date"),
                "cloned_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "size_bytes": dir_size_bytes(Path(args.workdir) / dirname),
                "reused": v.get("reused"), "stale": v.get("stale"),
            }
        if args.checkpoint_every and done % args.checkpoint_every == 0:
            write_json(str(out_path), proof)
            save_manifest(args.workdir, manifest)
            print(f"checkpoint: {len(proof)}/{len(targets)} -> {args.out}", flush=True)

    write_json(args.out, proof)
    save_manifest(args.workdir, manifest)
    n_ok = sum(1 for v in proof.values() if v.get("cloned"))
    n_src = sum(1 for v in proof.values() if v.get("has_shizuku_source"))
    n_reused = sum(1 for v in proof.values() if v.get("reused"))
    print(f"cloned {n_ok}/{len(proof)} ({n_src} with Shizuku source hits, {n_reused} reused) -> {args.out}")
    print(f"manifest: {len(manifest)} entries -> {Path(args.workdir) / 'manifest.json'}")

    if args.merge:
        by_url = proof
        for rec in records:
            if rec["url"] in by_url:
                rec.setdefault("enriched", {})["clone_proof"] = by_url[rec["url"]]
        write_json(args.enriched, records)
        print(f"merged proof back into {args.enriched}")


if __name__ == "__main__":
    main()
