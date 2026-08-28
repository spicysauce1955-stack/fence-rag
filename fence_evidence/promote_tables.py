"""Turn verified table readings into conditioned facts.

A cell is promoted with the conditions of the row it sits in, never on its own.
`36"` in a footing-depth column is not a fact; `footing_depth = 36" when
exposure = C` is. Promoting cells independently is precisely how the curated
dataset lost the applicability of a row.

Applicability that is drawn rather than written — the brace grouping rows under
`NON HVHZ` — is extracted from what readers recorded, and **fails closed**: if
two model families do not independently agree on the grouping, the condition is
recorded as ``unresolved`` and the fact says so. A wrong applicability is worse
than a missing one.
"""
from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict

from .store import connect, now
from .table_review import PROMOTABLE, normalise, reader_family

# column label -> what the value means
VALUE_COLUMNS = {
    r"footing\s*depth": "footing_depth_in",
    r"min\.?\s*footing.*depth": "footing_depth_in",
    r"max\.?\s*post\s*spacing": "post_spacing_in",
    r"min\.?\s*footing.*diameter": "footing_diameter_in",
}
# column label -> the condition it sets for its row
KEY_COLUMNS = {
    r"wind\s*exposure": "exposure_category",
    r"^exposure$": "exposure_category",
    r"fence\s*height": "fence_height",
}
_HVHZ_BOTH = re.compile(r"HVHZ\s+AND\s+NON[\s-]?HVHZ", re.I)
_NON_HVHZ = re.compile(r"NON[\s-]?HVHZ", re.I)


def _match(label: str | None, table: dict) -> str | None:
    if not label:
        return None
    low = label.strip().lower()
    for pattern, name in table.items():
        if re.search(pattern, low):
            return name
    return None


def _inches(value: str | None) -> float | None:
    if not value:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)(?:\s*(\d+)/(\d+))?", value.replace('"', " "))
    if not m:
        return None
    whole = float(m.group(1))
    if m.group(2) and m.group(3):
        try:
            whole += float(m.group(2)) / float(m.group(3))
        except ZeroDivisionError:
            pass
    return round(whole, 4)


def hvhz_for_exposure(notes: str, exposure: str) -> str | None:
    """Which applicability bracket covers this exposure letter, per one reader's note.

    Deliberately narrow. Anything it cannot parse confidently returns None, which
    the caller turns into ``unresolved``.
    """
    if not notes or not exposure:
        return None
    letter = exposure.strip().upper()[:1]
    if letter not in "BCD":
        return None
    verdicts = set()
    for sentence in re.split(r"[;.]", notes):
        if not re.search(rf"\b{letter}\b", sentence):
            continue
        if _HVHZ_BOTH.search(sentence):
            verdicts.add("HVHZ and non-HVHZ")
        elif _NON_HVHZ.search(sentence):
            verdicts.add("non-HVHZ only")
    return verdicts.pop() if len(verdicts) == 1 else None


def _row_applicability(readings: list[sqlite3.Row], exposure: str) -> tuple[str, str]:
    """Cross-family agreement on the bracket, or 'unresolved'."""
    by_family: dict[str, set] = defaultdict(set)
    for r in readings:
        v = hvhz_for_exposure(r["notes"] or "", exposure)
        family = reader_family(r["reader"])
        # `reader_family` fails OPEN: an unmapped reader name returns "unknown".
        # Counting that as a family inverts the guarantee this test exists to
        # make -- "unknown" + "claude-sonnet" reads as two families agreeing when
        # the second one is simply a reader nobody classified, and two unmapped
        # readers of the SAME model would read as one family rather than as an
        # error. table_review.mark_cross_family_verified already excludes it;
        # this path did not. The bracket is the HVHZ applicability, so a false
        # cross-family claim here promotes a footing row into the wrong
        # regulatory regime.
        if v and family != "unknown":
            by_family[family].add(v)
    agreed = {next(iter(v)) for v in by_family.values() if len(v) == 1}
    if len(by_family) >= 2 and len(agreed) == 1:
        return agreed.pop(), "cross-family agreement on the bracket label"
    return "unresolved", ("readers did not independently agree on the applicability "
                          "bracket; see the page crop")


