"""Shared test setup: put src/ on the path and expose common helpers."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fence_evidence.paths import EVIDENCE_DB  # noqa: E402


def requires_store(test):
    """Skip a test when the evidence store has not been built yet."""
    return unittest.skipUnless(EVIDENCE_DB.is_file(),
                               "evidence store not built; run ingestion first")(test)
