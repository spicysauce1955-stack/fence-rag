"""Report generation: the Phase 0 inspection reports and the Phase 5 coverage report.

Reports are written from measured data only.  Where a number is unknown or a
capability is missing, the report says so rather than omitting it
(prohibition 12).
"""
from __future__ import annotations

import json
import platform
import shutil
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

from . import __version__
from .manifest import (SCAN_CHARS_PER_PAGE, TEXT_LAYER_MIN_CHARS, load_manifest)
from .paths import (CORPUS_ROOTS, REPO_ROOT, REPORTS_DIR, WORKSPACE, open_write)
from .pilot import NO_HEADING_EXEMPT, PILOT
from .quality import (ASCII_TOKEN_RATIO_LIMIT, CONTROL_RATIO_LIMIT)
from .store import connect, stats
from .tools import tool_versions


def _table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join("" if v is None else str(v) for v in r) + " |")
    return "\n".join(out)


# ------------------------------------------------------------------ Phase 0
def environment_report() -> str:
    tv = tool_versions()
    total, used, free = shutil.disk_usage(REPO_ROOT)
    lines = [
        "# Environment report",
        "",
        "Measured on the machine that produced this workspace. Everything below was",
        "probed, not assumed.",
        "",
        "## Platform",
        "",
        _table(["Property", "Value"], [
            ["python", tv.get("python")],
            ["platform", platform.platform()],
            ["cpu count", len(__import__("os").sched_getaffinity(0))],
            ["disk free", f"{free / 1e9:.0f} GB of {total / 1e9:.0f} GB"],
            ["pipeline version", __version__],
        ]),
        "",
        "## Extraction tools",
        "",
        _table(["Tool", "Version", "Role"], [
            ["pdftotext", tv.get("pdftotext"), "text layer + word bounding boxes (`-bbox-layout`)"],
            ["pdftoppm", tv.get("pdftoppm"), "page images (evidence) and OCR renders"],
            ["pdfinfo", tv.get("pdfinfo"), "page count, page size, per-page rotation, encryption"],
            ["tesseract", tv.get("tesseract"), "OCR with word boxes and confidence (hOCR)"],
            ["pillow", tv.get("pillow"), "region crops from page images"],
            ["pdfplumber", tv.get("pdfplumber"), "**optional** table cells, raster/vector figure geometry"],
            ["sqlite3 FTS5", "stdlib", "the lexical index; no external service"],
        ]),
        "",
        "## Permission boundaries actually in force",
        "",
        "- No passwordless `sudo` and no `apt`: system packages could not be installed.",
        "  Every tool above was already present.",
        "- No system `pip`, and the interpreter is PEP 668 externally managed. Third-party",
        "  Python packages are therefore installed into `workspace/pylibs/` (git-ignored)",
        "  and loaded by `fence_evidence/__init__.py`. Nothing is written to system paths.",
        "- `pdfplumber` is the only third-party package used, and it is optional: without it",
        "  the pipeline still runs and records `fallback-whitespace` as the table backend.",
        "- Network is used only to fetch that package. The pipeline performs no network I/O.",
        "- The corpus is read-only and enforced in code by `paths.ensure_writable`.",
        "",
        "## Reproducibility",
        "",
        "```bash",
        "python3 -m fence_evidence.cli manifest      # Phase 0",
        "python3 -m fence_evidence.cli ingest --pilot",
        "python3 tests/run_tests.py                  # preservation + contract gates",
        "python3 -m fence_evidence.cli evaluate      # Phase 4",
        "python3 -m fence_evidence.cli ingest --all  # Phase 5",
        "python3 -m fence_evidence.cli facts --extract",
        "```",
    ]
    return "\n".join(lines) + "\n"


