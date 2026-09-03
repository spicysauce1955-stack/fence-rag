# Evaluation report — gold question set against the full corpus

Questions: **78** (41 answerable, 37 no-answer) · k = 10

Configuration: second stage on, R3 duplicate suppression on, R5 page cap off.

Every gold question was runnable.

| Metric | Value | Acceptance |
|---|---|---|
| Document recall@10 | 0.8049 | A3 ≥ 0.80 — PASS |
| Page recall@10 | 0.659 | reported |
| MRR | 0.557 | reported |
| Evidence support (terms in the retrieved unit) | 0.6946 | A3 ≥ 0.70 — FAIL |
| Page evidence support (terms anywhere on a retrieved page) | 0.769 | reported |
| No-answer precision | 0.3243 | A4 ≥ 0.66 — FAIL |
| False-unsupported rate (answerable questions wrongly declared unsupported) | 0.1463 | A4b ≤ 0.20 — PASS |

## By category

| Category | n | doc hits | passed | mean support | failing ids |
|---|---|---|---|---|---|
| comparison | 4 | 4 | 2 | 0.516 | gq-119, gq-120 |
| conditional_table_lookup | 7 | 5 | 4 | 0.61 | gq-113, gq-004, gq-006 |
| conflict | 2 | 1 | 0 | 0.298 | gq-015, gq-016 |
| current_version | 2 | 1 | 1 | 0.6 | gq-011 |
| exact_identifier | 3 | 3 | 3 | 1.0 | — |
| exact_product | 4 | 4 | 2 | 0.417 | gq-102, gq-104 |
| historical_version | 2 | 2 | 2 | 1.0 | — |
| no_answer | 37 | 0 | 12 | None | gq-116, gq-117, gq-118, gq-201, gq-202, gq-203, gq-204, gq-206, gq-207, gq-208, gq-210, gq-215, gq-222, gq-223, gq-224, gq-225, gq-226, gq-227, gq-228, gq-229, gq-230, gq-231, gq-232, gq-233, gq-234 |
| paraphrase | 5 | 3 | 3 | 0.6 | gq-106, gq-108 |
| source_verification | 4 | 4 | 4 | 0.834 | — |
| table_retrieval | 4 | 3 | 3 | 0.9 | gq-009 |
| visual_evidence | 4 | 3 | 3 | 0.938 | gq-019 |

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
| gq-011 | current_version | resolve | None → 1 | 0.2 → 1.0 | FAIL → PASS |

The search rows for these questions are unchanged and still appear in the by-category table and the failure list above; a routed question is not removed from the search denominator.

#### gq-011 — resolved `23-0314.05`

- active: manuals/industry-standards/structural/Miami-Dade-NOA_Barrette-Outdoor-Living_Extruded-PVC-Vinyl-Fencing_24-0117.05.pdf
- basis: no member is marked active; inferred in force from an agreed expiration date 2029-03-13 still ahead of 2026-08-28, and nothing in the chain supersedes it
- basis kind: `inferred_in_force`
- chain: 4 member(s)
- answer support is measured over the active member alone; terms found there 1.0, terms found anywhere in the chain 1.0
- page rank: not reported: this interface answers with documents, not pages
    - superseded  manuals/certainteed-bufftech/structural/NOA-06-1019.01-fence-columbia-imperial-chesterfield.pdf
    - superseded  manuals/certainteed-bufftech/structural/NOA-12-1106.11-extruded-pvc-vinyl-fencing.pdf
    - superseded  manuals/certainteed-bufftech/structural/NOA-23-0314.05-CertainTeed-Chesterfield-Columbia-Imperial-Breezewood-Brookline-current-2023-2029.pdf
    - unknown  manuals/industry-standards/structural/Miami-Dade-NOA_Barrette-Outdoor-Living_Extruded-PVC-Vinyl-Fencing_24-0117.05.pdf

## Phase 7 — experiments this evaluation would justify

Only categories that actually failed appear here. Nothing below is built.

