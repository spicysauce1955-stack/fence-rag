"""`Procedure` and `AssemblyStep` — the snapshot member, built from reviewed steps.

Declared in the payload since the contract was signed and empty ever since.
This fills it, under one rule: **a step candidate with no reviewer publishes
nothing, ever.** That is A1/C0 applied to a new seam — machine agreement was
once laundered into curation level 2 and 324 facts had to be un-promoted, and
the whole architecture here exists so that cannot happen again.

What is mechanical and what is judgement, kept apart:

* the TEXT is verbatim from a cited element, and the citation is exact;
* the KIND, SCOPE and SLOT are a person's decision, read from `step_reviews`
  and published only where one exists.

`AssemblyStep.kind` and `scope` are required by the shape, so a candidate
without a review cannot be published even in part. That is why an unreviewed
page produces a `Gap` rather than a partial `Procedure`: a half-classified step
would be this platform asserting something nobody decided.

A step cites its PAGE, not its element. The reviewed evidence is the page image
a person looked at, and the same reasoning that produced `source_ref_page` in
G73 applies here: the citation should name what was actually examined.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3

from .refs import ref_id

# Only these publish. `rejected` is a decision too -- it means a person looked
# and said no -- and it publishes nothing, which is the point.
PUBLISHABLE = ("accepted", "corrected")


def _default_source_ref_page(conn: sqlite3.Connection):
    """Standalone minter, so this module is testable without a builder.

    The integrator passes `SnapshotBuilder.source_ref_page`, which registers the
    document as a side effect and so keeps §1.2.1's closure rule structural
    rather than merely checked.
    """
    def mint(document_id: str, page_no: int) -> dict:
        row = conn.execute(
            """SELECT v.sha256 FROM pages p
                 JOIN document_versions v ON v.version_id = p.version_id
                WHERE v.document_id = ? AND p.page_no = ?""",
            (document_id, page_no)).fetchone()
        if row is None:
            raise KeyError(f"no such page: {document_id} p{page_no}")
        return {"id": ref_id(row["sha256"], page_no, None),
                "belongs_to": row["sha256"]}
    return mint


def _procedure_id(document_id: str, page_no: int) -> str:
    """Stable across revisions, which N13 says is load-bearing: without it
    `Warning.attaches_to{kind: procedure}` cannot address one, and a correction
    to one copy of a repeated procedure reaches none of the others."""
    return "proc-" + hashlib.sha256(
        f"{document_id}:{page_no}".encode()).hexdigest()[:12]


def _step_key(element_id: str, char_start: int, char_end: int) -> str:
    """Derived from the evidence, so it is the same key on every rebuild."""
    return "step-" + hashlib.sha256(
        f"{element_id}:{char_start}:{char_end}".encode()).hexdigest()[:12]


def build_procedures(conn: sqlite3.Connection, *, source_ref_page=None,
                     tenant: str | None = None) -> tuple[list[dict], list[dict]]:
    """`(procedures, gaps)`, both plain dicts ready for the wire."""
    from .parameters import _Gaps
    mint = source_ref_page or _default_source_ref_page(conn)
    gaps = _Gaps()

    # Explicitly: does this store have the tables at all? An older store has
    # neither and correctly publishes nothing. What must NOT happen is catching
    # `sqlite3.Error` around the query and treating every failure as "no data" --
    # the first version did exactly that, `step_reviews` was missing from the
    # live store, and the member silently published nothing while reporting
    # success. A swallowed error is the defect this codebase keeps finding.
    have = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    if not {"step_candidates", "step_reviews"} <= have:
        return [], []

    rows = conn.execute("""
            SELECT c.candidate_id, c.document_id, c.page_no, c.element_id,
                   c.ordinal, c.seq, c.char_start, c.char_end, c.text_raw,
                   c.segment_kind, c.review_status, d.title,
                   r.step_kind, r.step_scope, r.slot_target, r.text_final,
                   r.verdict
              FROM step_candidates c
              JOIN documents d ON d.document_id = c.document_id
              LEFT JOIN step_reviews r
                ON r.element_id = c.element_id
               AND r.char_start = c.char_start
               AND r.char_end = c.char_end
             ORDER BY c.document_id, c.page_no, c.ordinal, c.seq""").fetchall()

    by_page: dict[tuple, list] = {}
    waiting: dict[tuple, int] = {}
    titles: dict[tuple, str] = {}
    for r in rows:
        page = (r["document_id"], r["page_no"])
        titles[page] = r["title"] or r["document_id"]
        if r["review_status"] in PUBLISHABLE and r["step_kind"] and r["step_scope"]:
            by_page.setdefault(page, []).append(r)
        elif r["review_status"] == "unreviewed":
            waiting[page] = waiting.get(page, 0) + 1

    out: list[dict] = []
    for page in sorted(by_page):
        document_id, page_no = page
        try:
            cite = mint(document_id, page_no)
        except KeyError:
            continue
        steps = []
        previous = None
        for r in by_page[page]:
            key = _step_key(r["element_id"], r["char_start"], r["char_end"])
            steps.append({
                "key": key,
                "kind": r["step_kind"],
                "scope": r["step_scope"],
                "slots": [json.loads(r["slot_target"])] if r["slot_target"] else [],
                # Order on the page is a STATED order, so `after` is a reading
                # rather than an inference. Anything else -- `not_before`,
                # `exclusive_with` -- is a reviewer's call and is not derived here.
                "requires": ([{"kind": "after", "step": previous}] if previous else []),
                "cites": [cite],
                "text_i18n": r["text_final"] or _body(r["text_raw"]),
            })
            previous = key
        out.append({
            "id": _procedure_id(document_id, page_no),
            # `null` = owned by no product at all, which the shape permits and
            # which is honest: this guide's `FenceModel` does not exist yet, so
            # naming a referent would be inventing one.
            "scope": None,
            "steps": steps,
            "cites": [cite],
        })

    for page in sorted(waiting):
        document_id, page_no = page
        gaps.add(kind="missing_value",
                 subject={"kind": "page", "id": f"{document_id}#p{page_no}",
                          "tenant": tenant},
                 code="steps_awaiting_review",
                 params={"page_no": page_no, "waiting": waiting[page]},
                 would_close=(f"p{page_no} of \"{titles[page]}\": {waiting[page]} step "
                              f"candidates are waiting for a person; until somebody "
                              f"confirms what each line is, none of them publishes"),
                 closes_by="knowledge", severity="informational")
    return out, gaps.list()


def _body(text: str) -> str:
    """The instruction without its leader glyph, whitespace collapsed."""
    inner = text[1:] if text[:1] in "•*-" else text
    return " ".join(inner.split())
