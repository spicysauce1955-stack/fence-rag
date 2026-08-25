# Fence Evidence System

A source-preserving evidence store and lexical retrieval layer over the vinyl
fence document corpus in this repository — 137 PDFs, 6 CAD images and one DOCX
specification, 2147 pages (2140 of them PDF), including the Miami-Dade NOA
packages that carry the PE-sealed wind-load and footing tables.

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

The corpus is published to public object storage: **128 content-addressed
objects, 376.5 MB**, at `https://pub-3731f1c7bf1e4e1db0d1ad0db83f2b9f.r2.dev/`.
`cli fetch` pulls it from there, anonymously — no account, no token, no SDK,
just an HTTPS GET per object. **That is the documented path, and it is the one
to use.** R2 charges no egress fee, so fetching costs the maintainer nothing:
there is no allowance to exhaust, no shared budget to be sparing with, and
nothing you can do here that makes reads fail for anyone else.

```bash
# 1. Configure Git LFS once per machine. Installing the binary is not enough —
#    `git lfs install` is what registers the filters, and step 5 is unsafe
#    without them. Skip only if you have run it before on this machine.
git lfs install

# 2. Code, docs and datasets only — ~9 MB, no LFS bandwidth spent.
#    The PDFs arrive as pointer files; step 4 replaces them with real bytes.
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/spicysauce1955-stack/fence-rag.git
cd fence-rag

# 3. Prerequisites: poppler, tesseract, and pdfplumber into workspace/pylibs/.
scripts/bootstrap.sh

# 4. The corpus — all of it, or just the part you need.
python3 -m fence_evidence.cli fetch --subset structural   #  32 files,  73.5 MB
python3 -m fence_evidence.cli fetch --subset bufftech     #  14 files,  78.5 MB
python3 -m fence_evidence.cli fetch --subset china        #   4 files,  35.4 MB
python3 -m fence_evidence.cli fetch --subset all          # 144 files, 376.5 MB

# 5. Tell git the fetched bytes are what the pointers stood for.
#    Requires step 1. Check first: `git config filter.lfs.clean` must print
#    something. If it prints nothing, STOP and read the warning below.
git add --renormalize .
```

Run every command from the repository root. `fence_evidence/` sits there and is
not installed, so `python3 -m fence_evidence.cli …` resolves through the working
directory — from any other directory it will not import.

Step 5 is not optional bookkeeping. `git status` records each file's size and
mtime when it is checked out, and at clone time every PDF was a 131-byte
pointer, so after fetching, git lists all 137 of them as modified even though
`git diff` is empty and the content is byte-for-byte correct. `--renormalize`
re-reads them through the LFS clean filter, which turns each one back into the
pointer already in the index, and `git status` goes quiet. Without it the
obvious tidy-up — `git checkout .` or "discard changes" in an editor — silently
reverts the whole corpus to pointers.

> **Do not run step 5 if `git config filter.lfs.clean` prints nothing.** That
> means `git lfs install` has never been run on this machine, so git does not
> know what `filter=lfs` in `.gitattributes` means and skips the clean filter
> entirely. `--renormalize` would then stage 376 MB of raw PDF as ordinary git
> blobs, and committing that pushes the whole corpus into git history outside
> LFS — permanently. Run `git lfs install` first (or `git lfs install --local`
> to confine it to this repository), then step 5. If the `git-lfs` binary is not
> available at all, skip step 5 and live with the noisy `git status`; the
> fetched files are correct either way.

| subset | what it is | files | objects | bytes |
|---|---|---:|---:|---:|
| `structural` | every NOA, PE letter and CAD detail sheet | 32 | 28 | 73.5 MB |
| `bufftech` | the CertainTeed Bufftech vertical slice | 14 | 14 | 78.5 MB |
| `china` | the China track, in full | 4 | 4 | 35.4 MB |
| `all` | the whole corpus | 144 | 128 | 376.5 MB |

Files exceed objects because 14 groups of byte-identical files are filed under
different manufacturers. Objects are keyed by content hash, so each is
transferred once and copied to its siblings — `--subset all` moves 376.5 MB
over the wire, not the 432 MB the paths add up to.

Every object is verified against the SHA-256 that is also its key before it
lands; a mismatch fails the run rather than writing a bad file. `fetch` is
idempotent — a second run transfers nothing — so it is also the repair path for
a corrupted or half-fetched checkout. `--workers N` sets the download pool, and
`--manifest-url` points at a different manifest. Sizes and hashes come from
`workspace/catalog/distribution-manifest.json`, which is generated from
`corpus-manifest.jsonl` and committed.

`workspace/catalog/slice-bufftech-extruded-pvc.jsonl` lists exactly which files
the Bufftech slice is, if you want to see before you fetch.

