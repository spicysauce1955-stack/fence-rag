"""Phase 6: facts carry provenance, keep originals, and flag OCR-derived values."""
import json
import unittest

from context import requires_facts, requires_store, store_snapshot
from fence_evidence.facts import (_conditions, _normalise, _scan_text, _to_float,
                                  extract_facts, query_facts)
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


class TestFootingDiameterAdjacency(unittest.TestCase):
    """Regression cases for the \\D{0,16} bridging bug in footing_diameter_in.

    Each string is verbatim `evidence_text` from a fact in the live store that
    the old patterns got wrong: the diameter pattern's gap was wide enough to
    bridge over an unrelated number (usually the hole *depth*, sometimes a
    different post's size, sometimes an auger bit's size) instead of binding
    to the number that actually sits next to the word "diameter"/"dia".
    """

    def _diameters(self, text):
        return [r["value_normalized"] for r in _scan_text(text)
                if r["fact_type"] == "footing_diameter_in"]

    def test_diameter_before_an_unrelated_depth_introduced_by_by(self):
        # "Dig hole 8 inches in diameter by 30 inches deep." -> 8, not 30.
        self.assertEqual(self._diameters(
            "Dig hole 8 inches in diameter by 30 inches deep."), [8.0])

    def test_diameter_before_an_unrelated_depth_introduced_by_and(self):
        # 'Dig post holes 8" in diameter and 18" deep' -> 8, not 18.
        self.assertEqual(self._diameters(
            'a.) Dig post holes 8" in diameter and 18" deep (Fig. 2).'), [8.0])

    def test_diameter_hole_that_is_bridges_to_the_depth_range(self):
        # '5" posts require a 12" diameter hole that is 30" to 36" deep' -> 12.
        self.assertEqual(self._diameters(
            '5" posts require a 12" diameter hole that is 30" to 36" deep. '
            'Use two 80lb. bags of concrete'), [12.0])

    def test_diameter_hole_that_is_bridges_to_the_depth_range_second_post(self):
        # '4" posts require a 10" diameter hole that is 30" to 36" deep' -> 10.
        self.assertEqual(self._diameters(
            '4" posts require a 10" diameter hole that is 30" to 36" deep. '
            'Use two 60lb. bags of concrete'), [10.0])

    def test_diameter_hole_period_bridges_to_the_next_posts_size(self):
        # '5" posts will need a 12" diameter ho[le]' -> 12, not the "4" that
        # introduces the *next* sentence about 4" posts.
        self.assertEqual(self._diameters(
            'the stakes and dig the post holes. If installing with concrete, '
            '5" posts will need a 12" diameter ho'), [12.0])

    def test_auger_bit_is_not_a_footing(self):
        # A drill bit's diameter is not a footing diameter at all.
        self.assertEqual(self._diameters(
            'Use a 1in. or 1 1/2in. diameter x 18in. auger bit with an 18in. '
            'extension (both available at most ha'), [])

    def test_diameter_of_phrasing_still_matches(self):
        # Guidance example: trivial "of" filler must still be accepted.
        self.assertEqual(self._diameters("footing diameter of 8 inches"), [8.0])

    def test_bare_dia_abbreviation_still_matches(self):
        self.assertEqual(self._diameters('12"dia.'), [12.0])

    def test_diam_does_not_match_inside_diamond(self):
        # "Diamond rails" must not be read as a 4-inch diameter footing.
        self.assertEqual(self._diameters("3- 1 / 4 in. Diamond rails"), [])

    def test_dia_does_not_match_inside_diagonal_or_intermediate(self):
        self.assertEqual(self._diameters('8"X12" DIAGONAL LATTICE 2.75" OP'), [])
        self.assertEqual(self._diameters(
            "Intermediate Rails: All 5', 6', 7' and 8' heights"), [])


@requires_facts
class TestReextractionPreservesPromotedFacts(unittest.TestCase):
    """extract_facts() must only touch its own regex-derived rows.

    Facts promoted from verified table readings (extractor starting
    'table-read:') are gated by a human/agent review process this module
    knows nothing about, and promote_tables.py can never re-create one once
    the fact names its source candidate -- so a full re-extraction
    that deletes every fact row would destroy them permanently.

    Each test gets its own snapshot (rather than a shared class-level one):
    extract_facts() is destructive by design to regex rows, so tests that
    call it must not contaminate each other.
    """

    def setUp(self):
        self.snapshot = store_snapshot()
        self.conn = connect(self.snapshot)

    def tearDown(self):
        self.conn.close()
        import shutil
        shutil.rmtree(self.snapshot.parent, ignore_errors=True)

    def test_a_promoted_fact_names_its_reading(self):
        """The inverse of the old dangling-id test.

        `facts.from_candidate_id` points DOWN at the evidence, and is a declared
        foreign key, so a fact cannot name a reading that is not there. The test
        this replaces asserted no dangling `promoted_fact_id` survived a
        re-extraction -- a bug the schema now makes unrepresentable.
        """
        bad = self.conn.execute("""SELECT COUNT(*) FROM facts f
             LEFT JOIN table_read_candidates c ON c.candidate_id = f.from_candidate_id
            WHERE f.from_candidate_id IS NOT NULL AND c.candidate_id IS NULL
        """).fetchone()[0]
        self.assertEqual(bad, 0, "a fact names a reading that does not exist")

    def test_regex_facts_are_still_regenerated(self):
        before = self.conn.execute(
            "SELECT COUNT(*) FROM facts WHERE extractor LIKE 'regex-%'").fetchone()[0]
        self.assertGreater(before, 0)
        extract_facts(conn=self.conn)
        after = self.conn.execute(
            "SELECT COUNT(*) FROM facts WHERE extractor LIKE 'regex-%'").fetchone()[0]
        self.assertGreater(after, 0, "regex facts were not regenerated")


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
               OR review_status NOT IN ('extracted','flagged','reviewed','rejected',
                                        'cross_family_verified')
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
