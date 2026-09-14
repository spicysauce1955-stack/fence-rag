# Evaluation report — gold question set against the full corpus

Questions: **78** (41 answerable, 37 no-answer) · k = 10

Configuration: second stage on, R3 duplicate suppression on, R5 page cap off.

Every gold question was runnable.

## Acceptance — natural question

the question text verbatim — what query.py sends as situation.question

Figures published in `docs/` and `workspace/reports/` before 2026-09-14 were measured on the retired `keyword_hint` form and do not compare with these; see `docs/keyword-ruler-audit.md`.

| Metric | Value | Acceptance |
|---|---|---|
| Document recall@10 | 0.8049 | A3 ≥ 0.80 — PASS |
| Page recall@10 | 0.610 | reported |
| MRR | 0.611 | reported |
| Evidence support (terms in the retrieved unit) | 0.5271 | A3 ≥ 0.70 — FAIL |
| Page evidence support (terms anywhere on a retrieved page) | 0.637 | reported |
| No-answer precision | 0.4865 | A4 ≥ 0.66 — FAIL |
| False-unsupported rate (answerable questions wrongly declared unsupported) | 0.3902 | A4b ≤ 0.20 — FAIL |

## By category

| Category | n | doc hits | passed | mean support | failing ids |
|---|---|---|---|---|---|
| comparison | 4 | 3 | 1 | 0.3 | gq-120, gq-017, gq-018 |
| conditional_table_lookup | 7 | 7 | 5 | 0.614 | gq-112, gq-005 |
| conflict | 2 | 2 | 0 | 0.155 | gq-015, gq-016 |
| current_version | 2 | 1 | 1 | 0.3 | gq-012 |
| exact_identifier | 3 | 3 | 3 | 0.667 | — |
| exact_product | 4 | 4 | 4 | 0.75 | — |
| historical_version | 2 | 2 | 2 | 0.8 | — |
| no_answer | 37 | 0 | 18 | None | gq-117, gq-201, gq-202, gq-203, gq-204, gq-205, gq-207, gq-208, gq-210, gq-215, gq-222, gq-223, gq-224, gq-226, gq-227, gq-229, gq-230, gq-231, gq-232 |
| paraphrase | 5 | 1 | 1 | 0.2 | gq-105, gq-106, gq-108, gq-109 |
| source_verification | 4 | 4 | 3 | 0.733 | gq-021 |
| table_retrieval | 4 | 2 | 2 | 0.417 | gq-009, gq-010 |
| visual_evidence | 4 | 4 | 3 | 0.75 | gq-019 |

## Routed interfaces

Every metric above is the **search** harness over every gold question, routed ones included — same denominators, same values as before routing existed. The block below is separate and is not averaged into it.

Declared interfaces: `resolve` 1, `search` 77

1 question(s) are additionally answered through the interface they declare. The graded number is **`answer_support`**: the annotated answer terms in the text of the *one* document the interface asserts as its answer — the active member for `resolve`, the top-ranked fact's document for `facts`. It is the analogue of neither headline support metric (narrower than a page, wider than a unit) and is averaged with neither. `returned documents support` is the same terms anywhere in **any** document returned — for `resolve` that is the whole supersession chain, so a term printed only in a superseded member counts — and it is reported, never graded. The pass rule is the search harness's own (`doc_rank` found and `answer_support` ≥ 0.5).

`page_rank` is reported only by an interface that knows a page (0 of 1 routed question(s) here). `resolve` answers with a document and reports none: it used to stamp page 1 on every chain member, which measured only whether the annotation happened to name page 1.

| Interface | n | doc recall | MRR | answer support | returned-docs support | record support | passed |
|---|---|---|---|---|---|---|---|
| resolve | 1 | 1.0 | 1.0 | 1.0 | 1.0 | 0.4 | 1/1 |

### Before and after, question by question

| id | category | interface | doc rank search → routed | support search unit → routed answer document | passed search → routed |
|---|---|---|---|---|---|
| gq-011 | current_version | resolve | 1 → 1 | 0.6 → 1.0 | PASS → PASS |