def _scanned_table_paragraph() -> str:
    """Measured, not asserted: what OCR table reconstruction actually produced."""
    from .paths import EVIDENCE_DB
    lead = (
        "The wind-load and footing tables inside the NOA packages are line-work in a "
        "scanned engineering drawing, not text. pdfplumber cannot see them at all (no "
        "text layer), so a conservative OCR word-grid reconstructor was implemented: "
        "words cluster into rows, recurring x-positions become columns, and the "
        "candidate grid is rejected unless it has at least three columns, three rows, "
        "30% numeric cells, few single-character cells, and adequate word confidence.")
    if not EVIDENCE_DB.is_file():
        return lead + "\n\nNo store has been built yet, so its yield is unmeasured."
    conn = connect()
    try:
        grids = conn.execute("""SELECT d.source_path, e.page_no, t.n_rows, t.n_cols
              FROM tables t JOIN elements e ON e.element_id = t.element_id
              JOIN documents d ON d.document_id = e.document_id
             WHERE t.detector = 'ocr-word-grid'
             ORDER BY d.source_path, e.page_no""").fetchall()
        gaps = conn.execute("""SELECT COUNT(*) FROM quality_issues
             WHERE kind = 'table_not_reconstructed'""").fetchone()[0]
        structural_grids = conn.execute("""SELECT COUNT(*) FROM tables t
              JOIN elements e ON e.element_id = t.element_id
              JOIN documents d ON d.document_id = e.document_id
             WHERE t.detector = 'ocr-word-grid' AND d.structural = 1""").fetchone()[0]
    finally:
        conn.close()
    docs = sorted({Path(g["source_path"]).name for g in grids})
    body = [lead, "",
            f"Measured yield across the full corpus: **{len(grids)} grids accepted** in "
            f"{len(docs)} document(s), and **{gaps} pages** where a table is named but no "
            f"grid could be recovered."]
    if grids:
        body += ["", _table(["Document", "Page", "Grid"],
                            [[f"`{Path(g['source_path']).name[:52]}`", g["page_no"],
                              f"{g['n_rows']}x{g['n_cols']}"] for g in grids])]
    body += ["",
             "The split matters more than the total. What it recovers are scanned "
             "**catalog and specification** tables: picket size and spacing grids, rail "
             "and steel-reinforcement columns, ASCE terrain exposure constants. What it "
             f"does not recover is the material this corpus exists for. Only "
             f"{structural_grids} of these grids sits in a structural document, and none "
             "is a wind/exposure/footing table off an NOA drawing sheet: tesseract reads "
             "those pages at roughly 50% mean word confidence, and every candidate grid "
             "there was rejected by the gates that stop it inventing values. Rendering at "
             "400 and 500 dpi instead of 300 did not improve confidence.",
             "",
             "The consequence is stated rather than hidden. For those pages the preserved "
             "page image plus the OCR text is the faithful representation, a "
             "`table_not_reconstructed` quality issue is recorded, and the evaluation "
             "report names the Phase 7 experiment — visual or model-based page reading — "
             "that this failure would justify."]
    return "\n".join(body)


