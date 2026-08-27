"""The render-through crop cache.

The key is the whole point of this module, so most of these tests are about the
key: it must shard, it must move when the toolchain moves (G38), and it must
never be steerable by whatever a caller puts in a `ref_id`. Those need neither
poppler nor a corpus. The render itself is exercised against the real store and
skips cleanly without one.
"""
import shutil
import sqlite3
import unittest

import context  # noqa: F401  -- puts the repo root on sys.path
from context import requires_store
from fence_evidence import refs
from fence_evidence.cropcache import (CROPS_DIR, CropUnavailable, cache_path,
                                      ensure_crop, fingerprint_for,
                                      relative_url)
from fence_evidence.paths import DERIVED_DIR, EVIDENCE_DB, ensure_writable

REF = "eb2c863494b90243"          # "Call before you dig." -- registry §3
FP = "64e1ee02ac41867f"           # this store's only tool_fingerprint


def has_poppler() -> bool:
    return shutil.which("pdftoppm") is not None


class TestCacheKey(unittest.TestCase):
    """Pure: no store, no filesystem, no poppler."""

    def test_shards_on_the_first_two_characters(self):
        p = cache_path(REF, 200, FP)
        self.assertEqual(p.parent, CROPS_DIR / "eb")
        self.assertEqual(p.name, f"{REF}-200-{FP}.png")

    def test_the_toolchain_fingerprint_is_part_of_the_key(self):
        """G38: a re-extraction moves the pixels under an unchanged ref_id.

        A cache keyed on the id alone would keep serving the old crop after a
        poppler upgrade -- the published citation would resolve and show the
        wrong rectangle, which is the one failure mode nobody would notice.
        """
        self.assertNotEqual(cache_path(REF, 200, FP),
                            cache_path(REF, 200, "0" * 16))

    def test_dpi_is_part_of_the_key(self):
        self.assertNotEqual(cache_path(REF, 200, FP), cache_path(REF, 300, FP))

    def test_the_path_is_inside_the_workspace(self):
        """The corpus is read-only; `ensure_writable` refuses anything else."""
        ensure_writable(cache_path(REF, 200, FP))   # raises if it is not

    def test_a_traversing_ref_id_is_refused(self):
        """`ref_id` arrives from Planning and is interpolated into a path.

        Unvalidated, `cache_path` is a write primitive aimed anywhere on the
        filesystem. It refuses rather than sanitising: a malformed id names no
        evidence, so it gets the same answer an unknown one gets.
        """
        for bad in ("../../etc/passwd", "eb/../../x", "EB2C863494B90243",
                    "", "short", "g" * 16, REF + "a"):
            with self.subTest(ref_id=bad), self.assertRaises(CropUnavailable):
                cache_path(bad, 200, FP)

    def test_a_traversing_fingerprint_is_refused(self):
        for bad in ("../x", "", "not-hex", "z" * 16):
            with self.subTest(fingerprint=bad), self.assertRaises(CropUnavailable):
                cache_path(REF, 200, bad)

    def test_an_absurd_or_non_integer_dpi_is_refused(self):
        for bad in (0, -200, 100000, "200", 200.0, True, None):
            with self.subTest(dpi=bad), self.assertRaises(CropUnavailable):
                cache_path(REF, bad, FP)

    def test_the_published_url_is_relative(self):
        """source-refs-design.md §5: crops traverse Planning's backend.

        An absolute path published into an immutable snapshot would bake this
        machine's layout into a record that can never be edited.
        """
        url = relative_url(cache_path(REF, 200, FP))
        self.assertEqual(url, f"crops/eb/{REF}-200-{FP}.png")
        self.assertFalse(url.startswith("/"))
        self.assertNotIn("..", url)


