# Project alignment with the contract — 2026-09-06

**Historical audit:** the counts and probes below describe the original width
experiment. Its hand-authored fact and ledger review were subsequently removed
with user authorization; the narrow publisher was withdrawn and the linked
snapshot now resolves to an explicit tombstone. The source reading and user
confirmation remain private draft evidence, not an active reviewed fact.
Current rollback checks are in
[`emblem-73014714-width-rollback.json`](../workspace/reports/emblem-73014714-width-rollback.json).

## Finding

The intended deliverable is a set of source-backed **contract model instances**:
Parts, FenceModels and their PanelSpecs, procedures, warnings, parameter tables,
and explicit gaps. A snapshot is the immutable delivery package for those
instances. Producing an individually cited value is a useful infrastructure
check, but does not establish that a fence model can be authored or consumed.

The repository has a substantial evidence system and a partial publishing
system. The principal missing path is **authored product/assembly definitions
joined to source-backed claims, then validated and projected into the contract
types**. More human reviews alone cannot fill that implementation gap.

The preceding Emblem width work followed an existing parameter-table convention,
but introduced another special-purpose publisher without delivering an Emblem
FenceModel. Treat it as a withdrawn local publishing experiment and preserved
draft evidence, not as completion of the product-model objective. Do not repeat that
pattern with a separate publisher for every subsequent dimension.

## Scope and evidence

Reviewed the contract and domain-model definitions, integration and curation
designs, current status/build notes, the source-to-store and review workflows,
the publishing modules, snapshot storage/verification, CLI and HTTP routing,
the dataset shape, and relevant tests. Inventoried all Python modules in
`fence_evidence/`, their public entry points, and the live SQLite schema.

Measurements and controlled probes are recorded in
[`project-contract-alignment.json`](../workspace/reports/project-contract-alignment.json).
This is a system-level implementation review, not a line-by-line correctness
certification of every module or a visual re-review of all 2,147 source pages.
The separate Planning repository was not inspected. References to its intended
behavior come from the local integration contract and design correspondence.

## What the snapshot is

Contract §1.2 defines one object containing the published model instances.
`canonical.py` serializes it deterministically; `snapshot.py` constructs and
checks it; `snapshot_store.py` stores it by content hash. Planning is intended
to fetch and pin that object before a run, so the same project and knowledge
produce the same result without live retrieval during generation.

The file linked after the Emblem experiment was a **1,708-byte report excerpt**,
not the snapshot itself. The actual snapshot is **510,839 bytes**:

[`27cb8b01…15389.json`](../workspace/snapshots/27cb8b01fb9b23a5908d72030c7233d76906fa5be3139c258193944dd0615389.json).

Its product coverage is nevertheless thin:

| Member | Actual contents | Implementation state |
|---|---:|---|
| `source_docs` | 85 | Metadata for sources registered by published citations; not the full 144-document corpus. |
| `warnings` | 287 | Built, largely source/document-oriented. |
| `gaps` | 404 | Built; captures multiple kinds of missing or unusable evidence. |
| `part_types` | 5 | Manufacturer extensions for the existing CertainTeed slice. |
| `parts` | 11 | Existing CertainTeed component identities; only **2 spec fields total**. |
| `parameters` | 10 | Nine existing structural tables plus the Emblem actual-width experiment. |
| `models` | 0 | Literally emitted as `[]`; no FenceModel builder. |
| `procedures` | 0 | Builder exists, but all 71 current candidates are unreviewed; additional correctness issues below. |
| `combinations` | 0 | Deliberately deferred: contract obligation 17 and datamodel §3.9 say not to prioritize before consumer support. |
| `rules` | 0 | Shape unresolved; already recorded as candidate C16. Do not confuse Rule with PanelSpec's FixingRule. |

An empty member is permitted as an honest partial delivery. It is not evidence
that the corresponding model-generation capability is implemented.

## The path through the system

