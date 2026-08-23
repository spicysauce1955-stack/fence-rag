# 5 — Acceptance criteria

Every criterion is measured by `cli curate audit --slice bufftech`, which writes
`workspace/reports/curation-readiness.md`. Nothing here is judged by inspection.
A criterion with no deterministic checker is not a criterion.

Four groups: **preservation** (the phase did no harm), **curation** (the layer
was built correctly), **floor** (it actually produced something), **readiness**
(the slice is good enough to unfreeze the projection). All four must pass before
requirement 9's gate opens.

**Why there is a floor group.** Without it the entire set is passable by doing
nothing: read no tables, declare all 670 cells `unreadable_scan` gaps, mark all
1,293 claims `blocked`, and every "100% of *accepted* claims…" and "0
disagreements" criterion is vacuously true on an empty set. A gap has to cost
something, or gapping everything is the dominant strategy. Group F is what it
costs.

---

## Group P — Preservation (the immutable layer stayed immutable)

| # | Criterion | Measure | Target |
|---|---|---|---|
| P1 | Corpus files unmodified | SHA-256 of every file in `workspace/catalog/corpus-manifest.jsonl` | 144/144 identical |
| P1b | `data/` unmodified | SHA-256 of every file under `data/**` vs `workspace/catalog/data-digests.json`, written at C0 | all identical |
| P2 | Canonical tables unmodified | row count + ordered-row hash of all eleven canonical tables, before and after a full run | identical |
| P3 | `facts` unmodified | row count + ordered-row hash | identical, 1,988 rows |
| P4 | Projection not regenerated | `retrieval_units` and `retrieval_fts` row counts, and `retrieval_units.built_at` | unchanged, 10,886 |
| P5 | Write guard enforced | attempted write to each canonical table name and to `facts`, through the authorizer | every attempt rejected |
| P6 | Extraction code untouched | git diff over `extract.py`, `layout.py`, `hocr.py`, `tables.py`, `quality.py`, `ingest.py`, `manifest.py` | empty |
| P7 | Existing tests still pass | `python3 tests/run_tests.py` | 101/101, plus the new curation tests |

P1 is scoped to the manifest's 144 rows because the manifest covers only
`manuals/` and `china/`; `data/` — including the authority-20
`certainteed-bufftech-structural.json` that R9 turns on — has no recorded
baseline hash today, which is why P1b and its C0 deliverable exist.

P1–P4 are the technical statement of *"the current implementation is now the
immutable extraction and preservation layer"*. If any fails, nothing else here
matters.

---

## Group C — Curation correctness

### C-A Dossiers and page maps

| # | Criterion | Target |
|---|---|---|
| C-A1 | Dossier per slice document | 19/19, `UNIQUE(version_id)` |
| C-A2 | Page map per slice page | 522/522, each ≥1 content class |
| C-A3 | Revision status is quoted from a body | 100% of dossiers with `revision_status ≠ unknown` carry an `element_id` **and** a `revision_quote` that is a verbatim substring of that element's `text`/`ocr_text` |
| C-A4 | The quote is not the filename | 0 dossiers whose `revision_quote` is a substring of the source filename or of `documents.title` |
| C-A4b | The approvals are actually decided | all 5 NOA dossiers carry `revision_status ≠ unknown` — "all unknown" passes C-A3 vacuously while leaving CAP-8 unserved |
| C-A5 | Duplicate groups resolve | each of the 3 byte-identical groups has exactly 1 `canonical_for_duplicate_group=1` |
| C-A5b | Duplicate ≠ lineage | 0 pairs of documents with different `sha256` sharing a `duplicate_group_id` (prohibition 5) |
| C-A6 | The 24-0117.05 divergence is recorded | the dossier set records all 4 `manufacturer` values and all 4 `doc_type` values for one identical SHA-256 |
| C-A7 | Disagreement with the stored status is typed | `disagrees_with_stored = (revision_status ≠ map(stored_version_status))` holds for 19/19; ≥1 dossier has it set (23-0314.05) |
| C-A8 | Flag dispositions are typed and complete | all 7 known false-positive `table_not_reconstructed` pages appear in `workspace/catalog/table-flag-fixture.jsonl` with a `flag_disposition`; the 2 index sheets are `false_positive_index_sheet` and remain in C5 scope with `has_reviewable_table=1` |
| C-A9 | Authority assigned | 19/19 dossiers carry an `authority_level` from `cur_vocab` and a non-empty `authority_basis` |
| C-A10 | The slice spans what it claims | the 19 dossiers cover `install_manual`, `gate_manual`, `catalog`, `approval` and `warranty`, and ≥2 supersession generations (requirement 7). `spec_sheet` and `drawing_set` are not represented in this slice and are registered as `out_of_scope` gaps rather than left implied |
| C-A11 | Page maps are not guesses | a blind-labelled 40-page sample agrees with `cur_page_maps` on the primary content class at ≥0.90, with a confusion table in the report |
| C-A12 | Backfill completed (gate C4b) | 0 of the 5 approval dossiers have a NULL `effective_claim_id` or `expires_claim_id`; 0 page maps are entity-empty on a page whose dossier names a product line |

