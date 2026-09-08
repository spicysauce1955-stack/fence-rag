"""Pembroke 6x6 assembly slice: composition membership, authored counts and the
model candidate's honest exclusions stay separate from published Parts."""
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from context import ROOT, requires_store
from pathlib import Path
from fence_evidence import pembroke_cadpage_claims as recipe
from fence_evidence.part_types import (PEMBROKE_COMPONENT_IDS, PartTypeRegistry,
                                       build_part_types, load_pembroke_components)
from fence_evidence.parameters import _default_source_ref
from fence_evidence.parts import build_parts
from fence_evidence.store import connect
from fence_evidence.snapshot import build_snapshot, verify

DRAFT = ROOT / 'workspace/catalog/pembroke-6x6-model-draft.json'


class TestPembrokeComposition(unittest.TestCase):
    def test_components_carry_authored_counts_with_bases(self):
        components = load_pembroke_components()
        self.assertEqual({c['component_id'] for c in components},
                         set(PEMBROKE_COMPONENT_IDS))
        by_id = {c['component_id']: c for c in components}
        self.assertEqual(by_id['wea-pembroke-rail-slotted']['qty_per_panel'], 2)
        self.assertEqual(by_id['wea-pembroke-u-channel']['qty_per_panel'], 2)
        self.assertEqual(by_id['wea-pembroke-picket-tg']['qty_per_panel'], 6)
        self.assertEqual(by_id['wea-pembroke-metal-insert']['qty_per_panel'], 1)
        for cid in ('wea-pembroke-rail-slotted', 'wea-pembroke-u-channel',
                    'wea-pembroke-picket-tg', 'wea-pembroke-metal-insert'):
            self.assertIn('material list', by_id[cid]['qty_per_panel_basis'], cid)
        self.assertIn('72 - 2*5.5', by_id['wea-pembroke-u-channel']['qty_per_panel_basis'])
        # The post count is absent, not zero.
        self.assertNotIn('qty_per_panel', by_id['wea-pembroke-post-4x4'])

    def test_composition_resolves_spine_without_gaps(self):
        registry = PartTypeRegistry('Weatherables')
        types, gaps = build_part_types(load_pembroke_components(), registry)
        self.assertEqual(gaps, [])
        keys = {(t['namespace'], t['key']) for t in types}
        self.assertIn(('mfr/weatherables', 'picket'), keys)


