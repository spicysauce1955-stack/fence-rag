# Source-to-model workflow handoff

## Current workflow entry point

Use [docs/workflows/source-to-contract.md](docs/workflows/source-to-contract.md).
It now requires bounded source coverage before declaring data missing, including
canonical OCR and visual drawing inspection. Empty extracted text is not a
negative finding. Record whether a gap is uninspected, applicability/interpretation
unresolved, conversion/consumer work pending, or not found after inspection.

The later 2022 Emblem drawing discovery below supersedes earlier blanket
missing-dimension conclusions. Publish its supported knowledge in drawing scope
without silently equating it to the exact RTA SKU. Current source-specific
instructions are in [the Emblem workflow](docs/curation/emblem-publication-workflow.md).
Historical checkpoints below retain their original context; do not treat them
as a current exhaustive search result.

## Objective and scope

Formalize a repeatable conversion from source evidence into contract-valid data-model instances through fence-rag’s **Sources → Canonical → Claims → Published** layers. This session developed an Emblem prototype; it did **not** complete that layered conversion. The next session should formalize the workflow before extending the prototype.

Pilot: **Freedom Emblem Privacy White 6×8, exact model 73014714**. Sources include a manufacturer project sheet, installation manual, catalog, and supplementary manufacturer/retailer pages. Target entities include SourceDoc/SourceRef, classified values with Provenance, PartType/Part, FenceModel → PanelSpec → FrameSlot/Member → PartRequirement, Joint, PostSlot, assembly procedures, and explicit Gaps. Supplier packages and their contents additionally support purchase quantities; a packaged product is not interchangeable with a physical component.

The user wants small, jointly understandable steps with visible outcomes, source cross-reference, actual relationship/design validation, and independent logic/adversarial checks. They selected this exact model and named the reviewer **Developer**. That designation is not blanket approval of subsequent values.

## What actually worked, in execution order

1. **Bound product identity.** Select an exact model/color/size and identify applicable documents. Distinguish exact-model statements from family evidence, compatible replacement parts, and successor products.
2. **Inspect source meaning.** Read instructions and figures together, retain raw measurements, and anchor interpretations to canonical SourceRefs and source hashes. Cross-reference conflicting or missing information without silently treating similar products as equivalent.
3. **Author a bounded draft.** Record physical components, assembly relationships, quantities, unknowns, and interpretations. Separate source statements, calculations, authoring conventions, and user confirmations. Preserve the original source-bound draft.
4. **Make a private consumer candidate.** Translate selected draft content into the actual Planning parser’s shapes, retaining transformation evidence separately. This helped expose mismatches but was a diagnostic experiment, not the finished production route.
5. **Exercise real behavior.** Validate against real consumer Parts and run assembly/BOM scenarios beyond a single panel. Synthetic fixtures isolated engine capabilities; actual Emblem checks separately exposed missing inputs.
6. **Audit independently and correct.** Compare sources, contract declarations, entity references, generated quantities, and drawing behavior. Add targeted regression controls for reproduced failures.
7. **Run snapshot preflight and record measured gaps.** Verify the real snapshot envelope, publish actionable exclusion gaps, and state whether a model actually admitted. Append a measured state-and-gaps entry before committing a checkpoint.

**Critical limitation:** steps 3–4 largely used authored JSON and Python transformations outside the durable Claims lifecycle. Source citations in a sidecar are not equivalent to claims admission, review replay, or lossless public provenance. The prototype must not become the reusable workflow unchanged.

## Lessons and corrections

- **Parser acceptance is syntax, not correctness.** The private parser accepted candidates while discarding authorship/citations and supplying defaults. Real semantic checks and explicit provenance-loss reporting exposed this.
- **Do not conflate dimensions.** Nominal 6-inch board width is not installed pitch; outer rail height is not pocket depth; end U-channel depth is not rail-pocket depth. A 3-inch total rail cut allowance does not establish equal 1.5-inch insertion at each post.
- **Structure may be authored; numerical assertions still need provenance.** Counts and placement conventions were explicitly authored in the prototype. They require proper lifecycle integration, not merely a comment saying “cited.”
- **Publication and installation readiness differ.** Our original gate wrongly required universal human review, active-only entities, nonempty Part specs, and successful consumer fitting. The contract permits honestly classified unreviewed knowledge and documented nullable fields. G101 separated readiness diagnostics from structural exclusions. Required nonnullable geometry remains required.
- **Unknown must stay distinguishable from zero, absent fields, and unsupported behavior.** Legal null insertion margins emit gaps; missing required fields refuse. Null margins must not conceal engagement exceeding a known pocket depth.
- **Package quantities and physical quantities differ.** Kit credits should reduce purchases without erasing drawn components. Partial known contents must not masquerade as complete kit inventory.
- **Passing synthetic assemblies proves bounded mechanics only.** It establishes neither exact Emblem dimensions nor compatibility of successor kit documents.
- **Progress reporting needs measured gaps.** Earlier claims overstated readiness and amendment necessity. G101 explicitly corrected those claims rather than preserving a misleading success narrative.

