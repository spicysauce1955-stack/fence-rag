"""The gold evaluation set is well-formed and points at documents that exist."""
import json
import unittest
from pathlib import Path

from context import ROOT
from fence_evidence.evaluate import INTERFACES, load_gold, question_interface

SCHEMA = json.load(open(ROOT / "eval" / "gold-question-schema.json"))
CATEGORIES = set(SCHEMA["properties"]["category"]["enum"])
NO_ANSWER_CLASSES = SCHEMA["properties"]["no_answer_class"]["enum"]
SCHEMA_INTERFACES = SCHEMA["properties"]["interface"]["enum"]
MANIFEST = {json.loads(l)["source_path"]
            for l in open(ROOT / "workspace" / "catalog" / "corpus-manifest.jsonl")}


class TestGoldSet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.questions = load_gold()

    def test_size_is_at_least_what_the_guide_asks_for(self):
        # guide.md asks for 30-50; the negative set was later expanded past that
        # deliberately, so only the floor is enforced.
        self.assertGreaterEqual(len(self.questions), 30)

    def test_negative_set_is_large_enough_to_calibrate_on(self):
        negatives = [q for q in self.questions if not q.get("answerable")]
        self.assertGreaterEqual(
            len(negatives), 30,
            "no-answer precision moves in steps of 1/n; a small negative set "
            "produced a 0.667 figure that did not survive expansion, and an "
            "18-question one moved again when the set was doubled (G7)")

    def test_ids_unique(self):
        ids = [q["id"] for q in self.questions]
        self.assertEqual(len(ids), len(set(ids)))

    def test_required_fields_present(self):
        for q in self.questions:
            for field in SCHEMA["required"]:
                self.assertIn(field, q, f"{q.get('id')} lacks {field}")

    def test_categories_valid_and_broad(self):
        cats = {q["category"] for q in self.questions}
        for c in cats:
            self.assertIn(c, CATEGORIES)
        self.assertGreaterEqual(len(cats), 10,
                                "the benchmark must span the guide's query categories")

    def test_every_expected_document_exists_in_the_corpus(self):
        for q in self.questions:
            for path in q.get("expected_documents", []):
                self.assertIn(path, MANIFEST, f"{q['id']} names a path not in the corpus")
                self.assertTrue((ROOT / path).is_file())

    def test_expected_pages_reference_expected_documents(self):
        for q in self.questions:
            docs = set(q.get("expected_documents", []))
            for path, pages in (q.get("expected_pages") or {}).items():
                self.assertIn(path, docs, f"{q['id']} pages a document it does not expect")
                self.assertTrue(all(isinstance(p, int) and p >= 1 for p in pages))

    def test_answerable_questions_are_annotated(self):
        for q in self.questions:
            if not q.get("answerable"):
                continue
            self.assertTrue(q.get("expected_documents"), f"{q['id']} has no expected document")
            self.assertTrue(q.get("expected_answer_terms"),
                            f"{q['id']} has no answer terms to grade against")

    def test_no_answer_questions_expect_nothing(self):
        no_answer = [q for q in self.questions if not q.get("answerable")]
        self.assertGreaterEqual(len(no_answer), 3)
        for q in no_answer:
            self.assertEqual(q.get("expected_documents", []), [])
            self.assertIsNone(q.get("expected_answer"))

    def test_interface_is_optional_and_defaults_to_search(self):
        # G14: the field is a routing declaration, not an annotation. A question
        # that does not carry it must behave exactly as it did before the field
        # existed, so the default is asserted here rather than written into the
        # 58 questions that do not need it.
        self.assertEqual(SCHEMA["properties"]["interface"]["default"], "search")
        self.assertEqual(sorted(SCHEMA_INTERFACES), sorted(INTERFACES))
        self.assertNotIn("interface", SCHEMA["required"])
        for q in self.questions:
            if "interface" not in q:
                self.assertEqual(question_interface(q), "search", q["id"])

    def test_declared_interfaces_are_known_and_carry_their_input(self):
        for q in self.questions:
            iface = question_interface(q)
            self.assertIn(iface, SCHEMA_INTERFACES, q["id"])
            if iface == "resolve":
                self.assertTrue((q.get("interface_input") or {}).get("identifier"),
                                f"{q['id']} routes to resolve with no identifier")
            if iface == "facts":
                self.assertTrue((q.get("interface_input") or {}).get("fact_type"),
                                f"{q['id']} routes to facts with no fact_type")

    def test_routing_did_not_touch_the_expected_answers(self):
        # G8: never edit an expected answer to make a question pass. A routed
        # question keeps every annotation a search-graded question has.
        for q in self.questions:
            if question_interface(q) == "search":
                continue
            self.assertTrue(q.get("expected_documents"), q["id"])
            self.assertTrue(q.get("expected_answer_terms"), q["id"])
            self.assertTrue(q.get("expected_answer"), q["id"])

    def test_no_answer_class_is_optional_and_never_appears_on_a_positive(self):
        # G7: the field classifies an unanswerable question. It is optional, so
        # the three negatives that predate it (gq-116..gq-118, in the general
        # set) stay valid; but it must never be attached to a question the
        # corpus can answer, because there is nothing there to classify.
        self.assertNotIn("no_answer_class", SCHEMA["required"])
        for q in self.questions:
            if q.get("answerable"):
                self.assertNotIn("no_answer_class", q,
                                 f"{q['id']} is answerable and cannot have a no-answer class")

    def test_declared_no_answer_classes_are_known(self):
        for q in self.questions:
            if "no_answer_class" not in q:
                continue
            self.assertIn(q["no_answer_class"], NO_ANSWER_CLASSES, q["id"])

    def test_every_no_answer_question_is_marked_unanswerable(self):
        # The category and the flag must agree in both directions: a question
        # filed as no_answer that is still marked answerable would be counted
        # in recall and evidence support, and a question carrying a no-answer
        # class would be graded as if the corpus owed it an answer.
        for q in self.questions:
            if q["category"] == "no_answer":
                self.assertFalse(q.get("answerable", True),
                                 f"{q['id']} is category no_answer but answerable")
            if "no_answer_class" in q:
                self.assertFalse(q.get("answerable", True),
                                 f"{q['id']} carries a no-answer class but is answerable")
                self.assertEqual(q["category"], "no_answer", q["id"])

    def test_dedicated_negative_set_is_fully_classified_and_balanced(self):
        # The file that exists to hold negatives must classify all of them, and
        # no class may collapse: G7's finding is that no lexical feature
        # separates the three, so a per-class breakdown is the only way to read
        # no_answer_precision. Reporting it needs every class populated.
        path = ROOT / "eval" / "gold-questions-no-answer.json"
        with open(path) as fh:
            negatives = json.load(fh)["questions"]
        counts = {c: 0 for c in NO_ANSWER_CLASSES}
        for q in negatives:
            self.assertIn("no_answer_class", q,
                          f"{q['id']} is in the negative set and is unclassified")
            counts[q["no_answer_class"]] += 1
        for cls, n in counts.items():
            self.assertGreaterEqual(n, 5, f"class {cls} has only {n} questions")

    def test_negative_questions_record_the_evidence_that_they_are_negative(self):
        # A wrong negative question is worse than no question: the metric it
        # feeds would be measuring the annotation, not the retriever. Every
        # negative must therefore carry a method that names what was searched.
        for q in self.questions:
            if q.get("answerable"):
                continue
            method = (q.get("verification") or {}).get("method", "")
            self.assertGreater(len(method), 80,
                               f"{q['id']} does not record how absence was established")

    def test_every_question_records_its_verification(self):
        for q in self.questions:
            v = q.get("verification") or {}
            self.assertTrue(v.get("confirmed"), f"{q['id']} is not marked verified")
            self.assertTrue(v.get("method"), f"{q['id']} does not record how it was verified")


if __name__ == "__main__":
    unittest.main()
