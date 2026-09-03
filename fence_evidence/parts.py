"""`Part` (obligation 5, and obligation 14): one row per component in the
vertical slice `part_types.py` defines, typed against the spine. Identity and
membership are authored structure, not a value -- C3, `part_types.py`'s
module docstring -- and carry no `SourceRef` of their own.

**Obligation 14** reads *"a part publishes its manufactured `stock_length`
where a document states one."* This platform has such a statement for exactly
two components -- confirmed by direct query against the live store, not
assumed:

  "16 foot lengths"  conditions={"colour": "White"}
  "12 foot rails"    conditions={"colour": "Blend"}

all three under a "Post & Rail with CertaGrain(R) Texture" passage, which
matches `BT-RAIL-PR-3RAIL-WHITE` (1-1/2 x 5-1/2, White) and
`BT-RAIL-PR-3RAIL-COLOR` (2 x 6, Blend/Sierra Blend/etc.) by cross-section --
a real, content-verified correlation. An EARLIER version of this module
attached this same evidence to `BT-RAIL-CHESTERFIELD` instead; that was wrong
(the heading names "Breezewood", a sibling line, and the cross-sections do not
match Chesterfield's undifferentiated rail), caught by adversarial review
before anything shipped, not after. `_stock_length_evidence` re-queries this
live, rather than hardcoding the element ids that carry it today: an extraction
edition can move an element id (CLAUDE.md's own warning on `ref_id`), and a
synthetic or partial store simply does not have this data at all -- it must
produce nothing there, not raise.

**`SpecField.value` is now `Quantity | Token`** (C15, `conversation.md` T42):
`knowledge-datamodel.md` §2.2's old bare `38 | null` shape was a defect in a
document this platform owns and could correct directly -- obligation 4
(BINDING) already forbade a bare `_mm` field, so there was nothing to
ratify. Fixed there; this module publishes the `Quantity` side of the union.

**G63, found computing it.** `parameters.quantity()`/`_unit_of()` cannot be
reused unchanged here: they read `unit_normalized` first, and for
`stock_length_in` facts specifically that column does NOT mean "the unit the
source stated" -- it means "the unit `value_normalized` is expressed in",
which this fact type's extractor (`facts.stock_lengths`) always sets to
`"in"`, regardless of whether the source actually stated feet. `[measured]`:
33 of 62 `stock_length_in` facts are stated in feet (`'`, `foot`, `’`) and
every one still carries `unit_normalized: "in"`. Blindly reusing `quantity()`
here would have silently published "16 foot lengths" as 406400 milli-mm (16
INCHES) instead of the correct 4876800 (16 FEET) -- twelve times too small,
with a confident-looking `SourceRef` attached, the exact "letter satisfied,
intent missed" shape as the `domain_basis` bug and the Chesterfield
misattribution above. `unit_original` is not subject to this: verified
correct for all 62 rows across every group (`in.`, `'`, `foot`, `’`, `"`).
`_stock_length_quantity` reads it, never `unit_normalized`. See
`state-and-gaps.md` G63 for the corpus-wide count; this module does not fix
the extractor, only routes around it for the two values in this slice.
"""
from __future__ import annotations

import json
import sqlite3

from .canonical import canonical_bytes
from .parameters import (MILLI_PER_UNIT, _UNIT_ALIASES, _Gaps, _default_source_ref,
                         _magnitude, _round_half_up)

# The exact 3 documents (2 distinct content hashes -- doc-700e6e22c440 and
# doc-6431d597a32d share sha256) that state a stock length for either rail in
# this slice. No family-manifest file exists for this manufacturer today, so
# this is a named, explicit list rather than a derived one -- see module
# docstring for how it was found.
_STOCK_LENGTH_DOCUMENT_IDS = ("doc-24d0ddcfce69", "doc-6431d597a32d",
                              "doc-700e6e22c440")
# `conditions.colour` -> which component the evidence is about (cross-section
# match, confirmed against data/certainteed-bufftech.json).
_COMPONENT_OF_COLOUR = {"White": "BT-RAIL-PR-3RAIL-WHITE",
                        "Blend": "BT-RAIL-PR-3RAIL-COLOR"}


def _part_id(component_id: str, namespace: str) -> str:
    return f"{namespace}/{component_id.lower()}"


def _stock_length_quantity(value_original: str, unit_original: str | None) -> dict | None:
    """A `Quantity` from a `stock_length_in` fact's own text and
    `unit_original` -- never `unit_normalized`. See module docstring, G63."""
    unit = _UNIT_ALIASES.get((unit_original or "").strip().lower())
    magnitude = _magnitude(value_original)
    if unit is None or magnitude is None:
        return None
    return {"amount_milli": _round_half_up(magnitude * MILLI_PER_UNIT[unit]),
            "unit": "mm", "value_raw": [value_original.strip()]}