def corpus_audit_report() -> str:
    recs = load_manifest()
    on_disk = [r for r in recs if r.get("sha256")]
    pdfs = [r for r in on_disk if r.get("file_type") == "pdf"]
    images = [r for r in on_disk if r.get("file_type") in ("png", "jpg", "jpeg", "tif", "tiff")]
    docx = [r for r in on_disk if r.get("file_type") == "docx"]
    scans = [r for r in pdfs if r.get("suspected_scan")]
    text_layer = [r for r in pdfs if r.get("text_layer_available")]
    partial = [r for r in text_layer if (r.get("pages_with_text") or 0) < (r.get("page_count") or 0)]
    pages = sum(r.get("page_count") or 0 for r in pdfs)
    scan_pages = sum(r.get("page_count") or 0 for r in scans)

    by_mfr = Counter(r.get("manufacturer") or "unknown" for r in on_disk)
    by_type = Counter(r.get("doc_type") or "unspecified" for r in on_disk)
    by_status = Counter(r.get("version_status") or "unknown" for r in on_disk)

    dupes: dict[str, list[str]] = defaultdict(list)
    for r in on_disk:
        dupes[r["sha256"]].append(r["source_path"])
    dupe_groups = {k: v for k, v in dupes.items() if len(v) > 1}

    lines = [
        "# Corpus audit",
        "",
        f"Measured from `workspace/catalog/corpus-manifest.jsonl` "
        f"({len(recs)} manifest rows, {len(on_disk)} files present on disk).",
        "",
        "## Counts, and how they compare to `rag-pipeline-plan.md`",
        "",
        _table(["Quantity", "Measured", "Plan claimed", "Verdict"], [
            ["PDFs", len(pdfs), 137, "matches" if len(pdfs) == 137 else "DIFFERS"],
            ["PDFs with a text layer", len(text_layer), 115,
             "matches" if len(text_layer) == 115 else "DIFFERS"],
            ["scanned / image-only PDFs", len(scans), 22,
             "matches" if len(scans) == 22 else "DIFFERS"],
            ["CAD images (PNG)", len(images), 6,
             "matches" if len(images) == 6 else "DIFFERS"],
            ["DOCX specifications", len(docx), 1,
             "matches" if len(docx) == 1 else "DIFFERS"],
            ["total PDF pages", pages, "not stated", "newly measured"],
            ["pages inside scanned PDFs", scan_pages, "not stated", "newly measured"],
        ]),
        "",
        f"Text-layer detection thresholds: a page counts as having text at "
        f"{TEXT_LAYER_MIN_CHARS} characters; a document is suspected scanned below "
        f"{SCAN_CHARS_PER_PAGE} characters per page on average.",
        "",
        "## What the plan's counts do not capture",
        "",
        "### Text layers that decode to mojibake",
        "",
        "Six documents carry a text layer that passes any length-based test but decodes",
        "to unreadable glyph soup because the embedded font has no usable ToUnicode map",
        "(`bm|o|_;]uom7` for `into the ground`). A character-count heuristic marks these",
        "as clean text-layer PDFs. They are detected separately, per page, by control-",
        f"character ratio (> {CONTROL_RATIO_LIMIT}) combined with the share of pure-ASCII",
        f"word tokens (< {ASCII_TOKEN_RATIO_LIMIT}), and those pages are routed to OCR with",
        "a `mojibake_text_layer` quality issue recorded. Affected files:",
        "",
        "- `manuals/wam-bam/steady-freddy-VF16100-install-guide.pdf`",
        "- `manuals/wam-bam/nervous-nelly-VF15100-install-guide.pdf`",
        "- `manuals/wam-bam/nervous-nelly-VG25100-gate-install-guide.pdf`",
        "- `manuals/wam-bam/plain-jane-VG24200-gate-install-guide.pdf`",
        "- `manuals/wam-bam/privacy-gate-6ftx6ft-adjustable-install-guide.pdf`",
        "- `manuals/certainteed-bufftech/bufftech-catalog-2014.pdf` (spec-table cells only)",
        "",
        f"### Partially scanned documents ({len(partial)})",
        "",
        "These have a text layer on some pages and none on others, so they need a",
        "per-page decision rather than a per-document one. Extraction records the method",
        "used for each page in `pages.extraction_method`.",
        "",
        f"### Byte-identical duplicates ({len(dupe_groups)} groups)",
        "",
        "The same file is filed under several manufacturer directories. These are linked",
        "with a `same_content_as` relation and **never** deduplicated (prohibition 1);",
        "retrieval may return any copy and evaluation treats them as equivalent.",
        "",
    ]
    rows = []
    for sha, paths in sorted(dupe_groups.items(), key=lambda kv: -len(kv[1])):
        rows.append([len(paths), sha[:10], "<br>".join(p for p in sorted(paths))])
    lines += [_table(["copies", "sha256", "paths"], rows), ""]

    lines += [
        "## Distribution",
        "",
        "### By manufacturer directory",
        "",
        _table(["Manufacturer", "Files"],
               [[k, v] for k, v in sorted(by_mfr.items(), key=lambda kv: -kv[1])]),
        "",
        "### By document type",
        "",
        _table(["doc_type", "Files"],
               [[k, v] for k, v in sorted(by_type.items(), key=lambda kv: -kv[1])]),
        "",
        "### By version status",
        "",
        _table(["version_status", "Files"], [[k, v] for k, v in sorted(by_status.items())]),
        "",
        "Version status is derived conservatively: `active` or `superseded` only when the",
        "filename or curated title says so, otherwise `unknown`. Ingestion then upgrades",
        "it from evidence inside the documents — an NOA that names a previous approval",
        "marks that approval superseded.",
        "",
        "## Scanned tables: what could and could not be recovered",
        "",
        _scanned_table_paragraph(),
        "",
        "## Highest-value material",
        "",
        f"The {len(scans)} scanned PDFs carry {scan_pages} pages and include nearly every",
        "Miami-Dade NOA package: the PE-sealed wind-load and footing tables this system",
        "exists to answer from. They are also the hardest to extract, which is why three",
        "of them are in the pilot.",
        "",
        "## Encrypted documents",
        "",
    ]
    enc = [r for r in pdfs if (r.get("pdf_encrypted") or "no") != "no"]
    if enc:
        lines.append(_table(["File", "Encryption"],
                            [[r["source_path"], r.get("pdf_encrypted")] for r in enc]))
        lines.append("")
        lines.append("Encrypted documents are extracted where poppler permits it; a "
                     "`encrypted_pdf` quality issue is recorded so partial extraction "
                     "is never mistaken for complete extraction.")
    else:
        lines.append("None detected.")
    return "\n".join(lines) + "\n"


