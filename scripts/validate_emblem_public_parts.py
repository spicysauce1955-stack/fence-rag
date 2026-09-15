"""Exercise the actual Planning public Part reader; not a model/BOM adapter.

Run using Planning's Python environment. Success means the four published Parts
survive ingestion exactly, with resolvable source-document hashes and draft status intact.
SourceDoc extension metadata is outside this typed receipt guarantee.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fence_evidence.canonical import content_hash
from fence_evidence.emblem_claims import PART_READINGS
from fence_evidence.paths import open_write


def inspect(raw):
    from fenceai.knowledge.snapshot import ingest, load
    before = content_hash(raw)
    snapshot, defects = load(raw)
    receipt = ingest(snapshot)
    expected_ids = {part[0] for part in PART_READINGS}
    expected = [part for part in raw['parts'] if part['id'] in expected_ids]
    received = {part.id: part for part in receipt.published_parts}
    documents = {doc.content_hash for doc in receipt.source_docs}
    checks = []
    for part in expected:
        result = received.get(part['id'])
        refs = [cite for spec in part['spec'] for cite in spec['provenance']['cites']]
        checks.append({'part_id': part['id'], 'version': part['version'],
            'exact_public_round_trip': result is not None and result.model_dump(mode='json', exclude_unset=True) == part,
            'source_document_hashes_resolve': all(ref['belongs_to'] in documents for ref in refs),
            'draft_remains_inactive': part['status'] == 'draft' and part['id'] in receipt.inactive_parts,
            'not_a_generation_spec': not any(spec.part_id == part['id'] for spec in receipt.part_specs)})
    preserved = (len(checks) == len(expected_ids) and len({r['part_id'] for r in checks}) == len(expected_ids)
                 and all(all(r[key] for key in ('exact_public_round_trip', 'source_document_hashes_resolve',
                                                'draft_remains_inactive', 'not_a_generation_spec')) for r in checks))
    return {'scope': 'Actual published Part ingestion and provenance retention only',
        'snapshot_id': snapshot.snapshot_id, 'input_unchanged': before == content_hash(raw),
        'part_checks': checks, 'part_ingestion_verified': preserved and before == content_hash(raw),
        'part_defects': receipt.part_defects, 'quarantined_gap_count': len(defects),
        'model_count': len(snapshot.models), 'assembly_validated': False,
        'source_document_guarantee': 'Typed SourceDoc receipts retain citation hash joins; unknown extension metadata is not preserved.',
        'remaining': ['Public geometry/authoring mapping still needs an agreed representation and executable support.',
            'Private generation Part versions and selection are not changed by this receipt path.',
            'Source geometry, effective board pitch and fitting evidence remain incomplete.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--consumer-root', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'workspace/reports/emblem-public-parts-consumer-check.json')
    args = parser.parse_args()
    sys.path.insert(0, str(args.consumer_root.resolve() / 'src'))
    path = args.snapshot
    if path is None:
        progress = json.loads((ROOT / 'workspace/reports/emblem-workflow-progress.json').read_text())
        path = ROOT / 'workspace/snapshots' / (progress['snapshot_id'] + '.json')
    result = inspect(json.loads(path.read_text()))
    result['consumer_files'] = [{
        'path': filename, 'sha256': hashlib.sha256((args.consumer_root / filename).read_bytes()).hexdigest()}
        for filename in ('src/fenceai/knowledge/parts.py', 'src/fenceai/knowledge/snapshot.py')]
    with open_write(args.output) as output:
        json.dump(result, output, indent=2)
        output.write('\n')
    print(json.dumps({'scope': result['scope'], 'report': str(args.output),
        'part_ingestion_verified': result['part_ingestion_verified'], 'assembly_validated': False}))
    return 0 if result['part_ingestion_verified'] else 2


if __name__ == '__main__':
    sys.exit(main())
