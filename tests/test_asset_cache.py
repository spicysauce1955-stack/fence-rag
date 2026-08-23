"""resolve_asset materialises derived images on demand."""
import hashlib
import os
import unittest
from pathlib import Path

from context import ROOT, requires_store  # noqa: F401
from fence_evidence.paths import resolve_asset, REPO_ROOT


class _evicted:
    """Atomically move ``path`` aside for the duration of a test, then
    restore it.

    Both the eviction and the restoration are a single `os.replace` — an
    atomic rename on the same filesystem — rather than a copy-then-delete
    into a scratch tempdir. That means there is never a window where the
    real page image is simply gone with no recovery path: at every instant
    either the original path or the backup path holds the content, and a
    crash between the two `os.replace` calls (e.g. the test body raising)
    still leaves the backup file sitting next to the original, recoverable
    by hand, rather than losing a real page image out of the 4.5 GB store.
    """

    def __init__(self, path: Path):
        self.path = path
        self.backup = path.with_name(path.name + ".bak-test-asset-cache")

    def __enter__(self) -> str:
        original = self.path.read_bytes()
        os.replace(self.path, self.backup)
        return hashlib.sha256(original).hexdigest()

    def __exit__(self, exc_type, exc, tb):
        if self.backup.is_file():
            os.replace(self.backup, self.path)
        return False


class TestResolveAsset(unittest.TestCase):
    def test_none_input_returns_none(self):
        self.assertIsNone(resolve_asset(None))

    def test_existing_file_is_returned_unchanged(self):
        existing = "workspace/catalog/corpus-manifest.jsonl"
        if not (REPO_ROOT / existing).is_file():
            self.skipTest("manifest not built")
        self.assertEqual(resolve_asset(existing), (REPO_ROOT / existing).resolve())

    def test_unresolvable_asset_returns_none_rather_than_raising(self):
        self.assertIsNone(resolve_asset("workspace/derived/doc-nope/pages/9999.png"))

    @requires_store
    def test_rerender_reproduces_the_stored_page_image_bytes(self):
        """D5: an on-demand render matches what ingest wrote (PDF sources)."""
        import sqlite3
        from fence_evidence.paths import EVIDENCE_DB
        conn = sqlite3.connect(f"file:{EVIDENCE_DB}?mode=ro", uri=True)
        rows = conn.execute(
            "SELECT page_image_path FROM pages WHERE page_image_path IS NOT NULL LIMIT 20"
        ).fetchall()
        conn.close()
        checked = 0
        for (rel,) in rows:
            src = REPO_ROOT / rel
            if not src.is_file():
                continue
            with _evicted(src) as original:
                produced = resolve_asset(rel)
                if produced is None:
                    self.skipTest("source PDF absent; cannot re-render")
                self.assertEqual(hashlib.sha256(produced.read_bytes()).hexdigest(), original)
            checked += 1
            if checked >= 3:
                break
        if checked == 0:
            self.skipTest("no page images available to re-render")

    @requires_store
    def test_rerender_reproduces_a_cad_page_image_from_its_png_source(self):
        """A page whose corpus source is itself a PNG (not a PDF) — the
        Weatherables CAD sheets — must also be re-materialisable, matching
        the Pillow convert('RGB')+save operation extract.extract_image used
        (extract.py ~line 591)."""
        import sqlite3
        from fence_evidence.paths import EVIDENCE_DB
        conn = sqlite3.connect(f"file:{EVIDENCE_DB}?mode=ro", uri=True)
        rows = conn.execute(
            """SELECT p.page_image_path
                 FROM pages p
                 JOIN document_versions v ON p.version_id = v.version_id
                 JOIN documents d ON v.document_id = d.document_id
                WHERE p.page_image_path IS NOT NULL
                  AND lower(d.source_path) LIKE '%.png'
                LIMIT 5"""
        ).fetchall()
        conn.close()
        checked = 0
        for (rel,) in rows:
            src = REPO_ROOT / rel
            if not src.is_file():
                continue
            with _evicted(src) as original:
                produced = resolve_asset(rel)
                if produced is None:
                    self.skipTest("PIL unavailable or source PNG absent; cannot re-render")
                self.assertEqual(hashlib.sha256(produced.read_bytes()).hexdigest(), original)
            checked += 1
            if checked >= 3:
                break
        if checked == 0:
            self.skipTest("no CAD-sourced page images available to re-render")
