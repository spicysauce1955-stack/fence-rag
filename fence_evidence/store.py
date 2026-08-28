"""Canonical evidence store (SQLite) and the rebuildable retrieval projection.

Canonical tables (``documents`` … ``quality_issues``) hold what was actually in
the source.  ``retrieval_units`` and ``retrieval_fts`` are a *projection*: they
can be dropped and rebuilt from canonical rows at any time without
re-extracting anything, and nothing outside this module may write to them.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .ids import element_id_for, page_id_for, version_id_for
from .model import ExtractedDocument
from .lang import detect_lang
from .paths import EVIDENCE_DB, ensure_writable

SCHEMA_VERSION = 5

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY, value TEXT NOT NULL);

-- ---------------------------------------------------------------- canonical
CREATE TABLE IF NOT EXISTS documents (
    document_id     TEXT PRIMARY KEY,
    source_path     TEXT NOT NULL UNIQUE,
    file_type       TEXT NOT NULL,
    corpus_track    TEXT NOT NULL,              -- us | china
    manufacturer    TEXT,
    product_family  TEXT,
    doc_type        TEXT,
    title           TEXT,
    source_url      TEXT,
    date_or_version TEXT,
    issue_date      TEXT,
    expiration_date TEXT,
    version_status  TEXT NOT NULL DEFAULT 'unknown',   -- active|superseded|unknown
    version_status_basis TEXT,
    structural      INTEGER NOT NULL DEFAULT 0,
    in_curated_index INTEGER NOT NULL DEFAULT 0
);

-- One EDITION of one document: (bytes x toolchain), not bytes alone.
--
-- G38. `refs.ref_id` is sha256(content_hash:page_no:bbox). Two of those three
-- inputs are permanent; `bbox` is a *measurement* made by
-- `pdftotext -bbox-layout`. `version_exists()` below has always judged a
-- version's identity as bytes x toolchain -- "this exact content was already
-- extracted by these exact tools" -- but the fingerprint half of that judgement
-- lived only in the guard, never in the row. So a poppler upgrade that moves a
-- bbox by 0.02pt (measured: cd9f0d9d9c4e300f -> e25f68cec20de1bc) did not skip,
-- and `write_extracted` deleted the canonical rows the old ids named. A
-- published citation does not get re-pointed at wrong pixels; it stops
-- resolving -- and a snapshot is immutable, so it can never be repaired.
--
-- The fix is not a better hash. Measured over all 81,794 elements, `sha:page:text`
-- yields FEWER distinct ids (56,090 vs 69,306) and 6,660 `figure` elements have
-- no text at all. A sub-page identifier cannot be stable across re-extraction
-- because the rectangle it names is itself produced by extraction. So the store
-- honours what the id already assumes instead: new bytes -> new row, new
-- toolchain -> new row. Both change cases, one rule. Old rows and therefore old
-- ref_ids survive.
--
-- `tool_fingerprint` is denormalised from `extraction_runs`. It has to be a
-- column on THIS table because the UNIQUE constraint is what admits or forbids a
-- second edition, and a constraint cannot reach through a join. It is nullable
-- only for rows written before this column existed; `backfill_tool_fingerprint`
-- fills them from the run they name, and every read here goes through
-- COALESCE(v.tool_fingerprint, r.tool_fingerprint) so a store that has not been
-- migrated still answers correctly rather than declaring every document stale
-- and re-extracting the corpus.
--
-- `edition` is a per-(document, bytes) ordinal, 1 for everything that predates
-- editions. It exists so "which edition is current" has a total order that does
-- not depend on `ingested_at`, whose one-second resolution can tie.
CREATE TABLE IF NOT EXISTS document_versions (
    version_id      TEXT PRIMARY KEY,
    document_id     TEXT NOT NULL REFERENCES documents(document_id),
    sha256          TEXT NOT NULL,
    file_size_bytes INTEGER,
    page_count      INTEGER,
    ingested_at     TEXT NOT NULL,
    extraction_run_id TEXT REFERENCES extraction_runs(run_id),
    tool_fingerprint TEXT,
    edition         INTEGER NOT NULL DEFAULT 1,
    UNIQUE(document_id, sha256, tool_fingerprint)
);

CREATE TABLE IF NOT EXISTS extraction_runs (
    run_id          TEXT PRIMARY KEY,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    tool_versions   TEXT NOT NULL,        -- JSON
    tool_fingerprint TEXT NOT NULL,       -- hash of tool_versions, for idempotency
    pipeline_version TEXT NOT NULL,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS pages (
    page_id         TEXT PRIMARY KEY,
    version_id      TEXT NOT NULL REFERENCES document_versions(version_id),
    page_no         INTEGER NOT NULL,
    width           REAL NOT NULL,
    height          REAL NOT NULL,
    extraction_method TEXT NOT NULL,
    page_image_path TEXT,
    page_image_dpi  INTEGER,
    text_char_count INTEGER NOT NULL DEFAULT 0,
    has_text_layer  INTEGER NOT NULL DEFAULT 0,
    ocr_mean_confidence REAL,
    notes           TEXT,
    UNIQUE(version_id, page_no)
);

CREATE TABLE IF NOT EXISTS elements (
    element_id      TEXT PRIMARY KEY,
    page_id         TEXT NOT NULL REFERENCES pages(page_id),
    version_id      TEXT NOT NULL REFERENCES document_versions(version_id),
    document_id     TEXT NOT NULL REFERENCES documents(document_id),
    page_no         INTEGER NOT NULL,
    ordinal         INTEGER NOT NULL,
    element_type    TEXT NOT NULL,
    text            TEXT NOT NULL DEFAULT '',     -- source layer; OCR never writes here
    ocr_text        TEXT,                         -- OCR only
    text_source     TEXT NOT NULL,
    ocr_confidence  REAL,
    heading_level   INTEGER,
    heading_path    TEXT NOT NULL DEFAULT '[]',   -- JSON array
    caption         TEXT,
    bbox            TEXT,                         -- JSON [x0,y0,x1,y1]
    region_image_path TEXT,
    -- BCP-47 tag and how we know it. Obligation 10 requires `lang` and forbids
    -- normalising it; `lang_basis` keeps the assumption visible rather than
    -- letting `en` look like a measurement. Never derive lang from
    -- corpus_track: that axis is a standards regime (GB vs ASTM), not a
    -- language, and every China-track element measured here is English.
    lang            TEXT,
    lang_basis      TEXT,
    extra           TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS ix_elements_page ON elements(page_id, ordinal);
CREATE INDEX IF NOT EXISTS ix_elements_doc  ON elements(document_id, page_no);
CREATE INDEX IF NOT EXISTS ix_elements_type ON elements(element_type);

CREATE TABLE IF NOT EXISTS tables (
    table_id        TEXT PRIMARY KEY,
    element_id      TEXT NOT NULL REFERENCES elements(element_id),
    n_rows          INTEGER NOT NULL,
    n_cols          INTEGER NOT NULL,
    detector        TEXT NOT NULL,
    bbox            TEXT
);

CREATE TABLE IF NOT EXISTS table_cells (
    table_id        TEXT NOT NULL REFERENCES tables(table_id),
    row             INTEGER NOT NULL,
    col             INTEGER NOT NULL,
    rowspan         INTEGER NOT NULL DEFAULT 1,
    colspan         INTEGER NOT NULL DEFAULT 1,
    text            TEXT NOT NULL,
    bbox            TEXT,
    PRIMARY KEY (table_id, row, col)
);

CREATE TABLE IF NOT EXISTS assets (
    asset_id        TEXT PRIMARY KEY,
    document_id     TEXT NOT NULL REFERENCES documents(document_id),
    version_id      TEXT NOT NULL REFERENCES document_versions(version_id),
    page_no         INTEGER,
    element_id      TEXT,
    asset_type      TEXT NOT NULL,       -- page_image | region_image
    path            TEXT NOT NULL,
    sha256          TEXT,
    bytes           INTEGER,
    width_px        INTEGER,
    height_px       INTEGER
);
CREATE INDEX IF NOT EXISTS ix_assets_doc ON assets(document_id, page_no);

CREATE TABLE IF NOT EXISTS relations (
    relation_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    from_document_id TEXT NOT NULL REFERENCES documents(document_id),
    to_document_id   TEXT NOT NULL REFERENCES documents(document_id),
    relation_type   TEXT NOT NULL,   -- supersedes | superseded_by | same_content_as | same_product_as
    basis           TEXT,
    confidence      REAL,
    UNIQUE(from_document_id, to_document_id, relation_type)
);

CREATE TABLE IF NOT EXISTS quality_issues (
    issue_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id     TEXT REFERENCES documents(document_id),
    version_id      TEXT,
    page_no         INTEGER,
    element_id      TEXT,
    severity        TEXT NOT NULL,
    kind            TEXT NOT NULL,
    detail          TEXT,
    detected_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_issues_doc ON quality_issues(document_id, kind);

-- ------------------------------------------------------------- derived
CREATE TABLE IF NOT EXISTS retrieval_units (
    unit_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id     TEXT NOT NULL,
    version_id      TEXT NOT NULL,
    page_no         INTEGER NOT NULL,
    element_id      TEXT NOT NULL,
    element_ids     TEXT NOT NULL,       -- JSON list of contributing elements
    element_type    TEXT NOT NULL,
    text            TEXT NOT NULL,
    text_source     TEXT NOT NULL,
    heading_path    TEXT NOT NULL,
    bbox            TEXT,
    built_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_units_doc ON retrieval_units(document_id, page_no);

CREATE VIRTUAL TABLE IF NOT EXISTS retrieval_fts USING fts5(
    text, heading_path, title, manufacturer, doc_type,
    tokenize = "unicode61 remove_diacritics 2"
);

-- ------------------------------- table reading candidates (review-gated)
--
-- Readings of a scanned table, from any reader: an agent looking at the page
-- image, a future per-cell OCR pass, or a person. Nothing here is a fact. A row
-- becomes a fact only through fence_evidence.table_review.promote, which
-- refuses any status other than 'accepted' or 'corrected' — and in particular
-- refuses 'agent_verified', because two agents agreeing is a better reading,
-- not an accountable review.
CREATE TABLE IF NOT EXISTS table_read_candidates (
    candidate_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id     TEXT NOT NULL REFERENCES documents(document_id),
    version_id      TEXT NOT NULL,
    page_no         INTEGER NOT NULL,
    crop_path       TEXT NOT NULL,
    crop_sha256     TEXT,
    reader          TEXT NOT NULL,
    reader_kind     TEXT NOT NULL,          -- agent | ocr | human
    is_table        INTEGER,
    table_kind      TEXT,
    row_index       INTEGER,
    col_index       INTEGER,
    row_label       TEXT,
    col_label       TEXT,
    value           TEXT,
    illegible       INTEGER NOT NULL DEFAULT 0,
    reading_confidence TEXT,
    notes           TEXT,
    review_status   TEXT NOT NULL DEFAULT 'unreviewed',
    reviewed_value  TEXT,
    reviewer        TEXT,
    reviewed_at     TEXT,
    created_at      TEXT NOT NULL,
    UNIQUE(document_id, page_no, reader, row_index, col_index)
);
CREATE INDEX IF NOT EXISTS ix_trc_page ON table_read_candidates(document_id, page_no);
CREATE INDEX IF NOT EXISTS ix_trc_status ON table_read_candidates(review_status);

-- One human review of one table crop. The record; the annotations on
-- table_read_candidates are a projection of it, written in the same transaction
-- and regenerable by `cli review --rebuild`.
--
-- `spans` is the field the queue never had. The HVHZ applicability bracket and a
-- merged row-label band ("Up to 48\"" covering two rows) are the same shape -- a
-- value covering a range of rows -- and neither a per-cell nor a per-table column
-- can hold one honestly. It is what G41 discards: rowspan/colspan are never
-- written, so every one of the 18,472 cells claims to be 1x1.
--
-- `from_candidates` points DOWN, at the readings this was derived from. Nothing
-- on table_read_candidates points back up; that was `promoted_fact_id`, and
-- tests/test_pointer_direction.py forbids it.
CREATE TABLE IF NOT EXISTS table_reviews (
    review_id       TEXT PRIMARY KEY,
    crop_sha256     TEXT NOT NULL,
    document_id     TEXT NOT NULL REFERENCES documents(document_id),
    page_no         INTEGER NOT NULL,
    reviewer        TEXT NOT NULL,          -- asserted by Planning; unverifiable here
    reviewed_at     TEXT NOT NULL,
    verdict         TEXT NOT NULL,          -- accepted | rejected | bracket_unclear
    grid            TEXT NOT NULL,          -- JSON [{row, col, value}]
    spans           TEXT NOT NULL,          -- JSON [{row_from, row_to, col, text}]
    from_candidates TEXT NOT NULL,          -- JSON [candidate_id]
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS ix_treviews_crop ON table_reviews(crop_sha256);
CREATE INDEX IF NOT EXISTS ix_treviews_page ON table_reviews(document_id, page_no);

-- ------------------------------------------------------------- phase 6
CREATE TABLE IF NOT EXISTS facts (
    fact_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id     TEXT NOT NULL REFERENCES documents(document_id),
    version_id      TEXT NOT NULL,
    page_no         INTEGER NOT NULL,
    element_id      TEXT NOT NULL REFERENCES elements(element_id),
    fact_type       TEXT NOT NULL,
    subject         TEXT,
    value_original  TEXT NOT NULL,
    value_normalized REAL,
    unit_original   TEXT,
    unit_normalized TEXT,
    conditions      TEXT NOT NULL DEFAULT '{}',
    -- Obligation 15: a row states whether its conditions came from the source.
    --   stated     : the document gave them -- including giving none, which
    --                makes the row an explicit fallback
    --   assumed    : we inferred them, and a person could disagree
    --   unexamined : nobody looked. The regex matched a number and never asked
    --                what scoped it. Publishes as `assumed`; kept distinct here
    --                so the store does not assert an inference it never made.
    condition_basis TEXT NOT NULL DEFAULT 'unexamined',
    condition_basis_note TEXT,
    -- Obligation 4: where a source states two units and they disagree, publish
    -- both. JSON [{value_original, unit_original, value_normalized,
    -- unit_normalized}]. The primary pair above stays the primary pair.
    value_alternates TEXT,
    -- The reading this fact was promoted from, where it came from one. Points
    -- DOWN, at the evidence -- never the reverse. `table_read_candidates` used
    -- to carry `promoted_fact_id` instead, which had to be NULLed by hand on
    -- every delete and could dangle; a real foreign key cannot.
    from_candidate_id INTEGER REFERENCES table_read_candidates(candidate_id),
    evidence_text   TEXT NOT NULL,
    extractor       TEXT NOT NULL,
    ocr_derived     INTEGER NOT NULL DEFAULT 0,
    -- extracted        : found by the regex extractor, unchecked
    -- flagged          : read from low-confidence OCR; needs checking
    -- reviewed         : a person accepted or corrected it
    -- rejected         : checked and wrong
    review_status   TEXT NOT NULL DEFAULT 'extracted',
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_facts_doc ON facts(document_id, fact_type);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# Columns added after a table first shipped. SCHEMA above is authoritative for a
# NEW store; this list is what an EXISTING one is missing, because `migrate()` is
# CREATE TABLE IF NOT EXISTS and a table that already exists silently ignores its
# new columns. Every entry must also appear in SCHEMA, or a fresh store ends up
# without a column a migrated one has. tests/test_migration.py asserts the two
# agree on the SET of columns -- not on their ORDER, which genuinely does differ:
# ALTER appends, so a migrated `facts` carries the new columns at the end while a
# fresh one has them next to `conditions`. Nothing reads these tables
# positionally (every SELECT * goes through sqlite3.Row), so the difference is
# invisible -- but `dict(row)` key order is store-history-dependent, so never
# byte-compare serialised rows between a migrated and a re-ingested store.
# Additive only: no drops, no renames, no type changes. Those need a rebuild.
ADDED_COLUMNS = [
    # schema_version 2 -- build-plan A2/A3/A4
    ("elements", "lang", "TEXT"),
    ("elements", "lang_basis", "TEXT"),
    ("facts", "condition_basis", "TEXT NOT NULL DEFAULT 'unexamined'"),
    ("facts", "condition_basis_note", "TEXT"),
    ("facts", "value_alternates", "TEXT"),
    # schema_version 3 -- pointer direction: a fact names its reading, not the
    # reverse. The REFERENCES clause is carried here too, so a migrated store
    # gets the same declared foreign key as a fresh one rather than a soft link
    # (SQLite accepts it on ADD COLUMN as long as the default is NULL).
    ("facts", "from_candidate_id",
     "INTEGER REFERENCES table_read_candidates(candidate_id)"),
    # schema_version 5 -- G38, extraction editions. Both are plain ADD COLUMNs;
    # the part of this migration that ALTER cannot do -- widening
    # UNIQUE(document_id, sha256) to include tool_fingerprint -- is
    # `ensure_edition_unique` below, because SQLite has no DROP CONSTRAINT.
    # `edition` carries a non-null default so ALTER can fill 144 existing rows
    # with 1 without a backfill pass; `tool_fingerprint` cannot, because its
    # correct value differs per row and comes from the run each row names.
    ("document_versions", "tool_fingerprint", "TEXT"),
    ("document_versions", "edition", "INTEGER NOT NULL DEFAULT 1"),
]

# The rule, once. `CURRENT_EDITIONS_VIEW` below and every internal query that
# needs "the current edition" interpolate this same predicate, so a SQL consumer
# reading the view and this module's own Python cannot drift apart about what
# `current` means. It expects `document_versions` aliased as `v`.
#
# Scoped to (document_id, sha256), NOT to document_id: collapsing to one row per
# document would silently drop a genuinely different *byte* version, which is a
# separate axis this store has always kept. `facts.py` and `relations.py` pick
# the newest version per document with their own ROW_NUMBER() window over
# `ingested_at`; that keeps working unchanged, and because a newer edition is
# ingested later it also selects the newer edition.
#
# `edition` leads the ordering rather than `ingested_at` because `now()` has
# one-second resolution and two editions written in the same second would
# otherwise tie; `version_id` breaks any remaining tie so the answer is total
# and deterministic rather than whatever order the b-tree returns.
CURRENT_EDITION_PREDICATE = """v.version_id = (
            SELECT v2.version_id FROM document_versions v2
             WHERE v2.document_id = v.document_id AND v2.sha256 = v.sha256
             ORDER BY v2.edition DESC, v2.ingested_at DESC, v2.version_id DESC
             LIMIT 1)"""

# Which edition is current, for each (document, bytes) -- as a VIEW, so a caller
# writing plain SQL can join to it without importing this module.
#
# A view rather than a flag column: "current" is a fact about the other rows, so
# storing it would create a second copy of the truth that a half-finished write
# could leave disagreeing with the rows it describes. Same discipline as
# `retrieval_units` and `refs.build_index` -- derive it, never keep it.
#
# It is NOT part of SCHEMA. `migrate()` runs `executescript(SCHEMA)` before
# `ensure_columns()`, so a view over `document_versions.edition` created there
# would exist for the duration of the ALTER TABLE that adds that column -- and
# SQLite re-parses the whole schema on ALTER. It is also not created by
# `connect()`: nothing inside this module reads it (they interpolate the
# predicate directly), so a read-mostly command has no reason to write DDL to
# the store just by opening it. It appears when `cli migrate` runs.
#
# Columns are listed explicitly rather than `v.*`: a view freezes its column
# list at CREATE time, so `SELECT *` here would go stale the next time
# `document_versions` gains a column. Changing this definition therefore
# requires `cli migrate`, which drops the view first; `ensure_views` alone will
# not replace one that already exists.
CURRENT_EDITIONS_VIEW = """
CREATE VIEW IF NOT EXISTS current_editions AS
    SELECT v.version_id, v.document_id, v.sha256, v.file_size_bytes,
           v.page_count, v.ingested_at, v.extraction_run_id,
           v.tool_fingerprint, v.edition
      FROM document_versions v
     WHERE """ + CURRENT_EDITION_PREDICATE + ";\n"

# Columns that have been retired. Dropping is destructive and these tables are
# not all rebuildable, so `retire_columns` refuses to drop a column that still
# holds data -- it reports instead, and a human decides. Symmetric with
# ADDED_COLUMNS so the two directions are declared in one place.
RETIRED_COLUMNS = [
    ("table_read_candidates", "promoted_fact_id",
     "pointed UP at a derived row; superseded by facts.from_candidate_id"),
]


def ensure_columns(conn: sqlite3.Connection, spec=None) -> list[str]:
    """Add any column in `spec` that its table does not already have.

    Returns the `table.column` names actually added, so a caller can report the
    migration rather than perform it silently. A table that does not exist is
    skipped rather than fatal: a store predating it has nothing to migrate.
    """
    spec = ADDED_COLUMNS if spec is None else spec
    added = []
    for table, column, ddl in spec:
        info = conn.execute(f"PRAGMA table_info({table})").fetchall()
        if not info:
            continue
        if column in {r[1] for r in info}:
            continue
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
        added.append(f"{table}.{column}")
    if added:
        conn.commit()
    # Both directions, so a caller can report them. `retired["refused"]` is the
    # half that needs a person -- a column still holding data is not dropped.
    return added


# ------------------------------------------------- G38: extraction editions
#
# The two shapes `UNIQUE(...)` on `document_versions` can take. The legacy one
# permits exactly one extraction of a given document's bytes and is what made
# re-extraction destructive; the edition one adds the toolchain, so a second
# extraction with different tools lands beside the first instead of on top of it.
_LEGACY_VERSION_UNIQUE = ("document_id", "sha256")
_EDITION_VERSION_UNIQUE = ("document_id", "sha256", "tool_fingerprint")

# The version_id suffix that distinguishes edition 2..n from edition 1.
#
# Why only 2..n. Edition 1 keeps the id `ids.version_id_for` has always minted --
# `doc-24d0ddcfce69@00c965f58d30`. That asymmetry is not tidiness, it is the
# whole point: `element_id` is derived from `page_id`, which is derived from
# `version_id`, and every published `ref_id` was minted from an element that
# chain produced. Suffixing edition 1 too would be prettier and would rewrite
# all 144 existing version_ids, re-key 2,147 pages and 81,794 elements, and
# break the 431 published citations -- the exact failure this change exists to
# prevent. The toolchain of edition 1 is not lost by leaving its id alone; it is
# in `tool_fingerprint` on the row, where a query can reach it.
#
# The full 16-character fingerprint is used, not a prefix: truncating buys a
# shorter id and re-introduces a collision question on the one column whose job
# is to keep two toolchains apart.
EDITION_SEPARATOR = "~"


def _unique_index_columns(conn: sqlite3.Connection, table: str) -> list[tuple[str, ...]]:
    """The column tuples of every table-level UNIQUE constraint on `table`.

    `origin == 'u'` selects constraints declared UNIQUE in the CREATE TABLE, as
    opposed to the primary key (`'pk'`) or a CREATE INDEX (`'c'`). Read
    positionally so this works on a connection with no `row_factory`.
    """
    out = []
    for idx in conn.execute(f"PRAGMA index_list({table})"):
        if idx[3] != "u" or not idx[2]:
            continue
        out.append(tuple(r[2] for r in conn.execute(f"PRAGMA index_info({idx[1]})")))
    return out


def ensure_edition_unique(conn: sqlite3.Connection,
                          target: tuple[str, ...] = _EDITION_VERSION_UNIQUE) -> dict:
    """Widen `document_versions`'s UNIQUE constraint to include the toolchain.

    This is the one part of the editions change that `ALTER TABLE` cannot do:
    SQLite has no DROP CONSTRAINT, and a table-level UNIQUE is an implicit index
    that cannot be dropped either. So the table is rebuilt, by SQLite's own
    documented 12-step procedure. Three things make that acceptable *here* and
    would not make it acceptable on `elements`:

      * the table is 144 rows, and every column is copied verbatim -- no
        transformation, no id remapping, nothing to get wrong per row;
      * `version_id` is the primary key and is copied unchanged, which is the
        invariant everything downstream rests on. It is asserted, not assumed:
        the set of version_ids is compared before and after and the transaction
        rolls back if it moved by so much as one;
      * the new DDL is derived from the LIVE table's own `sqlite_master.sql`
        rather than retyped, so it cannot silently disagree with the columns the
        store actually has -- including any this function has never heard of.

    Idempotent: it looks for the legacy 2-column constraint and returns
    ``{"rebuilt": False}`` when it is already gone, so `migrate()` stays safe to
    re-run. Reversible: pass ``target=_LEGACY_VERSION_UNIQUE`` to narrow it back,
    which refuses rather than corrupts if a second edition already exists.

    Foreign keys are disabled for the duration, as the procedure requires --
    `pages`, `elements` and `assets` all declare
    `REFERENCES document_versions(version_id)`, and with FKs off SQLite leaves
    those clauses alone across the DROP and RENAME instead of rewriting them to
    name the temporary table. `PRAGMA foreign_key_check` runs before the commit,
    so the constraint is proven intact rather than hoped to be.
    """
    import re

    present = _unique_index_columns(conn, "document_versions")
    if not present:                      # table does not exist yet: nothing to do
        return {"rebuilt": False, "reason": "no document_versions table"}
    if tuple(target) in {tuple(c) for c in present}:
        return {"rebuilt": False, "reason": "already present", "unique": list(target)}

    cols = [r[1] for r in conn.execute("PRAGMA table_info(document_versions)")]
    missing = [c for c in target if c not in cols]
    if missing:
        # ensure_columns() has not run yet, or ran against an older spec. Refuse
        # rather than build a constraint over a column that does not exist.
        return {"rebuilt": False, "reason": f"missing column(s): {missing}"}

    if tuple(target) == _LEGACY_VERSION_UNIQUE:
        dupes = conn.execute("""SELECT COUNT(*) FROM (
                SELECT document_id, sha256 FROM document_versions
                 GROUP BY document_id, sha256 HAVING COUNT(*) > 1)""").fetchone()[0]
        if dupes:
            return {"rebuilt": False,
                    "reason": f"{dupes} (document, bytes) pairs already have more "
                              f"than one edition; narrowing the constraint would "
                              f"have to delete one"}

    sql = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND "
                       "name='document_versions'").fetchone()[0]
    # SQLite stores the CREATE statement as written, minus IF NOT EXISTS, and
    # ALTER TABLE ADD COLUMN splices each new column in after the last column
    # definition -- so on a migrated store the text reads
    # `... extraction_run_id TEXT ..., tool_fingerprint TEXT, edition INTEGER
    # NOT NULL DEFAULT 1,\n    UNIQUE(document_id, sha256)`. Whichever way the
    # columns landed, the clause itself is still there to find and rewrite.
    new_unique = f"UNIQUE({', '.join(target)})"
    new_sql, n = sql, 0
    for existing in present:
        pattern = (r"UNIQUE\s*\(\s*"
                   + r"\s*,\s*".join(re.escape(c) for c in existing)
                   + r"\s*\)")
        new_sql, n = re.subn(pattern, new_unique, sql, count=1)
        if n:
            break
    if not n:
        raise RuntimeError(
            "cannot find the UNIQUE clause in document_versions' stored DDL; "
            "refusing to rebuild a table whose schema this code does not "
            f"recognise:\n{sql}")
    new_sql = re.sub(r"^CREATE\s+TABLE\s+[\"\[`]?document_versions[\"\]`]?",
                     'CREATE TABLE "document_versions__new"', new_sql, count=1)
    if "document_versions__new" not in new_sql:
        raise RuntimeError(f"could not rename the rebuilt table in:\n{new_sql}")

    # The `current_editions` view names `document_versions`, and SQLite re-parses
    # every view when a table is renamed -- so RENAME fails with "error in view
    # current_editions: no such table" while the old table is dropped and the
    # new one not yet renamed. Drop it inside the transaction: a rollback brings
    # it back, and a commit is followed by `ensure_views` below.
    view_existed = bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='view' AND name='current_editions'"
    ).fetchone())

    collist = ", ".join(f'"{c}"' for c in cols)
    before_n = conn.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0]
    before_ids = sorted(r[0] for r in
                        conn.execute("SELECT version_id FROM document_versions"))

    # PRAGMA foreign_keys cannot change inside a transaction, and Python's
    # sqlite3 opens one implicitly before DML -- so commit, drop to autocommit,
    # and drive BEGIN/COMMIT by hand.
    prev_isolation = conn.isolation_level
    conn.commit()
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.isolation_level = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DROP VIEW IF EXISTS current_editions")
        conn.execute("DROP TABLE IF EXISTS document_versions__new")
        conn.execute(new_sql)
        conn.execute(f"INSERT INTO document_versions__new ({collist}) "
                     f"SELECT {collist} FROM document_versions")
        after_n = conn.execute("SELECT COUNT(*) FROM document_versions__new").fetchone()[0]
        after_ids = sorted(r[0] for r in
                           conn.execute("SELECT version_id FROM document_versions__new"))
        if after_n != before_n or after_ids != before_ids:
            conn.execute("ROLLBACK")
            moved = "differs" if after_ids != before_ids else "matches"
            raise RuntimeError(
                f"rebuild would have changed document_versions: {before_n} "
                f"rows in, {after_n} out; version_id set {moved}")
        conn.execute("DROP TABLE document_versions")
        conn.execute("ALTER TABLE document_versions__new RENAME TO document_versions")
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            conn.execute("ROLLBACK")
            raise RuntimeError(f"rebuild left {len(violations)} foreign-key "
                               f"violations; rolled back")
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.OperationalError:
            pass                          # already rolled back above
        raise
    finally:
        conn.isolation_level = prev_isolation
        conn.execute("PRAGMA foreign_keys=ON")
    if view_existed:
        ensure_views(conn)
    return {"rebuilt": True, "unique": list(target), "rows": before_n,
            "version_ids_preserved": True}


def ensure_views(conn: sqlite3.Connection) -> None:
    """(Re)create the derived views. Cheap, idempotent, and safe to call often.

    `CREATE VIEW IF NOT EXISTS` on a view that exists is a schema read, not a
    write, which is why every writer can afford to call this the way it already
    calls `ensure_columns`. It will not *replace* a view whose definition has
    changed -- `migrate()` drops first for that.
    """
    conn.executescript(CURRENT_EDITIONS_VIEW)


def backfill_tool_fingerprint(conn: sqlite3.Connection) -> int:
    """Copy each version's toolchain fingerprint down from the run that made it.

    Denormalisation, not new information: the value is already reachable through
    `extraction_run_id`. It has to live on the row because the UNIQUE constraint
    that admits a second edition cannot reach through a join.

    A version that names no run keeps NULL rather than getting a placeholder. A
    constant standing in for "unknown toolchain" would look like a fingerprint,
    would never change, and would therefore make two genuinely different
    toolchains collide into one edition -- G38 with extra steps. NULLs are also
    harmless to the UNIQUE constraint, since SQLite treats NULLs as distinct.
    """
    cur = conn.execute("""
        UPDATE document_versions AS v
           SET tool_fingerprint = (SELECT r.tool_fingerprint FROM extraction_runs r
                                    WHERE r.run_id = v.extraction_run_id)
         WHERE v.tool_fingerprint IS NULL AND v.extraction_run_id IS NOT NULL""")
    conn.commit()
    return cur.rowcount


def run_fingerprint(conn: sqlite3.Connection, run_id: str) -> str | None:
    row = conn.execute("SELECT tool_fingerprint FROM extraction_runs WHERE run_id=?",
                       (run_id,)).fetchone()
    return row[0] if row else None


def version_id_for_edition(conn: sqlite3.Connection, doc_id: str, sha256: str,
                           fingerprint: str | None) -> str:
    """The version_id for one (document x bytes x toolchain) edition.

    Three cases, in order:

      1. this exact edition already has a row -- return its id, so re-running an
         interrupted ingest rewrites the edition it wrote before rather than
         minting a second one beside it;
      2. these bytes have no row for this document at all -- return the id
         `ids.version_id_for` has always produced, unchanged. This is what keeps
         a fresh store's ids identical to today's;
      3. these bytes have a row, extracted by a *different* toolchain -- return
         a new id suffixed with this toolchain's fingerprint. The old row, its
         pages, its elements and every `ref_id` minted from them are untouched.

    Case 1 compares with `IS` rather than `=` so a legacy row whose fingerprint
    is still NULL, and whose run is gone, matches a NULL fingerprint instead of
    silently forking an edition on every ingest.
    """
    base = version_id_for(doc_id, sha256)
    row = conn.execute("""
        SELECT v.version_id
          FROM document_versions v
          LEFT JOIN extraction_runs r ON r.run_id = v.extraction_run_id
         WHERE v.document_id = ? AND v.sha256 = ?
           AND COALESCE(v.tool_fingerprint, r.tool_fingerprint) IS ?
         ORDER BY v.edition LIMIT 1""", (doc_id, sha256, fingerprint)).fetchone()
    if row is not None:
        return row[0]
    any_row = conn.execute(
        "SELECT 1 FROM document_versions WHERE document_id=? AND sha256=? LIMIT 1",
        (doc_id, sha256)).fetchone()
    if any_row is None:
        return base
    return f"{base}{EDITION_SEPARATOR}{fingerprint}"


def next_edition(conn: sqlite3.Connection, doc_id: str, sha256: str) -> int:
    row = conn.execute("SELECT MAX(edition) FROM document_versions "
                       "WHERE document_id=? AND sha256=?",
                       (doc_id, sha256)).fetchone()
    return int(row[0] or 0) + 1


def editions_of(conn: sqlite3.Connection, doc_id: str,
                sha256: str | None = None) -> list[sqlite3.Row]:
    """Every edition of a document, oldest first. The audit view of G38."""
    sql = ("SELECT * FROM document_versions WHERE document_id=?"
           + (" AND sha256=?" if sha256 else "")
           + " ORDER BY sha256, edition")
    params = (doc_id, sha256) if sha256 else (doc_id,)
    return conn.execute(sql, params).fetchall()


def current_edition(conn: sqlite3.Connection, doc_id: str,
                    sha256: str | None = None) -> sqlite3.Row | None:
    """Which edition is current, for one document (optionally, one byte version).

    Interpolates `CURRENT_EDITION_PREDICATE` -- the same text the
    `current_editions` view is built from -- rather than reading the view, so
    this answers correctly on a store that has not run `cli migrate` yet and
    still cannot disagree with what the view would have said. With no `sha256`
    and a document that has two genuinely different byte versions this returns
    the most recently ingested of their current editions -- the same choice
    `facts.py` makes.
    """
    sql = ("SELECT v.* FROM document_versions v WHERE " + CURRENT_EDITION_PREDICATE
           + " AND v.document_id=?"
           + (" AND v.sha256=?" if sha256 else "")
           + " ORDER BY v.ingested_at DESC, v.version_id DESC LIMIT 1")
    params = (doc_id, sha256) if sha256 else (doc_id,)
    return conn.execute(sql, params).fetchone()


def backfill_lang(conn: sqlite3.Connection, *, dry_run: bool = False) -> dict:
    """Tag elements that predate the `lang` column.

    Re-ingesting 144 PDFs to fill a nullable text column would be absurd, and
    `elements` is canonical -- it cannot be dropped and rebuilt the way `facts`
    can. So the tag is computed from text already in the store.
    """
    rows = conn.execute("""SELECT element_id, text, ocr_text FROM elements
                            WHERE lang IS NULL""").fetchall()
    counts: dict[str, int] = {}
    for r in rows:
        lang, basis = detect_lang(r["text"] or r["ocr_text"])
        counts[f"{lang}/{basis}"] = counts.get(f"{lang}/{basis}", 0) + 1
        if not dry_run:
            conn.execute("UPDATE elements SET lang=?, lang_basis=? WHERE element_id=?",
                         (lang, basis, r["element_id"]))
    if not dry_run:
        conn.commit()
    return {"tagged": 0 if dry_run else len(rows), "would_tag": len(rows) if dry_run else 0,
            "by_result": counts}


def connect(db_path: Path | None = None, *, read_only: bool = False) -> sqlite3.Connection:
    path = Path(db_path or EVIDENCE_DB)
    if not read_only:
        ensure_writable(path)
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    if not read_only:
        # An additive migration a writer cannot skip. Only `ingest` used to call
        # migrate(), so a store built before a column was added met it as
        # `no such column` in whatever command ran next -- and the fix looked
        # like a 33-minute re-ingest that was not actually needed. Five PRAGMA
        # reads and, on an up-to-date store, no writes at all.
        ensure_columns(conn)
    return conn


def retire_columns(conn: sqlite3.Connection, spec=None) -> dict:
    """Drop retired columns, but only where they hold nothing.

    A drop cannot be undone by re-running anything -- `table_read_candidates` is
    not regenerable -- so a column with data in it is reported and left alone
    rather than quietly destroyed.
    """
    spec = RETIRED_COLUMNS if spec is None else spec
    dropped, kept = [], {}
    for table, column, why in spec:
        info = conn.execute(f"PRAGMA table_info({table})").fetchall()
        if not info or column not in {r[1] for r in info}:
            continue
        n = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {column} IS NOT NULL").fetchone()[0]
        if n:
            kept[f"{table}.{column}"] = (
                f"{n} rows still carry a value; refusing to drop ({why})")
            continue
        conn.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
        dropped.append(f"{table}.{column}")
    if dropped:
        conn.commit()
    return {"dropped": dropped, "refused": kept}


def migrate(conn: sqlite3.Connection) -> dict:
    """Bring a store up to SCHEMA_VERSION. Additive, and safe to re-run.

    Step order is load-bearing:

      1. drop `current_editions` -- SQLite re-parses the whole schema on
         ALTER TABLE, and step 3 adds the very columns that view names;
      2. `SCHEMA` creates whatever tables are missing;
      3. `ensure_columns` adds whatever columns an existing table is missing;
      4. `ensure_edition_unique` does the one thing ALTER cannot: widen
         `UNIQUE(document_id, sha256)` to include the toolchain (G38). It is a
         no-op once done, and it refuses if step 3 has not run;
      5. `backfill_tool_fingerprint` fills the new column from the run each row
         already names -- no re-extraction, no source file read;
      6. the view goes back, now that every column it names exists.

    Every step is a no-op on an up-to-date store, so running this twice does
    exactly as much as running it once.
    """
    conn.execute("DROP VIEW IF EXISTS current_editions")
    conn.executescript(SCHEMA)
    added = ensure_columns(conn)
    conn.execute("DROP VIEW IF EXISTS current_editions")
    unique = ensure_edition_unique(conn)
    fingerprinted = backfill_tool_fingerprint(conn)
    ensure_views(conn)
    retired = retire_columns(conn)
    conn.execute("INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('schema_version', ?)",
                 (str(SCHEMA_VERSION),))
    conn.commit()
    # Both directions, so a caller can report them. `retired['refused']` is the
    # half that needs a person: a column still holding data is never dropped.
    return {"added": added, "retired": retired, "version_unique": unique,
            "tool_fingerprints_backfilled": fingerprinted}


def tool_fingerprint(tool_versions: dict) -> str:
    blob = json.dumps(tool_versions, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def start_run(conn: sqlite3.Connection, tool_versions: dict, pipeline_version: str,
              notes: str = "") -> str:
    fp = tool_fingerprint(tool_versions)
    run_id = f"run-{now().replace(':', '').replace('-', '')}-{fp[:6]}"
    conn.execute(
        "INSERT INTO extraction_runs(run_id, started_at, tool_versions, tool_fingerprint,"
        " pipeline_version, notes) VALUES (?,?,?,?,?,?)",
        (run_id, now(), json.dumps(tool_versions, sort_keys=True), fp, pipeline_version, notes))
    conn.commit()
    return run_id


def finish_run(conn: sqlite3.Connection, run_id: str) -> None:
    conn.execute("UPDATE extraction_runs SET finished_at=? WHERE run_id=?", (now(), run_id))
    conn.commit()


def upsert_document(conn: sqlite3.Connection, manifest_row: dict) -> str:
    doc_id = manifest_row["doc_id"]
    conn.execute("""
        INSERT INTO documents(document_id, source_path, file_type, corpus_track,
            manufacturer, product_family, doc_type, title, source_url, date_or_version,
            issue_date, expiration_date, version_status, version_status_basis,
            structural, in_curated_index)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(document_id) DO UPDATE SET
            manufacturer=excluded.manufacturer, product_family=excluded.product_family,
            doc_type=excluded.doc_type, title=excluded.title,
            source_url=excluded.source_url, date_or_version=excluded.date_or_version,
            issue_date=excluded.issue_date, expiration_date=excluded.expiration_date,
            version_status=excluded.version_status,
            version_status_basis=excluded.version_status_basis
    """, (doc_id, manifest_row["source_path"], manifest_row.get("file_type") or "",
          manifest_row.get("corpus_track") or "us", manifest_row.get("manufacturer"),
          manifest_row.get("product_family"), manifest_row.get("doc_type"),
          manifest_row.get("title"), manifest_row.get("source_url"),
          manifest_row.get("date_or_version"), manifest_row.get("issue_date"),
          manifest_row.get("expiration_date"),
          manifest_row.get("version_status") or "unknown",
          manifest_row.get("version_status_basis"),
          int(bool(manifest_row.get("structural_subdir"))),
          int(bool(manifest_row.get("in_curated_index")))))
    conn.commit()
    return doc_id


def version_exists(conn: sqlite3.Connection, doc_id: str, sha256: str,
                   fingerprint: str) -> bool:
    """True when this exact content was already extracted by these exact tools.

    Completion is judged from the *version row*, which is written in the same
    transaction as the document's pages and elements, not from the run's
    ``finished_at``.  Keying on the run would make every document of an
    interrupted run look stale and force a full re-extraction on resume.

    Under editions the fingerprint moved into the WHERE clause, and that is the
    substance of the change rather than a tidy-up. It used to fetch *the* row
    for (document, bytes) -- correct only while one could exist -- compare its
    fingerprint in Python, and answer False when it differed. Once a second
    edition can exist, that `fetchone()` picks an arbitrary edition, so a store
    holding both the old and the new toolchain's editions could answer False for
    the toolchain it already has and re-extract it. Asking the database for the
    edition that matches removes the ambiguity instead of ordering around it.

    ``COALESCE(v.tool_fingerprint, r.tool_fingerprint)`` reads the denormalised
    column when it is filled and falls back to the run it names when it is not,
    so a store that has not run `cli migrate` still answers correctly. Without
    the fallback, an un-migrated store would report every document stale and
    re-extract the whole corpus -- the loudest possible way to fail at being
    additive.
    """
    row = conn.execute("""
        SELECT v.version_id
          FROM document_versions v
          LEFT JOIN extraction_runs r ON r.run_id = v.extraction_run_id
         WHERE v.document_id=? AND v.sha256=?
           AND COALESCE(v.tool_fingerprint, r.tool_fingerprint) = ?
    """, (doc_id, sha256, fingerprint)).fetchone()
    if not row:
        return False
    # and that edition must actually carry content
    n = conn.execute("SELECT COUNT(*) FROM pages WHERE version_id=?",
                     (row[0],)).fetchone()[0]
    return n > 0


def _asset_row(conn, doc_id, version_id, page_no, element_id, asset_type, path_str):
    from .paths import REPO_ROOT
    p = REPO_ROOT / path_str
    if not p.is_file():
        return
    size = p.stat().st_size
    w = h = None
    try:
        from PIL import Image
        with Image.open(p) as im:
            w, h = im.size
    except Exception:
        pass
    # Keyed by (edition, path), not path alone. The id was `sha256(path)`, and
    # the write below is INSERT OR REPLACE -- so a second edition rendering the
    # same page image would have *overwritten* the first edition's asset row and
    # re-pointed it at the new edition's element_id. That is a destructive
    # re-extraction surviving inside an otherwise additive one. Nothing outside
    # this module derives or looks up an asset_id (checked), and none is
    # published, so widening the key costs nothing; rows written before this
    # keep their old ids and are only ever rewritten by a re-ingest of their own
    # edition, which deletes them by version_id first.
    asset_id = hashlib.sha256(f"{version_id}:{path_str}".encode()).hexdigest()[:16]
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    conn.execute("""INSERT OR REPLACE INTO assets(asset_id, document_id, version_id,
        page_no, element_id, asset_type, path, sha256, bytes, width_px, height_px)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                 (asset_id, doc_id, version_id, page_no, element_id, asset_type,
                  path_str, sha, size, w, h))


