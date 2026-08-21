"""Split the unresolved material into who can actually resolve it.

Three piles, because conflating them wastes the scarcest resource:

* **machine** — a vision-capable reader can transcribe it. Not a human task.
* **review** — already read, needs an accountable sign-off before promotion.
* **human** — needs judgement, or a better copy of the source than exists here.
  Nobody can read a glyph the plotter never printed.
"""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict

from .paths import CATALOG_DIR, REPORTS_DIR, open_write, rel
from .store import connect

MANIFEST = CATALOG_DIR / "unresolved-worklist.jsonl"
LOW_CONF = 70.0

# Findings from the manual verification pass that no amount of re-reading will
# settle. Each cites the evidence that produced it; see
# workspace/reports/manual-verification-round-1.md.
HUMAN_JUDGEMENT = [
    {"kind": "curated_dataset_error", "severity": "critical",
     "source_path": "data/structural/certainteed-bufftech-structural.json",
     "page_no": None, "json_path": "wind_load_tables[0].table[1]",
     "detail": "Exposure B / 24in footing / 66in spacing row is labelled 'HVHZ and "
               "Non-HVHZ'; NOA 23-0314.05 sheet 9 brackets it 'NON HVHZ' only. "
               "Confirmed by two agents, a cross-family reader and direct inspection.",
     "why_human": "amending your research dataset is your call; data/ is read-only to me",
     "action": "correct the row, or record that it stands"},
    {"kind": "curated_dataset_error", "severity": "major",
     "source_path": "data/structural/certainteed-bufftech-structural.json",
     "page_no": None, "json_path": "engineering_letters[2].engineer_of_record",
     "detail": "Records Robert Nieminen PE licence 59166 as Connecticut. The seal "
               "reads STATE OF FLORIDA; the Oxford CT address is the firm's office.",
     "why_human": "same file, same call", "action": "correct or confirm"},
    {"kind": "curated_dataset_error", "severity": "major",
     "source_path": "data/structural/certainteed-bufftech-structural.json",
     "page_no": None, "json_path": "hvhz_noa_approvals[2]",
     "detail": "NOA 22-0616.10 recorded as SimTek / 'Cementitious'. Cover page "
               "DESCRIPTION reads 'Polyethylene Plastic Shell Fence'.",
     "why_human": "same file, same call", "action": "correct or confirm"},
    {"kind": "curated_dataset_error", "severity": "major",
     "source_path": "data/structural/certainteed-bufftech-structural.json",
     "page_no": None, "json_path": "structural_reinforcement_supplement[3].dimensions",
     "detail": "Hat-shaped insert given as 4.500in wide, 0.080/0.036in wall. Drawing "
               "shows 2.750in base, single 0.080in wall; 4.500in belongs to item P/P1 "
               "and 0.036in to item I. Three components conflated.",
     "why_human": "same file, same call", "action": "correct or confirm"},
    {"kind": "source_defect_unreadable", "severity": "minor",
     "source_path": "manuals/certainteed-bufftech/structural/"
                    "NOA-23-0314.05-CertainTeed-Chesterfield-Columbia-Imperial-"
                    "Breezewood-Brookline-current-2023-2029.pdf",
     "page_no": 12,
     "detail": "Three consecutive ITEM codes in the Chesterfield-with-Lattice bill of "
               "material print as a hollow rectangle - a plotter or font artefact in "
               "the original drawing. Unreadable at 5x zoom by two readers.",
     "why_human": "the glyph was never printed; only a better copy from the vendor fixes it",
     "action": "obtain a clean drawing set, or accept the gap"},
    {"kind": "source_placeholder_unfilled", "severity": "major",
     "source_path": "manuals/weatherables/"
                    "weatherables-fencing-master-installation-instructions-2024.pdf",
     "page_no": 1,
     "detail": "The racking section reads 'a defined degree of slope (x inches over x "
               "feet)' - an authoring placeholder never filled in, referring to spec "
               "diagrams absent from the corpus.",
     "why_human": "the answer is not in the corpus; it needs the vendor",
     "action": "request the referenced spec diagrams, or record racking as undocumented"},
    {"kind": "version_ambiguity_two_stamps", "severity": "major",
     "source_path": "manuals/certainteed-bufftech/structural/"
                    "NOA-23-0314.05-CertainTeed-Chesterfield-Columbia-Imperial-"
                    "Breezewood-Brookline-current-2023-2029.pdf",
     "page_no": 17,
     "detail": "Two Miami-Dade approval stamps on one sheet: an older printed "
               "acceptance number overlaid by a newer PRODUCT REVISED stamp, leaving "
               "two acceptance numbers and two expiration dates legible.",
     "why_human": "which stamp governs is a regulatory reading, not a transcription",
     "action": "decide which acceptance number the sheet is filed under"},
]


