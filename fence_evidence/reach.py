"""What a published snapshot is scoped TO, and whether anyone can resolve it.

This module answers one question that neither system was asking: **the things
we publish carry our identifiers — can anything outside this repository turn one
of them into something it recognises?**

Today the answer is no, for every one of them, and it was no for weeks without
either side noticing. `conversation.md` T51 §2 measured it from the consumer
end: a published `ParameterTable` is scoped `{kind: "fence_model", id:
"mfr/certainteed-columbia-imperial-chesterfield"}`, the consumer's evaluator
matches a scope by plain equality against its own `FenceModel` id (`M-SLAT`,
`M-LEGACY`, `M-VINYL`), and across **6,563 stored generation runs an `mfr/*` id
appears at no path under `.graph` or `.strategy`**. Not one published table has
ever governed anything.

The rounding defect in T50 §3 survived in published data precisely because of
that: nothing exercised the path end to end, so nothing complained.

**Why this is a report and not a `Gap`.** A `Gap` is a hole in the KNOWLEDGE,
and §1.2.1's eight kinds are BINDING and closed — `unmodellable_entity`,
`uncovered_condition`, `unsatisfiable_requirement`, `unquantified`,
`missing_value`, `unmapped_part_kind`, `disputed`, `illegible_source`. None of
them means *"this is published to an identity no consumer can resolve"*, and
inventing one would be an amendment rather than a registry addition. The
knowledge here is not missing; its **reachability** is, and that is ours to
measure and say out loud rather than to publish as a hole in the corpus.

**What this module can and cannot know.** It reads what we publish, so it can
count identities exactly. It cannot know what a consumer is able to bind — that
is the consumer's declaration to make, and `AMENDING.md` §2's existing shape for
this is *"Condition dimensions … Planning declares what it can bind."* So
`DECLARED_ASSOCIATIONS` is a map this side fills in only once the other side has
said what resolves, and it is empty because nobody has said.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .snapshot_store import SNAPSHOT_DIR

# Every identity family any stored snapshot publishes into, as measured.
#
# This is a PIN, not a policy: a new family is not a defect, but publishing one
# without noticing is. `tests/test_scope_reach.py` fails when a snapshot carries
# a family that is not here, which is exactly what did not happen when
# `mfr/weatherables` arrived with 18 Parts in one session (`conversation.md`
# T53 §4) and neither system said a word.
KNOWN_IDENTITIES = (
    "mfr/barrette-outdoor-living-inc-simtek-molded-stone-look-fence-family",
    "mfr/barrette-outdoor-living-inc-vinyl-privacy-semi-privacy-fence-family-"
    "certainteed-era-model-names",
    "mfr/certainteed",
    "mfr/certainteed-columbia-imperial-chesterfield",
    "mfr/certainteed-columbia-imperial-chesterfield-breezewood-brookline",
    "mfr/certainteed-columbia-imperial-chesterfield-chesterfield-w-lattice-"
    "breezewood-brookline",
    "mfr/certainteed-general-bufftech-fence-installation-posts-rails-racking-"
    "stepping",
    "mfr/certainteed-simtek-molded-composite-not-extruded-pvc",
    "mfr/freedom-outdoor-living",
    "mfr/weatherables",
    "shared",
)

# Our identity -> what a consumer binds instead. EMPTY, and that is the finding.
#
# It stays empty until the consumer says what it can resolve. We must not guess
# the right-hand side: asserting `mfr/certainteed-columbia-imperial-chesterfield`
# IS `M-VINYL` would be inventing a product identity, which is the same class of
# error as attributing a manufacturer's datum -- caught and reversed once already
# before it shipped (see docs/state-and-gaps.md G62).
DECLARED_ASSOCIATIONS: dict[str, str] = {}


@dataclass(frozen=True)
class ScopeSurface:
    """The identity families a snapshot publishes into, and how much rides on them."""

    identities: tuple[str, ...]
    objects: int
    by_identity: dict[str, int]


def _part_family(identifier: str) -> str:
    """The identity a consumer would have to resolve, for a `Part.id`.

    A `Part.id` names a SKU inside a family (`mfr/weatherables/augusta-8x6-rail`),
    so its last segment comes off: the thing needing resolution is
    `mfr/weatherables`, once, not each of eighteen rails and pickets.

    A `ParameterTable.scope.id` gets no such treatment and is used whole --
    `mfr/certainteed-columbia-imperial-chesterfield` already IS the family, and
    trimming its last segment would leave the bare `mfr`, collapsing seven
    distinct products into one and reporting a single problem where there are
    seven.
    """
    return identifier.rsplit("/", 1)[0] if "/" in identifier else identifier


def scope_surface(snapshot: dict) -> ScopeSurface:
    """Count the identity families in one published snapshot document."""
    counts: dict[str, int] = {}
    objects = 0

    def record(family: str) -> None:
        nonlocal objects
        counts[family] = counts.get(family, 0) + 1
        objects += 1

    for table in snapshot.get("parameters") or ():
        scope_id = ((table.get("scope") or {}).get("id")) or ""
        if scope_id:
            record(scope_id)
    for part in snapshot.get("parts") or ():
        part_id = part.get("id") or ""
        if part_id:
            record(_part_family(part_id))
    return ScopeSurface(identities=tuple(sorted(counts)), objects=objects,
                        by_identity=counts)


def unresolvable(surface: ScopeSurface,
                 associations: dict[str, str] | None = None) -> tuple[str, ...]:
    """Which published identities nothing outside this repository can resolve."""
    declared = DECLARED_ASSOCIATIONS if associations is None else associations
    return tuple(i for i in surface.identities if i not in declared)


def reachability_report(root: Path | None = None) -> dict:
    """Every stored snapshot's scope surface, and how much of it reaches nobody.

    The number to read is `unreachable_objects`: published Parts and
    ParameterTables whose identity no consumer has declared it can bind.

    A snapshot publishing no scoped object is excluded rather than counted as
    clean. Zero objects checked is not zero objects stranded -- the same
    vacuous-green shape `cli refs --verify` refuses (G39), and reporting an
    empty snapshot as reaching everything is how this defect stayed quiet.
    """
    directory = SNAPSHOT_DIR if root is None else root
    snapshots: list[dict] = []
    families: dict[str, int] = {}
    for path in sorted(directory.glob("*.json")):
        try:
            document = json.loads(path.read_text())
        except (OSError, ValueError):
            # A snapshot we cannot read is not a snapshot we can clear. It is
            # skipped from the count rather than treated as reaching nobody,
            # because inventing either answer from unreadable bytes is worse
            # than the silence this module exists to end.
            continue
        surface = scope_surface(document)
        if not surface.identities:
            continue
        stranded = unresolvable(surface)
        snapshots.append({
            "snapshot_id": path.stem,
            "objects": surface.objects,
            "identities": list(surface.identities),
            "unresolvable": list(stranded),
            "unreachable_objects": sum(surface.by_identity[i] for i in stranded),
        })
        for identity, count in surface.by_identity.items():
            families[identity] = max(families.get(identity, 0), count)
    # NOT "latest". Snapshots are named by content hash, so sorting their
    # filenames orders them arbitrarily -- an earlier draft called the last
    # element `latest` and it named a cut from four sessions ago. Recency is
    # not recoverable from the store (mtime does not survive a fresh clone),
    # so the report names the snapshot with the MOST stranded objects, which
    # is both deterministic and the one worth looking at.
    worst = max(snapshots, key=lambda s: (s["unreachable_objects"],
                                          s["snapshot_id"])) if snapshots else None
    return {
        "snapshots_with_scoped_objects": len(snapshots),
        "identity_families": len(families),
        "declared_associations": len(DECLARED_ASSOCIATIONS),
        "unknown_identities": sorted(f for f in families
                                     if f not in KNOWN_IDENTITIES),
        "worst": worst,
        "per_snapshot": snapshots,
    }
