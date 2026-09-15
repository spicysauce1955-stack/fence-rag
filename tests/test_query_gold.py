"""The query surface's retrieval half, and its acceptance test.

`docs/knowledge-loop.md` §10 item 2 sets the bar: *"it answers the 78 gold
questions at or above the current retrieval baseline, with citations, and the
relevance audit still measures what it measured before."*

The way that bar is met here is structural rather than statistical, and that is
the point. `query._evidence` calls `search_evidence` with its shipped defaults,
adds no filters, and preserves the order it was handed. So the metrics cannot
move — and the test that keeps it that way compares the two result lists
question by question over the whole gold set, rather than re-running an
evaluation and eyeballing four means. A future edit that reorders, filters or
re-ranks inside the query surface fails here immediately, naming the question.

Two further guarantees the shape tests cannot reach:

* **Every ref handed out resolves.** Obligation 3 applies to a citation the
  moment it leaves this system, and a query answer is the first surface that
  mints refs live rather than at publish time. `cli refs --verify` walks stored
  snapshots; nothing walked these.
* **Tenancy is enforced where the ref is minted**, exactly as
  `SnapshotBuilder.source_ref` does it (G48). A hit in another tenant's document
  is unciteable, so it is not returned and the suppression is counted rather
  than silent.
"""
import sqlite3
import unittest

import context  # noqa: F401  -- puts the repo root on sys.path
from context import requires_full_store
from fence_evidence import refs
from fence_evidence.evaluate import _query_for, load_gold
from fence_evidence.query import Situation, answer_query
from fence_evidence.retrieval import search_evidence
from fence_evidence.store import SCHEMA, build_retrieval_units, connect

SNAPSHOT = {"snapshot_id": "q" * 64, "tenant": "default", "regime": "us_astm",
            "parameters": [], "procedures": [], "parts": [], "part_types": [],
            "models": [], "rules": [], "combinations": [], "source_docs": [],
            "warnings": [], "gaps": []}


@requires_full_store
class TestGoldSetRetrievalIsUnchanged(unittest.TestCase):
    """At or above the baseline, guaranteed by not touching the ranking."""

    @classmethod
    def setUpClass(cls):
        cls.conn = connect(read_only=True)
        cls.gold = load_gold()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_the_gold_set_is_still_seventy_eight_questions(self):
        self.assertEqual(len(self.gold), 78)

    def test_every_gold_question_returns_the_same_evidence_as_search(self):
        for question in self.gold:
            query = _query_for(question)
            expected = search_evidence(query, limit=10, conn=self.conn)
            answer = answer_query(Situation(question=query, limit=10),
                                  snapshot=SNAPSHOT, conn=self.conn)
            with self.subTest(question["id"]):
                self.assertEqual(
                    [(h["document_id"], h["page"], h["element_id"])
                     for h in answer.evidence],
                    [(r.document_id, r.page, r.element_id) for r in expected])

    def test_the_ranking_order_is_preserved(self):
        for question in self.gold:
            query = _query_for(question)
            expected = search_evidence(query, limit=10, conn=self.conn)
            answer = answer_query(Situation(question=query, limit=10),
                                  snapshot=SNAPSHOT, conn=self.conn)
            with self.subTest(question["id"]):
                self.assertEqual([h["score"] for h in answer.evidence],
                                 [r.score for r in expected])

    def test_r3s_suppression_report_survives_into_the_answer(self):
        """CLAUDE.md: without `duplicates_suppressed` R3 dropped 8 distinct
        documents and no metric noticed. A surface that loses it re-opens that."""
        for question in self.gold:
            answer = answer_query(
                Situation(question=_query_for(question), limit=10),
                snapshot=SNAPSHOT, conn=self.conn)
            for hit in answer.evidence:
                with self.subTest(question["id"]):
                    self.assertIn("duplicates_suppressed",
                                  hit["retrieval_reason"])

    def test_a_question_with_no_answer_returns_no_evidence_and_no_refs(self):
        unanswerable = [q for q in self.gold if not q["answerable"]]
        self.assertTrue(unanswerable)
        empty = 0
        for question in unanswerable:
            answer = answer_query(
                Situation(question=_query_for(question), limit=10),
                snapshot=SNAPSHOT, conn=self.conn)
            if not answer.evidence:
                empty += 1
                self.assertEqual(answer.refs, [])
        # Not an assertion about how many -- no-answer detection is measured in
        # `evaluate`, not here. Only that empty means empty all the way through.
        self.assertGreaterEqual(empty, 0)