The search rows for these questions are unchanged and still appear in the by-category table and the failure list above; a routed question is not removed from the search denominator.

#### gq-011 — resolved `23-0314.05`

- active: manuals/industry-standards/structural/Miami-Dade-NOA_Barrette-Outdoor-Living_Extruded-PVC-Vinyl-Fencing_24-0117.05.pdf
- basis: no member is marked active; inferred in force from an agreed expiration date 2029-03-13 still ahead of 2026-08-28, and nothing in the chain supersedes it
- basis kind: `inferred_in_force`
- chain: 8 member(s)
- answer support is measured over the active member alone; terms found there 1.0, terms found anywhere in the chain 1.0
- page rank: not reported: this interface answers with documents, not pages
    - superseded  manuals/certainteed-bufftech/structural/NOA-06-1019.01-fence-columbia-imperial-chesterfield.pdf
    - superseded  manuals/certainteed-bufftech/structural/NOA-12-1106.11-extruded-pvc-vinyl-fencing.pdf
    - superseded  manuals/certainteed-bufftech/structural/NOA-21-0125.07-CertainTeed-extruded-pvc-fencing-2021-2024-superseded.pdf
    - superseded  manuals/certainteed-bufftech/structural/NOA-23-0314.05-CertainTeed-Chesterfield-Columbia-Imperial-Breezewood-Brookline-current-2023-2029.pdf
    - unknown  manuals/industry-standards/structural/Miami-Dade-NOA_Barrette-Outdoor-Living_Extruded-PVC-Vinyl-Fencing_24-0117.05.pdf
    - unknown  manuals/freedom-outdoor-living/structural/MiamiDade-NOA-24-0117.05-Barrette-Extruded-PVC-Vinyl-Fence.pdf
    - unknown  manuals/certainteed-bufftech/structural/NOA-24-0117.05-Barrette-successor-extruded-pvc-fencing-post-CertainTeed-transfer-2029.pdf
    - unknown  manuals/barrette-outdoor-living/structural/noa-24-0117.05-vinyl-fencing.pdf

## Phase 7 — experiments this evaluation would justify

Only categories that actually failed appear here. Nothing below is built.

### conditional_table_lookup — 2 of 7 failing

- **Problem**: conditional_table_lookup questions fail lexical retrieval (failing ids: gq-112, gq-005).
- **Experiment**: Table-aware structured lookup keyed on conditions (wind speed, exposure, height) resolved against table_cells and facts.
- **Acceptance**: Answers the conditional questions with the correct cell, and returns 'outside documented range' rather than a nearest-neighbour value.

### conflict — 2 of 2 failing

- **Problem**: conflict questions fail lexical retrieval (failing ids: gq-015, gq-016).
- **Experiment**: Conflict surfacing: return every source that states a value for the same condition, with its version status.
- **Acceptance**: Both conflicting sources appear in the top 10 with their statuses.

### no_answer — 19 of 37 failing

- **Problem**: no_answer questions fail lexical retrieval (failing ids: gq-117, gq-201, gq-202, gq-203, gq-204, gq-205, gq-207, gq-208, gq-210, gq-215, gq-222, gq-223, gq-224, gq-226, gq-227, gq-229, gq-230, gq-231, gq-232).
- **Experiment**: Rarest-term coverage plus a calibrated score floor, reported as an explicit unsupported-answer response.
- **Acceptance**: No-answer precision >=0.66 with no loss of answerable recall.

### paraphrase — 4 of 5 failing

- **Problem**: paraphrase questions fail lexical retrieval (failing ids: gq-105, gq-106, gq-108, gq-109).
- **Experiment**: Dense semantic retrieval over the pilot corpus.
- **Acceptance**: Improves recall@10 on paraphrase questions by >=0.15 without reducing recall on exact_identifier or conditional_table_lookup.

### table_retrieval — 2 of 4 failing

- **Problem**: table_retrieval questions fail lexical retrieval (failing ids: gq-009, gq-010).
- **Experiment**: Field-boosted lexical retrieval that ranks table units above prose when the query asks for a table.
- **Acceptance**: Improves table_retrieval recall@10 without reducing overall recall.

