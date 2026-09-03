"""The human gate on a step candidate, and what publishes once it closes.

A candidate with no reviewer publishes nothing, ever. That is A1/C0: machine
agreement between two readers was once laundered into curation level 2 and 324
facts had to be un-promoted. The same rule, applied to a different seam.

The anchor is evidence, never a row id. `candidate_id` moves every time the
splitter is re-run — four times in one day, on this page.
"""
import sqlite3
import unittest

from context import ROOT  # noqa: F401
from fence_evidence import steps
from fence_evidence.reviews import ReviewRefused, submit_step_review
from fence_evidence.store import STEP_CANDIDATES_DDL, STEP_REVIEWS_DDL

BULLET = ("• I nsert post in hole\n• Determine rough height\n"
          "• Tamp concrete in hole to eliminate air pockets")


def scratch() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE documents (document_id TEXT PRIMARY KEY, source_path TEXT,
                                doc_type TEXT, title TEXT, owner_tenant TEXT);
        CREATE TABLE elements (element_id TEXT PRIMARY KEY, document_id TEXT,
                               version_id TEXT, page_no INTEGER, ordinal INTEGER,
                               element_type TEXT, text TEXT, ocr_text TEXT,
                               text_source TEXT, heading_path TEXT, bbox TEXT);
    """)
    conn.executescript(STEP_CANDIDATES_DDL)
    conn.executescript(STEP_REVIEWS_DDL)
    conn.execute("INSERT INTO documents VALUES ('doc-1','a.pdf','installation_manual',"
                 "'Guide',NULL)")
    conn.execute("INSERT INTO elements VALUES ('el-1','doc-1','v1',8,7,'list',?,NULL,"
                 "'pdf_text_layer','[]','[54,290,275,370]')", (BULLET,))
    steps.propose(conn, document_id="doc-1", page_no=8)
    return conn


def a_candidate(conn, n=0):
    return conn.execute("SELECT * FROM step_candidates ORDER BY seq").fetchall()[n]


def accept(conn, cand, **kw):
    args = dict(element_id=cand["element_id"], char_start=cand["char_start"],
                char_end=cand["char_end"], text_seen=cand["text_raw"],
                reviewer="a-person", verdict="accepted", step_kind="installation",
                step_scope="post", slot_target={"kind": "PostSlot", "key": "post"})
    args.update(kw)
    return submit_step_review(conn, **args)


class TestTheGate(unittest.TestCase):
    def test_a_review_projects_onto_its_candidate(self):
        conn = scratch()
        accept(conn, a_candidate(conn))
        row = a_candidate(conn)
        self.assertEqual(row["review_status"], "accepted")
        self.assertEqual(row["reviewer"], "a-person")
        self.assertIsNotNone(row["reviewed_at"])

    def test_an_unreviewed_candidate_stays_unreviewed(self):
        conn = scratch()
        accept(conn, a_candidate(conn, 0))
        self.assertEqual(a_candidate(conn, 1)["review_status"], "unreviewed")

    def test_a_blank_reviewer_is_refused(self):
        """The name is the only thing separating 'software read this' from 'a
        person confirmed it'."""
        conn = scratch()
        with self.assertRaises(ReviewRefused):
            accept(conn, a_candidate(conn), reviewer="  ")

    def test_a_machine_verdict_is_refused(self):
        conn = scratch()
        with self.assertRaises(ReviewRefused):
            accept(conn, a_candidate(conn), verdict="cross_family_verified")

    def test_an_unknown_kind_or_scope_is_refused(self):
        conn = scratch()
        with self.assertRaises(ReviewRefused):
            accept(conn, a_candidate(conn), step_kind="nonsense")
        with self.assertRaises(ReviewRefused):
            accept(conn, a_candidate(conn), step_scope="nonsense")

    def test_text_the_reviewer_did_not_see_is_refused(self):
        """The echo check: if the candidate's text has changed since the person
        looked, the review is of something that no longer exists."""
        conn = scratch()
        cand = a_candidate(conn)
        with self.assertRaises(ReviewRefused):
            accept(conn, cand, text_seen="something else entirely")

    def test_an_anchor_that_names_nothing_is_refused(self):
        conn = scratch()
        cand = a_candidate(conn)
        with self.assertRaises(ReviewRefused):
            accept(conn, cand, char_start=9999, char_end=10000)


class TestTheAnchorSurvivesARecut(unittest.TestCase):
    """`candidate_id` moves whenever the splitter re-runs. The review must not."""

    def test_a_review_survives_re_proposing(self):
        conn = scratch()
        accept(conn, a_candidate(conn))
        before = a_candidate(conn)["candidate_id"]
        conn.execute("DELETE FROM step_candidates")
        steps.propose(conn, document_id="doc-1", page_no=8)
        from fence_evidence.reviews import rebuild_step_projection
        rebuild_step_projection(conn)
        after = a_candidate(conn)
        self.assertNotEqual(after["candidate_id"], before,
                            "the fixture must actually re-mint ids")
        self.assertEqual(after["review_status"], "accepted")
        self.assertEqual(after["reviewer"], "a-person")

    def test_the_projection_is_rebuilt_from_the_record_alone(self):
        conn = scratch()
        accept(conn, a_candidate(conn))
        conn.execute("UPDATE step_candidates SET review_status='unreviewed',"
                     " reviewer=NULL, reviewed_at=NULL")
        from fence_evidence.reviews import rebuild_step_projection
        rebuild_step_projection(conn)
        self.assertEqual(a_candidate(conn)["review_status"], "accepted")


class TestWhatTheReviewerDecides(unittest.TestCase):
    def test_a_correction_records_the_text_the_person_confirmed(self):
        conn = scratch()
        cand = a_candidate(conn)
        accept(conn, cand, verdict="corrected", text_final="Insert post in hole")
        row = conn.execute("SELECT text_final, verdict FROM step_reviews").fetchone()
        self.assertEqual(row["text_final"], "Insert post in hole")
        self.assertEqual(row["verdict"], "corrected")

    def test_the_raw_text_is_never_rewritten(self):
        """`text_raw` is the source slice. A correction is a separate column."""
        conn = scratch()
        cand = a_candidate(conn)
        before = cand["text_raw"]
        accept(conn, cand, verdict="corrected", text_final="Insert post in hole")
        self.assertEqual(a_candidate(conn)["text_raw"], before)

    def test_a_rejection_is_recorded_and_reversible(self):
        conn = scratch()
        accept(conn, a_candidate(conn), verdict="rejected", step_kind=None,
               step_scope=None, slot_target=None)
        self.assertEqual(a_candidate(conn)["review_status"], "rejected")
        self.assertEqual(
            conn.execute("SELECT status_before FROM step_reviews").fetchone()[0],
            "unreviewed")


if __name__ == "__main__":
    unittest.main()
