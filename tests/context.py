"""Shared test setup: put src/ on the path and expose common helpers."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fence_evidence.paths import (EVIDENCE_DB, TESTS_DIR,  # noqa: E402
                                  is_lfs_pointer)


def _scan_corpus() -> bool:
    """True when every corpus PDF is real bytes, not an unsmudged LFS pointer.

    Checks all of them rather than probing one: the publish dry-run tests hash
    every row in the manifest, so a partial fetch would let them run and then
    fail on the first file still held as a pointer.
    """
    roots = (ROOT / "manuals", ROOT / "china" / "manuals")
    found = False
    for root in roots:
        for pdf in root.rglob("*.pdf"):
            found = True
            if is_lfs_pointer(pdf):
                return False
    return found


_CORPUS_FETCHED: "bool | None" = None


def _corpus_is_fetched() -> bool:
    """Cached: the decorators below run at import, once per test module."""
    global _CORPUS_FETCHED
    if _CORPUS_FETCHED is None:
        _CORPUS_FETCHED = _scan_corpus()
    return _CORPUS_FETCHED


def requires_store(test):
    """Skip a test when there is no evidence store worth asserting against.

    The store file existing is not enough. An ingest attempted on an unfetched
    checkout leaves a real database holding only the DOCX and the CAD PNGs --
    the two file types Git LFS does not track -- and every test that asks it
    about a PDF then fails, pointing at the pipeline rather than at the missing
    corpus. Require both, so the diagnosis stays "you have not fetched the
    corpus" instead of nineteen failures and ten errors.
    """
    return unittest.skipUnless(
        EVIDENCE_DB.is_file() and _corpus_is_fetched(),
        "evidence store not built over a fetched corpus; run "
        "`cli fetch --subset all` then `cli ingest --pilot`")(test)


def _store_counts() -> "tuple[int, int]":
    """(documents, facts) in the store, or (0, 0) if there is no store."""
    if not EVIDENCE_DB.is_file():
        return (0, 0)
    import sqlite3
    try:
        conn = sqlite3.connect(f"file:{EVIDENCE_DB}?mode=ro", uri=True)
    except sqlite3.Error:
        return (0, 0)
    try:
        def count(table):
            try:
                return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.Error:
                return 0
        return (count("documents"), count("facts"))
    finally:
        conn.close()


# The pilot is 10 documents; the corpus is 144. Anything materially above the
# pilot means `ingest --all` has run.
_PILOT_DOCUMENTS = 10


def requires_full_store(test):
    """Skip a test that asserts about a document outside the 10-document pilot.

    README order is `ingest --pilot` then `run_tests.py`, so this is the normal
    state for someone setting the project up, not an edge case. Without this
    the suite reported failures naming documents the user had been told not to
    ingest yet.
    """
    docs, _ = _store_counts()
    return unittest.skipUnless(
        docs > _PILOT_DOCUMENTS and _corpus_is_fetched(),
        f"store holds {docs} documents (pilot or less); run `cli ingest --all`")(test)


def requires_facts(test):
    """Skip a test that needs Phase 6 output; `cli facts --extract` builds it."""
    docs, facts = _store_counts()
    return unittest.skipUnless(
        facts > 0 and docs > _PILOT_DOCUMENTS and _corpus_is_fetched(),
        f"store holds {facts} facts; run `cli ingest --all` then "
        f"`cli facts --extract`")(test)


def requires_corpus(test):
    """Skip a test that needs corpus bytes on disk.

    A `GIT_LFS_SKIP_SMUDGE=1` clone leaves every PDF as a ~131-byte pointer, so
    anything that shells out to poppler or hashes a source file has to skip
    rather than fail -- otherwise a new user's first `run_tests.py` reports
    failures for a corpus they simply have not fetched yet. Populate with
    `python3 -m fence_evidence.cli fetch --subset all`.
    """
    return unittest.skipUnless(
        _corpus_is_fetched(),
        "corpus not fetched; run `cli fetch --subset all`")(test)


def store_snapshot() -> Path:
    """Copy the evidence store to a temp file for tests that write to it.

    Two test classes legitimately mutate the database — rebuilding the retrieval
    projection, and letting `get_region` cache an on-demand crop. Running those
    against the live store would corrupt a workspace someone else is using, and
    would collide with a running ingest.
    """
    # inside workspace/, because ensure_writable refuses anything outside it —
    # the guard applies to tests too
    base = TESTS_DIR / "snapshots"
    base.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="store-", dir=base)) / "evidence.db"
    shutil.copy2(EVIDENCE_DB, tmp)
    for suffix in ("-wal", "-shm"):
        side = EVIDENCE_DB.with_name(EVIDENCE_DB.name + suffix)
        if side.exists():
            shutil.copy2(side, tmp.with_name(tmp.name + suffix))
    return tmp
