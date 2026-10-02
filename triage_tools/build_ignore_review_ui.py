#!/usr/bin/env python3
"""Generate review_ignores.html: interactive dark-mode review UI for proposed ignores.

Reads triage_tools/verdicts.csv (ignore rows), the current ignore/*.lst entries
and (optionally) triage_tools/triage_enriched.json for star counts, then embeds
everything as JSON into a single self-contained review_ignores.html.

Maintainer decisions are autosaved to browser localStorage and can be
exported (download) / imported as ignore_decisions.json:
  {"<url>": {"decision": "confirm|skip|reject", "file": ..., "subsection": ...,
             "reason": ..., "note": ..., "ts": ...}}

Usage: python3 triage_tools/build_ignore_review_ui.py [--out review_ignores.html]
"""
import argparse
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def normalize_url(u):
    u = (u or "").strip().lower().rstrip("/")
    if u.endswith(".git"):
        u = u[:-4]
    return u


def parse_ignore_files(ignore_dir):
    groups = []
    entries = {}
    for p in sorted(Path(ignore_dir).glob("*.lst")):
        current = None
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                current = line[2:].strip()
                groups.append({"key": f"{p.name}|||{current}", "file": p.name,
                               "sub": current, "count": 0})
                continue
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            url = s.split(" # ", 1)[0].strip().split("#", 1)[0].strip()
            if "://" not in url:
                continue
            entries[normalize_url(url)] = s
            if current is not None:
                groups[-1]["count"] += 1
    return groups, entries


