"""Read a Miami-Dade parts-list `PART DESCRIPTION` into its stated parts.

The drawings write a part as a type phrase plus, usually, dimensions:

    .875 X 3 X 71.5 PICKET
    #8 X 1 1/2" SET SCREWS
    HOURGLASS G-60 STEEL CHANNEL X 92
    .5 INCH BULLET CLIP
    SNAP CAP WASHER

`[measured]` 2026-09-14 over all 177 reviewed rows: 174 parse, 3 do not. The
three are `POST REINF. FULL LENGTH -1"`, which states a length *relative to
another part* and so carries no magnitude of its own. It is refused rather than
guessed -- publishing either 1 inch or the post's length would be an invention,
and this module's whole job is to publish only what the string states.

Two orderings are load-bearing:

* **The gauge pattern is tried first.** `#8` is a wire gauge. Matched by the
  two-dimension pattern it would publish a 3/4-inch screw as 8 inches -- the
  G63 shape, a unit misread shipping a number an order of magnitude wrong.
* **A cross-section is never split into named dimensions.** `2 X 4` publishes
  as one token, because naming them width and height asserts which way up the
  rail runs, and `knowledge-datamodel.md` says a `Part` "never says where it
  goes, how it joins, or which way up it runs".

Exact `Fraction`s throughout: `.875` and `7/8` are the same piece and must mint
one id, and no float may reach `canonical.canonical_bytes`.
"""
from __future__ import annotations

import re
from fractions import Fraction

# A magnitude as these drawings write one: `71.5`, `1 1/2`, `3/4`, `92`, with an
# optional inch mark. Mixed numbers come first so `1 1/2` does not read as `1`.
_NUM = r'(?:\d+\s+\d+/\d+|\d+/\d+|\d*\.\d+|\d+)"?'
_X = r'\s*[xX]\s*'


def _magnitude(text: str) -> Fraction:
    """`1 1/2` -> 3/2. Exact; never a float."""
    t = text.strip().rstrip('"').strip()
    if " " in t:
        whole, frac = t.split(None, 1)
        return Fraction(whole) + Fraction(frac)
    return Fraction(t)


# Ordered. First match wins, and the order is the safety property -- see module
# docstring. Each entry is (name, compiled pattern).
_PATTERNS = (
    # #8 X 1 1/2" SET SCREWS  -- gauge, length, type
    ("gauge", re.compile(rf'^(?P<gauge>#\d+){_X}(?P<length>{_NUM})\s+(?P<type>.+)$')),
    # .875 X 3 X 71.5 PICKET  -- section pair, length, type
    ("section_length", re.compile(
        rf'^(?P<a>{_NUM}){_X}(?P<b>{_NUM}){_X}(?P<length>{_NUM})\s+(?P<type>.+)$')),
    # 1 3/4" X 3 1/2" RAIL  -- section pair only
    ("section", re.compile(rf'^(?P<a>{_NUM}){_X}(?P<b>{_NUM})\s+(?P<type>.+)$')),
    # ALUMINUM CHANNEL X 92 FOR 3.5 SQ. RAIL  -- type first, length last
    ("type_length", re.compile(
        rf'^(?P<type>.+?){_X}(?P<length>{_NUM})(?:\s+FOR\s+(?P<qualifier>.+))?$')),
    # .5 INCH BULLET CLIP  -- a size whose role the string does not state
    ("size", re.compile(rf'^(?P<size>{_NUM})\s+INCH\s+(?P<type>.+)$')),
)

# A description that names a length only by reference to another part -- it
# states no magnitude of its own, so it is refused rather than parsed.
#
# Matched on `FULL LENGTH` alone. A first cut also treated a leading minus as
# relational and refused `HOURGLASS G-60 STEEL CHANNEL X 92`, because `G-60` is
# a steel grade, not arithmetic. Broad refusals are as wrong as broad guesses:
# each one silently drops a part a person had already reviewed.
_RELATIONAL = re.compile(r'\bFULL\s+LENGTH\b', re.I)


def parse_description(text: str | None) -> dict | None:
    """The piece this string states, or None when it states no parseable piece.

    Returns `{type_phrase, section, length_in, size_in, gauge, qualifier}` with
    `Fraction` magnitudes. `None` means refuse: the caller raises a gap and
    publishes nothing, which is the only honest answer for a string this module
    does not understand.
    """
    if not text or not text.strip():
        return None
    normalised = " ".join(text.split())
    if _RELATIONAL.search(normalised):
        return None
    for name, pattern in _PATTERNS:
        m = pattern.match(normalised)
        if not m:
            continue
        groups = m.groupdict()
        type_phrase = (groups.get("type") or "").strip()
        if not type_phrase:
            continue
        return {
            "pattern": name,
            "type_phrase": type_phrase,
            "section": (f'{groups["a"].rstrip(chr(34))} X {groups["b"].rstrip(chr(34))}'
                        if groups.get("a") else None),
            "length_in": _magnitude(groups["length"]) if groups.get("length") else None,
            "size_in": _magnitude(groups["size"]) if groups.get("size") else None,
            "gauge": groups.get("gauge"),
            "qualifier": (groups.get("qualifier") or "").strip() or None,
        }
    # No dimension at all: the whole string is the type.
    return {"pattern": "type_only", "type_phrase": normalised, "section": None,
            "length_in": None, "size_in": None, "gauge": None, "qualifier": None}
