"""C3: every table cell carries the box it was read from.

`docs/integration/planning-asks.md` §1 calls the cell bounding box "the one
above everything else", and the reason is operational rather than cosmetic: a
reviewer shown a cell box can accept or reject a reading in one keystroke, while
a reviewer shown only the table has to find the cell first. That is the
difference between a bounded review queue and an unbounded one.

The geometry is pdfplumber's own -- `table.rows[i].cells[j]` is the rect -- so
the arithmetic tests here run on a stand-in and need neither pdfplumber, poppler
nor the corpus. The backfill test does need both a PDF and pdfplumber, and skips
without them.
"""
import json
import sqlite3
import unittest

import context  # noqa: F401  -- puts the repo root on sys.path
from context import ROOT, requires_corpus
from fence_evidence.tables import (backfill_cell_bboxes, cell_bboxes_from,
                                   _grid_to_cells)
from fence_evidence.tools import have_pdfplumber

# relative to the repo root: the suite runs from `tests/` as often as from the root
BUFFTECH_REL = "manuals/certainteed-bufftech/bufftech-fence-installation-guide-2024.pdf"
BUFFTECH = ROOT / BUFFTECH_REL


class _Row:
    def __init__(self, bbox, cells):
        self.bbox, self.cells = bbox, cells


class _Table:
    def __init__(self, rows):
        self.rows = rows


class TestCellBoxesFromGeometry(unittest.TestCase):
    def test_each_cell_reports_its_own_rect(self):
        t = _Table([_Row((0, 0, 20, 10), [(0, 0, 10, 10), (10, 0, 20, 10)])])
        self.assertEqual(cell_bboxes_from(t),
                         {(0, 0): (0.0, 0.0, 10.0, 10.0),
                          (0, 1): (10.0, 0.0, 20.0, 10.0)})

    def test_a_merge_continuation_has_no_box(self):
        """`None` is pdfplumber's continuation marker, not a zero-size cell."""
        t = _Table([_Row((0, 0, 20, 10), [(0, 0, 10, 10), (10, 0, 20, 20)]),
                    _Row((0, 10, 20, 20), [(0, 10, 10, 20), None])])
        boxes = cell_bboxes_from(t)
        self.assertNotIn((1, 1), boxes)
        # the merged cell's box covers both bands, which is the region to show
        self.assertEqual(boxes[(0, 1)], (10.0, 0.0, 20.0, 20.0))

    def test_coordinates_are_rounded_to_two_places(self):
        """Must match `detect_ocr_tables`, which rounds the same way.

        Two producers of the same column disagreeing on rounding would be worse
        than one producer missing: nothing downstream could compare them.
        """
        t = _Table([_Row((0, 0, 1, 1), [(1.234567, 2.0, 3.005, 4.9999)])])
        self.assertEqual(cell_bboxes_from(t)[(0, 0)], (1.23, 2.0, 3.0, 5.0))

    def test_unreadable_geometry_is_skipped_not_raised(self):
        t = _Table([_Row((0, 0, 20, 10), [("x", None, None, None),
                                          (10, 0, 20, 10)])])
        self.assertEqual(list(cell_bboxes_from(t)), [(0, 1)])


class TestGridToCellsCarriesBoxes(unittest.TestCase):
    def test_boxes_are_attached_by_row_and_column(self):
        cells = _grid_to_cells([["a", "b"]], (0, 0, 20, 10), None,
                               {(0, 1): (10.0, 0.0, 20.0, 10.0)})
        by = {(c.row, c.col): c.bbox for c in cells}
        self.assertEqual(by[(0, 1)], (10.0, 0.0, 20.0, 10.0))
        self.assertIsNone(by[(0, 0)], "a cell with no rect keeps a null bbox")

    def test_no_boxes_is_the_old_behaviour(self):
        """The argument is optional, so the fallback path still builds cells."""
        cells = _grid_to_cells([["a", "b"]], (0, 0, 20, 10))
        self.assertEqual([c.bbox for c in cells], [None, None])


@unittest.skipUnless(have_pdfplumber(), "pdfplumber not installed")
@requires_corpus
class TestExtractionSetsBoxes(unittest.TestCase):
    def test_bufftech_footing_table_cells_all_carry_a_box(self):
        from fence_evidence.tables import detect_page_tables_and_figures
        tables, _figs, _backend, _notes = detect_page_tables_and_figures(BUFFTECH, 17)
        found = [t for t in tables if t.detector.startswith("pdfplumber:")]
        self.assertTrue(found, "page 17 carries the footing-depth table")
        for t in found:
            self.assertTrue(all(c.bbox for c in t.cells))
            for c in t.cells:
                # inside the table it came from, in PDF points, x0<x1 and top<bottom
                self.assertLess(c.bbox[0], c.bbox[2])
                self.assertLess(c.bbox[1], c.bbox[3])
                self.assertGreaterEqual(round(c.bbox[0], 1), round(t.bbox[0] - 1, 1))
                self.assertLessEqual(round(c.bbox[2], 1), round(t.bbox[2] + 1, 1))


