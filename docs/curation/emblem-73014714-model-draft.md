# Emblem 73014714 — first model structure review

Status: **revision 4, private model-backed purchase generation added;
not contract-complete or published**. New mappings have not been
recorded as Developer reviews.

See [model-backed generation](emblem-model-generation.md) for the current
model-to-purchase preview, its clean layout inputs and validation. The component
and geometry findings below remain applicable; generation does not fill those gaps.

[Structured draft](../../workspace/catalog/emblem-73014714-model-draft.json)
contains one incomplete FenceModel and seven Part records. Its private wrapper
keeps confirmed readings, proposed relationships and unresolved contract fields
separate. The snapshot builder does not consume it yet.

## Review this grouping

| Contract location | Proposed contents | Part identity |
|---|---|---|
| `default_spec.frame`: bottom rail | One horizontal rail position | Provisional rail A |
| `default_spec.frame`: top rail | One horizontal rail position | Provisional rail B |
| `default_spec.infill` | Repeating vertical tongue-and-groove board between the rails | Provisional board |
| `post` | Post chosen for its station in the run | Line 73045783 / corner 73045784 / end 73045785 |
| `post.cap` | Contemporary white post top | 73013956 |

The three unnamed kit components have internal IDs, not claimed manufacturer
SKUs. Two rail positions do not prove that the physical rails are interchangeable;
the draft keeps separate provisional identities pending evidence. Board count
is unresolved. Posts belong outside the panel specification because adjacent
panels can share a post. The candidate post selection is review metadata, not
an implemented contract eligibility rule.

