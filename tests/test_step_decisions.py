"""A sitting's worth of step decisions, applied in one go — and what it publishes.

`cli steps --accept` records ONE judgement per process invocation. A page of the
Bufftech guide carries ~55 of them, so a sitting is 55 shell commands, each of
which must be typed with the candidate id, the kind, the scope and the slot
correct, and any one of which can half-apply the sitting. That is the surface
that has produced 0 step reviews since the table was built.

So the batch is the unit here, and the rules are the ones the review loop
already holds elsewhere: **a decision without a person is refused**, a decision
whose evidence moved under it is refused, and **one bad row refuses the whole
batch** — a half-applied sitting leaves the owner with no way to tell which of
the 55 landed, and re-running it would re-decide the ones that did.

The last test is the point of the file: the decisions reach `build_procedures`
and a `Procedure` comes out with those steps in it. That is the pipe the
headline gap is about.
"""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from context import ROOT  # noqa: F401
from fence_evidence import steps
from fence_evidence.procedures import build_procedures
from fence_evidence.reviews import (ReviewRefused, apply_step_decisions,
                                    read_step_decisions)
from fence_evidence.store import STEP_CANDIDATES_DDL, STEP_REVIEWS_DDL

BLOCK = ("• I nsert post in hole\n• Determine rough height\n"
         "• N ever strike the PVC post without a wood support")


def scratch() -> sqlite3.Connection:
    """The same slice fixture `test_procedures` uses, so the two agree about
    what a reviewed page is."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE documents (document_id TEXT PRIMARY KEY, source_path TEXT,
                                doc_type TEXT, title TEXT, owner_tenant TEXT,
                                manufacturer TEXT, product_family TEXT);
        CREATE TABLE document_versions (version_id TEXT PRIMARY KEY,
                                        document_id TEXT, sha256 TEXT);
        CREATE TABLE elements (element_id TEXT PRIMARY KEY, document_id TEXT,
                               version_id TEXT, page_no INTEGER, ordinal INTEGER,
                               element_type TEXT, text TEXT, ocr_text TEXT,
                               text_source TEXT, heading_path TEXT, bbox TEXT);
        CREATE TABLE pages (version_id TEXT, page_no INTEGER,
                            page_image_path TEXT, width REAL, height REAL,
                            page_image_dpi INTEGER);
    """)
    conn.executescript(STEP_CANDIDATES_DDL)
    conn.executescript(STEP_REVIEWS_DDL)
    conn.execute("INSERT INTO documents VALUES ('doc-1','a.pdf','installation_manual',"
                 "'Bufftech Guide',NULL,NULL,NULL)")
    conn.execute("INSERT INTO document_versions VALUES ('v1','doc-1','abc123')")
    conn.execute("INSERT INTO pages VALUES ('v1',8,'p.png',612.0,792.0,200)")
    conn.execute("INSERT INTO elements VALUES ('el-1','doc-1','v1',8,7,'list',?,NULL,"
                 "'pdf_text_layer','[]','[54,290,275,370]')", (BLOCK,))
    steps.propose(conn, document_id="doc-1", page_no=8)
    return conn


def candidates(conn):
    return conn.execute(
        "SELECT * FROM step_candidates ORDER BY ordinal, seq").fetchall()


def decision(row, **kw):
    d = {"candidate_id": row["candidate_id"], "text_seen": row["text_raw"],
         "verdict": "accepted", "step_kind": "installation",
         "step_scope": "post", "slot_target": {"kind": "PostSlot", "key": "post"}}
    d.update(kw)
    return d


def mint(conn):
    from fence_evidence.refs import ref_id

    def source_ref_page(document_id, page_no):
        sha = conn.execute(
            "SELECT sha256 FROM document_versions WHERE document_id=?",
            (document_id,)).fetchone()[0]
        return {"id": ref_id(sha, page_no, None), "belongs_to": sha}
    return source_ref_page


