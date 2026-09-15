"""Generate the review console from the store — and the step workbench in it.

Every number and every string on the page comes from `evidence.db` or a
published snapshot. Nothing is typed in by hand, so the page cannot drift from
the platform the way a written summary can — if it is wrong, the store is
wrong, and the citations are there to check it against.

Run from the repository root:

    python3 scripts/render_console_images.py     # page images, once
    python3 scripts/build_review_console.py      # -> workspace/reports/
    python3 scripts/build_review_console.py --document DOC --page N

**What section 1 is for.** `procedures` publishes 0, and it publishes 0 because
no step candidate has ever been reviewed: `AssemblyStep.kind` and `scope` are
required by the shape and only a person may decide them. Until now the console
printed the candidates read-only — a reviewer could read the queue and had
nowhere to put an answer. Section 1 is now a workbench: the sentence beside the
page it was cut from, the machine's proposal where there is one, and a control
per row. It writes no database; it emits a JSONL decision file, and

    python3 -m fence_evidence.cli review --apply-steps FILE --reviewer NAME --apply

records the sitting, whole or not at all.

The output is a single self-contained HTML file with the page images inlined as
data URIs, so it can be published as an Artifact or opened from disk. It is
git-ignored: it regenerates in seconds, and committing a rendered view of a
store that moves would be committing something that goes stale.
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import pathlib
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fence_evidence.paths import open_write  # noqa: E402
from fence_evidence.reviews import STEP_KINDS, STEP_SCOPES  # noqa: E402

DEFAULT_IMG = ROOT / "workspace/derived/console-img"
DEFAULT_OUT = ROOT / "workspace/reports/review-console.html"
# The slice CLAUDE.md names: page 8 of the 2024 Bufftech guide, the page the
# step design was worked against and the one page whose image is already
# rendered under its own name.
SLICE_DOC = "manuals/certainteed-bufftech/bufftech-fence-installation-guide-2024.pdf"

e = html.escape

# `SlotTarget` is a tagged union (`knowledge-datamodel.md` §3.6) and nothing
# validates its variants, so the console offers the ones the corpus actually
# uses rather than a free-text box: a mistyped variant publishes as a shape
# nobody declared. "other" leaves the field empty — an unsure reviewer records
# no slot rather than a wrong one.
SLOT_PRESETS = [
    ("", "— no slot —"),
    ('{"kind":"PostSlot","key":"post"}', "PostSlot · post"),
    ('{"kind":"PostSlot","key":"cap"}', "PostSlot · cap"),
    ('{"kind":"Footing","part":"hole"}', "Footing · hole"),
    ('{"kind":"Footing","part":"gravel"}', "Footing · gravel"),
    ('{"kind":"Footing","part":"concrete"}', "Footing · concrete"),
    ('{"kind":"PanelSlot","path":"bottom_rail"}', "PanelSlot · bottom_rail"),
    ('{"kind":"PanelSlot","path":"top_rail"}', "PanelSlot · top_rail"),
    ('{"kind":"SiteFixture","kind_of":"string_line"}', "SiteFixture · string line"),
    ('{"kind":"SiteFixture","kind_of":"stake"}', "SiteFixture · stake"),
]


# ---------------------------------------------------------------- the store
def connect(db=None) -> sqlite3.Connection:
    db = db or ROOT / "workspace/indexes/evidence.db"
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def img(name, img_dir=None):
    """A rendered page as a data URI, or None when it was never rendered."""
    p = pathlib.Path(img_dir or DEFAULT_IMG) / f"{name}.jpg"
    if not p.is_file():
        return None
    return "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode()


def page_image(conn, document_id, page_no, img_dir=None):
    """The page a sitting is worked against.

    Two names, because the slice page was rendered under a hand-written one
    before the per-page renderer existed and re-rendering it would be the only
    reason to make somebody run poppler again.
    """
    hit = img(f"step-{document_id}-p{page_no}", img_dir)
    if hit:
        return hit
    row = conn.execute("SELECT source_path FROM documents WHERE document_id=?",
                       (document_id,)).fetchone()
    if row is not None and row["source_path"] == SLICE_DOC and page_no == 8:
        return img("slice-p8", img_dir)
    return None


def pages_waiting(conn) -> list[dict]:
    """Every page holding a candidate nobody has decided, busiest first.

    2,312 candidates do not fit on one page and a sitting is not a marathon, so
    the console works one page at a time and this is how it says what is left.
    """
    rows = conn.execute("""
        SELECT c.document_id, c.page_no, d.title, d.source_path,
               SUM(c.review_status = 'unreviewed') AS waiting,
               COUNT(*) AS candidates
          FROM step_candidates c
          JOIN documents d ON d.document_id = c.document_id
         GROUP BY c.document_id, c.page_no
        HAVING waiting > 0
         ORDER BY waiting DESC, c.document_id, c.page_no""").fetchall()
    return [dict(r) for r in rows]


def target_page(conn, document_id=None, page_no=None):
    """`(document_id, page_no)` for this sitting, or None when nothing waits.

    With nothing named it opens on the slice page CLAUDE.md names — page 8 of
    the 2024 Bufftech guide — while anything on it is still undecided. That page
    is the one the step design was worked against and the one whose known traps
    are written down (G69 lists the five rows on it that read like steps and are
    not), so it is the cheapest first sitting. After it, the busiest page.
    """
    if document_id is not None:
        row = conn.execute(
            "SELECT document_id FROM documents WHERE document_id=? OR source_path=?",
            (document_id, document_id)).fetchone()
        if row is None:
            return None
        document_id = row["document_id"]
        if page_no is not None:
            return (document_id, page_no)
        for p in pages_waiting(conn):
            if p["document_id"] == document_id:
                return (document_id, p["page_no"])
        return None
    waiting = pages_waiting(conn)
    if not waiting:
        return None
    for p in waiting:
        if p["source_path"] == SLICE_DOC and p["page_no"] == 8:
            return (p["document_id"], 8)
    return (waiting[0]["document_id"], waiting[0]["page_no"])


def step_rows(conn, document_id, page_no) -> list[dict]:
    """The candidates on one page, in print order, each with the section it
    sits under — a bullet decides differently under `3. Install First Post`
    than under `Gate hardware`, and the section is itself a candidate."""
    rows = [dict(r) for r in conn.execute("""
        SELECT * FROM step_candidates
         WHERE document_id=? AND page_no=?
         ORDER BY ordinal, seq""", (document_id, page_no))]
    section = ""
    for r in rows:
        r["section"] = section
        if r["segment_kind"] == "section":
            section = _body(r["text_raw"])
            r["section"] = ""
    return rows


def _body(text: str) -> str:
    """The instruction without its leader glyph, whitespace collapsed. Display
    only: the decision file carries `text_raw` verbatim, because the echo check
    compares it byte for byte."""
    inner = text[1:] if text[:1] in "•*-" else text
    return " ".join(inner.split())


# ------------------------------------------------------------- the workbench
def _options(name, values, chosen):
    out = [f'<option value="">{e("— " + name + " —")}</option>']
    for v in values:
        mark = " selected" if v == chosen else ""
        out.append(f'<option value="{e(v)}"{mark}>{e(v)}</option>')
    return "".join(out)


def _slot_options(chosen):
    """The presets, plus whatever a proposer actually wrote.

    `step_proposals` writes `{"part": "hole", "target": "Footing"}` while this
    module's presets and `knowledge-datamodel.md` §3.6 tag the variant with
    `kind`. Nothing validates `SlotTarget`'s variants, so the two shapes coexist
    in the store today. The console neither picks a winner nor drops the
    proposal: it offers it verbatim, marked as a proposal, so a reviewer
    confirms exactly what a reader wrote.
    """
    out, matched = [], False
    canon = None
    if chosen:
        try:
            canon = json.dumps(json.loads(chosen), sort_keys=True,
                               separators=(",", ":"))
        except (TypeError, ValueError):
            canon = None
    for value, label in SLOT_PRESETS:
        same = bool(value) and canon is not None and canon == json.dumps(
            json.loads(value), sort_keys=True, separators=(",", ":"))
        matched = matched or same
        out.append(f'<option value="{e(value)}"{" selected" if same else ""}>'
                   f'{e(label)}</option>')
    if chosen and not matched:
        out.append(f'<option value="{e(chosen)}" selected>proposed: '
                   f'{e(chosen)}</option>')
    return "".join(out)


def _readers(proposal_basis) -> str:
    """How much a machine proposal is worth, in the one unit that matters here.

    Two readers agreeing is NOT a review: machine agreement laundered into
    curation level 2 is what A1/CUR-S0 revoked 324 facts over. So the count is
    shown beside the proposal rather than used to pre-decide anything.
    """
    if not proposal_basis:
        return ""
    _, _, blob = (proposal_basis or "").partition(":")
    try:
        basis = json.loads(blob)
    except (TypeError, ValueError):
        return ""
    n = len(basis.get("readers") or [])
    if not n:
        return ""
    return f"{n} reader{'s' if n != 1 else ''}, no review"


def step_workbench(conn, *, document_id, page_no, image=None) -> str:
    """One page of candidates beside the page image, with a control per row.

    The reviewer must be able to see the sentence and the page it came from at
    the same time: `segment_kind` says a line READS like an instruction, and
    whether it IS an `AssemblyStep` — rather than an ordering permission, a
    rationale, a cross-reference or a dimension — is often only decidable from
    the layout around it.
    """
    rows = step_rows(conn, document_id, page_no)
    title = conn.execute("SELECT title, source_path FROM documents WHERE document_id=?",
                         (document_id,)).fetchone()
    doc_title = (title["title"] or title["source_path"]) if title else document_id
    waiting = sum(1 for r in rows if r["review_status"] == "unreviewed")

    body = []
    for r in rows:
        decided = "" if r["review_status"] == "unreviewed" else r["review_status"]
        repair = ""
        if r["text_repair"]:
            conf = r["repair_confidence"] or "unrated"
            repair = (f'<div class="repair">proposed repair: '
                      f'<b>{e(r["text_repair"])}</b> '
                      f'<span class="conf {e(conf)}">{e(conf)}</span></div>')
        section = (f'<div class="under">under {e(r["section"])}</div>'
                   if r["section"] else "")
        proposal = ""
        if r["proposed_kind"] or r["proposed_scope"] or r["proposed_slot"]:
            who = _readers(r["proposal_basis"])
            proposal = (f'<span class="proposed">machine proposal: '
                        f'{e(r["proposed_kind"] or "?")} · '
                        f'{e(r["proposed_scope"] or "?")}'
                        f'{" · " + e(who) if who else ""}</span>')
        body.append(f"""
      <tr class="cand" data-cid="{r['candidate_id']}"
          data-element="{e(r['element_id'])}" data-start="{r['char_start']}"
          data-end="{r['char_end']}" data-text="{e(json.dumps(r['text_raw']))}"
          data-segment="{e(r['segment_kind'])}" data-verdict="{e(decided)}">
        <td class="line"><span class="num">{r['candidate_id']}</span><br>
            <span class="kind k-{e(r['segment_kind'])}">{e(r['segment_kind'])}</span>
            {'<span class="sub">sub</span>' if r['depth'] else ''}</td>
        <td class="txt">{section}{e(_body(r['text_raw']))}{repair}{proposal}</td>
        <td class="act">
          <button class="v a" data-v="accepted" title="a — this is a step">step</button>
          <button class="v c" data-v="corrected" title="c — a step, with the text fixed">fix</button>
          <button class="v r" data-v="rejected" title="x — not a step">no</button>
        </td>
        <td><select name="kind">{_options("kind", STEP_KINDS, r['proposed_kind'])}</select></td>
        <td><select name="scope">{_options("scope", STEP_SCOPES, r['proposed_scope'])}</select></td>
        <td><select name="slot">{_slot_options(r['proposed_slot'])}</select></td>
      </tr>""")

    if image:
        # Linked as well as shown: 90 dpi beside a table of 71 rows is small,
        # and a reviewer squinting at a bullet is a reviewer who guesses. The
        # link opens the same bytes full size.
        pane = (f'<a href="{image}" target="_blank" rel="noopener">'
                f'<img src="{image}" alt="page {page_no} of {e(doc_title)}"></a>'
                f'<p class="lede" style="margin:6px 0 0;font-size:12px">'
                f'Click the page to open it full size.</p>')
    else:
        pane = ('<div class="missing-img">No page image for this page yet. '
                'Render it with<br><code>python3 scripts/render_console_images.py</code>'
                '<br>A reviewer who cannot see the page cannot decide whether a '
                'bullet is a step.</div>')

    return f"""
