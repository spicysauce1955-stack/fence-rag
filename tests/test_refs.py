"""The evidence identifier, its inverse, and the guard on published citations.

Why this module exists at all: `ref_id` was defined in `snapshot.py` and
proposed a second time, incompatibly, in
`docs/integration/source-refs-design.md` 1 as an `sref_` locator. Two
identifiers for the same evidence is the failure that document itself rejects
Pillow crops for in 4.2. Addressing had no owner, so it got designed wherever
it was needed. It has one now.
"""
import unittest

import context  # noqa: F401  -- puts the repo root on sys.path
from fence_evidence.refs import ref_id


class TestIdentity(unittest.TestCase):
    """The formula is frozen: 431 published cites depend on it."""

    SHA = "00c965f58d3030b7e7c8a6c8c0b7e99f1579c5599dc476c8f6a62dd88c6cdd58"
    BBOX = "[117.69, 271.47, 266.99, 294.03]"

    def test_the_shipped_formula_is_unchanged(self):
        # Measured from the live store on 2026-08-26. If this fails, every
        # published citation has been invalidated.
        self.assertEqual(ref_id(self.SHA, 5, self.BBOX), "cd9f0d9d9c4e300f")

    def test_the_same_evidence_gets_the_same_id(self):
        self.assertEqual(ref_id(self.SHA, 5, self.BBOX),
                         ref_id(self.SHA, 5, self.BBOX))

    def test_a_hundredth_of_a_point_changes_the_id(self):
        """Not a bug -- the reason plan 2 exists. Recorded so it is not a surprise."""
        shifted = "[117.69, 271.47, 266.99, 294.05]"
        self.assertNotEqual(ref_id(self.SHA, 5, self.BBOX),
                            ref_id(self.SHA, 5, shifted))

    def test_different_bytes_give_a_different_id(self):
        other = "2f446717ee750908059bed45ce06552636671944ca8c1cbbe922092e8d769c3c"
        self.assertNotEqual(ref_id(self.SHA, 5, self.BBOX),
                            ref_id(other, 5, self.BBOX))

    def test_a_null_bbox_is_accepted_and_is_the_page_form(self):
        self.assertEqual(len(ref_id(self.SHA, 5, None)), 16)

    def test_snapshot_still_re_exports_it(self):
        """test_snapshot_build.py imports it from there; do not break that."""
        from fence_evidence.snapshot import ref_id as via_snapshot
        self.assertIs(via_snapshot, ref_id)


from context import requires_full_store
from fence_evidence.refs import Locus, build_index, resolve


@requires_full_store
class TestIndex(unittest.TestCase):
    """The inverse is a projection: rebuilt from canonical rows, never stored."""

    @classmethod
    def setUpClass(cls):
        from fence_evidence.store import connect
        cls.conn = connect(read_only=True)
        cls.index = build_index(cls.conn)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_it_indexes_the_whole_store(self):
        self.assertGreater(len(self.index), 60_000)

    def test_no_two_different_loci_share_an_id(self):
        """A true hash collision would make a citation ambiguous across documents."""
        for rid, locus in self.index.items():
            self.assertIsInstance(locus, Locus)
        # Distinct (sha, page, bbox) triples must map to distinct ids.
        triples = {(l.sha256, l.page_no, l.bbox) for l in self.index.values()}
        self.assertEqual(len(triples), len(self.index))

    def test_a_known_element_resolves_to_its_rectangle(self):
        rid = ref_id(
            "00c965f58d3030b7e7c8a6c8c0b7e99f1579c5599dc476c8f6a62dd88c6cdd58",
            5, "[117.69, 271.47, 266.99, 294.03]")
        locus = resolve(self.index, rid)
        self.assertIsNotNone(locus)
        self.assertEqual(locus.page_no, 5)
        self.assertIn("element-da08178108-0022", locus.element_ids)

    def test_an_unknown_id_resolves_to_none(self):
        self.assertIsNone(resolve(self.index, "0" * 16))

    def test_a_shared_rectangle_carries_every_element_not_one(self):
        """9,929 ids cover more than one element. Picking one silently would be
        a wrong quote; carrying all of them is the honest shape. See 5.2."""
        shared = [l for l in self.index.values() if len(l.element_ids) > 1]
        self.assertGreater(len(shared), 1_000)

    def test_page_refs_are_indexed_and_flagged(self):
        pages = [l for l in self.index.values() if l.is_page]
        self.assertGreater(len(pages), 1_000)


from fence_evidence.refs import verify_snapshots


