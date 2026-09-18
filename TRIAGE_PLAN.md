Full Revised Plan — Triage SUMMARY.md recent releases
0. Goal
Iterate every item in SUMMARY.md → “Apps with releases / Updated in the last 3 months” (main list + its Non-original content and No GitHub stars <details> blocks), and for each decide:
1. Candidate for awesome-shizuku → stage in CANDIDATES_REVIEW.md
2. Ignore → append directly to correct ignore/*.lst + document in NEW_IGNORES.md
3. Skip → leave untouched in SUMMARY.md
You review both markdown files later; ignore-file edits land directly.
1. Inputs (all already inspected in plan mode)
- Source: /home/tim/Development/app-crawler/SUMMARY.md lines 15–~350 + lines 452–541 (details blocks of that section). ~350–400 URLs total for this run.
- Awesome list: /home/tim/Development/awesome-shizuku/README.md (categories: AI agents, Android TV, Audio, Automation, Communication, Customization, Development utilities, Device Owner, Display management, Entertainment, File management, Games, Input methods, Installer & app stores, Miscellaneous, Network, Patching, Power management, Privacy, Productivity, Quick settings, Software management, Task manager, Terminals, Vendor-specific → Pixel/Samsung/MIUI/Other, Closed-source, Dev libraries, Rish shell), plus pages/CLOSED_SOURCE.md, pages/ARCHIVED.md.
- Inclusion rules: /home/tim/Development/awesome-shizuku/CONTRIBUTING.md — format * [Name](url) - desc <250 chars \SPDX\` (Source code) (url)], alphabetical, EN landing page/README/docs, download link (APK/Play/F-Droid), not deprecated, OSS in main list vs closed-source in CLOSED_SOURCE.md, SPDX or Proprietary, tags (Paid/IAP/Ads/n-day trial/Root`).
- Ignore lists in /home/tim/Development/app-crawler/ignore/ (8 files, subsections preserved):
- ai-generated.lst (# Low-quality, vibecoded and other alternatives exist already / # Low-quality, vibecoded and not working or not useful)
- forks-duplicates-mirrors.lst (# Duplicates / Detached forks… / # Other forks…not important enough)
- immature-undocumented.lst (# Insufficient / No proper application / # Insufficient documentation)
- false-positives.lst (# False positives / # Imports Shizuku, but does not make use / # Already in list from another source)
- testing-learning.lst (# Testing stuff / learning / investigation / # Demos/examples)
- out-of-scope.lst (# Xposed/Root/Kernel stuff / # Other libraries / # Explicitly does not provide downloads)
- deprecated-archived-abandoned.lst (# Deprecated or archived / # Succeeded by a fork / # Not updated in a long time…)
- redundant-alternatives-exist.lst (# Too many equivalent alternatives / # Many IAP or Ad-Free alternatives / # Requirements not met & other alternatives)
- New subsections only when a genuinely new class emerges; otherwise fit existing.
2. Binding policies from your answers
- Evidence: webfetch every item (repo page + README + releases page minimum). If inconclusive → shallow clone only: git clone --depth 1 <url> /tmp/opencode/<name> and inspect AndroidManifest.xml, *shizuku*/UserService/rish references, LICENSE, releases/APK, commit history. No verdict on name-pattern alone.
- No-release: strict — no download link = skip. Largely moot in this slice (all “with releases”), but any entry whose releases turn out empty/deleted → skip, not candidate.
- Language: EN README/docs required. Chinese-only → ignore/skip, except if it solves an original task with no English OSS equivalent → candidate with translated <250-char description, exception noted in details.
- Root enablers: GhostLock*, Root-My-*, KSuRoot*, s26u-m3q-temp-root, SMTShell-type are in scope when they establish privilege via Shizuku/wireless ADB/CVE chain on stock devices. out-of-scope only with fetched proof the app requires pre-existing root and Shizuku is incidental.
- Shizuku forks (Cinnazuku, Nightzuku, ShizukuX, Shizako, Stellar, etc.): verify divergence + usability from README/releases/code; forks-duplicates-mirrors.lst only with evidence.
3. Per-item procedure
1. Extract name + URL + crawler blurb from SUMMARY.md, preserving order.
2. Dedup: exact URL/name against awesome README.md + CLOSED_SOURCE.md + ARCHIVED.md + all 8 ignore files. Match → record as already-handled, no action.
3. Fetch pack:
- README content + language, screenshots/docs quality, EN translation presence.
- License: LICENSE file / GitHub license API → SPDX; none/non-SPDX → Proprietary.
- Download: release with APK / Play / F-Droid link (verify asset exists, not just tag).
- Shizuku proof: provider/API/binder/UserService/shell-command evidence; import-only → false-positives.lst.
- Activity/maturity: last commit, release date, issues, single-commit vibecode signs, fork parent + ahead/behind.
- Category fit + draft <250-char EN description.
4. Classify with reason:
- Candidate if: EN docs (or justified exception), download, active/usable, real Shizuku use, OSS (closed-source-but-worthy noted separately for CLOSED_SOURCE.md), not a near-duplicate of a listed app.
- Ignore with exact target file + subsection + one-line reason.
- Skip if promising but unfinished/unclear, or evidence conflicting — stays in SUMMARY.md, reason logged in working notes but no file change.
5. Stage outputs (no commit/push; commits/PRs only on explicit request).
4. Outputs
- /home/tim/Development/app-crawler/CANDIDATES_REVIEW.md — alphabetical within proposed awesome category sections:
* [Name](https://github.com/owner/repo) - Short description, under 250 characters `SPDX`
<details><summary>* [Name](https://github.com/owner/repo) - Short description ... `SPDX`</summary>

Findings: what it does, Shizuku usage proof, releases/download link, license source, EN-doc status (+ translation note if applicable), proposed category + why, maturity/activity, alternatives considered.
</details>
- /home/tim/Development/app-crawler/NEW_IGNORES.md — grouped by ignore/<file>.lst / subsection, one entry per ignore decision:
* https://github.com/owner/repo → `ignore/<file>.lst` / `<subsection header>`
<details><summary>https://github.com/owner/repo → file / subsection</summary>

Why: fetched evidence, which rule it violates (with subsection rationale), why not another list, key links checked.
</details>
- Direct edits to ignore/*.lst: append https://github.com/owner/repo # short reason under the chosen subsection. Pre-check main.py/util.py/report.py parsing for inline # comments since you flagged the parser doesn’t handle them yet; still write the format you specified and report any breakage risk before finalizing.
5. Execution order
1. Parser check for inline ignore comments.
2. Recent-releases main list top-to-bottom in batches of ~30–50, parallel fetch workers, centralized verdict pass for consistency (especially clusters: call recorders, AppOps managers, keymappers, installer/stores, agent harnesses, Shizuku forks, exploit/root enablers, reader forks).
3. Write CANDIDATES_REVIEW.md + NEW_IGNORES.md, apply ignore/*.lst appends.
4. Verify: every candidate satisfies CONTRIBUTING; every ignore has a NEW_IGNORES.md twin; git status/diff shows only the two new files + intended ignore appends; counts reconciled (candidates + ignores + skips = items processed).
6. Non-goals for this run
- No changes to SUMMARY.md (generated), no edits to awesome-shizuku itself, no handling of >3 months ago or no releases sections, no PRs/commits