<section>
  <h2>1 &nbsp;Step workbench <span class="tag">{waiting} of {len(rows)} undecided
  &middot; procedures publish nothing until you decide</span></h2>
  <p class="lede"><b>{e(doc_title)}</b>, page {page_no}. Each row is one line the
  splitter cut. <code>segment_kind</code> is <i>structural</i> &mdash; it says
  what kind of line this is, not that it is an <code>AssemblyStep</code>.
  Deciding that, and its <code>kind</code> and <code>scope</code>, is the
  judgement being asked for; nothing here writes to the store.</p>

  <div class="bar">
    <label>your name
      <input id="who" placeholder="the name that goes on every decision"></label>
    <label>default kind <select id="dk">{_options("kind", STEP_KINDS, None)}</select></label>
    <label>default scope <select id="ds">{_options("scope", STEP_SCOPES, None)}</select></label>
    <button id="bulk-sections">reject every section &amp; footnote</button>
    <button id="bulk-fill">fill blank kind/scope on accepted rows</button>
    <button id="reset">clear this page</button>
    <span class="count" id="count"></span>
  </div>

  <div class="split">
    <div class="panel tablewrap">
      <table><thead><tr>
        <th>line</th><th>text</th><th>is it a step?</th>
        <th>kind</th><th>scope</th><th>slot</th>
      </tr></thead>
      <tbody id="steps">{"".join(body)}</tbody></table>
    </div>
    <div class="sticky">
      {pane}
      <p class="lede" style="margin-top:10px;font-size:13px">The page every row on
      the left was cut from. Keyboard: <code>j</code>/<code>k</code> move,
      <code>a</code> step, <code>c</code> fix text, <code>x</code> not a step.</p>
    </div>
  </div>

  <div class="out">
    <h3>Your decisions</h3>
    <p class="lede">This page has no server behind it. Copy the lines below into a
    file and apply them &mdash; the batch is recorded whole or not at all, and one
    bad row refuses all of it rather than leaving you unsure which landed. Then
    export the ledger: a person's judgement is the one thing here that does not
    regenerate, and the build fails if a recorded review is not in it.</p>
    <pre class="cmd" id="cmd"></pre>
    <textarea id="jsonl" readonly spellcheck="false"></textarea>
    <div class="bar">
      <button id="copy">copy the decisions</button>
      <button id="save">download step-decisions.jsonl</button>
      <span class="count" id="count2"></span>
    </div>
  </div>