@requires_full_store
class TestVerify(unittest.TestCase):
    """Every published citation must still resolve. Obligation 3 in one command."""

    @classmethod
    def setUpClass(cls):
        from fence_evidence.store import connect
        cls.conn = connect(read_only=True)
        cls.result = verify_snapshots(cls.conn)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_it_looked_at_something(self):
        self.assertGreaterEqual(self.result["snapshots"], 1)
        self.assertGreaterEqual(self.result["cites"], 1)

    def test_every_published_cite_resolves_today(self):
        self.assertEqual(self.result["dangling"], [],
                         "a published value cites evidence that no longer "
                         "resolves; contract obligation 3 is violated and a "
                         "snapshot is immutable, so this cannot be repaired")

    def test_every_belongs_to_names_a_real_version(self):
        self.assertEqual(self.result["unknown_versions"], [])

    def test_resolved_and_dangling_account_for_every_cite(self):
        self.assertEqual(self.result["resolved"] + len(self.result["dangling"]),
                         self.result["cites"])


class TestVerifyDetectsRot(unittest.TestCase):
    """The guard must actually fire. Proven against a fabricated snapshot in a
    temporary directory, so no real published artifact is touched."""

    def test_a_dangling_cite_is_reported(self):
        import json
        import sqlite3
        import tempfile
        from pathlib import Path

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE documents(document_id TEXT);
            CREATE TABLE document_versions(version_id TEXT, document_id TEXT, sha256 TEXT);
            CREATE TABLE elements(element_id TEXT, document_id TEXT, page_no INT, bbox TEXT);
            CREATE TABLE pages(page_id TEXT, version_id TEXT, page_no INT);
            INSERT INTO document_versions VALUES ('v1', 'd1', 'aa');
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "snap1.json").write_text(json.dumps({
                "snapshot_id": "snap1",
                "warnings": [{"cites": [{"id": "f" * 16, "belongs_to": "aa"}]}],
            }))
            result = verify_snapshots(conn, root=root)
        self.assertEqual(result["cites"], 1)
        self.assertEqual(result["resolved"], 0)
        self.assertEqual(len(result["dangling"]), 1)
        self.assertEqual(result["dangling"][0]["ref_id"], "f" * 16)
        conn.close()

    def test_a_tombstoned_snapshot_is_skipped(self):
        import json
        import sqlite3
        import tempfile
        from pathlib import Path

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE document_versions(version_id TEXT, document_id TEXT, sha256 TEXT);
            CREATE TABLE elements(element_id TEXT, document_id TEXT, page_no INT, bbox TEXT);
            CREATE TABLE pages(page_id TEXT, version_id TEXT, page_no INT);
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "snap1.json").write_text(json.dumps({
                "snapshot_id": "snap1", "tombstoned": True,
                "warnings": [{"cites": [{"id": "f" * 16, "belongs_to": "aa"}]}],
            }))
            result = verify_snapshots(conn, root=root)
        self.assertEqual(result["tombstoned_skipped"], 1)
        self.assertEqual(result["cites"], 0)
        self.assertEqual(result["dangling"], [])
        conn.close()

    def test_a_citation_outside_warnings_is_still_found(self):
        """Obligation 3 is about every published value, not just warnings.
        `combinations, models, parameters, part_types, parts, procedures,
        rules` are all declared citation-bearing top-level sections and are
        empty today -- but a scoped walk would under-count silently the day
        one of them gains a citation. This fabricates exactly that: a
        citation living under `parts[0]["cites"][0]`, nowhere near
        `warnings`."""
        import json
        import sqlite3
        import tempfile
        from pathlib import Path

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE documents(document_id TEXT);
            CREATE TABLE document_versions(version_id TEXT, document_id TEXT, sha256 TEXT);
            CREATE TABLE elements(element_id TEXT, document_id TEXT, page_no INT, bbox TEXT);
            CREATE TABLE pages(page_id TEXT, version_id TEXT, page_no INT);
            INSERT INTO document_versions VALUES ('v1', 'd1', 'aa');
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "snap1.json").write_text(json.dumps({
                "snapshot_id": "snap1",
                "warnings": [],
                "parts": [{"name": "post-cap", "cites": [
                    {"id": "e" * 16, "belongs_to": "aa"}]}],
            }))
            result = verify_snapshots(conn, root=root)
        self.assertEqual(result["cites"], 1)
        self.assertEqual(result["resolved"], 0)
        self.assertEqual(len(result["dangling"]), 1)
        self.assertEqual(result["dangling"][0]["ref_id"], "e" * 16)
        self.assertEqual(result["dangling"][0]["at"], "$.parts[0].cites[0]")
        conn.close()

    def test_a_cite_with_no_belongs_to_is_not_invisible(self):
        """`owner and owner not in known_versions` would short-circuit on a
        falsy owner, so a cite with no `belongs_to` at all would be reported
        neither dangling nor unknown -- it would simply vanish. It must land
        in `unknown_versions` instead, carrying whatever `belongs_to` actually
        was (here, absent -> None)."""
        import json
        import sqlite3
        import tempfile
        from pathlib import Path

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE documents(document_id TEXT);
            CREATE TABLE document_versions(version_id TEXT, document_id TEXT, sha256 TEXT);
            CREATE TABLE elements(element_id TEXT, document_id TEXT, page_no INT, bbox TEXT);
            CREATE TABLE pages(page_id TEXT, version_id TEXT, page_no INT);
            INSERT INTO document_versions VALUES ('v1', 'd1', 'aa');
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "snap1.json").write_text(json.dumps({
                "snapshot_id": "snap1",
                "warnings": [{"cites": [{"id": "d" * 16}]}],
            }))
            result = verify_snapshots(conn, root=root)
        self.assertEqual(result["cites"], 1)
        self.assertEqual(len(result["unknown_versions"]), 1)
        self.assertEqual(result["unknown_versions"][0]["ref_id"], "d" * 16)
        self.assertIsNone(result["unknown_versions"][0]["belongs_to"])
        conn.close()

    def test_a_wellformed_citation_outside_any_cites_list_is_still_found(self):
        """snapshot.py's own verify()/walk() treats any dict with both `id`
        and `belongs_to`, at any depth, as a SourceRef -- not only inside a
        list literally named `cites`. This module must agree, or the two
        functions answer "is this a citation?" differently, which is exactly
        the "one concept designed twice" failure `refs.py` exists to end.
        Fabricates a well-formed citation directly at `parts[0]["source_ref"]`,
        not inside any `cites` list."""
        import json
        import sqlite3
        import tempfile
        from pathlib import Path

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE documents(document_id TEXT);
            CREATE TABLE document_versions(version_id TEXT, document_id TEXT, sha256 TEXT);
            CREATE TABLE elements(element_id TEXT, document_id TEXT, page_no INT, bbox TEXT);
            CREATE TABLE pages(page_id TEXT, version_id TEXT, page_no INT);
            INSERT INTO document_versions VALUES ('v1', 'd1', 'aa');
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "snap1.json").write_text(json.dumps({
                "snapshot_id": "snap1",
                "warnings": [],
                "parts": [{"name": "post-cap",
                           "source_ref": {"id": "c" * 16, "belongs_to": "aa"}}],
            }))
            result = verify_snapshots(conn, root=root)
        self.assertEqual(result["cites"], 1)
        self.assertEqual(result["resolved"], 0)
        self.assertEqual(len(result["dangling"]), 1)
        self.assertEqual(result["dangling"][0]["ref_id"], "c" * 16)
        self.assertEqual(result["dangling"][0]["at"], "$.parts[0].source_ref")
        conn.close()

    def test_a_gap_style_id_is_not_counted_as_a_citation(self):
        """A `Gap` is `(id, kind, subject, would_close, closes_by, severity)`
        -- a bare `id`, no `belongs_to`, and not inside any `cites` list. It
        must not be mistaken for a citation: the shipped snapshot carries 63
        of them, and counting them would inflate `cites` from 431 to 494."""
        import json
        import sqlite3
        import tempfile
        from pathlib import Path

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE documents(document_id TEXT);
            CREATE TABLE document_versions(version_id TEXT, document_id TEXT, sha256 TEXT);
            CREATE TABLE elements(element_id TEXT, document_id TEXT, page_no INT, bbox TEXT);
            CREATE TABLE pages(page_id TEXT, version_id TEXT, page_no INT);
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "snap1.json").write_text(json.dumps({
                "snapshot_id": "snap1",
                "warnings": [],
                "gaps": [{"id": "g" * 16, "kind": "unresolved_query",
                          "subject": "x", "would_close": "y",
                          "closes_by": "planning", "severity": "info"}],
            }))
            result = verify_snapshots(conn, root=root)
        self.assertEqual(result["cites"], 0)
        self.assertEqual(result["dangling"], [])
        self.assertEqual(result["unknown_versions"], [])
        conn.close()


if __name__ == "__main__":
    unittest.main()
