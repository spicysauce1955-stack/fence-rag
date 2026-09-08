"""Scoped readings for the Weatherables Pembroke 6x6 privacy panel.

Three bounded sources, all retained and hash-pinned:

* the manufacturer's Pembroke 6ft master CAD web page (retained HTML,
  `extract_html`/html_text origin): the 6x6 panel's own material list --
  per-configuration kit quantities and component dimensions stated by the
  manufacturer (2 rails, 1 bottom-rail metal insert, 2 U-channels,
  6 wide-board pickets). The list's U-channel length (61 in) closes exactly
  against the local CAD drawing's two-rail section chain (72 - 2*5.5 = 61,
  single picket run; the 6x8 list on the same page repeats 61 in for its own
  6 ft height); the picket stock length 64.25 in exceeds the 61 in run by an
  implied 3.25 in seating (config-dependent, not a measured engagement).
* the 2024 master installation instructions (text layer): the Solid Privacy
  two-rail flow names the bottom rail's aluminum insert and the family-level
  `1.5" U-Channel slides on the T&G picket` designation (p7, the two-rail
  flow matching this panel's configuration). Applicability note: that flow's
  diagram labels picture 7/8" x 6" pickets (the Premium family size), so no
  picket DIMENSION is taken from it — it supports only rail/U-channel
  membership and the designation Token.
* the privacy specsheet (text layer): the Classic style block pairs The
  Pembroke(TM) with `Picket Style: 7/8" x 11.3"` / `Tongue & Groove .055"`
  (p2), twice-observed positionally (the brochure p8 repeats the identical
  row order and values). The .055in tongue-and-groove wall gauge publishes
  with its verbatim leading-dot lexeme (the local quantity parser accepts
  the source's own form; the value is never rewritten as 0.055).

The local `pembroke 6ft privacy` CAD PNG raster is retained and hash-pinned
but its canonical OCR is unusable (2 garbled whole-image labels, mean conf
0): the drawing's labels (72 overall width, 72 overall height, 5.5/61/5.5
right-edge chain) were recovered only by diagnostic re-OCR at 16-24x upscale
plus glyph-pixel analysis, and close arithmetically against the material
list. Those readings are recorded in the coverage note as corroborating
evidence, deliberately NOT persisted as anchored facts: the canonical OCR
layer cannot support strict anchor validation, and no value publishes on it.

Text-layer and HTML readings publish as extracted. Kit quantities are the
manufacturer's per-panel KIT inventory statement, not installed-geometry
claims: a stock length is not a cut length until receiving geometry and
fitting are validated.
"""
from fractions import Fraction
import json
import re
from .canonical import content_hash
from .emblem_claims import _check_review_projection
from .parameters import CURATION_LEVEL, _source_class
from .reviews import effective_fact_value
from .store import now

NAMESPACE = 'mfr/weatherables'
PREFIX = NAMESPACE + '/pembroke-6x6-'

