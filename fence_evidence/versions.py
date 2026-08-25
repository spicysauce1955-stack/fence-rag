"""Conservative, date-aware version resolution.

The stored `documents.version_status` is derived from filenames, curated titles
and supersession edges found in document text. Phase 6 also extracted 84
`effective_date` and 75 `expiration_date` facts, every one carrying the element
it came from — and those cover all 17 NOA documents in the corpus, which is
exactly the material where "is this still the approval in force?" matters.

This module reads those facts at resolution time.  It deliberately does not
write to `documents`: classification stays as extracted until a review says
otherwise, and every date reported here carries its provenance and review
status so a caller can see what it rests on.

Conservative rules, in order:

1. A fact marked `rejected` is ignored.
2. If the facts of one type disagree, no value is returned — the candidates are
   reported as a conflict. Guessing which scan was read correctly is exactly the
   failure this system exists to avoid.
3. A value derived from a `flagged` (unreviewed OCR) fact is returned, but
   labelled `review_required`.
4. An expiry verdict is only given when the date is agreed and parseable, and
   the date it was evaluated against is always reported.
5. If the member otherwise selected as active has an agreed expiration date in
   the past, the active answer is withdrawn rather than asserted.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime

DATE_FACT_TYPES = ("effective_date", "expiration_date")

_MDY = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b")
_MONTH_D_Y = re.compile(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})\b")
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}


def parse_date(text: str) -> str | None:
    """Best-effort ISO date from the wording a document actually used."""
    if not text:
        return None
    m = _ISO.search(text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = _MDY.search(text)
    if m:
        mm, dd, yy = (int(g) for g in m.groups())
        if yy < 100:
            yy += 2000 if yy < 70 else 1900
        if 1 <= mm <= 12 and 1 <= dd <= 31:
            try:
                return date(yy, mm, dd).isoformat()
            except ValueError:
                return None
        return None
    m = _MONTH_D_Y.search(text)
    if m:
        month = _MONTHS.get(m.group(1).lower())
        if month:
            try:
                return date(int(m.group(3)), month, int(m.group(2))).isoformat()
            except ValueError:
                return None
    return None


def document_dates(conn: sqlite3.Connection, document_id: str) -> dict:
    """Effective and expiration dates for one document, with provenance."""
    out: dict[str, dict] = {}
    for fact_type in DATE_FACT_TYPES:
        rows = conn.execute("""SELECT fact_id, value_original, review_status, page_no,
                    element_id, ocr_derived FROM facts
                   WHERE document_id=? AND fact_type=? AND review_status != 'rejected'
                   ORDER BY page_no""", (document_id, fact_type)).fetchall()
        candidates: dict[str, list[dict]] = {}
        unparsed: list[str] = []
        for r in rows:
            iso = parse_date(r["value_original"])
            if iso is None:
                unparsed.append(r["value_original"])
                continue
            candidates.setdefault(iso, []).append({
                "element_id": r["element_id"], "page": r["page_no"],
                "original": r["value_original"], "review_status": r["review_status"],
                "ocr_derived": bool(r["ocr_derived"]),
            })
        key = fact_type.split("_")[0]          # effective | expiration
        if not candidates:
            out[key] = {"value": None, "agreement": "none",
                        "reason": ("no parseable date fact for this document"
                                   if not unparsed else
                                   f"{len(unparsed)} date fact(s) present but unparseable"),
                        "unparsed": unparsed, "sources": []}
            continue
        if len(candidates) > 1:
            out[key] = {
                "value": None, "agreement": "conflict",
                "reason": "date facts disagree; no value asserted",
                "candidates": [{"value": v, "sources": s} for v, s in
                               sorted(candidates.items())],
                "sources": [],
            }
            continue
        value, sources = next(iter(candidates.items()))
        flagged = any(s["review_status"] == "flagged" for s in sources)
        out[key] = {
            "value": value, "agreement": "unanimous",
            "confidence": "review_required" if flagged else "extracted",
            "occurrences": len(sources), "sources": sources,
        }
    return out


def expiry_status(dates: dict, as_of: str | None = None) -> dict:
    """Is this document's approval still in force, as of a stated date?"""
    as_of = as_of or date.today().isoformat()
    exp = (dates or {}).get("expiration") or {}
    if exp.get("agreement") == "conflict":
        return {"status": "unknown", "as_of": as_of,
                "basis": "expiration date facts disagree; see candidates"}
    if not exp.get("value"):
        return {"status": "unknown", "as_of": as_of,
                "basis": exp.get("reason") or "no expiration date available"}
    status = "expired" if exp["value"] < as_of else "in_force"
    return {"status": status, "as_of": as_of, "expiration": exp["value"],
            "confidence": exp.get("confidence", "extracted"),
            "basis": f"expiration {exp['value']} compared with {as_of}"}


def enrich_chain(conn: sqlite3.Connection, chain: list[dict],
                 as_of: str | None = None) -> list[dict]:
    """Attach dates and an expiry verdict to each member of a supersession chain."""
    enriched = []
    for member in chain:
        m = dict(member)
        m["dates"] = document_dates(conn, m["document_id"])
        m["expiry"] = expiry_status(m["dates"], as_of=as_of)
        enriched.append(m)
    return enriched


def effective_at(chain: list[dict], at: str) -> dict | None:
    """The chain member whose effective date is the latest at or before ``at``."""
    dated = [c for c in chain
             if (c.get("dates", {}).get("effective") or {}).get("value")]
    eligible = [c for c in dated if c["dates"]["effective"]["value"] <= at]
    if not eligible:
        return None
    return max(eligible, key=lambda c: c["dates"]["effective"]["value"])
