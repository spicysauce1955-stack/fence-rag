"""R3 and R5 — spending the k result slots on distinct evidence.

`workspace/reports/projection-relevance-audit.md` measured two ways a ten-result
list wastes its slots: F2, text that duplicates another unit's, and F3, a second
or third unit from a page already in the list. R3 and R5 are the audit's
recommendations against them, and both are **off by default** — they change what
a search returns, so they publish nothing until measurement says they should.

The filters run over the ranked rows before the result objects are built, so a
suppressed row is *backfilled* by the next-best row rather than leaving a short
list. That backfill is the whole point: dropping a redundant slot without
refilling it would trade redundancy for a shorter list, not for better evidence.
"""
import sqlite3
import unittest

from context import requires_store  # noqa: F401
from fence_evidence.retrieval import _slot_filtered, search_evidence
from fence_evidence.store import connect


def rows(*triples) -> list[sqlite3.Row]:
    """Real `sqlite3.Row`s in rank order, so the filter is tested on the shape
    it actually receives from `search_evidence` rather than on a stand-in."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE r(ord INTEGER, text TEXT, document_id TEXT, page_no INTEGER)")
    conn.executemany("INSERT INTO r VALUES (?,?,?,?)",
                     [(i, t, d, p) for i, (t, d, p) in enumerate(triples)])
    return conn.execute("SELECT * FROM r ORDER BY ord").fetchall()


class TestSlotFilters(unittest.TestCase):
    def test_both_filters_off_only_truncates(self):
        got = _slot_filtered(rows(("a", "d1", 1), ("a", "d1", 1), ("b", "d1", 2)),
                             limit=2, dedupe_text=False, page_cap=None)
        self.assertEqual([r["text"] for r in got], ["a", "a"])

    def test_dedupe_keeps_the_highest_ranked_member_of_a_group(self):
        got = _slot_filtered(rows(("keep", "d1", 1), ("keep", "d2", 9)),
                             limit=10, dedupe_text=True, page_cap=None)
        self.assertEqual([(r["document_id"], r["page_no"]) for r in got], [("d1", 1)])

    def test_dedupe_backfills_the_freed_slot(self):
        got = _slot_filtered(rows(("a", "d1", 1), ("a", "d2", 2), ("b", "d3", 3)),
                             limit=2, dedupe_text=True, page_cap=None)
        self.assertEqual([r["text"] for r in got], ["a", "b"],
                         "a suppressed duplicate must be replaced by the next-best row, "
                         "not leave the list one short")

    def test_dedupe_ignores_case_and_whitespace(self):
        got = _slot_filtered(rows(("1. None.", "d1", 1), ("1.  none.\n", "d2", 2)),
                             limit=10, dedupe_text=True, page_cap=None)
        self.assertEqual(len(got), 1)

    def test_dedupe_never_collapses_empty_text(self):
        got = _slot_filtered(rows(("", "d1", 1), ("", "d2", 2)),
                             limit=10, dedupe_text=True, page_cap=None)
        self.assertEqual(len(got), 2,
                         "an empty unit is not evidence that another unit is a duplicate")

    def test_page_cap_of_one_keeps_one_unit_per_page(self):
        got = _slot_filtered(rows(("a", "d1", 1), ("b", "d1", 1), ("c", "d1", 2)),
                             limit=10, dedupe_text=False, page_cap=1)
        self.assertEqual([r["text"] for r in got], ["a", "c"])

    def test_page_cap_of_two_keeps_two(self):
        got = _slot_filtered(rows(("a", "d1", 1), ("b", "d1", 1), ("c", "d1", 1)),
                             limit=10, dedupe_text=False, page_cap=2)
        self.assertEqual([r["text"] for r in got], ["a", "b"])

    def test_page_cap_is_scoped_to_the_document(self):
        got = _slot_filtered(rows(("a", "d1", 1), ("b", "d2", 1)),
                             limit=10, dedupe_text=False, page_cap=1)
        self.assertEqual(len(got), 2,
                         "page 1 of two different documents is two different pages")

    def test_a_suppressed_duplicate_does_not_spend_its_page_quota(self):
        """The two filters compose without one paying the other's cost.

        Row 2 repeats row 1's text and is dropped, so page 2 has still returned
        nothing and row 3 — the first real evidence on that page — is kept. If a
        suppressed row consumed the quota, R3 would silently cost a page.
        """
        got = _slot_filtered(rows(("a", "d1", 1), ("a", "d1", 2), ("b", "d1", 2),
                                  ("c", "d1", 3)),
                             limit=10, dedupe_text=True, page_cap=1)
        self.assertEqual([r["text"] for r in got], ["a", "b", "c"])

    def test_filters_compose(self):
        got = _slot_filtered(rows(("a", "d1", 1), ("b", "d1", 1), ("a", "d2", 5),
                                  ("c", "d3", 7)),
                             limit=10, dedupe_text=True, page_cap=1)
        self.assertEqual([r["text"] for r in got], ["a", "c"],
                         "'b' is capped out by page (d1,1); the second 'a' is a duplicate")

    def test_rank_order_is_preserved(self):
        got = _slot_filtered(rows(("a", "d1", 1), ("b", "d2", 2), ("c", "d3", 3)),
                             limit=3, dedupe_text=True, page_cap=1)
        self.assertEqual([r["text"] for r in got], ["a", "b", "c"])


QUERIES = [
    "footing depth exposure C Chesterfield",
    "post spacing 130 mph wind",
    "evidence submitted none",
    "rebar hinge gate post",
    "racking slope stepping hillside",
]


@requires_store
class TestAgainstTheStore(unittest.TestCase):
    """The filters are opt-in, so the shipped behaviour must not move."""

    @classmethod
    def setUpClass(cls):
        cls.conn = connect()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_r3_is_on_by_default_and_r5_is_not(self):
        """The measured decision, asserted rather than left to a comment.

        R3 improved unit support 0.623 -> 0.650 with three questions better and
        none worse, so it ships on. R5 cost 0.040 of that support across eight
        questions to buy page diversity, so it stays a flag.
        """
        for q in QUERIES:
            default = search_evidence(q, limit=10, conn=self.conn)
            r3 = search_evidence(q, limit=10, conn=self.conn, dedupe_text=True)
            self.assertEqual([r.element_id for r in default], [r.element_id for r in r3],
                             f"R3 is meant to be the default; {q!r} disagrees")
        # R5 is not applied unless asked for: at least one gold-set query still
        # returns two units from one page, which a default cap would forbid.
        repeats = 0
        for q in QUERIES:
            pages = [(r.document_id, r.page)
                     for r in search_evidence(q, limit=10, conn=self.conn)]
            repeats += len(pages) - len(set(pages))
        self.assertGreater(repeats, 0, "a page cap appears to be on by default")

    def test_the_dedupe_default_can_be_turned_off(self):
        raw = search_evidence("evidence submitted none", limit=10, conn=self.conn,
                              dedupe_text=False)
        texts = [" ".join((r.text or "").split()).lower() for r in raw]
        self.assertGreater(len(texts), len(set(texts)),
                           "this query is the one that exhibits F2; if it no longer "
                           "repeats text with the filter off, the fixture is stale")

    def test_dedupe_never_drops_text_the_raw_list_carried(self):
        """Why the default is safe: R3 replaces a slot, it never removes evidence.

        A suppressed row's text is by construction still present in the list
        through the row that kept it, and the backfilled row can only add terms.
        So the distinct text returned with R3 on is a superset of the text
        returned with it off — which is why no gold question got worse.
        """
        for q in QUERIES:
            raw = search_evidence(q, limit=10, conn=self.conn, dedupe_text=False)
            got = search_evidence(q, limit=10, conn=self.conn, dedupe_text=True)
            before = {" ".join((r.text or "").split()).lower() for r in raw}
            after = {" ".join((r.text or "").split()).lower() for r in got}
            self.assertTrue(before <= after, f"{q!r} lost {sorted(before - after)[:2]}")

    def test_dedupe_leaves_no_repeated_text_in_a_list(self):
        for q in QUERIES:
            got = search_evidence(q, limit=10, conn=self.conn, dedupe_text=True)
            texts = [" ".join((r.text or "").split()).lower() for r in got]
            self.assertEqual(len(texts), len(set(texts)), q)

    def test_page_cap_leaves_no_repeated_page_in_a_list(self):
        for q in QUERIES:
            got = search_evidence(q, limit=10, conn=self.conn, page_cap=1)
            pages = [(r.document_id, r.page) for r in got]
            self.assertEqual(len(pages), len(set(pages)), q)

    def test_a_filtered_list_is_not_shorter_than_the_baseline(self):
        """Backfill, measured against the real index rather than asserted."""
        for q in QUERIES:
            base = search_evidence(q, limit=10, conn=self.conn)
            for kwargs in ({"dedupe_text": True}, {"page_cap": 1},
                           {"dedupe_text": True, "page_cap": 1}):
                got = search_evidence(q, limit=10, conn=self.conn, **kwargs)
                self.assertEqual(len(got), len(base), f"{q!r} with {kwargs}")

    def test_filtering_does_not_reorder_what_it_keeps(self):
        for q in QUERIES:
            base = search_evidence(q, limit=10, conn=self.conn)
            got = search_evidence(q, limit=10, conn=self.conn, dedupe_text=True, page_cap=1)
            kept = [r.element_id for r in got if r.element_id in {b.element_id for b in base}]
            order = [b.element_id for b in base if b.element_id in {r.element_id for r in got}]
            self.assertEqual(kept, order, q)


if __name__ == "__main__":
    unittest.main()
