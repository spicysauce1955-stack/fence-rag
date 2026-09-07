"""Bound Emblem readings in the existing facts and fact-review lifecycle.

The recipe is reproducible from retained canonical elements. It does not record
a human review or infer installed pitch from the manufacturer's nominal width.
"""
from fractions import Fraction
import json
import re

from .canonical import content_hash
from .parameters import CURATION_LEVEL, _source_class
from .reviews import (FACT_STATUS_FOR_VERDICT, effective_fact_value, fact_ref_id,
                      _normalise_corrected)
from .store import now


NAMESPACE = 'mfr/freedom-outdoor-living'
BOARD_ID = NAMESPACE + '/emblem-73014714-board'
SOURCE_SHA = 'e90a649e0b96895fbc80d438132d5738f10d9b14b1669eb776a61436758f3a23'
EXTRACTOR = 'source-reading:emblem-73014714:v1'
ANCHORS = {
    'title': ('element-b540e75926-0001', '6X8 EMBLEM - WHITE'),
    'board': ('element-b540e75926-0007', '• 6 in. tongue & groove boards'),
    'description': ('element-b540e75926-0016', '6x8 Emblem Privacy Fence Kit - White (F)'),
    'sku': ('element-b540e75926-0018', '73014714'),
    'rails': ('element-b540e75926-0008', '• 2-¼ in. x 7 in. top & bottom rails'),
    'cap': ('element-b540e75926-0051', '5in. x 5in. Contemporary Post Top - White'),
    'cap_sku': ('element-b540e75926-0052', '73013956'),
}
READINGS = (
    ('board', 'nominal_board_width_in', '6 in.', 'in', 6.0),
    ('description', 'component_colour', 'White', None, None),
    ('rails', 'rail_width_in', '2-¼ in.', 'in', 2.25),
    ('rails', 'rail_height_in', '7 in.', 'in', 7.0),
    ('cap', 'nominal_cap_width_in', '5in.', 'in', 5.0),
    ('cap', 'nominal_cap_depth_in', '5in.', 'in', 5.0),
    ('cap', 'cap_colour', 'White', None, None),
)
PART_READINGS = (
    (BOARD_ID, 'infill', 'Emblem 73014714 tongue-and-groove board',
     ('nominal_board_width_in', 'component_colour')),
    (NAMESPACE + '/emblem-73014714-rail-a', 'rail', 'Emblem 73014714 rail A (provisional identity)',
     ('rail_width_in', 'rail_height_in', 'component_colour')),
    (NAMESPACE + '/emblem-73014714-rail-b', 'rail', 'Emblem 73014714 rail B (provisional identity)',
     ('rail_width_in', 'rail_height_in', 'component_colour')),
    (NAMESPACE + '/73013956', 'post_cap', 'White contemporary post top',
     ('nominal_cap_width_in', 'nominal_cap_depth_in', 'cap_colour')),
)


def checked_anchors(conn):
    """Require the pinned source and exact scoped readings; never search siblings."""
    anchors = {}
    for key, (element_id, expected) in ANCHORS.items():
        row = conn.execute('''SELECT e.*, v.sha256, d.doc_type,
                d.version_status, d.owner_tenant
            FROM elements e JOIN document_versions v ON v.version_id=e.version_id
            JOIN documents d ON d.document_id=e.document_id
            WHERE e.element_id=?''', (element_id,)).fetchone()
        if row is None:
            raise ValueError('Missing canonical Emblem anchor: ' + element_id)
        if (row['sha256'] != SOURCE_SHA or row['text'] != expected
                or row['owner_tenant'] is not None or row['text_source'] in ('ocr', 'image_ocr')):
            raise ValueError('Changed source, text, ownership or extraction: ' + element_id)
        anchors[key] = row
    locations = {(r['document_id'], r['version_id'], r['page_no']) for r in anchors.values()}
    if len(locations) != 1:
        raise ValueError('Emblem applicability anchors must share one source page and edition.')
    return anchors


