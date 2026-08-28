"""Distribution manifest projection and R2 configuration."""
import unittest
from pathlib import Path
import tempfile

from context import ROOT  # noqa: F401
from fence_evidence.config import load_env, R2Config, ConfigError


class TestLoadEnv(unittest.TestCase):
    def _write(self, text: str) -> Path:
        d = Path(tempfile.mkdtemp())
        p = d / ".env"
        p.write_text(text, encoding="utf-8")
        return p

    def test_parses_pairs_and_ignores_comments_and_blanks(self):
        p = self._write(
            "# a comment\n"
            "\n"
            "R2_BUCKET=fence-rag\n"
            "R2_ACCOUNT_ID=abc123\n"
        )
        env = load_env(p)
        self.assertEqual(env["R2_BUCKET"], "fence-rag")
        self.assertEqual(env["R2_ACCOUNT_ID"], "abc123")
        self.assertNotIn("# a comment", env)

    def test_strips_surrounding_quotes_and_whitespace(self):
        p = self._write('R2_SECRET_ACCESS_KEY = "s3cr3t"\n')
        self.assertEqual(load_env(p)["R2_SECRET_ACCESS_KEY"], "s3cr3t")

    def test_value_containing_equals_is_preserved(self):
        p = self._write("R2_SECRET_ACCESS_KEY=a=b=c\n")
        self.assertEqual(load_env(p)["R2_SECRET_ACCESS_KEY"], "a=b=c")

    def test_missing_file_returns_empty_mapping(self):
        self.assertEqual(load_env(Path("/nonexistent/.env")), {})


class TestR2Config(unittest.TestCase):
    FULL = {
        "R2_ACCOUNT_ID": "abc123",
        "R2_ACCESS_KEY_ID": "AKID",
        "R2_SECRET_ACCESS_KEY": "SECRET",
        "R2_BUCKET": "fence-rag",
        "R2_PUBLIC_BASE_URL": "https://pub.example.com/",
    }

    def test_endpoint_is_derived_from_account_id(self):
        cfg = R2Config.from_env(self.FULL)
        self.assertEqual(cfg.endpoint, "https://abc123.r2.cloudflarestorage.com")

    def test_missing_key_names_the_variable(self):
        env = dict(self.FULL)
        del env["R2_SECRET_ACCESS_KEY"]
        with self.assertRaises(ConfigError) as cm:
            R2Config.from_env(env)
        self.assertIn("R2_SECRET_ACCESS_KEY", str(cm.exception))

    def test_empty_value_is_treated_as_missing(self):
        env = dict(self.FULL, R2_ACCESS_KEY_ID="")
        with self.assertRaises(ConfigError) as cm:
            R2Config.from_env(env)
        self.assertIn("R2_ACCESS_KEY_ID", str(cm.exception))

    def test_public_base_url_is_normalised_to_end_with_slash(self):
        cfg = R2Config.from_env(dict(self.FULL, R2_PUBLIC_BASE_URL="https://pub.example.com"))
        self.assertEqual(cfg.public_base_url, "https://pub.example.com/")

    def test_redacted_never_exposes_the_secret(self):
        cfg = R2Config.from_env(self.FULL)
        blob = repr(cfg.redacted())
        self.assertNotIn("SECRET", blob)
        self.assertIn("fence-rag", blob)

    def test_repr_never_exposes_the_secret(self):
        cfg = R2Config.from_env(self.FULL)
        self.assertNotIn("SECRET", repr(cfg))


from fence_evidence.distribution import (SUBSETS, build_manifest, object_key,
                                         files_for_subset, load_corpus_manifest)


def _row(path, sha, size, structural=False):
    return {"source_path": path, "sha256": sha, "file_size_bytes": size,
            "structural_subdir": structural}


class TestSubsetPredicates(unittest.TestCase):
    def test_structural_uses_structural_subdir_not_structural(self):
        self.assertTrue(SUBSETS["structural"](_row("manuals/x/structural/a.pdf", "a", 1, True)))
        self.assertFalse(SUBSETS["structural"](_row("manuals/x/a.pdf", "a", 1, False)))

    def test_china_matches_the_china_track_only(self):
        self.assertTrue(SUBSETS["china"](_row("china/manuals/a.pdf", "a", 1)))
        self.assertFalse(SUBSETS["china"](_row("manuals/a.pdf", "a", 1)))

    def test_all_matches_everything(self):
        self.assertTrue(SUBSETS["all"](_row("anything", "a", 1)))


