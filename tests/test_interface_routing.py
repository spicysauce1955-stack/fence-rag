"""G14 — the benchmark grades more than one of the six interfaces.

Every gold question is still issued to `search_evidence` and graded exactly as
before; that is what keeps the published search numbers meaning what they meant.
A question may *additionally* declare an `interface`, and the routed answer is
graded in its own block. These tests police both halves: the search half must
not move, and the routed half must actually go through the other interface.
"""
import json
import tempfile
import unittest
from pathlib import Path

from context import (ROOT, requires_facts,  # noqa: F401
                     requires_full_store)
from fence_evidence.evaluate import (DEFAULT_INTERFACE, INTERFACES,
                                     evaluate_question,
                                     evaluate_routed_question, load_gold,
                                     question_interface, run_evaluation)
from fence_evidence.store import connect


def _gold_by_id() -> dict:
    return {q["id"]: q for q in load_gold()}


def _discard_report(name: str) -> None:
    """`run_evaluation` writes a report and a results file. These tests run it
    for its return value, so the artefacts are removed rather than left beside
    the real ones, where they would be mistaken for a measurement."""
    from fence_evidence.paths import REPORTS_DIR, TESTS_DIR
    for path in (TESTS_DIR / f"{name}-results.json",
                 REPORTS_DIR / f"{name}-report.md"):
        try:
            path.unlink()
        except OSError:
            pass


class TestInterfaceField(unittest.TestCase):
    def test_absent_field_defaults_to_search(self):
        self.assertEqual(DEFAULT_INTERFACE, "search")
        self.assertEqual(question_interface({"id": "gq-999"}), "search")
        self.assertEqual(question_interface({"id": "gq-999", "interface": None}),
                         "search")

    def test_explicit_search_is_accepted(self):
        self.assertEqual(question_interface({"id": "gq-999", "interface": "search"}),
                         "search")

    def test_unknown_interface_is_rejected_loudly(self):
        with self.assertRaises(ValueError) as ctx:
            question_interface({"id": "gq-999", "interface": "lookup"})
        self.assertIn("gq-999", str(ctx.exception))
        self.assertIn("lookup", str(ctx.exception))

    def test_load_gold_rejects_an_unknown_interface(self):
        tmp = Path(tempfile.mkdtemp()) / "gold-questions-bogus.json"
        tmp.write_text(json.dumps({"set": "bogus", "questions": [
            {"id": "gq-999", "category": "paraphrase", "question": "?",
             "answerable": True, "interface": "sql",
             "verification": {"method": "none", "confirmed": True}}]}))
        with self.assertRaises(ValueError):
            load_gold([tmp])

    def test_the_gold_set_declares_only_known_interfaces(self):
        for q in load_gold():
            self.assertIn(question_interface(q), INTERFACES, q["id"])

    def test_gq_011_is_routed_to_resolve(self):
        # The named case in G14: search scores it a failure while
        # resolve_document_version answers it.
        self.assertEqual(question_interface(_gold_by_id()["gq-011"]), "resolve")


class TestSearchGradingIsUnchanged(unittest.TestCase):
    """Routing must not reach into the search grader."""

    @classmethod
    @requires_full_store
    def setUpClass(cls):
        cls.conn = connect()

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "conn", None) is not None:
            cls.conn.close()

    @requires_full_store
    def test_a_routed_question_is_still_graded_by_search_identically(self):
        q = dict(_gold_by_id()["gq-011"])
        with_field = evaluate_question(q, conn=self.conn)
        stripped = {k: v for k, v in q.items()
                    if k not in ("interface", "interface_input")}
        without_field = evaluate_question(stripped, conn=self.conn)
        self.assertEqual(with_field, without_field,
                         "declaring an interface changed the search grading")

    @requires_full_store
    def test_search_denominators_still_cover_every_question(self):
        self.addCleanup(_discard_report, "test-interface-routing-full")
        out = run_evaluation(report_name="test-interface-routing-full")
        s = out["summary"]
        self.assertEqual(s["questions"], len(out["results"]))
        self.assertEqual(s["questions"], len(load_gold()))
        self.assertEqual(s["answerable"] + s["no_answer"], s["questions"])
        # gq-011 is routed, and still counted as a search failure
        self.assertIn("gq-011", s["by_category"]["current_version"]["failures"])


