"""Scoped readings for the Weatherables Augusta privacy panel.

Four bounded sources, all retained and hash-pinned:

* the Augusta 8x6 privacy CAD raster (single page, image OCR): rail callout
  dimensions, overall panel labels, picket-run segments and the U-Channels
  component label;
* the 2024 master installation instructions and the privacy specsheet (text
  layers): the 1.5in U-channel statement and the Augusta picket style block;
* the manufacturer's Augusta 8ft master CAD web page (retained HTML): the
  8x6 panel's own material list — per-configuration kit quantities and
  component dimensions stated by the manufacturer, including the metal rail
  inserts, the U-channel length, the picket stock length and the picket
  count. The list's U-channel length exactly closes against the drawing's
  section chain ((95.5 - 3*5.5)/2 = 39.5), the picket length exceeds the
  39.5in run (implied seating, config-dependent), and the panel kit lists
  no posts — posts are separately purchased.

AI-transcribed CAD readings remain flagged; text-layer and HTML readings are
extracted. Kit quantities are the manufacturer's per-panel KIT inventory
statement, not installed-geometry claims: a stock length is not a cut length
until receiving geometry and fitting are validated. Overall panel dimensions
and picket-run segments are persisted as facts but deliberately not projected
onto a component Part: no component owns overall panel geometry while
FenceModel provenance mapping (Amendment 008) remains pending.
"""
from fractions import Fraction
import json
import re
from .canonical import part_version
from .emblem_claims import _check_review_projection
from .parameters import CURATION_LEVEL, _source_class
from .reviews import effective_fact_value
from .store import now

NAMESPACE = 'mfr/weatherables'
CAD_SHA = '88612b32b98d57e504ddaa3fa53873712ad490d471e2d1da8311893a148d022d'
CAD_EXTRACTOR = 'source-reading:weatherables-augusta-8x6-cad:v1'
PREFIX = NAMESPACE + '/augusta-8x6-'

# Canonical OCR anchors on the single-page CAD PNG. OCR text is preserved
# verbatim; the interpretation of each label is recorded separately and was
# cross-checked against the sibling 8x8/gate CADs, the master installation
# guide, and the specsheet/brochure text layers (run log records the checks).
CAD_ANCHORS = {
    'overall_width': ('element-1b110be294-0000', '12"'),
    'rail_callout_top': ('element-1b110be294-0001', '5\'x 5.5" x 71.5"'),
    'section_upper': ('element-1b110be294-0005', '39.5"'),
    'overall_height': ('element-1b110be294-0006', '95.5"'),
    'u_channels': ('element-1b110be294-0017', 'U-Channels'),
    'section_lower': ('element-1b110be294-0018', '39.5"'),
    'rail_callout_bottom': ('element-1b110be294-0020', '15x55" x 715"'),
}
# component, fact_type, anchor, raw value. Overall and run-segment readings
# are persisted for a future model batch; rail dimensions publish onto the
# rail Part. The U-channel width lives with the install-guide reading below.
CAD_READINGS = (
    ('panel', 'panel_drawing_overall_width_in', 'overall_width', '72 in.'),
    ('panel', 'panel_drawing_overall_height_in', 'overall_height', '95.5 in.'),
    ('panel', 'panel_drawing_picket_run_upper_in', 'section_upper', '39.5 in.'),
    ('panel', 'panel_drawing_picket_run_lower_in', 'section_lower', '39.5 in.'),
    ('rail', 'rail_drawing_width_in', 'rail_callout_top', '1.5 in.'),
    ('rail', 'rail_drawing_height_in', 'rail_callout_top', '5.5 in.'),
    ('rail', 'rail_drawing_length_in', 'rail_callout_top', '71.5 in.'),
)

