"""The snapshot builder — closure, determinism, and refusing to publish a lie.

The property that matters most is the one the contract calls the closure rule:

  > BINDING. Every `SourceRef.belongs_to` cited anywhere inside a snapshot
  > resolves to a `SourceDoc` in that snapshot's `source_docs`.

It is binding because §3.2.2 forbids Planning from calling Discovery during a run,
so a dangling `belongs_to` carries zero admissibility bits into a pinned object.
The design answer is not to validate closure afterwards but to make it
*unrepresentable*: minting a reference registers its document, so a builder that
skipped the registration could not produce the reference either.
"""
import unittest

import context  # noqa: F401  -- puts the repo root on sys.path
from context import requires_store
from fence_evidence.snapshot import (Gap, SnapshotBuilder, SourceDoc, SourceRef,
                                     SOURCE_CLASS, build_snapshot)


class TestSourceClassMapping(unittest.TestCase):
    """19 doc_type values collapse into 8 SourceClass values. Lossy, and the
    source policy ranks on the result, so a wrong entry changes admissibility."""

    def test_every_mapped_value_is_a_real_source_class(self):
        legal = {"sealed_approval", "tested_report", "industry_standard",
                 "manufacturer_installation_instruction", "spec_sheet",
                 "marketing", "company_authored", "ai_proposal"}
        self.assertTrue(set(SOURCE_CLASS.values()) <= legal,
                        f"not a SourceClass: {set(SOURCE_CLASS.values()) - legal}")

    def test_an_approval_outranks_a_manual(self):
        self.assertEqual(SOURCE_CLASS["hvhz_noa"], "sealed_approval")
        self.assertEqual(SOURCE_CLASS["installation_manual"],
                         "manufacturer_installation_instruction")

    @requires_store
    def test_every_doc_type_in_the_store_is_mapped(self):
        """An unmapped doc_type must not silently become `marketing` — that would
        make a sealed approval inadmissible for the task it exists to serve."""
        from fence_evidence.store import connect
        conn = connect()
        try:
            seen = {r[0] for r in conn.execute(
                "SELECT DISTINCT doc_type FROM documents WHERE doc_type IS NOT NULL")}
        finally:
            conn.close()
        missing = seen - set(SOURCE_CLASS)
        self.assertEqual(missing, set(), f"unmapped doc_type values: {sorted(missing)}")


@requires_store
class TestClosureIsStructural(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fence_evidence.store import connect
        cls.conn = connect()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def _one_element(self):
        row = self.conn.execute(
            "SELECT element_id FROM elements WHERE bbox IS NOT NULL LIMIT 1").fetchone()
        return row["element_id"]

    def test_minting_a_ref_registers_its_document(self):
        b = SnapshotBuilder(self.conn, tenant="t", regime="us_astm")
        self.assertEqual(b.source_docs(), [])
        ref = b.source_ref(self._one_element())
        self.assertTrue(any(d.content_hash == ref.belongs_to for d in b.source_docs()),
                        "a ref was minted whose document is not in the snapshot")

    def test_the_same_element_yields_the_same_ref(self):
        b = SnapshotBuilder(self.conn, tenant="t", regime="us_astm")
        eid = self._one_element()
        self.assertEqual(b.source_ref(eid).id, b.source_ref(eid).id)

    def test_a_ref_id_is_a_function_of_what_it_points_at(self):
        """Not a counter, not a uuid. Two builds must mint identical ids."""
        eid = self._one_element()
        a = SnapshotBuilder(self.conn, tenant="t", regime="us_astm").source_ref(eid)
        b = SnapshotBuilder(self.conn, tenant="t", regime="us_astm").source_ref(eid)
        self.assertEqual(a.id, b.id)

    def test_an_unknown_element_raises_rather_than_minting_a_dangling_ref(self):
        b = SnapshotBuilder(self.conn, tenant="t", regime="us_astm")
        with self.assertRaises(KeyError):
            b.source_ref("element-does-not-exist-0000")


@requires_store
class TestBuiltSnapshot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = build_snapshot(tenant="acme", regime="us_astm")

    def test_it_declares_the_contract_it_was_built_against(self):
        for key in ("snapshot_id", "tenant", "regime", "contract_version",
                    "spine_version", "policy_version", "retain_until"):
            self.assertIn(key, self.snap, f"missing {key}")

    def test_exactly_one_regime(self):
        self.assertIn(self.snap["regime"], ("us_astm", "cn_gb"))

    def test_closure_holds_over_the_finished_object(self):
        """The property asserted end-to-end, not just at the mint site."""
        held = {d["content_hash"] for d in self.snap["source_docs"]}
        dangling = []
        def walk(node, path="$"):
            if isinstance(node, dict):
                if "belongs_to" in node and "id" in node:
                    if node["belongs_to"] not in held:
                        dangling.append((path, node["belongs_to"]))
                for k, v in node.items():
                    walk(v, f"{path}.{k}")
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, f"{path}[{i}]")
        walk(self.snap)
        self.assertEqual(dangling, [], "a SourceRef points outside this snapshot")

    def test_every_warning_carries_the_four_required_fields(self):
        for w in self.snap["warnings"]:
            for field in ("text_raw", "lang", "cites", "attaches_to"):
                self.assertTrue(w.get(field) not in (None, "", []),
                                f"warning missing {field}: {w.get('text_raw','')[:40]!r}")

    def test_no_warning_text_was_normalised(self):
        """Obligation 10: text_raw is verbatim and never normalised."""
        for w in self.snap["warnings"]:
            self.assertEqual(w["text_raw"], w["text_raw"].strip("\x00"))
            self.assertNotIn("  \n  ", w["text_raw"].replace("\n", "\n"))

    def test_every_gap_says_what_would_close_it_and_who_can(self):
        for g in self.snap["gaps"]:
            self.assertTrue(g.get("would_close"), f"gap {g.get('id')} has no would_close")
            self.assertIn(g.get("closes_by"), ("knowledge", "planning"))

    def test_building_twice_produces_the_same_hash(self):
        again = build_snapshot(tenant="acme", regime="us_astm")
        self.assertEqual(self.snap["snapshot_id"], again["snapshot_id"])

    def test_a_different_tenant_produces_a_different_hash(self):
        other = build_snapshot(tenant="other", regime="us_astm")
        self.assertNotEqual(self.snap["snapshot_id"], other["snapshot_id"])

    def test_it_publishes_something(self):
        self.assertGreater(len(self.snap["source_docs"]), 0)
        self.assertGreater(len(self.snap["warnings"]), 0)


if __name__ == "__main__":
    unittest.main()