def _expected_fact(anchor, fact_type, raw, unit, normalized):
    return dict(document_id=anchor['document_id'], version_id=anchor['version_id'],
        page_no=anchor['page_no'], element_id=anchor['element_id'], fact_type=fact_type,
        subject='Emblem 73014714 project-sheet component: ' + fact_type,
        value_original=raw, value_normalized=normalized, unit_original=unit,
        unit_normalized=unit, conditions=json.dumps({'model_number': '73014714', 'colour': 'White'}, sort_keys=True),
        condition_basis='assumed',
        condition_basis_note='Authored applicability: pinned project-sheet title and product rows; board/cap sizes are nominal, not installed pitch or mating clearances.',
        evidence_text=anchor['text'], extractor=EXTRACTOR, ocr_derived=0)


def _reading_rows(conn, anchors):
    for key, fact_type, raw, unit, normalized in READINGS:
        expected = _expected_fact(anchors[key], fact_type, raw, unit, normalized)
        rows = conn.execute('SELECT * FROM facts WHERE extractor=? AND fact_type=?',
                            (EXTRACTOR, fact_type)).fetchall()
        if len(rows) > 1 or any(any(row[k] != v for k, v in expected.items()) for row in rows):
            raise ValueError('Conflicting immutable Emblem reading: ' + fact_type)
        yield expected, rows[0] if rows else None


def import_readings(conn):
    """Idempotent, atomic import; existing decisions and original readings survive."""
    started_here = not conn.in_transaction
    conn.execute('BEGIN IMMEDIATE' if started_here else 'SAVEPOINT emblem_reading_import')
    result = []
    try:
        anchors = checked_anchors(conn)
        readings = list(_reading_rows(conn, anchors))
        for expected, existing in readings:
            if existing is not None:
                result.append({'fact_id': existing['fact_id'], 'inserted': False})
                continue
            values = dict(expected, review_status='extracted', created_at=now())
            columns = ','.join(values)
            placeholders = ','.join('?' for _ in values)
            cur = conn.execute(f'INSERT INTO facts ({columns}) VALUES ({placeholders})', tuple(values.values()))
            result.append({'fact_id': cur.lastrowid, 'inserted': True})
        conn.execute('COMMIT' if started_here else 'RELEASE SAVEPOINT emblem_reading_import')
    except Exception:
        if started_here:
            conn.rollback()
        else:
            conn.execute('ROLLBACK TO SAVEPOINT emblem_reading_import')
            conn.execute('RELEASE SAVEPOINT emblem_reading_import')
        raise
    return result


def _check_review_projection(conn, fact):
    """A projection may neither invent a decision nor move its evidence region."""
    latest = conn.execute('SELECT * FROM fact_reviews WHERE fact_id=? ORDER BY rowid DESC LIMIT 1',
                          (fact['fact_id'],)).fetchone()
    annotations = ('reviewed_value', 'reviewed_value_normalized', 'reviewer', 'reviewed_at')
    if latest is None:
        if (fact['review_status'] not in ('extracted', 'flagged')
                or any(fact[key] is not None for key in annotations)):
            raise ValueError('Emblem review projection has no supporting ledger record.')
        return
    if (any(latest[key] != fact[key] for key in ('document_id', 'page_no', 'element_id', 'fact_type'))
            or latest['value_before'] != fact['value_original']
            or latest['ref_id'] != fact_ref_id(conn, fact['fact_id'])
            or latest['verdict'] not in FACT_STATUS_FOR_VERDICT
            or not isinstance(latest['reviewer'], str) or not latest['reviewer'].strip()):
        raise ValueError('Emblem review ledger does not bind the current source reading.')
    corrected = latest['verdict'] == 'corrected'
    raw = latest['reviewed_value']
    if (corrected and (not isinstance(raw, str) or not raw.strip())) or (not corrected and raw is not None):
        raise ValueError('Emblem review ledger has an invalid corrected value.')
    expected = dict(review_status=FACT_STATUS_FOR_VERDICT[latest['verdict']],
        reviewed_value=raw, reviewer=latest['reviewer'], reviewed_at=latest['reviewed_at'],
        reviewed_value_normalized=_normalise_corrected(fact['fact_type'], raw) if corrected else None)
    if any(fact[key] != value for key, value in expected.items()):
        raise ValueError('Stale Emblem review projection; replay the authoritative review ledger.')


