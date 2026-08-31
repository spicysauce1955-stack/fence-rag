"""The `PartType` spine: obligation 5 -- "every part type in a snapshot resolves
to a spine type through its parent chain, and extension ids are namespaced
`shared` / `mfr/<manufacturer>` / `<tenant>`" (contract.md §3.1, §2.1).

Like `parameters.py` and `snapshot.py`, this is a projection, not an agent: it
makes no decisions, reads no PDF, and derives nothing that was not already
authored. What it reads is the hand-researched dataset's composition graph --
`data/certainteed-bufftech.json`'s `sub_assemblies[]` -- which `docs/layering.md`
§5 and candidate C3 (`conversation.md` T39, invariant 8/10 in
`knowledge-datamodel.md` §6) settle as authored structure: "this component
belongs to this assembly" is a membership edge, not a value, and carries no
`SourceRef` of its own. `dataset.verify_dataset()` is still called, uncaught,
before any read -- not because membership needs provenance, but because a
silent edit to the file this platform's whole composition graph comes from
must fail the build closed, the same doctrine as `TenantLeak`/`VerificationFailed`.

**Scope, named rather than left implicit.** Three assemblies from one file:
`BT-CHESTERFIELD-CERTAGRAIN` and `BT-CHESTERFIELD-GATE` (the vertical slice
this platform's `ParameterTable`s already cover), plus `BT-POSTRAIL-3RAIL` --
included not because it is Chesterfield, but because it is the one assembly in
this manufacturer file with real, correctly-attributable evidence for
obligation 14 (see `parts.py`'s module docstring for what that evidence is and
is not). Every other assembly, product line and manufacturer is out of scope;
widening it is a future round's work, not a silent side effect of this one.

`dataset.py`'s own docstring already names the sharpest limitation here: "211
of 225 `component_id` values appear nowhere in the corpus." `Part.id` does not
need a `SourceRef` -- identity is authored structure, not a value, per C3 --
but a reader should not mistake a `component_id`-derived id for something a
citation independently confirms; it is a name, not a claim.
"""
from __future__ import annotations

import json
import re

from . import dataset
from .paths import REPO_ROOT

# contract.md §2.1's eleven spine keys, verbatim. `site_material` is reserved --
# Planning's own vocabulary, never emitted by this platform.
SPINE = frozenset({
    "post", "post_cap", "rail", "bar", "infill", "reinforcement", "bracket",
    "fastener", "anchor", "gate_hardware", "site_material",
})

# The vertical slice: two Chesterfield assemblies (matching this platform's
# existing ParameterTable coverage) plus the one assembly with real,
# correctly-attributable obligation-14 evidence. See module docstring.
ASSEMBLY_IDS = ("BT-CHESTERFIELD-CERTAGRAIN", "BT-CHESTERFIELD-GATE",
                "BT-POSTRAIL-3RAIL")
_DATASET_FILE = REPO_ROOT / "data" / "certainteed-bufftech.json"
_MANUFACTURER = "CertainTeed"

# `component_type` (this dataset's own vocabulary) -> where it resolves on the
# spine. Measured against this slice's real data only -- 8 of the 13 distinct
# component_types actually present; `gate_kit` deliberately absent (see
# `build_part_types`). A future slice adds entries here; that is a registry
# addition, not a negotiation (CLAUDE.md: "Registry additions ... are not
# amendments and need no negotiation").
COMPONENT_TYPE_SPINE = {
    "post": ("shared", "post"),
    "rail": ("shared", "rail"),
    "post_cap": ("shared", "post_cap"),
    "picket": ("mfr", "infill"),
    "post_stiffener_aluminum": ("mfr", "reinforcement"),
    "hinge": ("mfr", "gate_hardware"),
    "latch": ("mfr", "gate_hardware"),
    "drop_rod": ("mfr", "gate_hardware"),
}


