"""Private mapping must not fill unknown geometry or erase source assertions."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from context import ROOT
from scripts.prepare_emblem_consumer_model import prepare


class TestConsumerCandidate(unittest.TestCase):
    def setUp(self):
        self.package = json.loads((ROOT / 'workspace/catalog/emblem-73014714-model-draft.json').read_text())

    def test_mapping_preserves_source_and_leaves_placements_unknown(self):
        before = deepcopy(self.package)
        result = prepare(self.package)
        self.assertEqual(self.package, before)
        self.assertFalse(result['publishable'])
        for slot in result['model']['default_spec']['frame']:
            self.assertEqual(slot['joint'], 'channel')
            self.assertNotIn('placement', slot)
            self.assertNotIn('channel_depth_mm', slot)
            self.assertEqual(result['source_joints'][slot['key']], {'kind': 'channel'})

    def test_numeric_joint_fields_cannot_be_silently_dropped(self):
        self.package['model_fragment']['default_spec']['frame'][0]['joint']['channel_depth'] = {
            'amount_milli': 1000, 'unit': 'mm', 'value_raw': ['fixture']}
        with self.assertRaisesRegex(ValueError, 'kind-only channel'):
            prepare(self.package)

    def test_missing_post_role_refused(self):
        binding = next(b for b in self.package['pending_bindings']
                       if b['target'] == '/model_fragment/post/requirement')
        binding['candidates'].pop()
        with self.assertRaisesRegex(ValueError, 'distinct end, line and corner'):
            prepare(self.package)

    def test_changed_post_quantity_cannot_be_silently_ignored(self):
        rule = next(r for r in self.package['purchase_quantity_rules'] if r['target'] == 'post')
        rule['quantity_per_basis']['amount_milli'] = 2000
        with self.assertRaisesRegex(ValueError, 'one-post-per-station'):
            prepare(self.package)

    def test_post_predicate_does_not_also_name_a_part(self):
        result = prepare(self.package)
        req = result['model']['post']['requirement']
        self.assertEqual(req['part_id'], '')
        self.assertEqual(req['qty'], 1)
        self.assertEqual(result['post_quantity_rule']['target'], 'post')
        self.assertEqual(result['expected_post_skus'],
                         {'end': '73045785', 'line': '73045783', 'corner': '73045784'})

    def test_confirmed_offsets_preserve_exact_value_and_disclose_rounding(self):
        confirmation = json.loads((ROOT / 'workspace/catalog/emblem-73014714-placement-confirmation.json').read_text())
        before = deepcopy(self.package)
        result = prepare(self.package, confirmation)
        self.assertEqual(self.package, before)
        self.assertEqual([s['placement'] for s in result['model']['default_spec']['frame']],
                         [{'kind': 'from_bottom', 'offset_mm': 89},
                          {'kind': 'from_top', 'offset_mm': 89}])
        projection = result['placement_projection']
        self.assertEqual(projection['exact_inward_offset_mm'], '88.9')
        self.assertEqual(projection['offset_rounding_error_mm'], '0.1')
        self.assertEqual(result['placement_inputs_required'], [])
        self.assertFalse(result['publishable'])
        self.assertFalse(result['bom_generation_verified'])

    def test_stale_or_different_confirmation_is_refused(self):
        confirmation = json.loads((ROOT / 'workspace/catalog/emblem-73014714-placement-confirmation.json').read_text())
        for key, value in [('source_package_hash', 'stale'), ('model_id', 'another-model'),
                           ('datum', 'above_ground'), ('rail_vertical_envelope_inches', '6'),
                           ('status', 'extracted'), ('reviewer', '')]:
            with self.subTest(key=key):
                changed = dict(confirmation, **{key: value})
                with self.assertRaisesRegex(ValueError, 'exact package and reviewed datum'):
                    prepare(self.package, changed)

    def test_rail_mapping_uses_vertical_height_and_preserves_source_dimensions(self):
        result = prepare(self.package)['component_authoring']
        for mapping in result['rail_dimension_mappings']:
            self.assertEqual(mapping['exact_mm'], '177.8')
            self.assertEqual(mapping['projected_mm'], 178)
            self.assertEqual(mapping['rounding_error_mm'], '0.2')
            original = {s['key']: s['value'] for s in mapping['original_part_specs']}
            self.assertEqual(original['width_mm']['amount_milli'], 57150)
            self.assertEqual(original['height_mm']['amount_milli'], 177800)
            self.assertTrue(mapping['source_spec']['provenance']['cites'])
        self.assertTrue(all(p['status'] == 'draft' for p in result['private_parts']))

    def test_u_channel_requirements_preserve_two_distinct_end_placements(self):
        result = prepare(self.package)
        authoring = result['component_authoring']
        self.assertEqual([p['edge'] for p in authoring['u_channel_placements']],
                         ['first_board_tongue', 'last_board_groove'])
        channel = authoring['private_parts'][-1]
        self.assertEqual(channel['type'], 'end_channel')
        self.assertEqual(channel['spec'], [])
        self.assertEqual([r['requirement']['part_id'] for r in result['model']['default_spec']['fixings']],
                         [channel['id'], channel['id']])
        self.assertFalse(authoring['handed_placement_consumed'])
        self.assertFalse(authoring['kit_purchase_credit_consumed'])

    def test_ambiguous_rail_height_and_changed_channel_inventory_are_refused(self):
        rail = self.package['part_fragments'][0]
        rail['spec'].append(deepcopy(next(s for s in rail['spec'] if s['key'] == 'height_mm')))
        with self.assertRaisesRegex(ValueError, 'exactly one sourced height'):
            prepare(self.package)
        rail['spec'].pop()
        inventory = next(i for i in self.package['packaged_assembly_inventory']
                         if i['component_key'] == 'end_u_channel')
        inventory['quantity_each'] = 4
        with self.assertRaisesRegex(ValueError, 'two handed end placements'):
            prepare(self.package)


class TestConsumerCandidateIntegration(unittest.TestCase):
    def test_real_consumer_refuses_incomplete_candidate_and_exposes_lost_fields(self):
        consumer = Path(os.environ.get('FENCE_PLANNING_ROOT', '/tmp/fence-planning-bom'))
        python = consumer / '.venv/bin/python'
        if not python.exists() or not (consumer / 'src/fenceai/fencemodel/model.py').exists():
            self.skipTest('Set FENCE_PLANNING_ROOT to a Planning checkout with its Python environment.')
        with tempfile.TemporaryDirectory(dir=ROOT / 'workspace') as directory:
            report = Path(directory) / 'report.json'
            command = [str(python), str(ROOT / 'scripts/prepare_emblem_consumer_model.py'),
                       '--consumer-root', str(consumer), '--package',
                       str(ROOT / 'workspace/catalog/emblem-73014714-model-draft.json'),
                       '--output', str(Path(directory) / 'candidate.json'), '--report', str(report)]
            for confirmed in (False, True):
                with self.subTest(confirmed=confirmed):
                    args = command + (['--placement-confirmation', str(ROOT / 'workspace/catalog/emblem-73014714-placement-confirmation.json')]
                                      if confirmed else [])
                    run = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
                    self.assertEqual(run.returncode, 2, run.stderr or run.stdout)
                    result = json.loads(report.read_text())
                    self.assertFalse(result['candidate_complete'])
                    self.assertFalse(result['bom_generation_verified'])
                    self.assertEqual(result['whole_model_parses'], confirmed)
                    self.assertEqual(result['partial_semantic_validation']['executed'], confirmed)
                    if confirmed:
                        probe = result['component_resolution_probe']
                        self.assertEqual(probe['rail_face_heights_mm'],
                                         {'bottom_rail': 178, 'top_rail': 178})
                        self.assertEqual(probe['u_channel_counts_per_panel'],
                                         {'u_channel_first_board_tongue': 1,
                                          'u_channel_last_board_groove': 1})
                        self.assertEqual(probe['u_channels_for_1_and_7_panels'], {'1': 2, '7': 14})
                        self.assertFalse(probe['handed_placement_consumed'])
                        errors = result['partial_semantic_validation']['errors']
                        self.assertTrue(any('bottom_rail' in e and 'channel_depth_mm=0' in e for e in errors))
                        self.assertTrue(any('top_rail' in e and 'channel_depth_mm=0' in e for e in errors))
                        self.assertTrue(any('length_rule=None' in e for e in errors))
                        self.assertIn(['default_spec', 'infill', 'pattern', 0, 'profile_edges'],
                                      result['unconsumed_authored_paths'])
