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
import re
import sqlite3

from pathlib import Path

from .canonical import canonical_bytes
from .paths import CATALOG_DIR, REPO_ROOT, open_write, rel
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
def _candidates(conn: sqlite3.Connection, crop_sha256: str,
                only: list[int] | None = None) -> list[sqlite3.Row]:
    """Readings of one crop; `only` restricts to a review's own candidate ids.

    The restriction is what stops a replay from signing readings the reviewer
    never saw. `submit_review` sees the readings that exist when it runs;
    without `only`, `rebuild_projection` would see the readings that exist
    *now*, and the real queue is loaded incrementally by `load_directory` --
    seven readers, arriving at different times. A reading loaded after a review
    would be stamped with that reviewer's name and become PROMOTABLE, which is
    a human sign-off record for something no human looked at, and PROMOTABLE is
    the only gate between a reading and a curation-level-2 fact.
    """
    if only is not None and not only:
        return []
    sql = """SELECT candidate_id, document_id, page_no, row_index, col_index, value
               FROM table_read_candidates
              WHERE crop_sha256 = ?"""
    args: list = [crop_sha256]
    if only is not None:
        sql += f" AND candidate_id IN ({','.join('?' * len(only))})"
        args += list(only)
    return conn.execute(sql + " ORDER BY candidate_id", args).fetchall()


def _project(conn: sqlite3.Connection, *, crop_sha256: str, verdict: str,
             grid_map: dict[tuple[int, int], str], reviewer: str,
             reviewed_at: str, only: list[int] | None = None
             ) -> tuple[list[int], int, int]:
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
    for row in _candidates(conn, crop_sha256, only):
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


def _check_echo_is_current(conn: sqlite3.Connection, crop_sha256: str) -> None:
    """Refuse a review whose echoed digest is not the image on disk NOW.

    §4.3 names this the one control that survives `reviewer` being unverifiable:
    *"a review must echo the `crop_sha256` of the image we served."* As first
    written it compared the echo against `table_read_candidates.crop_sha256` --
    a stored constant, and one that is committed to git in
    `workspace/catalog/noa-table-candidates.jsonl`. Quoting a public constant
    demonstrates nothing, so the check verified nothing.

    Recomputing from the file makes it a real check of the one property it can
    actually establish: **the digest matches the artifact this store holds
    today**. If the crop were re-rendered after the reading was taken, a review
    echoing the old digest is a review of an image that no longer exists, and
    that is worth refusing.

    Be clear about what this is NOT. A digest is not a secret, so echoing it
    proves the caller *had the digest*, never that a person looked at the
    picture. It detects staleness; it does not authenticate. Forgery is held off
    by the bearer allowlist and by Planning's own auth, and the honesty of
    `reviewer` rests on Planning, exactly as §4 says. See G46.

    Fails closed: a crop we cannot read is a crop we cannot claim was reviewed.
    """
    row = conn.execute("SELECT crop_path FROM table_read_candidates "
                       " WHERE crop_sha256 = ? AND crop_path IS NOT NULL LIMIT 1",
                       (crop_sha256,)).fetchone()
    path = REPO_ROOT / row["crop_path"] if row and row["crop_path"] else None
    if path is None or not path.exists():
        raise ReviewRefused(
            "error.crop_mismatch",
            f"the crop for {crop_sha256} is not on disk, so the echo cannot be "
            f"checked; a reading whose image we cannot serve cannot be reviewed")
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    actual = h.hexdigest()
    if actual != crop_sha256:
        raise ReviewRefused(
            "error.crop_mismatch",
            f"the echoed digest is not the image on disk: {crop_sha256} echoed, "
            f"{actual} held. The crop was re-rendered after this reading, so the "
            f"review is of a picture that no longer exists")


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
    _check_echo_is_current(conn, crop_sha256)
    # 14 groups of corpus files are byte-identical under different
    # manufacturers, so identical crop bytes can appear under more than one
    # document. The review names the lowest (document_id, page_no) for its own
    # row and projects onto every reading of those pixels: the reviewer looked
    # at one image, and the pixels are the same table wherever it is filed.
    document_id, page_no = min((r["document_id"], r["page_no"]) for r in rows)

    reviewed_at = reviewed_at or now()
    # The verdict and its content are in the id, not just who/what/when.
    # `now()` is second-resolution, so crop+reviewer+timestamp collided on a
    # double-submit, a client retry, or an accept-then-immediately-correct --
    # and `INSERT OR REPLACE` then dropped the first review outright, including
    # its `from_candidates` link. A differential fuzz over 3,000 interleavings
    # found ten distinct projection-drift shapes and every one traced to this.
    #
    # Folding the payload in keeps the good half of that behaviour: an identical
    # resubmission still lands on the same id and replaces itself, which is what
    # a retry should do, while two genuinely different reviews in one second stay
    # two rows.
    payload = json.dumps({"verdict": verdict, "grid": grid or [],
                          "spans": spans or [], "notes": notes},
                         sort_keys=True, separators=(",", ":"))
    review_id = hashlib.sha256(
        f"{crop_sha256}:{reviewer}:{reviewed_at}:{payload}".encode()).hexdigest()[:16]

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

    Replay order is arrival order (`rowid`), which is the order `submit_review`
    actually applied them in. Ordering by `reviewed_at` instead diverges the
    moment a backdated review is submitted after a later-stamped one: the live
    projection holds the backdated review's values and the rebuild holds the
    other's, so the projection disagrees with its own source.

    Each review is replayed only over the readings it was derived from
    (`from_candidates`), never over a live query. A reading loaded after a
    review is one the reviewer never saw, and stamping it would fabricate a
    human sign-off for a machine reading.
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
            # Scoped to the readings this review was actually derived from.
            # `from_candidates` already records exactly that; replaying against a
            # live query instead let a reading loaded AFTER the review acquire
            # the reviewer's name and a PROMOTABLE status.
            n, p = _project(conn, crop_sha256=r["crop_sha256"], verdict=r["verdict"],
                            grid_map=_grid_map(json.loads(r["grid"])),
                            reviewer=r["reviewer"], reviewed_at=r["reviewed_at"],
                            only=json.loads(r["from_candidates"]))[1:]
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


