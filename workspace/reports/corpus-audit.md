# Corpus audit

Measured from `workspace/catalog/corpus-manifest.jsonl` (144 manifest rows, 144 files present on disk).

## Counts, and how they compare to `rag-pipeline-plan.md`

| Quantity | Measured | Plan claimed | Verdict |
|---|---|---|---|
| PDFs | 137 | 137 | matches |
| PDFs with a text layer | 115 | 115 | matches |
| scanned / image-only PDFs | 22 | 22 | matches |
| CAD images (PNG) | 6 | 6 | matches |
| DOCX specifications | 1 | 1 | matches |
| total PDF pages | 2140 | not stated | newly measured |
| pages inside scanned PDFs | 358 | not stated | newly measured |

Text-layer detection thresholds: a page counts as having text at 100 characters; a document is suspected scanned below 60 characters per page on average.

## What the plan's counts do not capture

### Text layers that decode to mojibake

Six documents carry a text layer that passes any length-based test but decodes
to unreadable glyph soup because the embedded font has no usable ToUnicode map
(`bm|o|_;]uom7` for `into the ground`). A character-count heuristic marks these
as clean text-layer PDFs. They are detected separately, per page, by control-
character ratio (> 0.005) combined with the share of pure-ASCII
word tokens (< 0.85), and those pages are routed to OCR with
a `mojibake_text_layer` quality issue recorded. Affected files:

- `manuals/wam-bam/steady-freddy-VF16100-install-guide.pdf`
- `manuals/wam-bam/nervous-nelly-VF15100-install-guide.pdf`
- `manuals/wam-bam/nervous-nelly-VG25100-gate-install-guide.pdf`
- `manuals/wam-bam/plain-jane-VG24200-gate-install-guide.pdf`
- `manuals/wam-bam/privacy-gate-6ftx6ft-adjustable-install-guide.pdf`
- `manuals/certainteed-bufftech/bufftech-catalog-2014.pdf` (spec-table cells only)

### Partially scanned documents (31)

These have a text layer on some pages and none on others, so they need a
per-page decision rather than a per-document one. Extraction records the method
used for each page in `pages.extraction_method`.

### Byte-identical duplicates (14 groups)

The same file is filed under several manufacturer directories. These are linked
with a `same_content_as` relation and **never** deduplicated (prohibition 1);
retrieval may return any copy and evaluation treats them as equivalent.

| copies | sha256 | paths |
|---|---|---|
| 4 | 2f446717ee | manuals/barrette-outdoor-living/structural/noa-24-0117.05-vinyl-fencing.pdf<br>manuals/certainteed-bufftech/structural/NOA-24-0117.05-Barrette-successor-extruded-pvc-fencing-post-CertainTeed-transfer-2029.pdf<br>manuals/freedom-outdoor-living/structural/MiamiDade-NOA-24-0117.05-Barrette-Extruded-PVC-Vinyl-Fence.pdf<br>manuals/industry-standards/structural/Miami-Dade-NOA_Barrette-Outdoor-Living_Extruded-PVC-Vinyl-Fencing_24-0117.05.pdf |
| 2 | b39ab4a32b | manuals/barrette-outdoor-living/bufftech-gate-install-guide.pdf<br>manuals/certainteed-bufftech/bufftech-gate-installation-guide.pdf |
| 2 | 71c42837fd | manuals/barrette-outdoor-living/bufftech-simtek-fence-install-guide.pdf<br>manuals/certainteed-bufftech/bufftech-fence-installation-guide-2024.pdf |
| 2 | a4ba7699a8 | manuals/barrette-outdoor-living/install-5x5-post-surface-mount.pdf<br>manuals/freedom-outdoor-living/5x5PostSurfaceMount_Install.pdf |
| 2 | 80382740de | manuals/barrette-outdoor-living/install-cameron-privacy-vinyl-panel.pdf<br>manuals/freedom-outdoor-living/CameronPrivacyVinylFencePanel_Instructions.pdf |
| 2 | b157c5d91a | manuals/barrette-outdoor-living/install-horizontal-privacy-gate-kit.pdf<br>manuals/freedom-outdoor-living/HorizontalPrivacyGate_Instructions.pdf |
| 2 | 9186284efd | manuals/barrette-outdoor-living/install-post-rail-gates.pdf<br>manuals/freedom-outdoor-living/VinylPostAndRailGates_Instructions.pdf |
| 2 | 23b7721c30 | manuals/barrette-outdoor-living/install-privacy-gate.pdf<br>manuals/freedom-outdoor-living/VF-Privacy-Gate-Install_HingesLatchDropRod.pdf |
| 2 | 0cba6c8bc5 | manuals/barrette-outdoor-living/install-racking-gate.pdf<br>manuals/freedom-outdoor-living/BARRETTE-WEB_RackingGate_Install.pdf |
| 2 | 1d6217350a | manuals/barrette-outdoor-living/install-transition-brackets.pdf<br>manuals/freedom-outdoor-living/TransitionBrackets_Install_SlopeAccommodation.pdf |
| 2 | b5a8856501 | manuals/barrette-outdoor-living/install-transition-panel-kit.pdf<br>manuals/freedom-outdoor-living/VFTransitionPanelKit_SlopeAccommodation.pdf |
| 2 | 1c487c731b | manuals/certainteed-bufftech/structural/NOA-22-0616.10-CertainTeed-SimTek-molded-fence-2022-2028-superseded.pdf<br>manuals/freedom-outdoor-living/structural/Bufftech-MiamiDade-NOA-22-0616.10-Orem.pdf |
| 2 | c4eb900caf | manuals/illusions-vinyl-fence/75mph-wind-kit-noa-miami-dade.pdf<br>manuals/illusions-vinyl-fence/structural/noa-14-1209.01-PE-stamped-structural-drawings-dixon-engineering.pdf |
| 2 | 89369e12c4 | manuals/illusions-vinyl-fence/astm-info-flyer.pdf<br>manuals/industry-standards/ASTM-Info-Flyer_Illusions-F964-D4216-Summary.pdf |

