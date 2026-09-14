"""Answer terms only count as support when the expected document supplied them.

`score_question` joined `_returned_evidence` over **all ten results** while the
element-type and image checks beside it were scoped to `expected_documents`. So
a question could score full support on terms lifted from a document that is not
its answer — and `[measured]` 2026-09-14 two did, `gq-009` at 1.000 and `gq-018`
at 0.600, both with `doc_rank: None`.

Those questions already *fail* — `passed` requires `doc_rank` — but their
inflated support still entered the reported mean, so `evidence_support`
overstated by crediting evidence from the wrong document. The terms that earned
it are NOA boilerplate (`ASCE 7-10`, `HVHZ: MIAMI-DADE AND BROWARD COUNTIES`)
printed on every sibling sheet in the corpus.

`expected_documents` is `_equivalent_paths`-expanded before this check, so the
14 groups of byte-identical filings still count for one another. What no longer
counts is a genuinely different document.

See `docs/keyword-ruler-audit.md` §6a defect 1.
"""
import unittest

from context import ROOT  # noqa: F401
from fence_evidence.evaluate import score_question
from fence_evidence.retrieval import SearchResult


def _result(source_path: str, text: str, *, page: int = 1) -> SearchResult:
    """A search hit carrying `text`, from `source_path`."""
    return SearchResult(
        document_id="doc-" + source_path[-8:], title=None, source_path=source_path,
        status="active", manufacturer=None, doc_type=None, page=page,
        element_id="element-x", element_type="paragraph", heading_path=[],
        text=text, snippet=text, text_source="pdf_text_layer",
        page_image_path=None, region_image_path=None, bbox=None, score=20.0)


QUESTION = {
    "id": "gq-000",
    "question": "what footing depth applies?",
    "answerable": True,
    "expected_answer_terms": ["ASCE 7-10", "36 inches"],
    "expected_documents": ["manuals/x/the-expected-noa.pdf"],
}


class TestSupportComesFromTheExpectedDocument(unittest.TestCase):
    def test_a_term_found_only_in_another_document_earns_no_support(self):
        """The defect: boilerplate on a sibling sheet scored as an answer.

        Fails if `joined` is rebuilt over every result. Both terms are present
        in the returned text — but in a document that is not the answer, and
        the expected document was not retrieved at all.
        """
        results = [_result("manuals/x/some-other-noa.pdf",
                           "ASCE 7-10 and 36 inches of embedment")]
        row = score_question(QUESTION, results, conn=None)
        self.assertIsNone(row["doc_rank"], "sanity: the expected doc is absent")
        self.assertEqual(row["support"], 0.0)

    def test_a_term_found_in_the_expected_document_earns_support(self):
        """The property the scoping must not break."""
        results = [_result("manuals/x/the-expected-noa.pdf",
                           "ASCE 7-10 and 36 inches of embedment")]
        row = score_question(QUESTION, results, conn=None)
        self.assertEqual(row["doc_rank"], 1)
        self.assertEqual(row["support"], 1.0)

    def test_only_the_expected_document_half_of_a_mixed_result_list_counts(self):
        """A realistic list: one expected hit, one sibling carrying the rest.

        Half credit, not full — the sibling's term is not this question's
        evidence however true it is of the corpus.
        """
        results = [_result("manuals/x/the-expected-noa.pdf", "ASCE 7-10 only"),
                   _result("manuals/x/some-other-noa.pdf", "36 inches of embedment")]
        row = score_question(QUESTION, results, conn=None)
        self.assertEqual(row["support"], 0.5)


if __name__ == "__main__":
    unittest.main()
