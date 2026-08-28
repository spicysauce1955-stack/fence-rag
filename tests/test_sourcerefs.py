"""The Discovery read model behind `GET /source-refs/{id}`.

Almost everything here runs against a store built from `store.SCHEMA` in
memory, so it needs neither the corpus nor poppler and cannot damage either.
The handful of assertions that are really about *this* corpus are marked
`@requires_store` and skip cleanly without one.
"""
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

import context  # noqa: F401  -- puts the repo root on sys.path
from context import requires_store
from fence_evidence import refs, sourcerefs
from fence_evidence.cropcache import CropUnavailable
from fence_evidence.paths import EVIDENCE_DB, REPO_ROOT, TESTS_DIR, open_write
from fence_evidence import sourcerefs
from fence_evidence.sourcerefs import (SOURCE_CODES, source_ref,
                                       source_refs_batch)
from fence_evidence.store import SCHEMA

SHA = "a" * 64
BBOX = "[10.0, 20.0, 110.0, 40.0]"
PAGE = 3
RUN_FP = "abcdef0123456789"

# Deliberately a path that is not on disk: the default fixture exercises the
# "resolves, cannot be pictured" branch, which is the interesting one and the
# only one reachable without poppler.
MISSING_PDF = "manuals/nope/missing.pdf"


def make_store(*, source_path=MISSING_PDF, file_type="pdf",
               version_status="unknown",
               basis="no explicit version marker in curated metadata",
               text="Call before you dig.", text_source="pdf_text_layer",
               ocr_confidence=None) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute("""INSERT INTO extraction_runs(run_id, started_at, tool_versions,
                        tool_fingerprint, pipeline_version)
                    VALUES ('r1', '2026-08-20T00:00:00+00:00', '{}', ?, '1')""",
                 (RUN_FP,))
    conn.execute("""INSERT INTO documents(document_id, source_path, file_type,
                        corpus_track, manufacturer, doc_type, version_status,
                        version_status_basis)
                    VALUES ('doc-1', ?, ?, 'us', 'Acme', 'install_guide', ?, ?)""",
                 (source_path, file_type, version_status, basis))
    conn.execute("""INSERT INTO document_versions(version_id, document_id, sha256,
                        ingested_at, extraction_run_id)
                    VALUES ('v1', 'doc-1', ?, '2026-08-20T00:00:00+00:00', 'r1')""",
                 (SHA,))
    conn.execute("""INSERT INTO pages(page_id, version_id, page_no, width, height,
                        extraction_method, page_image_dpi, ocr_mean_confidence)
                    VALUES ('p1', 'v1', ?, 612, 792, 'pdf_text_layer', 200, 58.25)""",
                 (PAGE,))
    add_element(conn, "e1", text=text, text_source=text_source,
                ocr_confidence=ocr_confidence)
    conn.commit()
    return conn


def add_element(conn, element_id, *, text="", text_source="pdf_text_layer",
                ocr_confidence=None, bbox=BBOX, document_id="doc-1",
                version_id="v1", page_id="p1"):
    conn.execute("""INSERT INTO elements(element_id, page_id, version_id,
                        document_id, page_no, ordinal, element_type, text,
                        text_source, ocr_confidence, bbox)
                    VALUES (?,?,?,?,?,0,'paragraph',?,?,?,?)""",
                 (element_id, page_id, version_id, document_id, PAGE, text,
                  text_source, ocr_confidence, bbox))
    conn.commit()


def codes(ref: dict) -> list[str]:
    return [w["code"] for w in ref["warnings"]]


def params(ref: dict, code: str) -> dict:
    return next(w["params"] for w in ref["warnings"] if w["code"] == code)


REF = refs.ref_id(SHA, PAGE, BBOX)


