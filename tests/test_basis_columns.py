"""A2 and A3 — condition_basis, and the disagreeing second unit.

Build-plan A2 (obligation 15) and A3 (obligation 4), designed together because
they land on the same table. The store-level invariants at the bottom are the
ones that must keep holding after any later change to the extractor.
"""
import json
import unittest

import context  # noqa: F401  -- puts the repo root on sys.path
from context import requires_store
from fence_evidence.facts import CONDITION_BASIS, dual_units
from fence_evidence.store import connect


class TestDualUnits(unittest.TestCase):
    """A3: `4 inch (101 mm)` states two units and they disagree by 0.6 mm."""

    def test_finds_a_disagreeing_pair(self):
        alt = dual_units('the rail is 4 inch (101 mm) deep')
        self.assertIsNotNone(alt)
        self.assertEqual(alt["value_original"], "101 mm")
        self.assertEqual(alt["unit_original"], "mm")
        self.assertEqual(alt["value_normalized"], 101.0)

    def test_records_the_verbatim_lexeme_not_a_rounded_number(self):
        """Obligation 4: every verbatim source lexeme, alongside."""
        alt = dual_units('3-1/4 inch (83 mm)')
        self.assertEqual(alt["value_original"], "83 mm",
                         "the source's own words, not our arithmetic")

    def test_an_agreeing_pair_is_still_recorded(self):
        """Both lexemes cross whether or not they disagree; §4 says publish both."""
        alt = dual_units('2 inch (50.8 mm)')
        self.assertIsNotNone(alt, "an agreeing second unit is still a second lexeme")

    def test_no_second_unit_is_none(self):
        self.assertIsNone(dual_units('the rail is 4 inch deep'))
        self.assertIsNone(dual_units(''))
        self.assertIsNone(dual_units('post spacing 96 1/8"'))

    def test_a_parenthetical_that_is_not_a_unit_is_ignored(self):
        self.assertIsNone(dual_units('4 inch (see detail A)'))
        self.assertIsNone(dual_units('4 inch (typical)'))


class TestConditionBasisVocabulary(unittest.TestCase):
    def test_the_three_values(self):
        self.assertEqual(set(CONDITION_BASIS), {"stated", "assumed", "unexamined"})

    def test_unexamined_publishes_as_assumed(self):
        """The contract's enum is stated|assumed. `unexamined` is ours, and it
        must collapse rather than leak across the boundary."""
        from fence_evidence.facts import publish_condition_basis
        self.assertEqual(publish_condition_basis("unexamined"), "assumed")
        self.assertEqual(publish_condition_basis("assumed"), "assumed")
        self.assertEqual(publish_condition_basis("stated"), "stated")


@requires_store
class TestStoreInvariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = connect()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_no_underscore_key_survives_in_conditions(self):
        """A2: `conditions` publishes as condition dimensions under §1.3.

        An explanatory note in there is published as something Planning can bind
        a plan against. That was the defect; this is the guard.
        """
        bad = []
        for r in self.conn.execute("SELECT fact_id, conditions FROM facts"):
            for key in json.loads(r["conditions"] or "{}"):
                if key.startswith("_"):
                    bad.append((r["fact_id"], key))
        self.assertEqual(bad, [], "an underscore-prefixed key is inside `conditions`")

    def test_every_fact_states_its_condition_basis(self):
        n = self.conn.execute(
            "SELECT COUNT(*) FROM facts WHERE condition_basis IS NULL "
            "OR condition_basis NOT IN ('stated','assumed','unexamined')").fetchone()[0]
        self.assertEqual(n, 0, "a fact does not say where its conditions came from")

    def test_a_fact_with_conditions_is_not_marked_unexamined(self):
        """If conditions are attached, somebody or something examined them."""
        n = self.conn.execute("""SELECT COUNT(*) FROM facts
             WHERE condition_basis='unexamined' AND conditions NOT IN ('{}','')
        """).fetchone()[0]
        self.assertEqual(n, 0)

    def test_an_empty_condition_set_is_never_claimed_as_stated(self):
        """`stated` + empty means the document explicitly gave none — a fallback
        row. Nothing in this store has established that, so nothing may claim it."""
        n = self.conn.execute("""SELECT COUNT(*) FROM facts
             WHERE condition_basis='stated' AND conditions IN ('{}','')""").fetchone()[0]
        self.assertEqual(n, 0)

    def test_value_alternates_is_valid_json_when_present(self):
        for r in self.conn.execute(
                "SELECT fact_id, value_alternates FROM facts WHERE value_alternates IS NOT NULL"):
            alts = json.loads(r["value_alternates"])
            self.assertIsInstance(alts, list)
            for a in alts:
                self.assertIn("value_original", a)
                self.assertIn("unit_original", a)

    def test_every_element_carries_a_language_and_its_basis(self):
        n = self.conn.execute(
            "SELECT COUNT(*) FROM elements WHERE lang IS NULL OR lang_basis IS NULL").fetchone()[0]
        self.assertEqual(n, 0, "an element has no language tag")

    def test_no_element_claims_a_measured_language(self):
        """Obligation 10 is about the honesty of the claim, not the presence of
        a value. Nothing here can measure a language."""
        n = self.conn.execute(
            "SELECT COUNT(*) FROM elements WHERE lang_basis='measured'").fetchone()[0]
        self.assertEqual(n, 0)

    def test_language_is_not_derived_from_corpus_track(self):
        """The shortcut this design exists to refuse: China track != Chinese.

        Every China-track element measured as English. If a later change starts
        reading `lang` off the track, this fails.
        """
        zh_on_china = self.conn.execute("""SELECT COUNT(*) FROM elements e
             JOIN documents d ON d.document_id = e.document_id
            WHERE d.corpus_track='china' AND e.lang='zh'""").fetchone()[0]
        self.assertEqual(zh_on_china, 0,
                         "an element was tagged zh; measured, this corpus has no CJK")


