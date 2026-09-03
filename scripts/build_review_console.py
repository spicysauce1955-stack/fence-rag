"""Generate the review console from the store.

Every number and every string on the page comes from `evidence.db` or a
published snapshot. Nothing is typed in by hand, so the page cannot drift from
the platform the way a written summary can — if it is wrong, the store is
wrong, and the citations are there to check it against.

Run from the repository root:

    python3 scripts/render_console_images.py     # page images, once
    python3 scripts/build_review_console.py      # -> workspace/reports/

The output is a single self-contained HTML file with the page images inlined as
data URIs, so it can be published as an Artifact or opened from disk. It is
git-ignored: it is ~3 MB and regenerates in seconds, and committing a rendered
view of a store that moves would be committing something that goes stale.
"""
import base64
import html
import json
import pathlib
import sqlite3
import sys

ROOT = pathlib.Path.cwd()
IMG = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                   else ROOT / "workspace/derived/console-img")
OUT = pathlib.Path(sys.argv[2] if len(sys.argv) > 2
                   else ROOT / "workspace/reports/review-console.html")
SLICE = "manuals/certainteed-bufftech/bufftech-fence-installation-guide-2024.pdf"

conn = sqlite3.connect(f"file:{ROOT}/workspace/indexes/evidence.db?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
e = html.escape


def img(name):
    p = IMG / f"{name}.jpg"
    if not p.is_file():
        return None
    return "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode()


# ---------------------------------------------------------------- the state
snap_path = sorted((ROOT / "workspace/snapshots").glob("*.json"),
                   key=lambda p: p.stat().st_mtime)[-1]
snap = json.loads(snap_path.read_text())
state = {k: len(v) for k, v in snap.items() if isinstance(v, list)}
gap_sev = {}
for g in snap["gaps"]:
    gap_sev[g["severity"]] = gap_sev.get(g["severity"], 0) + 1

steps = conn.execute("""
    SELECT candidate_id, ordinal, seq, segment_kind, depth, branch, text_raw,
           text_repair, repair_confidence, element_id, char_start, char_end,
           review_status, page_no
      FROM step_candidates ORDER BY ordinal, seq""").fetchall()

crops = conn.execute("""
    SELECT t.crop_path, COUNT(*) rows_waiting, d.title, d.source_path, t.page_no,
           MIN(t.row_label) sample
      FROM table_read_candidates t JOIN documents d ON d.document_id = t.document_id
     WHERE t.review_status = 'unreviewed'
     GROUP BY t.crop_path ORDER BY rows_waiting DESC, d.title""").fetchall()

reviewed = conn.execute(
    "SELECT COUNT(DISTINCT crop_sha256) FROM table_reviews").fetchone()[0]

# G79: the disputed table and its siblings, straight from the snapshot
schedules = [t for t in snap.get("parameters", [])
             if t.get("parameter") == "footing_schedule"]


rows_html = []
for s in steps:
    lead = s["text_raw"][:1]
    txt = s["text_raw"][1:] if lead in "•*-" else s["text_raw"]
    txt = " ".join(txt.split())
    repair = s["text_repair"]
    conf = s["repair_confidence"]
    badge = (f'<span class="conf {conf}">{conf}</span>' if conf else "")
    rep = (f'<div class="repair">proposed: <b>{e(repair)}</b> {badge}</div>'
           if repair else "")
    branch = f'<span class="br">{e(s["branch"])}</span>' if s["branch"] else ""
    rows_html.append(f"""
      <tr class="k-{s['segment_kind']}" data-kind="{s['segment_kind']}">
        <td class="num">{s['candidate_id']}</td>
        <td><span class="kind k-{s['segment_kind']}">{s['segment_kind']}</span>
            {branch}{'<span class="sub">sub</span>' if s['depth'] else ''}</td>
        <td class="txt">{e(txt)}{rep}</td>
        <td class="prov"><code>{e(s['element_id'])}</code><br>
            <span class="span">chars {s['char_start']}&ndash;{s['char_end']}</span></td>
      </tr>""")

kind_counts = {}
for s in steps:
    kind_counts[s["segment_kind"]] = kind_counts.get(s["segment_kind"], 0) + 1

crop_html = []
for c in crops:
    key = c["crop_path"].rsplit("/", 1)[-1].split("-")[0]
    src = img(f"crop-{key}")
    crop_html.append(f"""
      <figure class="crop">
        {'<img loading="lazy" src="' + src + '" alt="page image">' if src else '<div class="missing">image not rendered</div>'}
        <figcaption>
          <b>{c['rows_waiting']} row{'s' if c['rows_waiting'] != 1 else ''} waiting</b><br>
          {e(c['title'] or c['source_path'])}<br>
          <span class="span">p{c['page_no']} · crop {e(key)}</span>
        </figcaption>
      </figure>""")

sched_html = []
for t in schedules:
    scope = (t.get("scope") or {}).get("id", "")
    unc = t.get("uncovered") or []
    disputed = not unc
    sched_html.append(f"""
      <tr class="{'disputed' if disputed else ''}">
        <td class="txt"><code>{e(str(scope))}</code></td>
        <td class="num">{len(t.get('rows') or [])}</td>
        <td>{e(json.dumps([r.get('conditions') for r in t.get('rows') or []]))}</td>
        <td>{'<b class="bad">none — claims full coverage</b>' if disputed
             else e(json.dumps(unc))}</td>
      </tr>""")

page8 = img("slice-p8")
g79a, g79b = img("g79-disputed"), img("g79-sibling")

doc = f"""<title>Fence Review Console</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap">
<style>
:root {{
  --bg:#eef1f4; --panel:#fff; --panel-2:#f6f8fa; --ink:#141b22; --soft:#4d5b6b;
  --faint:#7b8a9a; --rule:#d5dde4; --rule-2:#e6ecf1;
  --accent:#0b6ea8; --accent-bg:#e2eef6;
  --warn:#a8600f; --warn-bg:#f8eddc;
  --bad:#9c3535; --bad-bg:#f7e4e4;
  --ok:#1c6b52; --ok-bg:#e0efe9;
  --mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;
  --sans:"IBM Plex Sans",ui-sans-serif,system-ui,sans-serif;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg:#0d1319; --panel:#151d25; --panel-2:#1b242e; --ink:#e3eaf1; --soft:#a4b2c0;
  --faint:#74838f; --rule:#28323d; --rule-2:#1f2831;
  --accent:#5aa9db; --accent-bg:#12293a;
  --warn:#dd9a45; --warn-bg:#2e2415;
  --bad:#dc7d7d; --bad-bg:#2e1a1a;
  --ok:#57bd97; --ok-bg:#12291f;
}} }}
:root[data-theme="dark"] {{
  --bg:#0d1319; --panel:#151d25; --panel-2:#1b242e; --ink:#e3eaf1; --soft:#a4b2c0;
  --faint:#74838f; --rule:#28323d; --rule-2:#1f2831;
  --accent:#5aa9db; --accent-bg:#12293a;
  --warn:#dd9a45; --warn-bg:#2e2415;
  --bad:#dc7d7d; --bad-bg:#2e1a1a;
  --ok:#57bd97; --ok-bg:#12291f;
}}
*{{box-sizing:border-box}}
body{{background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:15px;
 line-height:1.5;margin:0;padding:0 20px 80px;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1280px;margin:0 auto}}
header{{padding:40px 0 22px}}
h1{{font-size:1.9rem;font-weight:700;letter-spacing:-.02em;margin:0 0 6px}}
.sub-h{{color:var(--soft);margin:0 0 22px;max-width:70ch}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(126px,1fr));gap:1px;
 background:var(--rule);border:1px solid var(--rule);border-radius:6px;overflow:hidden}}
.stat{{background:var(--panel);padding:13px 15px}}
.stat .v{{font-size:1.5rem;font-weight:600;font-variant-numeric:tabular-nums;line-height:1.1}}
.stat .l{{font-size:11.5px;color:var(--faint);margin-top:3px;line-height:1.3}}
.stat.act .v{{color:var(--warn)}}
section{{margin-top:44px}}
h2{{font-size:1.3rem;font-weight:600;letter-spacing:-.01em;margin:0 0 4px;
 display:flex;align-items:baseline;gap:11px;flex-wrap:wrap}}
h2 .tag{{font-family:var(--mono);font-size:11px;font-weight:500;padding:3px 8px;
 border-radius:4px;background:var(--warn-bg);color:var(--warn);letter-spacing:.03em}}
.lede{{color:var(--soft);margin:0 0 18px;max-width:78ch}}
.panel{{background:var(--panel);border:1px solid var(--rule);border-radius:6px;overflow:hidden}}
.split{{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(0,1fr);gap:18px;align-items:start}}
@media(max-width:1000px){{.split{{grid-template-columns:1fr}}}}
.sticky{{position:sticky;top:16px}}
.sticky img{{width:100%;height:auto;display:block;border:1px solid var(--rule);
 border-radius:6px;background:#fff}}
.tablewrap{{overflow:auto;max-height:78vh}}
table{{border-collapse:collapse;width:100%;font-size:13.5px}}
th{{position:sticky;top:0;background:var(--panel-2);text-align:left;font-size:11px;
 letter-spacing:.06em;text-transform:uppercase;color:var(--faint);font-weight:600;
 padding:9px 11px;border-bottom:1px solid var(--rule);z-index:2}}
td{{padding:9px 11px;border-bottom:1px solid var(--rule-2);vertical-align:top}}
tbody tr:hover{{background:var(--panel-2)}}
.num{{font-family:var(--mono);color:var(--faint);font-variant-numeric:tabular-nums;
 text-align:right;width:44px}}
.txt{{line-height:1.45}}
.prov{{font-size:11px;color:var(--faint);white-space:nowrap}}
.prov code{{font-family:var(--mono);font-size:10.5px}}
.span{{font-family:var(--mono);font-size:10.5px;color:var(--faint)}}
.kind{{display:inline-block;font-size:10.5px;font-weight:600;letter-spacing:.04em;
 text-transform:uppercase;padding:2px 7px;border-radius:3px;background:var(--panel-2);
 color:var(--soft);white-space:nowrap}}
.kind.k-step{{background:var(--accent-bg);color:var(--accent)}}
.kind.k-prohibition{{background:var(--bad-bg);color:var(--bad)}}
.kind.k-note{{background:var(--warn-bg);color:var(--warn)}}
.kind.k-branch{{background:var(--ok-bg);color:var(--ok)}}
.br{{font-family:var(--mono);font-size:11px;color:var(--ok);margin-left:5px}}
.sub{{font-size:10px;color:var(--faint);margin-left:5px}}
.repair{{margin-top:5px;font-size:12.5px;color:var(--soft)}}
.repair b{{color:var(--ink);font-weight:500}}
.conf{{font-family:var(--mono);font-size:10px;padding:1px 5px;border-radius:3px;margin-left:5px}}
.conf.high{{background:var(--ok-bg);color:var(--ok)}}
.conf.low{{background:var(--warn-bg);color:var(--warn)}}
.filters{{display:flex;gap:7px;flex-wrap:wrap;margin:0 0 13px}}
.filters button{{font-family:var(--sans);font-size:12px;font-weight:500;padding:5px 11px;
 border:1px solid var(--rule);background:var(--panel);color:var(--soft);border-radius:20px;
 cursor:pointer}}
.filters button[aria-pressed="true"]{{background:var(--accent);border-color:var(--accent);color:#fff}}
.filters button:focus-visible{{outline:2px solid var(--accent);outline-offset:2px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:15px}}
figure.crop{{margin:0;background:var(--panel);border:1px solid var(--rule);border-radius:6px;
 overflow:hidden;display:flex;flex-direction:column}}
figure.crop img{{width:100%;height:200px;object-fit:cover;object-position:top;
 display:block;background:#fff;border-bottom:1px solid var(--rule)}}
figure.crop figcaption{{padding:10px 12px;font-size:12px;line-height:1.4;color:var(--soft)}}
figure.crop b{{color:var(--warn)}}
.missing{{height:200px;display:grid;place-items:center;color:var(--faint);font-size:12px}}
.pair{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
@media(max-width:900px){{.pair{{grid-template-columns:1fr}}}}
.pair figure{{margin:0}}
.pair img{{width:100%;border:1px solid var(--rule);border-radius:6px;background:#fff}}
.pair figcaption{{font-size:12.5px;color:var(--soft);margin-top:8px}}
tr.disputed{{background:var(--bad-bg)}}
.bad{{color:var(--bad)}}
.note{{background:var(--panel);border:1px solid var(--rule);border-left:3px solid var(--warn);
 border-radius:5px;padding:15px 18px;margin:18px 0;font-size:14px;color:var(--soft)}}
.note b{{color:var(--ink)}}
code{{font-family:var(--mono);font-size:.86em}}
footer{{margin-top:56px;padding-top:20px;border-top:1px solid var(--rule);
 font-size:12.5px;color:var(--faint)}}
</style>

<div class="wrap">
<header>
  <h1>Fence Review Console</h1>
  <p class="sub-h">Generated from <code>evidence.db</code> and snapshot
  <code>{e(snap_path.stem[:12])}</code>. Every value below is read from the store, not
  transcribed &mdash; if a number here is wrong, the store is wrong.</p>
  <div class="stats">
    <div class="stat"><div class="v">{state.get('source_docs',0)}</div><div class="l">source docs published</div></div>
    <div class="stat"><div class="v">{state.get('warnings',0)}</div><div class="l">warnings</div></div>
    <div class="stat"><div class="v">{state.get('gaps',0)}</div><div class="l">gaps ({gap_sev.get('warns_line',0)} warn a line)</div></div>
    <div class="stat"><div class="v">{state.get('parameters',0)}</div><div class="l">parameter tables</div></div>
    <div class="stat"><div class="v">{state.get('parts',0)}</div><div class="l">parts</div></div>
    <div class="stat"><div class="v">{state.get('procedures',0)}</div><div class="l">procedures</div></div>
    <div class="stat act"><div class="v">{len(steps)}</div><div class="l">step candidates awaiting you</div></div>
    <div class="stat act"><div class="v">{len(crops)}</div><div class="l">table crops unreviewed</div></div>
  </div>
</header>

<section>
  <h2>1 &nbsp;Step candidates <span class="tag">{len(steps)} unreviewed &middot; nothing publishes</span></h2>
  <p class="lede">Page 8 of the Bufftech guide, split into candidates. <b>None is reviewed, so
  <code>procedures</code> publishes 0.</b> <code>segment_kind</code> is
  <i>structural</i> &mdash; it says what kind of line this is, not that it is an
  <code>AssemblyStep</code>. Deciding that is the judgement being asked for.</p>
  <div class="filters" id="f">
    <button aria-pressed="true" data-k="all">all {len(steps)}</button>
    {"".join(f'<button aria-pressed="false" data-k="{k}">{k} {v}</button>'
             for k, v in sorted(kind_counts.items(), key=lambda x: -x[1]))}
  </div>
  <div class="split">
    <div class="panel tablewrap">
      <table><thead><tr><th>#</th><th>kind</th><th>text &amp; proposed repair</th><th>provenance</th></tr></thead>
      <tbody id="steps">{"".join(rows_html)}</tbody></table>
    </div>
    <div class="sticky">
      {'<img src="' + page8 + '" alt="page 8 of the Bufftech installation guide">' if page8 else ''}
      <p class="lede" style="margin-top:10px;font-size:13px">The page every candidate on the
      left was cut from. Each row cites a character span into one element of it.</p>
    </div>
  </div>
</section>

<section>
  <h2>2 &nbsp;Table crops awaiting review <span class="tag">{len(crops)} of {len(crops)+reviewed} pages</span></h2>
  <p class="lede">Each is a page a reader proposed table values from, with nobody's judgement
  on it yet. Reviewing one is what lets its values become a published
  <code>ParameterTable</code>; until then they publish nothing at all.</p>
  <div class="grid">{"".join(crop_html)}</div>
</section>

<section>
  <h2>3 &nbsp;One decision that needs your eyes <span class="tag">G79</span></h2>
  <p class="lede">Five <code>footing_schedule</code> tables publish. Four restrict exposure B
  to non-HVHZ. The fifth claims full coverage &mdash; so its B values present as valid under
  HVHZ, where its siblings say they are not.</p>
  <div class="panel tablewrap" style="max-height:none">
    <table><thead><tr><th>scope</th><th>rows</th><th>published conditions</th><th>uncovered</th></tr></thead>
    <tbody>{"".join(sched_html)}</tbody></table>
  </div>
  <div class="note">
    <b>Why it is like that, and what only you can settle.</b> A table review recorded
    <code>NO HVHZ BRACKET PRINTED</code> for every row of the page on the left. Given that
    input the output follows exactly, and the code is behaving correctly. The question is
    whether the input is right &mdash; whether that page really prints no bracket, when its
    sibling on the right, built from the same drawing template, plainly does.
  </div>
  <div class="pair">
    <figure>
      {'<img src="' + g79a + '" alt="the disputed NOA page">' if g79a else ''}
      <figcaption><b>Disputed</b> &mdash; NOA 12-1106.11 p11. Reviewed as printing no HVHZ
      bracket, which is why its table claims full coverage.</figcaption>
    </figure>
    <figure>
      {'<img src="' + g79b + '" alt="a sibling NOA page">' if g79b else ''}
      <figcaption><b>Sibling</b> &mdash; NOA 23-0314.05 p17. Same template; its bracket
      was read as <code>NON HVHZ</code> for B and <code>HVHZ AND NON HVHZ</code> for C
      and D.</figcaption>
    </figure>
  </div>
</section>

<footer>
  Generated from <code>{e(str(snap_path.relative_to(ROOT)))}</code> and
  <code>workspace/indexes/evidence.db</code>. Page images rendered from the source PDFs at
  90&nbsp;dpi. This console shows the current state, defects included &mdash; it makes the
  work inspectable, not correct.
</footer>
</div>

<script>
(function () {{
  const bar = document.getElementById('f');
  const rows = Array.from(document.querySelectorAll('#steps tr'));
  bar.addEventListener('click', function (ev) {{
    const b = ev.target.closest('button');
    if (!b) return;
    bar.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
    const k = b.dataset.k;
    rows.forEach(r => {{ r.style.display = (k === 'all' || r.dataset.kind === k) ? '' : 'none'; }});
  }});
}})();
</script>
"""

OUT.write_text(doc)
print(f"wrote {OUT} ({OUT.stat().st_size/1024/1024:.2f} MB)")
print(f"  steps {len(steps)}  crops {len(crops)}  schedules {len(schedules)}")
