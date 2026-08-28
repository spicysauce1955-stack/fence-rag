"""Extraction editions: a re-extraction adds, it never deletes (G38).

The property under test, stated once:

    a `ref_id` minted under edition N still resolves after edition N+1 lands.

`ref_id` is `sha256(content_hash:page_no:bbox)`. Two of those inputs are
permanent and one -- `bbox` -- is a measurement made by `pdftotext
-bbox-layout`, so a poppler upgrade that shifts a rectangle by 0.02pt changes
the id completely. That was survivable only if the rows the OLD id names stay
in the store. Before this change they did not: `write_extracted` called
`delete_version_rows` on a version_id that carried no toolchain, so the new
extraction landed on top of the old one and every citation minted from it
stopped resolving -- inside an immutable snapshot, unrepairably, with no error.

These tests build stores in memory rather than touching
`workspace/indexes/evidence.db`, and no test here runs an extractor: a
`Page`/`Element` written by hand is a faithful stand-in, because the thing being
tested is what the *store* does with two extractions, not what poppler produces.
"""
import json
import sqlite3
import unittest

import context  # noqa: F401  -- puts the repo root on sys.path
from fence_evidence import refs, store
from fence_evidence.ids import version_id_for
from fence_evidence.model import Element, ExtractedDocument, Page

SHA = "a" * 64
DOC_PATH = "manuals/acme/install-guide.pdf"

TOOLS_OLD = {"pdftotext": "24.02.0", "tesseract": "5.3.4"}
TOOLS_NEW = {"pdftotext": "24.08.0", "tesseract": "5.3.4"}


def manifest_row(source_path: str = DOC_PATH) -> dict:
    from fence_evidence.ids import doc_id_for
    return {"doc_id": doc_id_for(source_path), "source_path": source_path,
            "file_type": "pdf", "corpus_track": "us", "manufacturer": "acme",
            "title": "Install Guide", "doc_type": "install_guide",
            "file_size_bytes": 1234}


def extracted(sha: str = SHA, *, shift: float = 0.0,
              source_path: str = DOC_PATH) -> ExtractedDocument:
    """One page, two elements. `shift` moves every bbox by that many points.

    0.02 is the measured size of the real event: 1/3600 of an inch, invisible on
    the page, and enough to change every id derived from the rectangle.
    """
    els = [
        Element(element_type="heading", text="Post Footings",
                bbox=(72.0 + shift, 72.0 + shift, 300.0 + shift, 90.0 + shift),
                ordinal=0, heading_level=1),
        Element(element_type="paragraph",
                text="Set posts in a footing 36 in. deep at Exposure C.",
                bbox=(72.0 + shift, 100.0 + shift, 540.0 + shift, 120.0 + shift),
                ordinal=1, heading_path=["Post Footings"]),
    ]
    page = Page(page_no=1, width=612.0, height=792.0,
                extraction_method="pdf_text_layer", elements=els,
                has_text_layer=True, text_char_count=61)
    doc = ExtractedDocument(source_path=source_path, sha256=sha,
                            file_type="pdf", pages=[page])
    doc.issue("info", "synthetic", "fixture issue, so the per-edition "
                                   "quality_issues assertion is not vacuous", 1)
    return doc


def start_run(conn: sqlite3.Connection, tools: dict) -> str:
    """`store.start_run` with a run_id that cannot collide.

    Its own run_id is `run-<utc seconds>-<fingerprint[:6]>`, so two runs with
    the same toolchain in the same second are the same id. Real runs are 33
    minutes apart; these are microseconds apart. The fingerprint -- the thing
    under test -- is computed exactly as `start_run` computes it.
    """
    fp = store.tool_fingerprint(tools)
    seq = conn.execute("SELECT COUNT(*) FROM extraction_runs").fetchone()[0]
    run_id = f"run-test-{fp}-{seq}"
    conn.execute(
        "INSERT INTO extraction_runs(run_id, started_at, tool_versions, "
        "tool_fingerprint, pipeline_version, notes) VALUES (?,?,?,?,?,?)",
        (run_id, store.now(), json.dumps(tools, sort_keys=True), fp, "1.0", ""))
    conn.commit()
    return run_id


