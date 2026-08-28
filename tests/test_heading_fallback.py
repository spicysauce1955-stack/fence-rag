"""R1 — a heading is projected as a unit only when no unit on its page carries it.

The relevance audit's F1 finding: headings are excluded from `retrieval_units`,
so heading text reaches the index only through the `heading_path` column of
units *beneath* the heading. Where no such unit exists on the page, the text is
unreachable — 27 pages hold canonical elements and no unit at all.

R1 is the fallback: project the heading itself, and only then. R2 (prefixing
heading text onto the first unit beneath it) is deliberately not implemented —
it double-counts the text against the `heading_path` column.

The switch is off by default and these tests are what pins that: with the flag
off `build_retrieval_units` must produce exactly the rows it produced before the
option existed. `tests/test_idempotency.py` is the standing guard on the live
store; this file is the guard on the mechanism.

Stores here are built in memory. Nothing runs an extractor: a `Page`/`Element`
written by hand is a faithful stand-in, because what is under test is what the
*projection* does with a heading, not what poppler produces.
"""
import json
import os
import sqlite3
import unittest
from unittest import mock

import context  # noqa: F401  -- puts the repo root on sys.path
from fence_evidence import refs, store
from fence_evidence.ids import doc_id_for
from fence_evidence.model import Element, ExtractedDocument, Page

SHA = "c" * 64
DOC_PATH = "manuals/acme/brochure.pdf"
TOOLS = {"pdftotext": "24.02.0", "tesseract": "5.3.4"}

# The two gold questions that fail on F1 name a product in a page-1 heading.
CARRIED_HEADING = "Wellington 6x6 Semi-Privacy Panel"
LONE_HEADING = "Pergola Kits"
ORPHAN_HEADING = "Fasteners"
CROSS_PAGE_HEADING = "Gate Hardware"


def manifest_row(source_path: str = DOC_PATH) -> dict:
    return {"doc_id": doc_id_for(source_path), "source_path": source_path,
            "file_type": "pdf", "corpus_track": "us", "manufacturer": "acme",
            "title": "Polyvinyl Fence Brochure", "doc_type": "brochure",
            "file_size_bytes": 4321}


def _heading(text: str, ordinal: int, y: float, path: list[str]) -> Element:
    return Element(element_type="heading", text=text, ordinal=ordinal,
                   heading_level=1, heading_path=path,
                   bbox=(72.0, y, 400.0, y + 18.0))


def _para(text: str, ordinal: int, y: float, path: list[str]) -> Element:
    return Element(element_type="paragraph", text=text, ordinal=ordinal,
                   heading_path=path, bbox=(72.0, y, 540.0, y + 40.0))


def _page(page_no: int, elements: list[Element]) -> Page:
    return Page(page_no=page_no, width=612.0, height=792.0,
                extraction_method="pdf_text_layer", elements=elements,
                has_text_layer=True,
                text_char_count=sum(len(e.text) for e in elements))


def extracted() -> ExtractedDocument:
    """Four pages covering each case R1 has to distinguish.

    p1 — a heading with a paragraph beneath it on the same page: CARRIED.
    p2 — a heading and nothing else: the F6 heading-only page, UNREACHABLE today.
    p3 — one carried heading, then a trailing heading with no body: ORPHAN.
    p4/p5 — a heading whose only body text is on the *next* page. R1 is stated
            per page ("no other unit on that page"), so the heading is projected
            even though a unit elsewhere carries it.
    """
    pages = [
        _page(1, [
            _heading(CARRIED_HEADING, 0, 72.0, [CARRIED_HEADING]),
            _para("Panel is 6 ft by 6 ft nominal, tongue and groove.",
                  1, 100.0, [CARRIED_HEADING]),
        ]),
        _page(2, [
            _heading(LONE_HEADING, 0, 72.0, [LONE_HEADING]),
        ]),
        _page(3, [
            _heading("Materials", 0, 72.0, ["Materials"]),
            _para("Extruded rigid PVC compound per ASTM D4726.",
                  1, 100.0, ["Materials"]),
            _heading(ORPHAN_HEADING, 2, 200.0, ["Fasteners"]),
        ]),
        _page(4, [
            _heading(CROSS_PAGE_HEADING, 0, 72.0, [CROSS_PAGE_HEADING]),
        ]),
        _page(5, [
            _para("Use stainless hinges and a self-closing latch.",
                  0, 72.0, [CROSS_PAGE_HEADING]),
        ]),
    ]
    return ExtractedDocument(source_path=DOC_PATH, sha256=SHA,
                             file_type="pdf", pages=pages)


def fresh_store() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    store.migrate(conn)
    return conn


def populate(conn: sqlite3.Connection) -> None:
    fp = store.tool_fingerprint(TOOLS)
    conn.execute(
        "INSERT INTO extraction_runs(run_id, started_at, tool_versions, "
        "tool_fingerprint, pipeline_version, notes) VALUES (?,?,?,?,?,?)",
        ("run-test-heading", store.now(), json.dumps(TOOLS, sort_keys=True),
         fp, "1.0", ""))
    conn.commit()
    store.write_extracted(conn, extracted(), manifest_row(), "run-test-heading")


