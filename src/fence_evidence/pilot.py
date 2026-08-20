"""The Phase 1 pilot document set.

Ten documents chosen to cover every extraction path the corpus contains, per
guide.md Phase 1.  Selection is explicit rather than sampled so the pilot gate
is reproducible and each choice carries a stated reason.
"""
from __future__ import annotations

PILOT: list[dict] = [
    {
        "source_path": "manuals/wam-bam/cambridge-BL19110-install-guide.pdf",
        "class": "text_layer_manual",
        "reason": "Clean InDesign text layer with step numbering and callouts; "
                  "the easy case that must be perfect before anything harder counts.",
        "expect": ["headings", "figures", "page_images", "bboxes"],
    },
    {
        "source_path": "manuals/barrette-outdoor-living/bufftech-simtek-fence-install-guide.pdf",
        "class": "text_layer_manual",
        "reason": "Multi-section installation guide with tables and exploded views; "
                  "exercises heading hierarchy across many pages.",
        "expect": ["headings", "tables", "figures", "page_images", "bboxes"],
    },
    {
        "source_path": "manuals/certainteed-bufftech/structural/NOA-23-0314.05-CertainTeed-Chesterfield-Columbia-Imperial-Breezewood-Brookline-current-2023-2029.pdf",
        "class": "scanned_structural",
        "reason": "The current CertainTeed Miami-Dade NOA. Scanned, PE-sealed, "
                  "carries the wind/exposure tables the system exists to answer from.",
        "expect": ["ocr", "tables_or_recorded_gap", "drawings", "page_images", "bboxes"],
    },
    {
        "source_path": "manuals/certainteed-bufftech/structural/NOA-21-0125.07-CertainTeed-extruded-pvc-fencing-2021-2024-superseded.pdf",
        "class": "scanned_structural",
        "reason": "The superseded predecessor of the above. Proves the store keeps "
                  "historical approvals as distinct records (prohibition 5).",
        "expect": ["ocr", "tables_or_recorded_gap", "page_images", "supersession_relation"],
    },
    {
        "source_path": "manuals/illusions-vinyl-fence/structural/noa-14-1209.01-PE-stamped-structural-drawings-dixon-engineering.pdf",
        "class": "scanned_structural",
        "reason": "Twenty pages of PE-stamped structural drawings with little prose; "
                  "the hardest OCR + drawing-label case in the corpus.",
        "expect": ["ocr", "drawings", "page_images", "bboxes"],
    },
    {
        "source_path": "manuals/freedom-outdoor-living/2024-Freedom-VF-Catalog-01-24_SpecialOrderCatalog.pdf",
        "class": "mixed_catalog",
        "reason": "Marketing photography and dimension tables inside one document — "
                  "the case that makes whole-document keep/drop wrong (prohibition 3).",
        "expect": ["headings", "tables", "figures", "page_images"],
    },
    {
        "source_path": "manuals/weatherables/weatherables-fencing-brochure.pdf",
        "class": "mixed_catalog",
        "reason": "Second mixed catalog from a different producer toolchain; guards "
                  "against tuning extraction to one vendor's PDF generator.",
        "expect": ["headings", "tables", "figures", "page_images"],
    },
    {
        "source_path": "manuals/industry-standards/CLFMI-Chain-Link-Wind-Load-Guide-Line-Post-Spacing_WLG2445_2023.pdf",
        "class": "table_heavy_spec",
        "reason": "Dense conditional wind-load / post-spacing tables. The table "
                  "fidelity gate: cells must survive as cells, not as flowed text.",
        "expect": ["tables", "table_cells", "page_images", "bboxes"],
    },
    {
        "source_path": "manuals/weatherables/structural/weatherables-cad-augusta-8x6-privacy.png",
        "class": "cad_image",
        "reason": "Bare CAD raster with dimension callouts and no container format; "
                  "proves drawing labels are captured with bboxes.",
        "expect": ["ocr", "drawing_labels", "page_images", "bboxes"],
    },
    {
        "source_path": "manuals/industry-standards/ARCAT-CSI-32-31-23-Vinyl-Fencing-and-Gates-MasterSpec_Superior-Outdoor.docx",
        "class": "docx_spec",
        "reason": "The only DOCX. CSI MasterSpec hierarchy (PART/2.1/A/1) is real "
                  "section structure that must become a heading path.",
        # measured: this document contains no <w:tbl> at all, so a table
        # assertion here would test the extractor against something the source
        # does not have. Table extraction from DOCX is unit-tested separately.
        "expect": ["headings", "bboxes_exempt"],
    },
]

PILOT_PATHS = [p["source_path"] for p in PILOT]

# Scanned NOA drawing sheets hold their wind/exposure tables as line-work inside
# an engineering drawing.  Tesseract reads those pages at roughly 50% mean word
# confidence, which is too poor to rebuild a cell grid without inventing values,
# so the gate accepts either recovered cells *or* an explicit
# ``table_not_reconstructed`` quality issue plus the preserved page image.
# Silently reporting "no tables" would violate prohibition 12.
TABLES_OR_RECORDED_GAP = [p["source_path"] for p in PILOT
                          if "tables_or_recorded_gap" in p["expect"]]

# Documents with no genuine heading hierarchy in the source; exempt from the
# section-hierarchy assertion (guide.md Phase 1) with the reason recorded.
NO_HEADING_EXEMPT = {
    "manuals/weatherables/structural/weatherables-cad-augusta-8x6-privacy.png":
        "single CAD raster; dimension callouts are labels, not sections",
    "manuals/illusions-vinyl-fence/structural/noa-14-1209.01-PE-stamped-structural-drawings-dixon-engineering.pdf":
        "drawing sheets carry title blocks rather than a prose heading hierarchy",
}
