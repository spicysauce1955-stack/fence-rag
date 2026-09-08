"""Augusta assembly slice: composition membership, authored counts and the
model candidate's honest exclusions stay separate from published Parts."""
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from context import ROOT, requires_store
from pathlib import Path
from fence_evidence import augusta_drawing_claims as recipe
from fence_evidence.part_types import (AUGUSTA_COMPONENT_IDS, PartTypeRegistry,
                                       build_part_types, load_augusta_components)
from fence_evidence.parameters import _default_source_ref
from fence_evidence.parts import build_parts
from fence_evidence.store import connect
from fence_evidence.snapshot import build_snapshot, verify

DRAFT = ROOT / 'workspace/catalog/augusta-8x6-model-draft.json'


class TestAugustaComposition(unittest.TestCase):
    def test_components_carry_authored_counts_with_bases(self):
        components = load_augusta_components()
        self.assertEqual({c['component_id'] for c in components},
                         set(AUGUSTA_COMPONENT_IDS))
        by_id = {c['component_id']: c for c in components}
        self.assertEqual(by_id['wea-augusta-rail-slotted']['qty_per_panel'], 3)
        self.assertEqual(by_id['wea-augusta-u-channel']['qty_per_panel'], 4)
        self.assertIn('material list', by_id['wea-augusta-u-channel']['qty_per_panel_basis'])
        self.assertIn('39.5', by_id['wea-augusta-u-channel']['qty_per_panel_basis'])
        self.assertTrue(by_id['wea-augusta-rail-slotted']['qty_per_panel_basis'])
        # Picket and post counts are absent, not zero.
        self.assertEqual(by_id['wea-augusta-picket-tg']['qty_per_panel'], 22)
        self.assertEqual(by_id['wea-augusta-metal-insert']['qty_per_panel'], 3)
        self.assertNotIn('qty_per_panel', by_id['wea-augusta-post-5x5'])

    def test_composition_resolves_spine_without_gaps(self):
        registry = PartTypeRegistry('Weatherables')
        types, gaps = build_part_types(load_augusta_components(), registry)
        self.assertEqual(gaps, [])
        keys = {(t['namespace'], t['key']) for t in types}
        self.assertIn(('mfr/weatherables', 'picket'), keys)