class TestABatchIsTheUnit(unittest.TestCase):
    def test_a_batch_records_one_step_review_for_each_decision(self):
        conn = scratch()
        rows = candidates(conn)
        out = apply_step_decisions(
            conn, [decision(r) for r in rows], reviewer="an-owner", dry_run=False)
        self.assertEqual(out["recorded"], len(rows))
        self.assertTrue(out["applied"])
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM step_reviews").fetchone()[0],
            len(rows))

    def test_a_dry_run_writes_nothing(self):
        """The default, for the same reason `--import` defaults dry: a batch is
        read from a file somebody generated, and reading it back should not be
        the act that commits it."""
        conn = scratch()
        out = apply_step_decisions(
            conn, [decision(r) for r in candidates(conn)], reviewer="an-owner")
        self.assertFalse(out["applied"])
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM step_reviews").fetchone()[0], 0)

    def test_one_bad_row_refuses_the_whole_batch(self):
        """Half a sitting is worse than none: the owner cannot tell which of the
        55 decisions landed, and re-running re-decides the ones that did."""
        conn = scratch()
        rows = candidates(conn)
        batch = [decision(rows[0]),
                 decision(rows[1], step_kind="a-kind-nobody-declared"),
                 decision(rows[2])]
        out = apply_step_decisions(conn, batch, reviewer="an-owner", dry_run=False)
        self.assertFalse(out["applied"])
        self.assertEqual(out["recorded"], 0)
        self.assertEqual([r["at"] for r in out["refusals"]], [1])
        self.assertEqual(out["refusals"][0]["code"], "error.bad_step_kind")
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM step_reviews").fetchone()[0], 0)

    def test_a_decision_that_neither_rejects_nor_classifies_is_refused(self):
        """`AssemblyStep.kind` and `scope` are required by the shape, so a
        half-classified accept can never publish — it would sit in the store
        looking decided and publish nothing, which is the state this whole
        exercise exists to end."""
        conn = scratch()
        out = apply_step_decisions(
            conn, [decision(candidates(conn)[0], step_scope=None)],
            reviewer="an-owner", dry_run=False)
        self.assertFalse(out["applied"])
        self.assertEqual(out["refusals"][0]["code"], "error.unclassified_step")

    def test_a_rejection_needs_no_kind_or_scope(self):
        """Rejecting is a decision too — it says this line is not a step — and
        it publishes nothing, so there is nothing to classify."""
        conn = scratch()
        out = apply_step_decisions(
            conn, [decision(candidates(conn)[0], verdict="rejected",
                            step_kind=None, step_scope=None, slot_target=None)],
            reviewer="an-owner", dry_run=False)
        self.assertTrue(out["applied"])
        self.assertEqual(
            conn.execute("SELECT review_status FROM step_candidates "
                         "WHERE candidate_id=?",
                         (candidates(conn)[0]["candidate_id"],)).fetchone()[0],
            "rejected")

    def test_a_decision_whose_text_moved_is_refused(self):
        """The echo check. The splitter re-cut this page four times in one day;
        a decision about text the candidate no longer holds is a decision about
        something that is gone."""
        conn = scratch()
        out = apply_step_decisions(
            conn, [decision(candidates(conn)[0], text_seen="something else")],
            reviewer="an-owner", dry_run=False)
        self.assertFalse(out["applied"])
        self.assertEqual(out["refusals"][0]["code"], "error.text_moved")

    def test_an_unknown_field_is_refused(self):
        """A batch is generated by a surface the reviewer cannot see inside.
        `kind` instead of `step_kind` would drop a person's classification
        silently and publish an unclassified accept."""
        conn = scratch()
        d = decision(candidates(conn)[0])
        d["kind"] = "installation"
        out = apply_step_decisions(conn, [d], reviewer="an-owner", dry_run=False)
        self.assertFalse(out["applied"])
        self.assertEqual(out["refusals"][0]["code"], "error.unknown_field")

    def test_a_batch_with_no_reviewer_is_refused(self):
        """The name is the only thing separating 'software read this' from 'a
        person confirmed it'."""
        conn = scratch()
        with self.assertRaises(ReviewRefused):
            apply_step_decisions(conn, [decision(candidates(conn)[0])],
                                 reviewer="  ", dry_run=False)

    def test_a_row_may_name_its_own_reviewer(self):
        """A file can be authored by somebody other than whoever replays it."""
        conn = scratch()
        apply_step_decisions(
            conn, [decision(candidates(conn)[0], reviewer="the-owner")],
            reviewer="a-replayer", dry_run=False)
        self.assertEqual(
            conn.execute("SELECT reviewer FROM step_reviews").fetchone()[0],
            "the-owner")

    def test_a_decision_may_be_anchored_by_evidence_instead_of_a_row_id(self):
        """`candidate_id` is re-minted by every re-proposal; the (element, span)
        anchor is not. A file written before a re-cut must still apply."""
        conn = scratch()
        row = candidates(conn)[0]
        out = apply_step_decisions(
            conn, [{"element_id": row["element_id"],
                    "char_start": row["char_start"], "char_end": row["char_end"],
                    "text_seen": row["text_raw"], "verdict": "accepted",
                    "step_kind": "installation", "step_scope": "post"}],
            reviewer="an-owner", dry_run=False)
        self.assertEqual(out["recorded"], 1)

    def test_a_decision_naming_no_candidate_is_refused(self):
        conn = scratch()
        out = apply_step_decisions(conn, [decision(candidates(conn)[0],
                                                   candidate_id=99999)],
                                   reviewer="an-owner", dry_run=False)
        self.assertEqual(out["refusals"][0]["code"], "error.no_such_candidate")


