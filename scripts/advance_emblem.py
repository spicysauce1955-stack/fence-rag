"""Reproduce the first Emblem claims-to-publication slice and full-model checklist.

Without --apply, work on an in-memory copy. --apply imports the bound readings
and stores a verified local snapshot. Neither mode publishes to a remote service.
Default success means verified partial knowledge is available.
--objective assembly requires the complete model and validated assembly.
"""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fence_evidence.authored_models import admit_authored_models
from fence_evidence.emblem_knowledge import completion_code, knowledge_ready, make_card, render_card
from scripts.check_emblem_assembly_sources import check_anchor
from fence_evidence.emblem_claims import BOARD_ID, EXTRACTOR, PART_READINGS, import_readings
from fence_evidence.paths import open_write
from fence_evidence.snapshot import build_snapshot, verify
from fence_evidence.snapshot_store import put_snapshot
from fence_evidence.store import connect
from scripts.validate_emblem_instances import audit, walk


# These are separate geometric datums, even where the same Joint shape owns them.
GEOMETRY = (
    ('/default_spec/frame/0/joint/channel_depth', 'Bottom rail board-pocket depth'),
    ('/default_spec/frame/1/joint/channel_depth', 'Top rail board-pocket depth'),
    ('/default_spec/infill/pattern/0/base_engagement', 'Board seating in bottom rail'),
    ('/default_spec/infill/pattern/0/top_engagement', 'Board seating in top rail'),
    ('/default_spec/infill/pattern/0/joint/channel_depth', 'Board groove receiving depth'),
    ('/post/joint/channel_depth', 'Post receiving depth for a rail end'),
)


def publication_slice(parts, facts):
    expected_ids = {reading[0] for reading in PART_READINGS}
    published = [part for part in parts if part['id'] in expected_ids]
    published_ids = {part['id'] for part in published}
    facts_by_type = {fact['fact_type']: fact for fact in facts}
    withheld = []
    for part_id, _, name, fact_types in PART_READINGS:
        if part_id in published_ids:
            continue
        rejected = [kind for kind in fact_types
                    if facts_by_type.get(kind, {}).get('review_status') == 'rejected']
        missing = [kind for kind in fact_types if kind not in facts_by_type]
        withheld.append({'id': part_id, 'name': name,
                         'rejected_readings': rejected, 'missing_readings': missing})
    return {'published_exact_parts': published,
            'published_exact_part_count': len(published),
            'withheld_exact_parts': withheld,
            'withheld_exact_part_count': len(withheld)}


def report(conn, package, candidate, confirmation):
    # Check retained source bytes and candidate bindings before importing anything.
    baseline = audit(package, candidate, conn, confirmation)
    if (not all(s['matches'] for s in baseline['source_file_checks'])
            or not all(r['canonical_locus_matches'] for r in baseline['canonical_source_ref_checks'])
            or not baseline['candidate_reproduces_from_checked_inputs']):
        raise ValueError('Source bytes, canonical references or deterministic candidate binding failed.')
    imported = import_readings(conn)
    snapshot = build_snapshot(tenant='default', conn=conn, authored_records=[package])
    verify(snapshot)
    refs = [node for _, node in walk([package, snapshot['parts']]) if isinstance(node, dict)
            and set(node) == {'id', 'belongs_to'}]
    admission = admit_authored_models([package], parts=snapshot['parts'],
        source_docs=snapshot['source_docs'], source_refs=refs, reviews=[])
    fields = dict(walk(package['model_fragment']))
    geometry = [{'path': path, 'meaning': meaning,
                 'state': 'missing' if path not in fields else 'null' if fields[path] is None else 'present_requires_evidence_validation',
                 'value': fields.get(path)} for path, meaning in GEOMETRY]
    board = next((p for p in snapshot['parts'] if p['id'] == BOARD_ID), None)
    facts = [dict(r) for r in conn.execute('''SELECT fact_id, fact_type, element_id,
        value_original, reviewed_value, review_status, condition_basis
        FROM facts WHERE extractor=? ORDER BY fact_type''', (EXTRACTOR,))]
    return snapshot, {
        'target': 'Exact Emblem 73014714 publication, validated assembly and component BOM',
        'purchase_bom': 'Subsequent checkpoint; complete kit inventory required for package credits',
        'input_hashes': baseline['artifact_hashes'],
        'source_checks': baseline['source_file_checks'],
        'canonical_references_verified': len(baseline['canonical_source_ref_checks']),
        'import': imported, 'facts': facts, 'published_board': board,
        **publication_slice(snapshot['parts'], facts),
        'snapshot_id': snapshot['snapshot_id'], 'snapshot_verified': True,
        'full_model_admitted': any(m['id'] == package['model_fragment']['id'] for m in snapshot['models']),
        'assembly_validated': False,
        'publication_exclusions': admission['exclusions'],
        'publication_readiness': admission['readiness'],
        'required_geometry': geometry,
        'assembly_remaining': [
            'Installed board pitch/overlap and explicit end-fitting policy',
            'Source-supported receiving depths and engagements on each axis',
            'Rail-to-post engagements at each end and shared-post clearance',
            'Lossless public geometry/provenance mapping and consumer support',
            'Mapping public Part receipts to private generation definitions without treating opaque versions as sortable revisions',
            'Single-panel and multi-panel assembly with shared posts, consistent cuts and component counts',
        ],
        'lifecycle': {'storage': 'facts', 'review': 'fact_reviews',
            'replay': 'existing review export/import ledger',
            'publication': 'Part.spec + Provenance in the actual snapshot builder',
            'unified_claims_table': 'proposed, not implemented',
            'numerical_model_mapping': 'unresolved; Amendment 008 remains pending'},
        'limitations': ['Published nominal width is not executable board pitch.',
            'No human review is created by this command.',
            'This Part slice does not admit the full FenceModel or validate assembly.'],
    }


