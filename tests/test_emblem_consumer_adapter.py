"""Adversarial checks of the current engine's Emblem admission boundary."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import unittest

from context import ROOT
from scripts.emblem_consumer_adapter import (
    AdaptationRefused, adapt_candidate, inspect_candidate,
)


class TestEmblemConsumerBoundary(unittest.TestCase):
    def setUp(self):
        self.candidate = json.loads((ROOT / 'workspace/catalog/emblem-73014714-consumer-model.json').read_text())

    def test_current_candidate_has_specific_data_and_engine_gaps(self):
        spec = self.candidate['model']['default_spec']
        spec['frame'][0]['requirement'].pop('qty', None)
        spec['frame'][0].pop('channel_depth_mm', None)
        spec['infill'].pop('justification', None)
        spec['infill']['pattern'][0]['requirement'].pop('length_rule', None)
        before = deepcopy(self.candidate)
        report = inspect_candidate(self.candidate)
        codes = {issue['code'] for issue in report['issues']}
        self.assertTrue({'unsupported_handed_geometry', 'unsupported_kit_geometry_credit',
                         'invalid_channel_depth', 'missing_board_length_rule',
                         'missing_explicit_quantity', 'missing_fitting_rule'} <= codes)
        self.assertFalse(report['ready'])
        self.assertFalse(report['semantic_validation_executed'])
        self.assertEqual(self.candidate, before)

    def test_approval_booleans_and_deleted_edge_metadata_cannot_enable_adaptation(self):
        self.candidate.update(publishable=True, bom_generation_verified=True)
        self.candidate['component_authoring'].update(
            handed_placement_consumed=True, kit_purchase_credit_consumed=True)
        self.candidate['model']['default_spec']['infill']['pattern'][0].pop('profile_edges', None)
        with self.assertRaises(AdaptationRefused) as caught:
            adapt_candidate(self.candidate)
        codes = {issue['code'] for issue in caught.exception.report['issues']}
        self.assertIn('unsupported_handed_geometry', codes)
        self.assertIn('unsupported_kit_geometry_credit', codes)

    def test_empty_and_malformed_shapes_have_controlled_refusal(self):
        for value in (None, [], {}, {'model': []}):
            with self.subTest(value=value), self.assertRaises(AdaptationRefused):
                adapt_candidate(value)
        for spec in (None, {}, {'frame': [None], 'infill': {'pattern': [False]}}):
            self.candidate['model']['default_spec'] = spec
            with self.subTest(spec=spec), self.assertRaises(AdaptationRefused):
                adapt_candidate(self.candidate)

    def test_boolean_quantity_and_depth_do_not_pass_as_integer(self):
        slot = self.candidate['model']['default_spec']['frame'][0]
        slot.update(channel_depth_mm=True)
        slot['requirement']['qty'] = True
        codes = {issue['code'] for issue in inspect_candidate(self.candidate)['issues']}
        self.assertIn('invalid_channel_depth', codes)
        self.assertIn('missing_explicit_quantity', codes)

    def test_different_product_is_not_treated_as_emblem(self):
        self.candidate['model']['id'] = 'other'
        self.assertEqual(inspect_candidate(self.candidate)['issues'][0]['code'], 'wrong_model')

    def test_real_parser_acceptance_does_not_enable_bom(self):
        consumer = Path(os.environ.get('FENCE_PLANNING_ROOT', '/tmp/fence-planning-bom'))
        python = consumer / '.venv/bin/python'
        if not python.exists():
            self.skipTest('Planning Python environment not present')
        program = '''
import json, sys
sys.path.insert(0, sys.argv[1] + '/src')
from fenceai.fencemodel.model import FenceModel, validate_model
from fenceai.catalog.model import Catalog
from scripts.emblem_consumer_adapter import inspect_candidate
with open(sys.argv[2]) as source:
    candidate = json.load(source)
report = inspect_candidate(candidate, FenceModel)
# Probe an attempted kit credit against real, drawn rail/board slots.
candidate['model']['default_spec']['fixings'][0]['requirement']['credits'] = {
    'kit_rail': 'bottom_rail', 'kit_board': 'board'}
model = FenceModel.model_validate(candidate['model'])
report['credit_probe_errors'] = validate_model(model, Catalog())
print(json.dumps(report))
'''
        run = subprocess.run([str(python), '-c', program, str(consumer),
                              str(ROOT / 'workspace/catalog/emblem-73014714-consumer-model.json')],
                             cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        report = json.loads(run.stdout)
        self.assertTrue(report['parser_accepts'])
        self.assertFalse(report['ready'])
        if report['capability_probe'].get('handed_geometry'):
            self.assertNotIn('/default_spec/infill/pattern/0/profile_edges', report['unconsumed_paths'])
            self.assertTrue(report['capability_probe']['drawn_purchase_credits'])
        else:
            self.assertIn('/default_spec/infill/pattern/0/profile_edges', report['unconsumed_paths'])
        for target in ('bottom_rail', 'board'):
            self.assertTrue(any(f'credits slot {target}, which is drawn at a position' in error
                                for error in report['credit_probe_errors']))


if __name__ == '__main__':
    unittest.main()
