# 1 — Target question and capability matrix

Nine capability areas. For each: the questions it must answer, the curated
objects an answer is assembled from, the minimum evidence an answer must carry,
what the store can do today (measured), and the check that decides whether the
capability is ready.

Every capability shares one non-negotiable output contract:

```text
answer := { claims[], evidence[], conditions_applied, authority, validity,
            conflicts[], gaps[], not_covered[] }
```

An answer with no `claims` is a legitimate answer. An answer with claims and no
`evidence` is a bug, not a low-confidence result.

---

## CAP-1 — Product identity

**Questions.** *Is "Chesterfield" a Bufftech style, a CertainTeed style, or a
Barrette style?* · *Which brand sells the Columbia line today?* · *Is
"Chesterfield w/ Lattice" the same product as "Chesterfield"?* · *Does the
Miami-Dade approval that names "Extruded PVC Vinyl Fencing" cover Chesterfield?*

**Built from.** `cur_entities` (manufacturer, brand, product_line,
product_style), `cur_entity_aliases`, `cur_entity_relations` (`brand_succeeds`,
`style_of`, `variant_of`).

**Minimum evidence.** Each alias and each succession edge cites an element on a
page. An alias with no element is `alias_kind='curator_label'` and can never be
accepted; a `brand_succeeds` edge with no `cur_claim_evidence` row cannot leave
`candidate`. Neither can be asserted from a filename or from a curator's
knowledge alone.

**Today.** `documents.manufacturer` holds 17 free-text spellings, **10 of which
denote the single Barrette Outdoor Living corporate group and its brands** —
including `Barrette Outdoor Living`, `Barrette Outdoor Living, Inc.`, `Barrette
Outdoor Living (Bufftech)`, `Barrette Outdoor Living (Bufftech / SimTek)`,
`CertainTeed`, `CertainTeed / Barrette Outdoor Living`, `Freedom Outdoor
Living`, `Freedom Outdoor Living / Barrette Outdoor Living`, and two Catalyst
variants. One of the 17 is a 141-character sentence of caveat rather than a
name. `documents.product_family` holds 104 distinct non-null values across the
114 documents that have one; the other 30 are null. There is no alias table and
no way to ask "same product, different label".

**Curation adds.** A resolved entity per real-world thing, every observed
spelling as an alias with its evidence, and succession edges sourced to the NOA
transfer language.

**Ready when.** Every Tier-A slice document resolves to exactly one manufacturer
entity, and each of the five model names resolves from every spelling in the
frozen spelling fixture.

---

## CAP-2 — Component selection

**Questions.** *Which post goes at a line position on a 6 ft Chesterfield run,
and which at a gate?* · *What is the post wall thickness?* · *When is steel
reinforcement required?* · *Which cap fits a 5×5 post?*

**Built from.** `cur_entities` (component, with `structural_role` ∈ line_post /
end_post / corner_post / gate_post / blank_post), `cur_claims` with `attribute`
∈ `component_dimension`, `wall_thickness`, `reinforcement_required`, and
`cur_entity_relations` (`fits`, `requires`, `excludes`).

**Minimum evidence.** A dimension claim quotes its raw lexeme (`5" x 5"`, `.150
nominal`) and cites the cell or line it was read from. Nominal and actual are
distinct attributes, never merged.

**Today.** 656 `reinforcement` facts exist, but the fact's `subject` is a
heading path, so none is bound to a post size or a fence height. No post
dimension, wall thickness, or cap fact type exists at all.

**Curation adds.** Component entities with the role vocabulary, and conditional
claims that bind a component attribute to fence height, position, and wind
condition.

**Ready when.** For the slice family, every component named in an installation
step resolves to a component entity, and every reinforcement claim states the
post size and the fence height it applies to, or carries those conditions with
`operator='unknown'` — which under the schema blocks acceptance rather than
quietly passing.

---

## CAP-3 — BOM construction

**Questions.** *Parts and quantities for 100 ft of 6 ft Chesterfield with two
gates on level ground?* · *How many bags of concrete?* · *How many brackets per
panel?*

