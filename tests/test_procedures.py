"""`procedures` — what a reviewed step publishes, and what an unreviewed one does not.

The member has been declared and empty since the contract was signed. This is
the path that fills it, and the rule it enforces is the one A1/C0 established:
a candidate with no reviewer publishes nothing, ever.

Because nothing on the slice page is reviewed yet, the live snapshot publishes
`procedures: []` and a gap that says so. These tests prove the path works by
reviewing a step and watching it appear — the machinery is finished even though
the queue is not.
"""
import sqlite3
import unittest

from context import ROOT  # noqa: F401
from fence_evidence import steps
from fence_evidence.procedures import build_procedures
from fence_evidence.reviews import submit_step_review
from fence_evidence.store import STEP_CANDIDATES_DDL, STEP_REVIEWS_DDL

BLOCK = ("• I nsert post in hole\n• Determine rough height\n"
         "• N ever strike the PVC post without a wood support")


def scratch() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE documents (document_id TEXT PRIMARY KEY, source_path TEXT,
                                doc_type TEXT, title TEXT, owner_tenant TEXT);
        CREATE TABLE document_versions (version_id TEXT PRIMARY KEY,
                                        document_id TEXT, sha256 TEXT);
        CREATE TABLE elements (element_id TEXT PRIMARY KEY, document_id TEXT,
                               version_id TEXT, page_no INTEGER, ordinal INTEGER,
                               element_type TEXT, text TEXT, ocr_text TEXT,
                               text_source TEXT, heading_path TEXT, bbox TEXT);
        CREATE TABLE pages (version_id TEXT, page_no INTEGER,
                            page_image_path TEXT, width REAL, height REAL,
                            page_image_dpi INTEGER);
    """)
    conn.executescript(STEP_CANDIDATES_DDL)
    conn.executescript(STEP_REVIEWS_DDL)
    conn.execute("INSERT INTO documents VALUES ('doc-1','a.pdf','installation_manual',"
                 "'Bufftech Guide',NULL)")
    conn.execute("INSERT INTO document_versions VALUES ('v1','doc-1','abc123')")
    conn.execute("INSERT INTO pages VALUES ('v1',8,'p.png',612.0,792.0,200)")
    conn.execute("INSERT INTO elements VALUES ('el-1','doc-1','v1',8,7,'list',?,NULL,"
                 "'pdf_text_layer','[]','[54,290,275,370]')", (BLOCK,))
    steps.propose(conn, document_id="doc-1", page_no=8)
    return conn


def review(conn, seq, **kw):
    row = conn.execute("SELECT * FROM step_candidates WHERE seq=?", (seq,)).fetchone()
    args = dict(element_id=row["element_id"], char_start=row["char_start"],
                char_end=row["char_end"], text_seen=row["text_raw"],
                reviewer="a-person", verdict="accepted",
                step_kind="installation", step_scope="post",
                slot_target={"kind": "PostSlot", "key": "post"})
    args.update(kw)
    return submit_step_review(conn, **args)


def mint(conn):
    from fence_evidence.refs import ref_id
    def source_ref_page(document_id, page_no):
        sha = conn.execute(
            "SELECT sha256 FROM document_versions WHERE document_id=?",
            (document_id,)).fetchone()[0]
        return {"id": ref_id(sha, page_no, None), "belongs_to": sha}
    return source_ref_page


class TestNothingPublishesWithoutAPerson(unittest.TestCase):
    def test_an_unreviewed_page_publishes_no_procedure(self):
        conn = scratch()
        procedures, gaps = build_procedures(conn, source_ref_page=mint(conn))
        self.assertEqual(procedures, [])

    def test_and_says_so_with_a_gap(self):
        """Silence must never read as coverage. The gap names the page and how
        many candidates are waiting on it."""
        conn = scratch()
        _, gaps = build_procedures(conn, source_ref_page=mint(conn))
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["kind"], "missing_value")
        self.assertIn("Bufftech Guide", gaps[0]["would_close"])
        self.assertIn("p8", gaps[0]["would_close"])

    def test_a_rejected_step_publishes_nothing_either(self):
        conn = scratch()
        review(conn, 0, verdict="rejected", step_kind=None, step_scope=None,
               slot_target=None)
        procedures, _ = build_procedures(conn, source_ref_page=mint(conn))
        self.assertEqual(procedures, [])


class TestAReviewedStepPublishes(unittest.TestCase):
    def test_one_reviewed_step_makes_one_procedure(self):
        conn = scratch()
        review(conn, 0)
        procedures, _ = build_procedures(conn, source_ref_page=mint(conn))
        self.assertEqual(len(procedures), 1)
        self.assertEqual(len(procedures[0]["steps"]), 1)

    def test_the_step_carries_what_the_person_decided(self):
        conn = scratch()
        review(conn, 0)
        step = build_procedures(conn, source_ref_page=mint(conn))[0][0]["steps"][0]
        self.assertEqual(step["kind"], "installation")
        self.assertEqual(step["scope"], "post")
        self.assertEqual(step["slots"], [{"kind": "PostSlot", "key": "post"}])

    def test_a_corrected_text_publishes_not_the_damaged_one(self):
        conn = scratch()
        review(conn, 0, verdict="corrected", text_final="Insert post in hole")
        step = build_procedures(conn, source_ref_page=mint(conn))[0][0]["steps"][0]
        self.assertEqual(step["text_i18n"], "Insert post in hole")
        self.assertNotIn("I nsert", step["text_i18n"])

    def test_every_step_cites_its_page(self):
        conn = scratch()
        review(conn, 0)
        step = build_procedures(conn, source_ref_page=mint(conn))[0][0]["steps"][0]
        self.assertEqual(len(step["cites"]), 1)
        self.assertEqual(step["cites"][0]["belongs_to"], "abc123")

    def test_the_procedure_owns_no_model(self):
        """`scope: null` — "owned by no product at all" — is honest here: the
        guide's `FenceModel` does not exist yet, so inventing a referent would
        be worse than saying nothing."""
        conn = scratch()
        review(conn, 0)
        proc = build_procedures(conn, source_ref_page=mint(conn))[0][0]
        self.assertIsNone(proc["scope"])

    def test_steps_keep_source_order_and_requires_follows_it(self):
        conn = scratch()
        review(conn, 0)
        review(conn, 1)
        proc = build_procedures(conn, source_ref_page=mint(conn))[0][0]
        keys = [s["key"] for s in proc["steps"]]
        self.assertEqual(len(keys), 2)
        self.assertEqual(proc["steps"][1]["requires"],
                         [{"kind": "after", "step": keys[0]}])

    def test_requires_names_a_key_inside_its_own_procedure(self):
        conn = scratch()
        review(conn, 0)
        review(conn, 1)
        proc = build_procedures(conn, source_ref_page=mint(conn))[0][0]
        keys = {s["key"] for s in proc["steps"]}
        for s in proc["steps"]:
            for edge in s["requires"]:
                self.assertIn(edge["step"], keys)


class TestItIsDeterministic(unittest.TestCase):
    def test_building_twice_gives_identical_bytes(self):
        from fence_evidence.canonical import canonical_bytes
        conn = scratch()
        review(conn, 0)
        a, _ = build_procedures(conn, source_ref_page=mint(conn))
        b, _ = build_procedures(conn, source_ref_page=mint(conn))
        self.assertEqual(canonical_bytes(a), canonical_bytes(b))

    def test_it_carries_no_float(self):
        from fence_evidence.canonical import canonical_bytes
        conn = scratch()
        review(conn, 0)
        procedures, gaps = build_procedures(conn, source_ref_page=mint(conn))
        canonical_bytes(procedures)   # raises on a float, a set, a bad key
        canonical_bytes(gaps)


if __name__ == "__main__":
    unittest.main()