class TestAugustaConsumerCandidate(unittest.TestCase):
    """The private consumer candidate converts units honestly and never
    mis-models the two stacked rows as an alternating pattern."""

    def setUp(self):
        self.candidate = json.loads(
            (ROOT / 'workspace/catalog/augusta-8x6-consumer-model.json').read_text())
        self.model = self.candidate['model']

    def test_offsets_are_centerlines_in_millimetre_magnitude(self):
        offsets = [slot['placement']['offset_mm']
                   for slot in self.model['default_spec']['frame']]
        # Exact centerlines 69.85/1212.85/2355.85 floor to whole mm with the
        # losses recorded; every offset is mm-magnitude, never raw milli-mm.
        self.assertEqual(offsets, [69, 1212, 2355])
        for value in offsets:
            self.assertLess(value, 3000, 'offset must be mm, not raw milli-mm')
        losses = self.candidate['transformation_evidence']['precision_losses']
        offset_losses = [l for l in losses if l['field'] == 'placement/offset']
        self.assertEqual(len(offset_losses), 3)
        self.assertAlmostEqual(offset_losses[0]['exact_mm'], 69.85)
        self.assertAlmostEqual(offset_losses[0]['loss_mm'], 0.85)
        self.assertAlmostEqual(offset_losses[0]['published_mm'], 69)
        self.assertAlmostEqual(offset_losses[2]['exact_mm'], 2355.85)
        self.assertAlmostEqual(offset_losses[2]['loss_mm'], 0.85)
        # The draft authors centerlines in exact milli-mm (consumer placement
        # semantics; the Emblem precedent: 88.9mm = half its 7in envelope).
        draft = json.loads((ROOT / 'workspace/catalog/augusta-8x6-model-draft.json').read_text())
        amounts = [s['placement']['offset']['amount_milli']
                   for s in draft['model_fragment']['default_spec']['frame']]
        self.assertEqual(amounts, [69850, 1212850, 2355850])

    def test_height_survives_parsing_with_recorded_loss(self):
        support = self.model['height_support']
        self.assertEqual(support['kind'], 'discrete')
        self.assertEqual(support['heights_mm'], [2425])
        losses = self.candidate['transformation_evidence']['precision_losses']
        height_losses = [l for l in losses if l['field'] == 'height']
        self.assertEqual(len(height_losses), 1)
        self.assertAlmostEqual(height_losses[0]['exact_mm'], 2425.7)
        self.assertAlmostEqual(height_losses[0]['loss_mm'], 0.7)

    def test_pattern_is_single_row_with_recorded_limitation(self):
        pattern = self.model['default_spec']['infill']['pattern']
        self.assertEqual([m['key'] for m in pattern], ['picket'])
        withheld = self.candidate['transformation_evidence']['withheld_from_consumer_shape']
        self.assertTrue(any('upper picket run' in note for note in withheld))
        self.assertTrue(any('withheld_mappings' in note for note in withheld))
        self.assertTrue(any('consumer_infill_single_cycle' in note
                            for note in self.candidate['limitations']))

    def test_u_channel_count_covers_both_runs(self):
        fixing = self.model['default_spec']['fixings'][0]
        # Two edge-bound handed fixings for the mapped lower run (Emblem shape);
        # the upper run's two segments are withheld (see completeness test).
        self.assertEqual(len(self.model['default_spec']['fixings']), 2)
        self.assertEqual(fixing['key'], 'u_channel_end_cover_first')
        self.assertEqual(fixing['qty_per_basis'], 1)
        self.assertEqual(fixing['edge_binding'],
                         {'member_key': 'picket', 'position': 'first', 'profile_edge': 'tongue'})
        self.assertEqual(fixing['requirement']['qty'], 1)
        # The exact authored basis lives in the dataset and the draft.
        draft = json.loads((ROOT / 'workspace/catalog/augusta-8x6-model-draft.json').read_text())
        fix = draft['model_fragment']['default_spec']['fixings'][0]
        self.assertEqual(fix['qty_per_basis']['amount_milli'], 4000)
        self.assertEqual(fix['requirement']['qty']['amount_milli'], 4000)
        self.assertIn('two runs', fix['requirement']['qty']['value_raw'][0])

    def test_withheld_upper_row_is_structured_and_complete(self):
        withheld = self.candidate['withheld_mappings']
        self.assertEqual(len(withheld), 2)
        entry = next(w for w in withheld
                     if w['path'].endswith('picket_upper'))
        self.assertEqual(entry['code'], 'consumer_infill_single_cycle')
        self.assertEqual(entry['closes_by'], 'planning')
        self.assertEqual(entry['draft_base_ref'], 'mid_rail')
        self.assertEqual(entry['draft_top_ref'], 'top_rail')
        self.assertTrue(entry['reason'] and entry['would_close'])
        segments = next(w for w in withheld if 'upper run' in w['path'])
        self.assertEqual(segments['code'], 'consumer_infill_single_cycle')
        self.assertIn('two', segments['reason'])
        completeness = self.candidate['mapping_completeness']
        self.assertTrue(completeness['complete'])
        self.assertTrue(completeness['fixing_count_complete'])
        self.assertEqual(completeness['draft_member_keys'], ['picket', 'picket_upper'])
        self.assertEqual(completeness['mapped_member_keys'], ['picket'])
        self.assertEqual(completeness['withheld_member_keys'], ['picket_upper'])
        self.assertEqual(completeness['draft_u_channel_segments'], 4)
        self.assertEqual(completeness['mapped_u_channel_segments'], 2)
        self.assertEqual(completeness['withheld_u_channel_segments'], 2)

    def test_unvalidated_capabilities_are_marked_false_with_reasons(self):
        capabilities = self.candidate['capability_validation']
        for name in ('assembly', 'fitting', 'cutting', 'purchasing'):
            self.assertIn(name, capabilities)
            self.assertIs(capabilities[name]['validated'], False)
            self.assertTrue(capabilities[name]['why'].strip())

    def test_an_unexpected_resolver_error_cannot_read_as_success(self):
        # The check's assertion, mirrored here: a closed enumeration where
        # ONLY the specific dimension-availability refusal or a genuinely
        # computed nonempty result passes.
        def behaves(resolution):
            if resolution is None or resolution.get('outcome') == 'unexpected_error':
                return False
            if resolution.get('outcome') == 'expected_dimensionless_draft_refusal':
                return True
            if resolution.get('outcome') == 'resolved':
                slots = resolution.get('slots')
                return (isinstance(slots, list) and len(slots) > 0
                        and all(isinstance(s.get('length_mm'), int) for s in slots))
            return False

        # Missing record (probe never reached the resolver) -> FAIL.
        self.assertFalse(behaves(None))
        # Unknown outcome key -> FAIL.
        self.assertFalse(behaves({}))
        self.assertFalse(behaves({'outcome': 'refused'}))
        # Unexpected exception -> FAIL.
        self.assertFalse(behaves({'outcome': 'unexpected_error', 'error_type': 'TypeError'}))
        # Empty resolved result -> FAIL (previously passed via all([])).
        self.assertFalse(behaves({'outcome': 'resolved', 'slots': []}))
        # Resolved with a slot missing length_mm or non-int -> FAIL.
        self.assertFalse(behaves({'outcome': 'resolved', 'slots': [{'key': 'r'}]}))
        self.assertFalse(behaves({'outcome': 'resolved', 'slots': [{'key': 'r', 'length_mm': 1702.5}]}))
        # The specific expected refusal -> PASS.
        self.assertTrue(behaves({'outcome': 'expected_dimensionless_draft_refusal',
                                  'error_type': 'ValueError',
                                  'error': 'member pattern never advances: widths [0] with gaps [0] ...'}))
        # A genuinely computed nonempty result -> PASS.
        self.assertTrue(behaves({'outcome': 'resolved',
                                  'slots': [{'key': 'bottom_rail', 'length_mm': 1702}]}))
        # The live probe record carries the expected outcome.
        report = json.loads((ROOT / 'workspace/reports/augusta-assembly-publication.json').read_text())
        check = next(c for c in report['consumer']['checks']
                     if c['check'] == 'panel_resolution_behaves_as_declared')
        self.assertTrue(check['ok'])
        self.assertEqual(check['detail']['actual']['outcome'],
                         'expected_dimensionless_draft_refusal')
        # And the record states what it does NOT prove.
        self.assertIn('NOT evaluated', check['detail']['asserted_outcome'])