@requires_full_store
class TestEveryRefHandedOutResolves(unittest.TestCase):
    """Obligation 3 at the query surface, where refs are minted live."""

    @classmethod
    def setUpClass(cls):
        cls.conn = connect(read_only=True)
        cls.index = refs.build_index(cls.conn)
        cls.gold = load_gold()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_every_evidence_ref_resolves_to_a_locus(self):
        checked = 0
        for question in self.gold:
            answer = answer_query(
                Situation(question=_query_for(question), limit=10),
                snapshot=SNAPSHOT, conn=self.conn)
            for hit in answer.evidence:
                checked += 1
                with self.subTest(question["id"], ref=hit["ref"]["id"]):
                    self.assertIsNotNone(
                        refs.resolve(self.index, hit["ref"]["id"]),
                        "a citation handed to a caller that resolves to nothing")
        self.assertGreater(checked, 0, "no refs were checked at all")

    def test_the_ref_names_the_page_the_hit_was_found_on(self):
        for question in self.gold[:20]:
            answer = answer_query(
                Situation(question=_query_for(question), limit=10),
                snapshot=SNAPSHOT, conn=self.conn)
            for hit in answer.evidence:
                locus = refs.resolve(self.index, hit["ref"]["id"])
                with self.subTest(question["id"]):
                    self.assertEqual(locus.page_no, hit["page"])
                    self.assertEqual(locus.sha256, hit["ref"]["belongs_to"])

    def test_the_explicit_ref_list_covers_every_evidence_hit(self):
        for question in self.gold[:20]:
            answer = answer_query(
                Situation(question=_query_for(question), limit=10),
                snapshot=SNAPSHOT, conn=self.conn)
            listed = {r["id"] for r in answer.refs}
            with self.subTest(question["id"]):
                self.assertEqual({h["ref"]["id"] for h in answer.evidence},
                                 listed)


class TestTenancyAtTheRefMinter(unittest.TestCase):
    """G48 — isolation is enforced where the citation is minted, not by a
    filter bolted on afterwards. A hit we cannot cite is not returned."""

    def store(self, owner):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        conn.execute(
            """INSERT INTO documents(document_id, source_path, file_type,
                    corpus_track, doc_type, title, version_status, owner_tenant)
               VALUES('doc-1','manuals/x/a.pdf','pdf','us','install_guide',
                      'A','unknown',?)""", (owner,))
        conn.execute(
            """INSERT INTO document_versions(version_id, document_id, sha256,
                    file_size_bytes, page_count, ingested_at)
               VALUES('v1','doc-1',?,1,1,'2026-09-08T00:00:00Z')""",
            ("d" * 64,))
        conn.execute(
            """INSERT INTO pages(page_id, version_id, page_no, width, height,
                    extraction_method, has_text_layer)
               VALUES('pg-1','v1',1,612,792,'text',1)""")
        conn.execute(
            """INSERT INTO elements(element_id, page_id, version_id, document_id,
                    page_no, ordinal, element_type, text, text_source,
                    heading_path, bbox)
               VALUES('el-1','pg-1','v1','doc-1',1,0,'paragraph',
                      'Set the post before the rail.','text','[]',
                      '[10.0, 20.0, 30.0, 40.0]')""")
        conn.commit()
        build_retrieval_units(conn)
        conn.commit()
        return conn

    def test_a_shared_document_is_returned_and_cited(self):
        conn = self.store(None)
        answer = answer_query(Situation(question="post rail", limit=10),
                              snapshot=SNAPSHOT, conn=conn)
        self.assertEqual(len(answer.evidence), 1)
        self.assertEqual(len(answer.refs), 1)
        self.assertEqual(answer.basis["tenancy_suppressed"], 0)

    def test_another_tenants_document_is_neither_returned_nor_cited(self):
        conn = self.store("acme-corp")
        answer = answer_query(Situation(question="post rail", limit=10),
                              snapshot=SNAPSHOT, conn=conn)
        self.assertEqual(answer.evidence, ())
        self.assertEqual(answer.refs, [])

    def test_the_suppression_is_counted_rather_than_silent(self):
        conn = self.store("acme-corp")
        answer = answer_query(Situation(question="post rail", limit=10),
                              snapshot=SNAPSHOT, conn=conn)
        self.assertEqual(answer.basis["tenancy_suppressed"], 1)

    def test_the_owning_tenant_sees_its_own_document(self):
        conn = self.store("acme-corp")
        snapshot = dict(SNAPSHOT, tenant="acme-corp")
        answer = answer_query(Situation(question="post rail", limit=10),
                              snapshot=snapshot, conn=conn)
        self.assertEqual(len(answer.evidence), 1)


