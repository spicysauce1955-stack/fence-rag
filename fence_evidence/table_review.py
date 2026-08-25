"""Review-gated readings of the scanned tables OCR could not rebuild.

A *reading* is what some reader saw on a page image: an agent, a future per-cell
OCR pass, or a person. Readings are stored, compared, and surfaced as candidates.
They are never facts.

The gate is enforced here rather than described in a document. What makes a
reading promotable is that a person compared it to the source crop:

* ``accepted`` / ``corrected`` — a person signed off. Promotable.
* ``cross_family_verified`` — readers from at least two different model families
  produced the identical value. **Not promotable.** Strong evidence, and the
  right thing to order a review queue by, but no person has looked.
* ``agent_verified`` — two readers from the *same* family agreed. Not
  promotable: their errors may be correlated, and nothing here measures that.

Independence between readers is what makes agreement worth ranking on. It is not
what makes a reading a fact. This gate once treated ``cross_family_verified`` as
promotable, which published 324 facts at a curation level no person had checked;
see ``docs/build-plan.md`` A1.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path

from .paths import REPO_ROOT
from .store import connect, now

PROMOTABLE = ("accepted", "corrected")
READ_STATUSES = ("unreviewed", "agent_verified", "cross_family_verified",
                 "accepted", "corrected", "rejected")

# Which model family produced a reading. Readers in the same family may fail the
# same way, so agreement between them is weaker evidence than agreement across.
READER_FAMILY = {
    "calibration-A": "claude-sonnet", "calibration-B": "claude-sonnet",
    "coverage-1": "claude-sonnet", "coverage-2": "claude-sonnet",
    "coverage-3": "claude-sonnet", "coverage-4": "claude-sonnet",
    "codex-C": "openai-codex",
}


def reader_family(reader: str) -> str:
    return READER_FAMILY.get(reader, "unknown")

_QUOTES = {"“": '"', "”": '"', "″": '"', "‘": "'",
           "’": "'", "′": "'", "–": "-", "—": "-"}


def normalise(value: str | None) -> str:
    """Compare readings on content, not on typography."""
    if value is None:
        return ""
    v = value
    for a, b in _QUOTES.items():
        v = v.replace(a, b)
    v = v.replace("''", '"').upper()
    v = re.sub(r"\s+", " ", v).strip()
    v = re.sub(r"\s*(IN\.?|INCHES|\")\s*$", '"', v)
    return v.strip(" .")


# ------------------------------------------------------------------ loading
def load_reading(conn: sqlite3.Connection, path: Path, *,
                 reader_kind: str = "agent") -> dict:
    """Load one reader's JSON output into `table_read_candidates`."""
    with open(path) as f:
        payload = json.load(f)
    pages = payload if isinstance(payload, list) else payload.get("pages", [])
    inserted = page_rows = skipped = 0
    for page in pages:
        src = page.get("source_path")
        row = conn.execute("""SELECT d.document_id, v.version_id FROM documents d
                JOIN document_versions v ON v.document_id = d.document_id
                WHERE d.source_path=?""", (src,)).fetchone()
        if row is None:
            skipped += 1
            continue
        crop = page.get("crop_path") or ""
        crop_sha = None
        cp = REPO_ROOT / crop if crop else None
        if cp and cp.is_file():
            crop_sha = hashlib.sha256(cp.read_bytes()).hexdigest()
        reader = page.get("reader") or path.stem
        common = dict(document_id=row["document_id"], version_id=row["version_id"],
                      page_no=int(page["page_no"]), crop_path=crop, crop_sha256=crop_sha,
                      reader=reader, reader_kind=reader_kind,
                      is_table=int(bool(page.get("is_table"))),
                      table_kind=page.get("table_kind"),
                      reading_confidence=page.get("reading_confidence"),
                      notes=(page.get("notes") or "")[:2000])
        page_rows += 1
        grid = page.get("grid") or {}
        headers = grid.get("headers") or []
        rows = grid.get("rows") or []
        if not rows:
            # a page-level verdict with no grid is still a reading worth keeping
            _insert(conn, common, row_index=-1, col_index=-1, row_label=None,
                    col_label=page.get("what_the_page_is"),
                    value=None, illegible=0)
            inserted += 1
            continue
        for r_i, r in enumerate(rows):
            cells = r.get("cells") or []
            illegible_cells = {str(x) for x in (r.get("illegible") or [])}
            row_label = cells[0] if cells else None
            for c_i, cell in enumerate(cells):
                _insert(conn, common, row_index=r_i, col_index=c_i,
                        row_label=row_label,
                        col_label=headers[c_i] if c_i < len(headers) else None,
                        value=cell,
                        illegible=int("?" in str(cell) or str(c_i) in illegible_cells))
                inserted += 1
    conn.commit()
    return {"file": str(path), "pages": page_rows, "cells": inserted,
            "pages_skipped_unknown_source": skipped}


