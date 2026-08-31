"""`Part` (obligation 5, and the identity half of obligation 14): one row per
component in the vertical slice `part_types.py` defines, typed against the
spine, cited to nothing of its own (C3: identity and membership are authored
structure, not a value -- see `part_types.py`'s module docstring).

**What this round does NOT publish, and why.** Obligation 14 reads *"a part
publishes its manufactured `stock_length` where a document states one."* This
platform has such a statement for exactly two components -- confirmed by
direct query against the live store, not assumed:

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

Getting the DATA right was not enough to publish it. `SpecField`'s wire shape
is not settled where it would need to be: `knowledge-datamodel.md` §2.2 (Tier
2 -- negotiation notes, not `contract.md`'s frozen stable core) sketches
`value: 38 | null` with a SIBLING `unit` field -- a bare, already-collapsed
number -- while obligation 4 (BINDING, §1.1) requires every dimension crossing
the boundary to be a full `Quantity` (`amount_milli`, `unit`, `value_raw` --
the verbatim source lexeme alongside). Those two are not the same shape, and
`SpecField` appears nowhere in `contract.md`'s own type list -- grepped, not
assumed. Deciding between them here would be inventing BINDING-adjacent
contract text unilaterally, which is exactly what `CANDIDATES.md`/`AMENDING.md`
exist to prevent. So: `Part.spec` publishes `[]` for every component this
round, and the two rows above are gaps instead, each citing its own evidence
-- a work item a curator or Planning can act on, not a value asserted under
an undefined shape.
"""
from __future__ import annotations

import json
import sqlite3

from .parameters import _Gaps, _default_source_ref

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


def _stock_length_evidence(conn: sqlite3.Connection | None) -> dict:
    """`component_id -> {"value_raw": str, "element_ids": [str, ...]}`, queried
    fresh against `conn`. `None` (a store with none of this data -- a
    synthetic test fixture, a partial ingestion) returns `{}`, not an error:
    the absence of this evidence is not this module's concern to flag."""
    if conn is None:
        return {}
    placeholders = ",".join("?" * len(_STOCK_LENGTH_DOCUMENT_IDS))
    rows = conn.execute(f"""
        SELECT element_id, conditions, value_original
          FROM facts
         WHERE fact_type = 'stock_length_in' AND condition_basis = 'stated'
           AND document_id IN ({placeholders})
         ORDER BY fact_id
    """, _STOCK_LENGTH_DOCUMENT_IDS).fetchall()
    out: dict[str, dict] = {}
    for r in rows:
        colour = json.loads(r["conditions"] or "{}").get("colour")
        component_id = _COMPONENT_OF_COLOUR.get(colour)
        if component_id is None:
            continue
        entry = out.setdefault(component_id,
                               {"value_raw": r["value_original"], "element_ids": []})
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
    mint = source_ref or _default_source_ref(conn)
    gaps = _Gaps()
    parts = []
    by_component_id = {c["component_id"]: c for c in components}

    for c in components:
        ref = registry.resolve(c["component_type"])
        if ref is None:
            continue        # already gapped as unmapped_part_kind by build_part_types
        parts.append({
            "id": _part_id(c["component_id"], ref["namespace"]),
            "version": 1,
            "status": "active",
            "type": ref,
            "name_i18n": {"en": c["component_name"] or c["component_id"]},
            "spec": [],
            "authorship": "third_party_authored",
            "cites": [],
            "contributing_sources": [],
        })

    for component_id, evidence in sorted(_stock_length_evidence(conn).items()):
        if component_id not in by_component_id:
            continue        # out of this build's slice
        cites = [mint(eid) for eid in sorted(evidence["element_ids"])]
        lexeme = evidence["value_raw"]
        gaps.add(
            kind="unmodellable_entity",
            subject={"kind": "component", "id": component_id, "tenant": None},
            code="specfield_wire_shape_unresolved",
            params={"component_id": component_id, "value_raw": lexeme,
                    "candidate_shapes": ["knowledge-datamodel.md §2.2: bare "
                                         "number + sibling unit",
                                         "obligation 4: full Quantity"]},
            cites=cites,
            would_close=f"{lexeme!r} is stated for {component_id} across "
                        f"{len(cites)} source(s) and is held back only because "
                        f"SpecField's wire shape is unresolved between "
                        f"knowledge-datamodel.md §2.2 and obligation 4 -- settle "
                        f"which shape SpecField.value takes, and this platform "
                        f"publishes it the same day",
            closes_by="planning")

    parts.sort(key=lambda p: p["id"])
    return parts, gaps.list()
