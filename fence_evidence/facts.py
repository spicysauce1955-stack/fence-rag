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

# `6 in. (152 mm) diameter 24 in. (609.6 mm) deep` binds 24 to "diameter" on its
# left as readily as 6 binds to it on its right, and the store held exactly that
# -- `diameter 24 in.` twice, both of them the hole's DEPTH. Harmless while the
# blanking hid the real 6, self-contradictory once it does not. So a number that
# sits *after* the diameter word is refused when the words immediately following
# it say it is a depth. Only the diameter-first form is checked: `8 inches in
# diameter by 30 inches deep` is a true diameter whose sentence also ends in
# "deep", and the number-first pattern already binds it correctly.
_DIAM_FIRST = re.compile(rf"^{_DIAM_WORD}", re.I)
_DEPTH_TRAILER = re.compile(r"^\s*(?:deep|depth|embedment|below\s+grade)\b", re.I)
_DEPTH_TRAILER_WINDOW = 30


# --------------------------------------------------------------- G34 cause 1
# The parenthetical sits between the number and the keyword every pattern needs.
# `6 in. (152 mm) diameter` is a footing diameter that no pattern could ever see,
# because `(152 mm)` breaks the adjacency; so is `[6 inches (152 mm) below
# grade]`, and so is `24 in. (609.6 mm) deep`.
#
# The fix blanks the restatement **in place**: the parenthetical is replaced by
# exactly as many spaces as it occupied, so `len(blanked) == len(text)` and every
# character outside it keeps its index. Offsets are the one thing that must not
# move -- `_scan_text` reports `start`/`end` into the element's own text, the
# stored `match_text`, `evidence_text` and the obligation-4 alternate are all
# sliced back out of the *untouched* text at those offsets, and anything
# downstream that resolves an element span to a box would be resolving a
# different box if they shifted. Deleting the parenthetical instead of blanking
# it would shift every later offset in the element.
#
# Only *unit restatements* are blanked, never parentheticals in general. Blanking
# every `(...)` was measured against the corpus and is strictly worse: it gains
# nothing beyond what this gains and loses 40 facts, because the corpus states
# `(90 MPH)`, `(30" Deep)` and `(68in o.c. posts)` inside parentheses -- there,
# the parenthesis *is* the statement.
_PARENTHETICAL = re.compile(r"\([^()\n]{0,60}\)")
_METRIC_RESTATEMENT = re.compile(
    r"""^\(\s*\d+(?:[.,]\d+)?\s*
         (?:millimet(?:er|re)s?|centimet(?:er|re)s?|met(?:er|re)s?|mm|cm|m)
         \s*\.?\s*\)$""", re.IGNORECASE | re.VERBOSE)


def blank_unit_parentheticals(text: str) -> str:
    """Replace `(152 mm)` with spaces of the same length; leave everything else.

    Length-preserving by construction, so every offset into the result is a
    valid offset into ``text`` naming the same character. `dual_units` still
    reads the original, which is where the second unit obligation 4 wants lives.
    """
    return _PARENTHETICAL.sub(
        lambda m: " " * (m.end() - m.start()) if _METRIC_RESTATEMENT.match(m.group(0))
        else m.group(0), text)


# `on center` states the spacing of whatever noun governs it, and in this corpus
# that noun is usually not a post. Of the six `post_spacing_in` matches the
# blanking above recovers, five are hog-ring, carriage-bolt or tension-bar-hole
# spacings from one CSI masterspec; only "Line posts installed at intervals not
# exceeding 10 ft. (3.05 m) on center" is about posts. G34 names the same error
# from the other side -- a gate *opening* is a leaf width, not a spacing.
#
# A blocklist, not an allowlist, and checked as a window like the auger guard
# above: two of the three spacings the store already held are OCR'd NOA table
# rows (`YARROW SEMI PRIVACY ALTERNATING 4 4 84 48 ON CENTER`) that never say
# "post" at all, so requiring one would throw them away.
_SPACING_NOT_A_POST = re.compile(
    r"\b(?:bolts?|screws?|rivets?|nuts?|washers?|hog\s*rings?|rings?|ties?"
    r"|clips?|bands?|holes?|fasteners?|staples?|nails?|brackets?|clamps?"
    r"|hinges?|rails?|mesh|fabric|openings?)\b", re.I)
