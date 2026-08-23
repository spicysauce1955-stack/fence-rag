# 4 — Curation and review plan

Eleven stages: C0 through C8, with a cheap feasibility probe at C0.5 and a
backfill at C4b. Each ends at a gate; a failed gate stops the stage that follows
it rather than being noted and passed. No stage touches the corpus, the
canonical tables, `facts`, or the retrieval projection.

**Two numbers set the shape of this plan.**

The slice's 1,293 facts — 1,041 `regex-v1` rows and 252 from the unreviewed
table-reading pass — collapse to **359 distinct `(document, attribute, value,
conditions)` tuples**, 257 of them in Tier A. Its 922 table-read candidate rows
collapse to **670 distinct cells across 39 distinct page crops**. Review is
scoped to distinct tuples and cells, not to raw rows; the duplication is real
information (a value repeated on eight pages is evidence of emphasis, and all
eight evidence rows are kept) but it is not eight decisions.
`cur_review_propagation` carries one decision to every claim sharing its
`tuple_signature`, so a per-tuple workload still yields a per-claim status.

And of those, **773 of 1,293 rows / 204 of 359 tuples fall into a mandatory
review class before a single table cell is read** — 476 rows from
`low_confidence_ocr` alone, because 113 of the slice's 522 pages have OCR mean
confidence below 80 or carry a `table_not_reconstructed`/`mojibake_text_layer`
issue. The sampling relief in the queue rules therefore applies to at most 155
tuples, not to the bulk of the work.

| Review class | Slice rows | Slice tuples |
|---|---|---|
| `low_confidence_ocr` (computed from OCR and page issues) | 476 | — |
| **any mandatory class** (structural attributes, dates, and the above) | **773** | **204** |
| non-mandatory — bounded sampling, see *Review queue mechanics* | 520 | 155 |
| **total** | **1,293** | **359** |

The two mandatory rows overlap rather than sum: `low_confidence_ocr` is computed
from page signals, and a structural attribute is mandatory regardless of OCR
quality. 773 is the union.

---

## Roles

| Role | Who | May do | May never do |
|---|---|---|---|
| **Reader** | agent (Claude subagent or `codex`) | propose claims, conditions, page maps, aliases, grid readings from a page image or element | set any status past `candidate` |
| **Adjudicator** | a *second*, independently prompted agent | read the same evidence blind and record agreement or disagreement | see the first reader's output before recording its own |
| **Reviewer** | a person | accept, reject, correct, mark `needs_source` | accept without the queue having rendered the crop |
| **Auditor** | `cli curate audit`, deterministic | measure, count, fail the gate | change a status |

Two independent agent readings that agree raise `confidence_basis` to
`two_reader_agreement` and move a claim to `in_review`. They never accept it.

> **This is a change, not a description of current behaviour.**
> `table_review.PROMOTABLE` is `("accepted", "corrected", "cross_family_verified")`
> today: agreement between two *different model families* already promotes, and
> 324 facts in the store were written that way with no human in the loop. C0
> removes `cross_family_verified` from `PROMOTABLE`. The 324 rows are recorded as
> a grandfathered exception and migrate as `candidate` like everything else.
>
> The agreement evidence is still worth having — two readers agreed on 174 of 174
> cells in the round-1 pass — but it is agreement between two same-family models
> on the same prompt family, and the round-1 report says so itself: *"correlated
> failure is possible."* It is reproducibility evidence, not correctness
> evidence. Only the human review is correctness evidence.

Agents read **corpus content as untrusted data** (prohibition 10). Reader
prompts state this explicitly and reader output is parsed into typed fields; no
text extracted from a page is executed, followed as an instruction, or used to
build a command.

---

## C0 — Schema, guards, and the curation CLI

**Build.** `src/fence_evidence/curation/` with `schema.py`, `guard.py`,
`entities.py`, `dossier.py`, `pagemap.py`, `migrate.py`, `claims.py`,
`crops.py`, `grids.py`, `review.py`, `procedures.py`, `conflicts.py`,
`bundle.py`, `audit.py`. Additive migration; `store.SCHEMA_VERSION` → 2.

Also in C0, one change to existing behaviour and five frozen fixtures, each with
its own test:

