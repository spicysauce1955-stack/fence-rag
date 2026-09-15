"""Audit actual Emblem instances and their joins; exit 2 while admission is blocked.

This report joins existing validators and canonical references. It does not define
another wire schema, fabricate reviews or make a private parser the authority.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fence_evidence.canonical import content_hash
from fence_evidence.part_types import SPINE
from fence_evidence.paths import open_write
from fence_evidence.refs import build_index
from fence_evidence.snapshot import build_snapshot, verify
from fence_evidence.store import connect
from scripts.prepare_emblem_consumer_model import prepare


def walk(node, path=''):
    yield path, node
    if isinstance(node, dict):
        for key, child in node.items():
            escaped = str(key).replace('~', '~0').replace('/', '~1')
            yield from walk(child, path + '/' + escaped)
    elif isinstance(node, list):
        for index, child in enumerate(node):
            yield from walk(child, path + '/' + str(index))


def reference_graph(model, parts, published_parts):
    """Check actual IDs without treating draft existence as publication."""
    ids = Counter(p['id'] for p in parts if isinstance(p, dict)
                  and isinstance(p.get('id'), str) and p['id'])
    published = {p['id'] for p in published_parts if isinstance(p, dict)
                 and isinstance(p.get('id'), str) and p['id']}
    requirements = []
    for path, node in walk(model):
        if isinstance(node, dict) and 'part_id' in node:
            pid = node['part_id']
            requirements.append({'path': path + '/part_id', 'part_id': pid,
                'definition_count': ids.get(pid, 0) if isinstance(pid, str) else 0,
                'published': isinstance(pid, str) and pid in published,
                'selection': 'literal' if pid else 'predicate_or_unresolved'})
    spec = model.get('default_spec', {}) if isinstance(model, dict) else {}
    spec = spec if isinstance(spec, dict) else {}
    frame_list = spec.get('frame', [])
    frames = Counter(s['key'] for s in frame_list if isinstance(s, dict)
                     and isinstance(s.get('key'), str) and s['key']) if isinstance(frame_list, list) else Counter()
    supports = []
    infill = spec.get('infill')
    pattern = infill.get('pattern', []) if isinstance(infill, dict) else []
    for member in pattern if isinstance(pattern, list) else []:
        if not isinstance(member, dict):
            continue
        for side in ('base_ref', 'top_ref'):
            key = member.get(side)
            supports.append({'member_key': member.get('key'), 'edge': side,
                             'frame_key': key, 'definition_count': frames.get(key, 0) if isinstance(key, str) else 0})
    literals = [r for r in requirements if r['selection'] == 'literal']
    return {'requirements': requirements, 'support_edges': supports,
            'duplicate_part_ids': sorted(k for k, n in ids.items() if n > 1),
            'literal_part_closure': bool(literals) and all(r['definition_count'] == 1 for r in literals),
            'published_part_closure': bool(requirements) and all(r['published'] for r in requirements),
            'support_reference_closure': bool(supports) and all(r['definition_count'] == 1 for r in supports)}


def audit(package, candidate, conn, confirmation=None):
    snapshot = build_snapshot(tenant='default', conn=conn, authored_records=[package])
    verify(snapshot)
    index = build_index(conn)
    references = {}
    for artifact, record in (('public_draft', package), ('private_candidate', candidate)):
        for path, node in walk(record):
            if not isinstance(node, dict) or not {'id', 'belongs_to'} <= node.keys():
                continue
            rid, sha = node['id'], node['belongs_to']
            locus = index.get(rid)
            item = references.setdefault((rid, sha), {'id': rid, 'belongs_to': sha,
                'canonical_locus_matches': locus is not None and locus.sha256 == sha,
                'uses': []})
            item['uses'].append({'artifact': artifact, 'path': path})
    sources = []
    for source in package['sources']:
        path = ROOT / source['path']
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        sources.append({'path': source['path'], 'expected_sha256': source['content_hash'],
                        'actual_sha256': actual, 'matches': actual == source['content_hash']})
    public_parts = package['part_fragments']
    private_parts = candidate['component_authoring']['private_parts']
    types = [{'part_id': p['id'], 'type': p.get('type'),
              'shared_spine_match': isinstance(p.get('type'), dict)
              and p['type'].get('namespace') == 'shared' and p['type'].get('key') in SPINE}
             for p in public_parts]
    gaps = [g for g in snapshot['gaps'] if g['because']['code'].startswith('authored_model_')]
    return {'scope': 'actual instance/reference audit; no complete physical-fit or wire-adapter claim',
        'authority_files': [{'path': str(p.relative_to(ROOT)),
            'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in [
                ROOT / 'docs/integration/contract.md', ROOT / 'docs/integration/knowledge-datamodel.md',
                ROOT / 'docs/integration/knowledge-design.md', ROOT / 'docs/four-layer-model-design.md']],
        'artifact_hashes': {'public_draft': content_hash(package), 'private_candidate': content_hash(candidate)},
        'candidate_declares_current_source_package_hash': candidate['source_package_hash'] == content_hash(package),
        'candidate_reproduces_from_checked_inputs': content_hash(candidate) == content_hash(prepare(package, confirmation)),
        'source_file_checks': sources, 'canonical_source_ref_checks': list(references.values()),
        'public_part_type_checks': types,
        'public_draft_graph': reference_graph(package['model_fragment'], public_parts, snapshot['parts']),
        'private_candidate_graph': reference_graph(candidate['model'], private_parts, snapshot['parts']),
        'snapshot': {'verified': True, 'id': snapshot['snapshot_id'],
            'parts': len(snapshot['parts']), 'models': len(snapshot['models']), 'authored_model_gaps': gaps},
        'complete_model_admitted': any(m['id'] == package['model_fragment']['id'] for m in snapshot['models']),
        'limitations': ['Reference closure proves identity/addressing, not interpretation of a source.',
            'The public artifact is explicitly a fragment; missing fields remain missing.',
            'The private candidate is not a contract-wire instance.',
            'No trusted human review, synthetic dimensions or consumer result is created by this audit.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'workspace/reports/emblem-instance-validation.json')
    args = parser.parse_args()
    package = json.loads((ROOT / 'workspace/catalog/emblem-73014714-model-draft.json').read_text())
    candidate = json.loads((ROOT / 'workspace/catalog/emblem-73014714-consumer-model.json').read_text())
    confirmation = json.loads((ROOT / 'workspace/catalog/emblem-73014714-placement-confirmation.json').read_text())
    conn = connect(read_only=True)
    try:
        result = audit(package, candidate, conn, confirmation)
    finally:
        conn.close()
    with open_write(args.output) as output:
        json.dump(result, output, indent=2, ensure_ascii=False)
        output.write('\n')
    print(json.dumps({'report': str(args.output), 'complete_model_admitted': result['complete_model_admitted'],
                      'source_refs': len(result['canonical_source_ref_checks'])}))
    return 0 if result['complete_model_admitted'] else 2


if __name__ == '__main__':
    sys.exit(main())
