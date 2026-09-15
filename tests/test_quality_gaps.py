"""G78 — a known extraction failure must reach the consumer as a `Gap`.

`warnings()` only inspects text matching a warning lexeme, so an entire class
of failure this platform ALREADY DETECTS was invisible in `gaps[]`: 73
`table_not_reconstructed` issues across 13 documents, 172 low-OCR passages, 81
mojibake pages, 34 failed OCR supplements. Not one produced a published gap.

That is the failure the member exists to prevent. A gap is a first-class
publication precisely so silence never reads as coverage — and a Planning
consumer had no signal whatever that 13 documents hold tables this platform
could not reconstruct, which G2 calls the corpus's highest-value numbers.
"""
import sqlite3
import unittest

from context import ROOT  # noqa: F401
from fence_evidence.snapshot import GAP_KINDS, SnapshotBuilder


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
        CREATE TABLE pages (version_id TEXT, page_no INTEGER,
                            page_image_path TEXT, width REAL, height REAL,
                            page_image_dpi INTEGER);
        CREATE TABLE elements (element_id TEXT PRIMARY KEY, document_id TEXT,
                               version_id TEXT, page_no INTEGER, ordinal INTEGER,
                               element_type TEXT, text TEXT, ocr_text TEXT,
                               bbox TEXT);
        CREATE TABLE relations (from_document_id TEXT, to_document_id TEXT,
                                relation_type TEXT, basis TEXT);
        CREATE TABLE quality_issues (issue_id TEXT, document_id TEXT,
                                     version_id TEXT, page_no INTEGER,
                                     element_id TEXT, severity TEXT, kind TEXT,
                                     detail TEXT, detected_at TEXT);
    """)
    conn.execute("INSERT INTO documents VALUES ('doc-1','hvhz_noa','Big NOA','active',"
                 "'b','2024-01-01','2029-01-01',NULL,'a.pdf','M')")
    conn.execute("INSERT INTO document_versions VALUES ('v1','doc-1','abc123')")
    for page in (11, 17):
        conn.execute("INSERT INTO pages VALUES ('v1',?,'p.png',1224.0,792.0,200)", (page,))
    # An element to cite, so a test can register the document the way a real
    # published value does and exercise the severity rule.
    conn.execute("INSERT INTO elements VALUES ('el-doc-1','doc-1','v1',17,0,"
                 "'paragraph','a value lives here',NULL,'[1,2,3,4]')")
    return conn


def issue(conn, kind, page, detail="d", severity="warning"):
    conn.execute("INSERT INTO quality_issues VALUES (?,?,?,?,?,?,?,?,?)",
                 (f"{kind}-{page}", "doc-1", "v1", page, None, severity, kind,
                  detail, "2026-01-01T00:00:00+00:00"))


class TestAKnownFailureIsPublished(unittest.TestCase):
    def test_an_unreconstructed_table_becomes_a_gap(self):
        conn = scratch()
        issue(conn, "table_not_reconstructed", 17,
              "page names a table or conditional wind/exposure data but no cell grid")
        b = SnapshotBuilder(conn, tenant="default", regime="us_astm")
        b.quality_gaps()
        gaps = b.gaps()
        self.assertEqual(len(gaps), 1)
        self.assertIn(gaps[0].kind, GAP_KINDS)
        self.assertEqual(gaps[0].closes_by, "knowledge")

    def test_each_affected_page_gets_its_own_gap(self):
        """`SnapshotBuilder.gap` dedupes on `[kind, subject]`, so a
        document-scoped subject would collapse every page of one document into
        a single gap and lose the rest. The page must be in the subject."""
        conn = scratch()
        issue(conn, "table_not_reconstructed", 11)
        issue(conn, "table_not_reconstructed", 17)
        b = SnapshotBuilder(conn, tenant="default", regime="us_astm")
        b.quality_gaps()
        self.assertEqual(len(b.gaps()), 2)

    def test_the_gap_cites_the_page_it_is_about(self):
        """Now possible because `source_ref_page` exists (G73). The evidence for
        'this page's table could not be reconstructed' is the page."""
        conn = scratch()
        issue(conn, "table_not_reconstructed", 17)
        b = SnapshotBuilder(conn, tenant="default", regime="us_astm")
        b.quality_gaps()
        cites = b.gaps()[0].cites
        self.assertEqual(len(cites), 1)
        self.assertEqual(cites[0]["belongs_to"], "abc123")

    def test_would_close_names_the_document_and_page(self):
        """G40: 51 of 63 gaps once carried the same string literal."""
        conn = scratch()
        issue(conn, "table_not_reconstructed", 17)
        b = SnapshotBuilder(conn, tenant="default", regime="us_astm")
        b.quality_gaps()
        text = b.gaps()[0].would_close
        self.assertIn("17", text)
        self.assertIn("Big NOA", text)

    def test_two_pages_do_not_share_a_would_close_string(self):
        conn = scratch()
        issue(conn, "table_not_reconstructed", 11)
        issue(conn, "table_not_reconstructed", 17)
        b = SnapshotBuilder(conn, tenant="default", regime="us_astm")
        b.quality_gaps()
        said = [g.would_close for g in b.gaps()]
        self.assertEqual(len(set(said)), 2)

    def test_every_published_kind_is_covered(self):
        """Each detected failure class must map to a gap, or be deliberately
        excluded — never silently dropped, which is the whole finding."""
        conn = scratch()
        for n, kind in enumerate(("table_not_reconstructed", "low_ocr_confidence",
                                  "mojibake_text_layer", "empty_page_after_ocr"), start=1):
            conn.execute("INSERT INTO pages VALUES ('v1',?,'p.png',1224.0,792.0,200)",
                         (100 + n,))
            issue(conn, kind, 100 + n)
        b = SnapshotBuilder(conn, tenant="default", regime="us_astm")
        b.quality_gaps()
        self.assertEqual(len(b.gaps()), 4)

    def test_an_informational_issue_is_not_published_as_a_line_warning(self):
        conn = scratch()
        issue(conn, "ocr_supplement_failed", 17, severity="info")
        b = SnapshotBuilder(conn, tenant="default", regime="us_astm")
        b.quality_gaps()
        self.assertEqual([g.severity for g in b.gaps()], ["informational"])

    def test_a_page_with_no_page_row_is_skipped_not_crashed(self):
        """A quality issue can name a page the store has no `pages` row for.
        Refusing to mint is right; taking the whole build down is not."""
        conn = scratch()
        issue(conn, "table_not_reconstructed", 999)
        b = SnapshotBuilder(conn, tenant="default", regime="us_astm")
        b.quality_gaps()
        self.assertEqual(b.gaps(), [])

    def test_another_tenants_document_raises_no_gap(self):
        conn = scratch()
        conn.execute("UPDATE documents SET owner_tenant='someone-else'")
        issue(conn, "table_not_reconstructed", 17)
        b = SnapshotBuilder(conn, tenant="default", regime="us_astm")
        b.quality_gaps()
        self.assertEqual(b.gaps(), [])