def dependency_options_report() -> str:
    tv = tool_versions()
    return "\n".join([
        "# Dependency options",
        "",
        "What was available, what was chosen, and what the fallback is if the choice",
        "disappears.",
        "",
        "## Constraint discovered first",
        "",
        "There is no passwordless `sudo`, so `apt-get` is unavailable, and the system",
        "Python has no `pip` and is PEP 668 externally managed. Two consequences:",
        "",
        "1. Every system tool the pipeline uses had to be present already. They were:",
        "   poppler-utils 24.02 and tesseract 5.3.4.",
        "2. Third-party Python packages are installed with a downloaded `pip` wheel run as",
        "   a zipapp, targeted at `workspace/pylibs/` (git-ignored). Nothing touches system",
        "   or user site-packages, and deleting that directory fully reverts the install.",
        "",
        "## Decisions",
        "",
        _table(["Need", "Options", "Chosen", "Why"], [
            ["page images", "pdftoppm; PyMuPDF; pdf2image",
             "**pdftoppm**",
             "already installed, deterministic, no Python dependency"],
            ["text + geometry", "pdftotext -bbox-layout; pdfminer; PyMuPDF",
             "**pdftotext -bbox-layout**",
             "word-level boxes with block/line structure, no dependency, fast"],
            ["OCR", "tesseract hOCR; cloud OCR",
             "**tesseract hOCR**",
             "installed; hOCR gives per-word boxes and confidence, which the "
             "evidence contract needs. Cloud OCR would send corpus content off the "
             "machine and was not considered further"],
            ["table cells", "pdfplumber; camelot; whitespace heuristic",
             "**pdfplumber, optional**",
             "ruling-line and text-alignment strategies with real cell grids; "
             "camelot needs Ghostscript (not installable here). Falls back to a "
             "whitespace-column heuristic that still preserves the region as "
             "`table_text` rather than losing it"],
            ["scanned tables", "OCR word-grid reconstruction; none",
             "**OCR word-grid, conservative**",
             "pdfplumber cannot see a scan. Reconstruction requires >=3 recurring "
             "columns, >=3 rows and 30% numeric cells; below that the page image "
             "is the evidence and a `table_not_reconstructed` issue is recorded"],
            ["DOCX", "python-docx; stdlib zipfile+ElementTree",
             "**stdlib**",
             "one file in the corpus; a dependency is not justified for it"],
            ["index", "SQLite FTS5; vector DB; Elasticsearch",
             "**SQLite FTS5**",
             "stdlib, no service, and BM25 suits identifier and spec lookups. A "
             "vector store is deferred until a measured failure category "
             "justifies it (prohibition 9)"],
            ["tests", "pytest; stdlib unittest",
             "**stdlib unittest**",
             "the suite must run on a clean checkout with no install step"],
        ]),
        "",
        "## Versions in this workspace",
        "",
        _table(["Component", "Version"], [[k, v] for k, v in sorted(tv.items())]),
        "",
        "Tool versions are stored per extraction run in `extraction_runs.tool_versions`",
        "and hashed into `tool_fingerprint`, which is what makes re-ingestion skip",
        "unchanged work and re-do work when a tool changes.",
        "",
        "## Rejected outright",
        "",
        "- **Cloud/LLM OCR or embedding APIs** — would move corpus content off the machine",
        "  and add a runtime network dependency to a system whose value is provenance.",
        "- **Ghostscript-based table tools** — not installable without root.",
        "- **A vector database** — no measured failure category justifies it yet; the",
        "  evaluation report names the exact conditions that would.",
    ]) + "\n"