def _insert(conn, common, **kw) -> None:
    conn.execute("""INSERT OR REPLACE INTO table_read_candidates
        (document_id, version_id, page_no, crop_path, crop_sha256, reader, reader_kind,
         is_table, table_kind, row_index, col_index, row_label, col_label, value,
         illegible, reading_confidence, notes, review_status, created_at)
        VALUES (:document_id,:version_id,:page_no,:crop_path,:crop_sha256,:reader,
                :reader_kind,:is_table,:table_kind,:row_index,:col_index,:row_label,
                :col_label,:value,:illegible,:reading_confidence,:notes,
                'unreviewed',:created_at)""",
                 {**common, **kw, "created_at": now()})


# --------------------------------------------------------------- agreement
def agreement(conn: sqlite3.Connection, readers: tuple[str, str]) -> dict:
    """Cell-level agreement between two independent readers."""
    a, b = readers
    rows = conn.execute("""
        SELECT x.document_id, x.page_no, x.row_index, x.col_index,
               x.value AS va, y.value AS vb, x.illegible AS ia, y.illegible AS ib
          FROM table_read_candidates x
          JOIN table_read_candidates y
            ON y.document_id=x.document_id AND y.page_no=x.page_no
           AND y.row_index=x.row_index AND y.col_index=x.col_index AND y.reader=?
         WHERE x.reader=? AND x.row_index >= 0""", (b, a)).fetchall()
    agree = disagree = both_illegible = one_illegible = 0
    conflicts = []
    for r in rows:
        if r["ia"] and r["ib"]:
            both_illegible += 1
            continue
        if r["ia"] or r["ib"]:
            one_illegible += 1
            continue
        if normalise(r["va"]) == normalise(r["vb"]):
            agree += 1
        else:
            disagree += 1
            conflicts.append({"document_id": r["document_id"], "page_no": r["page_no"],
                              "row": r["row_index"], "col": r["col_index"],
                              a: r["va"], b: r["vb"]})
    compared = agree + disagree
    return {"readers": [a, b], "cells_compared": compared,
            "agree": agree, "disagree": disagree,
            "agreement_rate": round(agree / compared, 4) if compared else None,
            "both_illegible": both_illegible, "one_illegible": one_illegible,
            "conflicts": conflicts}


def mark_cross_family_verified(conn: sqlite3.Connection, readers: list[str]) -> dict:
    """Flag cells that readers from two or more model families read identically.

    Agreement across families is the evidence that makes a reading promotable:
    two systems that fail differently producing the same string is a much
    stronger signal than two instances of one system agreeing.
    """
    families = {r: reader_family(r) for r in readers}
    if len({f for f in families.values() if f != "unknown"}) < 2:
        return {"error": "need readers from at least two model families",
                "families": families}
    placeholders = ",".join("?" * len(readers))
    rows = conn.execute(f"""
        SELECT document_id, page_no, row_index, col_index,
               COUNT(DISTINCT value) distinct_values,
               COUNT(*) n, GROUP_CONCAT(reader) readers, MIN(value) value
          FROM table_read_candidates
         WHERE reader IN ({placeholders}) AND row_index >= 0 AND illegible = 0
         GROUP BY document_id, page_no, row_index, col_index""", readers).fetchall()
    verified = skipped = 0
    for r in rows:
        present = {x for x in (r["readers"] or "").split(",")}
        if len({families.get(x, "unknown") for x in present}) < 2:
            skipped += 1
            continue
        values = {normalise(x["value"]) for x in conn.execute(f"""
            SELECT value FROM table_read_candidates
             WHERE document_id=? AND page_no=? AND row_index=? AND col_index=?
               AND reader IN ({placeholders})""",
            (r["document_id"], r["page_no"], r["row_index"], r["col_index"], *readers))}
        if len(values) != 1:
            skipped += 1
            continue
        conn.execute(f"""UPDATE table_read_candidates SET review_status='cross_family_verified'
             WHERE document_id=? AND page_no=? AND row_index=? AND col_index=?
               AND reader IN ({placeholders})""",
            (r["document_id"], r["page_no"], r["row_index"], r["col_index"], *readers))
        verified += 1
    conn.commit()
    return {"cells_verified": verified, "cells_not_verified": skipped,
            "families": sorted(set(families.values()))}