INSTALL_SHA = 'db02aeeed4ebbf704032d7775112a73fe68d01a74a3ab31bd8d516b8a2b1b20b'
# The U-channel reading is versioned. v1's u_channel_width_in asserted a
# measured axis the installation guide does not identify; v2 supersedes it
# with u_channel_designation_in. A v1 row is preserved wherever a store
# already holds one -- supersession, not cleanup -- and never publishes.
# v1 also wrote the designation identity itself during one uncommitted
# session before this version split, so both v1 shapes are recognized here
# as history. Publication reads v2 only.
LEGACY_INSTALL_EXTRACTOR = 'source-reading:weatherables-augusta-8x6-install:v1'
INSTALL_EXTRACTOR = 'source-reading:weatherables-augusta-8x6-install:v2'
# The 3-rail installation flow's U-channel callout. The statement is
# family-level ("the T&G picket") and names a "1.5in U-Channel" without
# identifying a measured axis; it is recorded and published as a nominal
# designation, not a width measurement. The CAD's own 'U-Channels' label
# may be cited as this panel-configuration membership evidence only after
# it passes the same strict anchor validation as the CAD branch.
INSTALL_ANCHORS = {
    'u_channel_designation': ('element-bc63a76c40-0021', '1.5" U-Channel slides\non the T&G picket'),
}
INSTALL_READINGS = (
    ('u-channel', 'u_channel_designation_in', 'u_channel_designation', '1.5 in.'),
)

SPECSHEET_SHA = '87dea78b1ccfc7e7ff526d59b51a668132481323beca9129208de46084ad739c'
SPECSHEET_EXTRACTOR = 'source-reading:weatherables-augusta-specsheet:v1'
# The specsheet pairs 'The Augusta(TM)' with its spec block in the same table
# column on page 1 (matching bboxes); the brochure page 7 shows the identical
# pairing, so the applicability join is positional and twice-observed.
SPECSHEET_ANCHORS = {
    'augusta_name': ('element-478d468055-0020', 'The Augusta™'),
    'picket_spec': ('element-478d468055-0024',
                    'Height: 6’, 7’ & 8’\nWidth: 6’ & 8’\nPicket Style: 7/8” x 6”\nTongue & Groove .060”\nColor:'),
}
SPECSHEET_READINGS = (
    ('picket', 'picket_thickness_in', 'picket_spec', '7/8 in.', 7 / 8),
    ('picket', 'picket_width_in', 'picket_spec', '6 in.', 6.0),
)

# The manufacturer's 8ft master CAD page (retained HTML): the 8x6 panel's own
# material list. This is the kit INVENTORY statement — quantities and stock
# dimensions per configuration — anchored to the canonical table element.
# Cross-validated before trust: the U-channel length (39.5 in) exactly equals
# the drawing-derived picket-run height (95.5 - 3*5.5)/2, and the sibling 6ft
# list's 27.75 in equals its (72 - 3*5.5)/2 the same way; the panel kit lists
# no posts, matching the separately-purchased posts in the install guide.
CADPAGE_SHA = '5586a6d4ee7a97134faed86c4846addd43628b7ff87bd78c9ee359b6047ef9cb'
CADPAGE_EXTRACTOR = 'source-reading:weatherables-augusta-8ft-cadpage:v1'
CADPAGE_ANCHORS = {
    'panel_8x6_list': ('element-398603ee1a-0240',
        '\nITEM | QTY | DIMENSIONS\nTop & Bottom Rail | 2 | 1.5" x 5.5" x 71.5"\nMid Rail | 1 | 1.5" x 5.5" x 71.5"\nMetal | 3 | 1.25" x 1.75" x 71.5"\nU-Channel | 4 | 1.25" x 1.5" x 39.5"\nT&G Pickets | 22 | 0.875" x 6" x 43"'),
    'panel_8x6_heading': ('element-398603ee1a-0182', 'Material List - 8x6 Panel'),
}
# component, fact_type, anchor, raw, normalized. Quantities are whole counts;
# dimensions are manufacturer-stated stock sizes for this configuration.
CADPAGE_READINGS = (
    ('rail-kit', 'kit_qty_rails', 'panel_8x6_list', '3 each', 3),
    ('metal-insert', 'kit_qty_metal_inserts', 'panel_8x6_list', '3 each', 3),
    ('metal-insert', 'metal_insert_width_in', 'panel_8x6_list', '1.25 in.', 1.25),
    ('metal-insert', 'metal_insert_height_in', 'panel_8x6_list', '1.75 in.', 1.75),
    ('metal-insert', 'metal_insert_length_in', 'panel_8x6_list', '71.5 in.', 71.5),
    ('u-channel', 'kit_qty_u_channels', 'panel_8x6_list', '4 each', 4),
    ('u-channel', 'u_channel_width_in', 'panel_8x6_list', '1.25 in.', 1.25),
    ('u-channel', 'u_channel_depth_in', 'panel_8x6_list', '1.5 in.', 1.5),
    ('u-channel', 'u_channel_length_in', 'panel_8x6_list', '39.5 in.', 39.5),
    ('picket', 'kit_qty_pickets', 'panel_8x6_list', '22 each', 22),
    ('picket', 'picket_stock_length_in', 'panel_8x6_list', '43 in.', 43.0),
)