def _rows(conn: sqlite3.Connection) -> list[dict]:
    out: list[dict] = []
    read = {(r["document_id"], r["page_no"]) for r in conn.execute(
        "SELECT DISTINCT document_id, page_no FROM table_read_candidates")}
    sha = {r["document_id"]: r["sha256"] for r in conn.execute(
        "SELECT document_id, sha256 FROM document_versions")}

    # --- machine: low-confidence pages nobody has looked at -----------------
    seen_content: set[tuple] = set()
    dupes: dict[tuple, list[str]] = defaultdict(list)
    candidates = []
    for r in conn.execute(f"""
        SELECT v.document_id, p.page_no, d.source_path, d.structural,
               p.ocr_mean_confidence conf, p.page_image_path
          FROM pages p JOIN document_versions v ON v.version_id = p.version_id
          JOIN documents d ON d.document_id = v.document_id
         WHERE p.ocr_mean_confidence < {LOW_CONF}
         ORDER BY d.structural DESC, p.ocr_mean_confidence ASC"""):
        if (r["document_id"], r["page_no"]) in read:
            continue
        key = (sha[r["document_id"]], r["page_no"])
        dupes[key].append(r["source_path"])
        if key in seen_content:
            continue
        seen_content.add(key)
        candidates.append(dict(r))
    for r in candidates:
        key = (sha[r["document_id"]], r["page_no"])
        out.append({
            "pile": "machine", "kind": "unread_low_confidence_page",
            "document_id": r["document_id"], "source_path": r["source_path"],
            "page_no": r["page_no"], "ocr_confidence": r["conf"],
            "structural": bool(r["structural"]),
            "page_image_path": r["page_image_path"],
            "also_applies_to": [p for p in dupes[key] if p != r["source_path"]],
            "action": "vision read; no OCR involved",
        })

    # --- review: read, agreed, awaiting an accountable signature ------------
    for r in conn.execute("""
        SELECT d.source_path, c.page_no, c.crop_path, COUNT(*) cells
          FROM table_read_candidates c JOIN documents d ON d.document_id = c.document_id
         WHERE c.review_status='agent_verified'
         GROUP BY d.source_path, c.page_no, c.crop_path ORDER BY cells DESC"""):
        out.append({"pile": "review", "kind": "agent_verified_cells",
                    "source_path": r["source_path"], "page_no": r["page_no"],
                    "crop_path": r["crop_path"], "cells": r["cells"],
                    "action": "open the crop, confirm or correct, then promote"})

    # --- machine: pages OCR found empty. Confirming a page is blank is one
    # --- glance for a vision reader, so this is not human work either.
    for r in conn.execute("""
        SELECT d.source_path, q.page_no, q.detail, v.document_id, p.page_image_path
          FROM quality_issues q JOIN documents d ON d.document_id = q.document_id
          JOIN document_versions v ON v.document_id = d.document_id
          LEFT JOIN pages p ON p.version_id = v.version_id AND p.page_no = q.page_no
         WHERE q.kind IN ('empty_page_after_ocr','empty_page')"""):
        out.append({"pile": "machine", "kind": "confirm_page_is_blank",
                    "document_id": r["document_id"], "source_path": r["source_path"],
                    "page_no": r["page_no"], "page_image_path": r["page_image_path"],
                    "also_applies_to": [],
                    "action": "vision check: genuinely blank, or content extraction missed?"})

    # --- human: judgement calls and source defects no reader can resolve ----
    for item in HUMAN_JUDGEMENT:
        out.append({"pile": "human", **item})
    for r in conn.execute("""
        SELECT d.source_path, q.detail FROM quality_issues q
          JOIN documents d ON d.document_id = q.document_id
         WHERE q.kind = 'encrypted_pdf'"""):
        out.append({"pile": "human", "kind": "encrypted_pdf",
                    "source_path": r["source_path"], "page_no": None,
                    "detail": (r["detail"] or "")[:200],
                    "why_human": "copy is restricted; extraction may be partial and we cannot tell",
                    "action": "obtain an unrestricted copy, or accept the gap on the record"})
    return out


def build(conn: sqlite3.Connection | None = None) -> dict:
    own = conn is None
    conn = conn or connect()
    try:
        rows = _rows(conn)
    finally:
        if own:
            conn.close()
    with open_write(MANIFEST) as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    counts: dict[str, int] = defaultdict(int)
    for r in rows:
        counts[r["pile"]] += 1
    return {"manifest": rel(MANIFEST), "rows": len(rows), "by_pile": dict(counts)}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
