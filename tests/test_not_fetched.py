"""An unfetched corpus must fail loudly, never look like a successful run.

A `GIT_LFS_SKIP_SMUDGE=1` clone leaves every corpus PDF as a ~131-byte text
stub. poppler reports one as a zero-page PDF, which is exactly what it reports
for a genuinely corrupt file, so nothing downstream could tell the two apart:
the manifest recorded the stub's hash as the document's identity, and
`ingest --pilot` reported `"ingested": 10, "failed": 0` over eight files whose
content was never on disk.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from context import ROOT
from fence_evidence import manifest as manifest_mod
from fence_evidence.distribution import build_manifest as build_dist_manifest
from fence_evidence.ingest import StaleManifestError, partition_targets
from fence_evidence.paths import is_lfs_pointer, lfs_pointer_info

POINTER = (b"version https://git-lfs.github.com/spec/v1\n"
           b"oid sha256:fb6d596f50662281fbd7bc94a6525debebcdb89e6bc619e4f06669c8cc482f1d\n"
           b"size 11145284\n")


def _pointer_file(suffix: str = ".pdf") -> Path:
    d = Path(tempfile.mkdtemp())
    p = d / f"stub{suffix}"
    p.write_bytes(POINTER)
    return p


class TestPointerDetection(unittest.TestCase):
    def test_recognises_a_pointer(self):
        self.assertTrue(is_lfs_pointer(_pointer_file()))

    def test_a_real_pdf_is_not_a_pointer(self):
        d = Path(tempfile.mkdtemp())
        p = d / "real.pdf"
        p.write_bytes(b"%PDF-1.7\n%\xa1\xb3\xc5\xd7\n1 0 obj\n")
        self.assertFalse(is_lfs_pointer(p))

    def test_a_missing_file_is_not_a_pointer(self):
        self.assertFalse(is_lfs_pointer(Path("/nonexistent/x.pdf")))

    def test_size_alone_cannot_be_used(self):
        """The check must be by signature: `find -size -1k` rounds up to a
        whole block, so a 131-byte pointer matches neither -1k nor +1k."""
        p = _pointer_file()
        self.assertLess(p.stat().st_size, 1024)
        self.assertTrue(is_lfs_pointer(p))

    def test_pointer_info_reports_the_real_objects_hash_and_size(self):
        info = lfs_pointer_info(_pointer_file())
        self.assertEqual(
            info["oid"],
            "fb6d596f50662281fbd7bc94a6525debebcdb89e6bc619e4f06669c8cc482f1d")
        self.assertEqual(info["size"], 11145284)

    def test_pointer_info_is_none_for_real_content(self):
        d = Path(tempfile.mkdtemp())
        p = d / "real.pdf"
        p.write_bytes(b"%PDF-1.7\n")
        self.assertIsNone(lfs_pointer_info(p))


class TestManifestRefusesPointers(unittest.TestCase):
    def _inspect(self) -> dict:
        return manifest_mod.inspect_file((str(_pointer_file()), {}))

    def test_records_no_sha256_for_a_pointer(self):
        """The stub's hash must never stand in for the document's identity."""
        self.assertIsNone(self._inspect()["sha256"])

    def test_marks_the_row_not_fetched(self):
        rec = self._inspect()
        self.assertEqual(rec["processing_state"], "not-fetched")
        self.assertEqual(rec["extraction_method"], "not-fetched")
        self.assertTrue(rec["lfs_pointer"])

    def test_keeps_the_declared_object_hash_for_traceability(self):
        rec = self._inspect()
        self.assertEqual(
            rec["lfs_declared_sha256"],
            "fb6d596f50662281fbd7bc94a6525debebcdb89e6bc619e4f06669c8cc482f1d")
        self.assertEqual(rec["lfs_declared_size_bytes"], 11145284)

    def test_does_not_claim_the_pdf_is_corrupt(self):
        """'pdfinfo reported 0 pages' is the note for a broken PDF, and reading
        it on an unfetched file sent people looking for the wrong problem."""
        notes = " ".join(self._inspect()["inspection_notes"])
        self.assertNotIn("pdfinfo", notes)
        self.assertIn("Git LFS pointer", notes)
        self.assertIn("fetch", notes.lower())


class TestIngestPreflight(unittest.TestCase):
    MANIFEST = {
        "manuals/x/real.pdf": {"source_path": "manuals/x/real.pdf",
                               "doc_id": "doc-real", "sha256": "a" * 64},
        "manuals/x/stub.pdf": {"source_path": "manuals/x/stub.pdf",
                               "doc_id": "doc-stub", "sha256": None},
    }

    def test_unknown_path_is_reported_not_silently_dropped(self):
        parts = partition_targets(["manuals/x/nope.pdf"], self.MANIFEST)
        self.assertEqual(parts["unknown"], ["manuals/x/nope.pdf"])
        self.assertEqual(parts["ready"], [])

    def test_a_hashed_row_whose_file_is_absent_is_ready(self):
        """partition_targets only rejects a file it can positively identify as
        a pointer; a missing file is extraction's problem to report."""
        parts = partition_targets(["manuals/x/real.pdf"], self.MANIFEST)
        self.assertEqual(parts["ready"], ["manuals/x/real.pdf"])

    def test_an_unhashed_row_whose_file_is_absent_is_stale(self):
        parts = partition_targets(["manuals/x/stub.pdf"], self.MANIFEST)
        self.assertEqual(parts["stale"], ["manuals/x/stub.pdf"])
        self.assertEqual(parts["ready"], [])

    def test_stale_manifest_error_names_the_remedy(self):
        self.assertIn("manifest", str(StaleManifestError("re-run cli manifest")))