class TestWireShape(unittest.TestCase):
    """§5.1 is the one part of the design Planning builds against."""

    def setUp(self):
        self.conn = make_store()

    def tearDown(self):
        self.conn.close()

    def test_the_response_has_exactly_the_five_declared_keys(self):
        self.assertEqual(set(source_ref(self.conn, REF)),
                         {"id", "belongs_to", "page_no", "text", "image", "warnings"})

    def test_belongs_to_is_the_content_hash_not_a_document_id(self):
        """A ref names bytes. 14 groups of byte-identical files are filed
        under different manufacturers, so "which document" has no answer."""
        got = source_ref(self.conn, REF)
        self.assertEqual(got["belongs_to"], SHA)
        self.assertEqual(got["id"], REF)
        self.assertEqual(got["page_no"], PAGE)

    def test_text_is_the_element_text_when_the_ref_names_one_element(self):
        self.assertEqual(source_ref(self.conn, REF)["text"], "Call before you dig.")

    def test_text_is_null_when_the_ref_names_more_than_one_element(self):
        """`ref_id` omits `kind` and is not injective -- 9,929 ids cover more
        than one element. Picking one would attribute the wrong quote to a
        citation; concatenating would invent a sentence that appears nowhere."""
        add_element(self.conn, "e2", text="Some other paragraph.")
        self.assertIsNone(source_ref(self.conn, REF)["text"])

    def test_an_unknown_ref_is_the_only_hard_failure(self):
        """It maps to 404 `error.unknown_ref`. `refs.resolve` says None must
        never be read as an empty result -- obligation 3 depends on it."""
        with self.assertRaises(CropUnavailable):
            source_ref(self.conn, "f" * 16)

    def test_every_code_it_emits_is_in_the_registry(self):
        self.assertTrue(set(codes(source_ref(self.conn, REF))) <= SOURCE_CODES)

    def test_warnings_are_sorted_so_two_builds_agree(self):
        got = codes(source_ref(self.conn, REF))
        self.assertEqual(got, sorted(got))


class TestUnrenderableCrops(unittest.TestCase):
    """A ref that resolves but cannot be pictured is still a ref.

    A 404 here would contradict what obligation 3 promises about a published
    citation, and would leave a reviewer with neither the text nor a reason.
    """

    def test_a_missing_source_file_returns_a_ref_with_no_image(self):
        conn = make_store()
        got = source_ref(conn, REF)
        self.assertIsNone(got["image"])
        self.assertEqual(got["text"], "Call before you dig.")
        self.assertIn(sourcerefs.SOURCE_NOT_FETCHED, codes(got))
        conn.close()

    def test_an_unfetched_checkout_says_which_subset_would_fix_it(self):
        """The failure is one `cli fetch` away and is neither the platform's
        fault nor the document's. Reporting it as "no image available" would
        tell a curator the evidence does not exist when it does."""
        conn = make_store()
        self.assertEqual(params(source_ref(conn, REF),
                                sourcerefs.SOURCE_NOT_FETCHED)["subset"], "all")
        conn.close()

        conn = make_store(source_path="china/manuals/showtech/nope.pdf")
        self.assertEqual(params(source_ref(conn, REF),
                                sourcerefs.SOURCE_NOT_FETCHED)["subset"], "china")
        conn.close()

    def test_a_source_poppler_cannot_read_says_no_image_available(self):
        """The six CAD PNGs and the DOCX: the file is there, poppler cannot
        open it, and crops.py §4.2 will not take a Pillow dependency for it."""
        tmp = Path(tempfile.mkdtemp(prefix="srcrefs-", dir=TESTS_DIR))
        try:
            fixture = tmp / "not-a-pdf.png"
            with open_write(fixture, "wb") as fh:
                fh.write(b"\x89PNG\r\n\x1a\n")
            rel = fixture.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
            conn = make_store(source_path=rel, file_type="png")
            got = source_ref(conn, REF)
            self.assertIsNone(got["image"])
            self.assertIn(sourcerefs.SOURCE_NO_IMAGE_AVAILABLE, codes(got))
            self.assertIn("reason",
                          params(got, sourcerefs.SOURCE_NO_IMAGE_AVAILABLE))
            conn.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_a_page_ref_has_no_rectangle_and_so_no_image(self):
        conn = make_store()
        conn.execute("UPDATE elements SET bbox = NULL WHERE element_id = 'e1'")
        conn.commit()
        page_ref = refs.ref_id(SHA, PAGE, None)
        got = source_ref(conn, page_ref)
        self.assertIsNone(got["image"])
        self.assertIn(sourcerefs.SOURCE_NO_IMAGE_AVAILABLE, codes(got))
        conn.close()


