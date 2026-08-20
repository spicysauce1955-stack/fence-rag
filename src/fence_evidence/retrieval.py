"""Phase 3 — lexical retrieval over the evidence store.

Every result carries the provenance needed to verify it: document, page,
element, bounding box, and the path to the page image and region crop that
show the reader where the text came from (prohibition 11).
"""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from .paths import REPO_ROOT
from .relations import APPROVAL_RE, supersession_chain
from .store import connect

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for",
    "from", "has", "have", "how", "i", "in", "is", "it", "its", "me", "my", "of",
    "on", "or", "show", "that", "the", "there", "this", "to", "use", "used",
    "using", "was", "what", "when", "where", "which", "who", "why", "will",
    "with", "you", "your", "find", "give", "tell", "list", "does", "did", "any",
}
UNIT_WORDS = {"mph", "in", "inch", "inches", "ft", "feet", "foot", "psf", "mm",
              "cm", "deg", "degrees", "lb", "lbs", "oc"}
_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/#'\"-]*")
_IDENT_RE = re.compile(r"\b\d{2}-\d{4}\.\d{2}\b|\b[A-Z]{1,3}\d{3,6}\b|\b\d{4,6}\b")
_NUM_UNIT_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*(mph|psf|in\.?|inch(?:es)?|ft|feet|mm|deg(?:rees)?)\b", re.I)

BM25_WEIGHTS = (1.0, 0.55, 0.45, 0.25, 0.15)   # text, heading_path, title, manufacturer, doc_type


@dataclass
class SearchResult:
    document_id: str
    title: Optional[str]
    source_path: str
    status: str
    manufacturer: Optional[str]
    doc_type: Optional[str]
    page: int
    element_id: str
    element_type: str
    heading_path: list[str]
    text: str
    snippet: str
    text_source: str
    page_image_path: Optional[str]
    region_image_path: Optional[str]
    bbox: Optional[list[float]]
    score: float
    retrieval_reason: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------- query
def _fts_escape(term: str) -> str:
    return '"' + term.replace('"', '""') + '"'


def build_match_expression(query: str) -> tuple[str, list[str]]:
    """Translate a natural-language question into an FTS5 MATCH expression.

    FTS5's unicode61 tokenizer splits identifiers like ``23-0314.05`` and
    measurements like ``130 mph`` into separate tokens, so those are re-issued
    as phrases; everything else is OR-ed so BM25 can rank partial matches
    rather than an AND requirement silently returning nothing.
    """
    phrases: list[str] = []
    terms: list[str] = []
    matched_source: list[str] = []

    for m in re.finditer(r'"([^"]+)"', query):
        phrases.append(_fts_escape(m.group(1)))
        matched_source.append(m.group(1))
    stripped = re.sub(r'"[^"]+"', " ", query)

    for m in _IDENT_RE.finditer(stripped):
        raw = m.group(0)
        parts = [p for p in re.split(r"[^A-Za-z0-9]+", raw) if p]
        if len(parts) > 1:
            phrases.append(_fts_escape(" ".join(parts)))
        else:
            terms.append(_fts_escape(raw))
        matched_source.append(raw)

    for m in _NUM_UNIT_RE.finditer(stripped):
        num, unit = m.group(1), m.group(2).rstrip(".")
        phrases.append(_fts_escape(f"{num} {unit}"))
        matched_source.append(m.group(0))

    for tok in _TOKEN_RE.findall(stripped):
        low = tok.lower().strip("\"'.-")
        if len(low) < 2 or low in STOPWORDS:
            continue
        if low.isdigit() and len(low) < 2:
            continue
        core = re.sub(r"[^A-Za-z0-9]+", " ", low).strip()
        if not core:
            continue
        if " " in core:
            phrases.append(_fts_escape(core))
        else:
            terms.append(_fts_escape(core))
        matched_source.append(tok)

    parts = phrases + terms
    if not parts:
        return "", []
    seen, unique = set(), []
    for p in parts:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return " OR ".join(unique), matched_source


def _matched_terms(text: str, sources: list[str]) -> list[str]:
    """Which of the query's terms actually appear in this result's text."""
    low = text.lower()
    out = []
    for s in sources:
        s_clean = s.strip("\"'").lower()
        if len(s_clean) < 2:
            continue
        if s_clean in low and s_clean not in out:
            out.append(s.strip("\"'"))
    return out


FILTER_COLUMNS = {
    "manufacturer": "d.manufacturer",
    "doc_type": "d.doc_type",
    "version_status": "d.version_status",
    "corpus_track": "d.corpus_track",
    "element_type": "u.element_type",
    "document_id": "u.document_id",
}


