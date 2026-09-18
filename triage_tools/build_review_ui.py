#!/usr/bin/env python3
"""Generate review.html: interactive dark-mode triage UI for candidate verdicts.

Reads triage_tools/verdicts.csv (candidate rows) + ignore/*.lst subsection
headers, embeds them as JSON into a single self-contained review.html.

Maintainer decisions are autosaved to browser localStorage and can be
exported (download) / imported as maintainer_decisions.json:
  {"<url>": {"decision": "accept|skip|deny", "deny_file": ...,
             "deny_subsection": ..., "reason": ..., "note": ..., "ts": ...}}
Save that file into the repo (e.g. triage_tools/) so it can be applied later.

Usage: python3 triage_tools/build_review_ui.py [--out review.html]
"""
import argparse
import csv
import html
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from common import AWESOME_CATEGORIES  # noqa: E402


def parse_ignore_files(ignore_dir):
    files = {}
    for p in sorted(Path(ignore_dir).glob("*.lst")):
        subs = []
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                subs.append(line[2:].strip())
        files[p.name] = subs
    return files


def load_candidates(verdicts_csv, enriched_json=None):
    stars = {}
    if enriched_json and Path(enriched_json).is_file():
        for r in json.loads(Path(enriched_json).read_text(encoding="utf-8")):
            u = (r.get("url") or "").rstrip("/")
            s = (r.get("enriched") or {}).get("stars")
            if u and isinstance(s, int):
                stars[u] = s
    cands = []
    with open(verdicts_csv, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if (r.get("verdict") or "").strip() != "candidate":
                continue
            d = {k: (r.get(k) or "") for k in (
                "url", "name", "category", "license", "en_desc", "findings",
                "download", "license_source", "shizuku_proof", "en_status",
                "vibe_score", "vibe_reasons", "alternatives", "recency")}
            s = stars.get((d["url"] or "").rstrip("/"))
            d["stars"] = s if s is not None else ""
            cands.append(d)
    return cands


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Shizuku triage review</title>
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
section.cat { margin-top:18px; }
section.cat > h1 { font-size:1.1em; border-bottom:1px solid #333; padding-bottom:4px; }
section.cat > h1 .sub { color:#9aa7b5; font-weight:normal; font-size:.8em; }
section.cat > h1 .toggle { float:right; font-size:.75em; color:#9aa7b5; background:none; border:none; cursor:pointer; }
.card { background:#1a1f26; border:1px solid #333; border-radius:10px; padding:12px 14px; margin:10px 0; }
.card h2 { margin:0 0 4px; font-size:1.05em; }
.card h2 a { color:#6cb8ff; text-decoration:none; }
.meta { color:#9aa7b5; font-size:.85em; margin:4px 0; }
.desc { margin:6px 0; }
details { margin-top:6px; font-size:.88em; color:#b9c4d0; }
.decide { display:flex; gap:8px; margin-top:10px; flex-wrap:wrap; align-items:center; }
.decide label { border:1px solid #444; border-radius:6px; padding:5px 12px; cursor:pointer; }
input[type=radio] { accent-color:#0d5cab; }
label.sel-accept { background:#0b4d2c; border-color:#0b4d2c; }
label.sel-skip { background:#5c4a0d; border-color:#5c4a0d; }
label.sel-deny { background:#6b1a1a; border-color:#6b1a1a; }
.denybox { display:none; gap:8px; margin-top:8px; flex-wrap:wrap; width:100%; }
.denybox.show { display:flex; }
.note { width:100%; margin-top:8px; }
.badge { display:inline-block; font-size:.75em; border-radius:4px; padding:1px 7px; margin-left:6px; }
.b-accept { background:#0b4d2c; } .b-skip { background:#5c4a0d; } .b-deny { background:#6b1a1a; }
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
<input type="text" id="search" placeholder="Search name, description, category...">
<select id="catjump"><option value="">Jump to category…</option></select>
</div>
<div class="row" style="margin-top:8px">
<button data-f="all" class="active">All</button>
<button data-f="pending">Pending</button>
<button data-f="accept">Accepted</button>
<button data-f="skip">Skipped</button>
<button data-f="deny">Denied</button>
<button id="export">Export decisions</button>
<button id="importBtn">Import decisions</button>
<input type="file" id="import" accept=".json" style="display:none">
<button id="reset">Reset</button>
</div>
</header>
<main id="list"></main>
<script>
const DATA = __DATA__;
const IGNORE = __IGNORE__;
const CAT_ORDER = __CATORDER__;
const KEY = "shizuku_triage_decisions_v1";
const COLKEY = "shizuku_triage_collapsed_v1";
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
    `${DATA.length} candidates | reviewed ${vals.length} | accept ${n("accept")} | skip ${n("skip")} | deny ${n("deny")}`;
  document.getElementById("progress").textContent =
    vals.length === DATA.length ? "All reviewed!" : `${DATA.length - vals.length} pending`;
}
function esc(s){ return String(s??"").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c])); }
function card(c, i) {
  const d = decisions[c.url] || {};
  const denyOpts = Object.entries(IGNORE).map(([f, subs]) =>
    `<optgroup label="${esc(f)}">` + subs.map(s => `<option value="${esc(f)}|||${esc(s)}" ${d.deny_file===f&&d.deny_subsection===s?"selected":""}>${esc(s)}</option>`).join("") + `</optgroup>`).join("");
  return `<div class="card" data-i="${i}">
    <h2><a href="${esc(c.url)}" target="_blank" rel="noopener">${esc(c.name)}</a>
    <span class="badge b-${d.decision||""}">${d.decision||"pending"}</span></h2>
    <div class="meta">${esc(c.category)} · <code>${esc(c.license)}</code> · ★${esc(c.stars === "" ? "?" : c.stars)} · ${esc(c.recency)} · vibe ${esc(c.vibe_score)}${c.alternatives?` · alt: ${esc(c.alternatives)}`:""}</div>
    <div class="desc">${esc(c.en_desc)}</div>
    <div class="meta">download: ${c.download?`<a href="${esc(c.download)}" target="_blank" rel="noopener">${esc(c.download)}</a>`:"<i>none recorded</i>"} (${esc(c.license_source)}, en:${esc(c.en_status)})</div>
    <details><summary>findings + shizuku proof</summary>
      <p>${esc(c.findings)}</p>
      <p><b>Shizuku:</b> ${esc(c.shizuku_proof)}</p>
      <p><b>Vibe:</b> ${esc(c.vibe_reasons)}</p>
    </details>
    <div class="decide">
      ${["accept","skip","deny"].map(v=>`<label class="${d.decision===v?"sel-"+v:""}"><input type="radio" name="dec-${i}" value="${v}" ${d.decision===v?"checked":""}> ${v}</label>`).join("")}
      <div class="denybox ${d.decision==="deny"?"show":""}">
        <select data-k="deny_sel"><option value="">deny reason: file / subsection…</option>${denyOpts}</select>
        <input type="text" data-k="reason" placeholder="reason (inline comment)" value="${esc(d.reason||"")}" style="flex:1;min-width:200px">
      </div>
      <input class="note" type="text" data-k="note" placeholder="note (optional)" value="${esc(d.note||"")}">
    </div>
  </div>`;
}
function render() {
  const q = query.toLowerCase();
  const groups = {};
  DATA.forEach((c,i) => {
    const dec = (decisions[c.url]||{}).decision || "pending";
    if (filter !== "all" && dec !== filter) return;
    if (q && !((c.name+" "+c.en_desc+" "+c.category+" "+c.url).toLowerCase().includes(q))) return;
    (groups[c.category] = groups[c.category] || []).push([c,i]);
  });
  const cats = Object.keys(groups).sort((a,b) => {
    const ia = CAT_ORDER.indexOf(a), ib = CAT_ORDER.indexOf(b);
    return (ia<0?999:ia) - (ib<0?999:ib);
  });
  const list = document.getElementById("list");
  list.innerHTML = cats.map(cat => {
    const items = groups[cat];
    const done = items.filter(([c]) => decisions[c.url]).length;
    const isCol = !!collapsed[cat];
    const cards = items.map(([c,i]) => card(c,i)).join("");
    return `<section class="cat" data-cat="${esc(cat)}" id="cat-${esc(cat).replace(/[^a-z0-9]+/gi,"-")}"><h1>${esc(cat)} <span class="sub">${done}/${items.length} reviewed</span><button class="toggle">${isCol?"expand":"collapse"}</button></h1><div class="cards"${isCol?' style="display:none"':""}>${cards}</div></section>`;
  }).join("") || "<p>No matches.</p>";
  list.querySelectorAll("section.cat").forEach(sec => {
    const cat = sec.dataset.cat;
    sec.querySelector("h1 .toggle").addEventListener("click", (e) => {
      const cards = sec.querySelector(".cards");
      const nowHidden = cards.style.display !== "none";
      cards.style.display = nowHidden ? "none" : "";
      e.target.textContent = nowHidden ? "expand" : "collapse";
      if (nowHidden) collapsed[cat] = 1; else delete collapsed[cat];
      localStorage.setItem(COLKEY, JSON.stringify(collapsed));
    });
  });
  list.querySelectorAll(".card").forEach(el => {
    const c = DATA[+el.dataset.i];
    el.querySelectorAll("input[type=radio]").forEach(r => r.addEventListener("change", () => {
      const cur = decisions[c.url] || {};
      cur.decision = r.value; cur.ts = new Date().toISOString();
      decisions[c.url] = cur; save(); render();
    }));
    const sel = el.querySelector("[data-k=deny_sel]");
    if (sel) sel.addEventListener("change", () => {
      const cur = decisions[c.url] || {};
      const [f, s] = (sel.value||"|||").split("|||");
      cur.deny_file = f; cur.deny_subsection = s; cur.ts = new Date().toISOString();
      if (!cur.decision) cur.decision = "deny";
      decisions[c.url] = cur; save(); updateCounts();
    });
    el.querySelectorAll("[data-k=reason],[data-k=note]").forEach(inp => inp.addEventListener("change", () => {
      const cur = decisions[c.url] || {};
      cur[inp.dataset.k] = inp.value; cur.ts = new Date().toISOString();
      decisions[c.url] = cur; save();
    }));
  });
}
document.getElementById("search").addEventListener("input", e => { query = e.target.value; render(); });
const catjump = document.getElementById("catjump");
CAT_ORDER.filter(c => DATA.some(d => d.category === c)).forEach(c => {
  const o = document.createElement("option"); o.value = c; o.textContent = c; catjump.appendChild(o);
});
catjump.addEventListener("change", () => {
  if (!catjump.value) return;
  const el = document.getElementById("cat-" + catjump.value.replace(/[^a-z0-9]+/gi,"-"));
  if (el) el.scrollIntoView();
});
document.querySelectorAll("button[data-f]").forEach(b => b.addEventListener("click", () => {
  document.querySelectorAll("button[data-f]").forEach(x=>x.classList.remove("active"));
  b.classList.add("active"); filter = b.dataset.f; render();
}));
document.getElementById("export").addEventListener("click", () => {
  const blob = new Blob([JSON.stringify(decisions, null, 1)], {type:"application/json"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = "maintainer_decisions.json"; a.click();
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
    ap.add_argument("--out", default=str(ROOT / "review.html"))
    args = ap.parse_args()

    cands = load_candidates(args.verdicts, args.enriched)
    ignore = parse_ignore_files(args.ignore_dir)
    page = PAGE.replace("__DATA__", json.dumps(cands)).replace(
        "__IGNORE__", json.dumps(ignore)).replace(
        "__CATORDER__", json.dumps(AWESOME_CATEGORIES))
    Path(args.out).write_text(page, encoding="utf-8")
    print(f"{len(cands)} candidates, {sum(len(v) for v in ignore.values())} "
          f"deny subsections -> {args.out}")


if __name__ == "__main__":
    main()