def delete_version_rows(conn: sqlite3.Connection, version_id: str) -> None:
    """Remove all canonical rows for ONE edition. Never called to make room.

    This function used to be the G38 defect. Its old docstring said "so
    re-extraction is not additive", and `write_extracted` called it
    unconditionally on a version_id that carried no toolchain -- so a poppler
    upgrade deleted the elements every published `ref_id` named, and the
    citations in an immutable snapshot stopped resolving with no error anywhere.

    **It survives, deliberately, for two jobs that are genuine deletes.**

      * Retiring an edition nothing cites. Editions cost ~31 MB each on a 69 MB
        store, and §5.1 of docs/four-layer-model-design.md is explicit that an
        edition is retained *while an un-tombstoned snapshot cites it* and
        dropped when none does. Without a delete there is no way to ever drop
        one, and the design becomes unbounded growth.
      * Rewriting an edition over itself. `write_extracted` re-running on the
        same (document x bytes x toolchain) clears that edition's rows before
        writing the identical ones back, which is what keeps a resumed or
        repeated ingest idempotent.

    What changed is that it can no longer be reached by *accident*: the only
    caller now guards on the version_id already existing AND its fingerprint
    matching the run doing the writing, so the rows deleted are always the rows
    about to be re-created. A different toolchain gets a different version_id
    and this function finds nothing to delete.

    Deliberately does NOT check whether a published snapshot cites the edition.
    `store` sits below `refs` and `snapshot_store`; importing them here to ask
    would invert the layering the whole repo is organised around. The check
    belongs to whatever command offers edition retirement, and
    `cli refs --verify` is the regression guard either way.
    """
    conn.execute("DELETE FROM table_cells WHERE table_id IN "
                 "(SELECT t.table_id FROM tables t JOIN elements e ON e.element_id=t.element_id"
                 " WHERE e.version_id=?)", (version_id,))
    conn.execute("DELETE FROM tables WHERE element_id IN "
                 "(SELECT element_id FROM elements WHERE version_id=?)", (version_id,))
    conn.execute("DELETE FROM assets WHERE version_id=?", (version_id,))
    conn.execute("DELETE FROM elements WHERE version_id=?", (version_id,))
    conn.execute("DELETE FROM pages WHERE version_id=?", (version_id,))
    conn.execute("DELETE FROM quality_issues WHERE version_id=?", (version_id,))


