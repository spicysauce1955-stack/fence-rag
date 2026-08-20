# Dependency options

What was available, what was chosen, and what the fallback is if the choice
disappears.

## Constraint discovered first

There is no passwordless `sudo`, so `apt-get` is unavailable, and the system
Python has no `pip` and is PEP 668 externally managed. Two consequences:

1. Every system tool the pipeline uses had to be present already. They were:
   poppler-utils 24.02 and tesseract 5.3.4.
2. Third-party Python packages are installed with a downloaded `pip` wheel run as
   a zipapp, targeted at `workspace/pylibs/` (git-ignored). Nothing touches system
   or user site-packages, and deleting that directory fully reverts the install.

## Decisions

| Need | Options | Chosen | Why |
|---|---|---|---|
| page images | pdftoppm; PyMuPDF; pdf2image | **pdftoppm** | already installed, deterministic, no Python dependency |
| text + geometry | pdftotext -bbox-layout; pdfminer; PyMuPDF | **pdftotext -bbox-layout** | word-level boxes with block/line structure, no dependency, fast |
| OCR | tesseract hOCR; cloud OCR | **tesseract hOCR** | installed; hOCR gives per-word boxes and confidence, which the evidence contract needs. Cloud OCR would send corpus content off the machine and was not considered further |
| table cells | pdfplumber; camelot; whitespace heuristic | **pdfplumber, optional** | ruling-line and text-alignment strategies with real cell grids; camelot needs Ghostscript (not installable here). Falls back to a whitespace-column heuristic that still preserves the region as `table_text` rather than losing it |
| scanned tables | OCR word-grid reconstruction; none | **OCR word-grid, conservative** | pdfplumber cannot see a scan. Reconstruction requires >=3 recurring columns, >=3 rows and 30% numeric cells; below that the page image is the evidence and a `table_not_reconstructed` issue is recorded |
| DOCX | python-docx; stdlib zipfile+ElementTree | **stdlib** | one file in the corpus; a dependency is not justified for it |
| index | SQLite FTS5; vector DB; Elasticsearch | **SQLite FTS5** | stdlib, no service, and BM25 suits identifier and spec lookups. A vector store is deferred until a measured failure category justifies it (prohibition 9) |
| tests | pytest; stdlib unittest | **stdlib unittest** | the suite must run on a clean checkout with no install step |

## Versions in this workspace

| Component | Version |
|---|---|
| pdfinfo | pdfinfo version 24.02.0 |
| pdfplumber | 0.11.10 |
| pdftoppm | pdftoppm version 24.02.0 |
| pdftotext | pdftotext version 24.02.0 |
| pillow | 10.2.0 |
| python | 3.12.3 |
| tesseract | tesseract 5.3.4 |

Tool versions are stored per extraction run in `extraction_runs.tool_versions`
and hashed into `tool_fingerprint`, which is what makes re-ingestion skip
unchanged work and re-do work when a tool changes.

## Rejected outright

- **Cloud/LLM OCR or embedding APIs** — would move corpus content off the machine
  and add a runtime network dependency to a system whose value is provenance.
- **Ghostscript-based table tools** — not installable without root.
- **A vector database** — no measured failure category justifies it yet; the
  evaluation report names the exact conditions that would.
