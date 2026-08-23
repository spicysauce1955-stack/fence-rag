"""resolve_asset materialises derived images on demand."""
import unittest
from pathlib import Path

from context import ROOT, requires_store  # noqa: F401
from fence_evidence.paths import resolve_asset, REPO_ROOT


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
        """D5: an on-demand render matches what ingest wrote."""
        import sqlite3, hashlib, shutil, tempfile
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
            original = hashlib.sha256(src.read_bytes()).hexdigest()
            backup = Path(tempfile.mkdtemp()) / "orig.png"
            shutil.copy2(src, backup)
            try:
                src.unlink()
                produced = resolve_asset(rel)
                if produced is None:
                    self.skipTest("source PDF absent; cannot re-render")
                self.assertEqual(hashlib.sha256(produced.read_bytes()).hexdigest(), original)
                checked += 1
            finally:
                shutil.copy2(backup, src)
            if checked >= 3:
                break
        if checked == 0:
            self.skipTest("no page images available to re-render")