### conditional_table_lookup — 3 of 7 failing

- **Problem**: conditional_table_lookup questions fail lexical retrieval (failing ids: gq-113, gq-004, gq-006).
- **Experiment**: Table-aware structured lookup keyed on conditions (wind speed, exposure, height) resolved against table_cells and facts.
- **Acceptance**: Answers the conditional questions with the correct cell, and returns 'outside documented range' rather than a nearest-neighbour value.

### conflict — 2 of 2 failing

- **Problem**: conflict questions fail lexical retrieval (failing ids: gq-015, gq-016).
- **Experiment**: Conflict surfacing: return every source that states a value for the same condition, with its version status.
- **Acceptance**: Both conflicting sources appear in the top 10 with their statuses.

### no_answer — 25 of 37 failing

- **Problem**: no_answer questions fail lexical retrieval (failing ids: gq-116, gq-117, gq-118, gq-201, gq-202, gq-203, gq-204, gq-206, gq-207, gq-208, gq-210, gq-215, gq-222, gq-223, gq-224, gq-225, gq-226, gq-227, gq-228, gq-229, gq-230, gq-231, gq-232, gq-233, gq-234).
- **Experiment**: Rarest-term coverage plus a calibrated score floor, reported as an explicit unsupported-answer response.
- **Acceptance**: No-answer precision >=0.66 with no loss of answerable recall.

### paraphrase — 2 of 5 failing

- **Problem**: paraphrase questions fail lexical retrieval (failing ids: gq-106, gq-108).
- **Experiment**: Dense semantic retrieval over the pilot corpus.
- **Acceptance**: Improves recall@10 on paraphrase questions by >=0.15 without reducing recall on exact_identifier or conditional_table_lookup.

### table_retrieval — 1 of 4 failing

- **Problem**: table_retrieval questions fail lexical retrieval (failing ids: gq-009).
- **Experiment**: Field-boosted lexical retrieval that ranks table units above prose when the query asks for a table.
- **Acceptance**: Improves table_retrieval recall@10 without reducing overall recall.

### visual_evidence — 1 of 4 failing

- **Problem**: visual_evidence questions fail lexical retrieval (failing ids: gq-019).
- **Experiment**: Visual/page-level retrieval for drawing-heavy documents.
- **Acceptance**: Improves recall@10 on visual_evidence questions without reducing lexical recall elsewhere.

Failing categories with no pre-registered experiment: comparison, current_version, exact_product. These need extraction or annotation review first, not a new retrieval mode.

## Failures in detail

### gq-102 — exact_product
*I need the installation sheet for the Freedom Wellington 6x6 semi-privacy panel. How do I work out the post hole on-center spacing from it?*

- query: `Wellington 6x6 semi privacy panel instructions Freedom Wellington panel install 73013822`
- expected: manuals/freedom-outdoor-living/73013822_Wellington6x6Semi-PrivacyPanel_Instructions.pdf
- doc rank: 1 · unit support: 0.333 · page support: 1.0 · missing terms: ['Coarse Gravel', 'on-center']
- top hit: manuals/freedom-outdoor-living/73013822_Wellington6x6Semi-PrivacyPanel_Instructions.pdf p1 score 27.774

### gq-104 — exact_product
*Where is the Weatherables cross buck gate install guide, and how much shorter than the opening do I cut the rails on a single gate?*

- query: `crossbuck gate installation Weatherables cross buck gate rail cut length vinyl crossbuck gate instructions`
- expected: manuals/weatherables/weatherables-crossbuck-gate-installation.pdf
- doc rank: 7 · unit support: 0.0 · page support: 0.0 · missing terms: ['Cross Buck Fence Gate Installation Guide', '2 1/2”', '93.5”']
- top hit: manuals/weatherables/weatherables-crossbuck-fence-installation-2024.pdf p2 score 19.4942

### gq-106 — paraphrase
*What keeps a vinyl gate from drooping and dragging after a couple of seasons?*