CADPAGE_SHA = '4b763b3c4761c02972e9685a1f8434920764dbb1b26a8911717ecc09b7f16606'
CADPAGE_EXTRACTOR = 'source-reading:weatherables-pembroke-6ft-cadpage:v1'
# The 6x6 panel's material list and its heading, anchored to canonical table
# and paragraph elements of the retained HTML page. Cross-validated before
# trust: the U-channel length (61 in) exactly equals the drawing-derived
# single-run height 72 - 2*5.5 (two-rail chain, one run), and the sibling
# 6x8 list repeats the same 61 in for its own 6 ft height; the panel lists
# name no posts, matching the separately-purchased posts in the install guide.
CADPAGE_ANCHORS = {
    'panel_6x6_list': ('element-77275b2b5b-0239',
        '\nITEM | QTY | DIMENSIONS\nTop Rail | 1 | 1.5" x 5.5" x 71.5"\nBottom Rail | 1 | 1.5" x 5.5" x 71.5"\n'
        'Metal | 1 | 1.25" x 1.75" x 71.5"\nU-Channel | 2 | 1.25" x 1.5" x 61"\nT&G Pickets | 6 | 0.875" x 11.3" x 64.25"'),
    'panel_6x6_heading': ('element-77275b2b5b-0182', 'Material List - 6x6 Panel'),
}
# component, fact_type, anchor, raw, normalized. Quantities are whole counts;
# dimensions are manufacturer-stated stock sizes for this configuration.
CADPAGE_READINGS = (
    ('rail-kit', 'kit_qty_rails_in', 'panel_6x6_list', '2 each', 2),
    ('metal-insert', 'kit_qty_metal_inserts_in', 'panel_6x6_list', '1 each', 1),
    ('metal-insert', 'metal_insert_width_in', 'panel_6x6_list', '1.25 in.', 1.25),
    ('metal-insert', 'metal_insert_height_in', 'panel_6x6_list', '1.75 in.', 1.75),
    ('metal-insert', 'metal_insert_length_in', 'panel_6x6_list', '71.5 in.', 71.5),
    ('u-channel', 'kit_qty_u_channels_in', 'panel_6x6_list', '2 each', 2),
    ('u-channel', 'u_channel_width_in', 'panel_6x6_list', '1.25 in.', 1.25),
    ('u-channel', 'u_channel_depth_in', 'panel_6x6_list', '1.5 in.', 1.5),
    ('u-channel', 'u_channel_length_in', 'panel_6x6_list', '61 in.', 61.0),
    ('picket', 'kit_qty_pickets_in', 'panel_6x6_list', '6 each', 6),
    ('picket', 'picket_stock_length_in', 'panel_6x6_list', '64.25 in.', 64.25),
    ('rail', 'rail_width_in', 'panel_6x6_list', '1.5 in.', 1.5),
    ('rail', 'rail_height_in', 'panel_6x6_list', '5.5 in.', 5.5),
    ('rail', 'rail_length_in', 'panel_6x6_list', '71.5 in.', 71.5),
)

INSTALL_SHA = 'db02aeeed4ebbf704032d7775112a73fe68d01a74a3ab31bd8d516b8a2b1b20b'
INSTALL_EXTRACTOR = 'source-reading:weatherables-pembroke-install:v1'
# The two-rail Solid Privacy flow's U-channel callout (p7) and the bottom-
# rail insert statement. Both are family-level text scoped to the two-rail
# solid privacy configuration; the 1.5in figure names a nominal designation
# without identifying a measured axis, exactly as in the Augusta recipe, and
# is recorded as a designation, never a width measurement. The flow's diagram
# labels picture 7/8in x 6in pickets (Premium size) — no Pembroke picket
# dimension is taken from this flow.
INSTALL_ANCHORS = {
    'u_channel_designation': ('element-0a581e02ec-0018', '1.5" U-channel slides\non the T&G picket'),
}
INSTALL_READINGS = (
    ('u-channel', 'u_channel_designation_in', 'u_channel_designation', '1.5 in.'),
)

