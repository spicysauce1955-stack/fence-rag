"""Negative controls for the private draft audit, independent of the corpus."""
import hashlib
import unittest
from unittest.mock import patch

import context  # noqa: F401
from scripts.audit_model_draft import audit, fitting_readiness


class TestModelDraftAudit(unittest.TestCase):
    def setUp(self):
        self.package = {
            'publishable': False, 'sources': [], 'source_docs': [],
            'confirmed_readings': [],
            'part_fragments': [{'id': 'rail', 'type': {'namespace': 'shared', 'key': 'rail'},
                                'cites': [], 'contributing_sources': []}],
            'model_fragment': {
                'id': 'model', 'cites': [], 'contributing_sources': [],
                'default_spec': {
                    'frame': [{'key': 'bottom', 'requirement': {'part_id': 'rail'}},
                              {'key': 'top', 'requirement': {'part_id': 'rail'}}],
                    'infill': {'pattern': [{'key': 'board', 'base_ref': 'bottom',
                                           'top_ref': 'top', 'requirement': {'part_id': 'rail'}}]},
                },
                'post': {'key': 'post'},
            },
        }

    def result(self):
        with patch('scripts.audit_model_draft.build_index', return_value={}):
            return audit(self.package, None)

    def test_incomplete_is_not_contract_valid(self):
        result = self.result()
        self.assertTrue(result['draft_integrity_passed'])
        self.assertEqual(result['contract_validity'], 'incomplete')
        paths = {item['path'] for item in result['missing_contract_fields']}
        self.assertIn('/model_fragment/height_support', paths)
        self.assertIn('/part_fragments/0/spec', paths)

    def external_fixture(self):
        self.package['external_applicability_evidence'] = {
            'download_path': 'workspace/catalog/emblem-linked-installation.pdf',
            'download_sha256': hashlib.sha256(b'fixture').hexdigest(),
        }
        self.package['connection_evidence'] = [
            {'evidence_anchor': {'text_raw': 'Boards enter rail'}}]

    def test_missing_optional_manual_is_explicitly_unchecked(self):
        self.external_fixture()
        with patch('pathlib.Path.is_file', return_value=False):
            result = self.result()
        self.assertTrue(result['draft_integrity_passed'])
        self.assertEqual(result['external_applicability_check'], 'not_checked_cache_missing')
        self.assertFalse(self.package['publishable'])

    def test_corrupt_cached_manual_fails(self):
        self.external_fixture()
        with patch('pathlib.Path.is_file', return_value=True), \
                patch('pathlib.Path.read_bytes', return_value=b'wrong'):
            result = self.result()
        self.assertFalse(result['draft_integrity_passed'])
        self.assertEqual(result['external_applicability_check'], 'failed')

    def test_cached_manual_requires_hash_and_statement_match(self):
        self.external_fixture()
        with patch('pathlib.Path.is_file', return_value=True), \
                patch('pathlib.Path.read_bytes', return_value=b'fixture'), \
                patch('scripts.audit_model_draft.subprocess.check_output',
                      return_value=b'Boards\nenter rail'):
            self.assertEqual(self.result()['external_applicability_check'], 'verified')
        with patch('pathlib.Path.is_file', return_value=True), \
                patch('pathlib.Path.read_bytes', return_value=b'fixture'), \
                patch('scripts.audit_model_draft.subprocess.check_output',
                      return_value=b'Unrelated text'):
            result = self.result()
        self.assertFalse(result['draft_integrity_passed'])
        self.assertEqual(result['external_applicability_check'], 'failed')

    def test_missing_part_rejected(self):
        self.package['model_fragment']['default_spec']['frame'][0]['requirement']['part_id'] = 'absent'
        self.assertIn('unresolved Part reference', str(self.result()['errors']))

    def test_missing_slot_rejected(self):
        self.package['model_fragment']['default_spec']['infill']['pattern'][0]['base_ref'] = 'absent'
        self.assertIn('unresolved FrameSlot reference', str(self.result()['errors']))

    def test_authored_role_rejected(self):
        self.package['model_fragment']['default_spec']['frame'][0]['requirement']['role'] = 'frame'
        self.assertIn('role must be derived', str(self.result()['errors']))

    def test_incomplete_cannot_claim_publishable(self):
        self.package['publishable'] = True
        self.assertIn('incomplete draft incorrectly claims publishable', self.result()['errors'])

    def test_bad_citation_rejected(self):
        self.package['model_fragment']['cites'] = [{'id': 'absent', 'belongs_to': 'absent'}]
        self.assertIn('citation does not resolve', str(self.result()['errors']))

    def test_duplicate_frame_key_rejected(self):
        self.package['model_fragment']['default_spec']['frame'][1]['key'] = 'bottom'
        self.assertIn('duplicate FrameSlot.key', self.result()['errors'])

    def test_noninteger_quantity_rejected(self):
        self.package['quantity_probe'] = {'amount_milli': True, 'unit': 'mm', 'value_raw': ['1']}
        self.assertIn('integer thousandths', str(self.result()['errors']))

    def test_wrong_conversion_rejected(self):
        self.package['confirmed_readings'] = [{
            'key': 'width', 'value': {'amount_milli': 94000, 'unit': 'mm', 'value_raw': ['94in. W']},
            'evidence_anchor': {'text_raw': '72in. H x 94in. W'},
        }]
        self.assertIn('incorrect inch-to-millimetre conversion', str(self.result()['errors']))

    def test_nominal_width_does_not_unlock_fitting(self):
        self.package['part_fragments'][0]['spec'] = [
            {'key': 'nominal_width_mm', 'value': {'amount_milli': 152400, 'unit': 'mm', 'value_raw': ['6 in.']}}]
        result = fitting_readiness(self.package)
        self.assertIn('board[0].Part.spec.width_mm', result['missing_inputs'])
        self.assertEqual(result['status'], 'blocked')
        self.assertIsNone(result['board_count'])

    def test_channel_kind_does_not_hide_missing_depth(self):
        self.package['model_fragment']['default_spec']['frame'][0]['joint'] = {'kind': 'channel'}
        result = self.result()
        self.assertIn('/model_fragment/default_spec/frame/0/joint/channel_depth',
                      {item['path'] for item in result['missing_contract_fields']})

    def test_missing_stock_length_blocks_cut_list(self):
        result = fitting_readiness(self.package)
        self.assertIn('frame.top.Part.spec.nominal_length_mm', result['missing_inputs'])
        self.assertIsNone(result['cut_lengths'])

    def test_specs_require_provenance_and_exact_evidence(self):
        self.package['part_fragments'][0]['spec'] = [
            {'key': 'width_mm', 'agree': '==', 'value': {'amount_milli': 127000, 'unit': 'mm', 'value_raw': ['5in.']}}]
        errors = str(self.result()['errors'])
        self.assertIn('incomplete spec provenance', errors)
        self.assertIn('missing exact spec evidence', errors)

    def test_corrupted_spec_conversion_rejected(self):
        cite = {'id': 'ref', 'belongs_to': 'source'}
        self.package['part_fragments'][0]['spec'] = [{
            'key': 'width_mm', 'agree': '==',
            'value': {'amount_milli': 5000, 'unit': 'mm', 'value_raw': ['5in.']},
            'provenance': {'cites': [cite], 'curation_level': 0, 'version_status': 'unknown'}}]
        self.package['spec_evidence'] = [{'part_id': 'rail', 'spec_key': 'width_mm',
                                          'anchor': {'text_raw': '5in.', 'cite': cite}}]
        self.assertIn('incorrect spec conversion', str(self.result()['errors']))