CAD_CONDITIONS = {'drawing': 'augusta-8x6-privacy', 'family': 'Augusta',
                  'panel_style': 'three-rail privacy', 'exact_sku': 'unverified'}


def _anchor_rows(conn, anchors, sha, text_source):
    rows = {}
    for key, (eid, expected) in anchors.items():
        row = conn.execute('''SELECT e.*, v.sha256, d.doc_type, d.version_status, d.owner_tenant
            FROM elements e JOIN document_versions v ON e.version_id=v.version_id
            JOIN documents d ON e.document_id=d.document_id WHERE e.element_id=?''', (eid,)).fetchone()
        if row is None:
            raise ValueError('Changed source anchor (missing or moved element): ' + eid)
        text = row['ocr_text'] if text_source in ('image_ocr', 'ocr') else row['text']
        if (row['sha256'] != sha or text != expected
                or row['text_source'] != text_source or row['owner_tenant'] is not None):
            raise ValueError('Changed source anchor: ' + eid)
        rows[key] = row
    return rows


def _reading_rows(conn, extractor, expected_items, page_scope):
    expected_items = list(expected_items)
    for expected in expected_items:
        rows = conn.execute('SELECT * FROM facts WHERE extractor=? AND fact_type=?',
                            (extractor, expected['fact_type'])).fetchall()
        if len(rows) > 1 or (rows and any(rows[0][k] != v for k, v in expected.items())):
            raise ValueError('Conflicting immutable Augusta reading: ' + expected['fact_type'])
        yield expected, rows[0] if rows else None
    live = {r['fact_type'] for r in conn.execute('SELECT fact_type FROM facts WHERE extractor=?', (extractor,))}
    known = {e['fact_type'] for e in expected_items}
    if live - known:
        raise ValueError('Unknown persisted reading types: ' + ','.join(sorted(live - known)))


def _import(conn, reading_rows, status):
    own = not conn.in_transaction
    conn.execute('BEGIN IMMEDIATE' if own else 'SAVEPOINT augusta_import')
    try:
        result = []
        for expected, row in reading_rows:
            if row is not None:
                result.append({'fact_id': row['fact_id'], 'inserted': False})
                continue
            values = dict(expected, review_status=status, created_at=now())
            cursor = conn.execute('INSERT INTO facts (' + ','.join(values) + ') VALUES ('
                                  + ','.join('?' for _ in values) + ')', tuple(values.values()))
            result.append({'fact_id': cursor.lastrowid, 'inserted': True})
        conn.execute('COMMIT' if own else 'RELEASE SAVEPOINT augusta_import')
        return result
    except Exception:
        if own:
            conn.rollback()
        else:
            conn.execute('ROLLBACK TO SAVEPOINT augusta_import')
            conn.execute('RELEASE SAVEPOINT augusta_import')
        raise


