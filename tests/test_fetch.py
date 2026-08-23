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
    last_user_agent = None

    def do_GET(self):
        _Handler.last_user_agent = self.headers.get("User-Agent")
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
        _Handler.last_user_agent = None
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

    def test_sends_an_explicit_user_agent(self):
        # Cloudflare's r2.dev public host returns 403 to the default
        # Python-urllib User-Agent; regression guard for that fix.
        dest = self.tmp / "a.pdf"
        download_object(self.base + "objects/" + SHA, SHA, dest, self.tmp)
        ua = _Handler.last_user_agent
        self.assertIsNotNone(ua)
        self.assertFalse(ua.startswith("Python-urllib"))


class TestFetchSubsetRefusesUnlistedPaths(ServerCase):
    def test_a_path_absent_from_the_manifest_is_refused(self):
        rows = [{"source_path": "manuals/ok/a.pdf", "sha256": SHA,
                 "file_size_bytes": len(PAYLOAD), "structural_subdir": False}]
        m = build_manifest(rows, self.base, "2026-01-01T00:00:00Z")
        m["files"][0]["source_path"] = "../escape.pdf"   # tamper after generation
        with self.assertRaises(CorpusWriteError):
            fetch_subset(m, "all", dest_root=ROOT, workers=1)


class _MultiHandler(http.server.BaseHTTPRequestHandler):
    """Serves whatever object the key names, and counts GETs per key."""

    bodies: dict = {}
    gets: list = []
    resolved_at_first_get = None

    def do_GET(self):
        key = self.path.lstrip("/")
        if _MultiHandler.resolved_at_first_get is None:
            _MultiHandler.resolved_at_first_get = len(_RESOLVED)
        _MultiHandler.gets.append(key)
        body = _MultiHandler.bodies.get(key)
        if body is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


PAYLOAD2 = b"%PDF-1.4 a second pretend document\n"
SHA2 = hashlib.sha256(PAYLOAD2).hexdigest()

_RESOLVED: list = []


class TestFetchSubsetDedupesByHash(unittest.TestCase):
    """14 groups of byte-identical corpus files mean 144 paths hold 128
    objects. Iterating paths rather than objects re-downloaded the 16
    redundant copies -- 55.5 MB on `--subset all`, 48% on `--subset
    structural`. Three paths / two hashes reproduces that in miniature."""

    ROWS = [
        {"source_path": "manuals/alpha/dup.pdf", "sha256": SHA,
         "file_size_bytes": len(PAYLOAD), "structural_subdir": False},
        {"source_path": "manuals/beta/dup.pdf", "sha256": SHA,
         "file_size_bytes": len(PAYLOAD), "structural_subdir": False},
        {"source_path": "manuals/beta/solo.pdf", "sha256": SHA2,
         "file_size_bytes": len(PAYLOAD2), "structural_subdir": False},
    ]

    def setUp(self):
        from fence_evidence import paths as paths_mod
        from fence_evidence import fetch as fetch_mod

        _MultiHandler.bodies = {"objects/" + SHA: PAYLOAD,
                                "objects/" + SHA2: PAYLOAD2}
        _MultiHandler.gets = []
        _MultiHandler.resolved_at_first_get = None
        del _RESOLVED[:]

        self.srv = http.server.HTTPServer(("127.0.0.1", 0), _MultiHandler)
        self.base = f"http://127.0.0.1:{self.srv.server_port}/"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

        # A fake repository root, so the real fetch_target guard runs in full
        # against a throwaway corpus instead of the read-only one. Writing the
        # actual manuals/ tree from a test is exactly what that guard exists
        # to prevent.
        self.root = Path(tempfile.mkdtemp()).resolve()
        (self.root / "manuals").mkdir()
        self.paths_mod = paths_mod
        self.fetch_mod = fetch_mod
        self._saved = (paths_mod.REPO_ROOT, paths_mod.CORPUS_ROOTS,
                       fetch_mod.fetch_target)
        paths_mod.REPO_ROOT = self.root
        paths_mod.CORPUS_ROOTS = (self.root / "manuals",)

        real = paths_mod.fetch_target

        def recording_fetch_target(path, allowed):
            out = real(path, allowed)
            _RESOLVED.append(out)
            return out

        fetch_mod.fetch_target = recording_fetch_target
        self.manifest = build_manifest(self.ROWS, self.base, "2026-01-01T00:00:00Z")

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        (self.paths_mod.REPO_ROOT, self.paths_mod.CORPUS_ROOTS,
         self.fetch_mod.fetch_target) = self._saved

    def test_a_shared_object_is_downloaded_once_and_copied_to_its_sibling(self):
        r = fetch_subset(self.manifest, "all", dest_root=self.root, workers=1)
        self.assertEqual(r["failed"], [])
        self.assertEqual(r["requested"], 3)
        self.assertEqual(r["objects"], 2)
        self.assertEqual(r["downloaded"], 2)
        self.assertEqual(r["copied"], 1)
        self.assertEqual(r["already_present"], 0)
        self.assertEqual(r["bytes"], len(PAYLOAD) + len(PAYLOAD2))
        # one GET per distinct object, never one per path
        self.assertEqual(sorted(_MultiHandler.gets),
                         sorted(["objects/" + SHA, "objects/" + SHA2]))
        for row, expected in zip(self.ROWS, (PAYLOAD, PAYLOAD, PAYLOAD2)):
            self.assertEqual((self.root / row["source_path"]).read_bytes(), expected)

    def test_every_target_is_resolved_before_the_first_byte_transfers(self):
        fetch_subset(self.manifest, "all", dest_root=self.root, workers=1)
        # all three targets had passed fetch_target before the first GET
        self.assertEqual(_MultiHandler.resolved_at_first_get, 3)

    def test_a_second_run_transfers_and_copies_nothing(self):
        fetch_subset(self.manifest, "all", dest_root=self.root, workers=1)
        _MultiHandler.gets = []
        r = fetch_subset(self.manifest, "all", dest_root=self.root, workers=1)
        self.assertEqual(_MultiHandler.gets, [])
        self.assertEqual(
            (r["downloaded"], r["copied"], r["already_present"], r["bytes"]),
            (0, 0, 3, 0))

    def test_a_missing_sibling_is_restored_without_a_download(self):
        fetch_subset(self.manifest, "all", dest_root=self.root, workers=1)
        (self.root / "manuals/beta/dup.pdf").unlink()
        _MultiHandler.gets = []
        r = fetch_subset(self.manifest, "all", dest_root=self.root, workers=1)
        self.assertEqual(_MultiHandler.gets, [])
        self.assertEqual((r["downloaded"], r["copied"], r["bytes"]), (0, 1, 0))
        self.assertEqual((self.root / "manuals/beta/dup.pdf").read_bytes(), PAYLOAD)


if __name__ == "__main__":
    unittest.main()
