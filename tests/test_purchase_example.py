import copy
import unittest

import context  # noqa: F401
from scripts.audit_purchase_example import audit


class TestPurchaseExample(unittest.TestCase):
    def setUp(self):
        self.example = {
            'stations': [{'id': 'a', 'role': 'end'}, {'id': 'b', 'role': 'end'}],
            'bays': [{'from': 'a', 'to': 'b', 'panel_model_number': '73014714'}],
            'purchase_lines': [
                {'manufacturer_model_number': sku, 'quantity_each': qty}
                for sku, qty in [('73014714', 1), ('73045785', 2), ('73013956', 2)]],
            'kit_contents': [{'component_key': 'end_u_channel', 'quantity_each': 2,
                              'edges': ['first_board_tongue', 'last_board_groove']}],
            'assembly_trace': [{'key': key} for key in ['attach_end_channels', 'insert_boards',
                                                       'place_top_rail', 'engage_second_post', 'fix_second_post']],
            'complete_installation_order': False,
        }

    def test_single_panel_counts(self):
        result = audit(self.example)
        self.assertTrue(result['example_checks_passed'], result['errors'])
        self.assertFalse(result['installation_ready'])

    def test_shared_posts_are_not_purchased_twice(self):
        e = self.example
        e['stations'] = [{'id': str(i), 'role': 'end' if i in (0, 3) else 'line'} for i in range(4)]
        e['bays'] = [{'from': str(i), 'to': str(i+1), 'panel_model_number': '73014714'} for i in range(3)]
        e['purchase_lines'] = [{'manufacturer_model_number': sku, 'quantity_each': qty}
                               for sku, qty in [('73014714', 3), ('73045785', 2), ('73045783', 2), ('73013956', 4)]]
        self.assertTrue(audit(e)['example_checks_passed'])
        e['purchase_lines'][2]['quantity_each'] = 4
        self.assertFalse(audit(e)['example_checks_passed'])

    def test_loose_rail_purchase_double_counts_kit_contents(self):
        self.example['purchase_lines'].append({'manufacturer_model_number': 'loose-rail', 'quantity_each': 2})
        self.assertFalse(audit(self.example)['example_checks_passed'])

    def test_line_post_cannot_terminate_this_run(self):
        self.example['stations'][1]['role'] = 'line'
        self.assertIn('post role differs', str(audit(self.example)['errors']))

    def test_second_post_cannot_be_fixed_before_panel_engages(self):
        trace = self.example['assembly_trace']
        trace[-1], trace[-2] = trace[-2], trace[-1]
        self.assertIn('engage_second_post before fix_second_post', str(audit(self.example)['errors']))

    def test_missing_channel_inventory_detected(self):
        self.example['kit_contents'] = []
        self.assertIn('two end U-channels', str(audit(self.example)['errors']))

    def test_handed_channel_edges_preserved(self):
        self.example['kit_contents'][0]['edges'] = ['first_board_tongue', 'last_board_tongue']
        self.assertIn('handedness lost', str(audit(self.example)['errors']))

    def test_duplicate_bay_is_not_a_second_panel(self):
        self.example['bays'].append(copy.deepcopy(self.example['bays'][0]))
        self.assertIn('duplicated bay endpoints', str(audit(self.example)['errors']))

    def test_incomplete_materials_cannot_claim_ready(self):
        self.example['complete_installation_order'] = True
        self.assertIn('unquantified installation materials', str(audit(self.example)['errors']))

    def complex_example(self):
        e = copy.deepcopy(self.example)
        e['layout_kind'] = 'orthogonal_open_runs'
        e['expected_run_count'] = 2
        points = [(0, 0), (1, 0), (2, 0), (3, 0), (3, 1), (3, 2), (0, 4), (1, 4), (2, 4)]
        roles = ['end', 'line', 'line', 'corner', 'line', 'end', 'end', 'line', 'end']
        e['stations'] = [{'id': str(i), 'role': role, 'schematic_point': list(point)}
                         for i, (role, point) in enumerate(zip(roles, points))]
        e['bays'] = [{'id': f'b{i}', 'from': str(i), 'to': str(i+1), 'panel_model_number': '73014714'}
                     for i in [0, 1, 2, 3, 4, 6, 7]]
        e['purchase_lines'] = [{'manufacturer_model_number': sku, 'quantity_each': qty}
                               for sku, qty in [('73014714', 7), ('73045785', 4), ('73045783', 4),
                                                ('73045784', 1), ('73013956', 9)]]
        e['build_runs'] = [{'id': 'A', 'station_order': [str(i) for i in range(6)]},
                           {'id': 'B', 'station_order': ['6', '7', '8']}]
        return e

    def test_corner_and_separate_run_counts(self):
        result = audit(self.complex_example())
        self.assertTrue(result['example_checks_passed'], result['errors'])
        self.assertEqual(result['unique_stations'], 9)
        self.assertEqual(result['connected_runs'], 2)
        self.assertEqual(result['kit_contained_u_channels'], 14)

    def test_corner_mislabeled_as_line_rejected_even_if_counts_match(self):
        e = self.complex_example()
        e['stations'][3]['role'] = 'line'
        e['purchase_lines'][2]['quantity_each'] = 5
        e['purchase_lines'].pop(3)
        self.assertIn('schematic angle', str(audit(e)['errors']))

    def test_missing_separate_run_end_post_rejected(self):
        e = self.complex_example()
        e['purchase_lines'][1]['quantity_each'] = 3
        self.assertFalse(audit(e)['example_checks_passed'])

    def test_missing_run_in_assembly_rejected(self):
        e = self.complex_example()
        e['build_runs'].pop()
        self.assertIn('omits or repeats a station', str(audit(e)['errors']))

    def test_each_post_fixed_once_and_each_receiving_post_engaged_first(self):
        result = audit(self.complex_example())
        fixed, engaged, starts = set(), set(), 0
        for event in result['assembly_simulation']:
            if event['action'] == 'engage_second_post':
                engaged.add(event['receiving_station'])
            elif event['action'] == 'fix_first_post':
                self.assertNotIn(event['station'], fixed)
                fixed.add(event['station'])
                starts += 1
            elif event['action'] == 'fix_second_post':
                sid = event['receiving_station']
                self.assertIn(sid, engaged)
                self.assertNotIn(sid, fixed)
                fixed.add(sid)
            elif event['action'] == 'insert_bottom_rail':
                self.assertIn(event['start_station'], fixed)
        self.assertEqual(len(fixed), 9)
        self.assertEqual(starts, 2)

    def test_coincident_station_identities_rejected(self):
        e = self.complex_example()
        e['stations'][6]['schematic_point'] = [0, 0]
        self.assertIn('same schematic point', str(audit(e)['errors']))

    def test_unsupported_branch_rejected(self):
        e = self.complex_example()
        e['bays'].append({'from': '2', 'to': '7', 'panel_model_number': '73014714'})
        self.assertFalse(audit(e)['example_checks_passed'])

    def test_crossing_disconnected_runs_rejected(self):
        e = self.complex_example()
        for station, point in zip(e['stations'][6:], [[2, -1], [2, 1], [2, 2]]):
            station['schematic_point'] = point
        self.assertIn('cross or overlap', str(audit(e)['errors']))

    def test_duplicate_bay_identity_rejected(self):
        e = self.complex_example()
        e['bays'][1]['id'] = e['bays'][0]['id']
        self.assertIn('duplicate bay identity', audit(e)['errors'])

    def test_duplicate_run_identity_rejected(self):
        e = self.complex_example()
        e['build_runs'][1]['id'] = e['build_runs'][0]['id']
        self.assertIn('duplicate build-run identity', audit(e)['errors'])