### visual_evidence — 1 of 4 failing

- **Problem**: visual_evidence questions fail lexical retrieval (failing ids: gq-019).
- **Experiment**: Visual/page-level retrieval for drawing-heavy documents.
- **Acceptance**: Improves recall@10 on visual_evidence questions without reducing lexical recall elsewhere.

Failing categories with no pre-registered experiment: comparison, current_version, source_verification. These need extraction or annotation review first, not a new retrieval mode.

## Failures in detail

### gq-105 — paraphrase
*My back yard drops away pretty steeply. How do I make the fence follow the hillside?*

- query: `My back yard drops away pretty steeply. How do I make the fence follow the hillside?`
- expected: manuals/wam-bam/murphys-vinyl-fence-laws.pdf
- doc rank: None · unit support: 0.0 · page support: 0.0 · missing terms: ['STEPPED', 'SLOPED', '10 degrees']
- top hit: manuals/wam-bam/structural/nantucket-spec-sheet-v3-alt.pdf p1 score 12.4783

### gq-106 — paraphrase
*What keeps a vinyl gate from drooping and dragging after a couple of seasons?*

- query: `What keeps a vinyl gate from drooping and dragging after a couple of seasons?`
- expected: manuals/barrette-outdoor-living/bufftech-gate-install-guide.pdf, manuals/certainteed-bufftech/bufftech-gate-installation-guide.pdf
- doc rank: None · unit support: 0.0 · page support: 0.0 · missing terms: ['stiffener', 'rebar', 'aluminum post inserts']
- top hit: manuals/certainteed-bufftech/bufftech-catalog-brochure-2009.pdf p12 score 5.8221

### gq-108 — paraphrase
*All the posts in the delivery look identical. How do I tell which one is meant for a corner?*

- query: `All the posts in the delivery look identical. How do I tell which one is meant for a corner?`
- expected: manuals/weatherables/weatherables-fencing-master-installation-instructions-2024.pdf
- doc rank: None · unit support: 0.0 · page support: 0.0 · missing terms: ['green dots', 'red dots', 'Line Posts - no marking']
- top hit: manuals/illusions-vinyl-fence/product-price-catalog-186pg.pdf p8 score 14.5351

### gq-109 — paraphrase
*How is a fence post beefed up so the run survives hurricane gusts?*

- query: `How is a fence post beefed up so the run survives hurricane gusts?`
- expected: manuals/illusions-vinyl-fence/75mph-wind-kit-installation-instructions.pdf
- doc rank: None · unit support: 0.0 · page support: 0.0 · missing terms: ['.250”', 'Heavy Duty Posts', 'VH88']
- top hit: manuals/weatherables/weatherables-full-line-catalog-2026.pdf p4 score 13.4388

### gq-112 — conditional_table_lookup
*Local code says design for 130 mph wind. For a 6 ft chain link fence with 2 3/8" Schedule 40 regular-grade posts, what maximum line post spacing does the CLFMI guide give before correction factors?*

- query: `Local code says design for 130 mph wind. For a 6 ft chain link fence with 2 3/8" Schedule 40 regular-grade posts, what maximum line post spacing does the CLFMI guide give before correction factors?`
- expected: manuals/industry-standards/CLFMI-Chain-Link-Wind-Load-Guide-Line-Post-Spacing_WLG2445_2023.pdf
- doc rank: 1 · unit support: 0.333 · page support: 0.333 · missing terms: ['TABLE 4', '130 MPH']
- top hit: manuals/industry-standards/CLFMI-Chain-Link-Wind-Load-Guide-Line-Post-Spacing_WLG2445_2023.pdf p12 score 34.6221

### gq-117 — no_answer
*What is the list price per section of an Illusions V300 6 ft privacy fence?*

- query: `What is the list price per section of an Illusions V300 6 ft privacy fence?`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/illusions-vinyl-fence/product-price-catalog-186pg.pdf p14 score 20.4643

