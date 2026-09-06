"""G75 — a published date comes from evidence, and amendment 002 still holds.

`_register_doc` copied `documents.issue_date`/`expiration_date` verbatim from
whichever filing a citation reached first. Those curated columns are blank for
most documents and, for one NOA with four byte-identical filings, disagree —
two rows filled, two blank — and the blank one won. Meanwhile `versions.py`
already resolves both dates from the 84 `effective_date` and 75
`expiration_date` facts Phase 6 extracted, and nothing called it.

The trap, and the reason this file exists: `versions.parse_date()` and
`dates.normalize_date()` are two independent parsers that DISAGREE.
`normalize_date` implements amendment 002 — when both day and month are ≤ 12
and unequal, refuse to guess — and `versions.parse_date` guesses
unconditionally. Wiring the resolver in naively would have overridden a
ratified amendment's refusal with a confident guess on four documents,
including NOA 23-0314.05, whose `Approval Date: 05/04/2023` is published as
`iso: null` today and must stay that way.
"""
import sqlite3
import unittest

from context import ROOT, requires_full_store  # noqa: F401
from fence_evidence.snapshot import SnapshotBuilder


def scratch(with_facts=True) -> sqlite3.Connection:
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
        CREATE TABLE facts (fact_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            document_id TEXT, version_id TEXT, page_no INTEGER,
                            element_id TEXT, fact_type TEXT, subject TEXT,
                            value_original TEXT, value_normalized TEXT,
                            unit_original TEXT, unit_normalized TEXT,
                            conditions TEXT, evidence_text TEXT, extractor TEXT,
                            ocr_derived INTEGER, review_status TEXT,
                            created_at TEXT, condition_basis TEXT,
                            condition_basis_note TEXT, value_alternates TEXT,
                            from_candidate_id INTEGER, reviewed_value TEXT,
                            reviewed_value_normalized TEXT, reviewer TEXT,
                            reviewed_at TEXT);
    """)
    # Two byte-identical filings whose curated columns DISAGREE: the defect.
    conn.execute("INSERT INTO documents VALUES ('doc-blank','hvhz_noa','NOA','unknown',"
                 "'no explicit version marker in curated metadata',NULL,NULL,NULL,"
                 "'a.pdf','M')")
    conn.execute("INSERT INTO documents VALUES ('doc-filled','hvhz_noa','NOA','unknown',"
                 "'no explicit version marker in curated metadata','04/24/2025',"
                 "'03/13/2029',NULL,'b.pdf','M2')")
    for doc in ("doc-blank", "doc-filled"):
        conn.execute("INSERT INTO document_versions VALUES (?,?,'abc123')",
                     (f"v-{doc}", doc))
        conn.execute("INSERT INTO pages VALUES (?,1,'p.png',612.0,792.0,200)",
                     (f"v-{doc}",))
        conn.execute("INSERT INTO elements VALUES (?,?,?,1,0,'paragraph','NOA',NULL,"
                     "'[1,2,3,4]')", (f"el-{doc}", doc, f"v-{doc}"))
        if with_facts:
            for ftype, raw in (("effective_date", "04/24/2025"),
                               ("expiration_date", "03/13/2029")):
                conn.execute(
                    "INSERT INTO facts(document_id, version_id, page_no, element_id,"
                    " fact_type, value_original, value_normalized, conditions,"
                    " evidence_text, extractor, ocr_derived, review_status, created_at,"
                    " condition_basis) VALUES (?,?,?,?,?,?,?,'{}','e','regex-v1',0,"
                    "'extracted','2026-01-01','unexamined')",
                    (doc, f"v-{doc}", 1, f"el-{doc}", ftype, raw, raw))
    return conn


def published(conn, document_id="doc-blank"):
    b = SnapshotBuilder(conn, tenant="default", regime="us_astm")
    b.source_ref(f"el-{document_id}")
    return b.source_docs()[0]


class TestDatesComeFromEvidence(unittest.TestCase):
    def test_a_blank_curated_column_is_filled_from_facts(self):
        doc = published(scratch(), "doc-blank")
        self.assertEqual(doc.expiration_date["iso"], "2029-03-13")
        self.assertEqual(doc.issue_date["iso"], "2025-04-24")

    def test_either_filing_gives_the_same_answer(self):
        """The order-dependence disappears because the resolver reads `facts`,
        which Phase 6 extracted independently for every filing, rather than the
        curated columns that disagree."""
        conn = scratch()
        blank = published(conn, "doc-blank")
        filled = published(scratch(), "doc-filled")
        self.assertEqual(blank.issue_date, filled.issue_date)
        self.assertEqual(blank.expiration_date, filled.expiration_date)

    def test_no_facts_falls_back_to_the_curated_column(self):
        doc = published(scratch(with_facts=False), "doc-filled")
        self.assertEqual(doc.expiration_date["iso"], "2029-03-13")

    def test_nothing_anywhere_publishes_no_date(self):
        doc = published(scratch(with_facts=False), "doc-blank")
        self.assertIsNone(doc.issue_date)


class TestAmendment002SurvivesTheWiring(unittest.TestCase):
    """The whole reason this fix needed measuring before it was written."""

    def test_an_ambiguous_date_is_still_refused(self):
        """`05/04/2023` — both tokens ≤ 12 and unequal. `versions.parse_date`
        resolves it to 2023-05-04 unconditionally; `dates.normalize_date`
        refuses, per amendment 002. The published value must be the refusal."""
        conn = scratch()
        conn.execute("UPDATE facts SET value_original='05/04/2023',"
                     " value_normalized='05/04/2023' WHERE fact_type='effective_date'")
        doc = published(conn, "doc-blank")
        self.assertIsNotNone(doc.issue_date, "the raw text must still be carried")
        self.assertIsNone(doc.issue_date["iso"],
                          "amendment 002 refuses to guess MM/DD vs DD/MM")
        self.assertIn("05/04/2023", doc.issue_date["value_raw"])

    def test_an_unambiguous_date_is_still_resolved(self):
        """The refusal must not swallow dates that are not ambiguous: 13 > 12,
        so `03/13/2029` has only one reading."""
        doc = published(scratch(), "doc-blank")
        self.assertEqual(doc.expiration_date["iso"], "2029-03-13")


class TestTheBasisStopsDenyingWhatWeHold(unittest.TestCase):
    def test_the_basis_names_the_evidence_when_there_is_some(self):
        """`version_status_basis` said 'no explicit version marker in curated
        metadata' for a document whose dates we had extracted from its own
        pages. That sentence was true about the curated column and false about
        the platform's knowledge."""
        doc = published(scratch(), "doc-blank")
        # The original clause is kept, not deleted: it is true ABOUT THE
        # CURATED COLUMN and stays specific about which thing was empty. What
        # it may not do is stand alone, implying the platform knows nothing.
        self.assertIn("no explicit version marker", doc.version_status_basis)
        self.assertIn("2029-03-13", doc.version_status_basis)
        self.assertIn("read from the document", doc.version_status_basis)

    def test_the_basis_is_untouched_when_there_is_no_evidence(self):
        doc = published(scratch(with_facts=False), "doc-blank")
        self.assertIn("no explicit version marker", doc.version_status_basis)

    def test_version_status_itself_does_not_move(self):
        """`select_active` reports `inferred_in_force`, which is NOT the same
        claim as a document marking itself active. The enum stays
        active|superseded|unknown and this fix does not promote anything into
        it; the dates let a consumer judge."""
        doc = published(scratch(), "doc-blank")
        self.assertEqual(doc.version_status, "unknown")