def effective_value(cell) -> str | None:
    """The value a promotion should carry: the person's, where there is one.

    G44. The INSERT below used `cell["value"]` -- the reader's transcription --
    even for a row whose `review_status` is `corrected`, so a reviewer's fix was
    stored in `reviewed_value` and then silently discarded at promotion. The
    published fact carried the machine's number under curation level 2, which
    claims a person checked it. Maximum asserted authority over unreviewed
    content is the worst combination this store can produce, and it is exactly
    what obligation 6 exists to prevent.
    """
    if cell["review_status"] == "corrected" and cell["reviewed_value"] is not None:
        return cell["reviewed_value"]
    return cell["value"]


def one_reading_per_cell(cells: list) -> list:
    """Collapse N readers' readings of one grid position to a single row.

    G43. Promotion grouped by (document, page, row) and then iterated the
    *readings* in that group, so three readers produced three identical facts:
    measured, 36 facts from one reviewed footing crop of which 12 were distinct.
    Three identical rows at one domain point violate `hit_policy: unique` in
    contract.md 1.3 -- on data this platform generated itself, independently of
    the real design-point pairing that candidate amendment C5 is about.

    Choosing one is safe because the readers agree: across 174 independently
    multi-read positions there were 6 value disagreements, every one of them a
    merged-cell artifact rather than a misread number (Phase 2 design 2). A
    `corrected` reading wins regardless, because that is the human verdict, and
    ties break on the lowest candidate_id so the choice is deterministic.
    """
    best: dict[int, object] = {}
    for c in sorted(cells, key=lambda r: r["candidate_id"]):
        col = c["col_index"]
        if col not in best:
            best[col] = c
        elif (c["review_status"] == "corrected"
              and best[col]["review_status"] != "corrected"):
            best[col] = c
    return [best[k] for k in sorted(best)]


def promote_verified(conn: sqlite3.Connection | None = None, *,
                     dry_run: bool = False) -> dict:
    own = conn is None
    conn = conn or connect()
    try:
        rows = conn.execute(f"""
            SELECT * FROM table_read_candidates
             WHERE review_status IN ({','.join('?' * len(PROMOTABLE))})
               AND row_index >= 0
             ORDER BY document_id, page_no, row_index, col_index""",
            PROMOTABLE).fetchall()
        # Already-promoted is a property of the CELL, not of the reading. Only
        # one of a cell's N readings carries the from_candidate_id, so a
        # per-reading NOT IN would re-promote that cell's other N-1 readings on
        # the next run -- turning G43's duplication into a slow leak instead of
        # fixing it. Skip the whole cell when any of its readings is linked.
        promoted = {r[0] for r in conn.execute(
            "SELECT from_candidate_id FROM facts WHERE from_candidate_id IS NOT NULL")}
        by_cell: dict[tuple, list[sqlite3.Row]] = defaultdict(list)
        for r in rows:
            by_cell[(r["document_id"], r["page_no"],
                     r["row_index"], r["col_index"])].append(r)
        groups: dict[tuple, list[sqlite3.Row]] = defaultdict(list)
        for (doc, page, row_i, _col), cell_rows in by_cell.items():
            if any(c["candidate_id"] in promoted for c in cell_rows):
                continue
            groups[(doc, page, row_i)].extend(one_reading_per_cell(cell_rows))

        created = skipped = unresolved = 0
        by_type: dict[str, int] = defaultdict(int)
        for (doc, page, row_i), cells in sorted(groups.items()):
            conditions: dict[str, str] = {}
            for cell in cells:
                key = _match(cell["col_label"], KEY_COLUMNS)
                val = effective_value(cell)
                if key and val and val.strip():
                    conditions[key] = val.strip()
            exposure = conditions.get("exposure_category", "")
            applicability, basis = _row_applicability(cells, exposure)
            if applicability == "unresolved":
                unresolved += 1
            conditions["hvhz_applicability"] = applicability
            # A2. This note used to live in `conditions` under an underscore key,
            # where §1.3 publishes it as a condition dimension -- a sentence about
            # readers disagreeing, dressed as something Planning can bind a plan
            # against. It belongs beside the conditions, not inside them.

            for cell in cells:
                fact_type = _match(cell["col_label"], VALUE_COLUMNS)
                value = effective_value(cell)
                if not fact_type or not (value or "").strip():
                    skipped += 1
                    continue
                if dry_run:
                    created += 1
                    by_type[fact_type] += 1
                    continue
                conn.execute("""INSERT INTO facts(document_id, version_id, page_no,
                    element_id, fact_type, subject, value_original, value_normalized,
                    unit_original, unit_normalized, conditions, condition_basis,
                    condition_basis_note, evidence_text, extractor,
                    ocr_derived, review_status, created_at, from_candidate_id)
                    SELECT ?,?,?,(SELECT element_id FROM elements WHERE document_id=?
                                   AND page_no=? ORDER BY ordinal LIMIT 1),
                           ?,?,?,?,?,?,?,?,?,?,?,0,?,?,?""",
                    (cell["document_id"], cell["version_id"], cell["page_no"],
                     cell["document_id"], cell["page_no"], fact_type,
                     cell["col_label"], value, _inches(value),
                     'in' if '"' in (value or "") else None, "in",
                     json.dumps(conditions),
                     # `stated`: these conditions are the table's own row and
                     # column labels. The document printed them in a grid, which
                     # is as stated as a condition gets -- and this is the one
                     # path in the codebase where that is true.
                     "stated", basis,
                     f"table row {row_i} of {cell['crop_path']}; read by "
                     f"{cell['reader']} ({reader_family(cell['reader'])})",
                     f"table-read:{cell['review_status']}",
                     cell["review_status"], now(), cell["candidate_id"]))
                created += 1
                by_type[fact_type] += 1
        if not dry_run:
            conn.commit()
        return {"rows_considered": len(groups), "facts_created": created,
                "cells_not_value_columns": skipped,
                "rows_with_unresolved_applicability": unresolved,
                "by_type": dict(by_type), "dry_run": dry_run}
    finally:
        if own:
            conn.close()


