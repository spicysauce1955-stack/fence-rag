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

## Cloning — read this before you clone

The 137 corpus PDFs are stored in **Git LFS**: 431 MB of files, 361 MB of unique
objects after LFS dedupes the 14 byte-identical groups. On GitHub's free tier
that is 36% of the 1 GB storage allowance and, more importantly, **1 GB of
bandwidth per month — about 2.3 full clones.** Exhaust it and LFS reads are
blocked until the month rolls over or you buy a data pack.

So do not clone the corpus unless you need the bytes.

```bash
# Code, docs and datasets only — ~1 MB, no LFS bandwidth spent.
# PDFs arrive as pointer files; everything except extraction still works.
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/spicysauce1955-stack/fence-rag.git

# Then pull only the part of the corpus you actually need:
git lfs pull --include="manuals/certainteed-bufftech/**"   # ~79 MB
git lfs pull --include="**/structural/**"                  # ~109 MB, every NOA and PE letter
git lfs pull --include="china/**"                          #  ~35 MB
git lfs pull                                               # ~432 MB, everything
```

Fetching only the Bufftech vertical slice costs **111 MB — nine clones a month
instead of two.** `workspace/catalog/slice-bufftech-extruded-pvc.jsonl` lists
exactly which files that is.

Rules of thumb that keep the allowance intact:

- **Never let CI or an agent do a full clone.** `GIT_LFS_SKIP_SMUDGE=1` plus a
  targeted `git lfs pull` is always the right shape. A job that clones the
  corpus on every run burns the monthly budget in a day.
- **Re-clone rarely.** `git pull` on an existing checkout transfers only changed
  objects, and the corpus is read-only, so it never changes.
- **Adding a PDF spends quota twice** — once on storage forever, once on
  bandwidth for everyone who fetches it. Check whether the document is actually
  needed before committing it.
- `du -sh .git/lfs` shows what your checkout is holding;
  `git lfs prune` reclaims objects no longer referenced by a recent commit.

The corpus is immutable input, so nothing here is versioned in a way that
benefits from git. If the allowance ever becomes a real constraint, the exit is
to publish the corpus as a GitHub Release asset — release downloads are not
metered like LFS — and fetch it against the SHA-256 already recorded for every
file in `workspace/catalog/corpus-manifest.jsonl`.

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
python3 -m fence_evidence.cli audit                     # relevance audit of the index
python3 -m fence_evidence.cli noa-table-crops           # crops for the unreadable table pages
python3 -m fence_evidence.cli resolve 23-0314.05 --as-of 2026-08-20
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
| `docs/second-stage-evaluation.md` | within-page retrieval: measurement and the decision not to default it on |
| `docs/experiment-noa-table-reading.md` | designed, not run: per-cell reading of the 73 scanned table pages |
| `workspace/reports/projection-relevance-audit.md` | relevance audit of the index; recommendations not applied |
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