- query: `gate sagging vinyl fence stop gate from dropping reinforce gate post vinyl`
- expected: manuals/barrette-outdoor-living/bufftech-gate-install-guide.pdf, manuals/certainteed-bufftech/bufftech-gate-installation-guide.pdf
- doc rank: None · unit support: 0.0 · page support: 0.0 · missing terms: ['stiffener', 'rebar', 'aluminum post inserts']
- top hit: manuals/freedom-outdoor-living/2024-Freedom-VF-Catalog-01-24_SpecialOrderCatalog.pdf p3 score 8.974

### gq-108 — paraphrase
*All the posts in the delivery look identical. How do I tell which one is meant for a corner?*

- query: `how to identify corner post vinyl fence post markings line end corner which post goes where fence kit`
- expected: manuals/weatherables/weatherables-fencing-master-installation-instructions-2024.pdf
- doc rank: None · unit support: 0.0 · page support: 0.0 · missing terms: ['green dots', 'red dots', 'Line Posts - no marking']
- top hit: manuals/industry-standards/Digger-Specialties-Polyvinyl-Fence-Brochure_Racking-Post-Spacing.pdf p27 score 12.8357

### gq-113 — conditional_table_lookup
*I'm running an 8 ft high Illusions privacy fence with the 75 mph wind kit, so I have to use the 8" x 8" posts. How deep and how wide does the post hole have to be?*

- query: `8x8 post hole depth Illusions wind kit post footing depth vinyl fence how deep 8 inch vinyl post`
- expected: manuals/illusions-vinyl-fence/75mph-wind-kit-installation-instructions.pdf
- doc rank: None · unit support: 0.0 · page support: 0.0 · missing terms: ['42”', '15”', '3000 PSI']
- top hit: manuals/industry-standards/ARCAT-CSI-32-31-23-Vinyl-Fencing-and-Gates-MasterSpec_Superior-Outdoor.docx p1 score 17.9681

### gq-116 — no_answer
*What torque should the gate hinge fasteners be tightened to on a vinyl fence gate, in inch-pounds?*

- query: `gate hinge screw torque spec vinyl fence fastener torque inch pounds how tight to tighten gate hinge bolts`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/weatherables/weatherables-post-mount-instructions-concrete.pdf p1 score 18.2046

### gq-117 — no_answer
*What is the list price per section of an Illusions V300 6 ft privacy fence?*

- query: `Illusions V300 price per section vinyl privacy fence cost per foot Illusions fence price list`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/illusions-vinyl-fence/product-price-catalog-186pg.pdf p14 score 20.452

### gq-118 — no_answer
*What Miami-Dade County NOA number and mph wind rating do Wam Bam vinyl fence panels carry?*

- query: `Wam Bam fence wind rating mph Wam Bam Miami Dade NOA no-dig vinyl fence hurricane approval`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/barrette-outdoor-living/structural/noa-24-0117.05-vinyl-fencing.pdf p7 score 15.8804

### gq-119 — comparison
*Weatherables versus Illusions - what wind speed does each say its vinyl privacy fence can be installed to withstand, and with what height limit?*

- query: `Weatherables vs Illusions wind rating vinyl privacy fence mph rating comparison how many mph is vinyl fence rated for`
- expected: manuals/illusions-vinyl-fence/75mph-wind-kit-installation-instructions.pdf, manuals/weatherables/weatherables-privacy-fencing-specsheet.pdf
- doc rank: 1 · unit support: 0.333 · page support: 0.333 · missing terms: ['130 mph', '6 feet tall and below']
- top hit: manuals/illusions-vinyl-fence/75mph-wind-kit-installation-instructions.pdf p4 score 12.829

### gq-120 — comparison
*How much racking does Bufftech quote for its Chesterfield privacy fence compared with what Digger Specialties quotes for its Kingston privacy panel?*

