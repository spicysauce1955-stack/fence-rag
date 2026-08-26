"""Promotion attaches row conditions, and fails closed on applicability."""
import json
import unittest

import shutil

from context import requires_store, store_snapshot
from fence_evidence.promote_tables import (_inches, _match, KEY_COLUMNS,
                                           VALUE_COLUMNS, hvhz_for_exposure)
from fence_evidence.table_review import PROMOTABLE
from fence_evidence.store import connect


class TestColumnMapping(unittest.TestCase):
    def test_value_columns(self):
        self.assertEqual(_match("FOOTING DEPTH", VALUE_COLUMNS), "footing_depth_in")
        self.assertEqual(_match("Max. Post Spacing", VALUE_COLUMNS), "post_spacing_in")
        self.assertEqual(_match("Min. Footing Req'd Diameter", VALUE_COLUMNS),
                         "footing_diameter_in")

    def test_key_columns_are_conditions_not_values(self):
        self.assertEqual(_match("WIND EXPOSURE", KEY_COLUMNS), "exposure_category")
        self.assertIsNone(_match("WIND EXPOSURE", VALUE_COLUMNS))

    def test_fractions(self):
        self.assertEqual(_inches('96 1/8"'), 96.125)
        self.assertEqual(_inches('30"'), 30.0)
        self.assertIsNone(_inches(""))


class TestApplicabilityFailsClosed(unittest.TestCase):
    def test_reads_a_clear_bracket(self):
        note = "NON HVHZ spans the two B rows; HVHZ AND NON HVHZ spans the two C rows."
        self.assertEqual(hvhz_for_exposure(note, "B"), "non-HVHZ only")
        self.assertEqual(hvhz_for_exposure(note, "C"), "HVHZ and non-HVHZ")

    def test_absent_bracket_is_none_not_a_guess(self):
        self.assertIsNone(hvhz_for_exposure("Table 1 values as printed.", "B"))
        self.assertIsNone(hvhz_for_exposure("", "B"))

    def test_ambiguous_note_is_none(self):
        note = "B rows NON HVHZ. Elsewhere B rows are HVHZ AND NON HVHZ."
        self.assertIsNone(hvhz_for_exposure(note, "B"))

    def test_unknown_exposure_letter(self):
        self.assertIsNone(hvhz_for_exposure("NON HVHZ for the B rows", "Z"))


