"""Scoped readings from NOA22-0217.05 drawing001 sheet4 (PDF page7).

AI-transcribed scan readings remain flagged. These are pre-built Emblem drawing
components, not verified replacements or geometry for SKU73014714.
"""
from fractions import Fraction
import json
import re
from .canonical import content_hash
from .emblem_claims import NAMESPACE, _check_review_projection
from .parameters import CURATION_LEVEL, _source_class
from .reviews import effective_fact_value
from .store import now

SOURCE_SHA='13041c76330a3e6c6fb27f73bab982b2cd71c89f6eea842f30c174a4831a2a0b'
EXTRACTOR='source-reading:emblem-noa22021705:v1'
PREFIX=NAMESPACE+'/emblem-noa22021705-'
ANCHORS={
    'style':('element-44a8582188-0000','PVC FENCE (PRE-BUILT PANEL STYLE)'),
    'model':('element-44a8582188-0001',"6'X8' EMBLEM PANEL"),
    'rail_width':('element-44a8582188-0011','225"'),
    'rail_dimensions':('element-44a8582188-0013','X 7,00°X94"'),
    'board':('element-44a8582188-0017','0.875°X6.00X61,5"'),
    'channel':('element-44a8582188-0044','99°X1,.34°S3.875"'),
}
# Interpretation verified against the source image, not corrected canonical OCR.
READINGS=(
    ('rail','drawing_width_mm','rail_width','2.25 in.'),
    ('rail','drawing_height_mm','rail_dimensions','7 in.'),
    ('rail','drawing_length_mm','rail_dimensions','94 in.'),
    ('board','drawing_thickness_mm','board','0.875 in.'),
    ('board','drawing_profile_width_mm','board','6 in.'),
    ('board','drawing_length_mm','board','61.5 in.'),
    ('end-channel','drawing_width_mm','channel','0.99 in.'),
    ('end-channel','drawing_depth_mm','channel','1.34 in.'),
    ('end-channel','drawing_length_mm','channel','53.875 in.'),
)


def checked_anchors(conn):
    anchors={}
    for key,(eid,expected) in ANCHORS.items():
        row=conn.execute('''SELECT e.*,v.sha256,d.doc_type,d.version_status,d.owner_tenant
            FROM elements e JOIN document_versions v ON e.version_id=v.version_id
            JOIN documents d ON e.document_id=d.document_id WHERE e.element_id=?''',(eid,)).fetchone()
        if row is None or row['sha256']!=SOURCE_SHA or row['ocr_text']!=expected or row['text_source']!='ocr' or row['owner_tenant'] is not None:
            raise ValueError('Changed drawing OCR/source anchor: '+eid)
        anchors[key]=row
    if len({(r['document_id'],r['version_id'],r['page_no']) for r in anchors.values()})!=1:
        raise ValueError('Drawing anchors must share the pinned page')
    return anchors


def expected_readings(anchors):
    for component,key,anchor,raw in READINGS:
        a=anchors[anchor]
        yield dict(document_id=a['document_id'],version_id=a['version_id'],page_no=a['page_no'],
            element_id=a['element_id'],fact_type=component.replace('-','_')+'_'+key,
            subject='Emblem pre-built drawing001 sheet4: '+component,
            value_original=raw,unit_original='in',conditions=json.dumps({
                'drawing':'001','sheet':'4 of 9','panel_style':'pre-built','family':'Emblem',
                'exact_sku':'unverified'},sort_keys=True),condition_basis='assumed',
            condition_basis_note='AI visual transcription of scanned dimensional label; canonical OCR is preserved. Scope is this drawing only; no ready-to-assemble SKU equivalence or installed pitch inferred.',
            evidence_text=a['ocr_text'],extractor=EXTRACTOR,ocr_derived=1)


def reading_rows(conn,anchors):
    for expected in expected_readings(anchors):
        rows=conn.execute('SELECT * FROM facts WHERE extractor=? AND fact_type=?',
            (EXTRACTOR,expected['fact_type'])).fetchall()
        if len(rows)>1 or (rows and any(rows[0][k]!=v for k,v in expected.items())):
            raise ValueError('Conflicting immutable drawing reading')
        yield expected,rows[0] if rows else None


def import_readings(conn):
    own=not conn.in_transaction
    conn.execute('BEGIN IMMEDIATE' if own else 'SAVEPOINT drawing_import')
    try:
        readings=list(reading_rows(conn,checked_anchors(conn)));result=[]
        for expected,row in readings:
            if row is not None:
                result.append({'fact_id':row['fact_id'],'inserted':False});continue
            values=dict(expected,review_status='flagged',created_at=now())
            cursor=conn.execute('INSERT INTO facts ('+','.join(values)+') VALUES ('+','.join('?' for _ in values)+')',tuple(values.values()))
            result.append({'fact_id':cursor.lastrowid,'inserted':True})
        conn.execute('COMMIT' if own else 'RELEASE SAVEPOINT drawing_import')
        return result
    except Exception:
        if own:conn.rollback()
        else:
            conn.execute('ROLLBACK TO SAVEPOINT drawing_import');conn.execute('RELEASE SAVEPOINT drawing_import')
        raise


def quantity(row):
    raw=effective_fact_value(row)
    match=re.fullmatch(r'(\d+(?:\.\d+)?)\s*in\.',raw or '')
    if not match:raise ValueError('Drawing dimension needs explicit decimal inches')
    amount=Fraction(match[1])*25400
    if amount<=0 or amount.denominator!=1:raise ValueError('Drawing dimension loses milli-mm precision')
    return {'amount_milli':int(amount),'unit':'mm','value_raw':[raw]}


def build_parts(conn,source_ref):
    if conn is None or not conn.execute('SELECT 1 FROM facts WHERE extractor=?',(EXTRACTOR,)).fetchone():return []
    anchors=checked_anchors(conn)
    facts={expected['fact_type']:row for expected,row in reading_rows(conn,anchors)}
    for row in facts.values():
        if row is not None:_check_review_projection(conn,row)
    parts=[]
    for component,kind in [('rail','rail'),('board','infill'),('end-channel','bar')]:
        specs=[]
        for member,key,anchor,_ in READINGS:
            if member!=component:continue
            row=facts[component.replace('-','_')+'_'+key]
            if row is None or row['review_status']=='rejected':continue
            cites=[source_ref(anchors[a]['element_id']) for a in (anchor,'style','model')]
            specs.append({'key':key,'agree':'==','value':quantity(row),'provenance':{
                'cites':cites,'source_class':_source_class(anchors[anchor]['doc_type']),
                'curation_level':CURATION_LEVEL.get(row['review_status'],0),
                'version_status':anchors[anchor]['version_status'] or 'unknown'}})
        if not specs:continue
        citations={json.dumps(c,sort_keys=True):c for spec in specs for c in spec['provenance']['cites']}
        part={'id':PREFIX+component,'type':{'namespace':'shared','key':kind},'status':'draft',
            'name_i18n':{'en':'Emblem '+component+' — NOA22-0217.05 pre-built drawing; exact SKU unverified'},
            'authorship':'third_party_authored','spec':specs,'cites':[citations[k] for k in sorted(citations)],
            'contributing_sources':[SOURCE_SHA]}
        part['version']='sha256:'+content_hash(part);parts.append(part)
    return parts