def fresh_store() -> sqlite3.Connection:
    """A store at the current schema, in memory.

    Built through `migrate()` rather than `executescript(SCHEMA)` so the tests
    exercise the same entry point an operator runs.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    store.migrate(conn)
    return conn


# The historical shape of `document_versions`, copied verbatim from the live
# store's `sqlite_master` before this change. It is the thing being migrated
# FROM, so it must be the real text and not a paraphrase: the rebuild finds the
# UNIQUE clause by pattern, and a paraphrase would test the pattern against
# itself.
LEGACY_DOCUMENT_VERSIONS = """
CREATE TABLE document_versions (
    version_id      TEXT PRIMARY KEY,
    document_id     TEXT NOT NULL REFERENCES documents(document_id),
    sha256          TEXT NOT NULL,
    file_size_bytes INTEGER,
    page_count      INTEGER,
    ingested_at     TEXT NOT NULL,
    extraction_run_id TEXT REFERENCES extraction_runs(run_id),
    UNIQUE(document_id, sha256)
);
"""


def legacy_store() -> sqlite3.Connection:
    """A store whose `document_versions` predates editions, with rows in it."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(LEGACY_DOCUMENT_VERSIONS)
    # Everything else comes from SCHEMA; CREATE TABLE IF NOT EXISTS leaves the
    # legacy table alone, which is exactly the situation on a real old store.
    conn.executescript(store.SCHEMA)
    return conn


class TestIdentityIncludesTheToolchain(unittest.TestCase):
    def setUp(self):
        self.conn = fresh_store()
        self.row = manifest_row()

    def tearDown(self):
        self.conn.close()

    def test_first_edition_keeps_the_id_it_has_always_had(self):
        """The invariant every published ref_id rests on."""
        run = start_run(self.conn, TOOLS_OLD)
        vid = store.write_extracted(self.conn, extracted(), self.row, run)
        self.assertEqual(vid, version_id_for(self.row["doc_id"], SHA))

    def test_a_new_toolchain_makes_a_new_edition_not_a_replacement(self):
        run1 = start_run(self.conn, TOOLS_OLD)
        v1 = store.write_extracted(self.conn, extracted(), self.row, run1)
        run2 = start_run(self.conn, TOOLS_NEW)
        v2 = store.write_extracted(self.conn, extracted(shift=0.02), self.row, run2)

        self.assertNotEqual(v1, v2)
        self.assertTrue(v2.startswith(v1 + store.EDITION_SEPARATOR),
                        f"edition 2 should extend edition 1's id, got {v2}")
        rows = store.editions_of(self.conn, self.row["doc_id"])
        self.assertEqual([r["version_id"] for r in rows], [v1, v2])
        self.assertEqual([r["edition"] for r in rows], [1, 2])
        self.assertEqual([r["tool_fingerprint"] for r in rows],
                         [store.tool_fingerprint(TOOLS_OLD),
                          store.tool_fingerprint(TOOLS_NEW)])

    def test_the_same_toolchain_rewrites_one_edition(self):
        """Re-running an interrupted ingest must not fork an edition."""
        run1 = start_run(self.conn, TOOLS_OLD)
        v1 = store.write_extracted(self.conn, extracted(), self.row, run1)
        run2 = start_run(self.conn, TOOLS_OLD)   # same tools
        v2 = store.write_extracted(self.conn, extracted(), self.row, run2)
        self.assertEqual(v1, v2)
        self.assertEqual(len(store.editions_of(self.conn, self.row["doc_id"])), 1)
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM elements").fetchone()[0], 2,
            "rewriting an edition should leave one copy of its rows, not two")

    def test_new_bytes_still_make_a_separate_version(self):
        """The case that already worked keeps working, by the same one rule."""
        run = start_run(self.conn, TOOLS_OLD)
        v1 = store.write_extracted(self.conn, extracted(), self.row, run)
        v2 = store.write_extracted(self.conn, extracted(sha="b" * 64), self.row, run)
        self.assertNotEqual(v1, v2)
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0], 2)


