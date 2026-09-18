# Triage tools

Helpers for the `SUMMARY.md` → `awesome-shizuku` triage. Scope: **all of
“Apps with releases”** (recent + older than 3 months; use `--recent-only`
on `triage_extract.py` for the old slice).

Clones are persistent: `clone_inspect.py` keeps every checkout under
`clones/` (gitignored, never deleted — reuse via fetch+reset, plus
`clones/manifest.json`). README/LICENSE evidence comes from the clone;
`fetch_readmes.py`/`corpus/` is legacy fallback for uncloneable URLs only.

## Pipeline

```bash
cd triage_tools
python3 triage_extract.py                       # -> triage_queue.json/csv (339 items, recency=recent|older)
python3 dedup_check.py                          # -> dedup_report.json
python3 feature_overlap.py                      # -> awesome_neighbors.json (lenient: info only, never auto-ignores)
python3 ignore_lint.py                          # read-only; see util.py inline-comment gap!

# needs network; gh auth or $GITHUB_AUTH recommended (60 req/h without)
python3 enrich_github.py                        # -> triage_enriched.json (cached in ../cache/triage/)
python3 clone_inspect.py --mode all --merge     # -> triage_proof.json (clones kept in clones/; --resume after kills)
# --fresh forces re-clone; --full-history enables commit-count vibe signals (bigger download)

python3 draft_entries.py --init-from-enriched triage_enriched.json --dedup dedup_report.json --out-verdicts verdicts.csv
# ... fill verdict column in verdicts.csv (candidate|ignore|skip) ...
# verdict rows also carry: vibe_score/vibe_reasons (0-3 flag, reviewer decides),
# alternatives (nearest awesome-list neighbors), recency
python3 draft_entries.py --verdicts verdicts.csv --check-only
python3 draft_entries.py --verdicts verdicts.csv   # -> ../CANDIDATES_REVIEW.md + ../NEW_IGNORES.md
```

## Scripts

| Script | Purpose |
|---|---|
| `common.py` | Shared SUMMARY parser, ignore/awesome loaders, URL normalization |
| `triage_extract.py` | Parse the all-releases slice into a work queue (`--recent-only` for old slice) |
| `dedup_check.py` | Match queue against awesome list + all `ignore/*.lst` subsections |
| `feature_overlap.py` | Nearest awesome-list neighbors per queue item (lenient overlap info) |
| `enrich_github.py` | GitHub API evidence pack per repo (README/lang/license/releases/stars/fork), cached + resumable |
| `clone_inspect.py` | Persistent-clone grep for Shizuku proof / root-direction signals + vibe score; clones never deleted |
| `draft_entries.py` | Validate verdicts; generate the two review files in `<details><summary>` format |
| `ignore_lint.py` | Duplicate/malformed/inline-comment audit for `ignore/*.lst` |

## Important: inline ignore comments

`util._load_ignore_list()` now strips inline `URL # reason` comments (splits
on `" #"`), so such lines filter normally. `ignore_lint.py` functionally
verifies this on every run. `append_ignores.py` writes that format.