def markdown(result):
    rows = ['# Emblem publication and assembly checklist', '',
        'Target: exact white 6×8 model 73014714, including assembly and component BOM.', '',
        f"Verified snapshot: `{result['snapshot_id']}`.",
        f"Full model admitted: **{result['full_model_admitted']}**. Assembly validated: **{result['assembly_validated']}**.", '',
        '## Current Part publication', '',
        f"Published exact Parts: **{result['published_exact_part_count']}**. Withheld exact Parts: **{result['withheld_exact_part_count']}**.", '',
        '| Part | State | Detail |', '|---|---|---|']
    rows += [f"| `{part['id']}` | published | Current review projection |"
             for part in result['published_exact_parts']]
    for part in result['withheld_exact_parts']:
        reasons = []
        if part['rejected_readings']:
            reasons.append('Rejected readings: ' + ', '.join(part['rejected_readings']))
        if part['missing_readings']:
            reasons.append('Missing readings: ' + ', '.join(part['missing_readings']))
        rows.append(f"| `{part['id']}` | withheld | {'; '.join(reasons) or 'Absent from this snapshot'} |")
    rows += ['',
        'Board width remains nominal, separate from installed pitch. Cap dimensions remain nominal, separate from mating clearances.',
        'Readings remain unreviewed unless an existing human review says otherwise.', '',
        '## Geometry needed for verified fit calculations', '', '| Field | Meaning | State |', '|---|---|---|']
    rows += [f"| `{r['path']}` | {r['meaning']} | {r['state']} |" for r in result['required_geometry']]
    rows += ['', '## Complete executable model exclusions', '', '| Field | Reason |', '|---|---|']
    rows += [f"| `{i['path']}` | {i['code']}: {i['message']} |"
             for exclusion in result['publication_exclusions'] for i in exclusion['issues']]
    rows += ['', '## Assembly work remaining', '']
    rows += ['- ' + item for item in result['assembly_remaining']]
    rows += ['', 'Kit purchasing follows the component BOM; incomplete package contents cannot supply purchase credits.', '']
    return '\n'.join(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--objective', choices=('knowledge','assembly'), default='knowledge')
    parser.add_argument('--output', type=Path, default=ROOT / 'workspace/reports/emblem-workflow-progress.json')
    args = parser.parse_args()
    catalog = ROOT / 'workspace/catalog'
    package = json.loads((catalog / 'emblem-73014714-model-draft.json').read_text())
    candidate = json.loads((catalog / 'emblem-73014714-consumer-model.json').read_text())
    confirmation = json.loads((catalog / 'emblem-73014714-placement-confirmation.json').read_text())
    source = connect(read_only=not args.apply)
    conn = source
    try:
        if not args.apply:
            conn = sqlite3.connect(':memory:')
            conn.row_factory = sqlite3.Row
            source.backup(conn)
            conn.execute('PRAGMA foreign_keys=ON')
        snapshot, result = report(conn, package, candidate, confirmation)
        result['objective'] = args.objective
        result['knowledge_available'] = knowledge_ready(result)
        relations = []
        for relation in package['connection_evidence']:
            check = check_anchor(conn, relation['evidence_anchor'])
            if not all(check[k] for k in ('text_matches','source_matches','region_matches')):
                raise ValueError('Assembly reading no longer matches canonical source')
            relations.append({**relation, 'page': check['page']})
        card = make_card(result, relations)
        card_path = args.output.with_name(args.output.stem + '-knowledge.json')
        with open_write(card_path) as output:
            json.dump(card, output, indent=2, ensure_ascii=False)
            output.write('\n')
        source_paths = {s['content_hash']: str((ROOT/s['path']).resolve()) for s in package['sources']}
        with open_write(card_path.with_suffix('.md')) as output:
            output.write(render_card(card, source_paths))
        result['knowledge_document'] = str(card_path)
        result['applied_to_store'] = args.apply
        result['snapshot_path'] = str(put_snapshot(snapshot).relative_to(ROOT)) if args.apply else None
        with open_write(args.output) as output:
            json.dump(result, output, indent=2, ensure_ascii=False)
            output.write('\n')
        with open_write(args.output.with_suffix('.md')) as output:
            output.write(markdown(result))
        print(json.dumps({'report': str(args.output), 'applied': args.apply,
            'snapshot_verified': True, 'objective': args.objective,
            'knowledge_available': result['knowledge_available'], 'knowledge_document': str(card_path),
            'full_model_admitted': result['full_model_admitted'],
            'assembly_validated': result['assembly_validated']}))
        return completion_code(result, args.objective)
    finally:
        if conn is not source:
            conn.close()
        source.close()


if __name__ == '__main__':
    sys.exit(main())