@requires_store
class TestAugustaAssemblySnapshot(unittest.TestCase):
    def setUp(self):
        source = connect(read_only=True)
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        source.backup(self.conn)
        source.close()
        self.addCleanup(self.conn.close)

    def test_snapshot_publishes_composition_and_value_parts_separately(self):
        snapshot = build_snapshot(tenant='default', conn=self.conn)
        verify(snapshot)
        ids = [p['id'] for p in snapshot['parts']]
        for pid in ('mfr/weatherables/wea-augusta-post-5x5',
                    'mfr/weatherables/wea-augusta-rail-slotted',
                    'mfr/weatherables/wea-augusta-picket-tg',
                    'mfr/weatherables/wea-augusta-u-channel',
                    'mfr/weatherables/wea-augusta-metal-insert'):
            self.assertIn(pid, ids)
        self.assertEqual(len(ids), len(set(ids)), 'no duplicate Part identities')

    def test_model_draft_declares_all_receiving_geometry_null(self):
        package = json.loads(DRAFT.read_text())
        fragment = package['model_fragment']
        for slot in fragment['default_spec']['frame']:
            self.assertIsNone(slot['joint']['channel_depth'])
            self.assertIsNone(slot['joint']['insertion_margin'])
        for member in fragment['default_spec']['infill']['pattern']:
            self.assertIsNone(member['base_engagement'])
            self.assertIsNone(member['top_engagement'])
            # The per-run picket count is now manufacturer-stated kit
            # inventory (22/2 = 11 per run), not a null.
            self.assertEqual(member['requirement']['qty']['amount_milli'], 11000)
            self.assertIn('material list', member['requirement']['qty']['value_raw'][0])
        # The model authors no post opinion: the retained sources state no
        # post identity or geometry beyond the brochure route-hole note.
        self.assertIsNone(fragment['post'])
        # Quantities that ARE source-supported are authored, not null.
        self.assertEqual(fragment['default_spec']['fixings'][0]['qty_per_basis']['amount_milli'], 4000)
        # Value-backed Part references resolve in the published Part set.
        part_ids = {p['id'] for p in build_snapshot(tenant='default', conn=self.conn)['parts']}
        for slot in fragment['default_spec']['frame']:
            self.assertIn(slot['requirement']['part_id'], part_ids)
        for member in fragment['default_spec']['infill']['pattern']:
            self.assertIn(member['requirement']['part_id'], part_ids)
        self.assertIn(fragment['default_spec']['fixings'][0]['requirement']['part_id'], part_ids)

    def test_step_candidates_wait_for_human_review(self):
        snapshot = build_snapshot(tenant='default', conn=self.conn)
        # Nothing publishes as a procedure without a human review.
        self.assertEqual(snapshot['procedures'], [])
        waiting = [g for g in snapshot['gaps']
                   if g['because']['code'] == 'steps_awaiting_review']
        pages = {g['subject']['id'] for g in waiting}
        self.assertTrue(any('doc-3e54ae26c66c' in p for p in pages),
                        'master-install pages are named as awaiting review')

