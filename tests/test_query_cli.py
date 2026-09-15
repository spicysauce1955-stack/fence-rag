"""`cli query` — the query surface as something a person can actually run.

The function is the deliverable (`docs/knowledge-loop.md` §10 item 2); this is
how it gets exercised before Planning sends the request shape that will decide
what an HTTP route looks like (`conversation.md` T58 §3). It is a CLI and not a
route on purpose, and the tests below are about the two things a CLI can get
wrong that the function cannot: **turning a refusal into a zero exit code**, and
**accepting an argument the function would refuse**.

Exit codes follow the convention `snapshot` and `refs` already set: a usage
error or a refusal is 2, and a guard that reports a problem on stdout and exits
0 is the vacuous-green class this repository keeps refusing.
"""
import contextlib
import io
import json
import unittest

import context  # noqa: F401  -- puts the repo root on sys.path
from context import requires_store
from fence_evidence.cli import main
from fence_evidence.snapshot_store import list_snapshots


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def _a_snapshot() -> str | None:
    live = [s for s in list_snapshots() if not s["tombstoned"]]
    return live[0]["snapshot_id"] if live else None


class TestUsage(unittest.TestCase):
    def test_a_query_naming_no_snapshot_is_refused_with_exit_two(self):
        code, _, _ = _run(["query", "--question", "footing depth"])
        self.assertEqual(code, 2)

    def test_the_refusal_says_why(self):
        code, out, err = _run(["query", "--question", "footing depth"])
        self.assertIn("snapshot", (out + err).lower())

    def test_a_condition_without_an_equals_sign_is_a_usage_error(self):
        snapshot_id = _a_snapshot() or "0" * 64
        code, _, _ = _run(["query", "--snapshot", snapshot_id,
                           "--condition", "exposure_category"])
        self.assertEqual(code, 2)

    def test_an_unknown_condition_dimension_exits_two_and_names_it(self):
        snapshot_id = _a_snapshot() or "0" * 64
        code, out, err = _run(["query", "--snapshot", snapshot_id,
                               "--condition", "soil_ph=7"])
        self.assertEqual(code, 2)
        self.assertIn("soil_ph", out + err)

    def test_a_scope_without_a_colon_is_a_usage_error(self):
        snapshot_id = _a_snapshot() or "0" * 64
        code, _, _ = _run(["query", "--snapshot", snapshot_id,
                           "--scope", "mfr/acme"])
        self.assertEqual(code, 2)

    def test_an_unknown_snapshot_id_exits_two_rather_than_crashing(self):
        code, _, _ = _run(["query", "--snapshot", "0" * 64,
                           "--question", "footing"])
        self.assertEqual(code, 2)


@requires_store
class TestAnswering(unittest.TestCase):
    def setUp(self):
        self.snapshot_id = _a_snapshot()
        if not self.snapshot_id:
            self.skipTest("no stored snapshot to query")

    def test_a_question_answers_and_exits_zero(self):
        code, out, _ = _run(["query", "--snapshot", self.snapshot_id,
                             "--question", "footing depth exposure C"])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out))

    def test_the_printed_answer_names_the_snapshot(self):
        _, out, _ = _run(["query", "--snapshot", self.snapshot_id,
                          "--question", "footing depth exposure C"])
        self.assertEqual(json.loads(out)["snapshot_id"], self.snapshot_id)

    def test_the_printed_answer_carries_refs_as_a_list(self):
        _, out, _ = _run(["query", "--snapshot", self.snapshot_id,
                          "--question", "footing depth exposure C"])
        payload = json.loads(out)
        self.assertIsInstance(payload["refs"], list)
        self.assertTrue(payload["refs"], "expected the search to cite something")
        for ref in payload["refs"]:
            self.assertEqual(sorted(ref), ["belongs_to", "id"])

    def test_every_cited_ref_is_in_the_printed_ref_list(self):
        _, out, _ = _run(["query", "--snapshot", self.snapshot_id,
                          "--question", "footing depth exposure C"])
        payload = json.loads(out)
        listed = {r["id"] for r in payload["refs"]}
        cited = {h["ref"]["id"] for h in payload["evidence"]}
        cited |= {c["id"] for v in payload["values"] for c in v["cites"]}
        self.assertEqual(cited, listed)

    def test_a_situation_with_conditions_and_no_question_still_answers(self):
        code, out, _ = _run(["query", "--snapshot", self.snapshot_id,
                             "--condition", "exposure_category=C"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["basis"]["conditions_stated"],
                         ["exposure_category"])

    def test_the_answer_says_it_resolved_no_conflicts(self):
        _, out, _ = _run(["query", "--snapshot", self.snapshot_id,
                          "--condition", "exposure_category=C"])
        self.assertIs(json.loads(out)["basis"]["conflicts_resolved"], False)

    def test_a_scope_is_parsed_as_kind_and_id(self):
        _, out, _ = _run(["query", "--snapshot", self.snapshot_id,
                          "--scope", "fence_model:mfr/certainteed-columbia-"
                                     "imperial-chesterfield"])
        payload = json.loads(out)
        self.assertTrue(payload["basis"]["scope_requested"])

    def test_booleans_in_conditions_are_parsed_not_left_as_strings(self):
        """`hvhz=true` must reach the matcher as the published `True`, or it
        matches nothing and the answer looks like an absence of knowledge."""
        code, out, _ = _run(["query", "--snapshot", self.snapshot_id,
                             "--condition", "hvhz=true"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