class TestTheDecisionFile(unittest.TestCase):
    def test_a_jsonl_file_reads_as_one_decision_per_line(self):
        """JSONL is what a browser can hand back through a clipboard without a
        server: one decision per line, appendable, diffable."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "decisions.jsonl"
            path.write_text('{"candidate_id": 1, "verdict": "rejected"}\n'
                            '\n'
                            '{"candidate_id": 2, "verdict": "rejected"}\n')
            self.assertEqual([d["candidate_id"] for d in read_step_decisions(path)],
                             [1, 2])

    def test_a_json_array_reads_the_same_way(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "decisions.json"
            path.write_text(json.dumps([{"candidate_id": 1, "verdict": "rejected"}]))
            self.assertEqual(len(read_step_decisions(path)), 1)

    def test_an_empty_file_is_refused_rather_than_reported_as_success(self):
        """Vacuous green: a sitting that recorded nothing must not print
        'applied 0 decisions' and exit 0."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "decisions.jsonl"
            path.write_text("\n")
            with self.assertRaises(ReviewRefused):
                read_step_decisions(path)


class TestTheLoopCloses(unittest.TestCase):
    """The whole point: decisions in, a `Procedure` out."""

    def test_a_reviewed_page_publishes_a_procedure_carrying_those_steps(self):
        conn = scratch()
        rows = candidates(conn)
        batch = [decision(rows[0]),
                 decision(rows[1], step_scope="run", slot_target=None),
                 decision(rows[2], verdict="rejected", step_kind=None,
                          step_scope=None, slot_target=None)]
        out = apply_step_decisions(conn, batch, reviewer="an-owner", dry_run=False)
        self.assertTrue(out["applied"])

        procedures, _ = build_procedures(conn, source_ref_page=mint(conn))
        self.assertEqual(len(procedures), 1)
        published = procedures[0]["steps"]
        self.assertEqual([s["scope"] for s in published], ["post", "run"])
        self.assertIn("Determine rough height",
                      [s["text_i18n"] for s in published])
        self.assertNotIn("N ever strike the PVC post without a wood support",
                         [s["text_i18n"] for s in published])
