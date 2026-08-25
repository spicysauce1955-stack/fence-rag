"""Date-aware, conservative version resolution."""
import unittest

from context import requires_facts, requires_store
from fence_evidence.retrieval import resolve_document_version
from fence_evidence.store import connect
from fence_evidence.versions import (document_dates, effective_at, expiry_status,
                                     parse_date)

CURRENT_NOA = "23-0314.05"
LEGACY_NOA = "12-1106.11"


class TestDateParsing(unittest.TestCase):
    def test_mdy(self):
        self.assertEqual(parse_date("Approval Date: 05/04/2023"), "2023-05-04")

    def test_month_name(self):
        self.assertEqual(parse_date("Approval Date: March 12, 2015"), "2015-03-12")

    def test_iso_passthrough(self):
        self.assertEqual(parse_date("expires 2029-03-13"), "2029-03-13")

    def test_two_digit_year(self):
        self.assertEqual(parse_date("03/13/29"), "2029-03-13")

    def test_impossible_date_is_rejected(self):
        self.assertIsNone(parse_date("Approval Date: 13/45/2023"))

    def test_no_date(self):
        self.assertIsNone(parse_date("Approval Date: pending"))
        self.assertIsNone(parse_date(""))


class TestExpiryVerdict(unittest.TestCase):
    def test_expired(self):
        v = expiry_status({"expiration": {"value": "2018-03-13", "agreement": "unanimous"}},
                          as_of="2026-08-20")
        self.assertEqual(v["status"], "expired")
        self.assertEqual(v["as_of"], "2026-08-20")

    def test_in_force(self):
        v = expiry_status({"expiration": {"value": "2029-03-13", "agreement": "unanimous"}},
                          as_of="2026-08-20")
        self.assertEqual(v["status"], "in_force")

    def test_conflict_yields_no_verdict(self):
        v = expiry_status({"expiration": {"value": None, "agreement": "conflict"}},
                          as_of="2026-08-20")
        self.assertEqual(v["status"], "unknown")
        self.assertIn("disagree", v["basis"])

    def test_absent_yields_no_verdict(self):
        v = expiry_status({}, as_of="2026-08-20")
        self.assertEqual(v["status"], "unknown")

    def test_as_of_is_always_reported(self):
        for dates in ({}, {"expiration": {"value": "2029-03-13", "agreement": "unanimous"}}):
            self.assertIn("as_of", expiry_status(dates, as_of="2026-01-01"))


class TestEffectiveAt(unittest.TestCase):
    def _chain(self):
        return [
            {"document_id": "a", "dates": {"effective": {"value": "2008-01-01"}}},
            {"document_id": "b", "dates": {"effective": {"value": "2013-04-04"}}},
            {"document_id": "c", "dates": {"effective": {"value": "2023-05-04"}}},
        ]

    def test_picks_latest_at_or_before(self):
        self.assertEqual(effective_at(self._chain(), "2015-01-01")["document_id"], "b")
        self.assertEqual(effective_at(self._chain(), "2023-05-04")["document_id"], "c")

    def test_none_before_the_first(self):
        self.assertIsNone(effective_at(self._chain(), "2000-01-01"))

    def test_members_without_dates_are_ignored(self):
        chain = self._chain() + [{"document_id": "d", "dates": {}}]
        self.assertEqual(effective_at(chain, "2030-01-01")["document_id"], "c")