The subsets are for reading a slice of the corpus, not for running the pipeline.
**The quick start below needs `--subset all`**: the 10 pilot documents are spread
across seven manufacturers, the gold question set draws on the whole corpus, and
no subset covers either. Anything still held as a pointer is recorded as
`not-fetched`, refused by `ingest`, and warned about by `evaluate` and `audit` —
so a partial fetch will not corrupt your store, but it will not run the pipeline
either.

### Fallback: Git LFS

The PDFs are still in Git LFS and `git lfs pull` still works. Nothing here
depends on it, and **you should not use it unless `cli fetch` is unavailable to
you** — a proxy that blocks the R2 host, an air-gapped mirror of the git
repository, or a bucket outage.

The reason is a budget that `cli fetch` does not touch. The corpus is 431 MB of
files, 361 MB of unique objects after LFS dedupes the 14 byte-identical groups.
On GitHub's free tier that is 36% of the 1 GB storage allowance and, more
importantly, **1 GB of bandwidth per month — about 2.3 full clones.** The
allowance is shared by everyone who clones, the repository is public, and when
it is exhausted LFS reads are blocked for everyone including the owner until
the month rolls over or someone buys a data pack.

```bash
git lfs pull --include="manuals/certainteed-bufftech/**"   # ~79 MB
git lfs pull --include="**/structural/**"                  # ~109 MB, every NOA and PE letter
git lfs pull --include="china/**"                          #  ~35 MB
git lfs pull                                               # ~432 MB, everything
```

Those globs are not the same sets as the `fetch` subsets — `**/structural/**`
matches a wider set of paths than the manifest's `structural` predicate, which
is why the sizes differ.

If you do end up on this path:

- **Never let CI or an agent do a full clone.** `GIT_LFS_SKIP_SMUDGE=1` plus a
  targeted `git lfs pull` is always the right shape. A job that clones the
  corpus on every run burns the monthly budget in a day.
- **Re-clone rarely.** `git pull` on an existing checkout transfers only changed
  objects, and the corpus is read-only, so it never changes.
- **Adding a PDF spends quota twice** — once on storage forever, once on
  bandwidth for everyone who fetches it. Check whether the document is actually
  needed before committing it, and re-run `cli publish` so R2 mirrors it.
- `du -sh .git/lfs` shows what your checkout is holding;
  `git lfs prune` reclaims objects no longer referenced by a recent commit.

`docs/distribution-design.md` records why the corpus is hosted this way and
what the arrangement still does not solve.

### Publishing (maintainer only)

Consuming the corpus is anonymous and needs no credentials. Uploading it does:
`cli publish` reads Cloudflare R2 keys from a git-ignored `.env`, for which
`.env.example` is the annotated template — `cp .env.example .env` and fill it
in. Nothing else in the repository reads `.env`, so if you are not the person
who owns the bucket you can ignore both files.

## Quick start

No installation is required; the pipeline runs on the standard library plus
poppler and tesseract. `pdfplumber` is optional and, when present, is loaded
from `workspace/pylibs/`. Run these from the repository root.

```bash
python3 -m fence_evidence.cli fetch --subset all  # the corpus, if you skipped it above
python3 -m fence_evidence.cli manifest          # Phase 0: inspect the corpus
python3 -m fence_evidence.cli ingest --pilot    # Phase 1: 10-document pilot
python3 tests/run_tests.py                      # preservation + contract gates (a)
python3 -m fence_evidence.cli evaluate          # Phase 4: gold question set
python3 -m fence_evidence.cli ingest --all      # Phase 5: full corpus
python3 -m fence_evidence.cli facts --extract   # Phase 6: structured facts
python3 -m fence_evidence.cli report            # regenerate workspace reports
```

(a) Run in this order, `run_tests.py` reports `OK` with about 22 skips: those
tests assert about documents outside the 10-document pilot, or about facts
Phase 6 has not extracted yet. Each skip names the command that unlocks it, and
they all run once `ingest --all` and `facts --extract` have. Use
`tests/run_tests.py` rather than a bare `python3 -m unittest` from `tests/` —
only the runner reports those as skips instead of failures.

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

The corpus is read-only, enforced in code: every pipeline write goes through
`fence_evidence.paths.ensure_writable`, which refuses any path outside
`workspace/`. The single exception is `cli fetch`, which has to populate the
corpus the way `git lfs pull` does; it writes through `paths.fetch_target`
instead, which accepts only a non-symlinked path inside a corpus root that the
distribution manifest names, and `tests/test_safety.py` asserts no other module
can reach it. Document content is data and is never executed — external tools
are always invoked with argument lists, never a shell. OCR text is stored beside
source text, never over it. Superseded approvals stay separate records, linked
by a relation. Byte-identical files filed under different manufacturers are
linked, never deduplicated. Measurements keep their original wording alongside
any normalised value. No technical value is returned without its document, page
and element.
