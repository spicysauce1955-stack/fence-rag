"""R3 and R5 — spending the k result slots on distinct evidence.

`workspace/reports/projection-relevance-audit.md` measured two ways a ten-result
list wastes its slots: F2, text that duplicates another unit's, and F3, a second
or third unit from a page already in the list. R3 and R5 are the audit's
recommendations against them. Both were measured over the gold set (G64): **R3
is on by default** and R5 is not, and these tests pin that decision rather than
leaving it to a comment.

The filters run over the ranked rows before the result objects are built, so a
suppressed row is *backfilled* by the next-best row. Backfill is bounded by the
over-fetched pool, not guaranteed: where the pool holds fewer than k distinct
records the list is genuinely shorter, because there was no k-th distinct thing
to show. `test_a_short_list_means_the_pool_ran_out` covers that case.
"""
import json
import sqlite3
import unittest

from context import requires_store  # noqa: F401
from fence_evidence.retrieval import _slot_filtered, search_evidence
from fence_evidence.store import connect


def rows(*items) -> list[sqlite3.Row]:
    """Real `sqlite3.Row`s in rank order, so the filter is tested on the shape
    it actually receives from `search_evidence` rather than on a stand-in.

    Each item is `(text, document_id, page_no)` or, where the heading matters,
    `(text, document_id, page_no, heading_path)`.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE r(ord INTEGER, text TEXT, document_id TEXT, "
                 "page_no INTEGER, heading_path TEXT)")
    conn.executemany("INSERT INTO r VALUES (?,?,?,?,?)",
                     [(i, it[0], it[1], it[2],
                       json.dumps(it[3]) if len(it) > 3 else "[]")
                      for i, it in enumerate(items)])
    return conn.execute("SELECT * FROM r ORDER BY ord").fetchall()


class TestSlotFilters(unittest.TestCase):
    def test_both_filters_off_only_truncates(self):
        got, _links = _slot_filtered(rows(("a", "d1", 1), ("a", "d1", 1), ("b", "d1", 2)),
                             limit=2, dedupe_text=False, page_cap=None)
        self.assertEqual([r["text"] for r in got], ["a", "a"])

    def test_dedupe_keeps_the_highest_ranked_member_of_a_group(self):
        got, _links = _slot_filtered(rows(("keep", "d1", 1), ("keep", "d2", 9)),
                             limit=10, dedupe_text=True, page_cap=None)
        self.assertEqual([(r["document_id"], r["page_no"]) for r in got], [("d1", 1)])

    def test_dedupe_backfills_the_freed_slot(self):
        got, _links = _slot_filtered(rows(("a", "d1", 1), ("a", "d2", 2), ("b", "d3", 3)),
                             limit=2, dedupe_text=True, page_cap=None)
        self.assertEqual([r["text"] for r in got], ["a", "b"],
                         "a suppressed duplicate must be replaced by the next-best row, "
                         "not leave the list one short")

    def test_dedupe_ignores_case_and_whitespace(self):
        got, _links = _slot_filtered(rows(("1. None.", "d1", 1), ("1.  none.\n", "d2", 2)),
                             limit=10, dedupe_text=True, page_cap=None)
        self.assertEqual(len(got), 1)

    def test_two_units_with_the_same_text_under_different_headings_are_not_duplicates(self):
        """The defect this key was written wrong for the first time.

        `evaluate._returned_evidence` measures support over the whole returned
        record — `text` AND `heading_path` — because in this corpus the
        condition a table row applies under is printed in the heading, not in
        the row. A key over `text` alone therefore discards real evidence and
        calls it a duplicate. Measured on the live store before the fix:
        `gq-010` lost the answer term `130MPH WIND` this way, and 11 of the 78
        gold questions lost at least one `heading_path` the raw list carried.
        """
        got, _links = _slot_filtered(
            rows(("HEIGHT OF THE PANEL (in)\n≤42\n48", "d1", 4,
                  ["Tesco", "GOVERNING LOAD", "130MPH WIND-EXPOSURE D"]),
                 ("HEIGHT OF THE PANEL (in)\n≤42\n48", "d1", 5,
                  ["Tesco", "GOVERNING LOAD", "120MPH WIND-EXPOSURE D"])),
            limit=10, dedupe_text=True, page_cap=None)
        self.assertEqual(len(got), 2,
                         "identical rows under different governing loads are two "
                         "different facts, not one fact twice")

    def test_the_same_text_under_the_same_heading_is_still_a_duplicate(self):
        got, _links = _slot_filtered(rows(("1. None.", "d1", 4, ["Evidence Submitted"]),
                                  ("1. None.", "d2", 9, ["Evidence Submitted"])),
                             limit=10, dedupe_text=True, page_cap=None)
        self.assertEqual(len(got), 1)

    def test_dedupe_never_collapses_empty_text(self):
        got, _links = _slot_filtered(rows(("", "d1", 1), ("", "d2", 2)),
                             limit=10, dedupe_text=True, page_cap=None)
        self.assertEqual(len(got), 2,
                         "an empty unit is not evidence that another unit is a duplicate")

    def test_page_cap_of_one_keeps_one_unit_per_page(self):
        got, _links = _slot_filtered(rows(("a", "d1", 1), ("b", "d1", 1), ("c", "d1", 2)),
                             limit=10, dedupe_text=False, page_cap=1)
        self.assertEqual([r["text"] for r in got], ["a", "c"])

    def test_page_cap_of_two_keeps_two(self):
        got, _links = _slot_filtered(rows(("a", "d1", 1), ("b", "d1", 1), ("c", "d1", 1)),
                             limit=10, dedupe_text=False, page_cap=2)
        self.assertEqual([r["text"] for r in got], ["a", "b"])

    def test_page_cap_is_scoped_to_the_document(self):
        got, _links = _slot_filtered(rows(("a", "d1", 1), ("b", "d2", 1)),
                             limit=10, dedupe_text=False, page_cap=1)
        self.assertEqual(len(got), 2,
                         "page 1 of two different documents is two different pages")

    def test_a_suppressed_duplicate_does_not_spend_its_page_quota(self):
        """The two filters compose without one paying the other's cost.

        Row 2 repeats row 1's text and is dropped, so page 2 has still returned
        nothing and row 3 — the first real evidence on that page — is kept. If a
        suppressed row consumed the quota, R3 would silently cost a page.
        """
        got, _links = _slot_filtered(rows(("a", "d1", 1), ("a", "d1", 2), ("b", "d1", 2),
                                  ("c", "d1", 3)),
                             limit=10, dedupe_text=True, page_cap=1)
        self.assertEqual([r["text"] for r in got], ["a", "b", "c"])

    def test_filters_compose(self):
        got, _links = _slot_filtered(rows(("a", "d1", 1), ("b", "d1", 1), ("a", "d2", 5),
                                  ("c", "d3", 7)),
                             limit=10, dedupe_text=True, page_cap=1)
        self.assertEqual([r["text"] for r in got], ["a", "c"],
                         "'b' is capped out by page (d1,1); the second 'a' is a duplicate")

    def test_a_suppressed_duplicate_is_linked_not_lost(self):
        """The audit specifies R3 as "collapse ... to one unit, LINKING the
        others". The linking half is not decoration: two rows sharing a key
        still differ in `document_id`, `source_path`, `page` and `bbox`, which
        is the entire product of this platform. Measured on the live store
        before this: R3 removed 8 genuinely distinct documents (not
        `same_content_as` twins) from the gold set's top-10 lists — among them
        the weatherables 2-rail and 4-rail installation guides, dropped because
        the 3-rail guide shares their text and outranked them.
        """
        kept, links = _slot_filtered(
            rows(("shared boilerplate", "d1", 1), ("shared boilerplate", "d2", 7),
                 ("other", "d3", 2)),
            limit=10, dedupe_text=True, page_cap=None)
        self.assertEqual([r["document_id"] for r in kept], ["d1", "d3"])
        self.assertEqual([[(x["document_id"], x["page_no"]) for x in group]
                          for group in links],
                         [[("d2", 7)], []],
                         "the row that lost the slot must still be reachable "
                         "through the row that took it")

    def test_nothing_is_linked_when_nothing_is_suppressed(self):
        kept, links = _slot_filtered(rows(("a", "d1", 1), ("b", "d2", 2)),
                                     limit=10, dedupe_text=True, page_cap=None)
        self.assertEqual(links, [[], []])

    def test_rank_order_is_preserved(self):
        got, _links = _slot_filtered(rows(("a", "d1", 1), ("b", "d2", 2), ("c", "d3", 3)),
                             limit=3, dedupe_text=True, page_cap=1)
        self.assertEqual([r["text"] for r in got], ["a", "b", "c"])


def _returned(r) -> str:
    """What the caller actually receives, the way `evaluate._returned_evidence`
    counts it: the text and the heading path together."""
    return (" ".join((r.text or "").split()).lower() + "\x00"
            + " ".join(" > ".join(r.heading_path or []).split()).lower())


QUERIES = [
    "footing depth exposure C Chesterfield",
    "post spacing 130 mph wind",
    "evidence submitted none",
    "rebar hinge gate post",
    "racking slope stepping hillside",
]


@requires_store
class TestAgainstTheStore(unittest.TestCase):
    """R3 on, R5 off — and the properties that justify that split."""

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

    def test_dedupe_never_drops_evidence_the_raw_list_carried(self):
        """Why the default is safe: R3 replaces a slot, it never removes evidence.

        A suppressed row's record is by construction still in the list through
        the row that kept it, and the backfilled row can only add. So the
        distinct evidence returned with R3 on is a superset of the evidence
        returned with it off.

        This must compare what `evaluate._returned_evidence` measures, not
        `r.text`. Comparing `r.text` alone made this assertion near-tautological
        — the first dedupe key was over `r.text` too, so the test could not see
        that the heading half was being discarded. It is the reason that defect
        reached a commit.
        """
        for q in QUERIES + ["governing load 130 mph wind exposure D panel height"]:
            raw = search_evidence(q, limit=10, conn=self.conn, dedupe_text=False)
            got = search_evidence(q, limit=10, conn=self.conn, dedupe_text=True)
            before = {_returned(r) for r in raw}
            after = {_returned(r) for r in got}
            self.assertTrue(before <= after,
                            f"{q!r} lost {sorted(before - after)[:1]}")

    def test_dedupe_leaves_no_repeated_record_in_a_list(self):
        """Records, not texts. Two rows with the same text under different
        headings are different evidence and both belong in the list."""
        for q in QUERIES:
            got = search_evidence(q, limit=10, conn=self.conn, dedupe_text=True)
            keys = [_returned(r) for r in got]
            self.assertEqual(len(keys), len(set(keys)), q)

    def test_page_cap_leaves_no_repeated_page_in_a_list(self):
        for q in QUERIES:
            got = search_evidence(q, limit=10, conn=self.conn, page_cap=1)
            pages = [(r.document_id, r.page) for r in got]
            self.assertEqual(len(pages), len(set(pages)), q)

    def test_a_filtered_list_is_not_shorter_than_the_unfiltered_one(self):
        """Backfill, measured against the real index rather than asserted.

        The baseline must be taken with the filters OFF. Read from the default
        it would compare R3 against itself and could not fail.
        """
        for q in QUERIES:
            base = search_evidence(q, limit=10, conn=self.conn,
                                   dedupe_text=False, page_cap=None)
            for kwargs in ({"dedupe_text": True}, {"page_cap": 1},
                           {"dedupe_text": True, "page_cap": 1}):
                got = search_evidence(q, limit=10, conn=self.conn, **kwargs)
                self.assertEqual(len(got), len(base), f"{q!r} with {kwargs}")

    def test_a_short_list_means_the_pool_ran_out(self):
        """Backfill is bounded by the over-fetched pool, and where a query has
        fewer than k distinct records to show, the list is shorter. That is the
        honest answer, not a bug — but it is real, so it is pinned here rather
        than claimed away in a docstring."""
        one_noa = {"source_path_prefix": "manuals/certainteed-bufftech/structural/"}
        raw = search_evidence("none", limit=10, conn=self.conn, filters=one_noa,
                              dedupe_text=False)
        got = search_evidence("none", limit=10, conn=self.conn, filters=one_noa)
        self.assertLessEqual(len(got), len(raw))
        self.assertEqual(len({_returned(r) for r in got}), len(got),
                         "whatever its length, the list holds no duplicate record")

    def test_filtering_does_not_reorder_what_it_keeps(self):
        for q in QUERIES:
            base = search_evidence(q, limit=10, conn=self.conn)
            got = search_evidence(q, limit=10, conn=self.conn, dedupe_text=True, page_cap=1)
            kept = [r.element_id for r in got if r.element_id in {b.element_id for b in base}]
            order = [b.element_id for b in base if b.element_id in {r.element_id for r in got}]
            self.assertEqual(kept, order, q)


if __name__ == "__main__":
    unittest.main()
