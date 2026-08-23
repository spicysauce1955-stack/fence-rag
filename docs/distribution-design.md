# Distribution design — public object storage for the corpus

```text
Status: Implemented. Tasks 1-8 built, tested, and the corpus is published.
Scope:  how a checkout obtains the corpus.
        Not a change to extraction, retrieval, ranking or the fact layer.
Built:  128 content-addressed objects / 376,489,773 bytes live in public
        R2; `cli fetch` is verified end-to-end against that bucket and is
        the documented way to obtain the corpus (README, bootstrap.sh).
Cut:    hosting a prebuilt evidence.db, and the `--build`/`--verify` flags
        this document once advertised. Descoped 2026-08-23; see §8.
```

## 1. Problem, measured

A fresh clone does not work as documented. Measured on 2026-08-23:

| What a cloner receives | |
|---|---|
| tracked under `workspace/` | `catalog/` (4 files), `reports/` (14), `tests/` (11) |
| `workspace/pylibs/` | **git-ignored** — 57 MB of vendored `pdfplumber` absent |
| `workspace/derived/` | **git-ignored** — 4.5 GB of page images absent |
| `workspace/indexes/` | **git-ignored** — the 60 MB `evidence.db` absent |
| corpus PDFs | present, but only by spending LFS bandwidth |

Four consequences, in order of how quietly they fail:

1. **`pylibs/` is absent and nothing says so.** `README.md` states the pipeline
   runs "on the standard library plus `pdfplumber` … from `workspace/pylibs/`"
   without saying how it gets there. Without it the table backend silently
   degrades to `fallback-whitespace`. No error is raised. This is the worst of
   the four because the result is a quieter, worse store rather than a failure.
2. **poppler and tesseract are undocumented hard prerequisites.** `tools.py`
   shells out to `pdftotext`, `pdftoppm`, `pdfinfo` and `tesseract`.
3. **LFS bandwidth is billed to the repository owner.** 1 GB/month against a
   431 MB corpus is ~2.3 full clones *from anyone on earth*, and the repository
   is public. When the allowance is exhausted, LFS reads fail for everyone,
   including the owner.
4. **Re-extraction is not reproducible across environments.** The byte-identical
   rebuild test covers `retrieval_units` rebuilt from canonical rows; it does
   not cover re-extraction. OCR text depends on tesseract 5.3.4 and page images
   on poppler 24.02.0. Every published measurement — evidence support 0.623,
   OCR mean confidence 77.0% — was produced on that toolchain.

`README.md` already named the exit: *"publish the corpus … and fetch it against
the SHA-256 already recorded for every file in
`workspace/catalog/corpus-manifest.jsonl`."* This document adopted that plan and
chose the store; that passage has since been replaced by the `cli fetch`
instructions it was anticipating.

## 2. What is stored, and what is never stored

| Artifact | Size | Hosted? | Why |
|---|---|---|---|
| corpus files (137 PDFs, 6 PNGs, 1 DOCX) | 144 rows, **128 unique objects, 376.5 MB** | **yes** | the only irreplaceable bytes |
| `evidence.db` | 60 MB | **no** | considered, descoped; see §8 |
| `workspace/derived/` | 4.5 GB | **never** | deterministic renders of PDF pages; see §6 |
| `workspace/pylibs/` | 57 MB | **never** | vendored from PyPI by `bootstrap.sh` |

**Hosted total: 376,489,773 bytes**, against Cloudflare R2's 10 GB free tier.
The 4.5 GB — the number that makes hosting sound infeasible — is the one thing
that must not be hosted. The corpus is the only thing that *is*: everything
else in the table is either reconstructible from it or fetched from PyPI.

The gap between 144 rows and 128 objects is the point of §3: the corpus contains
**14 groups of byte-identical files filed under different manufacturers** (30
files, 16 redundant copies, 55.5 MB). Content-addressed storage stores each once,
and the saving falls out of the key scheme rather than needing a dedupe pass.

All sizes above are measured from `corpus-manifest.jsonl`, summing
`file_size_bytes` over distinct `sha256`.

## 3. Bucket layout

