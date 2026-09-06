"""Actual Emblem reference graphs are distinct from publication and derivation."""
from copy import deepcopy
import json
import unittest

from context import ROOT, requires_store
from fence_evidence.store import connect
from scripts.validate_emblem_instances import audit, reference_graph


class TestEmblemInstanceValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package = json.loads((ROOT / 'workspace/catalog/emblem-73014714-model-draft.json').read_text())
        cls.candidate = json.loads((ROOT / 'workspace/catalog/emblem-73014714-consumer-model.json').read_text())

    def test_actual_public_fragment_closes_draft_parts_without_claiming_publication(self):
        graph = reference_graph(self.package['model_fragment'], self.package['part_fragments'], [])
        self.assertTrue(graph['literal_part_closure'])
        self.assertTrue(graph['support_reference_closure'])
        self.assertFalse(graph['published_part_closure'])
        self.assertTrue(graph['requirements'])
        self.assertEqual({r['frame_key'] for r in graph['support_edges']}, {'bottom_rail', 'top_rail'})

    def test_actual_private_graph_exposes_missing_board_and_cap_definitions(self):
        parts = self.candidate['component_authoring']['private_parts']
        graph = reference_graph(self.candidate['model'], parts, [])
        missing = {r['part_id'] for r in graph['requirements']
                   if r['selection'] == 'literal' and r['definition_count'] == 0}
        self.assertEqual(missing, {
            'mfr/freedom-outdoor-living/emblem-73014714-board',
            'mfr/freedom-outdoor-living/73013956',
        })
        self.assertFalse(graph['literal_part_closure'])
        post = next(r for r in graph['requirements'] if r['path'] == '/post/requirement/part_id')
        self.assertEqual(post['selection'], 'predicate_or_unresolved')
        self.assertEqual(post['part_id'], '')

    def test_duplicate_referenced_part_is_ambiguous_even_when_other_parts_exist(self):
        parts = deepcopy(self.package['part_fragments'])
        duplicate = deepcopy(parts[0])
        duplicate['name_i18n'] = {'en': 'Conflicting definition'}
        parts.append(duplicate)
        graph = reference_graph(self.package['model_fragment'], parts, [])
        self.assertFalse(graph['literal_part_closure'])
        self.assertIn(duplicate['id'], graph['duplicate_part_ids'])
        self.assertEqual(next(r['definition_count'] for r in graph['requirements']
                              if r['part_id'] == duplicate['id']), 2)

    def test_existing_part_does_not_repair_wrong_support_relationship(self):
        model = deepcopy(self.package['model_fragment'])
        model['default_spec']['infill']['pattern'][0]['top_ref'] = 'absent_rail'
        graph = reference_graph(model, self.package['part_fragments'], [])
        self.assertTrue(graph['literal_part_closure'])
        self.assertFalse(graph['support_reference_closure'])
        missing = next(r for r in graph['support_edges'] if r['edge'] == 'top_ref')
        self.assertEqual(missing['definition_count'], 0)

    def test_empty_or_malformed_graph_never_reports_coverage(self):
        for model in ({}, None, {'default_spec': []},
                      {'default_spec': {'frame': [None], 'infill': {'pattern': [None]}}}):
            with self.subTest(model=model):
                graph = reference_graph(model, [None, {'id': []}], [])
                self.assertFalse(graph['literal_part_closure'])
                self.assertFalse(graph['published_part_closure'])
                self.assertFalse(graph['support_reference_closure'])

    def test_unhashable_supports_and_duplicate_frame_targets_are_not_valid_edges(self):
        for mutation in ('unhashable_support', 'duplicate_frame'):
            model = deepcopy(self.package['model_fragment'])
            if mutation == 'unhashable_support':
                model['default_spec']['infill']['pattern'][0]['top_ref'] = []
            else:
                model['default_spec']['frame'].append(deepcopy(model['default_spec']['frame'][0]))
            with self.subTest(mutation=mutation):
                graph = reference_graph(model, self.package['part_fragments'], [])
                self.assertFalse(graph['support_reference_closure'])

    @requires_store
    def test_stale_candidate_package_binding_is_reported_with_real_snapshot_refusal(self):
        candidate = deepcopy(self.candidate)
        candidate['source_package_hash'] = '0' * 64
        conn = connect(read_only=True)
        try:
            result = audit(self.package, candidate, conn)
        finally:
            conn.close()
        self.assertFalse(result['candidate_declares_current_source_package_hash'])
        self.assertFalse(result['candidate_reproduces_from_checked_inputs'])
        self.assertTrue(result['snapshot']['verified'])
        self.assertFalse(result['complete_model_admitted'])
        self.assertEqual(result['snapshot']['models'], 0)
        self.assertTrue(result['snapshot']['authored_model_gaps'])
        self.assertTrue(result['source_file_checks'])
        self.assertTrue(all(s['matches'] for s in result['source_file_checks']))
        self.assertTrue(result['canonical_source_ref_checks'])
        self.assertTrue(all(r['canonical_locus_matches'] for r in result['canonical_source_ref_checks']))

    @requires_store
    def test_copied_package_hash_does_not_authenticate_altered_candidate(self):
        candidate = deepcopy(self.candidate)
        candidate['model']['default_spec']['infill']['pattern'][0]['requirement']['qty'] = 99
        confirmation = json.loads((ROOT / 'workspace/catalog/emblem-73014714-placement-confirmation.json').read_text())
        conn = connect(read_only=True)
        try:
            baseline = audit(self.package, self.candidate, conn, confirmation)
            result = audit(self.package, candidate, conn, confirmation)
        finally:
            conn.close()
        self.assertTrue(baseline['candidate_reproduces_from_checked_inputs'])
        self.assertTrue(result['candidate_declares_current_source_package_hash'])
        self.assertFalse(result['candidate_reproduces_from_checked_inputs'])
        self.assertFalse(result['complete_model_admitted'])
        self.assertNotEqual(baseline['artifact_hashes']['private_candidate'],
                            result['artifact_hashes']['private_candidate'])


if __name__ == '__main__':
    unittest.main()