class TestWarnings(unittest.TestCase):
    """registry-additions.md §2, including the three counts §2.1 corrected."""

    def test_ocr_text_carries_its_confidence(self):
        conn = make_store(text="", text_source="ocr", ocr_confidence=93.75)
        conn.execute("UPDATE elements SET ocr_text = 'read by machine'")
        conn.commit()
        got = source_ref(conn, REF)
        self.assertIn(sourcerefs.SOURCE_TEXT_FROM_OCR, codes(got))
        self.assertEqual(params(got, sourcerefs.SOURCE_TEXT_FROM_OCR),
                         {"confidence": 93.8})
        self.assertEqual(got["text"], "read by machine",
                         "ocr_text fills in only where the source layer is empty")
        conn.close()

    def test_a_non_injective_ref_publishes_the_weakest_reading_it_covers(self):
        conn = make_store(text="", text_source="ocr", ocr_confidence=93.75)
        add_element(conn, "e2", text="", text_source="ocr", ocr_confidence=41.0)
        got = source_ref(conn, REF)
        self.assertEqual(params(got, sourcerefs.SOURCE_TEXT_FROM_OCR),
                         {"confidence": 41.0})
        conn.close()

    def test_a_text_layer_element_does_not_claim_to_be_ocr(self):
        conn = make_store()
        self.assertNotIn(sourcerefs.SOURCE_TEXT_FROM_OCR, codes(source_ref(conn, REF)))
        conn.close()

    def test_superseded_fires_on_the_status_not_on_the_edge(self):
        """registry §2.1: 9 documents are `superseded`, only 6 have a
        successor. Suppressing the warning where the param is empty would
        hide exactly the weakest three."""
        conn = make_store(version_status="superseded",
                          basis="keyword in title/filename")
        got = source_ref(conn, REF)
        self.assertIn(sourcerefs.SOURCE_DOCUMENT_SUPERSEDED, codes(got))
        self.assertEqual(params(got, sourcerefs.SOURCE_DOCUMENT_SUPERSEDED),
                         {"superseded_by": []})
        self.assertIn(sourcerefs.SOURCE_STATUS_BASIS_FILENAME, codes(got))
        conn.close()

    def test_superseded_by_is_a_list_and_can_name_several(self):
        """doc-8727ba0fd4d4 fans out to seven successors, which is why the
        param was corrected from a scalar to a list in T1."""
        conn = make_store(version_status="superseded")
        for i, sha in enumerate(("b" * 64, "c" * 64)):
            conn.execute("""INSERT INTO documents(document_id, source_path,
                                file_type, corpus_track)
                            VALUES (?,?,'pdf','us')""",
                         (f"doc-{i+2}", f"manuals/x/{i}.pdf"))
            conn.execute("""INSERT INTO document_versions(version_id, document_id,
                                sha256, ingested_at)
                            VALUES (?,?,?,'2026-08-20T00:00:00+00:00')""",
                         (f"v{i+2}", f"doc-{i+2}", sha))
            # subject -> object: the FROM side is the superseded document.
            # Marking the wrong side once labelled every current NOA superseded.
            conn.execute("""INSERT INTO relations(from_document_id, to_document_id,
                                relation_type) VALUES ('doc-1',?, 'superseded_by')""",
                         (f"doc-{i+2}",))
        conn.commit()
        self.assertEqual(
            params(source_ref(conn, REF),
                   sourcerefs.SOURCE_DOCUMENT_SUPERSEDED)["superseded_by"],
            ["b" * 64, "c" * 64])
        conn.close()

    def test_an_unknown_version_status_is_declared(self):
        conn = make_store()
        self.assertIn(sourcerefs.SOURCE_VERSION_STATUS_UNKNOWN,
                      codes(source_ref(conn, REF)))
        conn.close()

    def test_an_active_document_carries_neither_status_warning(self):
        conn = make_store(version_status="active")
        got = codes(source_ref(conn, REF))
        self.assertNotIn(sourcerefs.SOURCE_VERSION_STATUS_UNKNOWN, got)
        self.assertNotIn(sourcerefs.SOURCE_DOCUMENT_SUPERSEDED, got)
        conn.close()

    def test_a_page_whose_table_was_not_reconstructed_says_so(self):
        """~50% OCR confidence at every dpi tried: the page image *is* the
        evidence, and a curator has to be told that."""
        conn = make_store()
        conn.execute("""INSERT INTO quality_issues(document_id, page_no, severity,
                            kind, detected_at)
                        VALUES ('doc-1', ?, 'warning', 'table_not_reconstructed',
                                '2026-08-20T00:00:00+00:00')""", (PAGE,))
        conn.commit()
        self.assertIn(sourcerefs.SOURCE_TABLE_NOT_RECONSTRUCTED,
                      codes(source_ref(conn, REF)))
        conn.close()

    def test_low_page_confidence_comes_from_the_issue_the_extractor_recorded(self):
        """Never by re-applying a literal threshold here: a second copy of
        `< 70` would be a second definition of "low", free to drift."""
        conn = make_store()
        self.assertNotIn(sourcerefs.SOURCE_OCR_LOW_CONFIDENCE,
                         codes(source_ref(conn, REF)),
                         "58.25 is below any threshold, but no issue was recorded")
        conn.execute("""INSERT INTO quality_issues(document_id, page_no, severity,
                            kind, detected_at)
                        VALUES ('doc-1', ?, 'warning', 'low_ocr_confidence',
                                '2026-08-20T00:00:00+00:00')""", (PAGE,))
        conn.commit()
        got = source_ref(conn, REF)
        self.assertEqual(params(got, sourcerefs.SOURCE_OCR_LOW_CONFIDENCE),
                         {"confidence": 58.2})
        conn.close()

    def test_mojibake_reports_how_many_pages_it_hit(self):
        conn = make_store()
        for page in (1, 2, 3):
            conn.execute("""INSERT INTO quality_issues(document_id, page_no,
                                severity, kind, detected_at)
                            VALUES ('doc-1', ?, 'warning', 'mojibake_text_layer',
                                    '2026-08-20T00:00:00+00:00')""", (page,))
        conn.commit()
        self.assertEqual(params(source_ref(conn, REF),
                                sourcerefs.SOURCE_TEXT_LAYER_MOJIBAKE),
                         {"pages_affected": 3})
        conn.close()

    def test_a_second_filing_of_the_same_bytes_is_named(self):
        """registry §5: the class is a property of the bytes, the filing is a
        property of the catalogue. 14 such groups here, never deduplicated."""
        conn = make_store()
        conn.execute("""INSERT INTO documents(document_id, source_path, file_type,
                            corpus_track, manufacturer, doc_type)
                        VALUES ('doc-2', 'manuals/other/same.pdf', 'pdf', 'us',
                                'Beta', 'hvhz_noa')""")
        conn.execute("""INSERT INTO document_versions(version_id, document_id,
                            sha256, ingested_at)
                        VALUES ('v2', 'doc-2', ?, '2026-08-20T00:00:00+00:00')""",
                     (SHA,))
        conn.execute("""INSERT INTO relations(from_document_id, to_document_id,
                            relation_type)
                        VALUES ('doc-1', 'doc-2', 'same_content_as')""")
        conn.execute("""INSERT INTO relations(from_document_id, to_document_id,
                            relation_type)
                        VALUES ('doc-2', 'doc-1', 'same_content_as')""")
        conn.commit()
        got = source_ref(conn, REF)
        self.assertEqual(params(got, sourcerefs.SOURCE_CONTENT_DUPLICATED),
                         {"also_filed_under": [{"manufacturer": "Beta",
                                                "doc_type": "hvhz_noa"}]})
        conn.close()

    def test_a_singly_filed_document_carries_no_duplication_warning(self):
        conn = make_store()
        self.assertNotIn(sourcerefs.SOURCE_CONTENT_DUPLICATED,
                         codes(source_ref(conn, REF)))
        conn.close()


