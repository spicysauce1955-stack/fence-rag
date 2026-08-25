# RAG Pipeline Plan — Vinyl Fence BOM Corpus

```text
Status:    HISTORICAL. Kept because `guide.md`, `docs/mvp-implementation-spec.md`
           and `fence_evidence/reports.py` cite it as the audit that motivated the
           build. It is not a plan any more and nothing here is authoritative.
Superseded by: docs/mvp-implementation-spec.md (authoritative) and
           docs/state-and-gaps.md (what is actually true, measured).
Known stale: it says tesseract is not installed. It is.
```

Status when written: **proposed, not yet built**. Two decisions below were blocking
before implementation started; both were since decided and built.

## Goal

Turn the raw corpus collected in rounds 1–2 (`manuals/`, `china/manuals/`, `data/*.json`) into a
filtered, queryable RAG index for Q&A — e.g. "what's the footing depth for CertainTeed Chesterfield
at 130mph exposure C" — while dropping redundant, narrative, warranty, and marketing content. The
structural and manuals content is the highest-value material and should not be diluted or lost during
filtering.

## Content audit (as of 2026-08-20)

- **137 PDFs** total (`manuals/` + `china/manuals/`), plus 6 PNG CAD images and 1 docx (ARCAT CSI
  master spec).
- **115 PDFs have a real text layer** — directly extractable via `pdftotext -layout`, no OCR needed.
- **22 PDFs are scanned images with ~0 extractable text.** This is disproportionately the *most*
  valuable material: nearly all the Miami-Dade NOA structural packages (CertainTeed, Barrette,
  Illusions, Freedom, VEKA), plus the 3 Showtech China catalogs and 2 legacy CertainTeed docs.
  `tesseract-ocr` is not installed but is available via `apt-get` (candidate 5.3.4-1build5).
- **Content is bimodal, not uniformly noisy.** Sampled keyword density across doc types:
  - Install manuals / spec sheets: mostly technical (e.g. a Bufftech install guide scored 439
    technical-term hits vs. 16 marketing hits).
  - Warranty docs (6 total): essentially all narrative/legal boilerplate — safe to drop wholesale.
  - Catalogs: genuinely mixed *within the same document* — one Freedom catalog scored 189 technical
    hits *and* 98 marketing hits in one 160K-character PDF. Whole-document keep/drop would either
    lose real dimension tables or keep pages of lifestyle photography captions.
- No embeddings/vector-DB MCP is connected in this session. **SQLite FTS5** (stdlib `sqlite3`, no
  new dependency) is the default choice for the index — keyword/BM25 search, which tends to perform
  at least as well as embeddings for spec-style lookups keyed on exact technical terms and model names.

## Proposed pipeline

| Step | What | Notes |
|---|---|---|
| A. Extract | `pdftotext -layout` on the 115 text-layer PDFs; docx→text on the ARCAT spec | Deterministic, already validated to work |
| B. OCR the 22 scanned docs | via `tesseract` | **Blocked on decision 1** — installs a system package |
| C. Chunk | per page/section, tagged with manufacturer, doc_type, title, page, source url/local_path | Preserves citations for every answer |
| D. Classify chunks | keyword-density prefilter: auto-keep technical, auto-drop pure marketing/warranty, flag mixed chunks for a closer pass | Avoids whole-document keep/drop losing data buried in catalogs |
| E. Dedupe | collapse near-identical chunks across catalog vs. dedicated install manual; collapse superseded NOA versions | **Superseded-NOA handling blocked on decision 2** |
| F. Index | SQLite + FTS5, one row per kept chunk, with full metadata | Queryable immediately, no external service |
| G. Sanity check | run ~10 real technical questions against the index before calling it done | Catches retrieval gaps early |

## Open decisions

1. **Scanned NOAs (22 files):** OCR via `tesseract` (more complete, touches system packages) vs.
   index the structural-pass agents' already-transcribed JSON summaries instead for just these docs
   (already vetted, free, but lower fidelity than full OCR text).
2. **Superseded NOA versions** (e.g. CertainTeed's 2012/2021 NOAs, since replaced by 23-0314.05):
   keep full text indexed for historical/audit reference, or reduce to a metadata stub pointing at
   the current/active NOA only.

## Not in scope for this pass

- Semantic/vector search — no embeddings MCP connected; can be added later as an upgrade if keyword
  search proves insufficient.
- Re-scraping or additional Tavily research — this pipeline operates only on the corpus already on
  disk.