class TestIngestOnAnUnfetchedCheckout(unittest.TestCase):
    """End-to-end: ingest a pointer and confirm the run is not called clean."""

    def test_pointer_target_is_not_reported_as_ingested(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Path(tmp) / "manuals" / "x"
            corpus.mkdir(parents=True)
            (corpus / "stub.pdf").write_bytes(POINTER)
            code = (
                "import sys; sys.path.insert(0, %r)\n"
                "import fence_evidence.paths as P\n"
                "P.REPO_ROOT = __import__('pathlib').Path(%r)\n"
                "import fence_evidence.ingest as I\n"
                "I.REPO_ROOT = P.REPO_ROOT\n"
                "m = {'manuals/x/stub.pdf': {'source_path': 'manuals/x/stub.pdf',\n"
                "     'doc_id': 'doc-stub', 'sha256': None}}\n"
                "import json; print(json.dumps("
                "I.partition_targets(['manuals/x/stub.pdf'], m)))\n"
            ) % (str(ROOT), tmp)
            out = subprocess.run([sys.executable, "-c", code],
                                 capture_output=True, text=True, check=True)
            parts = json.loads(out.stdout)
            self.assertEqual(parts["not_fetched"], ["manuals/x/stub.pdf"])
            self.assertEqual(parts["ready"], [])


class TestPublishRefusesAPartialCorpus(unittest.TestCase):
    def test_unhashed_row_is_refused_not_keyed_as_objects_none(self):
        rows = [{"source_path": "manuals/x/stub.pdf", "sha256": None,
                 "file_size_bytes": 131, "structural_subdir": False}]
        with self.assertRaises(ValueError) as cm:
            build_dist_manifest(rows, "https://example.com/", "2026-01-01T00:00:00Z")
        self.assertIn("sha256", str(cm.exception))

    def test_a_fully_hashed_corpus_still_projects(self):
        rows = [{"source_path": "manuals/x/real.pdf", "sha256": "a" * 64,
                 "file_size_bytes": 10, "structural_subdir": False}]
        man = build_dist_manifest(rows, "https://example.com/", "2026-01-01T00:00:00Z")
        self.assertEqual(man["files"][0]["key"], "objects/" + "a" * 64)


if __name__ == "__main__":
    unittest.main()
