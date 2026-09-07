"""Read-only S→C→K→P checkpoint for a declared Part conversion batch.

Reuses the existing snapshot builder and verifier. The manifest is a run recipe,
not a claims store, public schema, importer, or replacement review ledger.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fence_evidence.canonical import content_hash
from fence_evidence.paths import open_write
from fence_evidence.refs import ref_id
from fence_evidence.snapshot import build_snapshot, verify
from fence_evidence.store import connect


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_bindings(conn, bindings, parts):
    """Trace every selected public spec to an existing canonical-bound fact."""
    traces = []
    for part in parts:
        for spec in part['spec']:
            candidates = [b for b in bindings if b['part_id'] == part['id'] and b['spec_key'] == spec['key']]
            if len(candidates) != 1:
                raise ValueError('Missing or ambiguous claim binding: ' + part['id'] + '/' + spec['key'])
            binding = candidates[0]
            rows = conn.execute('''SELECT f.*, e.text AS canonical_text,e.bbox,
                e.page_no AS canonical_page,e.version_id AS canonical_version,
                e.document_id AS canonical_document,v.sha256
                FROM facts f JOIN elements e ON f.element_id=e.element_id
                JOIN document_versions v ON e.version_id=v.version_id
                WHERE f.extractor=? AND f.fact_type=? AND f.element_id=?''',
                (binding['extractor'],binding['fact_type'],binding['element_id'])).fetchall()
            if len(rows) != 1:
                raise ValueError('Missing or ambiguous persisted claim: ' + spec['key'])
            row = rows[0]
            if (row['review_status'] == 'rejected' or row['evidence_text'] != row['canonical_text']
                    or row['page_no'] != row['canonical_page'] or row['version_id'] != row['canonical_version']
                    or row['document_id'] != row['canonical_document']):
                raise ValueError('Claim state or canonical binding mismatch: ' + spec['key'])
            cite = {'id':ref_id(row['sha256'],row['page_no'],row['bbox']), 'belongs_to':row['sha256']}
            if cite not in spec['provenance']['cites']:
                raise ValueError('Published specification lost its claim evidence: ' + spec['key'])
            traces.append({'part_id':part['id'],'spec_key':spec['key'],'fact_id':row['fact_id'],
                'element_id':row['element_id'],'source_ref':cite,'review_status':row['review_status'],
                'value_original':row['value_original'],'reviewed_value':row['reviewed_value'],
                'published_value':spec['value'],'provenance':spec['provenance']})
    return traces


def compare_slice(expected, current, ids):
    def select(snapshot):
        chosen = [p for p in snapshot['parts'] if p['id'] in ids]
        if len({p['id'] for p in chosen}) != len(chosen):
            raise ValueError('Duplicate selected Part identity')
        return sorted(chosen,key=lambda p:p['id'])
    old, new = select(expected), select(current)
    if old != new:
        raise ValueError('Selected published slice differs from current publisher; rebuild through the normal publication path')
    return new


def check_batch(batch, conn, stages):
    if batch['profile'] != 'persisted-facts-to-parts-v1' or not batch['part_ids']:
        raise ValueError('Unsupported or empty conversion profile')
    if len(set(batch['part_ids'])) != len(batch['part_ids']):
        raise ValueError('Duplicate requested Part identity')
    for source in batch['sources']:
        if digest(ROOT/source['path']) != source['sha256']:
            raise ValueError('Source bytes changed: ' + source['path'])
    stages.append({'stage':'S','status':'checked','sources':batch['sources']})
    for line in (ROOT/'docs/integration/contract.sha256').read_text().splitlines():
        expected, name = line.split()
        if digest(ROOT/'docs/integration'/name) != expected:
            raise ValueError('Frozen boundary checksum mismatch: ' + name)
    stored = json.loads((ROOT/batch['snapshot']).read_text())
    verify(stored)
    # Current producer also checks review projections and contract reference closure.
    current = build_snapshot(tenant=batch['tenant'],conn=conn)
    verify(current)
    parts = compare_slice(stored,current,set(batch['part_ids']))
    traces = check_bindings(conn,batch['bindings'],parts)
    source_hashes = {s['sha256'] for s in batch['sources']}
    if any(cite['belongs_to'] not in source_hashes for p in parts for s in p['spec'] for cite in s['provenance']['cites']):
        raise ValueError('Published evidence falls outside declared source scope')
    stages.extend([{'stage':'C/K','status':'checked','claim_traces':traces},
        {'stage':'P','status':'checked','snapshot_id':stored['snapshot_id'],
         'selected_parts_reproduced':len(parts),'missing_requested_parts':sorted(set(batch['part_ids'])-{p['id'] for p in parts})}])
    return 'partial_knowledge_verified' if parts and traces else 'no_supported_slice'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('batch',type=Path)
    parser.add_argument('--round',type=int,choices=(1,2,3),default=1,
                        help='Initial checkpoint plus at most two correction rounds per batch revision')
    parser.add_argument('--lesson',action='append',default=[])
    parser.add_argument('--propose',action='append',default=[])
    args=parser.parse_args()
    batch=json.loads(args.batch.read_text())
    result={'batch_id':batch['batch_id'],'batch_hash':content_hash(batch),
        'run_id':uuid4().hex,'at':datetime.now(timezone.utc).isoformat(),'round':args.round,
        'stages':[],'rerun':['source hashes','canonical/fact/spec joins','current publisher selected Part comparison','snapshot verification','frozen boundary checks'],
        'reused_not_rerun':batch.get('historical_evidence',[]),
        'limitations':batch['limitations'],'lessons':args.lesson,'proposed_improvements':args.propose,
        'runner_sha256':digest(Path(__file__)),
        'implementation_hashes':{name:digest(ROOT/name) for name in batch['implementation_files']}}
    try:
        conn=connect(read_only=True)
        try:
            conn.execute('BEGIN')
            result['status']=check_batch(batch,conn,result['stages'])
        finally:
            conn.close()
    except Exception as error:
        result.update(status='failed',error=type(error).__name__+': '+str(error))
    output=ROOT/'workspace/reports/conversion-runs'/ (result['run_id']+'.json')
    with open_write(output) as f:
        json.dump(result,f,indent=2,ensure_ascii=False);f.write('\n')
    with open_write(ROOT/'workspace/reports/conversion-runs/history.jsonl',mode='a') as f:
        f.write(json.dumps(result,ensure_ascii=False)+'\n')
    print(json.dumps({'status':result['status'],'run_log':str(output)}))
    return 0 if result['status']=='partial_knowledge_verified' else 2


if __name__=='__main__':
    sys.exit(main())
