# Structured technical facts (Phase 6)

Facts are *derived from* canonical elements and never replace them. Every row
carries the element, page and document it came from, the original wording, the
normalised value beside it, and a review status. A value read from OCR text on a
page whose mean word confidence is below 80 is created as `flagged`, not
`extracted`: a misread digit in a footing depth is a structural error, not a typo.

| Measure | Value |
|---|---|
| facts | 1714 |
| with conditions attached | 176 |
| facts without a source element | 0 |

## By review status

| Status | Count |
|---|---|
| extracted | 1448 |
| flagged | 266 |

## By type

| Fact type | Count | Flagged for review | OCR-derived |
|---|---|---|---|
| reinforcement | 656 | 91 | 210 |
| approval_id | 271 | 78 | 265 |
| wind_speed_mph | 269 | 55 | 160 |
| footing_depth_in | 149 | 4 | 24 |
| depth_below_grade_in | 100 | 0 | 16 |
| effective_date | 84 | 20 | 84 |
| expiration_date | 75 | 10 | 75 |
| stock_length_in | 62 | 0 | 0 |
| footing_diameter_in | 25 | 5 | 11 |
| exposure_category | 15 | 0 | 0 |
| racking_degrees | 5 | 2 | 5 |
| post_spacing_in | 3 | 1 | 2 |

## Where the conditions came from

Obligation 15: a row states whether its conditions came from the source.
`stated` means the document gave them -- including giving none, which makes the
row an explicit fallback. `assumed` means we inferred them. `unexamined` means
nobody looked: the regex matched a number and never asked what scoped it. That
third value is internal and publishes as `assumed`; it exists so the store does
not assert an inference it never made.

| condition basis | Count | Means |
|---|---|---|
| unexamined | 1538 | no conditions, and nothing looked for any |
| assumed | 117 | captured by regex proximity, not asserted by the document |
| stated | 59 | the document said so |

## Second units, where a source states one

Obligation 4: where a source states two units and they disagree, publish both.
**3** of 1714 facts carry an alternate lexeme in `value_alternates`,
of which **0 disagree** with the primary value.

**Read that second number carefully.** The schema can now represent a disagreeing
second unit -- that is the gap obligation 4 declared, and it is closed. But the
corpus's disagreeing statements are not reaching it. Measured: 64 real disagreeing
statements across 201 occurrences in 15 unique-content documents, and **none of
them is reachable by this extractor**. Two causes, the second much larger:

1. An adjacency defect worth 3 statements. The parenthetical sits between the
   number and the keyword a pattern needs -- `6 inches (152 mm) below grade`
   never matches `depth_below_grade_in`.
2. Missing fact types, worth the other 61. Every dual-unit disagreement in this
   corpus is about *product geometry* -- fence height, mesh opening, picket gap,
   member section, stock length -- and this extractor covers footing, spacing,
   wind and approval metadata. The two populations barely intersect: of the
   elements carrying a paired dual-unit statement, only 6 produce any fact at all.

Closing obligation 4's disagreement clause is a fact-type expansion, not a
dual-unit-parsing problem. See `docs/state-and-gaps.md` G34.

## Language, and the fact that none of it was measured

Obligation 10 requires `lang` and forbids normalising it. Script is measured by
Unicode range; **language is not.** Telling English from another Latin-script
language is not something this pipeline can do, and tesseract here has only
`eng` installed. So every tag below is `assumed` or `unknown`, and `measured`
stays reserved for a real language identifier that does not exist yet.

Language is **not** derived from `corpus_track`. That axis is a standards regime
-- GB rather than ASTM -- not a language, and the China-track documents here are
English-language export catalogues. Measured: zero CJK-bearing elements corpus-wide.

| lang | basis | Elements |
|---|---|---|
| en | assumed | 58033 |
| und | unknown | 22453 |
| es | assumed | 674 |
| fr | assumed | 634 |

## Sample, with provenance