Content-addressed, so the 14 duplicate groups cost storage once and every object
is self-verifying:

```text
r2://fence-rag/
  objects/<sha256>                    137 PDFs + 6 PNGs + 1 DOCX, deduped to 128 objects
  distribution-manifest.json          the index; see §4
```

That is the whole bucket. Two objects and nothing else: the content-addressed
corpus, and the manifest that indexes it.

Access model: **public-read, anonymous.** A consumer needs no account, no token
and no SDK — a plain HTTPS `GET` per object, which the standard library can
issue. Writes require R2 credentials held only by the maintainer. This is what
makes "anyone can clone and use this" true.

Object keys are content hashes, never source paths, because:

- the same bytes filed under `certainteed-bufftech/` and
  `freedom-outdoor-living/` resolve to one object;
- an object can never be silently replaced — a changed file is a new key;
- integrity checking is inherent rather than bolted on.

## 4. The fetch manifest

`workspace/catalog/corpus-manifest.jsonl` already carries `source_path`,
`sha256`, `file_size_bytes`, `manufacturer`, `doc_type` and `structural` for all
144 files. It is already a download manifest. The distribution manifest is a
generated projection of it — never hand-edited, regenerated by
`cli publish --manifest`:

```json
{
  "schema": 1,
  "generated_at": "…",
  "base_url": "https://<public-r2-host>/",
  "subsets": {
    "structural":  {"files": 32, "unique": 28, "bytes":  73500000},
    "bufftech":    {"files": 14, "unique": 14, "bytes":  78500000},
    "china":       {"files":  4, "unique":  4, "bytes":  35400000},
    "all":         {"files": 144, "unique": 128, "bytes": 376500000}
  },
  "files": [
    {"source_path": "manuals/…/NOA-23-0314.05….pdf",
     "sha256": "0f983c…", "bytes": 2027930, "subsets": ["structural", "bufftech", "all"]}
  ]
}
```

Subsets are defined by **predicates over manifest fields**, never by a hand-kept
list, so they cannot drift from the corpus:

| subset | predicate | files | unique | bytes |
|---|---|---|---|---|
| `all` | everything | 144 | 128 | 376.5 MB |
| `structural` | `structural_subdir == true` | 32 | 28 | 73.5 MB |
| `bufftech` | `source_path` prefix `manuals/certainteed-bufftech/` | 14 | 14 | 78.5 MB |
| `china` | `source_path` prefix `china/` | 4 | 4 | 35.4 MB |

Note the field is `structural_subdir`, not `structural` — the latter exists on
the `documents` table but not in the manifest. `README.md` quotes a 109 MB figure
for `**/structural/**`; that is an LFS glob over a wider set of paths than the
manifest predicate, and the two are not interchangeable.

## 5. Client — `cli fetch`

```bash
python3 -m fence_evidence.cli fetch --subset structural   #  32 files,  73.5 MB
python3 -m fence_evidence.cli fetch --subset bufftech     #  14 files,  78.5 MB
python3 -m fence_evidence.cli fetch --subset china        #   4 files,  35.4 MB
python3 -m fence_evidence.cli fetch --subset all          # 144 files, 376.5 MB
```

Three flags, and no others: `--subset` (default `all`), `--manifest-url` (a
manifest other than the committed one, also settable as `FENCE_RAG_MANIFEST_URL`)
and `--workers` (download pool size, default 4).

Behaviour:

- **Writes only into the corpus paths the manifest names.**
  `paths.ensure_writable` guards the workspace, not the corpus, so `fetch` has
  its own explicit guard, `paths.fetch_target`: a target must resolve inside a
  corpus root, appear in the manifest, and contain no symlinked component.
  Every target is resolved through it *before the first byte transfers*, so a
  manifest naming a path outside the corpus fails the run rather than being
  reported as one object's failure. `tests/test_safety.py` asserts no module
  other than `paths.py`, `fetch.py` and `cli.py` can even reach that function.
- **Verifies every object against its key** before moving it into place.
  Download to a temp file under `workspace/`, hash, compare to the key, then
  rename. A mismatch is an error, never a warning.
