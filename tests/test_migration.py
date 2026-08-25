"""Additive column migration — the thing `migrate()` could not do.

`migrate()` is `executescript(SCHEMA)`, which is `CREATE TABLE IF NOT EXISTS`
and nothing else. On a store that already exists, a new column in SCHEMA is a
silent no-op: the table is there, so the statement does nothing and the column
never appears. This is the fifteen lines that close that hole.
"""
import sqlite3
import unittest

import context  # noqa: F401  -- puts the repo root on sys.path
from fence_evidence.store import (ADDED_COLUMNS, SCHEMA, SCHEMA_VERSION,
                                  ensure_columns, migrate)


class TestEnsureColumns(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("CREATE TABLE widget (widget_id INTEGER PRIMARY KEY, name TEXT)")

    def tearDown(self):
        self.conn.close()

    def _cols(self, table="widget"):
        return {r[1] for r in self.conn.execute(f"PRAGMA table_info({table})")}

    def test_adds_a_missing_column(self):
        ensure_columns(self.conn, [("widget", "colour", "TEXT")])
        self.assertIn("colour", self._cols())

    def test_is_idempotent(self):
        spec = [("widget", "colour", "TEXT")]
        ensure_columns(self.conn, spec)
        self.conn.execute("INSERT INTO widget(name, colour) VALUES ('a', 'red')")
        added = ensure_columns(self.conn, spec)
        self.assertEqual(added, [], "a second run tried to add the column again")
        row = self.conn.execute("SELECT colour FROM widget").fetchone()
        self.assertEqual(row["colour"], "red", "re-running the migration lost data")

    def test_reports_what_it_added(self):
        added = ensure_columns(self.conn, [("widget", "colour", "TEXT"),
                                           ("widget", "name", "TEXT")])
        self.assertEqual(added, ["widget.colour"], "should skip the column that exists")

    def test_preserves_existing_rows(self):
        self.conn.execute("INSERT INTO widget(name) VALUES ('before')")
        ensure_columns(self.conn, [("widget", "colour", "TEXT DEFAULT 'unset'")])
        row = self.conn.execute("SELECT name, colour FROM widget").fetchone()
        self.assertEqual(row["name"], "before")
        self.assertEqual(row["colour"], "unset")

    def test_an_unknown_table_is_skipped_not_fatal(self):
        """A store predating a table should not crash the migration for it."""
        added = ensure_columns(self.conn, [("no_such_table", "x", "TEXT")])
        self.assertEqual(added, [])


class TestSchemaDeclaration(unittest.TestCase):
    def test_schema_version_moved_for_this_change(self):
        self.assertGreaterEqual(SCHEMA_VERSION, 2)

    def test_every_added_column_is_declared(self):
        """Pinned so a column cannot be added to SCHEMA without being migrated
        onto existing stores too -- the silent-no-op failure this list exists for."""
        declared = {f"{t}.{c}" for t, c, _ in ADDED_COLUMNS}
        self.assertEqual(declared, {
            # schema_version 2 -- A2/A3/A4
            "elements.lang", "elements.lang_basis",
            "facts.condition_basis", "facts.condition_basis_note",
            "facts.value_alternates",
            # schema_version 3 -- pointer direction
            "facts.from_candidate_id"})

    def test_the_inverted_pointer_carries_its_foreign_key(self):
        """A migrated store must get the same declared FK as a fresh one, or the
        two diverge in the one property the inversion was made for."""
        ddl = {c: d for t, c, d in ADDED_COLUMNS}["from_candidate_id"]
        self.assertIn("REFERENCES table_read_candidates(candidate_id)", ddl)

    def test_migrate_applies_them_to_a_fresh_store(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        migrate(conn)
        for table, col, _ in ADDED_COLUMNS:
            cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
            self.assertIn(col, cols, f"{table}.{col} missing after migrate()")
        conn.close()

    def test_migrate_records_the_version(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        migrate(conn)
        v = conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()
        self.assertEqual(int(v[0]), SCHEMA_VERSION)
        conn.close()

    def test_migrate_is_idempotent_on_an_existing_store(self):
        """The real scenario: a v1 store on disk, migrated twice."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        migrate(conn)
        migrate(conn)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(facts)")]
        self.assertEqual(len(cols), len(set(cols)), "a column was added twice")
        conn.close()


class TestFreshAndMigratedAgree(unittest.TestCase):
    """A fresh store and a migrated one must hold the same columns.

    They do NOT hold them in the same ORDER -- ALTER appends, so a migrated
    table carries its new columns at the end. That is fine, because nothing
    reads these tables positionally. What must not happen is a column existing
    in one shape and not the other, which is what you get by adding an entry to
    SCHEMA and forgetting ADDED_COLUMNS, or the reverse.
    """

    def _cols(self, conn, table):
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}

    def test_same_column_set_for_every_migrated_table(self):
        fresh = sqlite3.connect(":memory:")
        fresh.row_factory = sqlite3.Row
        fresh.executescript(SCHEMA)          # a brand-new store, SCHEMA only

        aged = sqlite3.connect(":memory:")
        aged.row_factory = sqlite3.Row
        aged.executescript(SCHEMA)
        for table, column, _ in ADDED_COLUMNS:  # roll it back to the pre-change shape
            aged.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
        ensure_columns(aged)                 # then migrate it forward

        try:
            for table in {t for t, _, _ in ADDED_COLUMNS}:
                self.assertEqual(self._cols(fresh, table), self._cols(aged, table),
                                 f"{table} differs between a fresh and a migrated store")
        finally:
            fresh.close()
            aged.close()

    def test_every_added_column_is_also_in_the_schema_text(self):
        """The two declarations are in two places; this is what keeps them honest."""
        for table, column, _ in ADDED_COLUMNS:
            self.assertIn(column, SCHEMA,
                          f"{table}.{column} is in ADDED_COLUMNS but not in SCHEMA, "
                          f"so a fresh store would never get it")


class TestAnExistingStoreSelfMigrates(unittest.TestCase):
    """The failure this closes: only `ingest` called `migrate()`.

    Someone holding a store built before schema_version 2 who ran
    `cli facts --extract` -- which does not re-ingest -- hit `no such column:
    condition_basis` and had no obvious way to fix it short of a 33-minute
    re-ingest they did not need.
    """

    def test_connect_adds_missing_columns_to_a_writable_store(self):
        import tempfile, pathlib as pl
        from fence_evidence.store import connect
        from fence_evidence.paths import WORKSPACE
        # inside workspace/, because ensure_writable refuses anything outside it
        base = WORKSPACE / "tests" / "snapshots"
        base.mkdir(parents=True, exist_ok=True)
        tmp = pl.Path(tempfile.mkdtemp(prefix="v1store-", dir=base)) / "evidence.db"
        try:
            # build a store, then drop back to a v1 shape by rebuilding `facts`
            # without the new columns
            c = connect(tmp)
            migrate(c)
            c.execute("DROP TABLE facts")
            c.execute("""CREATE TABLE facts (fact_id INTEGER PRIMARY KEY,
                         conditions TEXT NOT NULL DEFAULT '{}')""")
            c.commit()
            c.close()

            c = connect(tmp)          # <- the migration must happen here
            cols = {r[1] for r in c.execute("PRAGMA table_info(facts)")}
            c.close()
            self.assertIn("condition_basis", cols)
            self.assertIn("value_alternates", cols)
        finally:
            import shutil
            shutil.rmtree(tmp.parent, ignore_errors=True)

    def test_read_only_connect_does_not_write(self):
        """A read-only caller must never trigger DDL."""
        import inspect
        from fence_evidence import store
        src = inspect.getsource(store.connect)
        self.assertIn("read_only", src)
        idx = src.index("ensure_columns")
        self.assertLess(src.index("if not read_only"), idx,
                        "ensure_columns must sit behind the read_only guard")


if __name__ == "__main__":
    unittest.main()
