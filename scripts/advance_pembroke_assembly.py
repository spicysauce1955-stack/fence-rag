"""Advance the Pembroke 6x6 assembly slice: composition, counts and the
authored model candidate. Never creates a human review.

Stages:
1. verify retained source bytes and the re-baselined dataset;
2. publish Parts through the normal builder (composition + scoped recipes);
3. verify Emblem non-interference by byte-comparison of every Emblem-owned
   Part against the previous published snapshot (hard boundary);
4. run the authored-model preflight (admit_authored_models), which honestly
   excludes the model pending Amendment 008 and missing receiving geometry;
5. validate actual consumer behavior on an in-memory copy of the published
   snapshot: Parts ingest, the model fragment parses, and unsupported
   geometry (null engagements/channels) refuses fitted-dimension answers.

Exit-code discipline (the Emblem completion_code pattern): the snapshot is
stored ONLY if every consumer check passes and the Emblem byte-comparison
holds; otherwise the script writes an ABORTED report and exits 2. Unexpected
crashes (missing consumer venv, unreadable baseline) exit nonzero with a
traceback and store nothing — storage discipline holds; only the designed
check-failure path writes an ABORTED report.
"""
import json
import hashlib
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fence_evidence import pembroke_cadpage_claims as recipe
from fence_evidence.dataset import verify_dataset
from fence_evidence.paths import open_write
from fence_evidence.snapshot import build_snapshot, verify
from fence_evidence.snapshot_store import put_snapshot
from fence_evidence.store import connect
from fence_evidence.authored_models import admit_authored_models

DRAFT = ROOT / 'workspace/catalog/pembroke-6x6-model-draft.json'
CONSUMER_ROOT = Path('/tmp/fence-planning-bom')
COMPOSITION_PARTS = (
    'mfr/weatherables/wea-pembroke-post-4x4',
    'mfr/weatherables/wea-pembroke-rail-slotted',
    'mfr/weatherables/wea-pembroke-picket-tg',
    'mfr/weatherables/wea-pembroke-u-channel',
    'mfr/weatherables/wea-pembroke-metal-insert',
)
# The previous published snapshot supplies the Emblem byte-comparison
# baseline; the batch's own snapshot becomes the next baseline.
PREVIOUS_SNAPSHOT = ROOT / ('workspace/snapshots/95c770b849cb6817daaa03fc397bc'
                            'c55e78bc9f48c51eff2e00dd548bdb44e58.json')
EMBLEM_ID_PREFIXES = ('mfr/freedom-outdoor-living/', 'mfr/freedom/', 'emblem')
SOURCES = [
    ('manuals/weatherables/structural/weatherables-pembroke-6ft-cad-page.html', recipe.CADPAGE_SHA),
    ('manuals/weatherables/weatherables-fencing-master-installation-instructions-2024.pdf', recipe.INSTALL_SHA),
    ('manuals/weatherables/weatherables-privacy-fencing-specsheet.pdf', recipe.SPECSHEET_SHA),
    ('manuals/weatherables/weatherables-fencing-brochure.pdf',
     'cb90e6a275ac5ff050a4c10d33d82b6478922683cd6d2c857e5c50a3dcb6c629'),
    ('manuals/weatherables/structural/weatherables-cad-pembroke-6ft-privacy.png',
     '3fd74eaceddba4ac85905552e2419fdcfe4e4b29d258cb49b5c3f2aba5fcd8b8'),
]


def emblem_interference(previous_path, snapshot):
    """Byte-compare every Emblem-owned Part across snapshots.

    Hard boundary: this batch never edits Emblem-owned files or Parts. The
    comparison pins each Emblem Part id to its previous published JSON bytes;
    any difference (value change, missing Part, new Emblem Part) fails the
    run before the snapshot is stored.
    """
    previous = json.loads(previous_path.read_text())
    old = {p['id']: json.dumps(p, sort_keys=True) for p in previous['parts']
           if p['id'].startswith(EMBLEM_ID_PREFIXES)}
    new = {p['id']: json.dumps(p, sort_keys=True) for p in snapshot['parts']
           if p['id'].startswith(EMBLEM_ID_PREFIXES)}
    changed = sorted(k for k in old.keys() & new.keys() if old[k] != new[k])
    missing = sorted(old.keys() - new.keys())
    added = sorted(new.keys() - old.keys())
    ok = not changed and not missing and not added
    return {'ok': ok, 'emblem_parts_compared': len(old),
            'changed': changed, 'missing': missing, 'added': added}