def _cad_expected(anchors):
    for component, fact_type, anchor, raw in CAD_READINGS:
        a = anchors[anchor]
        yield dict(document_id=a['document_id'], version_id=a['version_id'], page_no=a['page_no'],
            element_id=a['element_id'], fact_type=fact_type,
            subject='Weatherables Augusta 8x6 CAD drawing: ' + component,
            value_original=raw, unit_original='in',
            conditions=json.dumps(CAD_CONDITIONS, sort_keys=True), condition_basis='assumed',
            condition_basis_note='AI visual transcription of CAD raster labels (mean OCR confidence 32.19); canonical OCR preserved verbatim. '
                'Interpretation cross-checked against sibling 8x8/gate CADs and the master installation guide. '
                'Scope is this drawing only; no installed pitch, cut allowance or exact-SKU equivalence inferred.',
            evidence_text=a['ocr_text'], extractor=CAD_EXTRACTOR, ocr_derived=1)


def import_cad_readings(conn):
    anchors = _anchor_rows(conn, CAD_ANCHORS, CAD_SHA, 'image_ocr')
    if len({(r['document_id'], r['version_id'], r['page_no']) for r in anchors.values()}) != 1:
        raise ValueError('CAD anchors must share the pinned page')
    return _import(conn, _reading_rows(conn, CAD_EXTRACTOR, _cad_expected(anchors), 'page'), 'flagged')


def _install_expected(anchors):
    for component, fact_type, anchor, raw in INSTALL_READINGS:
        a = anchors[anchor]
        yield dict(document_id=a['document_id'], version_id=a['version_id'], page_no=a['page_no'],
            element_id=a['element_id'], fact_type=fact_type,
            subject='Weatherables master installation instructions: ' + component,
            value_original=raw, unit_original='in',
            conditions=json.dumps({'family': 'Weatherables privacy panels', 'exact_sku': 'unverified',
                'supersedes': 'u_channel_width_in (v1 width interpretation; measured axis not identified by source)',
                'panel_membership_evidence': 'augusta-8x6-privacy CAD U-Channels label'}, sort_keys=True),
            condition_basis='assumed',
            condition_basis_note='Authored applicability: the 1.5in U-Channel statement is family-level text; the Augusta 8x6 CAD '
                'labels U-Channels as a component of this panel configuration. The statement names the component and a nominal 1.5in '
                'designation without identifying a measured axis; it is not a width, groove or receiving-depth measurement.',
            evidence_text=a['text'], extractor=INSTALL_EXTRACTOR, ocr_derived=0)


# The two shapes v1 actually wrote, preserved for supersession. Any other
# v1-prefixed fact type refuses: an unrecognized legacy shape is a conflict,
# not history to silently carry.
LEGACY_INSTALL_FACT_TYPES = frozenset({
    'u_channel_width_in',          # the superseded width interpretation
    'u_channel_designation_in',    # the designation identity, pre-version-split
})


def _legacy_install_rows(conn):
    """Superseded v1 rows are recognized, never imported, never published.

    Duplicate legacy rows refuse, matching the current extractor's own
    immutability check: history is preserved exactly once, not silently
    accumulated by a store that double-inserted during the v1 era.
    """
    rows = conn.execute('SELECT * FROM facts WHERE extractor=?', (LEGACY_INSTALL_EXTRACTOR,)).fetchall()
    unknown = {r['fact_type'] for r in rows} - LEGACY_INSTALL_FACT_TYPES
    if unknown:
        raise ValueError('Unknown legacy install reading types: ' + ','.join(sorted(unknown)))
    seen = set()
    for row in rows:
        if row['fact_type'] in seen:
            raise ValueError('Conflicting legacy install reading: ' + row['fact_type'])
        seen.add(row['fact_type'])
    return rows


def import_install_readings(conn):
    _legacy_install_rows(conn)
    anchors = _anchor_rows(conn, INSTALL_ANCHORS, INSTALL_SHA, 'pdf_text_layer')
    return _import(conn, _reading_rows(conn, INSTALL_EXTRACTOR, _install_expected(anchors), 'page'), 'extracted')


