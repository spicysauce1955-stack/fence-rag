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


class TestRequiredConditionsUseTheRegistrysNames(unittest.TestCase):
    """`required_conditions` was inert, and drifted while nothing read it.

    `[measured]` 2026-09-09: 7 questions carried the field, using 12 dimension
    names of which 3 existed in `parameters.CONDITION_SCOPE`. `evaluate.py`'s
    `_evaluate_facts` is its only reader and runs only for a question declaring
    `interface: "facts"` — and **zero of the 78 questions declares one**, so no
    code has ever executed or validated those names. `eval/gold-question-
    schema.json` typed the field as a bare object, which is how a thirteenth
    name gets invented next. G108 records the same defect one layer down.

    Nine of the twelve names had no home. Four were an existing dimension under
    another name or unit and are now spelled the registry's way. The other five
    are not condition dimensions and must not become them: `post_size_in`,
    `line_post_size_in`, `post_group` and `wind_kit` are product identity, and
    Planning declined exactly this shape in writing for `material` ("Declining,
    not deferring") — the instrument is `ParameterTable.scope` plus the
    `Part`/`PartType` spine. `footing_depth_in` was rejected with a measurement
    in ratified amendment 006. They keep their information in
    `required_selectors`, a separate field, because one key over two
    vocabularies is defect E-3 and this file is not the place to repeat it.
    """

    @classmethod
    def setUpClass(cls):
        cls.questions = load_gold()

    def declared(self):
        return SCHEMA["properties"]["required_conditions"]["propertyNames"]["enum"]

    def test_the_schema_declares_exactly_the_registrys_dimensions(self):
        """One definition per vocabulary (`naming.md` §6). The schema is JSON
        and cannot import Python, so the copy is checked rather than avoided —
        the same reason `query.KNOWN_DIMENSIONS` is built FROM
        `CONDITION_SCOPE` instead of retyped beside it."""
        from fence_evidence.parameters import CONDITION_SCOPE
        self.assertEqual(self.declared(), sorted(CONDITION_SCOPE))

    def test_every_required_condition_names_a_declared_dimension(self):
        declared = set(self.declared())
        checked = 0
        for q in self.questions:
            for key in q.get("required_conditions") or {}:
                checked += 1
                with self.subTest(question=q["id"], key=key):
                    self.assertIn(key, declared)
        self.assertGreater(checked, 0, "no required_conditions were checked")

    def test_a_quantity_valued_condition_carries_its_unit(self):
        """`fence_height` publishes `domain: "range(mm)"`, so a bare `6` reads
        as six millimetres. The value is a label the publisher parses, exactly
        as `parameters._parse_fence_height` reads one off a table."""
        from fence_evidence.parameters import _parse_fence_height
        checked = 0
        for q in self.questions:
            value = (q.get("required_conditions") or {}).get("fence_height")
            if value is None:
                continue
            checked += 1
            with self.subTest(question=q["id"], value=value):
                self.assertIsNotNone(_parse_fence_height(str(value)))
        self.assertGreater(checked, 0, "no fence_height conditions were checked")

    def test_a_selector_is_never_something_the_registry_already_declares(self):
        """The split has to stay real: a name that gains a scope belongs in
        `required_conditions`, not in the field that exists for names that
        deliberately have none."""
        declared = set(self.declared())
        for q in self.questions:
            for key in q.get("required_selectors") or {}:
                with self.subTest(question=q["id"], key=key):
                    self.assertNotIn(key, declared)

    def test_one_source_column_is_not_two_names(self):
        """`[measured]` 2026-09-09: gq-005 and gq-112 read the SAME CLFMI
        column — line post size, `2 3/8` — under `line_post_size_in` and
        `post_size_in`. §1: a second name for one value is admissible only when
        it marks a role or a layer."""
        clfmi = [q for q in self.questions
                 if any("CLFMI" in d for d in q.get("expected_documents") or [])]
        self.assertGreaterEqual(len(clfmi), 2, "the CLFMI questions moved")
        for q in clfmi:
            keys = set(q.get("required_selectors") or {})
            with self.subTest(question=q["id"]):
                self.assertNotIn("post_size_in", keys,
                                 "the CLFMI table's column is the line post's")
