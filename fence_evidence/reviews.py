"""The review loop: a person accepts or corrects a machine reading of a table.

`PROMOTABLE` is `("accepted", "corrected")` and until this module existed
nothing in the package wrote either, so `promote-tables --apply` was a no-op and
the level-2 population of the store was zero. This is the hole in the middle of
the publishing work, not the tail of it.

Two things follow from the measurement in the Phase 2 design §2, and they shape
every signature here:

* **The unit is one table per crop, never one cell.** A row-label band spans the
  rows it labels, so a per-cell box is ambiguous on exactly the tables this
  targets, and a bracket spans a *pair* of rows, so a per-row verdict would
  record it twice and the two copies could disagree.
* **Review is not mostly about wrong numbers.** Across 174 independently
  multi-read positions the readers never once disagreed about a number; all 30
  disagreements were about whether a merged value carries down into its
  continuation row. So a review records `spans` as well as `grid` — the
  structure the row model cannot express and G41 discards.

`table_reviews` is the record. The `review_status` / `reviewed_value` /
`reviewer` / `reviewed_at` annotations on `table_read_candidates` are a
*projection* of it, written in the same transaction and regenerable by
`rebuild_projection()` — the same guarantee `rebuild-index` gives
`retrieval_units`. Without it, "both storage forms" means two sources of truth
that drift.

Pointers run down: `table_reviews.from_candidates` names the readings a review
was derived from, and nothing on `table_read_candidates` points back up at a
review. That was `promoted_fact_id`, and `tests/test_pointer_direction.py`
forbids it.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3

from .store import now
from .table_review import PROMOTABLE, normalise

VERDICTS = ("accepted", "rejected", "bracket_unclear")

# The statuses only a review can write, and therefore the only ones
# `rebuild_projection` may clear. `cross_family_verified` and `agent_verified`
# are machine annotations that no review produced, so a rebuild must leave them
# alone or it would silently demote readings it never looked at.
REVIEW_STATUSES = PROMOTABLE + ("rejected", "bracket_unclear")


class ReviewRefused(RuntimeError):
    """A review that was not recorded, and the `error.*` code saying why.

    The code namespace matters: Planning's `test_locale_bundles.py` fails their
    build on any *warning-registry* code lacking both locale bundles, so an HTTP
    error must never borrow one. These are `error.*` and stay out of the
    registry.
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


# ------------------------------------------------------------------ validation
def _grid_map(grid) -> dict[tuple[int, int], str]:
    """Index the submitted grid by position, refusing anything ambiguous."""
    if not isinstance(grid, list):
        raise ReviewRefused("error.malformed_review", "grid must be a list of cells")
    out: dict[tuple[int, int], str] = {}
    for i, cell in enumerate(grid):
        if not isinstance(cell, dict):
            raise ReviewRefused("error.malformed_review", f"grid[{i}] is not an object")
        missing = [k for k in ("row", "col", "value") if k not in cell]
        if missing:
            raise ReviewRefused("error.malformed_review",
                                f"grid[{i}] is missing {', '.join(missing)}")
        row, col = cell["row"], cell["col"]
        # bool is an int subclass, and `{"row": true}` is not a row index.
        for name, v in (("row", row), ("col", col)):
            if isinstance(v, bool) or not isinstance(v, int):
                raise ReviewRefused("error.malformed_review",
                                    f"grid[{i}].{name} is not an integer: {v!r}")
        if not isinstance(cell["value"], str):
            # The column is TEXT and comparison runs through `normalise`, which
            # takes a string. Refusing a number is better than guessing at how
            # to render one.
            raise ReviewRefused("error.malformed_review",
                                f"grid[{i}].value must be a string, not "
                                f"{type(cell['value']).__name__}")
        if (row, col) in out and out[(row, col)] != cell["value"]:
            raise ReviewRefused("error.malformed_review",
                                f"grid gives two different values for row {row} col {col}")
        out[(row, col)] = cell["value"]
    return out


