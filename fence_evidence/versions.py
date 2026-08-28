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

1. A fact marked `rejected` is ignored — a person looked at it and said the
   machine was wrong, so resolving on it is worse than having no date. The
   count of rejected facts is still reported, because a document whose only
   date was struck out is a different situation from one that never had a date.
2. Where a person corrected a fact, the *person's* value is what resolves.
   `reviews.effective_fact_value` is the single place that decides this; reading
   `facts.value_original` here would repeat G44 one layer out, and this reader
   is the one that decides whether an approval is in force.
3. If the facts of one type disagree, no value is returned — the candidates are
   reported as a conflict. Guessing which scan was read correctly is exactly the
   failure this system exists to avoid.
4. Every date is labelled with what it rests on, in `confidence`
   (`DATE_CONFIDENCE`), and the label is the *weakest* of its sources:

   ``review_required``
       At least one source is `flagged` — read off OCR below 80% confidence and
       still unreviewed. Unchanged from before the review loop existed.
   ``extracted``
       Machine extraction that nothing flagged and nobody checked.
   ``reviewed``
       Every source was accepted or corrected by a named person, which is
       curation level 2. This is a *stronger* claim than `extracted` and is
       kept distinct from it for the same reason `marked` and
       `inferred_in_force` are kept distinct below: "a person looked" and
       "a regex matched" are different evidence, and flattening them is how a
       corrected fact came to read as confidently as an unreviewed one.

   Being reviewed is not the same as being confident, and the vocabulary says
   so: a `reviewed` date beside an `extracted` one reports `extracted`, and a
   single unreviewed `flagged` source keeps the whole date `review_required`.
5. An expiry verdict is only given when the date is agreed and parseable, and
   the date it was evaluated against is always reported.
6. If the member otherwise selected as active has an agreed expiration date in
   the past, the active answer is withdrawn rather than asserted.

Where a value came from a correction, the machine's wording stays visible:
each source carries `original` (what the extractor read) beside `corrected`
(what the person read) and the `reviewer` who read it, and the date itself
carries `corrected_from` so a caller that never opens `sources` still cannot
act on a corrected date without knowing it was corrected. `expiry_status`
echoes that field through, because its verdict is the one a caller acts on.

`select_active` applies the same discipline to the "which member is in force?"
question, and — this is the point of it — labels *what the answer rests on*
rather than widening `active`. Four kinds of answer, never conflated:

``marked``
    A member carries ``version_status='active'``: a filename, a curated title or
    another document said so explicitly.
``inferred_in_force``
    Nothing is marked, but exactly one member that nothing supersedes has an
    agreed, parseable expiration date still in the future as of the stated day.
    This is an answer from evidence, and it is reported as a *different kind* of
    answer from an explicit mark so a caller can weigh it differently.
``assumed_newest``
    The old positional fallback — newest in the chain and not marked superseded
    — kept, but named for what it is: no version evidence at all.
``conflict`` / ``withdrawn`` / ``none``
    No value is asserted. Two members in force, two explicit marks, or
    expiration facts that disagree all produce ``conflict`` with the candidates
    listed; an expired selection produces ``withdrawn``, naming the expiry date
    and the day it was judged against.

A member marked ``superseded`` is never selected, whatever its dates say. The
*from* side of a ``superseded_by`` edge is the superseded document; reading that
edge backwards once labelled every current NOA superseded, and the guard against
repeating it belongs at the inference site too, not only in `relations.py`.

`document_edition` reads the edition stamp a document prints on itself — "WEB
REV 3.21", "Revised 2/2026". 33 documents in this corpus carry one and 31 of
those are classified `unknown`, so it is *not* true that the unclassified
documents have no version information in their bodies. It is true that the
information is not a status: an edition stamp says which printing this is, not
whether it is in force, and no two documents in this corpus were found to be the
same document at two different editions. So the edition is reported as evidence,
with the element it came from, and never turned into a `version_status`.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime

DATE_FACT_TYPES = ("effective_date", "expiration_date")

#: Every value `document_dates` can put in a date's ``confidence``, weakest
#: first. See rule 4 in the module docstring for what each one claims.
DATE_CONFIDENCE = ("review_required", "extracted", "reviewed")

#: The `facts.review_status` values that mean *a person compared this to the
#: source image*. `reviews.FACT_STATUS_FOR_VERDICT` writes `reviewed` for both
#: an acceptance and a correction; `promote_tables` writes `accepted` and
#: `corrected` for a fact promoted out of a reviewed table cell. The authority
#: on the set is `parameters.CURATION_LEVEL` — anything it scores at level 2
#: belongs here, and `tests/test_versions.py` fails if the two drift apart.
REVIEWED_FACT_STATUSES = ("accepted", "corrected", "reviewed")