def mark_agent_verified(conn: sqlite3.Connection, readers: tuple[str, str]) -> int:
    """Flag cells two same-family agents read identically.

    A reading status, not a promotion status: `promote` still refuses it,
    because same-family errors may be correlated.
    """
    a, b = readers
    rows = conn.execute("""
        SELECT x.candidate_id AS ca, y.candidate_id AS cb, x.value AS va, y.value AS vb
          FROM table_read_candidates x
          JOIN table_read_candidates y
            ON y.document_id=x.document_id AND y.page_no=x.page_no
           AND y.row_index=x.row_index AND y.col_index=x.col_index AND y.reader=?
         WHERE x.reader=? AND x.row_index >= 0
           AND x.illegible=0 AND y.illegible=0
           AND x.review_status='unreviewed'""", (b, a)).fetchall()
    n = 0
    for r in rows:
        if normalise(r["va"]) == normalise(r["vb"]):
            conn.execute("""UPDATE table_read_candidates SET review_status='agent_verified'
                            WHERE candidate_id IN (?,?)""", (r["ca"], r["cb"]))
            n += 2
    conn.commit()
    return n


# ------------------------------------------------------- the promotion gate
class ReviewRequired(RuntimeError):
    """Raised when something tries to turn an unreviewed reading into a fact."""