# ============================================================================
# The fact review loop — G6's review half.
# ============================================================================
#
# Everything above judges a *table crop*. This judges one **regex-extracted
# fact**, which is a different unit with a different failure mode and needed
# its own loop rather than a widened one.
#
# The defect it closes, quoting `docs/state-and-gaps.md` G6: *"266 of 1,714
# facts are `flagged` because they came from OCR below 80% confidence, and no
# promotion path from `flagged` to `reviewed` exists — there is no review UI or
# workflow, only the column."* `store.SCHEMA` has documented `reviewed` as "a
# person accepted or corrected it" since the facts table shipped, and nothing
# in the package could write it for a regex fact.
#
# Three properties are carried over from the table loop deliberately, because
# each of them was paid for:
#
# * **One person, one fact, by name.** There is no signature here that takes a
#   set of readings and returns a verdict. `cross_family_verified` was
#   PROMOTABLE once; two model families agreeing produced 324 curation-level-2
#   facts nobody had looked at (G17), and build-plan A1 un-promoted every one.
#   `FACT_VERDICTS` holds three human verdicts and no machine one, and
#   `reviewed_without_a_reviewer` is the standing check that no other path
#   opened.
# * **The record is the table; the columns on `facts` are a projection.**
#   `rebuild_fact_projection` regenerates them from `fact_reviews` alone, the
#   same guarantee `rebuild_projection` gives `table_read_candidates` and
#   `rebuild-index` gives `retrieval_units`. Without it, "both storage forms"
#   means two sources of truth that drift.
# * **Nothing is one-way.** G47 found promotion skipping any cell that already
#   had a fact, so a reviewer's later rejection never reached the published
#   value. Here every review supersedes the last, a rejection is undone by a
#   later acceptance, and withdrawing the record and rebuilding puts the fact
#   back at the status it held before anybody touched it.
#
# And one that is not carried over. A table review echoes `crop_sha256` and the
# check recomputes it from the image on disk. A fact's evidence is not a
# pre-rendered artifact — `sourcerefs.source_ref` cuts it out of the PDF on
# demand — so the echo here is the `ref_id`, and the check is that it still
# equals the id this store mints for that fact's element **today**. That
# detects the G38 failure exactly: a toolchain upgrade moves a bbox by 0.02pt,
# the id changes completely, and a review quoting the old one is a review of a
# rectangle that no longer exists. It authenticates nothing; a ref id is not a
# secret. See G46 for the same caveat stated about crops.

# The verdicts a person may reach. Three, all human. Adding a fourth that some
# process could compute is the A1 defect, and `tests/test_fact_review.py` pins
# this set for that reason.
FACT_VERDICTS = ("accepted", "corrected", "rejected")

# `facts.review_status` a fact review may write. `accepted` and `corrected`
# both land on `reviewed`, because that is the status `store.SCHEMA` and
# `parameters.CURATION_LEVEL` already define as "a person accepted or corrected
# it" / curation level 2. The verdict itself is kept, unflattened, in
# `fact_reviews.verdict`.
FACT_STATUS_FOR_VERDICT = {"accepted": "reviewed", "corrected": "reviewed",
                           "rejected": "rejected"}

# What the queue offers. Only `flagged` — that is the pile G6 names, and it is
# the pile whose evidence is measurably weak. A person may still rule on any
# other fact by id; the queue is a work list, not a permission.
FACT_QUEUE_STATUS = "flagged"


def ensure_fact_reviews(conn: sqlite3.Connection) -> None:
    """Create `fact_reviews` if this store predates it.

    `store.connect` runs `ensure_columns` but never `executescript(SCHEMA)`, so
    a new *table* is invisible to an existing store until `cli migrate` runs.
    `CREATE TABLE IF NOT EXISTS` is a no-op once it has, and applying the one
    fragment keeps `store.SCHEMA` the single declaration of it.
    """
    from .store import FACT_REVIEWS_DDL
    conn.executescript(FACT_REVIEWS_DDL)


# ------------------------------------------------------------------ the ref
def fact_ref_id(conn: sqlite3.Connection, fact_id: int) -> str | None:
    """The `ref_id` of the region a reviewer has to look at, or None.

    Minted by `refs.ref_id` from the fact's own element — the same formula
    `snapshot` cites and `GET /source-refs/{id}` resolves, so a queue entry and
    a published citation name the identical rectangle. None means the fact's
    element or version is not in this store, which makes the fact unreviewable
    rather than merely unrendered.
    """
    from .refs import ref_id as mint
    row = conn.execute("""SELECT e.bbox, f.page_no, v.sha256
          FROM facts f
          JOIN elements e ON e.element_id = f.element_id
          JOIN document_versions v ON v.version_id = f.version_id
         WHERE f.fact_id = ?""", (fact_id,)).fetchone()
    if row is None:
        return None
    return mint(row["sha256"], row["page_no"], row["bbox"])


def fact_source_ref(conn: sqlite3.Connection, fact_id: int, *, dpi: int = 200) -> dict:
    """The §5.1 `SourceRef` for a fact: the picture, the text and the warnings.

    Straight through `sourcerefs.source_ref`, which renders through `crops.py`
    and caches through `cropcache.py`. Nothing about cropping is reimplemented
    here; a reviewer looking at a flagged fact sees exactly the artifact
    Planning's screens serve, which is the only way "compared it to the source
    image" means the same thing on both sides of the boundary.
    """
    from .sourcerefs import source_ref
    rid = fact_ref_id(conn, fact_id)
    if rid is None:
        raise ReviewRefused(
            "error.unknown_fact",
            f"fact {fact_id} names no element in this store, so there is no "
            f"region to show")
    return source_ref(conn, rid, dpi=dpi)


# ----------------------------------------------------------------- the value
def effective_fact_value(row) -> str | None:
    """What a fact actually says: the person's value where one exists.

    G44 in one function, one layer out from `promote_tables.effective_value`.
    There, promotion wrote the machine's transcription into a fact whose status
    was `corrected` and published it at curation level 2 — the reviewer's `99"`
    was in the store and never read. A consumer that reaches for
    `value_original` on a corrected row repeats that, so the choice lives here
    and not in each caller.
    """
    keys = row.keys() if hasattr(row, "keys") else row
    if "reviewed_value" in keys and row["reviewed_value"] is not None:
        return row["reviewed_value"]
    return row["value_original"]


def effective_fact_normalized(row):
    keys = row.keys() if hasattr(row, "keys") else row
    if "reviewed_value" in keys and row["reviewed_value"] is not None:
        return row["reviewed_value_normalized"]
    return row["value_normalized"]


# The magnitude inside a corrected value, the same shape `facts._NUM` matches.
_CORRECTED_NUMBER = re.compile(r"\d+(?:[.½¾¼/⁄]\d+)?")


def _normalise_corrected(fact_type: str, text: str):
    """The corrected value's number, on the same scale as `value_normalized`.

    Runs the extractor's own `facts._normalise`, imported rather than
    reimplemented: two normalisers for one column is how a corrected `36"` ends
    up publishing 24. It returns None where the extractor would — a value with
    no number in it, or a fact type that carries no scale — and None is already
    an allowed state of the column, so nothing is invented to fill it.
    """
    # Deferred: `facts` imports `store`, and pulling it in at module scope
    # would put a heavier module on the path of every table review too.
    from .facts import _normalise
    m = _CORRECTED_NUMBER.search(text or "")
    if m is None:
        return None
    return _normalise(fact_type, m.group(0), text)[0]


