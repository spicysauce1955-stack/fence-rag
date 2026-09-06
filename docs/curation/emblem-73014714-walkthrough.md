# Emblem 73014714 walkthrough

## Selected case

Freedom Outdoor Living Emblem 6x8 White privacy fence kit, model 73014714.
Work through one source and one reviewable outcome at a time, together with
the user, toward a source-backed published result.

## Source check — 2026-09-06

Source: `manuals/freedom-outdoor-living/73014714-6x8Emblem-White-ProjectPlanning.pdf`,
page 1. Document ID: `doc-1e71ed3bf8a5`.
SHA-256: `e90a649e0b96895fbc80d438132d5738f10d9b14b1669eb776a61436758f3a23`.
Image: `workspace/derived/doc-1e71ed3bf8a5/pages/0001.png`.

The user was shown the source image and the following five entries, then
confirmed: "great, this is correct". Reviewer identity is the user in this
conversation; no personal name was supplied.

| Field | Confirmed reading |
|---|---|
| Product | Emblem Privacy Fence Kit — White |
| Model | 73014714 |
| Actual panel size | 72 inches high x 94 inches wide |
| Boards | 6-inch tongue-and-groove |
| Top and bottom rails | 2 1/4 inches x 7 inches |

Keep the nominal product label `6x8` separate from actual panel dimensions.
The source row includes `(F)` after the product name; its meaning was not reviewed.
The board entry does not establish thickness, length, or count. The rail
entry does not establish rail length. No installation procedure, post spacing,
or structural applicability was reviewed in this check.

## Persistence check

A read-only query of the local `facts` table on 2026-09-06 found four facts
for this document: three 108-inch post stock lengths and one 106-inch gate
post insert stock length. None represents the five entries reviewed above.
Those four facts were not reviewed by this confirmation and remain unchanged.

This file preserves the conversation review; it is not a fact-review ledger
entry and does not make these values available in a published snapshot.

Next outcome: trace the five confirmed entries through the existing data and
publishing paths, and identify the smallest change needed to persist and expose
them with their product scope and source citation intact.

## Width trace — 2026-09-06

The next agreed checkpoint is actual panel width: 94 inches = 2387.6 mm
(`amount_milli: 2387600` when represented as a millimetre Quantity).

Inspection found:

- `data/freedom-outdoor-living.json` describes the Emblem family under
  `freedom-emblem-privacy-panel`, with multiple heights and colors. It is not
  a dedicated record for model 73014714.
- That assembly has `width_on_center_in: 99`. This is a different measurement
  from actual panel width; the user's review of 94 inches does not validate,
  replace, or contradict the center-spacing claim by itself.
- `part_types.load_slice_components()` selects three CertainTeed assemblies
  only; Emblem is outside that published slice.
- `parts.build_parts()` emits component Parts and stock-length specs. It
  does not publish a complete panel model or panel-width claim.
- `snapshot.py` emits `models: []`; there is no FenceModel builder wired in.

The width has therefore not been persisted as a reviewed structured claim or
published. Choosing its representation must account for the exact product
variant and the distinction between a panel assembly and its component Parts.
Adding a width to an arbitrary rail Part or replacing center spacing would
misrepresent the source.

## Width experiment withdrawn — 2026-09-06

The user confirmed the displayed source readings and supplied reviewer name
**Developer**. The width reading remains `94in. W` (94 inches), converted exactly
to 2387.6 mm. Product identity and dimension-cell anchors are preserved in
`workspace/catalog/emblem-73014714-reviewed-width.json`; despite its historical
filename, it is now explicitly a **draft source reading**, not a reviewed fact
export or an import payload.

The earlier experiment manually created fact 22751 and review 78fe49766acc86a1.
Standard ledger replay cannot recreate that hand-authored fact. With user
authorization, both records were removed from the local store and the review
was removed from the tracked ledger. Conversation confirmation is retained;
there is no active or replayed Developer review for this width. The private
reading carries no extraction or review status.

The dedicated `dimensions.py` publisher and its tests were removed, and snapshot
integration and registry documentation restored to the preceding revision.
The former snapshot
`27cb8b01fb9b23a5908d72030c7233d76906fa5be3139c258193944dd0615389`
was withdrawn using the repository's `snapshot_store.tombstone` API. That ID
resolves to an excision reason, never an altered payload or a missing file.
`workspace/reports/emblem-73014714-snapshot-check.json` records withdrawal;
`workspace/reports/emblem-73014714-width-rollback.json` records current checks.
No live `actual_panel_width_mm` publication is retained.

The source corpus, extracted source text and private model/purchase drafts are
preserved. Future publication requires reproducible supported authoring and
review, not restoration of a hand-authored database ID.