- query: `how much does vinyl privacy fence rack Chesterfield racking degrees Kingston rackable section 8 foot`
- expected: manuals/certainteed-bufftech/bufftech-catalog-2014.pdf, manuals/industry-standards/Digger-Specialties-Polyvinyl-Fence-Brochure_Racking-Post-Spacing.pdf
- doc rank: 5 · unit support: 0.333 · page support: 0.333 · missing terms: ['Rackable', '12” per 8’ Section']
- top hit: manuals/certainteed-bufftech/bufftech-installation-guide-afence.pdf p46 score 16.3232

### gq-201 — no_answer
*What footing depth and maximum post spacing does Bufftech specify for a Danbury picket fence in Wind Exposure C?*

- query: `Bufftech Danbury footing depth exposure C Danbury max post spacing wind exposure CertainTeed Danbury fence footing dimensions`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/certainteed-bufftech/bufftech-installation-guide-afence.pdf p29 score 38.8762

### gq-202 — no_answer
*What is the notched Izod impact strength (ASTM D256), in ft-lb per inch of notch, of the PVC compound used in Illusions vinyl fence profiles?*

- query: `Illusions vinyl fence Izod impact ft-lb per inch Illusions PVC ASTM D256 impact value EverStrong profile notched izod impact strength`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/barrette-outdoor-living/structural/noa-10-1217.01-vinyl-fencing-legacy.pdf p5 score 31.7045

### gq-203 — no_answer
*How many pounds of gate weight is the Illusions Extra Strong Hinge rated to support?*

- query: `Illusions extra strong hinge weight rating lbs Illusions vinyl gate hinge load capacity pounds IESH hinge supports gates up to`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/illusions-vinyl-fence/extra-strong-hinge-brochure.pdf p2 score 34.4866

### gq-204 — no_answer
*What aluminum alloy and wall thickness are the Weatherables aluminum post and rail inserts (stiffeners) made from?*

- query: `Weatherables aluminum insert alloy wall thickness Weatherables post stiffener 6005-T5 aluminum insert gauge weatherables vinyl fence`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/barrette-outdoor-living/structural/noa-10-1217.02-vinyl-fencing-legacy.pdf p12 score 20.3661

### gq-206 — no_answer
*What is the minimum ambient temperature at which a Bufftech vinyl fence may be installed?*

- query: `minimum temperature to install vinyl fence Bufftech cold weather installation temperature limit how cold is too cold to install vinyl fence`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/wam-bam/murphys-vinyl-fence-laws.pdf p13 score 9.1012

### gq-207 — no_answer
*What is the coefficient of linear thermal expansion of Illusions vinyl fence PVC, in inches per inch per degree F?*

- query: `coefficient of thermal expansion vinyl fence PVC Illusions PVC ASTM D696 thermal expansion value how much does a vinyl fence rail expand per degree`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/illusions-vinyl-fence/astm-info-flyer.pdf p1 score 24.8851

### gq-208 — no_answer
*How many inches below the frost line must a vinyl fence post footing extend?*

- query: `how far below frost line post footing inches below frost line fence post hole depth footing depth below frost line requirement`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/industry-standards/CLFMI-Product-Manual-CSI-Section-32-31-13-Chain-Link-Fence-Gates.pdf p14 score 23.3812

### gq-210 — no_answer
*Which ASCE 7 wind exposure category does the Weatherables 130 mph wind-gust rating apply to?*

- query: `Weatherables 130 mph wind exposure category weatherables vinyl fence ASCE 7 exposure B C D what exposure category is the 130 mph fence rating`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/weatherables/weatherables-full-line-catalog-2026.pdf p4 score 25.9886

### gq-215 — no_answer
*Is there a pet door / dog door insert available for a vinyl privacy fence panel, and what size opening does it need?*

- query: `pet door insert vinyl fence panel dog door for privacy fence panel size vinyl fence dog door kit opening dimensions`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/barrette-outdoor-living/install-picket-closedtop-semiprivacy-panel-kit.pdf p3 score 14.5058

### gq-222 — no_answer
*For how many hours of ASTM B117 salt-spray exposure is the galvanized steel rail reinforcement tested?*

