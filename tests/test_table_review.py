"""The review gate: a reading never becomes a fact without accountable review."""
import shutil
import unittest

from context import requires_store, store_snapshot
from fence_evidence.store import connect
from fence_evidence.table_review import (PROMOTABLE, READER_FAMILY, ReviewRequired,
                                         agreement, mark_agent_verified,
                                         mark_cross_family_verified, normalise,
                                         promote, reader_family, summary)


class TestNormalisation(unittest.TestCase):
    def test_typography_is_folded(self):
        self.assertEqual(normalise('30”'), normalise('30"'))
        self.assertEqual(normalise("36 in."), normalise('36"'))
        self.assertEqual(normalise(" 97\" "), normalise("97\""))

    def test_case_and_space(self):
        self.assertEqual(normalise("Exposure  C"), normalise("EXPOSURE C"))

    def test_different_numbers_stay_different(self):
        self.assertNotEqual(normalise('30"'), normalise('36"'))

    def test_none_is_empty(self):
        self.assertEqual(normalise(None), "")


@requires_store
class TestPromotionGate(unittest.TestCase):
    """Exercised on a snapshot: promotion writes facts."""

    @classmethod
    def setUpClass(cls):
        cls.snapshot = store_snapshot()
        cls.conn = connect(cls.snapshot)
        row = cls.conn.execute("""SELECT d.document_id, v.version_id, d.source_path,
                p.page_no, p.page_image_path FROM documents d
                JOIN document_versions v ON v.document_id=d.document_id
                JOIN pages p ON p.version_id=v.version_id
                WHERE p.page_image_path IS NOT NULL LIMIT 1""").fetchone()
        cls.doc = row
        from fence_evidence.store import now
        for status in ("unreviewed", "agent_verified", "rejected", "accepted",
                       "cross_family_verified"):
            cls.conn.execute("""INSERT INTO table_read_candidates(document_id, version_id,
                page_no, crop_path, reader, reader_kind, is_table, row_index, col_index,
                row_label, col_label, value, review_status, created_at)
                VALUES (?,?,?,?,?,?,1,0,1,'C','FOOTING DEPTH','36"',?,?)""",
                (row["document_id"], row["version_id"], row["page_no"],
                 row["page_image_path"], f"probe-{status}", "agent", status, now()))
        cls.conn.commit()
        cls.ids = {r["review_status"]: r["candidate_id"] for r in cls.conn.execute(
            "SELECT candidate_id, review_status FROM table_read_candidates "
            "WHERE reader LIKE 'probe-%'")}

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        shutil.rmtree(cls.snapshot.parent, ignore_errors=True)

    def test_unreviewed_is_refused(self):
        with self.assertRaises(ReviewRequired):
            promote(self.conn, self.ids["unreviewed"], fact_type="footing_depth_in")

    def test_same_family_agreement_alone_is_refused(self):
        """Two readers that can fail the same way are not independent evidence."""
        with self.assertRaises(ReviewRequired) as ctx:
            promote(self.conn, self.ids["agent_verified"], fact_type="footing_depth_in")
        self.assertIn("correlated", str(ctx.exception))

    def test_cross_family_agreement_alone_is_refused(self):
        """Two agents agreeing is evidence, not review. Only a person promotes."""
        with self.assertRaises(ReviewRequired) as ctx:
            promote(self.conn, self.ids["cross_family_verified"],
                    fact_type="footing_depth_in")
        self.assertIn("person", str(ctx.exception))

    def test_human_review_promotes(self):
        fact_id = promote(self.conn, self.ids["accepted"],
                          fact_type="footing_depth_in", reviewer="a-person")
        fact = self.conn.execute("SELECT * FROM facts WHERE fact_id=?",
                                 (fact_id,)).fetchone()
        self.assertEqual(fact["review_status"], "reviewed")
        self.assertIn("accepted", fact["extractor"])

    def test_cross_family_marking_needs_two_families(self):
        out = mark_cross_family_verified(self.conn, ["calibration-A", "calibration-B"])
        self.assertIn("error", out)
        self.assertIn("two model families", out["error"])

    def test_reader_families_are_declared(self):
        self.assertEqual(reader_family("calibration-A"), "claude-sonnet")
        self.assertEqual(reader_family("codex-C"), "openai-codex")
        self.assertEqual(reader_family("nobody"), "unknown")
        self.assertGreaterEqual(len(set(READER_FAMILY.values())), 2)

    def test_rejected_is_refused(self):
        with self.assertRaises(ReviewRequired):
            promote(self.conn, self.ids["rejected"], fact_type="footing_depth_in")

    def test_accepted_promotes_and_records_provenance(self):
        fact_id = promote(self.conn, self.ids["accepted"],
                          fact_type="footing_depth_in", reviewer="test")
        fact = self.conn.execute("SELECT * FROM facts WHERE fact_id=?", (fact_id,)).fetchone()
        self.assertEqual(fact["review_status"], "reviewed")
        self.assertTrue(fact["element_id"])
        self.assertTrue(fact["evidence_text"])
        self.assertIn("table-review", fact["extractor"])
        link = self.conn.execute("SELECT reviewer FROM "
                                 "table_read_candidates WHERE candidate_id=?",
                                 (self.ids["accepted"],)).fetchone()
        # The link lives on the fact and points down -- the candidate records
        # only that a person handled it. See tests/test_pointer_direction.py.
        back = self.conn.execute("SELECT from_candidate_id FROM facts WHERE fact_id=?",
                                 (fact_id,)).fetchone()
        self.assertIsNotNone(back["from_candidate_id"])
        self.assertEqual(link["reviewer"], "test")

    def test_a_candidate_without_its_crop_cannot_be_promoted(self):
        from fence_evidence.store import now
        self.conn.execute("""INSERT INTO table_read_candidates(document_id, version_id,
            page_no, crop_path, reader, reader_kind, is_table, row_index, col_index,
            value, review_status, created_at)
            VALUES (?,?,?,'workspace/derived/does-not-exist.png','probe-nocrop','agent',
                    1,0,1,'36"','accepted',?)""",
            (self.doc["document_id"], self.doc["version_id"], self.doc["page_no"], now()))
        self.conn.commit()
        cid = self.conn.execute("SELECT candidate_id FROM table_read_candidates "
                                "WHERE reader='probe-nocrop'").fetchone()[0]
        with self.assertRaises(ReviewRequired) as ctx:
            promote(self.conn, cid, fact_type="footing_depth_in")
        self.assertIn("crop", str(ctx.exception))

    def test_unknown_candidate(self):
        with self.assertRaises(ReviewRequired):
            promote(self.conn, 10**9, fact_type="footing_depth_in")

    def test_only_human_review_is_promotable(self):
        """No machine-only status promotes. Agreement is evidence for a reviewer."""
        self.assertNotIn("agent_verified", PROMOTABLE)
        self.assertNotIn("cross_family_verified", PROMOTABLE)
        self.assertEqual(set(PROMOTABLE), {"accepted", "corrected"})

    def test_cross_family_marking_never_overwrites_a_human_verdict(self):
        """G55: a person's accepted/corrected row must survive being re-agreed with."""
        from fence_evidence.store import now
        for reader, status in (("calibration-A", "accepted"), ("codex-C", "unreviewed")):
            self.conn.execute("""INSERT INTO table_read_candidates(document_id, version_id,
                page_no, crop_path, reader, reader_kind, is_table, row_index, col_index,
                row_label, col_label, value, review_status, created_at)
                VALUES (?,?,?,?,?,'agent',1,0,2,'C','FOOTING DEPTH','36"',?,?)""",
                (self.doc["document_id"], self.doc["version_id"], self.doc["page_no"],
                 self.doc["page_image_path"], reader, status, now()))
        self.conn.commit()
        mark_cross_family_verified(self.conn, ["calibration-A", "codex-C"])
        rows = {r["reader"]: r["review_status"] for r in self.conn.execute(
            "SELECT reader, review_status FROM table_read_candidates "
            "WHERE reader IN ('calibration-A', 'codex-C') AND col_index=2")}
        self.assertEqual(rows["calibration-A"], "accepted",
                         "a human verdict must not be overwritten by a later machine agreement")
        self.assertEqual(rows["codex-C"], "cross_family_verified")


if __name__ == "__main__":
    unittest.main()