class TestBuildManifest(unittest.TestCase):
    ROWS = [
        _row("manuals/certainteed-bufftech/a.pdf", "aaa", 100, False),
        _row("manuals/certainteed-bufftech/structural/b.pdf", "bbb", 200, True),
        _row("manuals/freedom-outdoor-living/b-copy.pdf", "bbb", 200, False),
        _row("china/manuals/c.pdf", "ccc", 300, False),
    ]

    def setUp(self):
        self.m = build_manifest(self.ROWS, "https://pub.example.com/", "2026-01-01T00:00:00Z")

    def test_duplicate_sha256_is_counted_once_in_bytes(self):
        # 4 files, 3 unique objects, 100+200+300 = 600 bytes
        self.assertEqual(self.m["subsets"]["all"]["files"], 4)
        self.assertEqual(self.m["subsets"]["all"]["unique"], 3)
        self.assertEqual(self.m["subsets"]["all"]["bytes"], 600)

    def test_every_file_lists_the_subsets_it_belongs_to(self):
        by_path = {f["source_path"]: f for f in self.m["files"]}
        self.assertIn("structural", by_path["manuals/certainteed-bufftech/structural/b.pdf"]["subsets"])
        self.assertIn("bufftech", by_path["manuals/certainteed-bufftech/a.pdf"]["subsets"])
        self.assertIn("china", by_path["china/manuals/c.pdf"]["subsets"])

    def test_base_url_is_recorded_and_no_secret_is_present(self):
        self.assertEqual(self.m["base_url"], "https://pub.example.com/")
        blob = repr(self.m)
        self.assertNotIn("SECRET", blob)
        self.assertNotIn("R2_SECRET_ACCESS_KEY", blob)

    def test_files_for_subset_returns_both_paths_of_a_duplicate(self):
        got = {f["source_path"] for f in files_for_subset(self.m, "all")}
        self.assertEqual(len(got), 4)

    def test_unknown_subset_raises(self):
        with self.assertRaises(KeyError):
            files_for_subset(self.m, "nope")


class TestObjectKey(unittest.TestCase):
    def test_key_is_content_addressed(self):
        self.assertEqual(object_key("abc123"), "objects/abc123")


class TestAgainstTheRealCorpusManifest(unittest.TestCase):
    def test_real_manifest_projects_to_128_unique_objects(self):
        rows = load_corpus_manifest()
        if not rows:
            self.skipTest("corpus manifest not built")
        m = build_manifest(rows, "https://pub.example.com/", "2026-01-01T00:00:00Z")
        self.assertEqual(m["subsets"]["all"]["files"], 144)
        self.assertEqual(m["subsets"]["all"]["unique"], 128)
        self.assertEqual(m["subsets"]["structural"]["files"], 32)
        self.assertEqual(m["subsets"]["china"]["files"], 4)


# --- writing the distribution manifest (G25) --------------------------------
#
# `publish.publish_manifest` writes workspace/catalog/distribution-manifest.json
# as a side effect of running, which is why it had no test: calling it rewrote
# the committed file. The serialization and the guarded write now live here, in
# the projection module that owns the manifest's shape, with the output path
# injectable so a test can point it at a scratch directory.

import hashlib
import json as _json
import shutil

from fence_evidence import paths as _paths
from fence_evidence.distribution import (DIST_MANIFEST_PATH, manifest_bytes,
                                         write_manifest)
from fence_evidence.paths import CorpusWriteError, REPO_ROOT, TESTS_DIR


class _ScratchDir(unittest.TestCase):
    """A temp directory inside workspace/, because the write guard refuses
    anything outside it -- and removed again, because workspace/tests/ is not
    git-ignored below its two named subdirectories."""

    def scratch(self) -> Path:
        TESTS_DIR.mkdir(parents=True, exist_ok=True)
        d = Path(tempfile.mkdtemp(prefix="distmanifest-", dir=TESTS_DIR))
        self.addCleanup(shutil.rmtree, d, True)
        return d


_ROWS = [
    _row("manuals/certainteed-bufftech/a.pdf", "aaa", 100, False),
    _row("manuals/certainteed-bufftech/structural/b.pdf", "bbb", 200, True),
    _row("manuals/freedom-outdoor-living/b-copy.pdf", "bbb", 200, False),
    _row("china/manuals/c.pdf", "ccc", 300, False),
]


