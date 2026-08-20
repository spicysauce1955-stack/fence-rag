# Pilot selection

Ten documents, 313 pages, chosen to exercise every extraction path in
the corpus. Selection is explicit rather than sampled so the Phase 1 gate is
reproducible and each choice carries a stated reason.

| Class | Document | Pages | Scanned | Why this one |
|---|---|---|---|---|
| text_layer_manual | `manuals/wam-bam/cambridge-BL19110-install-guide.pdf` | 26 | no | Clean InDesign text layer with step numbering and callouts; the easy case that must be perfect before anything harder counts. |
| text_layer_manual | `manuals/barrette-outdoor-living/bufftech-simtek-fence-install-guide.pdf` | 50 | no | Multi-section installation guide with tables and exploded views; exercises heading hierarchy across many pages. |
| scanned_structural | `manuals/certainteed-bufftech/structural/NOA-23-0314.05-CertainTeed-Chesterfield-Columbia-Imperial-Breezewood-Brookline-current-2023-2029.pdf` | 17 | yes | The current CertainTeed Miami-Dade NOA. Scanned, PE-sealed, carries the wind/exposure tables the system exists to answer from. |
| scanned_structural | `manuals/certainteed-bufftech/structural/NOA-21-0125.07-CertainTeed-extruded-pvc-fencing-2021-2024-superseded.pdf` | 16 | yes | The superseded predecessor of the above. Proves the store keeps historical approvals as distinct records (prohibition 5). |
| scanned_structural | `manuals/illusions-vinyl-fence/structural/noa-14-1209.01-PE-stamped-structural-drawings-dixon-engineering.pdf` | 20 | yes | Twenty pages of PE-stamped structural drawings with little prose; the hardest OCR + drawing-label case in the corpus. |
| mixed_catalog | `manuals/freedom-outdoor-living/2024-Freedom-VF-Catalog-01-24_SpecialOrderCatalog.pdf` | 112 | no | Marketing photography and dimension tables inside one document — the case that makes whole-document keep/drop wrong (prohibition 3). |
| mixed_catalog | `manuals/weatherables/weatherables-fencing-brochure.pdf` | 22 | no | Second mixed catalog from a different producer toolchain; guards against tuning extraction to one vendor's PDF generator. |
| table_heavy_spec | `manuals/industry-standards/CLFMI-Chain-Link-Wind-Load-Guide-Line-Post-Spacing_WLG2445_2023.pdf` | 49 | no | Dense conditional wind-load / post-spacing tables. The table fidelity gate: cells must survive as cells, not as flowed text. |
| cad_image | `manuals/weatherables/structural/weatherables-cad-augusta-8x6-privacy.png` | 1 | yes | Bare CAD raster with dimension callouts and no container format; proves drawing labels are captured with bboxes. |
| docx_spec | `manuals/industry-standards/ARCAT-CSI-32-31-23-Vinyl-Fencing-and-Gates-MasterSpec_Superior-Outdoor.docx` |  | no | The only DOCX. CSI MasterSpec hierarchy (PART/2.1/A/1) is real section structure that must become a heading path. |

## Coverage against the guide's Phase 1 requirement

| Required | Provided |
|---|---|
| two text-layer manuals | Wam Bam Cambridge, Bufftech/SimTek install guide |
| three scanned structural/NOA documents | CertainTeed NOA 23-0314.05 (current), NOA 21-0125.07 (superseded), Illusions NOA 14-1209.01 (PE drawings) |
| two mixed catalogs | Freedom 2024 special-order catalog, Weatherables brochure |
| one table-heavy specification | CLFMI wind-load / line-post-spacing guide |
| one CAD image | Weatherables Augusta 8x6 privacy CAD PNG |
| the DOCX specification | ARCAT CSI 32 31 23 MasterSpec |

## Documented exemptions

Two documents are exempt from the section-hierarchy assertion, because the
source genuinely has no prose hierarchy to preserve:

| Document | Reason |
|---|---|
| `manuals/weatherables/structural/weatherables-cad-augusta-8x6-privacy.png` | single CAD raster; dimension callouts are labels, not sections |
| `manuals/illusions-vinyl-fence/structural/noa-14-1209.01-PE-stamped-structural-drawings-dixon-engineering.pdf` | drawing sheets carry title blocks rather than a prose heading hierarchy |

The DOCX is exempt from the page-image and bounding-box assertions: a DOCX has
no page geometry and no document renderer is available in this environment. The
limitation is recorded as a `no_page_image_for_docx` quality issue rather than
passed over silently, and its section hierarchy and table cells are preserved.
