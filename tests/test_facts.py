"""Phase 6: facts carry provenance, keep originals, and flag OCR-derived values."""
import json
import unittest

from context import requires_facts, requires_store, store_snapshot
from fence_evidence.facts import (_conditions, _normalise, _scan_text, _to_float,
                                  alternate_for, blank_unit_parentheticals,
                                  dual_units, extract_facts, query_facts)
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

    def test_a_number_after_diameter_that_is_a_depth_is_refused(self):
        # `6 in. (152 mm) diameter 24 in. (609.6 mm) deep` -- 24 is the DEPTH.
        # The store held it as a diameter twice; harmless only while the metric
        # blanking hid the real 6, self-contradictory once it does not.
        self.assertEqual(self._diameters(
            "concrete footing minimum 6 in. (152 mm) diameter 24 in. "
            "(609.6 mm) deep."), [6.0])
        self.assertEqual(self._diameters(
            "concrete footing minimum 6 in. (152 mm) diameter, 24 in. "
            "(609.6 mm) deep."), [6.0])

    def test_a_diameter_whose_sentence_also_ends_in_deep_still_matches(self):
        # The number-first form binds correctly; the guard must not touch it.
        self.assertEqual(self._diameters(
            "Dig hole 8 inches in diameter by 30 inches deep."), [8.0])

    def test_dia_does_not_match_inside_diagonal_or_intermediate(self):
        self.assertEqual(self._diameters('8"X12" DIAGONAL LATTICE 2.75" OP'), [])
        self.assertEqual(self._diameters(
            "Intermediate Rails: All 5', 6', 7' and 8' heights"), [])


class TestUnitParentheticalBlanking(unittest.TestCase):
    """G34 cause 1: the metric restatement sits between the number and the keyword.

    `6 in. (152 mm) diameter` never reached `footing_diameter_in` because the
    parenthetical broke the adjacency every pattern requires. The fix blanks the
    parenthetical **in place** -- same length, so every offset, and therefore
    every span the rest of the pipeline derives from one, is unmoved -- while
    `dual_units` still reads the untouched original and records the second unit.
    """

    def _types(self, text, fact_type):
        return [r["value_normalized"] for r in _scan_text(text)
                if r["fact_type"] == fact_type]

    # ---- the two statements G34 names
    def test_below_grade_across_a_metric_parenthetical(self):
        self.assertEqual(self._types(
            "Top of post concrete footing to be [at grade] [6 inches (152 mm) "
            "below grade] crowned to shed water.", "depth_below_grade_in"), [6.0])

    def test_diameter_across_a_metric_parenthetical(self):
        self.assertEqual(self._types(
            "receivers shall be set in a concrete footing minimum 6 in. "
            "(152 mm) diameter 24 in. (609.6 mm) deep.", "footing_diameter_in"), [6.0])

    def test_depth_across_a_metric_parenthetical(self):
        self.assertEqual(self._types(
            "receivers shall be set in a concrete footing minimum 6 in. "
            "(152 mm) diameter 24 in. (609.6 mm) deep.", "footing_depth_in"), [24.0])

    # ---- blanking preserves offsets and originals
    def test_blanking_preserves_length_and_every_offset(self):
        text = "minimum 6 in. (152 mm) diameter."
        blanked = blank_unit_parentheticals(text)
        self.assertEqual(len(blanked), len(text))
        self.assertNotIn("152", blanked)
        # every character outside the parenthetical is where it was
        for i, ch in enumerate(text):
            if not (text.index("(") <= i < text.index(")") + 1):
                self.assertEqual(blanked[i], ch, f"offset {i} moved")

    def test_a_recovered_span_still_points_at_the_original_characters(self):
        text = ("receivers shall be set in a concrete footing minimum 6 in. "
                "(152 mm) diameter 24 in. (609.6 mm) deep.")
        [m] = [r for r in _scan_text(text) if r["fact_type"] == "footing_diameter_in"]
        self.assertEqual(text[m["start"]:m["end"]], "6 in. (152 mm) diameter")
        # and what is stored is the source's own wording, not the blanked one
        self.assertEqual(m["match_text"], "6 in. (152 mm) diameter")

    def test_recovered_feet_still_normalise_from_the_original_wording(self):
        text = "Line posts installed at intervals not exceeding 10 ft. (3.05 m) on center."
        self.assertEqual(self._types(text, "post_spacing_in"), [120.0])

    # ---- obligation 4: the alternate is read off the untouched text
    def test_value_alternates_for_a_disagreeing_recovered_pair(self):
        text = ("Top of post concrete footing to be [6 inches (152 mm) below grade] "
                "crowned to shed water.")
        [m] = [r for r in _scan_text(text) if r["fact_type"] == "depth_below_grade_in"]
        alt = alternate_for(text, m)
        self.assertIsNotNone(alt, "the metric restatement was lost with the blanking")
        self.assertEqual(alt["value_original"], "152 mm")
        # 6 in is 152.4 mm: the document disagrees with itself, which is the
        # whole point of obligation 4's disagreement clause.
        self.assertNotEqual(alt["value_normalized"], round(6 * 25.4, 1))

    def test_value_alternates_for_a_recovered_diameter(self):
        text = ("concrete footing minimum 6 in. (152 mm) diameter 24 in. "
                "(609.6 mm) deep.")
        [m] = [r for r in _scan_text(text) if r["fact_type"] == "footing_diameter_in"]
        self.assertEqual(alternate_for(text, m)["value_original"], "152 mm")

    def test_value_alternates_for_a_recovered_spacing(self):
        text = "Line posts installed at intervals not exceeding 10 ft. (3.05 m) on center."
        [m] = [r for r in _scan_text(text) if r["fact_type"] == "post_spacing_in"]
        self.assertEqual(alternate_for(text, m)["value_original"], "3.05 m")

    # ---- only unit restatements are blanked
    def test_a_non_metric_parenthetical_is_left_alone(self):
        # `(68in o.c. posts)` is the only thing that makes this a spacing at all.
        text = "6ft (68in o.c. posts) wide by 3.5ft high"
        self.assertEqual(blank_unit_parentheticals(text), text)
        self.assertEqual(self._types(text, "post_spacing_in"), [68.0])

    def test_a_parenthesised_wind_speed_survives(self):
        text = "DESIGN WIND SPEED (90 MPH) EXPOSURE C"
        self.assertEqual(blank_unit_parentheticals(text), text)
        self.assertEqual(self._types(text, "wind_speed_mph"), [90.0])

    def test_a_parenthesised_imperial_depth_survives(self):
        text = 'POST EMBEDMENT (30" Deep) TYPICAL'
        self.assertEqual(self._types(text, "footing_depth_in"), [30.0])


