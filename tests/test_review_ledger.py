"""The review ledger — G49's two halves: re-attachment and durability.

A human review is the one thing in this system that cannot be rebuilt from the
read-only corpus. `cli ingest` regenerates elements, `cli facts --extract`
regenerates assertions, `cli rebuild-index` regenerates the projection
byte-identically. A review is a judgement a person made looking at a page image,
and until this module's subject existed it lived only as rows in a git-ignored
SQLite file.

Two properties are asserted here and nowhere else:

* **A regex re-extraction does not destroy a fact review.** `extract_facts`
  deletes and re-inserts every `regex-%` fact, so the row id a review names is
  gone. The review is re-bound on *evidence* — the element it cites, the fact
  type, and the value it was reviewing — and where that evidence does not name
  exactly one fact, nothing is guessed. A review silently attached to the wrong
  fact is worse than one left unbound, because it launders a person's signature
  onto a value they never saw.
* **The ledger is deterministic and id-free.** `table_reviews` is keyed on
  `crop_sha256`, the bytes of the crop; the fact half is keyed on the same
  evidence the re-attachment matches on, and carries **no `fact_id` at all**,
  because a fact id moves on every re-extraction. Two exports over identical
  review state are byte-identical, and a ledger replays into a store that minted
  entirely different fact ids.

Nothing here records a review of the real corpus. Every review in this file is
fabricated in an in-memory store by a test; obligation 6 is about the live store
and `TestTheCommittedLedger` is the only class that touches it, read-only.
"""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import context  # noqa: F401  -- puts the repo root on sys.path
from context import requires_store
from fence_evidence import reviews
from fence_evidence.facts import extract_facts
from fence_evidence.paths import CorpusWriteError
from fence_evidence.store import SCHEMA

SHA = "b" * 64
BBOX = "[72.0, 100.0, 300.0, 120.0]"
TEXT = "Set posts in a footing depth of 24 in. minimum."
CROP_A = "1" * 64
CROP_B = "2" * 64


