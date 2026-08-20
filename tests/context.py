"""Shared test setup: put src/ on the path and expose common helpers."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fence_evidence.paths import EVIDENCE_DB, TESTS_DIR  # noqa: E402


def requires_store(test):
    """Skip a test when the evidence store has not been built yet."""
    return unittest.skipUnless(EVIDENCE_DB.is_file(),
                               "evidence store not built; run ingestion first")(test)


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