SPECSHEET_SHA = '87dea78b1ccfc7e7ff526d59b51a668132481323beca9129208de46084ad739c'
SPECSHEET_EXTRACTOR = 'source-reading:weatherables-pembroke-specsheet:v1'
# The specsheet's Classic block (p2) pairs The Pembroke(TM) with the wide-board
# picket style block in the same table column (matching bboxes); the brochure p8
# repeats the identical row order and values, so the applicability join is
# positional and twice-observed.
SPECSHEET_ANCHORS = {
    'pembroke_spec': ('element-d3efcd2267-0015',
        'The Pembroke™ | The G | lenshire™ | The Tuscany™ | The D\n\n'
        'Height: 4’, 5’, 6’, 7’, 8’ | Height: | 5’, 6’, 7’, 8’ | Height: 6’, 7’, 8’ | Height:\n'
        'Width: 6’ & 8’ | Width: 6 | ’ & 8’ | Width: 6’ & 8’ | Width: 6\n'
        'Picket Style: 7/8” x 11.3” | Picket S | tyle: 7/8” x 11.3” | Picket Style: 7/8” x 11.3” | Picket S\n'
        'Tongue & Groove .055” | Tongue | & Groove .055” | Tongue & Groove .055” | Tongue\n'
        'Color: | Color: | (accents 3/4” round black | (accents\n'
        'aluminum) Color: | Color:\n'
        '59 lb1 | 61 lb1 | 59 lb1 | 66 lb1\n\n'
        'The Calgary™ | The G | ideon™\n\n'
        'Height: 6’, 7’, 8’ | Height: | 6’, 7’, 8’\n'
        'Width: 6’ & 8’ | Width: 6 | ’ & 8’\n'
        'Picket Style: 7/8” x 11.3” | Picket S | tyle: 7/8” x 11.3”\n'
        'Tongue & Groove .055” | Tongue | & Groove .055”\n'
        '(accents 7/8” x 1.5”) | (accents | 1.25” x 1.25”)'),
}
SPECSHEET_READINGS = (
    ('picket', 'picket_thickness_in', 'pembroke_spec', '7/8 in.', 7 / 8),
    ('picket', 'picket_width_in', 'pembroke_spec', '11.3 in.', 11.3),
    ('picket', 'picket_tongue_groove_wall_gauge_in', 'pembroke_spec', '.055 in.', 0.055),
)

CADPAGE_CONDITIONS = {'family': 'Pembroke', 'panel_configuration': '6ft tall x 6ft wide',
                      'list': 'Material List - 6x6 Panel', 'statement_kind': 'manufacturer_kit_inventory',
                      'exact_sku': 'unverified'}


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
            raise ValueError('Conflicting immutable Pembroke reading: ' + expected['fact_type'])
        yield expected, rows[0] if rows else None
    live = {r['fact_type'] for r in conn.execute('SELECT fact_type FROM facts WHERE extractor=?', (extractor,))}
    known = {e['fact_type'] for e in expected_items}
    if live - known:
        raise ValueError('Unknown persisted reading types: ' + ','.join(sorted(live - known)))


def _import(conn, reading_rows, status):
    own = not conn.in_transaction
    conn.execute('BEGIN IMMEDIATE' if own else 'SAVEPOINT pembroke_import')
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
        conn.execute('COMMIT' if own else 'RELEASE SAVEPOINT pembroke_import')
        return result
    except Exception:
        if own:
            conn.rollback()
        else:
            conn.execute('ROLLBACK TO SAVEPOINT pembroke_import')
            conn.execute('RELEASE SAVEPOINT pembroke_import')
        raise


def _cadpage_expected(anchors):
    for component, fact_type, anchor, raw, normalized in CADPAGE_READINGS:
        a = anchors[anchor]
        unit = 'each' if fact_type.startswith('kit_qty') else 'in'
        yield dict(document_id=a['document_id'], version_id=a['version_id'], page_no=a['page_no'],
            element_id=a['element_id'], fact_type=fact_type,
            subject='Weatherables Pembroke 6ft CAD page material list (6x6 panel): ' + component,
            value_original=raw, value_normalized=normalized, unit_original=unit, unit_normalized=unit,
            conditions=json.dumps(CADPAGE_CONDITIONS, sort_keys=True),
            condition_basis='stated',
            condition_basis_note=('Manufacturer web page states the 6x6 panel kit material list with quantities and '
                'stock dimensions. Quantities are kit inventory, not installed geometry: the U-channel length 61in '
                'exactly equals the drawing-derived single picket-run height 72 - 2*5.5 (two-rail panel, one run; '
                'the sibling 6x8 list repeats 61in for its own 6ft height), and the picket stock length 64.25in '
                'exceeds the 61in run — the 3.25in difference is implied seating, not a measured engagement. '
                'The panel kit lists no posts.'),
            evidence_text=a['text'], extractor=CADPAGE_EXTRACTOR, ocr_derived=0)


