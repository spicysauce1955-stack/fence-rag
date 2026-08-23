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
