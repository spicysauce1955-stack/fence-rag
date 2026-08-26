"""Every reference points DOWN a layer, never up.

A row may name the thing it was derived FROM. It may never name the thing that
was derived from IT. Stated as a layering:

    L5 published  ──▶ L2 elements        (SourceRef)
    L4 entities   ──▶ L2 elements        (component sources)
    L3 facts      ──▶ L2 elements        (facts.element_id)
    L2 elements   ──▶ L2 pages ──▶ documents

Why it is a rule and not a preference: an upward pointer has to be maintained by
hand. `table_read_candidates.promoted_fact_id` pointed up, and it cost two things
that both disappear when it is inverted --

  * `revoke_machine_promotions` had to NULL it out after deleting a fact, or
    leave a dangling id behind;
  * `tests/test_facts.py` carried a test asserting no dangling ids survive a
    re-extraction, which is a test for a bug the schema should not permit.

A downward pointer is enforceable as a real foreign key and needs neither.
"""
import unittest

import context  # noqa: F401  -- puts the repo root on sys.path
from context import requires_store
from fence_evidence.store import RETIRED_COLUMNS, SCHEMA, connect


class TestSchemaDirection(unittest.TestCase):
    def _block(self, table):
        """The CREATE TABLE body for one table, comments and all."""
        start = SCHEMA.index(f"CREATE TABLE IF NOT EXISTS {table} (")
        return SCHEMA[start:SCHEMA.index(");", start)]

    def test_facts_names_the_candidate_it_came_from(self):
        self.assertIn("from_candidate_id", self._block("facts"),
                      "a promoted fact must name the reading it was derived from")

    def test_candidates_do_not_name_the_fact_they_produced(self):
        # Scoped to the table's own block: the word still appears in `facts`,
        # in the comment explaining why it moved.
        self.assertNotIn("promoted_fact_id", self._block("table_read_candidates"),
                         "a reading must not point at a row derived from it")

    def test_the_retirement_is_declared(self):
        retired = {(t, c) for t, c, _ in RETIRED_COLUMNS}
        self.assertIn(("table_read_candidates", "promoted_fact_id"), retired)


@requires_store
class TestLiveStoreDirection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = connect()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def _cols(self, table):
        return {r[1] for r in self.conn.execute(f"PRAGMA table_info({table})")}

    def test_the_upward_pointer_is_gone_from_the_store(self):
        self.assertNotIn("promoted_fact_id", self._cols("table_read_candidates"))

    def test_the_downward_pointer_is_present(self):
        self.assertIn("from_candidate_id", self._cols("facts"))

    def test_it_is_a_real_foreign_key_now(self):
        """The point of pointing down: the database can enforce it."""
        fks = [r for r in self.conn.execute("PRAGMA foreign_key_list(facts)")]
        targets = {(r[2], r[3], r[4]) for r in fks}   # table, from, to
        self.assertIn(("table_read_candidates", "from_candidate_id", "candidate_id"),
                      targets, "from_candidate_id should be a declared FK, not a soft link")

    def test_no_fact_names_a_candidate_that_does_not_exist(self):
        n = self.conn.execute("""SELECT COUNT(*) FROM facts f
             LEFT JOIN table_read_candidates c ON c.candidate_id = f.from_candidate_id
            WHERE f.from_candidate_id IS NOT NULL AND c.candidate_id IS NULL""").fetchone()[0]
        self.assertEqual(n, 0)


if __name__ == "__main__":
    unittest.main()
