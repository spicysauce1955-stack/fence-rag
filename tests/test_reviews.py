"""The review loop — the first thing in the package that writes a PROMOTABLE status.

Everything here runs against a store built from `store.SCHEMA` in memory, so it
needs neither the corpus nor an ingested database and cannot damage either.
"""
import json
import sqlite3
import unittest

import context  # noqa: F401  -- puts the repo root on sys.path
from fence_evidence.reviews import (REVIEW_STATUSES, ReviewRefused,
                                    rebuild_projection, review_queue,
                                    review_summary, submit_review)
from fence_evidence.store import SCHEMA
from fence_evidence.table_review import PROMOTABLE

CROP = "a" * 64          # the crop the reviewer echoes back
OTHER = "b" * 64


def make_store() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute("""INSERT INTO documents(document_id, source_path, file_type,
                        corpus_track) VALUES ('doc-1', 'manuals/x/a.pdf', 'pdf', 'us')""")
    return conn


def add_reading(conn, *, reader="calibration-A", crop=CROP, page_no=6,
                cells=(("B", '24"'), ("C", '30"')), document_id="doc-1"):
    """One reader's grid: row i is [row_label, value]."""
    for r_i, (label, value) in enumerate(cells):
        for c_i, cell in enumerate((label, value)):
            conn.execute("""INSERT INTO table_read_candidates
                (document_id, version_id, page_no, crop_path, crop_sha256, reader,
                 reader_kind, is_table, row_index, col_index, row_label, col_label,
                 value, created_at)
                VALUES (?,?,?,?,?,?,'agent',1,?,?,?,?,?,'2026-08-27T00:00:00+00:00')""",
                (document_id, "v1", page_no, f"workspace/derived/{crop[:8]}.png", crop,
                 reader, r_i, c_i, label,
                 "WIND EXPOSURE" if c_i == 0 else "FOOTING DEPTH", cell))
    conn.commit()


def full_grid(cells=(("B", '24"'), ("C", '30"'))):
    return [{"row": r_i, "col": c_i, "value": v}
            for r_i, pair in enumerate(cells) for c_i, v in enumerate(pair)]


def annotations(conn):
    """Every review-derived column, in a stable order: what a rebuild must match."""
    return [tuple(r) for r in conn.execute(
        """SELECT candidate_id, review_status, reviewed_value, reviewer, reviewed_at
             FROM table_read_candidates ORDER BY candidate_id""")]