1. `table_review.PROMOTABLE` loses `cross_family_verified`.
2. `workspace/catalog/data-digests.json` is written, recording SHA-256 for every
file under `data/**` — the corpus manifest's 144 rows cover only `manuals/` and
`china/`, so `data/` has no baseline hash anywhere today, and P1b cannot check
it without one.
3. `workspace/catalog/spelling-fixture.jsonl` freezes a blind-labelled set of
every observed spelling of the five styles and the manufacturers, each with its
`element_id`, hashed. C-B2 measures recall against it.
4. `workspace/catalog/table-flag-fixture.jsonl` enumerates the seven known
false-positive `table_not_reconstructed` pages with a typed `flag_disposition`,
reconciling the `is_table` contradiction in the ground-truth JSON.
5. `eval/curation-questions.json` holds one fixture question per capability
(CAP-1..CAP-9) with the exact call and the expected answer shape, so R3, R5, R6,
R7 and R10 have predicates rather than the word "pass".
6. `workspace/catalog/ground-truth-round-1.jsonl` freezes the blind
manual-verification readings currently living unhashed in
`workspace/tests/agent-read-*.json`, with a recorded SHA-256 and a
`reader_count` per crop. Every later criterion cites *that file*, not a report
whose companion table has drifted — `table_read_candidates` has moved from the
report's 1,051 rows / 348 `agent_verified` to 1,225 / 12 `agent_verified` / 504
`cross_family_verified`.

CLI surface, all new under `cli curate`:

```bash
cli curate init                        # additive migration
cli curate probe    --slice bufftech   # C0.5
cli curate entities --slice bufftech   # C1
cli curate dossier  --slice bufftech   # C2
cli curate pagemap  --slice bufftech   # C3
cli curate migrate  --slice bufftech   # C4
cli curate backfill --slice bufftech   # C4b
cli curate grids    --slice bufftech   # C5
cli curate procedures --slice bufftech # C6
cli curate queue    --class footing --limit 25
cli curate review   --claim <id> --decision accept --rationale "..."
cli curate conflicts --slice bufftech  # C7
cli curate bundle   --slice bufftech   # C7
cli curate audit    --slice bufftech   # C8
```

**Gate C0.** A test asserts a full curation run leaves the eleven canonical
tables and `facts` byte-identical (row count and an ordered-row hash). A test
asserts the `set_authorizer` guard rejects a write to every canonical table
name. A test asserts `retrieval_units` and `retrieval_fts` are untouched. The
existing 101 tests still pass.

---

## C0.5 — Feasibility probe (cheap, before anything expensive)

**Why it exists.** C5 is the stage that can fail, and everything before it is
expensive: 522 page maps of which roughly 365 need agent reading — the round-1
pass read 44 pages across seven agents and that was already a substantial run —
plus 19 dossiers with four human judgement calls, entity resolution with review
rows, and 1,293 claim migrations with crop generation. Discovering at C5 that
the method does not work would waste all of it.

**What it does.** One `wind_exposure_footing` crop. Two blind readers. Compare
against the frozen ground truth. It needs only `cur_claims`,
`cur_claim_evidence`, `cur_table_readings`, and a crop — minutes, not hours.

**It also fixes R2's baseline and F1's floor.** The 0.588 digit-bearing recall
figure was measured over 534 values across all 44 flagged pages and all table
kinds. C5's actual population is different: of the 39 Tier-A crops, **8 are
`wind_exposure_footing`, 24 are `bill_of_materials`, 6 are `drawing_only` and 1
is prose**, and only **7 of the 39 have more than one reader** — the other 32
have a single agent reading, so "cell-for-cell against ground truth" is against
one reader on 82% of the surface. C0.5 recomputes the store-recall baseline on
the exact frozen denominator R2 will use, and publishes it. R2's target is set
from that number, not from 0.588.

**Gate C0.5.** The probe reads one grid, produces cell claims with
`evidence_kind='visual_reading'` and pixel bboxes, renders its crop, and writes
to the readiness report: the recomputed store-recall baseline on the frozen
denominator, the per-crop reader counts, **R2's target**, and **F1's N** — the
minimum count of accepted, fully-conditioned structural claims slice 1 must
produce. Both numbers are published before C5 runs and are not revised
afterwards. If two readers cannot agree on a grid the ground truth already
contains, C1 does not start and nothing downstream of it does either.

---

## C1 — Entities, aliases, relations

