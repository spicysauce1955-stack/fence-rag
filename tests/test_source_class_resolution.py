"""A document's source class must not depend on which filing arrived first.

`[measured]` 2026-09-14: the bytes `c4eb900c…` are filed twice — once as
`noa-14-1209.01-PE-stamped-structural-drawings…` with `doc_type='unspecified'`,
once as `75mph-wind-kit-noa-miami-dade.pdf` with `doc_type='csi_spec'`. The
first maps to `marketing`, the second to `industry_standard`, and the snapshot
published **marketing** — because `_register_doc` is idempotent per hash and
took the class from whichever filing a citation reached first.

§1.4 makes `marketing` inadmissible for every task, so an arrival-order
accident silently made a Miami-Dade NOA unusable.

This is the same defect G75 closed for `issue_date`/`expiration_date`, in the
same function, left open for the class. The fix keeps the platform's refusal
posture: a filing that cannot be classified never outranks one that can, and two
filings that *are* classified and disagree raise a gap rather than pick a winner.
"""
import unittest

from context import ROOT  # noqa: F401
from fence_evidence.snapshot import SOURCE_CLASS, UNCLASSIFIED, resolve_source_class


class TestAnUnclassifiableFilingNeverOutranksAClassifiedOne(unittest.TestCase):
    def test_the_classified_filing_wins_whatever_the_order(self):
        """The measured defect: `unspecified` beat `csi_spec` by arriving first.

        Both orders are asserted, because the whole defect was that order
        decided the answer.
        """
        self.assertEqual(resolve_source_class(["unspecified", "csi_spec"]),
                         SOURCE_CLASS["csi_spec"])
        self.assertEqual(resolve_source_class(["csi_spec", "unspecified"]),
                         SOURCE_CLASS["csi_spec"])

    def test_a_single_unclassified_filing_still_publishes_the_weakest_class(self):
        """Unchanged behaviour where there is genuinely nothing better.

        Publishing at the weakest class and raising `source_class_unclassified`
        is the deliberate conservative default; this fix must not disturb it.
        """
        only = next(iter(UNCLASSIFIED))
        self.assertEqual(resolve_source_class([only]), SOURCE_CLASS[only])

    def test_two_classified_filings_that_disagree_refuse_to_pick(self):
        """Refuse rather than guess — the platform's posture everywhere else.

        `csi_spec` and `hvhz_noa` are both classifiable and land on different
        §1.4 classes. Ranking them would mint a precedence order this project
        has never agreed, so the resolver returns None and the caller raises a
        gap naming both.
        """
        self.assertIsNone(resolve_source_class(["csi_spec", "hvhz_noa"]))

    def test_agreeing_filings_are_not_a_conflict(self):
        """Two filings landing on the same class is the common case."""
        self.assertEqual(resolve_source_class(["hvhz_noa", "engineering_approval"]),
                         "sealed_approval")


if __name__ == "__main__":
    unittest.main()
