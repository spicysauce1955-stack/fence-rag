"""Storing a snapshot — the first artifact this system produces that it must keep.

Everything under `workspace/` so far has been regenerable: delete `evidence.db`
and 33 minutes of ingest brings it back, byte for byte. A snapshot is not like
that. Rebuilding one requires the L2/L3 state it was built from, and that state
moves forward — the moment a reviewer accepts one more claim, the previous
snapshot can never be reconstructed by anything. But obligation 1 says fetching
it by hash returns the same bytes until `retain_until`.

So the store below is write-once and refuses to overwrite. That refusal is the
whole point: a snapshot that can be silently rewritten is a hash that lies.
"""
import unittest

import context  # noqa: F401  -- puts the repo root on sys.path
from context import requires_store
from fence_evidence.snapshot_store import (SnapshotExists, SnapshotMissing,
                                           get_snapshot, list_snapshots,
                                           put_snapshot, tombstone)


def _snap(sid="a" * 64, tenant="acme"):
    return {"snapshot_id": sid, "tenant": tenant, "regime": "us_astm",
            "retain_until": "2028-01-01", "source_docs": [], "warnings": [],
            "gaps": [], "part_types": [], "parts": [], "models": [],
            "procedures": [], "parameters": [], "combinations": [], "rules": [],
            "spine_version": "0.1.0", "contract_version": "1.1.0",
            "policy_version": "0.1.0"}


class TestWriteOnce(unittest.TestCase):
    def setUp(self):
        import tempfile, pathlib
        from fence_evidence.paths import WORKSPACE
        base = WORKSPACE / "tests" / "snapstore"
        base.mkdir(parents=True, exist_ok=True)
        self.root = pathlib.Path(tempfile.mkdtemp(dir=base))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.root, ignore_errors=True)

    def test_a_stored_snapshot_comes_back_byte_identical(self):
        put_snapshot(_snap(), root=self.root)
        got = get_snapshot("a" * 64, root=self.root)
        self.assertEqual(got["tenant"], "acme")
        self.assertEqual(got["snapshot_id"], "a" * 64)

    def test_storing_the_same_id_twice_is_refused(self):
        put_snapshot(_snap(), root=self.root)
        with self.assertRaises(SnapshotExists):
            put_snapshot(_snap(tenant="somebody-else"), root=self.root)

    def test_re_storing_identical_bytes_is_not_an_error(self):
        """Idempotent, because a rebuild that produces the same bytes has not
        changed anything — refusing that would make retries fail for no reason."""
        put_snapshot(_snap(), root=self.root)
        put_snapshot(_snap(), root=self.root)          # must not raise

    def test_a_rebuild_on_a_later_day_is_the_same_snapshot(self):
        """`retain_until` sits OUTSIDE the hash on purpose — it moves with the
        clock, and hashing it would mean two builds over identical knowledge
        never matched. But that means a rebuild tomorrow has the same id and
        different bytes, and refusing it would be wrong: the ID is the identity.

        The stored copy wins. Its `retain_until` is the promise already made to
        whoever pinned that hash, and a later build must not quietly extend or
        shorten it.
        """
        put_snapshot(_snap(), root=self.root)
        later = _snap()
        later["retain_until"] = "2029-06-01"           # a day passed
        put_snapshot(later, root=self.root)            # must not raise
        self.assertEqual(get_snapshot("a" * 64, root=self.root)["retain_until"],
                         "2028-01-01", "the stored promise was overwritten")

    def test_the_same_id_with_different_CONTENT_is_still_refused(self):
        """Only the unhashed metadata may differ. If a hashed member changed, the
        id should have changed too, so something is badly wrong."""
        put_snapshot(_snap(), root=self.root)
        tampered = _snap()
        tampered["warnings"] = [{"text_raw": "injected", "lang": "en",
                                 "severity_lexeme": None,
                                 "attaches_to": {"kind": "document", "ref": "h1"},
                                 "cites": []}]
        with self.assertRaises(SnapshotExists):
            put_snapshot(tampered, root=self.root)

    def test_fetching_something_that_was_never_stored_raises(self):
        with self.assertRaises(SnapshotMissing):
            get_snapshot("b" * 64, root=self.root)

    def test_listing_reports_what_is_held(self):
        put_snapshot(_snap(sid="a" * 64), root=self.root)
        put_snapshot(_snap(sid="c" * 64), root=self.root)
        ids = {s["snapshot_id"] for s in list_snapshots(root=self.root)}
        self.assertEqual(ids, {"a" * 64, "c" * 64})


class TestTombstone(unittest.TestCase):
    """A document may eventually have to be removed. When it does, an old fetch
    must say so — never 404, and never silently recompute to a different answer."""

    def setUp(self):
        import tempfile, pathlib
        from fence_evidence.paths import WORKSPACE
        base = WORKSPACE / "tests" / "snapstore"
        base.mkdir(parents=True, exist_ok=True)
        self.root = pathlib.Path(tempfile.mkdtemp(dir=base))
        put_snapshot(_snap(), root=self.root)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.root, ignore_errors=True)

    def test_an_excised_snapshot_returns_a_tombstone_not_a_404(self):
        tombstone("a" * 64, reason="source document withdrawn by publisher",
                  root=self.root)
        got = get_snapshot("a" * 64, root=self.root)
        self.assertTrue(got["tombstoned"])
        self.assertIn("withdrawn", got["reason"])
        self.assertEqual(got["snapshot_id"], "a" * 64)

    def test_a_tombstone_never_carries_the_payload(self):
        tombstone("a" * 64, reason="x", root=self.root)
        got = get_snapshot("a" * 64, root=self.root)
        self.assertNotIn("warnings", got)
        self.assertNotIn("source_docs", got)

    def test_a_tombstone_requires_a_reason(self):
        with self.assertRaises(ValueError):
            tombstone("a" * 64, reason="", root=self.root)


@requires_store
class TestRoundTripFromARealBuild(unittest.TestCase):
    def test_a_real_snapshot_survives_the_round_trip_unchanged(self):
        import tempfile, pathlib, shutil
        from fence_evidence.paths import WORKSPACE
        from fence_evidence.canonical import canonical_bytes
        from fence_evidence.snapshot import build_snapshot
        base = WORKSPACE / "tests" / "snapstore"
        base.mkdir(parents=True, exist_ok=True)
        root = pathlib.Path(tempfile.mkdtemp(dir=base))
        try:
            built = build_snapshot(tenant="acme")
            put_snapshot(built, root=root)
            got = get_snapshot(built["snapshot_id"], root=root)
            self.assertEqual(canonical_bytes(got), canonical_bytes(built),
                             "a snapshot changed between storing and fetching")
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