def _value(fact):
    raw = effective_fact_value(fact)
    if fact['fact_type'] in ('component_colour', 'cap_colour'):
        if not isinstance(raw, str) or raw.strip().casefold() != 'white':
            raise ValueError('Colour correction changes exact white-model applicability.')
        return 'colour', {'key': 'white', 'value_raw': [raw]}
    match = re.fullmatch(r'(\d+(?:\.\d+)?)(?:-([¼½¾]))?\s*(?:in\.?|inches|inch|\")', raw or '')
    if match is None:
        raise ValueError('Dimension needs an explicit inch value; correction requires re-authoring otherwise.')
    inches = Fraction(match[1]) + {None: Fraction(0), '¼': Fraction(1, 4),
                                  '½': Fraction(1, 2), '¾': Fraction(3, 4)}[match[2]]
    milli = inches * 25400
    if milli <= 0 or milli.denominator != 1:
        raise ValueError('Dimension must be positive and exactly representable in milli-mm.')
    key = {'nominal_board_width_in': 'nominal_width_mm', 'rail_width_in': 'width_mm',
           'rail_height_in': 'height_mm', 'nominal_cap_width_in': 'nominal_width_mm',
           'nominal_cap_depth_in': 'nominal_depth_mm'}[fact['fact_type']]
    return key, {'amount_milli': int(milli), 'unit': 'mm', 'value_raw': [raw]}


def build_emblem_parts(conn, source_ref):
    """Publish only persisted readings, using current review projections."""
    if conn is None or not conn.execute('SELECT 1 FROM facts WHERE extractor=? LIMIT 1', (EXTRACTOR,)).fetchone():
        return []
    anchors = checked_anchors(conn)
    readings = {expected['fact_type']: row for expected, row in _reading_rows(conn, anchors)}
    for row in readings.values():
        if row is not None:
            _check_review_projection(conn, row)
    identity_cites = [source_ref(anchors[key]['element_id']) for key in ('title', 'description', 'sku')]
    parts = []
    for pid, kind, name, fact_types in PART_READINGS:
        selected = [readings[t] for t in fact_types]
        if any(row is None or row['review_status'] == 'rejected' for row in selected):
            continue
        specs = []
        for row in selected:
            key, value = _value(row)
            cites = [source_ref(row['element_id'])]
            cites += [c for c in identity_cites if c not in cites]
            if kind == 'post_cap':
                cites.append(source_ref(anchors['cap_sku']['element_id']))
            anchor = next(a for a in anchors.values() if a['element_id'] == row['element_id'])
            specs.append({'key': key, 'agree': '==', 'value': value, 'provenance': {
                'cites': cites, 'source_class': _source_class(anchor['doc_type']),
                'curation_level': CURATION_LEVEL.get(row['review_status'], 0),
                'version_status': anchor['version_status'] or 'unknown'}})
        cites = {json.dumps(c, sort_keys=True): c for sf in specs for c in sf['provenance']['cites']}
        part = {'id': pid, 'status': 'draft',
            'type': {'namespace': 'shared', 'key': kind}, 'name_i18n': {'en': name},
            'spec': specs, 'authorship': 'third_party_authored',
            'cites': [cites[k] for k in sorted(cites)], 'contributing_sources': [SOURCE_SHA]}
        part['version'] = 'sha256:' + content_hash(part)
        parts.append(part)
    return parts


def build_board_parts(conn, source_ref):
    return [part for part in build_emblem_parts(conn, source_ref) if part['id'] == BOARD_ID]