**Sequenced first**, because `cur_document_dossiers.issuing_org_entity_id` /
`brand_entity_id` and `cur_page_map_entities` all reference `cur_entities`. Run
in the other order, all 522 page maps ship with no entity links and no later
gate forces a backfill.

**Method.** Seed from `documents.manufacturer` and `documents.product_family`
(17 and 104 free-text values corpus-wide), then resolve. Every seed string
becomes an alias with `alias_kind='observed_in_source'` and its evidence; the
canonical name is a curator decision recorded in a review row.

**Must produce.** One manufacturer entity per corporate entity, with
`brand_succeeds` edges cited to the NOA transfer language — ten of the seventeen
spellings denote the single Barrette group. Five `product_style` entities
(Columbia, Imperial, Chesterfield, Breezewood, Brookline) resolving from every
spelling in the slice. The component role vocabulary populated. One approval
entity per NOA number with `issued_by → Miami-Dade` and `approved_under` edges.

**Gate C1.** Every Tier-A document resolves to exactly one manufacturer entity.
Each of the five style names resolves from every spelling in the frozen spelling
fixture (see doc 5, C-B2). Every `accepted` alias cites an `element_id`; every
alias without one is `curator_label` and stays `candidate`. No entity is
`accepted` without a review row.

---

## C2 — Document dossiers

**Scope.** All 19 slice documents.

**Method.** Deterministic where possible: `coverage`, `known_defects`,
`duplicate_group_id` and `approval_lineage_id` derive from canonical rows and
the existing `relations` edges. Judgement where necessary: `authority_level`,
`document_role`, `revision_status` and its basis and quote.

**The four decisions this stage must produce on the record:**

1. Which of the four byte-identical filings of NOA 24-0117.05 is
`canonical_for_duplicate_group`, and why.
2. Whether NOA 23-0314.05 is `current` or `superseded`, cited to a quoted
sentence in a document body — the stored status says `superseded`, the curated
title says *"current"*, and the resolver reads it `in_force`.
3. What `authority_level` the 2009 catalog carries, given that its OCR'd pages
read at 28.0% mean confidence.
4. Whether `bufftech-installation-guide-afence.pdf` (100% scanned, 222 facts) is
`manufacturer_legacy_technical` or `unknown` revision status.

**Gate C2.** 19/19 dossiers. Every `revision_status` other than `unknown`
carries an `element_id` **and** a `revision_quote` that is a verbatim substring
of that element and is *not* a substring of the filename or `documents.title`.
Every duplicate group has exactly one `canonical_for_duplicate_group=1`. No two
documents with different `sha256` share a `duplicate_group_id`. The five NOAs
specifically carry a non-`unknown` status — the supersession language
demonstrably exists in their bodies, so "all unknown" is not an acceptable pass.

---

## C3 — Page content maps

**Scope.** 522 pages.

**Method.** A deterministic first pass assigns `ocr_risk`, `drawing_present`,
`has_reviewable_table`, `flag_disposition` and the mechanical content classes
(`blank`, `pe_seal`, `contact_boilerplate`, `toc`) from canonical signals. An
agent reader classifies the remainder from the page image plus its elements.
Pages carrying `table_not_reconstructed`, `mojibake_text_layer`, or OCR mean
below 80 are pre-marked `ocr_risk='high'` — **113 pages**, before anything is
read.

**Cost control.** All five byte-identical duplicates copy their twin's map with
`derived_from_page_map_id` recorded: the two manual pairs (106 pages) and the
three NOA filings (51 pages of the most expensive scanned material). That
removes **157 of 522 pages** from agent reading, and it applies the same rule
C-A5 uses for dossiers rather than a different one.

**The false-positive list is a fixture, not a markdown table.** The
manual-verification report says seven pages are false-positive
`table_not_reconstructed` and its table lists five. The ground-truth JSON holds
two more — NOA-23-0314.05 p9 and NOA-06-1019.01 p3 — both recorded with
`is_table: true` *and* `table_kind: drawing_only`, contradictory on their face,
and both different in kind from the other five: they are index sheets carrying
**per-model maximum post-spacing labels**. Those are real CAP-6 values.
`flag_disposition` distinguishes `false_positive_cross_reference` from
`false_positive_index_sheet`, and the index sheets stay in C5's scope.