class TestManifestBytes(unittest.TestCase):
    def test_serialization_is_deterministic_for_fixed_inputs(self):
        a = manifest_bytes(build_manifest(_ROWS, "https://x/", "2026-01-01T00:00:00Z"))
        b = manifest_bytes(build_manifest(_ROWS, "https://x/", "2026-01-01T00:00:00Z"))
        self.assertEqual(a, b)

    def test_input_row_order_does_not_change_the_bytes(self):
        a = manifest_bytes(build_manifest(_ROWS, "https://x/", "2026-01-01T00:00:00Z"))
        b = manifest_bytes(build_manifest(list(reversed(_ROWS)), "https://x/",
                                          "2026-01-01T00:00:00Z"))
        self.assertEqual(a, b)

    def test_bytes_round_trip_back_to_the_same_manifest(self):
        m = build_manifest(_ROWS, "https://x/", "2026-01-01T00:00:00Z")
        self.assertEqual(_json.loads(manifest_bytes(m).decode("utf-8")), m)

    def test_the_committed_manifest_reserialises_to_itself(self):
        """Pins today's on-disk encoding: indent=1, sort_keys, UTF-8, no
        trailing newline. If this fails, `cli publish` would rewrite the
        committed manifest with different bytes for identical knowledge."""
        if not DIST_MANIFEST_PATH.is_file():
            self.skipTest("distribution manifest not built")
        raw = DIST_MANIFEST_PATH.read_bytes()
        self.assertEqual(manifest_bytes(_json.loads(raw.decode("utf-8"))), raw)


