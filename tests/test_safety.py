"""The corpus is read-only and document content is never executed."""
import os
import unittest
from pathlib import Path

from context import ROOT
from fence_evidence import paths, tools
from fence_evidence.paths import fetch_target, CorpusWriteError, REPO_ROOT


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


class TestFetchTargetGuard(unittest.TestCase):
    ALLOWED = {"manuals/example/doc.pdf"}

    def test_allows_a_listed_corpus_path(self):
        p = fetch_target(REPO_ROOT / "manuals/example/doc.pdf", self.ALLOWED)
        self.assertEqual(p, (REPO_ROOT / "manuals/example/doc.pdf").resolve())

    def test_refuses_a_corpus_path_not_in_the_manifest(self):
        with self.assertRaises(CorpusWriteError):
            fetch_target(REPO_ROOT / "manuals/example/other.pdf", self.ALLOWED)

    def test_refuses_a_path_outside_the_corpus_even_if_listed(self):
        with self.assertRaises(CorpusWriteError):
            fetch_target(REPO_ROOT / "fence_evidence/cli.py",
                         {"fence_evidence/cli.py"})

    def test_refuses_traversal_out_of_the_corpus(self):
        with self.assertRaises(CorpusWriteError):
            fetch_target(REPO_ROOT / "manuals/../fence_evidence/x.py",
                         {"manuals/../fence_evidence/x.py"})

    def test_refuses_a_symlinked_component(self):
        # The symlink must not live inside manuals/ -- creating one there
        # would itself be a write into the read-only corpus. Instead we
        # place the link under workspace/, but point it INTO the corpus
        # (manuals/example) so the resolved path satisfies conditions 1
        # (inside CORPUS_ROOTS) and 2 (listed in allowed) -- the symlink
        # check is then the ONLY thing that can make fetch_target refuse.
        # (Pointing at an unrelated scratch dir, as an earlier version of
        # this test did, lets it pass for the wrong reason: it would also
        # fail condition 1, so a fetch_target with the symlink check moved
        # to *after* .resolve() -- the exact vulnerability this test exists
        # to catch -- would still raise CorpusWriteError, just for "outside
        # the corpus" instead of "symlink". assertRaisesRegex pins the
        # reason so that regression cannot hide again.)
        link = paths.WORKSPACE / "_test_fetch_link"
        try:
            os.symlink(REPO_ROOT / "manuals" / "example", link)
            with self.assertRaisesRegex(CorpusWriteError, "symlink"):
                fetch_target(link / "doc.pdf", {"manuals/example/doc.pdf"})
        finally:
            if link.is_symlink():
                link.unlink()


class TestFetchTargetIsNotReachableFromPipelineCode(unittest.TestCase):
    """fetch_target is the one hole in the read-only guard. Keep it contained."""

    PERMITTED = {"paths.py", "fetch.py", "cli.py"}

    def test_only_fetch_and_cli_reference_fetch_target(self):
        pkg = REPO_ROOT / "fence_evidence"
        modules = sorted(pkg.glob("*.py"))
        # Assert the scan found something. Pointing this at a directory that no
        # longer exists makes the test pass over an empty list, which is how a
        # guard quietly stops guarding when the package is moved.
        self.assertGreater(len(modules), 20,
                           f"expected to scan the package, found {len(modules)} "
                           f"modules under {pkg}")
        offenders = []
        for py in modules:
            if py.name in self.PERMITTED:
                continue
            if "fetch_target" in py.read_text(encoding="utf-8"):
                offenders.append(py.name)
        self.assertEqual(offenders, [],
                         f"fetch_target must not be reachable from pipeline code: {offenders}")


if __name__ == "__main__":
    unittest.main()
