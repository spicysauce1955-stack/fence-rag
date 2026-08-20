# Fence Evidence System

A source-preserving evidence store and lexical retrieval layer over the vinyl
fence document corpus in this repository — 137 PDFs, 6 CAD images and one DOCX
specification, 2140 pages, including the Miami-Dade NOA packages that carry the
PE-sealed wind-load and footing tables.

The goal is not a RAG demo. It is to answer a question like *"what footing depth
applies to CertainTeed Chesterfield at Exposure C?"* **with the page it came
from**, and to be honest when the corpus does not say.

## What it does

```
corpus (read-only)                 workspace/ (all output)
manuals/  china/manuals/  data/    catalog/    corpus-manifest.jsonl
        │                          derived/    page images, region crops
        ▼                          indexes/    evidence.db (canonical + FTS5)
  extraction                       reports/    audits, coverage, evaluation
  pdftotext -bbox-layout           tests/      evaluation results
  pdftoppm + tesseract hOCR
  pdfplumber (optional)
        │
        ▼
  canonical evidence store ──────► retrieval units ──► FTS5 BM25 search
  documents, versions, pages,      (rebuildable            │
  elements, tables, table_cells,    projection)            ▼
  assets, relations, facts,                          result + page image
  quality_issues, extraction_runs                     + region crop + bbox
```

Canonical rows record what the source actually contained. Retrieval units are a
projection that can be dropped and rebuilt without re-reading a single PDF.

## Quick start

No installation is required; the pipeline runs on the standard library plus
poppler and tesseract. `pdfplumber` is optional and, when present, is loaded
from `workspace/pylibs/`.

```bash
python3 -m fence_evidence.cli manifest          # Phase 0: inspect the corpus
python3 -m fence_evidence.cli ingest --pilot    # Phase 1: 10-document pilot
python3 tests/run_tests.py                      # preservation + contract gates
python3 -m fence_evidence.cli evaluate          # Phase 4: gold question set
python3 -m fence_evidence.cli ingest --all      # Phase 5: full corpus
python3 -m fence_evidence.cli facts --extract   # Phase 6: structured facts
python3 -m fence_evidence.cli report            # regenerate workspace reports
```

Searching:

```bash
python3 -m fence_evidence.cli search "footing depth exposure C" -k 5
python3 -m fence_evidence.cli search "post spacing" --element-type table
python3 -m fence_evidence.cli resolve 23-0314.05        # supersession chain
python3 -m fence_evidence.cli page doc-3c8ab51045c7 17  # a page and its elements
python3 -m fence_evidence.cli region element-...        # image evidence
```

Every search result carries `source_path`, `page`, `element_id`, `bbox`,
`page_image_path` and, where the element is visual, `region_image_path`.

## Python API

```python
from fence_evidence.retrieval import (search_evidence, get_document, get_page,
                                      get_region, get_element_context,
                                      resolve_document_version)

for hit in search_evidence("racking degrees Chesterfield", limit=5):
    print(hit.source_path, hit.page, hit.score, hit.page_image_path)
```

## Documents

| File | Status |
|---|---|
| `guide.md` | the contract this implements |
| `rag-pipeline-plan.md` | original corpus audit and proposal (historical) |
| `docs/mvp-implementation-spec.md` | **authoritative** specification |
| `docs/target-architecture.md` | informative future direction |
| `docs/phase-checkpoints.md` | per-phase record: implemented, tested, incomplete |
| `docs/state-and-gaps.md` | current snapshot: measured state, and every known gap |
| `workspace/reports/` | environment, corpus audit, dependency options, pilot selection, coverage, evaluation |
| `eval/gold-questions-*.json` | 44 hand-verified benchmark questions |

## Non-negotiables

The corpus is read-only, enforced in code: every write goes through
`fence_evidence.paths.ensure_writable`, which refuses any path outside
`workspace/`. Document content is data and is never executed — external tools
are always invoked with argument lists, never a shell. OCR text is stored beside
source text, never over it. Superseded approvals stay separate records, linked
by a relation. Byte-identical files filed under different manufacturers are
linked, never deduplicated. Measurements keep their original wording alongside
any normalised value. No technical value is returned without its document, page
and element.