class TestOldRefsSurviveANewEdition(unittest.TestCase):
    """The point of the whole change, and contract obligation 3."""

    def setUp(self):
        self.conn = fresh_store()
        self.row = manifest_row()
        run1 = start_run(self.conn, TOOLS_OLD)
        self.v1 = store.write_extracted(self.conn, extracted(), self.row, run1)
        self.published = refs.build_index(self.conn)
        self.assertTrue(self.published, "fixture minted no refs")

    def tearDown(self):
        self.conn.close()

    def _re_extract(self):
        run2 = start_run(self.conn, TOOLS_NEW)
        return store.write_extracted(self.conn, extracted(shift=0.02), self.row, run2)

    def test_a_two_hundredth_of_a_point_really_does_change_the_ids(self):
        """Guards the test itself: if the shift were a no-op, the rest is vacuous."""
        before = {r for r in self.published}
        self._re_extract()
        after = set(refs.build_index(self.conn))
        self.assertTrue(after - before,
                        "a 0.02pt shift produced no new ref_id; the fixture is "
                        "not reproducing the failure it claims to")

    def test_every_ref_minted_under_edition_one_still_resolves(self):
        self._re_extract()
        index = refs.build_index(self.conn)
        for rid, locus in self.published.items():
            with self.subTest(ref_id=rid):
                self.assertIsNotNone(refs.resolve(index, rid),
                                     "a published citation stopped resolving")

    def test_the_old_ref_still_names_the_element_it_named(self):
        """Resolving is not enough -- it must resolve to the same evidence."""
        self._re_extract()
        index = refs.build_index(self.conn)
        for rid, locus in self.published.items():
            if not locus.element_ids:
                continue
            with self.subTest(ref_id=rid):
                self.assertTrue(set(locus.element_ids)
                                <= set(index[rid].element_ids))

    def test_the_old_edition_keeps_its_rows(self):
        before = self.conn.execute(
            "SELECT COUNT(*) FROM elements WHERE version_id=?", (self.v1,)).fetchone()[0]
        self._re_extract()
        after = self.conn.execute(
            "SELECT COUNT(*) FROM elements WHERE version_id=?", (self.v1,)).fetchone()[0]
        self.assertEqual(before, after,
                         "re-extraction deleted the previous edition's elements")
        for table in ("pages", "quality_issues"):
            self.assertGreater(
                self.conn.execute(f"SELECT COUNT(*) FROM {table} WHERE version_id=?",
                                  (self.v1,)).fetchone()[0], 0,
                f"re-extraction emptied {table} for the previous edition")


