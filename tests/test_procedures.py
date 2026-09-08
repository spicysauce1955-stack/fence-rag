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
from unittest.mock import patch

from context import ROOT  # noqa: F401
from fence_evidence import steps
from fence_evidence.procedures import build_procedures
from fence_evidence.reviews import rebuild_step_projection, submit_step_review
from fence_evidence.store import STEP_CANDIDATES_DDL, STEP_REVIEWS_DDL

BLOCK = ("• I nsert post in hole\n• Determine rough height\n"
         "• N ever strike the PVC post without a wood support")


def scratch() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE documents (document_id TEXT PRIMARY KEY, source_path TEXT,
                                doc_type TEXT, title TEXT, owner_tenant TEXT,
                                manufacturer TEXT, product_family TEXT);
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
                 "'Bufftech Guide',NULL,NULL,NULL)")
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

    def test_the_procedure_is_scoped_like_every_other_published_object(self):
        """`scope: null` is a CLAIM -- "owned by no product at all" -- and it was
        the wrong one.

        `knowledge-datamodel.md:1392` defines `Procedure.scope: EntityRef | null`
        with `null` = *owned by no product*. This builder published `null` because
        the guide's `FenceModel` does not exist yet, which is *product unknown* --
        a different fact, and one the shape has a better answer for.

        `parameters._default_scope` already resolves exactly this for a
        `ParameterTable` off the same documents: a `fence_model` ref in the `mfr/`
        namespace where the curated metadata names a family, and the document
        itself where it does not. Procedures now use it, so a procedure and a
        parameter table read off one guide agree about what they are about.
        """
        conn = scratch()
        review(conn, 0)
        proc = build_procedures(conn, source_ref_page=mint(conn))[0][0]
        self.assertEqual(proc["scope"],
                         {"kind": "source_document", "id": "doc-1", "tenant": None})

    def test_steps_keep_source_order_but_print_order_is_not_a_dependency(self):
        """Contract obligation 11, quoted: *"Publish `requires` where a document
        ASSERTS a dependency ... and leave it empty where the document merely
        prints one step after another. Two guides here explicitly DENY their own
        print order."*

        This builder synthesised an `after` edge between every consecutive pair,
        on a comment claiming page order is "a STATED order". The contract's own
        evidence is that it is not: a guide that prints A then B and then says
        the order does not matter would have been published asserting that it
        does. Order is preserved in the list; it is no longer published as an
        edge.
        """
        conn = scratch()
        review(conn, 0)
        review(conn, 1)
        proc = build_procedures(conn, source_ref_page=mint(conn))[0][0]
        keys = [s["key"] for s in proc["steps"]]
        self.assertEqual(len(keys), 2)
        self.assertEqual(proc["steps"][0]["requires"], [])
        self.assertEqual(proc["steps"][1]["requires"], [],
                         "print order is not an asserted dependency")

    def test_no_step_anywhere_publishes_a_synthesised_edge(self):
        conn = scratch()
        review(conn, 0)
        review(conn, 1)
        review(conn, 2)
        proc = build_procedures(conn, source_ref_page=mint(conn))[0][0]
        self.assertEqual([s["requires"] for s in proc["steps"]], [[], [], []])

    def test_a_guide_naming_a_family_scopes_into_the_mfr_namespace(self):
        """The branch that matters on real data, and the point of the change.

        A `ParameterTable` read off a CertainTeed guide is scoped
        `mfr/certainteed-bufftech`. Before this fix a `Procedure` off the SAME
        guide published `scope: null`, so the two disagreed about what they were
        about, and the procedure was invisible to `reach.py`'s identity count.
        Now they agree.
        """
        conn = scratch()
        conn.execute("UPDATE documents SET manufacturer='CertainTeed', "
                     "product_family='Bufftech' WHERE document_id='doc-1'")
        review(conn, 0)
        proc = build_procedures(conn, source_ref_page=mint(conn))[0][0]
        self.assertEqual(proc["scope"], {"kind": "fence_model",
                                         "id": "mfr/certainteed-bufftech",
                                         "tenant": None})

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