**Gate C3.** 522/522 mapped, each with ≥1 content class. Every page classed
`wind_exposure_footing_table` carries `has_reviewable_table=1`. The seven
flagged pages are enumerated in the fixture with a typed `flag_disposition` and
the `is_table` contradiction reconciled. A blind-labelled 40-page sample agrees
with the map on the primary content class at ≥0.90.

---

## C4 — Fact → candidate claim migration (requirement 4)

**This stage creates zero facts. It creates 1,293 candidates and rejects most of
them at the door.**

The slice's 1,293 `facts` rows split by extractor: 1,041 `regex-v1` migrate with
`origin='regex_fact_migration'`, and 252 `table-read:cross_family_verified`
migrate with `origin='table_read_candidate'`. Neither origin confers status.
Lineage is a natural key (`source_fact_key`), never a foreign key onto
`facts.fact_id` — an inbound FK would make `cli facts --extract`'s `DELETE FROM
facts` raise, and fact ids are reassigned on every re-extract.

For a `regex-v1` row:

```text
cur_claims.origin           = 'regex_fact_migration'
cur_claims.source_fact_key  = sha256(document_id|version_id|page_no|element_id|
                                     fact_type|value_original)[:16]
cur_claims.status           = 'candidate'          # always
cur_claims.subject_text_raw = facts.subject        # verbatim, e.g.
                                                   # 'FENCING INSTRUCTIONS > POST'
cur_claims.subject_entity_id= NULL                 # until a curator binds it
cur_claims.subject_binding  = 'unbound'
cur_claims.attribute        = FACT_TYPE_TO_ATTRIBUTE[facts.fact_type]
cur_claims.value_raw_lexeme = facts.value_original # '30" deep'
cur_claims.confidence_basis = 'regex_match' | 'ocr_below_threshold'
cur_claims.review_class     = derived from attribute + OCR signals
```

`facts.conditions = '{}'` becomes **no condition rows at all**. It is not
backfilled, guessed, or inherited from a neighbouring fact, and under §2.5.4 a
mandatory-class claim with no stated condition cannot be accepted.

**Migration order is bindability order**, because most of this work is
predestined: migrate the 60 style-rooted heading paths and the 252 conditioned
table-read rows first, gate on a 50-row sample, and generate crops lazily for
rows whose heading root matches no style alias.

Three consequences, stated plainly because they are the point of the stage:

- **Nothing migrates to `accepted`.** Not one of the 1,988 corpus facts, and not
one of the 1,293 slice facts.
- **Almost nothing is bindable as it stands, but the bindable part is
identifiable.** Of the 1,041 `regex-v1` slice facts, **513 carry a heading path
as their subject**, **528 carry neither a heading path nor a product name** —
stray labels, table fragments, and OCR noise such as `'\ CUT-OUT'` and `'YO4
SGNJ TV YADOVLS'` — and exactly **60 name one of the five product styles**. All
60 are a subset of the 513, and **54 of them name the style in the heading's
root segment** — e.g. `'Privacy Fence – Chesterfield, Chesterfield with
CertaGrain Texture > 3. Install First Post'` — while the other 6 have the root
`'P.S.I. MINIMUM'` and the style one level down. That gives the binding pass a
deterministic first cut: match any heading segment against the style aliases
from C1, root first. The 6 non-root matches are the reminder that matching only
the root would quietly miss some. The remaining 981 will mostly not be bindable
even after review: *"dig holes 30″ deep or to frost line"* in a general
instructions section is a claim about no particular product, and the honest
outcome is `blocked`, not a guessed binding.
- **The 252 slice facts marked `cross_family_verified`** — 126
`footing_depth_in` and all 126 `post_spacing_in` — came from an unreviewed agent
reading pass. They carry conditions and a table row label, so they are the
migration's *best* material; they still migrate as `candidate` with
`confidence_basis='two_reader_agreement'` and `review_class='footing'` /
`'spacing'`. Their prior status confers nothing.

Tier-B facts migrate too — all 380 of them, all `regex-v1` — but as
`duplicate_of_claim_id` pointers to their Tier-A twin's claim. No Tier-B claim
is reviewed or accepted independently.

**Gate C4.** 1,293/1,293 migrated, 0 accepted. Every claim has ≥1
`cur_claim_evidence` row whose `crop_path` exists on disk and whose
`crop_sha256` matches. `facts` unchanged, asserted by hash. Every `exact_quote`
is a verbatim substring of the cited element's `text`/`ocr_text` at the cited
`version_id` — not merely equal to the claim's own lexeme, which the same code
writes and which would pass trivially.