| Stage | Code/data | What it does |
|---|---|---|
| Source distribution | `fetch`, `distribution`, `publish`, manifests | Retrieves/verifies source bytes; `publish.py` publishes corpus objects, not product models. |
| Extraction and canonical evidence | `extract`, `layout`, `tables`, `hocr`, `quality`, `ingest`, `store` | Preserves documents, extraction editions, pages, text, geometry, tables, assets and issues. |
| Source lookup | `refs`, `crops`, `cropcache`, `sourcerefs`, `assets` | Resolves citations and renders the reviewed evidence. |
| Candidate claims and reviews | `facts`, `table_review`, `promote_tables`, `steps`, `reviews` | Extracts values/readings/step candidates and records human decisions. |
| Discovery and measurements | `retrieval`, `versions`, `relations`, `evaluate`, `audit`, `reports`, `worklist` | Search and diagnostic surfaces; not the deterministic source of a planning run. |
| Authored domain structure | Legacy `data/*.json`; narrow `part_types.load_slice_components()` | Some composition data exists, but no general authoring/publishing path for the contract's assembly graph. |
| Published definitions | `parts`, `parameters`, `procedures`, experimental `dimensions` | Separate limited projections; no model/rule/combination producer. |
| Delivery | `snapshot`, `canonical`, `snapshot_store`, CLI | Builds and stores local immutable packages. HTTP resolution endpoints are absent. |

`fence_evidence/model.py` is the **extraction intermediate representation**
(`Word`, `Element`, `Page`, etc.), not the contract's FenceModel implementation.
`schema/bom-schema.json` describes the older research dataset, not a complete
validator for the integration snapshot.

## Required domain structure that is missing

Datamodel §§3.1–3.6 describe connected definitions:

* `PartType` classifies a `Part`; `Part.spec` supplies sourced properties.
* `FenceModel` contains height support, option axes, a default `PanelSpec`,
  variants, post requirements, layout contributions and assembly steps.
* `PanelSpec` holds frame slots, infill members/patterns and fixing rules.
* `PartRequirement` connects those positions to component definitions.
* `Joint` describes reception/engagement/clearance, where supported.
* `PostSlot` belongs outside the panel because a post can be shared by bays.
* `ContainedSlot` represents inserts and other contained components.
* Steps refer to these structural positions; dependency edges must be sourced.
* Warnings, parameters and gaps attach to the appropriate definitions.

No current producer assembles this graph into `models[]`. The SQLite store
has no authored FenceModel/PanelSpec storage; that alone is not a defect (files
could serve this purpose), but no equivalent file-based producer exists either.
The legacy family dataset is not already this graph: it mixes several product
variants and has component lists without the required slot/joint/requirement
relationships. Its values also cannot be treated as automatically reviewed.

The contract's invariant is **structure is authored, not extracted**. We can
draft structure with source assistance and have it reviewed; OCR and regex
extraction alone will not produce a valid PanelSpec. A large new claims-schema
migration is not a prerequisite to authoring one real model.

## Concrete alignment issues

### 1. Verification is substantially narrower than model conformance

In memory, replacing each of `models`, `parameters`, `rules`, or `combinations`
with `[{"id": "incomplete-object"}]` still passes `snapshot.verify()`.
No invalid snapshot was stored. The test demonstrates missing shape validation,
not that the existing parameter builder's own collision checks are absent.

The gate checks source closure, floats, warnings/gaps, selected Part fields,
and selected Procedure fields. It does not establish that a FenceModel has a
PanelSpec, that members reference real frame slots or Parts, or that member
placement and dependencies satisfy the contract. The 1,364-test passing run
therefore proves existing tested behavior, not complete contract coverage.

### 2. Parameters name models that the snapshot does not define

All ten parameter tables name `fence_model` scopes with no corresponding model
in `models[]`. `parameters._default_scope()` explicitly uses manufacturer and
family metadata to mint these references before entities exist. The Emblem
publisher follows that precedent with a more precise model-number binding.

Source-document closure does not imply product-reference closure. A parameter
with a valid citation can still lack the assembly definition or consumer
binding needed to use it. Emblem's explicit missing-model gap makes this
absence visible; it does not close it.

### 3. Procedure prerequisites contradict contract obligation 11