class TestPembrokeConsumerCandidate(unittest.TestCase):
    """The private consumer candidate converts units honestly and maps the
    single picket run completely (no withholding exists for this two-rail
    panel)."""

    def setUp(self):
        self.candidate = json.loads(
            (ROOT / 'workspace/catalog/pembroke-6x6-consumer-model.json').read_text())
        self.model = self.candidate['model']

    def test_offsets_are_centerlines_in_millimetre_magnitude(self):
        offsets = [slot['placement']['offset_mm']
                   for slot in self.model['default_spec']['frame']]
        # Exact centerlines 69.85/1758.95 floor to whole mm with the losses
        # recorded; every offset is mm-magnitude, never raw milli-mm.
        self.assertEqual(offsets, [69, 1758])
        for value in offsets:
            self.assertLess(value, 3000, 'offset must be mm, not raw milli-mm')
        losses = self.candidate['transformation_evidence']['precision_losses']
        offset_losses = [l for l in losses if l['field'] == 'placement/offset']
        self.assertEqual(len(offset_losses), 2)
        self.assertAlmostEqual(offset_losses[0]['exact_mm'], 69.85)
        self.assertAlmostEqual(offset_losses[0]['loss_mm'], 0.85)
        self.assertAlmostEqual(offset_losses[0]['published_mm'], 69)
        self.assertAlmostEqual(offset_losses[1]['exact_mm'], 1758.95)
        self.assertAlmostEqual(offset_losses[1]['loss_mm'], 0.95)
        # The draft authors centerlines in exact milli-mm (consumer placement
        # semantics; the Emblem precedent: 88.9mm = half its 7in envelope).
        draft = json.loads((ROOT / 'workspace/catalog/pembroke-6x6-model-draft.json').read_text())
        amounts = [s['placement']['offset']['amount_milli']
                   for s in draft['model_fragment']['default_spec']['frame']]
        self.assertEqual(amounts, [69850, 1758950])

    def test_height_survives_parsing_with_recorded_loss(self):
        support = self.model['height_support']
        self.assertEqual(support['kind'], 'discrete')
        self.assertEqual(support['heights_mm'], [1828])
        losses = self.candidate['transformation_evidence']['precision_losses']
        height_losses = [l for l in losses if l['field'] == 'height']
        self.assertEqual(len(height_losses), 1)
        self.assertAlmostEqual(height_losses[0]['exact_mm'], 1828.8)
        self.assertAlmostEqual(height_losses[0]['loss_mm'], 0.8)

    def test_pattern_is_single_run_fully_mapped(self):
        pattern = self.model['default_spec']['infill']['pattern']
        self.assertEqual([m['key'] for m in pattern], ['picket'])
        completeness = self.candidate['mapping_completeness']
        self.assertTrue(completeness['complete'])
        self.assertEqual(completeness['withheld_member_keys'], [])
        self.assertEqual(completeness['withheld_u_channel_segments'], 0)
        self.assertEqual(completeness['mapped_u_channel_segments'], 2)
        self.assertTrue(completeness['fixing_count_complete'])

    def test_u_channel_fixings_cover_the_whole_authored_count(self):
        fixings = self.model['default_spec']['fixings']
        self.assertEqual({f['key'] for f in fixings},
                         {'u_channel_end_cover_first', 'u_channel_end_cover_last'})
        for fixing in fixings:
            self.assertEqual(fixing['basis'], 'per_panel')
            self.assertEqual(fixing['qty_per_basis'], 1)
            self.assertEqual(fixing['requirement']['qty'], 1)
            self.assertIn('edge_binding', fixing)
        self.assertEqual(sum(f['qty_per_basis'] for f in fixings), 2,
                         'two-rail panel: both authored segments map, none withheld')

    def test_unvalidated_capabilities_are_marked_false_with_reasons(self):
        capabilities = self.candidate['capability_validation']
        for key in ('assembly', 'fitting', 'cutting', 'purchasing'):
            self.assertIn(key, capabilities)
            self.assertIs(capabilities[key]['validated'], False)
            self.assertTrue(capabilities[key]['why'])

    def test_rail_length_limitation_is_recorded(self):
        # The routed-rail length limitation (rails slide into post sockets;
        # clear_between_posts undercounts the known 71.5in stock until a
        # receiving joint exists) must be recorded, not silent.
        candidate = json.loads((ROOT / 'workspace/catalog/pembroke-6x6-consumer-model.json').read_text())
        self.assertTrue(any('routed post sockets' in note for note in candidate['limitations']))
        self.assertTrue(any('undercount' in note for note in candidate['limitations']))
        self.assertTrue(any('receiving_joint' in note or 'ReceivingPostJoint' in note
                            for note in candidate['limitations']))

    def test_post_omission_reason_is_truthful(self):
        # The draft must not claim "no source states post dimensions" while the
        # dataset carries a sourced post component; the honest reason is the
        # absence of a post Part with citable values.
        draft = json.loads((ROOT / 'workspace/catalog/pembroke-6x6-model-draft.json').read_text())
        for entry in draft.get('unresolved_fields', []):
            if entry.get('path_pattern') == '/model_fragment/post':
                self.assertNotIn('no source states Pembroke post dimensions',
                                 entry['reason'])