def _specsheet_expected(anchors):
    for component, fact_type, anchor, raw, normalized in SPECSHEET_READINGS:
        a = anchors[anchor]
        yield dict(document_id=a['document_id'], version_id=a['version_id'], page_no=a['page_no'],
            element_id=a['element_id'], fact_type=fact_type,
            subject='Weatherables Augusta specsheet picket: ' + fact_type,
            value_original=raw, value_normalized=normalized, unit_original='in', unit_normalized='in',
            conditions=json.dumps({'family': 'Augusta', 'style': 'privacy', 'exact_sku': 'unverified',
                'panel_configurations': '6ft-8ft tall, 6ft-8ft wide'}, sort_keys=True),
            condition_basis='assumed',
            condition_basis_note='Authored applicability: specsheet pairs The Augusta(TM) with the picket-style block in the same '
                'table column on page 1; the brochure page 7 repeats the identical pairing. Applies to the Augusta privacy family, not one exact SKU.',
            evidence_text=a['text'], extractor=SPECSHEET_EXTRACTOR, ocr_derived=0)


def import_specsheet_readings(conn):
    anchors = _anchor_rows(conn, SPECSHEET_ANCHORS, SPECSHEET_SHA, 'pdf_text_layer')
    if len({(r['document_id'], r['version_id'], r['page_no']) for r in anchors.values()}) != 1:
        raise ValueError('Specsheet anchors must share one page and edition')
    return _import(conn, _reading_rows(conn, SPECSHEET_EXTRACTOR, _specsheet_expected(anchors), 'page'), 'extracted')


def _cadpage_expected(anchors):
    for component, fact_type, anchor, raw, normalized in CADPAGE_READINGS:
        a = anchors[anchor]
        # `kit_qty_*` carries NO unit suffix (`naming.md` §2, B-2): a count
        # is not a quantity whose unit the name must declare, and the `_in`
        # it used to carry is a live dispatch key -- `facts._normalise`
        # branches on `endswith("_in")` and would multiply a picket count
        # by twelve. The unit is declared here, on the prefix, and nowhere
        # else.
        unit = 'each' if fact_type.startswith('kit_qty') else 'in'
        yield dict(document_id=a['document_id'], version_id=a['version_id'], page_no=a['page_no'],
            element_id=a['element_id'], fact_type=fact_type,
            subject='Weatherables Augusta 8ft CAD page material list (8x6 panel): ' + component,
            value_original=raw, value_normalized=normalized, unit_original=unit, unit_normalized=unit,
            conditions=json.dumps({'family': 'Augusta', 'panel_configuration': '8ft tall x 6ft wide',
                'list': 'Material List - 8x6 Panel', 'statement_kind': 'manufacturer_kit_inventory',
                'exact_sku': 'unverified'}, sort_keys=True),
            condition_basis='stated',
            condition_basis_note=('Manufacturer web page states the 8x6 panel kit material list with quantities and stock '
                'dimensions. Quantities are kit inventory, not installed geometry: the U-channel length 39.5in equals the '
                'drawing-derived picket-run height (95.5 - 3*5.5)/2 exactly (the 6ft list closes the same way at 27.75in), '
                'and the picket stock length 43in exceeds the 39.5in run — the 3.5in difference is implied seating, not a '
                'measured engagement. The panel kit lists no posts.'),
            evidence_text=a['text'], extractor=CADPAGE_EXTRACTOR, ocr_derived=0)


def import_cadpage_readings(conn):
    anchors = _anchor_rows(conn, CADPAGE_ANCHORS, CADPAGE_SHA, 'html_text')
    if anchors['panel_8x6_list']['document_id'] != anchors['panel_8x6_heading']['document_id']:
        raise ValueError('CAD page anchors must share the retained document')
    return _import(conn, _reading_rows(conn, CADPAGE_EXTRACTOR, _cadpage_expected(anchors), 'page'), 'extracted')


def quantity(row):
    raw = effective_fact_value(row)
    match = re.fullmatch(r'(\d+(?:\.\d+)?(?:/\d+)?)\s*in\.', raw or '')
    if not match:
        raise ValueError('Augusta dimension needs an explicit inch value')
    amount = Fraction(match[1]) * 25400
    if amount <= 0 or amount.denominator != 1:
        raise ValueError('Augusta dimension loses milli-mm precision')
    return {'amount_milli': int(amount), 'unit': 'mm', 'value_raw': [raw]}