@requires_store
class TestPromotionWritesTheBasis(unittest.TestCase):
    """The promotion path is the ONE place where the basis is genuinely `stated`.

    A promoted fact's conditions are built from the table's own row and column
    labels -- the document laid them out in a grid, which is as stated as a
    condition gets. Defaulting them to `unexamined` (publishing as `assumed`)
    inverts obligation 15 for the most reliable facts in the store, and does it
    silently, because the column has a DEFAULT.
    """

    @classmethod
    def setUpClass(cls):
        import shutil
        from context import store_snapshot
        from fence_evidence.store import connect as _c
        cls.snapshot = store_snapshot()
        cls._rm = shutil.rmtree
        cls.conn = _c(cls.snapshot)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        cls._rm(cls.snapshot.parent, ignore_errors=True)

    def _accept_one(self):
        """Mark a real cross-family reading as human-accepted, the way a
        reviewer eventually will."""
        row = self.conn.execute("""SELECT candidate_id FROM table_read_candidates
             WHERE review_status='cross_family_verified' AND row_index >= 0
             ORDER BY candidate_id LIMIT 1""").fetchone()
        if row is None:
            self.skipTest("no candidate readings in this store")
        self.conn.execute("""UPDATE table_read_candidates
             SET review_status='accepted', reviewer='test-reviewer'
             WHERE candidate_id=?""", (row["candidate_id"],))
        self.conn.commit()
        return row["candidate_id"]

    def test_promote_records_a_stated_basis(self):
        from fence_evidence.table_review import promote
        cid = self._accept_one()
        fact_id = promote(self.conn, cid, fact_type="footing_depth_in",
                          reviewer="test-reviewer")
        row = self.conn.execute("SELECT condition_basis, conditions FROM facts "
                                "WHERE fact_id=?", (fact_id,)).fetchone()
        self.assertIsNotNone(row["condition_basis"])
        self.assertNotEqual(row["condition_basis"], "unexamined",
                            "a promoted fact's conditions came off a printed grid; "
                            "calling that 'nobody looked' is false")

    def test_promote_verified_never_writes_an_underscore_key(self):
        """A2's writer half. The rows were cleaned; this is the thing that
        re-creates them the moment review starts promoting."""
        from fence_evidence.promote_tables import promote_verified
        self.conn.execute("""UPDATE table_read_candidates SET review_status='accepted'
             WHERE review_status='cross_family_verified'""")
        self.conn.commit()
        promote_verified(self.conn)
        bad = []
        for r in self.conn.execute(
                "SELECT fact_id, conditions FROM facts WHERE extractor LIKE 'table-read%'"):
            for key in json.loads(r["conditions"] or "{}"):
                if key.startswith("_"):
                    bad.append((r["fact_id"], key))
        self.assertEqual(bad, [], "promotion put an underscore key back into `conditions`")

    def test_promote_verified_states_its_basis(self):
        from fence_evidence.promote_tables import promote_verified
        self.conn.execute("""UPDATE table_read_candidates SET review_status='accepted'
             WHERE review_status='cross_family_verified'""")
        self.conn.commit()
        promote_verified(self.conn)
        n = self.conn.execute("""SELECT COUNT(*) FROM facts
             WHERE extractor LIKE 'table-read%'
               AND (condition_basis IS NULL OR condition_basis='unexamined')""").fetchone()[0]
        self.assertEqual(n, 0, "a promoted fact does not state where its conditions came from")

    def test_the_applicability_note_survives_somewhere(self):
        """Moving it out of `conditions` must not mean losing it -- it records
        that the readers disagreed on the bracket, which a reviewer needs."""
        from fence_evidence.promote_tables import promote_verified
        self.conn.execute("""UPDATE table_read_candidates SET review_status='accepted'
             WHERE review_status='cross_family_verified'""")
        self.conn.commit()
        promote_verified(self.conn)
        n = self.conn.execute("""SELECT COUNT(*) FROM facts
             WHERE extractor LIKE 'table-read%' AND condition_basis_note IS NOT NULL
        """).fetchone()[0]
        self.assertGreater(n, 0, "the applicability reasoning was dropped, not moved")


if __name__ == "__main__":
    unittest.main()
