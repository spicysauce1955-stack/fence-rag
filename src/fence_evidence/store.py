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
from .paths import EVIDENCE_DB, ensure_writable

SCHEMA_VERSION = 1

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

CREATE TABLE IF NOT EXISTS document_versions (
    version_id      TEXT PRIMARY KEY,
    document_id     TEXT NOT NULL REFERENCES documents(document_id),
    sha256          TEXT NOT NULL,
    file_size_bytes INTEGER,
    page_count      INTEGER,
    ingested_at     TEXT NOT NULL,
    extraction_run_id TEXT REFERENCES extraction_runs(run_id),
    UNIQUE(document_id, sha256)
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
    evidence_text   TEXT NOT NULL,
    extractor       TEXT NOT NULL,
    ocr_derived     INTEGER NOT NULL DEFAULT 0,
    review_status   TEXT NOT NULL DEFAULT 'extracted',   -- extracted|flagged|reviewed|rejected
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_facts_doc ON facts(document_id, fact_type);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: Path | None = None, *, read_only: bool = False) -> sqlite3.Connection:
    path = Path(db_path or EVIDENCE_DB)
    if not read_only:
        ensure_writable(path)
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.execute("INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('schema_version', ?)",
                 (str(SCHEMA_VERSION),))
    conn.commit()


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
    """
    row = conn.execute("""
        SELECT r.tool_fingerprint AS fp
          FROM document_versions v JOIN extraction_runs r
            ON r.run_id = v.extraction_run_id
         WHERE v.document_id=? AND v.sha256=?
    """, (doc_id, sha256)).fetchone()
    if not row or row["fp"] != fingerprint:
        return False
    # and the version must actually carry content
    n = conn.execute("""SELECT COUNT(*) FROM pages p
        JOIN document_versions v ON v.version_id = p.version_id
        WHERE v.document_id=? AND v.sha256=?""", (doc_id, sha256)).fetchone()[0]
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
    asset_id = hashlib.sha256(path_str.encode()).hexdigest()[:16]
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    conn.execute("""INSERT OR REPLACE INTO assets(asset_id, document_id, version_id,
        page_no, element_id, asset_type, path, sha256, bytes, width_px, height_px)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                 (asset_id, doc_id, version_id, page_no, element_id, asset_type,
                  path_str, sha, size, w, h))


def delete_version_rows(conn: sqlite3.Connection, version_id: str) -> None:
    """Remove all canonical rows for a version so re-extraction is not additive."""
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
    """Write one extracted document into the canonical store. Idempotent per version."""
    doc_id = upsert_document(conn, manifest_row)
    version_id = version_id_for(doc_id, extracted.sha256)
    page_count = len(extracted.pages)
    delete_version_rows(conn, version_id)
    conn.execute("""INSERT INTO document_versions(version_id, document_id, sha256,
        file_size_bytes, page_count, ingested_at, extraction_run_id)
        VALUES (?,?,?,?,?,?,?)
        ON CONFLICT(version_id) DO UPDATE SET page_count=excluded.page_count,
            ingested_at=excluded.ingested_at, extraction_run_id=excluded.extraction_run_id""",
                 (version_id, doc_id, extracted.sha256,
                  manifest_row.get("file_size_bytes"), page_count, now(), run_id))

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
            conn.execute("""INSERT INTO elements(element_id, page_id, version_id, document_id,
                page_no, ordinal, element_type, text, ocr_text, text_source, ocr_confidence,
                heading_level, heading_path, caption, bbox, region_image_path, extra)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                         (element_id, page_id, version_id, doc_id, page.page_no, el.ordinal,
                          el.element_type, el.text or "", el.ocr_text, el.text_source,
                          el.ocr_confidence, el.heading_level, json.dumps(el.heading_path),
                          el.caption, json.dumps(el.bbox) if el.bbox else None,
                          el.region_image_path, json.dumps(el.extra)))
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
        rows = conn.execute("""SELECT * FROM elements WHERE document_id=?
                               ORDER BY version_id, page_no, ordinal""",
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
        "pages": one("SELECT COUNT(*) FROM pages"),
        "elements": one("SELECT COUNT(*) FROM elements"),
        "tables": one("SELECT COUNT(*) FROM tables"),
        "table_cells": one("SELECT COUNT(*) FROM table_cells"),
        "assets": one("SELECT COUNT(*) FROM assets"),
        "relations": one("SELECT COUNT(*) FROM relations"),
        "quality_issues": one("SELECT COUNT(*) FROM quality_issues"),
        "retrieval_units": one("SELECT COUNT(*) FROM retrieval_units"),
        "facts": one("SELECT COUNT(*) FROM facts"),
    }
