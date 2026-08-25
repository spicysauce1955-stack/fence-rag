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
        if v:
            by_family[reader_family(r["reader"])].add(v)
    agreed = {next(iter(v)) for v in by_family.values() if len(v) == 1}
    if len(by_family) >= 2 and len(agreed) == 1:
        return agreed.pop(), "cross-family agreement on the bracket label"
    return "unresolved", ("readers did not independently agree on the applicability "
                          "bracket; see the page crop")


def promote_verified(conn: sqlite3.Connection | None = None, *,
                     dry_run: bool = False) -> dict:
    own = conn is None
    conn = conn or connect()
    try:
        rows = conn.execute(f"""
            SELECT * FROM table_read_candidates
             WHERE review_status IN ({','.join('?' * len(PROMOTABLE))})
               AND row_index >= 0 AND promoted_fact_id IS NULL
             ORDER BY document_id, page_no, row_index, col_index""",
            PROMOTABLE).fetchall()
        groups: dict[tuple, list[sqlite3.Row]] = defaultdict(list)
        for r in rows:
            groups[(r["document_id"], r["page_no"], r["row_index"])].append(r)

        created = skipped = unresolved = 0
        by_type: dict[str, int] = defaultdict(int)
        for (doc, page, row_i), cells in sorted(groups.items()):
            conditions: dict[str, str] = {}
            for cell in cells:
                key = _match(cell["col_label"], KEY_COLUMNS)
                if key and cell["value"] and cell["value"].strip():
                    conditions[key] = cell["value"].strip()
            exposure = conditions.get("exposure_category", "")
            applicability, basis = _row_applicability(cells, exposure)
            if applicability == "unresolved":
                unresolved += 1
            conditions["hvhz_applicability"] = applicability
            conditions["_applicability_basis"] = basis

            for cell in cells:
                fact_type = _match(cell["col_label"], VALUE_COLUMNS)
                if not fact_type or not (cell["value"] or "").strip():
                    skipped += 1
                    continue
                if dry_run:
                    created += 1
                    by_type[fact_type] += 1
                    continue
                cur = conn.execute("""INSERT INTO facts(document_id, version_id, page_no,
                    element_id, fact_type, subject, value_original, value_normalized,
                    unit_original, unit_normalized, conditions, evidence_text, extractor,
                    ocr_derived, review_status, created_at)
                    SELECT ?,?,?,(SELECT element_id FROM elements WHERE document_id=?
                                   AND page_no=? ORDER BY ordinal LIMIT 1),
                           ?,?,?,?,?,?,?,?,?,0,?,?""",
                    (cell["document_id"], cell["version_id"], cell["page_no"],
                     cell["document_id"], cell["page_no"], fact_type,
                     cell["col_label"], cell["value"], _inches(cell["value"]),
                     'in' if '"' in (cell["value"] or "") else None, "in",
                     json.dumps(conditions),
                     f"table row {row_i} of {cell['crop_path']}; read by "
                     f"{cell['reader']} ({reader_family(cell['reader'])})",
                     f"table-read:{cell['review_status']}",
                     cell["review_status"], now()))
                conn.execute("UPDATE table_read_candidates SET promoted_fact_id=? "
                             "WHERE candidate_id=?", (cur.lastrowid, cell["candidate_id"]))
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
            SELECT candidate_id, promoted_fact_id, review_status
              FROM table_read_candidates
             WHERE promoted_fact_id IS NOT NULL
               AND review_status NOT IN ({','.join('?' * len(PROMOTABLE))})""",
            PROMOTABLE).fetchall()
        by_status: dict[str, int] = defaultdict(int)
        for r in rows:
            by_status[r["review_status"]] += 1
        if dry_run:
            return {"facts_deleted": 0, "candidates_reset": 0,
                    "would_revoke": len(rows), "by_status": dict(by_status)}

        deleted = 0
        for r in rows:
            cur = conn.execute("DELETE FROM facts WHERE fact_id=?",
                               (r["promoted_fact_id"],))
            deleted += cur.rowcount
            conn.execute("""UPDATE table_read_candidates
                               SET promoted_fact_id=NULL, reviewer=NULL, reviewed_at=NULL
                             WHERE candidate_id=?""", (r["candidate_id"],))
        conn.commit()
        return {"facts_deleted": deleted, "candidates_reset": len(rows),
                "by_status": dict(by_status)}
    finally:
        if own:
            conn.close()