def search_evidence(query: str, *, limit: int = 10, filters: dict | None = None,
                    mode: str = "fts5", conn: sqlite3.Connection | None = None,
                    min_score: float = 0.0) -> list[SearchResult]:
    if mode != "fts5":
        raise ValueError(f"only mode='fts5' is implemented in the MVP; got {mode!r}")
    own = conn is None
    conn = conn or connect()
    try:
        match, sources = build_match_expression(query)
        if not match:
            return []
        where = ["retrieval_fts MATCH ?"]
        params: list[Any] = [match]
        for key, value in (filters or {}).items():
            if key == "source_path_prefix":
                where.append("d.source_path LIKE ?")
                params.append(f"{value}%")
                continue
            col = FILTER_COLUMNS.get(key)
            if not col:
                raise ValueError(f"unsupported filter {key!r}")
            if isinstance(value, (list, tuple, set)):
                where.append(f"{col} IN ({','.join('?' * len(value))})")
                params.extend(list(value))
            else:
                where.append(f"{col} = ?")
                params.append(value)
        sql = f"""
            SELECT u.*, d.title, d.source_path, d.version_status, d.manufacturer,
                   d.doc_type,
                   bm25(retrieval_fts, {','.join(str(w) for w in BM25_WEIGHTS)}) AS bm25,
                   snippet(retrieval_fts, 0, '', '', ' … ', 28) AS snip,
                   p.page_image_path AS page_image_path
              FROM retrieval_fts
              JOIN retrieval_units u ON u.unit_id = retrieval_fts.rowid
              JOIN documents d ON d.document_id = u.document_id
              LEFT JOIN pages p ON p.version_id = u.version_id AND p.page_no = u.page_no
             WHERE {' AND '.join(where)}
             ORDER BY bm25
             LIMIT ?
        """
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        results: list[SearchResult] = []
        for r in rows:
            score = round(-float(r["bm25"]), 4)
            if score < min_score:
                continue
            region = conn.execute(
                "SELECT region_image_path FROM elements WHERE element_id=?",
                (r["element_id"],)).fetchone()
            results.append(SearchResult(
                document_id=r["document_id"], title=r["title"],
                source_path=r["source_path"], status=r["version_status"],
                manufacturer=r["manufacturer"], doc_type=r["doc_type"],
                page=r["page_no"], element_id=r["element_id"],
                element_type=r["element_type"],
                heading_path=json.loads(r["heading_path"] or "[]"),
                text=r["text"], snippet=r["snip"], text_source=r["text_source"],
                page_image_path=r["page_image_path"],
                region_image_path=region["region_image_path"] if region else None,
                bbox=json.loads(r["bbox"]) if r["bbox"] else None,
                score=score,
                retrieval_reason={"mode": "fts5",
                                  "matched_terms": _matched_terms(r["text"], sources),
                                  "bm25": round(float(r["bm25"]), 4),
                                  "match_expression": match}))
        return results
    finally:
        if own:
            conn.close()


# ----------------------------------------------------------------- accessors
def get_document(identifier: str, *, conn: sqlite3.Connection | None = None) -> dict | None:
    own = conn is None
    conn = conn or connect()
    try:
        row = conn.execute("""SELECT * FROM documents WHERE document_id=? OR source_path=?""",
                           (identifier, identifier)).fetchone()
        if not row:
            return None
        doc = dict(row)
        doc["versions"] = [dict(v) for v in conn.execute(
            "SELECT * FROM document_versions WHERE document_id=? ORDER BY ingested_at",
            (row["document_id"],))]
        doc["page_count"] = conn.execute(
            "SELECT COUNT(*) FROM pages p JOIN document_versions v ON v.version_id=p.version_id"
            " WHERE v.document_id=?", (row["document_id"],)).fetchone()[0]
        doc["relations"] = [dict(r) for r in conn.execute(
            "SELECT relation_type, to_document_id, basis FROM relations WHERE from_document_id=?",
            (row["document_id"],))]
        doc["quality_issues"] = [dict(r) for r in conn.execute(
            "SELECT severity, kind, page_no, detail FROM quality_issues WHERE document_id=?",
            (row["document_id"],))]
        return doc
    finally:
        if own:
            conn.close()


def get_page(document_id: str, page_no: int, *,
             conn: sqlite3.Connection | None = None) -> dict | None:
    own = conn is None
    conn = conn or connect()
    try:
        # newest version wins when a document has been re-ingested
        row = conn.execute("""SELECT p.* FROM pages p
            JOIN document_versions v ON v.version_id = p.version_id
            WHERE v.document_id=? AND p.page_no=?
            ORDER BY v.ingested_at DESC LIMIT 1""",
            (document_id, page_no)).fetchone()
        if not row:
            return None
        page = dict(row)
        page["notes"] = json.loads(page.get("notes") or "[]")
        page["elements"] = [dict(e) for e in conn.execute(
            """SELECT element_id, element_type, ordinal, text, ocr_text, text_source,
                      heading_path, bbox, region_image_path, caption
                 FROM elements WHERE page_id=? ORDER BY ordinal""", (row["page_id"],))]
        for e in page["elements"]:
            e["heading_path"] = json.loads(e["heading_path"] or "[]")
            e["bbox"] = json.loads(e["bbox"]) if e["bbox"] else None
        return page
    finally:
        if own:
            conn.close()


