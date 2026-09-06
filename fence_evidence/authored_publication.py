"""Connect authored-model preflight to the existing provenance and gap builder."""
from dataclasses import asdict

from .authored_models import admit_authored_models
from .refs import build_index
from .tenancy import TenantLeak, visible_to


def build_authored_models(builder, records, parts, *, reviews=(), model_validator=None):
    if not records:
        return []
    from .snapshot import SourceRef
    index = build_index(builder.conn)
    found = {}

    def register(node):
        if isinstance(node, dict):
            rid, sha = node.get('id'), node.get('belongs_to')
            if isinstance(rid, str) and isinstance(sha, str):
                locus = index.get(rid)
                if locus is not None and locus.sha256 == sha:
                    ref = None
                    if locus.element_ids:
                        for eid in locus.element_ids:
                            row = builder.conn.execute(
                                'SELECT d.owner_tenant FROM elements e JOIN documents d ON d.document_id=e.document_id WHERE e.element_id=?',
                                (eid,)).fetchone()
                            if row is not None and visible_to(row['owner_tenant'], builder.tenant):
                                ref = builder.source_ref(eid)
                                break
                        if ref is None:
                            raise TenantLeak('Authored source reference has no visible filing for this tenant.')
                    elif locus.is_page:
                        rows = builder.conn.execute(
                            'SELECT d.document_id, d.owner_tenant FROM document_versions v JOIN documents d ON d.document_id=v.document_id WHERE v.sha256 = ? ORDER BY d.document_id',
                            (sha,)).fetchall()
                        for row in rows:
                            if visible_to(row['owner_tenant'], builder.tenant):
                                ref = builder.source_ref_page(row['document_id'], locus.page_no, content_hash=sha)
                                break
                        if ref is None and rows:
                            raise TenantLeak('Authored page reference has no visible filing for this tenant.')
                    if ref is not None and ref.id == rid and ref.belongs_to == sha:
                        found[(rid, sha)] = asdict(ref)
            for child in node.values():
                register(child)
        elif isinstance(node, list):
            for child in node:
                register(child)

    register(records)
    register(parts)
    result = admit_authored_models(
        records, parts=parts, source_docs=[asdict(d) for d in builder.source_docs()],
        source_refs=list(found.values()), reviews=reviews, model_validator=model_validator)
    def evidence_for(mid):
        refs = {}
        def collect(node):
            if isinstance(node, dict):
                pair = node.get('id'), node.get('belongs_to')
                if all(isinstance(v, str) for v in pair) and pair in found:
                    refs[pair] = found[pair]
                for child in node.values():
                    collect(child)
            elif isinstance(node, list):
                for child in node:
                    collect(child)
        for record in records:
            if not isinstance(record, dict):
                continue
            model = record.get('model', record.get('model_fragment', {}))
            if isinstance(model, dict) and model.get('id') == mid:
                collect(model)
                collect(record.get('field_evidence', {}))
        return [refs[k] for k in sorted(refs)]

    groups = {}
    for index, exclusion in enumerate(result['exclusions']):
        mid = exclusion['model_id']
        identity = mid if isinstance(mid, str) and mid else f'authored-record-{index}'
        for planning in (False, True):
            issues = [i for i in exclusion['issues']
                      if i['code'].startswith('consumer_') == planning]
            if not issues:
                continue
            group = groups.setdefault((identity, planning), {'issues': [], 'cites': evidence_for(mid),
                                                            'would_close': exclusion['would_close']})
            group['issues'].extend(issues)
    for (identity, planning), group in sorted(groups.items()):
        issues = group['issues']
        subject = {'kind': 'model', 'id': identity, 'tenant': builder.tenant}
        builder.gap(
                kind='unmodellable_entity' if planning else 'missing_value', subject=subject,
                code='authored_model_consumer_unavailable' if planning else 'authored_model_not_admitted',
                params={'paths': sorted({i['path'] for i in issues}),
                        'reasons': sorted({i['code'] for i in issues})},
                cites=[SourceRef(**c) for c in group['cites']],
                would_close=('Implement a lossless consumer adapter and validate this model with its exact Part library.'
                             if planning else group['would_close']),
                closes_by='planning' if planning else 'knowledge', severity='warns_line')
    return result['models']
