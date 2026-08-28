"""The fact review loop — the half of G6 that was a column and no workflow.

266 of 1,714 facts sit at `review_status='flagged'` because the OCR they were
read off scored below 80% mean word confidence. Until this module's subject
existed there was no way for a person to move one of them anywhere: `flagged`
was a dead end, and the `reviewed` status the schema comment promised was
written by nothing that looks at a regex-extracted fact.

Everything here runs against a store built from `store.SCHEMA` in memory, so it
needs neither the corpus nor an ingested database and cannot damage either. The
last class is the exception: it asserts against the real store, and it asserts
that **nothing in it has been reviewed**, which is the measurement obligation 6
turns on.
"""
import json
import sqlite3
import unittest

import context  # noqa: F401  -- puts the repo root on sys.path
from context import requires_store
from fence_evidence import reviews
from fence_evidence.refs import ref_id
from fence_evidence.store import SCHEMA, connect

SHA = "a" * 64
BBOX = "[72.0, 100.0, 300.0, 120.0]"
OTHER_BBOX = "[72.0, 200.0, 300.0, 220.0]"


def make_store() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute("""INSERT INTO documents(document_id, source_path, file_type,
                    corpus_track) VALUES ('doc-1','manuals/x/a.pdf','pdf','us')""")
    conn.execute("""INSERT INTO document_versions(version_id, document_id, sha256,
                    ingested_at) VALUES ('v1','doc-1',?, '2026-08-28T00:00:00+00:00')""",
                 (SHA,))
    conn.execute("""INSERT INTO pages(page_id, version_id, page_no, width, height,
                    extraction_method) VALUES ('p1','v1',6,612.0,792.0,'ocr')""")
    for eid, bbox, conf in (("e1", BBOX, 41.2), ("e2", OTHER_BBOX, 93.0)):
        conn.execute("""INSERT INTO elements(element_id, page_id, version_id,
            document_id, page_no, ordinal, element_type, text, text_source,
            ocr_confidence, bbox) VALUES (?, 'p1','v1','doc-1',6,1,'paragraph',
            'footing depth 24 in', 'ocr', ?, ?)""", (eid, conf, bbox))
    conn.commit()
    return conn


def add_fact(conn, *, element_id="e1", fact_type="footing_depth_in",
             value='24"', normalized=24.0, status="flagged",
             extractor="regex-v1", ocr_derived=1) -> int:
    cur = conn.execute("""INSERT INTO facts(document_id, version_id, page_no,
        element_id, fact_type, subject, value_original, value_normalized,
        unit_original, unit_normalized, conditions, evidence_text, extractor,
        ocr_derived, review_status, created_at)
        VALUES ('doc-1','v1',6,?,?,NULL,?,?,'in','in','{}','...',?,?,?,
                '2026-08-28T00:00:00+00:00')""",
        (element_id, fact_type, value, normalized, extractor, ocr_derived, status))
    conn.commit()
    return cur.lastrowid


def the_ref(bbox=BBOX) -> str:
    return ref_id(SHA, 6, bbox)


def fact(conn, fact_id):
    return conn.execute("SELECT * FROM facts WHERE fact_id=?", (fact_id,)).fetchone()


# --------------------------------------------------------------------- queue
class TestQueue(unittest.TestCase):
    def setUp(self):
        self.conn = make_store()

    def tearDown(self):
        self.conn.close()

    def test_the_queue_is_exactly_the_flagged_facts(self):
        flagged = {add_fact(self.conn), add_fact(self.conn, fact_type="wind_speed_mph",
                                                 value="150 mph", normalized=150.0)}
        add_fact(self.conn, status="extracted", element_id="e2")
        add_fact(self.conn, status="reviewed", element_id="e2")
        add_fact(self.conn, status="rejected", element_id="e2")
        queue = reviews.fact_review_queue(self.conn)
        self.assertEqual({q["fact_id"] for q in queue}, flagged,
                         "the queue must list the flagged facts and nothing else")

    def test_a_queue_entry_carries_a_resolvable_source_ref(self):
        fid = add_fact(self.conn)
        entry, = reviews.fact_review_queue(self.conn)
        self.assertEqual(entry["fact_id"], fid)
        self.assertEqual(entry["ref_id"], the_ref(),
                         "the entry must name the region a reviewer has to look at")
        # And the id it names must be one this store actually produces, i.e. it
        # must resolve through the same index `GET /source-refs/{id}` uses.
        from fence_evidence import refs
        self.assertIsNotNone(refs.resolve(refs.build_index(self.conn), entry["ref_id"]))

    def test_a_reviewed_fact_leaves_the_queue(self):
        fid = add_fact(self.conn)
        reviews.submit_fact_review(self.conn, fact_id=fid, reviewer="ann",
                                   verdict="accepted", ref_id=the_ref())
        self.assertEqual(reviews.fact_review_queue(self.conn), [])

    def test_the_summary_counts_what_is_waiting(self):
        add_fact(self.conn)
        add_fact(self.conn, status="extracted", element_id="e2")
        s = reviews.fact_review_summary(self.conn)
        self.assertEqual(s["pending"], 1)
        self.assertEqual(s["reviews"], 0)
        self.assertEqual(s["reviewers"], [])