@requires_store
class TestSupersessionDirection(unittest.TestCase):
    """Regression: the status update once marked the wrong side of the edge.

    A `superseded_by` edge reads subject -> object, so its *from* side is the
    superseded document. Marking the *to* side flagged every current NOA as
    superseded and left the CertainTeed/Barrette chain with no active member.
    """

    @classmethod
    def setUpClass(cls):
        cls.conn = connect()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_the_superseding_document_is_not_marked_superseded(self):
        rows = self.conn.execute("""
            SELECT d.source_path, d.version_status
              FROM relations r JOIN documents d ON d.document_id = r.from_document_id
             WHERE r.relation_type='supersedes'
               AND NOT EXISTS (SELECT 1 FROM relations x
                                WHERE x.relation_type='supersedes'
                                  AND x.to_document_id = r.from_document_id)
            """).fetchall()
        self.assertGreater(len(rows), 0, "no un-superseded superseding document found")
        for r in rows:
            self.assertNotEqual(
                r["version_status"], "superseded",
                f"{r['source_path']} supersedes another approval and nothing supersedes "
                "it, yet it is marked superseded")

    def test_the_superseded_document_is_marked(self):
        rows = self.conn.execute("""
            SELECT d.source_path, d.version_status FROM relations r
              JOIN documents d ON d.document_id = r.to_document_id
             WHERE r.relation_type='supersedes'""").fetchall()
        self.assertGreater(len(rows), 0)
        for r in rows:
            self.assertEqual(r["version_status"], "superseded",
                             f"{r['source_path']} is superseded by a later approval but is "
                             f"marked {r['version_status']}")


@requires_facts
class TestResolutionUsesDateFacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = connect()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_dates_carry_provenance(self):
        res = resolve_document_version(CURRENT_NOA, as_of="2026-08-20", conn=self.conn)
        self.assertIsNotNone(res)
        eff = res["dates"]["effective"]
        self.assertEqual(eff["agreement"], "unanimous")
        self.assertTrue(eff["value"])
        self.assertGreater(len(eff["sources"]), 0)
        for src in eff["sources"]:
            self.assertTrue(src["element_id"])
            self.assertIsNotNone(src["page"])
            self.assertIn(src["review_status"], ("extracted", "flagged", "reviewed"))

    def test_expiry_verdict_reports_the_date_it_used(self):
        res = resolve_document_version(CURRENT_NOA, as_of="2026-08-20", conn=self.conn)
        self.assertEqual(res["expiry"]["as_of"], "2026-08-20")
        self.assertIn(res["expiry"]["status"], ("in_force", "expired", "unknown"))

    def test_legacy_approval_is_expired(self):
        res = resolve_document_version(LEGACY_NOA, as_of="2026-08-20", conn=self.conn)
        self.assertEqual(res["expiry"]["status"], "expired")

    def test_chain_members_are_enriched(self):
        res = resolve_document_version(CURRENT_NOA, as_of="2026-08-20", conn=self.conn)
        self.assertGreater(len(res["chain"]), 1)
        for member in res["chain"]:
            self.assertIn("dates", member)
            self.assertIn("expiry", member)

    def test_effective_at_resolves_a_historical_date(self):
        res = resolve_document_version(LEGACY_NOA, at="2015-01-01", as_of="2026-08-20",
                                       conn=self.conn)
        member = res.get("effective_at")
        self.assertIsNotNone(member, "no chain member resolved for 2015-01-01")
        self.assertLessEqual(member["dates"]["effective"]["value"], "2015-01-01")

    def test_an_expired_member_is_never_offered_as_active(self):
        for ident in (CURRENT_NOA, LEGACY_NOA):
            res = resolve_document_version(ident, as_of="2035-01-01", conn=self.conn)
            active = res.get("active")
            if active is not None:
                self.assertNotEqual(active["expiry"]["status"], "expired")
            else:
                self.assertTrue(res["active_basis"])

    def test_resolution_does_not_write_to_documents(self):
        before = self.conn.execute(
            "SELECT version_status, version_status_basis FROM documents "
            "WHERE source_path LIKE '%NOA-23-0314.05%'").fetchone()
        resolve_document_version(CURRENT_NOA, as_of="2026-08-20", conn=self.conn)
        after = self.conn.execute(
            "SELECT version_status, version_status_basis FROM documents "
            "WHERE source_path LIKE '%NOA-23-0314.05%'").fetchone()
        self.assertEqual(tuple(before), tuple(after),
                         "resolution mutated stored classification")


if __name__ == "__main__":
    unittest.main()
