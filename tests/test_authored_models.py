"""Admission boundaries use synthetic evidence, never manufacturer claims."""
import copy
import unittest

import context  # noqa: F401 -- repository imports for standalone unittest runs
from fence_evidence.authored_models import admit_authored_models, content_hash


class AuthoredModelTests(unittest.TestCase):
    def setUp(self):
        self.cite = {'id': 'test-ref', 'belongs_to': 'a' * 64}
        self.parts = [{'id': 'test/part', 'status': 'active', 'spec': [
            {'key': 'width_mm', 'value': self.q(10),
             'provenance': {'cites': [self.cite]}}]}]
        req = {'part_id': 'test/part', 'qty': self.q(1, 'each'),
               'length_rule': 'between_frame', 'overlap': self.q(0)}
        joint = {'kind': 'channel', 'channel_depth': self.q(10), 'insertion_margin': self.q(1)}
        slot = {'key': 'bottom', 'orientation': 'horizontal',
                'placement': {'kind': 'from_bottom', 'offset': self.q(10)},
                'joint': joint, 'requirement': req}
        top = copy.deepcopy(slot)
        top['key'] = 'top'
        top['placement']['kind'] = 'from_top'
        member = {'key': 'board', 'base_ref': 'bottom', 'top_ref': 'top',
                  'base_engagement': self.q(5), 'top_engagement': self.q(5),
                  'gap_after': self.q(0), 'face_offset': self.q(0),
                  'profile_edges': {'start': 'tongue', 'end': 'groove'},
                  'requirement': req}
        model = {'id': 'test/model', 'version': '1', 'status': 'active',
                 'name_i18n': {'en': 'Synthetic'}, 'authorship': 'third_party_authored',
                 'grade': 'residential', 'height_support': {'kind': 'discrete', 'heights': [self.q(100)]},
                 'option_axes': [], 'variants': [], 'layout_policy': [], 'assembly': [],
                 'cites': [self.cite], 'contributing_sources': ['a' * 64],
                 'default_spec': {'frame': [slot, top], 'infill': {
                     'orientation': 'vertical', 'pattern': [member], 'justification': 'start',
                     'excess': 'trim_last', 'edge_margin': self.q(0), 'supply': 'assembly'},
                     'fixings': []},
                 'post': {'key': 'post', 'requirement': req, 'joint': joint, 'cap': None}}
        self.record = {'model': copy.deepcopy(model), 'field_evidence': {}}
        def evidence(node, path=''):
            if isinstance(node, dict):
                for key, value in node.items():
                    pointer = path + '/' + key
                    self.record['field_evidence'][pointer] = [self.cite]
                    evidence(value, pointer)
            elif isinstance(node, list):
                for i, value in enumerate(node):
                    evidence(value, path + '/' + str(i))
        evidence(self.record['model'])
        self.review = self.make_review()

    @staticmethod
    def q(number, unit='mm'):
        return {'amount_milli': number * 1000, 'unit': unit, 'value_raw': [str(number)]}

    def make_review(self):
        return {'content_hash': content_hash(self.record, self.parts), 'decision': 'accepted',
                'reviewer_kind': 'human', 'reviewer': 'Synthetic test reviewer',
                'review_id': 'test-review', 'reviewed_at': '2026-09-06T00:00:00Z'}

    def run_gate(self, **overrides):
        args = dict(parts=self.parts, source_docs=[{'content_hash': 'a' * 64}],
                    source_refs=[self.cite], reviews=[self.review], model_validator=lambda m, p: [])
        args.update(overrides)
        return admit_authored_models([self.record], **args)

    def codes(self, result):
        return {i['code'] for e in result['exclusions'] for i in e['issues']}

    def test_positive_requires_external_semantic_validation(self):
        result = self.run_gate()
        self.assertEqual(result['exclusions'], [])
        self.assertEqual(len(result['models']), 1)
        result['models'][0]['id'] = 'changed'
        self.assertEqual(self.record['model']['id'], 'test/model')
        self.assertIn('consumer_validation_missing', self.codes(self.run_gate(model_validator=None)))
        self.assertIn('consumer_validation_failed', self.codes(self.run_gate(model_validator=lambda m, p: ['fit failed'])))

    def test_missing_review_and_embedded_claim_cannot_admit(self):
        self.record['review'] = self.review
        self.record['review_status'] = 'human_approved'
        self.assertIn('unreviewed_authored_model', self.codes(self.run_gate(reviews=[])))
        self.review['reviewer_kind'] = 'agent'
        self.assertIn('unreviewed_authored_model', self.codes(self.run_gate()))

    def test_review_binds_parts_and_field_evidence(self):
        for mutate in ('part', 'evidence', 'model'):
            with self.subTest(mutate=mutate):
                self.setUp()
                if mutate == 'part':
                    self.parts[0]['spec'][0]['value'] = self.q(20)
                elif mutate == 'evidence':
                    self.record['field_evidence']['/grade'] = []
                else:
                    self.record['model']['grade'] = 'commercial'
                self.assertIn('unreviewed_authored_model', self.codes(self.run_gate()))

    def test_latest_review_revokes_acceptance(self):
        rejection = dict(self.review, decision='rejected', reviewed_at='2026-09-06T01:00:00Z')
        self.assertIn('unreviewed_authored_model', self.codes(self.run_gate(reviews=[rejection, self.review])))

    def test_source_and_reference_closure(self):
        self.assertIn('citation_closure', self.codes(self.run_gate(source_docs=[])))
        self.assertIn('citation_closure', self.codes(self.run_gate(source_refs=[])))

    def test_geometry_refusals(self):
        for key, value, expected in [('channel_depth', self.q(0), 'invalid_quantity'),
                                     ('channel_depth', self.q(3), 'engagement_exceeds_channel'),
                                     ('insertion_margin', None, 'invalid_quantity')]:
            with self.subTest(key=key, value=value):
                self.setUp()
                self.record['model']['default_spec']['frame'][0]['joint'][key] = value
                self.review = self.make_review()
                self.assertIn(expected, self.codes(self.run_gate()))

    def test_explicit_quantities_and_fitting(self):
        self.record['model']['default_spec']['infill']['pattern'][0]['requirement'].pop('qty')
        self.assertIn('missing_value', self.codes(self.run_gate()))
        self.record['model']['default_spec']['infill']['justification'] = 'spread_to_fit'
        self.assertIn('unsupported_fitting', self.codes(self.run_gate()))

    def test_empty_identity_and_unhashable_shapes_refused(self):
        for value in (None, [], {}, ''):
            with self.subTest(value=value):
                self.record['model']['default_spec']['frame'][0]['key'] = value
                self.record['model']['default_spec']['infill']['pattern'][0]['base_ref'] = value
                self.assertIn('invalid_key', self.codes(self.run_gate()))
        self.assertTrue(admit_authored_models([None], parts=[], source_docs=[], source_refs=[], reviews=[])['exclusions'])

    def test_signed_overlap_and_offsets_are_valid(self):
        member = self.record['model']['default_spec']['infill']['pattern'][0]
        member['gap_after'] = self.q(-2)
        member['face_offset'] = self.q(-1)
        self.review = self.make_review()
        self.assertEqual(self.run_gate()['exclusions'], [])

    def test_duplicate_models_exclude_both_definitions(self):
        result = admit_authored_models([self.record, self.record], parts=self.parts,
                                      source_docs=[{'content_hash': 'a' * 64}],
                                      source_refs=[self.cite], reviews=[self.review],
                                      model_validator=lambda m, p: [])
        self.assertEqual(result['models'], [])
        self.assertEqual(len(result['exclusions']), 2)
        self.assertIn('duplicate_identity', self.codes(result))

    def test_referenced_part_containment_is_refused(self):
        self.parts[0]['contains'] = [{'part_id': 'test/child'}]
        self.parts.append({'id': 'test/child', 'spec': []})
        self.review = self.make_review()
        self.assertIn('unsupported_part_contains', self.codes(self.run_gate()))
        self.parts[1]['spec'] = [{'key': 'width_mm', 'value': self.q(100)}]
        self.assertIn('unsupported_part_contains', self.codes(self.run_gate()))
        self.assertEqual(self.run_gate()['models'], [])

    def test_duplicate_part_ids_refused_and_digest_order_stable(self):
        duplicate = copy.deepcopy(self.parts[0])
        duplicate['spec'][0]['value'] = self.q(20)
        self.parts.append(duplicate)
        before = content_hash(self.record, self.parts)
        self.parts.reverse()
        self.assertEqual(before, content_hash(self.record, self.parts))
        self.review = self.make_review()
        self.assertIn('duplicate_part_identity', self.codes(self.run_gate()))
        self.assertEqual(self.run_gate()['models'], [])

    def test_adversarial_review_cannot_bypass_preflight(self):
        mutations = [
            ('grade_evidence', 'uncited'), ('height_evidence', 'uncited'),
            ('spec_shape', 'missing_part_dimensions'), ('hidden_requirement_part', 'unsupported_requirement_contents'),
            ('assembly', 'unsupported_assembly'), ('fake_height', 'unsupported_height_support'),
            ('inactive_part', 'inactive_part')]
        for mutation, expected in mutations:
            with self.subTest(mutation=mutation):
                self.setUp()
                if mutation == 'grade_evidence':
                    self.record['field_evidence'].pop('/grade')
                elif mutation == 'height_evidence':
                    self.record['field_evidence']['/height_support'] = []
                elif mutation == 'spec_shape':
                    self.parts[0]['spec'] = {'width_mm': 10}
                elif mutation == 'hidden_requirement_part':
                    self.record['model']['default_spec']['frame'][0]['requirement']['contained'] = [{'part_id': 'hidden'}]
                elif mutation == 'assembly':
                    self.record['model']['assembly'] = [{'made_up': True}]
                elif mutation == 'fake_height':
                    self.record['model']['height_support'] = {'anything': True}
                else:
                    self.parts[0]['status'] = 'rejected'
                self.review = self.make_review()
                self.assertIn(expected, self.codes(self.run_gate()))
                self.assertEqual(self.run_gate()['models'], [])

    def test_identity_only_parts_refused(self):
        self.parts[0]['spec'] = []
        self.assertIn('missing_part_dimensions', self.codes(self.run_gate()))

    def test_draft_emblem_is_excluded_without_inventing_review(self):
        import json
        from pathlib import Path
        draft = Path(__file__).resolve().parents[1] / 'workspace/catalog/emblem-73014714-model-draft.json'
        if not draft.exists():
            self.skipTest('Private draft absent')
        record = json.loads(draft.read_text())
        result = admit_authored_models([record], parts=[], source_docs=[], source_refs=[], reviews=[])
        self.assertEqual(result['models'], [])
        self.assertIn('unreviewed_authored_model', self.codes(result))
        self.assertIn('missing_value', self.codes(result))


if __name__ == '__main__':
    unittest.main()
