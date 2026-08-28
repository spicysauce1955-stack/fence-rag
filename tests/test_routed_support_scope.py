"""What a routed interface is allowed to claim it measured.

Two overclaims in the G14 routing block, both fixed here:

* `resolve` stamped `page: 1` on every member of a supersession chain, so
  `page_rank` recorded whether the annotation happened to name page 1 and
  nothing else. An interface that answers with documents now reports no
  `page_rank` and says why.
* support was measured over the concatenated text of *every* document returned,
  which for `resolve` is the whole chain — so a term printed only in a
  superseded member counted as support for the current one. The graded number
  is now `answer_support`, over the one document the interface asserts.

The synthetic store here is two documents that each hold one of the two answer
terms. That is the whole mechanism: if the grader is scoped correctly the
answer document scores 0.5 and the union scores 1.0, and they cannot both be
right about what was measured.
"""
import json
import sqlite3
import unittest

import context  # noqa: F401  -- puts the repo root on sys.path
from fence_evidence import store
from fence_evidence.evaluate import NO_PAGE, _grade_returned_documents
from fence_evidence.ids import doc_id_for
from fence_evidence.model import Element, ExtractedDocument, Page

TOOLS = {"pdftotext": "24.02.0"}
ANSWER = "manuals/acme/current-noa.pdf"
SUPERSEDED = "manuals/acme/old-noa.pdf"


def _row(path: str) -> dict:
    return {"doc_id": doc_id_for(path), "source_path": path, "file_type": "pdf",
            "corpus_track": "us", "manufacturer": "acme", "title": path,
            "doc_type": "noa", "file_size_bytes": 10}


def _doc(path: str, sha: str, text: str) -> ExtractedDocument:
    page = Page(page_no=1, width=612.0, height=792.0,
                extraction_method="pdf_text_layer", has_text_layer=True,
                text_char_count=len(text),
                elements=[Element(element_type="paragraph", text=text,
                                  bbox=(72.0, 72.0, 540.0, 120.0), ordinal=0)])
    return ExtractedDocument(source_path=path, sha256=sha, file_type="pdf",
                             pages=[page])


class TestRoutedSupportScope(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        store.migrate(self.conn)
        self.conn.execute(
            "INSERT INTO extraction_runs(run_id, started_at, tool_versions, "
            "tool_fingerprint, pipeline_version, notes) VALUES (?,?,?,?,?,?)",
            ("r", store.now(), json.dumps(TOOLS), store.tool_fingerprint(TOOLS),
             "1.0", ""))
        store.write_extracted(self.conn, _doc(ANSWER, "a" * 64,
                                              "Approval Date 04/24/2025."),
                              _row(ANSWER), "r")
        store.write_extracted(self.conn, _doc(SUPERSEDED, "b" * 64,
                                              "Signed by Robert Nieminen."),
                              _row(SUPERSEDED), "r")
        self.q = {"id": "gq-synthetic", "category": "current_version",
                  "answerable": True,
                  "expected_documents": [ANSWER],
                  "expected_pages": {ANSWER: [1]},
                  "expected_answer_terms": ["04/24/2025", "Robert Nieminen"]}
        # the shape `_evaluate_resolve` produces: a chain, no page on any member
        self.chain = [{"source_path": ANSWER, "page": None},
                      {"source_path": SUPERSEDED, "page": None}]

    def tearDown(self):
        self.conn.close()

    def test_support_is_scoped_to_the_asserted_answer_document(self):
        row = _grade_returned_documents(self.q, self.conn, self.chain, "",
                                        answer_paths=[ANSWER])
        self.assertEqual(row["answer_support"], 0.5)
        self.assertEqual(row["found_terms"], ["04/24/2025"])
        self.assertEqual(row["missing_terms"], ["Robert Nieminen"])

    def test_the_union_over_the_chain_is_reported_and_not_graded(self):
        row = _grade_returned_documents(self.q, self.conn, self.chain, "",
                                        answer_paths=[ANSWER])
        self.assertEqual(row["returned_documents_support"], 1.0,
                         "the union figure should still be reported")
        self.assertNotEqual(row["returned_documents_support"],
                            row["answer_support"],
                            "the fixture must make the two scopes differ")

    def test_a_term_only_in_a_superseded_member_cannot_carry_a_pass(self):
        q = dict(self.q, expected_answer_terms=["Robert Nieminen"])
        row = _grade_returned_documents(q, self.conn, self.chain, "",
                                        answer_paths=[ANSWER])
        self.assertEqual(row["answer_support"], 0.0)
        self.assertEqual(row["returned_documents_support"], 1.0)
        self.assertFalse(row["passed"],
                         "a term printed only in the superseded NOA passed the "
                         "question about the current one")

    def test_a_document_returning_interface_reports_no_page_rank(self):
        row = _grade_returned_documents(self.q, self.conn, self.chain, "",
                                        answer_paths=[ANSWER])
        self.assertIsNone(row["page_rank"])
        self.assertEqual(row["page_rank_basis"], NO_PAGE)

    def test_an_interface_that_knows_a_page_still_reports_one(self):
        cited = [{"source_path": ANSWER, "page": 1}]
        row = _grade_returned_documents(self.q, self.conn, cited, "")
        self.assertEqual(row["page_rank"], 1)
        self.assertNotEqual(row["page_rank_basis"], NO_PAGE)

    def test_the_answer_document_defaults_to_the_top_ranked_candidate(self):
        row = _grade_returned_documents(self.q, self.conn, self.chain, "")
        self.assertEqual(row["answer_documents"], [ANSWER])

    def test_nothing_returned_grades_as_a_failure_rather_than_an_error(self):
        row = _grade_returned_documents(self.q, self.conn, [], "",
                                        answer_paths=[])
        self.assertIsNone(row["doc_rank"])
        self.assertEqual(row["answer_support"], 0.0)
        self.assertFalse(row["passed"])


if __name__ == "__main__":
    unittest.main()