def promote(conn: sqlite3.Connection, candidate_id: int, *, fact_type: str,
            reviewer: str | None = None) -> int:
    """Write a fact from a reviewed candidate. Refuses anything else."""
    row = conn.execute("SELECT * FROM table_read_candidates WHERE candidate_id=?",
                       (candidate_id,)).fetchone()
    if row is None:
        raise ReviewRequired(f"no such candidate: {candidate_id}")
    if row["review_status"] not in PROMOTABLE:
        raise ReviewRequired(
            f"candidate {candidate_id} is '{row['review_status']}'; only "
            f"{', '.join(PROMOTABLE)} may become a fact — each of which means a "
            f"person compared the reading to its source crop. Agreement between "
            f"readers is evidence for that person, never a substitute for them: "
            f"'cross_family_verified' ranks the queue, it does not clear it, and "
            f"'agent_verified' is weaker still because same-family errors may be "
            f"correlated.")
    if not row["crop_path"] or not (REPO_ROOT / row["crop_path"]).is_file():
        raise ReviewRequired(
            f"candidate {candidate_id} has no source crop on disk; a number that "
            "cannot be checked against its pixels must not become a fact")
    value = row["reviewed_value"] or row["value"]
    element = conn.execute("""SELECT element_id FROM elements
        WHERE document_id=? AND page_no=? ORDER BY ordinal LIMIT 1""",
        (row["document_id"], row["page_no"])).fetchone()
    if element is None:
        raise ReviewRequired("no canonical element on that page to anchor the fact to")
    cur = conn.execute("""INSERT INTO facts(document_id, version_id, page_no, element_id,
        fact_type, subject, value_original, value_normalized, unit_original,
        unit_normalized, conditions, condition_basis, condition_basis_note,
        evidence_text, extractor, ocr_derived, review_status, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (row["document_id"], row["version_id"], row["page_no"], element["element_id"],
         fact_type, row["row_label"], value, None, None, None,
         json.dumps({"col_label": row["col_label"], "row_label": row["row_label"]}),
         # `stated` -- the labels came off the document's own printed grid, and a
         # person compared them to the crop before this row could exist at all.
         "stated",
         f"row and column labels read from {row['crop_path']}, "
         f"reviewed by {reviewer or row['reviewer'] or 'unknown'}",
         f"read from {row['crop_path']} row {row['row_index']} col {row['col_index']}",
         f"table-review:{row['review_status']}:{row['reader']}", 0,
         "reviewed", now()))
    conn.execute("""UPDATE table_read_candidates SET promoted_fact_id=?, reviewer=?,
                    reviewed_at=? WHERE candidate_id=?""",
                 (cur.lastrowid, reviewer or row["reviewer"], now(), candidate_id))
    conn.commit()
    return cur.lastrowid


def summary(conn: sqlite3.Connection) -> dict:
    by_status = {r["review_status"]: r["n"] for r in conn.execute(
        "SELECT review_status, COUNT(*) n FROM table_read_candidates GROUP BY 1")}
    by_reader = {r["reader"]: r["n"] for r in conn.execute(
        "SELECT reader, COUNT(*) n FROM table_read_candidates GROUP BY 1 ORDER BY n DESC")}
    pages = conn.execute("""SELECT COUNT(DISTINCT document_id || '#' || page_no)
                            FROM table_read_candidates""").fetchone()[0]
    tables = conn.execute("""SELECT COUNT(DISTINCT document_id || '#' || page_no)
        FROM table_read_candidates WHERE is_table=1""").fetchone()[0]
    return {"candidates": sum(by_status.values()), "by_status": by_status,
            "by_reader": by_reader, "pages_read": pages,
            "pages_reported_as_tables": tables,
            "promoted_facts": conn.execute(
                "SELECT COUNT(*) FROM table_read_candidates "
                "WHERE promoted_fact_id IS NOT NULL").fetchone()[0]}


# ------------------------------------------- what the pipeline's OCR missed
def compare_with_pipeline(conn: sqlite3.Connection, reader: str | None = None) -> dict:
    """For every value a reader saw, ask whether the pipeline's OCR has it.

    This is the measurement the whole exercise exists for: the pipeline flagged
    these pages `table_not_reconstructed`, and this quantifies how much of the
    readable content that flag was hiding.
    """
    where = "AND c.reader = ?" if reader else ""
    params = (reader,) if reader else ()
    rows = conn.execute(f"""
        SELECT c.document_id, c.page_no, c.reader, c.row_label, c.col_label, c.value
          FROM table_read_candidates c
         WHERE c.row_index >= 0 AND c.illegible = 0
           AND c.value IS NOT NULL AND TRIM(c.value) != '' {where}""", params).fetchall()
    page_text: dict[tuple[str, int], str] = {}
    found = missing = 0
    missed_examples = []
    for r in rows:
        key = (r["document_id"], r["page_no"])
        if key not in page_text:
            parts = conn.execute("""SELECT COALESCE(NULLIF(e.text,''), e.ocr_text) t
                    FROM elements e WHERE e.document_id=? AND e.page_no=?""", key).fetchall()
            cells = conn.execute("""SELECT tc.text t FROM table_cells tc
                    JOIN tables tb ON tb.table_id = tc.table_id
                    JOIN elements e ON e.element_id = tb.element_id
                    WHERE e.document_id=? AND e.page_no=?""", key).fetchall()
            page_text[key] = normalise(" ".join(
                (x["t"] or "") for x in list(parts) + list(cells)))
        needle = normalise(r["value"])
        if needle and needle in page_text[key]:
            found += 1
        else:
            missing += 1
            if len(missed_examples) < 25:
                missed_examples.append({
                    "document_id": r["document_id"], "page_no": r["page_no"],
                    "row_label": r["row_label"], "col_label": r["col_label"],
                    "value": r["value"], "reader": r["reader"]})
    total = found + missing
    return {"reader": reader or "all", "values_checked": total,
            "present_in_pipeline_text": found, "absent_from_pipeline_text": missing,
            "ocr_recall_on_readable_values": round(found / total, 4) if total else None,
            "examples_absent": missed_examples}


def load_directory(conn: sqlite3.Connection, directory: Path,
                   pattern: str = "agent-read-*.json") -> dict:
    """Load every reader output file in a directory."""
    loaded = []
    for path in sorted(Path(directory).glob(pattern)):
        try:
            loaded.append(load_reading(conn, path))
        except (ValueError, KeyError) as e:
            loaded.append({"file": str(path), "error": f"{e.__class__.__name__}: {e}"})
    return {"files": loaded}