</section>"""


def pages_table(conn, current) -> str:
    """What the sitting has not reached yet, and the command for each page."""
    rows = pages_waiting(conn)
    if not rows:
        return ('<section><h2>2 &nbsp;Other pages waiting</h2>'
                '<p class="lede">None: every step candidate in the store has been '
                'decided.</p></section>')
    body = []
    for p in rows[:60]:
        here = (p["document_id"], p["page_no"]) == current
        body.append(f"""
      <tr class="{'here' if here else ''}">
        <td class="num">{p['waiting']}</td>
        <td>{e(p['title'] or p['source_path'])}</td>
        <td class="num">p{p['page_no']}</td>
        <td><code>build_review_console.py --document {e(p['document_id'])}
            --page {p['page_no']}</code></td>
      </tr>""")
    total = sum(p["waiting"] for p in rows)
    return f"""
<section>
  <h2>2 &nbsp;Other pages waiting <span class="tag">{total} candidates across
  {len(rows)} pages</span></h2>
  <p class="lede">One page is one sitting. This is what the rest of the queue
  holds; the command rebuilds this console against any of them.</p>
  <div class="panel tablewrap" style="max-height:44vh">
    <table><thead><tr><th>undecided</th><th>document</th><th>page</th>
    <th>build it</th></tr></thead><tbody>{"".join(body)}</tbody></table>
  </div>
