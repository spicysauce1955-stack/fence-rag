"""The new columns must be visible to a person, not only to a query.

Build-plan Phase A's exit condition is that every item is "measurable in the
store". A column nobody can see in a report is measurable only by whoever
already knows to look for it.
"""
import unittest

import context  # noqa: F401  -- puts the repo root on sys.path
from context import requires_store


@requires_store
class TestFactsReportShowsBasis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fence_evidence.reports import facts_report
        from fence_evidence.store import connect
        cls.conn = connect()
        cls.md = facts_report(cls.conn)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_reports_the_condition_basis_split(self):
        self.assertIn("condition basis", self.md.lower())
        for value in ("stated", "assumed", "unexamined"):
            self.assertIn(value, self.md,
                          f"the report never mentions condition_basis '{value}'")

    def test_reports_the_language_tally_with_its_basis(self):
        self.assertIn("lang", self.md.lower())
        self.assertIn("assumed", self.md)

    def test_says_plainly_that_no_language_was_measured(self):
        """Obligation 10 is about the honesty of the claim. A report that shows
        a language count without showing that none of it was measured is the
        exact laundering the obligation forbids."""
        self.assertIn("measured", self.md.lower())

    def test_reports_dual_unit_coverage(self):
        self.assertIn("alternate", self.md.lower())


class TestDisagreementIsCountedInOneScale(unittest.TestCase):
    """Obligation 4 turns on whether two lexemes DISAGREE, so the count of
    disagreements is the number that carries the obligation. It compared
    `in` against `mm` and nothing else, which silently skipped every pair
    stated in feet and metres -- `10 ft. (3.05 m)` disagrees by 2 mm and was
    reported as agreement, so the report printed 3 where the truth was 4."""

    def test_a_foot_metre_pair_is_a_disagreement(self):
        from fence_evidence.reports import _to_mm
        self.assertAlmostEqual(_to_mm(120.0, "in"), 3048.0)
        self.assertAlmostEqual(_to_mm(3.05, "m"), 3050.0)
        self.assertGreater(abs(_to_mm(120.0, "in") - _to_mm(3.05, "m")), 0.05)

    def test_an_exact_restatement_is_not_a_disagreement(self):
        from fence_evidence.reports import _to_mm
        self.assertLessEqual(
            abs(_to_mm(24.0, "in") - _to_mm(609.6, "mm")), 0.05)

    def test_a_non_length_never_pairs(self):
        """mph and deg have no second unit in this corpus. Returning None keeps
        them out of the comparison rather than giving them a bogus scale."""
        from fence_evidence.reports import _to_mm
        self.assertIsNone(_to_mm(90.0, "mph"))
        self.assertIsNone(_to_mm(15.0, "deg"))
        self.assertIsNone(_to_mm(None, "in"))


if __name__ == "__main__":
    unittest.main()
