"""Ingestion is idempotent and the retrieval projection is rebuildable."""
import json
import unittest

from context import requires_store
from fence_evidence.store import (build_retrieval_units, connect, stats,
                                  tool_fingerprint, version_exists)
from fence_evidence.tools import tool_versions


@requires_store
class TestIdempotency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = connect()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_ingested_versions_are_recognised_as_current(self):
        fp = tool_fingerprint(tool_versions())
        rows = self.conn.execute("""SELECT document_id, sha256 FROM document_versions
                                    LIMIT 20""").fetchall()
        self.assertGreater(len(rows), 0)
        for r in rows:
            self.assertTrue(version_exists(self.conn, r["document_id"], r["sha256"], fp),
                            "an already-ingested version would be re-extracted")

    def test_changed_tools_force_re_extraction(self):
        rows = self.conn.execute("SELECT document_id, sha256 FROM document_versions "
                                 "LIMIT 1").fetchall()
        self.assertFalse(version_exists(self.conn, rows[0]["document_id"],
                                        rows[0]["sha256"], "0000000000000000"))

    def test_no_duplicate_elements_per_page(self):
        dupes = self.conn.execute("""SELECT page_id, ordinal, COUNT(*) n FROM elements
            GROUP BY page_id, ordinal HAVING n > 1""").fetchall()
        self.assertEqual(len(dupes), 0, f"{len(dupes)} duplicated element ordinals")

    def test_one_page_row_per_source_page(self):
        dupes = self.conn.execute("""SELECT version_id, page_no, COUNT(*) n FROM pages
            GROUP BY version_id, page_no HAVING n > 1""").fetchall()
        self.assertEqual(len(dupes), 0)

    def test_retrieval_units_rebuild_identically(self):
        before = self.conn.execute("""SELECT document_id, page_no, element_id, element_ids,
            element_type, text, heading_path FROM retrieval_units
            ORDER BY document_id, page_no, element_id""").fetchall()
        self.assertGreater(len(before), 0)
        n = build_retrieval_units(self.conn)
        after = self.conn.execute("""SELECT document_id, page_no, element_id, element_ids,
            element_type, text, heading_path FROM retrieval_units
            ORDER BY document_id, page_no, element_id""").fetchall()
        self.assertEqual(n, len(before), "rebuild produced a different unit count")
        self.assertEqual([tuple(r) for r in before], [tuple(r) for r in after],
                         "rebuilding the projection changed its contents")

    def test_fts_row_count_matches_units(self):
        units = self.conn.execute("SELECT COUNT(*) FROM retrieval_units").fetchone()[0]
        fts = self.conn.execute("SELECT COUNT(*) FROM retrieval_fts").fetchone()[0]
        self.assertEqual(units, fts, "FTS index and retrieval_units are out of step")

    def test_canonical_rows_survive_a_projection_rebuild(self):
        before = stats(self.conn)
        build_retrieval_units(self.conn)
        after = stats(self.conn)
        for key in ("documents", "versions", "pages", "elements", "tables",
                    "table_cells", "assets"):
            self.assertEqual(before[key], after[key],
                             f"rebuilding the projection changed canonical {key}")

    def test_every_element_resolves_to_provenance(self):
        orphans = self.conn.execute("""SELECT COUNT(*) FROM elements e
            LEFT JOIN pages p ON p.page_id = e.page_id WHERE p.page_id IS NULL""").fetchone()[0]
        self.assertEqual(orphans, 0)
        no_run = self.conn.execute("""SELECT COUNT(*) FROM document_versions
            WHERE extraction_run_id IS NULL""").fetchone()[0]
        self.assertEqual(no_run, 0)


if __name__ == "__main__":
    unittest.main()
