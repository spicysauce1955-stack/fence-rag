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


class TestFactsReportShowsWhatReviewDecided(unittest.TestCase):
    """A report that prints the machine's number for a row a person corrected is
    G44 in a document instead of in a fact. `reviews.effective_fact_value` is the
    one place that decides which value answers, and this report is a reader.

    Runs against a store built from `store.SCHEMA` in memory.
    """

    def _store(self):
        import sqlite3

        from fence_evidence.store import SCHEMA
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        conn.execute("""INSERT INTO documents(document_id, source_path, file_type,
            corpus_track) VALUES ('doc-1','manuals/x/guide.pdf','pdf','us')""")
        conn.execute("""INSERT INTO document_versions(version_id, document_id,
            sha256, ingested_at) VALUES ('v1','doc-1',?,
            '2026-08-28T00:00:00+00:00')""", ("c" * 64,))
        conn.execute("""INSERT INTO pages(page_id, version_id, page_no, width,
            height, extraction_method) VALUES ('p1','v1',3,612.0,792.0,'ocr')""")
        conn.execute("""INSERT INTO elements(element_id, page_id, version_id,
            document_id, page_no, ordinal, element_type, text, text_source,
            ocr_confidence, bbox) VALUES ('e1','p1','v1','doc-1',3,1,'paragraph',
            'footing depth 24 in', 'ocr', 41.0, '[72.0, 100.0, 300.0, 120.0]')""")
        conn.commit()
        return conn

    def _fact(self, conn, **kw):
        row = {"fact_type": "footing_depth_in", "value_original": '24"',
               "value_normalized": 24.0, "review_status": "flagged",
               "reviewed_value": None, "reviewed_value_normalized": None,
               "reviewer": None}
        row.update(kw)
        conn.execute("""INSERT INTO facts(document_id, version_id, page_no,
            element_id, fact_type, value_original, value_normalized,
            unit_original, unit_normalized, conditions, evidence_text, extractor,
            ocr_derived, review_status, created_at, reviewed_value,
            reviewed_value_normalized, reviewer)
            VALUES ('doc-1','v1',3,'e1',?,?,?,'in','in',
                    '{"exposure": "C"}','...','regex-v1',1,?,
                    '2026-08-28T00:00:00+00:00',?,?,?)""",
            (row["fact_type"], row["value_original"], row["value_normalized"],
             row["review_status"], row["reviewed_value"],
             row["reviewed_value_normalized"], row["reviewer"]))
        conn.commit()

    def test_the_sample_prints_the_persons_value_not_the_machines(self):
        from fence_evidence.reports import facts_report
        conn = self._store()
        self._fact(conn, review_status="reviewed", reviewed_value='36"',
                   reviewed_value_normalized=36.0, reviewer="J. Curator")
        md = facts_report(conn)
        conn.close()
        self.assertIn('36"', md)
        self.assertIn("36.0 in", md)

    def test_the_machine_value_is_still_printed_beside_it(self):
        from fence_evidence.reports import facts_report
        conn = self._store()
        self._fact(conn, review_status="reviewed", reviewed_value='36"',
                   reviewed_value_normalized=36.0, reviewer="J. Curator")
        md = facts_report(conn)
        conn.close()
        self.assertIn('24"', md, "the corrected-from value vanished from the report")
        self.assertIn("J. Curator", md)

    def test_a_correction_gets_its_own_section(self):
        from fence_evidence.reports import facts_report
        conn = self._store()
        self._fact(conn, review_status="reviewed", reviewed_value='36"',
                   reviewed_value_normalized=36.0, reviewer="J. Curator")
        md = facts_report(conn)
        conn.close()
        self.assertIn("What review changed", md)

    def test_a_rejection_is_reported(self):
        from fence_evidence.reports import facts_report
        conn = self._store()
        self._fact(conn, review_status="rejected", reviewer="J. Curator")
        md = facts_report(conn)
        conn.close()
        self.assertIn("What review changed", md)
        self.assertIn("rejected", md)

    def test_nothing_reviewed_prints_no_review_section(self):
        """The live store has zero reviews and its committed report must not
        move. The section is emitted only when there is something to say."""
        from fence_evidence.reports import facts_report
        conn = self._store()
        self._fact(conn)
        md = facts_report(conn)
        conn.close()
        self.assertNotIn("What review changed", md)
        self.assertIn('`24"`', md)


class TestEnvironmentReportDoesNotMoveOnItsOwn(unittest.TestCase):
    """`workspace/reports/environment-report.md` is a committed artifact.

    It carried `disk free`, so every `cli report` run rewrote it and left the
    tree dirty for no content reason. G28 records what a permanently dirty tree
    costs here: the obvious tidy-up reverts 137 PDFs to LFS pointers, and the
    renormalize that fixes that stages 376 MB outside LFS when the filters are
    not installed. The same class of bug closed today in `evaluation-report.md`,
    where a version basis embedded the wall clock.
    """

    def test_two_runs_produce_identical_bytes(self):
        from fence_evidence.reports import environment_report
        self.assertEqual(environment_report(), environment_report())

    def test_no_value_in_it_depends_on_free_disk_space(self):
        """The strong form of the same claim. Two runs in a row prove nothing
        if the churning value simply did not move in that second; a report that
        is identical under a disk of a wholly different size cannot contain
        one."""
        import shutil
        from unittest import mock

        from fence_evidence.reports import environment_report
        real = environment_report()
        fake = shutil._ntuple_diskusage(total=1, used=1, free=0)
        with mock.patch("shutil.disk_usage", return_value=fake) as probe:
            self.assertEqual(environment_report(), real)
        self.assertEqual(probe.call_count, 0,
                         "the environment report probed the disk; whatever it "
                         "learned will be stale the moment the file is written")

    def test_it_still_says_how_much_room_a_run_needs(self):
        """Stability must not be bought by dropping what the reader came for."""
        from fence_evidence.reports import (WORKSPACE_DISK_BUDGET_GB,
                                            environment_report)
        md = environment_report()
        self.assertIn(f"{WORKSPACE_DISK_BUDGET_GB} GB", md)
        self.assertIn("df -h", md, "the report must say how to check the machine")


if __name__ == "__main__":
    unittest.main()
