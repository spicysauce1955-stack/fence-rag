# Corpus coverage report

| Measure | Value |
|---|---|
| documents in store | 144 |
| ingestable files in manifest | 144 |
| not ingested | 0 |
| versions | 144 |
| pages | 2147 |
| elements | 81794 |
| tables / cells | 603 / 18472 |
| assets (page + region images) | 9624 |
| relations | 102 |
| retrieval units | 10886 |
| facts | 1652 |
| quality issues | 374 |

Every ingestable file in the manifest is present in the store.

Every document stored exactly as many pages as its source has.

## Quality issues by kind

| Kind | Count |
|---|---|
| low_ocr_confidence | 172 |
| mojibake_text_layer | 81 |
| table_not_reconstructed | 73 |
| ocr_supplement_failed | 34 |
| empty_page_after_ocr | 9 |
| empty_page | 3 |
| encrypted_pdf | 1 |
| no_page_image_for_docx | 1 |

| Severity | Count |
|---|---|
| warning | 339 |
| info | 35 |

## Per document

| Document | Pages | Source pages | Match | Elements | Tables | Cells | Assets | OCR pages | Mean OCR conf | Issues |
|---|---|---|---|---|---|---|---|---|---|---|
| `unifloor-composite-fencing-installation-guide.pdf` | 4 | 4 | yes | 76 | 0 | 0 | 78 | 1 | 90.1 | 3 |
| `PVC-fence-catalog-2022.pdf` | 14 | 14 | yes | 967 | 0 | 0 | 22 | 14 | 68.3 | 7 |
| `PVC-fence-catalog-2024.pdf` | 24 | 24 | yes | 1582 | 0 | 0 | 35 | 24 | 57.2 | 19 |
| `Showtech-WPC-fence-decking-catalog-2024.pdf` | 10 | 10 | yes | 258 | 0 | 0 | 15 | 10 | 76.4 | 2 |
| `bufftech-fence-limited-lifetime-warranty.pdf` | 2 | 2 | yes | 65 | 0 | 0 | 3 | 0 |  | 0 |
| `bufftech-gate-install-guide.pdf` | 56 | 56 | yes | 2326 | 16 | 377 | 148 | 3 | 93.8 | 0 |
| `bufftech-simtek-fence-install-guide.pdf` | 50 | 50 | yes | 1533 | 18 | 206 | 147 | 1 | 96.0 | 0 |
| `catalyst-capecod-sku-sheet.pdf` | 3 | 3 | yes | 71 | 4 | 78 | 23 | 0 |  | 0 |
| `catalyst-fence-accents-hardware-sku-sheet.pdf` | 23 | 23 | yes | 277 | 30 | 1037 | 132 | 0 |  | 0 |
| `catalyst-install-picket-closedtop-semiprivacy-kit.pd` | 19 | 19 | yes | 422 | 1 | 11 | 76 | 3 | 94.8 | 0 |
| `catalyst-vinyl-molded-composite-fence-warranty.pdf` | 2 | 2 | yes | 68 | 0 | 0 | 5 | 0 |  | 0 |
| `catalyst-vinyl-privacy-picket-gates.pdf` | 19 | 19 | yes | 879 | 3 | 21 | 97 | 0 |  | 0 |
| `install-5x5-post-surface-mount.pdf` | 13 | 13 | yes | 251 | 5 | 40 | 48 | 0 |  | 0 |
| `install-cameron-privacy-vinyl-panel.pdf` | 10 | 10 | yes | 240 | 0 | 0 | 29 | 0 |  | 0 |
| `install-horizontal-privacy-fence-panel.pdf` | 36 | 36 | yes | 972 | 4 | 44 | 138 | 2 | 65.9 | 2 |
| `install-horizontal-privacy-gate-kit.pdf` | 19 | 19 | yes | 398 | 2 | 14 | 51 | 0 |  | 0 |
| `install-picket-closedtop-semiprivacy-panel-kit.pdf` | 16 | 16 | yes | 307 | 0 | 0 | 43 | 0 |  | 0 |
| `install-post-rail-gates.pdf` | 16 | 16 | yes | 263 | 6 | 105 | 59 | 2 | 96.0 | 2 |
| `install-post-rail-ranch-rail.pdf` | 16 | 16 | yes | 350 | 3 | 30 | 63 | 1 | 67.2 | 1 |
| `install-privacy-gate.pdf` | 19 | 19 | yes | 656 | 6 | 49 | 64 | 0 |  | 0 |
| `install-privacy-picket-gates.pdf` | 20 | 20 | yes | 766 | 4 | 21 | 84 | 1 | 96.0 | 0 |
| `install-racking-gate.pdf` | 25 | 25 | yes | 718 | 4 | 23 | 136 | 0 |  | 0 |
| `install-semiprivacy-enclosure.pdf` | 16 | 16 | yes | 550 | 16 | 135 | 65 | 0 |  | 0 |
| `install-transition-brackets.pdf` | 3 | 3 | yes | 60 | 0 | 0 | 9 | 0 |  | 0 |
| `install-transition-panel-kit.pdf` | 3 | 3 | yes | 184 | 6 | 36 | 27 | 0 |  | 0 |
| `owners-manual-vinyl-fence-v3.pdf` | 8 | 8 | yes | 190 | 0 | 0 | 58 | 0 |  | 0 |
| `catalyst-madison-horizontal-privacy-sku-sheet.pdf` | 8 | 8 | yes | 202 | 14 | 399 | 59 | 0 |  | 0 |
| `catalyst-vinyl-post-rail-ranch-rail-install-current.` | 19 | 19 | yes | 400 | 3 | 30 | 78 | 2 | 79.4 | 1 |
| `noa-10-1217.01-vinyl-fencing-legacy.pdf` | 14 | 14 | yes | 904 | 0 | 0 | 14 | 14 | 67.7 | 11 |
| `noa-10-1217.02-vinyl-fencing-legacy.pdf` | 13 | 13 | yes | 956 | 0 | 0 | 14 | 13 | 66.8 | 11 |
| `noa-24-0117.05-vinyl-fencing.pdf` | 17 | 17 | yes | 1058 | 0 | 0 | 19 | 17 | 74.6 | 18 |
| `noa-24-0117.06-simtek-fence.pdf` | 8 | 8 | yes | 533 | 0 | 0 | 10 | 8 | 85.7 | 2 |
| `warranty-vinyl-fence-30yr.pdf` | 1 | 1 | yes | 21 | 0 | 0 | 1 | 0 |  | 0 |
| `bufftech-catalog-2014.pdf` | 30 | 30 | yes | 1279 | 2 | 207 | 423 | 9 | 86.3 | 8 |
| `bufftech-catalog-brochure-2009.pdf` | 28 | 28 | yes | 857 | 1 | 44 | 221 | 1 | 28.0 | 2 |
| `bufftech-fence-installation-guide-2024.pdf` | 50 | 50 | yes | 1533 | 18 | 206 | 147 | 1 | 96.0 | 0 |
| `bufftech-gate-installation-guide.pdf` | 56 | 56 | yes | 2326 | 16 | 377 | 148 | 3 | 93.8 | 0 |
| `bufftech-install-semiprivate.pdf` | 6 | 6 | yes | 384 | 0 | 0 | 10 | 0 |  | 0 |
| `bufftech-installation-guide-40-40-70743.pdf` | 44 | 44 | yes | 2001 | 3 | 76 | 81 | 0 |  | 2 |
| `bufftech-installation-guide-afence.pdf` | 56 | 56 | yes | 3357 | 1 | 39 | 389 | 56 | 87.2 | 6 |
| `bufftech-vinyl-catalog-standardfencing.pdf` | 22 | 22 | yes | 521 | 3 | 358 | 146 | 22 | 75.2 | 4 |
| `NOA-06-1019.01-fence-columbia-imperial-chesterfield.` | 10 | 10 | yes | 555 | 0 | 0 | 11 | 10 | 69.9 | 11 |
| `NOA-12-1106.11-extruded-pvc-vinyl-fencing.pdf` | 11 | 11 | yes | 940 | 1 | 12 | 18 | 11 | 69.8 | 13 |
| `NOA-21-0125.07-CertainTeed-extruded-pvc-fencing-2021` | 16 | 16 | yes | 1015 | 0 | 0 | 17 | 16 | 67.0 | 18 |
| `NOA-22-0616.10-CertainTeed-SimTek-molded-fence-2022-` | 8 | 8 | yes | 455 | 0 | 0 | 10 | 8 | 82.1 | 4 |
| `NOA-23-0314.05-CertainTeed-Chesterfield-Columbia-Imp` | 17 | 17 | yes | 1164 | 0 | 0 | 21 | 17 | 67.1 | 18 |
| `NOA-24-0117.05-Barrette-successor-extruded-pvc-fenci` | 17 | 17 | yes | 1058 | 0 | 0 | 19 | 17 | 74.6 | 18 |
| `2017_LWS_VF_Warranty.pdf` | 1 | 1 | yes | 21 | 0 | 0 | 1 | 0 |  | 0 |
| `2023_Decorative-Picket_SellSheet.pdf` | 2 | 2 | yes | 43 | 1 | 30 | 15 | 0 |  | 0 |
| `2023_Emblem_Sell-Sheet.pdf` | 2 | 2 | yes | 53 | 0 | 0 | 13 | 0 |  | 0 |
| `2024-Freedom-VF-Catalog-01-24_SpecialOrderCatalog.pd` | 112 | 112 | yes | 5872 | 183 | 3320 | 1072 | 0 |  | 0 |
| `5x5PostSurfaceMount_Install.pdf` | 13 | 13 | yes | 251 | 5 | 40 | 48 | 0 |  | 0 |
| `73008781_Brighton6x6PrivacyPanel_Instructions.pdf` | 2 | 2 | yes | 196 | 2 | 27 | 11 | 0 |  | 0 |
| `73013029_Ashford4x8DecorativePanel_Instructions.pdf` | 2 | 2 | yes | 169 | 2 | 30 | 8 | 0 |  | 0 |
| `73013822_Wellington6x6Semi-PrivacyPanel_Instructions` | 2 | 2 | yes | 186 | 2 | 29 | 8 | 0 |  | 0 |
| `73014714-6x8Emblem-White-ProjectPlanning.pdf` | 1 | 1 | yes | 98 | 1 | 9 | 16 | 0 |  | 0 |
| `73040126-6x8Wakefield-White-ProjectPlanning.pdf` | 1 | 1 | yes | 89 | 0 | 0 | 9 | 0 |  | 0 |
| `BARRETTE-WEB_RackingGate_Install.pdf` | 25 | 25 | yes | 718 | 4 | 23 | 136 | 0 |  | 0 |
| `CameronPrivacyVinylFencePanel_Instructions.pdf` | 10 | 10 | yes | 240 | 0 | 0 | 29 | 0 |  | 0 |
| `FREEDOM-VFPicketClosedSemiPanelKit_Install.pdf` | 16 | 16 | yes | 321 | 0 | 0 | 51 | 1 | 91.6 | 0 |
| `FREEDOM-WEB-PrivacyKit_Ready-to-Assemble-Privacy-Vin` | 8 | 8 | yes | 175 | 0 | 0 | 35 | 1 | 90.2 | 0 |
| `FREEDOM-WEB-VFCare_CareAndMaintenance.pdf` | 1 | 1 | yes | 17 | 0 | 0 | 1 | 0 |  | 0 |
| `FREEDOM-WEB_LouveredFence_Install.pdf` | 13 | 13 | yes | 260 | 9 | 54 | 56 | 0 |  | 0 |
| `FREEDOM_HorizontalPrivacyFencePanel_Install.pdf` | 36 | 36 | yes | 972 | 5 | 52 | 139 | 2 | 60.3 | 2 |
| `Freedom_RTA_Cutdown_Instructions.pdf` | 2 | 2 | yes | 99 | 0 | 0 | 24 | 0 |  | 0 |
| `HorizontalPrivacyGate_Instructions.pdf` | 19 | 19 | yes | 398 | 2 | 14 | 51 | 0 |  | 0 |
| `TransitionBrackets_Install_SlopeAccommodation.pdf` | 3 | 3 | yes | 60 | 0 | 0 | 9 | 0 |  | 0 |
| `VF-Privacy-Gate-Install_HingesLatchDropRod.pdf` | 19 | 19 | yes | 656 | 6 | 49 | 64 | 0 |  | 0 |
| `VFTransitionPanelKit_SlopeAccommodation.pdf` | 3 | 3 | yes | 184 | 6 | 36 | 27 | 0 |  | 0 |
| `VinylPostAndRailGates_Instructions.pdf` | 16 | 16 | yes | 263 | 6 | 105 | 59 | 2 | 96.0 | 2 |
| `VinylPrivacyPicketGate_Inserts_Instructions.pdf` | 20 | 20 | yes | 766 | 4 | 21 | 84 | 1 | 96.0 | 0 |
| `2023_Conway-Sell-Sheet.pdf` | 2 | 2 | yes | 44 | 0 | 0 | 9 | 0 |  | 0 |
| `Barrette-Privacy-Railing-2021-Engineering-Report-PE.` | 23 | 23 | yes | 415 | 6 | 267 | 88 | 4 | 70.8 | 2 |
| `Bufftech-MiamiDade-NOA-22-0616.10-Orem.pdf` | 8 | 8 | yes | 455 | 0 | 0 | 10 | 8 | 82.1 | 4 |
| `MiamiDade-NOA-22-0217.05-Barrette-Extruded-PVC-Vinyl` | 12 | 12 | yes | 1154 | 0 | 0 | 21 | 12 | 73.3 | 6 |
| `MiamiDade-NOA-24-0117.05-Barrette-Extruded-PVC-Vinyl` | 17 | 17 | yes | 1058 | 0 | 0 | 19 | 17 | 74.6 | 18 |
| `75mph-wind-kit-installation-instructions.pdf` | 4 | 4 | yes | 223 | 0 | 0 | 26 | 0 |  | 0 |
| `75mph-wind-kit-noa-miami-dade.pdf` | 20 | 20 | yes | 1715 | 0 | 0 | 32 | 20 | 73.6 | 8 |
| `astm-info-flyer.pdf` | 1 | 1 | yes | 30 | 1 | 16 | 6 | 0 |  | 0 |
| `classic-product-brochure.pdf` | 24 | 24 | yes | 922 | 4 | 119 | 238 | 0 |  | 0 |
| `extra-strong-hinge-brochure.pdf` | 2 | 2 | yes | 84 | 0 | 0 | 22 | 0 |  | 1 |
| `gate-hardware-catalog-page.pdf` | 1 | 1 | yes | 23 | 1 | 82 | 13 | 0 |  | 0 |
| `gate-installation-instructions.pdf` | 4 | 4 | yes | 153 | 0 | 0 | 27 | 0 |  | 0 |
| `gate-types-flyer-uniweld-vs-assembled.pdf` | 2 | 2 | yes | 26 | 0 | 0 | 16 | 0 |  | 0 |
| `grand-illusions-advantage-brochure.pdf` | 6 | 6 | yes | 104 | 1 | 12 | 39 | 1 | 94.2 | 0 |
| `installation-instructions-assembled-panel.pdf` | 4 | 4 | yes | 129 | 0 | 0 | 28 | 0 |  | 0 |
| `majestic-entranceway-8x8-posts-brochure.pdf` | 2 | 2 | yes | 57 | 0 | 0 | 31 | 0 |  | 0 |
| `pergola-kit-installation-instructions.pdf` | 5 | 5 | yes | 79 | 0 | 0 | 25 | 0 |  | 0 |
| `product-price-catalog-186pg.pdf` | 186 | 186 | yes | 11571 | 110 | 2130 | 616 | 2 | 83.3 | 0 |
| `product-warranty.pdf` | 1 | 1 | yes | 15 | 0 | 0 | 1 | 0 |  | 0 |
| `noa-14-1209.01-PE-stamped-structural-drawings-dixon-` | 20 | 20 | yes | 1715 | 0 | 0 | 32 | 20 | 73.6 | 8 |
| `traverse-gravity-latch-flyer.pdf` | 1 | 1 | yes | 14 | 0 | 0 | 4 | 0 |  | 0 |
| `ARCAT-CSI-32-31-23-Vinyl-Fencing-and-Gates-MasterSpe` | 1 | n/a | yes | 416 | 0 | 0 | 0 | 0 |  | 0 |
| `ASTM-Info-Flyer_Illusions-F964-D4216-Summary.pdf` | 1 | 1 | yes | 30 | 1 | 16 | 6 | 0 |  | 0 |
| `ASTM-Standards-for-Fence-Materials-and-Products_Comp` | 1 | 1 | yes | 121 | 0 | 0 | 1 | 0 |  | 0 |
| `CLFMI-Chain-Link-Wind-Load-Guide-Line-Post-Spacing_W` | 49 | 49 | yes | 545 | 24 | 7150 | 162 | 6 | 89.6 | 1 |
| `CLFMI-Product-Manual-CSI-Section-32-31-13-Chain-Link` | 17 | 17 | yes | 222 | 2 | 98 | 28 | 0 |  | 0 |
| `Digger-Specialties-Polyvinyl-Fence-Brochure_Racking-` | 28 | 28 | yes | 740 | 9 | 496 | 282 | 6 | 53.6 | 7 |
| `Wheatland-Fence-SpecCheck_ASTM-AASHTO-Federal-Specs_` | 8 | 8 | yes | 99 | 0 | 0 | 8 | 0 |  | 0 |
| `MECA-Fence-Wind-Load-Worked-Example_ASCE7-16.pdf` | 2 | 2 | yes | 62 | 0 | 0 | 3 | 0 |  | 0 |
| `Miami-Dade-NOA_Barrette-Outdoor-Living_Extruded-PVC-` | 17 | 17 | yes | 1058 | 0 | 0 | 19 | 17 | 74.6 | 18 |
| `Miami-Dade-NOA_VEKA-Inc_PVC-Privacy-Fence-Panels_24-` | 7 | 7 | yes | 386 | 0 | 0 | 7 | 7 | 76.6 | 2 |
| `all-american-ZP19084-install-guide.pdf` | 25 | 25 | yes | 365 | 0 | 0 | 97 | 1 | 43.6 | 1 |
| `cambridge-BL19110-install-guide.pdf` | 26 | 26 | yes | 379 | 0 | 0 | 95 | 0 |  | 0 |
| `even-steven-VG24100-gate-install-guide.pdf` | 16 | 16 | yes | 312 | 1 | 27 | 74 | 0 |  | 0 |
| `murphys-vinyl-fence-laws.pdf` | 39 | 39 | yes | 813 | 0 | 0 | 264 | 0 |  | 0 |
| `nervous-nelly-VF15100-install-guide.pdf` | 21 | 21 | yes | 538 | 1 | 30 | 82 | 18 | 90.6 | 18 |
| `nervous-nelly-VG25100-gate-install-guide.pdf` | 18 | 18 | yes | 469 | 0 | 0 | 88 | 13 | 86.9 | 15 |
| `plain-jane-VG24200-gate-install-guide.pdf` | 18 | 18 | yes | 447 | 0 | 0 | 88 | 12 | 88.9 | 12 |
| `privacy-gate-6ftx6ft-adjustable-install-guide.pdf` | 17 | 17 | yes | 397 | 1 | 21 | 80 | 11 | 90.5 | 11 |
| `steady-freddy-VF16100-install-guide.pdf` | 21 | 21 | yes | 583 | 0 | 0 | 84 | 19 | 89.4 | 19 |
| `generic-vinyl-fence-spec-lowes.pdf` | 1 | 1 | yes | 23 | 0 | 0 | 6 | 0 |  | 0 |
| `important-install-info-thdstatic.pdf` | 25 | 25 | yes | 587 | 1 | 13 | 189 | 0 |  | 0 |
| `nantucket-spec-sheet-v3-alt.pdf` | 3 | 3 | yes | 181 | 0 | 0 | 32 | 0 |  | 0 |
| `nantucket-spec-sheet-v3.pdf` | 1 | 1 | yes | 48 | 0 | 0 | 5 | 0 |  | 0 |
| `sturbridge-spec-sheet-lowes.pdf` | 1 | 1 | yes | 53 | 0 | 0 | 6 | 0 |  | 0 |
| `sturbridge-BL19103-install-guide.pdf` | 12 | 12 | yes | 259 | 2 | 25 | 50 | 0 |  | 0 |
| `vinyl-surface-mount-SB61000-install-guide.pdf` | 7 | 7 | yes | 115 | 0 | 0 | 25 | 0 |  | 0 |
| `windsor-BL19107-install-guide.pdf` | 22 | 22 | yes | 316 | 0 | 0 | 67 | 0 |  | 0 |
| `weatherables-cad-augusta-8x6-privacy.png` | 1 | 1 | yes | 22 | 0 | 0 | 1 | 1 | 32.2 | 0 |
| `weatherables-cad-augusta-8x8-privacy.png` | 1 | 1 | yes | 28 | 0 | 0 | 1 | 1 | 38.6 | 0 |
| `weatherables-cad-augusta-gate-44.5in.png` | 1 | 1 | yes | 18 | 0 | 0 | 1 | 1 | 32.9 | 0 |
| `weatherables-cad-captiva-4x6-pool.png` | 1 | 1 | yes | 5 | 0 | 0 | 1 | 1 | 68.2 | 0 |
| `weatherables-cad-captiva-gate-48in.png` | 1 | 1 | yes | 7 | 0 | 0 | 1 | 1 | 71.4 | 0 |
| `weatherables-cad-pembroke-6ft-privacy.png` | 1 | 1 | yes | 2 | 0 | 0 | 1 | 1 |  | 0 |
| `triwest-vinyl-reference-guide.pdf` | 32 | 32 | yes | 237 | 7 | 92 | 87 | 1 | 68.7 | 1 |
| `weatherables-2-rail-fence-installation-2024.pdf` | 6 | 6 | yes | 102 | 0 | 0 | 21 | 1 | 88.3 | 0 |
| `weatherables-2-rail-gate-installation.pdf` | 4 | 4 | yes | 78 | 0 | 0 | 14 | 1 | 90.0 | 0 |
| `weatherables-3-rail-fence-installation-2024.pdf` | 6 | 6 | yes | 105 | 0 | 0 | 21 | 1 | 92.7 | 0 |
| `weatherables-3-rail-gate-installation.pdf` | 4 | 4 | yes | 80 | 0 | 0 | 17 | 1 | 90.0 | 0 |
| `weatherables-4-rail-fence-installation-2024.pdf` | 6 | 6 | yes | 104 | 0 | 0 | 21 | 1 | 82.3 | 0 |
| `weatherables-4-rail-gate-installation.pdf` | 4 | 4 | yes | 78 | 0 | 0 | 13 | 1 | 90.0 | 0 |
| `weatherables-black-weathergrain-panels-install.pdf` | 1 | 1 | yes | 32 | 0 | 0 | 2 | 0 |  | 0 |
| `weatherables-crossbuck-fence-installation-2024.pdf` | 6 | 6 | yes | 100 | 0 | 0 | 21 | 1 | 94.3 | 0 |
| `weatherables-crossbuck-gate-installation.pdf` | 4 | 4 | yes | 51 | 0 | 0 | 14 | 1 | 90.0 | 0 |
| `weatherables-fencing-brochure.pdf` | 22 | 22 | yes | 638 | 1 | 6 | 199 | 1 | 93.6 | 0 |
| `weatherables-fencing-master-installation-instruction` | 19 | 19 | yes | 762 | 0 | 0 | 73 | 0 |  | 0 |
| `weatherables-full-line-catalog-2026.pdf` | 40 | 40 | yes | 1431 | 1 | 5 | 423 | 0 |  | 0 |
| `weatherables-general-mount-instructions.pdf` | 1 | 1 | yes | 21 | 0 | 0 | 5 | 0 |  | 0 |
| `weatherables-limited-warranty.pdf` | 2 | 2 | yes | 31 | 0 | 0 | 3 | 0 |  | 0 |
| `weatherables-post-mount-instructions-concrete.pdf` | 1 | 1 | yes | 33 | 0 | 0 | 2 | 0 |  | 0 |
| `weatherables-post-mount-instructions-wood.pdf` | 1 | 1 | yes | 42 | 0 | 0 | 2 | 0 |  | 0 |
| `weatherables-premium-gate-installation-2017.pdf` | 5 | 5 | yes | 95 | 0 | 0 | 18 | 1 | 81.0 | 0 |
| `weatherables-privacy-fencing-specsheet.pdf` | 2 | 2 | yes | 87 | 1 | 53 | 34 | 0 |  | 0 |