class TestWriteManifest(_ScratchDir):
    def setUp(self):
        self.m = build_manifest(_ROWS, "https://x/", "2026-01-01T00:00:00Z")

    def test_the_injected_path_is_honoured(self):
        out = self.scratch() / "dm.json"
        write_manifest(self.m, out)
        self.assertTrue(out.is_file())
        self.assertEqual(out.read_bytes(), manifest_bytes(self.m))

    def test_nothing_is_written_to_the_default_location(self):
        before = DIST_MANIFEST_PATH.read_bytes() if DIST_MANIFEST_PATH.is_file() else None
        write_manifest(self.m, self.scratch() / "dm.json")
        after = DIST_MANIFEST_PATH.read_bytes() if DIST_MANIFEST_PATH.is_file() else None
        self.assertEqual(before, after)

    def test_the_default_path_is_the_committed_manifest(self):
        self.assertEqual(DIST_MANIFEST_PATH,
                         _paths.CATALOG_DIR / "distribution-manifest.json")

    def test_missing_parent_directories_are_created(self):
        out = self.scratch() / "a" / "b" / "dm.json"
        write_manifest(self.m, out)
        self.assertTrue(out.is_file())

    def test_the_report_names_the_size_hash_and_repo_relative_path(self):
        out = self.scratch() / "dm.json"
        rep = write_manifest(self.m, out)
        payload = manifest_bytes(self.m)
        self.assertEqual(rep["bytes"], len(payload))
        self.assertEqual(rep["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(rep["local"], str(out.relative_to(REPO_ROOT)))

    def test_writing_twice_is_byte_identical(self):
        out = self.scratch() / "dm.json"
        first = write_manifest(self.m, out)
        second = write_manifest(self.m, out)
        self.assertEqual(first, second)

    def test_the_write_guard_refuses_a_path_outside_the_workspace(self):
        outside = Path(tempfile.mkdtemp()) / "dm.json"
        with self.assertRaises(CorpusWriteError):
            write_manifest(self.m, outside)
        self.assertFalse(outside.exists())

    def test_the_write_guard_refuses_the_repository_root(self):
        with self.assertRaises(CorpusWriteError):
            write_manifest(self.m, REPO_ROOT / "distribution-manifest.json")
        self.assertFalse((REPO_ROOT / "distribution-manifest.json").exists())

    def test_the_write_guard_refuses_a_corpus_path(self):
        with self.assertRaises(CorpusWriteError):
            write_manifest(self.m, REPO_ROOT / "manuals" / "dm.json")


class TestPublishManifestDelegates(_ScratchDir):
    """`publish.publish_manifest` is the caller `cli publish` uses. Its local
    write must stay byte-for-byte what it was, and a dry run must not touch the
    network. Pointed at a scratch path so the committed manifest is not
    rewritten -- which is the whole of G25's testability half: before `path`
    existed, the only way to exercise this function was to overwrite the
    committed artifact."""

    def _cfg(self):
        from fence_evidence.config import R2Config
        return R2Config(account_id="a" * 32, bucket="b",
                        public_base_url="https://x/",
                        access_key_id="AK", secret_access_key="SECRET")

    def test_dry_run_writes_the_same_bytes_locally_and_issues_no_request(self):
        from unittest import mock
        from fence_evidence import publish
        m = build_manifest(_ROWS, "https://x/", "2026-01-01T00:00:00Z")
        target = self.scratch() / "distribution-manifest.json"
        calls = []
        with mock.patch.object(publish, "_request",
                               lambda *a, **k: calls.append(a) or 200):
            out = publish.publish_manifest(self._cfg(), m, dry_run=True,
                                           path=target)
        self.assertEqual(calls, [])
        self.assertTrue(out["dry_run"])
        written = target.read_bytes()
        self.assertEqual(written, manifest_bytes(m))
        self.assertEqual(out["bytes"], len(written))

    def test_a_real_publish_uploads_exactly_the_bytes_it_wrote(self):
        """The local file and the object in the bucket are the same manifest.

        They were serialised twice from the same dict, which happened to agree;
        one encoding is now the only encoding, and this pins it."""
        from unittest import mock
        from fence_evidence import distribution as distmod
        from fence_evidence import publish
        m = build_manifest(_ROWS, "https://x/", "2026-01-01T00:00:00Z")
        # The DEFAULT path is redirected rather than an injected one passed:
        # `path=` with `dry_run=False` is refused, because that combination
        # writes the local copy somewhere else while uploading under the fixed
        # key. Redirecting the default keeps the call shape a real publish has.
        target = self.scratch() / "distribution-manifest.json"
        calls = []
        with mock.patch.object(distmod, "DIST_MANIFEST_PATH", target), \
             mock.patch.object(publish, "_request",
                               lambda *a, **k: calls.append(a) or 200):
            out = publish.publish_manifest(self._cfg(), m, dry_run=False)
        self.assertEqual(len(calls), 1)
        _cfg, method, key, payload, content_type = calls[0]
        self.assertEqual(method, "PUT")
        self.assertEqual(key, "distribution-manifest.json")
        self.assertEqual(content_type, "application/json")
        self.assertEqual(payload, target.read_bytes())
        self.assertFalse(out["dry_run"])

    def test_a_real_publish_with_an_injected_path_is_refused(self):
        """The one combination that silently diverges the committed artifact
        from the bucket: local copy to `path`, object under the fixed key."""
        from unittest import mock
        from fence_evidence import publish
        m = build_manifest(_ROWS, "https://x/", "2026-01-01T00:00:00Z")
        target = self.scratch() / "distribution-manifest.json"
        calls = []
        with mock.patch.object(publish, "_request",
                               lambda *a, **k: calls.append(a) or 200):
            with self.assertRaises(ValueError):
                publish.publish_manifest(self._cfg(), m, dry_run=False,
                                         path=target)
        self.assertEqual(calls, [], "it uploaded before refusing")
        self.assertFalse(target.exists(), "it wrote before refusing")

    def test_the_default_path_is_still_the_committed_manifest(self):
        """The injected path is an addition, not a change of default: `cli
        publish` passes none and must keep regenerating the committed file."""
        import inspect
        from fence_evidence import publish
        self.assertIsNone(
            inspect.signature(publish.publish_manifest).parameters["path"].default)


class TestBuildManifestRefusesUnhashedRows(unittest.TestCase):
    def test_a_row_with_no_sha256_stops_the_whole_run(self):
        rows = _ROWS + [{"source_path": "manuals/x/unfetched.pdf",
                         "sha256": None, "file_size_bytes": 0}]
        with self.assertRaises(ValueError) as cm:
            build_manifest(rows, "https://x/", "2026-01-01T00:00:00Z")
        self.assertIn("manuals/x/unfetched.pdf", str(cm.exception))
        self.assertIn("cli manifest", str(cm.exception))

    def test_an_empty_sha256_counts_as_unhashed(self):
        rows = [{"source_path": "manuals/x/a.pdf", "sha256": "", "file_size_bytes": 0}]
        with self.assertRaises(ValueError):
            build_manifest(rows, "https://x/", "2026-01-01T00:00:00Z")


class TestLoadCorpusManifest(unittest.TestCase):
    def test_a_missing_file_is_an_empty_list_not_an_error(self):
        self.assertEqual(load_corpus_manifest(Path("/nonexistent/corpus.jsonl")), [])

    def test_blank_lines_are_skipped_and_rows_parse(self):
        d = Path(tempfile.mkdtemp())
        p = d / "corpus-manifest.jsonl"
        p.write_text('{"source_path": "a", "sha256": "aa"}\n\n'
                     '  \n{"source_path": "b", "sha256": "bb"}\n', encoding="utf-8")
        rows = load_corpus_manifest(p)
        self.assertEqual([r["source_path"] for r in rows], ["a", "b"])