class TestTheDestructivePathIsUnreachable(unittest.TestCase):
    def setUp(self):
        self.conn = fresh_store()
        self.row = manifest_row()

    def tearDown(self):
        self.conn.close()

    def test_write_extracted_refuses_to_overwrite_a_foreign_edition(self):
        """A defensive assertion, tested by corrupting the row it defends.

        There is no honest way to reach this through the public path -- that is
        the point. It fires only if `version_id_for_edition` ever hands back an
        id belonging to a different toolchain, and the right response to that is
        to stop, because deleting there is the original defect.
        """
        run1 = start_run(self.conn, TOOLS_OLD)
        store.write_extracted(self.conn, extracted(), self.row, run1)
        fp_new = store.tool_fingerprint(TOOLS_NEW)
        base = version_id_for(self.row["doc_id"], SHA)
        squatter = f"{base}{store.EDITION_SEPARATOR}{fp_new}"
        self.conn.execute(
            """INSERT INTO document_versions(version_id, document_id, sha256,
               ingested_at, tool_fingerprint, edition) VALUES (?,?,?,?,?,?)""",
            (squatter, self.row["doc_id"], SHA, store.now(), "deadbeefdeadbeef", 2))
        self.conn.commit()

        run2 = start_run(self.conn, TOOLS_NEW)
        with self.assertRaises(RuntimeError) as ctx:
            store.write_extracted(self.conn, extracted(shift=0.02), self.row, run2)
        self.assertIn("refusing to overwrite", str(ctx.exception))

    def test_delete_version_rows_survives_for_a_genuine_delete(self):
        """Retiring an uncited edition has to remain possible, or editions grow
        without bound at ~31 MB each."""
        run1 = start_run(self.conn, TOOLS_OLD)
        v1 = store.write_extracted(self.conn, extracted(), self.row, run1)
        run2 = start_run(self.conn, TOOLS_NEW)
        v2 = store.write_extracted(self.conn, extracted(shift=0.02), self.row, run2)

        store.delete_version_rows(self.conn, v1)
        self.conn.commit()
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM elements WHERE version_id=?", (v1,)).fetchone()[0], 0)
        self.assertGreater(self.conn.execute(
            "SELECT COUNT(*) FROM elements WHERE version_id=?", (v2,)).fetchone()[0], 0,
            "deleting one edition must not touch another")

    def test_assets_of_the_old_edition_are_not_overwritten(self):
        """`asset_id` used to be sha256(path) alone, and the write is INSERT OR
        REPLACE -- so two editions rendering the same page image collapsed onto
        one row pointing at the newer edition.

        `_asset_row` only records a file that exists, so a real repository file
        stands in for a page image. Nothing about the file's contents matters
        here; only that two editions produce two rows.
        """
        self.row["file_size_bytes"] = 1
        doc = extracted()
        doc.pages[0].page_image_path = "README.md"
        run1 = start_run(self.conn, TOOLS_OLD)
        v1 = store.write_extracted(self.conn, doc, self.row, run1)
        if not self.conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]:
            self.skipTest("README.md not present; nothing stood in for a page image")

        doc2 = extracted(shift=0.02)
        doc2.pages[0].page_image_path = "README.md"
        run2 = start_run(self.conn, TOOLS_NEW)
        v2 = store.write_extracted(self.conn, doc2, self.row, run2)

        owners = {r[0] for r in self.conn.execute("SELECT version_id FROM assets")}
        self.assertEqual(owners, {v1, v2},
                         "a second edition replaced the first edition's asset row")


class TestVersionExists(unittest.TestCase):
    def setUp(self):
        self.conn = fresh_store()
        self.row = manifest_row()

    def tearDown(self):
        self.conn.close()

    def test_it_answers_per_edition_not_per_document(self):
        run1 = start_run(self.conn, TOOLS_OLD)
        store.write_extracted(self.conn, extracted(), self.row, run1)
        run2 = start_run(self.conn, TOOLS_NEW)
        store.write_extracted(self.conn, extracted(shift=0.02), self.row, run2)

        for tools in (TOOLS_OLD, TOOLS_NEW):
            self.assertTrue(store.version_exists(self.conn, self.row["doc_id"], SHA,
                                                 store.tool_fingerprint(tools)),
                            "an edition already in the store would be re-extracted")
        self.assertFalse(store.version_exists(self.conn, self.row["doc_id"], SHA,
                                              "0" * 16))

    def test_it_falls_back_to_the_run_when_the_column_is_not_backfilled(self):
        """An un-migrated store must not report every document stale."""
        run1 = start_run(self.conn, TOOLS_OLD)
        store.write_extracted(self.conn, extracted(), self.row, run1)
        self.conn.execute("UPDATE document_versions SET tool_fingerprint=NULL")
        self.conn.commit()
        self.assertTrue(store.version_exists(self.conn, self.row["doc_id"], SHA,
                                             store.tool_fingerprint(TOOLS_OLD)))

    def test_an_empty_edition_does_not_count_as_extracted(self):
        run1 = start_run(self.conn, TOOLS_OLD)
        store.write_extracted(self.conn, extracted(), self.row, run1)
        self.conn.execute("DELETE FROM elements")
        self.conn.execute("DELETE FROM pages")
        self.conn.commit()
        self.assertFalse(store.version_exists(self.conn, self.row["doc_id"], SHA,
                                              store.tool_fingerprint(TOOLS_OLD)))


