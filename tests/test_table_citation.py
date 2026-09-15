"""G73 and G74 — what a promoted table row cites, and what it calls uncovered.

G73. `promote_tables` bound a promoted fact's `element_id` to the first element
on the page in reading order, with no reference to where the table is. On a
scanned NOA page that is the banner, so every one of the 9 published
`ParameterTable`s cited a heading — `PARTS AND COMPONENTS (CONT.)`, a product
title, and in one case the OCR noise `4908829980295,`. 108 of 108 promoted
facts had `ordinal = 0`. The `ref_id` resolved, and resolved to the wrong
evidence.

The reviewed crop is the WHOLE PAGE (`is_page=True`, `bbox=None`) — a person
looked at the page image, not a sub-region — so no geometry can pick a table
rectangle, and the honest citation is the page. `refs.ref_id(sha, page, None)`
is already the page-level id and `refs.build_index` already marks it
`is_page`; the gap was only that nothing could mint one.

G74. Coverage was computed by raw byte equality, so a row that legitimately
omits a condition dimension covered nothing, and 16 of 20 published
`uncovered` points were false.
"""
import sqlite3
import unittest

from context import ROOT  # noqa: F401
from fence_evidence import refs
from fence_evidence.parameters import _matches, _uncovered_points


class TestUncoveredRespectsAWildcardRow(unittest.TestCase):
    """A row that states fewer dimensions covers MORE points, not fewer."""

    POINTS = [{"exposure_category": e, "hvhz": h}
              for e in ("B", "C", "D") for h in (False, True)]

    def test_a_row_omitting_a_dimension_covers_every_value_of_it(self):
        """The NOA page brackets B as `NON HVHZ` but C and D as `HVHZ AND NON
        HVHZ`, so the C and D rows carry no `hvhz` key at all — which under
        `_matches` means they match both. Only `{B, hvhz: true}` is a real gap."""
        rows = [{"conditions": {"exposure_category": "B", "hvhz": False}},
                {"conditions": {"exposure_category": "C"}},
                {"conditions": {"exposure_category": "D"}}]
        self.assertEqual(_uncovered_points(rows, self.POINTS),
                         [{"exposure_category": "B", "hvhz": True}])

    def test_an_exactly_stated_row_covers_only_its_own_point(self):
        rows = [{"conditions": {"exposure_category": "B", "hvhz": False}}]
        self.assertEqual(len(_uncovered_points(rows, self.POINTS)), 5)

    def test_a_fully_unconditioned_row_covers_everything(self):
        self.assertEqual(_uncovered_points([{"conditions": {}}], self.POINTS), [])

    def test_it_agrees_with_the_matcher_the_rest_of_the_file_uses(self):
        """The bug was using byte equality where `_matches` was the tool, in a
        file that already used `_matches` for this exact purpose elsewhere."""
        rows = [{"conditions": {"exposure_category": "C"}}]
        for point in self.POINTS:
            covered_by_matcher = any(_matches(r["conditions"], point) for r in rows)
            covered_by_function = point not in _uncovered_points(rows, self.POINTS)
            self.assertEqual(covered_by_matcher, covered_by_function, point)


def scratch() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE documents (document_id TEXT PRIMARY KEY, doc_type TEXT,
                                title TEXT, version_status TEXT,
                                version_status_basis TEXT, issue_date TEXT,
                                expiration_date TEXT, owner_tenant TEXT,
                                source_path TEXT, manufacturer TEXT);
        CREATE TABLE document_versions (version_id TEXT PRIMARY KEY,
                                        document_id TEXT, sha256 TEXT);
        CREATE TABLE elements (element_id TEXT PRIMARY KEY, document_id TEXT,
                               version_id TEXT, page_no INTEGER, ordinal INTEGER,
                               element_type TEXT, text TEXT, ocr_text TEXT,
                               bbox TEXT);
        CREATE TABLE pages (version_id TEXT, page_no INTEGER,
                            page_image_path TEXT, width REAL, height REAL,
                            page_image_dpi INTEGER);
        CREATE TABLE relations (from_document_id TEXT, to_document_id TEXT,
                                relation_type TEXT, basis TEXT);
    """)
    conn.execute("INSERT INTO documents VALUES ('doc-1','hvhz_noa','NOA','active',"
                 "'basis','2024-01-01','2029-01-01',NULL,'a.pdf','M')")
    conn.execute("INSERT INTO document_versions VALUES ('v1','doc-1','abc123')")
    conn.execute("INSERT INTO pages VALUES ('v1',17,'p.png',1224.0,792.0,200)")
    conn.execute("INSERT INTO elements VALUES ('el-banner','doc-1','v1',17,0,"
                 "'heading','PARTS AND COMPONENTS (CONT.)',NULL,'[163,58,364,69]')")
    conn.execute("INSERT INTO elements VALUES ('el-table','doc-1','v1',17,54,"
                 "'paragraph','MAXIMUM POST SPACING AND FOOTING DIMENSIONS',"
                 "NULL,'[112,584,828,601]')")
    return conn


class TestThePageLevelCitation(unittest.TestCase):
    """The reviewed crop is the page, so the citation must be the page."""

    def test_a_page_ref_is_not_the_banner_elements_ref(self):
        conn = scratch()
        page = refs.ref_id("abc123", 17, None)
        banner = refs.ref_id("abc123", 17, "[163,58,364,69]")
        self.assertNotEqual(page, banner)

    def test_the_page_ref_resolves_and_says_it_is_a_page(self):
        conn = scratch()
        index = refs.build_index(conn)
        loc = refs.resolve(index, refs.ref_id("abc123", 17, None))
        self.assertIsNotNone(loc, "a page ref must resolve; obligation 3")
        self.assertTrue(loc.is_page)
        self.assertIsNone(loc.bbox)

    def test_the_builder_can_mint_one(self):
        from fence_evidence.snapshot import SnapshotBuilder
        conn = scratch()
        b = SnapshotBuilder(conn, tenant="default", regime="us_astm")
        ref = b.source_ref_page("doc-1", 17)
        self.assertEqual(ref.id, refs.ref_id("abc123", 17, None))
        self.assertEqual(ref.belongs_to, "abc123")

    def test_minting_a_page_ref_registers_its_document(self):
        """Closure is structural: a cite whose SourceDoc is absent must be
        unconstructible, not merely caught by verify()."""
        from fence_evidence.snapshot import SnapshotBuilder
        conn = scratch()
        b = SnapshotBuilder(conn, tenant="default", regime="us_astm")
        b.source_ref_page("doc-1", 17)
        self.assertEqual([d.content_hash for d in b.source_docs()], ["abc123"])

    def test_an_unknown_page_raises_rather_than_minting_a_dangling_ref(self):
        from fence_evidence.snapshot import SnapshotBuilder
        conn = scratch()
        b = SnapshotBuilder(conn, tenant="default", regime="us_astm")
        with self.assertRaises(KeyError):
            b.source_ref_page("doc-1", 999)

    def test_it_refuses_another_tenants_page(self):
        from fence_evidence.snapshot import SnapshotBuilder, TenantLeak
        conn = scratch()
        conn.execute("UPDATE documents SET owner_tenant='someone-else'")
        b = SnapshotBuilder(conn, tenant="default", regime="us_astm")
        with self.assertRaises(TenantLeak):
            b.source_ref_page("doc-1", 17)


if __name__ == "__main__":
    unittest.main()