### gq-120 — comparison
*How much racking does Bufftech quote for its Chesterfield privacy fence compared with what Digger Specialties quotes for its Kingston privacy panel?*

- query: `How much racking does Bufftech quote for its Chesterfield privacy fence compared with what Digger Specialties quotes for its Kingston privacy panel?`
- expected: manuals/certainteed-bufftech/bufftech-catalog-2014.pdf, manuals/industry-standards/Digger-Specialties-Polyvinyl-Fence-Brochure_Racking-Post-Spacing.pdf
- doc rank: 1 · unit support: 0.0 · page support: 0.333 · missing terms: ['Racks up to 10 degrees', 'Rackable', '12” per 8’ Section']
- top hit: manuals/industry-standards/Digger-Specialties-Polyvinyl-Fence-Brochure_Racking-Post-Spacing.pdf p8 score 19.7892

### gq-201 — no_answer
*What footing depth and maximum post spacing does Bufftech specify for a Danbury picket fence in Wind Exposure C?*

- query: `What footing depth and maximum post spacing does Bufftech specify for a Danbury picket fence in Wind Exposure C?`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/certainteed-bufftech/bufftech-installation-guide-afence.pdf p29 score 28.0825

### gq-202 — no_answer
*What is the notched Izod impact strength (ASTM D256), in ft-lb per inch of notch, of the PVC compound used in Illusions vinyl fence profiles?*

- query: `What is the notched Izod impact strength (ASTM D256), in ft-lb per inch of notch, of the PVC compound used in Illusions vinyl fence profiles?`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/barrette-outdoor-living/structural/noa-10-1217.01-vinyl-fencing-legacy.pdf p5 score 32.3138

### gq-203 — no_answer
*How many pounds of gate weight is the Illusions Extra Strong Hinge rated to support?*

- query: `How many pounds of gate weight is the Illusions Extra Strong Hinge rated to support?`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/illusions-vinyl-fence/extra-strong-hinge-brochure.pdf p2 score 24.9159

### gq-204 — no_answer
*What aluminum alloy and wall thickness are the Weatherables aluminum post and rail inserts (stiffeners) made from?*

- query: `What aluminum alloy and wall thickness are the Weatherables aluminum post and rail inserts (stiffeners) made from?`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/weatherables/weatherables-4-rail-fence-installation-2024.pdf p3 score 18.8022

### gq-205 — no_answer
*How much can a Weatherables tongue-and-groove privacy fence panel rack, in inches over an 8 ft span?*

- query: `How much can a Weatherables tongue-and-groove privacy fence panel rack, in inches over an 8 ft span?`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/weatherables/weatherables-3-rail-fence-installation-2024.pdf p6 score 34.9418

### gq-207 — no_answer
*What is the coefficient of linear thermal expansion of Illusions vinyl fence PVC, in inches per inch per degree F?*

- query: `What is the coefficient of linear thermal expansion of Illusions vinyl fence PVC, in inches per inch per degree F?`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/illusions-vinyl-fence/astm-info-flyer.pdf p1 score 14.7514

### gq-208 — no_answer
*How many inches below the frost line must a vinyl fence post footing extend?*

- query: `How many inches below the frost line must a vinyl fence post footing extend?`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/industry-standards/CLFMI-Product-Manual-CSI-Section-32-31-13-Chain-Link-Fence-Gates.pdf p14 score 14.4053

### gq-210 — no_answer
*Which ASCE 7 wind exposure category does the Weatherables 130 mph wind-gust rating apply to?*

- query: `Which ASCE 7 wind exposure category does the Weatherables 130 mph wind-gust rating apply to?`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/industry-standards/CLFMI-Chain-Link-Wind-Load-Guide-Line-Post-Spacing_WLG2445_2023.pdf p11 score 26.9117

### gq-215 — no_answer
*Is there a pet door / dog door insert available for a vinyl privacy fence panel, and what size opening does it need?*

- query: `Is there a pet door / dog door insert available for a vinyl privacy fence panel, and what size opening does it need?`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/weatherables/weatherables-2-rail-gate-installation.pdf p2 score 17.3523