class TestWhichEditionIsCurrent(unittest.TestCase):
    def setUp(self):
        self.conn = fresh_store()
        self.row = manifest_row()
        run1 = start_run(self.conn, TOOLS_OLD)
        self.v1 = store.write_extracted(self.conn, extracted(), self.row, run1)
        run2 = start_run(self.conn, TOOLS_NEW)
        self.v2 = store.write_extracted(self.conn, extracted(shift=0.02), self.row, run2)

    def tearDown(self):
        self.conn.close()

    def test_the_newest_edition_is_current(self):
        cur = store.current_edition(self.conn, self.row["doc_id"], SHA)
        self.assertEqual(cur["version_id"], self.v2)
        self.assertEqual(cur["edition"], 2)

    def test_the_view_agrees_with_the_helper(self):
        """One rule, two spellings -- they must not drift."""
        store.ensure_views(self.conn)
        from_view = {r["version_id"] for r in
                     self.conn.execute("SELECT version_id FROM current_editions")}
        self.assertEqual(from_view, {self.v2})

    def test_the_view_does_not_collapse_two_byte_versions(self):
        run = start_run(self.conn, TOOLS_NEW)
        other = store.write_extracted(self.conn, extracted(sha="b" * 64), self.row, run)
        store.ensure_views(self.conn)
        from_view = {r["version_id"] for r in
                     self.conn.execute("SELECT version_id FROM current_editions")}
        self.assertEqual(from_view, {self.v2, other},
                         "a different byte version is a different document, not "
                         "a superseded edition")

    def test_the_join_refs_uses_is_untouched(self):
        """`refs.build_index` joins elements to versions on `version_id`.

        Editions add rows to `document_versions`; they change neither the join
        key nor its cardinality, so the index keeps being buildable and every
        element still maps to exactly one version.
        """
        fanout = self.conn.execute("""
            SELECT COUNT(*) FROM elements e
              JOIN document_versions v ON v.version_id = e.version_id""").fetchone()[0]
        self.assertEqual(fanout,
                         self.conn.execute("SELECT COUNT(*) FROM elements").fetchone()[0])
        self.assertTrue(refs.build_index(self.conn))

    def test_stats_counts_the_superseded_edition(self):
        st = store.stats(self.conn)
        self.assertEqual(st["versions"], 2)
        self.assertEqual(st["superseded_editions"], 1)


class TestProjectionUsesTheCurrentEditionOnly(unittest.TestCase):
    def setUp(self):
        self.conn = fresh_store()
        self.row = manifest_row()

    def tearDown(self):
        self.conn.close()

    def test_a_second_edition_does_not_double_the_index(self):
        run1 = start_run(self.conn, TOOLS_OLD)
        store.write_extracted(self.conn, extracted(), self.row, run1)
        n_one = store.build_retrieval_units(self.conn)
        self.assertGreater(n_one, 0)

        run2 = start_run(self.conn, TOOLS_NEW)
        v2 = store.write_extracted(self.conn, extracted(shift=0.02), self.row, run2)
        n_two = store.build_retrieval_units(self.conn)
        self.assertEqual(n_one, n_two,
                         "both editions were projected; every hit would come "
                         "back twice")
        owners = {r[0] for r in
                  self.conn.execute("SELECT DISTINCT version_id FROM retrieval_units")}
        self.assertEqual(owners, {v2})

    def test_two_byte_versions_are_both_still_projected(self):
        """The filter is per (document, bytes) and must not eat a real version."""
        run = start_run(self.conn, TOOLS_OLD)
        v1 = store.write_extracted(self.conn, extracted(), self.row, run)
        v2 = store.write_extracted(self.conn, extracted(sha="b" * 64), self.row, run)
        store.build_retrieval_units(self.conn)
        owners = {r[0] for r in
                  self.conn.execute("SELECT DISTINCT version_id FROM retrieval_units")}
        self.assertEqual(owners, {v1, v2})


