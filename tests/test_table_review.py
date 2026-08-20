"""The review gate: a reading never becomes a fact without accountable review."""
import shutil
import unittest

from context import requires_store, store_snapshot
from fence_evidence.store import connect
from fence_evidence.table_review import (PROMOTABLE, ReviewRequired, agreement,
                                         mark_agent_verified, normalise, promote,
                                         summary)


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
        for status in ("unreviewed", "agent_verified", "rejected", "accepted"):
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

    def test_agent_agreement_alone_is_refused(self):
        with self.assertRaises(ReviewRequired) as ctx:
            promote(self.conn, self.ids["agent_verified"], fact_type="footing_depth_in")
        self.assertIn("accountable review", str(ctx.exception))

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
        link = self.conn.execute("SELECT promoted_fact_id, reviewer FROM "
                                 "table_read_candidates WHERE candidate_id=?",
                                 (self.ids["accepted"],)).fetchone()
        self.assertEqual(link["promoted_fact_id"], fact_id)
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

    def test_promotable_statuses_exclude_agent_verified(self):
        self.assertNotIn("agent_verified", PROMOTABLE)


if __name__ == "__main__":
    unittest.main()
