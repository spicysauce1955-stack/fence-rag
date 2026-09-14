"""A condition the caller stated and nothing checked must never read as satisfied.

`[measured]` 2026-09-14 against snapshot `0e04d171`: stating
`frost_depth_mm=1067` (a 42-inch frost line) alongside `exposure_category=B`,
`fence_height=1219mm` and `hvhz=no` returns `footing_depth_mm = 610mm ("24\"")`
labelled `applicability.conditions = "stated_and_satisfied"`, with
`unstated_conditions: []` and `outside_domain: []`.

No published row declares `frost_depth_mm`, so `_row_verdict` -- which iterates
the dimensions the ROW declares -- never examined it. The caller's condition was
received (`basis.conditions_stated` lists it) and silently discarded, and the
answer then asserted the conditions were satisfied.

A 24-inch footing in a 42-inch frost region heaves. An agent trusting that label
would specify it believing it had been checked against the source. This is the
applicability layer claiming something it did not verify, which is the one thing
`docs/knowledge-loop.md` says may never happen quietly.

`unstated_conditions` covers the opposite direction -- a dimension the rows
declare that the caller did not state. There was no field for this one.
"""
import unittest

from context import ROOT  # noqa: F401
from fence_evidence.query import _row_verdict


class TestAnUncheckedConditionIsNeverReportedAsSatisfied(unittest.TestCase):
    def test_a_stated_dimension_no_row_constrains_is_not_satisfied(self):
        """The measured defect, at the unit that decides it.

        The row constrains exposure only. The caller also stated a frost depth.
        Nothing published speaks to frost depth, so the verdict must not be
        `stated_and_satisfied`.
        """
        admitted, verdict, excluded, unevaluated = _row_verdict(
            {"exposure_category": "B"},
            {"exposure_category": "B", "frost_depth_mm": 1067})
        self.assertTrue(admitted, "the row is still applicable, just not verified")
        self.assertEqual(excluded, set())
        self.assertEqual(unevaluated, {"frost_depth_mm"})
        self.assertNotEqual(verdict, "stated_and_satisfied")

    def test_every_stated_dimension_checked_is_still_satisfied(self):
        """The property the fix must not break."""
        admitted, verdict, excluded, unevaluated = _row_verdict(
            {"exposure_category": "B"}, {"exposure_category": "B"})
        self.assertTrue(admitted)
        self.assertEqual(verdict, "stated_and_satisfied")
        self.assertEqual(unevaluated, set())

    def test_an_excluding_dimension_still_excludes(self):
        """Exclusion outranks everything; an unchecked extra must not rescue a row."""
        admitted, verdict, excluded, unevaluated = _row_verdict(
            {"exposure_category": "C"},
            {"exposure_category": "B", "frost_depth_mm": 1067})
        self.assertFalse(admitted)
        self.assertEqual(excluded, {"exposure_category"})


if __name__ == "__main__":
    unittest.main()
