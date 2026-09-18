"""Join queue + proof + clones into review bundles for the verdict phase.

Reads:
  triage_queue.json      list of {name, url, fdroid, desc, group, recency}
  dedup_report.json      {needs_triage: [...], already_in_awesome: [...], already_ignored: [...]}
                         (list items may be {name,url,...} dicts or plain URL strings)
  triage_proof.json      {url: {cloned, clone_dir, files_scanned, has_shizuku_dep,
                         has_shizuku_source, import_only_suspect, shizuku_hits{...},
                         root_signals, snippets[], git{commit_count,...},
                         vibe_score, vibe_reasons,
                         meta{license_spdx_guess, readme_file, latin_ratio, cjk_ratio,
                         links{apk,play,fdroid,releases}}}}
  clones/<owner>__<repo>/  persistent checkouts: README text is read from the
                         clone first (no separate network fetch).
  corpus/corpus_index.json  legacy fallback for uncloneable URLs only
  awesome_neighbors.json    lenient feature-overlap neighbors per queue URL

Writes:
  review_items.jsonl     one JSON object per needs_triage URL with all evidence inline
                         (readme_text truncated to --readme-chars, default 2500)
  review_slices/slice_N.json  equally-sized slices (default 8) for parallel reviewers

Auto-verdicts (written to auto_verdicts.csv):
  Only the highest-confidence mechanical case: repo inaccessible (clone failed AND
  no clone README) -> verdict=skip, reason recorded. Everything else -> review.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from common import parse_github_owner_repo, read_json

HERE = Path(__file__).resolve().parent
NSLICES_DEFAULT = 8
README_CHARS_DEFAULT = 2500


def need_entry(item):
    if isinstance(item, dict):
        return item.get("url", ""), item.get("name", "")
    return item, ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", default=str(HERE / "triage_queue.json"))
    ap.add_argument("--dedup", default=str(HERE / "dedup_report.json"))
    ap.add_argument("--proof", default=str(HERE / "triage_proof.json"))
    ap.add_argument("--clones-dir", default=str(HERE / "clones"),
                    help="Persistent checkouts; README text is read from the clone first")
    ap.add_argument("--neighbors", default=str(HERE / "awesome_neighbors.json"),
                    help="Lenient feature-overlap neighbors per queue URL")
    ap.add_argument("--corpus-index", default=str(HERE / "corpus" / "corpus_index.json"),
                    help="Legacy fallback for uncloneable URLs only")
    ap.add_argument("--corpus-dir", default=str(HERE / "corpus"))
    ap.add_argument("--out", default=str(HERE / "review_items.jsonl"))
    ap.add_argument("--slices-dir", default=str(HERE / "review_slices"))
    ap.add_argument("--nslices", type=int, default=NSLICES_DEFAULT)
    ap.add_argument("--readme-chars", type=int, default=README_CHARS_DEFAULT)
    ap.add_argument("--auto-out", default=str(HERE / "auto_verdicts.csv"))
    args = ap.parse_args()

    queue = read_json(args.queue)
    qmap = {}
    for item in queue:
        url, name = need_entry(item)
        qmap[url] = {"name": name or (item.get("name", "") if isinstance(item, dict) else ""),
                     "desc": item.get("desc", "") if isinstance(item, dict) else "",
                     "group": item.get("group", "") if isinstance(item, dict) else "",
                     "recency": item.get("recency", "") if isinstance(item, dict) else "",
                     "fdroid": item.get("fdroid", False) if isinstance(item, dict) else False}
    dedup = read_json(args.dedup)
    if isinstance(dedup, dict):
        needs = [need_entry(i)[0] for i in dedup.get("needs_triage", [])]
    else:
        # flat report: [{..., status: needs_triage|already_in_awesome|already_ignored, ...}]
        needs = [need_entry(i)[0] for i in dedup if isinstance(i, dict) and i.get("status") == "needs_triage"]
    proof = read_json(args.proof)
    cidx = read_json(args.corpus_index) if Path(args.corpus_index).exists() else {}
    corpus_dir = Path(args.corpus_dir)
    clones_dir = Path(args.clones_dir)
    neighbors = {}
    if Path(args.neighbors).exists():
        try:
            neighbors = read_json(args.neighbors) or {}
        except Exception:
            neighbors = {}

    def clone_readme_text(url):
        """README text from the persistent clone (no network)."""
        try:
            owner, repo = parse_github_owner_repo(url)
        except ValueError:
            return "", ""
        for stem in (f"{owner}__{repo}",):
            d = clones_dir / stem
            if not d.is_dir():
                continue
            for cand in sorted(d.glob("README*")):
                if cand.is_file():
                    try:
                        if cand.stat().st_size > 500_000:
                            continue
                        return cand.read_text(encoding="utf-8", errors="replace"), cand.name
                    except OSError:
                        continue
        return "", ""

    bundles = []
    auto = []
    for url in needs:
        q = qmap.get(url, {"name": "", "desc": "", "group": "", "recency": "", "fdroid": False})
        pr = proof.get(url, {})
        ci = cidx.get(url, {})
        readme_text = ""
        readme_source = ""
        # Clone first: persistent checkout, no network.
        clone_text, clone_file = clone_readme_text(url)
        if clone_text.strip():
            readme_text = clone_text[: args.readme_chars]
            readme_source = f"clone:{clone_file}"
        else:
            rinfo = ci.get("readme") or {}
            rp = None
            if rinfo.get("file"):
                # corpus files are stored as {owner}__{repo}__README.md; the index
                # only records the remote filename, so reconstruct the local path.
                try:
                    owner, repo = parse_github_owner_repo(url)
                    cand = corpus_dir / f"{owner}__{repo}__README.md"
                    rp = cand if cand.exists() else corpus_dir / rinfo["file"]
                except ValueError:
                    rp = corpus_dir / rinfo["file"]
                if rp.exists():
                    try:
                        readme_text = rp.read_text(encoding="utf-8", errors="replace")[: args.readme_chars]
                        readme_source = "corpus"
                    except OSError:
                        readme_text = ""
        meta = pr.get("meta", {}) or {}
        git = pr.get("git", {}) or {}
        bundles.append({
            "name": q["name"] or pr.get("name", ""),
            "url": url,
            "queue_desc": q["desc"],
            "queue_group": q["group"],
            "recency": q.get("recency", ""),
            "fdroid": q["fdroid"],
            "cloned": pr.get("cloned"),
            "clone_dir": pr.get("clone_dir", ""),
            "stale": pr.get("stale", False),
            "files_scanned": pr.get("files_scanned"),
            "has_shizuku_dep": pr.get("has_shizuku_dep"),
            "has_shizuku_source": pr.get("has_shizuku_source"),
            "import_only_suspect": pr.get("import_only_suspect"),
            "shizuku_hits": pr.get("shizuku_hits", {}),
            "root_signals": pr.get("root_signals", {}),
            "snippets": (pr.get("snippets") or [])[:12],
            "meta": meta,
            "git": {k: git.get(k) for k in ("commit_count", "author_count", "first_date",
                                            "last_date", "timespan_hours", "shallow",
                                            "commit_sha", "commit_date")},
            "vibe_score": pr.get("vibe_score", 0),
            "vibe_reasons": pr.get("vibe_reasons", []),
            "neighbors": (neighbors.get(url) or [])[:3],
            "corpus_readme_file": readme_source,
            "corpus_license_file": (ci.get("license") or {}).get("file", "") or meta.get("license_file", ""),
            "readme_text": readme_text,
        })
        # Mechanical auto-verdict: repo inaccessible everywhere.
        rinfo = ci.get("readme") or {}
        if pr.get("cloned") is False and not readme_text.strip() and not rinfo.get("file"):
            auto.append({"url": url, "name": q["name"],
                         "verdict": "skip",
                         "reason": "repo inaccessible: git clone failed and no README fetchable; cannot verify, crawler will drop it if gone"})

    out_path = Path(args.out)
    with out_path.open("w", encoding="utf-8") as fh:
        for b in bundles:
            fh.write(json.dumps(b, ensure_ascii=False) + "\n")

    sdir = Path(args.slices_dir)
    sdir.mkdir(exist_ok=True)
    n = args.nslices
    slices = [bundles[i::n] for i in range(n)]
    for i, sl in enumerate(slices):
        (sdir / f"slice_{i}.json").write_text(json.dumps(sl, ensure_ascii=False, indent=1), encoding="utf-8")

    with open(args.auto_out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["url", "name", "verdict", "reason"])
        w.writeheader()
        w.writerows(auto)

    print(f"bundles={len(bundles)} slices={n} auto={len(auto)} -> {out_path}")


if __name__ == "__main__":
    main()