def _check_spans(spans, grid_map: dict[tuple[int, int], str]) -> None:
    """A span must lie inside the grid it annotates.

    A span reaching outside is not a merge we failed to model; it is a review
    describing a table other than the one it submitted, and recording it would
    put a bracket on rows nobody looked at.
    """
    if not isinstance(spans, list):
        raise ReviewRefused("error.malformed_review", "spans must be a list")
    if not spans:
        return
    if not grid_map:
        raise ReviewRefused("error.malformed_review",
                            "spans were given with no grid to place them in")
    rows = {r for r, _ in grid_map}
    cols = {c for _, c in grid_map}
    row_lo, row_hi = min(rows), max(rows)
    for i, span in enumerate(spans):
        if not isinstance(span, dict):
            raise ReviewRefused("error.malformed_review", f"spans[{i}] is not an object")
        missing = [k for k in ("row_from", "row_to", "col") if k not in span]
        if missing:
            raise ReviewRefused("error.malformed_review",
                                f"spans[{i}] is missing {', '.join(missing)}")
        vals = {}
        for name in ("row_from", "row_to", "col"):
            v = span[name]
            if isinstance(v, bool) or not isinstance(v, int):
                raise ReviewRefused("error.malformed_review",
                                    f"spans[{i}].{name} is not an integer: {v!r}")
            vals[name] = v
        if not row_lo <= vals["row_from"] <= row_hi or not row_lo <= vals["row_to"] <= row_hi:
            raise ReviewRefused("error.malformed_review",
                                f"spans[{i}] covers rows {vals['row_from']}..{vals['row_to']}, "
                                f"outside the grid's rows {row_lo}..{row_hi}")
        # Rows are bounded, columns deliberately are NOT. A span records
        # structure the readers did not capture, and on the footing tables the
        # applicability column is exactly that: measured, every
        # wind_exposure_footing crop was transcribed as columns 0..2 -- wind
        # exposure, footing depth, max post spacing -- and the fourth column
        # carrying "NON HVHZ" appears in no reading anywhere. Bounding col by
        # the transcribed grid would forbid recording the one fact spans exist
        # for. A negative column is still nonsense.
        if vals["col"] < 0:
            raise ReviewRefused("error.malformed_review",
                                f"spans[{i}].col is negative: {vals['col']}")
        if vals["row_from"] > vals["row_to"]:
            raise ReviewRefused("error.malformed_review",
                                f"spans[{i}] runs backwards: {vals['row_from']} > "
                                f"{vals['row_to']}")


# ------------------------------------------------------------------ projection
def _candidates(conn: sqlite3.Connection, crop_sha256: str) -> list[sqlite3.Row]:
    return conn.execute("""SELECT candidate_id, document_id, page_no, row_index,
                                  col_index, value
                             FROM table_read_candidates
                            WHERE crop_sha256 = ?
                            ORDER BY candidate_id""", (crop_sha256,)).fetchall()


def _project(conn: sqlite3.Connection, *, crop_sha256: str, verdict: str,
             grid_map: dict[tuple[int, int], str], reviewer: str,
             reviewed_at: str) -> tuple[list[int], int, int]:
    """Write the candidate annotations for one review. Returns (ids, cells, promotable).

    Both `submit_review` and `rebuild_projection` go through here, over the same
    stored inputs, which is what makes acceptance 3 — a byte-identical rebuild —
    a property of the code rather than of two implementations agreeing.

    The two verdict shapes are deliberately asymmetric. `rejected` and
    `bracket_unclear` are verdicts on the *table*: the reading as a whole is
    wrong or its applicability is unreadable, so every row of the crop carries
    it. `accepted` is a claim about the positions the reviewer actually
    recorded; a position they left out of the grid is one they did not confirm,
    and it stays unreviewed rather than being promoted by omission.
    """
    touched: list[int] = []
    promotable = 0
    for row in _candidates(conn, crop_sha256):
        if verdict == "accepted":
            # row_index -1 is a page-level verdict with no grid, not a cell.
            if row["row_index"] is None or row["row_index"] < 0:
                continue
            key = (row["row_index"], row["col_index"])
            if key not in grid_map:
                continue
            submitted = grid_map[key]
            # Compare on content, not typography: a curly quote in the reading
            # and a straight one in the review are the same number, and
            # recording that as a correction would misreport what review found.
            if normalise(submitted) == normalise(row["value"]):
                status, reviewed_value = "accepted", None
            else:
                status, reviewed_value = "corrected", submitted
        else:
            status, reviewed_value = verdict, None
        conn.execute("""UPDATE table_read_candidates
                           SET review_status = ?, reviewed_value = ?,
                               reviewer = ?, reviewed_at = ?
                         WHERE candidate_id = ?""",
                     (status, reviewed_value, reviewer, reviewed_at, row["candidate_id"]))
        touched.append(row["candidate_id"])
        if status in PROMOTABLE:
            promotable += 1
    return touched, len(touched), promotable