class TestTwoFindingsAboutOnePageBothSurvive(unittest.TestCase):
    """`SnapshotBuilder.gap` deduped on `[kind, subject]` while
    `parameters._Gaps.add` deduped on `[kind, subject, code]`. Two collectors,
    two different rules for the same concept.

    Every quality gap is `illegible_source`, so a page with BOTH an
    unreconstructed table and low OCR confidence collapsed to one gap and the
    second was silently dropped — 53 of 73 unreconstructed tables lost, by the
    fix written to publish them. Research earlier in this session warned about
    exactly this and the warning was not heeded; the rule is now one rule.
    """

    def test_both_findings_publish(self):
        conn = scratch()
        issue(conn, "table_not_reconstructed", 17)
        issue(conn, "low_ocr_confidence", 17)
        b = SnapshotBuilder(conn, tenant="default", regime="us_astm")
        b.quality_gaps()
        codes = sorted(g.because["code"] for g in b.gaps())
        self.assertEqual(codes, ["ocr_below_confidence_floor", "table_not_reconstructed"])

    def test_the_same_finding_twice_still_dedupes(self):
        conn = scratch()
        issue(conn, "table_not_reconstructed", 17)
        b = SnapshotBuilder(conn, tenant="default", regime="us_astm")
        b.quality_gaps()
        b.quality_gaps()
        self.assertEqual(len(b.gaps()), 1)

    def test_the_two_collectors_now_agree(self):
        """The defect was two dedupe rules for one concept, not one wrong rule.

        Asserted on behaviour rather than by reading the source: an earlier
        version of this test parsed `canonical_bytes(` out of the function text
        and passed or failed on comment placement, which is exactly the class
        of test this session has already been caught writing twice.
        """
        from fence_evidence.parameters import _Gaps
        subject = {"kind": "page", "id": "doc-1#p17", "tenant": None}
        collector = _Gaps()
        for code in ("table_not_reconstructed", "ocr_below_confidence_floor"):
            collector.add(kind="illegible_source", subject=subject, code=code,
                          would_close=f"close {code}", closes_by="knowledge")
        self.assertEqual(len(collector.list()), 2, "_Gaps collapsed two findings")

        conn = scratch()
        issue(conn, "table_not_reconstructed", 17)
        issue(conn, "low_ocr_confidence", 17)
        b = SnapshotBuilder(conn, tenant="default", regime="us_astm")
        b.quality_gaps()
        self.assertEqual(len(b.gaps()), 2, "SnapshotBuilder collapsed two findings")