class TestFingerprintWithoutARun(unittest.TestCase):
    def test_a_store_with_no_extraction_run_refuses_rather_than_inventing_one(self):
        """A placeholder would look like a fingerprint and never change --
        exactly the staleness G38 puts this field in the key to prevent."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE document_versions(version_id TEXT, document_id TEXT,
                                           sha256 TEXT, extraction_run_id TEXT);
            CREATE TABLE extraction_runs(run_id TEXT, started_at TEXT,
                                         tool_fingerprint TEXT);
            INSERT INTO document_versions VALUES ('v1', 'd1', 'aa', NULL);
        """)
        with self.assertRaises(CropUnavailable):
            fingerprint_for(conn, "aa")
        conn.close()

    def test_it_falls_back_to_the_newest_run_when_the_version_names_none(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE document_versions(version_id TEXT, document_id TEXT,
                                           sha256 TEXT, extraction_run_id TEXT);
            CREATE TABLE extraction_runs(run_id TEXT, started_at TEXT,
                                         tool_fingerprint TEXT);
            INSERT INTO document_versions VALUES ('v1', 'd1', 'aa', NULL);
            INSERT INTO extraction_runs VALUES ('r1', '2026-01-01', 'aaaaaaaaaaaa');
            INSERT INTO extraction_runs VALUES ('r2', '2026-02-01', 'bbbbbbbbbbbb');
        """)
        self.assertEqual(fingerprint_for(conn, "aa"), "bbbbbbbbbbbb")
        conn.close()


@requires_store
@unittest.skipUnless(has_poppler(), "poppler (pdftoppm) is not installed")
class TestRenderThrough(unittest.TestCase):
    """Against the real store. Writes only into workspace/derived/crops/."""

    @classmethod
    def setUpClass(cls):
        cls.conn = sqlite3.connect(f"file:{EVIDENCE_DB}?mode=ro", uri=True)
        cls.conn.row_factory = sqlite3.Row
        cls.index = refs.build_index(cls.conn)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def a_boxed_pdf_ref(self):
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
        return refs.ref_id(row["sha256"], row["page_no"], row["bbox"])

    def test_a_cold_crop_renders_and_a_second_call_is_a_hit(self):
        rid = self.a_boxed_pdf_ref()
        fp = fingerprint_for(self.conn, refs.resolve(self.index, rid).sha256)
        cache_path(rid, 200, fp).unlink(missing_ok=True)

        cold = ensure_crop(self.conn, rid, index=self.index)
        self.assertFalse(cold["cached"], "a deleted crop reported as cached")
        self.assertTrue(cold["path"].is_file())
        self.assertEqual(cold["dpi"], 200)

        warm = ensure_crop(self.conn, rid, index=self.index)
        self.assertTrue(warm["cached"], "a rendered crop was rendered again")
        self.assertEqual(warm["sha256"], cold["sha256"])
        self.assertEqual(warm["path"], cold["path"])

    def test_the_sha256_is_of_the_png_bytes(self):
        """D6 makes this the one checkable claim in a review -- *this person
        looked at the image we hold* -- so it must hash the served file."""
        import hashlib
        crop = ensure_crop(self.conn, self.a_boxed_pdf_ref(), index=self.index)
        self.assertEqual(
            crop["sha256"],
            hashlib.sha256(crop["path"].read_bytes()).hexdigest())

    def test_what_it_writes_is_a_png(self):
        crop = ensure_crop(self.conn, self.a_boxed_pdf_ref(), index=self.index)
        self.assertEqual(crop["path"].read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_it_writes_only_under_the_derived_directory(self):
        crop = ensure_crop(self.conn, self.a_boxed_pdf_ref(), index=self.index)
        self.assertIn(DERIVED_DIR.resolve(), crop["path"].resolve().parents)

    def test_it_leaves_no_temporary_file_behind(self):
        rid = self.a_boxed_pdf_ref()
        fp = fingerprint_for(self.conn, refs.resolve(self.index, rid).sha256)
        path = cache_path(rid, 200, fp)
        path.unlink(missing_ok=True)
        ensure_crop(self.conn, rid, index=self.index)
        leftovers = [p.name for p in path.parent.glob(".*")]
        self.assertEqual(leftovers, [], f"render left scratch files: {leftovers}")

    def test_a_different_dpi_is_a_different_file(self):
        rid = self.a_boxed_pdf_ref()
        self.assertNotEqual(ensure_crop(self.conn, rid, dpi=200, index=self.index)["path"],
                            ensure_crop(self.conn, rid, dpi=150, index=self.index)["path"])

    def test_an_unknown_ref_is_unavailable(self):
        with self.assertRaises(CropUnavailable):
            ensure_crop(self.conn, "f" * 16, index=self.index)

    def test_a_page_ref_has_no_rectangle_and_is_unavailable(self):
        """`ref_id` omits `kind`, so a page ref is a real, resolvable id with
        no bbox. Cropping the whole page would answer a different question."""
        row = self.conn.execute(
            """SELECT p.page_no, v.sha256 FROM pages p
                 JOIN document_versions v ON v.version_id = p.version_id
                ORDER BY p.page_id LIMIT 1""").fetchone()
        rid = refs.ref_id(row["sha256"], row["page_no"], None)
        locus = refs.resolve(self.index, rid)
        if locus is None or locus.bbox is not None:
            self.skipTest("no bbox-less page ref in this store")
        with self.assertRaises(CropUnavailable):
            ensure_crop(self.conn, rid, index=self.index)

    def test_a_source_poppler_cannot_read_is_unavailable(self):
        """The six CAD PNGs and the DOCX. crops.py §4.2 will not take a Pillow
        dependency to cover them, so they have no crop -- said out loud."""
        row = self.conn.execute(
            """SELECT e.bbox, e.page_no, v.sha256
                 FROM elements e
                 JOIN document_versions v ON v.version_id = e.version_id
                 JOIN documents d ON d.document_id = e.document_id
                WHERE d.file_type <> 'pdf' AND e.bbox IS NOT NULL
                ORDER BY e.element_id LIMIT 1""").fetchone()
        if row is None:
            self.skipTest("this store holds only PDFs")
        rid = refs.ref_id(row["sha256"], row["page_no"], row["bbox"])
        with self.assertRaises(CropUnavailable):
            ensure_crop(self.conn, rid, index=self.index)


if __name__ == "__main__":
    unittest.main()
