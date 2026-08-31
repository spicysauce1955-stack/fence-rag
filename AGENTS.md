# Repository Guidelines

## Project Structure & Module Organization

`fence_evidence/` contains the Python evidence system and CLI. The package is not installed; run module commands from the repository root so imports resolve. `tests/` holds stdlib `unittest` tests named `test_*.py`. `data/` and `data/structural/` contain the US/Western datasets; `china/` is the separate China track. `manuals/` and `china/manuals/` are the source corpus. `docs/` records architecture, integration contracts, curation plans, and status. `workspace/` contains generated indexes, reports, crops, snapshots, and test outputs; most large derived files are git-ignored.

## Build, Test, and Development Commands

There is no package build step or requirements file. The pipeline uses Python 3.10+, poppler, tesseract, and optional `pdfplumber` vendored into `workspace/pylibs/`.

- `scripts/bootstrap.sh`: check external tools and vendor optional extraction dependencies.
- `python3 -m fence_evidence.cli fetch --subset all`: fetch the corpus from public object storage.
- `python3 -m fence_evidence.cli manifest`: rebuild the corpus manifest.
- `python3 -m fence_evidence.cli ingest --pilot`: ingest the 10-document pilot.
- `python3 -m fence_evidence.cli evaluate`: run the gold question evaluation.
- `python3 tests/run_tests.py`: run the full test suite with repository-aware skips.
- `python3 scripts/build_master.py`: regenerate `master-dataset.json` and `data/documents-index.json` after dataset edits.
- `python3 scripts/build_china.py`: regenerate China aggregate outputs.

## Coding Style & Naming Conventions

Use 4-space indentation, descriptive snake_case names for functions and variables, and PascalCase for test classes. Prefer standard-library code and existing helpers over new dependencies. Keep comments short and limited to non-obvious constraints. Preserve provenance fields such as `_research_note`, `remaining_gaps`, and `not_found` when editing JSON.

## Testing Guidelines

Tests use `unittest`. Add focused `tests/test_*.py` coverage for behavior changes, especially migrations, extraction, retrieval, generated data contracts, and source-preservation rules. Prefer `python3 tests/run_tests.py` for the full suite because it reports missing-corpus or missing-store cases as skips. For a single test, use `cd tests && python3 -m unittest test_lang -v`.

## Commit & Pull Request Guidelines

Recent commits use concise sentence-style messages, sometimes with scoped prefixes such as `Fix:`, `A5:`, or `K3:`. Keep subjects specific to the behavioral or data change. Pull requests should describe the change, list commands run, note corpus subset assumptions, and call out regenerated artifacts.

## Security & Configuration Tips

Never commit `.env` files or credentials; use `.env.example` only as a template. Do not use Git LFS for routine corpus fetching from automation; prefer `cli fetch`. Treat `docs/integration/contract.md` and `AMENDING.md` as controlled boundary documents.