@requires_store
class TestPromotedFacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = connect()
        cls.rows = cls.conn.execute(
            "SELECT * FROM facts WHERE extractor LIKE 'table-read%'").fetchall()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_facts_exist(self):
        if not self.rows:
            self.skipTest("no table readings promoted yet")
        self.assertGreater(len(self.rows), 0)

    def test_every_promoted_fact_carries_its_row_conditions(self):
        if not self.rows:
            self.skipTest("no table readings promoted yet")
        for r in self.rows:
            cond = json.loads(r["conditions"])
            self.assertIn("hvhz_applicability", cond,
                          "a conditional value was promoted without an applicability field")
            self.assertTrue(cond.get("exposure_category") or cond.get("fence_height"),
                            "promoted without the key column that scopes it")

    def test_no_fact_was_promoted_without_a_person(self):
        """Obligation 6: nothing reaches level 2 that no person compared to the crop.

        Machine agreement ranks the review queue; it never clears it. A fact
        naming a candidate that carries a machine-only status is the defect A1
        closed, and this is the assertion that keeps it closed.

        Note the direction: the join starts at `facts`, because that is the side
        holding the pointer -- see tests/test_pointer_direction.py.
        """
        machine = self.conn.execute(f"""
            SELECT c.review_status, COUNT(*) n
              FROM facts f
              JOIN table_read_candidates c ON c.candidate_id = f.from_candidate_id
             WHERE c.review_status NOT IN ({','.join('?' * len(PROMOTABLE))})
             GROUP BY 1""", PROMOTABLE).fetchall()
        self.assertEqual([tuple(r) for r in machine], [],
                         "a reading became a fact with no person in the loop")

    def test_no_fact_carries_a_machine_only_review_status(self):
        orphans = self.conn.execute(
            "SELECT COUNT(*) FROM facts WHERE review_status IN "
            "('cross_family_verified', 'agent_verified')").fetchone()[0]
        self.assertEqual(orphans, 0,
                         "a fact is labelled with a status no person conferred")

    def test_unresolved_applicability_is_stated_not_omitted(self):
        if not self.rows:
            self.skipTest("no table readings promoted yet")
        for r in self.rows:
            cond = json.loads(r["conditions"])
            if cond["hvhz_applicability"] == "unresolved":
                # A2 moved this note OUT of `conditions` -- under §1.3 everything
                # in there publishes as a condition dimension, and a sentence
                # about readers disagreeing is not one. It lives on the fact now.
                self.assertTrue(r["condition_basis_note"],
                                "unresolved applicability with no reason recorded")

    def test_no_promoted_fact_came_from_same_family_agreement_alone(self):
        for r in self.rows:
            self.assertNotIn("agent_verified", r["extractor"])

    def test_every_promoted_fact_links_back_to_a_candidate(self):
        if not self.rows:
            self.skipTest("no table readings promoted yet")
        linked = self.conn.execute(
            "SELECT COUNT(*) FROM table_read_candidates WHERE from_candidate_id IS NOT NULL"
        ).fetchone()[0]
        self.assertEqual(linked, len(self.rows))

    def test_the_row_that_broke_the_curated_dataset_is_right(self):
        """Exposure B / 24in / 66in must be non-HVHZ only, not both."""
        rows = self.conn.execute("""SELECT conditions, value_original FROM facts
            WHERE extractor LIKE 'table-read%' AND fact_type='footing_depth_in'
              AND value_original LIKE '24%'
              AND json_extract(conditions,'$.exposure_category')='B'""").fetchall()
        if not rows:
            self.skipTest("that row has not been promoted")
        for r in rows:
            app = json.loads(r["conditions"])["hvhz_applicability"]
            self.assertNotEqual(app, "HVHZ and non-HVHZ",
                                "the Exposure B 24-inch row was promoted as HVHZ-applicable, "
                                "which is the error the curated dataset made")


@requires_store
class TestRevokeMachinePromotions(unittest.TestCase):
    """A1: un-promote what the old gate let through, without losing the reading."""

    @classmethod
    def setUpClass(cls):
        cls.snapshot = store_snapshot()
        cls.conn = connect(cls.snapshot)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        shutil.rmtree(cls.snapshot.parent, ignore_errors=True)

    def test_revokes_facts_but_keeps_the_readings(self):
        from fence_evidence.promote_tables import revoke_machine_promotions
        before = self.conn.execute(
            "SELECT COUNT(*) FROM table_read_candidates").fetchone()[0]
        crops = self.conn.execute(
            "SELECT COUNT(*) FROM table_read_candidates WHERE crop_sha256 IS NOT NULL"
        ).fetchone()[0]

        out = revoke_machine_promotions(self.conn)

        self.assertEqual(out["facts_deleted"], out["candidates_reset"])
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM table_read_candidates").fetchone()[0],
            before, "revocation destroyed readings; it must only un-promote them")
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM table_read_candidates "
                              "WHERE crop_sha256 IS NOT NULL").fetchone()[0],
            crops, "revocation dropped the crop evidence the review queue needs")
        left = self.conn.execute(
            "SELECT COUNT(*) FROM facts f "
            "JOIN table_read_candidates c ON c.candidate_id = f.from_candidate_id "
            "WHERE c.review_status NOT IN ('accepted','corrected')").fetchone()[0]
        self.assertEqual(left, 0)

    def test_is_idempotent(self):
        from fence_evidence.promote_tables import revoke_machine_promotions
        revoke_machine_promotions(self.conn)
        again = revoke_machine_promotions(self.conn)
        self.assertEqual(again["facts_deleted"], 0)

    def test_dry_run_changes_nothing(self):
        from fence_evidence.promote_tables import revoke_machine_promotions
        n = self.conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        revoke_machine_promotions(self.conn, dry_run=True)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0], n)


if __name__ == "__main__":
    unittest.main()