class TestSubmitReview(unittest.TestCase):
    def setUp(self):
        self.conn = make_store()
        add_reading(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_accepted_reading_becomes_promotable(self):
        out = submit_review(self.conn, crop_sha256=CROP, reviewer="alice",
                            verdict="accepted", grid=full_grid(), spans=[])
        self.assertEqual(out["cells_written"], 4)
        self.assertEqual(out["promotable"], 4)
        statuses = {r[0] for r in self.conn.execute(
            "SELECT review_status FROM table_read_candidates")}
        self.assertEqual(statuses, {"accepted"})
        for s in statuses:
            self.assertIn(s, PROMOTABLE)

    def test_a_changed_value_is_a_correction_not_an_acceptance(self):
        grid = full_grid((("B", '34"'), ("C", '30"')))
        out = submit_review(self.conn, crop_sha256=CROP, reviewer="alice",
                            verdict="accepted", grid=grid, spans=[])
        rows = self.conn.execute("""SELECT value, review_status, reviewed_value
            FROM table_read_candidates WHERE row_index=0 AND col_index=1""").fetchone()
        self.assertEqual(rows["review_status"], "corrected")
        self.assertEqual(rows["reviewed_value"], '34"')
        self.assertEqual(rows["value"], '24"', "the reading itself was overwritten")
        self.assertEqual(out["promotable"], 4, "a correction is promotable too")

    def test_typography_alone_is_not_a_correction(self):
        """`normalise` decides sameness, so a curly quote is not a finding."""
        grid = full_grid((("B", "24”"), ("C", '30"')))
        submit_review(self.conn, crop_sha256=CROP, reviewer="alice",
                      verdict="accepted", grid=grid, spans=[])
        row = self.conn.execute("""SELECT review_status, reviewed_value
            FROM table_read_candidates WHERE row_index=0 AND col_index=1""").fetchone()
        self.assertEqual(row["review_status"], "accepted")
        self.assertIsNone(row["reviewed_value"])

    def test_a_position_left_out_of_the_grid_stays_unreviewed(self):
        grid = [c for c in full_grid() if (c["row"], c["col"]) != (1, 1)]
        out = submit_review(self.conn, crop_sha256=CROP, reviewer="alice",
                            verdict="accepted", grid=grid, spans=[])
        self.assertEqual(out["cells_written"], 3)
        left = self.conn.execute("""SELECT review_status FROM table_read_candidates
            WHERE row_index=1 AND col_index=1""").fetchone()[0]
        self.assertEqual(left, "unreviewed",
                         "a cell nobody confirmed was promoted by omission")

    def test_rejected_covers_the_whole_table_and_promotes_nothing(self):
        out = submit_review(self.conn, crop_sha256=CROP, reviewer="alice",
                            verdict="rejected", grid=[], spans=[])
        self.assertEqual(out["cells_written"], 4)
        self.assertEqual(out["promotable"], 0)
        statuses = {r[0] for r in self.conn.execute(
            "SELECT review_status FROM table_read_candidates")}
        self.assertEqual(statuses, {"rejected"})

    def test_bracket_unclear_is_recorded_without_a_reviewed_value(self):
        """D4: the values can be right while the applicability is unreadable."""
        submit_review(self.conn, crop_sha256=CROP, reviewer="alice",
                      verdict="bracket_unclear", grid=full_grid(), spans=[])
        rows = self.conn.execute("""SELECT review_status, reviewed_value
            FROM table_read_candidates""").fetchall()
        self.assertTrue(all(r["review_status"] == "bracket_unclear" for r in rows))
        self.assertTrue(all(r["reviewed_value"] is None for r in rows))
        self.assertNotIn("bracket_unclear", PROMOTABLE)

    def test_spans_are_stored_and_survive_a_round_trip(self):
        spans = [{"row_from": 0, "row_to": 1, "col": 0, "text": "NON HVHZ"}]
        submit_review(self.conn, crop_sha256=CROP, reviewer="alice",
                      verdict="accepted", grid=full_grid(), spans=spans)
        stored = self.conn.execute("SELECT spans FROM table_reviews").fetchone()[0]
        self.assertEqual(json.loads(stored), spans)

    def test_no_spans_serialises_to_an_empty_list_never_null(self):
        """'no merges seen' and 'not asked' must stay distinguishable."""
        submit_review(self.conn, crop_sha256=CROP, reviewer="alice",
                      verdict="accepted", grid=full_grid(), spans=[])
        self.assertEqual(
            self.conn.execute("SELECT spans FROM table_reviews").fetchone()[0], "[]")

    def test_from_candidates_names_the_readings_it_came_from(self):
        submit_review(self.conn, crop_sha256=CROP, reviewer="alice",
                      verdict="accepted", grid=full_grid(), spans=[])
        stored = json.loads(
            self.conn.execute("SELECT from_candidates FROM table_reviews").fetchone()[0])
        ids = [r[0] for r in self.conn.execute(
            "SELECT candidate_id FROM table_read_candidates ORDER BY candidate_id")]
        self.assertEqual(stored, ids)

    def test_review_id_is_the_hash_of_crop_reviewer_and_time(self):
        import hashlib
        at = "2026-08-27T12:00:00+00:00"
        out = submit_review(self.conn, crop_sha256=CROP, reviewer="alice",
                            verdict="accepted", grid=full_grid(), spans=[],
                            reviewed_at=at)
        self.assertEqual(out["review_id"], hashlib.sha256(
            f"{CROP}:alice:{at}".encode()).hexdigest()[:16])
        self.assertEqual(len(out["review_id"]), 16)

    def test_the_record_and_the_projection_land_together(self):
        """Acceptance 1: one transaction, so neither can exist without the other."""
        submit_review(self.conn, crop_sha256=CROP, reviewer="alice",
                      verdict="accepted", grid=full_grid(), spans=[])
        review = self.conn.execute("SELECT * FROM table_reviews").fetchone()
        self.assertEqual(review["document_id"], "doc-1")
        self.assertEqual(review["page_no"], 6)
        stamped = self.conn.execute("""SELECT COUNT(*) FROM table_read_candidates
            WHERE reviewer='alice' AND reviewed_at=?""", (review["reviewed_at"],)
        ).fetchone()[0]
        self.assertEqual(stamped, 4)


class TestRefusals(unittest.TestCase):
    def setUp(self):
        self.conn = make_store()
        add_reading(self.conn)

    def tearDown(self):
        self.conn.close()

    def _refused(self, code, **kw):
        args = dict(crop_sha256=CROP, reviewer="alice", verdict="accepted",
                    grid=full_grid(), spans=[])
        args.update(kw)
        with self.assertRaises(ReviewRefused) as ctx:
            submit_review(self.conn, **args)
        self.assertEqual(ctx.exception.code, code)
        return ctx.exception

    def test_an_unknown_crop_is_refused_and_writes_nothing(self):
        """Acceptance 4. The echo is the only claim in the request we can check."""
        self._refused("error.crop_mismatch", crop_sha256=OTHER)
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM table_reviews").fetchone()[0], 0)
        self.assertEqual(
            {r[0] for r in self.conn.execute(
                "SELECT review_status FROM table_read_candidates")}, {"unreviewed"})

    def test_an_unknown_verdict_is_refused(self):
        self._refused("error.malformed_review", verdict="looks-fine")

    def test_a_span_outside_the_grid_ROWS_is_refused(self):
        """Acceptance 5. Rows are bounded; a span must cover rows that exist."""
        self._refused("error.malformed_review",
                      spans=[{"row_from": 0, "row_to": 9, "col": 0, "text": "x"}])
        self._refused("error.malformed_review",
                      spans=[{"row_from": -1, "row_to": 1, "col": 0, "text": "x"}])
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM table_reviews").fetchone()[0], 0)

    def test_a_span_may_name_a_column_the_readers_never_transcribed(self):
        """The bug this replaced a bound with: spans record what the grid lacks.

        Measured: every `wind_exposure_footing` crop in the queue was
        transcribed as columns 0..2 -- wind exposure, footing depth, max post
        spacing -- and the fourth column carrying "NON HVHZ" appears in no
        reading anywhere. Bounding `span.col` by the transcribed grid refused
        the one fact spans exist to record, and the end-to-end run on real data
        is what found it.
        """
        out = submit_review(self.conn, crop_sha256=CROP, reviewer="alice",
                            verdict="accepted",
                            grid=[{"row": 0, "col": 0, "value": "B"}],
                            spans=[{"row_from": 0, "row_to": 0, "col": 3,
                                    "text": "NON HVHZ"}])
        self.assertTrue(out["review_id"])
        stored = self.conn.execute("SELECT spans FROM table_reviews").fetchone()[0]
        self.assertIn("NON HVHZ", stored)

    def test_a_negative_span_column_is_still_refused(self):
        self._refused("error.malformed_review",
                      spans=[{"row_from": 0, "row_to": 1, "col": -1, "text": "x"}])

    def test_a_span_with_no_grid_is_refused(self):
        self._refused("error.malformed_review", grid=[],
                      spans=[{"row_from": 0, "row_to": 1, "col": 0, "text": "x"}])

    def test_a_malformed_grid_entry_is_refused(self):
        self._refused("error.malformed_review", grid=[{"row": 0, "col": 0}])
        self._refused("error.malformed_review",
                      grid=[{"row": "0", "col": 0, "value": "x"}])
        self._refused("error.malformed_review",
                      grid=[{"row": True, "col": 0, "value": "x"}])
        self._refused("error.malformed_review", grid=[{"row": 0, "col": 0, "value": 24}])

    def test_a_grid_that_gives_one_position_two_values_is_refused(self):
        self._refused("error.malformed_review",
                      grid=[{"row": 0, "col": 0, "value": "B"},
                            {"row": 0, "col": 0, "value": "C"}])

    def test_the_code_travels_on_the_exception(self):
        e = self._refused("error.malformed_review", verdict="nope")
        self.assertTrue(e.code.startswith("error."),
                        "an HTTP error borrowed the warning registry namespace")
        self.assertIn("nope", str(e))


class TestRebuildProjection(unittest.TestCase):
    """Acceptance 3: the projection is a cache of `table_reviews`, not a second truth."""

    def setUp(self):
        self.conn = make_store()
        add_reading(self.conn, reader="calibration-A")
        add_reading(self.conn, reader="codex-C")

    def tearDown(self):
        self.conn.close()

    def test_a_backdated_review_replays_in_arrival_order(self):
        """Replaying by `reviewed_at` diverges from what submit_review did.

        submit_review applies reviews as they arrive, last write wins. If the
        rebuild orders by timestamp instead, a review submitted second but
        stamped earlier loses on rebuild and wins live -- the projection and its
        source disagree, which is the one thing acceptance 3 forbids. Ordering
        the replay by rowid makes the rebuild reproduce arrival order exactly.
        """
        submit_review(self.conn, crop_sha256=CROP, reviewer="alice",
                      verdict="accepted", grid=[{"row": 0, "col": 0, "value": "AAA"}],
                      spans=[], reviewed_at="2026-08-27T12:00:10")
        submit_review(self.conn, crop_sha256=CROP, reviewer="bob",
                      verdict="accepted", grid=[{"row": 0, "col": 0, "value": "BBB"}],
                      spans=[], reviewed_at="2026-08-27T12:00:05")   # backdated
        q = ("SELECT reviewed_value, reviewer, review_status FROM table_read_candidates"
             " WHERE row_index=0 AND col_index=0")
        live = [tuple(r) for r in self.conn.execute(q)]
        rebuild_projection(self.conn)
        self.assertEqual(live, [tuple(r) for r in self.conn.execute(q)])
        # and it is the later ARRIVAL that stands, not the later timestamp
        self.assertEqual(live[0][1], "bob")

    def test_rebuild_is_byte_identical(self):
        submit_review(self.conn, crop_sha256=CROP, reviewer="alice",
                      verdict="accepted", grid=full_grid((("B", '34"'), ("C", '30"'))),
                      spans=[], reviewed_at="2026-08-27T09:00:00+00:00")
        before = annotations(self.conn)
        out = rebuild_projection(self.conn)
        self.assertEqual(annotations(self.conn), before)
        self.assertEqual(out["reviews_replayed"], 1)
        self.assertEqual(out["cells_written"], 8)

    def test_rebuild_replays_several_reviews_in_review_order(self):
        submit_review(self.conn, crop_sha256=CROP, reviewer="alice",
                      verdict="rejected", grid=[], spans=[],
                      reviewed_at="2026-08-27T09:00:00+00:00")
        submit_review(self.conn, crop_sha256=CROP, reviewer="bob",
                      verdict="accepted", grid=full_grid(), spans=[],
                      reviewed_at="2026-08-27T10:00:00+00:00")
        before = annotations(self.conn)
        rebuild_projection(self.conn)
        self.assertEqual(annotations(self.conn), before)
        self.assertEqual({r[0] for r in self.conn.execute(
            "SELECT review_status FROM table_read_candidates")}, {"accepted"},
            "the later review did not win the replay")

    def test_rebuild_is_idempotent(self):
        submit_review(self.conn, crop_sha256=CROP, reviewer="alice",
                      verdict="accepted", grid=full_grid(), spans=[])
        rebuild_projection(self.conn)
        once = annotations(self.conn)
        rebuild_projection(self.conn)
        self.assertEqual(annotations(self.conn), once)

    def test_rebuild_clears_an_annotation_no_review_supports(self):
        """A hand-set status with no record behind it must not survive a rebuild."""
        self.conn.execute("""UPDATE table_read_candidates
            SET review_status='accepted', reviewer='ghost' WHERE candidate_id=1""")
        self.conn.commit()
        rebuild_projection(self.conn)
        row = self.conn.execute("""SELECT review_status, reviewer
            FROM table_read_candidates WHERE candidate_id=1""").fetchone()
        self.assertEqual(row["review_status"], "unreviewed")
        self.assertIsNone(row["reviewer"])

    def test_rebuild_leaves_machine_statuses_alone(self):
        """`cross_family_verified` is not review-derived, so a rebuild must not eat it."""
        self.conn.execute("""UPDATE table_read_candidates
            SET review_status='cross_family_verified' WHERE candidate_id=1""")
        self.conn.commit()
        rebuild_projection(self.conn)
        self.assertEqual(self.conn.execute(
            "SELECT review_status FROM table_read_candidates WHERE candidate_id=1"
        ).fetchone()[0], "cross_family_verified")
        self.assertNotIn("cross_family_verified", REVIEW_STATUSES)


class TestQueueAndSummary(unittest.TestCase):
    def setUp(self):
        self.conn = make_store()
        add_reading(self.conn, reader="calibration-A")
        add_reading(self.conn, reader="codex-C")
        add_reading(self.conn, reader="calibration-A", crop=OTHER, page_no=17)

    def tearDown(self):
        self.conn.close()

    def test_queue_lists_one_entry_per_crop_with_its_counts(self):
        q = review_queue(self.conn)
        self.assertEqual(len(q), 2)
        by_crop = {e["crop_sha256"]: e for e in q}
        self.assertEqual(by_crop[CROP]["readers"], 2)
        self.assertEqual(by_crop[CROP]["cells"], 4,
                         "counts grid positions once, not once per reader")
        self.assertEqual(by_crop[OTHER]["readers"], 1)
        self.assertEqual(by_crop[CROP]["page_no"], 6)

    def test_a_reviewed_crop_leaves_the_queue(self):
        submit_review(self.conn, crop_sha256=CROP, reviewer="alice",
                      verdict="accepted", grid=full_grid(), spans=[])
        self.assertEqual([e["crop_sha256"] for e in review_queue(self.conn)], [OTHER])

    def test_queue_honours_its_limit(self):
        self.assertEqual(len(review_queue(self.conn, limit=1)), 1)

    def test_summary_counts_verdicts_reviewers_and_what_became_promotable(self):
        s = review_summary(self.conn)
        self.assertEqual(s["reviews"], 0)
        self.assertEqual(s["crops_pending"], 2)
        submit_review(self.conn, crop_sha256=CROP, reviewer="alice",
                      verdict="accepted", grid=full_grid(), spans=[])
        submit_review(self.conn, crop_sha256=OTHER, reviewer="bob",
                      verdict="rejected", grid=[], spans=[])
        s = review_summary(self.conn)
        self.assertEqual(s["reviews"], 2)
        self.assertEqual(s["by_verdict"], {"accepted": 1, "rejected": 1})
        self.assertEqual(s["reviewers"], ["alice", "bob"])
        self.assertEqual(s["crops_reviewed"], 2)
        self.assertEqual(s["crops_pending"], 0)
        self.assertEqual(s["promotable"], 8, "both readers' cells of the accepted crop")
        self.assertEqual(s["cells_annotated"], 12)


if __name__ == "__main__":
    unittest.main()
