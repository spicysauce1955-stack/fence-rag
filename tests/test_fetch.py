"""Anonymous fetch: hash verification, idempotency, and manifest containment."""
import hashlib
import http.server
import json
import tempfile
import threading
import unittest
from pathlib import Path

from context import ROOT  # noqa: F401
from fence_evidence.distribution import build_manifest
from fence_evidence.fetch import download_object, fetch_subset
from fence_evidence.paths import CorpusWriteError

PAYLOAD = b"%PDF-1.4 pretend document\n"
SHA = hashlib.sha256(PAYLOAD).hexdigest()


class _Handler(http.server.BaseHTTPRequestHandler):
    corrupt = False

    def do_GET(self):
        body = b"tampered" if self.corrupt else PAYLOAD
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class ServerCase(unittest.TestCase):
    def setUp(self):
        _Handler.corrupt = False
        self.srv = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
        self.base = f"http://127.0.0.1:{self.srv.server_port}/"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        self.srv.shutdown()


class TestDownloadObject(ServerCase):
    def test_downloads_and_verifies(self):
        dest = self.tmp / "a.pdf"
        self.assertTrue(download_object(self.base + "objects/" + SHA, SHA, dest, self.tmp))
        self.assertEqual(dest.read_bytes(), PAYLOAD)

    def test_second_call_transfers_nothing(self):
        dest = self.tmp / "a.pdf"
        download_object(self.base + "objects/" + SHA, SHA, dest, self.tmp)
        self.assertFalse(download_object(self.base + "objects/" + SHA, SHA, dest, self.tmp))

    def test_hash_mismatch_raises_and_leaves_no_file(self):
        _Handler.corrupt = True
        dest = self.tmp / "a.pdf"
        with self.assertRaises(ValueError) as cm:
            download_object(self.base + "objects/" + SHA, SHA, dest, self.tmp)
        self.assertIn("sha256", str(cm.exception).lower())
        self.assertFalse(dest.exists())

    def test_no_temp_files_are_left_behind_after_failure(self):
        _Handler.corrupt = True
        dest = self.tmp / "a.pdf"
        with self.assertRaises(ValueError):
            download_object(self.base + "objects/" + SHA, SHA, dest, self.tmp)
        self.assertEqual(list(self.tmp.glob("*.part")), [])

    def test_refuses_a_destination_that_exists_and_is_not_a_regular_file(self):
        dest = self.tmp / "a_dir"
        dest.mkdir()
        with self.assertRaises(IsADirectoryError):
            download_object(self.base + "objects/" + SHA, SHA, dest, self.tmp)


class TestFetchSubsetRefusesUnlistedPaths(ServerCase):
    def test_a_path_absent_from_the_manifest_is_refused(self):
        rows = [{"source_path": "manuals/ok/a.pdf", "sha256": SHA,
                 "file_size_bytes": len(PAYLOAD), "structural_subdir": False}]
        m = build_manifest(rows, self.base, "2026-01-01T00:00:00Z")
        m["files"][0]["source_path"] = "../escape.pdf"   # tamper after generation
        with self.assertRaises(CorpusWriteError):
            fetch_subset(m, "all", dest_root=ROOT, workers=1)


if __name__ == "__main__":
    unittest.main()
