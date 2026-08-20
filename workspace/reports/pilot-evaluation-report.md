# Evaluation report — gold question set against the ten-document pilot

Questions: **18** (15 answerable, 3 no-answer) · k = 10

26 questions were skipped because none of their expected documents are in the store yet: gq-102, gq-103, gq-104, gq-105, gq-106, gq-108, gq-109, gq-110, gq-111, gq-113, gq-114, gq-119, gq-120, gq-121, gq-003, gq-006, gq-007, gq-008, gq-010, gq-011, gq-012, gq-013, gq-015, gq-016, gq-021, gq-022.

| Metric | Value | Acceptance |
|---|---|---|
| Document recall@10 | 0.800 | A3 ≥ 0.80 — PASS |
| Page recall@10 | 0.600 | reported |
| MRR | 0.628 | reported |
| Evidence support (terms in the retrieved unit) | 0.723 | A3 ≥ 0.70 — PASS |
| Page evidence support (terms anywhere on a retrieved page) | 0.867 | reported |
| No-answer precision | 1.0 | A4 ≥ 0.66 — PASS |

## By category

| Category | n | doc hits | passed | mean support | failing ids |
|---|---|---|---|---|---|
| comparison | 2 | 2 | 1 | 0.5 | gq-017 |
| conditional_table_lookup | 3 | 2 | 2 | 0.756 | gq-004 |
| exact_identifier | 2 | 2 | 2 | 0.75 | — |
| exact_product | 1 | 1 | 1 | 0.667 | — |
| historical_version | 1 | 1 | 1 | 1.0 | — |
| no_answer | 3 | 0 | 3 | None | — |
| paraphrase | 1 | 1 | 1 | 1.0 | — |
| source_verification | 1 | 1 | 1 | 0.667 | — |
| table_retrieval | 1 | 0 | 0 | 0.75 | gq-009 |
| visual_evidence | 3 | 2 | 2 | 0.667 | gq-019 |

## Phase 7 — experiments this evaluation would justify

Only categories that actually failed appear here. Nothing below is built.

### conditional_table_lookup — 1 of 3 failing

- **Problem**: conditional_table_lookup questions fail lexical retrieval (failing ids: gq-004).
- **Experiment**: Table-aware structured lookup keyed on conditions (wind speed, exposure, height) resolved against table_cells and facts.
- **Acceptance**: Answers the conditional questions with the correct cell, and returns 'outside documented range' rather than a nearest-neighbour value.

### table_retrieval — 1 of 1 failing

- **Problem**: table_retrieval questions fail lexical retrieval (failing ids: gq-009).
- **Experiment**: Field-boosted lexical retrieval that ranks table units above prose when the query asks for a table.
- **Acceptance**: Improves table_retrieval recall@10 without reducing overall recall.

### visual_evidence — 1 of 3 failing

- **Problem**: visual_evidence questions fail lexical retrieval (failing ids: gq-019).
- **Experiment**: Visual/page-level retrieval for drawing-heavy documents.
- **Acceptance**: Improves recall@10 on visual_evidence questions without reducing lexical recall elsewhere.

Failing categories with no pre-registered experiment: comparison. These need extraction or annotation review first, not a new retrieval mode.

## Failures in detail

### gq-004 — conditional_table_lookup
*I'm installing Bufftech Chesterfield fence in Miami-Dade in Exposure C. If I pour a 36 inch deep footing, what is the maximum post spacing the NOA allows?*

- query: `Exposure C 36 inch footing maximum post spacing vinyl fence NOA Bufftech post spacing footing depth table HVHZ max post spacing exposure C`
- expected: manuals/certainteed-bufftech/structural/NOA-23-0314.05-CertainTeed-Chesterfield-Columbia-Imperial-Breezewood-Brookline-current-2023-2029.pdf
- doc rank: None · unit support: 1.0 · page support: 1.0 · missing terms: []
- top hit: manuals/barrette-outdoor-living/bufftech-simtek-fence-install-guide.pdf p17 score 30.9146

### gq-009 — table_retrieval
*Show me the maximum post spacing and footing dimensions table from the current CertainTeed / Bufftech extruded PVC vinyl fence NOA.*

- query: `maximum post spacing and footing dimensions table vinyl fence NOA Table 1 footing depth post spacing wind exposure Bufftech footing table`
- expected: manuals/certainteed-bufftech/structural/NOA-23-0314.05-CertainTeed-Chesterfield-Columbia-Imperial-Breezewood-Brookline-current-2023-2029.pdf
- doc rank: None · unit support: 0.75 · page support: 1.0 · missing terms: ['FOOTING TABLE']
- top hit: manuals/industry-standards/CLFMI-Chain-Link-Wind-Load-Guide-Line-Post-Spacing_WLG2445_2023.pdf p14 score 22.2422

### gq-017 — comparison
*When the Columbia/Imperial/Chesterfield fence approval moved from CertainTeed to Barrette, did the allowable post spacing change - and did the engineer of record change?*

- query: `did post spacing change CertainTeed to Barrette vinyl fence NOA compare NOA 23-0314.05 and 24-0117.05 post spacing table engineer of record change Barrette CertainTeed fence`
- expected: manuals/barrette-outdoor-living/structural/noa-24-0117.05-vinyl-fencing.pdf, manuals/certainteed-bufftech/structural/NOA-23-0314.05-CertainTeed-Chesterfield-Columbia-Imperial-Breezewood-Brookline-current-2023-2029.pdf
- doc rank: 2 · unit support: 0.2 · page support: 0.4 · missing terms: ['Pedro De Figueiredo', 'Robert Nieminen', 'POST SPACING AND FOOTING DIMENSIONS', 'ASCE 7-10']
- top hit: manuals/certainteed-bufftech/structural/NOA-21-0125.07-CertainTeed-extruded-pvc-fencing-2021-2024-superseded.pdf p8 score 19.1602

### gq-019 — visual_evidence
*Show me the post and footing cross-section from the current Bufftech vinyl fence NOA - what footing diameter, concrete strength and post reinforcement does it detail?*

- query: `vinyl fence post footing cross section 12 inch diameter 3000 psi aluminum post reinforcement footing detail Bufftech NOA post and footing design detail vinyl fence`
- expected: manuals/certainteed-bufftech/structural/NOA-23-0314.05-CertainTeed-Chesterfield-Columbia-Imperial-Breezewood-Brookline-current-2023-2029.pdf
- doc rank: None · unit support: 0.0 · page support: 0.0 · missing terms: ['POST AND FOOTING DESIGN', '3000 PSI CONCRETE', 'EXISTING SOIL', 'FOOTING TABLE']
- top hit: manuals/industry-standards/CLFMI-Chain-Link-Wind-Load-Guide-Line-Post-Spacing_WLG2445_2023.pdf p14 score 17.3125