#: Every value `select_active` can put in ``active_basis_kind``.  "marked" and
#: "inferred_in_force" both carry an answer and must stay distinguishable; the
#: rest carry none.
ACTIVE_BASIS_KINDS = ("marked", "inferred_in_force", "assumed_newest",
                      "conflict", "withdrawn", "none")

_MDY = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b")
_MONTH_D_Y = re.compile(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})\b")
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}


def _distinct(values: list[str]) -> list[str]:
    """Order-preserving dedupe, so two sources quoting one wording say it once."""
    seen: set[str] = set()
    out = []
    for v in values:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


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


def date_confidence(sources: list[dict]) -> str:
    """What a date rests on, taken from its WEAKEST source.

    Three labels, and the point of the third is that it is not the second.
    Before the fact review loop there were two — a `flagged` source meant
    `review_required` and everything else meant `extracted` — which was fine
    while nothing could be reviewed. It stops being fine the moment a person
    can accept or correct a fact: an accepted date and a date no human has ever
    looked at would report the same word, and a *corrected* one would report it
    while carrying a number the machine never read.

    Weakest-first is deliberate. A date agreed by two sources, one reviewed and
    one not, rests on the unreviewed one just as much; claiming `reviewed`
    there would assert a person checked something nobody checked.
    """
    statuses = {s.get("review_status") for s in sources}
    if "flagged" in statuses:
        return "review_required"
    if statuses and statuses <= set(REVIEWED_FACT_STATUSES):
        return "reviewed"
    return "extracted"


def document_dates(conn: sqlite3.Connection, document_id: str) -> dict:
    """Effective and expiration dates for one document, with provenance.

    The value a date resolves on is `reviews.effective_fact_value` — the
    person's wording where a review supplied one, the extractor's otherwise.
    The extractor's wording is never dropped: it stays on the source as
    `original`, and the date carries `corrected_from` so it is visible without
    opening `sources`.
    """
    from .reviews import effective_fact_value

    out: dict[str, dict] = {}
    for fact_type in DATE_FACT_TYPES:
        # Both value columns and both reviewed-value columns, so the row
        # satisfies `effective_fact_value` AND `effective_fact_normalized`.
        # Only the first is used here -- a date has no numeric scale -- but a
        # row that answers one helper and KeyErrors on the other is a trap.
        rows = conn.execute("""SELECT fact_id, value_original, value_normalized,
                    reviewed_value, reviewed_value_normalized, reviewer,
                    review_status, page_no, element_id, ocr_derived FROM facts
                   WHERE document_id=? AND fact_type=? AND review_status != 'rejected'
                   ORDER BY page_no""", (document_id, fact_type)).fetchall()
        # A date a person struck out is not the same as a date that was never
        # found, and a caller cannot tell the two apart from an empty answer.
        rejected = conn.execute(
            """SELECT COUNT(*) FROM facts
                WHERE document_id=? AND fact_type=? AND review_status='rejected'""",
            (document_id, fact_type)).fetchone()[0]
        candidates: dict[str, list[dict]] = {}
        unparsed: list[str] = []
        for r in rows:
            text = effective_fact_value(r)
            iso = parse_date(text)
            if iso is None:
                unparsed.append(text)
                continue
            source = {
                "element_id": r["element_id"], "page": r["page_no"],
                "original": r["value_original"], "review_status": r["review_status"],
                "ocr_derived": bool(r["ocr_derived"]),
            }
            if r["reviewed_value"] is not None:
                # `original` above is what the extractor read; these two say who
                # disagreed with it and what they read instead. G44 is what
                # happens when only one of the pair survives.
                source["corrected"] = r["reviewed_value"]
                source["reviewer"] = r["reviewer"]
            candidates.setdefault(iso, []).append(source)
        key = fact_type.split("_")[0]          # effective | expiration
        if not candidates:
            if unparsed:
                reason = f"{len(unparsed)} date fact(s) present but unparseable"
            elif rejected:
                reason = (f"{rejected} date fact(s) present; every one was "
                          f"rejected at review")
            else:
                reason = "no parseable date fact for this document"
            out[key] = {"value": None, "agreement": "none", "reason": reason,
                        "unparsed": unparsed, "sources": []}
        elif len(candidates) > 1:
            out[key] = {
                "value": None, "agreement": "conflict",
                "reason": "date facts disagree; no value asserted",
                "candidates": [{"value": v, "sources": s} for v, s in
                               sorted(candidates.items())],
                "sources": [],
            }
        else:
            value, sources = next(iter(candidates.items()))
            entry = {
                "value": value, "agreement": "unanimous",
                "confidence": date_confidence(sources),
                "occurrences": len(sources), "sources": sources,
            }
            corrected_from = _distinct([s["original"] for s in sources
                                        if "corrected" in s])
            if corrected_from:
                entry["corrected_from"] = corrected_from
            out[key] = entry
        if rejected:
            out[key]["rejected"] = rejected
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
    verdict = {"status": status, "as_of": as_of, "expiration": exp["value"],
               "confidence": exp.get("confidence", "extracted"),
               "basis": f"expiration {exp['value']} compared with {as_of}"}
    # This dict is what a caller acts on, and most callers never open `sources`.
    # A verdict resting on a date a person rewrote must say so where it is read.
    if exp.get("corrected_from"):
        verdict["corrected_from"] = list(exp["corrected_from"])
    return verdict


