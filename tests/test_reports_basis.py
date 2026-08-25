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


if __name__ == "__main__":
    unittest.main()