class TestBatch(unittest.TestCase):
    def test_over_the_cap_raises_before_touching_the_store(self):
        """413 `error.batch_too_large`. A request-shape error the caller can
        fix by asking for less, so it is loud -- and `conn` is never used,
        which is what passing None proves."""
        with self.assertRaises(ValueError):
            source_refs_batch(None, ["a" * 16] * 51)

    def test_exactly_the_cap_is_accepted(self):
        conn = make_store()
        got = source_refs_batch(conn, [REF] * 50, deadline_s=60.0)
        self.assertEqual(len(got["refs"]), 50)
        self.assertFalse(got["deadline_exceeded"])
        conn.close()

    def test_the_deadline_returns_partial_results_and_never_raises(self):
        """§7: a reviewer seeing nothing is the worse failure. K3 §1 measures
        the render distribution as bimodal -- one p99 element must not cost
        the other 49 their crops."""
        conn = make_store()
        got = source_refs_batch(conn, [REF, REF, REF], deadline_s=0.0)
        self.assertTrue(got["deadline_exceeded"])
        self.assertEqual(got["refs"], [])
        self.assertEqual(got["not_rendered"], [REF, REF, REF])
        conn.close()

    def test_an_unrenderable_crop_is_a_ref_not_a_deadline_drop(self):
        """Planning retries `not_rendered`; an unrenderable crop is not
        retryable, so it must not land there."""
        conn = make_store()
        got = source_refs_batch(conn, [REF])
        self.assertEqual(got["not_rendered"], [])
        self.assertFalse(got["deadline_exceeded"])
        self.assertEqual(len(got["refs"]), 1)
        self.assertIsNone(got["refs"][0]["image"])
        self.assertEqual(got["refs"][0]["text"], "Call before you dig.")
        conn.close()

    def test_one_unknown_id_does_not_cost_the_others_their_answer(self):
        conn = make_store()
        got = source_refs_batch(conn, [REF, "f" * 16])
        self.assertEqual([r["id"] for r in got["refs"]], [REF])
        # `unknown`, not `not_rendered`: the two ask the caller for opposite
        # things. A deadline drop is retryable; a bad id is not, and a
        # response-level `deadline_exceeded` cannot separate them in a batch
        # that carries both.
        self.assertEqual(got["unknown"], ["f" * 16])
        self.assertEqual(got["not_rendered"], [])
        self.assertFalse(got["deadline_exceeded"],
                         "an unknown id is not a timeout and must not look like one")
        conn.close()

    def test_a_deadline_drop_and_a_bad_id_are_told_apart(self):
        """The reason the fourth key exists: a batch can carry both at once.

        The clock is driven rather than raced: the deadline is checked before
        each id, so the first reading lets the bad id through and the second
        puts the good one over. A real elapsed time here would be a flaky test.
        """
        import unittest.mock as _mock
        conn = make_store()
        with _mock.patch.object(sourcerefs.time, "monotonic",
                                side_effect=[0.0, 0.0, 100.0]):
            got = source_refs_batch(conn, ["f" * 16, REF], deadline_s=10.0)
        self.assertEqual(got["unknown"], ["f" * 16], "a bad id is not a timeout")
        self.assertEqual(got["not_rendered"], [REF], "a timeout is not a bad id")
        self.assertTrue(got["deadline_exceeded"])
        conn.close()

    def test_the_answer_lines_up_with_the_request(self):
        conn = make_store()
        got = source_refs_batch(conn, [REF, REF])
        self.assertEqual([r["id"] for r in got["refs"]], [REF, REF])
        conn.close()


