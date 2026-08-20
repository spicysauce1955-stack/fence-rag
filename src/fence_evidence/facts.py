"""Phase 6 — structured technical facts with mandatory provenance.

A fact is only ever *derived* from a canonical element; it never replaces one.
Every row records the element it came from, the original wording, the original
and normalised value (prohibition 7), the conditions it holds under, and a
review status.  Facts read out of OCR text on a low-confidence page are created
as ``flagged`` rather than ``extracted``, because a misread digit in a footing
depth is a structural error, not a typo.
"""
from __future__ import annotations

import json
import re
import sqlite3
from typing import Iterator

from .store import connect, now

OCR_REVIEW_CONFIDENCE = 80.0

_NUM = r"(\d+(?:[.½¾/]\d+)?)"
_IN = r"(?:in\.?|inch(?:es)?|\")"
_FT = r"(?:ft\.?|feet|foot|')"

PATTERNS: list[tuple[str, re.Pattern, str]] = [
    ("wind_speed_mph", re.compile(rf"{_NUM}\s*mph", re.I), "mph"),
    ("exposure_category", re.compile(r"exposure\s*(?:category|categories)?\s*[:\-]?\s*([BCD])\b", re.I), ""),
    ("footing_depth_in", re.compile(
        rf"(?:depth|embedment|embed(?:ded)?|below\s+grade)\D{{0,24}}{_NUM}\s*(?:{_IN}|{_FT})", re.I), "in"),
    ("footing_depth_in", re.compile(
        rf"{_NUM}\s*(?:{_IN}|{_FT})\s*(?:deep|depth|embedment|below\s+grade)", re.I), "in"),
    ("footing_diameter_in", re.compile(
        rf"(?:diam(?:eter)?\.?|dia\.?)\D{{0,16}}{_NUM}\s*(?:{_IN}|{_FT})", re.I), "in"),
    ("footing_diameter_in", re.compile(
        rf"{_NUM}\s*(?:{_IN}|{_FT})\s*(?:diam(?:eter)?\.?|dia\.?)", re.I), "in"),
    ("post_spacing_in", re.compile(
        rf"{_NUM}\s*(?:{_IN}|{_FT})?\s*(?:on\s*cent(?:er|re)|o\.?\s?c\.?)\b", re.I), "in"),
    ("racking_degrees", re.compile(rf"rack(?:s|ing|able)?\D{{0,24}}{_NUM}\s*(?:degrees?|deg\.?|°)", re.I), "deg"),
    ("approval_id", re.compile(r"\b(\d{2}-\d{4}\.\d{2})\b"), ""),
    ("reinforcement", re.compile(
        r"((?:aluminum|steel|galvanized)[^.\n]{0,60}?(?:stiffener|insert|channel|reinforcement))", re.I), ""),
    ("expiration_date", re.compile(
        r"expir(?:es|ation)\D{0,20}(\d{1,2}/\d{1,2}/\d{2,4}|\w+ \d{1,2},? \d{4})", re.I), ""),
    ("effective_date", re.compile(
        r"(?:approv(?:ed|al)|issued|effective)\D{0,20}(\d{1,2}/\d{1,2}/\d{2,4}|\w+ \d{1,2},? \d{4})", re.I), ""),
]

_FRACTIONS = {"½": 0.5, "¾": 0.75, "¼": 0.25}


def _to_float(raw: str) -> float | None:
    raw = raw.strip()
    for glyph, val in _FRACTIONS.items():
        if glyph in raw:
            whole = raw.replace(glyph, "").strip()
            try:
                return (float(whole) if whole else 0.0) + val
            except ValueError:
                return val
    if "/" in raw:
        try:
            a, b = raw.split("/")
            return float(a) / float(b)
        except (ValueError, ZeroDivisionError):
            return None
    try:
        return float(raw)
    except ValueError:
        return None


def _normalise(fact_type: str, raw: str, match_text: str) -> tuple[float | None, str | None]:
    """Return (normalised value, normalised unit).  Original is stored untouched."""
    value = _to_float(raw)
    if value is None:
        return None, None
    if fact_type.endswith("_in"):
        # feet in the source are converted; the original wording still says feet
        if re.search(rf"{_NUM}\s*(?:{_FT})", match_text, re.I) and \
                not re.search(rf"{_NUM}\s*(?:{_IN})", match_text, re.I):
            return round(value * 12.0, 3), "in"
        return round(value, 3), "in"
    if fact_type == "wind_speed_mph":
        return round(value, 3), "mph"
    if fact_type == "racking_degrees":
        return round(value, 3), "deg"
    return None, None


_COND_WIND = re.compile(rf"{_NUM}\s*mph", re.I)
_COND_EXPOSURE = re.compile(r"exposure\s*(?:category)?\s*[:\-]?\s*([BCD])\b", re.I)
_COND_HEIGHT = re.compile(rf"{_NUM}\s*(?:{_FT})\s*(?:high|tall|height|fence)", re.I)
_COND_HVHZ = re.compile(r"\bHVHZ\b", re.I)