</section>"""


def crops_section(conn, img_dir=None) -> str:
    """The table-review queue, unchanged: a page a reader proposed values from
    with nobody's judgement on it yet."""
    crops = conn.execute("""
        SELECT t.crop_path, COUNT(*) rows_waiting, d.title, d.source_path, t.page_no
          FROM table_read_candidates t
          JOIN documents d ON d.document_id = t.document_id
         WHERE t.review_status = 'unreviewed'
         GROUP BY t.crop_path ORDER BY rows_waiting DESC, d.title""").fetchall()
    reviewed = conn.execute(
        "SELECT COUNT(DISTINCT crop_sha256) FROM table_reviews").fetchone()[0]
    cards = []
    for c in crops:
        key = c["crop_path"].rsplit("/", 1)[-1].split("-")[0]
        src = img(f"crop-{key}", img_dir)
        cards.append(f"""
      <figure class="crop">
        {'<img loading="lazy" src="' + src + '" alt="page image">' if src
         else '<div class="missing">image not rendered</div>'}
        <figcaption>
          <b>{c['rows_waiting']} row{'s' if c['rows_waiting'] != 1 else ''} waiting</b><br>
          {e(c['title'] or c['source_path'])}<br>
          <span class="span">p{c['page_no']} &middot; crop {e(key)}</span>
        </figcaption>
      </figure>""")
    return f"""
<section>
  <h2>3 &nbsp;Table crops awaiting review <span class="tag">{len(crops)} of
  {len(crops) + reviewed} pages</span></h2>
  <p class="lede">Each is a page a reader proposed table values from, with nobody's
  judgement on it yet. Reviewing one is what lets its values become a published
  <code>ParameterTable</code>; until then they publish nothing at all.</p>
  <div class="grid">{"".join(cards)}</div>
</section>"""


def footing_schedules(snap, img_dir=None) -> str:
    """G79, carried over unchanged: five published `footing_schedule` tables,
    four of which restrict exposure B to non-HVHZ while the fifth claims full
    coverage. It is still open, and dropping it from the console because a new
    section arrived would quietly retire a decision nobody made."""
    tables = [t for t in (snap or {}).get("parameters", [])
              if t.get("parameter") == "footing_schedule"]
    if not tables:
        return ""
    body = []
    for t in tables:
        scope = (t.get("scope") or {}).get("id", "")
        unc = t.get("uncovered") or []
        body.append(f"""
      <tr class="{'disputed' if not unc else ''}">
        <td class="txt"><code>{e(str(scope))}</code></td>
        <td class="num">{len(t.get('rows') or [])}</td>
        <td>{e(json.dumps([r.get('conditions') for r in t.get('rows') or []]))}</td>
        <td>{'<b class="bad">none — claims full coverage</b>' if not unc
             else e(json.dumps(unc))}</td>
      </tr>""")
    a, b = img("g79-disputed", img_dir), img("g79-sibling", img_dir)
    return f"""
<section>
  <h2>4 &nbsp;One decision that needs your eyes <span class="tag">G79</span></h2>
  <p class="lede">Five <code>footing_schedule</code> tables publish. Four restrict
  exposure B to non-HVHZ. The fifth claims full coverage &mdash; so its B values
  present as valid under HVHZ, where its siblings say they are not.</p>
  <div class="panel tablewrap" style="max-height:none">
    <table><thead><tr><th>scope</th><th>rows</th><th>published conditions</th>
    <th>uncovered</th></tr></thead><tbody>{"".join(body)}</tbody></table>
  </div>
  <div class="pair">
    <figure>{'<img src="' + a + '" alt="the disputed NOA page">' if a else ''}
      <figcaption><b>Disputed</b> &mdash; NOA 12-1106.11 p11. Reviewed as printing
      no HVHZ bracket, which is why its table claims full coverage.</figcaption>
    </figure>
    <figure>{'<img src="' + b + '" alt="a sibling NOA page">' if b else ''}
      <figcaption><b>Sibling</b> &mdash; NOA 23-0314.05 p17. Same template; its
      bracket was read as <code>NON HVHZ</code> for B and
      <code>HVHZ AND NON HVHZ</code> for C and D.</figcaption>
    </figure>
  </div>
</section>"""


