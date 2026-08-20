"""Phase 3 gate: the retrieval response contract from the spec (§8)."""
import shutil
import unittest

from context import ROOT, requires_store, store_snapshot
from fence_evidence.retrieval import (get_document, get_element_context, get_page,
                                      get_region, resolve_document_version,
                                      search_evidence)
from fence_evidence.store import connect

QUERIES = ["footing depth exposure C", "post spacing", "racking slope",
           "gate hinge installation", "NOA 23-0314.05"]

REQUIRED_FIELDS = {
    "document_id": str, "source_path": str, "status": str, "page": int,
    "element_id": str, "element_type": str, "heading_path": list, "text": str,
    "text_source": str, "score": float, "retrieval_reason": dict,
}


@requires_store
class TestSearchContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = connect()
        cls.results = {q: search_evidence(q, limit=5, conn=cls.conn) for q in QUERIES}

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_queries_return_results(self):
        for q, res in self.results.items():
            self.assertGreater(len(res), 0, f"no results for {q!r}")

    def test_required_fields_and_types(self):
        for q, res in self.results.items():
            for r in res:
                d = r.to_dict()
                for field, typ in REQUIRED_FIELDS.items():
                    self.assertIn(field, d, f"{field} missing for {q!r}")
                    self.assertIsInstance(d[field], typ,
                                          f"{field} is {type(d[field])} for {q!r}")

    def test_page_image_resolves_on_disk(self):
        for q, res in self.results.items():
            for r in res:
                if r.source_path.endswith(".docx"):
                    continue    # documented exemption: no page geometry
                self.assertTrue(r.page_image_path, f"no page image for {q!r}")
                self.assertTrue((ROOT / r.page_image_path).is_file(),
                                f"page image missing on disk: {r.page_image_path}")

    def test_bbox_is_four_numbers_or_none(self):
        for res in self.results.values():
            for r in res:
                if r.bbox is None:
                    continue
                self.assertEqual(len(r.bbox), 4)
                self.assertTrue(all(isinstance(v, (int, float)) for v in r.bbox))

    def test_matched_terms_come_from_the_text(self):
        for res in self.results.values():
            for r in res:
                for term in r.retrieval_reason["matched_terms"]:
                    self.assertIn(term.lower(), r.text.lower(),
                                  "matched_terms echoed a query term absent from the text")

    def test_retrieval_reason_records_mode(self):
        for res in self.results.values():
            for r in res:
                self.assertEqual(r.retrieval_reason["mode"], "fts5")
                self.assertIn("match_expression", r.retrieval_reason)

    def test_identifier_query_finds_the_noa(self):
        res = self.results["NOA 23-0314.05"]
        self.assertTrue(any("23-0314.05" in r.source_path for r in res),
                        "identifier lookup did not surface the matching NOA")

    def test_filters_apply(self):
        res = search_evidence("post", limit=5, filters={"element_type": "table"},
                              conn=self.conn)
        for r in res:
            self.assertEqual(r.element_type, "table")

    def test_unsupported_filter_is_rejected(self):
        with self.assertRaises(ValueError):
            search_evidence("post", filters={"nonsense": 1}, conn=self.conn)

    def test_unsupported_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            search_evidence("post", mode="dense", conn=self.conn)


@requires_store
class TestAccessors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # get_region caches an on-demand crop, which is a write: use a copy
        cls.snapshot = store_snapshot()
        cls.conn = connect(cls.snapshot)
        cls.hit = search_evidence("footing depth", limit=1, conn=cls.conn)[0]

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        shutil.rmtree(cls.snapshot.parent, ignore_errors=True)

    def test_get_document_by_id_and_path(self):
        by_id = get_document(self.hit.document_id, conn=self.conn)
        by_path = get_document(self.hit.source_path, conn=self.conn)
        self.assertEqual(by_id["document_id"], by_path["document_id"])
        self.assertIn("versions", by_id)
        self.assertEqual(len(by_id["versions"][0]["sha256"]), 64)

    def test_get_page_returns_elements(self):
        page = get_page(self.hit.document_id, self.hit.page, conn=self.conn)
        self.assertIsNotNone(page)
        self.assertGreater(len(page["elements"]), 0)
        self.assertTrue(any(e["element_id"] == self.hit.element_id
                            for e in page["elements"]))

    def test_get_region_produces_image_evidence(self):
        region = get_region(self.hit.element_id, conn=self.conn)
        self.assertIsNotNone(region)
        self.assertIn("bbox", region)
        if region["region_image_path"]:
            self.assertTrue((ROOT / region["region_image_path"]).is_file())

    def test_get_element_context_returns_neighbours(self):
        ctx = get_element_context(self.hit.element_id, before=2, after=2, conn=self.conn)
        self.assertIsNotNone(ctx)
        self.assertIn("context", ctx)

    def test_missing_ids_return_none(self):
        self.assertIsNone(get_document("doc-does-not-exist", conn=self.conn))
        self.assertIsNone(get_page("doc-does-not-exist", 1, conn=self.conn))
        self.assertIsNone(get_region("element-nope", conn=self.conn))
        self.assertIsNone(get_element_context("element-nope", conn=self.conn))


@requires_store
class TestVersionResolution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = connect()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_resolves_by_approval_id(self):
        res = resolve_document_version("23-0314.05", conn=self.conn)
        self.assertIsNotNone(res)
        self.assertIn("chain", res)
        self.assertIn("active", res)

    def test_superseded_document_is_marked(self):
        res = resolve_document_version(
            "manuals/certainteed-bufftech/structural/"
            "NOA-21-0125.07-CertainTeed-extruded-pvc-fencing-2021-2024-superseded.pdf",
            conn=self.conn)
        self.assertEqual(res["status"], "superseded")

    def test_unknown_identifier(self):
        self.assertIsNone(resolve_document_version("99-9999.99", conn=self.conn))


if __name__ == "__main__":
    unittest.main()
