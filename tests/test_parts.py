"""`Part` identity/type (obligation 5) and the obligation-14 gap this round
withholds rather than guesses a schema for."""
import unittest

import context  # noqa: F401
from fence_evidence.part_types import PartTypeRegistry, build_part_types
from fence_evidence.parts import _STOCK_LENGTH_DOCUMENT_IDS, build_parts
from test_parameters import add_document, add_fact, make_store


def _mint(element_id):
    return {"id": f"ref-{element_id}", "belongs_to": "f" * 64}


class TestPartIdentity(unittest.TestCase):
    def setUp(self):
        self.components = [
            {"assembly_id": "A", "component_id": "BT-POST-5X5", "component_type": "post",
             "component_name": "5x5 Post"},
            {"assembly_id": "A", "component_id": "BT-PICKET-7-7-TG", "component_type": "picket",
             "component_name": "Picket"},
        ]
        self.registry = PartTypeRegistry()
        for c in self.components:
            self.registry.resolve(c["component_type"])

    def test_every_component_publishes_one_part(self):
        parts, gaps = build_parts(self.components, self.registry, source_ref=_mint)
        self.assertEqual(len(parts), 2)

    def test_a_spine_native_part_uses_the_shared_namespace_in_its_id(self):
        parts, _ = build_parts(self.components, self.registry, source_ref=_mint)
        post = next(p for p in parts if "post" in p["id"])
        self.assertEqual(post["id"], "shared/bt-post-5x5")
        self.assertEqual(post["type"], {"namespace": "shared", "key": "post"})

    def test_an_extension_part_uses_the_manufacturer_namespace_in_its_id(self):
        parts, _ = build_parts(self.components, self.registry, source_ref=_mint)
        picket = next(p for p in parts if "picket" in p["id"])
        self.assertEqual(picket["id"], "mfr/certainteed/bt-picket-7-7-tg")

    def test_identity_carries_no_citation(self):
        """C3: identity/membership is authored structure, not a value."""
        parts, _ = build_parts(self.components, self.registry, source_ref=_mint)
        for p in parts:
            self.assertEqual(p["cites"], [])
            self.assertEqual(p["contributing_sources"], [])

    def test_spec_is_empty_this_round_for_every_part(self):
        parts, _ = build_parts(self.components, self.registry, source_ref=_mint)
        for p in parts:
            self.assertEqual(p["spec"], [])

    def test_authorship_is_third_party(self):
        parts, _ = build_parts(self.components, self.registry, source_ref=_mint)
        for p in parts:
            self.assertEqual(p["authorship"], "third_party_authored")

    def test_output_is_id_sorted(self):
        parts, _ = build_parts(self.components, self.registry, source_ref=_mint)
        ids = [p["id"] for p in parts]
        self.assertEqual(ids, sorted(ids))

    def test_an_unmapped_component_produces_no_part(self):
        components = self.components + [
            {"assembly_id": "A", "component_id": "BT-GATE-FRAME-ALUM",
             "component_type": "gate_kit", "component_name": "Gate Kit"}]
        registry = PartTypeRegistry()
        for c in components:
            registry.resolve(c["component_type"])
        parts, _ = build_parts(components, registry, source_ref=_mint)
        self.assertEqual(len(parts), 2, "gate_kit is unmapped and must not publish")


class TestObligation14IsWithheld(unittest.TestCase):
    """SpecField's wire shape is unresolved (see parts.py's module docstring);
    this round gaps the two real stock-length values instead of guessing.
    `_stock_length_evidence` queries the store fresh rather than trusting a
    hardcoded element id -- these tests exercise that real query path, over a
    synthetic store shaped exactly like the live one (`promoted=False`: real
    `stock_length_in` facts are never table-promoted)."""

    def setUp(self):
        self.components = [
            {"assembly_id": "BT-POSTRAIL-3RAIL", "component_id": "BT-RAIL-PR-3RAIL-WHITE",
             "component_type": "rail", "component_name": "3-Rail Ribbed Rail (White)"},
            {"assembly_id": "BT-POSTRAIL-3RAIL", "component_id": "BT-RAIL-PR-3RAIL-COLOR",
             "component_type": "rail", "component_name": "3-Rail Ribbed Rail (Color)"},
        ]
        self.registry = PartTypeRegistry()
        for c in self.components:
            self.registry.resolve(c["component_type"])
        self.doc_id = _STOCK_LENGTH_DOCUMENT_IDS[0]
        self.conn = make_store()
        add_document(self.conn, document_id=self.doc_id, manufacturer="CertainTeed")
        add_fact(self.conn, fact_type="stock_length_in", value="16 foot lengths",
                conditions={"colour": "White"}, condition_basis="stated",
                document_id=self.doc_id, promoted=False)
        add_fact(self.conn, fact_type="stock_length_in", value="12 foot rails",
                conditions={"colour": "Blend"}, condition_basis="stated",
                document_id=self.doc_id, promoted=False)

    def tearDown(self):
        self.conn.close()

    def test_no_evidence_without_a_store_still_publishes_identity(self):
        """conn=None (a synthetic fixture, a partial store) must not crash --
        it publishes Part identity and simply finds no stock-length evidence."""
        parts, gaps = build_parts(self.components, self.registry, source_ref=_mint)
        self.assertEqual(len(parts), 2)
        self.assertEqual(gaps, [])

    def test_both_rail_components_still_publish_with_empty_spec(self):
        parts, _ = build_parts(self.components, self.registry, source_ref=_mint,
                               conn=self.conn)
        self.assertEqual(len(parts), 2)
        for p in parts:
            self.assertEqual(p["spec"], [])

    def test_both_colours_produce_a_gap_closed_by_planning(self):
        _, gaps = build_parts(self.components, self.registry, source_ref=_mint,
                              conn=self.conn)
        self.assertEqual(len(gaps), 2)
        for g in gaps:
            self.assertEqual(g["kind"], "unmodellable_entity")
            self.assertEqual(g["closes_by"], "planning")
            self.assertTrue(g["cites"], "the gap carries the real evidence, not just a claim")

    def test_gap_subjects_name_the_specific_component(self):
        _, gaps = build_parts(self.components, self.registry, source_ref=_mint,
                              conn=self.conn)
        subjects = {g["subject"]["id"] for g in gaps}
        self.assertEqual(subjects, {"BT-RAIL-PR-3RAIL-WHITE", "BT-RAIL-PR-3RAIL-COLOR"})

    def test_a_component_outside_this_build_gets_no_gap(self):
        """Real evidence exists in the store, but no component of this build
        matches it -- only publish a gap for a component actually in scope."""
        registry = PartTypeRegistry()
        _, gaps = build_parts([], registry, source_ref=_mint, conn=self.conn)
        self.assertEqual(gaps, [])

    def test_an_unrelated_colour_is_ignored_not_guessed(self):
        add_fact(self.conn, fact_type="stock_length_in", value="9 feet",
                 conditions={"colour": "Sandstone"}, condition_basis="stated",
                 document_id=self.doc_id, promoted=False)
        _, gaps = build_parts(self.components, self.registry, source_ref=_mint,
                              conn=self.conn)
        self.assertEqual(len(gaps), 2, "an unmapped colour must not add a "
                         "third guessed component")


if __name__ == "__main__":
    unittest.main()
