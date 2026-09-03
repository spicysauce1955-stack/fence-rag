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


class TestObligation14Publishes(unittest.TestCase):
    """C15 resolved (conversation.md T42): SpecField.value is Quantity | Token.
    The two real stock-length values now publish as SpecFields, computed from
    unit_original -- never unit_normalized, which for stock_length_in facts
    means "value_normalized is expressed in inches" (an extractor convention),
    not "the source stated inches" (G63). `_stock_length_evidence` queries the
    store fresh rather than trusting a hardcoded element id -- these tests
    exercise that real query path, over a synthetic store shaped exactly like
    the live one (`promoted=False`: real `stock_length_in` facts are never
    table-promoted; `unit_original="foot"`, matching real data exactly)."""

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
        # unit_original="foot" matches the real store exactly (verified by direct
        # query) -- unit_normalized stays "in" here too, matching real data's own
        # (misleading, see G63) convention for this fact type, so these tests
        # exercise the actual defect the fix routes around, not a sanitised one.
        add_fact(self.conn, fact_type="stock_length_in", value="16 foot lengths",
                conditions={"colour": "White"}, condition_basis="stated",
                document_id=self.doc_id, promoted=False, unit_original="foot")
        add_fact(self.conn, fact_type="stock_length_in", value="12 foot rails",
                conditions={"colour": "Blend"}, condition_basis="stated",
                document_id=self.doc_id, promoted=False, unit_original="foot")

    def tearDown(self):
        self.conn.close()

    def test_no_evidence_without_a_store_still_publishes_identity(self):
        """conn=None (a synthetic fixture, a partial store) must not crash --
        it publishes Part identity and simply finds no stock-length evidence."""
        parts, gaps = build_parts(self.components, self.registry, source_ref=_mint)
        self.assertEqual(len(parts), 2)
        self.assertEqual(gaps, [])

    def test_both_rail_components_publish_one_specfield_each(self):
        parts, gaps = build_parts(self.components, self.registry, source_ref=_mint,
                                  conn=self.conn)
        self.assertEqual(gaps, [], "the wire shape is resolved; nothing to gap")
        for p in parts:
            self.assertEqual(len(p["spec"]), 1)

    def test_the_white_rail_gets_the_correct_quantity_not_the_unit_normalized_one(self):
        """16 ft = 4876800 milli-mm. Using unit_normalized='in' (the corpus
        defect, G63) would silently compute 406400 -- twelve times too small."""
        parts, _ = build_parts(self.components, self.registry, source_ref=_mint,
                               conn=self.conn)
        white = next(p for p in parts if p["id"].endswith("white"))
        spec = white["spec"][0]
        self.assertEqual(spec["key"], "nominal_length_mm")
        self.assertEqual(spec["agree"], "==")
        self.assertEqual(spec["value"],
                         {"amount_milli": 4876800, "unit": "mm",
                          "value_raw": ["16 foot lengths"]})

    def test_the_blend_rail_gets_its_own_correct_quantity(self):
        parts, _ = build_parts(self.components, self.registry, source_ref=_mint,
                               conn=self.conn)
        colour = next(p for p in parts if p["id"].endswith("color"))
        self.assertEqual(colour["spec"][0]["value"],
                         {"amount_milli": 3657600, "unit": "mm",
                          "value_raw": ["12 foot rails"]})

    def test_specfield_provenance_carries_a_resolvable_citation(self):
        parts, _ = build_parts(self.components, self.registry, source_ref=_mint,
                               conn=self.conn)
        for p in parts:
            prov = p["spec"][0]["provenance"]
            self.assertTrue(prov["cites"])
            self.assertIn("source_class", prov)
            self.assertIn("curation_level", prov)

    def test_part_level_cites_rolls_up_the_spec_citations(self):
        parts, _ = build_parts(self.components, self.registry, source_ref=_mint,
                               conn=self.conn)
        for p in parts:
            self.assertEqual(p["cites"], p["spec"][0]["provenance"]["cites"])
            self.assertTrue(p["contributing_sources"])

    def test_a_component_outside_this_build_gets_no_part(self):
        """Real evidence exists in the store, but no component of this build
        matches it -- nothing crashes, nothing publishes."""
        registry = PartTypeRegistry()
        parts, gaps = build_parts([], registry, source_ref=_mint, conn=self.conn)
        self.assertEqual(parts, [])
        self.assertEqual(gaps, [])

    def test_two_documents_minting_the_same_ref_do_not_duplicate_a_citation(self):
        """ref_id() is a pure function of (sha256, page_no, bbox), not of the
        element id -- two byte-identical documents (this evidence's real
        shape: two of its three documents share one sha256) can mint the
        IDENTICAL ref from two different element ids. A `source_ref` that
        does so must not leave a literal duplicate in the citation list."""
        add_document(self.conn, document_id="doc-twin", sha256="a" * 64,
                    version_id="v-twin", manufacturer="CertainTeed")
        add_fact(self.conn, fact_type="stock_length_in", value="16 foot lengths",
                conditions={"colour": "White"}, condition_basis="stated",
                document_id="doc-twin", version_id="v-twin",
                promoted=False, unit_original="foot")

        def content_addressed_mint(element_id):
            # Every element mints the SAME ref, as if every source in this
            # test were one byte-identical document -- the extreme case of
            # what real ref_id() does for two documents that happen to share
            # a sha256.
            return {"id": "ref-shared", "belongs_to": "shared" + "f" * 58}

        parts, _ = build_parts(self.components, self.registry,
                               source_ref=content_addressed_mint, conn=self.conn)
        white = next(p for p in parts if p["id"].endswith("white"))
        cites = white["spec"][0]["provenance"]["cites"]
        self.assertEqual(cites, [{"id": "ref-shared", "belongs_to": "shared" + "f" * 58}],
                         "two elements minting the identical ref must collapse to one")

    def test_an_unrelated_colour_is_ignored_not_guessed(self):
        add_fact(self.conn, fact_type="stock_length_in", value="9 feet",
                 conditions={"colour": "Sandstone"}, condition_basis="stated",
                 document_id=self.doc_id, promoted=False, unit_original="foot")
        parts, gaps = build_parts(self.components, self.registry, source_ref=_mint,
                                  conn=self.conn)
        self.assertEqual(gaps, [])
        for p in parts:
            self.assertEqual(len(p["spec"]), 1,
                             "an unmapped colour must not add a third guessed value")


if __name__ == "__main__":
    unittest.main()