_SPACING_WINDOW = 60


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
    # Patterns run against the blanked copy; everything reported comes back out
    # of `text`. The two are the same length, so an offset means the same thing
    # in both -- see `blank_unit_parentheticals`.
    scanned = blank_unit_parentheticals(text)
    for fact_type, rx, unit in PATTERNS:
        for m in rx.finditer(scanned):
            raw = m.group(1)
            key = (fact_type, raw.strip().lower())
            if key in seen:
                continue
            seen.add(key)
            # The source's own wording, parenthetical included -- prohibition 7.
            # `m.group(0)` here would store the blanked text as if the document
            # had written it.
            match_text = text[m.start():m.end()]
            if fact_type == "footing_diameter_in":
                w = _DIAM_TOOL_CONTEXT_WINDOW
                window = text[max(0, m.start() - w):m.end() + w]
                if _DIAM_TOOL_CONTEXT.search(window):
                    continue   # a boring tool's diameter, not a footing's
                # `diameter 24 in. (609.6 mm) deep` -- that number is the depth.
                # Read the trailer off `scanned`, so a blanked restatement does
                # not fill the window before the keyword arrives.
                if _DIAM_FIRST.match(match_text) and _DEPTH_TRAILER.match(
                        scanned[m.end():m.end() + _DEPTH_TRAILER_WINDOW]):
                    continue
            if fact_type == "post_spacing_in":
                w = _SPACING_WINDOW
                before = text[max(0, m.start() - w):m.start()]
                if _SPACING_NOT_A_POST.search(before + match_text):
                    continue   # something other than a post is what is spaced
            norm, norm_unit = _normalise(fact_type, raw, match_text)
            lo_hi = PLAUSIBLE.get(fact_type)
            if lo_hi and norm is not None and not (lo_hi[0] <= norm <= lo_hi[1]):
                continue   # not credible for this quantity
            results.append({"fact_type": fact_type, "unit_original": unit,
                            "match_text": match_text.strip(), "raw": raw,
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
                            -- tie-broken on version_id, so this and
                            -- retrieval.get_page cannot disagree about which
                            -- version is newest when two land in one second
                            ROW_NUMBER() OVER (PARTITION BY document_id
                                               ORDER BY ingested_at DESC,
                                                        version_id DESC) rn
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


ALTERNATE_WINDOW = 40


def alternate_for(text: str, match: dict) -> dict | None:
    """Obligation 4's second unit for one `_scan_text` match, or None.

    A3's rule: look inside the value's own window, not the whole element, or a
    `(mm)` elsewhere on the page binds to the wrong number. The window is sliced
    from the **original** text -- the blanking `_scan_text` matches against is
    never seen here, which is the whole reason it preserves offsets.
    """
    return dual_units(text[match["start"]:match["end"] + ALTERNATE_WINDOW])


# --------------------------------------------------------------- A5, obligation 14
# "A part publishes its manufactured `stock_length` where a document states one."
#
# The value is CONDITIONAL, not scalar, and the condition is colour: the same rail
# is 16 ft in White and 12 ft in Blend, and at a 97" maximum spacing that is the
# difference between a member running continuously through an intermediate post
# and one cut per bay. Publishing a single number would licence a continuous rail
# in a colour not supplied long enough to be one.
#
# Neither "stock length" nor "standard length" occurs anywhere in this corpus.
# The real wording is "Standard rails are supplied in 16 foot lengths".
_SUPPLIED = re.compile(
    r"(?:supplied|furnished|available|sold|packaged)\s+in\s+"
    r"(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>foot|feet|ft\.?|inch(?:es)?|in\.?|')\s*"
    r"(?:long\s+)?(?:lengths?|sections?|rails?)", re.IGNORECASE)
# The parenthetical that carries the second colour: "(12 foot rails for Blend products)"
_ALT_COLOUR = re.compile(
    r"(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>foot|feet|ft\.?|')\s*rails?\s+for\s+"
    r"(?P<colour>[A-Z][A-Za-z]+)", re.IGNORECASE)
_FOR_COLOUR = re.compile(r"\blengths?\s+for\s+(?P<colour>[A-Z][A-Za-z]+)")

# Measured false positives. A price list is full of `8' Rail Insert Kit` and
# `PRIVACY FENCE FILL KITS 8' SECTIONS` -- product names, not statements about
# how rails are supplied -- and `cut to 95 1/2"` is what an installer does to a
# rail, not how it arrives.
_NOT_STOCK = re.compile(
    r"insert\s+kit|fill\s+kits?|\bkit\b|\bheights?\b|\bhigh\b|\bwide\b|\bwidth\b"
    r"|\bcut\s+to\b|\btrim\b|\bshorten|\bsubtract\b|\bSKU\b|Model\s*#"
    r"|\bcent(?:er|re)s?\b|\bon\s+cent|\bo\.?c\.?\b|\bspacing\b|\bapart\b"
    r"|(?:shim|cap)\s+stock|\bin\s+stock\b",
    re.IGNORECASE)

# A SKU dimension triple: `1-1/2" x 5-1/2" x 16' Rail`. This is where the data
# actually is -- 735 instances, against 11 in prose. The third dimension is the
# length; the first two are the profile.
_TRIPLE = re.compile(
    r"(?P<a>\d+(?:[-\s]\d+/\d+|\.\d+)?)\s*(?:\"|\u201d|in\.?|inch(?:es)?)\s*[xX\u00d7]\s*"
    r"(?P<b>\d+(?:[-\s]\d+/\d+|\.\d+)?)\s*(?:\"|\u201d|in\.?|inch(?:es)?)\s*[xX\u00d7]\s*"
    r"(?P<num>\d+(?:[-\s]\d+/\d+|\.\d+)?)\s*"
    r"(?P<unit>\"|\u201d|in\.?|inch(?:es)?|'|\u2019|ft\.?|foot|feet)\s*"
    r"(?P<trailer>[A-Za-z][A-Za-z \-]{0,28})", re.IGNORECASE)
# The trailing noun must be a linear part. A price list is full of spacer blocks,
# end loops and carrying cases that match the grammar exactly.
_PART_WORD = re.compile(r"\b(rail|post|picket|board|plank|spindle|baluster"
                        r"|channel|stiffener|insert)s?\b", re.IGNORECASE)
_NOT_PART = re.compile(r"block|spacer|wood|loop|pipe|screw|bolt|nail|bracket"
                       r"|hinge|latch|size|blend|kit|case", re.IGNORECASE)
# `- White` on the end of a SKU description. For Freedom, which lists the same
# 5x5 post at different lengths per colour, this suffix is the ONLY thing
# expressing the condition -- no sentence anywhere states it.
_SKU_COLOUR = re.compile(
    r"[-\u2013]\s*(White|Sand|Gray|Grey|Tan|Clay|Almond|Khaki|Mocha|Cypress"
    r"|Driftwood|Black|[A-Z][a-z]+\s+Blend|Blend)\b")

MIN_STOCK_IN, MAX_STOCK_IN = 48.0, 288.0        # 4 ft to 24 ft


def _fraction(num: str) -> float | None:
    """`16`, `93-3/4`, `5.5`, `7/8` -> a float; None where it is not a number.

    Returns None rather than raising: this is reached from a regex match, and a
    caller that gets None skips the match, where an exception would abort a whole
    extraction run over one odd string.
    """
    t = (num or "").strip().replace("\u2044", "/")
    if m := re.match(r"^(\d+)[-\s](\d+)/(\d+)$", t):          # 93-3/4
        return int(m.group(1)) + int(m.group(2)) / int(m.group(3))
    if m := re.match(r"^(\d+)/(\d+)$", t):                      # 7/8
        return int(m.group(1)) / int(m.group(2))
    try:
        return float(t)
    except ValueError:
        return None


def _to_inches(num: str, unit: str) -> float | None:
    # `_fraction`, not `float`: `_TRIPLE` deliberately captures `15-1/2` and
    # `93-3/4`, and a bare float() raises on both. That was an unguarded
    # ValueError in `cli facts --extract`.
    v = _fraction(num)
    if v is None:
        return None
    # Every glyph the corpus actually uses, not only the words. `93-3/4"` was
    # silently returning None -- so SKU triples whose length used the inch mark
    # were dropped rather than extracted, and nothing complained.
    u = unit.lower().rstrip(".")
    if u in ("foot", "feet", "ft", "'", "\u2019"):
        return v * 12.0
    if u in ("inch", "inches", "in", '"', "\u201d"):
        return v
    return None


def _stock_from_triples(text: str) -> list[dict]:
    """Lengths stated as the third dimension of a SKU triple."""
    out = []
    for m in _TRIPLE.finditer(text):
        trailer = m.group("trailer").strip()
        if _NOT_PART.search(trailer) or not (pw := _PART_WORD.search(trailer)):
            continue
        inches = _to_inches(m.group("num"), m.group("unit"))
        if inches is None or not (MIN_STOCK_IN <= inches <= MAX_STOCK_IN):
            continue
        cond = {"part": pw.group(1).lower()}
        # the trailer usually swallows the suffix ("Rail - White"), so look there
        # first and only then at what follows
        if c := _SKU_COLOUR.search(trailer + text[m.end():m.end() + 30]):
            cond["colour"] = c.group(1)
        out.append({
            "value_original": f"{m.group('num')} {m.group('unit').rstrip('.')}",
            "value_normalized": inches, "unit_original": m.group("unit"),
            "unit_normalized": "in", "conditions": cond,
            # The part is read off the SKU line itself; the colour, where present,
            # is a suffix the publisher wrote. Both are the document speaking.
            "condition_basis": "stated"})
    return out


def stock_lengths(text: str | None, *, element_type: str | None = None,
                  text_source: str | None = None) -> list[dict]:
    """Manufactured lengths a document states, with the colour that scopes them.

    Returns one dict per (length, condition) pair -- two for the White/Blend
    sentence, one for a bare statement. Empty where the text states no supplied
    length, which is the common case.
    """
    # Scanned NOA drawings OCR into text that looks exactly like a SKU triple but
    # states the *tested specimen's* members at 96" post spacing -- not orderable
    # lengths. 176 measured false positives, removed by refusing the element kind.
    if element_type in ("drawing", "drawing_label", "figure", "ocr_supplement"):
        return []
    if text_source in ("ocr", "image_ocr"):
        return []
    if not text or _NOT_STOCK.search(text):
        return []
    if triples := _stock_from_triples(text):
        return triples
    m = _SUPPLIED.search(text)
    if not m:
        return []
    inches = _to_inches(m.group("num"), m.group("unit"))
    if inches is None or not (MIN_STOCK_IN <= inches <= MAX_STOCK_IN):
        return []

    lexeme = f"{m.group('num')} {m.group('unit').rstrip('.')}"
    tail = text[m.end():]

    # "…16 foot lengths for White (12 foot rails for Blend products)"
    primary_colour = None
    if fc := _FOR_COLOUR.search(text[m.start():]):
        primary_colour = fc.group("colour")
    alts = [a for a in _ALT_COLOUR.finditer(tail)]

    out = []
    # The colour is `stated` only when the document names it in the same
    # sentence. A bare "supplied in 16 foot lengths" has no condition and must
    # not claim one -- `unexamined` says nobody looked for a colour, which is
    # true, rather than `assumed`, which would claim an inference.
    out.append({"value_original": f"{lexeme} lengths",
                "value_normalized": inches, "unit_original": m.group("unit"),
                "unit_normalized": "in",
                "conditions": {"colour": primary_colour} if primary_colour else {},
                "condition_basis": "stated" if primary_colour else "unexamined"})
    for a in alts:
        alt_in = _to_inches(a.group("num"), a.group("unit"))
        if alt_in is None or not (MIN_STOCK_IN <= alt_in <= MAX_STOCK_IN):
            continue
        out.append({"value_original": f"{a.group('num')} {a.group('unit').rstrip('.')} rails",
                    "value_normalized": alt_in, "unit_original": a.group("unit"),
                    "unit_normalized": "in",
                    "conditions": {"colour": a.group("colour")},
                    "condition_basis": "stated"})
    return out


def extract_facts(*, document_id: str | None = None,
                  conn: sqlite3.Connection | None = None) -> dict:
    own = conn is None
    conn = conn or connect()
    try:
        # Only regex-derived facts are regenerated here. Facts promoted from
        # verified table readings (extractor='table-read:...', see
        # promote_tables.py) must survive a re-extraction: promote_verified()
        # only ever promotes a candidate that no fact already names, so
        # deleting a regex fact cannot strand one. Note the pointer direction:
        # the FACT names the candidate, so deleting a fact takes its link with
        # it and nothing can dangle -- which is why the column was inverted.
        # See docs/layering.md §3.
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

            # A5 / obligation 14. Its own pass, because a stock length is
            # conditional on colour and part rather than on the wind/exposure
            # dimensions `_conditions` knows, and because the SKU-triple seam
            # needs the element's kind to reject scanned drawings.
            for sl in stock_lengths(text, element_type=row["element_type"],
                                    text_source=row["text_source"]):
                conn.execute("""INSERT INTO facts(document_id, version_id, page_no,
                    element_id, fact_type, subject, value_original, value_normalized,
                    unit_original, unit_normalized, conditions, condition_basis,
                    condition_basis_note, value_alternates, evidence_text,
                    extractor, ocr_derived, review_status, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (row["document_id"], row["version_id"], row["page_no"],
                     row["element_id"], "stock_length_in",
                     " > ".join(heading_path[-2:]) or None,
                     sl["value_original"], sl["value_normalized"],
                     sl["unit_original"], sl["unit_normalized"],
                     json.dumps(sl["conditions"]), sl["condition_basis"],
                     "the document states the part, and the colour where one is "
                     "given, on the same line as the length"
                     if sl["condition_basis"] == "stated" else None,
                     None, text[:180].strip(), "regex-v1", int(from_ocr),
                     "extracted", now()))
                counts["stock_length_in"] = counts.get("stock_length_in", 0) + 1
                total += 1
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
                alt = alternate_for(text, match)
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