- query: `salt spray ASTM B117 hours galvanized steel rail reinforcement how many hours salt spray test fence steel insert B117 corrosion test duration fence hardware`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/industry-standards/ASTM-Standards-for-Fence-Materials-and-Products_Compilation-FENCE21.pdf p1 score 30.558

### gq-223 — no_answer
*What ground snow load, in pounds per square foot, is a 6 ft vinyl privacy fence panel rated to withstand?*

- query: `vinyl fence panel ground snow load psf snow load rating privacy fence pounds per square foot how much snow can a vinyl fence panel take`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/industry-standards/CLFMI-Chain-Link-Wind-Load-Guide-Line-Post-Spacing_WLG2445_2023.pdf p48 score 17.8727

### gq-224 — no_answer
*What maximum allowable rail deflection, in inches, applies to a vinyl fence rail at its rated design wind pressure?*

- query: `maximum allowable rail deflection inches design wind pressure vinyl fence vinyl fence rail deflection limit under wind load allowable deflection fence rail span inches`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/industry-standards/CLFMI-Chain-Link-Wind-Load-Guide-Line-Post-Spacing_WLG2445_2023.pdf p32 score 19.3158

### gq-225 — no_answer
*What clearance, in inches, must be kept between the two 1/2" rebar pieces and the inside wall of a concrete-filled vinyl post?*

- query: `rebar clearance from post wall separator clip inches how far apart rebar in vinyl fence post rebar cover concrete filled fence post`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/certainteed-bufftech/bufftech-install-semiprivate.pdf p1 score 20.3832

### gq-226 — no_answer
*At what wind speed, in mph, must fence panels be temporarily braced or removed during installation?*

- query: `wind speed mph temporary bracing fence panels during installation brace fence panels high wind while installing maximum wind during fence installation mph`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/certainteed-bufftech/structural/NOA-06-1019.01-fence-columbia-imperial-chesterfield.pdf p3 score 18.3744

### gq-227 — no_answer
*What minimum edge distance, in inches, is required for the 3/8" wedge anchors that fasten a Wam Bam surface mount to a concrete slab?*

- query: `wedge anchor minimum edge distance concrete surface mount how close to slab edge can I set the fence surface mount anchors 3/8 wedge anchor edge distance vinyl fence post mount`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/wam-bam/vinyl-surface-mount-SB61000-install-guide.pdf p6 score 31.4941

### gq-228 — no_answer
*What Sound Transmission Class (STC) rating does a Bufftech Imperial privacy fence achieve under ASTM E90?*

- query: `Bufftech Imperial STC sound transmission loss rating Imperial privacy fence sound transmission class CertainTeed Bufftech ASTM E 90 sound transmission test Imperial`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/certainteed-bufftech/bufftech-catalog-2014.pdf p29 score 47.8546

### gq-229 — no_answer
*What ASTM D4216 cell classification does the PVC compound used in Weatherables fence profiles meet?*

- query: `Weatherables ASTM D4216 cell classification PVC Weatherables vinyl cell class rigid PVC compound TriWest PVC cell classification D1784`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/industry-standards/ASTM-Info-Flyer_Illusions-F964-D4216-Summary.pdf p1 score 36.0823

### gq-230 — no_answer
*What titanium dioxide UV-inhibitor loading does the Illusions PVC compound use?*

- query: `Illusions titanium dioxide UV inhibitor PVC compound Illusions TiO2 content vinyl fence material titanium dioxide UV inhibitor Illusions fence specification`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: china/manuals/showtech/PVC-fence-catalog-2022.pdf p3 score 34.8826

### gq-231 — no_answer
*What maximum gate weight, in pounds, is the Bufftech adjustable nylon gate hinge rated to support?*

- query: `Bufftech adjustable nylon gate hinge gate weight lbs CertainTeed vinyl gate hinge weight capacity pounds how heavy a gate will the nylon hinge support`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/freedom-outdoor-living/2024-Freedom-VF-Catalog-01-24_SpecialOrderCatalog.pdf p106 score 23.3331

