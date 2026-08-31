"""The PartType spine (obligation 5): resolution, minting, and the dataset
baseline gate."""
import unittest
from unittest.mock import patch

import context  # noqa: F401
from fence_evidence import part_types
from fence_evidence.dataset import DatasetChanged
from fence_evidence.part_types import (MANUFACTURER_NAMESPACE, PartTypeRegistry,
                                       build_part_types, load_slice_components,
                                       mfr_namespace)
from fence_evidence.snapshot import CLOSED_BY_PLANNING


class TestNamespace(unittest.TestCase):
    def test_certainteed_slugifies_to_the_expected_namespace(self):
        self.assertEqual(mfr_namespace("CertainTeed"), "mfr/certainteed")

    def test_the_module_constant_matches_the_function(self):
        self.assertEqual(MANUFACTURER_NAMESPACE, mfr_namespace("CertainTeed"))


class TestSpineResolution(unittest.TestCase):
    def test_a_direct_spine_match_needs_no_extension(self):
        reg = PartTypeRegistry()
        ref = reg.resolve("post")
        self.assertEqual(ref, {"namespace": "shared", "key": "post"})
        self.assertEqual(reg.rows(), [])

    def test_an_off_spine_type_mints_exactly_one_extension_row(self):
        reg = PartTypeRegistry()
        ref = reg.resolve("picket")
        self.assertEqual(ref, {"namespace": "mfr/certainteed", "key": "picket"})
        rows = reg.rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["namespace"], "mfr/certainteed")
        self.assertNotEqual(rows[0]["namespace"], "shared",
                            "an extension never claims the shared namespace")
        self.assertEqual(rows[0]["parent"], {"namespace": "shared", "key": "infill"})

    def test_repeat_resolution_of_the_same_type_is_idempotent(self):
        reg = PartTypeRegistry()
        reg.resolve("hinge")
        reg.resolve("hinge")
        reg.resolve("latch")
        self.assertEqual(len(reg.rows()), 2)

    def test_an_unmapped_component_type_returns_none_not_a_guess(self):
        reg = PartTypeRegistry()
        self.assertIsNone(reg.resolve("gate_kit"))
        self.assertEqual(reg.rows(), [])

    def test_rows_are_sorted_by_namespace_then_key(self):
        reg = PartTypeRegistry()
        reg.resolve("latch")
        reg.resolve("hinge")
        reg.resolve("picket")
        keys = [r["key"] for r in reg.rows()]
        self.assertEqual(keys, sorted(keys))


class TestBuildPartTypes(unittest.TestCase):
    def test_unmapped_component_produces_a_gap_closed_by_planning(self):
        components = [
            {"assembly_id": "A", "component_id": "C1", "component_type": "gate_kit",
             "component_name": "Some Kit"},
            {"assembly_id": "A", "component_id": "C2", "component_type": "post",
             "component_name": "A Post"},
        ]
        rows, gaps = build_part_types(components)
        self.assertEqual(rows, [])          # 'post' is shared, mints nothing
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["kind"], "unmapped_part_kind")
        self.assertEqual(gaps[0]["closes_by"], "planning")
        self.assertIn(gaps[0]["kind"], CLOSED_BY_PLANNING)
        self.assertEqual(gaps[0]["subject"]["id"], "C1")

    def test_mapped_components_mint_the_expected_extensions(self):
        components = [
            {"assembly_id": "A", "component_id": "C1", "component_type": "picket",
             "component_name": "A Picket"},
            {"assembly_id": "A", "component_id": "C2", "component_type": "hinge",
             "component_name": "A Hinge"},
        ]
        rows, gaps = build_part_types(components)
        self.assertEqual(gaps, [])
        self.assertEqual({r["key"] for r in rows}, {"picket", "hinge"})


class TestDatasetBaseline(unittest.TestCase):
    def test_a_forged_baseline_raises_uncaught(self):
        with patch.object(part_types.dataset, "verify_dataset",
                          side_effect=DatasetChanged("forged for the test")):
            with self.assertRaises(DatasetChanged):
                load_slice_components()


class TestRealChesterfieldSlice(unittest.TestCase):
    """Measured shape of the real dataset file, so a silent edit to
    data/certainteed-bufftech.json or to this module's ASSEMBLY_IDS is
    caught by a red test rather than a wrong publication."""

    def test_the_slice_has_the_measured_component_count_and_types(self):
        components = load_slice_components()
        self.assertEqual(len(components), 13,
                         "10 Chesterfield/gate + 3 Post & Rail Fence components")
        ids = {c["component_id"] for c in components}
        # Chesterfield panel + gate (10)
        for expected in ("BT-POST-5X5", "BT-RAIL-CHESTERFIELD", "BT-PICKET-7-7-TG",
                         "BT-POSTCAP-VARIOUS", "BT-STIFFENER-ALUM",
                         "BT-GATE-FRAME-ALUM", "BT-HINGE-SS", "BT-LATCH-SS",
                         "BT-NYLON-HW-KIT", "BT-DROP-ROD-48",
                         # Post & Rail Fence (3): the one assembly with real
                         # obligation-14 evidence in this manufacturer file
                         "BT-POST-5X5-PR", "BT-RAIL-PR-3RAIL-WHITE",
                         "BT-RAIL-PR-3RAIL-COLOR"):
            self.assertIn(expected, ids, f"{expected} missing from the slice")

    def test_the_slice_produces_exactly_two_unmapped_gate_kit_gaps(self):
        rows, gaps = build_part_types(load_slice_components())
        unmapped = [g for g in gaps if g["kind"] == "unmapped_part_kind"]
        self.assertEqual(len(unmapped), 2)
        self.assertEqual({g["because"]["params"]["component_id"] for g in unmapped},
                         {"BT-GATE-FRAME-ALUM", "BT-NYLON-HW-KIT"})


if __name__ == "__main__":
    unittest.main()