def _spec(row, key, anchor_row, source_ref):
    return {'key': key, 'agree': '==', 'value': quantity(row), 'provenance': {
        'cites': [source_ref(anchor_row['element_id'])],
        'source_class': _source_class(anchor_row['doc_type']),
        'curation_level': CURATION_LEVEL.get(row['review_status'], 0),
        'version_status': anchor_row['version_status'] or 'unknown'}}


def _designation_token(row):
    """The U-channel's 1.5in as a nominal designation Token, not a width.

    The installation guide names a '1.5in U-Channel' without identifying a
    measured axis; publishing it as width_mm would assert an interpretation
    the source does not state. A Token preserves the designation and its raw
    lexeme without a dimensional claim.
    """
    raw = effective_fact_value(row)
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError('U-channel designation needs its original text')
    return {'key': 'designation', 'value_raw': [raw.strip()]}


def _part(part_id, kind, name, specs, cites, sources):
    part = {'id': part_id, 'type': {'namespace': 'shared', 'key': kind}, 'status': 'draft',
        'name_i18n': {'en': name}, 'authorship': 'third_party_authored', 'spec': specs,
        'cites': cites, 'contributing_sources': sources}
    part['version'] = part_version(part)
    return part


def _collect_cites(specs):
    unique = {json.dumps(c, sort_keys=True): c for spec in specs for c in spec['provenance']['cites']}
    return [unique[k] for k in sorted(unique)]


def _checked_facts(conn, extractor, expected):
    """Rows for an extractor with every present review projection verified.

    A rejected or missing row stays in the mapping; callers decide what a
    rejected or missing reading means for their Part. Verification happens
    before any filtering so a forged or stale projection cannot be silenced by
    rejection.
    """
    facts = {e['fact_type']: row for e, row in expected}
    for row in facts.values():
        if row is not None:
            _check_review_projection(conn, row)
    return facts


def _cad_membership_row(conn):
    """The CAD 'U-Channels' label, only when it independently passes the full
    anchor validation: pinned hash, verbatim OCR text, image-OCR extraction
    origin, unowned tenant, and the pinned Augusta 8x6 drawing page (scope).
    A label that moved, changed or fails validation cites nothing; the Part
    then publishes only the family-level designation the install guide alone
    supports. None means 'unvalidated, do not cite', never 'missing element'."""
    eid, expected = CAD_ANCHORS['u_channels']
    row = conn.execute('''SELECT e.*, v.sha256, d.doc_type, d.version_status, d.owner_tenant
        FROM elements e JOIN document_versions v ON e.version_id=v.version_id
        JOIN documents d ON e.document_id=d.document_id WHERE e.element_id=?''', (eid,)).fetchone()
    if (row is None or row['sha256'] != CAD_SHA or row['ocr_text'] != expected
            or row['text_source'] != 'image_ocr' or row['owner_tenant'] is not None):
        return None
    return row


