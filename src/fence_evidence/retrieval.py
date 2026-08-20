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
from .versions import (document_dates, effective_at, enrich_chain, expiry_status)
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

# --- second stage: within-page element retrieval ------------------------------
# The first stage ranks *units*: a projection that merges consecutive paragraphs
# and excludes headings entirely (headings carry 33.9% of their text nowhere
# else — see workspace/reports/projection-relevance-audit.md). So a returned unit
# can sit on the right page while the element naming the product, or holding the
# dimension, is not in it.
#
# The second stage searches inside each page the first stage already chose and
# attaches the one element that covers query terms the unit missed. It
# *augments*; it never replaces. Replacing was measured first and was worse —
# a merged unit's text covers more terms than any single element, so swapping it
# out lost evidence (unit support 0.540 against a 0.623 baseline).
#
# By construction the document set, page set, ordering and result count are
# untouched, so document recall and page-level support cannot change.
SECOND_STAGE_MAX_CHARS = 1400      # an augmenting element must be a passage, not a page blob
# Attachments are bounded deliberately. Attaching every element on the page
# would reach the within-page ceiling by definition and make the support metric
# meaningless — it would be returning the page, not retrieving within it. Each
# attachment must cover a query term the unit missed, and the set is capped both
# in count and in total characters.
SECOND_STAGE_MAX_ATTACHMENTS = 2
SECOND_STAGE_ATTACH_CHAR_BUDGET = 1400
# An attachment must be worth the reader's attention. Without a floor, a common
# brand token missing from the unit is enough to attach a phone number or a
# footer, because those do "cover a missing term". The floor is expressed against
# the corpus rather than against the query: the term an attachment contributes
# must be rarer than this share of the index. A query-relative floor (half the
# most informative missing term) was tried first and disabled the mechanism
# outright on ordinary queries.
SECOND_STAGE_MIN_TERM_DF_SHARE = 0.30
SECOND_STAGE_HEADING_PATH_WEIGHT = 0.25   # inherited context breaks ties, nothing more


SECOND_STAGE_MAX_NGRAM = 4
SECOND_STAGE_MAX_TERMS = 60


def _content_terms(sources: list[str], *, ngrams: bool = False) -> list[str]:
    """Query terms worth scoring: no stopwords, no bare units, deduplicated.

    With ``ngrams``, contiguous runs of the query's content words are added as
    phrase candidates. A single element that carries a whole product name
    (``Wellington 6x6 Semi-Privacy Panel``) is much better evidence than several
    elements that happen to mention those words separately, and only a phrase
    candidate can express that.
    """
    tokens: list[str] = []
    for raw in sources:
        t = raw.strip("\"'").lower()
        if len(t) < 2 or t in STOPWORDS or t in UNIT_WORDS or t in tokens:
            continue
        tokens.append(t)
    if not ngrams:
        return tokens
    out = list(tokens)
    words = [t for t in tokens if " " not in t]
    for n in range(2, SECOND_STAGE_MAX_NGRAM + 1):
        for i in range(len(words) - n + 1):
            phrase = " ".join(words[i:i + n])
            if phrase not in out:
                out.append(phrase)
    # longest first: a phrase should be credited before its component words
    out.sort(key=lambda t: -len(t))
    return out[:SECOND_STAGE_MAX_TERMS]


class _IdfCache:
    """Document frequency per term, from the unit index, memoised per query."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._df: dict[str, int] = {}
        self.total = conn.execute("SELECT COUNT(*) FROM retrieval_units").fetchone()[0] or 1

    def floor_for_df_share(self, share: float) -> float:
        """IDF of a term occurring in exactly ``share`` of the index."""
        import math
        return math.log(1.0 + 1.0 / max(share, 1e-9))

    def idf(self, term: str) -> float:
        import math
        if term not in self._df:
            try:
                row = self.conn.execute(
                    "SELECT COUNT(*) FROM retrieval_fts WHERE retrieval_fts MATCH ?",
                    ('"' + term.replace('"', '""') + '"',)).fetchone()
                self._df[term] = int(row[0]) if row else 0
            except sqlite3.Error:
                self._df[term] = 0
        return math.log(1.0 + self.total / (1.0 + self._df[term]))


def _own_text(row: sqlite3.Row) -> str:
    """The element's own content: source text, else OCR text, plus its caption."""
    parts = [(row["text"] or "").strip() or (row["ocr_text"] or "").strip(),
             (row["caption"] or "").strip()]
    return "\n".join(p for p in parts if p)


def _heading_text(row_or_list) -> str:
    if isinstance(row_or_list, list):
        return " > ".join(row_or_list)
    try:
        return " > ".join(json.loads(row_or_list["heading_path"] or "[]"))
    except (TypeError, ValueError, KeyError):
        return ""


def _terms_present(text: str, terms: list[str]) -> set[str]:
    low = (text or "").lower()
    return {t for t in terms if t in low}


