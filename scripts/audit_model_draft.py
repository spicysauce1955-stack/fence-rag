"""Audit the private model draft; this is not a full Planning schema validator.

Run from the repository root. Exit 0 means the checked subset passes, 1 means
draft integrity errors, and 2 means contract fields remain incomplete.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import re
from pathlib import Path
import sqlite3
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fence_evidence.canonical import canonical_bytes
from fence_evidence.part_types import SPINE
from fence_evidence.paths import EVIDENCE_DB, REPO_ROOT, open_write
from fence_evidence.refs import build_index


# Required field presence from knowledge-datamodel.md §§3.1–3.5. This does not
# settle union serialization, policy admission, fit arithmetic or applicability.
FIELDS = {
    'Part': 'id version status type name_i18n spec authorship cites contributing_sources',
    'FenceModel': 'id version status name_i18n grade height_support option_axes default_spec variants layout_policy post assembly authorship cites contributing_sources',
    'PanelSpec': 'frame infill fixings',
    'FrameSlot': 'key orientation placement joint requirement contains',
    'InfillSpec': 'orientation pattern justification excess edge_margin supply',
    'Member': 'key base_ref top_ref joint base_engagement top_engagement gap_after face_offset profile_edges requirement contains',
    'PostSlot': 'key joint requirement cap contains',
    'PartRequirement': 'part_id qty length_rule overlap option_axis sku_by_option eligibility',
    'Joint': 'kind channel_depth insertion_margin shared_host_gap gap_reason',
}


def fitting_readiness(package):
    """Inspect dependencies only. This repository does not own the fitter."""
    model = package['model_fragment']
    panel = model['default_spec']
    parts = {part['id']: part for part in package['part_fragments']}
    missing = []
    for i, member in enumerate(panel['infill']['pattern']):
        part = parts.get(member['requirement'].get('part_id'), {})
        specs = {sf['key']: sf for sf in part.get('spec', [])}
        for key in ('width_mm', 'thickness_mm', 'nominal_length_mm'):
            if key not in specs:
                missing.append(f"board[{i}].Part.spec.{key}")
        for key in ('base_engagement', 'top_engagement', 'gap_after'):
            if key not in member:
                missing.append(f'board[{i}].{key}')
    for slot in panel['frame']:
        if 'placement' not in slot:
            missing.append(f"frame.{slot['key']}.placement")
        if 'channel_depth' not in slot.get('joint', {}):
            missing.append(f"frame.{slot['key']}.joint.channel_depth")
        part = parts.get(slot['requirement'].get('part_id'), {})
        if not any(sf['key'] == 'nominal_length_mm' for sf in part.get('spec', [])):
            missing.append(f"frame.{slot['key']}.Part.spec.nominal_length_mm")
    for key in ('edge_margin', 'justification', 'excess'):
        if key not in panel['infill']:
            missing.append(f'infill.{key}')
    return {'status': 'blocked' if missing else 'requires_Planning_execution',
            'missing_inputs': missing, 'authored_frame_positions': len(panel['frame']),
            'board_count': None, 'cut_lengths': None,
            'reason': 'No fitting/BOM engine is present here. Nominal board width is not effective pitch; panel width is not clear infill width. Field presence alone never proves fit.'}


def audit(package, conn):
    errors, missing = [], []
    index = build_index(conn)
    sources = {s['content_hash']: s for s in package['sources']}
    source_docs = {s['content_hash']: s for s in package.get('source_docs', [])}
    for sha, source in sources.items():
        path = REPO_ROOT / source['path']
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            errors.append(f"source hash mismatch: {source['path']}")
        row = conn.execute('SELECT 1 FROM document_versions WHERE document_id=? AND sha256=?',
                           (source['document_id'], sha)).fetchone()
        if row is None:
            errors.append(f"document/version mismatch: {source['document_id']}")
        if sha not in source_docs:
            errors.append(f'missing SourceDoc: {sha}')

    cites_checked = 0

    def walk(value, path='$'):
        nonlocal cites_checked
        if isinstance(value, dict):
            if 'belongs_to' in value:
                cites_checked += 1
                locus = index.get(value.get('id'))
                if locus is None or locus.sha256 != value['belongs_to']:
                    errors.append(f'{path}: citation does not resolve to its owner')
                if value['belongs_to'] not in source_docs:
                    errors.append(f'{path}: citation has no pinned SourceDoc')
            if 'element_id' in value and 'text_raw' in value:
                row = conn.execute('SELECT text FROM elements WHERE element_id=?',
                                   (value['element_id'],)).fetchone()
                locus = index.get(value.get('cite', {}).get('id'))
                if row is None or row['text'] != value['text_raw']:
                    errors.append(f'{path}: source text differs')
                if locus is None or value['element_id'] not in locus.element_ids:
                    errors.append(f'{path}: anchor citation names another element')
            if 'amount_milli' in value:
                if type(value['amount_milli']) is not int:
                    errors.append(f'{path}: quantity must use integer thousandths')
                if not isinstance(value.get('value_raw'), list) or not value['value_raw']:
                    errors.append(f'{path}: quantity needs source lexemes')
            for key, child in value.items():
                walk(child, f'{path}/{key}')
        elif isinstance(value, list):
            for i, child in enumerate(value):
                walk(child, f'{path}/{i}')

    walk(package)
    try:
        canonical_bytes(package)
    except (TypeError, ValueError) as exc:
        errors.append(f'canonical serialization: {exc}')

    parts = package['part_fragments']
    ids = {p['id'] for p in parts}
    if len(ids) != len(parts):
        errors.append('duplicate Part.id')

    def shape(obj, kind, path):
        if not isinstance(obj, dict):
            errors.append(f'{path}: expected {kind} object')
            return
        for key in FIELDS[kind].split():
            if key not in obj:
                missing.append({'path': f'{path}/{key}', 'shape': kind})

    def requirement(obj, path):
        shape(obj, 'PartRequirement', path)
        if obj.get('part_id') not in ids:
            errors.append(f'{path}: unresolved Part reference')
        if 'role' in obj:
            errors.append(f'{path}: role must be derived, never authored')

    for i, part in enumerate(parts):
        shape(part, 'Part', f'/part_fragments/{i}')
        if part.get('type', {}).get('namespace') != 'shared' or part['type'].get('key') not in SPINE:
            errors.append(f'/part_fragments/{i}: unsupported type in this draft audit')
        seen = set()
        for sf in part.get('spec', []):
            if sf.get('key') in seen:
                errors.append(f"{part['id']}: duplicate spec key")
            seen.add(sf.get('key'))
            prov = sf.get('provenance', {})
            if not prov.get('cites') or prov.get('curation_level') not in (0, 1, 2):
                errors.append(f"{part['id']}: incomplete spec provenance")
            if prov.get('version_status') not in ('active', 'superseded', 'unknown'):
                errors.append(f"{part['id']}: invalid spec version status")
            if sf.get('agree') != '==':
                errors.append(f"{part['id']}: unsupported spec comparison in this audit")
    model = package['model_fragment']
    shape(model, 'FenceModel', '/model_fragment')
    for obj in [model, *parts]:
        owners = sorted({c['belongs_to'] for c in obj.get('cites', [])})
        if obj.get('contributing_sources') != owners:
            errors.append(f"{obj['id']}: source roll-up differs from citations")
    panel = model['default_spec']
    base = '/model_fragment/default_spec'
    shape(panel, 'PanelSpec', base)
    keys = [slot['key'] for slot in panel['frame']]
    if len(set(keys)) != len(keys):
        errors.append('duplicate FrameSlot.key')
    for i, slot in enumerate(panel['frame']):
        path = f'{base}/frame/{i}'
        shape(slot, 'FrameSlot', path)
        if 'joint' in slot:
            shape(slot['joint'], 'Joint', path + '/joint')
        requirement(slot['requirement'], path + '/requirement')
    infill = panel['infill']
    shape(infill, 'InfillSpec', base + '/infill')
    for i, member in enumerate(infill['pattern']):
        path = f'{base}/infill/pattern/{i}'
        shape(member, 'Member', path)
        requirement(member['requirement'], path + '/requirement')
        for ref in ('base_ref', 'top_ref'):
            if member.get(ref) not in keys:
                errors.append(f'{path}/{ref}: unresolved FrameSlot reference')
    post = model['post']
    shape(post, 'PostSlot', '/model_fragment/post')
    for field in ('requirement', 'cap'):
        if isinstance(post.get(field), dict):
            requirement(post[field], '/model_fragment/post/' + field)
    for binding in package.get('pending_bindings', []):
        for candidate in binding['candidates']:
            if candidate['part_id'] not in ids:
                errors.append('pending post binding names unknown Part')
    for reading in package['confirmed_readings']:
        anchor = reading.get('evidence_anchor', {})
        if any(raw not in anchor.get('text_raw', '') for raw in reading['value']['value_raw']):
            errors.append(f"{reading['key']}: lexeme absent from source anchor")
        raw = reading['value']['value_raw'][0]
        match = re.match(r'(\d+)(?:[- ]?([¼½¾]))?\s*in\.', raw)
        if not match:
            errors.append(f"{reading['key']}: unsupported source quantity in this audit")
        else:
            inches = Fraction(match[1]) + {'¼': Fraction(1, 4), '½': Fraction(1, 2),
                                         '¾': Fraction(3, 4), None: Fraction(0)}[match[2]]
            if reading['value'].get('unit') != 'mm' or reading['value']['amount_milli'] != inches * 25400:
                errors.append(f"{reading['key']}: incorrect inch-to-millimetre conversion")
    for association in package.get('part_identity_anchors', []):
        sku = association['model_number']['text_raw']
        if association['part_id'] not in ids or association['part_id'].rsplit('/', 1)[-1] != sku:
            errors.append('Part identity differs from source model number')
        description = index.get(association['description']['cite']['id'])
        number = index.get(association['model_number']['cite']['id'])
        if description and number:
            same_row = (description.sha256 == number.sha256 and description.page_no == number.page_no
                        and description.bbox and number.bbox
                        and json.loads(description.bbox)[1::2] == json.loads(number.bbox)[1::2])
            if not same_row:
                errors.append('Part description and model number are not on the same source row')
    specs_checked = 0
    evidence = {(item['part_id'], item['spec_key']): item for item in package.get('spec_evidence', [])}
    for part in parts:
        for sf in part.get('spec', []):
            specs_checked += 1
            entry = evidence.get((part['id'], sf['key']))
            if not entry:
                errors.append(f"{part['id']}/{sf['key']}: missing exact spec evidence")
                continue
            raw_values = sf.get('value', {}).get('value_raw', [])
            if not raw_values or any(raw not in entry['anchor']['text_raw'] for raw in raw_values):
                errors.append(f"{part['id']}/{sf['key']}: spec lexeme differs from source")
            if entry['anchor']['cite'] not in sf.get('provenance', {}).get('cites', []):
                errors.append(f"{part['id']}/{sf['key']}: spec citation differs from anchor")
            if 'amount_milli' in sf['value']:
                match = re.fullmatch(r'(\d+)(?:[- ]?([¼½¾]))?\s*in\.', raw_values[0]) if raw_values else None
                if not match:
                    errors.append(f"{part['id']}/{sf['key']}: unsupported numeric lexeme")
                else:
                    amount = Fraction(match[1]) + {None: 0, '¼': Fraction(1, 4), '½': Fraction(1, 2), '¾': Fraction(3, 4)}[match[2]]
                    if sf['value'].get('unit') != 'mm' or sf['value']['amount_milli'] != amount * 25400:
                        errors.append(f"{part['id']}/{sf['key']}: incorrect spec conversion")
    external_check = 'not_applicable'
    external = package.get('external_applicability_evidence')
    if external:
        download = REPO_ROOT / external['download_path']
        if not download.is_file():
            external_check = 'not_checked_cache_missing'
        elif hashlib.sha256(download.read_bytes()).hexdigest() != external['download_sha256']:
            external_check = 'failed'
            errors.append('linked manual download hash mismatch')
        else:
            external_check = 'verified'
            content = subprocess.check_output(['pdftotext', '-raw', str(download), '-']).decode()
            compact = lambda text: re.sub(r'\s+', ' ', text).strip()
            for connection in package.get('connection_evidence', []):
                if compact(connection['evidence_anchor']['text_raw']) not in compact(content):
                    external_check = 'failed'
                    errors.append('connection statement absent from linked manual')
    if (missing or errors) and package.get('publishable') is not False:
        errors.append('incomplete draft incorrectly claims publishable')
    return {'draft_integrity_passed': not errors, 'errors': errors,
            'field_check_basis': 'syntactic_presence_diagnostics_not_mandatory_authoring_requirements',
            'wire_shape_issues': [
                'PartRequirement presence checks include mutually exclusive modes; not every absent field is required.',
                'Planning private length_rule uses registered names, but published models have no consumer adapter; private defaults are not wire agreement.'],
            'external_applicability_check': external_check,
            'missing_contract_fields': missing, 'missing_contract_field_count': len(missing),
            'citations_checked': cites_checked, 'source_hashes_checked': len(sources),
            'spec_fields_checked': specs_checked, 'fitting_readiness': fitting_readiness(package),
            'contract_validity': 'incomplete' if missing else 'not_established',
            'limitations': ['Presence checks cover this draft shape only, not a full contract schema.',
                            'No Planning consumer, fit or BOM execution is performed.',
                            'Source applicability and authored choices still require semantic review.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('draft', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    conn = sqlite3.connect(f'file:{EVIDENCE_DB}?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    try:
        result = audit(json.loads(args.draft.read_text()), conn)
    finally:
        conn.close()
    if args.report:
        with open_write(args.report, encoding='utf-8') as handle:
            json.dump(result, handle, indent=2)
            handle.write('\n')
    print(json.dumps(result, indent=2))
    sys.exit(1 if result['errors'] else 2 if result['missing_contract_fields'] else 0)
