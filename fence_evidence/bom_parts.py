"""Publish a `Part` from a parts-list row a person reviewed against its crop.

`[measured]` 2026-09-14: 177 reviewed parts-list rows across 5 Miami-Dade NOAs,
531 cells, one reviewer, every row `accepted` or `corrected`. They publish
nothing today, while the 42 `Part`s that do publish come from hand-written
Python modules carrying values transcribed into source.

The difference this module makes is the provenance, not the count: every number
it publishes traces to a row a named person compared against the image this
store holds, and `curation_level` is READ from that review column rather than
asserted.

Two refusals do the real work, and both were shaped by defects this project has
already paid for:

* a description the parser does not understand publishes nothing (`bom_parse`)
* a type phrase with no spine mapping publishes nothing. Guessing that
  `SNAP CAP` -- a screw cover -- is a `post_cap` is the G62 shape: an invented
  attribution that shipped once and had to be reversed.
"""
from __future__ import annotations

import re
from fractions import Fraction

from .part_types import COMPONENT_TYPE_SPINE, mfr_namespace

# Drawing phrase -> the `COMPONENT_TYPE_SPINE` key it hangs from. Longest match
# wins, so `ROUTED RAIL` and `DECO RAIL` both reach `rail` without `RAIL` having
# to be listed first.
#
# Deliberately partial. `[measured]` 43 of 177 rows name a phrase that is not
# here -- LOCK RING, BULLET CLIP, SNAP CAP, SNAP CAP WASHER, HORIZONTAL and
# VERTICAL CHANNEL. Those publish nothing and raise a gap naming the phrase,
# because a person deciding what a lock ring IS takes a minute and inventing it
# takes a reversal.
BOM_TYPE_SPINE = {
    "ROUTED POST": "post",
    "POST": "post",
    "ROUTED RAIL": "rail",
    "DECO RAIL": "rail",
    "ACCENT RAIL": "rail",
    "RAIL": "rail",
    "HORIZONTAL BEAM": "rail",
    "TONGUE AND GROOVE PICKET": "picket",
    "RIBBED PICKET": "picket",
    "PICKETS": "picket",
    "PICKET": "picket",
    "SET SCREWS": "fastener",
    "SET SCREW": "fastener",
    "SCREWS": "fastener",
    "SCREW": "fastener",
    "ALUMINUM CHANNEL": "post_stiffener_aluminum",
    "HOURGLASS G-60 STEEL CHANNEL": "post_stiffener_aluminum",
    "U-SHAPED G-60 STEEL CHANNEL": "post_stiffener_aluminum",
    "U-SHAPPED G-60 STEEL CHANNEL": "post_stiffener_aluminum",
}

# `U-SHAPPED` is the drawing's own misspelling -- the reviewer corrected TOWARD
# it, which is evidence about the source and must survive in `value_raw`. It is
# unified here, at the type level, and never repaired in the lexeme.
_SPINE_PHRASES = sorted(BOM_TYPE_SPINE, key=len, reverse=True)


def spine_type(type_phrase: str | None) -> str | None:
    """The spine key this phrase hangs from, or None to refuse.

    None is a decision, not a failure: the caller raises a gap naming the
    phrase so a person can map it, and publishes nothing meanwhile.
    """
    if not type_phrase:
        return None
    upper = " ".join(type_phrase.upper().split())
    for phrase in _SPINE_PHRASES:
        if upper == phrase or upper.endswith(" " + phrase) or upper.startswith(phrase + " "):
            return BOM_TYPE_SPINE[phrase]
    return None


def _decimal(value: Fraction) -> str:
    """`Fraction(143, 2)` -> `71-5`. Exact, and stable across spellings.

    `.875` and `7/8` reach the same string, which is the whole point: they are
    one thickness and a fork would publish one piece twice.
    """
    as_float = float(value)
    text = f"{as_float:.4f}".rstrip("0").rstrip(".")
    return text.replace(".", "-")


def bom_part_id(parsed: dict | None, manufacturer: str) -> str | None:
    """`mfr/certainteed/…`-style id, flat at two segments, or None to refuse.

    Two segments deliberately: `reach._part_family` takes `rsplit("/", 1)[0]`,
    so a third segment would mint an identity family nothing declares an
    association with -- G106 seen from the other end.

    Keyed on what the document STATES -- type and dimensions -- never on a
    product family. `parameters._default_scope`-style slugs forked one NOA
    lineage into five ids that reached nobody (G112); this does not repeat it.
    """
    if not parsed:
        return None
    kind = spine_type(parsed.get("type_phrase"))
    if kind is None:
        return None
    bits = [kind]
    if parsed.get("gauge"):
        bits.append("no" + parsed["gauge"].lstrip("#"))
    if parsed.get("section"):
        bits.append(_decimal_section(parsed["section"]))
    for key in ("length_in", "size_in"):
        if parsed.get(key) is not None:
            bits.append(_decimal(parsed[key]))
    return f"{mfr_namespace(manufacturer)}/bom-" + "-".join(bits)


def _decimal_section(section: str) -> str:
    """`.875 X 3` -> `0-875x3`, via exact Fractions so spellings unify."""
    from .bom_parse import _magnitude
    parts = [p for p in re.split(r"[xX]", section) if p.strip()]
    return "x".join(_decimal(_magnitude(p)) for p in parts)


def _unused_spine_check() -> set:
    """Every phrase maps to a key the spine actually declares."""
    return {v for v in BOM_TYPE_SPINE.values() if v not in COMPONENT_TYPE_SPINE}