class TestG89OneResolverForBothMembers(unittest.TestCase):
    """G75's fix reached `SourceDoc` and stopped there.

    `parameters.py` kept reading the raw `documents` column, so a published
    rule and the `SourceDoc` its `authority` names carried DIFFERENT dates --
    17 of 31 rows published no expiry beside a document that had one, and two
    of those documents had lapsed. Obligation 16's check reads `valid_until`,
    so it compared against a null and found nothing wrong.
    """

    def test_evidence_beats_a_blank_column_for_a_rule_too(self):
        from fence_evidence.versions import resolved_document_dates
        conn = scratch()
        # doc-blank's curated columns are NULL; its facts carry both dates.
        issue, expiry, note = resolved_document_dates(conn, "doc-blank", None, None)
        self.assertEqual(expiry["iso"], "2029-03-13")
        self.assertEqual(issue["iso"], "2025-04-24")
        self.assertIn("expiration", note)

    def test_the_column_is_still_the_fallback_when_no_evidence_exists(self):
        from fence_evidence.versions import resolved_document_dates
        conn = scratch(with_facts=False)
        _, expiry, note = resolved_document_dates(
            conn, "doc-filled", "04/24/2025", "03/13/2029")
        self.assertEqual(expiry["iso"], "2029-03-13")
        self.assertEqual(note, "")  # nothing was resolved FROM evidence

    def test_amendment_002_still_refuses_through_this_path(self):
        from fence_evidence.versions import resolved_document_dates
        conn = scratch(with_facts=False)
        _, expiry, _ = resolved_document_dates(
            conn, "doc-filled", None, "05/04/2023")
        self.assertIsNone(expiry["iso"])
        self.assertEqual(expiry["value_raw"], ["05/04/2023"])

@requires_full_store
class TestG89TheInvariantOnTheRealSnapshot(unittest.TestCase):
    """The claim `parameters.py` makes in a comment -- that the `SourceDoc` its
    `authority` names "carries the same dates" -- asserted against a real cut.

    Deliberately NOT a source-text assertion: checking that both modules
    mention one function name would pass against two functions that disagree.
    This compares the published values.
    """

    @classmethod
    def setUpClass(cls):
        from fence_evidence.snapshot import build_snapshot
        cls.snap = build_snapshot(tenant="default")
        cls.docs = {d["content_hash"]: d for d in cls.snap["source_docs"]}

    def test_every_rule_agrees_with_the_document_it_names(self):
        for table in self.snap["parameters"]:
            for row in table["rows"]:
                doc = self.docs.get(row["authority"], {})
                for field, published in (("expiration_date", "valid_until"),
                                         ("issue_date", "valid_from")):
                    self.assertEqual(
                        (row.get(published) or {}).get("iso"),
                        (doc.get(field) or {}).get("iso"),
                        f"{table['parameter']} row disagrees with its "
                        f"SourceDoc on {field}")

    def test_a_lapsed_authority_is_visible_on_the_rule_not_only_the_document(self):
        """Obligation 16 reads `valid_until`. While that was null on a rule
        backed by a lapsed approval, the check compared against nothing."""
        lapsed = [t["parameter"] for t in self.snap["parameters"] for r in t["rows"]
                  if (r.get("valid_until") or {}).get("iso", "9999") < "2026-09-06"]
        self.assertTrue(lapsed, "no rule reports a lapsed authority; if the "
                                "corpus really has none, this guard is stale")


if __name__ == "__main__":
    unittest.main()
