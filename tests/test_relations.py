"""Superseded and active documents stay separate but linked."""
import unittest

from context import requires_store
from fence_evidence.relations import primary_approval_id, supersession_chain
from fence_evidence.store import connect


class TestApprovalIds(unittest.TestCase):
    def test_from_filename(self):
        self.assertEqual(
            primary_approval_id("manuals/x/NOA-23-0314.05-current.pdf", None),
            "23-0314.05")

    def test_from_title_when_filename_lacks_it(self):
        self.assertEqual(primary_approval_id("manuals/x/fence.pdf",
                                             "Miami-Dade NOA 24-0117.05 — vinyl"),
                         "24-0117.05")

    def test_none_when_absent(self):
        self.assertIsNone(primary_approval_id("manuals/x/install.pdf", "Install guide"))


@requires_store
class TestRelations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = connect()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_no_self_relations(self):
        n = self.conn.execute("""SELECT COUNT(*) FROM relations
            WHERE from_document_id = to_document_id""").fetchone()[0]
        self.assertEqual(n, 0)

    def test_relations_reference_real_documents(self):
        n = self.conn.execute("""SELECT COUNT(*) FROM relations r
            LEFT JOIN documents a ON a.document_id = r.from_document_id
            LEFT JOIN documents b ON b.document_id = r.to_document_id
            WHERE a.document_id IS NULL OR b.document_id IS NULL""").fetchone()[0]
        self.assertEqual(n, 0)

    def test_supersedes_is_paired_with_superseded_by(self):
        rows = self.conn.execute("""SELECT from_document_id f, to_document_id t
            FROM relations WHERE relation_type='supersedes'""").fetchall()
        for r in rows:
            back = self.conn.execute("""SELECT COUNT(*) FROM relations
                WHERE from_document_id=? AND to_document_id=? AND
                      relation_type='superseded_by'""", (r["t"], r["f"])).fetchone()[0]
            self.assertEqual(back, 1, "supersedes edge without its inverse")

    def test_superseded_documents_are_not_merged(self):
        rows = self.conn.execute("""SELECT r.from_document_id f, r.to_document_id t,
            a.source_path ap, b.source_path bp FROM relations r
            JOIN documents a ON a.document_id=r.from_document_id
            JOIN documents b ON b.document_id=r.to_document_id
            WHERE r.relation_type='supersedes'""").fetchall()
        for r in rows:
            self.assertNotEqual(r["ap"], r["bp"])
            for doc in (r["f"], r["t"]):
                pages = self.conn.execute("""SELECT COUNT(*) FROM pages p
                    JOIN document_versions v ON v.version_id=p.version_id
                    WHERE v.document_id=?""", (doc,)).fetchone()[0]
                self.assertGreater(pages, 0,
                                   "a document in a supersession chain lost its pages")

    def test_chain_is_ordered_and_acyclic(self):
        rows = self.conn.execute("""SELECT DISTINCT from_document_id d FROM relations
            WHERE relation_type='supersedes'""").fetchall()
        for r in rows:
            chain = supersession_chain(self.conn, r["d"])
            self.assertEqual(len(chain), len(set(chain)), "supersession chain has a cycle")

    def test_identical_files_are_linked_not_deduplicated(self):
        groups = self.conn.execute("""SELECT sha256, COUNT(*) n FROM document_versions
            GROUP BY sha256 HAVING n > 1""").fetchall()
        for g in groups:
            docs = [r["document_id"] for r in self.conn.execute(
                "SELECT document_id FROM document_versions WHERE sha256=?", (g["sha256"],))]
            for d in docs:
                pages = self.conn.execute("""SELECT COUNT(*) FROM pages
                    WHERE version_id IN (SELECT version_id FROM document_versions
                    WHERE document_id=?)""", (d,)).fetchone()[0]
                self.assertGreater(pages, 0, "a duplicate copy was dropped instead of linked")
            linked = self.conn.execute("""SELECT COUNT(*) FROM relations
                WHERE relation_type='same_content_as' AND from_document_id=?""",
                (docs[0],)).fetchone()[0]
            self.assertGreater(linked, 0, "identical files are not linked")


if __name__ == "__main__":
    unittest.main()
