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


from context import requires_full_store
from fence_evidence.refs import Locus, build_index, resolve


@requires_full_store
class TestIndex(unittest.TestCase):
    """The inverse is a projection: rebuilt from canonical rows, never stored."""

    @classmethod
    def setUpClass(cls):
        from fence_evidence.store import connect
        cls.conn = connect(read_only=True)
        cls.index = build_index(cls.conn)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_it_indexes_the_whole_store(self):
        self.assertGreater(len(self.index), 60_000)

    def test_no_two_different_loci_share_an_id(self):
        """A true hash collision would make a citation ambiguous across documents."""
        for rid, locus in self.index.items():
            self.assertIsInstance(locus, Locus)
        # Distinct (sha, page, bbox) triples must map to distinct ids.
        triples = {(l.sha256, l.page_no, l.bbox) for l in self.index.values()}
        self.assertEqual(len(triples), len(self.index))

    def test_a_known_element_resolves_to_its_rectangle(self):
        rid = ref_id(
            "00c965f58d3030b7e7c8a6c8c0b7e99f1579c5599dc476c8f6a62dd88c6cdd58",
            5, "[117.69, 271.47, 266.99, 294.03]")
        locus = resolve(self.index, rid)
        self.assertIsNotNone(locus)
        self.assertEqual(locus.page_no, 5)
        self.assertIn("element-da08178108-0022", locus.element_ids)

    def test_an_unknown_id_resolves_to_none(self):
        self.assertIsNone(resolve(self.index, "0" * 16))

    def test_a_shared_rectangle_carries_every_element_not_one(self):
        """9,929 ids cover more than one element. Picking one silently would be
        a wrong quote; carrying all of them is the honest shape. See 5.2."""
        shared = [l for l in self.index.values() if len(l.element_ids) > 1]
        self.assertGreater(len(shared), 1_000)

    def test_page_refs_are_indexed_and_flagged(self):
        pages = [l for l in self.index.values() if l.is_page]
        self.assertGreater(len(pages), 1_000)


if __name__ == "__main__":
    unittest.main()
