"""Layout transformations must preserve demand and its calculation traces."""
import json
import random
import unittest
from copy import deepcopy

from context import ROOT
from fence_evidence.purchase_preview import generate


class TestLayoutTransformations(unittest.TestCase):
    def check_scenario(self, scenario):
        package = json.loads((ROOT / 'workspace/catalog/emblem-73014714-model-draft.json').read_text())
        layout = json.loads((ROOT / f'workspace/catalog/emblem-{scenario}-layout.json').read_text())
        baseline = generate(package, layout)
        for seed in range(40):
            with self.subTest(scenario=scenario, seed=seed):
                transformed = deepcopy(layout)
                randomizer = random.Random(seed)
                randomizer.shuffle(transformed['stations'])
                randomizer.shuffle(transformed['bays'])
                for station in transformed['stations']:
                    x, y = station['schematic_point']
                    station['schematic_point'] = [-3*y+17, 3*x-11]
                for bay in transformed['bays']:
                    if randomizer.choice([True, False]):
                        bay['from'], bay['to'] = bay['to'], bay['from']
                result = generate(package, transformed)
                self.assertEqual(result['purchase_lines'], baseline['purchase_lines'])
                self.assertEqual(result['station_roles'], baseline['station_roles'])
                for line in result['purchase_lines']:
                    self.assertEqual(sum(d['quantity_each'] for d in line['quantity_derivations']),
                                     line['quantity_each'])

    def test_single_panel(self):
        self.check_scenario('single')

    def test_seven_panels_with_corner_and_separate_run(self):
        self.check_scenario('complex')
