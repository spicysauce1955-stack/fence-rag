Reusable execution instructions: [source-to-contract workflow](../workflows/source-to-contract.md).
This document retains Emblem-specific details and historical checkpoints.

# Emblem publication and assembly workflow

Target: useful knowledge for Freedom Emblem Privacy White 6×8, exact model
**73014714**, plus separately scoped supporting drawings. Partial knowledge
publication is the first milestone. Complete model mapping, physical assembly,
component cuts/counts and supplier purchasing have separate acceptance checks.

## Current source coverage and two conversion slices

- **Exact-SKU project sheet:** seven persisted readings produce four draft Parts.
- **2022 structural drawing:** PDF page 7 / drawing 001 sheet 4 explicitly names
  6×8 Emblem, pre-built panel style. Nine flagged scan readings produce three
  separate drawing-scoped Parts. They include board length/thickness, rail
  length and end-channel dimensions; exact RTA component equivalence is not
  asserted.

[Coverage inventory](../../workspace/reports/emblem-source-review/coverage.json)
and [findings](../../workspace/reports/emblem-source-review/findings.md) record
what was inspected, how, and what it answered. Earlier blanket statements that
these dimensions were not found are superseded for the drawing's scope.
The 2024 approval names other models; it must not automatically replace the
2022 Emblem drawing merely because their identifiers or filing names resemble
one another. Canonical `ocr_text` must be checked when `text` is empty.

The sell sheet and transition/cutdown guides also support scoped answers. Those
research findings are distinct from the two slices actually persisted and
published. Use the general workflow's gap states to distinguish uninspected
sources, unresolved applicability/datums, conversion work, consumer work and
information not found after inspection.

```bash
python3 scripts/advance_emblem_drawing.py
python3 scripts/check_conversion_batch.py workspace/catalog/emblem-drawing-conversion-batch.json --round 1
```

The importer preserves original OCR evidence and records AI visual readings as
flagged, not human reviewed. New quantities use `drawing_*` fields and scoped
Part identities; they never silently become installed pitch or exact-SKU cuts.

## Implemented source-to-Part path

`fence_evidence/emblem_claims.py` is a bounded extraction recipe over retained
canonical elements, pinned to the project-sheet SHA and exact source text.
It imports seven readings into the existing `facts` table. The four-layer
design's unified `claims` table remains proposed; no parallel store was added.

The readings cover board nominal width, panel colour, rail width and height,
cap nominal width and depth, and cap colour. The two cap axes have independent
fact identities and can be corrected independently. Original text survives in
`value_original`; publication reads `effective_fact_value`, including any
correction. Re-import preserves existing reviews and refuses conflicting or
ambiguous original readings. It creates no human review.

Import obtains its write lock before checking existing readings and preserves
caller transactions with a savepoint. Publication checks each review projection
against the latest-arriving ledger record and its current source reference; a
forged annotation or moved evidence region refuses. Inch conversion uses exact
rational arithmetic, including unusually long decimal corrections.

`parts.build_parts` projects these persisted readings into four exact Parts:
the board, rail A, rail B, and cap 73013956. Each SpecField carries the source
classification, curation level, version status and canonical references,
including exact-model applicability anchors. Parts remain draft. The rail
identities remain provisional: positions do not establish separate supplier
SKUs or interchangeability. Existing family Parts keep their separate IDs.

Each exact Part now has a `sha256:` version derived from all its public content
except the version itself. A correction or changed classification produces a
different version; replay of identical content preserves it. Archived snapshots
with the earlier numeric version 1 remain unchanged. These hashes identify
content, not chronology. Planning's public Part receipt now preserves these string identities. Private
generation revisions remain integers; public-to-generation mapping is separate.

The rail dimensions remain exact at 57150 and 177800 milli-mm. Board nominal
width does not become installed pitch. Cap nominal dimensions do not become
mating clearance. No post geometry or kit inventory is inferred.

The normal snapshot builder includes these Parts. Geometry on FenceModel
owners still has no implemented lossless public provenance mapping; Amendment
008 is pending and this path neither applies nor ratifies it.

