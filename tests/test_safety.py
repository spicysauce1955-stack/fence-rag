"""The corpus is read-only and document content is never executed."""
import unittest
from pathlib import Path

from context import ROOT
from fence_evidence import paths, tools


class TestWriteGuard(unittest.TestCase):
    def test_refuses_corpus_write(self):
        for target in ("manuals/x.pdf", "data/documents-index.json",
                       "master-dataset.json", "../escape.txt"):
            with self.assertRaises(paths.CorpusWriteError):
                paths.ensure_writable(ROOT / target)

    def test_allows_workspace_write(self):
        p = paths.ensure_writable(paths.REPORTS_DIR / "probe.md")
        self.assertTrue(str(p).startswith(str(paths.WORKSPACE)))

    def test_open_write_rejects_corpus(self):
        with self.assertRaises(paths.CorpusWriteError):
            paths.open_write(ROOT / "guide.md", "w")

    def test_symlink_escape_is_refused(self):
        link = paths.WORKSPACE / "escape-link"
        try:
            if not link.exists():
                link.symlink_to(ROOT / "manuals")
            with self.assertRaises(paths.CorpusWriteError):
                paths.ensure_writable(link / "evil.pdf")
        finally:
            if link.is_symlink():
                link.unlink()


class TestNoShell(unittest.TestCase):
    def test_run_rejects_string_commands(self):
        # a string would be interpreted by a shell if shell=True were ever set
        with self.assertRaises(TypeError):
            tools.run("pdftotext -v")

    def test_run_rejects_non_string_items(self):
        with self.assertRaises(TypeError):
            tools.run(["pdftotext", 3])


if __name__ == "__main__":
    unittest.main()