@requires_store
class TestAdversarialHardening(unittest.TestCase):
    """Fixes for defects found by the five-way adversarial review."""

    def setUp(self):
        source = connect(read_only=True)
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        source.backup(self.conn)
        source.close()
        self.addCleanup(self.conn.close)

    def test_missing_anchor_element_raises_designed_valueerror(self):
        # A deleted or moved anchor element must raise the designed
        # ValueError naming the element, not a TypeError.
        self.conn.execute("DELETE FROM elements WHERE element_id=?",
                          ('element-1b110be294-0001',))
        self.conn.commit()
        with self.assertRaisesRegex(ValueError, 'Changed source anchor'):
            recipe.import_cad_readings(self.conn)

    def test_duplicate_legacy_rows_refuse(self):
        # History is preserved exactly once; a store that double-inserted
        # during the v1 era must not silently accumulate.
        el = self.conn.execute("SELECT * FROM elements WHERE element_id=?",
                               (recipe.INSTALL_ANCHORS['u_channel_designation'][0],)).fetchone()
        insert = '''INSERT INTO facts (document_id,version_id,page_no,element_id,fact_type,subject,
            value_original,unit_original,conditions,condition_basis,evidence_text,extractor,ocr_derived,
            review_status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)'''
        row = (el['document_id'], el['version_id'], el['page_no'], el['element_id'],
              'u_channel_width_in', 'legacy', '1.5 in.', 'in', '{}', 'assumed',
              el['text'], recipe.LEGACY_INSTALL_EXTRACTOR, 0, 'extracted', '2026-09-07T00:00:00')
        self.conn.execute(insert, row)
        self.conn.execute(insert, row)
        self.conn.commit()
        with self.assertRaisesRegex(ValueError, 'Conflicting legacy'):
            recipe.import_install_readings(self.conn)
        with self.assertRaisesRegex(ValueError, 'Conflicting legacy'):
            recipe.build_parts(self.conn, _default_source_ref(self.conn))

    def test_fractional_count_refuses_not_silently_zeroed(self):
        # A count is exact knowledge: a fractional milli-each count must
        # refuse, never silently truncate to zero (the pre-fix behavior
        # turned a sub-milli qty into qty: 0).
        package = json.loads((ROOT / 'workspace/catalog/augusta-8x6-model-draft.json').read_text())
        package['model_fragment']['default_spec']['fixings'][0]['requirement']['qty']['amount_milli'] = 1
        with tempfile.TemporaryDirectory() as tmp:
            draft = Path(tmp) / 'draft.json'
            draft.write_text(json.dumps(package))
            script = Path(ROOT / 'scripts/prepare_augusta_consumer_model.py').read_text()
            script = script.replace("DRAFT = ROOT / 'workspace/catalog/augusta-8x6-model-draft.json'",
                                    f"DRAFT = Path({str(draft)!r})")
            script = script.replace("OUT = ROOT / 'workspace/catalog/augusta-8x6-consumer-model.json'",
                                    f"OUT = Path({str(Path(tmp) / 'out.json')!r})")
            script = script.replace("sys.path.insert(0, str(ROOT))",
                                    f"sys.path.insert(0, {str(ROOT)!r})")
            exec_path = Path(tmp) / 'transform.py'
            exec_path.write_text(script)
            result = subprocess.run([sys.executable, str(exec_path)],
                                    capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0, 'a fractional count must refuse')
        self.assertIn('not a whole count', result.stderr)

    def test_advance_script_gates_snapshot_on_consumer_checks(self):
        # Exit-code discipline: the advance script must refuse to store the
        # snapshot and exit nonzero when a consumer check fails (mirrors the
        # Emblem completion_code discipline). Verified from the code path:
        # put_snapshot is unreachable when a check fails.
        source = (ROOT / 'scripts/advance_augusta_assembly.py').read_text()
        self.assertIn('failed_consumer_checks', source)
        self.assertIn('return 2', source)
        # put_snapshot must come after the failure gate, not before.
        gate_index = source.index('failed_consumer_checks')
        store_index = source.index('put_snapshot(snapshot)')
        self.assertLess(gate_index, store_index,
                        'the consumer-check gate must run before put_snapshot')
        # The latest report must be the product of a fully passing run.
        report = json.loads((ROOT / 'workspace/reports/augusta-assembly-publication.json').read_text())
        self.assertTrue(report.get('consumer_checks_passed') or report.get('snapshot_stored'))
        self.assertFalse(report.get('aborted'), 'the committed run must have passed all checks')

    def test_rail_length_limitation_is_recorded(self):
        # The routed-rail length limitation (rails slide into post sockets;
        # clear_between_posts undercounts the known 71.5in stock until a
        # receiving joint exists) must be recorded, not silent.
        candidate = json.loads((ROOT / 'workspace/catalog/augusta-8x6-consumer-model.json').read_text())
        self.assertTrue(any('routed post sockets' in note for note in candidate['limitations']))
        self.assertTrue(any('undercount' in note for note in candidate['limitations']))
        self.assertTrue(any('receiving_joint' in note or 'ReceivingPostJoint' in note
                            for note in candidate['limitations']))

    def test_post_omission_reason_is_truthful(self):
        # The draft must not claim "no source states post dimensions" while
        # the dataset carries a sourced post component; the honest reason is
        # the absence of a post Part with citable values.
        draft = json.loads((ROOT / 'workspace/catalog/augusta-8x6-model-draft.json').read_text())
        for entry in draft.get('unresolved_fields', []):
            if entry.get('path_pattern') == '/model_fragment/post':
                self.assertNotIn('no source states Augusta post', entry['reason'])
                self.assertIn('post Part', entry['reason'])
