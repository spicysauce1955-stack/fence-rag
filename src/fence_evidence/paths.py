"""Repository paths and the read-only corpus guard.

Prohibition 1 of the implementation spec: the ingestion system must never
modify, rename, deduplicate or delete an original source file.  Every write
in this package goes through :func:`ensure_writable`, which refuses any path
that is not inside ``workspace/``.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# --- read-only corpus roots -------------------------------------------------
CORPUS_ROOTS = (
    REPO_ROOT / "manuals",
    REPO_ROOT / "china" / "manuals",
)
DATA_ROOTS = (
    REPO_ROOT / "data",
    REPO_ROOT / "china" / "data",
    REPO_ROOT / "schema",
)
DOCUMENT_INDEXES = (
    REPO_ROOT / "data" / "documents-index.json",
    REPO_ROOT / "china" / "data" / "china-documents-index.json",
)

# --- writable workspace -----------------------------------------------------
WORKSPACE = REPO_ROOT / "workspace"
CATALOG_DIR = WORKSPACE / "catalog"
DERIVED_DIR = WORKSPACE / "derived"
INDEX_DIR = WORKSPACE / "indexes"
REPORTS_DIR = WORKSPACE / "reports"
TESTS_DIR = WORKSPACE / "tests"

EVIDENCE_DB = INDEX_DIR / "evidence.db"
MANIFEST_PATH = CATALOG_DIR / "corpus-manifest.jsonl"
GOLD_SET_PATH = REPO_ROOT / "eval" / "gold-questions.json"


class CorpusWriteError(RuntimeError):
    """Raised when something attempts to write outside workspace/."""


def ensure_writable(path: os.PathLike | str) -> Path:
    """Return ``path`` if it is inside workspace/, else raise.

    Any code path that opens a file for writing must call this first.
    """
    p = Path(path).resolve()
    try:
        p.relative_to(WORKSPACE.resolve())
    except ValueError:
        raise CorpusWriteError(
            f"refusing to write outside the workspace: {p}\n"
            f"the corpus and dataset are read-only; workspace is {WORKSPACE}"
        ) from None
    return p


def fetch_target(path: os.PathLike | str, allowed: set[str]) -> Path:
    """Return ``path`` if it is a corpus file the distribution manifest names.

    This is the ONE exception to the read-only corpus rule, and it exists only
    so `cli fetch` can populate a checkout the way `git lfs pull` does. It is
    not pipeline code: `tests/test_safety.py` asserts that no module other than
    fetch.py and cli.py references it.

    Three conditions, all required:
      1. the path resolves inside a corpus root;
      2. its repo-relative form appears in ``allowed`` (the manifest);
      3. no component is a symlink.
    """
    p = Path(path)
    for parent in (p, *p.parents):
        if parent.is_symlink():
            raise CorpusWriteError(f"refusing to write through a symlink: {parent}")
    resolved = p.resolve()
    try:
        relative = resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        raise CorpusWriteError(f"refusing to write outside the repository: {resolved}") from None
    if not any(_is_within(resolved, root) for root in CORPUS_ROOTS):
        raise CorpusWriteError(f"not a corpus path: {relative}")
    if relative not in allowed:
        raise CorpusWriteError(
            f"{relative} is not listed in the distribution manifest; refusing to write")
    return resolved


def _is_within(child: Path, root: Path) -> bool:
    try:
        child.relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def open_write(path: os.PathLike | str, mode: str = "w", **kw):
    """open() for writing, guarded by :func:`ensure_writable`."""
    if "r" in mode and "+" not in mode:
        raise ValueError("open_write is for writing modes only")
    p = ensure_writable(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return open(p, mode, **kw)


def rel(path: os.PathLike | str) -> str:
    """Path relative to the repository root, for provenance records."""
    return os.path.relpath(Path(path).resolve(), REPO_ROOT)


def init_workspace() -> None:
    for d in (CATALOG_DIR, DERIVED_DIR, INDEX_DIR, REPORTS_DIR, TESTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