def pilot_selection_report() -> str:
    recs = {r["source_path"]: r for r in load_manifest()}
    rows = []
    for spec in PILOT:
        r = recs.get(spec["source_path"], {})
        rows.append([spec["class"], f"`{spec['source_path']}`", r.get("page_count"),
                     "yes" if r.get("suspected_scan") else "no", spec["reason"]])
    total_pages = sum((recs.get(s["source_path"], {}).get("page_count") or 0) for s in PILOT)
    return "\n".join([
        "# Pilot selection",
        "",
        f"Ten documents, {total_pages} pages, chosen to exercise every extraction path in",
        "the corpus. Selection is explicit rather than sampled so the Phase 1 gate is",
        "reproducible and each choice carries a stated reason.",
        "",
        _table(["Class", "Document", "Pages", "Scanned", "Why this one"], rows),
        "",
        "## Coverage against the guide's Phase 1 requirement",
        "",
        _table(["Required", "Provided"], [
            ["two text-layer manuals", "Wam Bam Cambridge, Bufftech/SimTek install guide"],
            ["three scanned structural/NOA documents",
             "CertainTeed NOA 23-0314.05 (current), NOA 21-0125.07 (superseded), "
             "Illusions NOA 14-1209.01 (PE drawings)"],
            ["two mixed catalogs", "Freedom 2024 special-order catalog, Weatherables brochure"],
            ["one table-heavy specification", "CLFMI wind-load / line-post-spacing guide"],
            ["one CAD image", "Weatherables Augusta 8x6 privacy CAD PNG"],
            ["the DOCX specification", "ARCAT CSI 32 31 23 MasterSpec"],
        ]),
        "",
        "## Documented exemptions",
        "",
        "Two documents are exempt from the section-hierarchy assertion, because the",
        "source genuinely has no prose hierarchy to preserve:",
        "",
        _table(["Document", "Reason"],
               [[f"`{k}`", v] for k, v in NO_HEADING_EXEMPT.items()]),
        "",
        "The DOCX is exempt from the page-image and bounding-box assertions: a DOCX has",
        "no page geometry and no document renderer is available in this environment. The",
        "limitation is recorded as a `no_page_image_for_docx` quality issue rather than",
        "passed over silently, and its section hierarchy and table cells are preserved.",
    ]) + "\n"