class TestLatestReviewWins(unittest.TestCase):
    def test_second_review_publishes_one_corrected_step_without_self_dependency(self):
        conn = scratch()
        with patch('fence_evidence.store.now', return_value='2026-01-01T00:00:00Z'):
            review(conn, 0)
        with patch('fence_evidence.store.now', return_value='2026-01-02T00:00:00Z'):
            review(conn, 0, verdict='corrected', text_final='Insert post in hole')
        published = build_procedures(conn)[0][0]['steps']
        self.assertEqual(len(published), 1)
        self.assertEqual(published[0]['text_i18n'], 'Insert post in hole')
        self.assertEqual(published[0]['requires'], [])

    def test_older_arriving_rejection_does_not_override_newer_acceptance(self):
        conn = scratch()
        with patch('fence_evidence.store.now', return_value='2026-01-02T00:00:00Z'):
            review(conn, 0)
        with patch('fence_evidence.store.now', return_value='2026-01-01T00:00:00Z'):
            review(conn, 0, verdict='rejected', step_kind=None, step_scope=None,
                   slot_target=None)
        before = build_procedures(conn)
        self.assertEqual(len(before[0][0]['steps']), 1)
        rebuild_step_projection(conn)
        self.assertEqual(build_procedures(conn), before)

    def test_newer_rejection_suppresses_older_acceptance(self):
        conn = scratch()
        with patch('fence_evidence.store.now', return_value='2026-01-01T00:00:00Z'):
            review(conn, 0)
        with patch('fence_evidence.store.now', return_value='2026-01-02T00:00:00Z'):
            review(conn, 0, verdict='rejected', step_kind=None, step_scope=None,
                   slot_target=None)
        self.assertEqual(build_procedures(conn)[0], [])
        rebuild_step_projection(conn)
        self.assertEqual(build_procedures(conn)[0], [])

    def test_same_timestamp_tie_is_stable_after_reverse_insertion(self):
        conn = scratch()
        with patch('fence_evidence.store.now', return_value='2026-01-01T00:00:00Z'):
            review(conn, 0, verdict='corrected', text_final='First correction')
            review(conn, 0, verdict='corrected', text_final='Second correction')
        rows = conn.execute('SELECT * FROM step_reviews ORDER BY rowid').fetchall()
        winner = max(rows, key=lambda row: row['step_review_id'])
        before = build_procedures(conn)
        self.assertEqual(len(before[0][0]['steps']), 1)
        self.assertEqual(before[0][0]['steps'][0]['text_i18n'], winner['text_final'])
        conn.execute('DELETE FROM step_reviews')
        for row in reversed(rows):
            conn.execute('INSERT INTO step_reviews VALUES (' + ','.join('?' * len(row))
                         + ')', tuple(row))
        conn.commit()
        rebuild_step_projection(conn)
        self.assertEqual(build_procedures(conn), before)

    def test_rebuild_uses_review_time_after_reverse_insertion(self):
        conn = scratch()
        with patch('fence_evidence.store.now', return_value='2026-01-01T00:00:00Z'):
            review(conn, 0)
        with patch('fence_evidence.store.now', return_value='2026-01-02T00:00:00Z'):
            review(conn, 0, verdict='corrected', text_final='Latest correction')
        before = build_procedures(conn)
        rows = conn.execute('SELECT * FROM step_reviews ORDER BY rowid DESC').fetchall()
        conn.execute('DELETE FROM step_reviews')
        for row in rows:
            conn.execute('INSERT INTO step_reviews VALUES (' + ','.join('?' * len(row))
                         + ')', tuple(row))
        conn.commit()
        rebuild_step_projection(conn)
        self.assertEqual(build_procedures(conn), before)


if __name__ == "__main__":
    unittest.main()