class TestQualityGapsAreInformational(unittest.TestCase):
    """`warns_line` means a line of a plan gets a warning. A page this platform
    read badly is a statement about ITS OWN knowledge, not about any particular
    line, and 372 of them at `warns_line` would drown the channel that G74 just
    finished making trustworthy."""

    def test_a_quality_gap_does_not_warn_a_line(self):
        conn = scratch()
        issue(conn, "table_not_reconstructed", 17)
        issue(conn, "low_ocr_confidence", 11)
        b = SnapshotBuilder(conn, tenant="default", regime="us_astm")
        b.quality_gaps()
        self.assertEqual({g.severity for g in b.gaps()}, {"informational"})


class TestADocumentScopedFailureStillPublishes(unittest.TestCase):
    """`WHERE q.page_no IS NOT NULL` meant a document-level failure could never
    publish. `encrypted_pdf` is exactly that — one row, `page_no` NULL, a
    document whose extraction is known-partial — and `QUALITY_GAP_KINDS` listed
    it as publishable while the query silently excluded it.

    That is this fix's own defect reproducing in miniature: a detected failure
    staying invisible, inside the change written to stop that happening."""

    def test_a_null_page_publishes_a_document_scoped_gap(self):
        conn = scratch()
        conn.execute("INSERT INTO quality_issues VALUES ('enc','doc-1','v1',NULL,NULL,"
                     "'warning','encrypted_pdf','document is encrypted','2026-01-01')")
        b = SnapshotBuilder(conn, tenant="default", regime="us_astm")
        b.quality_gaps()
        gaps = b.gaps()
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0].subject["kind"], "source_document")
        self.assertEqual(gaps[0].because["code"], "encrypted_pdf")

    def test_a_document_scoped_gap_names_its_document(self):
        conn = scratch()
        conn.execute("INSERT INTO quality_issues VALUES ('enc','doc-1','v1',NULL,NULL,"
                     "'warning','encrypted_pdf','d','2026-01-01')")
        b = SnapshotBuilder(conn, tenant="default", regime="us_astm")
        b.quality_gaps()
        self.assertIn("Big NOA", b.gaps()[0].would_close)


class TestSeverityFollowsWhetherTheDocumentBacksAValue(unittest.TestCase):
    """The first cut made every quality gap `informational`, justified as "a
    page we read badly is attached to no plan line".

    `[measured]`, and the justification was false: 11 of the 13 documents
    carrying `table_not_reconstructed` are the SAME documents backing published
    `ParameterTable` rows, and 68 of 73 such gaps (93%) sit on a document that
    already backs a live plan-facing value. Those pages are siblings, in the
    same authority document, of pages that do warn real lines — which is
    exactly the signal a curator working that NOA's footing schedule wants.
    """

    def test_a_gap_on_a_document_that_backs_a_value_warns_a_line(self):
        conn = scratch()
        issue(conn, "table_not_reconstructed", 17)
        b = SnapshotBuilder(conn, tenant="default", regime="us_astm")
        b.source_ref("el-doc-1")          # something published cites this document
        b.quality_gaps()
        self.assertEqual([g.severity for g in b.gaps()], ["warns_line"])

    def test_a_gap_on_a_document_nothing_cites_is_informational(self):
        conn = scratch()
        issue(conn, "table_not_reconstructed", 17)
        b = SnapshotBuilder(conn, tenant="default", regime="us_astm")
        b.quality_gaps()
        self.assertEqual([g.severity for g in b.gaps()], ["informational"])

    def test_an_info_issue_stays_informational_either_way(self):
        conn = scratch()
        issue(conn, "ocr_supplement_failed", 17, severity="info")
        b = SnapshotBuilder(conn, tenant="default", regime="us_astm")
        b.source_ref("el-doc-1")
        b.quality_gaps()
        self.assertEqual([g.severity for g in b.gaps()], ["informational"])


if __name__ == "__main__":
    unittest.main()
