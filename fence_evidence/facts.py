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

from .paths import rel, resolve_asset
from .store import connect, now

OCR_REVIEW_CONFIDENCE = 80.0

# The negative lookbehind stops the number half of a fraction being captured on
# its own: "40 1/2\" On Center" must not yield a 2-inch spacing.
_NUM = r"(?<![\d/\u2044.])(\d+(?:[.½¾¼/\u2044]\d+)?)"
_IN = r"(?:in\.?|inch(?:es)?|\")"
_FT = r"(?:ft\.?|feet|foot|')"

# \b right after the word (before the optional trailing period) so this
# never matches inside "Diamond", "diagram" or "intermediate".
_DIAM_WORD = r"(?:diam(?:eter)?\b\.?|dia\b\.?)"

PATTERNS: list[tuple[str, re.Pattern, str]] = [
    ("wind_speed_mph", re.compile(rf"{_NUM}\s*mph", re.I), "mph"),
    ("exposure_category", re.compile(r"exposure\s*(?:category|categories)?\s*[:\-]?\s*([BCD])\b", re.I), ""),
    ("footing_depth_in", re.compile(
        rf"(?:depth|embedment|embed(?:ded)?)\D{{0,24}}{_NUM}\s*(?:{_IN}|{_FT})", re.I), "in"),
    ("footing_depth_in", re.compile(
        rf"{_NUM}\s*(?:{_IN}|{_FT})\s*(?:deep|depth|embedment)", re.I), "in"),
    # "below grade" is kept as its own type: in these manuals it more often
    # describes where the concrete stops than how deep the footing goes, and
    # conflating the two would put a wrong number under footing depth.
    ("depth_below_grade_in", re.compile(
        rf"{_NUM}\s*(?:{_IN}|{_FT})\s*below\s+grade", re.I), "in"),
    ("depth_below_grade_in", re.compile(
        rf"below\s+grade\D{{0,16}}{_NUM}\s*(?:{_IN}|{_FT})", re.I), "in"),
    # The number must bind *adjacently* to "diameter"/"dia" — either just
    # before it (with an optional connecting "in", as in "8 inches in
    # diameter"), or immediately after it with only trivial filler ("of",
    # or a colon/dash/comma). An arbitrary-width gap (the old \D{0,16}) lets
    # the match bridge across words like "by", "and" or "hole that is" to a
    # number describing something else entirely (usually the hole *depth*).
    # \b after the diam/dia word stops it matching inside an unrelated word
    # such as "Diamond", "diagram" or "intermediate".
    ("footing_diameter_in", re.compile(
        rf"{_DIAM_WORD}\s*(?:of\s*)?[:\-,]?\s*{_NUM}\s*(?:{_IN}|{_FT})", re.I), "in"),
    ("footing_diameter_in", re.compile(
        rf"{_NUM}\s*(?:{_IN}|{_FT})\s*(?:in\s+)?{_DIAM_WORD}", re.I), "in"),
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

# Values outside these ranges are not credible for the quantity named, so they
# are dropped rather than stored as facts a reviewer would have to refute.
PLAUSIBLE: dict[str, tuple[float, float]] = {
    "footing_depth_in": (6.0, 120.0),
    "depth_below_grade_in": (0.5, 120.0),
    "footing_diameter_in": (4.0, 60.0),
    "post_spacing_in": (12.0, 240.0),
    "wind_speed_mph": (30.0, 250.0),
    "racking_degrees": (0.5, 45.0),
}

# For these types the value *is* the condition, so re-deriving it as a condition
# from surrounding text can contradict the fact itself.
SELF_CONDITION = {"wind_speed_mph": "wind_speed_mph",
                  "exposure_category": "exposure_category"}

# A diameter phrase near "auger"/"drill"/"bit" is describing a boring tool,
# not a footing hole (e.g. "1 1/2in. diameter x 18in. auger bit") — a
# footing_diameter_in fact should never be produced from it. Checked as a
# small window of context around the match rather than folded into the regex
# itself, since the tool words can appear on either side of the number.
_DIAM_TOOL_CONTEXT = re.compile(r"\b(?:auger|drill|bit)\b", re.I)
_DIAM_TOOL_CONTEXT_WINDOW = 50


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


def _scan_text(text: str) -> list[dict]:
    """Run PATTERNS against raw element text; one dict per accepted match.

    Pure function, no database involved — this is what `extract_facts` calls
    per element, and what tests exercise directly against fixed evidence
    strings without needing a built store.
    """
    results: list[dict] = []
    seen: set[tuple] = set()
    for fact_type, rx, unit in PATTERNS:
        for m in rx.finditer(text):
            raw = m.group(1)
            key = (fact_type, raw.strip().lower())
            if key in seen:
                continue
            seen.add(key)
            if fact_type == "footing_diameter_in":
                w = _DIAM_TOOL_CONTEXT_WINDOW
                window = text[max(0, m.start() - w):m.end() + w]
                if _DIAM_TOOL_CONTEXT.search(window):
                    continue   # a boring tool's diameter, not a footing's
            norm, norm_unit = _normalise(fact_type, raw, m.group(0))
            lo_hi = PLAUSIBLE.get(fact_type)
            if lo_hi and norm is not None and not (lo_hi[0] <= norm <= lo_hi[1]):
                continue   # not credible for this quantity
            results.append({"fact_type": fact_type, "unit_original": unit,
                            "match_text": m.group(0).strip(), "raw": raw,
                            "value_normalized": norm, "unit_normalized": norm_unit,
                            "start": m.start(), "end": m.end()})
    return results


def _iter_candidates(conn: sqlite3.Connection, document_id: str | None) -> Iterator[sqlite3.Row]:
    # Only the newest version of each document contributes facts; an older
    # version's values stay in the store but are not re-asserted as current.
    sql = """SELECT e.element_id, e.document_id, e.version_id, e.page_no, e.element_type,
                    e.text, e.ocr_text, e.text_source, e.ocr_confidence, e.heading_path
               FROM elements e
               JOIN (SELECT document_id, version_id,
                            ROW_NUMBER() OVER (PARTITION BY document_id
                                               ORDER BY ingested_at DESC) rn
                       FROM document_versions) latest
                 ON latest.version_id = e.version_id AND latest.rn = 1"""
    params: tuple = ()
    if document_id:
        sql += " WHERE e.document_id = ?"
        params = (document_id,)
    yield from conn.execute(sql, params)


# Obligation 15's vocabulary. `unexamined` is ours, not the contract's: the
# regex matches a number and never asks what scoped it, and calling that
# `assumed` claims an inference nobody performed. It collapses on publish.
CONDITION_BASIS = ("stated", "assumed", "unexamined")


def publish_condition_basis(basis: str) -> str:
    """Collapse the internal vocabulary to the contract's `stated | assumed`."""
    return "stated" if basis == "stated" else "assumed"


# `4 inch (101 mm)` -- a parenthesised metric restatement of the value just
# given. 4" is 101.600 mm, so the document disagrees with itself by 0.6 mm, and
# obligation 4 says publish both rather than pick one. The unit alternatives are
# spelled out so `(see detail A)` and `(typical)` cannot match.
_DUAL_UNIT = re.compile(
    r"""(?P<num>\d+(?:\.\d+)?)\s*
        (?P<unit>mm|millimet(?:er|re)s?|cm|centimet(?:er|re)s?|m\b|met(?:er|re)s?)
        \s*\)""",
    re.IGNORECASE | re.VERBOSE)

_UNIT_NORMAL = {"mm": "mm", "millimeter": "mm", "millimetre": "mm",
                "millimeters": "mm", "millimetres": "mm",
                "cm": "cm", "centimeter": "cm", "centimetre": "cm",
                "centimeters": "cm", "centimetres": "cm",
                "m": "m", "meter": "m", "metre": "m", "meters": "m", "metres": "m"}


def dual_units(text: str | None) -> dict | None:
    """The second unit a source states for a value it has just given.

    Returns the alternate as its own verbatim lexeme plus a normalised value, or
    None where the source states only one unit. Obligation 4 wants **every**
    verbatim source lexeme, so this preserves the document's own digits rather
    than recomputing them -- `83 mm` stays `83 mm` even though 3-1/4" is 82.550.
    """
    if not text:
        return None
    # An opening paren must precede, or `4 inch 101 mm)` would match on noise.
    for m in _DUAL_UNIT.finditer(text):
        open_paren = text.rfind("(", 0, m.start())
        if open_paren == -1 or ")" in text[open_paren:m.start()]:
            continue
        unit = _UNIT_NORMAL.get(m.group("unit").lower())
        if not unit:
            continue
        return {"value_original": f"{m.group('num')} {unit}",
                "unit_original": unit,
                "value_normalized": float(m.group("num")),
                "unit_normalized": unit}
    return None


def extract_facts(*, document_id: str | None = None,
                  conn: sqlite3.Connection | None = None) -> dict:
    own = conn is None
    conn = conn or connect()
    try:
        # Only regex-derived facts are regenerated here. Facts promoted from
        # verified table readings (extractor='table-read:...', see
        # promote_tables.py) must survive a re-extraction: promote_verified()
        # only ever promotes a table_read_candidates row once
        # (`from_candidate_id IS NULL`), so deleting those facts here would
        # both destroy 300+ human/agent-gated readings and leave
        # facts.from_candidate_id pointing at rows that no
        # longer exist -- with no way to re-promote them, since the
        # candidate no longer looks unpromoted.
        if document_id:
            conn.execute("DELETE FROM facts WHERE document_id=? AND extractor LIKE 'regex-%'",
                        (document_id,))
        else:
            conn.execute("DELETE FROM facts WHERE extractor LIKE 'regex-%'")
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
            for match in _scan_text(text):
                fact_type = match["fact_type"]
                fact_conditions = dict(conditions)
                self_key = SELF_CONDITION.get(fact_type)
                if self_key:
                    fact_conditions.pop(self_key, None)
                review = "extracted"
                if from_ocr and (conf is None or conf < OCR_REVIEW_CONFIDENCE):
                    review = "flagged"
                start = max(0, match["start"] - 90)
                evidence = text[start:match["end"] + 90].strip()
                # A2. The regex captures conditions by *proximity* -- it matches
                # `exposure_category` near a number without establishing the
                # document attached them to it (G15 records that failure). So a
                # captured condition is `assumed`, and no conditions at all is
                # `unexamined`: nobody looked. Neither is `stated`, which would
                # require the document to have said so.
                basis = "assumed" if fact_conditions else "unexamined"
                # A3. Look for the second unit inside the value's own window,
                # not the whole element, or a `(mm)` elsewhere on the page binds
                # to the wrong number.
                alt = dual_units(text[match["start"]:match["end"] + 40])
                conn.execute("""INSERT INTO facts(document_id, version_id, page_no,
                    element_id, fact_type, subject, value_original, value_normalized,
                    unit_original, unit_normalized, conditions, condition_basis,
                    condition_basis_note, value_alternates, evidence_text,
                    extractor, ocr_derived, review_status, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (row["document_id"], row["version_id"], row["page_no"],
                     row["element_id"], fact_type,
                     " > ".join(heading_path[-2:]) or None,
                     match["match_text"], match["value_normalized"],
                     match["unit_original"] or None, match["unit_normalized"],
                     json.dumps(fact_conditions), basis,
                     "conditions captured by regex proximity, not asserted by the "
                     "document" if fact_conditions else None,
                     json.dumps([alt]) if alt else None,
                     evidence, "regex-v1", int(from_ocr), review, now()))
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
            # Same treatment as `conditions`, for the same reason: a caller
            # reading one row should not get a dict for one JSON column and a
            # raw string for the one beside it.
            r["value_alternates"] = json.loads(r["value_alternates"] or "[]")
            resolved_page_image = resolve_asset(r.get("page_image_path"))
            r["page_image_path"] = rel(resolved_page_image) if resolved_page_image else None
        if conditions:
            rows = [r for r in rows
                    if all(str(r["conditions"].get(k)) == str(v) for k, v in conditions.items())]
        return rows[:limit]
    finally:
        if own:
            conn.close()


if __name__ == "__main__":
    print(json.dumps(extract_facts(), indent=2))
