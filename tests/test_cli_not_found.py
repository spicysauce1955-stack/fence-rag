"""`document`/`resolve`/`page`/`region`/`context`/`search --element-type` on
bad input: named in `docs/state-and-gaps.md` beside the `fetch --subset` fix
as the same defect class, left unfixed there as "a larger, CLI-wide pattern
that deserves its own pass". This is that pass.

Before this fix: `document <unknown-id>` and `resolve <unknown-id>` printed
`null` and exited 0 -- indistinguishable from a script bug that passed an
empty identifier and got back "no versions, no relations, nothing to say"
for a document that DOES exist. `page`/`region`/`context` shared the exact
same shape (`dict | None` + unconditional `_print`) and are fixed the same
way. `search --element-type <typo>` silently returned `[]` and exited 0 --
indistinguishable from a query that legitimately has no matches within a
real element type.
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
        self.assertIn('"error"', out)

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
        self.assertIn('"error"', out)

    def test_a_real_identifier_still_exits_zero(self):
        code, out = _run(["resolve", self.real_id])
        self.assertEqual(code, 0)
        self.assertNotIn('"error"', out)


@requires_store
class TestPageRegionContextNotFound(unittest.TestCase):
    """`page`/`region`/`context` share `document`/`resolve`'s exact shape --
    a review of this fix caught that the first cut left them behind, framing
    itself as the full CLI-wide pass while three siblings kept the defect."""

    @classmethod
    def setUpClass(cls):
        from fence_evidence.store import connect
        cls.conn = connect()
        doc = cls.conn.execute("SELECT document_id FROM documents LIMIT 1").fetchone()
        el = cls.conn.execute("SELECT element_id FROM elements LIMIT 1").fetchone()
        if doc is None or el is None:
            raise unittest.SkipTest("store has no documents or elements")
        cls.real_document_id = doc[0]
        cls.real_element_id = el[0]

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_page_on_an_unknown_document_exits_nonzero(self):
        code, out = _run(["page", "no-such-document-id", "1"])
        self.assertEqual(code, 1)
        self.assertIn('"error"', out)

    def test_page_past_the_last_real_page_exits_nonzero(self):
        code, out = _run(["page", self.real_document_id, "999999"])
        self.assertEqual(code, 1)
        self.assertIn('"error"', out)

    def test_region_on_an_unknown_element_exits_nonzero(self):
        code, out = _run(["region", "no-such-element-id"])
        self.assertEqual(code, 1)
        self.assertIn('"error"', out)

    def test_region_on_a_real_element_still_exits_zero(self):
        code, out = _run(["region", self.real_element_id])
        self.assertEqual(code, 0)
        self.assertNotIn('"error"', out)

    def test_context_on_an_unknown_element_exits_nonzero(self):
        code, out = _run(["context", "no-such-element-id"])
        self.assertEqual(code, 1)
        self.assertIn('"error"', out)

    def test_context_on_a_real_element_still_exits_zero(self):
        code, out = _run(["context", self.real_element_id])
        self.assertEqual(code, 0)
        self.assertNotIn('"error"', out)


@requires_store
class TestSearchElementTypeNotFound(unittest.TestCase):
    """`--element-type` has no argparse `choices=` -- the real vocabulary is
    whatever `extract.py` has actually assigned, the same reason `fetch
    --subset` validates against the fetched manifest rather than a list
    hardcoded in the CLI. Validated against `retrieval_units`, the table the
    filter is actually applied to (`retrieval.FILTER_COLUMNS["element_type"]
    == "u.element_type"`) -- NOT `elements`, the canonical table: `heading`
    and `figure` are real `elements.element_type` values that are
    structurally excluded from `retrieval_units` (`store.
    UNIT_EXCLUDED_TYPES`, and figures carry no unit at all), so validating
    against `elements` would let both through and then return `[]` forever,
    for every query -- the exact silent-forever-empty failure this fix
    exists to remove, just moved one column over."""

    @classmethod
    def setUpClass(cls):
        from fence_evidence.store import connect
        cls.conn = connect()
        row = cls.conn.execute(
            "SELECT element_type FROM retrieval_units LIMIT 1").fetchone()
        if row is None:
            raise unittest.SkipTest("store has no retrieval units")
        cls.real_type = row[0]

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_an_unknown_element_type_exits_nonzero(self):
        code, out = _run(["search", "footing depth", "--element-type", "no-such-type"])
        self.assertEqual(code, 2)
        self.assertIn('"error"', out)

    def test_heading_is_a_real_element_type_but_never_a_search_filter(self):
        """`heading` is a genuine `elements.element_type` value -- validating
        against `elements` would have accepted it and then matched nothing,
        for any query, forever. It must be refused up front instead."""
        code, out = _run(["search", "footing depth", "--element-type", "heading"])
        self.assertEqual(code, 2)
        self.assertIn('"error"', out)

    def test_figure_is_also_a_real_element_type_but_never_a_search_filter(self):
        code, out = _run(["search", "footing depth", "--element-type", "figure"])
        self.assertEqual(code, 2)
        self.assertIn('"error"', out)

    def test_a_real_element_type_with_no_hits_still_exits_zero(self):
        """A known, searchable type that this particular query does not
        match is a normal empty result, not a bad-input error."""
        code, out = _run(["search", "zzzzznonexistentqueryzzzzz",
                          "--element-type", self.real_type])
        self.assertEqual(code, 0)
        self.assertNotIn('"error"', out)


if __name__ == "__main__":
    unittest.main()