- **Transfers each object once, not each path.** Targets are grouped by
  `sha256`; the first path in a group is downloaded and the rest are copied
  from it, re-hashed on the way. This is the same saving §3's key scheme takes
  on the way up. Iterating paths instead cost 55.5 MB on `--subset all` and 48%
  on `--subset structural`.
- **Resumable and idempotent.** Re-running fetches nothing already present —
  and since it hashes every target it finds on disk, a plain re-run *is* the
  verification pass: it reports `already_present` for each path whose bytes
  match the manifest, and repairs any that do not.
- **Standard library only** — `urllib.request`. No boto3, no SDK. Consistent
  with the existing rule that every third-party package stays optional.
- **Parallel with a small pool** (4), because 128 objects at 3 MB average over
  one connection is needlessly slow.

The returned counts distinguish paths from objects, because they now differ:
`requested`, `already_present`, `copied` and `failed` count paths and partition
`requested`; `objects` counts distinct hashes, and `downloaded` and `bytes`
count what actually crossed the wire.

## 6. Page images on demand — `derived/` becomes a cache

This is what keeps 4.5 GB off the wire, and it is the only change here that
touches existing code.

`page_image_path` and `region_image_path` are stable identifiers in the store and
**do not change**. What changes is that five call sites currently resolve them by
string-joining `REPO_ROOT` and assuming the file exists:

```text
retrieval.py:401,485   noa_tables.py:120   facts.py:226
evaluate.py:213        extract.py:402
```

Introduce one resolver that all five route through:

```python
def resolve_asset(rel_path: str) -> Path | None:
    """Return a local path for a derived asset, materialising it if absent."""
```

Resolution order: local cache hit → render from the source → `None`. The
source is a PDF for 2,140 of 2,147 pages, rendered with `pdftoppm` at the DPI
recorded on the `pages` row, giving the same bytes the ingest would have
written. Six pages — the CAD sheets under `manuals/*/structural/` whose source
is a `.png` — are materialised from that PNG instead, since there is no PDF to
render. `None` is a legitimate outcome for the remaining page, the DOCX, which
has no image at all; `evaluate.py:213` and the retrieval contract test already
tolerate that.

Consequence worth stating plainly: a consumer who fetches a subset gets page
images only for the documents in that subset. Outside it there is text evidence
and no picture. That is a real reduction in what this system promises, and it is
why `--subset structural` exists — the documents where the image *is* the
evidence are exactly the scanned NOA sheets.

## 7. Migration — LFS stays

**Git history is not rewritten.** Removing the PDFs from LFS history would be
disruptive, would break every existing checkout, and buys nothing: the objects
are already uploaded and the storage allowance is not the binding constraint,
the *bandwidth* allowance is.

Instead:

1. Publish to R2 and generate the distribution manifest. **Done** — 128
   objects, 376,489,773 bytes.
2. Change `README.md` so the documented path is `bootstrap.sh` + `cli fetch`.
   LFS becomes an unexercised fallback. **Done** — `README.md`, `CLAUDE.md`
   and `scripts/bootstrap.sh` all lead with `cli fetch` and keep the LFS
   instructions, labelled as a fallback with the bandwidth warning intact.
3. Leave `.gitattributes` untouched. A future PDF still lands in LFS; `cli
   publish` mirrors it. **Done** — untouched.

Bandwidth stops being spent because nobody follows the LFS path any more, not
because the LFS path was removed. Step 2 is the step that actually saves the
bandwidth: without it the objects sit in R2 and the allowance is spent at
exactly the old rate.

## 8. What this does not solve

