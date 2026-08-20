"""Phase 1 gate: the preservation assertions from the implementation spec §6.

Each pilot document must demonstrate that extraction kept the things that make
a source verifiable — hierarchy, page images, OCR text, table cells, figures,
drawing labels, bounding boxes, metadata and provenance.
"""
import json
import unittest

from context import ROOT, requires_store
from fence_evidence.pilot import NO_HEADING_EXEMPT, PILOT
from fence_evidence.store import connect


@requires_store
class TestPilotPreservation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = connect()
        cls.docs = {}
        for spec in PILOT:
            row = cls.conn.execute(
                "SELECT * FROM documents WHERE source_path=?",
                (spec["source_path"],)).fetchone()
            if row:
                cls.docs[spec["source_path"]] = row

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def _pilot(self, cls_filter=None):
        for spec in PILOT:
            if cls_filter and spec["class"] != cls_filter:
                continue
            row = self.docs.get(spec["source_path"])
            if row is None:
                self.fail(f"pilot document not ingested: {spec['source_path']}")
            yield spec, row

    def test_all_ten_pilot_documents_ingested(self):
        self.assertEqual(len(self.docs), len(PILOT),
                         f"missing: {set(p['source_path'] for p in PILOT) - set(self.docs)}")

    def test_section_hierarchy(self):
        for spec, row in self._pilot():
            if spec["source_path"] in NO_HEADING_EXEMPT:
                continue
            n = self.conn.execute(
                "SELECT COUNT(*) FROM elements WHERE document_id=? AND heading_path != '[]'",
                (row["document_id"],)).fetchone()[0]
            self.assertGreater(n, 0, f"no heading path anywhere in {spec['source_path']}")

    def test_page_images_exist_for_every_page(self):
        for spec, row in self._pilot():
            pages = self.conn.execute("""SELECT p.page_no, p.page_image_path FROM pages p
                JOIN document_versions v ON v.version_id=p.version_id
                WHERE v.document_id=?""", (row["document_id"],)).fetchall()
            self.assertGreater(len(pages), 0, f"no pages for {spec['source_path']}")
            if row["file_type"] == "docx":
                # A DOCX has no page geometry and no renderer is available in
                # this environment; the limitation is recorded as a quality
                # issue instead of being silently passed over.
                issue = self.conn.execute(
                    """SELECT COUNT(*) FROM quality_issues WHERE document_id=?
                       AND kind='no_page_image_for_docx'""",
                    (row["document_id"],)).fetchone()[0]
                self.assertGreater(issue, 0,
                                   "DOCX page-image limitation is not recorded as a "
                                   "quality issue")
                continue
            for p in pages:
                self.assertTrue(p["page_image_path"], f"page {p['page_no']} has no image")
                f = ROOT / p["page_image_path"]
                self.assertTrue(f.is_file(), f"missing image file {p['page_image_path']}")
                self.assertGreater(f.stat().st_size, 1000, f"empty image {f}")

    def test_page_count_matches_source(self):
        for spec, row in self._pilot():
            if row["file_type"] == "docx":
                continue
            n_pages = self.conn.execute("""SELECT COUNT(*) FROM pages p
                JOIN document_versions v ON v.version_id=p.version_id
                WHERE v.document_id=?""", (row["document_id"],)).fetchone()[0]
            manifest = {json.loads(l)["source_path"]: json.loads(l)
                        for l in open(ROOT / "workspace/catalog/corpus-manifest.jsonl")}
            expected = manifest[spec["source_path"]]["page_count"]
            self.assertEqual(n_pages, expected,
                             f"{spec['source_path']}: {n_pages} pages stored, source has {expected}")

    def test_ocr_text_present_for_scanned_documents(self):
        for spec, row in self._pilot():
            if "ocr" not in spec["expect"]:
                continue
            n = self.conn.execute("""SELECT COUNT(*) FROM elements
                WHERE document_id=? AND ocr_text IS NOT NULL AND ocr_text != ''""",
                (row["document_id"],)).fetchone()[0]
            self.assertGreater(n, 0, f"no OCR text for scanned {spec['source_path']}")
            conf = self.conn.execute("""SELECT AVG(p.ocr_mean_confidence) FROM pages p
                JOIN document_versions v ON v.version_id=p.version_id
                WHERE v.document_id=? AND p.ocr_mean_confidence IS NOT NULL""",
                (row["document_id"],)).fetchone()[0]
            self.assertIsNotNone(conf, "OCR confidence not recorded")

    def test_ocr_never_overwrites_source_text(self):
        bad = self.conn.execute("""SELECT COUNT(*) FROM elements
            WHERE text_source='ocr' AND text != ''""").fetchone()[0]
        self.assertEqual(bad, 0, "OCR text was written into the source-text column")

    def test_tables_and_cells(self):
        for spec, row in self._pilot():
            if "tables" not in spec["expect"]:
                continue
            tables = self.conn.execute("""SELECT t.table_id FROM tables t
                JOIN elements e ON e.element_id=t.element_id WHERE e.document_id=?""",
                (row["document_id"],)).fetchall()
            self.assertGreater(len(tables), 0, f"no tables in {spec['source_path']}")
            cells = self.conn.execute("""SELECT COUNT(*) FROM table_cells
                WHERE table_id=?""", (tables[0]["table_id"],)).fetchone()[0]
            self.assertGreaterEqual(cells, 4, "table stored with fewer than 4 cells")

    def test_scanned_tables_are_recovered_or_the_gap_is_recorded(self):
        """A table that OCR cannot rebuild must be reported, never passed over."""
        for spec, row in self._pilot():
            if "tables_or_recorded_gap" not in spec["expect"]:
                continue
            tables = self.conn.execute("""SELECT COUNT(*) FROM tables t
                JOIN elements e ON e.element_id=t.element_id WHERE e.document_id=?""",
                (row["document_id"],)).fetchone()[0]
            if tables:
                continue
            recorded = self.conn.execute("""SELECT COUNT(*) FROM quality_issues
                WHERE document_id=? AND kind='table_not_reconstructed'""",
                (row["document_id"],)).fetchone()[0]
            self.assertGreater(recorded, 0,
                               f"{spec['source_path']}: no table cells and no recorded "
                               "table_not_reconstructed issue")
            imaged = self.conn.execute("""SELECT COUNT(*) FROM pages p
                JOIN document_versions v ON v.version_id=p.version_id
                WHERE v.document_id=? AND p.page_image_path IS NOT NULL""",
                (row["document_id"],)).fetchone()[0]
            self.assertGreater(imaged, 0,
                               "the page image is the only faithful representation of an "
                               "unreconstructable table and it is missing")

    def test_figures_present_where_expected(self):
        for spec, row in self._pilot():
            if "figures" not in spec["expect"] and "drawings" not in spec["expect"]:
                continue
            n = self.conn.execute("""SELECT COUNT(*) FROM elements WHERE document_id=?
                AND element_type IN ('figure','drawing','drawing_label')""",
                (row["document_id"],)).fetchone()[0]
            self.assertGreater(n, 0, f"no figure/drawing elements in {spec['source_path']}")

    def test_drawing_labels_have_boxes(self):
        row = self.docs["manuals/weatherables/structural/weatherables-cad-augusta-8x6-privacy.png"]
        labels = self.conn.execute("""SELECT bbox, ocr_text FROM elements
            WHERE document_id=? AND element_type='drawing_label'""",
            (row["document_id"],)).fetchall()
        self.assertGreater(len(labels), 0, "CAD image produced no drawing labels")
        for l in labels:
            self.assertTrue(l["bbox"], "drawing label without a bounding box")
            self.assertEqual(len(json.loads(l["bbox"])), 4)

    def test_bounding_boxes_within_page(self):
        for spec, row in self._pilot():
            if row["file_type"] == "docx":
                continue  # a DOCX has no page geometry
            rows = self.conn.execute("""SELECT e.bbox, p.width, p.height, e.element_id
                FROM elements e JOIN pages p ON p.page_id=e.page_id
                WHERE e.document_id=? AND e.bbox IS NOT NULL""",
                (row["document_id"],)).fetchall()
            self.assertGreater(len(rows), 0, f"no bounding boxes at all in {spec['source_path']}")
            for r in rows:
                x0, y0, x1, y1 = json.loads(r["bbox"])
                self.assertLessEqual(x1, r["width"] + 1, f"{r['element_id']} exceeds page width")
                self.assertLessEqual(y1, r["height"] + 1, f"{r['element_id']} exceeds page height")
                self.assertGreaterEqual(x0, -1)
                self.assertGreaterEqual(y0, -1)

    def test_document_metadata_populated(self):
        for spec, row in self._pilot():
            self.assertTrue(row["title"] or row["manufacturer"],
                            f"no curated metadata carried for {spec['source_path']}")
            self.assertIn(row["version_status"], ("active", "superseded", "unknown"))

    def test_source_provenance_complete(self):
        for spec, row in self._pilot():
            v = self.conn.execute("""SELECT v.sha256, v.extraction_run_id, r.tool_versions
                FROM document_versions v JOIN extraction_runs r ON r.run_id=v.extraction_run_id
                WHERE v.document_id=?""", (row["document_id"],)).fetchone()
            self.assertIsNotNone(v, f"no version/run provenance for {spec['source_path']}")
            self.assertEqual(len(v["sha256"]), 64)
            tools = json.loads(v["tool_versions"])
            self.assertIn("pdftotext", tools)
            self.assertIn("tesseract", tools)

    def test_superseded_and_active_are_separate_documents(self):
        active = self.docs["manuals/certainteed-bufftech/structural/"
                           "NOA-23-0314.05-CertainTeed-Chesterfield-Columbia-Imperial-"
                           "Breezewood-Brookline-current-2023-2029.pdf"]
        superseded = self.docs["manuals/certainteed-bufftech/structural/"
                               "NOA-21-0125.07-CertainTeed-extruded-pvc-fencing-2021-2024-"
                               "superseded.pdf"]
        self.assertNotEqual(active["document_id"], superseded["document_id"])
        self.assertEqual(superseded["version_status"], "superseded")


if __name__ == "__main__":
    unittest.main()
