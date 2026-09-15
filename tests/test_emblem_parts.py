"""Emblem family membership projects without SKU or value inference."""
import unittest
from unittest.mock import patch

import context  # noqa: F401
from fence_evidence import part_types
from fence_evidence.dataset import DatasetChanged
from fence_evidence.part_types import (
    PartTypeRegistry, build_part_types, load_emblem_components,
    load_slice_components,
)
from fence_evidence.parts import build_parts


class TestEmblemPartProjection(unittest.TestCase):
    def setUp(self):
        self.components = load_emblem_components()
        self.registry = PartTypeRegistry("Freedom Outdoor Living")

    def test_panel_slice_excludes_colisted_gates_and_their_hardware(self):
        self.assertEqual({c['component_id'] for c in self.components}, {
            'freedom-5x5-line-post', 'freedom-5x5-corner-post',
            'freedom-5x5-end-post', 'freedom-5x5-post-top',
            'freedom-emblem-rail', 'freedom-emblem-board',
        })
        self.assertEqual({c['assembly_id'] for c in self.components},
                         {'freedom-emblem-privacy-panel'})

    def test_manufacturer_extensions_do_not_leak_between_registries(self):
        freedom = self.registry.resolve('picket')
        certainteed = PartTypeRegistry().resolve('picket')
        self.assertEqual(freedom['namespace'], 'mfr/freedom-outdoor-living')
        self.assertEqual(certainteed['namespace'], 'mfr/certainteed')
        self.assertEqual(self.registry.rows()[0]['parent'],
                         {'namespace': 'shared', 'key': 'infill'})

    def test_parts_use_authored_family_ids_without_sku_or_spec_inference(self):
        types, gaps = build_part_types(self.components, self.registry)
        parts, part_gaps = build_parts(
            self.components, self.registry,
            identity_namespace=self.registry.namespace)
        self.assertEqual(gaps + part_gaps, [])
        self.assertEqual(len(types), 1)
        self.assertEqual(len(parts), 6)
        for part in parts:
            self.assertTrue(part['id'].startswith('mfr/freedom-outdoor-living/freedom-'))
            self.assertEqual(part['spec'], [])
            self.assertEqual(part['cites'], [])
        post = next(p for p in parts if p['id'].endswith('line-post'))
        self.assertEqual(post['type'], {'namespace': 'shared', 'key': 'post'})
        self.assertEqual(sum(p['type']['key'] == 'rail' for p in parts), 1)

    def test_existing_identity_defaults_are_preserved(self):
        components = load_slice_components()
        parts, gaps = build_parts(components, PartTypeRegistry())
        self.assertEqual(len(parts), 11)
        self.assertIn('shared/bt-post-5x5', {p['id'] for p in parts})
        self.assertIn('mfr/certainteed/bt-picket-7-7-tg', {p['id'] for p in parts})
        self.assertEqual(gaps, [])

    def test_emblem_loader_does_not_bypass_dataset_baseline(self):
        with patch.object(part_types.dataset, 'verify_dataset',
                          side_effect=DatasetChanged('test baseline mismatch')):
            with self.assertRaises(DatasetChanged):
                load_emblem_components()


if __name__ == '__main__':
    unittest.main()