# ------------------------------------------------------------------- submit
def submit_fact_review(conn: sqlite3.Connection, *, fact_id: int, reviewer: str,
                       verdict: str, ref_id: str, value: str | None = None,
                       notes: str | None = None,
                       reviewed_at: str | None = None) -> dict:
    """Record one person's verdict on one flagged fact, and project it.

    Refuses, writing nothing, unless all of these hold:

    * `verdict` is one of `FACT_VERDICTS` — three human verdicts, no machine
      one;
    * `reviewer` is a non-blank name. It is unverifiable here and asserted by
      the caller, exactly as §4 says of a table review, but its absence is the
      difference between "software read this" and "a person confirmed it" and
      an absent one is refused rather than defaulted;
    * the fact exists;
    * `ref_id` is the id this store mints for that fact's element *now*.

    A `corrected` verdict carries the person's value and the other two carry
    none, so the shape of the call cannot silently mean something other than
    the verb the reviewer chose.
    """
    ensure_fact_reviews(conn)
    if verdict not in FACT_VERDICTS:
        raise ReviewRefused(
            "error.malformed_review",
            f"verdict {verdict!r} is not one of {', '.join(FACT_VERDICTS)}. "
            f"Agreement between automated readers is not among them and will "
            f"not be: that was `cross_family_verified`, and it produced 324 "
            f"curation-level-2 facts no person had looked at (G17).")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ReviewRefused(
            "error.missing_reviewer",
            "a review needs a reviewer: the name is the only thing separating "
            "'software read this' from 'a person compared it to the source "
            "image', which is the whole of contract obligation 6")
    reviewer = reviewer.strip()

    row = conn.execute("SELECT * FROM facts WHERE fact_id = ?", (fact_id,)).fetchone()
    if row is None:
        raise ReviewRefused("error.unknown_fact", f"no such fact: {fact_id}")

    if verdict == "corrected":
        if not isinstance(value, str) or not value.strip():
            raise ReviewRefused(
                "error.malformed_review",
                "a `corrected` verdict must carry the value the person read off "
                "the image; without one the correction says only that the fact "
                "is wrong, which is `rejected`")
        value = value.strip()
        if value == row["value_original"]:
            raise ReviewRefused(
                "error.malformed_review",
                f"the correction is identical to what the fact already says "
                f"({value!r}); a correction that changes nothing is an "
                f"acceptance, and recording it as a correction would misreport "
                f"what review found")
    elif value is not None:
        raise ReviewRefused(
            "error.malformed_review",
            f"a `{verdict}` verdict carries no value; pass --value only with "
            f"--correct")

    current = fact_ref_id(conn, fact_id)
    if current is None:
        raise ReviewRefused(
            "error.unknown_fact",
            f"fact {fact_id} names no element in this store, so there is no "
            f"region a person could have compared it to")
    if ref_id != current:
        raise ReviewRefused(
            "error.ref_mismatch",
            f"the echoed ref is not the region this store holds for fact "
            f"{fact_id}: {ref_id!r} echoed, {current!r} held. Either the review "
            f"is of a different fact, or the element was re-extracted and its "
            f"bbox moved (G38) -- in which case the rectangle that was looked "
            f"at no longer exists")

    reviewed_at = reviewed_at or now()
    # The payload is folded into the id for the reason `submit_review` records:
    # `now()` is second-resolution, so fact+reviewer+timestamp collided on a
    # double-submit or an accept-then-immediately-correct, and `INSERT OR
    # REPLACE` then dropped the first review outright. Folding it in keeps the
    # good half -- an identical resubmission still replaces itself.
    payload = json.dumps({"verdict": verdict, "value": value, "notes": notes},
                         sort_keys=True, separators=(",", ":"))
    fact_review_id = hashlib.sha256(
        f"{fact_id}:{ref_id}:{reviewer}:{reviewed_at}:{payload}".encode()
    ).hexdigest()[:16]

    started_here = not conn.in_transaction
    if started_here:
        conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute("""INSERT OR REPLACE INTO fact_reviews
            (fact_review_id, fact_id, ref_id, document_id, page_no, element_id,
             fact_type, reviewer, reviewed_at, verdict, value_before,
             status_before, reviewed_value, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (fact_review_id, fact_id, ref_id, row["document_id"], row["page_no"],
             row["element_id"], row["fact_type"], reviewer, reviewed_at, verdict,
             row["value_original"], row["review_status"], value, notes))
        _project_fact(conn, fact_id=fact_id, verdict=verdict, value=value,
                      fact_type=row["fact_type"], reviewer=reviewer,
                      reviewed_at=reviewed_at)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"fact_review_id": fact_review_id, "fact_id": fact_id,
            "verdict": verdict, "review_status": FACT_STATUS_FOR_VERDICT[verdict],
            "reviewer": reviewer, "reviewed_at": reviewed_at,
            "value_before": row["value_original"], "reviewed_value": value}


def _project_fact(conn: sqlite3.Connection, *, fact_id: int, verdict: str,
                  value: str | None, fact_type: str, reviewer: str,
                  reviewed_at: str) -> None:
    """Write one review's annotations onto the fact. The only writer of them.

    Every column is set on every call, including back to NULL. A later
    acceptance after a correction must clear `reviewed_value`, or the withdrawn
    correction outlives the review that withdrew it and `effective_fact_value`
    keeps answering with it -- G47's shape, in the projection instead of in
    promotion.
    """
    normalized = _normalise_corrected(fact_type, value) if verdict == "corrected" else None
    conn.execute("""UPDATE facts
                       SET review_status = ?, reviewed_value = ?,
                           reviewed_value_normalized = ?, reviewer = ?,
                           reviewed_at = ?
                     WHERE fact_id = ?""",
                 (FACT_STATUS_FOR_VERDICT[verdict], value, normalized,
                  reviewer, reviewed_at, fact_id))


# ------------------------------------------------------------------ rebuild
def rebuild_fact_projection(conn: sqlite3.Connection) -> dict:
    """Regenerate the fact annotations from `fact_reviews` alone.

    Two halves, and the first is the one that makes a rejection reversible.

    **Reset.** Every fact named by a review goes back to the `status_before`
    the *earliest* review of it recorded -- the status it held before anybody
    touched it -- with `reviewer`, `reviewed_at` and both reviewed-value
    columns cleared. Withdraw the record and rebuild, and the fact is where it
    started; nothing is stuck at a status it no longer earns (G47).

    The reset is scoped to facts a review names, never to a status. A fact
    promoted by `table_review.promote` sits at `reviewed` on the strength of a
    row in `table_reviews`, and demoting it here would silently revoke a review
    this function never wrote -- the same reason `REVIEW_STATUSES` exists above.

    **Replay.** Arrival order (`rowid`), not `reviewed_at`, for the reason
    `rebuild_projection` records: a backdated review submitted after a
    later-stamped one wins live, so replaying by timestamp makes the projection
    disagree with its own source.

    A review whose fact no longer exists is counted in `orphaned` and applied
    to nothing. `facts --extract` deletes and re-inserts every `regex-%` fact,
    so this is the expected state after a re-extraction, and it fails in the
    safe direction: the reviews survive as a record, and no fact claims a
    review it cannot show.
    """
    ensure_fact_reviews(conn)
    started_here = not conn.in_transaction
    if started_here:
        conn.execute("BEGIN IMMEDIATE")
    try:
        # `status_before` of the earliest review, per fact. MIN(rowid) picks the
        # first arrival; the correlated subquery reads its status.
        conn.execute("""
            UPDATE facts
               SET review_status = COALESCE((
                       SELECT r.status_before FROM fact_reviews r
                        WHERE r.fact_id = facts.fact_id
                        ORDER BY r.rowid LIMIT 1), review_status),
                   reviewed_value = NULL, reviewed_value_normalized = NULL,
                   reviewer = NULL, reviewed_at = NULL
             WHERE fact_id IN (SELECT fact_id FROM fact_reviews)""")
        # A forged annotation -- a status written straight onto `facts` with no
        # record behind it -- is not reachable through this module, but it is
        # reachable with a SQL client, and a projection that leaves one standing
        # is not a projection. Clear every annotation no review accounts for.
        conn.execute("""
            UPDATE facts
               SET reviewed_value = NULL, reviewed_value_normalized = NULL,
                   reviewer = NULL, reviewed_at = NULL
             WHERE reviewer IS NOT NULL
               AND fact_id NOT IN (SELECT fact_id FROM fact_reviews)""")
        for fid in [r[0] for r in conn.execute("""
                SELECT f.fact_id FROM facts f
                 WHERE f.review_status IN ('reviewed', 'rejected')
                   AND f.from_candidate_id IS NULL
                   AND f.fact_id NOT IN (SELECT fact_id FROM fact_reviews)""")]:
            # Level 2 with nothing behind it. `flagged` rather than `extracted`:
            # these facts are reviewable material, and the honest thing is to
            # put them back in the queue rather than to call them clean.
            conn.execute("UPDATE facts SET review_status='flagged' WHERE fact_id=?",
                         (fid,))

        replayed = applied = orphaned = 0
        for r in conn.execute("SELECT * FROM fact_reviews ORDER BY rowid").fetchall():
            fact_row = conn.execute("SELECT fact_type FROM facts WHERE fact_id=?",
                                    (r["fact_id"],)).fetchone()
            if fact_row is None:
                orphaned += 1
                continue
            _project_fact(conn, fact_id=r["fact_id"], verdict=r["verdict"],
                          value=r["reviewed_value"], fact_type=fact_row["fact_type"],
                          reviewer=r["reviewer"], reviewed_at=r["reviewed_at"])
            replayed += 1
            applied += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"reviews_replayed": replayed, "facts_written": applied,
            "orphaned": orphaned}


# -------------------------------------------------------------------- audit
def reviewed_without_a_reviewer(conn: sqlite3.Connection) -> list[int]:
    """Facts at curation level 2 that no accountable record explains.

    Obligation 6 as a query, and the standing guard that no second path to
    `reviewed` opened. A fact earns the status two ways and only two:

    * `from_candidate_id IS NOT NULL` -- promoted from a table reading whose
      `review_status` was PROMOTABLE, which `table_review.promote` refuses
      unless a person signed it. That gate has its own record and its own
      tests; this function does not second-guess it.
    * a row in `fact_reviews` and a `reviewer` on the fact -- this loop.

    Anything else is a level-2 assertion with nobody behind it, which is
    exactly the 324 facts build-plan A1 un-promoted. Returns their ids, sorted,
    so a caller can print them rather than a boolean.
    """
    ensure_fact_reviews(conn)
    return [r[0] for r in conn.execute("""
        SELECT f.fact_id FROM facts f
         WHERE f.review_status = 'reviewed'
           AND f.from_candidate_id IS NULL
           AND (f.reviewer IS NULL
                OR NOT EXISTS (SELECT 1 FROM fact_reviews r
                                WHERE r.fact_id = f.fact_id
                                  AND r.verdict IN ('accepted', 'corrected')))
         ORDER BY f.fact_id""")]


# -------------------------------------------------------------------- queue
def fact_review_queue(conn: sqlite3.Connection, *, limit: int = 50,
                      fact_type: str | None = None) -> list[dict]:
    """Flagged facts waiting for a person, weakest evidence first.

    Ordered by the page's own OCR confidence ascending: the lower the
    confidence the likelier the digit is wrong, and a misread digit in a
    footing depth is the failure mode this whole pile exists for (G15, G16).

    Every entry carries `ref_id`, so the reviewer can pull the picture with
    `GET /source-refs/{id}`, `cli fact-review --show`, or
    `reviews.fact_source_ref` -- all three the same rectangle, because all
    three mint it with `refs.ref_id`.

    The joins are LEFT joins on purpose. A flagged fact whose element or
    version is missing is *unreviewable*, and dropping it out of the queue
    would hide it; it appears with `ref_id: null` instead, which is a defect to
    report rather than a row to lose.
    """
    sql = """
        SELECT f.fact_id, f.document_id, f.page_no, f.fact_type, f.subject,
               f.value_original, f.value_normalized, f.unit_original,
               f.conditions, f.condition_basis, f.evidence_text, f.extractor,
               f.ocr_derived, e.bbox, e.ocr_confidence, v.sha256,
               d.manufacturer, d.title
          FROM facts f
          LEFT JOIN elements e ON e.element_id = f.element_id
          LEFT JOIN document_versions v ON v.version_id = f.version_id
          LEFT JOIN documents d ON d.document_id = f.document_id
         WHERE f.review_status = ?"""
    args: list = [FACT_QUEUE_STATUS]
    if fact_type:
        sql += " AND f.fact_type = ?"
        args.append(fact_type)
    sql += """ ORDER BY e.ocr_confidence IS NULL DESC, e.ocr_confidence,
                        f.fact_id LIMIT ?"""
    args.append(limit)

    from .refs import ref_id as mint
    out = []
    for r in conn.execute(sql, args):
        row = dict(r)
        row["ref_id"] = (mint(r["sha256"], r["page_no"], r["bbox"])
                         if r["sha256"] is not None else None)
        if row["ref_id"] is None:
            row["blocked"] = ("no element or version row for this fact, so no "
                              "region can be shown and it cannot be reviewed")
        row.pop("sha256", None)
        row["evidence_text"] = (row["evidence_text"] or "")[:240]
        out.append(row)
    return out


def fact_review_summary(conn: sqlite3.Connection) -> dict:
    """What the pile looks like, and who has touched it.

    `reviewers` empty and `reviews` zero is the honest reading of the store
    today: the mechanism exists and nobody has used it. Do not read a summary
    with a non-empty `by_status['reviewed']` and an empty `reviewers` as
    anything but a defect -- `reviewed_without_a_reviewer` names the rows.
    """
    ensure_fact_reviews(conn)
    by_status = {r["review_status"]: r["n"] for r in conn.execute(
        "SELECT review_status, COUNT(*) n FROM facts GROUP BY 1 ORDER BY 1")}
    by_verdict = {r["verdict"]: r["n"] for r in conn.execute(
        "SELECT verdict, COUNT(*) n FROM fact_reviews GROUP BY 1 ORDER BY 1")}
    by_type = {r["fact_type"]: r["n"] for r in conn.execute(
        """SELECT fact_type, COUNT(*) n FROM facts WHERE review_status = ?
            GROUP BY 1 ORDER BY 2 DESC, 1""", (FACT_QUEUE_STATUS,))}
    return {
        "facts": sum(by_status.values()),
        "by_status": by_status,
        "pending": by_status.get(FACT_QUEUE_STATUS, 0),
        "pending_by_type": by_type,
        "reviews": sum(by_verdict.values()),
        "by_verdict": by_verdict,
        "reviewers": [r[0] for r in conn.execute(
            "SELECT DISTINCT reviewer FROM fact_reviews ORDER BY 1")],
        "unaccountable": reviewed_without_a_reviewer(conn),
    }


# ============================================================================
# Re-attachment — a review outlives the row id it was written against.
# ============================================================================
#
# `facts.extract_facts` deletes every `regex-%` fact and re-inserts it, so the
# `fact_id` a review names does not survive a re-extraction. Two things follow.
#
# **`fact_id` is a pointer, and the evidence is the identity.** A review already
# records everything needed to find its fact again without one: the element it
# cites, the fact type, and `value_before` -- the value the person was looking
# at. That triple is the anchor, and it is the same triple the ledger below is
# keyed on. `fact_review_id` is not, because its formula folds in `fact_id`.
#
# **Nothing is guessed.** If the new extraction produces no fact carrying that
# evidence, or more than one, the review keeps the binding it had and is
# reported. A review silently attached to the wrong fact is worse than one left
# unbound: it launders a person's signature onto a value they never saw, and
# `reviewed_without_a_reviewer` cannot see that, because there *is* a reviewer.
#
# One property makes this safe rather than merely careful: `facts.fact_id` is
# `INTEGER PRIMARY KEY AUTOINCREMENT`, so SQLite never reuses an id even after a
# delete. A re-extraction therefore cannot hand an old review a *different*
# fact under its old id; the binding is either intact or plainly missing.
# `tests/test_review_ledger.py` asserts that too.


def _fact_anchor(row) -> tuple[str, str, str]:
    """The evidence a fact review is really about: element, type, value seen."""
    return (row["element_id"], row["fact_type"], row["value_before"])


def _facts_matching(conn: sqlite3.Connection, element_id: str, fact_type: str,
                    value: str, *, exclude=()) -> tuple[list[int], list[str]]:
    """(fact ids carrying exactly this evidence, other values now extracted).

    The second half is the signal G49 asks for: a review whose value the new
    extraction no longer produces means the extractor changed its mind about a
    number a person checked, and that is worth printing rather than counting as
    a plain miss.
    """
    exclude = set(exclude)
    rows = conn.execute("""SELECT fact_id, value_original FROM facts
                            WHERE element_id = ? AND fact_type = ?
                            ORDER BY fact_id""", (element_id, fact_type)).fetchall()
    rows = [r for r in rows if r["fact_id"] not in exclude]
    match = [r["fact_id"] for r in rows if r["value_original"] == value]
    others = sorted({r["value_original"] for r in rows if r["value_original"] != value})
    return match, others


def reattach_fact_reviews(conn: sqlite3.Connection, *, superseded=None,
                          dry_run: bool = False) -> dict:
    """Re-bind fact reviews to the facts a re-extraction produced.

    A review needs a decision when the `fact_id` it names is not in `facts` at
    all -- a store written before `foreign_keys=ON` could reach that -- or when
    the caller has named that row in `superseded`: a reviewed fact `extract_facts`
    kept alive across the delete precisely so the review would not dangle, and
    which the new extraction may have reproduced under a new id.

    Reviews are decided in groups sharing one anchor, because every review of
    one fact shares it (`value_before` is that fact's `value_original`, which no
    review changes). A group is re-bound only when **exactly one** fact now
    carries its evidence *and* the group came from exactly one old fact. Two
    old facts collapsing onto one new row is ambiguous even though the candidate
    is unique: two people signed two rows and only one row remains, so binding
    either signature to it asserts something neither person did.

    Returns counts and, in `detail`, the rows behind each of them. Counted per
    review, not per group, so `reattached + still_orphaned == considered`.
    """
    ensure_fact_reviews(conn)
    superseded = set(superseded or ())
    live = {r[0] for r in conn.execute("SELECT fact_id FROM facts")}
    rows = conn.execute("SELECT * FROM fact_reviews ORDER BY rowid").fetchall()
    need = [r for r in rows
            if r["fact_id"] not in live or r["fact_id"] in superseded]
    need_ids = {r["fact_review_id"] for r in need}
    # A fact some *other* review already binds is not available to be claimed
    # here; taking it would merge two facts' review histories.
    claimed = {r["fact_id"] for r in rows if r["fact_review_id"] not in need_ids}

    groups: dict[tuple, list] = {}
    for r in need:
        groups.setdefault(_fact_anchor(r), []).append(r)

    out = {"considered": len(need), "reattached": 0, "still_orphaned": 0,
           "ambiguous": 0, "value_changed": 0,
           "detail": {"reattached": [], "ambiguous": [], "value_changed": [],
                      "orphaned": []},
           "dry_run": bool(dry_run)}

    started_here = not conn.in_transaction and not dry_run
    if started_here:
        conn.execute("BEGIN IMMEDIATE")
    try:
        for anchor in sorted(groups):
            element_id, fact_type, value_before = anchor
            grp = groups[anchor]
            old_ids = sorted({r["fact_id"] for r in grp})
            candidates, others = _facts_matching(
                conn, element_id, fact_type, value_before,
                exclude=superseded | claimed)
            entry = {"element_id": element_id, "fact_type": fact_type,
                     "value_before": value_before,
                     "fact_review_ids": sorted(r["fact_review_id"] for r in grp),
                     "reviewers": sorted({r["reviewer"] for r in grp}),
                     "was_fact_id": old_ids}
            if len(candidates) == 1 and len(old_ids) == 1:
                new = candidates[0]
                out["reattached"] += len(grp)
                out["detail"]["reattached"].append({**entry, "now_fact_id": new})
                if not dry_run:
                    for r in grp:
                        conn.execute(
                            "UPDATE fact_reviews SET fact_id = ? WHERE fact_review_id = ?",
                            (new, r["fact_review_id"]))
                    old = old_ids[0]
                    if old in superseded and old != new:
                        # The retained copy has done its job: the review now
                        # names the row the current extractor stands behind.
                        conn.execute("DELETE FROM facts WHERE fact_id = ?", (old,))
                continue
            out["still_orphaned"] += len(grp)
            if candidates:
                out["ambiguous"] += len(grp)
                out["detail"]["ambiguous"].append({
                    **entry, "candidates": candidates,
                    "why": ("more than one fact now carries this evidence"
                            if len(candidates) > 1 else
                            "two reviewed facts shared this evidence and one row "
                            "remains, so no signature can be placed on it")})
            elif others:
                out["value_changed"] += len(grp)
                out["detail"]["value_changed"].append({
                    **entry, "now_extracted": others,
                    "why": ("the extractor no longer produces the value a person "
                            "checked; it now reads this element differently")})
            else:
                out["detail"]["orphaned"].append({
                    **entry, "why": ("nothing in the store carries this evidence "
                                     "any more")})
        if started_here:
            conn.commit()
    except Exception:
        if started_here:
            conn.rollback()
        raise
    return out


# ============================================================================
# The ledger — G49. The one artifact in this repository that is authored.
# ============================================================================
#
# Everything else regenerates: `cli ingest` rebuilds elements, `cli facts
# --extract` rebuilds assertions, `cli rebuild-index` rebuilds the projection
# byte-identically. A review is a judgement a person made looking at a page
# image, and it lived only in `workspace/indexes/evidence.db`, which is
# git-ignored, has no backup, and is deleted by any clean rebuild. Obligation 6
# was therefore backed by the least durable artifact in the repository.
#
# Four decisions, each of them the reason a line looks the way it does.
#
# * **JSONL, canonical, sorted.** One review per line so a diff shows a decision
#   rather than a reflowed document, `canonical.canonical_bytes` for the bytes
#   so two exports over identical state are identical, and a sort key made only
#   of fields that do not move. No clock reading of the export itself appears
#   anywhere in the file.
# * **The table half keeps `crop_sha256`.** It is the bytes of the crop, not a
#   row id, so a table review survives re-extraction by construction. That
#   property is preserved here rather than re-derived.
# * **The fact half carries no `fact_id` at all.** A fact id moves on every
#   re-extraction, so writing one into a committed file would make the ledger
#   un-replayable within a day. The line carries the anchor instead --
#   `element_id`, `fact_type`, `value_before` -- and import resolves it against
#   whatever ids the target store minted, using the same rule
#   `reattach_fact_reviews` uses and refusing in the same places.
# * **Import never overwrites a decision.** A line whose id is already in the
#   store and whose content matches is a no-op, which is what makes replay
#   idempotent. A line whose content *differs* is a conflict between two
#   people's records, and the whole import is refused: last-write-wins on a
#   human sign-off is the failure obligation 6 exists to prevent.
#
# What this does NOT establish. A ledger is a record, not an attestation: it
# says a store held these reviews, never that the named person made them.
# `reviewer` is asserted by the caller and unverifiable here, exactly as §4 of
# the Phase 2 design says of a table review. See G46.

LEDGER_PATH = CATALOG_DIR / "review-ledger.jsonl"
LEDGER_SCHEMA = 1
LEDGER_HEADER_KIND = "ledger"
KIND_TABLE_REVIEW = "table_review"
KIND_FACT_REVIEW = "fact_review"

_TABLE_REVIEW_COLUMNS = ("review_id", "crop_sha256", "document_id", "page_no",
                         "reviewer", "reviewed_at", "verdict", "grid", "spans",
                         "from_candidates", "notes")
_TABLE_REVIEW_JSON = ("grid", "spans", "from_candidates")
# `fact_id` is deliberately absent: it is the one column that moves.
_FACT_REVIEW_COLUMNS = ("fact_review_id", "ref_id", "document_id", "page_no",
                        "element_id", "fact_type", "reviewer", "reviewed_at",
                        "verdict", "value_before", "status_before",
                        "reviewed_value", "notes")


def _table_review_record(row) -> dict:
    rec = {"kind": KIND_TABLE_REVIEW}
    for col in _TABLE_REVIEW_COLUMNS:
        rec[col] = row[col]
    for col in _TABLE_REVIEW_JSON:
        # Parsed, not carried as an escaped string: a ledger nobody can read is
        # not an audit trail. Re-serialising through `canonical_bytes` on the
        # way out is what makes the representation single-valued, so two stores
        # that spell the same grid differently still export identical bytes.
        rec[col] = json.loads(row[col] or "[]")
    return rec


def _fact_review_record(row) -> dict:
    rec = {"kind": KIND_FACT_REVIEW}
    for col in _FACT_REVIEW_COLUMNS:
        rec[col] = row[col]
    return rec


def _ledger_sort_key(rec):
    if rec["kind"] == KIND_TABLE_REVIEW:
        return (rec["kind"], rec["crop_sha256"], rec["reviewed_at"], rec["review_id"])
    return (rec["kind"], rec["element_id"], rec["fact_type"],
            rec["value_before"] or "", rec["reviewed_at"], rec["fact_review_id"])


def build_ledger(conn: sqlite3.Connection) -> list[dict]:
    """Every review in this store, as the lines of its ledger.

    Line 0 is a header. An empty ledger is then one line saying so, rather than
    an empty file -- a zero-byte artifact reads as an oversight, and *"no review
    has been recorded in this store"* is a statement worth committing.
    """
    ensure_fact_reviews(conn)
    body = [_table_review_record(r) for r in
            conn.execute("SELECT * FROM table_reviews")]
    facts = [_fact_review_record(r) for r in
             conn.execute("SELECT * FROM fact_reviews")]
    body.extend(facts)
    body.sort(key=_ledger_sort_key)
    header = {"kind": LEDGER_HEADER_KIND, "schema": LEDGER_SCHEMA,
              "fact_reviews": len(facts), "table_reviews": len(body) - len(facts)}
    return [header] + body


def ledger_bytes(records: list[dict]) -> bytes:
    """The one serialisation of a ledger: canonical JSON, one object per line."""
    return b"".join(canonical_bytes(r) + b"\n" for r in records)


def export_reviews(conn: sqlite3.Connection, path=None) -> dict:
    """Write the ledger and report what was written.

    `path` defaults to the committed location; a caller -- a test, or a build
    that wants to inspect the output before it lands -- can point it anywhere
    inside `workspace/`. The write goes through `paths.open_write`, so a path
    outside raises `CorpusWriteError` and nothing is written. Same treatment as
    `distribution.write_manifest`, for the same reason.
    """
    target = Path(path) if path is not None else LEDGER_PATH
    records = build_ledger(conn)
    payload = ledger_bytes(records)
    with open_write(target, "wb") as fh:
        fh.write(payload)
    header = records[0]
    return {"path": rel(target), "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "table_reviews": header["table_reviews"],
            "fact_reviews": header["fact_reviews"]}


def read_ledger(path) -> tuple[dict, list[dict]]:
    """Parse a ledger, refusing anything that is not one.

    The header's counts are checked against the body. They are redundant with
    it, which is the point: a hand-edited ledger that dropped a line says so
    here rather than importing quietly.
    """
    p = Path(path)
    if not p.is_file():
        raise ReviewRefused("error.malformed_ledger", f"no ledger at {p}")
    lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not lines:
        raise ReviewRefused("error.malformed_ledger",
                            f"{p} is empty; even a store with no reviews has a "
                            f"header line")
    try:
        parsed = [json.loads(l) for l in lines]
    except json.JSONDecodeError as e:
        raise ReviewRefused("error.malformed_ledger", f"{p}: {e}") from None
    header = parsed[0]
    if not isinstance(header, dict) or header.get("kind") != LEDGER_HEADER_KIND:
        raise ReviewRefused("error.malformed_ledger",
                            f"{p} does not begin with a ledger header")
    if header.get("schema") != LEDGER_SCHEMA:
        raise ReviewRefused(
            "error.malformed_ledger",
            f"{p} is schema {header.get('schema')!r}; this build reads "
            f"{LEDGER_SCHEMA}")
    body = parsed[1:]
    counts = {KIND_TABLE_REVIEW: 0, KIND_FACT_REVIEW: 0}
    for i, rec in enumerate(body, start=2):
        if not isinstance(rec, dict):
            raise ReviewRefused("error.malformed_ledger",
                                f"{p} line {i} is not an object")
        kind = rec.get("kind")
        if kind not in counts:
            raise ReviewRefused("error.malformed_ledger",
                                f"{p} line {i} has kind {kind!r}")
        required = (_TABLE_REVIEW_COLUMNS if kind == KIND_TABLE_REVIEW
                    else _FACT_REVIEW_COLUMNS)
        missing = [c for c in required if c not in rec]
        if missing:
            raise ReviewRefused("error.malformed_ledger",
                                f"{p} line {i} is missing {', '.join(missing)}")
        if kind == KIND_FACT_REVIEW and "fact_id" in rec:
            raise ReviewRefused(
                "error.malformed_ledger",
                f"{p} line {i} carries a fact_id. A fact id moves on every "
                f"re-extraction and is resolved from the evidence on import; "
                f"a ledger that names one is describing a store, not a review")
        counts[kind] += 1
    for kind, key in ((KIND_TABLE_REVIEW, "table_reviews"),
                      (KIND_FACT_REVIEW, "fact_reviews")):
        if header.get(key) != counts[kind]:
            raise ReviewRefused(
                "error.malformed_ledger",
                f"{p} header says {header.get(key)!r} {key} and the body holds "
                f"{counts[kind]}")
    return header, body


def _differences(ledger_rec: dict, store_rec: dict) -> dict:
    return {k: {"ledger": ledger_rec.get(k), "store": store_rec.get(k)}
            for k in sorted(set(ledger_rec) | set(store_rec))
            if ledger_rec.get(k) != store_rec.get(k)}


def import_reviews(conn: sqlite3.Connection, path, *, dry_run: bool = True) -> dict:
    """Replay a ledger into this store. Dry run unless told otherwise.

    Three outcomes per line, and only the first writes anything:

    * **new** -- the id is not in this store. A table review lands as it is; a
      fact review's `fact_id` is resolved from its anchor, by the rule
      `reattach_fact_reviews` uses. An anchor naming no fact, or more than one,
      is `unresolvable`: reported, skipped, never guessed at.
    * **identical** -- the id is here and says the same thing. Skipped, which is
      what makes a replay idempotent.
    * **conflict** -- the id is here and says something *else*. Two records of
      one person's decision disagree, and that is for a person to resolve. The
      whole import is refused; nothing at all is written, including the lines
      that would have been fine.

    On success the projections are rebuilt from the records, so the store's
    `facts` and `table_read_candidates` annotations follow the reviews rather
    than being asserted twice.
    """
    header, body = read_ledger(path)
    ensure_fact_reviews(conn)

    inserts: list[tuple[str, dict, int | None]] = []
    identical = conflicts = unresolvable = 0
    detail: dict[str, list] = {"conflicts": [], "unresolvable": []}

    for rec in body:
        if rec["kind"] == KIND_TABLE_REVIEW:
            existing = conn.execute("SELECT * FROM table_reviews WHERE review_id = ?",
                                    (rec["review_id"],)).fetchone()
            if existing is not None:
                differs = _differences(rec, _table_review_record(existing))
                if differs:
                    conflicts += 1
                    detail["conflicts"].append({"kind": rec["kind"],
                                                "id": rec["review_id"],
                                                "differs": differs})
                else:
                    identical += 1
                continue
            inserts.append((KIND_TABLE_REVIEW, rec, None))
            continue

        existing = conn.execute("SELECT * FROM fact_reviews WHERE fact_review_id = ?",
                                (rec["fact_review_id"],)).fetchone()
        if existing is not None:
            differs = _differences(rec, _fact_review_record(existing))
            if differs:
                conflicts += 1
                detail["conflicts"].append({"kind": rec["kind"],
                                            "id": rec["fact_review_id"],
                                            "differs": differs})
            else:
                identical += 1
            continue
        candidates, others = _facts_matching(conn, rec["element_id"],
                                             rec["fact_type"], rec["value_before"])
        if len(candidates) != 1:
            unresolvable += 1
            detail["unresolvable"].append({
                "kind": rec["kind"], "id": rec["fact_review_id"],
                "element_id": rec["element_id"], "fact_type": rec["fact_type"],
                "value_before": rec["value_before"], "candidates": candidates,
                "now_extracted": others,
                "why": ("no fact in this store carries that evidence"
                        if not candidates else
                        "more than one fact carries that evidence, and binding "
                        "the review to either would assert what the reviewer "
                        "did not")})
            continue
        inserts.append((KIND_FACT_REVIEW, rec, candidates[0]))

    out = {"records": len(body), "inserted": len(inserts), "identical": identical,
           "conflicts": conflicts, "unresolvable": unresolvable,
           "applied": False, "refused": bool(conflicts), "detail": detail,
           "projection": None, "dry_run": bool(dry_run)}
    if dry_run or conflicts:
        return out

    started_here = not conn.in_transaction
    if started_here:
        conn.execute("BEGIN IMMEDIATE")
    try:
        for kind, rec, fact_id in inserts:
            if kind == KIND_TABLE_REVIEW:
                conn.execute("""INSERT INTO table_reviews
                    (review_id, crop_sha256, document_id, page_no, reviewer,
                     reviewed_at, verdict, grid, spans, from_candidates, notes)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (rec["review_id"], rec["crop_sha256"], rec["document_id"],
                     rec["page_no"], rec["reviewer"], rec["reviewed_at"],
                     rec["verdict"], json.dumps(rec["grid"]),
                     json.dumps(rec["spans"]), json.dumps(rec["from_candidates"]),
                     rec["notes"]))
            else:
                conn.execute("""INSERT INTO fact_reviews
                    (fact_review_id, fact_id, ref_id, document_id, page_no,
                     element_id, fact_type, reviewer, reviewed_at, verdict,
                     value_before, status_before, reviewed_value, notes)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (rec["fact_review_id"], fact_id, rec["ref_id"],
                     rec["document_id"], rec["page_no"], rec["element_id"],
                     rec["fact_type"], rec["reviewer"], rec["reviewed_at"],
                     rec["verdict"], rec["value_before"], rec["status_before"],
                     rec["reviewed_value"], rec["notes"]))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    out["applied"] = True
    out["projection"] = {"tables": rebuild_projection(conn),
                         "facts": rebuild_fact_projection(conn)}
    return out


# ------------------------------------------------- step reviews (the slice)
# The vocabularies a reviewer may choose from, straight out of
# `knowledge-datamodel.md` §3.6. Closed sets: a value outside them cannot be
# published, so it is refused at the door rather than at the wire.
STEP_KINDS = ("assembly", "installation", "preparation", "part_modification",
              "maintenance")
STEP_SCOPES = ("panel", "bay", "post", "run", "site")
STEP_VERDICTS = ("accepted", "corrected", "rejected")
STEP_STATUS_FOR_VERDICT = {"accepted": "accepted", "corrected": "corrected",
                           "rejected": "rejected"}
# What a rebuild may overwrite. `unreviewed` is the default a candidate is born
# with; anything else here was written by a review and only a review may move
# it. Same reasoning as REVIEW_STATUSES for the table loop.
STEP_STATUSES = tuple(STEP_STATUS_FOR_VERDICT.values())


def ensure_step_reviews(conn: sqlite3.Connection) -> None:
    """Create `step_reviews` if this store predates it."""
    from .store import STEP_REVIEWS_DDL
    conn.executescript(STEP_REVIEWS_DDL)


def _step_anchor(element_id: str, char_start: int, char_end: int) -> tuple:
    """The evidence a step review is about: a span of one element.

    NOT `candidate_id`. The splitter re-runs and re-mints every id -- four times
    in one day on the slice page -- so a review keyed on a row id would be
    silently orphaned by an ordinary re-proposal.
    """
    return (element_id, char_start, char_end)


def submit_step_review(conn: sqlite3.Connection, *, element_id: str,
                       char_start: int, char_end: int, text_seen: str,
                       reviewer: str, verdict: str, step_kind: str | None = None,
                       step_scope: str | None = None,
                       slot_target: dict | None = None,
                       text_final: str | None = None,
                       notes: str | None = None) -> dict:
    """Record one person's judgement about one step candidate.

    Refuses rather than guesses: a blank reviewer, a verdict outside
    `STEP_VERDICTS`, a `kind`/`scope` outside the published vocabularies, an
    anchor naming no candidate, or text that is not what the candidate holds
    now. That last is the echo check -- if the splitter has moved since the
    person looked, the review is of something that no longer exists.
    """
    from .store import now
    ensure_step_reviews(conn)
    if not (reviewer or "").strip():
        raise ReviewRefused(
            "error.missing_reviewer",
            "a step review needs a reviewer: the name is the only thing "
            "separating 'software read this' from 'a person confirmed it'")
    if verdict not in STEP_VERDICTS:
        raise ReviewRefused(
            "error.bad_verdict",
            f"verdict must be one of {', '.join(STEP_VERDICTS)}; got {verdict!r}. "
            f"No machine verdict belongs here -- that is what A1/C0 revoked.")
    if step_kind is not None and step_kind not in STEP_KINDS:
        raise ReviewRefused("error.bad_step_kind",
                            f"kind must be one of {', '.join(STEP_KINDS)}")
    if step_scope is not None and step_scope not in STEP_SCOPES:
        raise ReviewRefused("error.bad_step_scope",
                            f"scope must be one of {', '.join(STEP_SCOPES)}")

    row = conn.execute(
        """SELECT * FROM step_candidates
            WHERE element_id=? AND char_start=? AND char_end=?""",
        _step_anchor(element_id, char_start, char_end)).fetchone()
    if row is None:
        raise ReviewRefused(
            "error.no_such_candidate",
            f"no step candidate at {element_id} chars {char_start}-{char_end}")
    if row["text_raw"] != text_seen:
        raise ReviewRefused(
            "error.text_moved",
            f"the candidate at {element_id} chars {char_start}-{char_end} no "
            f"longer holds the text this review is about; it was re-cut after "
            f"the reviewer looked, so the review is of something that is gone")

    reviewed_at = now()
    payload = json.dumps({"verdict": verdict, "kind": step_kind,
                          "scope": step_scope, "slot": slot_target,
                          "text": text_final, "notes": notes},
                         sort_keys=True, separators=(",", ":"))
    # The payload is folded into the id for the reason `review_id` folds it in:
    # `now()` has one-second resolution, so two submissions in one second would
    # otherwise collide and INSERT OR REPLACE would drop the first.
    step_review_id = hashlib.sha256(
        f"{element_id}:{char_start}:{char_end}:{reviewer}:{reviewed_at}:{payload}"
        .encode()).hexdigest()[:16]

    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            """INSERT OR REPLACE INTO step_reviews
               (step_review_id, element_id, char_start, char_end, text_seen,
                document_id, page_no, reviewer, reviewed_at, verdict, step_kind,
                step_scope, slot_target, text_final, status_before, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (step_review_id, element_id, char_start, char_end, text_seen,
             row["document_id"], row["page_no"], reviewer, reviewed_at, verdict,
             step_kind, step_scope,
             json.dumps(slot_target, sort_keys=True) if slot_target else None,
             text_final, row["review_status"], notes))
        _project_step(conn, element_id, char_start, char_end,
                      STEP_STATUS_FOR_VERDICT[verdict], reviewer, reviewed_at)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return {"step_review_id": step_review_id, "verdict": verdict,
            "reviewer": reviewer, "reviewed_at": reviewed_at}


def _project_step(conn, element_id, char_start, char_end, status, reviewer,
                  reviewed_at) -> None:
    """The ONLY writer of the projection columns. Sets every one on every call,
    including back to NULL, so a rebuild cannot leave a stale half-state."""
    conn.execute(
        """UPDATE step_candidates
              SET review_status=?, reviewer=?, reviewed_at=?
            WHERE element_id=? AND char_start=? AND char_end=?""",
        (status, reviewer, reviewed_at, element_id, char_start, char_end))


def rebuild_step_projection(conn: sqlite3.Connection) -> dict:
    """Regenerate the projection from `step_reviews` alone.

    This is what makes a review survive a re-cut of the queue: the candidates
    are rebuildable, the reviews are not, and the anchor is evidence rather
    than a row id. Replays in arrival order, so the last word wins.
    """
    ensure_step_reviews(conn)
    conn.execute(
        f"""UPDATE step_candidates SET review_status='unreviewed',
                   reviewer=NULL, reviewed_at=NULL
             WHERE review_status IN ({','.join('?' * len(STEP_STATUSES))})""",
        STEP_STATUSES)
    applied = orphaned = 0
    for r in conn.execute("""SELECT * FROM step_reviews ORDER BY rowid"""):
        hit = conn.execute(
            """SELECT 1 FROM step_candidates
                WHERE element_id=? AND char_start=? AND char_end=?""",
            (r["element_id"], r["char_start"], r["char_end"])).fetchone()
        if hit is None:
            orphaned += 1
            continue
        _project_step(conn, r["element_id"], r["char_start"], r["char_end"],
                      STEP_STATUS_FOR_VERDICT[r["verdict"]], r["reviewer"],
                      r["reviewed_at"])
        applied += 1
    conn.commit()
    return {"applied": applied, "orphaned": orphaned}