### C-B Entities

| # | Criterion | Target |
|---|---|---|
| C-B1 | Manufacturer resolution | every Tier-A document → exactly 1 manufacturer entity |
| C-B2 | Style resolution | each of the five styles resolves from every spelling in `workspace/catalog/spelling-fixture.jsonl` — a frozen, hashed, blind-labelled set of observed spellings with their `element_id`s. Recall is measured against the fixture, and the fixture's own coverage is reported as a caveat, because "every spelling that occurs" is the task, not a checkable set |
| C-B3 | Alias evidence | 100% of `accepted` aliases cite an `element_id`; 0 `curator_label` aliases are `accepted` |
| C-B4 | Succession sourced | every `brand_succeeds` edge cites an element in a document body |
| C-B5 | No entity self-accepted | 100% of `accepted` entities have a review row |

### C-C Claim migration (requirement 4)

| # | Criterion | Target |
|---|---|---|
| C-C1 | All slice facts migrated | 1,293/1,293 candidate claims (1,041 `regex-v1`, 252 table-read) |
| C-C2 | **Nothing inherits trust** | 0 migrated claims `accepted` at migration time |
| C-C3 | Prior "verified" statuses confer nothing | the 252 `cross_family_verified` slice facts migrate as `candidate`; `table_review.PROMOTABLE` no longer contains `cross_family_verified` |
| C-C4 | Empty conditions stay empty | facts with `conditions='{}'` produce 0 condition rows; 0 backfilled or inherited conditions |
| C-C5 | Subject binding honest | every migrated claim starts `unbound` — including the 60 style-rooted heading paths, which are the only bindable-looking ones; no claim becomes `bound` without a review row |
| C-C6 | Quotes are quotes | 100% of `element_quote` evidence: `exact_quote` is a verbatim substring of the cited element's `text`/`ocr_text` or the cited `table_cells.text`, **at the cited `version_id`**. Equality with the claim's own `value_raw_lexeme` does not count — the same code writes both |
| C-C7 | Tier B does not double-count | 100% of claims from the five Tier-B *duplicate* documents carry `duplicate_of_claim_id`; 0 Tier-B claims are `accepted` independently. The Tier-B warranty is not a duplicate and is exempt |
| C-C8 | No float canonical values | 0 REAL columns hold a canonical measurement; `value_decimal` and `confidence_value` are fixed-scale TEXT; `value_milli` is the only sortable numeric copy |
| C-C9 | Lineage survives re-extraction | `cli facts --extract` runs to completion with the curation tables present (no FK onto `facts.fact_id`), and every `source_fact_key` still resolves |

