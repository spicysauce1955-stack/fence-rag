"""publish.py: the one module that holds credentials and writes outward.

Every test here stubs `publish._request`, or the `urlopen` beneath it, so no
network call is ever made and `--apply` is never simulated against a real
bucket. The R2Config is fabricated from literals in this file; the real .env
is never read, because this repository is public and a test that reads a live
credential is a test that can print one into CI output.
"""
import hashlib
import json
import unittest
import urllib.error
from unittest import mock

from context import ROOT, requires_corpus  # noqa: F401
from fence_evidence import publish
from fence_evidence.config import R2Config
from fence_evidence.distribution import load_corpus_manifest

FAKE_KEY_ID = "AKIAFAKEKEYIDFORTESTS"
FAKE_SECRET = "s3cr3t-that-must-never-appear-in-any-output"

CFG = R2Config(
    account_id="0123456789abcdef0123456789abcdef",
    bucket="fence-rag-test",
    public_base_url="https://example.invalid/",
    access_key_id=FAKE_KEY_ID,
    secret_access_key=FAKE_SECRET,
)


class _Recorder:
    """Stands in for publish._request and records what it was asked to do."""

    def __init__(self, status=200):
        self.calls = []
        self.status = status

    def __call__(self, cfg, method, key, payload, content_type):
        self.calls.append((method, key, len(payload), content_type))
        return self.status


class TestDryRun(unittest.TestCase):
    """A dry run must be exactly that: no request, no upload, real counts."""

    @requires_corpus
    def test_a_dry_run_issues_no_request_at_all(self):
        rows = load_corpus_manifest()
        if not rows:
            self.skipTest("corpus manifest not built")
        rec = _Recorder()
        with mock.patch.object(publish, "_request", rec):
            out = publish.publish_objects(CFG, rows, dry_run=True)
        self.assertEqual(rec.calls, [])
        self.assertTrue(out["dry_run"])
        self.assertEqual(out["uploaded"], 0)

    @requires_corpus
    def test_a_dry_run_counts_the_real_corpus_objects_and_duplicates(self):
        """144 corpus paths hold 128 distinct objects; the 16 redundant
        paths are skipped rather than uploaded twice."""
        rows = load_corpus_manifest()
        if not rows:
            self.skipTest("corpus manifest not built")
        if any(not (publish.REPO_ROOT / r["source_path"]).is_file() for r in rows):
            self.skipTest("corpus files absent (unsmudged LFS pointers?)")
        rec = _Recorder()
        with mock.patch.object(publish, "_request", rec):
            out = publish.publish_objects(CFG, rows, dry_run=True)
        self.assertEqual(len(rows), 144)
        self.assertEqual(out["unique_objects"], 128)
        self.assertEqual(out["skipped_duplicate_paths"], 16)
        self.assertEqual(out["unique_objects"] + out["skipped_duplicate_paths"],
                         len(rows))
        self.assertEqual(out["bytes"], 376489773)


class TestIntegrityGuard(unittest.TestCase):
    def test_a_row_whose_sha256_disagrees_with_the_file_raises(self):
        """The bytes on disk are what gets uploaded, so a manifest that has
        drifted from the file must stop the run, not publish the wrong bytes
        under a key that claims to be their hash."""
        rows = [{"source_path": "README.md", "sha256": "00" * 32}]
        rec = _Recorder()
        with mock.patch.object(publish, "_request", rec):
            with self.assertRaises(RuntimeError) as cm:
                publish.publish_objects(CFG, rows, dry_run=True)
        self.assertIn("does not match its manifest sha256", str(cm.exception))
        self.assertEqual(rec.calls, [])

    def test_a_row_whose_sha256_matches_passes(self):
        payload = (publish.REPO_ROOT / "README.md").read_bytes()
        rows = [{"source_path": "README.md",
                 "sha256": hashlib.sha256(payload).hexdigest()}]
        rec = _Recorder()
        with mock.patch.object(publish, "_request", rec):
            out = publish.publish_objects(CFG, rows, dry_run=True)
        self.assertEqual(out["unique_objects"], 1)
        self.assertEqual(out["bytes"], len(payload))


def _http_error(code):
    return urllib.error.HTTPError("https://example.invalid/k", code,
                                  "nope", {}, None)


class TestHeadObject(unittest.TestCase):
    """404 means absent. Nothing else does -- least of all 403, which is what
    a wrong or expired credential returns. Treating that as 'absent' would
    make publish re-upload the entire corpus on every run and mask the real
    fault."""

    def test_404_means_absent(self):
        with mock.patch("urllib.request.urlopen", side_effect=_http_error(404)):
            self.assertFalse(publish.head_object(CFG, "objects/abc"))

    def test_403_propagates_as_an_error(self):
        with mock.patch("urllib.request.urlopen", side_effect=_http_error(403)):
            with self.assertRaises(RuntimeError) as cm:
                publish.head_object(CFG, "objects/abc")
        self.assertIn("403", str(cm.exception))

    def test_500_propagates_as_an_error(self):
        with mock.patch("urllib.request.urlopen", side_effect=_http_error(500)):
            with self.assertRaises(RuntimeError):
                publish.head_object(CFG, "objects/abc")

    def test_200_means_present(self):
        resp = mock.MagicMock()
        resp.status = 200
        resp.__enter__.return_value = resp
        with mock.patch("urllib.request.urlopen", return_value=resp):
            self.assertTrue(publish.head_object(CFG, "objects/abc"))

    def test_an_error_message_never_carries_the_secret(self):
        with mock.patch("urllib.request.urlopen", side_effect=_http_error(403)):
            with self.assertRaises(RuntimeError) as cm:
                publish.head_object(CFG, "objects/abc")
        self.assertNotIn(FAKE_SECRET, str(cm.exception))
        self.assertNotIn(FAKE_KEY_ID, str(cm.exception))


class TestNothingLeaksTheCredential(unittest.TestCase):
    """`cli publish` prints its return value as JSON. Nothing in it may be a
    secret: this repository is public."""

    def test_the_returned_dict_carries_no_credential(self):
        payload = (publish.REPO_ROOT / "README.md").read_bytes()
        rows = [{"source_path": "README.md",
                 "sha256": hashlib.sha256(payload).hexdigest()}]
        with mock.patch.object(publish, "_request", _Recorder()):
            out = publish.publish_objects(CFG, rows, dry_run=True)
        blob = json.dumps(out)
        self.assertNotIn(FAKE_SECRET, blob)
        self.assertNotIn(FAKE_KEY_ID, blob)

    def test_the_redacted_config_carries_no_secret(self):
        blob = json.dumps(CFG.redacted())
        self.assertNotIn(FAKE_SECRET, blob)
        self.assertNotIn(FAKE_KEY_ID, blob)

    def test_repr_carries_no_secret(self):
        self.assertNotIn(FAKE_SECRET, repr(CFG))
        self.assertNotIn(FAKE_KEY_ID, repr(CFG))


if __name__ == "__main__":
    unittest.main()