class TestPembrokeSnapshot(unittest.TestCase):
    def setUp(self):
        source = connect(read_only=True)
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        source.backup(self.conn)
        source.close()
        self.addCleanup(self.conn.close)
        recipe.import_cadpage_readings(self.conn)
        recipe.import_install_readings(self.conn)
        recipe.import_specsheet_readings(self.conn)

    def test_snapshot_publishes_composition_and_value_parts_separately(self):
        snapshot = build_snapshot(tenant='default', conn=self.conn)
        verify(snapshot)
        ids = [p['id'] for p in snapshot['parts']]
        for pid in ('mfr/weatherables/wea-pembroke-post-4x4',
                    'mfr/weatherables/wea-pembroke-rail-slotted',
                    'mfr/weatherables/wea-pembroke-picket-tg',
                    'mfr/weatherables/wea-pembroke-u-channel',
                    'mfr/weatherables/wea-pembroke-metal-insert'):
            self.assertIn(pid, ids)
        # The two-rail Pembroke panel and the three-rail Augusta panel now
        # publish side by side: no duplicate identity, no lost Augusta Part.
        self.assertEqual(len(ids), len(set(ids)), 'no duplicate Part identity')
        for pid in ('mfr/weatherables/augusta-8x6-rail',
                    'mfr/weatherables/wea-augusta-rail-slotted'):
            self.assertIn(pid, ids)

    def test_value_parts_carry_exact_stock_dimensions(self):
        snapshot = build_snapshot(tenant='default', conn=self.conn)
        by_id = {p['id']: p for p in snapshot['parts']}
        rail = by_id['mfr/weatherables/pembroke-6x6-rail']
        specs = {s['key']: s['value'] for s in rail['spec']}
        # 1.5 x 5.5 x 71.5 in, in exact milli-mm.
        self.assertEqual(specs['width_mm']['amount_milli'], 38100)
        self.assertEqual(specs['height_mm']['amount_milli'], 139700)
        self.assertEqual(specs['length_mm']['amount_milli'], 1816100)
        self.assertEqual(specs['kit_count_per_panel']['value_raw'], ['2 each'])
        channel = by_id['mfr/weatherables/pembroke-6x6-u-channel']
        cspecs = {s['key']: s['value'] for s in channel['spec']}
        # 1.25 x 1.5 x 61 in: the length closes exactly against the two-rail
        # section chain 72 - 2*5.5 = 61.
        self.assertEqual(cspecs['length_mm']['amount_milli'], 1549400)
        self.assertEqual(cspecs['kit_count_per_panel']['value_raw'], ['2 each'])
        picket = by_id['mfr/weatherables/pembroke-6x6-picket']
        pspecs = {s['key']: s['value'] for s in picket['spec']}
        self.assertEqual(pspecs['nominal_width_mm']['amount_milli'], 287020)
        self.assertEqual(pspecs['stock_length_mm']['amount_milli'], 1631950)
        self.assertEqual(pspecs['kit_count_per_panel']['value_raw'], ['6 each'])
        # The .055in tongue-and-groove wall gauge publishes in exact milli-mm
        # with its verbatim leading-dot lexeme (the source writes '.055"').
        self.assertEqual(pspecs['tongue_groove_wall_gauge_mm']['amount_milli'], 1397)
        self.assertEqual(pspecs['tongue_groove_wall_gauge_mm']['value_raw'], ['.055 in.'])
        insert = by_id['mfr/weatherables/pembroke-6x6-metal-insert']
        ispecs = {s['key']: s['value'] for s in insert['spec']}
        self.assertEqual(ispecs['kit_count_per_panel']['value_raw'], ['1 each'])
        self.assertEqual(ispecs['length_mm']['amount_milli'], 1816100)

    def test_kit_counts_publish_as_tokens_not_quantities(self):
        snapshot = build_snapshot(tenant='default', conn=self.conn)
        for pid in ('mfr/weatherables/pembroke-6x6-rail',
                    'mfr/weatherables/pembroke-6x6-u-channel',
                    'mfr/weatherables/pembroke-6x6-picket',
                    'mfr/weatherables/pembroke-6x6-metal-insert'):
            part = next(p for p in snapshot['parts'] if p['id'] == pid)
            count = next(s for s in part['spec'] if s['key'] == 'kit_count_per_panel')
            self.assertEqual(count['value']['key'], 'count', pid)
            self.assertNotIn('amount_milli', count['value'], pid)

    def test_model_draft_declares_all_receiving_geometry_null(self):
        package = json.loads(DRAFT.read_text())
        fragment = package['model_fragment']
        for slot in fragment['default_spec']['frame']:
            self.assertIsNone(slot['joint']['channel_depth'])
            self.assertIsNone(slot['joint']['insertion_margin'])
        for member in fragment['default_spec']['infill']['pattern']:
            self.assertIsNone(member['base_engagement'])
            self.assertIsNone(member['top_engagement'])
            # The per-panel picket count is manufacturer-stated kit
            # inventory (6, single run), not a null.
            self.assertEqual(member['requirement']['qty']['amount_milli'], 6000)
            self.assertIn('material list', member['requirement']['qty']['value_raw'][0])
        # The model authors no post opinion: the retained sources state no
        # panel-kit post; the gate lists name 4x4x76 posts for gates only.
        self.assertIsNone(fragment['post'])
        # Quantities that ARE source-supported are authored, not null.
        self.assertEqual(fragment['default_spec']['fixings'][0]['qty_per_basis']['amount_milli'], 2000)
        # The height is an authored arithmetic closure recorded as such.
        self.assertEqual(fragment['height_support']['heights'][0]['amount_milli'], 1828800)
        self.assertIn('authored closure', fragment['height_support']['heights'][0]['value_raw'][0])
        # Value-backed Part references resolve in the published Part set.
        part_ids = {p['id'] for p in build_snapshot(tenant='default', conn=self.conn)['parts']}
        for slot in fragment['default_spec']['frame']:
            self.assertIn(slot['requirement']['part_id'], part_ids)
        for member in fragment['default_spec']['infill']['pattern']:
            self.assertIn(member['requirement']['part_id'], part_ids)
        self.assertIn(fragment['default_spec']['fixings'][0]['requirement']['part_id'], part_ids)

    def test_nothing_publishes_from_the_unusable_cad_ocr(self):
        # The local CAD raster's canonical OCR is 2 garbled whole-image
        # labels; no Pembroke fact may anchor to that OCR and no Part may
        # cite the CAD PNG.
        rows = self.conn.execute(
            "SELECT COUNT(*) FROM facts WHERE extractor LIKE '%pembroke%' AND ocr_derived=1"
        ).fetchone()[0]
        self.assertEqual(rows, 0)
        snapshot = build_snapshot(tenant='default', conn=self.conn)
        for part in snapshot['parts']:
            for source in part['contributing_sources']:
                self.assertNotEqual(
                    source, '3fd74eaceddba4ac85905552e2419fdcfe4e4b29d258cb49b5c3f2aba5fcd8b8',
                    'the unusable CAD raster must not become contributing evidence')

    def test_single_run_panel_needs_no_cycle_withholding(self):
        # The consumer dialect's single-cycle limitation (Augusta's
        # consumer_infill_single_cycle) does not apply to this two-rail,
        # one-run panel: nothing is withheld and mapping_completeness shows it.
        candidate = json.loads(
            (ROOT / 'workspace/catalog/pembroke-6x6-consumer-model.json').read_text())
        self.assertEqual(candidate['withheld_mappings'], [])
        self.assertEqual(candidate['mapping_completeness']['draft_member_keys'],
                         candidate['mapping_completeness']['mapped_member_keys'])
        # The limitation list carries the rail-length and diagnostic-scope
        # notes, but no upper-run note.
        self.assertFalse(any('upper picket run' in note
                              for note in candidate['limitations']))