---

## C4b — Backfill

Dossier and page-map fields that reference claims created in C4 and C5:
`effective_claim_id`, `expires_claim_id`, and any `cur_page_map_entities` left
empty.

**Gate C4b.** 0 of the 5 approval dossiers have a NULL `effective_claim_id` or
`expires_claim_id`; 0 page maps are entity-empty on a page whose dossier names a
product line. Measured by C-A12.

---

## C5 — Structural table reading (CAP-6)

670 distinct cells across 39 distinct page crops in Tier A, of which 8 crops and
132 cells are `wind_exposure_footing` — the grids CAP-6 actually needs.

**Method.** Not the four stages in `docs/experiment-noa-table-reading.md` — that
document specifies morphological grid detection, per-cell tesseract, restricted
/ unrestricted agreement, and plausibility checks. This is a different method
and saying otherwise borrows evidence it has not earned:

1. **Crop.** Full-page crops, already produced by `cli noa-table-crops`, with
SHA-256s. The crop is always the full page: the ruled-band detector was measured
locking onto fence picket line-work and clipping a real table off the bottom, so
the band is a hint in `notes`, never the crop boundary.
2. **Read the grid as an object.** A reader produces one `cur_table_readings` row
— header vectors with spans, row and column count — plus `cur_table_annotations`
for every bracket, footnote, and unit note, each with the rows and columns it
spans. **The `NON HVHZ` bracket is one reviewed object, not a condition retyped
onto each of N cells.** Then cells, each with its value and its bounding box *in
crop pixels*.
3. **Two blind readers, then adjudicate.** Agreement → `two_reader_agreement`,
status `in_review`. Disagreement → a `reading_disagreement` conflict, front of
the human queue.
4. **Human review, cell by cell, against the crop.** Every accepted cell becomes
a claim with its full condition tuple — `fence_height`, `exposure_category`,
`hvhz_applicability`, `post_size` — generated from the reviewed grid and its
annotations, or it is not accepted.

**Evidence for these claims is `evidence_kind='visual_reading'`.** There is no
element and no quote: the five NOAs have one `table` element between them — a
4×3 OCR word-grid that is not a Table 1 — and a large share of the digit-bearing
cell values appear in no element on their page at all. The claim carries page,
crop, crop hash, `cell_bbox_px`, row and column labels, and the reader's
identity, and the absence of an element is recorded rather than faked.

**The condition that is not negotiable.** The G16 error was a row bracketed `NON
HVHZ` in the source recorded as applying to `HVHZ and Non-HVHZ`. Under this
schema that row cannot be written without an `hvhz_applicability` condition
generated from a reviewed annotation, and a reviewer who cannot see which rows a
bracket spans records `needs_source` and a `knowledge_gap` — not a guess.

**Gate C5.** All 8 `wind_exposure_footing` crops are read, not one. Every one of
their 132 distinct cells is either an accepted claim with a full condition tuple
or a `knowledge_gap` with a reason **and** a recorded abstention. Zero accepted
values disagree with the frozen ground truth. Zero silent errors — a wrong value
that was not abstained on fails the stage outright, which is the criterion
`docs/experiment-noa-table-reading.md` already sets and the one that would have
caught G16. Coverage, recall, precision and abstention are reported together;
recall alone rewards both guessing and shrinking the set.

---

## C6 — Procedures and compatibility

**Scope.** The two current install guides (`1085f7c65c47` fence, `6431d597a32d`
gate) plus the family sheet `c0fa3df89251`.

**Method.** Steps grouped from existing `list` and `paragraph` elements in
reading order; ordinals, prerequisites, and step→figure links proposed by a
reader and reviewed. Warnings attach to their step at creation — there is no
intermediate state in which a warning exists unattached.

Compatibility edges (`attaches_to`, `fits`, `incompatible_with`) come from the
same guides. `incompatible_with` carries `review_class='compatibility'` and is
mandatory-review: a missing "do not use with" is a safety failure, a spurious
one is an inconvenience.

**Gate C6.** ≥1 complete post-and-panel procedure with contiguous ordinals,
every warning attached to a step, every figure evidence row resolving to a crop
on disk. Every `incompatible_with` edge has a human review row.