## Validation and adversarial review to preserve

Use distinct review roles: source applicability/interpretation; schema, relationship and provenance closure; physical assembly/BOM logic; adversarial malformed inputs and boundary cases. Assign bounded independent tasks, then reconcile findings against authoritative declarations and reproducible cases—not majority vote or agent confidence.

Useful checks included source-byte hashes, canonical reference resolution, PartType spine closure, literal Part/support-reference graphs, deterministic candidate reproduction, actual consumer validation, and actual snapshot verification. Preserve original inputs and check that diagnostics have not mutated them.

Assembly adversaries covered multi-panel runs, shared posts, corners/disconnected runs, component counts versus package credits, stock adequacy, handed tongue/groove ends, cuts versus drawing extents, and crossing rail bands at shared posts. Refuse unsupported configurations explicitly.

Regressions caught omitted Part.spec becoming [], impossible engagement hidden by null margin, gap deduplication losing a second unknown, and contradictory review records depending on input order. Identical duplicate reviews remain distinct from conflicting records.

Latest recorded evidence: G101 full suite **1,553 tests**, one expected failure; after the final regression, **30 focused tests** passed, independently repeated and also exercised against committed snapshot code. G100 consumer suite: **2,584 tests**, seven warnings. These are historical results, not checks performed for this handoff. Actual Emblem admission remains false.

## Artifact map

- `docs/four-layer-model-design.md`, `docs/layering.md`: architecture and downward-reference rules. `docs/integration/contract.md`, `AMENDING.md`, `knowledge-datamodel.md`, `knowledge-design.md`: boundary authority and model/design declarations; frozen contract wins disagreements.
- `docs/state-and-gaps.md`, especially G98–G101: measured progression and corrections; G101 supersedes overly strict publication claims.
- `workspace/catalog/emblem-73014714-model-draft.json`: original source-bound draft, identities, evidence and unresolved bindings. `emblem-73014714-placement-confirmation.json` beside it: narrow user-confirmed placement interpretation, not manufacturer measurement approval.
- `scripts/prepare_emblem_consumer_model.py` and `workspace/catalog/emblem-73014714-consumer-model.json`: private transformation and generated candidate; not a public adapter.
- `fence_evidence/authored_models.py`, `authored_publication.py`: preflight, readiness diagnostics and snapshot gaps. Publication still has an unconditional unresolved numeric-provenance-mapping guard.
- `scripts/validate_emblem_instances.py`, `scripts/emblem_consumer_adapter.py`: actual-instance audit and bounded consumer diagnostics. Reports: `workspace/reports/emblem-instance-validation.json`, `emblem-authored-build-check.json`, `emblem-73014714-consumer-model-check.json`.
- `workspace/reports/emblem-blocker-progress.md`, `emblem-remaining-inputs.md`, `emblem-cross-source-findings.md`: current blockers, exact source request and prior research; consult before repeating searches.
- `docs/integration/amendments/008-authored-geometry-provenance.md`: pending proposal, **not ratified**. Related synthetic example/report are under `workspace/reports/authored-geometry-provenance-*`.
- `workspace/reports/emblem-consumer-capabilities.patch`, `emblem-consumer-adversarial-review.md`, `emblem-post-receiving-independent-review.md`: bounded consumer implementation and limitations. Checkout `/tmp/fence-planning-bom` may not persist; patch base is recorded in the reports.

## Remaining task and smallest reusable workflow

**Unfinished:** integrate supported values and authored rules with the durable claims/authoring lifecycle; implement a lossless public mapping/adapter; obtain exact-model receiving depths, engagements, fitting evidence and complete package inventory; then validate and publish a meaningful FenceModel. Current `models=[]`. A board Member Joint is also absent; handed profile labels do not supply groove depth. Exact successor/replacement equivalence remains unestablished. No applicable new geometry source was found in the bounded reviews.

**Proposed improvement, not tested end to end:** use one traceable vertical slice: exact product/source scope → canonical evidence → durable classified claims plus authored relationships → published contract object → actual consumer outcome. Require a reviewable artifact and explicit unresolved items at each transition. Finish one slice through all layers before expanding component families. First determine the existing supported claims/import/review path; do not invent another parallel store. Preserve the tested checks above as transition checks.

Numeric provenance is already required; its precise geometry association remains unresolved. Amendment 008 is one proposal, not the only possible solution. Bilateral acceptance has not been recorded. Do not reinterpret “continue” as ratification or user review of unseen values.

