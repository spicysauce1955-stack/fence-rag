"""`document`/`resolve`/`search --element-type` on bad input: named in
`docs/state-and-gaps.md` beside the `fetch --subset` fix as the same defect
class, left unfixed there as "a larger, CLI-wide pattern that deserves its
own pass". This is that pass, scoped to exactly the three commands named.

Before this fix: `document <unknown-id>` and `resolve <unknown-id>` printed
`null` and exited 0 -- indistinguishable from a script bug that passed an
empty identifier and got back "no versions, no relations, nothing to say"
for a document that DOES exist. `search --element-type <typo>` silently
returned `[]` and exited 0 -- indistinguishable from a query that legitimately
has no matches within a real element type.
"""
import contextlib
import io
import unittest

import context  # noqa: F401  -- puts the repo root on sys.path
from context import requires_store
from fence_evidence.cli import main


def _run(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = main(argv)
    return code, buf.getvalue()


@requires_store
class TestDocumentNotFound(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fence_evidence.store import connect
        cls.conn = connect()
        row = cls.conn.execute("SELECT document_id FROM documents LIMIT 1").fetchone()
        if row is None:
            raise unittest.SkipTest("store has no documents")
        cls.real_id = row[0]

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_an_unknown_identifier_exits_nonzero(self):
        code, out = _run(["document", "no-such-document-id"])
        self.assertEqual(code, 1)
        self.assertIn("error", out)

    def test_a_real_identifier_still_exits_zero(self):
        code, out = _run(["document", self.real_id])
        self.assertEqual(code, 0)
        self.assertNotIn('"error"', out)


@requires_store
class TestResolveNotFound(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fence_evidence.store import connect
        cls.conn = connect()
        row = cls.conn.execute("SELECT document_id FROM documents LIMIT 1").fetchone()
        if row is None:
            raise unittest.SkipTest("store has no documents")
        cls.real_id = row[0]

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_an_unknown_identifier_exits_nonzero(self):
        code, out = _run(["resolve", "no-such-document-id"])
        self.assertEqual(code, 1)
        self.assertIn("error", out)

    def test_a_real_identifier_still_exits_zero(self):
        code, out = _run(["resolve", self.real_id])
        self.assertEqual(code, 0)
        self.assertNotIn('"error"', out)


@requires_store
class TestSearchElementTypeNotFound(unittest.TestCase):
    """`--element-type` has no argparse `choices=` -- the real vocabulary is
    whatever `extract.py` has actually assigned in the live store, the same
    reason `fetch --subset` validates against the fetched manifest rather
    than a list hardcoded in the CLI."""

    @classmethod
    def setUpClass(cls):
        from fence_evidence.store import connect
        cls.conn = connect()
        row = cls.conn.execute(
            "SELECT element_type FROM elements LIMIT 1").fetchone()
        if row is None:
            raise unittest.SkipTest("store has no elements")
        cls.real_type = row[0]

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_an_unknown_element_type_exits_nonzero(self):
        code, out = _run(["search", "footing depth", "--element-type", "no-such-type"])
        self.assertEqual(code, 2)
        self.assertIn("error", out)

    def test_a_real_element_type_with_no_hits_still_exits_zero(self):
        """A known type that this particular query does not match is a
        normal empty result, not a bad-input error."""
        code, out = _run(["search", "zzzzznonexistentqueryzzzzz",
                          "--element-type", self.real_type])
        self.assertEqual(code, 0)
        self.assertNotIn('"error"', out)


if __name__ == "__main__":
    unittest.main()