def write_extracted(conn: sqlite3.Connection, extracted: ExtractedDocument,
                    manifest_row: dict, run_id: str) -> str:
    """Write one extracted document into the canonical store. Idempotent per edition."""
    doc_id = upsert_document(conn, manifest_row)

    # G38. The version's identity is (document x bytes x toolchain), which is
    # what `version_exists` has always assumed and the row never recorded. A run
    # with a different toolchain now writes a NEW edition beside the old one
    # instead of deleting it, so every `ref_id` minted from the old edition's
    # elements keeps resolving. Nothing here re-points anything: old rows are
    # simply not touched.
    fingerprint = run_fingerprint(conn, run_id)
    version_id = version_id_for_edition(conn, doc_id, extracted.sha256, fingerprint)
    page_count = len(extracted.pages)

    existing = conn.execute(
        """SELECT v.edition,
                  COALESCE(v.tool_fingerprint,
                           (SELECT r.tool_fingerprint FROM extraction_runs r
                             WHERE r.run_id = v.extraction_run_id)) AS fp
             FROM document_versions v WHERE v.version_id = ?""",
        (version_id,)).fetchone()
    if existing is None:
        edition = next_edition(conn, doc_id, extracted.sha256)
    else:
        # The only path on which anything is deleted, and it deletes exactly the
        # rows the rest of this function is about to write again: same document,
        # same bytes, same tools. If the fingerprints disagree,
        # `version_id_for_edition` has a bug and the safe response is to stop --
        # deleting here would be the original defect, and a wrong answer that
        # destroys evidence is worse than no answer.
        if existing["fp"] is not None and fingerprint is not None \
                and existing["fp"] != fingerprint:
            raise RuntimeError(
                f"version {version_id} was extracted by toolchain "
                f"{existing['fp']} but this run is {fingerprint}; refusing to "
                f"overwrite another edition's canonical rows (G38)")
        edition = existing["edition"]
        delete_version_rows(conn, version_id)

    conn.execute("""INSERT INTO document_versions(version_id, document_id, sha256,
        file_size_bytes, page_count, ingested_at, extraction_run_id,
        tool_fingerprint, edition)
        VALUES (?,?,?,?,?,?,?,?,?)
        ON CONFLICT(version_id) DO UPDATE SET page_count=excluded.page_count,
            ingested_at=excluded.ingested_at, extraction_run_id=excluded.extraction_run_id,
            tool_fingerprint=excluded.tool_fingerprint""",
                 (version_id, doc_id, extracted.sha256,
                  manifest_row.get("file_size_bytes"), page_count, now(), run_id,
                  fingerprint, edition))

    for page in extracted.pages:
        page_id = page_id_for(version_id, page.page_no)
        conn.execute("""INSERT INTO pages(page_id, version_id, page_no, width, height,
            extraction_method, page_image_path, page_image_dpi, text_char_count,
            has_text_layer, ocr_mean_confidence, notes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                     (page_id, version_id, page.page_no, page.width, page.height,
                      page.extraction_method, page.page_image_path, page.page_image_dpi,
                      page.text_char_count, int(page.has_text_layer),
                      page.ocr_mean_confidence, json.dumps(page.notes)))
        if page.page_image_path:
            _asset_row(conn, doc_id, version_id, page.page_no, None,
                       "page_image", page.page_image_path)
        for el in page.elements:
            element_id = element_id_for(page_id, el.ordinal)
            el_lang, el_lang_basis = detect_lang(el.text or el.ocr_text)
            conn.execute("""INSERT INTO elements(element_id, page_id, version_id, document_id,
                page_no, ordinal, element_type, text, ocr_text, text_source, ocr_confidence,
                heading_level, heading_path, caption, bbox, region_image_path,
                lang, lang_basis, extra)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                         (element_id, page_id, version_id, doc_id, page.page_no, el.ordinal,
                          el.element_type, el.text or "", el.ocr_text, el.text_source,
                          el.ocr_confidence, el.heading_level, json.dumps(el.heading_path),
                          el.caption, json.dumps(el.bbox) if el.bbox else None,
                          el.region_image_path, el_lang, el_lang_basis,
                          json.dumps(el.extra)))
            if el.region_image_path:
                _asset_row(conn, doc_id, version_id, page.page_no, element_id,
                           "region_image", el.region_image_path)
            if el.table is not None:
                table_id = f"table-{element_id}"
                conn.execute("""INSERT INTO tables(table_id, element_id, n_rows, n_cols,
                    detector, bbox) VALUES (?,?,?,?,?,?)""",
                             (table_id, element_id, el.table.n_rows, el.table.n_cols,
                              el.table.detector,
                              json.dumps(el.table.bbox) if el.table.bbox else None))
                for c in el.table.cells:
                    conn.execute("""INSERT OR REPLACE INTO table_cells(table_id, row, col,
                        rowspan, colspan, text, bbox) VALUES (?,?,?,?,?,?,?)""",
                                 (table_id, c.row, c.col, c.rowspan, c.colspan, c.text,
                                  json.dumps(c.bbox) if c.bbox else None))

    for issue in extracted.quality_issues:
        conn.execute("""INSERT INTO quality_issues(document_id, version_id, page_no,
            severity, kind, detail, detected_at) VALUES (?,?,?,?,?,?,?)""",
                     (doc_id, version_id, issue.get("page_no"), issue["severity"],
                      issue["kind"], issue["detail"], now()))
    conn.commit()
    return version_id