### C-D Conditions, authority, validity, confidence (requirement 5)

| # | Criterion | Target |
|---|---|---|
| C-D1 | Structural claims are conditional | 100% of `accepted` claims in `footing`, `spacing`, `wind_condition` carry conditions on `fence_height`, `exposure_category`, `hvhz_applicability` **and `post_size`** — the same four C5 requires, named once here and referenced from there |
| C-D2 | Unknown is explicit and blocking | 0 `accepted` mandatory-class claims with any `operator='unknown'` condition; the trigger refuses it |
| C-D3 | Authority present | 100% of claims carry an `authority_level` resolving in `cur_vocab` |
| C-D4 | Validity present or gapped | 100% of approval-sourced claims carry `valid_from`/`valid_until`, or `validity_basis='none'` **and** a `cur_knowledge_gaps` row with `scope_kind='claim'` and `scope_ref=claim_id` — checked by join, not by prose |
| C-D5 | Confidence has a basis | 100% of claims carry a `confidence_basis` from `cur_vocab` |
| C-D6 | Confidence never promotes | 0 claims reached `accepted` without a review row |

### C-E Review workflow (requirement 6)

| # | Criterion | Target |
|---|---|---|
| C-E1 | Mandatory classes gated — claims | 0 `accepted` claims in the eight mandatory classes lack a `reviewer_kind='human'` accept row |
| C-E1b | Mandatory classes gated — relations | 0 `accepted` `cur_entity_relations` rows with `review_class='compatibility'` lack a human accept row |
| C-E2 | The gate cannot be unwound | four tests: accept-on-insert refused; accept-on-update refused; `UPDATE … SET review_mandatory` cannot slip past; deleting or downgrading the human review an accepted claim rests on is refused |
| C-E3 | OCR risk auto-classified | 100% of claims whose evidence element has `ocr_confidence < 80`, or whose page has `ocr_mean_confidence < 80`, or whose page carries `table_not_reconstructed`/`mojibake_text_layer`, carry `low_confidence_ocr` or a higher-priority mandatory class. Expected slice volume: 476 rows |
| C-E4 | Evidence was rendered | 0 accept rows with an empty `evidence_seen`; every hash in it matches a `crop_sha256` on that claim's evidence **and** the file on disk; every accept row carries a `session_token` the queue issued. Reported explicitly as *attestation that the tool rendered the crop*, not proof a person looked |
| C-E5 | Rejections retained | 100% of `rejected` and `superseded` claims still queryable with their evidence |
| C-E6 | Sampling is bounded, not nominal | non-mandatory claims grouped by `attribute` where `review_mandatory=0` (155 slice tuples); per group, sample size such that the upper 95% bound on that group's error rate is ≤ 0.10, with the bound reported per group |
| C-E7 | Propagated decisions name their source | 100% of claims whose status came from `cur_review_propagation` name the review row, and the inheriting claim's value and conditions are byte-identical to the reviewed one |

### C-F Evidence integrity (requirement 10)

| # | Criterion | Target |
|---|---|---|
| C-F1 | **Full provenance chain** | 100% of claims resolve to document → version SHA-256 → page → *(element + bbox, or `cell_bbox_px`)* → crop, **with the `element_quote` / `visual_reading` split reported**. `derived` claims are excluded and are separately required never to be `accepted` |
| C-F2 | Crops exist | 100% of `crop_path` files on disk for `element_quote` and `visual_reading` evidence |
| C-F3 | Crops hash | 100% of `crop_sha256` match the file |
| C-F4 | Bboxes are inside their page | 0 `bbox` exceeding page `width`/`height`; 0 `cell_bbox_px` outside its crop |
| C-F5 | Crops are deterministic | regenerating every crop reproduces an identical **decoded pixel buffer**, within a fixed `cur_runs.tool_fingerprint`; byte identity is asserted only against the same poppler version |
| C-F6 | Table cells cite their labels | 100% of `visual_reading` evidence carries `row_label`, `col_label`, `grid_id` and `reader` |
| C-F7 | No Pillow dependency | crop generation succeeds on a checkout with `workspace/pylibs/` absent |
| C-F8 | Grid structure preserved | every cell claim references a `cur_table_readings` row; every condition derived from a bracket references the `cur_table_annotations` row it came from (prohibition 4) |

