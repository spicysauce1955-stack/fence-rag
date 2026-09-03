"""`step_candidates` — the assertion layer between an element and a Procedure.

Proposals live here and publish nothing. The precedent is A1/C0: machine
agreement between two readers was being laundered into curation level 2, and
324 facts had to be un-promoted. A candidate with no reviewer is worth exactly
nothing, and these tests pin that rather than trusting it.

Pointers run DOWN. A candidate names the element it was split from; nothing on
`elements` names a candidate. `tests/test_pointer_direction.py` is the general
guard; this file checks the specific shape.
"""
import sqlite3
import unittest

from context import ROOT, requires_full_store  # noqa: F401
from fence_evidence import steps
from fence_evidence.store import STEP_CANDIDATES_DDL, connect

SLICE_DOC = "manuals/certainteed-bufftech/bufftech-fence-installation-guide-2024.pdf"


def scratch() -> sqlite3.Connection:
    """A store holding just enough to exercise the table."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE documents (document_id TEXT PRIMARY KEY, source_path TEXT,
                                doc_type TEXT, owner_tenant TEXT);
        CREATE TABLE elements (element_id TEXT PRIMARY KEY, document_id TEXT,
                               version_id TEXT, page_no INTEGER, ordinal INTEGER,
                               element_type TEXT, text TEXT, ocr_text TEXT,
                               text_source TEXT, heading_path TEXT, bbox TEXT);
    """)
    conn.executescript(STEP_CANDIDATES_DDL)
    conn.execute("INSERT INTO documents VALUES ('doc-1','a.pdf','installation_manual',NULL)")
    # verbatim from the slice page, ordinal 5 -- one bullet, one `-` sub-bullet,
    # one more bullet, so the fixture exercises depth as well as count.
    conn.execute(
        "INSERT INTO elements VALUES ('el-1','doc-1','v1',8,3,'list',?,"
        "NULL,'pdf_text_layer','[]','[1,2,3,4]')",
        ('\u2022 Dig holes 30" deep or to frost line\n'
         '- Hole size for 4x4 posts = approximately 10"\n'
         '\u2022 Clean holes and check for straight walls',))
    return conn


class TestTheTableShape(unittest.TestCase):
    def test_a_candidate_names_the_element_it_came_from(self):
        conn = scratch()
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(step_candidates)")}
        self.assertIn("element_id", cols)
        self.assertIn("char_start", cols)
        self.assertIn("char_end", cols)

    def test_nothing_on_elements_names_a_candidate(self):
        conn = scratch()
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(elements)")}
        self.assertFalse([c for c in cols if "candidate" in c or "step" in c],
                         "a pointer up a layer; docs/layering.md forbids it")

    def test_a_new_candidate_is_unreviewed(self):
        conn = scratch()
        steps.propose(conn, document_id="doc-1", page_no=8)
        statuses = {r[0] for r in conn.execute(
            "SELECT DISTINCT review_status FROM step_candidates")}
        self.assertEqual(statuses, {"unreviewed"})


class TestProposing(unittest.TestCase):
    def test_it_writes_one_row_per_segment(self):
        conn = scratch()
        n = steps.propose(conn, document_id="doc-1", page_no=8)
        self.assertEqual(n, 3)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM step_candidates").fetchone()[0], 3)

    def test_the_span_slices_back_to_the_element(self):
        conn = scratch()
        steps.propose(conn, document_id="doc-1", page_no=8)
        src = conn.execute("SELECT text FROM elements WHERE element_id='el-1'").fetchone()[0]
        for r in conn.execute("SELECT char_start, char_end, text_raw FROM step_candidates"):
            self.assertEqual(src[r["char_start"]:r["char_end"]], r["text_raw"])

    def test_it_is_idempotent(self):
        """Re-proposing must not double the queue, and must not silently discard
        a review that has already happened."""
        conn = scratch()
        steps.propose(conn, document_id="doc-1", page_no=8)
        conn.execute("UPDATE step_candidates SET review_status='accepted', "
                     "reviewer='someone' WHERE depth=1")
        steps.propose(conn, document_id="doc-1", page_no=8)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM step_candidates").fetchone()[0], 3)
        kept = conn.execute("SELECT reviewer FROM step_candidates "
                            "WHERE review_status='accepted'").fetchall()
        self.assertEqual([r[0] for r in kept], ["someone"],
                         "re-proposing destroyed a human review")

    def test_it_records_the_proposed_repair_without_applying_it(self):
        conn = scratch()
        conn.execute("UPDATE elements SET text = ? WHERE element_id='el-1'",
                     ("\u2022 I nsert post in hole",))
        steps.propose(conn, document_id="doc-1", page_no=8)
        row = conn.execute("SELECT text_raw, text_repair FROM step_candidates").fetchone()
        self.assertEqual(row["text_raw"], "• I nsert post in hole")
        self.assertEqual(row["text_repair"], "Insert post in hole")

    def test_non_list_elements_are_not_proposed(self):
        conn = scratch()
        conn.execute("""INSERT INTO elements VALUES
            ('el-2','doc-1','v1',8,4,'paragraph','• not a list element',
             NULL,'pdf_text_layer','[]','[1,2,3,4]')""")
        steps.propose(conn, document_id="doc-1", page_no=8)
        got = {r[0] for r in conn.execute("SELECT DISTINCT element_id FROM step_candidates")}
        self.assertEqual(got, {"el-1"})


@requires_full_store
class TestAgainstTheSlicePage(unittest.TestCase):
    def test_the_slice_page_proposes_the_measured_number(self):
        """55 candidates: 44 from bullets, 11 from the sub-bullets nested inside
        ordinal 24. If this moves, the design's arithmetic moved with it."""
        conn = connect()
        try:
            doc = conn.execute("SELECT document_id FROM documents WHERE source_path=?",
                               (SLICE_DOC,)).fetchone()
            if doc is None:
                self.skipTest("slice document not ingested")
            rows = conn.execute(
                """SELECT element_type, text_source,
                          COALESCE(NULLIF(text,''), ocr_text) t
                     FROM elements WHERE document_id=? AND page_no=8""",
                (doc[0],)).fetchall()
        finally:
            conn.close()
        n = sum(1 for r in rows if r["element_type"] == "list"
                for s in steps.split_block(r["t"], text_source=r["text_source"])
                if s.kind == "step")
        self.assertEqual(n, 55)


if __name__ == "__main__":
    unittest.main()