**Built from.** `configuration` entities (style × height × panel width),
`cur_claims` with `attribute` ∈ `quantity_per_unit`, `panel_width`,
`post_spacing_max`, plus a deterministic quantity calculator that consumes
claims — it never invents them.

**Minimum evidence.** Every input quantity is an accepted claim. The
calculator's output carries `origin='calculated'` with `derived_from_claims`
naming what it multiplied, authority `inferred`, and `evidence_kind='derived'` —
which under the schema can never itself be `accepted`.

**Today.** Nothing. `post_spacing_in` yields 129 facts of which 126 arrived from
the unreviewed table-reading pass; no panel-width or per-panel-count fact type
exists. The 2009 and 2014 catalogs carry the SKU and dimension tables that would
supply these, and both are partly scanned.

**Curation adds.** Configuration entities, per-unit quantity claims from catalog
tables, and an explicit statement of what a BOM cannot yet cover.

**Ready when.** A BOM for one configuration of the slice family lists every line
item with a claim id, and every line item a person would expect but the corpus
does not state appears in `gaps[]` rather than being silently absent.

---

## CAP-4 — Assembly

**Questions.** *How does a rail attach to a post on this line — routed through,
bracketed, screwed?* · *Which fastener, how many, where?* · *Can a Chesterfield
panel be used with a 4×4 post?*

**Built from.** `cur_entity_relations` (`attaches_to`, `compatible_with`,
`incompatible_with`) with a `method` attribute, and `cur_claims` with
`attribute='fastener_spec'`.

**Minimum evidence.** A compatibility edge cites the passage or drawing that
establishes it. Compatibility inferred from co-occurrence in a catalog page is
`inferred` and requires review before it is accepted.

**Today.** Not represented in any form. The information exists in the 44-page
and 50-page installation guides as prose and figures.

**Curation adds.** The compatibility graph, restricted to the slice family, with
`incompatible_with` treated as first-class — a "do not use with" sentence is a
safety claim and is on the mandatory-review list.

**Ready when.** Every attachment method used in the slice family's install
guides is an edge with evidence, and every `incompatible_with` edge is reviewed.

---

## CAP-5 — Installation

**Questions.** *In what order do I install posts, rails, and pickets?* · *How
long does concrete cure before panels go on?* · *How do I rack a panel on a
slope, and to how many degrees?* · *What warning applies to setting posts?*

**Built from.** `cur_procedures` and `cur_procedure_steps` (ordinal, action,
parts, prerequisites, warnings, figure references), `cur_claims` with
`attribute` ∈ `cure_time`, `racking_degrees`, `slope_method`.

**Minimum evidence.** Each step cites the element it came from. A warning is
stored attached to its step, never as a free-floating claim — separating a
warning from the step it governs is a documented failure mode.

**Today.** Steps exist only as `list` and `paragraph` elements in reading order;
7,219 list elements corpus-wide with no ordinal semantics, no prerequisite
edges, and no step→figure link. `racking_degrees` yields 5 facts corpus-wide,
all OCR-derived, 2 flagged.

**Curation adds.** Ordered procedure graphs for the slice family, with warnings
and figures bound to their step.

**Ready when.** The slice family has ≥1 complete post-and-panel procedure whose
steps are contiguous, whose warnings are each attached to a step, and whose
figure references resolve to a region crop.

---

## CAP-6 — Structural validation

**Questions.** *What footing depth applies to Chesterfield at 6 ft, Exposure C,
HVHZ?* · *What is the maximum post spacing at 180 mph?* · *Which design wind
speed was this line tested to, under which ASCE edition?*

**Built from.** `cur_claims` with `attribute` ∈ `footing_depth`,
`footing_diameter`, `post_spacing_max`, `wind_speed_design`, `embedment_depth`,
each carrying a mandatory condition set over `fence_height`,
`exposure_category`, `hvhz_applicability` and `post_size`, and each referencing
the `cur_table_readings` grid it came from.