@unittest.skipUnless(have_pdfplumber(), "pdfplumber not installed")
@requires_corpus
class TestBackfill(unittest.TestCase):
    """The backfill runs against a store built here, never the live one.

    It also proves the thing that makes the backfill safe to run at all: it
    writes `table_cells.bbox` and nothing else, so no `ref_id` input moves
    (G38). The test asserts that by hashing every other column before and after.
    """

    def _store(self):
        from fence_evidence.store import SCHEMA
        conn = sqlite3.connect(":memory:")   # never touches the workspace
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        return conn

    def _seed(self, conn, *, detector="pdfplumber:lines", bbox=None,
              n_rows=None, n_cols=None):
        """One document/element/table for the real Bufftech footing table."""
        from fence_evidence.tables import detect_page_tables_and_figures
        tables, _f, _b, _n = detect_page_tables_and_figures(BUFFTECH, 17)
        src = next(t for t in tables if t.detector == "pdfplumber:lines")
        conn.execute("INSERT INTO documents(document_id, source_path, file_type,"
                     " corpus_track) VALUES ('d1', ?, 'pdf', 'us')", (BUFFTECH_REL,))
        conn.execute("INSERT INTO document_versions(version_id, document_id,"
                     " sha256, ingested_at) VALUES ('v1','d1','0'*64,'now')")
        conn.execute("INSERT INTO pages(page_id, version_id, page_no, width,"
                     " height, extraction_method)"
                     " VALUES ('p1','v1',17,612,792,'pdftotext')")
        conn.execute("INSERT INTO elements(element_id, page_id, version_id,"
                     " document_id, page_no, ordinal, element_type, text_source)"
                     " VALUES ('e1','p1','v1','d1',17,0,'table','pdftotext')")
        conn.execute("INSERT INTO tables(table_id, element_id, n_rows, n_cols,"
                     " detector, bbox) VALUES ('t1','e1',?,?,?,?)",
                     (n_rows or src.n_rows, n_cols or src.n_cols, detector,
                      json.dumps(list(bbox or src.bbox))))
        for c in src.cells:
            conn.execute("INSERT INTO table_cells(table_id, row, col, text, bbox)"
                         " VALUES ('t1',?,?,?,NULL)", (c.row, c.col, c.text))
        conn.commit()
        return src

    def test_dry_run_counts_but_writes_nothing(self):
        conn = self._store()
        src = self._seed(conn)
        out = backfill_cell_bboxes(conn, dry_run=True)
        self.assertEqual(out["tables_matched"], 1)
        self.assertEqual(out["cells_updated"], len(src.cells))
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM table_cells WHERE bbox IS NOT NULL"
                         ).fetchone()[0], 0)

    def test_apply_writes_the_same_boxes_extraction_would(self):
        conn = self._store()
        src = self._seed(conn)
        before = conn.execute("SELECT table_id, row, col, rowspan, colspan, text"
                              " FROM table_cells ORDER BY row, col").fetchall()
        before_tables = conn.execute("SELECT * FROM tables").fetchall()
        out = backfill_cell_bboxes(conn, dry_run=False)
        self.assertEqual(out["cells_updated"], len(src.cells))
        stored = {(r["row"], r["col"]): tuple(json.loads(r["bbox"]))
                  for r in conn.execute("SELECT row, col, bbox FROM table_cells")}
        self.assertEqual(stored, {(c.row, c.col): c.bbox for c in src.cells},
                         "the backfill and extraction must agree cell for cell")
        # nothing else moved: no text, no span, no table bbox, no id
        after = conn.execute("SELECT table_id, row, col, rowspan, colspan, text"
                             " FROM table_cells ORDER BY row, col").fetchall()
        self.assertEqual([tuple(r) for r in before], [tuple(r) for r in after])
        self.assertEqual([tuple(r) for r in before_tables],
                         [tuple(r) for r in conn.execute("SELECT * FROM tables")])

    def test_rerunning_is_a_no_op(self):
        conn = self._store()
        self._seed(conn)
        backfill_cell_bboxes(conn, dry_run=False)
        self.assertEqual(backfill_cell_bboxes(conn, dry_run=False)["cells_updated"], 0,
                         "only NULL bboxes are filled, so a second pass is idle")

    def test_a_table_whose_geometry_moved_is_skipped(self):
        """Matched by its stored bbox; a drifted one is counted, not guessed."""
        conn = self._store()
        self._seed(conn, bbox=(1.0, 2.0, 3.0, 4.0))
        out = backfill_cell_bboxes(conn, dry_run=False)
        self.assertEqual(out["tables_unmatched"], 1)
        self.assertEqual(out["cells_updated"], 0)

    def test_a_table_whose_shape_moved_is_skipped(self):
        """Row/col indices are the only join, so a reshaped grid is unusable."""
        conn = self._store()
        self._seed(conn, n_cols=99)
        out = backfill_cell_bboxes(conn, dry_run=False)
        self.assertEqual(out["tables_shape_mismatch"], 1)
        self.assertEqual(out["cells_updated"], 0)

    def test_ocr_cells_are_outside_the_query(self):
        """The OCR path already sets bbox; the backfill must not revisit it."""
        conn = self._store()
        self._seed(conn, detector="ocr-word-grid")
        out = backfill_cell_bboxes(conn, dry_run=True)
        self.assertEqual(out["tables_considered"], 0)


if __name__ == "__main__":
    unittest.main()