Compare with the [exact model's project sheet image](../../workspace/derived/doc-1e71ed3bf8a5/pages/0001.png)
and [original PDF](../../manuals/freedom-outdoor-living/73014714-6x8Emblem-White-ProjectPlanning.pdf).
The post and cap product rows have been read by the assistant; they were not
part of Developer's earlier five-reading confirmation.

## Already confirmed, preserved in the package

- Emblem Privacy Fence Kit — White, manufacturer model **73014714**, nominal **6x8**.
- Actual panel **72 inches high × 94 inches wide**.
- **6-inch tongue-and-groove boards**.
- Top and bottom rail profile **2¼ inches × 7 inches**.

The draft preserves exact millimetre conversions and source lexemes. Revision 3
populates supported Part specifications while retaining dimensional gaps. Only panel width has the saved fact-review
entry from the earlier checkpoint. Conversation confirmation of the other readings
has not been represented as additional ledger reviews.

## What remains unresolved

The [generic privacy guide, page 4](../../workspace/derived/doc-a2462b702402/pages/0004.png)
shows U-channels on the two end boards. Revision 3 establishes a stronger
applicability link through the exact model's retailer-linked manufacturer manual,
described below. The channel dimensions and contract representation remain open.

The draft explicitly lists missing placements, joints, engagement depths,
clearances, board coverage and count, component lengths, post selection rules,
fixings, layout policies and assembly steps. An omitted field means unfinished;
it does not mean zero, no requirement, or a contract-valid default. Panel width
does not establish rail length or post center spacing. The rail profile pair now
has an assistant-authored axis mapping supported by the catalog cutaway; this is
not a new human approval.

Gate hardware and the gate post insert remain outside this basic panel review.

## Revision 2 checks (historical)

Revision 2 adds pinned `source_docs` through the existing `SnapshotBuilder`,
derived `contributing_sources`, and exact source-element anchors for the five
measurements and four post/cap product identities. These are provenance fields
that could already be populated; they should not have remained missing.

Both cited PDFs match their recorded SHA-256 hashes. All 39 citation occurrences
resolve to the correct document versions. Proposed Part links and both
board-to-rail slot links resolve within the draft. Source text matches the stored
elements; post/cap descriptions and model numbers occupy matching source rows.
All five inch-to-millimetre conversions pass exact rational arithmetic checks.
Canonical serialization passes.

**Contract completeness fails: 58 field locations are still absent.** These include
the seven Part specification arrays, model policies, rail placement and joints,
infill geometry, and requirements. This count is a presence check over the
documented shapes; it does not resolve optional-field serialization or establish
validity of fields added later. The draft is not ready for Planning or publication.

Reproduce the scoped audit from the repository root:

```sh
python3 scripts/audit_model_draft.py workspace/catalog/emblem-73014714-model-draft.json --report workspace/reports/emblem-73014714-model-audit.json
```

Expected exit code: **2**, meaning incomplete. Exit 1 indicates draft integrity
errors. See the [machine-readable findings](../../workspace/reports/emblem-73014714-model-audit.json)
for every missing path. This audit is deliberately narrower than a full Planning
validator and does not run fitting, layout or BOM calculations.

The existing `snapshot.verify()` accepted an in-memory snapshot containing this
incomplete model. It also accepted three negative controls: an unknown Part ID,
an unknown frame-slot reference, and a model containing only an ID. Those probe
snapshots were never saved. Passing that validator is therefore insufficient to
claim model correctness. Its production behavior is unchanged by this audit.

Applicable tests passed: 100 snapshot tests, 17 Part tests, 10 dimension tests,
and 9 new scoped-audit tests. The latter verify rejection of broken references,
duplicate slot keys, authored roles, invalid citations, incorrect conversions,
noninteger quantities and false publication claims. They also verify that an
intact incomplete draft is reported as incomplete.

The grouping remains a structural proposal, supported by the project sheet.
The next completion checkpoint is source-backed component specifications and
board/rail connection evidence. Structural approval alone cannot make the missing
geometry or generic-guide applicability valid.

## Revision 3 — specifications and connection evidence

All seven Parts now carry specifications: **23 fields**, with exact source
anchors, original lexemes and contract-v1.3 provenance. `curation_level: 0`
records the new assistant mapping; no human review or policy admission is invented.
The earlier conversation-confirmed readings remain intact as draft evidence.
The hand-authored width fact and its ledger review have been withdrawn; the
draft does not claim an active or replayable source-level review.

| Components | Fields populated | Dimensional interpretation |
|---|---|---|
| Two provisional rail Parts | Width 57.15 mm, height 177.8 mm, White | External profile; neither dimension is channel depth |
| Board | Nominal width 152.4 mm, White | Product size only; effective pitch and physical thickness remain unknown |
| Three post Parts | Width/depth 127 mm, nominal length 2743.2 mm, White | Manufactured post dimensions; not embedment |
| Post cap | Nominal width/depth 127 mm, White | Post-fit size; not actual outer dimensions or cavity clearance |

Spec-key mappings remain part of this private draft, not a claim that the
external consumer already accepts every key. The [catalog page 14 image](../../workspace/derived/doc-d8a7e4aae7db/pages/0014.png)
names the exact SKU and shows the rail profile. It supports the profile-axis
mapping and receiving-channel topology; no dimension was measured from pixels.

The [exact model listing](https://www.lowes.com/pd/freedom-actual-6-ft-x-7-82-ft-ready-to-assemble-emblem-white-vinyl-flat-top-vinyl-fence-panel/50374104)
links a [Freedom installation manual](https://pdf.lowes.com/productdocuments/1c328a11-74cb-411d-b7af-c1b2a3513614/64773145.pdf).
Optional ignored local cache: `workspace/catalog/emblem-linked-installation.pdf`, SHA-256
`20a881589b9f9035b3f6e5bc6c38e80747659cd1c4df0fb0ea3558a058a33a95`.
The URL and hash remain in the draft; the external PDF is not tracked. This is
a different edition from the local PDF, not an identical filing. The earlier
comparison found four assembly statements matching after whitespace normalization: end-channel count,
first/last-board handedness, boards inserted into the bottom rail, and the top
rail guided over the boards. Those comparison results are historical; the audit
rechecks them only when the optional cache is present. Without it, the audit
reports `not_checked_cache_missing`, not a verified match. The external
locator remains private applicability evidence, not an invented canonical SourceRef.

The model now records component supply, an authored tongue-to-groove orientation,
and partial rail `Joint{kind: channel}` objects. The dimensional joint fields
remain explicitly missing. U-channels remain in connection evidence until their
handed end treatment has a complete contract representation; a generic count of
two must not lose which edge each channel covers.

The catalog's wind-installation passage is also retained as conditional evidence.
The ordinary 7-inch-rail insert exception does not prove complete wind-design
applicability. No wind configuration or structural approval was created.

**Current audit after rollback:** zero integrity errors; 118 citation occurrences,
three corpus hashes and all 23 spec fields checked. External applicability is
`not_checked_cache_missing`; the linked PDF was not verified in this run.
Seventeen scoped audit tests pass. The audit still exits **2**: 55 field locations are absent,
including newly inspected nested joint fields. Filling `joint.kind` no longer
hides absent `joint.channel_depth`.

This count is a syntactic diagnostic, not 55 mandatory authoring obligations:
the checker includes mutually exclusive PartRequirement modes. Its report now
states that limitation and the unresolved `length_rule` wire shape. The quantity
rule checkpoint adds three cited authored rules, bringing checked citation
occurrences to 121; it does not complete the contract model.

The executable fitting preflight returns **blocked**, with 15 missing input
locations. It deliberately returns no board count or cut lengths. Overall panel
width is not the clear infill opening, and nominal board width is not verified
effective pitch. The remaining needs are board thickness and stock length,
rail stock length, clear-opening geometry, channel depths and engagements,
and fitting policies. Searching the other indexed documents for Emblem or this
SKU found no further dimensional source.

Completion needs a manufacturer dimensional drawing or recorded measurements
for these quantities. End-to-end fit/BOM verification also requires the separate
Planning consumer; this repository's preflight is not a replacement fitter.