**Minimum evidence.** The table cell, its row and column labels, the table crop,
and the crop's SHA-256. Wind speed is never converted to pressure.

**Today. This is the weakest capability and the highest-value one.** The values
live in Table 1 of the NOA drawing sheets, which are line-work in a scan. 73
pages carry `table_not_reconstructed`; 66 of them are in the slice. A blind
manual verification of the 44 distinct flagged pages measured digit-bearing
value recall at **0.588** — OCR reads the words and loses the numbers, and the
numbers it loses are the footing depths and maximum post spacings. 311
`footing_depth_in` facts exist, but the 162 that carry real conditions were
written by an **unreviewed** cross-family reading pass — and they were promoted
into `facts` without a person, because `table_review.PROMOTABLE` accepts
`cross_family_verified`. 324 candidates across the corpus carry a
`promoted_fact_id`, and `facts` has grown from 1,664 to 1,988 accordingly.

The structural consequence for the evidence model: the five NOAs have exactly
**one `table` element between them** — a 4×3 OCR word-grid on 12-1106.11, and
not a Table 1 wind/exposure grid. The values CAP-6 needs have no element, no
bounding box and no quotable text. They exist only as pixels. That is why
`cur_claim_evidence` carries a second evidence kind rather than a nullable
element id.

**Curation adds.** Every structural claim gets its full condition tuple or it
does not exist. Every one is on the mandatory-review list. The 922 slice
`table_read_candidates` become the review queue rather than a fact source.

**Ready when.** For all 8 `wind_exposure_footing` grids in the slice — 132
distinct cells — every cell is either an accepted claim with its full condition
tuple or an explicit `knowledge_gap` with a reason. A single accepted claim
whose value disagrees with the page image fails the capability outright.

---

## CAP-7 — Approvals

**Questions.** *Is a 6 ft Chesterfield fence Miami-Dade approved?* · *Under
which NOA, valid until when, for which configurations, in which jurisdiction?* ·
*Does the approval cover the gate as well as the panel?*

**Built from.** `cur_entities` (approval, authority, jurisdiction), `cur_claims`
with `attribute` ∈ `approval_scope`, `effective_date`, `expiration_date`,
`tested_configuration`, and `cur_entity_relations` (`approved_under`,
`issued_by`).

**Minimum evidence.** The NOA number, the issuing authority, and the scope
sentence, each cited. Scope is a claim about *which configurations* — an
approval that covers Columbia and Imperial does not automatically cover a style
whose name appears only in a catalog.

**Today.** 271 `approval_id` facts, 265 of them OCR-derived and 78 flagged. 84
`effective_date` and 75 `expiration_date` facts, all OCR-derived.
`retrieval.resolve_document_version` already reads the dates correctly and
reports an expiry verdict against an `as_of` date it echoes back. There is no
scope claim of any kind: nothing records *what* an approval approves.

**Curation adds.** Approval scope as an explicit, reviewed claim, and a
jurisdiction attribute so an HVHZ row is never returned for a non-HVHZ question
— the exact error found in G16.

**Ready when.** Each of the five NOAs in the slice has a reviewed scope claim
naming the models it covers, a reviewed date pair, and an `hvhz_applicability`
value on every structural claim derived from it.

---

## CAP-8 — Version handling

**Questions.** *Which NOA is in force for this family today?* · *Is the 2009
catalog still applicable?* · *Which of these two 50-page install guides is
current?* · *What changed between NOA 21-0125.07 and 23-0314.05?*

**Built from.** `cur_document_dossiers.revision_status` with a cited basis and a
verbatim quote, `cur_entity_relations` (`supersedes`), and the existing
canonical `relations` edges, which curation reads and does not rewrite.

**Minimum evidence.** Revision status derived from the document body, never from
a filename, a download date, or PDF metadata.

