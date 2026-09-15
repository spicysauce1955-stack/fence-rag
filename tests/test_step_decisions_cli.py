"""`cli review --apply-steps` — the command that ends a sitting.

The surface the owner works is a generated HTML page with no server behind it,
so the decisions come back as a file. This is the one command that turns that
file into `step_reviews` rows, and it holds the same two properties the rest of
the review loop holds: it is **dry by default**, and it **exits non-zero when it
refuses**, so a script cannot mistake a refused sitting for an applied one.

It lives under `review` rather than `steps` because it is the review loop, not
the splitter: the same place `--import` replays a ledger.
"""
import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from context import ROOT  # noqa: F401
from fence_evidence.cli import main
from test_step_decisions import candidates, decision, scratch


class KeepOpen:
    """`main` closes the connection it is handed, and each test here runs one
    command against a fixture that must outlive it."""

    def __init__(self, conn):
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        pass


def run(argv, conn):
    buf = io.StringIO()
    with patch("fence_evidence.store.connect", return_value=KeepOpen(conn)):
        with contextlib.redirect_stdout(buf):
            code = main(argv)
    return code, json.loads(buf.getvalue() or "null")


class TestApplyingASitting(unittest.TestCase):
    def setUp(self):
        self.conn = scratch()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def file(self, decisions):
        path = Path(self.tmp.name) / "decisions.jsonl"
        path.write_text("".join(json.dumps(d) + "\n" for d in decisions))
        return str(path)

    def reviews_in_store(self):
        return self.conn.execute("SELECT COUNT(*) FROM step_reviews").fetchone()[0]

    def test_it_is_a_dry_run_unless_apply_is_given(self):
        path = self.file([decision(r) for r in candidates(self.conn)])
        code, out = run(["review", "--apply-steps", path, "--reviewer", "an-owner"],
                        self.conn)
        self.assertEqual(code, 0)
        self.assertFalse(out["applied"])
        self.assertEqual(self.reviews_in_store(), 0)

    def test_with_apply_it_records_every_decision(self):
        rows = candidates(self.conn)
        path = self.file([decision(r) for r in rows])
        code, out = run(["review", "--apply-steps", path, "--reviewer", "an-owner",
                         "--apply"], self.conn)
        self.assertEqual(code, 0)
        self.assertEqual(out["recorded"], len(rows))
        self.assertEqual(self.reviews_in_store(), len(rows))

    def test_a_refused_batch_exits_nonzero_and_writes_nothing(self):
        """A refusal is the owner's file disagreeing with the store, not a bad
        argument — report it, write nothing, and make sure a wrapper script
        cannot read the exit code as success."""
        rows = candidates(self.conn)
        path = self.file([decision(rows[0]),
                          decision(rows[1], step_kind="not-a-kind")])
        code, out = run(["review", "--apply-steps", path, "--reviewer", "an-owner",
                         "--apply"], self.conn)
        self.assertEqual(code, 1)
        self.assertEqual(out["refusals"][0]["code"], "error.bad_step_kind")
        self.assertEqual(self.reviews_in_store(), 0)

    def test_it_refuses_to_run_without_a_reviewer(self):
        path = self.file([decision(candidates(self.conn)[0])])
        code, out = run(["review", "--apply-steps", path], self.conn)
        self.assertEqual(code, 2)
        self.assertIn("error", out)

    def test_it_cannot_be_combined_with_another_review_mode(self):
        """`review` requires exactly one mode, so a usage error exits 2 rather
        than doing one of the two things asked for."""
        path = self.file([decision(candidates(self.conn)[0])])
        code, _ = run(["review", "--apply-steps", path, "--reviewer", "x",
                       "--queue"], self.conn)
        self.assertEqual(code, 2)


class TestTheSittingReachesTheSnapshotBuilder(unittest.TestCase):
    def test_procedures_appear_once_the_sitting_is_applied(self):
        """End to end, in one test: a file of decisions goes in through the CLI
        and a `Procedure` comes out of `build_procedures`."""
        from fence_evidence.procedures import build_procedures
        from test_step_decisions import mint
        conn = scratch()
        rows = candidates(conn)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "d.jsonl"
            path.write_text("".join(
                json.dumps(decision(r)) + "\n" for r in rows[:2]))
            code, _ = run(["review", "--apply-steps", str(path), "--reviewer",
                           "an-owner", "--apply"], conn)
        self.assertEqual(code, 0)
        procedures, _ = build_procedures(conn, source_ref_page=mint(conn))
        self.assertEqual(len(procedures), 1)
        self.assertEqual(len(procedures[0]["steps"]), 2)