# ---------------------------------------------------------------------- submit
def submit_review(conn: sqlite3.Connection, *, crop_sha256: str, reviewer: str,
                  verdict: str, grid: list[dict], spans: list[dict],
                  notes: str | None = None, reviewed_at: str | None = None) -> dict:
    """Record one person's verdict on one table crop, and project it.

    `crop_sha256` is the whole integrity story. We never see the end user and
    cannot verify `reviewer`; the one checkable claim is *"this person looked at
    the image we hold"*, so a crop we do not recognise is refused and nothing is
    written — not recorded with a caveat.
    """
    if verdict not in VERDICTS:
        raise ReviewRefused("error.malformed_review",
                            f"verdict {verdict!r} is not one of {', '.join(VERDICTS)}")
    grid_map = _grid_map(grid or [])
    _check_spans(spans or [], grid_map)

    rows = _candidates(conn, crop_sha256)
    if not rows:
        raise ReviewRefused("error.crop_mismatch",
                            f"no reading in this store came from crop {crop_sha256}; "
                            f"the echoed image is not one we served")
    # 14 groups of corpus files are byte-identical under different
    # manufacturers, so identical crop bytes can appear under more than one
    # document. The review names the lowest (document_id, page_no) for its own
    # row and projects onto every reading of those pixels: the reviewer looked
    # at one image, and the pixels are the same table wherever it is filed.
    document_id, page_no = min((r["document_id"], r["page_no"]) for r in rows)

    reviewed_at = reviewed_at or now()
    review_id = hashlib.sha256(
        f"{crop_sha256}:{reviewer}:{reviewed_at}".encode()).hexdigest()[:16]

    # One transaction for the record and its projection, so the store is never
    # left holding a review whose annotations did not land. sqlite3 defers BEGIN
    # to the first DML, which would leave each UPDATE free-standing under an
    # autocommit connection; start it explicitly instead.
    started_here = not conn.in_transaction
    if started_here:
        conn.execute("BEGIN IMMEDIATE")
    try:
        touched, cells, promotable = _project(
            conn, crop_sha256=crop_sha256, verdict=verdict, grid_map=grid_map,
            reviewer=reviewer, reviewed_at=reviewed_at)
        conn.execute("""INSERT OR REPLACE INTO table_reviews
            (review_id, crop_sha256, document_id, page_no, reviewer, reviewed_at,
             verdict, grid, spans, from_candidates, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (review_id, crop_sha256, document_id, page_no, reviewer, reviewed_at,
             verdict, json.dumps(grid or []), json.dumps(spans or []),
             json.dumps(touched), notes))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"review_id": review_id, "verdict": verdict,
            "cells_written": cells, "promotable": promotable}


# --------------------------------------------------------------------- rebuild
def rebuild_projection(conn: sqlite3.Connection) -> dict:
    """Regenerate the candidate annotations from `table_reviews` alone.

    Replay order is `(reviewed_at, review_id)` — the order the reviews claim to
    have happened in, not the order they arrived. A review backdated behind one
    already applied therefore lands *before* it here, which is the record's own
    order and the one we treat as authoritative.
    """
    started_here = not conn.in_transaction
    if started_here:
        conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(f"""UPDATE table_read_candidates
                            SET review_status = 'unreviewed', reviewed_value = NULL,
                                reviewer = NULL, reviewed_at = NULL
                          WHERE review_status IN ({','.join('?' * len(REVIEW_STATUSES))})""",
                     REVIEW_STATUSES)
        replayed = cells = promotable = 0
        # Arrival order, not `reviewed_at`. submit_review applies reviews as they
        # arrive and the last write wins, so replaying by timestamp diverges the
        # moment a BACKDATED review is submitted after a later-stamped one:
        # the live projection holds the backdated review's values and the rebuild
        # holds the other's. Measured, and it is the only way acceptance 3 can
        # break. rowid is insertion order, and INSERT OR REPLACE on a resubmitted
        # review_id assigns a new one -- which is the wanted semantics, since a
        # resubmission IS the most recent arrival.
        for r in conn.execute("""SELECT * FROM table_reviews
                                  ORDER BY rowid""").fetchall():
            n, p = _project(conn, crop_sha256=r["crop_sha256"], verdict=r["verdict"],
                            grid_map=_grid_map(json.loads(r["grid"])),
                            reviewer=r["reviewer"], reviewed_at=r["reviewed_at"])[1:]
            replayed += 1
            cells += n
            promotable += p
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"reviews_replayed": replayed, "cells_written": cells,
            "promotable": promotable}


# ----------------------------------------------------------------- the queue
def review_queue(conn: sqlite3.Connection, *, limit: int = 50) -> list[dict]:
    """Crops no person has ruled on yet, hardest evidence first.

    Ordered by how many positions two independent model families already read
    identically: `cross_family_verified` is the right thing to *order* a queue
    by and never a substitute for clearing it, so it ranks here and decides
    nothing.
    """
    rows = conn.execute("""
        SELECT c.document_id, c.page_no, c.crop_sha256,
               MIN(c.crop_path) AS crop_path,
               COUNT(DISTINCT c.row_index || ':' || c.col_index) AS cells,
               COUNT(DISTINCT c.reader) AS readers,
               SUM(CASE WHEN c.review_status = 'cross_family_verified'
                        THEN 1 ELSE 0 END) AS cross_family_verified
          FROM table_read_candidates c
         WHERE c.crop_sha256 IS NOT NULL
           AND NOT EXISTS (SELECT 1 FROM table_reviews r
                            WHERE r.crop_sha256 = c.crop_sha256)
         GROUP BY c.document_id, c.page_no, c.crop_sha256
         ORDER BY cross_family_verified DESC, cells DESC, c.document_id, c.page_no
         LIMIT ?""", (limit,)).fetchall()
    return [dict(r) for r in rows]


def review_summary(conn: sqlite3.Connection) -> dict:
    by_verdict = {r["verdict"]: r["n"] for r in conn.execute(
        "SELECT verdict, COUNT(*) n FROM table_reviews GROUP BY 1 ORDER BY 1")}
    by_status = {r["review_status"]: r["n"] for r in conn.execute(
        f"""SELECT review_status, COUNT(*) n FROM table_read_candidates
             WHERE review_status IN ({','.join('?' * len(REVIEW_STATUSES))})
             GROUP BY 1 ORDER BY 1""", REVIEW_STATUSES)}
    reviewed = conn.execute(
        "SELECT COUNT(DISTINCT crop_sha256) FROM table_reviews").fetchone()[0]
    pending = conn.execute("""SELECT COUNT(DISTINCT c.crop_sha256)
          FROM table_read_candidates c
         WHERE c.crop_sha256 IS NOT NULL
           AND NOT EXISTS (SELECT 1 FROM table_reviews r
                            WHERE r.crop_sha256 = c.crop_sha256)""").fetchone()[0]
    return {"reviews": sum(by_verdict.values()), "by_verdict": by_verdict,
            "reviewers": [r[0] for r in conn.execute(
                "SELECT DISTINCT reviewer FROM table_reviews ORDER BY 1")],
            "crops_reviewed": reviewed, "crops_pending": pending,
            "cells_annotated": sum(by_status.values()), "by_status": by_status,
            "promotable": sum(by_status.get(s, 0) for s in PROMOTABLE)}