### gq-222 — no_answer
*For how many hours of ASTM B117 salt-spray exposure is the galvanized steel rail reinforcement tested?*

- query: `For how many hours of ASTM B117 salt-spray exposure is the galvanized steel rail reinforcement tested?`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/industry-standards/ASTM-Standards-for-Fence-Materials-and-Products_Compilation-FENCE21.pdf p1 score 21.8316

### gq-223 — no_answer
*What ground snow load, in pounds per square foot, is a 6 ft vinyl privacy fence panel rated to withstand?*

- query: `What ground snow load, in pounds per square foot, is a 6 ft vinyl privacy fence panel rated to withstand?`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/industry-standards/CLFMI-Chain-Link-Wind-Load-Guide-Line-Post-Spacing_WLG2445_2023.pdf p48 score 17.8878

### gq-224 — no_answer
*What maximum allowable rail deflection, in inches, applies to a vinyl fence rail at its rated design wind pressure?*

- query: `What maximum allowable rail deflection, in inches, applies to a vinyl fence rail at its rated design wind pressure?`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/industry-standards/CLFMI-Chain-Link-Wind-Load-Guide-Line-Post-Spacing_WLG2445_2023.pdf p11 score 14.8465

### gq-226 — no_answer
*At what wind speed, in mph, must fence panels be temporarily braced or removed during installation?*

- query: `At what wind speed, in mph, must fence panels be temporarily braced or removed during installation?`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/industry-standards/CLFMI-Chain-Link-Wind-Load-Guide-Line-Post-Spacing_WLG2445_2023.pdf p11 score 15.7916

### gq-227 — no_answer
*What minimum edge distance, in inches, is required for the 3/8" wedge anchors that fasten a Wam Bam surface mount to a concrete slab?*

- query: `What minimum edge distance, in inches, is required for the 3/8" wedge anchors that fasten a Wam Bam surface mount to a concrete slab?`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/wam-bam/vinyl-surface-mount-SB61000-install-guide.pdf p6 score 32.9015

### gq-229 — no_answer
*What ASTM D4216 cell classification does the PVC compound used in Weatherables fence profiles meet?*

- query: `What ASTM D4216 cell classification does the PVC compound used in Weatherables fence profiles meet?`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/illusions-vinyl-fence/installation-instructions-assembled-panel.pdf p4 score 35.8774

### gq-230 — no_answer
*What titanium dioxide UV-inhibitor loading does the Illusions PVC compound use?*

- query: `What titanium dioxide UV-inhibitor loading does the Illusions PVC compound use?`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/freedom-outdoor-living/structural/MiamiDade-NOA-22-0217.05-Barrette-Extruded-PVC-Vinyl-Fence.pdf p11 score 16.9917

### gq-231 — no_answer
*What maximum gate weight, in pounds, is the Bufftech adjustable nylon gate hinge rated to support?*

- query: `What maximum gate weight, in pounds, is the Bufftech adjustable nylon gate hinge rated to support?`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/certainteed-bufftech/bufftech-installation-guide-afence.pdf p3 score 18.5041

### gq-232 — no_answer
*Which Miami-Dade County NOA covers Weatherables vinyl privacy fence, and what is its expiration date?*

- query: `Which Miami-Dade County NOA covers Weatherables vinyl privacy fence, and what is its expiration date?`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/freedom-outdoor-living/structural/Bufftech-MiamiDade-NOA-22-0616.10-Orem.pdf p3 score 13.4753

### gq-005 — conditional_table_lookup
*For a 6 ft high chain link fence in a 130 mph wind zone, what maximum line post spacing does the CLFMI guide give for a 2 3/8 inch Schedule 40 regular grade steel line post?*