def _stats(conn, snap, waiting_here, waiting_all) -> str:
    state = {k: len(v) for k, v in (snap or {}).items() if isinstance(v, list)}
    cells = [("source docs published", state.get("source_docs", 0), ""),
             ("parameter tables", state.get("parameters", 0), ""),
             ("parts", state.get("parts", 0), ""),
             ("procedures published", state.get("procedures", 0),
              "act" if not state.get("procedures") else ""),
             ("step reviews ever recorded",
              conn.execute("SELECT COUNT(*) FROM step_reviews").fetchone()[0]
              if _has(conn, "step_reviews") else 0, "act"),
             ("undecided on this page", waiting_here, "act"),
             ("undecided in the store", waiting_all, "act")]
    if snap is None:
        cells = cells[3:]
    return "".join(
        f'<div class="stat {cls}"><div class="v">{v}</div>'
        f'<div class="l">{e(label)}</div></div>' for label, v, cls in cells)


def _has(conn, table) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (table,)).fetchone() is not None


def build_console(conn, snap=None, *, img_dir=None, document_id=None,
                  page_no=None, snapshot_name="") -> str:
    """The whole page. `snap` is a published snapshot payload, or None — a store
    that has published nothing is exactly the state a first sitting starts from,
    and the console must render there."""
    target = target_page(conn, document_id, page_no)
    waiting = pages_waiting(conn)
    waiting_all = sum(p["waiting"] for p in waiting)
    if target is None:
        workbench = ('<section><h2>1 &nbsp;Step workbench</h2><p class="lede">'
                     'No step candidate is waiting for a decision. Propose some '
                     'with <code>cli steps --propose --document PATH</code>.'
                     '</p></section>')
        here = 0
    else:
        doc, page = target
        workbench = step_workbench(conn, document_id=doc, page_no=page,
                                   image=page_image(conn, doc, page, img_dir))
        here = next((p["waiting"] for p in waiting
                     if (p["document_id"], p["page_no"]) == target), 0)

    crops = crops_section(conn, img_dir) if _has(conn, "table_read_candidates") else ""
    schedules = footing_schedules(snap, img_dir)
    source = (f"snapshot <code>{e(snapshot_name)}</code> and " if snapshot_name else "")
    # The charset is not decoration: the page carries em-dashes, bullet glyphs
    # and ¾ marks straight out of the corpus, and a file opened from disk or
    # served by a plain static server gets no charset header at all. Without it
    # the reviewer reads mojibake in the one column they are judging.
    return f"""<meta charset="utf-8">
<title>Fence Review Console</title>
<style>{CSS}</style>
<div class="wrap">
<header>
  <h1>Fence Review Console</h1>
  <p class="sub-h">Generated from {source}<code>evidence.db</code>. Every value
  below is read from the store, not transcribed &mdash; if a number here is
  wrong, the store is wrong. <b>Nothing on this page writes to the store</b>:
  section 1 produces a decision file that one command records.</p>
  <div class="stats">{_stats(conn, snap, here, waiting_all)}</div>
</header>
{workbench}
{pages_table(conn, target)}
{crops}
{schedules}
<footer>
  Generated from <code>workspace/indexes/evidence.db</code>. Page images rendered
  from the source PDFs at 90&nbsp;dpi. This console shows the current state,
  defects included &mdash; it makes the work inspectable, not correct.
</footer>
</div>
<script>{JS}</script>
"""


