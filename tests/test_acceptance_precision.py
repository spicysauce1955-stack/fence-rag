"""The acceptance gate must grade the measurement, not its display rounding.

Found while measuring R3: with the second stage on, mean unit support is
0.699512, which the summary displays as 0.700 — and the gate, reading that
displayed value, reported `A3_evidence_support_ge_0.70` as PASS for a number
below the threshold. No configuration had ever landed inside a rounding step of
a threshold before, so the defect was latent rather than wrong-in-practice.

This is the same failure as G52: a metric that says more than it measures.
"""
import unittest

from context import ROOT  # noqa: F401
from fence_evidence.evaluate import acceptance_flags


class TestAcceptanceGradesTheRawValue(unittest.TestCase):
    def test_support_just_below_the_threshold_fails(self):
        flags = acceptance_flags(recall_at_k=0.805, evidence_support=0.699512,
                                 no_answer_precision=0.324, false_unsupported_rate=0.146)
        self.assertFalse(flags["A3_evidence_support_ge_0.70"],
                         "0.699512 displays as 0.700 but does not clear 0.70")

    def test_support_exactly_at_the_threshold_passes(self):
        flags = acceptance_flags(recall_at_k=0.805, evidence_support=0.70,
                                 no_answer_precision=0.324, false_unsupported_rate=0.146)
        self.assertTrue(flags["A3_evidence_support_ge_0.70"])

    def test_recall_just_below_its_threshold_fails(self):
        flags = acceptance_flags(recall_at_k=0.7995, evidence_support=0.5,
                                 no_answer_precision=0.324, false_unsupported_rate=0.146)
        self.assertFalse(flags["A3_recall_at_10_ge_0.80"])

    def test_a_false_unsupported_rate_just_over_its_ceiling_fails(self):
        flags = acceptance_flags(recall_at_k=0.805, evidence_support=0.5,
                                 no_answer_precision=0.324, false_unsupported_rate=0.2004)
        self.assertFalse(flags["A4b_false_unsupported_le_0.20"],
                         "0.2004 displays as 0.200 but exceeds the 0.20 ceiling")

    def test_a_missing_measurement_is_not_a_pass(self):
        """`None` means nothing was measured, which must never grade as success.

        That includes the ceiling criterion: an unmeasured false-unsupported
        rate is not evidence that the ceiling was respected, so it fails too.
        """
        flags = acceptance_flags(recall_at_k=0.0, evidence_support=None,
                                 no_answer_precision=None, false_unsupported_rate=None)
        self.assertFalse(flags["A3_evidence_support_ge_0.70"])
        self.assertFalse(flags["A4_no_answer_precision_ge_0.66"])
        self.assertFalse(flags["A4b_false_unsupported_le_0.20"])


class TestTheReportShowsEnoughPrecisionToJustifyItsVerdict(unittest.TestCase):
    """A row reading `0.700 | A3 >= 0.70 - FAIL` is not a typo the reader can
    resolve. The graded rows carry the precision the verdict was made on."""

    SUMMARY = {
        "k": 10, "recall_at_k": 0.805, "page_recall_at_k": 0.659, "mrr": 0.557,
        "evidence_support": 0.7, "page_evidence_support": 0.777,
        "no_answer_precision": 0.324, "false_unsupported_rate": 0.146,
        "acceptance": {"A3_recall_at_10_ge_0.80": True,
                       "A3_evidence_support_ge_0.70": False,
                       "A4_no_answer_precision_ge_0.66": False,
                       "A4b_false_unsupported_le_0.20": True},
        "raw": {"evidence_support": 0.699512, "recall_at_k": 0.8049,
                "no_answer_precision": 0.32432, "false_unsupported_rate": 0.14634},
    }

    def test_a_failing_support_row_does_not_read_as_the_threshold(self):
        from fence_evidence.evaluate import acceptance_table
        row = next(r for r in acceptance_table(self.SUMMARY) if "Evidence support" in r)
        self.assertIn("FAIL", row)
        self.assertIn("0.6995", row)
        self.assertNotIn("| 0.7 |", row)

    def test_every_graded_row_carries_a_verdict(self):
        from fence_evidence.evaluate import acceptance_table
        rows = [r for r in acceptance_table(self.SUMMARY) if r.startswith("| ")]
        graded = [r for r in rows if "PASS" in r or "FAIL" in r]
        self.assertEqual(len(graded), 4)


if __name__ == "__main__":
    unittest.main()
