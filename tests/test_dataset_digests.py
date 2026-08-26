"""A baseline for the hand-researched dataset, so a change to it is visible.

`data/` has exactly one commit in its entire history — the initial import — and
carries four claims that were checked against their own sources and contradicted
(`docs/state-and-gaps.md` G16). Those four are still present verbatim, because
`data/` is read-only input and correcting someone's research is their call.

The moment that changes, the ability to say what the researcher originally wrote
is gone. Acceptance criterion P1b asks for a SHA-256 of every file under `data/**`
before any curation phase begins; this writes it. It is cheap insurance against
the failure where a value is silently corrected, a snapshot is rebuilt, and
nobody can tell which of the two readings the old hash was made from.
"""
import json
import unittest

import context  # noqa: F401  -- puts the repo root on sys.path
from fence_evidence.dataset import (DatasetChanged, digest_dataset,
                                    load_digests, verify_dataset, write_digests)


class TestDigest(unittest.TestCase):
    def test_it_covers_every_json_under_data(self):
        d = digest_dataset()
        self.assertGreater(len(d["files"]), 10)
        self.assertTrue(any(p.startswith("data/structural/") for p in d["files"]),
                        "the structural supplements are the half with known errors")

    def test_each_entry_carries_a_sha256_and_a_size(self):
        for path, meta in digest_dataset()["files"].items():
            self.assertEqual(len(meta["sha256"]), 64, path)
            self.assertGreater(meta["bytes"], 0, path)

    def test_it_is_deterministic(self):
        self.assertEqual(digest_dataset()["files"], digest_dataset()["files"])

    def test_paths_are_repo_relative_and_sorted(self):
        paths = list(digest_dataset()["files"])
        self.assertEqual(paths, sorted(paths))
        self.assertFalse(any(p.startswith("/") for p in paths))

    def test_generated_artifacts_are_excluded(self):
        """`master-dataset.json` and the two documents-index files are OUTPUT of
        `build_master.py`. Baselining them would flag every legitimate rebuild."""
        paths = digest_dataset()["files"]
        self.assertNotIn("master-dataset.json", paths)
        self.assertFalse(any("documents-index" in p for p in paths))

    def test_it_records_what_it_is_a_baseline_of(self):
        d = digest_dataset()
        self.assertIn("why", d)
        self.assertIn("G16", d["why"])


class TestVerify(unittest.TestCase):
    def test_the_dataset_matches_its_own_baseline(self):
        """Run against the live tree: if this fails, either `data/` changed or the
        baseline is stale, and either way somebody needs to look."""
        write_digests()                       # idempotent
        verify_dataset()                      # must not raise

    def test_a_changed_file_is_detected(self):
        base = digest_dataset()
        first = next(iter(base["files"]))
        base["files"][first]["sha256"] = "0" * 64
        with self.assertRaises(DatasetChanged) as ctx:
            verify_dataset(baseline=base)
        self.assertIn(first, str(ctx.exception))

    def test_a_removed_file_is_detected(self):
        base = digest_dataset()
        base["files"]["data/does-not-exist.json"] = {"sha256": "0" * 64, "bytes": 1}
        with self.assertRaises(DatasetChanged) as ctx:
            verify_dataset(baseline=base)
        self.assertIn("missing", str(ctx.exception).lower())

    def test_a_new_file_is_detected(self):
        base = digest_dataset()
        base["files"].pop(next(iter(base["files"])))
        with self.assertRaises(DatasetChanged) as ctx:
            verify_dataset(baseline=base)
        self.assertIn("not in the baseline", str(ctx.exception).lower())

    def test_the_written_baseline_round_trips(self):
        write_digests()
        self.assertEqual(load_digests()["files"], digest_dataset()["files"])


if __name__ == "__main__":
    unittest.main()
