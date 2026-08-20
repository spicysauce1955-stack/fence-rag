"""Second-stage within-page element retrieval.

The design guarantee is structural: the second stage may only *add* evidence
from pages the first stage already returned. Document set, page set, ordering
and result count must be identical with it on and off, so document recall and
page-level support cannot change. These tests assert that guarantee rather than
trusting it.
"""
import unittest

from context import ROOT, requires_store
from fence_evidence.retrieval import (SECOND_STAGE_ATTACH_CHAR_BUDGET,
                                      SECOND_STAGE_MAX_ATTACHMENTS,
                                      SECOND_STAGE_MAX_CHARS, search_evidence)
from fence_evidence.store import connect

QUERIES = [
    "Freedom Wellington 6x6 semi-privacy panel installation",
    "Illusions pergola kit post size",
    "footing depth exposure C Chesterfield",
    "post spacing 130 mph wind",
    "racking slope stepping hillside",
]


@requires_store
class TestSecondStageInvariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = connect()
        cls.pairs = []
        for q in QUERIES:
            base = search_evidence(q, limit=10, conn=cls.conn, second_stage=False)
            aug = search_evidence(q, limit=10, conn=cls.conn, second_stage=True)
            cls.pairs.append((q, base, aug))

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_result_count_unchanged(self):
        for q, base, aug in self.pairs:
            self.assertEqual(len(base), len(aug), q)

    def test_document_and_page_sequence_unchanged(self):
        for q, base, aug in self.pairs:
            self.assertEqual([(r.document_id, r.page) for r in base],
                             [(r.document_id, r.page) for r in aug],
                             f"the second stage changed which pages are returned for {q!r}")

    def test_first_stage_unit_is_preserved(self):
        for q, base, aug in self.pairs:
            self.assertEqual([r.element_id for r in base], [r.element_id for r in aug],
                             "the second stage replaced the first-stage unit instead of "
                             "augmenting it")
            self.assertEqual([r.text for r in base], [r.text for r in aug])

    def test_scores_and_order_unchanged(self):
        for q, base, aug in self.pairs:
            self.assertEqual([r.score for r in base], [r.score for r in aug], q)

    def test_attachments_absent_when_disabled(self):
        for q, base, _aug in self.pairs:
            for r in base:
                self.assertIsNone(r.within_page_evidence, q)

    def test_every_attachment_adds_a_term_the_unit_lacked(self):
        seen_any = False
        for q, _base, aug in self.pairs:
            for r in aug:
                for a in (r.within_page_evidence or []):
                    seen_any = True
                    self.assertTrue(a["adds_terms"], "attachment claims no new terms")
                    unit_text = (r.text + " " + " ".join(r.heading_path or [])).lower()
                    for term in a["adds_terms"]:
                        self.assertNotIn(term, unit_text,
                                         "attachment 'adds' a term the unit already had")
                        self.assertIn(term, (a["text"] + " " +
                                             " ".join(a["heading_path"] or [])).lower())
        self.assertTrue(seen_any, "no attachment was produced for any probe query")

    def test_attachments_come_from_the_same_page(self):
        for q, _base, aug in self.pairs:
            for r in aug:
                for a in (r.within_page_evidence or []):
                    row = self.conn.execute(
                        "SELECT document_id, page_no FROM elements WHERE element_id=?",
                        (a["element_id"],)).fetchone()
                    self.assertEqual(row["document_id"], r.document_id)
                    self.assertEqual(row["page_no"], r.page)

    def test_attachments_are_bounded(self):
        for q, _base, aug in self.pairs:
            for r in aug:
                attachments = r.within_page_evidence or []
                self.assertLessEqual(len(attachments), SECOND_STAGE_MAX_ATTACHMENTS)
                self.assertLessEqual(sum(len(a["text"]) for a in attachments),
                                     SECOND_STAGE_ATTACH_CHAR_BUDGET + SECOND_STAGE_MAX_CHARS)
                for a in attachments:
                    self.assertLessEqual(len(a["text"]), SECOND_STAGE_MAX_CHARS)

    def test_attachments_are_never_reused_across_results(self):
        for q, _base, aug in self.pairs:
            ids = [a["element_id"] for r in aug for a in (r.within_page_evidence or [])]
            self.assertEqual(len(ids), len(set(ids)),
                             "the same element was offered twice in one result list")
            unit_ids = {r.element_id for r in aug}
            self.assertFalse(set(ids) & unit_ids,
                             "an attachment duplicates a first-stage unit in the same list")

    def test_attachments_carry_provenance(self):
        for q, _base, aug in self.pairs:
            for r in aug:
                for a in (r.within_page_evidence or []):
                    self.assertTrue(a["element_id"])
                    self.assertTrue(a["text"].strip())
                    self.assertIn("element_type", a)
                    if a["region_image_path"]:
                        self.assertTrue((ROOT / a["region_image_path"]).is_file())

    def test_reaches_elements_the_index_excludes(self):
        """The point of the second stage: evidence the projection cannot return.

        Headings are excluded from `retrieval_units` (audit finding F1), so an
        attachment sourced from a heading proves the second stage searches
        canonical rows rather than the index.
        """
        self.conn.execute("CREATE TEMP TABLE IF NOT EXISTS proj(element_id TEXT PRIMARY KEY)")
        self.conn.execute("DELETE FROM proj")
        self.conn.execute("INSERT OR IGNORE INTO proj "
                          "SELECT j.value FROM retrieval_units u, json_each(u.element_ids) j")
        unindexed = 0
        for _q, _base, aug in self.pairs:
            for r in aug:
                for a in (r.within_page_evidence or []):
                    row = self.conn.execute(
                        "SELECT 1 FROM proj WHERE element_id=?", (a["element_id"],)).fetchone()
                    if row is None:
                        unindexed += 1
        self.assertGreater(unindexed, 0,
                           "every attachment came from an element already in the index; "
                           "the second stage is not reaching canonical rows")

    def test_attachments_clear_the_information_floor(self):
        """A common token missing from the unit must not be enough to attach a footer."""
        for q, _base, aug in self.pairs:
            for r in aug:
                for a in (r.within_page_evidence or []):
                    self.assertGreater(a["gain"], 0.0, q)


if __name__ == "__main__":
    unittest.main()
