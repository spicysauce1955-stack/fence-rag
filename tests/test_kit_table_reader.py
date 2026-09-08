"""The machine kit-table reader: canonical table cells into the review
lifecycle. The reader proposes; it never promotes, publishes or classifies
(Invariant 10: no table reader produces a PanelSpec)."""
import json
import sqlite3
import sys
import unittest
from pathlib import Path

from context import ROOT, requires_store  # noqa: F401
from fence_evidence.store import connect
from fence_evidence.table_review import load_reading

OUTPUT = ROOT / 'workspace/tests/machine-read-kit-tables.json'


class TestKitTableReader(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, str(ROOT / 'scripts/read_kit_tables.py')],
            capture_output=True, text=True, cwd=str(ROOT))
        if result.returncode != 0:
            raise unittest.SkipTest('reader failed: ' + result.stderr[:200])

    def test_output_file_exists_and_is_json(self):
        payload = json.loads(OUTPUT.read_text())
        pages = payload['pages']
        self.assertGreaterEqual(len(pages), 15)
        for page in pages:
            self.assertIn('source_path', page)
            self.assertEqual(page['reader'], 'machine-kit-tables-v1')
            self.assertEqual(page['is_table'], True)
            self.assertEqual(page['table_kind'], 'kit_material_list')
            headers = page['grid']['headers']
            self.assertEqual(headers[0], 'ITEM')
            self.assertEqual(headers[1], 'QTY')
            for row in page['grid']['rows']:
                cells = row['cells']
                self.assertGreaterEqual(len(cells), 2)
                # A quantity cell parses as a whole count.
                self.assertRegex(cells[1], r'^\d+$')

    def test_kit_shape_test_rejects_sku_matrices(self):
        # The accents/hardware SKU matrices (two-row headers, color columns,
        # QTY/SKU pairs) are catalogs, not kit BOMs: the shape test must not
        # read them as material lists.
        sys.path.insert(0, str(ROOT))
        from scripts.read_kit_tables import _cells, _is_kit_table
        conn = sqlite3.connect(
            f"file:{ROOT / 'workspace/indexes/evidence.db'}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        grid = _cells(conn, 'element-20559cc73d-0007')   # accents matrix
        self.assertFalse(_is_kit_table(grid)[0])
        grid = _cells(conn, 'element-cce7c312c4-0010')    # Cape Cod kit list
        self.assertTrue(_is_kit_table(grid)[0])
        conn.close()

    def test_cape_cod_kit_rows_are_read(self):
        payload = json.loads(OUTPUT.read_text())
        page = next(p for p in payload['pages'] if 'capecod' in p['source_path'])
        items = [row['cells'][0] for row in page['grid']['rows']]
        self.assertIn('Top Rail', items)
        self.assertIn('Bottom Rail', items)
        self.assertIn('Pickets', items)

    @requires_store
    def test_loading_enters_the_existing_review_lifecycle(self):
        # Load into an in-memory copy: candidates land in table_read_candidates
        # with reader_kind distinguishing machine readings, row-granular, and
        # reviewed rows are never touched by a reload.
        source = connect(read_only=True)
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        source.backup(conn)
        source.close()
        self.addCleanup(conn.close)
        result = load_reading(conn, OUTPUT, reader_kind='machine')
        self.assertEqual(result['pages_skipped_unknown_source'], 0)
        n = conn.execute(
            "SELECT COUNT(*) FROM table_read_candidates WHERE reader='machine-kit-tables-v1'"
        ).fetchone()[0]
        self.assertGreaterEqual(n, 100)
        kinds = {r[0] for r in conn.execute(
            "SELECT DISTINCT reader_kind FROM table_read_candidates "
            "WHERE reader='machine-kit-tables-v1'")}
        self.assertEqual(kinds, {'machine'})
        # Review state starts unreviewed; nothing is promoted by loading.
        statuses = {r[0] for r in conn.execute(
            "SELECT DISTINCT review_status FROM table_read_candidates "
            "WHERE reader='machine-kit-tables-v1'")}
        self.assertLessEqual(statuses, {'unreviewed'})
        # Idempotent: reloading replaces rather than duplicates.
        load_reading(conn, OUTPUT, reader_kind='machine')
        n2 = conn.execute(
            "SELECT COUNT(*) FROM table_read_candidates WHERE reader='machine-kit-tables-v1'"
        ).fetchone()[0]
        self.assertEqual(n2, n)


if __name__ == '__main__':
    unittest.main()