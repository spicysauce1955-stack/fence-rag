"""The gold evaluation set is well-formed and points at documents that exist."""
import json
import unittest
from pathlib import Path

from context import ROOT
from fence_evidence.evaluate import load_gold

SCHEMA = json.load(open(ROOT / "eval" / "gold-question-schema.json"))
CATEGORIES = set(SCHEMA["properties"]["category"]["enum"])
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
            len(negatives), 15,
            "no-answer precision moves in steps of 1/n; a small negative set "
            "produced a 0.667 figure that did not survive expansion")

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

    def test_every_question_records_its_verification(self):
        for q in self.questions:
            v = q.get("verification") or {}
            self.assertTrue(v.get("confirmed"), f"{q['id']} is not marked verified")
            self.assertTrue(v.get("method"), f"{q['id']} does not record how it was verified")


if __name__ == "__main__":
    unittest.main()
