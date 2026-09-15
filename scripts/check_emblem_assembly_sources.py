"""Read-only canonical cross-reference of retained assembly evidence anchors."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fence_evidence.canonical import content_hash
from fence_evidence.paths import open_write
from fence_evidence.refs import ref_id
from fence_evidence.store import connect


def check_anchor(conn, anchor):
    row = conn.execute('''SELECT e.*, v.sha256 FROM elements e
        JOIN document_versions v ON e.version_id=v.version_id WHERE element_id=?''',
        (anchor['element_id'],)).fetchone()
    return {'element_id': anchor['element_id'], 'cite': anchor['cite'],
        'page': row['page_no'] if row else None,
        'text_matches': row is not None and row['text'] == anchor['text_raw'],
        'source_matches': row is not None and row['sha256'] == anchor['cite']['belongs_to'],
        'region_matches': row is not None and ref_id(row['sha256'],row['page_no'],row['bbox']) == anchor['cite']['id']}


def main():
    path = ROOT / 'workspace/catalog/emblem-73014714-model-draft.json'
    package = json.loads(path.read_text())
    with connect(read_only=True) as conn:
        checks = [{'relationship': r['relationship'], **check_anchor(conn,r['evidence_anchor'])}
                  for r in package['connection_evidence']]
        checks += [{'relationship': r['condition'], **check_anchor(conn,r['anchor'])}
                   for r in package['conditional_design_evidence']]
    sources = [{'path':s['path'], 'matches': hashlib.sha256((ROOT/s['path']).read_bytes()).hexdigest() == s['content_hash']}
               for s in package['sources']]
    passed = bool(checks) and all(all(c[k] for k in ('text_matches','source_matches','region_matches')) for c in checks) and all(s['matches'] for s in sources)
    result = {'scope':'Retained local source bytes and exact canonical assembly evidence only',
        'package_hash':content_hash(package),'checks':checks,'sources':sources,
        'verified':passed,'emblem_fit_validated':False,
        'limitations':['This command checks retained canonical sources only; recovered revised-manual comparison is recorded separately in emblem-recovered-manual-check.json.',
            'Assembly relations do not supply numerical overlap, receiving depths or channel lengths.',
            'No review, source admission, or publication decision is created.']}
    with open_write(ROOT/'workspace/reports/emblem-assembly-source-check.json') as f:
        json.dump(result,f,indent=2)
        f.write('\n')
    print(json.dumps({'verified':passed,'anchors':len(checks),'source_files':len(sources)}))
    return 0 if passed else 2


if __name__ == '__main__':
    sys.exit(main())