class TestOnCentreSubjectGuard(unittest.TestCase):
    """`on center` states the spacing of whatever noun governs it -- rarely a post.

    Measured on the corpus: of the six `post_spacing_in` matches the blanking
    recovers, five are hog-ring, carriage-bolt or tension-bar-hole spacings in
    the same CSI masterspec. G34 names the same error in the other direction --
    a gate *opening* is a leaf width, not a spacing.
    """

    def _spacings(self, text):
        return [r["value_normalized"] for r in _scan_text(text)
                if r["fact_type"] == "post_spacing_in"]

    def test_gate_opening_is_not_a_post_spacing(self):
        self.assertEqual(self._spacings(
            "Post size for gate openings up to and including 10 ft. (3.05 m) "
            "shall be 2.875 in OD (73 mm)"), [])

    def test_gate_opening_is_not_a_post_spacing_even_stated_on_centre(self):
        self.assertEqual(self._spacings(
            "Post size for gate openings up to and including 10 ft. (3.05 m) "
            "on center shall be 2.875 in OD"), [])

    def test_hog_ring_spacing_is_not_a_post_spacing(self):
        self.assertEqual(self._spacings(
            "Secure the tension wire to the chain link fabric with 9 gauge hog "
            "rings 18 in. (457.2 mm) on center and to each line post."), [])

    def test_carriage_bolt_spacing_is_not_a_post_spacing(self):
        self.assertEqual(self._spacings(
            "tension bands and 5/16 in. (7.94 mm) carriage bolts spaced no "
            "greater than 12 inches (304.8mm) on center."), [])

    def test_tension_bar_hole_spacing_is_not_a_post_spacing(self):
        self.assertEqual(self._spacings(
            "cross section of 2 in. (51 mm) by 3/16 in. (4.8 mm) with holes "
            "spaced 15 in. (381 mm) on center to accommodate carriage bolts"), [])

    def test_a_real_line_post_spacing_still_matches(self):
        self.assertEqual(self._spacings(
            "crowned to shed water away from the post. Line posts installed at "
            "intervals not exceeding 10 ft. (3.05 m) on center."), [120.0])

    def test_the_existing_ocr_table_spacings_still_match(self):
        # Verbatim evidence_text of two of the three post_spacing_in facts the
        # store held before this change; neither names a post at all.
        self.assertEqual(self._spacings(
            'DOGWOOD 4? ru 7g ru 36" ON CENTER ARE IN COMPLIANCE WITH 2007 '
            'FLORIDA BUILDING CODE'), [36.0])
        self.assertEqual(self._spacings(
            "YARROW SEMI PRIVACY ALTERNATING 4 4 84 48 ON CENTER"), [48.0])


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
               -- 'accepted' and 'corrected' are `table_review.PROMOTABLE`:
               -- the two statuses a person's verdict writes, and the only two
               -- obligation 6 lets reach curation level 2. This list predates
               -- build-plan A1 and omitted them, which was invisible while the
               -- promoted set was empty.
               OR review_status NOT IN ('extracted','flagged','reviewed','rejected',
                                        'cross_family_verified','accepted',
                                        'corrected')
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