def import_cadpage_readings(conn):
    anchors = _anchor_rows(conn, CADPAGE_ANCHORS, CADPAGE_SHA, 'html_text')
    if anchors['panel_6x6_list']['document_id'] != anchors['panel_6x6_heading']['document_id']:
        raise ValueError('CAD page anchors must share the retained document')
    return _import(conn, _reading_rows(conn, CADPAGE_EXTRACTOR, _cadpage_expected(anchors), 'page'), 'extracted')


def _install_expected(anchors):
    for component, fact_type, anchor, raw in INSTALL_READINGS:
        a = anchors[anchor]
        yield dict(document_id=a['document_id'], version_id=a['version_id'], page_no=a['page_no'],
            element_id=a['element_id'], fact_type=fact_type,
            subject='Weatherables master installation instructions (Solid Privacy two-rail flow): ' + component,
            value_original=raw, unit_original='in',
            conditions=json.dumps({'family': 'Weatherables two-rail solid privacy panels', 'exact_sku': 'unverified',
                'panel_configuration_evidence': 'pembroke 6x6 material list (two rails, one run, U-channel 2)',
                'flow': 'Solid Privacy, page 7'}, sort_keys=True),
            condition_basis='assumed',
            condition_basis_note='Authored applicability: the 1.5in U-Channel statement is family-level text in the '
                'two-rail Solid Privacy flow; the Pembroke 6x6 material list shows exactly that configuration '
                '(2 rails, 1 run, 2 u-channels). The statement names the component and a nominal 1.5in designation '
                'without identifying a measured axis; it is not a width, groove or receiving-depth measurement.',
            evidence_text=a['text'], extractor=INSTALL_EXTRACTOR, ocr_derived=0)


def import_install_readings(conn):
    anchors = _anchor_rows(conn, INSTALL_ANCHORS, INSTALL_SHA, 'pdf_text_layer')
    return _import(conn, _reading_rows(conn, INSTALL_EXTRACTOR, _install_expected(anchors), 'page'), 'extracted')


def _specsheet_expected(anchors):
    for component, fact_type, anchor, raw, normalized in SPECSHEET_READINGS:
        a = anchors[anchor]
        yield dict(document_id=a['document_id'], version_id=a['version_id'], page_no=a['page_no'],
            element_id=a['element_id'], fact_type=fact_type,
            subject='Weatherables Pembroke specsheet Classic block: ' + fact_type,
            value_original=raw, value_normalized=normalized, unit_original='in', unit_normalized='in',
            conditions=json.dumps({'family': 'Pembroke', 'style': 'Classic wide-board privacy', 'exact_sku': 'unverified',
                'panel_configurations': '4ft-8ft tall, 6ft-8ft wide'}, sort_keys=True),
            condition_basis='assumed',
            condition_basis_note='Authored applicability: the specsheet Classic block (p2) pairs The Pembroke(TM) '
                'with the 7/8in x 11.3in wide-board picket style; the brochure p8 repeats the identical row order '
                'and values, so the pairing is twice-observed. Applies to the Pembroke privacy family, not one exact SKU.',
            evidence_text=a['text'], extractor=SPECSHEET_EXTRACTOR, ocr_derived=0)


def import_specsheet_readings(conn):
    anchors = _anchor_rows(conn, SPECSHEET_ANCHORS, SPECSHEET_SHA, 'pdf_text_layer')
    if len({(r['document_id'], r['version_id'], r['page_no']) for r in anchors.values()}) != 1:
        raise ValueError('Specsheet anchors must share one page and edition')
    return _import(conn, _reading_rows(conn, SPECSHEET_EXTRACTOR, _specsheet_expected(anchors), 'page'), 'extracted')


