"""The graded column must be measured on the query production actually sends.

`[measured]` 2026-09-14: all 79 gold questions carry hand-written `query_terms`,
and `evaluate._query_for` preferred them, while `query.py` passes
`situation.question` unchanged. So every acceptance number in this repository
was measured on annotator keyword strings that production never sends.

Re-run on the natural question, the verdict inverts: recall@10 0.805 PASS
becomes 0.756 FAIL, and false-unsupported 0.146 PASS becomes 0.390 FAIL. Both
criteria this platform believed it passed were artifacts of the rewrite.

This module pins the fix: one run reports both columns, and the column that is
graded is the one production sends. See `docs/coverage-remediation-plan.md` §1.
"""
import unittest

from context import ROOT, requires_full_store  # noqa: F401
from fence_evidence.paths import REPORTS_DIR, TESTS_DIR
from fence_evidence.evaluate import (KEYWORD_HINT, NATURAL_QUESTION, QUERY_FORMS,
                                     _query_for, run_evaluation)


class TestTheTwoColumnsAreMeasuredOnDifferentStrings(unittest.TestCase):
    """Store-free: the two forms must not silently collapse into one.

    If `_query_for` returned the same string for both forms, the report would
    show two columns that are the same measurement wearing two names — which is
    worse than the single misleading column it replaces, because it would look
    like corroboration.
    """

    def test_a_question_with_keywords_yields_a_different_string_per_form(self):
        """The keyword form joins `query_terms`; the natural form does not.

        Fails if `form` is ignored — which is exactly the regression that would
        restore today's behaviour while leaving the new report shape in place.
        """
        question = {
            "id": "gq-000",
            "question": "what footing depth applies at exposure C?",
            "query_terms": ["footing", "depth", "exposure", "C"],
        }
        self.assertEqual(_query_for(question, form=NATURAL_QUESTION),
                         "what footing depth applies at exposure C?")
        self.assertEqual(_query_for(question, form=KEYWORD_HINT),
                         "footing depth exposure C")

    def test_a_question_without_keywords_is_the_same_in_both_forms(self):
        """`query_terms` is optional; absent, there is only one string to use.

        Guards the fallback: a gold question added later without keywords must
        not raise, and must not make the two columns diverge for no reason.
        """
        question = {"id": "gq-001", "question": "how deep do I dig?"}
        self.assertEqual(_query_for(question, form=NATURAL_QUESTION),
                         _query_for(question, form=KEYWORD_HINT))


class TestTheGradedColumnIsTheQueryProductionSends(unittest.TestCase):
    """One run reports both columns, and grades the one production sends.

    The run is done once for the class: two search passes over 78 questions is
    real work, and every assertion below reads the same summary.
    """

    summary: dict = {}

    @classmethod
    @requires_full_store
    def setUpClass(cls):
        out = run_evaluation(report_name="test-query-form-grading")
        cls.summary = out["summary"]

    @classmethod
    def tearDownClass(cls):
        """A variant run must not leave artifacts behind for the next reader."""
        for path in (REPORTS_DIR / "test-query-form-grading-report.md",
                     TESTS_DIR / "test-query-form-grading-results.json"):
            path.unlink(missing_ok=True)

    @requires_full_store
    def test_one_run_reports_both_query_forms(self):
        """Both columns come from a single run, not two invocations.

        Two runs would let the columns drift apart — a store rebuilt between
        them would be compared against itself at two different times and read
        as a retrieval change.
        """
        self.assertEqual(set(self.summary["query_forms"]), set(QUERY_FORMS))

    @requires_full_store
    def test_the_graded_column_is_the_natural_question(self):
        """`[measured]` grading the keyword column reported two false passes.

        recall@10 0.805 PASS and false-unsupported 0.146 PASS both invert on the
        question production actually sends. This asserts the summary grades the
        honest column, so a regression to keyword grading cannot pass quietly.
        `docs/coverage-remediation-plan.md` §1.
        """
        self.assertEqual(self.summary["graded_query_form"], NATURAL_QUESTION)
        graded = self.summary["query_forms"][NATURAL_QUESTION]
        self.assertEqual(self.summary["acceptance"], graded["acceptance"],
                         "the top-level verdict must be the graded column's")

    @requires_full_store
    def test_each_column_carries_its_own_unrounded_means(self):
        """G65: acceptance is graded on the raw value, not its display rounding.

        Both columns need `raw`, because a future reader comparing them must
        compare measurements rather than three-decimal displays.
        """
        for form in QUERY_FORMS:
            raw = self.summary["query_forms"][form]["raw"]
            for key in ("recall_at_k", "evidence_support",
                        "no_answer_precision", "false_unsupported_rate"):
                self.assertIn(key, raw, f"{form} is missing raw[{key}]")

    @requires_full_store
    def test_a_stale_reader_of_the_old_shape_breaks_loudly(self):
        """The old top-level metric keys are removed, not re-pointed.

        Re-pointing them would let a reader compare 0.622 against the 0.650 in
        `docs/` and see a regression that is really a change of instrument. A
        KeyError sends them to the report instead.
        """
        for key in ("recall_at_k", "evidence_support", "by_category"):
            self.assertNotIn(key, self.summary,
                             f"{key} must move into query_forms, not stay top-level")


if __name__ == "__main__":
    unittest.main()