## Reproduction

From the repository root:

```bash
# Check on an in-memory copy; write reports only.
python3 scripts/advance_emblem.py

# Import persisted readings and store a verified local snapshot.
python3 scripts/advance_emblem.py --apply

# Full suite, including replay, source integrity and exact Part projection.
python3 tests/run_tests.py
```

The default knowledge objective exits **0** when a verified nonempty exact Part
slice is available. `--objective assembly` exits **2** until the complete model
and assembly are validated. Neither outcome substitutes for the other. The report records the snapshot identity, source hashes, current
facts, Parts, field-level exclusions and missing geometry. The command never
sends data to an external service.

Human review uses the existing `cli fact-review` path. Its evidence-bound
decisions are exported and replayed by `cli review --export/--import`.
Synthetic correction/rejection tests exercise that replay without placing any
test review in the live ledger. A corrected value with unsupported units,
lost precision or changed white-model identity refuses publication pending
explicit re-authoring.

Fact-review export preserves arrival order within each evidence anchor, including
backdated and tied timestamps. Import refuses conflicting or incomplete history
that could make an older decision win. Previously exported ledgers that already
lost arrival order cannot recover it without another authoritative record.

## Remaining transitions

1. Bring supported authored assembly relationships and numeric rules through
   a durable authoring path with value-level classifications. The private
   candidate's sidecars remain diagnostic inputs, not the published mapping.
2. Resolve the public geometry/provenance association and implement the
   supported consumer mapping. Any boundary change follows the existing
   amendment procedure; no inferred ratification.
3. Obtain exact-model rail pockets, board groove depth, board engagements,
   post receiving geometry, installed pitch and applicable fitting allowances.
   Distinguish missing measurements from legally nullable margins.
4. Validate single-panel and multi-panel assemblies: shared posts, rail-end
   clearance, handed board ends, cuts/drawing extents and physical component
   quantities. Keep unsupported arrangements as explicit refusals.
5. Admit the complete model into a verified snapshot and demonstrate the
   assembly from its public representation. Then add supplier package contents
   and stock evidence for purchasing.

Current generated checklist: `workspace/reports/emblem-workflow-progress.md`.
Fresh consumer diagnostic: `workspace/reports/emblem-workflow-consumer-check.json`.
The source-bound draft and placement confirmation remain unchanged.


## Public consumer receipt checkpoint

Planning's private checkout now reads the actual four published draft Parts
without rewriting their opaque version identities. Full Part payloads survive
the round trip, including original provenance, and remain inactive. Its public
receipt path is separate from private integer generation revisions. SourceDoc
receipts retain typed fields and citation hash joins; unknown document extension
metadata is not an archival guarantee.

Reproduce with Planning's environment:

```bash
/tmp/fence-planning-bom/.venv/bin/python scripts/validate_emblem_public_parts.py --consumer-root /tmp/fence-planning-bom
python3 scripts/geometry_provenance_proposal.py
```

`workspace/reports/emblem-public-parts-consumer-check.json` records the bounded
ingestion result and consumer source hashes. The separate
`workspace/reports/emblem-geometry-disposition.md` packet makes a subset of the
proposed numeric association rules executable for review. It is not an approved
boundary, a full geometry validator, or manufacturer evidence.


## Answer useful questions before geometry is complete

The default `advance_emblem.py` objective is now `knowledge`. Its generated
`emblem-workflow-progress-knowledge.json` and `.md` provide current published
Part specifications, original provenance, separately labeled source-checked
assembly readings, task-specific limitations and follow-up questions. These are
local answer documents alongside the existing contract-valid snapshot, not an
additional executable model format or a deployed endpoint.

Answers follow the current review projection: a withheld Part supplies no
default claims, and corrections retain exact milli-unit precision. Missing fit
inputs restrict cut/count calculations, not explanations of available sources.
Ask the relevant follow-up when the user's task needs it rather than forcing
every user through a complete geometry checklist. Full geometry and purchasing
work remains available through the explicit assembly objective.