### C-G Bundle (requirement 8)

| # | Criterion | Target |
|---|---|---|
| C-G1 | Bundle builds and validates | schema-valid, hash recorded |
| C-G2 | Accepted only | 100% of claim members are `accepted`, enforced by trigger |
| C-G3 | All ten sections present | supported_claims, source_documents, components, configurations, installation_steps, **tables**, drawings, conflicts, knowledge_gaps, not_covered |
| C-G4 | Gaps non-empty | ≥1 gap — an empty list on this corpus means the detector is broken |
| C-G5 | Conflicts non-empty | ≥1 group — the five-generation chain guarantees it |
| C-G6 | Conflicts unresolved by default | 0 groups resolved without a review row |
| C-G7 | Bundle is regenerable | rebuilding produces identical output modulo `generated_at`; `export_sha256` is computed over the export with `generated_at` excluded |

---

## Group F — Floor (the phase produced something)

These are absolute counts. They cannot be satisfied by an empty set, and they
are what makes every "100% of accepted claims" criterion above mean anything.

| # | Criterion | Measure | Target |
|---|---|---|---|
| F1 | Structural claims exist | accepted claims with a full four-dimension condition tuple, sourced from the 8 `wind_exposure_footing` crops (132 distinct cells) | ≥ N, where **N is fixed and published by Gate C0.5** as a stated fraction of the digit-bearing values in the frozen ground truth for those crops, before C5 runs, and is not revised afterwards |
| F2 | Coverage is not shrunk | cells attempted / cells in the frozen ground truth for those 8 crops | reported, with the abstention rate |
| F3 | All eight grids are read | `cur_table_readings` rows with `table_kind='wind_exposure_footing'` and `status='reviewed'` (a defined `grid_status` value), covering all 132 distinct cells | 8/8 grids, 132/132 cells dispositioned — not "at least one Table 1", which is satisfiable by reading the one grid whose values are already published in three places |
| F4 | Bindings exist | claims with `subject_binding='bound'` and `subject_entity_id` naming a `product_style` | ≥ 1 per style that the corpus documents |
| F5 | A procedure exists | `cur_procedures` with ≥1 reviewed, contiguous step sequence | ≥ 1 |
| F6 | Gaps are specific, not blanket | share of `cur_knowledge_gaps` whose `scope_kind` is `page` or `table` rather than `capability` | reported; a slice where every gap is capability-wide has not been curated |

---

## Group R — Data readiness (requirement 9's gate)

Groups P, C and F must already pass.