def enrich_chain(conn: sqlite3.Connection, chain: list[dict],
                 as_of: str | None = None) -> list[dict]:
    """Attach dates and an expiry verdict to each member of a supersession chain."""
    enriched = []
    for member in chain:
        m = dict(member)
        m["dates"] = document_dates(conn, m["document_id"])
        m["expiry"] = expiry_status(m["dates"], as_of=as_of)
        # Evidence about which printing this is. Never a status; see
        # document_edition.
        m["edition"] = document_edition(conn, m["document_id"])
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


# --------------------------------------------------------------------------
# Printed edition stamps
# --------------------------------------------------------------------------
#
# What this matches, and only this: the edition stamp a document prints on
# itself, always REV/WEB REV/Revised immediately followed by a month and a
# year -- "WEB REV 3.21", "REV. 4.24", "CAT36-D-634250 | Revised 2/2026".
#
# What it deliberately does not match, because all three occur in this corpus
# and none of them is the document's own edition:
#   "last revision #2 dated November 30, 2020"  -- a cited drawing's revision
#   "with Revision 4 dated 09/16/2009"          -- a cited test report's revision
#   "Description Date [Rev i | 24-0117.05"      -- OCR noise in a title block
# Requiring a month.year pair right after the word is what separates them; a
# bare "Revision <n>" is a revision of something the document is citing.
_EDITION = re.compile(
    r"(?<![A-Za-z])(?:WEB[\s-]*)?REV(?:ISED)?\.?\s*[:#]?\s*"
    r"(\d{1,2})\s*[./-]\s*(\d{2}|\d{4})(?![\d./-])", re.I)


def parse_edition(text: str) -> str | None:
    """``YYYY-MM`` from a printed edition stamp, or None if there is not one."""
    if not text:
        return None
    for m in _EDITION.finditer(text):
        month = int(m.group(1))
        if not 1 <= month <= 12:
            continue
        year = int(m.group(2))
        if year < 100:
            year += 2000
        if not 1990 <= year <= 2100:
            continue
        return f"{year:04d}-{month:02d}"
    return None


def document_edition(conn: sqlite3.Connection, document_id: str) -> dict | None:
    """The edition this document prints on itself, with the element it came from.

    Returns None when the document prints no stamp — which is the answer for
    111 of the 144 documents here, and saying so is the point. This is evidence
    about *which printing* a document is, never about whether it is in force:
    nothing in the return value is a `version_status` and nothing here writes
    one. Disagreeing stamps inside one document are reported as a conflict with
    no value, exactly as disagreeing date facts are.
    """
    rows = conn.execute("""SELECT element_id, page_no, text, ocr_text FROM elements
                            WHERE document_id=? ORDER BY page_no, ordinal""",
                        (document_id,)).fetchall()
    found: dict[str, list[dict]] = {}
    for r in rows:
        body = r["text"] or r["ocr_text"] or ""
        for m in _EDITION.finditer(body):
            value = parse_edition(m.group(0))
            if value is None:
                continue
            found.setdefault(value, []).append({
                "element_id": r["element_id"], "page": r["page_no"],
                "marker": m.group(0).strip(),
            })
    if not found:
        return None
    if len(found) > 1:
        return {"value": None, "agreement": "conflict",
                "reason": "the document prints more than one edition stamp",
                "candidates": [{"value": v, "sources": s}
                               for v, s in sorted(found.items())],
                "sources": []}
    value, sources = next(iter(found.items()))
    return {"value": value, "agreement": "unanimous",
            "occurrences": len(sources), "sources": sources,
            "is_version_status": False}


# --------------------------------------------------------------------------
# Which member of a chain is in force
# --------------------------------------------------------------------------

def _correction_note(member: dict) -> str:
    """A clause naming the correction an expiry answer rests on, or "".

    Empty while nothing is reviewed, which is why the basis strings over the
    live corpus are byte-identical to what they were. Once a date IS corrected,
    the prose that says why a member is in force must not quietly present a
    person's rewrite as the machine's reading.
    """
    exp = (member.get("dates") or {}).get("expiration") or {}
    was = exp.get("corrected_from")
    if not was:
        return ""
    return f"; that date was corrected at review from {', '.join(was)}"