**Today.** 132 of 144 documents are `version_status='unknown'` (9 `superseded`,
3 `active`). The supersession chain for this exact family is the corpus's
best-populated: 22 `supersedes` and 22 `superseded_by` edges between slice
documents, out of 24 each corpus-wide, direction-guarded by a regression test.
But the slice contains a live contradiction the dossier must resolve: NOA
23-0314.05 is stored as `superseded` while its own curated title reads
*"current"*, and NOA 24-0117.05 is stored `unknown` in **all four** of its
filings, so the corpus's current approval has no asserted status anywhere. And
the four byte-identical filings of 24-0117.05 sit under four different
`manufacturer` values with four different `doc_type` values —
`engineering_approval`, `hvhz_noa`, `unspecified`, and
`real_miami_dade_noa_vinyl_fence`.

**Curation adds.** One dossier per document that states revision status, its
basis, and its evidence; and a family-level canonical selection that names one
filing as the citable one while every duplicate stays addressable.

**Ready when.** The slice family answers "which approval is in force" with one
document, one date pair, and one evidence citation, and the other three filings
of that approval resolve to it as duplicates rather than as competing answers.

---

## CAP-9 — Visual evidence

**Questions.** *Show me the drawing that defines the footing detail.* · *Show me
the page this footing depth came from, with the cell highlighted.* · *Which
figure shows rail-to-post attachment?*

**Built from.** `cur_claim_evidence.crop_path` with either `bbox` (an
`element_quote`) or `cell_bbox_px` (a `visual_reading`),
`pages.page_image_path`, and `figure`/`drawing`/`table` region crops.

**Minimum evidence.** A crop file that exists on disk, with a recorded SHA-256,
whose bbox lies inside the page.

**Today. Strong for text, absent for the values that matter.** All 522 slice
pages have a page image at 200 dpi. All 24,088 slice elements have a bbox. But
region crops exist only for `figure`, `table`, and `drawing` elements — 1,484 of
them — so of the slice's 1,041 `regex-v1` facts, **74 sit on an element with a
stored crop and 967 do not**; those 967 are paragraphs (341), lists (392),
headings (221) and OCR supplements (13). And the CAP-6 values have no element at
all. Their bboxes are in PDF display points and the page image scale is a fixed
200/72, so the crop is deterministically derivable; it has simply never been
derived.

**Curation adds.** A crop for every claim, cut with `pdftoppm` at the page's own
`page_image_dpi` — poppler, not the optional Pillow — with its own SHA-256.
Element-backed claims carry `bbox`; grid readings carry `cell_bbox_px` instead,
and the absence of an element is recorded rather than faked. That split is what
makes requirement 10 checkable rather than aspirational.

**Ready when.** 100% of accepted claims in the slice resolve to an on-disk crop
whose SHA-256 matches the recorded value.

---

## Cross-capability summary

| Capability | Today | Blocking gap | Mandatory review |
|---|---|---|---|
| CAP-1 identity | free-text, 104 family strings | no alias resolution | entity acceptance needs a review row |
| CAP-2 component | unbound reinforcement facts | no component entity | `dimension`, `compatibility` |
| CAP-3 BOM | absent | no quantity claims | `dimension`, `spacing` |
| CAP-4 assembly | absent | no compatibility graph | `compatibility` |
| CAP-5 installation | flat text | no step ordering | `tolerance` |
| CAP-6 structural | **0.588 digit recall**, 1 table element in 5 NOAs | scanned Table 1 (G2/G15) | **all eight classes** |
| CAP-7 approvals | dates work, scope absent | no scope claim | `wind_condition`, `version_status` |
| CAP-8 versions | chain exists, 132 unknown | no dossier | `version_status` |
| CAP-9 visual | pages+bbox complete | crops for 74/1,041 regex facts; no element for CAP-6 values | `low_confidence_ocr` |

CAP-6 is the capability that justifies the whole phase and the one most likely
to fail. Document 4 therefore puts a cheap feasibility probe (C0.5) in front of
every expensive stage, so a failure there costs minutes rather than the whole
dossier and page-map effort.

CAP-2, CAP-3 and CAP-4 have "Ready when" clauses but no Group-R readiness
criterion in document 5. That is deliberate: they are out of scope for slice 1's
readiness gate and are registered under R10 as capability gaps, so their absence
is published rather than implied.
