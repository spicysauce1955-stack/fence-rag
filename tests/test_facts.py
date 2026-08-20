"""Phase 6: facts carry provenance, keep originals, and flag OCR-derived values."""
import json
import unittest

from context import requires_store
from fence_evidence.facts import _conditions, _normalise, _to_float, query_facts
from fence_evidence.store import connect


class TestNormalisation(unittest.TestCase):
    def test_feet_are_converted_and_original_kept(self):
        norm, unit = _normalise("footing_depth_in", "3", "3 ft deep")
        self.assertEqual((norm, unit), (36.0, "in"))

    def test_inches_pass_through(self):
        self.assertEqual(_normalise("footing_depth_in", "36", '36" deep'), (36.0, "in"))

    def test_fractions(self):
        self.assertEqual(_to_float("2½"), 2.5)
        self.assertEqual(_to_float("3/4"), 0.75)

    def test_non_numeric_types_are_not_normalised(self):
        self.assertEqual(_normalise("exposure_category", "C", "Exposure C"), (None, None))

    def test_conditions_extracted_from_text_and_headings(self):
        cond = _conditions("Exposure C at 130 mph for 6 ft high fence",
                           ["Installation", "HVHZ"])
        self.assertEqual(cond["exposure_category"], "C")
        self.assertEqual(cond["wind_speed_mph"], 130.0)
        self.assertEqual(cond["fence_height_ft"], 6.0)
        self.assertTrue(cond["hvhz"])


@requires_store
class TestFactProvenance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = connect()
        cls.n = cls.conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_facts_exist(self):
        if self.n == 0:
            self.skipTest("facts not extracted yet")
        self.assertGreater(self.n, 0)

    def test_every_fact_resolves_to_an_element(self):
        if self.n == 0:
            self.skipTest("facts not extracted yet")
        orphans = self.conn.execute("""SELECT COUNT(*) FROM facts f
            LEFT JOIN elements e ON e.element_id = f.element_id
            WHERE e.element_id IS NULL""").fetchone()[0]
        self.assertEqual(orphans, 0, "a fact exists without a source element")

    def test_every_fact_has_page_and_evidence(self):
        if self.n == 0:
            self.skipTest("facts not extracted yet")
        bad = self.conn.execute("""SELECT COUNT(*) FROM facts
            WHERE page_no IS NULL OR evidence_text = '' OR value_original = ''
               OR review_status NOT IN ('extracted','flagged','reviewed','rejected')
            """).fetchone()[0]
        self.assertEqual(bad, 0)

    def test_ocr_derived_facts_are_flagged_or_confident(self):
        if self.n == 0:
            self.skipTest("facts not extracted yet")
        rows = self.conn.execute("""SELECT f.review_status, e.ocr_confidence
            FROM facts f JOIN elements e ON e.element_id = f.element_id
            WHERE f.ocr_derived = 1""").fetchall()
        for r in rows:
            if r["ocr_confidence"] is None or r["ocr_confidence"] < 80.0:
                self.assertEqual(r["review_status"], "flagged",
                                 "a low-confidence OCR fact was not flagged for review")

    def test_original_value_is_never_discarded(self):
        if self.n == 0:
            self.skipTest("facts not extracted yet")
        rows = self.conn.execute("""SELECT value_original, value_normalized, unit_normalized
            FROM facts WHERE value_normalized IS NOT NULL LIMIT 50""").fetchall()
        for r in rows:
            self.assertTrue(r["value_original"].strip())

    def test_query_returns_provenance(self):
        if self.n == 0:
            self.skipTest("facts not extracted yet")
        rows = query_facts(limit=5, conn=self.conn)
        for r in rows:
            self.assertTrue(r["source_path"])
            self.assertTrue(r["element_id"])
            self.assertIsNotNone(r["page_no"])


if __name__ == "__main__":
    unittest.main()