- **Hosting the built `evidence.db`. Considered, and descoped on 2026-08-23.**
  §2, §3 and §5 of this document originally carried a
  `builds/<extraction_run_id>/evidence.db.zst` object (~18 MB from 60 MB), a
  sibling `manifest.json` recording toolchain versions and row counts, and the
  flags `cli fetch --build latest` and `cli fetch --verify`. None of it was
  built and none of it should be, for two reasons.

  It is a second feature, not part of this one. Everything above is about
  obtaining *source bytes* the consumer cannot otherwise get; a prebuilt store
  is a convenience over bytes they can already derive themselves, with its own
  staleness, versioning and trust questions — a store you did not build is a
  store you are trusting the maintainer about, which is the opposite of what a
  content-addressed corpus buys.

  And compression: zstd reached the standard library only in Python 3.14, as
  `compression.zstd`. On the interpreters this project targets it needs a
  vendored third-party package — against the first constraint in `guide.md`,
  that every third-party dependency stays optional. Shipping the store
  uncompressed at 60 MB, or falling back to `lzma`, would be trading the
  project's cleanest rule for a convenience.

  `--verify` needs no replacement: `cli fetch` hashes every target it finds on
  disk, so re-running it verifies the checkout and repairs it in one pass.

  Recorded here rather than deleted, so the option can be re-opened
  deliberately — most plausibly once 3.14 is a safe floor.

- **Reproducibility of extraction.** Unchanged by this design, and no longer
  even mitigated: hosting a prebuilt `evidence.db` would have let a consumer
  *avoid* the divergence without fixing it, and that is now descoped. What
  remains is `bootstrap.sh`, which reports the local poppler and tesseract
  versions and warns when they differ from the reference toolchain (poppler
  24.02.0, tesseract 5.3.4) that produced every published measurement.
- **Preservation.** R2 is a second copy, which is strictly better than one, but
  two copies under one owner's control is not an archive. Unchanged by this
  design and deferred by the user on 2026-08-23.
- **Redistribution posture.** Publishing to an anonymous public bucket makes
  redistribution explicit in a way LFS-behind-a-repo does not. Miami-Dade NOAs
  are public records; manufacturer catalogues and install guides are not. This
  is a decision for the maintainer, recorded here so it is not made by accident.

## 9. Acceptance criteria

| # | Criterion |
|---|---|
| D1 | On a machine with no checkout, `bootstrap.sh` reports every missing prerequisite by name and exits non-zero rather than degrading silently |
| D2 | `GIT_LFS_SKIP_SMUDGE=1` clone + `cli fetch --subset structural` + `ingest` yields a working `search` with page-image evidence for every structural result, spending **zero** LFS bandwidth |
| D3 | Every fetched object's SHA-256 matches its key; a corrupted download fails the run rather than landing on disk |
| D4 | `cli fetch` is idempotent — a second run transfers zero bytes |
| D5 | `resolve_asset` returns byte-identical images to those `ingest` writes, asserted against the existing derived store for a sample of 20 pages |
| D6 | Deleting `workspace/derived/` entirely does not change any evaluation number |
| D7 | `cli fetch` writes only to paths named in the distribution manifest; an attempt to write elsewhere raises |

D2 was restated on 2026-08-23. It named `cli fetch --build latest`, which was
descoped (§8) and can therefore never be satisfied as written. The consumer
still has to build the store — that is what `ingest` is doing in the criterion
— and the point being tested is unchanged and is met: source bytes and page
images both arrive without touching LFS.

D6 is the criterion that proves `derived/` is a cache rather than a data source.
It is also the cheapest to run and should be run first.

**D6: measured 2026-08-23. Pass.** `cli evaluate` was run with `workspace/derived/`
intact, then again with the directory moved aside (not deleted, so the run could
be restored rather than rebuilt) so every page image the evaluation touched had
to be rendered on demand through `resolve_asset`. The two pretty-printed JSON
outputs were diffed field for field, including the per-category breakdown and
`false_unsupported_ids`: **zero differences.**

```
recall_at_k              0.805
page_recall_at_k         0.659
mrr                      0.552
evidence_support         0.623
page_evidence_support    0.769
no_answer_precision      0.333
false_unsupported_rate   0.146
passed                   27 of 59 (41 answerable, 18 no-answer)
```

These match the figures already published in `docs/state-and-gaps.md` exactly,
which independently confirms the baseline run was trustworthy.

With `derived/` absent, the on-demand renders regenerated 462 MB of the 4.5 GB
store — roughly 10% of the cache is what an evaluation run actually touches,
which bounds the real cost of a cold cache for a consumer who never fetches a
page image.
