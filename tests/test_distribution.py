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
