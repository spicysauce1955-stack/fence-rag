"""Model changes must affect preview output; input layouts contain no answers."""
import copy
import unittest

import context  # noqa: F401
from fence_evidence.purchase_preview import generate, PreviewError


class TestPurchasePreview(unittest.TestCase):
    def setUp(self):
        def anchor(text):
            return {'text_raw': text, 'element_id': 'e', 'cite': {'id': 'r', 'belongs_to': 'source'}}
        def part(pid, kind):
            return {'id': pid, 'type': {'namespace': 'shared', 'key': kind}, 'name_i18n': {'en': pid}}
        self.package = {
            'scope': {'model_number': 'KIT-X'}, 'identity_anchors': [anchor('KIT-X')],
            'source_docs': [{'content_hash': 'source'}],
            'part_fragments': [part(pid, kind) for pid, kind in [('rail', 'rail'), ('board', 'infill'),
                              ('end', 'post'), ('line', 'post'), ('corner', 'post'), ('cap', 'post_cap')]],
            'part_identity_anchors': [
                {'part_id': role, 'post_role': role, 'description': anchor(role + ' post'),
                 'model_number': anchor('PRODUCT-' + role)} for role in ['end', 'line', 'corner']
            ] + [{'part_id': 'cap', 'description': anchor('post top'), 'model_number': anchor('CAP-X')}],
            'model_fragment': {'id': 'model', 'name_i18n': {'en': 'Kit model'},
                'default_spec': {'frame': [{'key': 'bottom', 'requirement': {'part_id': 'rail'}},
                                          {'key': 'top', 'requirement': {'part_id': 'rail'}}],
                                 'infill': {'pattern': [{'key': 'board', 'requirement': {'part_id': 'board'}}]}},
                'post': {'cap': {'part_id': 'cap'}}},
            'pending_bindings': [{'target': '/model_fragment/post/requirement',
                                  'candidates': [{'post_role': r, 'part_id': r} for r in ['end', 'line', 'corner']]}],
            'purchase_projection': {'panel_kit_covers': [
                {'slot_kind': kind, 'slot_key': key, 'part_id': pid} for kind, key, pid in
                [('frame', 'bottom', 'rail'), ('frame', 'top', 'rail'), ('infill', 'board', 'board')]]},
            'packaged_assembly_inventory': [{'component_key': 'boards', 'quantity_each': None}],
        }
        self.layout = {'kind': 'full_panel_schematic', 'expected_run_count': 1,
                       'stations': [{'id': 'a', 'schematic_point': [0, 0]}, {'id': 'b', 'schematic_point': [1, 0]}],
                       'bays': [{'id': 'bay', 'from': 'a', 'to': 'b', 'model_id': 'model', 'supply': 'full_kit'}]}

    def counts(self):
        return {line['manufacturer_model_number']: line['quantity_each']
                for line in generate(self.package, self.layout)['purchase_lines']}

    def test_reads_model_identities_not_hardcoded_emblem_numbers(self):
        self.assertEqual(self.counts(), {'KIT-X': 1, 'PRODUCT-end': 2, 'CAP-X': 2})

    def test_cap_model_change_changes_output(self):
        self.package['part_identity_anchors'][-1]['model_number']['text_raw'] = 'CAP-Y'
        self.assertIn('CAP-Y', self.counts())
        self.assertNotIn('CAP-X', self.counts())

    def test_explicit_no_cap_removes_demand(self):
        self.package['model_fragment']['post']['cap'] = None
        self.assertEqual(self.counts(), {'KIT-X': 1, 'PRODUCT-end': 2})

    def test_missing_cap_is_not_no_cap(self):
        del self.package['model_fragment']['post']['cap']
        with self.assertRaisesRegex(PreviewError, 'cap requirement is missing'):
            self.counts()

    def test_wrong_cap_type_fails(self):
        self.package['model_fragment']['post']['cap']['part_id'] = 'end'
        with self.assertRaisesRegex(PreviewError, 'wrong Part type'):
            self.counts()

    def test_missing_identity_fails(self):
        self.package['part_identity_anchors'].pop()
        with self.assertRaisesRegex(PreviewError, 'identity missing'):
            self.counts()

    def test_swapped_post_candidates_fail(self):
        self.package['pending_bindings'][0]['candidates'][0]['part_id'] = 'line'
        with self.assertRaisesRegex(PreviewError, 'post-role binding'):
            self.counts()

    def test_missing_kit_coverage_fails(self):
        self.package['purchase_projection']['panel_kit_covers'].pop()
        with self.assertRaisesRegex(PreviewError, 'kit coverage'):
            self.counts()

    def test_different_model_fails(self):
        self.layout['bays'][0]['model_id'] = 'other'
        with self.assertRaisesRegex(PreviewError, 'different model'):
            self.counts()

    def test_cut_intent_cannot_be_silently_ignored(self):
        self.layout['bays'][0]['cut_length_mm'] = 1000
        with self.assertRaisesRegex(PreviewError, 'unsupported bay fields'):
            self.counts()

    def test_rejects_example_answers_as_layout_input(self):
        self.layout['purchase_lines'] = [{'manufacturer_model_number': 'WRONG', 'quantity_each': 999}]
        with self.assertRaisesRegex(PreviewError, 'unsupported layout fields'):
            self.counts()

    def test_unknown_board_count_preserved(self):
        out = generate(self.package, self.layout)
        self.assertIsNone(out['covered_kit_inventory_per_bay'][0]['quantity_each'])
        self.assertFalse(out['publishable'])
        self.assertFalse(out['source_identity_verified'])

    def test_is_deterministic_and_does_not_mutate_inputs(self):
        before = copy.deepcopy((self.package, self.layout))
        self.assertEqual(generate(self.package, self.layout), generate(self.package, self.layout))
        self.assertEqual(before, (self.package, self.layout))

    def test_corner_role_derived_without_role_answers(self):
        self.layout['stations'].append({'id': 'c', 'schematic_point': [1, 1]})
        self.layout['bays'].append({'id': 'bay2', 'from': 'b', 'to': 'c', 'model_id': 'model', 'supply': 'full_kit'})
        self.assertEqual(self.counts(), {'KIT-X': 2, 'PRODUCT-end': 2, 'PRODUCT-corner': 1, 'CAP-X': 3})

    def test_does_not_override_future_contract_requirement(self):
        self.package['model_fragment']['post']['requirement'] = {'part_id': 'end'}
        with self.assertRaisesRegex(PreviewError, 'must not override'):
            self.counts()

    def test_additional_fixings_are_not_silently_omitted(self):
        self.package['model_fragment']['default_spec']['fixings'] = [{'key': 'extra-bracket'}]
        with self.assertRaisesRegex(PreviewError, 'fixings need explicit'):
            self.counts()

    def test_post_reinforcement_is_not_silently_omitted(self):
        self.package['model_fragment']['post']['contains'] = [{'key': 'insert'}]
        with self.assertRaisesRegex(PreviewError, 'reinforcement or containment'):
            self.counts()

    def test_rail_containment_is_not_silently_omitted(self):
        self.package['model_fragment']['default_spec']['frame'][0]['contains'] = [{'key': 'insert'}]
        with self.assertRaisesRegex(PreviewError, 'contained panel parts'):
            self.counts()

    def test_incompatible_kit_and_cap_identity_collision_rejected(self):
        self.package['part_identity_anchors'][-1]['model_number']['text_raw'] = 'KIT-X'
        with self.assertRaisesRegex(PreviewError, 'incompatible purchase meanings'):
            self.counts()

    def test_surface_mount_intent_is_not_silently_ignored(self):
        self.layout['stations'][0]['mounting'] = 'surface_mounted'
        with self.assertRaisesRegex(PreviewError, 'unsupported station intent'):
            self.counts()

    def test_empty_manifest_cannot_claim_verified_evidence(self):
        self.package['sources'] = []
        with self.assertRaisesRegex(PreviewError, 'source manifest does not cover'):
            generate(self.package, self.layout, conn=object())