## Distribution

### By manufacturer directory

| Manufacturer | Files |
|---|---|
| Weatherables | 24 |
| Freedom Outdoor Living | 19 |
| Wam Bam Fence Co | 17 |
| Illusions Fence | 16 |
| Barrette Outdoor Living | 15 |
| CertainTeed | 12 |
| Freedom Outdoor Living / Barrette Outdoor Living | 10 |
| Industry Standards / Cross-Manufacturer | 10 |
| Catalyst Fence Solutions | 6 |
| Barrette Outdoor Living, Inc. | 4 |
| Zhejiang Showtech Outdoor Products Co., Ltd. | 3 |
| Barrette Outdoor Living (Bufftech) | 2 |
| CertainTeed / Barrette Outdoor Living | 2 |
| Cross-manufacturer / installation-technical | 1 |
| Barrette Outdoor Living (Bufftech / SimTek) | 1 |
| Catalyst Fence Solutions (Barrette Outdoor Living / Bufftech successor brand) | 1 |
| TriWest Fencing (dealer/distributor, not Weatherables) - included for reference only, not used as a data source for this Weatherables dataset | 1 |

### By document type

| doc_type | Files |
|---|---|
| installation_manual | 69 |
| cut_sheet | 16 |
| unspecified | 12 |
| spec_sheet | 11 |
| cad_detail | 8 |
| warranty | 6 |
| hvhz_noa | 6 |
| engineering_approval | 4 |
| real_miami_dade_noa_vinyl_fence | 2 |
| Installation diagram guide (image-only PDF, no dimensions/text) | 1 |
| csi_spec | 1 |
| csi_masterspec_vinyl | 1 |
| astm_compliance_summary_flyer | 1 |
| astm_standards_compilation | 1 |
| association_technical_bulletin | 1 |
| csi_masterspec_template | 1 |
| manufacturer_brochure_with_engineering_data | 1 |
| industry_spec_reference_guide | 1 |
| structural_engineering_worked_example | 1 |

### By version status

| version_status | Files |
|---|---|
| active | 6 |
| superseded | 6 |
| unknown | 132 |

Version status is derived conservatively: `active` or `superseded` only when the
filename or curated title says so, otherwise `unknown`. Ingestion then upgrades
it from evidence inside the documents — an NOA that names a previous approval
marks that approval superseded.

## Scanned tables: what could and could not be recovered

The wind-load and footing tables inside the NOA packages are line-work in a scanned engineering drawing, not text. pdfplumber cannot see them at all (no text layer), so a conservative OCR word-grid reconstructor was implemented: words cluster into rows, recurring x-positions become columns, and the candidate grid is rejected unless it has at least three columns, three rows, 30% numeric cells, few single-character cells, and adequate word confidence.

Measured yield across the full corpus: **9 grids accepted** in 6 document(s), and **73 pages** where a table is named but no grid could be recovered.

| Document | Page | Grid |
|---|---|---|
| `bufftech-catalog-2014.pdf` | 28 | 29x8 |
| `bufftech-installation-guide-afence.pdf` | 31 | 13x3 |
| `bufftech-vinyl-catalog-standardfencing.pdf` | 4 | 9x3 |
| `bufftech-vinyl-catalog-standardfencing.pdf` | 19 | 20x8 |
| `bufftech-vinyl-catalog-standardfencing.pdf` | 20 | 32x11 |
| `NOA-12-1106.11-extruded-pvc-vinyl-fencing.pdf` | 2 | 4x3 |
| `CLFMI-Chain-Link-Wind-Load-Guide-Line-Post-Spacing_W` | 31 | 35x9 |
| `CLFMI-Chain-Link-Wind-Load-Guide-Line-Post-Spacing_W` | 39 | 11x12 |
| `nervous-nelly-VF15100-install-guide.pdf` | 10 | 8x7 |

The split matters more than the total. What it recovers are scanned **catalog and specification** tables: picket size and spacing grids, rail and steel-reinforcement columns, ASCE terrain exposure constants. What it does not recover is the material this corpus exists for. Only 1 of these grids sits in a structural document, and none is a wind/exposure/footing table off an NOA drawing sheet: tesseract reads those pages at roughly 50% mean word confidence, and every candidate grid there was rejected by the gates that stop it inventing values. Rendering at 400 and 500 dpi instead of 300 did not improve confidence.

The consequence is stated rather than hidden. For those pages the preserved page image plus the OCR text is the faithful representation, a `table_not_reconstructed` quality issue is recorded, and the evaluation report names the Phase 7 experiment — visual or model-based page reading — that this failure would justify.

## Highest-value material

The 22 scanned PDFs carry 358 pages and include nearly every
Miami-Dade NOA package: the PE-sealed wind-load and footing tables this system
exists to answer from. They are also the hardest to extract, which is why three
of them are in the pilot.

## Encrypted documents

| File | Encryption |
|---|---|
| manuals/illusions-vinyl-fence/extra-strong-hinge-brochure.pdf | yes (print:yes copy:no change:no addNotes:no algorithm:AES) |

Encrypted documents are extracted where poppler permits it; a `encrypted_pdf` quality issue is recorded so partial extraction is never mistaken for complete extraction.
