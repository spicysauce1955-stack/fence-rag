"""Private mapping must not fill unknown geometry or erase source assertions."""
from copy import deepcopy
import json
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
