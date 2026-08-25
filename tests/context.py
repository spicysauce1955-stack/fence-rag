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


def requires_store(test):
    """Skip a test when the evidence store has not been built yet."""
    return unittest.skipUnless(EVIDENCE_DB.is_file(),
                               "evidence store not built; run ingestion first")(test)


def _corpus_is_fetched() -> bool:
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