CSS = """
:root {
  --bg:#eef1f4; --panel:#fff; --panel-2:#f6f8fa; --ink:#141b22; --soft:#4d5b6b;
  --faint:#7b8a9a; --rule:#d5dde4; --rule-2:#e6ecf1;
  --accent:#0b6ea8; --accent-bg:#e2eef6;
  --warn:#a8600f; --warn-bg:#f8eddc;
  --bad:#9c3535; --bad-bg:#f7e4e4;
  --ok:#1c6b52; --ok-bg:#e0efe9;
  --mono:ui-monospace,Menlo,Consolas,monospace;
  --sans:ui-sans-serif,system-ui,-apple-system,sans-serif;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg:#0d1319; --panel:#151d25; --panel-2:#1b242e; --ink:#e3eaf1; --soft:#a4b2c0;
  --faint:#74838f; --rule:#28323d; --rule-2:#1f2831;
  --accent:#5aa9db; --accent-bg:#12293a;
  --warn:#dd9a45; --warn-bg:#2e2415;
  --bad:#dc7d7d; --bad-bg:#2e1a1a;
  --ok:#57bd97; --ok-bg:#12291f;
} }
:root[data-theme="dark"] {
  --bg:#0d1319; --panel:#151d25; --panel-2:#1b242e; --ink:#e3eaf1; --soft:#a4b2c0;
  --faint:#74838f; --rule:#28323d; --rule-2:#1f2831;
  --accent:#5aa9db; --accent-bg:#12293a;
  --warn:#dd9a45; --warn-bg:#2e2415;
  --bad:#dc7d7d; --bad-bg:#2e1a1a;
  --ok:#57bd97; --ok-bg:#12291f;
}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:15px;
 line-height:1.5;margin:0;padding:0 20px 80px;-webkit-font-smoothing:antialiased}
.wrap{max-width:1500px;margin:0 auto}
header{padding:36px 0 20px}
h1{font-size:1.9rem;font-weight:700;letter-spacing:-.02em;margin:0 0 6px}
h3{font-size:1rem;margin:0 0 4px}
.sub-h{color:var(--soft);margin:0 0 22px;max-width:74ch}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(126px,1fr));gap:1px;
 background:var(--rule);border:1px solid var(--rule);border-radius:6px;overflow:hidden}
.stat{background:var(--panel);padding:13px 15px}
.stat .v{font-size:1.5rem;font-weight:600;font-variant-numeric:tabular-nums;line-height:1.1}
.stat .l{font-size:11.5px;color:var(--faint);margin-top:3px;line-height:1.3}
.stat.act .v{color:var(--warn)}
section{margin-top:40px}
h2{font-size:1.3rem;font-weight:600;letter-spacing:-.01em;margin:0 0 4px;
 display:flex;align-items:baseline;gap:11px;flex-wrap:wrap}
h2 .tag{font-family:var(--mono);font-size:11px;font-weight:500;padding:3px 8px;
 border-radius:4px;background:var(--warn-bg);color:var(--warn);letter-spacing:.03em}
.lede{color:var(--soft);margin:0 0 16px;max-width:82ch}
.panel{background:var(--panel);border:1px solid var(--rule);border-radius:6px;overflow:hidden}
.split{display:grid;grid-template-columns:minmax(0,1.75fr) minmax(0,1fr);gap:18px;
 align-items:start}
@media(max-width:1000px){.split{grid-template-columns:1fr}}
.sticky{position:sticky;top:16px}
.sticky img{width:100%;height:auto;display:block;border:1px solid var(--rule);
 border-radius:6px;background:#fff}
.missing-img{border:1px dashed var(--rule);border-radius:6px;padding:22px;
 color:var(--warn);background:var(--warn-bg);font-size:13px;line-height:1.6}
.tablewrap{overflow:auto;max-height:80vh}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th{position:sticky;top:0;background:var(--panel-2);text-align:left;font-size:11px;
 letter-spacing:.06em;text-transform:uppercase;color:var(--faint);font-weight:600;
 padding:9px 11px;border-bottom:1px solid var(--rule);z-index:2}
td{padding:7px 7px;border-bottom:1px solid var(--rule-2);vertical-align:top}
tbody tr:hover{background:var(--panel-2)}
tr.here{background:var(--accent-bg)}
tr.cand[data-verdict="accepted"]{background:var(--ok-bg)}
tr.cand[data-verdict="corrected"]{background:var(--accent-bg)}
tr.cand[data-verdict="rejected"]{opacity:.5}
tr.cand.on{outline:2px solid var(--accent);outline-offset:-2px}
.num{font-family:var(--mono);color:var(--faint);font-variant-numeric:tabular-nums;
 text-align:right;width:46px}
.txt{line-height:1.45;min-width:20ch}
.line{white-space:nowrap;width:1%}
.under{font-size:11px;color:var(--faint);text-transform:uppercase;letter-spacing:.04em}
.kind{display:inline-block;font-size:10.5px;font-weight:600;letter-spacing:.04em;
 text-transform:uppercase;padding:2px 7px;border-radius:3px;background:var(--panel-2);
 color:var(--soft);white-space:nowrap}
.kind.k-step{background:var(--accent-bg);color:var(--accent)}
.kind.k-prohibition{background:var(--bad-bg);color:var(--bad)}
.kind.k-note{background:var(--warn-bg);color:var(--warn)}
.kind.k-branch{background:var(--ok-bg);color:var(--ok)}
.sub{font-size:10px;color:var(--faint);margin-left:5px}
.repair{margin-top:4px;font-size:12.5px;color:var(--soft)}
.repair b{color:var(--ink);font-weight:500}
.proposed{display:inline-block;margin-top:4px;font-family:var(--mono);font-size:10.5px;
 color:var(--accent)}
.conf{font-family:var(--mono);font-size:10px;padding:1px 5px;border-radius:3px}
.conf.high{background:var(--ok-bg);color:var(--ok)}
.conf.low{background:var(--warn-bg);color:var(--warn)}
.fix{width:100%;margin-top:5px;font-family:var(--sans);font-size:12.5px;
 border:1px solid var(--rule);border-radius:4px;padding:5px;background:var(--panel-2);
 color:var(--ink)}
.act{white-space:nowrap}
button{font-family:var(--sans);font-size:12px;font-weight:500;padding:5px 8px;
 border:1px solid var(--rule);background:var(--panel);color:var(--soft);
 border-radius:5px;cursor:pointer}
button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.v{margin-right:3px}
tr.cand[data-verdict="accepted"] .v.a,
tr.cand[data-verdict="corrected"] .v.c{background:var(--ok);border-color:var(--ok);color:#fff}
tr.cand[data-verdict="rejected"] .v.r{background:var(--bad);border-color:var(--bad);color:#fff}
select{font-family:var(--sans);font-size:12px;padding:3px;border:1px solid var(--rule);
 border-radius:4px;background:var(--panel);color:var(--ink);max-width:13ch}
td select{width:100%;max-width:15ch}
.bar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:0 0 12px}
.bar label{font-size:12px;color:var(--faint);display:flex;gap:6px;align-items:center}
.bar input{font-family:var(--sans);font-size:13px;padding:5px 8px;border-radius:5px;
 border:1px solid var(--rule);background:var(--panel);color:var(--ink);min-width:24ch}
.count{font-family:var(--mono);font-size:12px;color:var(--warn)}
.out{margin-top:22px;background:var(--panel);border:1px solid var(--rule);
 border-radius:6px;padding:16px 18px}
.cmd{font-family:var(--mono);font-size:12px;background:var(--panel-2);border-radius:5px;
 padding:10px 12px;overflow:auto;white-space:pre-wrap;color:var(--ink);margin:0 0 10px}
textarea{width:100%;height:150px;font-family:var(--mono);font-size:11.5px;
 border:1px solid var(--rule);border-radius:5px;padding:9px;background:var(--panel-2);
 color:var(--ink);resize:vertical}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:15px}
figure.crop{margin:0;background:var(--panel);border:1px solid var(--rule);border-radius:6px;
 overflow:hidden;display:flex;flex-direction:column}
figure.crop img{width:100%;height:200px;object-fit:cover;object-position:top;
 display:block;background:#fff;border-bottom:1px solid var(--rule)}
figure.crop figcaption{padding:10px 12px;font-size:12px;line-height:1.4;color:var(--soft)}
figure.crop b{color:var(--warn)}
.missing{height:200px;display:grid;place-items:center;color:var(--faint);font-size:12px}
.span{font-family:var(--mono);font-size:10.5px;color:var(--faint)}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}
@media(max-width:900px){.pair{grid-template-columns:1fr}}
.pair figure{margin:0}
.pair img{width:100%;border:1px solid var(--rule);border-radius:6px;background:#fff}
.pair figcaption{font-size:12.5px;color:var(--soft);margin-top:8px}
tr.disputed{background:var(--bad-bg)}
.bad{color:var(--bad)}
code{font-family:var(--mono);font-size:.86em}
footer{margin-top:52px;padding-top:20px;border-top:1px solid var(--rule);
 font-size:12.5px;color:var(--faint)}
"""