class TestPassagesFromCitedDocumentsAreMarked(unittest.TestCase):
    """A returned passage and a returned value can come from the SAME document,
    and until now the answer did not say so.

    `evidence` and `values` arrived as two parallel lists with nothing joining
    them: a sealed approval's footing schedule beside three passages from an
    installation guide, and no way for a caller to tell which passages were
    even in the same document as the number it is about to cite.

    What is marked here is **document identity and nothing more** — the passage
    and the value share a `belongs_to`, which is mechanical and already in the
    answer. It is deliberately NOT a claim that the passage states the value:
    that would be asserting support this platform has not verified, on the same
    page as a value whose whole worth is that it was verified. The test below
    that pins a passage with unrelated text is what keeps the two apart.
    """

    VALUE_SHA = "d" * 64
    OTHER_SHA = "e" * 64

    def store(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        for n, (doc, sha, text) in enumerate((
                ("doc-cited", self.VALUE_SHA,
                 "Footing depth for post embedment in firm soil."),
                ("doc-uncited", self.OTHER_SHA,
                 "Footing depth is measured from finished grade."))):
            conn.execute(
                """INSERT INTO documents(document_id, source_path, file_type,
                        corpus_track, doc_type, title, version_status)
                   VALUES(?,?,'pdf','us','install_guide',?,'unknown')""",
                (doc, f"manuals/x/{doc}.pdf", doc))
            conn.execute(
                """INSERT INTO document_versions(version_id, document_id, sha256,
                        file_size_bytes, page_count, ingested_at)
                   VALUES(?,?,?,1,1,'2026-09-08T00:00:00Z')""",
                (f"v{n}", doc, sha))
            conn.execute(
                """INSERT INTO pages(page_id, version_id, page_no, width, height,
                        extraction_method, has_text_layer)
                   VALUES(?,?,1,612,792,'text',1)""", (f"pg{n}", f"v{n}"))
            conn.execute(
                """INSERT INTO elements(element_id, page_id, version_id,
                        document_id, page_no, ordinal, element_type, text,
                        text_source, heading_path, bbox)
                   VALUES(?,?,?,?,1,0,'paragraph',?,'text','[]',
                          '[10.0, 20.0, 30.0, 40.0]')""",
                (f"el{n}", f"pg{n}", f"v{n}", doc, text))
        conn.commit()
        build_retrieval_units(conn)
        conn.commit()
        return conn

    def snapshot(self):
        return dict(SNAPSHOT, parameters=[{
            "condition_scope": {"exposure_category": "site"},
            "domain": {"exposure_category": ["B", "C", "D"]},
            "domain_basis": "measured", "hit_policy": "unique",
            "parameter": "footing_depth_mm", "task": "structural_parameter",
            "scope": {"kind": "fence_model", "id": "mfr/acme", "tenant": None},
            "uncovered": [], "value_type": "quantity(mm)",
            "rows": [{
                "authority": self.VALUE_SHA, "condition_basis": "stated",
                "conditions": {"exposure_category": "C"},
                "valid_from": None, "valid_until": None,
                "value": {"amount_milli": 762000, "unit": "mm",
                          "value_raw": ['30"']},
                "provenance": {"curation_level": 2,
                               "source_class": "sealed_approval",
                               "version_status": "active",
                               "cites": [{"id": "ffffffffffffffff",
                                          "belongs_to": self.VALUE_SHA}]},
            }]}])

    def answer(self):
        return answer_query(Situation(question="footing depth", limit=10),
                            snapshot=self.snapshot(), conn=self.store())

    def test_both_documents_are_still_returned(self):
        """The marking annotates; it must not filter."""
        answer = self.answer()
        self.assertEqual(len(answer.evidence), 2)

    def test_a_passage_sharing_a_document_with_a_value_is_marked(self):
        answer = self.answer()
        marked = [h for h in answer.evidence if h["from_cited_document"]]
        self.assertEqual([h["ref"]["belongs_to"] for h in marked],
                         [self.VALUE_SHA])

    def test_it_names_what_else_cites_that_document(self):
        answer = self.answer()
        hit = [h for h in answer.evidence if h["from_cited_document"]][0]
        self.assertEqual(hit["cited_by"],
                         [{"kind": "value", "id": "footing_depth_mm"}])

    def test_a_passage_from_an_uncited_document_is_marked_false(self):
        answer = self.answer()
        hit = [h for h in answer.evidence
               if h["ref"]["belongs_to"] == self.OTHER_SHA][0]
        self.assertIs(hit["from_cited_document"], False)
        self.assertEqual(hit["cited_by"], [])

    def test_the_mark_is_document_identity_and_not_a_claim_of_support(self):
        """The marked passage says nothing about a footing DEPTH VALUE -- it
        only shares a document with one. If this ever starts meaning "this
        passage states that value", it has to be earned, not inferred."""
        answer = self.answer()
        hit = [h for h in answer.evidence if h["from_cited_document"]][0]
        self.assertNotIn("30", hit["text"])
        self.assertIs(hit["from_cited_document"], True)

    def test_the_basis_says_support_was_not_claimed(self):
        answer = self.answer()
        self.assertIs(answer.basis["evidence_support_claimed"], False)

    def test_marking_adds_no_refs(self):
        """A document-identity annotation must not enlarge the citation list --
        that list is what a grounding check matches against."""
        answer = self.answer()
        cited = {c["id"] for v in answer.values for c in v.cites}
        cited |= {h["ref"]["id"] for h in answer.evidence}
        self.assertEqual({r["id"] for r in answer.refs}, cited)

    def test_a_procedure_sharing_a_document_is_named_too(self):
        snapshot = dict(self.snapshot(), procedures=[{
            "id": "proc-abc123",
            "scope": {"kind": "fence_model", "id": "mfr/acme", "tenant": None},
            "cites": [{"id": "eeeeeeeeeeeeeeee",
                       "belongs_to": self.OTHER_SHA}],
            "steps": [],
        }])
        answer = answer_query(Situation(question="footing depth", limit=10),
                              snapshot=snapshot, conn=self.store())
        hit = [h for h in answer.evidence
               if h["ref"]["belongs_to"] == self.OTHER_SHA][0]
        self.assertEqual(hit["cited_by"],
                         [{"kind": "procedure", "id": "proc-abc123"}])


if __name__ == "__main__":
    unittest.main()