### gq-232 — no_answer
*Which Miami-Dade County NOA covers Weatherables vinyl privacy fence, and what is its expiration date?*

- query: `Weatherables Miami-Dade NOA number expiration date Weatherables notice of acceptance hurricane approval Weatherables Florida product approval expiration`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/illusions-vinyl-fence/75mph-wind-kit-noa-miami-dade.pdf p1 score 24.443

### gq-233 — no_answer
*To what depth below grade must the posts of a Showtech ST101 full privacy PVC fence be set?*

- query: `Showtech PVC privacy fence post embedment depth below grade Showtech vinyl fence footing depth post hole how deep to set posts Showtech privacy fence`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/industry-standards/CLFMI-Chain-Link-Wind-Load-Guide-Line-Post-Spacing_WLG2445_2023.pdf p7 score 21.725

### gq-234 — no_answer
*What withdrawal (pull-out) strength, in pounds, does the #8 x 3/4" screw that locks a Bufftech top rail into the post develop?*

- query: `#8 x 3/4 screw pulled out load lbf rail post vinyl fence rail locking screw strength pounds how much load will the rail screw hold before the threads pulled out`
- expected: (nothing — no-answer question)
- doc rank: None · unit support: None · page support: None · missing terms: []
- top hit: manuals/freedom-outdoor-living/structural/Barrette-Privacy-Railing-2021-Engineering-Report-PE.pdf p17 score 30.2774

### gq-004 — conditional_table_lookup
*I'm installing Bufftech Chesterfield fence in Miami-Dade in Exposure C. If I pour a 36 inch deep footing, what is the maximum post spacing the NOA allows?*

- query: `Exposure C 36 inch footing maximum post spacing vinyl fence NOA Bufftech post spacing footing depth table HVHZ max post spacing exposure C`
- expected: manuals/certainteed-bufftech/structural/NOA-23-0314.05-CertainTeed-Chesterfield-Columbia-Imperial-Breezewood-Brookline-current-2023-2029.pdf
- doc rank: None · unit support: 1.0 · page support: 1.0 · missing terms: []
- top hit: manuals/barrette-outdoor-living/bufftech-gate-install-guide.pdf p17 score 31.3999

### gq-006 — conditional_table_lookup
*Barrette full privacy railing, 72 inch high panel, 130 mph wind in Exposure D - what post spacing does the engineering report recommend and what load governs?*

- query: `Barrette privacy railing 130 mph exposure D post spacing 72 inch panel privacy railing post spacing table wind exposure D recommended post spacing 130 mph`
- expected: manuals/freedom-outdoor-living/structural/Barrette-Privacy-Railing-2021-Engineering-Report-PE.pdf
- doc rank: 8 · unit support: 0.2 · page support: 0.4 · missing terms: ['130MPH WIND', 'EXPOSURE D', '1.67FT (20in)', '46.7 psf wind']
- top hit: manuals/industry-standards/CLFMI-Chain-Link-Wind-Load-Guide-Line-Post-Spacing_WLG2445_2023.pdf p4 score 24.3478

### gq-009 — table_retrieval
*Show me the maximum post spacing and footing dimensions table from the current CertainTeed / Bufftech extruded PVC vinyl fence NOA.*

- query: `maximum post spacing and footing dimensions table vinyl fence NOA Table 1 footing depth post spacing wind exposure Bufftech footing table`
- expected: manuals/certainteed-bufftech/structural/NOA-23-0314.05-CertainTeed-Chesterfield-Columbia-Imperial-Breezewood-Brookline-current-2023-2029.pdf
- doc rank: None · unit support: 1.0 · page support: 1.0 · missing terms: []
- top hit: manuals/certainteed-bufftech/bufftech-installation-guide-afence.pdf p29 score 32.0071

### gq-011 — current_version
*Which Miami-Dade NOA is currently in force for the Columbia / Imperial / Chesterfield / Breezewood vinyl fence line, and which NOA did it replace?*