- query: `For a 6 ft high chain link fence in a 130 mph wind zone, what maximum line post spacing does the CLFMI guide give for a 2 3/8 inch Schedule 40 regular grade steel line post?`
- expected: manuals/industry-standards/CLFMI-Chain-Link-Wind-Load-Guide-Line-Post-Spacing_WLG2445_2023.pdf
- doc rank: 1 · unit support: 0.4 · page support: 0.4 · missing terms: ['TABLE 4', '130 MPH', '2 3/8']
- top hit: manuals/industry-standards/CLFMI-Chain-Link-Wind-Load-Guide-Line-Post-Spacing_WLG2445_2023.pdf p12 score 39.3293

### gq-009 — table_retrieval
*Show me the maximum post spacing and footing dimensions table from the current CertainTeed / Bufftech extruded PVC vinyl fence NOA.*

- query: `Show me the maximum post spacing and footing dimensions table from the current CertainTeed / Bufftech extruded PVC vinyl fence NOA.`
- expected: manuals/certainteed-bufftech/structural/NOA-23-0314.05-CertainTeed-Chesterfield-Columbia-Imperial-Breezewood-Brookline-current-2023-2029.pdf
- doc rank: None · unit support: 0.0 · page support: 0.0 · missing terms: ['POST SPACING AND FOOTING DIMENSIONS', 'HVHZ: MIAMI-DADE AND BROWARD COUNTIES', 'ASCE 7-10', 'FOOTING TABLE']
- top hit: manuals/freedom-outdoor-living/structural/MiamiDade-NOA-24-0117.05-Barrette-Extruded-PVC-Vinyl-Fence.pdf p17 score 30.4669

### gq-010 — table_retrieval
*I need the whole recommended post spacing table for Barrette privacy railing at 130 mph - both exposure groups, all panel heights.*

- query: `I need the whole recommended post spacing table for Barrette privacy railing at 130 mph - both exposure groups, all panel heights.`
- expected: manuals/freedom-outdoor-living/structural/Barrette-Privacy-Railing-2021-Engineering-Report-PE.pdf
- doc rank: None · unit support: 0.0 · page support: 0.0 · missing terms: ['130MPH WIND', 'RECOMMENDED POST SPACING (O.C.)', 'GOVERNING LOAD', '38.5 psf wind', '46.7 psf wind']
- top hit: manuals/weatherables/weatherables-full-line-catalog-2026.pdf p4 score 26.5928

### gq-012 — current_version
*Is VEKA's PVC privacy fence approval still current, and what earlier acceptance does it supersede?*

- query: `Is VEKA's PVC privacy fence approval still current, and what earlier acceptance does it supersede?`
- expected: manuals/industry-standards/structural/Miami-Dade-NOA_VEKA-Inc_PVC-Privacy-Fence-Panels_24-0729.04.pdf
- doc rank: None · unit support: 0.0 · page support: 0.0 · missing terms: ['24-0729.04', 'revises and renews NOA #21-0308.05', '08/14/2029', '10/03/2024']
- top hit: manuals/industry-standards/CLFMI-Product-Manual-CSI-Section-32-31-13-Chain-Link-Fence-Gates.pdf p5 score 9.2533

### gq-015 — conflict
*Barrette has two live Miami-Dade NOAs for extruded PVC vinyl fencing. Do they call for the same post footing, and if not what does each one specify?*

- query: `Barrette has two live Miami-Dade NOAs for extruded PVC vinyl fencing. Do they call for the same post footing, and if not what does each one specify?`
- expected: manuals/barrette-outdoor-living/structural/noa-24-0117.05-vinyl-fencing.pdf, manuals/freedom-outdoor-living/structural/MiamiDade-NOA-22-0217.05-Barrette-Extruded-PVC-Vinyl-Fence.pdf
- doc rank: 10 · unit support: 0.167 · page support: 0.333 · missing terms: ['22-0217.05', 'Jacek Sluzynski', 'Drawing No. 001', 'PVC VINYL FENCING NOA', 'ASCE 7-10']
- top hit: manuals/weatherables/weatherables-fencing-master-installation-instructions-2024.pdf p4 score 18.4149

### gq-016 — conflict
*The old Barrette Active Yards NOA and the current Barrette vinyl fence NOA give different post footing sizes - what does each say?*