# ------------------------------------------------------------------ relations
def add_relation(conn: sqlite3.Connection, from_doc: str, to_doc: str, rtype: str,
                 basis: str = "", confidence: float = 1.0) -> None:
    if from_doc == to_doc:
        return
    conn.execute("""INSERT OR IGNORE INTO relations(from_document_id, to_document_id,
        relation_type, basis, confidence) VALUES (?,?,?,?,?)""",
                 (from_doc, to_doc, rtype, basis, confidence))


# ------------------------------------------------- retrieval projection (derived)
MERGE_MAX_CHARS = 1400
MERGE_TYPES = {"paragraph", "list", "caption", "table_text", "drawing_label"}

# Heading elements are deliberately *not* projected as standalone units.  They
# remain canonical elements, and their text already reaches the index through
# the heading_path column of every unit beneath them.  Indexing them separately
# gave one- and two-word units whose BM25 length normalisation outranked the
# tables and OCR paragraphs that actually hold the answer.
UNIT_EXCLUDED_TYPES = {"heading"}


def _unit_text(row: sqlite3.Row) -> str:
    return (row["text"] or "").strip() or (row["ocr_text"] or "").strip()


def build_retrieval_units(conn: sqlite3.Connection, *, document_id: str | None = None) -> int:
    """(Re)build the searchable projection from canonical elements.

    Safe to run at any time: it derives everything from ``elements`` and never
    reads a source file.  Rebuilding must reproduce identical rows.

    Projects the CURRENT edition of each (document, bytes) and no other. Under
    G38 a re-extraction adds a second edition of the same bytes rather than
    replacing the first, and both editions describe the identical page -- so
    without this filter every search hit would come back twice, once per
    toolchain. Note what it does *not* do: two genuinely different byte versions
    of a document are still both projected, as they always have been, because
    they are different content and not different measurements of it.

    It interpolates `CURRENT_EDITION_PREDICATE` rather than joining the
    `current_editions` view, so the projection is rebuildable on a store that
    has not run `cli migrate` yet. On a store with one edition per (document,
    bytes) -- which is every store that exists today -- the predicate selects
    every version row and this join changes nothing; measured on the live store,
    all 10,886 units rebuild byte-identically. `tests/test_idempotency.py` is
    the standing guard.
    """
    if document_id:
        old = [r[0] for r in conn.execute(
            "SELECT unit_id FROM retrieval_units WHERE document_id=?", (document_id,))]
        for uid in old:
            conn.execute("DELETE FROM retrieval_fts WHERE rowid=?", (uid,))
        conn.execute("DELETE FROM retrieval_units WHERE document_id=?", (document_id,))
        docs = [document_id]
    else:
        conn.execute("DELETE FROM retrieval_fts")
        conn.execute("DELETE FROM retrieval_units")
        conn.execute("DELETE FROM sqlite_sequence WHERE name='retrieval_units'")
        docs = [r[0] for r in conn.execute("SELECT document_id FROM documents ORDER BY document_id")]

    built = now()
    total = 0
    for doc_id in docs:
        meta = conn.execute("SELECT title, manufacturer, doc_type FROM documents "
                            "WHERE document_id=?", (doc_id,)).fetchone()
        rows = conn.execute("""SELECT e.* FROM elements e
                               JOIN document_versions v ON v.version_id = e.version_id
                               WHERE e.document_id=? AND """
                            + CURRENT_EDITION_PREDICATE
                            + " ORDER BY e.version_id, e.page_no, e.ordinal",
                            (doc_id,)).fetchall()
        buffer: list[sqlite3.Row] = []

        def flush():
            nonlocal total, buffer
            if not buffer:
                return
            text = "\n".join(_unit_text(r) for r in buffer if _unit_text(r))
            if not text.strip():
                buffer = []
                return
            first = buffer[0]
            boxes = [json.loads(r["bbox"]) for r in buffer if r["bbox"]]
            bbox = None
            if boxes:
                bbox = [min(b[0] for b in boxes), min(b[1] for b in boxes),
                        max(b[2] for b in boxes), max(b[3] for b in boxes)]
            heading_path = json.loads(first["heading_path"] or "[]")
            cur = conn.execute("""INSERT INTO retrieval_units(document_id, version_id,
                page_no, element_id, element_ids, element_type, text, text_source,
                heading_path, bbox, built_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (doc_id, first["version_id"], first["page_no"], first["element_id"],
                 json.dumps([r["element_id"] for r in buffer]), first["element_type"],
                 text, first["text_source"], json.dumps(heading_path),
                 json.dumps(bbox) if bbox else None, built))
            uid = cur.lastrowid
            conn.execute("""INSERT INTO retrieval_fts(rowid, text, heading_path, title,
                manufacturer, doc_type) VALUES (?,?,?,?,?,?)""",
                (uid, text, " > ".join(heading_path), meta["title"] or "",
                 meta["manufacturer"] or "", meta["doc_type"] or ""))
            total += 1
            buffer = []

        for row in rows:
            if row["element_type"] in UNIT_EXCLUDED_TYPES:
                continue
            if not _unit_text(row) and row["element_type"] not in ("figure", "drawing"):
                continue
            if row["element_type"] not in MERGE_TYPES:
                flush()
                buffer = [row]
                flush()
                continue
            if buffer:
                same_page = buffer[0]["page_no"] == row["page_no"]
                same_head = buffer[0]["heading_path"] == row["heading_path"]
                # a unit must never straddle two versions of the same document
                same_version = buffer[0]["version_id"] == row["version_id"]
                size = sum(len(_unit_text(r)) for r in buffer)
                if not (same_page and same_head and same_version) \
                        or size > MERGE_MAX_CHARS:
                    flush()
            buffer.append(row)
        flush()
    conn.commit()
    return total


def stats(conn: sqlite3.Connection) -> dict:
    def one(sql: str) -> int:
        return conn.execute(sql).fetchone()[0]
    return {
        "documents": one("SELECT COUNT(*) FROM documents"),
        "versions": one("SELECT COUNT(*) FROM document_versions"),
        # `versions` counts every edition; `superseded_editions` is how many of
        # them a newer extraction of the same bytes has replaced as current. It
        # is 0 on a store that has never been re-extracted with new tools, and
        # the difference is the ~31 MB-per-edition retention cost made visible.
        "superseded_editions": one(
            "SELECT COUNT(*) FROM document_versions v WHERE NOT ("
            + CURRENT_EDITION_PREDICATE + ")"),
        "pages": one("SELECT COUNT(*) FROM pages"),
        "elements": one("SELECT COUNT(*) FROM elements"),
        "tables": one("SELECT COUNT(*) FROM tables"),
        "table_cells": one("SELECT COUNT(*) FROM table_cells"),
        "assets": one("SELECT COUNT(*) FROM assets"),
        "relations": one("SELECT COUNT(*) FROM relations"),
        "quality_issues": one("SELECT COUNT(*) FROM quality_issues"),
        "retrieval_units": one("SELECT COUNT(*) FROM retrieval_units"),
        "facts": one("SELECT COUNT(*) FROM facts"),
        "table_read_candidates": one("SELECT COUNT(*) FROM table_read_candidates"),
    }