def load_ignores(verdicts_csv, enriched_json, entries):
    stars = {}
    if enriched_json and Path(enriched_json).is_file():
        for r in json.loads(Path(enriched_json).read_text(encoding="utf-8")):
            u = normalize_url(r.get("url"))
            s = (r.get("enriched") or {}).get("stars")
            if u and isinstance(s, int):
                stars[u] = s
    items = []
    with open(verdicts_csv, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if (r.get("verdict") or "").strip() != "ignore":
                continue
            u = r.get("url") or ""
            d = {k: (r.get(k) or "") for k in (
                "url", "name", "category", "license", "en_desc", "findings",
                "reason", "shizuku_proof", "en_status", "vibe_score",
                "vibe_reasons", "alternatives", "recency",
                "ignore_file", "subsection")}
            s = stars.get(normalize_url(u))
            d["stars"] = s if s is not None else ""
            d["entry"] = entries.get(normalize_url(u), "")
            d["g"] = f"{d['ignore_file']}|||{d['subsection']}"
            items.append(d)
    return items


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Shizuku triage ignore review</title>
<style>
:root { color-scheme: dark; }
body { background:#111418; color:#dfe6ee; font-family:system-ui,sans-serif; margin:0; }
header { position:sticky; top:0; background:#1a1f26; border-bottom:1px solid #333; padding:10px 16px; z-index:10; }
header .row { display:flex; gap:10px; align-items:center; flex-wrap:wrap; }
#progress { font-weight:bold; }
button, select, input[type=text] { background:#242b34; color:#dfe6ee; border:1px solid #444; border-radius:6px; padding:6px 10px; }
button:hover { background:#2e3742; cursor:pointer; }
button.active { background:#0d5cab; border-color:#0d5cab; }
#search { flex:1; min-width:200px; }
main { max-width:1000px; margin:0 auto; padding:12px 16px 60px; }
section.grp { margin-top:18px; }
section.grp > h1 { font-size:1.05em; border-bottom:1px solid #333; padding-bottom:4px; }
section.grp > h1 .sub { color:#9aa7b5; font-weight:normal; font-size:.8em; }
section.grp > h1 .toggle { float:right; font-size:.75em; color:#9aa7b5; background:none; border:none; cursor:pointer; }
.grpkey { color:#9aa7b5; font-size:.8em; font-weight:normal; }
.card { background:#1a1f26; border:1px solid #333; border-radius:10px; padding:12px 14px; margin:10px 0; }
.card h2 { margin:0 0 4px; font-size:1.05em; }
.card h2 a { color:#6cb8ff; text-decoration:none; }
.meta { color:#9aa7b5; font-size:.85em; margin:4px 0; }
.desc { margin:6px 0; }
.target { margin:6px 0; font-size:.9em; }
.target code { color:#ffd479; }
.entry { margin:6px 0; font-size:.85em; color:#9aa7b5; }
.entry code { color:#9ad48f; word-break:break-all; }
details { margin-top:6px; font-size:.88em; color:#b9c4d0; }
.decide { display:flex; gap:8px; margin-top:10px; flex-wrap:wrap; align-items:center; }
.decide label { border:1px solid #444; border-radius:6px; padding:5px 12px; cursor:pointer; }
input[type=radio] { accent-color:#0d5cab; }
label.sel-confirm { background:#0b4d2c; border-color:#0b4d2c; }
label.sel-skip { background:#5c4a0d; border-color:#5c4a0d; }
label.sel-reject { background:#6b1a1a; border-color:#6b1a1a; }
.note { width:100%; margin-top:8px; }
.badge { display:inline-block; font-size:.75em; border-radius:4px; padding:1px 7px; margin-left:6px; }
.b-confirm { background:#0b4d2c; } .b-skip { background:#5c4a0d; } .b-reject { background:#6b1a1a; }
.counts { font-size:.9em; color:#9aa7b5; }
</style>
</head>
<body>
<header>
<div class="row">
<span id="progress"></span>
<span class="counts" id="counts"></span>
</div>
<div class="row" style="margin-top:8px">
<input type="text" id="search" placeholder="Search name, description, reason, url...">
<select id="grpjump"><option value="">Jump to section…</option></select>
</div>
<div class="row" style="margin-top:8px">
<button data-f="all" class="active">All</button>
<button data-f="pending">Pending</button>
<button data-f="confirm">Confirmed</button>
<button data-f="skip">Skipped</button>
<button data-f="reject">Rejected</button>
<button id="export">Export decisions</button>
<button id="importBtn">Import decisions</button>
<input type="file" id="import" accept=".json" style="display:none">
<button id="reset">Reset</button>
</div>
</header>
<main id="list"></main>
<script>
const DATA = __DATA__;
const GROUPS = __GROUPS__;
const KEY = "shizuku_ignore_review_v1";
const COLKEY = "shizuku_ignore_review_collapsed_v1";
let decisions = {};
try { decisions = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch(e) { decisions = {}; }
let collapsed = {};
try { collapsed = JSON.parse(localStorage.getItem(COLKEY) || "{}"); } catch(e) { collapsed = {}; }
let filter = "all", query = "";
function save() { localStorage.setItem(KEY, JSON.stringify(decisions)); updateCounts(); }
function updateCounts() {
  const vals = Object.values(decisions);
  const n = d => vals.filter(v => v.decision === d).length;
  document.getElementById("counts").textContent =
    `${DATA.length} proposed ignores | reviewed ${vals.length} | confirm ${n("confirm")} | skip ${n("skip")} | reject ${n("reject")}`;
  document.getElementById("progress").textContent =
    vals.length === DATA.length ? "All reviewed!" : `${DATA.length - vals.length} pending`;
}
function esc(s){ return String(s??"").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c])); }
function card(c, i) {
  const d = decisions[c.url] || {};
  return `<div class="card" data-i="${i}">
    <h2><a href="${esc(c.url)}" target="_blank" rel="noopener">${esc(c.name)}</a>
    <span class="badge b-${d.decision||""}">${d.decision||"pending"}</span></h2>
    <div class="meta">${esc(c.category)} · <code>${esc(c.license)}</code> · ★${esc(c.stars === "" ? "?" : c.stars)} · ${esc(c.recency)} · vibe ${esc(c.vibe_score)}${c.alternatives?` · alt: ${esc(c.alternatives)}`:""}</div>
    <div class="desc">${esc(c.en_desc)}</div>
    <div class="target">ignore as: <code>${esc(c.ignore_file)} › ${esc(c.subsection)}</code></div>
    <div class="entry">in list: ${c.entry?`<code>${esc(c.entry)}</code>`:"<i>not found in ignore files</i>"}</div>
    <details><summary>reason + evidence</summary>
      <p><b>Why:</b> ${esc(c.reason)}</p>
      <p><b>Findings:</b> ${esc(c.findings)}</p>
      <p><b>Code signals:</b> ${esc(c.shizuku_proof)}</p>
      <p><b>Vibe:</b> ${esc(c.vibe_reasons)}</p>
    </details>
    <div class="decide">
      ${["confirm","skip","reject"].map(v=>`<label class="${d.decision===v?"sel-"+v:""}"><input type="radio" name="dec-${i}" value="${v}" ${d.decision===v?"checked":""}> ${v}</label>`).join("")}
      <input class="note" type="text" data-k="note" placeholder="note (optional)" value="${esc(d.note||"")}">
    </div>
  </div>`;
}
function render() {
  const q = query.toLowerCase();
  const byGroup = {};
  DATA.forEach((c,i) => {
    const dec = (decisions[c.url]||{}).decision || "pending";
    if (filter !== "all" && dec !== filter) return;
    if (q && !((c.name+" "+c.en_desc+" "+c.reason+" "+c.url+" "+c.ignore_file+" "+c.subsection).toLowerCase().includes(q))) return;
    (byGroup[c.g] = byGroup[c.g] || []).push([c,i]);
  });
  const order = GROUPS.map(g => g.key).filter(k => byGroup[k]);
  Object.keys(byGroup).forEach(k => { if (!order.includes(k)) order.push(k); });
  const meta = {}; GROUPS.forEach(g => meta[g.key] = g);
  const list = document.getElementById("list");
  list.innerHTML = order.map(key => {
    const items = byGroup[key];
    const g = meta[key] || {file:"?", sub:key};
    const done = items.filter(([c]) => decisions[c.url]).length;
    const isCol = !!collapsed[key];
    const cards = items.map(([c,i]) => card(c,i)).join("");
    return `<section class="grp" data-k="${esc(key)}"><h1><span class="grpkey">${esc(g.file)} ›</span> ${esc(g.sub)} <span class="sub">${done}/${items.length} reviewed</span><button class="toggle">${isCol?"expand":"collapse"}</button></h1><div class="cards"${isCol?' style="display:none"':""}>${cards}</div></section>`;
  }).join("") || "<p>No matches.</p>";
  list.querySelectorAll("section.grp").forEach(sec => {
    const key = sec.dataset.k;
    sec.querySelector("h1 .toggle").addEventListener("click", (e) => {
      const cards = sec.querySelector(".cards");
      const nowHidden = cards.style.display !== "none";
      cards.style.display = nowHidden ? "none" : "";
      e.target.textContent = nowHidden ? "expand" : "collapse";
      if (nowHidden) collapsed[key] = 1; else delete collapsed[key];
      localStorage.setItem(COLKEY, JSON.stringify(collapsed));
    });
  });
  list.querySelectorAll(".card").forEach(el => {
    const c = DATA[+el.dataset.i];
    el.querySelectorAll("input[type=radio]").forEach(r => r.addEventListener("change", () => {
      const cur = decisions[c.url] || {};
      cur.decision = r.value; cur.file = c.ignore_file; cur.subsection = c.subsection;
      cur.reason = c.reason; cur.ts = new Date().toISOString();
      decisions[c.url] = cur; save(); render();
    }));
    el.querySelectorAll("[data-k=note]").forEach(inp => inp.addEventListener("change", () => {
      const cur = decisions[c.url] || {};
      cur[inp.dataset.k] = inp.value; cur.ts = new Date().toISOString();
      decisions[c.url] = cur; save();
    }));
  });
}
document.getElementById("search").addEventListener("input", e => { query = e.target.value; render(); });
const grpjump = document.getElementById("grpjump");
GROUPS.filter(g => DATA.some(d => d.g === g.key)).forEach(g => {
  const o = document.createElement("option"); o.value = g.key; o.textContent = `${g.file} › ${g.sub} (${g.count})`;
  grpjump.appendChild(o);
});
grpjump.addEventListener("change", () => {
  if (!grpjump.value) return;
  const el = document.querySelector(`section.grp[data-k="${CSS.escape(grpjump.value)}"]`);
  if (el) el.scrollIntoView();
});
document.querySelectorAll("button[data-f]").forEach(b => b.addEventListener("click", () => {
  document.querySelectorAll("button[data-f]").forEach(x=>x.classList.remove("active"));
  b.classList.add("active"); filter = b.dataset.f; render();
}));
document.getElementById("export").addEventListener("click", () => {
  const blob = new Blob([JSON.stringify(decisions, null, 1)], {type:"application/json"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = "ignore_decisions.json"; a.click();
  URL.revokeObjectURL(a.href);
});
document.getElementById("importBtn").addEventListener("click", () => document.getElementById("import").click());
document.getElementById("import").addEventListener("change", e => {
  const f = e.target.files[0]; if (!f) return;
  const rd = new FileReader();
  rd.onload = () => { try { decisions = JSON.parse(rd.result); save(); render(); } catch(err){ alert("Invalid JSON"); } };
  rd.readAsText(f);
});
document.getElementById("reset").addEventListener("click", () => {
  if (confirm("Clear all decisions?")) { decisions = {}; save(); render(); }
});
updateCounts(); render();
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verdicts", default=str(HERE / "verdicts.csv"))
    ap.add_argument("--enriched", default=str(HERE / "triage_enriched.json"))
    ap.add_argument("--ignore-dir", default=str(ROOT / "ignore"))
    ap.add_argument("--out", default=str(ROOT / "review_ignores.html"))
    args = ap.parse_args()

    groups, entries = parse_ignore_files(args.ignore_dir)
    items = load_ignores(args.verdicts, args.enriched, entries)
    page = PAGE.replace("__DATA__", json.dumps(items)).replace(
        "__GROUPS__", json.dumps(groups))
    Path(args.out).write_text(page, encoding="utf-8")
    print(f"{len(items)} proposed ignores in {len({i['g'] for i in items})} sections "
          f"-> {args.out}")


if __name__ == "__main__":
    main()