class TestMigration(unittest.TestCase):
    """Additive, idempotent, and it must not move a single `version_id`."""

    def _populate_legacy(self, conn):
        from fence_evidence.ids import doc_id_for, page_id_for
        vids = []
        for i in range(3):
            path = f"manuals/acme/doc-{i}.pdf"
            did = doc_id_for(path)
            conn.execute("""INSERT INTO documents(document_id, source_path, file_type,
                corpus_track) VALUES (?,?,?,?)""", (did, path, "pdf", "us"))
            run = start_run(conn, TOOLS_OLD)
            vid = version_id_for(did, chr(ord("a") + i) * 64)
            conn.execute("""INSERT INTO document_versions(version_id, document_id,
                sha256, page_count, ingested_at, extraction_run_id)
                VALUES (?,?,?,?,?,?)""",
                         (vid, did, chr(ord("a") + i) * 64, 1, store.now(), run))
            conn.execute("""INSERT INTO pages(page_id, version_id, page_no, width,
                height, extraction_method) VALUES (?,?,?,?,?,?)""",
                         (page_id_for(vid, 1), vid, 1, 612.0, 792.0, "pdf_text_layer"))
            vids.append(vid)
        conn.commit()
        return vids

    def test_the_legacy_unique_is_widened_and_nothing_moves(self):
        conn = legacy_store()
        try:
            vids = self._populate_legacy(conn)
            self.assertEqual(store._unique_index_columns(conn, "document_versions"),
                             [store._LEGACY_VERSION_UNIQUE])

            result = store.migrate(conn)
            self.assertTrue(result["version_unique"]["rebuilt"])
            self.assertEqual(store._unique_index_columns(conn, "document_versions"),
                             [store._EDITION_VERSION_UNIQUE])
            self.assertEqual(
                sorted(r[0] for r in
                       conn.execute("SELECT version_id FROM document_versions")),
                sorted(vids),
                "the rebuild moved a version_id; every published ref_id would break")
            self.assertEqual(result["version_unique"]["rows"], len(vids))
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
        finally:
            conn.close()

    def test_it_is_idempotent(self):
        conn = legacy_store()
        try:
            vids = self._populate_legacy(conn)
            store.migrate(conn)
            snapshot = [dict(r) for r in
                        conn.execute("SELECT * FROM document_versions ORDER BY version_id")]
            second = store.migrate(conn)
            self.assertFalse(second["version_unique"]["rebuilt"])
            self.assertEqual(second["tool_fingerprints_backfilled"], 0)
            self.assertEqual(second["added"], [])
            again = [dict(r) for r in
                     conn.execute("SELECT * FROM document_versions ORDER BY version_id")]
            self.assertEqual(snapshot, again)
            self.assertEqual(len(again), len(vids))
        finally:
            conn.close()

    def test_the_fingerprint_is_backfilled_from_the_run(self):
        conn = legacy_store()
        try:
            self._populate_legacy(conn)
            result = store.migrate(conn)
            self.assertEqual(result["tool_fingerprints_backfilled"], 3)
            fps = {r[0] for r in
                   conn.execute("SELECT tool_fingerprint FROM document_versions")}
            self.assertEqual(fps, {store.tool_fingerprint(TOOLS_OLD)})
        finally:
            conn.close()

    def test_a_version_with_no_run_keeps_a_null_fingerprint(self):
        """A placeholder would look like a fingerprint and never change, which
        would make two real toolchains collide into one edition."""
        conn = legacy_store()
        try:
            conn.execute("""INSERT INTO documents(document_id, source_path, file_type,
                corpus_track) VALUES ('d1','manuals/x.pdf','pdf','us')""")
            conn.execute("""INSERT INTO document_versions(version_id, document_id,
                sha256, ingested_at) VALUES ('v1','d1','aa',?)""", (store.now(),))
            conn.commit()
            store.migrate(conn)
            self.assertIsNone(conn.execute(
                "SELECT tool_fingerprint FROM document_versions WHERE version_id='v1'"
            ).fetchone()[0])
        finally:
            conn.close()

    def test_editions_default_to_one(self):
        conn = legacy_store()
        try:
            self._populate_legacy(conn)
            store.migrate(conn)
            self.assertEqual(
                {r[0] for r in conn.execute("SELECT edition FROM document_versions")},
                {1})
        finally:
            conn.close()

    def test_a_fresh_store_needs_no_rebuild(self):
        conn = fresh_store()
        try:
            self.assertEqual(store._unique_index_columns(conn, "document_versions"),
                             [store._EDITION_VERSION_UNIQUE])
            self.assertFalse(store.ensure_edition_unique(conn)["rebuilt"])
        finally:
            conn.close()

    def test_the_added_columns_are_declared(self):
        declared = {(t, c) for t, c, _ in store.ADDED_COLUMNS}
        self.assertIn(("document_versions", "tool_fingerprint"), declared)
        self.assertIn(("document_versions", "edition"), declared)

    def test_the_rebuild_refuses_a_schema_it_does_not_recognise(self):
        """Better to stop than to rebuild a table by guesswork.

        Here the UNIQUE is written column-level (`sha256 TEXT UNIQUE`), so
        `PRAGMA index_list` reports a constraint that has no `UNIQUE(...)`
        clause anywhere in the stored DDL. Rewriting by pattern cannot work, and
        the alternative to raising is emitting a table definition nobody wrote.
        """
        conn = sqlite3.connect(":memory:")
        try:
            conn.executescript("""
                CREATE TABLE document_versions(
                    version_id TEXT PRIMARY KEY, document_id TEXT,
                    sha256 TEXT UNIQUE, tool_fingerprint TEXT,
                    edition INTEGER DEFAULT 1);""")
            with self.assertRaises(RuntimeError) as ctx:
                store.ensure_edition_unique(conn)
            self.assertIn("does not recognise", str(ctx.exception))
        finally:
            conn.close()