| # | Criterion | Measure | Target |
|---|---|---|---|
| R1 | **No silent errors** | accepted `visual_reading` values that disagree with the frozen ground truth **and were not abstained on**, over the full ground-truth denominator for the 8 grids (132 cells) | **0** |
| R2 | Agreement with prior readings | accepted values vs `workspace/catalog/ground-truth-round-1.jsonl` (SHA-256 recorded), reported as **coverage, recall, precision and abstention together**, split by crops with 1 reader (32) and >1 reader (7) | ≥ the target set at C0.5 |
| R2b | Correctness is the human's number | inter-rater disagreement between the human reviewer and the agent consensus, per grid | reported as a first-class number |
| R3 | CAP-6 answerable | *"footing depth for Chesterfield, 6 ft, Exposure C, HVHZ"* returns one winning claim (`cur_conflicts.winning_claim_id` where a group exists) with a complete condition tuple and a rendering crop, superseded members addressable but not returned — or a knowledge gap with a reason | pass, against a fixture in `eval/curation-questions.json` |
| R4 | CAP-7 answerable | each of the 5 NOAs has a reviewed scope claim naming its models and a reviewed date pair | 5/5 |
| R5 | CAP-8 answerable | *"which approval is in force"* returns one document, one date pair, one citation; the other 3 filings resolve as duplicates | pass, against a fixture in `eval/curation-questions.json` |
| R6 | CAP-1 answerable | *"who sells Chesterfield today"* resolves through the succession edges with evidence | pass, against a fixture in `eval/curation-questions.json` |
| R7 | CAP-5 answerable | ≥1 complete post-and-panel procedure, contiguous ordinals, every warning attached, every figure crop resolving | pass, against a fixture in `eval/curation-questions.json` |
| R8 | CAP-9 answerable | every accepted claim renders its crop | 100% |
| R9 | **G16 regression, inverted** | for the three in-slice errors — the HVHZ bracket on the Exposure-B rows, the PE licence state, the hat-insert dimensions — the bundle contains an **accepted claim on the same attribute/subject/condition signature whose value matches the source page**, each with its crop | 3/3 |
| R10 | Capability partition | for each of CAP-1..CAP-9, the bundle contains either ≥1 accepted claim satisfying that capability's fixture predicate **or** ≥1 gap with `capability='CAP-n'` | 9/9, no capability silently absent |
| R11 | Review is finished, not abandoned | 0 claims in `in_review`; every *reviewed* claim is `accepted`, `rejected`, `needs_source`, `blocked` or `superseded`; unreviewed claims remain `candidate` and their count is reported per class | pass |
| R12 | Idempotency | a second full run with unchanged inputs and `config_hash` produces rows identical on every column except `started_at`, `finished_at`, `created_at`, `reviewed_at`, `resolved_at`, `generated_at` — the explicit list, as `tests/test_idempotency.py` already does for the projection | pass |

**R1 is a hard zero, and it is about wrong values, not missing ones.** The G16
failure was a confidently wrong number, and
`docs/experiment-noa-table-reading.md` already makes silent-error rate the
deciding criterion. One accepted value that contradicts what a reader
transcribed from the page image, without having abstained, fails readiness
outright regardless of every other number.

**R2 measures reproducibility, not correctness, and says so.** Both the C5
readers and the frozen ground truth are blind agent readings from the same model
family; the round-1 report warns that *"correlated failure is possible"*. R2 is
therefore agreement-with-prior-readings. R2b — the human reviewer against the
agent consensus — is the correctness measure, and it is reported alongside,
never instead.

**R9 is inverted from its first draft.** As originally written it passed by
doing nothing: the four G16 errors are absent from the bundle by construction,
since `data/structural/*.json` is never a claim source on its own. Requiring the
bundle to contain the *correct* claim, accepted, with its crop, is a test the
phase can fail. The fourth error (NOA 22-0616.10, SimTek) is a Tier-C document
and moves to slice 2's criteria rather than being scored here.

---

## What passing does and does not authorise

**Passing authorises** regenerating the retrieval projection with curated claims
as an additional unit type, for this slice only; and beginning slice 2.

**Passing does not authorise** corpus-wide curation without a second review of
what slice 1 cost and what it found; dense retrieval, reranking, serving, or
answer generation, all of which remain paused; or treating any `accepted` claim
as verified without its conditions — the bundle carries conditions on every
claim precisely so a downstream consumer cannot drop them.

---

## Reporting rule

`workspace/reports/curation-readiness.md` reports **every** criterion with its
measured value, including the ones that pass, and states the verdict per group.
Partial reporting is how A4's no-answer precision looked acceptable at 0.667 on
a three-question negative set before an 18-question set measured it at 0.333.
Metrics that can be gamed by omission are reported together or not at all —
which is why R2 reports coverage, recall, precision and abstention as one row,
and why Group F exists at all.