---

## C7 — Conflicts, gaps, and the bundle

**Conflicts.** Detected where attribute, subject entity, and
`condition_signature` all match and values differ — with `valid_from` and
`revision_status` *inside* the signature, so the five-generation NOA chain
produces `version_difference` groups rather than being invisible. Expected:
version differences on footing and spacing across the chain; a `contradiction`
group on `effective_date`/`expiration_date` where two chain members read
`in_force` simultaneously; `authority_difference` groups against
`data/structural/*.json`'s `curated_dataset` claims. Nothing is auto-resolved.

**Gaps.** Registered for every unreadable table, every attribute a capability
needs and the corpus does not state, every Tier-C exclusion that blocks an
answer, and every claim in `needs_source` — each with a typed `scope_ref` so the
criteria in doc 5 are joins rather than string searches.

**Bundle** (requirement 8). `cli curate bundle --slice bufftech` writes
`workspace/bundles/slice-bufftech-extruded-pvc/bundle.json`:

```text
supported_claims     accepted claims only, each with conditions, authority,
                     validity, confidence, and its evidence array
source_documents     dossiers, with authority level and revision status
components           component entities and their roles
configurations       style x height x width, with the claims that define each
installation_steps   ordered procedures with warnings and figure evidence
tables               reviewed grids with headers, spans and annotations
drawings             drawing and figure evidence with crop paths and hashes
conflicts            every group, unresolved ones included, with all members
knowledge_gaps       every gap, with its reason
not_covered          Tier-C exclusions, named
```

`tables` is a section because prohibition 4 forbids flattening a grid into
independent cells and discarding its structure.

Every claim carries `document_id`, `version_sha256`, `page_no`, `evidence_kind`,
`element_id`+`bbox` **or** `cell_bbox_px`, `crop_path`, `crop_sha256`, and
`exact_quote` where the kind has one. A bundle entry that cannot render its crop
is a build failure, not a warning.

**Gate C7.** Bundle validates; every claim member is `accepted`; every crop
resolves and hashes; `conflicts` and `knowledge_gaps` are non-empty.

---

## C8 — Data-readiness review (requirement 9)

One explicit gate, run by `cli curate audit --slice bufftech`, producing
`workspace/reports/curation-readiness.md`. The projection stays frozen until it
returns `pass`. Criteria are in document 5. A failure is recorded by criterion
and the phase iterates; the projection is not rebuilt "in the meantime".

---

## Review queue mechanics

Ordering, highest priority first:

1. `reading_disagreement` conflicts — two readers differed on a number.
2. Grid annotations (brackets, footnotes) — one decision that conditions many cells.
3. `footing`, `spacing`, `wind_condition` claims.
4. `version_status` claims — they determine which of the others apply.
5. `compatibility` relations, `incompatible_with` first.
6. `dimension`, `tolerance` claims.
7. `low_confidence_ocr` claims not already covered above.
8. Non-mandatory claims, grouped by `attribute` where `review_mandatory=0`,
reviewed by sampling. The sample size is set so the upper 95% bound on that
attribute's error rate is ≤ 0.10, and the bound is reported per attribute — "10%
with zero rejections" is consistent with a true error rate near 25% and is not
evidence of anything.

`cli curate queue --class footing --limit 25` renders 25 claims with their crops
and issues a session token per crop it actually rendered. The reviewer's
decision, rationale, duration, and the crop hashes from that session are
recorded. This is attestation that the tool rendered the evidence, not proof
that a person looked at it, and the readiness report says so.

**Estimated human review volume for the slice:** 204 mandatory tuples plus 670
distinct cell decisions across 39 crops, of which the 8 `wind_exposure_footing`
grids carry **132 distinct cells** (behind 384 candidate reader rows) — the
smallest and most valuable part of the surface. The experiment document's own
cost model is roughly 15 minutes per page; 39 crops is on the order of ten hours
before condition tuples and review records. The C0.5 probe measures the real
per-cell rate and that number replaces this estimate.

---

## What is explicitly deferred

Corpus-wide curation. Slice 2 (SimTek, the second approval chain, including the
NOA 22-0616.10 material-class error from G16). The Catalyst successor catalog.
The China track. Any retrieval, projection, ranking, embedding, serving, or
answer-generation change. All of these wait on C8.