if __name__ == "__main__":
    print(json.dumps(promote_verified(dry_run=True), indent=2))


def revoke_machine_promotions(conn: sqlite3.Connection | None = None, *,
                              dry_run: bool = False) -> dict:
    """Un-promote facts that reached the store without a person in the loop.

    Build-plan A1. `PROMOTABLE` once contained ``cross_family_verified``, so two
    agents agreeing wrote a fact carrying a curation level no human conferred.
    Closing the gate stops new ones; this removes the ones already written.

    It **un-promotes**, it does not delete. The reading, its crop and its
    crop_sha256 stay exactly as they are — that is the evidence a reviewer needs,
    and cross-family agreement remains the right thing to order their queue by.
    Only the fact and the promotion link go.
    """
    own = conn is None
    conn = conn or connect()
    try:
        rows = conn.execute(f"""
            SELECT f.fact_id, c.candidate_id, c.review_status
              FROM facts f
              JOIN table_read_candidates c ON c.candidate_id = f.from_candidate_id
             WHERE c.review_status NOT IN ({','.join('?' * len(PROMOTABLE))})""",
            PROMOTABLE).fetchall()
        by_status: dict[str, int] = defaultdict(int)
        for r in rows:
            by_status[r["review_status"]] += 1
        if dry_run:
            return {"facts_deleted": 0, "candidates_reset": 0,
                    "would_revoke": len(rows), "by_status": dict(by_status)}

        deleted = 0
        for r in rows:
            # Deleting the fact removes the link with it: the pointer lives on
            # the fact and points down. Nothing to clean up, nothing to dangle.
            cur = conn.execute("DELETE FROM facts WHERE fact_id=?", (r["fact_id"],))
            deleted += cur.rowcount
            conn.execute("""UPDATE table_read_candidates
                               SET reviewer=NULL, reviewed_at=NULL
                             WHERE candidate_id=?""", (r["candidate_id"],))
        conn.commit()
        return {"facts_deleted": deleted, "candidates_reset": len(rows),
                "by_status": dict(by_status)}
    finally:
        if own:
            conn.close()