def _no_answer(kind: str, basis: str, candidates: list[str] | None = None) -> dict:
    out = {"active": None, "active_basis_kind": kind, "active_basis": basis}
    if candidates is not None:
        out["active_candidates"] = candidates
    return out


def select_active(chain: list[dict], as_of: str | None = None) -> dict:
    """Which member of an enriched chain is in force, and on what evidence.

    ``chain`` is what `enrich_chain` returns: oldest first, each member carrying
    ``version_status``, ``dates`` and an ``expiry`` verdict. The answer is a
    dict with ``active`` (a chain member or None), ``active_basis_kind`` (one of
    `ACTIVE_BASIS_KINDS`) and a human-readable ``active_basis``; a conflict also
    carries ``active_candidates``.

    The kind is the load-bearing part. ``marked`` and ``inferred_in_force`` both
    hand back a member, but they rest on different things — an explicit marker
    against a date still in the future — and a caller that must not act on an
    inference can tell them apart without parsing prose.

    Nothing here writes to the store.
    """
    as_of = as_of or date.today().isoformat()
    if not chain:
        return _no_answer("none", "the chain is empty")

    # Never select a document another approval supersedes. The `from` side of a
    # `superseded_by` edge is the superseded document; this is the same
    # direction `relations.py` records and the guard tested in test_versions.
    candidates = [m for m in chain if m.get("version_status") != "superseded"]
    if not candidates:
        return _no_answer(
            "none", f"every member of the chain ({len(chain)}) is marked superseded")

    marked = [m for m in candidates if m.get("version_status") == "active"]
    if len(marked) > 1:
        return _no_answer(
            "conflict",
            f"{len(marked)} members of the chain are marked active; no value asserted",
            [m["document_id"] for m in marked])
    if marked:
        selected, kind = marked[0], "marked"
        basis = "marked active by the corpus"
    else:
        in_force = [m for m in candidates
                    if (m.get("expiry") or {}).get("status") == "in_force"]
        if len(in_force) > 1:
            return _no_answer(
                "conflict",
                f"{len(in_force)} members of the chain are in force as of {as_of} and "
                "none is marked active; no value asserted",
                [m["document_id"] for m in in_force])
        if in_force:
            selected, kind = in_force[0], "inferred_in_force"
            exp = selected["expiry"].get("expiration")
            basis = ("no member is marked active; inferred in force from an agreed "
                     f"expiration date {exp} still ahead of {as_of}, and nothing in "
                     "the chain supersedes it" + _correction_note(selected))
        else:
            selected, kind = candidates[-1], "assumed_newest"
            # The earlier wording said this rests on "no version evidence -- the
            # document states no date and carries no marker". Measured, that is
            # false for 31 of the 125 documents this branch answers for: they
            # print an edition stamp, `document_edition` reads it at 33/33
            # precision, and `enrich_chain` attaches it right here. The DECISION
            # is still right -- an edition says which printing this is, not
            # whether it is in force, and §G3 measures that no supersession is
            # inferable from one in this corpus -- but a basis string must not
            # deny something the member it describes is carrying.
            edition = (selected.get("edition") or {}).get("value")
            seen = (f"; it prints edition {edition}, which says which printing "
                    f"this is and not whether it is in force" if edition else "")
            basis = ("newest member of the chain and not marked superseded; this rests "
                     "on no EXPIRATION evidence and no explicit status marker" + seen)

    # Disagreeing evidence asserts nothing, whatever the positional reading says.
    expiration = (selected.get("dates") or {}).get("expiration") or {}
    if expiration.get("agreement") == "conflict":
        return _no_answer(
            "conflict",
            f"the expiration date facts for {selected['document_id']} disagree; "
            "no active value asserted",
            [selected["document_id"]])

    verdict = selected.get("expiry") or {}
    if verdict.get("status") == "expired":
        return _no_answer(
            "withdrawn",
            f"withdrawn: the member otherwise selected ({selected['document_id']}, "
            f"{kind}) expired on {verdict.get('expiration')} as of "
            f"{verdict.get('as_of', as_of)}" + _correction_note(selected))

    return {"active": selected, "active_basis_kind": kind, "active_basis": basis}


def chain_for(conn: sqlite3.Connection, document_id: str,
              as_of: str | None = None) -> list[dict]:
    """The enriched supersession chain for one document, oldest first.

    A read. `resolve_document_version` builds the same list inline; this exists
    so the active question can be asked — and tested — without going through
    retrieval, and so nothing has to re-derive the chain to do it.
    """
    from .relations import supersession_chain

    rows = []
    for did in supersession_chain(conn, document_id):
        d = conn.execute("""SELECT document_id, source_path, title, version_status,
                date_or_version, issue_date, expiration_date FROM documents
                WHERE document_id=?""", (did,)).fetchone()
        if d:
            rows.append(dict(d))
    return enrich_chain(conn, rows, as_of=as_of)