@requires_store
class TestAgainstTheRealCorpus(unittest.TestCase):
    """The assertions that are about *this* corpus, not about the shape."""

    @classmethod
    def setUpClass(cls):
        cls.conn = sqlite3.connect(f"file:{EVIDENCE_DB}?mode=ro", uri=True)
        cls.conn.row_factory = sqlite3.Row
        cls.index = refs.build_index(cls.conn)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_the_registry_exemplar_still_reads_as_published(self):
        """registry §3 publishes `eb2c863494b90243` as "Call before you dig."
        If this ever fails, a published citation has moved -- G38."""
        if refs.resolve(self.index, "eb2c863494b90243") is None:
            self.skipTest("the exemplar's document is not in this store")
        got = source_ref(self.conn, "eb2c863494b90243", index=self.index)
        self.assertEqual(got["text"], "Call before you dig.")
        self.assertEqual(len(got["belongs_to"]), 64)
        self.assertTrue(set(codes(got)) <= SOURCE_CODES)

    def test_a_served_image_url_is_relative_and_hashes_to_the_file(self):
        if not shutil.which("pdftoppm"):
            self.skipTest("poppler (pdftoppm) is not installed")
        row = self.conn.execute(
            """SELECT e.bbox, e.page_no, v.sha256
                 FROM elements e
                 JOIN document_versions v ON v.version_id = e.version_id
                 JOIN documents d ON d.document_id = e.document_id
                 JOIN pages p ON p.page_id = e.page_id
                WHERE e.bbox IS NOT NULL AND d.file_type = 'pdf'
                  AND p.page_image_dpi IS NOT NULL
                ORDER BY e.element_id LIMIT 1""").fetchone()
        if row is None:
            self.skipTest("no boxed element on a PDF page in this store")
        rid = refs.ref_id(row["sha256"], row["page_no"], row["bbox"])
        got = source_ref(self.conn, rid, index=self.index)
        if got["image"] is None:
            self.skipTest(f"no crop available: {codes(got)}")
        import hashlib

        from fence_evidence.paths import DERIVED_DIR
        url = got["image"]["url"]
        self.assertTrue(url.startswith("crops/"), url)
        self.assertFalse(url.startswith("/"))
        on_disk = DERIVED_DIR / url
        self.assertEqual(got["image"]["sha256"],
                         hashlib.sha256(on_disk.read_bytes()).hexdigest())
        self.assertEqual(got["image"]["dpi"], 200)


if __name__ == "__main__":
    unittest.main()
