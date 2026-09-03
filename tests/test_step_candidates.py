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
        """Against the REAL declaration, not a fixture.

        The first version of this test read `PRAGMA table_info(elements)` on the
        two-column `elements` table this file defines by hand forty lines up. It
        was a tautology over its own fixture — it could never fail whatever the
        real schema said — while its docstring claimed to enforce
        `docs/layering.md`. Same class of error as the dedupe test the earlier
        review caught: an assertion that reads the thing it is asserting about.
        """
        import re as _re
        from fence_evidence.store import SCHEMA
        m = _re.search(r"CREATE TABLE IF NOT EXISTS elements\s*\((.*?)\n\);",
                       SCHEMA, _re.S)
        self.assertIsNotNone(m, "could not find the elements declaration")
        offenders = [line.strip() for line in m.group(1).splitlines()
                     if _re.match(r"\s*(step|candidate)\w*", line)
                     or "step_candidate" in line]
        self.assertEqual(offenders, [],
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
        """54 steps: 44 bullets + 11 sub-bullets nested inside ordinal 24, minus
        the one prohibition. `Never strike the PVC post without a wood support`
        is typed `prohibition`, which is what the design's §6 worked example
        always said it should be and what the first cut got wrong.

        Five of the remaining 54 are still not actions — an ordering permission,
        a rationale, a cross-reference, a resulting behaviour and a dimension.
        Those are for the reviewer, not for another regex; see G69."""
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
        self.assertEqual(n, 54)


@requires_full_store
class TestTheRowsActuallyInTheStore(unittest.TestCase):
    """Nothing tested the 71 rows on disk — only that `split_block` returns the
    right count if you call it again inside the test. A wrong `version_id`,
    `seq`, `ordinal` or `page_no` written by `propose()` was uncaught."""

    @classmethod
    def setUpClass(cls):
        cls.conn = connect()
        row = cls.conn.execute("SELECT document_id FROM documents WHERE source_path=?",
                               (SLICE_DOC,)).fetchone()
        if row is None:
            raise unittest.SkipTest("slice document not ingested")
        cls.doc = row[0]
        cls.rows = cls.conn.execute(
            """SELECT * FROM step_candidates WHERE document_id=? AND page_no=8
                ORDER BY ordinal, seq""", (cls.doc,)).fetchall()
        if not cls.rows:
            raise unittest.SkipTest("slice not proposed; run `cli steps --propose`")

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_every_stored_span_slices_back_to_its_element(self):
        for r in self.rows:
            src = self.conn.execute(
                "SELECT COALESCE(NULLIF(text,''), ocr_text) FROM elements "
                "WHERE element_id=?", (r["element_id"],)).fetchone()[0]
            self.assertEqual(src[r["char_start"]:r["char_end"]], r["text_raw"],
                             r["element_id"])

    def test_every_row_names_a_real_element_and_version(self):
        for r in self.rows:
            got = self.conn.execute(
                "SELECT version_id, page_no, ordinal FROM elements WHERE element_id=?",
                (r["element_id"],)).fetchone()
            self.assertIsNotNone(got, r["element_id"])
            self.assertEqual((got["version_id"], got["page_no"], got["ordinal"]),
                             (r["version_id"], r["page_no"], r["ordinal"]),
                             f"{r['element_id']} disagrees with its element")

    def test_seq_is_dense_and_ordered_within_each_element(self):
        by_element = {}
        for r in self.rows:
            by_element.setdefault(r["element_id"], []).append(r["seq"])
        for element_id, seqs in by_element.items():
            self.assertEqual(seqs, list(range(len(seqs))), element_id)

    def test_a_confidence_is_recorded_wherever_a_repair_is(self):
        for r in self.rows:
            if r["text_repair"] is not None:
                self.assertIn(r["repair_confidence"], ("high", "low"),
                              f"{r['element_id']} proposes a repair worth nothing")

    def test_nothing_is_reviewed_so_nothing_may_publish(self):
        statuses = {r["review_status"] for r in self.rows}
        self.assertEqual(statuses, {"unreviewed"})
        self.assertEqual({r["reviewer"] for r in self.rows}, {None})


if __name__ == "__main__":
    unittest.main()