def mfr_namespace(manufacturer: str) -> str:
    """`\"CertainTeed\"` -> `\"mfr/certainteed\"`. The identical slugify idiom
    `parameters._default_scope` uses for a `fence_model` ref, applied to the
    manufacturer alone."""
    slug = re.sub(r"[^a-z0-9]+", "-", manufacturer.lower()).strip("-")
    return f"mfr/{slug}"


MANUFACTURER_NAMESPACE = mfr_namespace(_MANUFACTURER)


def load_slice_components(path=None) -> list[dict]:
    """The vertical slice's components, flattened and content-sorted.

    Fails closed on a baseline mismatch (`dataset.verify_dataset()`,
    uncaught): a silent edit to the dataset file is exactly what the baseline
    exists to catch, and this is the one reader of the file's composition
    graph as of this round.
    """
    dataset.verify_dataset()
    data = json.loads((path or _DATASET_FILE).read_text())
    out = []
    for line in data.get("product_lines", []):
        for assembly in line.get("assemblies", []):
            if assembly["assembly_id"] not in ASSEMBLY_IDS:
                continue
            for sub in assembly.get("sub_assemblies", []):
                out.append({
                    "assembly_id": assembly["assembly_id"],
                    "component_id": sub["component_id"],
                    "component_type": sub["component_type"],
                    "component_name": sub.get("component_name"),
                })
    out.sort(key=lambda c: (c["assembly_id"], c["component_id"]))
    return out


class PartTypeRegistry:
    """Resolves a `component_type` to a spine-terminating `PartTypeRef`,
    minting an `mfr/` extension row as a byproduct where the spine has no
    matching key. Idempotent: resolving the same `component_type` twice mints
    once."""

    def __init__(self):
        self._extensions: dict[str, dict] = {}   # component_type -> PartType row

    def resolve(self, component_type: str) -> dict | None:
        """`component_type` -> `PartTypeRef` (`{namespace, key}`), or `None`
        if this round has not registered it (a gap, not a guess)."""
        entry = COMPONENT_TYPE_SPINE.get(component_type)
        if entry is None:
            return None
        kind, key = entry
        if kind == "shared":
            return {"namespace": "shared", "key": key}
        if component_type not in self._extensions:
            self._extensions[component_type] = {
                "key": component_type,
                "namespace": MANUFACTURER_NAMESPACE,
                "parent": {"namespace": "shared", "key": key},
                "label_i18n": {"en": component_type.replace("_", " ")},
            }
        return {"namespace": MANUFACTURER_NAMESPACE, "key": component_type}

    def rows(self) -> list[dict]:
        return sorted(self._extensions.values(),
                      key=lambda pt: (pt["namespace"], pt["key"]))


def build_part_types(components: list[dict] | None = None,
                     registry: "PartTypeRegistry | None" = None
                     ) -> tuple[list[dict], list[dict]]:
    """The slice's components -> (`[PartType]` extension rows, `[Gap]`).

    Pass `registry` when a caller (e.g. `snapshot.build_snapshot`) needs the
    SAME registry afterward, to build `Part` rows through the identical
    resolution without walking the components twice.
    """
    from .parameters import _Gaps      # lazy: parameters.py never imports this module

    components = load_slice_components() if components is None else components
    registry = PartTypeRegistry() if registry is None else registry
    gaps = _Gaps()
    for c in components:
        if registry.resolve(c["component_type"]) is None:
            gaps.add(
                kind="unmapped_part_kind",
                subject={"kind": "component", "id": c["component_id"], "tenant": None},
                code="component_type_unmapped",
                params={"component_type": c["component_type"],
                        "component_id": c["component_id"],
                        "assembly_id": c["assembly_id"]},
                would_close=f"decide whether {c['component_type']!r} "
                            f"({c['component_name']}, {c['component_id']}) is one "
                            f"part or several, and which spine key or mfr/ "
                            f"extension it resolves to -- §2.2's mechanical test "
                            f"is the one to apply",
                closes_by="planning")
    return registry.rows(), gaps.list()