def _conditions(text: str, heading_path: list[str]) -> dict:
    hay = text + " " + " ".join(heading_path)
    cond: dict = {}
    m = _COND_WIND.search(hay)
    if m:
        cond["wind_speed_mph"] = _to_float(m.group(1))
    m = _COND_EXPOSURE.search(hay)
    if m:
        cond["exposure_category"] = m.group(1).upper()
    m = _COND_HEIGHT.search(hay)
    if m:
        cond["fence_height_ft"] = _to_float(m.group(1))
    if _COND_HVHZ.search(hay):
        cond["hvhz"] = True
    return cond


def _iter_candidates(conn: sqlite3.Connection, document_id: str | None) -> Iterator[sqlite3.Row]:
    sql = """SELECT e.element_id, e.document_id, e.version_id, e.page_no, e.element_type,
                    e.text, e.ocr_text, e.text_source, e.ocr_confidence, e.heading_path
               FROM elements e"""
    params: tuple = ()
    if document_id:
        sql += " WHERE e.document_id = ?"
        params = (document_id,)
    yield from conn.execute(sql, params)


def extract_facts(*, document_id: str | None = None,
                  conn: sqlite3.Connection | None = None) -> dict:
    own = conn is None
    conn = conn or connect()
    try:
        if document_id:
            conn.execute("DELETE FROM facts WHERE document_id=?", (document_id,))
        else:
            conn.execute("DELETE FROM facts")
        counts: dict[str, int] = {}
        flagged = 0
        total = 0
        for row in _iter_candidates(conn, document_id):
            text = row["text"] or row["ocr_text"] or ""
            if not text.strip():
                continue
            from_ocr = row["text_source"] in ("ocr", "image_ocr")
            conf = row["ocr_confidence"]
            heading_path = json.loads(row["heading_path"] or "[]")
            conditions = _conditions(text, heading_path)
            seen: set[tuple] = set()
            for fact_type, rx, unit in PATTERNS:
                for m in rx.finditer(text):
                    raw = m.group(1)
                    key = (fact_type, raw.strip().lower())
                    if key in seen:
                        continue
                    seen.add(key)
                    norm, norm_unit = _normalise(fact_type, raw, m.group(0))
                    if fact_type.endswith("_in") and norm is not None and not (1 <= norm <= 400):
                        continue   # implausible as an inch dimension
                    if fact_type == "wind_speed_mph" and norm is not None and not (30 <= norm <= 250):
                        continue
                    review = "extracted"
                    if from_ocr and (conf is None or conf < OCR_REVIEW_CONFIDENCE):
                        review = "flagged"
                    start = max(0, m.start() - 90)
                    conn.execute("""INSERT INTO facts(document_id, version_id, page_no,
                        element_id, fact_type, subject, value_original, value_normalized,
                        unit_original, unit_normalized, conditions, evidence_text,
                        extractor, ocr_derived, review_status, created_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (row["document_id"], row["version_id"], row["page_no"],
                         row["element_id"], fact_type,
                         " > ".join(heading_path[-2:]) or None,
                         m.group(0).strip(), norm, unit or None, norm_unit,
                         json.dumps(conditions), text[start:m.end() + 90].strip(),
                         "regex-v1", int(from_ocr), review, now()))
                    counts[fact_type] = counts.get(fact_type, 0) + 1
                    total += 1
                    flagged += 1 if review == "flagged" else 0
        conn.commit()
        return {"facts": total, "flagged_for_review": flagged, "by_type": counts}
    finally:
        if own:
            conn.close()


def query_facts(fact_type: str | None = None, *, conditions: dict | None = None,
                manufacturer: str | None = None, limit: int = 20,
                include_flagged: bool = True,
                conn: sqlite3.Connection | None = None) -> list[dict]:
    """Look up facts with their provenance.  Never returns a value without a source."""
    own = conn is None
    conn = conn or connect()
    try:
        sql = """SELECT f.*, d.source_path, d.manufacturer, d.title, d.version_status,
                        p.page_image_path
                   FROM facts f
                   JOIN documents d ON d.document_id = f.document_id
              LEFT JOIN pages p ON p.version_id = f.version_id AND p.page_no = f.page_no
                  WHERE 1=1"""
        params: list = []
        if fact_type:
            sql += " AND f.fact_type = ?"
            params.append(fact_type)
        if manufacturer:
            sql += " AND d.manufacturer = ?"
            params.append(manufacturer)
        if not include_flagged:
            sql += " AND f.review_status IN ('extracted','reviewed')"
        sql += " ORDER BY d.version_status='active' DESC, f.page_no LIMIT ?"
        params.append(limit * 5 if conditions else limit)
        rows = [dict(r) for r in conn.execute(sql, params)]
        for r in rows:
            r["conditions"] = json.loads(r["conditions"] or "{}")
        if conditions:
            rows = [r for r in rows
                    if all(str(r["conditions"].get(k)) == str(v) for k, v in conditions.items())]
        return rows[:limit]
    finally:
        if own:
            conn.close()


if __name__ == "__main__":
    print(json.dumps(extract_facts(), indent=2))