# -------------------------------------------------------------------- accept
class TestAccept(unittest.TestCase):
    def setUp(self):
        self.conn = make_store()
        self.fid = add_fact(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_accept_records_who_when_and_what(self):
        out = reviews.submit_fact_review(
            self.conn, fact_id=self.fid, reviewer="ann", verdict="accepted",
            ref_id=the_ref(), reviewed_at="2026-08-28T09:00:00+00:00")
        row = fact(self.conn, self.fid)
        self.assertEqual(row["review_status"], "reviewed")
        self.assertEqual(row["reviewer"], "ann")
        self.assertEqual(row["reviewed_at"], "2026-08-28T09:00:00+00:00")
        self.assertIsNone(row["reviewed_value"], "an acceptance changes no value")
        self.assertEqual(row["value_original"], '24"')

        rec = self.conn.execute("SELECT * FROM fact_reviews WHERE fact_review_id=?",
                                (out["fact_review_id"],)).fetchone()
        self.assertEqual(rec["verdict"], "accepted")
        self.assertEqual(rec["reviewer"], "ann")
        self.assertEqual(rec["value_before"], '24"')
        self.assertEqual(rec["status_before"], "flagged")
        self.assertEqual(rec["fact_id"], self.fid)

    def test_the_record_names_the_region_that_was_looked_at(self):
        out = reviews.submit_fact_review(self.conn, fact_id=self.fid, reviewer="ann",
                                         verdict="accepted", ref_id=the_ref())
        rec = self.conn.execute("SELECT ref_id FROM fact_reviews WHERE fact_review_id=?",
                                (out["fact_review_id"],)).fetchone()
        self.assertEqual(rec["ref_id"], the_ref())


# ------------------------------------------------------------------- correct
class TestCorrect(unittest.TestCase):
    def setUp(self):
        self.conn = make_store()
        self.fid = add_fact(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_a_correction_keeps_the_original_alongside_it(self):
        """G44's shape, one layer over: the person's value must not overwrite
        the machine's, and the machine's must not survive as the answer."""
        reviews.submit_fact_review(self.conn, fact_id=self.fid, reviewer="ann",
                                   verdict="corrected", ref_id=the_ref(), value='36"')
        row = fact(self.conn, self.fid)
        self.assertEqual(row["value_original"], '24"', "the original was destroyed")
        self.assertEqual(row["reviewed_value"], '36"')
        self.assertEqual(row["review_status"], "reviewed")
        self.assertEqual(reviews.effective_fact_value(row), '36"',
                         "a consumer reading the fact must get the person's value")

    def test_a_correction_normalises_the_new_value_too(self):
        """CLAUDE.md: store both original and normalized values for any
        measurement. A corrected text with the machine's old number beside it
        would publish 24 while displaying 36."""
        reviews.submit_fact_review(self.conn, fact_id=self.fid, reviewer="ann",
                                   verdict="corrected", ref_id=the_ref(), value='36"')
        row = fact(self.conn, self.fid)
        self.assertEqual(row["value_normalized"], 24.0, "the original number moved")
        self.assertEqual(row["reviewed_value_normalized"], 36.0)

    def test_a_correction_needs_a_value(self):
        with self.assertRaises(reviews.ReviewRefused):
            reviews.submit_fact_review(self.conn, fact_id=self.fid, reviewer="ann",
                                       verdict="corrected", ref_id=the_ref())

    def test_a_correction_that_changes_nothing_is_refused(self):
        with self.assertRaises(reviews.ReviewRefused):
            reviews.submit_fact_review(self.conn, fact_id=self.fid, reviewer="ann",
                                       verdict="corrected", ref_id=the_ref(),
                                       value='24"')

    def test_an_acceptance_may_not_carry_a_value(self):
        with self.assertRaises(reviews.ReviewRefused):
            reviews.submit_fact_review(self.conn, fact_id=self.fid, reviewer="ann",
                                       verdict="accepted", ref_id=the_ref(),
                                       value='36"')

    def test_a_later_acceptance_clears_the_earlier_correction(self):
        reviews.submit_fact_review(self.conn, fact_id=self.fid, reviewer="ann",
                                   verdict="corrected", ref_id=the_ref(), value='36"')
        reviews.submit_fact_review(self.conn, fact_id=self.fid, reviewer="bea",
                                   verdict="accepted", ref_id=the_ref())
        row = fact(self.conn, self.fid)
        self.assertIsNone(row["reviewed_value"],
                          "a stale correction outlived the review that withdrew it")
        self.assertEqual(reviews.effective_fact_value(row), '24"')


# -------------------------------------------------------------------- reject
class TestReject(unittest.TestCase):
    def setUp(self):
        self.conn = make_store()
        self.fid = add_fact(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_reject_is_honoured(self):
        reviews.submit_fact_review(self.conn, fact_id=self.fid, reviewer="ann",
                                   verdict="rejected", ref_id=the_ref())
        row = fact(self.conn, self.fid)
        self.assertEqual(row["review_status"], "rejected")
        self.assertEqual(row["reviewer"], "ann")

    def test_a_rejected_fact_never_holds_a_reviewed_status(self):
        """G47: a fact must not keep a status it no longer earns."""
        reviews.submit_fact_review(self.conn, fact_id=self.fid, reviewer="ann",
                                   verdict="accepted", ref_id=the_ref())
        reviews.submit_fact_review(self.conn, fact_id=self.fid, reviewer="bea",
                                   verdict="rejected", ref_id=the_ref())
        self.assertEqual(fact(self.conn, self.fid)["review_status"], "rejected")

    def test_a_rejection_is_reversible_by_a_later_review(self):
        reviews.submit_fact_review(self.conn, fact_id=self.fid, reviewer="ann",
                                   verdict="rejected", ref_id=the_ref())
        reviews.submit_fact_review(self.conn, fact_id=self.fid, reviewer="bea",
                                   verdict="accepted", ref_id=the_ref())
        self.assertEqual(fact(self.conn, self.fid)["review_status"], "reviewed")

    def test_a_rejection_is_reversible_by_rebuilding_from_the_record(self):
        """The other direction: withdraw the record, and the fact goes back to
        the status it had before anybody touched it -- not to `reviewed`, and
        not stuck at `rejected`."""
        reviews.submit_fact_review(self.conn, fact_id=self.fid, reviewer="ann",
                                   verdict="rejected", ref_id=the_ref())
        self.conn.execute("DELETE FROM fact_reviews WHERE fact_id=?", (self.fid,))
        self.conn.commit()
        reviews.rebuild_fact_projection(self.conn)
        row = fact(self.conn, self.fid)
        self.assertEqual(row["review_status"], "flagged")
        self.assertIsNone(row["reviewer"])
        self.assertIsNone(row["reviewed_at"])


# ------------------------------------------------------------------ refusals
class TestRefusals(unittest.TestCase):
    def setUp(self):
        self.conn = make_store()
        self.fid = add_fact(self.conn)

    def tearDown(self):
        self.conn.close()

    def _refused(self, **kw):
        args = dict(fact_id=self.fid, reviewer="ann", verdict="accepted",
                    ref_id=the_ref())
        args.update(kw)
        with self.assertRaises(reviews.ReviewRefused) as cm:
            reviews.submit_fact_review(self.conn, **args)
        return cm.exception

    def test_a_review_with_no_reviewer_is_refused(self):
        for bad in (None, "", "   "):
            e = self._refused(reviewer=bad)
            self.assertEqual(e.code, "error.missing_reviewer")
        self.assertEqual(fact(self.conn, self.fid)["review_status"], "flagged")
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM fact_reviews").fetchone()[0], 0,
            "a refused review must write nothing at all")

    def test_an_unknown_verdict_is_refused(self):
        self.assertEqual(self._refused(verdict="cross_family_verified").code,
                         "error.malformed_review")
        self.assertEqual(self._refused(verdict="agent_verified").code,
                         "error.malformed_review")

    def test_an_unknown_fact_is_refused(self):
        self.assertEqual(self._refused(fact_id=99999).code, "error.unknown_fact")

    def test_a_ref_that_is_not_the_region_served_is_refused(self):
        """The one checkable claim: the reviewer named the rectangle this store
        holds for that fact today. A re-extraction that moved the bbox makes the
        echo stale, and a review of a picture that no longer exists is refused."""
        self.assertEqual(self._refused(ref_id=the_ref(OTHER_BBOX)).code,
                         "error.ref_mismatch")
        self.assertEqual(self._refused(ref_id="").code, "error.ref_mismatch")

    def test_a_moved_bbox_invalidates_the_echo(self):
        stale = the_ref()
        self.conn.execute("UPDATE elements SET bbox=? WHERE element_id='e1'",
                          ("[72.02, 100.0, 300.0, 120.0]",))
        self.conn.commit()
        self.assertEqual(self._refused(ref_id=stale).code, "error.ref_mismatch")


# ------------------------------------------- obligation 6: no automated path
class TestNothingAutomatedReachesReviewed(unittest.TestCase):
    """Build-plan A1 cost 324 facts to the inverse of this test.

    `cross_family_verified` was PROMOTABLE, so two model families agreeing
    produced a curation-level-2 fact nobody had looked at. The fact review loop
    must not reintroduce that shape in a new place.
    """

    def setUp(self):
        self.conn = make_store()

    def tearDown(self):
        self.conn.close()

    def test_the_only_verdicts_are_human_verdicts(self):
        self.assertEqual(set(reviews.FACT_VERDICTS),
                         {"accepted", "corrected", "rejected"})
        for machine in ("cross_family_verified", "agent_verified", "auto",
                        "extracted", "reviewed"):
            self.assertNotIn(machine, reviews.FACT_VERDICTS)

    def test_agreement_between_readers_is_not_a_review(self):
        """No signature anywhere in the module takes a set of readings and
        returns a verdict. The only way in is one person, one fact, by name."""
        import inspect
        sig = inspect.signature(reviews.submit_fact_review)
        self.assertIn("reviewer", sig.parameters)
        self.assertNotIn("readers", sig.parameters)
        self.assertNotIn("candidates", sig.parameters)

    def test_a_rebuild_over_no_reviews_reviews_nothing(self):
        """The projection has exactly one source. Run the rebuild on a store
        full of flagged facts and no review records, and nothing is reviewed --
        so there is no path from `facts` alone to level 2."""
        ids = [add_fact(self.conn) for _ in range(3)]
        reviews.rebuild_fact_projection(self.conn)
        for fid in ids:
            self.assertEqual(fact(self.conn, fid)["review_status"], "flagged")
        self.assertEqual(reviews.reviewed_without_a_reviewer(self.conn), [])

    def test_every_reviewed_regex_fact_names_the_person_who_reviewed_it(self):
        fid = add_fact(self.conn)
        reviews.submit_fact_review(self.conn, fact_id=fid, reviewer="ann",
                                   verdict="accepted", ref_id=the_ref())
        self.assertEqual(reviews.reviewed_without_a_reviewer(self.conn), [])
        # Forge one the way an automated pass would: write the status directly.
        forged = add_fact(self.conn)
        self.conn.execute("UPDATE facts SET review_status='reviewed' WHERE fact_id=?",
                          (forged,))
        self.conn.commit()
        self.assertEqual(reviews.reviewed_without_a_reviewer(self.conn), [forged],
                         "an unaccountable level-2 fact must be detectable")

    def test_a_rebuild_removes_a_forged_review(self):
        forged = add_fact(self.conn)
        self.conn.execute("UPDATE facts SET review_status='reviewed', "
                          "reviewer='nobody' WHERE fact_id=?", (forged,))
        self.conn.commit()
        reviews.rebuild_fact_projection(self.conn)
        row = fact(self.conn, forged)
        self.assertEqual(row["review_status"], "flagged")
        self.assertIsNone(row["reviewer"])


# ------------------------------------------------------------------- rebuild
class TestRebuild(unittest.TestCase):
    def setUp(self):
        self.conn = make_store()

    def tearDown(self):
        self.conn.close()

    def _projection(self):
        return [tuple(r) for r in self.conn.execute(
            """SELECT fact_id, review_status, reviewed_value,
                      reviewed_value_normalized, reviewer, reviewed_at
                 FROM facts ORDER BY fact_id""")]

    def test_a_rebuild_reproduces_the_projection_exactly(self):
        a = add_fact(self.conn)
        b = add_fact(self.conn, fact_type="wind_speed_mph", value="150 mph",
                     normalized=150.0)
        c = add_fact(self.conn, element_id="e2", status="flagged")
        reviews.submit_fact_review(self.conn, fact_id=a, reviewer="ann",
                                   verdict="corrected", ref_id=the_ref(), value='36"')
        reviews.submit_fact_review(self.conn, fact_id=b, reviewer="bea",
                                   verdict="rejected", ref_id=the_ref())
        reviews.submit_fact_review(self.conn, fact_id=c, reviewer="cal",
                                   verdict="accepted", ref_id=the_ref(OTHER_BBOX))
        before = self._projection()
        reviews.rebuild_fact_projection(self.conn)
        self.assertEqual(self._projection(), before)

    def test_a_rebuild_replays_in_arrival_order(self):
        fid = add_fact(self.conn)
        reviews.submit_fact_review(self.conn, fact_id=fid, reviewer="ann",
                                   verdict="accepted", ref_id=the_ref(),
                                   reviewed_at="2026-08-28T12:00:00+00:00")
        # Backdated, but it ARRIVED second, so it wins -- same rule as
        # `rebuild_projection`, and the only way the two can agree.
        reviews.submit_fact_review(self.conn, fact_id=fid, reviewer="bea",
                                   verdict="rejected", ref_id=the_ref(),
                                   reviewed_at="2026-08-28T08:00:00+00:00")
        self.assertEqual(fact(self.conn, fid)["review_status"], "rejected")
        reviews.rebuild_fact_projection(self.conn)
        row = fact(self.conn, fid)
        self.assertEqual(row["review_status"], "rejected")
        self.assertEqual(row["reviewer"], "bea")

    def test_a_rebuild_leaves_table_promoted_facts_alone(self):
        """`table_review.promote` writes `reviewed` from its own record. This
        rebuild owns `fact_reviews` and must not demote a row it never wrote."""
        cand = self.conn.execute("""INSERT INTO table_read_candidates(document_id,
            version_id, page_no, crop_path, crop_sha256, reader, reader_kind,
            row_index, col_index, value, review_status, reviewer, created_at)
            VALUES ('doc-1','v1',6,'workspace/derived/x.png','deadbeef','ann',
                    'human',0,1,'24\"','accepted','ann',
                    '2026-08-28T00:00:00+00:00')""").lastrowid
        fid = add_fact(self.conn, status="reviewed",
                       extractor="table-review:accepted:calibration-A", ocr_derived=0)
        self.conn.execute("UPDATE facts SET from_candidate_id=? WHERE fact_id=?",
                          (cand, fid))
        self.conn.commit()
        out = reviews.rebuild_fact_projection(self.conn)
        self.assertEqual(fact(self.conn, fid)["review_status"], "reviewed")
        self.assertEqual(out["reviews_replayed"], 0)

    def test_a_review_of_a_vanished_fact_is_reported_not_applied(self):
        fid = add_fact(self.conn)
        reviews.submit_fact_review(self.conn, fact_id=fid, reviewer="ann",
                                   verdict="accepted", ref_id=the_ref())
        self.conn.execute("PRAGMA foreign_keys=OFF")
        self.conn.execute("DELETE FROM facts WHERE fact_id=?", (fid,))
        self.conn.commit()
        out = reviews.rebuild_fact_projection(self.conn)
        self.assertEqual(out["orphaned"], 1,
                         "a review naming a fact that re-extraction deleted must "
                         "be reported, never silently dropped")


# ---------------------------------------------------------- the live store
@requires_store
class TestTheRealQueue(unittest.TestCase):
    """The measurement. Nothing here may have been reviewed by anybody."""

    @classmethod
    def setUpClass(cls):
        cls.conn = connect(read_only=True)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_nothing_in_the_store_has_been_reviewed(self):
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(facts)")}
        if "reviewer" not in cols:
            self.skipTest("store predates the fact review loop; run `cli migrate`")
        n = self.conn.execute(
            "SELECT COUNT(*) FROM facts WHERE reviewer IS NOT NULL").fetchone()[0]
        self.assertEqual(n, 0, "a fact claims a reviewer; nobody has reviewed one")

    def test_no_reviewed_fact_lacks_an_accountable_record(self):
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(facts)")}
        if "reviewer" not in cols:
            self.skipTest("store predates the fact review loop; run `cli migrate`")
        self.assertEqual(reviews.reviewed_without_a_reviewer(self.conn), [])


if __name__ == "__main__":
    unittest.main()