- query: `The old Barrette Active Yards NOA and the current Barrette vinyl fence NOA give different post footing sizes - what does each say?`
- expected: manuals/barrette-outdoor-living/structural/noa-10-1217.01-vinyl-fencing-legacy.pdf, manuals/barrette-outdoor-living/structural/noa-24-0117.05-vinyl-fencing.pdf
- doc rank: 1 · unit support: 0.143 · page support: 0.714 · missing terms: ['16', '36', '96', 'CONCRETE', '42485', 'ASCE 7-10']
- top hit: manuals/barrette-outdoor-living/structural/noa-10-1217.01-vinyl-fencing-legacy.pdf p2 score 17.4697

### gq-017 — comparison
*When the Columbia/Imperial/Chesterfield fence approval moved from CertainTeed to Barrette, did the allowable post spacing change - and did the engineer of record change?*

- query: `When the Columbia/Imperial/Chesterfield fence approval moved from CertainTeed to Barrette, did the allowable post spacing change - and did the engineer of record change?`
- expected: manuals/barrette-outdoor-living/structural/noa-24-0117.05-vinyl-fencing.pdf, manuals/certainteed-bufftech/structural/NOA-23-0314.05-CertainTeed-Chesterfield-Columbia-Imperial-Breezewood-Brookline-current-2023-2029.pdf
- doc rank: 2 · unit support: 0.2 · page support: 0.4 · missing terms: ['Pedro De Figueiredo', 'Robert Nieminen', 'POST SPACING AND FOOTING DIMENSIONS', 'ASCE 7-10']
- top hit: manuals/certainteed-bufftech/structural/NOA-21-0125.07-CertainTeed-extruded-pvc-fencing-2021-2024-superseded.pdf p8 score 14.4403

### gq-018 — comparison
*Compare the Weatherables Augusta privacy panel CAD details for the 6 ft wide and the 8 ft wide panel - what changes?*

- query: `Compare the Weatherables Augusta privacy panel CAD details for the 6 ft wide and the 8 ft wide panel - what changes?`
- expected: manuals/weatherables/structural/weatherables-cad-augusta-8x6-privacy.png, manuals/weatherables/structural/weatherables-cad-augusta-8x8-privacy.png
- doc rank: None · unit support: 0.0 · page support: 0.0 · missing terms: ['72', '96', 'U-Channels', '39.5', '5.5']
- top hit: manuals/certainteed-bufftech/bufftech-installation-guide-afence.pdf p27 score 16.213

### gq-019 — visual_evidence
*Show me the post and footing cross-section from the current Bufftech vinyl fence NOA - what footing diameter, concrete strength and post reinforcement does it detail?*

- query: `Show me the post and footing cross-section from the current Bufftech vinyl fence NOA - what footing diameter, concrete strength and post reinforcement does it detail?`
- expected: manuals/barrette-outdoor-living/structural/noa-24-0117.05-vinyl-fencing.pdf
- doc rank: 3 · unit support: 0.0 · page support: 0.0 · missing terms: ['POST AND FOOTING DESIGN', '3000 PSI CONCRETE', 'EXISTING SOIL', 'FOOTING TABLE']
- top hit: manuals/industry-standards/CLFMI-Product-Manual-CSI-Section-32-31-13-Chain-Link-Fence-Gates.pdf p14 score 20.4524

### gq-021 — source_verification
*How deep does VEKA's approved drawing bury the post for the Tahoe II privacy fence, and what is under the concrete?*

- query: `How deep does VEKA's approved drawing bury the post for the Tahoe II privacy fence, and what is under the concrete?`
- expected: manuals/industry-standards/structural/Miami-Dade-NOA_VEKA-Inc_PVC-Privacy-Fence-Panels_24-0729.04.pdf
- doc rank: 6 · unit support: 0.333 · page support: 0.5 · missing terms: ['17.71', 'DESIGN PRESSURE', 'FASTEST MILE', '3000 PSI MIN']
- top hit: manuals/wam-bam/cambridge-BL19110-install-guide.pdf p16 score 9.8512