def quantity(row):
    raw = effective_fact_value(row)
    # The specsheet writes the gauge without a leading zero ('.055”'); the
    # pattern accepts that verbatim form so the published value_raw can stay
    # faithful to the source instead of being "corrected" to 0.055.
    match = re.fullmatch(r'(\d*\.?\d+(?:/\d+)?)\s*in\.', raw or '')
    if not match:
        raise ValueError('Pembroke dimension needs an explicit inch value')
    amount = Fraction(match[1]) * 25400
    if amount <= 0 or amount.denominator != 1:
        raise ValueError('Pembroke dimension loses milli-mm precision')
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
    part['version'] = 'sha256:' + content_hash(part)
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


def build_parts(conn, source_ref):
    """Publish only persisted readings, using current review projections."""
    if conn is None:
        return []
    parts = []
    # Kit inventory and stock dimensions publish as manufacturer-stated values
    # for THIS configuration; counts are Tokens, lengths are Quantities, and
    # none of it is installed geometry.
    cadpage = conn.execute('SELECT 1 FROM facts WHERE extractor=? LIMIT 1', (CADPAGE_EXTRACTOR,)).fetchone()
    if cadpage:
        anchors = _anchor_rows(conn, CADPAGE_ANCHORS, CADPAGE_SHA, 'html_text')
        facts = _checked_facts(conn, CADPAGE_EXTRACTOR,
            _reading_rows(conn, CADPAGE_EXTRACTOR, _cadpage_expected(anchors), 'page'))

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
        # Rail: the material list is this panel's own dimension source (the
        # CAD PNG's canonical OCR cannot anchor its rail callout).
        r_specs = []
        for fact_type, key in (('rail_width_in', 'width_mm'),
                               ('rail_height_in', 'height_mm'),
                               ('rail_length_in', 'length_mm'),
                               ('kit_qty_rails_in', 'kit_count_per_panel')):
            if fact_type in by_type:
                component, row, anchor_row = by_type[fact_type]
                r_specs.append(kit_count_spec(row, key, anchor_row) if key == 'kit_count_per_panel'
                               else _spec(row, key, anchor_row, source_ref))
        if r_specs:
            parts.append(_part(PREFIX + 'rail', 'rail',
                'Weatherables Pembroke rail — 6ft CAD page material list (6x6 panel); exact SKU unverified',
                r_specs, _collect_cites(r_specs), [CADPAGE_SHA]))
        # U-channel: manufacturer-stated profile + kit count, upgraded with the
        # family-level designation when that reading is present and accepted.
        u_specs = []
        for fact_type, key in (('u_channel_width_in', 'width_mm'),
                               ('u_channel_depth_in', 'depth_mm'),
                               ('u_channel_length_in', 'length_mm'),
                               ('kit_qty_u_channels_in', 'kit_count_per_panel')):
            if fact_type in by_type:
                component, row, anchor_row = by_type[fact_type]
                u_specs.append(kit_count_spec(row, key, anchor_row) if key == 'kit_count_per_panel'
                               else _spec(row, key, anchor_row, source_ref))
        if u_specs:
            parts.append(_part(PREFIX + 'u-channel', 'bar',
                'Weatherables Pembroke U-channel — 6ft CAD page material list (6x6 panel); exact SKU unverified',
                u_specs, _collect_cites(u_specs), [CADPAGE_SHA]))
        # Metal insert: bottom-rail reinforcement for the two-rail panel.
        m_specs = []
        for fact_type, key in (('metal_insert_width_in', 'width_mm'),
                               ('metal_insert_height_in', 'height_mm'),
                               ('metal_insert_length_in', 'length_mm'),
                               ('kit_qty_metal_inserts_in', 'kit_count_per_panel')):
            if fact_type in by_type:
                component, row, anchor_row = by_type[fact_type]
                m_specs.append(kit_count_spec(row, key, anchor_row) if key == 'kit_count_per_panel'
                               else _spec(row, key, anchor_row, source_ref))
        if m_specs:
            parts.append(_part(PREFIX + 'metal-insert', 'reinforcement',
                'Weatherables Pembroke metal rail insert (bottom rail) — 6ft CAD page material list (6x6 panel); exact SKU unverified',
                m_specs, _collect_cites(m_specs), [CADPAGE_SHA]))
        # Picket: specsheet style values + stock length and kit count.
        specsheet = conn.execute('SELECT 1 FROM facts WHERE extractor=? LIMIT 1', (SPECSHEET_EXTRACTOR,)).fetchone()
        p_specs = []
        if specsheet:
            s_anchors = _anchor_rows(conn, SPECSHEET_ANCHORS, SPECSHEET_SHA, 'pdf_text_layer')
            s_facts = _checked_facts(conn, SPECSHEET_EXTRACTOR,
                _reading_rows(conn, SPECSHEET_EXTRACTOR, _specsheet_expected(s_anchors), 'page'))
            for component, fact_type, anchor, _raw, _n in SPECSHEET_READINGS:
                row = s_facts[fact_type]
                if row is None or row['review_status'] == 'rejected':
                    continue
                key = {'picket_thickness_in': 'nominal_thickness_mm',
                       'picket_width_in': 'nominal_width_mm',
                       'picket_tongue_groove_wall_gauge_in': 'tongue_groove_wall_gauge_mm'}[fact_type]
                p_specs.append(_spec(row, key, s_anchors[anchor], source_ref))
        for fact_type, key in (('picket_stock_length_in', 'stock_length_mm'),
                               ('kit_qty_pickets_in', 'kit_count_per_panel')):
            if fact_type in by_type:
                component, row, anchor_row = by_type[fact_type]
                p_specs.append(kit_count_spec(row, key, anchor_row) if key == 'kit_count_per_panel'
                               else _spec(row, key, anchor_row, source_ref))
        if p_specs:
            cites = _collect_cites(p_specs)
            sources = sorted({CADPAGE_SHA}
                              | ({SPECSHEET_SHA} if specsheet else set()))
            parts.append(_part(PREFIX + 'picket', 'infill',
                'Weatherables Pembroke wide-board tongue-and-groove picket — specsheet Classic block and 6ft CAD page material list; exact SKU unverified',
                p_specs, cites, sources))
    # The family-level U-channel designation publishes only as a Token Part
    # when the configuration-specific Part above is absent (the material
    # list is the stronger source; this fallback keeps the designation honest
    # if the list reading is ever rejected).
    install = conn.execute('SELECT 1 FROM facts WHERE extractor=? LIMIT 1', (INSTALL_EXTRACTOR,)).fetchone()
    has_u_channel_part = any(p['id'] == PREFIX + 'u-channel' for p in parts)
    if install and not has_u_channel_part:
        anchors = _anchor_rows(conn, INSTALL_ANCHORS, INSTALL_SHA, 'pdf_text_layer')
        facts = _checked_facts(conn, INSTALL_EXTRACTOR,
            _reading_rows(conn, INSTALL_EXTRACTOR, _install_expected(anchors), 'page'))
        specs = []
        for component, fact_type, anchor, _ in INSTALL_READINGS:
            row = facts[fact_type]
            if row is None or row['review_status'] == 'rejected':
                continue
            designation = _designation_token(row)
            specs.append({'key': 'nominal_designation', 'agree': '==', 'value': designation, 'provenance': {
                'cites': [source_ref(anchors[anchor]['element_id'])],
                'source_class': _source_class(anchors[anchor]['doc_type']),
                'curation_level': CURATION_LEVEL.get(row['review_status'], 0),
                'version_status': anchors[anchor]['version_status'] or 'unknown'}})
        if specs:
            parts.append(_part(PREFIX + 'u-channel', 'bar',
                'Weatherables U-channel — nominal designation from master installation instructions (two-rail Solid Privacy flow, family level); exact SKU unverified',
                specs, _collect_cites(specs),
                sorted({c['belongs_to'] for s in specs for c in s['provenance']['cites']})))
    return parts