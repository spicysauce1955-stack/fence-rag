"""R3/R5 as a *measurement*: bad input is refused, and a variant cannot
overwrite the baseline's committed numbers.

`evaluate.default_report_name`'s docstring records why the second half matters:
`cli evaluate --second-stage` once wrote its numbers to `evaluation-report.md`,
so a committed baseline claimed 0.672 unit support where the shipped
configuration measures 0.623. A slot-filter variant is one more configuration
that measures something different, so it needs its own path for the same reason.
"""
import unittest

from context import requires_store  # noqa: F401
from fence_evidence.evaluate import default_report_name
from fence_evidence.retrieval import search_evidence
from fence_evidence.store import connect


def _scratch():
    """A throwaway connection, so these tests never touch the real store."""
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


class TestPageCapValidation(unittest.TestCase):
    """Store-free on purpose. `search_evidence` opens the evidence store the
    moment it is called without a connection, and `store.connect` CREATES an
    empty database rather than failing — so a validation test that omitted the
    connection would leave a stray `workspace/indexes/evidence.db` behind on a
    checkout that has none, and make `requires_store` half true for every test
    that ran afterwards."""

    def test_a_cap_below_one_is_refused(self):
        for bad in (0, -1):
            with self.assertRaises(ValueError, msg=f"page_cap={bad}"):
                search_evidence("footing depth", page_cap=bad, conn=_scratch())

    def test_a_cap_of_one_is_allowed(self):
        """The guard must reject nonsense without rejecting R5's headline value."""
        try:
            # An empty query short-circuits before any SQL, so no schema needed.
            search_evidence("", page_cap=1, conn=_scratch())
        except ValueError as exc:            # pragma: no cover - guards the guard
            self.fail(f"page_cap=1 refused: {exc}")


class TestReportNaming(unittest.TestCase):
    def test_each_variant_gets_its_own_report(self):
        names = {
            default_report_name(None, False),                       # shipped
            default_report_name(None, True),
            default_report_name(None, False, dedupe_text=False),
            default_report_name(None, False, page_cap=1),
            default_report_name(None, False, page_cap=2),
            default_report_name(None, False, dedupe_text=False, page_cap=1),
        }
        self.assertEqual(len(names), 6,
                         "two configurations that measure different things must not "
                         f"share one artifact path; got {sorted(names)}")

    def test_the_shipped_configuration_keeps_the_plain_name(self):
        """`evaluation-report.md` must always be what this platform returns, so
        the name follows the default rather than the flag."""
        self.assertEqual(default_report_name(None, False), "evaluation")
        self.assertEqual(default_report_name(None, False, dedupe_text=True), "evaluation")
        self.assertEqual(default_report_name(None, True), "evaluation-second-stage")
        self.assertEqual(default_report_name(None, False, dedupe_text=False),
                         "evaluation-nodedupe")

    def test_an_explicit_name_still_wins(self):
        self.assertEqual(
            default_report_name("scratch", False, dedupe_text=False, page_cap=2), "scratch")


@requires_store
class TestSearchCli(unittest.TestCase):
    """`cli search` must be able to reach the filters, and must refuse a bad cap
    with the exit code the rest of the CLI uses for bad input (2), not a
    traceback."""

    @staticmethod
    def _run(argv):
        import contextlib
        import io
        from fence_evidence.cli import main
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(argv)
        return code, buf.getvalue()

    def test_page_cap_one_returns_distinct_pages(self):
        import json
        code, out = self._run(["search", "footing depth exposure C", "-k", "5",
                               "--page-cap", "1"])
        self.assertEqual(code, 0, out)
        rows = json.loads(out)
        pages = [(r["document_id"], r["page"]) for r in rows]
        self.assertEqual(len(pages), len(set(pages)))

    def test_search_returns_distinct_text_by_default(self):
        import json
        code, out = self._run(["search", "evidence submitted none", "-k", "5", "--full"])
        self.assertEqual(code, 0, out)
        texts = [" ".join((r["text"] or "").split()).lower() for r in json.loads(out)]
        self.assertEqual(len(texts), len(set(texts)))

    def test_no_dedupe_text_restores_the_unfiltered_ranking(self):
        import json
        code, out = self._run(["search", "evidence submitted none", "-k", "5",
                               "--no-dedupe-text", "--full"])
        self.assertEqual(code, 0, out)
        texts = [" ".join((r["text"] or "").split()).lower() for r in json.loads(out)]
        self.assertGreater(len(texts), len(set(texts)),
                           "the escape hatch must actually reach the raw ranking")

    def test_a_bad_page_cap_is_a_clean_error(self):
        code, out = self._run(["search", "footing depth", "--page-cap", "0"])
        self.assertEqual(code, 2, out)
        self.assertIn("page-cap", out)