def consumer_checks(snapshot, package):
    """Exercise the actual consumer parser and model validator on the real
    published snapshot and authored fragment, using the consumer's own Python
    environment. Negative assurance is the goal: missing geometry must refuse,
    not silently default."""
    import subprocess
    payload = {
        'snapshot': snapshot,
        'model_fragment': package['model_fragment'],
        'composition_parts': COMPOSITION_PARTS,
    }
    candidate_path = ROOT / 'workspace/catalog/pembroke-6x6-consumer-model.json'
    candidate_file = json.loads(candidate_path.read_text()) if candidate_path.exists() else None
    candidate_model = candidate_file['model'] if candidate_file else None
    # Stale-candidate binding: the candidate declares the content hash of the
    # draft it transformed. A draft edited without re-running the transformer
    # must fail here — otherwise the probe validates the candidate and the
    # draft fragment independently and a mismatched pair could both pass.
    from fence_evidence.canonical import content_hash
    if candidate_file is not None:
        expected_hash = candidate_file.get('source_package_hash')
        actual_hash = content_hash(package)
        checks = [{'check': 'candidate_matches_current_draft',
                   'ok': expected_hash == actual_hash,
                   'detail': {'declared': expected_hash, 'actual': actual_hash}}]
    else:
        checks = [{'check': 'candidate_matches_current_draft', 'ok': False,
                   'detail': 'candidate file missing'}]
    payload['consumer_model'] = candidate_model
    probe = ROOT / 'workspace/reports/pembroke-assembly-consumer-probe.json'
    with open_write(probe) as f:
        json.dump(payload, f)
    script = r'''
import json, sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / 'src'))
from pydantic import ValidationError
from fenceai.knowledge.snapshot import load, ingest
from fenceai.fencemodel.model import FenceModel, validate_model
from fenceai.fencemodel.resolve import PanelContext, resolve_panel
payload = json.loads(Path(sys.argv[2]).read_text())
snapshot = payload['snapshot']
loaded, defects = load(snapshot)
receipt = ingest(loaded, as_of='2026-09-07', gap_defects=defects)
received = {part.id for part in receipt.published_parts}
out = {'parts_ingest': {pid: pid in received for pid in payload['composition_parts']},
       'part_count': len(received),
       'draft_inactive': [p['id'] for p in snapshot['parts']
                          if p['id'].startswith('mfr/weatherables/pembroke-6x6-')
                          and p['id'] in receipt.inactive_parts],
       'model_parse_errors': [], 'model_parsed': False,
       'draft_fragment_parse_errors': [], 'draft_fragment_parsed': False,
       'geometry_refusals': [],
       'offset_magnitudes': [], 'heights_mm': [], 'pattern_keys': [],
       'pattern_alternates': None,
       'panel_resolution': None}
try:
    FenceModel.model_validate(payload['consumer_model'])
    out['model_parsed'] = True
    model = FenceModel.model_validate(payload['consumer_model'])
    errors = validate_model(model, None)
    out['geometry_refusals'] = [e[:120] for e in errors if 'mechanic' in e or 'engagement' in e]
    out['other_errors'] = [e[:120] for e in errors if not ('mechanic' in e or 'engagement' in e)]
    out['offset_magnitudes'] = [s.placement.offset_mm for s in model.default_spec.frame
                                if hasattr(s.placement, 'offset_mm')]
    out['heights_mm'] = list(model.height_support.heights_mm) if hasattr(model.height_support, 'heights_mm') else []
    out['pattern_keys'] = [m.key for m in (model.default_spec.infill.pattern if model.default_spec.infill else [])]
    out['pattern_alternates'] = len(out['pattern_keys']) > 1
    # Exercise the real panel resolver on a synthetic bay (72in nominal width,
    # 72in authored height). The record is a CLOSED enumeration: `outcome` is
    # one of 'resolved', 'expected_dimensionless_draft_refusal' or
    # 'unexpected_error', and it is never absent -- a probe that never reached
    # the resolver leaves the key itself missing, which the check treats as
    # failure. The one expected failure is the resolver refusing to fill the
    # infill axis from a Part that carries no dimensions (the draft picket is
    # inactive and dimension-less to the resolver, so widths are [0]): that
    # proves the resolver invents no dimensions. It does NOT prove receiving
    # geometry was evaluated -- that remains untested.
    ctx = PanelContext(centre_width_mm=1829, clear_width_mm=1702, height_mm=1828)
    try:
        resolved = resolve_panel(model.default_spec, ctx)
        out['panel_resolution'] = {
            'outcome': 'resolved',
            'slots': [{'key': s.slot_key, 'length_mm': s.length_mm} for s in resolved.slots],
        }
    except ValueError as exc:
        message = str(exc)
        expected = message.startswith('member pattern never advances: widths [0] with gaps [0]')
        out['panel_resolution'] = {
            'outcome': 'expected_dimensionless_draft_refusal' if expected else 'unexpected_error',
            'error_type': 'ValueError', 'error': message[:200],
        }
    except Exception as exc:
        out['panel_resolution'] = {
            'outcome': 'unexpected_error',
            'error_type': type(exc).__name__, 'error': str(exc)[:200],
        }
except ValidationError as exc:
    out['model_parse_errors'] = [f"{list(e['loc'])}: {e['msg'][:140]}" for e in exc.errors()]
try:
    FenceModel.model_validate(payload['model_fragment'])
    out['draft_fragment_parsed'] = True
except ValidationError as exc:
    out['draft_fragment_parse_errors'] = [f"{list(e['loc'])}: {e['msg'][:140]}" for e in exc.errors()]
print(json.dumps(out))
'''
    payload['consumer_model'] = candidate_model
    result = subprocess.run([str(CONSUMER_ROOT / '.venv/bin/python'), '-c', script,
                             str(CONSUMER_ROOT), str(probe)],
                            capture_output=True, text=True)
    checks.append({'check': 'consumer_environment', 'ok': result.returncode == 0,
                   'detail': (result.stderr or result.stdout)[-400:] if result.returncode else 'consumer venv ok'})
    if result.returncode == 0:
        out = json.loads(result.stdout.strip().splitlines()[-1])
        checks.append({'check': 'composition_parts_ingest',
                       'ok': all(out['parts_ingest'].values()),
                       'detail': out['parts_ingest']})
        # Membership-pinned (not count-only): each expected draft Part must be
        # present BY ID and inactive; a rename that preserves the count fails.
        expected_draft_ids = {'mfr/weatherables/pembroke-6x6-rail',
                              'mfr/weatherables/pembroke-6x6-u-channel',
                              'mfr/weatherables/pembroke-6x6-picket',
                              'mfr/weatherables/pembroke-6x6-metal-insert'}
        checks.append({'check': 'draft_value_parts_inactive',
                       'ok': expected_draft_ids <= set(out['draft_inactive']),
                       'detail': {'expected': sorted(expected_draft_ids),
                                  'actual': out['draft_inactive']}})
        checks.append({'check': 'consumer_dialect_candidate_parses',
                       'ok': out['model_parsed'],
                       'detail': out['model_parse_errors'][:12]})
        checks.append({'check': 'producer_draft_fragment_refused_by_consumer',
                       'ok': not out['draft_fragment_parsed'],
                       'detail': out['draft_fragment_parse_errors'][:4]})
        # Negative assurance: the consumer must REFUSE fitted dimensions for
        # the undeclared receiving geometry, and must refuse nothing else.
        # 3 = two channel rails + the single-run groove member (this two-rail
        # panel has one run, so no withheld upper row exists).
        checks.append({'check': 'consumer_refuses_fitted_dimensions_without_geometry',
                       'ok': len(out['geometry_refusals']) == 3 and not out.get('other_errors'),
                       'detail': {'geometry_refusals': out['geometry_refusals'],
                                  'other_errors': out.get('other_errors')}})
        # Dimension fidelity: offsets are CENTERLINE placements in whole-floor
        # millimetres (the draft authors exact centerlines in milli-mm; the
        # fractional losses are recorded by the transformer), the height
        # survives parsing, and the single-run pattern is one non-alternating
        # member (nothing is withheld for this configuration). The expected
        # magnitudes are DERIVED from the draft the candidate declares, not
        # hardcoded — a stale or edited draft fails the binding check above,
        # and these pins verify the transformer's own arithmetic.
        draft_offsets_mm = [s['placement']['offset']['amount_milli'] // 1000
                            for s in package['model_fragment']['default_spec']['frame']]
        draft_heights_mm = [h['amount_milli'] // 1000
                            for h in package['model_fragment']['height_support']['heights']]
        offset_losses = [l for l in candidate_file['transformation_evidence']['precision_losses']
                         if l['field'] == 'placement/offset']
        height_losses = [l for l in candidate_file['transformation_evidence']['precision_losses']
                         if l['field'] == 'height']
        checks.append({'check': 'offsets_are_millimetre_magnitude',
                       'ok': out['offset_magnitudes'] == draft_offsets_mm
                             and len(offset_losses) == len(draft_offsets_mm)
                             and all(abs(l['published_mm'] - l['exact_mm'] + l['loss_mm']) < 1e-9
                                      for l in offset_losses),
                       'detail': {'offsets': out['offset_magnitudes'],
                                  'derived_from_draft_mm': draft_offsets_mm,
                                  'offset_losses_recorded': len(offset_losses),
                                  'losses': [l['loss_mm'] for l in offset_losses]}})
        checks.append({'check': 'height_survives_parsing',
                       'ok': out['heights_mm'] == draft_heights_mm
                             and len(height_losses) == len(draft_heights_mm)
                             and all(abs(l['published_mm'] - l['exact_mm'] + l['loss_mm']) < 1e-9
                                      for l in height_losses),
                       'detail': {'heights_mm': out['heights_mm'],
                                  'derived_from_draft_mm': draft_heights_mm,
                                  'losses': [l['loss_mm'] for l in height_losses]}})
        checks.append({'check': 'pattern_is_single_row_fully_mapped',
                       'ok': out['pattern_keys'] == ['picket'] and out['pattern_alternates'] is False,
                       'detail': {'pattern_keys': out['pattern_keys'],
                                  'note': 'two-rail panel: the single picket run maps completely; no consumer_infill_single_cycle withholding exists for this configuration'}})
        # Behavior, not just parsing. The resolver record uses a CLOSED
        # enumeration; the check passes on exactly one of:
        #   outcome == 'expected_dimensionless_draft_refusal' -- the resolver
        #     refused to fill the infill axis from the dimension-less draft
        #     Part, proving it invents no dimensions;
        #   outcome == 'resolved' with a NONEMPTY slot list whose entries all
        #     carry length_mm -- a genuine computed answer.
        # A missing record (the model never parsed, or the probe never reached
        # the resolver), an 'unexpected_error', an empty slot list or a slot
        # without length_mm all FAIL. This check does not evaluate receiving
        # geometry and does not claim to.
        resolution = out.get('panel_resolution')
        if resolution is None or resolution.get('outcome') == 'unexpected_error':
            behaves = False
        elif resolution.get('outcome') == 'expected_dimensionless_draft_refusal':
            behaves = True
        elif resolution.get('outcome') == 'resolved':
            slots = resolution.get('slots')
            behaves = (isinstance(slots, list) and len(slots) > 0
                       and all(type(s.get('length_mm')) is int for s in slots))
        else:
            behaves = False
        checks.append({'check': 'panel_resolution_behaves_as_declared',
                       'ok': behaves,
                       'detail': {'asserted_outcome':
                                      'expected_dimensionless_draft_refusal (dimension-availability '
                                      'refusal; receiving geometry NOT evaluated) or resolved-nonempty',
                                  'actual': resolution}})
        # Mapping completeness and capability honesty come from the candidate
        # file itself; the probe re-verifies rather than trusting the file.
        completeness = candidate_file.get('mapping_completeness', {})
        capabilities = candidate_file.get('capability_validation', {})
        checks.append({'check': 'mapping_completeness_holds',
                       'ok': completeness.get('complete') is True
                             and sorted(completeness.get('mapped_member_keys', [])
                                        + completeness.get('withheld_member_keys', []))
                             == completeness.get('draft_member_keys'),
                       'detail': completeness})
        checks.append({'check': 'fixing_count_complete_holds',
                       'ok': completeness.get('fixing_count_complete') is True
                             and completeness.get('mapped_u_channel_segments') == 2
                             and completeness.get('withheld_u_channel_segments') == 0,
                       'detail': completeness})
        checks.append({'check': 'unvalidated_capabilities_marked',
                       'ok': capabilities and all(
                              isinstance(capabilities[k].get('validated'), bool)
                              and capabilities[k]['validated'] is False
                              and capabilities[k].get('why')
                              for k in ('assembly', 'fitting', 'cutting', 'purchasing')),
                       'detail': {k: capabilities[k].get('validated') for k in capabilities}})
    return {'consumer_root': str(CONSUMER_ROOT), 'checks': checks}


