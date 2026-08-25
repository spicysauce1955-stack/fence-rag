# Structured technical facts (Phase 6)

Facts are *derived from* canonical elements and never replace them. Every row
carries the element, page and document it came from, the original wording, the
normalised value beside it, and a review status. A value read from OCR text on a
page whose mean word confidence is below 80 is created as `flagged`, not
`extracted`: a misread digit in a footing depth is a structural error, not a typo.

| Measure | Value |
|---|---|
| facts | 1652 |
| with conditions attached | 117 |
| facts without a source element | 0 |

## By review status

| Status | Count |
|---|---|
| extracted | 1386 |
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
| footing_diameter_in | 25 | 5 | 11 |
| exposure_category | 15 | 0 | 0 |
| racking_degrees | 5 | 2 | 5 |
| post_spacing_in | 3 | 1 | 2 |

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
