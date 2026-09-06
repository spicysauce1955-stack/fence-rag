"""A step review must survive a rebuilt store, not only a re-cut queue.

`step_reviews` lives in the store, and the store is rebuildable from the corpus
— which means every review in it is one `ingest --all` away from being gone.
The ledger is the committed, deterministic record that makes a human judgement
durable, and until now it carried table and fact reviews only.

Adding a third kind moves `LEDGER_SCHEMA` from 1 to 2, because the header
carries per-kind counts and its shape changes. `read_ledger` accepts both: a
schema-1 file is a valid ledger that predates step reviews, and refusing to
read one would strand every export taken before today.
"""
import json
import sqlite3
import unittest

from context import ROOT  # noqa: F401
from fence_evidence import reviews, steps
from fence_evidence.reviews import (LEDGER_SCHEMA, ReviewRefused, build_ledger,
                                    import_reviews, ledger_bytes,
                                    submit_step_review)
from fence_evidence.store import STEP_CANDIDATES_DDL, STEP_REVIEWS_DDL

BLOCK = "• I nsert post in hole\n• Determine rough height"


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
        CREATE TABLE table_reviews (review_id TEXT PRIMARY KEY, crop_sha256 TEXT,
                                    document_id TEXT, page_no INTEGER,
                                    reviewer TEXT, reviewed_at TEXT, verdict TEXT,
                                    grid TEXT, spans TEXT, from_candidates TEXT,
                                    notes TEXT);
        CREATE TABLE table_read_candidates (candidate_id INTEGER PRIMARY KEY,
                                            crop_sha256 TEXT, review_status TEXT,
                                            reviewed_value TEXT, reviewer TEXT,
                                            reviewed_at TEXT, value TEXT,
                                            row_index INTEGER, col_index INTEGER,
                                            document_id TEXT, page_no INTEGER);
        CREATE TABLE facts (fact_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            element_id TEXT, fact_type TEXT, value_original TEXT,
                            review_status TEXT, reviewed_value TEXT,
                            reviewed_value_normalized TEXT, reviewer TEXT,
                            reviewed_at TEXT, value_normalized TEXT,
                            from_candidate_id INTEGER, unit_normalized TEXT,
                            ocr_derived INTEGER);
    """)
    conn.executescript(STEP_CANDIDATES_DDL)
    conn.executescript(STEP_REVIEWS_DDL)
    reviews.ensure_fact_reviews(conn)
    conn.execute("INSERT INTO documents VALUES ('doc-1','a.pdf','installation_manual',"
                 "'Guide',NULL)")
    conn.execute("INSERT INTO elements VALUES ('el-1','doc-1','v1',8,7,'list',?,NULL,"
                 "'pdf_text_layer','[]','[54,290,275,370]')", (BLOCK,))
    steps.propose(conn, document_id="doc-1", page_no=8)
    return conn


def review_one(conn, seq=0, **kw):
    row = conn.execute("SELECT * FROM step_candidates WHERE seq=?", (seq,)).fetchone()
    args = dict(element_id=row["element_id"], char_start=row["char_start"],
                char_end=row["char_end"], text_seen=row["text_raw"],
                reviewer="a-person", verdict="accepted",
                step_kind="installation", step_scope="post",
                slot_target={"kind": "PostSlot", "key": "post"})
    args.update(kw)
    return submit_step_review(conn, **args)


class TestAStepReviewReachesTheLedger(unittest.TestCase):
    def test_the_schema_moved(self):
        self.assertEqual(LEDGER_SCHEMA, 2)

    def test_a_step_review_is_a_line(self):
        conn = scratch()
        review_one(conn)
        kinds = [r["kind"] for r in build_ledger(conn)]
        self.assertIn("step_review", kinds)

    def test_the_header_counts_it(self):
        conn = scratch()
        review_one(conn)
        header = build_ledger(conn)[0]
        self.assertEqual(header["step_reviews"], 1)
        self.assertEqual(header["schema"], 2)

    def test_no_moving_row_id_is_carried(self):
        """`candidate_id` is re-minted on every re-cut of the queue. A ledger
        that named one would describe a store rather than a review."""
        conn = scratch()
        review_one(conn)
        line = [r for r in build_ledger(conn) if r["kind"] == "step_review"][0]
        self.assertNotIn("candidate_id", line)
        self.assertIn("element_id", line)
        self.assertIn("char_start", line)
        self.assertIn("text_seen", line)

    def test_it_is_deterministic(self):
        conn = scratch()
        review_one(conn)
        self.assertEqual(ledger_bytes(build_ledger(conn)),
                         ledger_bytes(build_ledger(conn)))


class TestItReplaysIntoARebuiltStore(unittest.TestCase):
    """The point of the whole exercise: a store is rebuildable and a judgement
    is not, so the judgement has to live somewhere the rebuild cannot reach."""

    def test_a_review_replays_after_the_store_is_wiped(self):
        conn = scratch()
        review_one(conn)
        blob = ledger_bytes(build_ledger(conn))

        fresh = scratch()                       # the same corpus, no reviews
        self.assertEqual(
            fresh.execute("SELECT COUNT(*) FROM step_reviews").fetchone()[0], 0)
        path = ROOT / "workspace" / "tests" / "step-ledger-replay.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
        try:
            out = import_reviews(fresh, path, dry_run=False)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(out["step_reviews"]["new"], 1)
        row = fresh.execute("SELECT * FROM step_candidates WHERE seq=0").fetchone()
        self.assertEqual(row["review_status"], "accepted")
        self.assertEqual(row["reviewer"], "a-person")

    def test_replaying_twice_changes_nothing(self):
        conn = scratch()
        review_one(conn)
        blob = ledger_bytes(build_ledger(conn))
        path = ROOT / "workspace" / "tests" / "step-ledger-idem.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
        try:
            import_reviews(conn, path, dry_run=False)
            out = import_reviews(conn, path, dry_run=False)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(out["step_reviews"]["new"], 0)
        self.assertEqual(out["step_reviews"]["identical"], 1)


class TestItStillReadsTheOldSchema(unittest.TestCase):
    def test_a_schema_1_ledger_is_not_refused(self):
        """A file exported before today is a valid ledger that predates step
        reviews. Refusing it would strand every export already taken."""
        conn = scratch()
        path = ROOT / "workspace" / "tests" / "step-ledger-old.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(
            json.dumps({"kind": "ledger", "schema": 1, "fact_reviews": 0,
                        "table_reviews": 0}, sort_keys=True).encode() + b"\n")
        try:
            out = import_reviews(conn, path)
        finally:
            path.unlink(missing_ok=True)
        self.assertIn("step_reviews", out)

    def test_an_unknown_schema_is_still_refused(self):
        conn = scratch()
        path = ROOT / "workspace" / "tests" / "step-ledger-future.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(
            json.dumps({"kind": "ledger", "schema": 99}, sort_keys=True).encode() + b"\n")
        try:
            with self.assertRaises(ReviewRefused):
                import_reviews(conn, path)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