def _stock_length_evidence(conn: sqlite3.Connection | None) -> dict:
    """`component_id -> {"value_original", "unit_original", "doc_type",
    "version_status", "review_status", "element_ids": [str, ...]}`, queried
    fresh against `conn`. `None` (a store with none of this data -- a
    synthetic test fixture, a partial ingestion) returns `{}`, not an error:
    the absence of this evidence is not this module's concern to flag."""
    if conn is None:
        return {}
    placeholders = ",".join("?" * len(_STOCK_LENGTH_DOCUMENT_IDS))
    rows = conn.execute(f"""
        SELECT f.element_id, f.conditions, f.value_original, f.unit_original,
               f.review_status, d.doc_type, d.version_status
          FROM facts f JOIN documents d ON d.document_id = f.document_id
         WHERE f.fact_type = 'stock_length_in' AND f.condition_basis = 'stated'
           AND f.document_id IN ({placeholders})
         ORDER BY f.fact_id
    """, _STOCK_LENGTH_DOCUMENT_IDS).fetchall()
    out: dict[str, dict] = {}
    for r in rows:
        colour = json.loads(r["conditions"] or "{}").get("colour")
        component_id = _COMPONENT_OF_COLOUR.get(colour)
        if component_id is None:
            continue
        entry = out.setdefault(component_id, {
            "value_original": r["value_original"], "unit_original": r["unit_original"],
            "review_status": r["review_status"], "doc_type": r["doc_type"],
            "version_status": r["version_status"], "element_ids": []})
        if r["element_id"] not in entry["element_ids"]:
            entry["element_ids"].append(r["element_id"])
    return out


def build_parts(components: list[dict], registry, *, source_ref=None,
                conn: sqlite3.Connection | None = None) -> tuple[list[dict], list[dict]]:
    """`(components, registry)` -> `([Part], [Gap])`.

    `registry` is a `part_types.PartTypeRegistry` already walked by
    `part_types.build_part_types` over the SAME `components` list -- reused,
    not rebuilt, so a component this platform already gapped as unmapped is
    skipped here rather than gapped twice.
    """
    from .parameters import CURATION_LEVEL, _source_class     # lazy: no cycle, matches parameters.py's own discipline

    mint = source_ref or _default_source_ref(conn)
    gaps = _Gaps()
    parts_by_id: dict[str, dict] = {}
    by_component_id = {c["component_id"]: c for c in components}

    for c in components:
        ref = registry.resolve(c["component_type"])
        if ref is None:
            continue        # already gapped as unmapped_part_kind by build_part_types
        part_id = _part_id(c["component_id"], ref["namespace"])
        parts_by_id[c["component_id"]] = {
            "id": part_id,
            "version": 1,
            "status": "active",
            "type": ref,
            "name_i18n": {"en": c["component_name"] or c["component_id"]},
            "spec": [],
            "authorship": "third_party_authored",
            "cites": [],
            "contributing_sources": [],
        }

    for component_id, evidence in sorted(_stock_length_evidence(conn).items()):
        part = parts_by_id.get(component_id)
        if part is None:
            continue        # out of this build's slice, or unmapped
        value = _stock_length_quantity(evidence["value_original"],
                                       evidence["unit_original"])
        # Two of this evidence's three documents share one sha256 (byte-
        # identical filings), so two different element ids can mint the
        # IDENTICAL ref -- ref_id() is a pure function of (sha256, page_no,
        # bbox), not of the element id. Dedup by the minted ref itself, the
        # same canonical_bytes idiom parameters._merge() uses for the same
        # reason, or the citation list carries a literal duplicate entry.
        minted = [mint(eid) for eid in sorted(evidence["element_ids"])]
        cites = sorted({canonical_bytes(c): c for c in minted}.values(),
                       key=canonical_bytes)
        if value is None:
            gaps.add(
                kind="unquantified",
                subject={"kind": "component", "id": component_id, "tenant": None},
                code="stock_length_not_a_quantity",
                params={"component_id": component_id,
                        "value_raw": evidence["value_original"]},
                cites=cites,
                would_close=f"{evidence['value_original']!r} is stated for "
                            f"{component_id} but carries no parseable "
                            f"magnitude or convertible unit; a person should "
                            f"read the source and record the number with its "
                            f"unit",
                closes_by="knowledge")
            continue
        part["spec"].append({
            "key": "nominal_length_mm",
            "agree": "==",
            "value": value,
            "provenance": {
                "cites": cites,
                "source_class": _source_class(evidence["doc_type"]),
                "curation_level": CURATION_LEVEL.get(evidence["review_status"], 0),
                "version_status": evidence["version_status"] or "unknown",
            },
        })
        part["cites"] = cites
        part["contributing_sources"] = sorted({c["belongs_to"] for c in cites})

    parts = sorted(parts_by_id.values(), key=lambda p: p["id"])
    return parts, gaps.list()