`procedures.build_procedures()` synthesizes an `after` edge to each preceding
published step. Its comment equates source order with a stated dependency.
Contract §3.1.11 explicitly distinguishes those and requires empty dependencies
when the page only lists steps in order.

Reproduced with the existing in-memory two-bullet fixture: reviewing the bullets
creates an `after` edge without any review of a dependency. The existing test
`test_steps_keep_source_order_and_requires_follows_it` endorses this mismatch.
The review schema has no field for the required typed dependency edges.

The same builder always sets `Procedure.scope` to null because a model does
not exist. The contract defines null as **owned by no product**, not **product
unknown/unimplemented**. Cape Cod-specific instructions must not become
product-independent merely because their FenceModel has not been authored.

### 4. Regime is currently a label without content separation

Two in-memory builds with `us_astm` and `cn_gb` produce identical Parts,
parameters, models, procedures, warnings and source-doc contents. The regime
coordinate changes, but the structural tables are not selected by regime.
This does not implement the intended US/China separation in contract §1.2.

### 5. Delivery APIs are partial

The contract names Resolution, Discovery and Authoring surfaces. `api.dispatch`
currently routes table reviews and source-ref lookup/batching. An authenticated
`GET /snapshots/{stored_hash}` returns 404 in the current HTTP dispatcher.
Snapshot storage and fetching exist as Python/CLI functions, so local artifacts
work; a complete resolution service is not established by that fact.

### 6. Emblem's withdrawn width path was a special case

The former `dimensions.py` bound one PDF hash, one product identity and one field.
The manually authored fact had an export and standard review-ledger entry, but
no automatic fresh-store importer. No Planning binding was implemented or tested.
The publisher, parameter registry additions, fact and review have now been
removed with user authorization. Adding similar modules for other dimensions
would increase code without creating the reusable model-authoring path.

The conversation-confirmed values survive as private draft readings, with no
active review claim. The experiment snapshot was withdrawn through the existing
tombstone API; its ID retains an explicit excision reason, not a changed payload.

### 7. Historical status prose obscures current work

The README/snapshot module introduction still describe the earliest small
snapshot. The build plan contains superseded counts and claims that Procedure
is unbuilt; the later G81 entry says the procedure pipeline is complete despite
the dependency/scope issues above. Some documents describe features implemented
in Planning, not in this repository. Read implementation evidence and the
contract together; do not take every "built" label as end-to-end readiness.

Not every empty member is an implementation oversight: combinations are
explicitly deferred, Rule is unresolved (C16), and model-specific shape
questions C7/C9/C10 must be checked against the chosen source before inventing
a workaround. These do not justify indefinitely postponing a model whose
supported structure can already be authored.

## Correct next unit of work

**One reviewable Emblem 73014714 model package**, with explicit completeness
status, is the next deliverable. Its structure should follow the contract
before more individual values are published:

1. Author an exact product identity/variant mapping and a contract-field map.
   Keep the 94-inch actual panel width, nominal 6x8 label and any post-center
   spacing as distinct facts; the last is not established by this review.
2. Draft the component definitions and the FenceModel/PanelSpec graph from the
   source set: rails, infill, post/cap requirements and applicable connections.
   Record source-backed, unreviewed and missing fields separately in the draft.
   Do not write null/zero into required contract fields merely to serialize it.
3. Review the graph and groups of sourced values with Developer. Confirm the
   installation guide's applicability before transferring its instructions.
4. Implement one data-driven authoring-to-publication path, preserving the
   existing fact/review evidence and stable product identities.
5. Validate real relationships and quantities against the contract, then
   publish the resulting connected model package. Unsupported required fields
   keep a draft unpublishable or generate the contract's explicit gaps; they
   do not become invented defaults.
6. Exercise the consumer loader/selection when its repository is available.
   Report separately whether the package is valid, selectable, and sufficient
   for one representative planning case.

The acceptance question is: **Does the snapshot contain a usable definition of
this product, with its connected parts, assembly structure and visible gaps?**
The next checkpoint is not another isolated number in `parameters[]`.