def unit_rows(conn: sqlite3.Connection) -> list[tuple]:
    return [tuple(r) for r in conn.execute("""
        SELECT document_id, version_id, page_no, element_id, element_ids,
               element_type, text, text_source, heading_path, bbox
          FROM retrieval_units
         ORDER BY page_no, element_id""")]


def heading_units(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    return {r["text"]: r for r in conn.execute(
        "SELECT * FROM retrieval_units WHERE element_type='heading'")}


class TestFlagIsOffByDefault(unittest.TestCase):
    def setUp(self):
        self.conn = fresh_store()
        populate(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_default_build_projects_no_heading(self):
        store.build_retrieval_units(self.conn)
        self.assertEqual(heading_units(self.conn), {},
                         "headings reached the projection with the flag off")

    def test_flag_off_rows_are_byte_identical_to_a_default_build(self):
        store.build_retrieval_units(self.conn)
        default = unit_rows(self.conn)
        self.assertGreater(len(default), 0)
        store.build_retrieval_units(self.conn, heading_fallback=False)
        self.assertEqual(default, unit_rows(self.conn),
                         "an explicit heading_fallback=False changed the rows")

    def test_turning_the_flag_on_and_off_again_restores_the_rows(self):
        store.build_retrieval_units(self.conn)
        default = unit_rows(self.conn)
        store.build_retrieval_units(self.conn, heading_fallback=True)
        self.assertNotEqual(default, unit_rows(self.conn))
        store.build_retrieval_units(self.conn)
        self.assertEqual(default, unit_rows(self.conn),
                         "the projection did not come back to baseline")

    def test_environment_variable_switches_it_on(self):
        store.build_retrieval_units(self.conn)
        baseline = len(unit_rows(self.conn))
        with mock.patch.dict(os.environ, {store.HEADING_FALLBACK_ENV: "1"}):
            store.build_retrieval_units(self.conn)
            self.assertGreater(len(unit_rows(self.conn)), baseline)
        # and an explicit keyword still wins over the environment
        with mock.patch.dict(os.environ, {store.HEADING_FALLBACK_ENV: "1"}):
            store.build_retrieval_units(self.conn, heading_fallback=False)
            self.assertEqual(len(unit_rows(self.conn)), baseline)

    def test_an_unset_or_empty_environment_variable_is_off(self):
        for value in ("", "0", "false", "no"):
            with mock.patch.dict(os.environ, {store.HEADING_FALLBACK_ENV: value}):
                store.build_retrieval_units(self.conn)
                self.assertEqual(heading_units(self.conn), {},
                                 f"{value!r} read as on")


class TestFallbackSelectsOnlyUncarriedHeadings(unittest.TestCase):
    def setUp(self):
        self.conn = fresh_store()
        populate(self.conn)
        store.build_retrieval_units(self.conn, heading_fallback=True)

    def tearDown(self):
        self.conn.close()

    def test_a_heading_no_unit_carries_becomes_a_unit(self):
        self.assertIn(LONE_HEADING, heading_units(self.conn))

    def test_a_trailing_heading_on_a_populated_page_becomes_a_unit(self):
        self.assertIn(ORPHAN_HEADING, heading_units(self.conn))

    def test_a_carried_heading_adds_nothing(self):
        self.assertNotIn(CARRIED_HEADING, heading_units(self.conn),
                         "a heading already reachable through heading_path was "
                         "projected a second time")
        self.assertNotIn("Materials", heading_units(self.conn))

    def test_carrying_is_judged_per_page(self):
        """R1 says 'no other unit on that page'. p4's heading is carried on p5."""
        self.assertIn(CROSS_PAGE_HEADING, heading_units(self.conn))
        self.assertEqual(heading_units(self.conn)[CROSS_PAGE_HEADING]["page_no"], 4)

    def test_only_the_uncarried_headings_are_added(self):
        self.assertEqual(set(heading_units(self.conn)),
                         {LONE_HEADING, ORPHAN_HEADING, CROSS_PAGE_HEADING})

    def test_a_heading_only_page_becomes_reachable(self):
        """F6: p2 has canonical elements and, today, no unit."""
        unit_less = self.conn.execute("""
            SELECT COUNT(*) FROM pages p
             WHERE NOT EXISTS (SELECT 1 FROM retrieval_units u
                                WHERE u.version_id=p.version_id
                                  AND u.page_no=p.page_no)
               AND (SELECT COUNT(*) FROM elements e
                     WHERE e.page_id=p.page_id) > 0""").fetchone()[0]
        self.assertEqual(unit_less, 0, "a page of headings is still unsearchable")

    def test_the_added_unit_is_searchable(self):
        rows = self.conn.execute(
            "SELECT rowid FROM retrieval_fts WHERE retrieval_fts MATCH ?",
            ('"pergola kits"',)).fetchall()
        self.assertEqual(len(rows), 1)
        unit = self.conn.execute("SELECT * FROM retrieval_units WHERE unit_id=?",
                                 (rows[0][0],)).fetchone()
        self.assertEqual(unit["text"], LONE_HEADING)

    def test_the_fts_row_count_still_matches(self):
        units = self.conn.execute("SELECT COUNT(*) FROM retrieval_units").fetchone()[0]
        fts = self.conn.execute("SELECT COUNT(*) FROM retrieval_fts").fetchone()[0]
        self.assertEqual(units, fts)

    def test_the_build_is_deterministic_with_the_flag_on(self):
        first = unit_rows(self.conn)
        store.build_retrieval_units(self.conn, heading_fallback=True)
        self.assertEqual(first, unit_rows(self.conn))

    def test_a_single_document_rebuild_behaves_the_same(self):
        doc_id = manifest_row()["doc_id"]
        whole = unit_rows(self.conn)
        store.build_retrieval_units(self.conn, document_id=doc_id,
                                    heading_fallback=True)
        self.assertEqual(whole, unit_rows(self.conn))


class TestProvenanceOfAnAddedUnit(unittest.TestCase):
    def setUp(self):
        self.conn = fresh_store()
        populate(self.conn)
        store.build_retrieval_units(self.conn, heading_fallback=True)
        self.unit = heading_units(self.conn)[LONE_HEADING]

    def tearDown(self):
        self.conn.close()

    def test_it_names_one_real_element_on_the_right_page(self):
        el = self.conn.execute(
            "SELECT * FROM elements WHERE element_id=?",
            (self.unit["element_id"],)).fetchone()
        self.assertIsNotNone(el, "the unit names an element that does not exist")
        self.assertEqual(el["element_type"], "heading")
        self.assertEqual(el["page_no"], self.unit["page_no"])
        self.assertEqual(el["version_id"], self.unit["version_id"])
        self.assertEqual(el["document_id"], self.unit["document_id"])
        self.assertEqual(json.loads(self.unit["element_ids"]), [el["element_id"]])
        self.assertEqual(self.unit["text_source"], el["text_source"])

    def test_the_bbox_is_the_elements_own_rectangle(self):
        el = self.conn.execute("SELECT bbox FROM elements WHERE element_id=?",
                               (self.unit["element_id"],)).fetchone()
        self.assertEqual(json.loads(self.unit["bbox"]), json.loads(el["bbox"]))

    def test_a_source_ref_minted_from_it_resolves(self):
        el = self.conn.execute("""SELECT e.bbox, e.page_no, v.sha256 FROM elements e
              JOIN document_versions v ON v.version_id = e.version_id
             WHERE e.element_id=?""", (self.unit["element_id"],)).fetchone()
        rid = refs.ref_id(el["sha256"], el["page_no"], el["bbox"])
        index = refs.build_index(self.conn)
        locus = refs.resolve(index, rid)
        self.assertIsNotNone(locus, "a citation of the added unit would not resolve")
        self.assertIn(self.unit["element_id"], locus.element_ids)
        self.assertEqual(locus.page_no, self.unit["page_no"])

    def test_the_heading_text_is_not_double_counted_into_heading_path(self):
        """The unit's own text must not also fill its `heading_path` column.

        That is R2's defect — the reason R2 was not chosen — and it would apply
        to a heading unit too, because an element's own `heading_path` includes
        itself.
        """
        self.assertNotIn(LONE_HEADING, json.loads(self.unit["heading_path"]))
        fts = self.conn.execute(
            "SELECT heading_path FROM retrieval_fts WHERE rowid=?",
            (self.unit["unit_id"],)).fetchone()
        self.assertNotIn(LONE_HEADING.lower(), (fts[0] or "").lower())

    def test_an_ancestor_path_is_kept(self):
        """Only the heading itself is dropped from its path, not its parents."""
        conn = fresh_store()
        try:
            fp = store.tool_fingerprint(TOOLS)
            conn.execute(
                "INSERT INTO extraction_runs(run_id, started_at, tool_versions, "
                "tool_fingerprint, pipeline_version, notes) VALUES (?,?,?,?,?,?)",
                ("r", store.now(), json.dumps(TOOLS, sort_keys=True), fp, "1.0", ""))
            doc = ExtractedDocument(
                source_path="manuals/acme/other.pdf", sha256="d" * 64,
                file_type="pdf",
                pages=[_page(1, [
                    _heading("Gates", 0, 72.0, ["Gates"]),
                    _para("Gate leaves ship unassembled.", 1, 100.0, ["Gates"]),
                    _heading("Latches", 2, 200.0, ["Gates", "Latches"]),
                ])])
            store.write_extracted(conn, doc,
                                  manifest_row("manuals/acme/other.pdf"), "r")
            store.build_retrieval_units(conn, heading_fallback=True)
            unit = heading_units(conn)["Latches"]
            self.assertEqual(json.loads(unit["heading_path"]), ["Gates"])
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