| Type | Original | Normalised | Conditions | Status | Source | Page |
|---|---|---|---|---|---|---|
| approval_id | `09-0826.07` | None | `{"wind_speed_mph": 75.0}` | extracted | `75mph-wind-kit-installation-instructions` | 4 |
| approval_id | `24-0117.06` | None | `{"wind_speed_mph": 75.0}` | flagged | `noa-24-0117.06-simtek-fence.pdf` | 7 |
| approval_id | `24-0117.06` | None | `{"wind_speed_mph": 75.0}` | flagged | `noa-24-0117.06-simtek-fence.pdf` | 8 |
| approval_id | `24-0117.05` | None | `{"wind_speed_mph": 75.0, "hvhz": true}` | extracted | `noa-24-0117.05-vinyl-fencing.pdf` | 7 |
| approval_id | `20-0302.01` | None | `{"wind_speed_mph": 75.0}` | flagged | `NOA-22-0616.10-CertainTeed-SimTek-molded` | 8 |
| approval_id | `20-0302.01` | None | `{"wind_speed_mph": 75.0}` | flagged | `Bufftech-MiamiDade-NOA-22-0616.10-Orem.p` | 8 |
| approval_id | `20-0303.62` | None | `{"wind_speed_mph": 75.0, "hvhz": true}` | flagged | `NOA-23-0314.05-CertainTeed-Chesterfield-` | 7 |
| approval_id | `24-0117.05` | None | `{"wind_speed_mph": 75.0, "hvhz": true}` | extracted | `NOA-24-0117.05-Barrette-successor-extrud` | 7 |
| approval_id | `24-0117.05` | None | `{"wind_speed_mph": 75.0, "hvhz": true}` | extracted | `MiamiDade-NOA-24-0117.05-Barrette-Extrud` | 7 |
| approval_id | `09-0826.07` | None | `{"wind_speed_mph": 75.0}` | flagged | `75mph-wind-kit-noa-miami-dade.pdf` | 4 |
| approval_id | `09-0826.07` | None | `{"wind_speed_mph": 75.0}` | flagged | `noa-14-1209.01-PE-stamped-structural-dra` | 4 |
| approval_id | `24-0117.05` | None | `{"wind_speed_mph": 75.0, "hvhz": true}` | extracted | `Miami-Dade-NOA_Barrette-Outdoor-Living_E` | 7 |
| footing_depth_in | `Depth | Max. Post Spacing
B
30"` | 30.0 in | `{"hvhz": true}` | extracted | `bufftech-gate-install-guide.pdf` | 31 |
| footing_depth_in | `Depth | Max. Post Spacing
B
30"` | 30.0 in | `{"hvhz": true}` | extracted | `bufftech-installation-guide-40-40-70743.` | 25 |
| footing_depth_in | `Depth | Max. Post Spacing
B
30"` | 30.0 in | `{"hvhz": true}` | extracted | `bufftech-gate-installation-guide.pdf` | 31 |
| footing_depth_in | `depth of holes is
30"` | 30.0 in | `{"fence_height_ft": 8.0}` | extracted | `weatherables-fencing-master-installation` | 3 |
| footing_depth_in | `Depth Diameter B - 24"` | 24.0 in | `{"wind_speed_mph": 75.0}` | flagged | `noa-24-0117.06-simtek-fence.pdf` | 8 |
| footing_depth_in | `DEPTH SPACING -__B : 30"` | 30.0 in | `{"hvhz": true}` | flagged | `NOA-12-1106.11-extruded-pvc-vinyl-fencin` | 11 |
| footing_depth_in | `30" deep` | 30.0 in | `{"hvhz": true}` | extracted | `bufftech-installation-guide-afence.pdf` | 18 |
| footing_depth_in | `30" deep` | 30.0 in | `{"hvhz": true}` | extracted | `bufftech-installation-guide-afence.pdf` | 20 |
| footing_depth_in | `Depth Spacing A B 30"` | 30.0 in | `{"hvhz": true}` | extracted | `bufftech-installation-guide-afence.pdf` | 29 |
| footing_depth_in | `12" EMBEDMENT` | 12.0 in | `{"hvhz": true}` | extracted | `bufftech-installation-guide-afence.pdf` | 29 |
| post_spacing_in | `68in o.c` | 68.0 in | `{"fence_height_ft": 3.5}` | extracted | `Barrette-Privacy-Railing-2021-Engineerin` | 17 |
| racking_degrees | `Racks | up to 5 degrees` | 5.0 deg | `{"fence_height_ft": 4.0}` | flagged | `bufftech-catalog-2014.pdf` | 28 |
| racking_degrees | `Racks up | 10 degrees` | 10.0 deg | `{"fence_height_ft": 4.0}` | flagged | `bufftech-catalog-2014.pdf` | 28 |

## What this layer is not

The extractor is a documented set of regular expressions (`extractor='regex-v1'`),
not a model. It finds values that are stated in a sentence or a recovered table
cell. It does **not** read values out of scanned drawing tables, because those
cells were never recovered (see the corpus audit). Any fact whose conditions
matter for a structural decision should be confirmed against the page image
before use; that is what the review status is for.
