# Environment report

Measured on the machine that produced this workspace. Everything below was
probed, not assumed.

## Platform

| Property | Value |
|---|---|
| python | 3.12.3 |
| platform | Linux-6.17.0-20-generic-x86_64-with-glibc2.39 |
| cpu count | 24 |
| disk needed for a full run | ~6 GB writable under `workspace/` |
| pipeline version | 1.0.0 |

Free space is stated as a requirement, not probed. This file is committed, and a
`disk free` reading rewrote that row on every `cli report` run -- a tree that is
dirty for no content reason invites the tidy-up G28 measured, where `git checkout .`
reverts 137 PDFs to LFS pointers. The requirement is the half a reader needs and the
half that does not move: ~6 GB for `workspace/derived` (page images and region
crops) plus the SQLite store and its FTS5 index, and ~0.4 GB for the fetched
corpus. Whether this machine has that room is a question for `df -h .` now, not
for this file as of whenever it was last written.

## Extraction tools

| Tool | Version | Role |
|---|---|---|
| pdftotext | pdftotext version 24.02.0 | text layer + word bounding boxes (`-bbox-layout`) |
| pdftoppm | pdftoppm version 24.02.0 | page images (evidence) and OCR renders |
| pdfinfo | pdfinfo version 24.02.0 | page count, page size, per-page rotation, encryption |
| tesseract | tesseract 5.3.4 | OCR with word boxes and confidence (hOCR) |
| pillow | 10.2.0 | region crops from page images |
| pdfplumber | 0.11.10 | **optional** table cells, raster/vector figure geometry |
| sqlite3 FTS5 | stdlib | the lexical index; no external service |

## Permission boundaries actually in force

- No passwordless `sudo` and no `apt`: system packages could not be installed.
  Every tool above was already present.
- No system `pip`, and the interpreter is PEP 668 externally managed. Third-party
  Python packages are therefore installed into `workspace/pylibs/` (git-ignored)
  and loaded by `fence_evidence/__init__.py`. Nothing is written to system paths.
- `pdfplumber` is the only third-party package used, and it is optional: without it
  the pipeline still runs and records `fallback-whitespace` as the table backend.
- Network is used only to fetch that package. The pipeline performs no network I/O.
- The corpus is read-only and enforced in code by `paths.ensure_writable`.

## Reproducibility

```bash
python3 -m fence_evidence.cli manifest      # Phase 0
python3 -m fence_evidence.cli ingest --pilot
python3 tests/run_tests.py                  # preservation + contract gates
python3 -m fence_evidence.cli evaluate      # Phase 4
python3 -m fence_evidence.cli ingest --all  # Phase 5
python3 -m fence_evidence.cli facts --extract
```