Last pushed checkpoint: `1691563`, branch `codex/emblem-model-purchase-preview`. At handoff, concurrent edits in `fence_evidence/snapshot.py` and untracked test logs were deliberately left outside that commit. Preserve and identify their ownership before further edits. This handoff adds no implementation or fresh verification.


## Continuation checkpoint — G104, 2026-09-07

The original workflow limitations above remain historical context. G102–G104
now persist seven exact-model source readings through facts/review replay and
publish four draft Parts; no full model or assembly has admitted. Snapshot
`b5048772101e18513a9cbd2c913978da05046fced986e03c42afddc5c5b19ec7`
is the current verified partial output.

Planning now ingests these exact public Part payloads and opaque versions in its
local checkout. Draft Parts stay inactive; public receipts do not populate the
private generation library. See `workspace/reports/emblem-public-parts-consumer-check.json`
and the cumulative patch/base receipt
`workspace/reports/emblem-consumer-public-receipts-patch.json`. This supersedes
the old report's claim that no public Part ingestion path exists.

Next: disposition the bounded geometry/provenance proposal in
`workspace/reports/emblem-geometry-disposition.md`, then implement the agreed
authoring/consumer path. Amendment 008 is still pending. Exact-model receiving
depths, engagements, installed pitch and fitting evidence are also required;
nominal sizes cannot substitute. All live Emblem readings remain unreviewed.

Combined synthetic assembly checkpoint: 17 new combined cases, 65 related tests
passing. One/two/seven explicitly spaced straight panels exercise board seating,
handed channels, receiving posts and kit credits together. See
`workspace/reports/emblem-assembly-review.md` and
`workspace/reports/emblem-consumer-combined-assembly-patch.json`. Exact-model
geometry remains missing; corner receiving joints remain unsupported.

Source/sequence follow-up: negative profiled overlap now refuses until receiving
geometry exists; private panel AssemblyStep dependencies checked after credits.
2625 consumer tests and39 related evidence tests pass. New cumulative patch/base
receipt: `workspace/reports/emblem-consumer-source-sequence-patch.json`.
Source audit: `workspace/reports/emblem-combined-source-audit.md`; reproducible
canonical check: `python3 scripts/check_emblem_assembly_sources.py`. End-channel
extents and real T&G dimensions remain unknown; panel order is not complete
post installation sequencing. Linked revised manual bytes are absent locally.


G105 supersedes the all-or-nothing completion framing: user explicitly wants
useful partial knowledge now, improved as documents/answers arrive. Default
`advance_emblem.py --apply` succeeds with verified available Parts and creates
a source-backed knowledge answer document. `--objective assembly` separately
requires full model/assembly. See `emblem-workflow-progress-knowledge.md`. Missing
geometry limits calculations, not supported explanations. The revised manual
was recovered and verified in `emblem-recovered-manual-check.json`; earlier
local-absence notes are stale. No external deployment was performed.


Reusable workflow checkpoint — 2026-09-07: general instructions now live in
`docs/workflows/source-to-contract.md`; source-specific recipe metadata lives in
`workspace/catalog/emblem-conversion-batch.json`. The read-only
`scripts/check_conversion_batch.py` reuses the publisher, verifies S/C/K/P joins
for the declared Part slice, and records per-run receipts plus JSONL history.
Final representative run: `workspace/reports/conversion-runs/2e2f343156444c93ac2b0a4e8854bba8.json`.
Four existing Parts passed; four focused tests passed. No subagents, source
ingestion, live review mutation, broad suite or consumer experiments were run
for this checkpoint. Earlier assembly answer prose is explicitly excluded from
the layered acceptance claim. New batch invocation is in the workflow document.


Missed structural drawing recovered — 2026-09-07: the retained NOA22-0217.05
PDFpage7/drawing001sheet4 explicitly names6x8 Emblem (pre-built panel style).
Board0.875x6x61.5in, rail2.25x7x94in and U-channel0.99x1.34x53.875in are
visible. Canonical OCR already existed in ocr_text despite empty text. These
dimensions are no longer "not found"; exact RTA SKU/revision equivalence and
reinforced construction applicability remain unresolved.2024 approval covers
other named models and is not a blanket replacement for the2022 Emblem drawing.

Nine flagged visual readings now persist in facts through
`fence_evidence/emblem_drawing_claims.py`; normal publisher emits3 drawing-scoped
draft Parts, preserving original exact-SKU Parts. New snapshot:
55bc6c769a933079f37e7b5795bd0042ee52a66d5beefe95c9a9d079dcc05bda.
70 focused tests pass. Source coverage/findings:
`workspace/reports/emblem-source-review/findings.md`. Repeat with
`python3 scripts/advance_emblem_drawing.py`, then
`python3 scripts/check_conversion_batch.py workspace/catalog/emblem-drawing-conversion-batch.json`.
No synthetic dimensions, human reviews, or consumer assembly approval were added.