def _second_stage(results: list["SearchResult"], sources: list[str],
                  conn: sqlite3.Connection) -> list["SearchResult"]:
    """Attach, per result, the within-page element covering terms the unit missed."""
    terms = _content_terms(sources, ngrams=True)
    if not terms or not results:
        return results
    idf = _IdfCache(conn)
    page_cache: dict[tuple[str, int], list[sqlite3.Row]] = {}
    claimed: set[str] = set(r.element_id for r in results)
    for r in results:
        key = (r.document_id, r.page)
        if key not in page_cache:
            page_cache[key] = conn.execute(
                """SELECT element_id, element_type, ordinal, text, ocr_text, text_source,
                          heading_path, caption, bbox, region_image_path, ocr_confidence
                     FROM elements WHERE document_id=? AND page_no=? ORDER BY ordinal""",
                (r.document_id, r.page)).fetchall()
        have = _terms_present("\n".join([r.text, _heading_text(r.heading_path or [])]), terms)
        missing = [t for t in terms if t not in have]
        if not missing:
            r.retrieval_reason["second_stage"] = {"attached": False,
                                                 "reason": "unit already covers every term"}
            continue
        attachments: list[dict] = []
        budget = SECOND_STAGE_ATTACH_CHAR_BUDGET
        still_missing = list(missing)
        gain_floor = idf.floor_for_df_share(SECOND_STAGE_MIN_TERM_DF_SHARE)
        while len(attachments) < SECOND_STAGE_MAX_ATTACHMENTS and still_missing:
            best, best_gain, best_added = None, 0.0, set()
            for row in page_cache[key]:
                if row["element_id"] in claimed:
                    continue
                own = _own_text(row)
                if not own.strip() or len(own) > min(SECOND_STAGE_MAX_CHARS, budget):
                    continue     # no text of its own, a page blob, or over budget
                added = _terms_present(own, still_missing)
                if not added:
                    continue
                gain = sum(idf.idf(t) for t in added)
                gain += SECOND_STAGE_HEADING_PATH_WEIGHT * sum(
                    idf.idf(t) for t in _terms_present(_heading_text(row), still_missing) - added)
                if gain > best_gain:
                    best, best_gain, best_added = row, gain, added
            if best is None or best_gain < gain_floor:
                break
            claimed.add(best["element_id"])
            own = _own_text(best)
            budget -= len(own)
            still_missing = [t for t in still_missing if t not in best_added]
            attachments.append({
                "element_id": best["element_id"],
                "element_type": best["element_type"],
                "text": own,
                "text_source": best["text_source"],
                "heading_path": json.loads(best["heading_path"] or "[]"),
                "bbox": json.loads(best["bbox"]) if best["bbox"] else None,
                "region_image_path": best["region_image_path"],
                "ocr_confidence": best["ocr_confidence"],
                "adds_terms": sorted(best_added),
                "gain": round(best_gain, 4),
            })
        if not attachments:
            r.retrieval_reason["second_stage"] = {
                "attached": False,
                "reason": "no element on this page covers a missing term informatively "
                          f"enough (gain floor {gain_floor:.2f})"}
            continue
        r.within_page_evidence = attachments
        r.retrieval_reason["second_stage"] = {
            "attached": True, "count": len(attachments),
            "adds_terms": sorted({t for a in attachments for t in a["adds_terms"]}),
            "basis": "idf-weighted coverage of query terms absent from the first-stage unit, "
                     "over all canonical elements on this page including headings",
        }
    return results


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
    # Second stage: bounded set of elements on this page covering query terms the
    # first-stage unit missed. None when the second stage is off, when the unit
    # already covered everything, or when the page had nothing to add.
    within_page_evidence: Optional[list[dict[str, Any]]] = None

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
                    min_score: float = 0.0,
                    second_stage: bool = False) -> list[SearchResult]:
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
        if second_stage:
            results = _second_stage(results, sources, conn)
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
                             as_of: str | None = None,
                             conn: sqlite3.Connection | None = None) -> dict | None:
    """Resolve a document or approval id to its supersession chain and active member.

    ``at`` asks which member was effective on that date. ``as_of`` is the date
    expiry is judged against; it defaults to today and is always echoed back, so
    a stale answer can never be mistaken for a timeless one.
    """
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
        # Phase 6 date facts, read at resolution time. Stored classification is
        # never overwritten from here; see fence_evidence.versions.
        chain = enrich_chain(conn, chain, as_of=as_of)
        active = [c for c in chain if c["version_status"] == "active"]
        newest = chain[-1] if chain else None
        selected = active[0] if active else (
            newest if newest and newest["version_status"] != "superseded" else None)
        active_basis = ("marked active by the corpus" if active else
                        "newest member of the chain and not marked superseded"
                        if selected else
                        "no member is marked active and the newest is superseded")
        # Conservative withdrawal: never present an expired approval as active.
        if selected is not None and selected["expiry"]["status"] == "expired":
            active_basis = (f"withdrawn: the member otherwise selected "
                            f"({selected['document_id']}) expired on "
                            f"{selected['expiry']['expiration']} as of "
                            f"{selected['expiry']['as_of']}")
            selected = None
        result = {
            "query": identifier,
            "document_id": row["document_id"],
            "status": row["version_status"],
            "status_basis": row["version_status_basis"],
            "dates": chain[-1]["dates"] if chain and chain[-1]["document_id"] == row["document_id"]
                     else document_dates(conn, row["document_id"]),
            "expiry": expiry_status(document_dates(conn, row["document_id"]), as_of=as_of),
            "chain": chain,
            "active": selected,
            "active_basis": active_basis,
            "newest_in_chain": newest,
        }
        if at:
            member = effective_at(chain, at)
            result["effective_at"] = member
            result["effective_at_basis"] = (
                "the chain member with the latest effective date at or before the "
                "requested date, taken from Phase 6 date facts; None means no member "
                "has an agreed effective date that early"
                if member is None else
                f"effective date {member['dates']['effective']['value']} from "
                f"{len(member['dates']['effective']['sources'])} source element(s)")
        return result
    finally:
        if own:
            conn.close()