- query: `current NOA Columbia Imperial Chesterfield vinyl fence which NOA replaced 23-0314.05 Barrette Outdoor Living extruded PVC vinyl fencing current NOA`
- expected: manuals/barrette-outdoor-living/structural/noa-24-0117.05-vinyl-fencing.pdf, manuals/certainteed-bufftech/structural/NOA-24-0117.05-Barrette-successor-extruded-pvc-fencing-post-CertainTeed-transfer-2029.pdf, manuals/freedom-outdoor-living/structural/MiamiDade-NOA-24-0117.05-Barrette-Extruded-PVC-Vinyl-Fence.pdf, manuals/industry-standards/structural/Miami-Dade-NOA_Barrette-Outdoor-Living_Extruded-PVC-Vinyl-Fencing_24-0117.05.pdf
- doc rank: None · unit support: 0.2 · page support: 0.2 · missing terms: ['revises NOA #23-0314.05', '04/24/2025', 'Egg Harbor City', 'Robert Nieminen']
- top hit: manuals/certainteed-bufftech/structural/NOA-23-0314.05-CertainTeed-Chesterfield-Columbia-Imperial-Breezewood-Brookline-current-2023-2029.pdf p3 score 19.8822

### gq-015 — conflict
*Barrette has two live Miami-Dade NOAs for extruded PVC vinyl fencing. Do they call for the same post footing, and if not what does each one specify?*

- query: `Barrette vinyl fence NOA footing diameter conflict 18 inch vs 12 inch footing vinyl fence NOA post footing diameter depth Barrette extruded PVC vinyl fencing`
- expected: manuals/barrette-outdoor-living/structural/noa-24-0117.05-vinyl-fencing.pdf, manuals/freedom-outdoor-living/structural/MiamiDade-NOA-22-0217.05-Barrette-Extruded-PVC-Vinyl-Fence.pdf
- doc rank: None · unit support: 0.167 · page support: 0.167 · missing terms: ['22-0217.05', 'Jacek Sluzynski', 'Drawing No. 001', 'PVC VINYL FENCING NOA', 'POST SPACING AND FOOTING DIMENSIONS']
- top hit: manuals/barrette-outdoor-living/structural/noa-24-0117.06-simtek-fence.pdf p8 score 19.7692

### gq-016 — conflict
*The old Barrette Active Yards NOA and the current Barrette vinyl fence NOA give different post footing sizes - what does each say?*

- query: `Barrette Active Yards footing diameter 16 inch footing 36 inch deep vinyl fence NOA old vs new Barrette vinyl fence footing size`
- expected: manuals/barrette-outdoor-living/structural/noa-10-1217.01-vinyl-fencing-legacy.pdf, manuals/barrette-outdoor-living/structural/noa-24-0117.05-vinyl-fencing.pdf
- doc rank: 6 · unit support: 0.429 · page support: 0.571 · missing terms: ['CONCRETE', '42485', 'POST SPACING AND FOOTING DIMENSIONS', 'ASCE 7-10']
- top hit: manuals/industry-standards/ARCAT-CSI-32-31-23-Vinyl-Fencing-and-Gates-MasterSpec_Superior-Outdoor.docx p1 score 24.5487

### gq-019 — visual_evidence
*Show me the post and footing cross-section from the current Bufftech vinyl fence NOA - what footing diameter, concrete strength and post reinforcement does it detail?*

- query: `vinyl fence post footing cross section 12 inch diameter 3000 psi aluminum post reinforcement footing detail Bufftech NOA post and footing design detail vinyl fence`
- expected: manuals/certainteed-bufftech/structural/NOA-23-0314.05-CertainTeed-Chesterfield-Columbia-Imperial-Breezewood-Brookline-current-2023-2029.pdf
- doc rank: None · unit support: 1.0 · page support: 1.0 · missing terms: []
- top hit: manuals/certainteed-bufftech/structural/NOA-06-1019.01-fence-columbia-imperial-chesterfield.pdf p8 score 20.5615