# The whole interaction. No framework and no server: the page holds the sitting
# in memory (and in localStorage, so an interrupted one survives a reload), and
# hands back a JSONL file that `cli review --apply-steps` records.
JS = r"""
(function () {
  var tbody = document.getElementById('steps');
  if (!tbody) return;
  var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr.cand'));
  var who = document.getElementById('who');
  var dk = document.getElementById('dk'), ds = document.getElementById('ds');
  var jsonl = document.getElementById('jsonl'), cmd = document.getElementById('cmd');
  var key = 'fence-steps:' + location.pathname + ':' + (rows[0] ?
            rows[0].dataset.element : '');
  var cur = 0;

  function sel(r, name) { return r.querySelector('select[name="' + name + '"]'); }

  function fixBox(r, make) {
    var box = r.querySelector('textarea.fix');
    if (make && !box) {
      box = document.createElement('textarea');
      box.className = 'fix';
      box.rows = 2;
      box.value = r.querySelector('.txt').textContent.trim();
      r.querySelector('.txt').appendChild(box);
      box.addEventListener('input', emit);
    }
    if (!make && box) box.remove();
    return box;
  }

  function setVerdict(r, v) {
    r.dataset.verdict = (r.dataset.verdict === v) ? '' : v;
    var on = r.dataset.verdict;
    if (on === 'accepted' || on === 'corrected') {
      if (!sel(r, 'kind').value) sel(r, 'kind').value = dk.value;
      if (!sel(r, 'scope').value) sel(r, 'scope').value = ds.value;
    }
    fixBox(r, on === 'corrected');
    emit();
  }

  function decision(r) {
    var v = r.dataset.verdict;
    if (!v) return null;
    var d = {candidate_id: Number(r.dataset.cid),
             element_id: r.dataset.element,
             char_start: Number(r.dataset.start),
             char_end: Number(r.dataset.end),
             text_seen: JSON.parse(r.dataset.text),
             verdict: v};
    if (who.value.trim()) d.reviewer = who.value.trim();
    if (v !== 'rejected') {
      d.step_kind = sel(r, 'kind').value || null;
      d.step_scope = sel(r, 'scope').value || null;
      var slot = sel(r, 'slot').value;
      if (slot) d.slot_target = JSON.parse(slot);
      var box = r.querySelector('textarea.fix');
      if (v === 'corrected' && box && box.value.trim()) d.text_final = box.value.trim();
    }
    return d;
  }

  function emit() {
    var lines = [], done = 0, incomplete = 0;
    rows.forEach(function (r) {
      var d = decision(r);
      if (!d) return;
      done++;
      if (d.verdict !== 'rejected' && (!d.step_kind || !d.step_scope)) incomplete++;
      lines.push(JSON.stringify(d));
    });
    jsonl.value = lines.join('\n') + (lines.length ? '\n' : '');
    var name = who.value.trim() || 'YOUR NAME';
    cmd.textContent =
      'python3 -m fence_evidence.cli review --apply-steps step-decisions.jsonl \\\n' +
      '    --reviewer "' + name + '" --apply\n' +
      '# then, because a review is the one thing here that does not regenerate:\n' +
      'python3 -m fence_evidence.cli review --export';
    var note = done + ' of ' + rows.length + ' decided here, none recorded yet';
    if (incomplete) note += ' · ' + incomplete +
      ' accepted without a kind or scope — the batch will be refused';
    if (!who.value.trim() && done) note += ' · put your name in';
    document.getElementById('count').textContent = note;
    document.getElementById('count2').textContent = note;
    try {
      localStorage.setItem(key, JSON.stringify({who: who.value, lines: rows.map(
        function (r) {
          return [r.dataset.verdict, sel(r, 'kind').value, sel(r, 'scope').value,
                  sel(r, 'slot').value,
                  (r.querySelector('textarea.fix') || {}).value || ''];
        })}));
    } catch (err) { /* a private window has no storage; the sitting still works */ }
  }

  function restore() {
    var saved;
    try { saved = JSON.parse(localStorage.getItem(key) || 'null'); }
    catch (err) { saved = null; }
    if (!saved || !saved.lines || saved.lines.length !== rows.length) return;
    who.value = saved.who || '';
    rows.forEach(function (r, i) {
      var s = saved.lines[i];
      if (!s) return;
      r.dataset.verdict = s[0] || r.dataset.verdict;
      sel(r, 'kind').value = s[1] || sel(r, 'kind').value;
      sel(r, 'scope').value = s[2] || sel(r, 'scope').value;
      sel(r, 'slot').value = s[3] || sel(r, 'slot').value;
      var box = fixBox(r, r.dataset.verdict === 'corrected');
      if (box && s[4]) box.value = s[4];
    });
  }

  tbody.addEventListener('click', function (ev) {
    var b = ev.target.closest('button.v');
    var r = ev.target.closest('tr.cand');
    if (r) focus(rows.indexOf(r));
    if (b && r) setVerdict(r, b.dataset.v);
  });
  tbody.addEventListener('change', emit);
  who.addEventListener('input', emit);

  function focus(i) {
    if (i < 0 || i >= rows.length) return;
    rows.forEach(function (r) { r.classList.remove('on'); });
    cur = i;
    rows[i].classList.add('on');
    rows[i].scrollIntoView({block: 'nearest'});
  }

  document.addEventListener('keydown', function (ev) {
    if (/^(INPUT|TEXTAREA|SELECT)$/.test(ev.target.tagName)) return;
    if (ev.key === 'j') { focus(cur + 1); ev.preventDefault(); }
    else if (ev.key === 'k') { focus(cur - 1); ev.preventDefault(); }
    else if (ev.key === 'a') { setVerdict(rows[cur], 'accepted'); focus(cur + 1); }
    else if (ev.key === 'c') { setVerdict(rows[cur], 'corrected'); }
    else if (ev.key === 'x') { setVerdict(rows[cur], 'rejected'); focus(cur + 1); }
  });

  document.getElementById('bulk-sections').addEventListener('click', function () {
    rows.forEach(function (r) {
      if (!r.dataset.verdict &&
          (r.dataset.segment === 'section' || r.dataset.segment === 'footnote')) {
        r.dataset.verdict = 'rejected';
      }
    });
    emit();
  });
  document.getElementById('bulk-fill').addEventListener('click', function () {
    rows.forEach(function (r) {
      if (r.dataset.verdict !== 'accepted' && r.dataset.verdict !== 'corrected') return;
      if (!sel(r, 'kind').value) sel(r, 'kind').value = dk.value;
      if (!sel(r, 'scope').value) sel(r, 'scope').value = ds.value;
    });
    emit();
  });
  document.getElementById('reset').addEventListener('click', function () {
    rows.forEach(function (r) { r.dataset.verdict = ''; fixBox(r, false); });
    emit();
  });
  document.getElementById('copy').addEventListener('click', function () {
    jsonl.select();
    try { navigator.clipboard.writeText(jsonl.value); } catch (err) {
      document.execCommand('copy');
    }
  });
  document.getElementById('save').addEventListener('click', function () {
    var blob = new Blob([jsonl.value], {type: 'application/x-ndjson'});
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'step-decisions.jsonl';
    a.click();
  });

  restore();
  emit();
  focus(0);
})();
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("img", nargs="?", default=None,
                    help="directory of rendered page images")
    ap.add_argument("out", nargs="?", default=None, help="the HTML to write")
    ap.add_argument("--document", help="document_id or source_path to review")
    ap.add_argument("--page", type=int, help="the page to review")
    ap.add_argument("--db", default=None)
    args = ap.parse_args(argv)

    img_dir = pathlib.Path(args.img) if args.img else DEFAULT_IMG
    out = pathlib.Path(args.out) if args.out else DEFAULT_OUT
    conn = connect(args.db)

    snap, name = None, ""
    snaps = sorted((ROOT / "workspace/snapshots").glob("*.json"),
                   key=lambda p: p.stat().st_mtime) if (
        ROOT / "workspace/snapshots").is_dir() else []
    if snaps:
        snap = json.loads(snaps[-1].read_text())
        name = snaps[-1].stem[:12]

    doc = build_console(conn, snap, img_dir=img_dir, document_id=args.document,
                        page_no=args.page, snapshot_name=name)
    with open_write(out) as f:
        f.write(doc)
    target = target_page(conn, args.document, args.page)
    print(f"wrote {out} ({out.stat().st_size / 1024 / 1024:.2f} MB)")
    print(f"  workbench: {target}  "
          f"undecided in store: {sum(p['waiting'] for p in pages_waiting(conn))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