@requires_store
class TestTheAuditStillMeasuresTheProjection(unittest.TestCase):
    """The relevance audit measures F2/F3 *through* `search_evidence`, so once R3
    ships on by default the instrument would read its own fix and report that
    the duplication it exists to measure had vanished. It must ask for the
    unfiltered list explicitly."""

    def test_the_composition_audit_still_sees_duplicated_slots(self):
        from fence_evidence.audit import result_list_composition
        from fence_evidence.store import connect
        conn = connect()
        try:
            comp = result_list_composition(conn, k=10)
        finally:
            conn.close()
        self.assertGreater(
            comp["slots_with_duplicated_text"], 0,
            "F2 measured 29.5% of slots holding duplicated text. A zero here means "
            "the audit is measuring the retrieval-time filter, not the projection.")
        self.assertGreater(
            comp["slots_repeating_a_page"], 0,
            "same for F3 — the audit must not be reading a filter it did not ask for")


@requires_store
class TestSummaryRecordsTheVariant(unittest.TestCase):
    """A measurement that does not say what it measured is not a measurement."""

    def test_summary_carries_the_slot_filter_settings(self):
        from fence_evidence.evaluate import run_evaluation
        out = run_evaluation(k=10, write=False, dedupe_text=False, page_cap=2)
        self.assertEqual(out["summary"]["dedupe_text"], False)
        self.assertEqual(out["summary"]["page_cap"], 2)

    def test_the_shipped_summary_says_so_too(self):
        from fence_evidence.evaluate import run_evaluation
        out = run_evaluation(k=10, write=False)
        self.assertEqual(out["summary"]["dedupe_text"], True)
        self.assertIsNone(out["summary"]["page_cap"])


@requires_store
class TestAVariantRunCannotOverwriteTheShippedArtifacts(unittest.TestCase):
    """The naming guard has to hold on the programmatic path too.

    `run_evaluation` used to default `report_name="evaluation"`, so
    `run_evaluation(page_cap=1)` wrote a variant's numbers over the committed
    shipped-configuration report — the exact failure `default_report_name`
    exists to prevent, left open on the one path that does not parse arguments.
    """

    def setUp(self):
        from fence_evidence.paths import REPORTS_DIR, TESTS_DIR
        self.shipped = TESTS_DIR / "evaluation-results.json"
        self.before = self.shipped.read_bytes() if self.shipped.is_file() else None
        self.strays = [TESTS_DIR / "evaluation-pagecap1-results.json",
                       REPORTS_DIR / "evaluation-pagecap1-report.md"]

    def tearDown(self):
        for path in self.strays:
            if path.is_file():
                path.unlink()

    def test_a_page_cap_run_writes_its_own_files_and_leaves_the_baseline_alone(self):
        from fence_evidence.evaluate import run_evaluation
        run_evaluation(k=10, page_cap=1)
        for path in self.strays:
            self.assertTrue(path.is_file(), f"{path.name} was not written")
        if self.before is not None:
            self.assertEqual(self.shipped.read_bytes(), self.before,
                             "a variant run overwrote the shipped configuration's "
                             "committed results")


if __name__ == "__main__":
    unittest.main()
