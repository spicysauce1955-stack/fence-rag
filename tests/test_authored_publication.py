"""Authored candidates must leave an actionable refusal in the real snapshot."""
import json
import unittest
from unittest.mock import Mock, patch

from context import ROOT, requires_store
from fence_evidence.authored_publication import build_authored_models
from fence_evidence.snapshot import SnapshotBuilder, build_snapshot, verify
from fence_evidence.store import connect


class TestAuthoredPublication(unittest.TestCase):
    def test_empty_input_does_not_touch_the_store(self):
        builder = Mock()
        self.assertEqual(build_authored_models(builder, [], []), [])
        self.assertEqual(builder.mock_calls, [])

    def test_a_forged_hash_is_not_registered_as_source_evidence(self):
        builder = Mock(tenant='default')
        builder.source_docs.return_value = []
        record = {'model': {'id': 'm', 'cites': [{'id': 'r', 'belongs_to': 'forged'}]}}
        locus = Mock(sha256='actual')
        with patch('fence_evidence.authored_publication.build_index', return_value={'r': locus}):
            self.assertEqual(build_authored_models(builder, [record], []), [])
        builder.source_ref.assert_not_called()
        builder.source_ref_page.assert_not_called()
        self.assertTrue(builder.gap.called)

    @requires_store
    def test_real_draft_remains_excluded_and_both_owners_get_actionable_gaps(self):
        package = json.loads((ROOT / 'workspace/catalog/emblem-73014714-model-draft.json').read_text())
        snapshot = build_snapshot(tenant='default', authored_records=[package])
        verify(snapshot)
        self.assertEqual(snapshot['models'], [])
        gaps = {g['because']['code']: g for g in snapshot['gaps']
                if g['because']['code'].startswith('authored_model_')}
        self.assertEqual(set(gaps), {'authored_model_not_admitted', 'authored_model_consumer_unavailable'})
        self.assertEqual(gaps['authored_model_not_admitted']['closes_by'], 'knowledge')
        self.assertEqual(gaps['authored_model_consumer_unavailable']['closes_by'], 'planning')
        for gap in gaps.values():
            self.assertEqual(gap['subject']['id'], package['model_fragment']['id'])
            self.assertTrue(gap['would_close'])
            self.assertTrue(gap['because']['params']['paths'])
            self.assertTrue(gap['cites'])

    def test_duplicate_exclusions_are_merged_before_builder_deduplication(self):
        builder = Mock(tenant='default')
        builder.source_docs.return_value = []
        exclusions = [{'model_id': 'm', 'content_hash': 'h', 'would_close': 'Fix inputs.',
                       'issues': [{'path': path, 'code': 'missing_value', 'message': 'Missing.'}]}
                      for path in ('/first', '/second')]
        with patch('fence_evidence.authored_publication.build_index', return_value={}), \
                patch('fence_evidence.authored_publication.admit_authored_models',
                      return_value={'models': [], 'exclusions': exclusions}):
            build_authored_models(builder, [{'model': {'id': 'm'}}], [])
        builder.gap.assert_called_once()
        self.assertEqual(builder.gap.call_args.kwargs['params']['paths'], ['/first', '/second'])

    @requires_store
    def test_page_reference_is_bound_to_the_requested_content_version(self):
        package = json.loads((ROOT / 'workspace/catalog/emblem-73014714-model-draft.json').read_text())
        source = package['sources'][0]
        conn = connect(read_only=True)
        try:
            builder = SnapshotBuilder(conn, tenant='default', regime='us_astm')
            with self.assertRaises(KeyError):
                builder.source_ref_page(source['document_id'], 1, content_hash='0' * 64)
            self.assertEqual(builder.source_docs(), [])
            ref = builder.source_ref_page(source['document_id'], 1, content_hash=source['content_hash'])
            self.assertEqual(ref.belongs_to, source['content_hash'])
        finally:
            conn.close()

    def test_nullable_fields_survive_builder_gap_deduplication(self):
        builder = Mock(tenant='default')
        builder.source_docs.return_value = []
        gaps = [{'model_id': 'm', 'path': path, 'kind': 'missing_value',
                 'code': 'authored_model_incomplete_value', 'closes_by': 'knowledge',
                 'would_close': 'Supply ' + path, 'cites': []}
                for path in ('/post', '/default_spec/frame/0/joint/insertion_margin',
                             '/default_spec/frame/1/joint/insertion_margin')]
        with patch('fence_evidence.authored_publication.build_index', return_value={}), \
                patch('fence_evidence.authored_publication.admit_authored_models',
                      return_value={'models': [], 'exclusions': [], 'gaps': gaps}):
            build_authored_models(builder, [{'model': {'id': 'm'}}], [])
        builder.gap.assert_called_once()
        emitted = builder.gap.call_args.kwargs
        self.assertEqual(emitted['params']['paths'], sorted(g['path'] for g in gaps))
        self.assertEqual(emitted['closes_by'], 'knowledge')
        for gap in gaps:
            self.assertIn(gap['would_close'], emitted['would_close'])

    @requires_store
    def test_real_snapshot_preserves_both_unknown_margins_with_source_context(self):
        package = json.loads((ROOT / 'workspace/catalog/emblem-73014714-model-draft.json').read_text())
        for frame in package['model_fragment']['default_spec']['frame']:
            frame['joint']['insertion_margin'] = None
        snapshot = build_snapshot(tenant='default', authored_records=[package])
        verify(snapshot)
        gaps = [g for g in snapshot['gaps']
                if g['because']['code'] == 'authored_model_incomplete_value']
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]['because']['params']['paths'], [
            '/default_spec/frame/0/joint/insertion_margin',
            '/default_spec/frame/1/joint/insertion_margin'])
        self.assertTrue(gaps[0]['cites'])
        self.assertEqual(snapshot['models'], [])