## Direction after project-level review — 2026-09-06

The user clarified that the deliverable is the contract's data models, not a
sequence of isolated parameters. The withdrawn width experiment exercised a
local source/review/publication path but did not establish reproducible authoring
or implement an Emblem FenceModel.

See [project-contract-alignment-review.md](../project-contract-alignment-review.md)
for measured coverage, validation gaps and implementation mismatches. Preserve
Developer's five conversation-confirmed readings as draft evidence. Next, prepare
one contract-shaped Emblem model package for review, starting with identity,
parts and the PanelSpec structure, with unknowns explicitly identified. Do not
expand the special-case dimension publisher one field at a time.

## First model structure draft — 2026-09-06

Prepared [the model structure review](emblem-73014714-model-draft.md) and
`workspace/catalog/emblem-73014714-model-draft.json`: one incomplete FenceModel,
seven Part fragments, confirmed readings, conditional source applicability,
and explicit unresolved contract fields. Structure is proposed and awaits
Developer review. The draft is not wired into snapshots or claimed publishable.
Verified source hashes, citation ownership, internal references and JSON read-back.

## Executable model audit — 2026-09-06

At the user's request, checked the actual draft with repository code and negative
controls. The existing snapshot validator accepts incomplete models and broken
model links; it cannot establish this object's correctness. Added a scoped audit
script and nine tests, then populated derivable source documents, roll-ups and
exact evidence anchors in draft revision 2. Its integrity checks pass, but the
contract-field presence audit exits 2 with 58 missing field locations. All 136
applicable tests pass. See the model structure review for commands and limitations.
The contract object remains incomplete; no model snapshot was published.

## Component and connection checkpoint — 2026-09-06

Revision 3 populates 23 source-backed specification fields across all seven Parts.
The exact SKU retailer page links a revised manufacturer installation manual;
four relevant assembly statements match the local edition. The draft now carries
those connection anchors, component supply, board edge orientation and partial
rail channel joints. The new mappings remain assistant-curated, not new Developer
reviews. Catalog evidence preserves conditional wind requirements separately.

The expanded audit passes integrity, specification conversions and source checks,
with 14 focused tests passing. It still reports incomplete contract geometry and
a blocked fitting preflight; no board counts or cut lengths are fabricated.
See the model review's revision 3 section for sources, missing inputs and results.

## Purchase objective selected — 2026-09-06

The user selected A: complete panel-kit purchasing rather than individual
component fabrication. Prepared [a three-panel straight-run example](emblem-73014714-purchase-example.md):
3 kits, 2 end posts, 2 line posts, 4 caps. Unique-station counts and source
references check out. This is an authored example, not a measured site or a
Planning run. Whole-panel kit coverage cannot be represented merely by changing
the infill supply flag; consumer matching and kit-credit support remain to verify.

## Single-panel acceptance and independent assembly review — 2026-09-06

After clarifying the distinction between supplier catalog items and internal kit
components, the user accepted one kit, two end posts and two caps, and requested
independent agent assembly reviews. Two agents checked the count and full-privacy
instruction branch. Corrected the active example from three panels to one,
retaining the three-panel artifact separately. Added two handed kit-contained
U-channels, explicit unquantified installation materials, and the constraint to
engage the second post before fixing it in concrete. These are private inventory
and walkthrough records; the corresponding contract graph is still incomplete.
Nine new purchasing/sequence tests and 14 model-audit tests pass. Supplier pack
quantities, installation material quantities, wind applicability and consumer kit
coverage remain unresolved. Full findings are in the purchase-count checkpoint.

## Complex layout review — 2026-09-06

At the user's request, added a [seven-panel example](emblem-73014714-complex-example.md):
a five-panel L and a separate two-panel straight run. Independent review confirms
7 kits, 4 end posts, 4 line posts, 1 corner post and 9 caps. Expanded the checker
from one straight path to declared orthogonal open runs, with angle-based post
checks and a bay/station-specific assembly trace. Nineteen tests pass; the accepted
single-panel case remains valid. Physical corner clearance, installation-material
quantities and consumer kit coverage are still unverified.

## Model-backed generation — 2026-09-06

Implemented [private model-backed purchase previews](emblem-model-generation.md).
Two clean layouts contain only bay/model references and schematic coordinates;
the generator derives post roles and reads kit/post/cap identities from draft
revision 4. Both generated lists match the independently checked examples.
New tests demonstrate that model changes alter output and unsupported semantics
fail rather than silently disappearing. Forty focused purchase tests pass.
The consumer repository location has been requested: this closes the hardcoded
example-output gap, but not the contract Product/kit integration gap. No snapshot
publication is claimed.