def get_region(element_id: str, *, conn: sqlite3.Connection | None = None) -> dict | None:
    """The image evidence for one element, cropping on demand if needed."""
    own = conn is None
    conn = conn or connect()
    try:
        row = conn.execute("""SELECT e.*, p.page_image_path, p.width, p.height
            FROM elements e JOIN pages p ON p.page_id = e.page_id
            WHERE e.element_id=?""", (element_id,)).fetchone()
        if not row:
            return None
        bbox = json.loads(row["bbox"]) if row["bbox"] else None
        region = row["region_image_path"]
        if not region and bbox and row["page_image_path"]:
            from .extract import _crop_region, derived_dir
            out = (derived_dir(row["document_id"]) / "regions" /
                   f"p{row['page_no']:04d}-{row['ordinal']:04d}-ondemand.png")
            if _crop_region(REPO_ROOT / row["page_image_path"], row["width"], bbox, out):
                from .paths import rel
                region = rel(out)
                conn.execute("UPDATE elements SET region_image_path=? WHERE element_id=?",
                             (region, element_id))
                conn.commit()
        return {
            "element_id": element_id, "document_id": row["document_id"],
            "page": row["page_no"], "bbox": bbox,
            "page_image_path": row["page_image_path"],
            "region_image_path": region,
            "element_type": row["element_type"],
            "text": row["text"] or row["ocr_text"] or "",
        }
    finally:
        if own:
            conn.close()


def get_element_context(element_id: str, *, before: int = 1, after: int = 1,
                        conn: sqlite3.Connection | None = None) -> dict | None:
    own = conn is None
    conn = conn or connect()
    try:
        row = conn.execute("SELECT * FROM elements WHERE element_id=?",
                           (element_id,)).fetchone()
        if not row:
            return None
        neighbours = conn.execute("""SELECT element_id, element_type, ordinal, page_no,
                text, ocr_text, heading_path FROM elements
                WHERE document_id=? AND version_id=? AND (
                    (page_no = ? AND ordinal BETWEEN ? AND ?)
                    OR (page_no BETWEEN ? AND ? AND page_no != ?))
                ORDER BY page_no, ordinal""",
            (row["document_id"], row["version_id"], row["page_no"], row["ordinal"] - before,
             row["ordinal"] + after, row["page_no"] - (1 if before else 0),
             row["page_no"] + (1 if after else 0), row["page_no"])).fetchall()
        return {
            "element_id": element_id,
            "document_id": row["document_id"],
            "page": row["page_no"],
            "heading_path": json.loads(row["heading_path"] or "[]"),
            "element": {"text": row["text"] or row["ocr_text"] or "",
                        "element_type": row["element_type"]},
            "context": [{"element_id": n["element_id"], "page": n["page_no"],
                         "element_type": n["element_type"],
                         "text": (n["text"] or n["ocr_text"] or "")[:600]}
                        for n in neighbours if n["element_id"] != element_id],
        }
    finally:
        if own:
            conn.close()


def resolve_document_version(identifier: str, *, at: str | None = None,
                             conn: sqlite3.Connection | None = None) -> dict | None:
    """Resolve a document or approval id to its supersession chain and active member."""
    own = conn is None
    conn = conn or connect()
    try:
        row = conn.execute("SELECT * FROM documents WHERE document_id=? OR source_path=?",
                           (identifier, identifier)).fetchone()
        if row is None and APPROVAL_RE.search(identifier or ""):
            aid = APPROVAL_RE.search(identifier).group(1)
            row = conn.execute(
                "SELECT * FROM documents WHERE source_path LIKE ? OR title LIKE ? LIMIT 1",
                (f"%{aid}%", f"%{aid}%")).fetchone()
        if row is None:
            return None
        chain_ids = supersession_chain(conn, row["document_id"])
        chain = []
        for did in chain_ids:
            d = conn.execute("""SELECT document_id, source_path, title, version_status,
                    date_or_version, issue_date, expiration_date FROM documents
                    WHERE document_id=?""", (did,)).fetchone()
            if d:
                chain.append(dict(d))
        active = [c for c in chain if c["version_status"] == "active"]
        newest = chain[-1] if chain else None
        result = {
            "query": identifier,
            "document_id": row["document_id"],
            "status": row["version_status"],
            "status_basis": row["version_status_basis"],
            "chain": chain,
            "active": active[0] if active else (newest if newest and
                                                newest["version_status"] != "superseded" else None),
            "newest_in_chain": newest,
        }
        if at:
            effective = [c for c in chain
                         if (c.get("issue_date") or "") and str(c["issue_date"]) <= at]
            result["effective_at"] = effective[-1] if effective else None
            result["effective_at_basis"] = ("issue dates are sparse in this corpus; "
                                            "None means no member has a parseable issue date "
                                            "at or before the requested date")
        return result
    finally:
        if own:
            conn.close()