@requires_store
class TestPembrokeAdversarialHardening(unittest.TestCase):
    """Fixes for defects found by the adversarial review discipline."""

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
                          ('element-77275b2b5b-0239',))
        self.conn.commit()
        with self.assertRaisesRegex(ValueError, 'Changed source anchor'):
            recipe.import_cadpage_readings(self.conn)

    def test_unknown_persisted_reading_types_refuse(self):
        # A foreign fact_type under the Pembroke extractor is a conflict,
        # not history to silently carry.
        el = self.conn.execute(
            "SELECT * FROM elements WHERE element_id=?",
            (recipe.CADPAGE_ANCHORS['panel_6x6_list'][0],)).fetchone()
        self.conn.execute(
            '''INSERT INTO facts (document_id,version_id,page_no,element_id,fact_type,subject,
            value_original,unit_original,conditions,condition_basis,evidence_text,extractor,ocr_derived,
            review_status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (el['document_id'], el['version_id'], el['page_no'], el['element_id'],
             'foreign_fact_type', 'foreign', '1 in.', 'in', '{}', 'assumed',
             el['text'], recipe.CADPAGE_EXTRACTOR, 0, 'extracted', '2026-09-07T00:00:00'))
        self.conn.commit()
        with self.assertRaisesRegex(ValueError, 'Unknown persisted reading types'):
            recipe.import_cadpage_readings(self.conn)

    def test_fractional_count_refuses_not_silently_zeroed(self):
        # A count is exact knowledge: a fractional milli-each count must
        # refuse, never silently truncate to zero.
        package = json.loads((ROOT / 'workspace/catalog/pembroke-6x6-model-draft.json').read_text())
        package['model_fragment']['default_spec']['fixings'][0]['requirement']['qty']['amount_milli'] = 1
        with tempfile.TemporaryDirectory() as tmp:
            draft = Path(tmp) / 'draft.json'
            draft.write_text(json.dumps(package))
            script = Path(ROOT / 'scripts/prepare_pembroke_consumer_model.py').read_text()
            script = script.replace("DRAFT = ROOT / 'workspace/catalog/pembroke-6x6-model-draft.json'",
                                    f"DRAFT = Path({str(draft)!r})")
            script = script.replace("OUT = ROOT / 'workspace/catalog/pembroke-6x6-consumer-model.json'",
                                    f"OUT = Path({str(Path(tmp) / 'out.json')!r})")
            script = script.replace("sys.path.insert(0, str(ROOT))",
                                    f"sys.path.insert(0, {str(ROOT)!r})")
            exec_path = Path(tmp) / 'transform.py'
            exec_path.write_text(script)
            result = subprocess.run([sys.executable, str(exec_path)],
                                    capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0, 'a fractional count must refuse')
        self.assertIn('not a whole count', result.stderr)

    def test_wrong_fixing_count_refuses(self):
        # The transformer pins the authored 2 installed segments; a draft
        # edited to a different count must refuse rather than transform.
        package = json.loads((ROOT / 'workspace/catalog/pembroke-6x6-model-draft.json').read_text())
        package['model_fragment']['default_spec']['fixings'][0]['qty_per_basis']['amount_milli'] = 4000
        with tempfile.TemporaryDirectory() as tmp:
            draft = Path(tmp) / 'draft.json'
            draft.write_text(json.dumps(package))
            script = Path(ROOT / 'scripts/prepare_pembroke_consumer_model.py').read_text()
            script = script.replace("DRAFT = ROOT / 'workspace/catalog/pembroke-6x6-model-draft.json'",
                                    f"DRAFT = Path({str(draft)!r})")
            script = script.replace("OUT = ROOT / 'workspace/catalog/pembroke-6x6-consumer-model.json'",
                                    f"OUT = Path({str(Path(tmp) / 'out.json')!r})")
            script = script.replace("sys.path.insert(0, str(ROOT))",
                                    f"sys.path.insert(0, {str(ROOT)!r})")
            exec_path = Path(tmp) / 'transform.py'
            exec_path.write_text(script)
            result = subprocess.run([sys.executable, str(exec_path)],
                                    capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0, 'a wrong u-channel count must refuse')
        self.assertIn('authored 2', result.stderr)

    def test_wrong_frame_structure_refuses(self):
        # The transformer pins the two-rail frame: 3 rails, doubled
        # quantities or nonzero overlap must refuse rather than transform.
        for mutate in ('extra_rail', 'rail_qty_2', 'overlap_nonzero'):
            package = json.loads((ROOT / 'workspace/catalog/pembroke-6x6-model-draft.json').read_text())
            if mutate == 'extra_rail':
                second = dict(package['model_fragment']['default_spec']['frame'][1])
                second['key'] = 'mid_rail'
                package['model_fragment']['default_spec']['frame'].append(second)
            elif mutate == 'rail_qty_2':
                package['model_fragment']['default_spec']['frame'][0]['requirement']['qty']['amount_milli'] = 2000
            else:
                package['model_fragment']['default_spec']['frame'][0]['requirement']['overlap']['amount_milli'] = 500000
            with tempfile.TemporaryDirectory() as tmp:
                draft = Path(tmp) / 'draft.json'
                draft.write_text(json.dumps(package))
                script = Path(ROOT / 'scripts/prepare_pembroke_consumer_model.py').read_text()
                script = script.replace("DRAFT = ROOT / 'workspace/catalog/pembroke-6x6-model-draft.json'",
                                        f"DRAFT = Path({str(draft)!r})")
                script = script.replace("OUT = ROOT / 'workspace/catalog/pembroke-6x6-consumer-model.json'",
                                        f"OUT = Path({str(Path(tmp) / 'out.json')!r})")
                script = script.replace("sys.path.insert(0, str(ROOT))",
                                        f"sys.path.insert(0, {str(ROOT)!r})")
                exec_path = Path(tmp) / 'transform.py'
                exec_path.write_text(script)
                result = subprocess.run([sys.executable, str(exec_path)],
                                        capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0, mutate + ' must refuse')
            expected = {'extra_rail': 'exactly 2 rails', 'rail_qty_2': 'qty must be 1',
                        'overlap_nonzero': 'overlap must be 0'}[mutate]
            self.assertIn(expected, result.stderr, mutate)

    def test_advance_script_gates_snapshot_on_consumer_checks(self):
        # Exit-code discipline: the advance script must refuse to store the
        # snapshot and exit nonzero when a consumer check fails (mirrors the
        # Emblem completion_code discipline). Verified from the code path:
        # put_snapshot is unreachable when a check fails.
        source = (ROOT / 'scripts/advance_pembroke_assembly.py').read_text()
        self.assertIn('failed_consumer_checks', source)
        self.assertIn('return 2', source)
        # put_snapshot must come after the failure gate, not before. The pins
        # index the real statements (the failure branch's report write and
        # the store call), not comments.
        gate_index = source.index("print(json.dumps({'aborted': True, 'failed_consumer_checks': failed}))")
        store_index = source.index('put_snapshot(snapshot)')
        self.assertLess(gate_index, store_index,
                        'the consumer-check gate must run before put_snapshot')
        self.assertIn('return 2', source[gate_index:store_index],
                      'the failure branch must exit nonzero before the store call')
        # The Emblem non-interference boundary gates the same store.
        self.assertIn("failed.append('emblem_non_interference')", source)
        self.assertIn('emblem_interference', source)
        # The latest report must be the product of a fully passing run: BOTH
        # flags (an `or` lets a partial report pass).
        report = json.loads((ROOT / 'workspace/reports/pembroke-assembly-publication.json').read_text())
        self.assertTrue(report.get('consumer_checks_passed') and report.get('snapshot_stored'))
        self.assertFalse(report.get('aborted'), 'the committed run must have passed all checks')
        self.assertTrue(report['emblem_interference']['ok'])

    def test_stale_candidate_fails_the_binding_check(self):
        # A draft edited without re-running the transformer must fail the
        # advance script's candidate_matches_current_draft check: the probe
        # validates the candidate and the draft fragment independently, so
        # the binding check is what couples them.
        source = (ROOT / 'scripts/advance_pembroke_assembly.py').read_text()
        self.assertIn("candidate_matches_current_draft", source)
        self.assertIn('source_package_hash', source)
        self.assertIn('content_hash(package)', source)
        candidate = json.loads(
            (ROOT / 'workspace/catalog/pembroke-6x6-consumer-model.json').read_text())
        draft = json.loads((ROOT / 'workspace/catalog/pembroke-6x6-model-draft.json').read_text())
        import fence_evidence.canonical as canonical
        self.assertEqual(candidate['source_package_hash'],
                         canonical.content_hash(draft),
                         'the committed candidate must declare the current draft hash')

    def test_excess_substitution_is_recorded(self):
        # The trim_last -> space substitution must be recorded in the
        # candidate's transformation evidence, not performed silently.
        candidate = json.loads(
            (ROOT / 'workspace/catalog/pembroke-6x6-consumer-model.json').read_text())
        substitutions = candidate['transformation_evidence'].get('authored_field_substitutions', [])
        self.assertEqual(len(substitutions), 1)
        self.assertEqual(substitutions[0]['field'], 'default_spec/infill/excess')
        self.assertEqual(substitutions[0]['draft_value'], 'trim_last')
        self.assertEqual(substitutions[0]['candidate_value'], 'space')
        self.assertIn('u-channels cover end gaps', substitutions[0]['reason'])

    def test_metal_insert_omission_is_recorded(self):
        # The metal insert is kit inventory with no model requirement; the
        # refusal must be recorded, not silent.
        draft = json.loads((ROOT / 'workspace/catalog/pembroke-6x6-model-draft.json').read_text())
        entries = [e for e in draft.get('unresolved_fields', [])
                   if e.get('path_pattern') == '/model_fragment/default_spec']
        self.assertTrue(any('metal_insert_requirement' in e.get('fields', []) for e in entries))
        self.assertTrue(any('wea-pembroke-metal-insert' in e.get('reason', '') for e in entries))

    def test_grade_citation_supports_warranty_scope_only(self):
        # /grade cites the warranty's Protection Coverage statement (residential
        # homeowners); the draft must record that this is warranty scope, not a
        # structural grade rating, in unresolved_fields.
        draft = json.loads((ROOT / 'workspace/catalog/pembroke-6x6-model-draft.json').read_text())
        grade_cite = draft['field_evidence'].get('/grade')
        self.assertEqual(grade_cite[0]['id'], 'bcfae99b87f8a413')
        entries = [e for e in draft.get('unresolved_fields', [])
                   if e.get('path_pattern') == '/model_fragment/grade']
        self.assertTrue(entries, 'grade must be recorded as unresolved')
        self.assertIn('warranty scope', entries[0]['reason'])
        self.assertIn('grade', entries[0]['reason'])


class TestPembrokeGapClosing(unittest.TestCase):
    """The gap-closing round: what retained sources support is closed at its
    owning layer; what they do not is an explicit inspected-not-claimed gap."""

    def test_dataset_records_width_options_with_basis(self):
        d = json.load(open(ROOT / 'data/weatherables.json'))
        for pl in d['product_lines']:
            for a in pl.get('assemblies', []):
                if a.get('assembly_id') == 'wea-pembroke-privacy':
                    self.assertEqual(a['width_options_in'], [72, 96])
                    self.assertIn('Width: 6', a['width_options_basis'])
                    self.assertIn('reduced', a['width_options_basis'])
                    self.assertEqual(a['width_on_center_in'], 96)

    def test_dataset_records_ground_clearance_and_wind_claims(self):
        d = json.load(open(ROOT / 'data/weatherables.json'))
        for pl in d['product_lines']:
            for a in pl.get('assemblies', []):
                if a.get('assembly_id') == 'wea-pembroke-privacy':
                    self.assertIn('2', a['panel_ground_clearance_in'])
                    self.assertIn('minimum', a['panel_ground_clearance_in'])
                    wind = a['wind_rating_claims']
                    self.assertIn('110', wind['standard_install_faq'])
                    self.assertIn('120', wind['high_wind_install_with_fasteners_master_install_p15'])
                    self.assertIn('conflict_note', wind)
                    self.assertIn('reproduced verbatim', wind['conflict_note'])

    def test_dataset_records_inspected_not_claimed_gaps(self):
        d = json.load(open(ROOT / 'data/weatherables.json'))
        for pl in d['product_lines']:
            for a in pl.get('assemblies', []):
                if a.get('assembly_id') == 'wea-pembroke-privacy':
                    gaps = a['inspected_not_claimed']
                    for key in ('panel_post_height_pairing', 'panel_post_cap',
                                'rail_slot_dimension', 'u_channel_screw_note',
                                'receiving_geometry'):
                        self.assertIn(key, gaps)
                        self.assertTrue(gaps[key].startswith(('not found after inspection',
                                                              'not claimed',
                                                              'not applicable',
                                                              'unchanged open gap')),
                                        key + ' must carry an explicit gap state, not silence')
                    self.assertIn('WeatherGrain', gaps['u_channel_screw_note'])
                    self.assertIn('lattice-variant', gaps['rail_slot_dimension'])

    def test_post_component_carries_family_catalog_data(self):
        d = json.load(open(ROOT / 'data/weatherables.json'))
        for pl in d['product_lines']:
            for a in pl.get('assemblies', []):
                if a.get('assembly_id') == 'wea-pembroke-privacy':
                    post = next(s for s in a['sub_assemblies']
                                if s['component_id'] == 'wea-pembroke-post-4x4')
                    self.assertIn('twice-observed', post['profile_depth_in'])
                    self.assertIn('gate scope', post['profile_depth_in'])
                    # Post count stays absent, not zero.
                    self.assertNotIn('qty_per_panel', post)

    def test_tongue_groove_gauge_fact_persists_and_publishes(self):
        # The .055in T&G wall gauge is a real stated dimension (specsheet p2,
        # twice-observed): it persists as a fact and publishes on the picket
        # Part with its verbatim lexeme — never rewritten as 0.055.
        source = connect(read_only=True)
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        source.backup(conn)
        source.close()
        self.addCleanup(conn.close)
        recipe.import_specsheet_readings(conn)
        row = conn.execute(
            "SELECT value_original FROM facts WHERE extractor=? AND fact_type=?",
            (recipe.SPECSHEET_EXTRACTOR, 'picket_tongue_groove_wall_gauge_in')).fetchone()
        self.assertEqual(row['value_original'], '.055 in.')
        snapshot = build_snapshot(tenant='default', conn=conn)
        picket = next(p for p in snapshot['parts']
                      if p['id'] == 'mfr/weatherables/pembroke-6x6-picket')
        gauge = next(s for s in picket['spec']
                     if s['key'] == 'tongue_groove_wall_gauge_mm')
        self.assertEqual(gauge['value']['amount_milli'], 1397)
        self.assertEqual(gauge['value']['value_raw'], ['.055 in.'])

    def test_quantity_parser_accepts_leading_dot_verbatim_form(self):
        # The local parser accepts the source's '.055' form; it still refuses
        # garbage and keeps milli-mm precision.
        class Row(dict):
            def __getitem__(self, k):
                return dict.__getitem__(self, k)
        row = {'value_original': '.055 in.', 'reviewed_value': None}
        value = recipe.quantity(row)
        self.assertEqual(value['amount_milli'], 1397)
        self.assertEqual(value['value_raw'], ['.055 in.'])
        bad = {'value_original': 'about an inch', 'reviewed_value': None}
        with self.assertRaisesRegex(ValueError, 'explicit inch value'):
            recipe.quantity(bad)


if __name__ == '__main__':
    unittest.main()