class TestResolveRouting(unittest.TestCase):
    @classmethod
    @requires_full_store
    def setUpClass(cls):
        cls.conn = connect()

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "conn", None) is not None:
            cls.conn.close()

    @requires_full_store
    def test_gq_011_is_graded_through_resolution(self):
        row = evaluate_routed_question(_gold_by_id()["gq-011"], conn=self.conn)
        self.assertEqual(row["interface"], "resolve")
        self.assertEqual(row["id"], "gq-011")
        self.assertIsNotNone(row["doc_rank"],
                             "resolution did not return an expected document")
        self.assertTrue(row["passed"])
        self.assertIn("24-0117.05", row["active_document"] or "")
        # the chain is what answers "which NOA did it replace"
        self.assertTrue(any("23-0314.05" in p for p in row["returned_documents"]))

    @requires_full_store
    def test_a_search_question_cannot_be_routed(self):
        with self.assertRaises(ValueError):
            evaluate_routed_question(_gold_by_id()["gq-012"], conn=self.conn)

    @requires_full_store
    def test_an_unresolvable_identifier_fails_rather_than_raises(self):
        q = dict(_gold_by_id()["gq-011"])
        q["interface_input"] = {"identifier": "99-9999.99"}
        row = evaluate_routed_question(q, conn=self.conn)
        self.assertIsNone(row["doc_rank"])
        self.assertFalse(row["passed"])
        self.assertTrue(row["note"])


class TestFactsRouting(unittest.TestCase):
    @classmethod
    @requires_facts
    def setUpClass(cls):
        cls.conn = connect()

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "conn", None) is not None:
            cls.conn.close()

    @requires_facts
    def test_a_facts_question_is_answered_by_the_fact_layer(self):
        row = self.conn.execute(
            """SELECT d.source_path, f.value_original FROM facts f
                 JOIN documents d ON d.document_id = f.document_id
                WHERE f.fact_type = 'expiration_date' LIMIT 1""").fetchone()
        if row is None:
            self.skipTest("no expiration_date facts in this store")
        q = {"id": "gq-901", "category": "exact_identifier",
             "question": "when does it expire?", "answerable": True,
             "interface": "facts",
             "interface_input": {"fact_type": "expiration_date", "limit": 50},
             "expected_documents": [row["source_path"]],
             "expected_answer_terms": [],
             "verification": {"method": "synthetic", "confirmed": True}}
        graded = evaluate_routed_question(q, conn=self.conn)
        self.assertEqual(graded["interface"], "facts")
        self.assertGreater(graded["n_results"], 0)
        self.assertIsNotNone(graded["doc_rank"])
        self.assertTrue(graded["passed"])

    @requires_facts
    def test_a_facts_question_needs_a_fact_type(self):
        q = {"id": "gq-902", "category": "exact_identifier", "question": "?",
             "answerable": True, "interface": "facts",
             "verification": {"method": "synthetic", "confirmed": True}}
        with self.assertRaises(ValueError):
            evaluate_routed_question(q, conn=self.conn)


class TestRoutedBlockIsSeparate(unittest.TestCase):
    @requires_full_store
    def test_the_routed_block_reports_before_and_after(self):
        gold = _gold_by_id()
        tmp = Path(tempfile.mkdtemp()) / "gold-questions-slice.json"
        tmp.write_text(json.dumps(
            {"set": "slice", "questions": [gold["gq-011"], gold["gq-012"]]}))
        self.addCleanup(_discard_report, "test-interface-routing-slice")
        out = run_evaluation(gold_paths=[tmp],
                             report_name="test-interface-routing-slice")
        s = out["summary"]
        self.assertEqual(s["interfaces"], {"resolve": 1, "search": 1})
        routed = s["routed"]
        self.assertEqual(routed["n"], 1)
        self.assertEqual(routed["by_interface"]["resolve"]["n"], 1)
        entry = routed["questions"][0]
        self.assertEqual(entry["id"], "gq-011")
        # the before/after the gap entry asks to be recorded
        self.assertIsNone(entry["search"]["doc_rank"])
        self.assertFalse(entry["search"]["passed"])
        self.assertIsNotNone(entry["doc_rank"])
        self.assertTrue(entry["passed"])
        # the headline numbers are the search harness and nothing else
        self.assertEqual(s["questions"], 2)
        self.assertEqual(s["answerable"], 2)
        self.assertNotIn("gq-011", [r["id"] for r in out["results"] if r["passed"]])


if __name__ == "__main__":
    unittest.main()