def main():
    for path, sha in SOURCES:
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != sha:
            raise ValueError('Retained source bytes changed: ' + path)
    verify_dataset()
    package = json.loads(DRAFT.read_text())
    conn = connect()
    try:
        imported = {'cadpage': recipe.import_cadpage_readings(conn),
                    'install': recipe.import_install_readings(conn),
                    'specsheet': recipe.import_specsheet_readings(conn)}
        # The authored record passes through the normal builder so its preflight
        # exclusions and nullable-field gaps publish in the snapshot itself.
        snapshot = build_snapshot(tenant='default', conn=conn,
                                 authored_records=[package])
        verify(snapshot)
        # Hard boundary: Emblem-owned Parts must be byte-identical across
        # snapshots; the check fails the run before anything is stored.
        interference = emblem_interference(PREVIOUS_SNAPSHOT, snapshot)
        # Authored-model preflight on the live store's published Parts.
        refs = []
        def walk(node):
            if isinstance(node, dict):
                if isinstance(node.get('id'), str) and isinstance(node.get('belongs_to'), str):
                    refs.append({'id': node['id'], 'belongs_to': node['belongs_to']})
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)
        walk([package['model_fragment'], package['field_evidence']])
        walk(snapshot['parts'])
        admission = admit_authored_models([package], parts=snapshot['parts'],
            source_docs=snapshot['source_docs'], source_refs=refs, reviews=[])
        # Consumer validation through the consumer's own environment
        # (never publishes anything; reads only the local snapshot copy).
        consumer = consumer_checks(snapshot, package)
        failed = [c['check'] for c in consumer['checks'] if not c['ok']]
        if not interference['ok']:
            failed.append('emblem_non_interference')
        if failed:
            # A failed consumer check or a failed boundary check must never
            # read as success: the snapshot is NOT stored, the failure is
            # reported, and the exit code is nonzero (the Emblem
            # completion_code discipline, applied here).
            report = {'scope': 'Pembroke 6x6 assembly slice — ABORTED: consumer/boundary checks failed',
                'snapshot_id': snapshot['snapshot_id'], 'snapshot_stored': False,
                'failed_consumer_checks': failed,
                'emblem_interference': interference,
                'consumer': consumer,
                'sources': [{'path': p, 'sha256': s} for p, s in SOURCES]}
            with open_write(ROOT / 'workspace/reports/pembroke-assembly-publication.json') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
                f.write('\n')
            print(json.dumps({'aborted': True, 'failed_consumer_checks': failed}))
            return 2
        path = put_snapshot(snapshot)
        report = {
            'scope': 'Pembroke 6x6 assembly slice: composition, counts, authored model candidate',
            'sources': [{'path': p, 'sha256': s} for p, s in SOURCES],
            'imported': imported,
            'snapshot_id': snapshot['snapshot_id'],
            'snapshot_path': str(path.relative_to(ROOT)),
            'snapshot_stored': True,
            'consumer_checks_passed': not failed,
            'emblem_interference': interference,
            'composition_parts': [p for p in snapshot['parts'] if p['id'] in COMPOSITION_PARTS],
            'value_parts': [p for p in snapshot['parts'] if p['id'].startswith('mfr/weatherables/pembroke-6x6-')],
            'models_admitted': len(snapshot['models']),
            'model_exclusions': admission['exclusions'],
            'model_readiness': admission['readiness'],
            'nullable_gaps': [g for g in snapshot['gaps'] if g.get('code') == 'authored_model_incomplete_value'],
            'consumer': consumer,
            'consumer_validation_scope': (
                'Consumer checks prove: ingestion, dialect fidelity (unit conversion with every precision '
                'loss recorded — lengths and placements floor, counts refuse fractional values; height '
                'field; single-run pattern fully mapped with no withholding; centerline placement '
                'datum), parser acceptance, mapping completeness (mapped + withheld == draft members '
                'AND draft counts — here 2 mapped u-channel segments == the authored 2, nothing '
                'withheld), that validate_model and the real panel resolver REFUSE undeclared geometry '
                '— with a closed outcome enumeration: only the expected dimension-availability refusal '
                'or a genuinely computed nonempty result passes; missing records, unexpected errors, '
                'and empty results all fail. They do NOT prove assembly, fitting, cutting or '
                'purchasing: capability_validation marks all four validated=false with reasons, and '
                'they stay unvalidated until receiving geometry and step reviews exist. The '
                'panel-resolution refusal is the resolver refusing to fill an axis from an inactive, '
                'dimension-less draft Part — the boundary between "validated parsing" and "validated '
                'assembly" is demonstrated, not claimed. The advance script refuses to store the '
                'snapshot and exits nonzero if any check fails, and the Emblem byte-comparison '
                '(non-interference) gates the same store.'),
            'human_reviews_created': False,
            'remaining_gaps': [
                'Receiving geometry (rail slot depth, picket seating beyond the implied 3.25in, post rail-socket depth) is absent from all retained sources; fitted dimensions, seated cut lengths and engagement checks remain unvalidated.',
                'Exact SKU identity for the 6x6 kit; per-style color availability beyond the dataset list needs per-SKU verification.',
                'FenceModel publication remains blocked by the unresolved numeric provenance mapping (Amendment 008 pending).',
                'Purchasing quantities: installed per-panel counts are manufacturer kit inventory (2 rails, 1 metal insert, 6 pickets, 2 u-channels); posts, caps and concrete are separate purchases and the panel kit lists none.',
                'The local CAD raster canonical OCR is unusable (2 garbled labels, mean conf 0); its corroborating labels (72 width, 5.5/61/5.5 chain) are recorded in workspace/reports/pembroke-source-review/findings.md as diagnostic re-OCR evidence only — no fact anchors to that OCR and no Part cites the PNG.',
            ],
        }
        out = ROOT / 'workspace/reports/pembroke-assembly-publication.json'
        with open_write(out) as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            f.write('\n')
        print(json.dumps({'snapshot_id': snapshot['snapshot_id'],
            'composition_parts': len(report['composition_parts']),
            'value_parts': len(report['value_parts']),
            'models_admitted': report['models_admitted'],
            'model_excluded': bool(report['model_exclusions']),
            'emblem_non_interference': interference['ok'],
            'consumer_checks': {c['check']: c['ok'] for c in consumer['checks']}}))
        return 0
    finally:
        conn.close()


if __name__ == '__main__':
    sys.exit(main())