class TestReversibility(unittest.TestCase):
    def test_the_constraint_can_be_narrowed_back(self):
        conn = legacy_store()
        try:
            from fence_evidence.ids import doc_id_for
            path, sha = "manuals/acme/a.pdf", SHA
            did = doc_id_for(path)
            conn.execute("""INSERT INTO documents(document_id, source_path, file_type,
                corpus_track) VALUES (?,?,?,?)""", (did, path, "pdf", "us"))
            vid = version_id_for(did, sha)
            conn.execute("""INSERT INTO document_versions(version_id, document_id,
                sha256, ingested_at) VALUES (?,?,?,?)""", (vid, did, sha, store.now()))
            conn.commit()
            store.migrate(conn)

            back = store.ensure_edition_unique(conn, store._LEGACY_VERSION_UNIQUE)
            self.assertTrue(back["rebuilt"])
            self.assertEqual(store._unique_index_columns(conn, "document_versions"),
                             [store._LEGACY_VERSION_UNIQUE])
            self.assertEqual([r[0] for r in
                              conn.execute("SELECT version_id FROM document_versions")],
                             [vid])
        finally:
            conn.close()

    def test_narrowing_is_refused_when_two_editions_exist(self):
        conn = fresh_store()
        try:
            row = manifest_row()
            run1 = start_run(conn, TOOLS_OLD)
            store.write_extracted(conn, extracted(), row, run1)
            run2 = start_run(conn, TOOLS_NEW)
            store.write_extracted(conn, extracted(shift=0.02), row, run2)

            back = store.ensure_edition_unique(conn, store._LEGACY_VERSION_UNIQUE)
            self.assertFalse(back["rebuilt"])
            self.assertIn("more than one edition", back["reason"])
            self.assertEqual(store._unique_index_columns(conn, "document_versions"),
                             [store._EDITION_VERSION_UNIQUE])
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