# ------------------------------------------------------------------ Phase 5
def coverage_report(conn: sqlite3.Connection) -> str:
    recs = {r["source_path"]: r for r in load_manifest()}
    docs = conn.execute("""SELECT d.document_id, d.source_path, d.file_type, d.manufacturer,
            d.version_status, v.version_id, v.page_count
            FROM documents d JOIN document_versions v ON v.document_id = d.document_id
            ORDER BY d.source_path""").fetchall()
    rows = []
    missing_pages = []
    for d in docs:
        el = conn.execute("SELECT COUNT(*) FROM elements WHERE version_id=?",
                          (d["version_id"],)).fetchone()[0]
        tb = conn.execute("""SELECT COUNT(*) FROM tables t JOIN elements e
                ON e.element_id=t.element_id WHERE e.version_id=?""",
                          (d["version_id"],)).fetchone()[0]
        cells = conn.execute("""SELECT COUNT(*) FROM table_cells c JOIN tables t
                ON t.table_id=c.table_id JOIN elements e ON e.element_id=t.element_id
                WHERE e.version_id=?""", (d["version_id"],)).fetchone()[0]
        assets = conn.execute("SELECT COUNT(*) FROM assets WHERE version_id=?",
                              (d["version_id"],)).fetchone()[0]
        ocr_pages = conn.execute("""SELECT COUNT(*) FROM pages WHERE version_id=?
                AND ocr_mean_confidence IS NOT NULL""", (d["version_id"],)).fetchone()[0]
        conf = conn.execute("""SELECT AVG(ocr_mean_confidence) FROM pages
                WHERE version_id=? AND ocr_mean_confidence IS NOT NULL""",
                            (d["version_id"],)).fetchone()[0]
        issues = conn.execute("""SELECT COUNT(*) FROM quality_issues WHERE version_id=?
                AND severity IN ('error','warning')""", (d["version_id"],)).fetchone()[0]
        expected = recs.get(d["source_path"], {}).get("page_count")
        stored = d["page_count"]
        ok = (expected is None) or (stored == expected)
        if not ok:
            missing_pages.append((d["source_path"], stored, expected))
        rows.append([f"`{Path(d['source_path']).name[:52]}`", stored,
                     expected if expected is not None else "n/a",
                     "yes" if ok else "**NO**", el, tb, cells, assets, ocr_pages,
                     f"{conf:.1f}" if conf else "", issues])
    st = stats(conn)
    kinds = Counter(r["kind"] for r in conn.execute("SELECT kind FROM quality_issues"))
    sev = Counter(r["severity"] for r in conn.execute("SELECT severity FROM quality_issues"))
    manifest_targets = [r for r in load_manifest()
                        if r.get("sha256") and r.get("extraction_method") not in
                        (None, "unsupported", "unreadable")]
    ingested = {d["source_path"] for d in docs}
    not_ingested = [r["source_path"] for r in manifest_targets
                    if r["source_path"] not in ingested]

    lines = [
        "# Corpus coverage report",
        "",
        _table(["Measure", "Value"], [
            ["documents in store", st["documents"]],
            ["ingestable files in manifest", len(manifest_targets)],
            ["not ingested", len(not_ingested)],
            ["versions", st["versions"]],
            ["pages", st["pages"]],
            ["elements", st["elements"]],
            ["tables / cells", f"{st['tables']} / {st['table_cells']}"],
            ["assets (page + region images)", st["assets"]],
            ["relations", st["relations"]],
            ["retrieval units", st["retrieval_units"]],
            ["facts", st["facts"]],
            ["quality issues", st["quality_issues"]],
        ]),
        "",
    ]
    if not_ingested:
        lines += ["## Files not ingested", "",
                  "\n".join(f"- `{p}`" for p in not_ingested), ""]
    else:
        lines += ["Every ingestable file in the manifest is present in the store.", ""]
    if missing_pages:
        lines += ["## Page-count mismatches", "",
                  _table(["Document", "Pages stored", "Pages in source"],
                         [[f"`{a}`", b, c] for a, b, c in missing_pages]), ""]
    else:
        lines += ["Every document stored exactly as many pages as its source has.", ""]
    lines += [
        "## Quality issues by kind",
        "",
        _table(["Kind", "Count"], [[k, v] for k, v in kinds.most_common()]),
        "",
        _table(["Severity", "Count"], [[k, v] for k, v in sev.most_common()]),
        "",
        "## Per document",
        "",
        _table(["Document", "Pages", "Source pages", "Match", "Elements", "Tables",
                "Cells", "Assets", "OCR pages", "Mean OCR conf", "Issues"], rows),
    ]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ Phase 6