def make_store(*, text: str = TEXT) -> sqlite3.Connection:
    """A store with one document, one page, one element and no facts.

    `PRAGMA foreign_keys=ON` because `store.connect` sets it, and the FK from
    `fact_reviews.fact_id` to `facts` is exactly what makes the naive
    delete-and-re-insert fail rather than orphan.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("""INSERT INTO documents(document_id, source_path, file_type,
                    corpus_track) VALUES ('doc-1','manuals/x/a.pdf','pdf','us')""")
    conn.execute("""INSERT INTO document_versions(version_id, document_id, sha256,
                    ingested_at) VALUES ('v1','doc-1',?, '2026-08-28T00:00:00+00:00')""",
                 (SHA,))
    conn.execute("""INSERT INTO pages(page_id, version_id, page_no, width, height,
                    extraction_method) VALUES ('p1','v1',6,612.0,792.0,'ocr')""")
    conn.execute("""INSERT INTO elements(element_id, page_id, version_id,
        document_id, page_no, ordinal, element_type, text, text_source,
        ocr_confidence, bbox) VALUES ('e1','p1','v1','doc-1',6,1,'paragraph',
        ?, 'ocr', 41.2, ?)""", (text, BBOX))
    conn.commit()
    return conn


def add_fact(conn, *, element_id="e1", fact_type="footing_depth_in",
             value="depth of 24 in.", normalized=24.0, status="flagged",
             extractor="regex-v1") -> int:
    cur = conn.execute("""INSERT INTO facts(document_id, version_id, page_no,
        element_id, fact_type, subject, value_original, value_normalized,
        unit_original, unit_normalized, conditions, evidence_text, extractor,
        ocr_derived, review_status, created_at)
        VALUES ('doc-1','v1',6,?,?,NULL,?,?,'in','in','{}','...',?,1,?,
                '2026-08-28T00:00:00+00:00')""",
        (element_id, fact_type, value, normalized, extractor, status))
    conn.commit()
    return cur.lastrowid


def review_a_fact(conn, fact_id, *, reviewer="a.person", verdict="accepted",
                  value=None, at="2026-08-28T09:00:00+00:00", notes=None):
    return reviews.submit_fact_review(
        conn, fact_id=fact_id, reviewer=reviewer, verdict=verdict,
        ref_id=reviews.fact_ref_id(conn, fact_id), value=value, notes=notes,
        reviewed_at=at)


def add_table_review(conn, *, review_id, crop=CROP_A, reviewer="a.person",
                     at="2026-08-28T09:00:00+00:00", verdict="accepted",
                     grid=None, spans=None, candidates=None, notes=None):
    conn.execute("""INSERT INTO table_reviews(review_id, crop_sha256, document_id,
        page_no, reviewer, reviewed_at, verdict, grid, spans, from_candidates,
        notes) VALUES (?,?, 'doc-1', 6, ?,?,?,?,?,?,?)""",
        (review_id, crop, reviewer, at, verdict,
         json.dumps(grid if grid is not None else [{"row": 0, "col": 0, "value": "24"}]),
         json.dumps(spans if spans is not None else []),
         json.dumps(candidates if candidates is not None else [1, 2]), notes))
    conn.commit()


def orphan_every_fact(conn):
    """Delete the facts out from under the reviews, as an old store could.

    With `foreign_keys=ON` this is not reachable through `extract_facts` any
    more, but a store written before the review loop existed can hold one, and
    `reattach_fact_reviews` has to cope with it.
    """
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("DELETE FROM facts")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.commit()


# ======================================================================
# A. Re-attachment
# ======================================================================
class TestReattachment(unittest.TestCase):
    def setUp(self):
        self.conn = make_store()

    def tearDown(self):
        self.conn.close()

    def test_a_review_whose_fact_still_exists_is_left_alone(self):
        fid = add_fact(self.conn)
        review_a_fact(self.conn, fid)
        out = reviews.reattach_fact_reviews(self.conn)
        self.assertEqual(out["considered"], 0)
        self.assertEqual(out["reattached"], 0)
        self.assertEqual(
            self.conn.execute("SELECT fact_id FROM fact_reviews").fetchone()[0], fid)

    def test_an_orphan_finds_the_one_fact_carrying_its_evidence(self):
        fid = add_fact(self.conn)
        review_a_fact(self.conn, fid)
        orphan_every_fact(self.conn)
        new = add_fact(self.conn)          # the same evidence, a new row id
        self.assertNotEqual(new, fid, "AUTOINCREMENT must not reuse the old id")

        out = reviews.reattach_fact_reviews(self.conn)
        self.assertEqual(out["reattached"], 1)
        self.assertEqual(out["still_orphaned"], 0)
        self.assertEqual(out["ambiguous"], 0)
        self.assertEqual(
            self.conn.execute("SELECT fact_id FROM fact_reviews").fetchone()[0], new)

    def test_two_matching_facts_are_ambiguous_and_nothing_is_guessed(self):
        fid = add_fact(self.conn)
        review_a_fact(self.conn, fid)
        orphan_every_fact(self.conn)
        add_fact(self.conn)
        add_fact(self.conn)               # two rows carry the same evidence

        out = reviews.reattach_fact_reviews(self.conn)
        self.assertEqual(out["reattached"], 0)
        self.assertEqual(out["ambiguous"], 1)
        self.assertEqual(out["still_orphaned"], 1)
        self.assertEqual(
            self.conn.execute("SELECT fact_id FROM fact_reviews").fetchone()[0], fid,
            "an ambiguous review must keep the id it had, not pick a winner")
        self.assertEqual(len(out["detail"]["ambiguous"]), 1)
        self.assertEqual(len(out["detail"]["ambiguous"][0]["candidates"]), 2)

    def test_a_review_is_never_bound_to_a_fact_with_a_different_value(self):
        fid = add_fact(self.conn)
        review_a_fact(self.conn, fid)
        orphan_every_fact(self.conn)
        add_fact(self.conn, value="depth of 36 in.", normalized=36.0)

        out = reviews.reattach_fact_reviews(self.conn)
        self.assertEqual(out["reattached"], 0,
                         "36 inches is not the number the person signed for")
        self.assertEqual(out["still_orphaned"], 1)

    def test_a_value_the_extraction_no_longer_produces_is_reported_not_swallowed(self):
        fid = add_fact(self.conn)
        review_a_fact(self.conn, fid)
        orphan_every_fact(self.conn)
        add_fact(self.conn, value="depth of 36 in.", normalized=36.0)

        out = reviews.reattach_fact_reviews(self.conn)
        self.assertEqual(out["value_changed"], 1)
        changed = out["detail"]["value_changed"][0]
        self.assertEqual(changed["value_before"], "depth of 24 in.")
        self.assertEqual(changed["now_extracted"], ["depth of 36 in."])

    def test_a_fact_type_that_vanished_is_orphaned_but_not_a_value_change(self):
        fid = add_fact(self.conn)
        review_a_fact(self.conn, fid)
        orphan_every_fact(self.conn)

        out = reviews.reattach_fact_reviews(self.conn)
        self.assertEqual(out["still_orphaned"], 1)
        self.assertEqual(out["value_changed"], 0)
        self.assertEqual(len(out["detail"]["orphaned"]), 1)

    def test_a_dry_run_reports_and_rebinds_nothing(self):
        fid = add_fact(self.conn)
        review_a_fact(self.conn, fid)
        orphan_every_fact(self.conn)
        new = add_fact(self.conn)

        out = reviews.reattach_fact_reviews(self.conn, dry_run=True)
        self.assertEqual(out["reattached"], 1)
        self.assertEqual(
            self.conn.execute("SELECT fact_id FROM fact_reviews").fetchone()[0], fid)
        self.assertNotEqual(new, fid)

    def test_two_reviews_of_one_fact_move_together(self):
        fid = add_fact(self.conn)
        review_a_fact(self.conn, fid, at="2026-08-28T09:00:00+00:00")
        review_a_fact(self.conn, fid, verdict="corrected", value='36"',
                      at="2026-08-28T10:00:00+00:00")
        orphan_every_fact(self.conn)
        new = add_fact(self.conn)

        out = reviews.reattach_fact_reviews(self.conn)
        self.assertEqual(out["reattached"], 2)
        self.assertEqual({r[0] for r in self.conn.execute(
            "SELECT DISTINCT fact_id FROM fact_reviews")}, {new})

    def test_two_different_facts_sharing_one_anchor_are_ambiguous(self):
        a = add_fact(self.conn)
        b = add_fact(self.conn)           # identical evidence, two rows
        review_a_fact(self.conn, a)
        review_a_fact(self.conn, b, reviewer="another.person")
        orphan_every_fact(self.conn)
        add_fact(self.conn)               # one row now carries that evidence

        out = reviews.reattach_fact_reviews(self.conn)
        self.assertEqual(out["reattached"], 0,
                         "two people reviewed two rows; collapsing them onto one "
                         "would put a signature on a row nobody saw")
        self.assertEqual(out["ambiguous"], 2)


# ======================================================================
# A2. The re-extraction itself
# ======================================================================
class TestExtractFactsKeepsReviews(unittest.TestCase):
    def test_a_re_extraction_preserves_the_review_and_its_projection(self):
        conn = make_store()
        self.addCleanup(conn.close)
        extract_facts(conn=conn)
        fid = conn.execute("SELECT fact_id FROM facts").fetchone()[0]
        review_a_fact(conn, fid)

        out = extract_facts(conn=conn)
        self.assertEqual(out["facts"], 1)
        self.assertEqual(out["review_reattachment"]["reattached"], 1)
        self.assertEqual(out["review_reattachment"]["still_orphaned"], 0)

        # one review, one fact, and the fact carries the person's name again
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM fact_reviews").fetchone()[0], 1)
        row = conn.execute("SELECT * FROM facts").fetchone()
        self.assertEqual(row["review_status"], "reviewed")
        self.assertEqual(row["reviewer"], "a.person")
        self.assertEqual(
            conn.execute("SELECT fact_id FROM fact_reviews").fetchone()[0],
            row["fact_id"])

    def test_a_re_extraction_never_raises_a_foreign_key_error(self):
        """The bug this closes: with `foreign_keys=ON` the naive DELETE aborts.

        `fact_reviews.fact_id` is `NOT NULL REFERENCES facts(fact_id)`, so
        `DELETE FROM facts WHERE extractor LIKE 'regex-%'` raises
        `FOREIGN KEY constraint failed` the moment one fact has been reviewed --
        the whole re-extraction fails rather than orphaning anything.
        """
        conn = make_store()
        self.addCleanup(conn.close)
        extract_facts(conn=conn)
        review_a_fact(conn, conn.execute("SELECT fact_id FROM facts").fetchone()[0])
        extract_facts(conn=conn)          # must not raise

    def test_a_reviewed_fact_the_extractor_no_longer_produces_is_retained(self):
        conn = make_store()
        self.addCleanup(conn.close)
        extract_facts(conn=conn)
        fid = conn.execute("SELECT fact_id FROM facts").fetchone()[0]
        review_a_fact(conn, fid)

        # the extractor changes its mind about the number a person checked
        conn.execute("UPDATE elements SET text = ? WHERE element_id='e1'",
                     ("Set posts in a footing depth of 36 in. minimum.",))
        conn.commit()
        out = extract_facts(conn=conn)

        self.assertEqual(out["review_reattachment"]["value_changed"], 1)
        self.assertEqual(
            conn.execute("SELECT fact_id FROM fact_reviews").fetchone()[0], fid,
            "the reviewed fact is kept; a person's signature is not deleted by "
            "a regex regression")
        values = {r[0] for r in conn.execute("SELECT value_original FROM facts")}
        self.assertEqual(values, {"depth of 24 in.", "depth of 36 in."})

    def test_an_unreviewed_fact_is_still_regenerated_wholesale(self):
        conn = make_store()
        self.addCleanup(conn.close)
        extract_facts(conn=conn)
        first = conn.execute("SELECT fact_id FROM facts").fetchone()[0]
        second = extract_facts(conn=conn)
        self.assertEqual(second["facts"], 1)
        self.assertNotEqual(
            conn.execute("SELECT fact_id FROM facts").fetchone()[0], first,
            "with nothing reviewed, re-extraction is still delete-and-re-insert")


# ======================================================================
# B. The ledger
# ======================================================================
class TestLedgerShape(unittest.TestCase):
    def setUp(self):
        self.conn = make_store()

    def tearDown(self):
        self.conn.close()

    def lines(self):
        return [json.loads(l) for l in
                reviews.ledger_bytes(reviews.build_ledger(self.conn))
                .decode("utf-8").splitlines()]

    def test_an_empty_ledger_is_a_header_and_nothing_else(self):
        lines = self.lines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], {"kind": "ledger", "schema": reviews.LEDGER_SCHEMA,
                                    "fact_reviews": 0, "table_reviews": 0})

    def test_a_fact_review_line_carries_no_fact_id(self):
        fid = add_fact(self.conn)
        review_a_fact(self.conn, fid)
        rec = [l for l in self.lines() if l["kind"] == "fact_review"][0]
        self.assertNotIn("fact_id", rec,
                         "a fact id moves on every re-extraction; keying the "
                         "ledger on one would make it un-replayable")
        for field in ("element_id", "fact_type", "value_before", "ref_id",
                      "reviewer", "reviewed_at", "verdict", "status_before"):
            self.assertIn(field, rec)

    def test_a_table_review_line_keeps_the_crop_digest(self):
        add_table_review(self.conn, review_id="r1")
        rec = [l for l in self.lines() if l["kind"] == "table_review"][0]
        self.assertEqual(rec["crop_sha256"], CROP_A)
        self.assertEqual(rec["grid"], [{"row": 0, "col": 0, "value": "24"}])

    def test_the_header_counts_the_body(self):
        add_table_review(self.conn, review_id="r1")
        review_a_fact(self.conn, add_fact(self.conn))
        header = self.lines()[0]
        self.assertEqual(header["table_reviews"], 1)
        self.assertEqual(header["fact_reviews"], 1)


class TestLedgerDeterminism(unittest.TestCase):
    def test_two_exports_over_identical_state_are_byte_identical(self):
        conn = make_store()
        self.addCleanup(conn.close)
        review_a_fact(conn, add_fact(conn))
        add_table_review(conn, review_id="r1")
        first = reviews.ledger_bytes(reviews.build_ledger(conn))
        second = reviews.ledger_bytes(reviews.build_ledger(conn))
        self.assertEqual(first, second)

    def test_insertion_order_does_not_change_the_bytes(self):
        def build(order):
            conn = make_store()
            self.addCleanup(conn.close)
            for rid, crop, at in order:
                add_table_review(conn, review_id=rid, crop=crop, at=at)
            return reviews.ledger_bytes(reviews.build_ledger(conn))

        a = build([("r1", CROP_A, "2026-08-28T09:00:00+00:00"),
                   ("r2", CROP_B, "2026-08-28T10:00:00+00:00")])
        b = build([("r2", CROP_B, "2026-08-28T10:00:00+00:00"),
                   ("r1", CROP_A, "2026-08-28T09:00:00+00:00")])
        self.assertEqual(a, b)

    def test_the_ledger_holds_no_clock_reading_of_its_own(self):
        conn = make_store()
        self.addCleanup(conn.close)
        review_a_fact(conn, add_fact(conn))
        text = reviews.ledger_bytes(reviews.build_ledger(conn)).decode()
        self.assertNotIn("generated_at", text)
        self.assertNotIn("exported_at", text)

    def test_every_line_is_canonical_json(self):
        conn = make_store()
        self.addCleanup(conn.close)
        review_a_fact(conn, add_fact(conn))
        add_table_review(conn, review_id="r1")
        from fence_evidence.canonical import canonical_bytes
        for line in reviews.ledger_bytes(reviews.build_ledger(conn)).splitlines():
            self.assertEqual(canonical_bytes(json.loads(line)), line)


class TestExportPath(unittest.TestCase):
    def test_the_out_path_is_injectable(self):
        conn = make_store()
        self.addCleanup(conn.close)
        review_a_fact(conn, add_fact(conn))
        with tempfile.TemporaryDirectory(dir=str(context.ROOT / "workspace" / "tests")) as d:
            target = Path(d) / "ledger.jsonl"
            out = reviews.export_reviews(conn, target)
            self.assertTrue(target.is_file())
            self.assertEqual(out["fact_reviews"], 1)
            self.assertEqual(target.read_bytes(),
                             reviews.ledger_bytes(reviews.build_ledger(conn)))

    def test_a_path_outside_the_workspace_is_refused(self):
        conn = make_store()
        self.addCleanup(conn.close)
        with self.assertRaises(CorpusWriteError):
            reviews.export_reviews(conn, context.ROOT / "data" / "ledger.jsonl")

    def test_the_default_path_is_the_committed_one(self):
        self.assertEqual(reviews.LEDGER_PATH.name, "review-ledger.jsonl")
        self.assertEqual(reviews.LEDGER_PATH.parent.name, "catalog")


# ----------------------------------------------------------------- import
class TestImport(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory(
            dir=str(context.ROOT / "workspace" / "tests"))
        self.addCleanup(self.dir.cleanup)
        self.path = Path(self.dir.name) / "ledger.jsonl"

    def source(self):
        conn = make_store()
        self.addCleanup(conn.close)
        review_a_fact(conn, add_fact(conn))
        add_table_review(conn, review_id="r1")
        reviews.export_reviews(conn, self.path)
        return conn

    def test_import_is_a_dry_run_by_default(self):
        self.source()
        fresh = make_store()
        self.addCleanup(fresh.close)
        add_fact(fresh)
        out = reviews.import_reviews(fresh, self.path)
        self.assertFalse(out["applied"])
        self.assertEqual(out["inserted"], 2)
        self.assertEqual(fresh.execute("SELECT COUNT(*) FROM table_reviews").fetchone()[0], 0)
        self.assertEqual(fresh.execute("SELECT COUNT(*) FROM fact_reviews").fetchone()[0], 0)

    def test_import_is_idempotent(self):
        self.source()
        fresh = make_store()
        self.addCleanup(fresh.close)
        add_fact(fresh)
        reviews.import_reviews(fresh, self.path, dry_run=False)
        again = reviews.import_reviews(fresh, self.path, dry_run=False)
        self.assertEqual(again["inserted"], 0)
        self.assertEqual(again["identical"], 2)
        self.assertEqual(again["conflicts"], 0)
        self.assertEqual(fresh.execute("SELECT COUNT(*) FROM fact_reviews").fetchone()[0], 1)

    def test_a_differing_review_is_a_conflict_and_nothing_is_written(self):
        self.source()
        fresh = make_store()
        self.addCleanup(fresh.close)
        add_fact(fresh)
        # the same review id, a different person's verdict
        add_table_review(fresh, review_id="r1", verdict="rejected")
        out = reviews.import_reviews(fresh, self.path, dry_run=False)
        self.assertTrue(out["refused"])
        self.assertFalse(out["applied"])
        self.assertEqual(out["conflicts"], 1)
        self.assertIn("verdict", out["detail"]["conflicts"][0]["differs"])
        self.assertEqual(fresh.execute(
            "SELECT verdict FROM table_reviews WHERE review_id='r1'").fetchone()[0],
            "rejected", "the store's own decision must survive a replay")
        self.assertEqual(fresh.execute("SELECT COUNT(*) FROM fact_reviews").fetchone()[0], 0,
                         "a conflict refuses the whole ledger, not just its line")

    def test_a_fact_review_whose_anchor_matches_nothing_is_reported(self):
        self.source()
        fresh = make_store()          # no facts at all
        self.addCleanup(fresh.close)
        out = reviews.import_reviews(fresh, self.path, dry_run=False)
        self.assertEqual(out["unresolvable"], 1)
        self.assertEqual(fresh.execute("SELECT COUNT(*) FROM fact_reviews").fetchone()[0], 0)
        self.assertEqual(fresh.execute("SELECT COUNT(*) FROM table_reviews").fetchone()[0], 1,
                         "the table half does not depend on a fact id and lands")

    def test_a_header_that_miscounts_its_body_is_refused(self):
        self.source()
        lines = self.path.read_text().splitlines()
        header = json.loads(lines[0])
        header["fact_reviews"] = 99
        self.path.write_text("\n".join([json.dumps(header, sort_keys=True)] + lines[1:]) + "\n")
        fresh = make_store()
        self.addCleanup(fresh.close)
        with self.assertRaises(reviews.ReviewRefused):
            reviews.import_reviews(fresh, self.path)

    def test_a_ledger_with_no_header_is_refused(self):
        self.path.write_text('{"kind":"table_review"}\n')
        fresh = make_store()
        self.addCleanup(fresh.close)
        with self.assertRaises(reviews.ReviewRefused):
            reviews.import_reviews(fresh, self.path)


class TestRoundTrip(unittest.TestCase):
    def test_a_ledger_replays_into_a_store_that_minted_different_fact_ids(self):
        with tempfile.TemporaryDirectory(
                dir=str(context.ROOT / "workspace" / "tests")) as d:
            path = Path(d) / "ledger.jsonl"

            origin = make_store()
            self.addCleanup(origin.close)
            extract_facts(conn=origin)
            review_a_fact(origin, origin.execute("SELECT fact_id FROM facts").fetchone()[0],
                          notes="checked against the page image")
            add_table_review(origin, review_id="r1")
            add_table_review(origin, review_id="r2", crop=CROP_B, verdict="bracket_unclear",
                             at="2026-08-28T11:00:00+00:00")
            first = reviews.export_reviews(origin, path)

            # a fresh store whose fact ids deliberately do not line up
            fresh = make_store()
            self.addCleanup(fresh.close)
            for _ in range(7):
                add_fact(fresh, fact_type="wind_speed_mph", value="150 mph",
                         normalized=150.0)
            fresh.execute("DELETE FROM facts")
            fresh.commit()
            extract_facts(conn=fresh)
            self.assertNotEqual(
                fresh.execute("SELECT fact_id FROM facts").fetchone()[0],
                origin.execute("SELECT fact_id FROM facts").fetchone()[0])

            out = reviews.import_reviews(fresh, path, dry_run=False)
            self.assertTrue(out["applied"])
            self.assertEqual(out["inserted"], 3)
            self.assertEqual(out["unresolvable"], 0)

            # the review state is the same knowledge, and re-exporting proves it
            second = Path(d) / "again.jsonl"
            reviews.export_reviews(fresh, second)
            self.assertEqual(second.read_bytes(), path.read_bytes())
            self.assertEqual(first["sha256"],
                             reviews.export_reviews(fresh, second)["sha256"])

            # and the projection followed: the fact carries the person's name
            row = fresh.execute("SELECT * FROM facts").fetchone()
            self.assertEqual(row["review_status"], "reviewed")
            self.assertEqual(row["reviewer"], "a.person")
            self.assertEqual(
                fresh.execute("SELECT fact_id FROM fact_reviews").fetchone()[0],
                row["fact_id"])


# ======================================================================
# C. The live store
# ======================================================================
class TestTheCommittedLedger(unittest.TestCase):
    """The committed file must be what the store holds. Read-only.

    This is `dataset --verify`'s shape applied to the one artifact that cannot
    be regenerated from the corpus. It fails when somebody records a review and
    does not export it -- which is precisely the loss G49 is about.
    """

    @requires_store
    def test_the_committed_ledger_matches_the_live_store(self):
        from fence_evidence.store import connect
        conn = connect(read_only=True)
        self.addCleanup(conn.close)
        expected = reviews.ledger_bytes(reviews.build_ledger(conn))
        self.assertTrue(reviews.LEDGER_PATH.is_file(),
                        f"{reviews.LEDGER_PATH} is missing; run "
                        f"`python3 -m fence_evidence.cli review --export`")
        self.assertEqual(reviews.LEDGER_PATH.read_bytes(), expected,
                         "the committed ledger disagrees with the store; run "
                         "`python3 -m fence_evidence.cli review --export`")

    @requires_store
    def test_nothing_in_the_live_store_has_been_reviewed(self):
        """Obligation 6's measurement, restated where the ledger can see it.

        Building durability for human decisions is not making them. If this
        ever fails because a real person reviewed something, delete it and say
        so in `docs/state-and-gaps.md`; if it fails because a *process* wrote a
        review, that is the G17 defect returning.
        """
        from fence_evidence.store import connect
        conn = connect(read_only=True)
        self.addCleanup(conn.close)
        reviews.ensure_fact_reviews(conn)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM fact_reviews").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM table_reviews").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