def build_parts(conn, source_ref):
    """Publish only persisted readings, using current review projections."""
    if conn is None:
        return []
    parts = []
    cad = conn.execute('SELECT 1 FROM facts WHERE extractor=? LIMIT 1', (CAD_EXTRACTOR,)).fetchone()
    if cad:
        anchors = _anchor_rows(conn, CAD_ANCHORS, CAD_SHA, 'image_ocr')
        facts = _checked_facts(conn, CAD_EXTRACTOR,
            _reading_rows(conn, CAD_EXTRACTOR, _cad_expected(anchors), 'page'))
        specs = []
        rail_keys = {'rail_drawing_width_in': 'width_mm', 'rail_drawing_height_in': 'height_mm',
                     'rail_drawing_length_in': 'length_mm'}
        for component, fact_type, anchor, _ in CAD_READINGS:
            row = facts[fact_type]
            if row is None or row['review_status'] == 'rejected' or component != 'rail':
                continue
            specs.append(_spec(row, rail_keys[fact_type], anchors[anchor], source_ref))
        if specs:
            parts.append(_part(PREFIX + 'rail', 'rail',
                'Weatherables Augusta rail — 8x6 privacy CAD drawing rail; exact SKU unverified',
                specs, _collect_cites(specs), [CAD_SHA]))
    # A present v2 install reading publishes; superseded v1 rows are recognized
    # history and never reach publication.
    _legacy_install_rows(conn)
    install = conn.execute('SELECT 1 FROM facts WHERE extractor=? LIMIT 1', (INSTALL_EXTRACTOR,)).fetchone()
    if install:
        anchors = _anchor_rows(conn, INSTALL_ANCHORS, INSTALL_SHA, 'pdf_text_layer')
        facts = _checked_facts(conn, INSTALL_EXTRACTOR,
            _reading_rows(conn, INSTALL_EXTRACTOR, _install_expected(anchors), 'page'))
        specs = []
        for component, fact_type, anchor, _ in INSTALL_READINGS:
            row = facts[fact_type]
            if row is None or row['review_status'] == 'rejected':
                continue
            designation = _designation_token(row)
            # The install guide alone supports the family-level designation;
            # the validated CAD 'U-Channels' label adds this panel
            # configuration's membership evidence when it passes validation.
            cites = [source_ref(anchors[anchor]['element_id'])]
            membership = _cad_membership_row(conn)
            if membership is not None:
                cites.append(source_ref(membership['element_id']))
            specs.append({'key': 'nominal_designation', 'agree': '==', 'value': designation, 'provenance': {
                'cites': cites, 'source_class': _source_class(anchors[anchor]['doc_type']),
                'curation_level': CURATION_LEVEL.get(row['review_status'], 0),
                'version_status': anchors[anchor]['version_status'] or 'unknown'}})
        if specs:
            name = ('Weatherables Augusta U-channel — nominal designation and CAD panel membership; exact SKU unverified'
                    if any(len(s['provenance']['cites']) > 1 for s in specs)
                    else 'Weatherables U-channel — nominal designation from master installation instructions (family level); exact SKU unverified')
            parts.append(_part(PREFIX + 'u-channel', 'bar', name, specs, _collect_cites(specs),
                sorted({c['belongs_to'] for s in specs for c in s['provenance']['cites']})))
    specsheet = conn.execute('SELECT 1 FROM facts WHERE extractor=? LIMIT 1', (SPECSHEET_EXTRACTOR,)).fetchone()
    if specsheet:
        anchors = _anchor_rows(conn, SPECSHEET_ANCHORS, SPECSHEET_SHA, 'pdf_text_layer')
        facts = _checked_facts(conn, SPECSHEET_EXTRACTOR,
            _reading_rows(conn, SPECSHEET_EXTRACTOR, _specsheet_expected(anchors), 'page'))
        specs = []
        keys = {'picket_thickness_in': 'nominal_thickness_mm', 'picket_width_in': 'nominal_width_mm'}
        for component, fact_type, anchor, _raw, _n in SPECSHEET_READINGS:
            row = facts[fact_type]
            if row is None or row['review_status'] == 'rejected':
                continue
            specs.append(_spec(row, keys[fact_type], anchors[anchor], source_ref))
        if specs:
            parts.append(_part(PREFIX + 'picket', 'infill',
                'Weatherables Augusta tongue-and-groove picket — specsheet style block; exact SKU unverified',
                specs, _collect_cites(specs), [SPECSHEET_SHA]))
    cadpage = conn.execute('SELECT 1 FROM facts WHERE extractor=? LIMIT 1', (CADPAGE_EXTRACTOR,)).fetchone()
    if cadpage:
        anchors = _anchor_rows(conn, CADPAGE_ANCHORS, CADPAGE_SHA, 'html_text')
        facts = _checked_facts(conn, CADPAGE_EXTRACTOR,
            _reading_rows(conn, CADPAGE_EXTRACTOR, _cadpage_expected(anchors), 'page'))
        # Kit inventory and stock dimensions publish as manufacturer-stated
        # values for THIS configuration; counts are Tokens, lengths are
        # Quantities, and none of it is installed geometry.
        def kit_count_spec(row, key, anchor_row):
            raw = effective_fact_value(row)
            return {'key': key, 'agree': '==',
                'value': {'key': 'count', 'value_raw': [raw]},
                'provenance': {'cites': [source_ref(anchor_row['element_id'])],
                    'source_class': _source_class(anchor_row['doc_type']),
                    'curation_level': CURATION_LEVEL.get(row['review_status'], 0),
                    'version_status': anchor_row['version_status'] or 'unknown'}}
        by_type = {}
        for component, fact_type, anchor, _raw, _n in CADPAGE_READINGS:
            row = facts[fact_type]
            if row is not None and row['review_status'] != 'rejected':
                by_type[fact_type] = (component, row, anchors[anchor])
        # U-channel: manufacturer-stated profile + kit count (upgrades the
        # family-level designation Part with configuration-specific values).
        u_specs = []
        if 'u_channel_width_in' in by_type:
            component, row, anchor_row = by_type['u_channel_width_in']
            u_specs.append(_spec(row, 'width_mm', anchor_row, source_ref))
        if 'u_channel_depth_in' in by_type:
            component, row, anchor_row = by_type['u_channel_depth_in']
            u_specs.append(_spec(row, 'depth_mm', anchor_row, source_ref))
        if 'u_channel_length_in' in by_type:
            component, row, anchor_row = by_type['u_channel_length_in']
            u_specs.append(_spec(row, 'length_mm', anchor_row, source_ref))
        if 'kit_qty_u_channels' in by_type:
            component, row, anchor_row = by_type['kit_qty_u_channels']
            u_specs.append(kit_count_spec(row, 'kit_count_per_panel', anchor_row))
        if u_specs:
            parts = [p for p in parts if p['id'] != PREFIX + 'u-channel']
            parts.append(_part(PREFIX + 'u-channel', 'bar',
                'Weatherables Augusta U-channel — 8ft CAD page material list (8x6 panel); exact SKU unverified',
                u_specs, _collect_cites(u_specs), [CADPAGE_SHA]))
        # Metal insert: a component the earlier slices did not know existed.
        m_specs = []
        for fact_type, key in (('metal_insert_width_in', 'width_mm'),
                               ('metal_insert_height_in', 'height_mm'),
                               ('metal_insert_length_in', 'length_mm'),
                               ('kit_qty_metal_inserts', 'kit_count_per_panel')):
            if fact_type in by_type:
                component, row, anchor_row = by_type[fact_type]
                m_specs.append(kit_count_spec(row, key, anchor_row) if key == 'kit_count_per_panel'
                               else _spec(row, key, anchor_row, source_ref))
        if m_specs:
            parts.append(_part(PREFIX + 'metal-insert', 'reinforcement',
                'Weatherables Augusta metal rail insert — 8ft CAD page material list (8x6 panel); exact SKU unverified',
                m_specs, _collect_cites(m_specs), [CADPAGE_SHA]))
        # Picket: add stock length and kit count to the specsheet-based Part.
        p_add = []
        for fact_type, key in (('picket_stock_length_in', 'stock_length_mm'),
                               ('kit_qty_pickets', 'kit_count_per_panel')):
            if fact_type in by_type:
                component, row, anchor_row = by_type[fact_type]
                p_add.append(kit_count_spec(row, key, anchor_row) if key == 'kit_count_per_panel'
                             else _spec(row, key, anchor_row, source_ref))
        if p_add:
            picket = next((p for p in parts if p['id'] == PREFIX + 'picket'), None)
            if picket is not None:
                picket['spec'] = picket['spec'] + p_add
                picket['cites'] = _merge_cites(picket, p_add)
                picket['contributing_sources'] = sorted(set(picket['contributing_sources']) | {CADPAGE_SHA})
                picket['name_i18n'] = {'en': 'Weatherables Augusta tongue-and-groove picket — specsheet style and 8ft CAD page material list; exact SKU unverified'}
                picket['version'] = part_version(picket)
    return parts


def _merge_cites(picket, added_specs):
    merged = {json.dumps(c, sort_keys=True): c
              for spec in added_specs for c in spec['provenance']['cites']}
    for c in picket['cites']:
        merged[json.dumps(c, sort_keys=True)] = c
    return [merged[k] for k in sorted(merged)]