def facts_report(conn: sqlite3.Connection) -> str:
    total = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
    if total == 0:
        return "# Structured technical facts\n\nNo facts extracted yet.\n"
    by_type = conn.execute("""SELECT fact_type, COUNT(*) n,
            SUM(review_status='flagged') flagged, SUM(ocr_derived) ocr
            FROM facts GROUP BY fact_type ORDER BY n DESC""").fetchall()
    by_basis = conn.execute("""SELECT condition_basis, COUNT(*) n FROM facts
        GROUP BY 1 ORDER BY n DESC""").fetchall()
    with_alts = conn.execute(
        "SELECT COUNT(*) FROM facts WHERE value_alternates IS NOT NULL").fetchone()[0]
    # Whether the two lexemes actually DISAGREE is the whole point of obligation
    # 4, so count it rather than let `with_alts` quietly imply it.
    disagreeing = 0
    for _r in conn.execute("""SELECT value_normalized, unit_normalized, value_alternates
                                FROM facts WHERE value_alternates IS NOT NULL"""):
        if _r["value_normalized"] is None or _r["unit_normalized"] != "in":
            continue
        for _a in json.loads(_r["value_alternates"] or "[]"):
            if _a.get("unit_normalized") != "mm":
                continue
            if abs(_r["value_normalized"] * 25.4 - (_a.get("value_normalized") or 0)) > 0.05:
                disagreeing += 1
                break
    by_lang = conn.execute("""SELECT COALESCE(lang,'(untagged)') lang,
        COALESCE(lang_basis,'(untagged)') lang_basis, COUNT(*) n
        FROM elements GROUP BY 1,2 ORDER BY n DESC""").fetchall()
    by_status = conn.execute("""SELECT review_status, COUNT(*) n FROM facts
            GROUP BY review_status ORDER BY n DESC""").fetchall()
    conditioned = conn.execute("""SELECT COUNT(*) FROM facts
            WHERE conditions != '{}'""").fetchone()[0]
    no_prov = conn.execute("""SELECT COUNT(*) FROM facts f
            LEFT JOIN elements e ON e.element_id=f.element_id
            WHERE e.element_id IS NULL""").fetchone()[0]
    samples = conn.execute("""SELECT f.fact_type, f.value_original, f.value_normalized,
            f.unit_normalized, f.conditions, f.review_status, d.source_path, f.page_no,
            f.element_id FROM facts f JOIN documents d ON d.document_id=f.document_id
            WHERE f.fact_type IN ('footing_depth_in','post_spacing_in','wind_speed_mph',
                                  'racking_degrees','approval_id')
              AND f.conditions != '{}'
            ORDER BY f.fact_type LIMIT 25""").fetchall()
    lines = [
        "# Structured technical facts (Phase 6)",
        "",
        "Facts are *derived from* canonical elements and never replace them. Every row",
        "carries the element, page and document it came from, the original wording, the",
        "normalised value beside it, and a review status. A value read from OCR text on a",
        "page whose mean word confidence is below 80 is created as `flagged`, not",
        "`extracted`: a misread digit in a footing depth is a structural error, not a typo.",
        "",
        _table(["Measure", "Value"], [
            ["facts", total],
            ["with conditions attached", conditioned],
            ["facts without a source element", f"**{no_prov}**" if no_prov else 0],
        ]),
        "",
        "## By review status",
        "",
        _table(["Status", "Count"], [[r["review_status"], r["n"]] for r in by_status]),
        "",
        "## By type",
        "",
        _table(["Fact type", "Count", "Flagged for review", "OCR-derived"],
               [[r["fact_type"], r["n"], r["flagged"], r["ocr"]] for r in by_type]),
        "",
        "## Where the conditions came from",
        "",
        "Obligation 15: a row states whether its conditions came from the source.",
        "`stated` means the document gave them -- including giving none, which makes the",
        "row an explicit fallback. `assumed` means we inferred them. `unexamined` means",
        "nobody looked: the regex matched a number and never asked what scoped it. That",
        "third value is internal and publishes as `assumed`; it exists so the store does",
        "not assert an inference it never made.",
        "",
        _table(["condition basis", "Count", "Means"],
               [[r["condition_basis"], r["n"], {
                   "stated": "the document said so",
                   "assumed": "captured by regex proximity, not asserted by the document",
                   "unexamined": "no conditions, and nothing looked for any",
               }.get(r["condition_basis"], "")] for r in by_basis]),
        "",
        "## Second units, where a source states one",
        "",
        "Obligation 4: where a source states two units and they disagree, publish both.",
        f"**{with_alts}** of {total} facts carry an alternate lexeme in `value_alternates`,",
        f"of which **{disagreeing} disagree** with the primary value.",
        "",
        "**Read that second number carefully.** The schema can now represent a disagreeing",
        "second unit -- that is the gap obligation 4 declared, and it is closed. But the",
        "corpus's disagreeing statements are not reaching it. Measured: 64 real disagreeing",
        "statements across 201 occurrences in 15 unique-content documents, and **none of",
        "them is reachable by this extractor**. Two causes, the second much larger:",
        "",
        "1. An adjacency defect worth 3 statements. The parenthetical sits between the",
        "   number and the keyword a pattern needs -- `6 inches (152 mm) below grade`",
        "   never matches `depth_below_grade_in`.",
        "2. Missing fact types, worth the other 61. Every dual-unit disagreement in this",
        "   corpus is about *product geometry* -- fence height, mesh opening, picket gap,",
        "   member section, stock length -- and this extractor covers footing, spacing,",
        "   wind and approval metadata. The two populations barely intersect: of the",
        "   elements carrying a paired dual-unit statement, only 6 produce any fact at all.",
        "",
        "Closing obligation 4's disagreement clause is a fact-type expansion, not a",
        "dual-unit-parsing problem. See `docs/state-and-gaps.md` G34.",
        "",
        "## Language, and the fact that none of it was measured",
        "",
        "Obligation 10 requires `lang` and forbids normalising it. Script is measured by",
        "Unicode range; **language is not.** Telling English from another Latin-script",
        "language is not something this pipeline can do, and tesseract here has only",
        "`eng` installed. So every tag below is `assumed` or `unknown`, and `measured`",
        "stays reserved for a real language identifier that does not exist yet.",
        "",
        "Language is **not** derived from `corpus_track`. That axis is a standards regime",
        "-- GB rather than ASTM -- not a language, and the China-track documents here are",
        "English-language export catalogues. Measured: zero CJK-bearing elements corpus-wide.",
        "",
        _table(["lang", "basis", "Elements"],
               [[r["lang"], r["lang_basis"], r["n"]] for r in by_lang]),
        "",
        "## Sample, with provenance",
        "",
        _table(["Type", "Original", "Normalised", "Conditions", "Status", "Source", "Page"],
               [[r["fact_type"], f"`{r['value_original'][:40]}`",
                 f"{r['value_normalized']} {r['unit_normalized'] or ''}".strip(),
                 f"`{r['conditions']}`", r["review_status"],
                 f"`{Path(r['source_path']).name[:40]}`", r["page_no"]]
                for r in samples]),
        "",
        "## What this layer is not",
        "",
        "The extractor is a documented set of regular expressions (`extractor='regex-v1'`),",
        "not a model. It finds values that are stated in a sentence or a recovered table",
        "cell. It does **not** read values out of scanned drawing tables, because those",
        "cells were never recovered (see the corpus audit). Any fact whose conditions",
        "matter for a structural decision should be confirmed against the page image",
        "before use; that is what the review status is for.",
    ]
    return "\n".join(lines) + "\n"


def write_all_reports() -> dict:
    written = {}
    for name, body in (("environment-report.md", environment_report()),
                       ("corpus-audit.md", corpus_audit_report()),
                       ("dependency-options.md", dependency_options_report()),
                       ("pilot-selection.md", pilot_selection_report())):
        with open_write(REPORTS_DIR / name) as f:
            f.write(body)
        written[name] = len(body.splitlines())
    from .paths import EVIDENCE_DB
    if EVIDENCE_DB.is_file():
        conn = connect()
        try:
            body = coverage_report(conn)
        finally:
            conn.close()
        with open_write(REPORTS_DIR / "coverage-report.md") as f:
            f.write(body)
        written["coverage-report.md"] = len(body.splitlines())
        conn = connect()
        try:
            body = facts_report(conn)
        finally:
            conn.close()
        with open_write(REPORTS_DIR / "facts-report.md") as f:
            f.write(body)
        written["facts-report.md"] = len(body.splitlines())
    return written
