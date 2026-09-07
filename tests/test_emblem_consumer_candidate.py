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

    def test_handed_bindings_name_the_actual_pattern_member(self):
        model = prepare(self.package)['model']
        key = model['default_spec']['infill']['pattern'][0]['key']
        self.assertEqual([f['edge_binding'] for f in model['default_spec']['fixings']], [
            {'member_key': key, 'position': 'first', 'profile_edge': 'tongue'},
            {'member_key': key, 'position': 'last', 'profile_edge': 'groove'}])

    def test_board_and_cap_identity_mapping_retains_nominal_readings_only_in_sidecar(self):
        result = prepare(self.package)['component_authoring']
        by_type = {p['type']: p for p in result['private_parts']}
        board, cap = by_type['infill'], by_type['post_cap']
        self.assertEqual({sf['key'] for sf in board['spec']}, {'colour'})
        self.assertEqual({sf['key']: sf['value'] for sf in cap['spec']},
                         {'colour': 'white', 'sku': '73013956'})
        mappings = {m['part_id']: m for m in result['identity_mappings']}
        self.assertIsNone(mappings[board['id']]['component_sku'])
        nominal = mappings[board['id']]['unconsumed_dimensions'][0]
        self.assertEqual(nominal['value']['amount_milli'], 152400)
        self.assertFalse(mappings[board['id']]['fit_geometry_verified'])
        self.assertTrue(mappings[cap['id']]['sku_identity_anchor']['model_number']['cite'])

    def test_identity_mapping_refuses_wrong_type_and_uncited_cap_identity(self):
        for mutation in ('type', 'sku', 'cite'):
            package = deepcopy(self.package)
            if mutation == 'type':
                board = next(p for p in package['part_fragments'] if p['type']['key'] == 'infill')
                board['type']['key'] = 'post'
            else:
                cap = next(a for a in package['part_identity_anchors'] if a['part_id'].endswith('/73013956'))
                cap['model_number']['text_raw' if mutation == 'sku' else 'cite'] = 'wrong' if mutation == 'sku' else {}
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                prepare(package)

    def test_kit_membership_preserves_unknown_inventory_and_excludes_separate_cap(self):
        result = prepare(self.package)
        kit = result['kit_membership_authoring']
        parts = {p['id'] for p in result['component_authoring']['private_parts']}
        self.assertEqual(kit['supplier_model_number'], '73014714')
        self.assertFalse(kit['runtime_requirements_added'])
        self.assertEqual(kit['emission_status'], 'blocked_incomplete_inventory_and_stock')
        relations = {r['component_key']: r for r in kit['relationships']}
        self.assertEqual([relations[k]['quantity_each'] for k in
                          ('bottom_rail', 'top_rail', 'tongue_and_groove_boards', 'end_u_channel')],
                         [1, 1, None, 2])
        self.assertTrue(all(r['part_id'] in parts and r['stock_length_mm'] is None
                            for r in kit['relationships']))
        cap = result['model']['post']['cap']['part_id']
        self.assertEqual(kit['separately_purchased_part_ids'], [cap])
        self.assertNotIn(cap, {r['part_id'] for r in kit['relationships']})
        self.assertEqual(len(result['model']['default_spec']['fixings']), 2)
        self.assertEqual(result['model']['default_spec']['infill']['pattern'][0]['requirement']['qty'], 1)

    def test_unverified_board_pack_count_cannot_be_filled_from_repeat_count(self):
        entry = next(i for i in self.package['packaged_assembly_inventory']
                     if i['component_key'] == 'tongue_and_groove_boards')
        entry['quantity_each'] = 15
        with self.assertRaisesRegex(ValueError, 'currently evidenced inventory'):
            prepare(self.package)

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

    def test_board_length_rule_and_quantities_are_authored_without_seating_defaults(self):
        result = prepare(self.package)
        spec = result['model']['default_spec']
        board = spec['infill']['pattern'][0]
        self.assertEqual(board['requirement']['length_rule'], 'between_frame')
        self.assertEqual(board['requirement']['qty'], 1)
        self.assertEqual(spec['infill']['justification'], 'start')
        self.assertNotIn('base_engagement_mm', board)
        self.assertNotIn('excess', spec['infill'])
        self.assertTrue(all(s['requirement']['qty'] == 1 for s in spec['frame']))
        self.assertEqual(result['model']['post']['cap']['qty'], 1)
        self.assertEqual(result['assembly_authoring']['review_status'], 'unreviewed_authored')

    def test_boolean_rail_count_and_wrong_model_cap_rule_refused(self):
        inventory = next(i for i in self.package['packaged_assembly_inventory'] if i['component_key'] == 'top_rail')
        inventory['quantity_each'] = True
        with self.assertRaisesRegex(ValueError, 'Rail quantity'):
            prepare(self.package)
        inventory['quantity_each'] = 1
        rule = next(r for r in self.package['purchase_quantity_rules'] if r['target'] == 'post_cap')
        rule['model_id'] = 'another-model'
        with self.assertRaisesRegex(ValueError, 'Cap quantity'):
            prepare(self.package)

    def test_adversarial_assembly_mutations_are_refused(self):
        mutations = [
            lambda p: p['model_fragment']['default_spec']['infill'].update(orientation='horizontal'),
            lambda p: p['model_fragment']['default_spec']['infill']['pattern'][0]['requirement'].update(part_id='cap'),
            lambda p: p['model_fragment']['default_spec']['infill']['pattern'][0]['requirement'].update(qty=99),
            lambda p: p['model_fragment']['default_spec']['infill']['pattern'][0]['requirement'].update(length_rule='panel_height'),
            lambda p: p['purchase_quantity_rules'][-1].update(condition={'only_when': 'gate'}),
            lambda p: p['packaged_assembly_inventory'].append(deepcopy(p['packaged_assembly_inventory'][0])),
            lambda p: p['connection_evidence'].append(deepcopy(p['connection_evidence'][0])),
            lambda p: p['part_fragments'][0]['type'].update(key='post'),
            lambda p: next(s for s in p['part_fragments'][0]['spec'] if s['key'] == 'height_mm')['value'].update(amount_milli=57150),
        ]
        for i, mutate in enumerate(mutations):
            with self.subTest(i=i):
                package = deepcopy(self.package)
                mutate(package)
                with self.assertRaises(ValueError):
                    prepare(package)


    def test_identity_colour_rejects_contradictory_readings_and_malformed_values(self):
        for suffix in ('-board', '/73013956'):
            for bad_value in (None, {'key': 'white', 'value_raw': ['Black']},
                              {'key': 'white', 'value_raw': [True]}):
                with self.subTest(part=suffix, value=bad_value):
                    package = deepcopy(self.package)
                    part = next(p for p in package['part_fragments'] if p['id'].endswith(suffix))
                    next(s for s in part['spec'] if s['key'] == 'colour')['value'] = bad_value
                    with self.assertRaisesRegex(ValueError, 'white colour token'):
                        prepare(package)

    def test_cap_identity_requires_compatible_description_and_same_known_source_version(self):
        for mutation in ('unknown_source', 'other_known_source', 'malformed_cite',
                         'bad_ref_id', 'gate_description', 'wrong_colour', 'missing_anchor'):
            with self.subTest(mutation=mutation):
                package = deepcopy(self.package)
                anchor = next(a for a in package['part_identity_anchors']
                              if a['part_id'].endswith('/73013956'))
                if mutation == 'unknown_source':
                    anchor['model_number']['cite']['belongs_to'] = '0' * 64
                elif mutation == 'other_known_source':
                    current = anchor['model_number']['cite']['belongs_to']
                    other = next(s['content_hash'] for s in package['sources']
                                 if s['content_hash'] != current)
                    anchor['model_number']['cite']['belongs_to'] = other
                elif mutation == 'malformed_cite':
                    anchor['model_number']['cite'] = {'x': 1}
                elif mutation == 'bad_ref_id':
                    anchor['model_number']['cite']['id'] = 'not-a-source-ref'
                elif mutation == 'gate_description':
                    anchor['description']['text_raw'] = 'Gate Post Insert White'
                elif mutation == 'wrong_colour':
                    anchor['description']['text_raw'] = 'Contemporary Post Top - Black'
                else:
                    anchor['description'] = None
                with self.assertRaises(ValueError):
                    prepare(package)


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
                        part_aware = result['part_aware_semantic_validation']
                        self.assertTrue(part_aware['executed'])
                        self.assertTrue(part_aware['actual_authored_parts_remain_draft'])
                        self.assertTrue(any("width_mm must be positive" in e
                                            for e in part_aware['errors']))
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
                        self.assertFalse(any('length_rule=None' in e for e in errors))
                        lost = ['default_spec', 'infill', 'pattern', 0, 'profile_edges'] in result['unconsumed_authored_paths']
                        self.assertEqual(result['profile_edges_preserved_by_parser'], not lost)
