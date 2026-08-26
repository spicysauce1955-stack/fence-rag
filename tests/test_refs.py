"""The evidence identifier, its inverse, and the guard on published citations.

Why this module exists at all: `ref_id` was defined in `snapshot.py` and
proposed a second time, incompatibly, in
`docs/integration/source-refs-design.md` 1 as an `sref_` locator. Two
identifiers for the same evidence is the failure that document itself rejects
Pillow crops for in 4.2. Addressing had no owner, so it got designed wherever
it was needed. It has one now.
"""
import unittest

import context  # noqa: F401  -- puts the repo root on sys.path
from fence_evidence.refs import ref_id


class TestIdentity(unittest.TestCase):
    """The formula is frozen: 431 published cites depend on it."""

    SHA = "00c965f58d3030b7e7c8a6c8c0b7e99f1579c5599dc476c8f6a62dd88c6cdd58"
    BBOX = "[117.69, 271.47, 266.99, 294.03]"

    def test_the_shipped_formula_is_unchanged(self):
        # Measured from the live store on 2026-08-26. If this fails, every
        # published citation has been invalidated.
        self.assertEqual(ref_id(self.SHA, 5, self.BBOX), "cd9f0d9d9c4e300f")

    def test_the_same_evidence_gets_the_same_id(self):
        self.assertEqual(ref_id(self.SHA, 5, self.BBOX),
                         ref_id(self.SHA, 5, self.BBOX))

    def test_a_hundredth_of_a_point_changes_the_id(self):
        """Not a bug -- the reason plan 2 exists. Recorded so it is not a surprise."""
        shifted = "[117.69, 271.47, 266.99, 294.05]"
        self.assertNotEqual(ref_id(self.SHA, 5, self.BBOX),
                            ref_id(self.SHA, 5, shifted))

    def test_different_bytes_give_a_different_id(self):
        other = "2f446717ee750908059bed45ce06552636671944ca8c1cbbe922092e8d769c3c"
        self.assertNotEqual(ref_id(self.SHA, 5, self.BBOX),
                            ref_id(other, 5, self.BBOX))

    def test_a_null_bbox_is_accepted_and_is_the_page_form(self):
        self.assertEqual(len(ref_id(self.SHA, 5, None)), 16)

    def test_snapshot_still_re_exports_it(self):
        """test_snapshot_build.py imports it from there; do not break that."""
        from fence_evidence.snapshot import ref_id as via_snapshot
        self.assertIs(via_snapshot, ref_id)


if __name__ == "__main__":
    unittest.main()
