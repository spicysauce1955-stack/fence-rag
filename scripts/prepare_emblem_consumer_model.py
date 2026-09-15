"""Prepare an explicitly incomplete private Planning model for author review.

Run with Planning's Python environment. This does not publish a Snapshot or
apply private parser defaults as source facts. Rail placements require a bound
user confirmation. Exit 2 means the candidate remains incomplete, including when
it parses but semantic checks fail or the exact Part library is unavailable.
"""
import argparse
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
import json
import hashlib
import re
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fence_evidence.canonical import content_hash
from fence_evidence.paths import open_write


def unique_records(records, key):
    result = {}
    for record in records:
        value = record[key]
        if value in result:
            raise ValueError('Duplicate authored ' + key + ': ' + str(value))
        result[value] = record
    return result


def set_authored(node, key, value):
    if key in node and (type(node[key]) is not type(value) or node[key] != value):
        raise ValueError('Conflicting authored value: ' + key)
    node[key] = value


def check_rail_reading(quantity):
    raw = quantity.get('value_raw')
    if not isinstance(raw, list) or len(raw) != 1 or not isinstance(raw[0], str):
        raise ValueError('Rail dimension needs one original inch reading.')
    match = re.fullmatch(r'(\d+)(?:-([¼½¾]))?\s+in\.', raw[0])
    if not match:
        raise ValueError('Unsupported rail dimension reading; review its conversion explicitly.')
    inches = Decimal(match[1]) + {'¼': Decimal('.25'), '½': Decimal('.5'),
                                  '¾': Decimal('.75'), None: Decimal(0)}[match[2]]
    if (quantity.get('unit') != 'mm' or type(quantity.get('amount_milli')) is not int
            or quantity['amount_milli'] != inches * 25400):
        raise ValueError('Rail dimension contradicts its retained original inch reading.')


def author_assembly_rules(package, model):
    """State supported rules explicitly without filling missing fitting geometry."""
    relations = unique_records(package['connection_evidence'], 'relationship')
    bottom = relations['boards_into_bottom_rail']
    top = relations['top_rail_over_boards']
    if (bottom['targets'] != ['board', 'bottom_rail']
            or top['targets'] != ['top_rail', 'board']
            or not bottom['evidence_anchor']['cite'] or not top['evidence_anchor']['cite']):
        raise ValueError('Board length rule requires both cited rail connections.')
    infill = model['default_spec']['infill']
    if infill['orientation'] != 'vertical' or len(infill['pattern']) != 1:
        raise ValueError('Only the evidenced single-board repeat is supported.')
    board = infill['pattern'][0]
    expected_board = model['id'].replace('-emblem-73014714', '/emblem-73014714-board')
    if board['key'] != 'board' or board['requirement']['part_id'] != expected_board:
        raise ValueError('Board rule requires the exact authored Emblem board Part.')
    if board['base_ref'] != 'bottom_rail' or board['top_ref'] != 'top_rail':
        raise ValueError('Board references disagree with the cited assembly.')
    set_authored(board['requirement'], 'length_rule', 'between_frame')
    set_authored(board['requirement'], 'qty', 1)
    set_authored(infill, 'justification', 'start')
    evidence = [{'target': 'default_spec.infill.pattern.0.requirement',
                 'authorship': 'third_party_authored',
                 'derivation': 'One physical board per fitted repeat; cut length between rail faces plus separately evidenced seating at both ends.',
                 'anchors': [deepcopy(bottom['evidence_anchor']), deepcopy(top['evidence_anchor'])]},
                {'target': 'default_spec.infill.justification',
                 'authorship': 'third_party_authored',
                 'derivation': 'Author the local start axis at the first installed post to follow the instructed assembly direction; this axis convention is not a manufacturer coordinate datum.',
                 'anchors': [deepcopy(bottom['evidence_anchor'])]}]
    inventory = unique_records(package['packaged_assembly_inventory'], 'component_key')
    for slot in model['default_spec']['frame']:
        source = inventory[slot['key']]
        if type(source['quantity_each']) is not int or source['quantity_each'] != 1 or not source['evidence']['cite']:
            raise ValueError('Rail quantity requires its cited one-per-panel inventory.')
        set_authored(slot['requirement'], 'qty', 1)
        evidence.append({'target': 'default_spec.frame.' + slot['key'] + '.requirement.qty',
                         'authorship': 'third_party_authored',
                         'derivation': 'One of each named top and bottom rail per full panel.',
                         'anchors': [deepcopy(source['evidence'])]})
    caps = [r for r in package['purchase_quantity_rules'] if r['target'] == 'post_cap']
    if (len(caps) != 1 or caps[0]['model_id'] != model['id']
            or caps[0]['basis'] != 'unique_post_station'
            or type(caps[0]['quantity_per_basis']['amount_milli']) is not int
            or caps[0]['quantity_per_basis']['amount_milli'] != 1000
            or caps[0]['quantity_per_basis']['unit'] != 'each' or not caps[0]['evidence']):
        raise ValueError('Cap quantity requires the cited one-per-post-station rule.')
    set_authored(model['post']['cap'], 'qty', 1)
    evidence.append({'target': 'post.cap.qty', 'authorship': 'third_party_authored',
                     'derivation': caps[0]['derivation'], 'anchors': deepcopy(caps[0]['evidence'])})
    return {'field_evidence': evidence,
            'remaining_inputs': ['effective board pitch/overlap', 'end allowance and excess policy',
                                 'base/top engagement', 'receiving channel depths',
                                 'stock lengths and source-defined cut allowances'],
            'review_status': 'unreviewed_authored', 'physical_fit_verified': False}


def author_identity_parts(package, model):
    """Close board/cap identity references without promoting nominal fit geometry."""
    sources = unique_records(package['part_fragments'], 'id')
    anchors = unique_records(package['part_identity_anchors'], 'part_id')
    known_hashes = {source['content_hash'] for source in package['sources']}

    def checked_cite(value):
        if (not isinstance(value, dict) or set(value) != {'id', 'belongs_to'}
                or not isinstance(value['id'], str)
                or re.fullmatch(r'[0-9a-f]{16}', value['id']) is None
                or not isinstance(value['belongs_to'], str)
                or re.fullmatch(r'[0-9a-f]{64}', value['belongs_to']) is None
                or value['belongs_to'] not in known_hashes):
            raise ValueError('Identity citation must name a known package source with a valid SourceRef.')
        return value['belongs_to']

    def checked_anchor(value):
        if (not isinstance(value, dict) or not isinstance(value.get('text_raw'), str)
                or not value['text_raw'].strip() or not isinstance(value.get('element_id'), str)
                or not value['element_id']):
            raise ValueError('Identity anchor requires source text and an element ID.')
        return checked_cite(value.get('cite'))

    board_id = model['default_spec']['infill']['pattern'][0]['requirement']['part_id']
    cap_id = model['post']['cap']['part_id']
    parts, mappings = [], []
    for pid, expected in ((board_id, 'infill'), (cap_id, 'post_cap')):
        if not isinstance(pid, str) or pid not in sources:
            raise ValueError('Board/cap identity must resolve to a source Part.')
        source = sources[pid]
        if source.get('type') != {'namespace': 'shared', 'key': expected}:
            raise ValueError('Identity mapping requires the source board/cap PartType.')
        specs = source.get('spec')
        if not isinstance(specs, list) or any(not isinstance(sf, dict) for sf in specs):
            raise ValueError('Board/cap identity requires a list of source SpecFields.')
        colours = [sf for sf in specs if sf.get('key') == 'colour']
        colour = colours[0] if len(colours) == 1 else {}
        value, provenance = colour.get('value'), colour.get('provenance')
        if (colour.get('agree') != '==' or not isinstance(value, dict)
                or value.get('key') != 'white'
                or not isinstance(value.get('value_raw'), list) or not value['value_raw']
                or any(not isinstance(raw, str) or raw.strip().casefold() != 'white'
                       for raw in value['value_raw'])
                or not isinstance(provenance, dict)
                or not isinstance(provenance.get('cites'), list) or not provenance['cites']):
            raise ValueError('Board/cap identity requires the cited white colour token.')
        colour_hashes = {checked_cite(cite) for cite in provenance['cites']}
        private = {'id': pid, 'version': source['version'], 'status': 'draft',
                   'type': expected, 'name_i18n': deepcopy(source['name_i18n']),
                   'spec': [{'key': 'colour', 'agree': '==', 'value': 'white'}]}
        mapping = {'part_id': pid, 'source_part': deepcopy(source),
                   'fit_geometry_verified': False,
                   'unconsumed_dimensions': [deepcopy(sf) for sf in source['spec']
                                             if sf['key'] != 'colour'],
                   'reason': 'Nominal dimensions are not manufactured dimensions, installed pitch or internal clearance.'}
        if expected == 'post_cap':
            if pid not in anchors:
                raise ValueError('Cap identity needs its cited SKU anchor.')
            identity = anchors[pid]
            number, description = identity.get('model_number'), identity.get('description')
            number_hash = checked_anchor(number)
            description_hash = checked_anchor(description)
            sku = number['text_raw']
            if (sku != pid.rsplit('/', 1)[-1] or number_hash != description_hash
                    or description_hash not in colour_hashes
                    or re.search(r'\bpost\s+top\b', description['text_raw'], re.I) is None
                    or re.search(r'\bwhite\b', description['text_raw'], re.I) is None):
                raise ValueError('Cap SKU must match its cited source identity.')
            private['spec'].append({'key': 'sku', 'agree': '==', 'value': sku})
            mapping['sku_identity_anchor'] = deepcopy(identity)
        else:
            mapping['component_sku'] = None
            mapping['reason'] += ' The panel-kit SKU is not a board SKU.'
        parts.append(private)
        mappings.append(mapping)
    return parts, mappings


def author_components(package, model):
    """Map cited identity and rail constraints, leaving unknown fitting explicit."""
    source_parts = unique_records(package['part_fragments'], 'id')
    parts, dimensions, matching = [], [], []
    for slot in model['default_spec']['frame']:
        if slot['orientation'] != 'horizontal':
            raise ValueError('Rail face-height mapping requires horizontal rails.')
        source = source_parts[slot['requirement']['part_id']]
        if source['type']['key'] != 'rail':
            raise ValueError('Rail slot must reference a rail Part.')
        heights = [s for s in source['spec'] if s['key'] == 'height_mm']
        if len(heights) != 1:
            raise ValueError('Rail mapping requires exactly one sourced height.')
        height = heights[0]
        value = height['value']
        check_rail_reading(value)
        if (height['agree'] != '==' or value['unit'] != 'mm'
                or type(value['amount_milli']) is not int or value['amount_milli'] <= 0
                or not height['provenance']['cites']):
            raise ValueError('Rail mapping requires a positive cited millimetre height.')
        exact = Decimal(value['amount_milli']) / 1000
        projected = int(exact.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        parts.append({'id': source['id'], 'version': source['version'], 'status': 'draft',
                      'type': 'rail', 'name_i18n': source['name_i18n'],
                      'spec': [{'key': 'thickness_mm', 'agree': '==',
                                'value': projected, 'unit': 'mm'}]})
        matching_specs = [s for s in source['spec'] if s['key'] in ('width_mm', 'colour')]
        if len(matching_specs) != 2 or {s['key'] for s in matching_specs} != {'width_mm', 'colour'}:
            raise ValueError('Rail matching requires one width and one colour constraint.')
        for spec in matching_specs:
            if spec['key'] not in ('width_mm', 'colour'):
                continue
            if spec['agree'] != '==' or not spec['provenance']['cites']:
                raise ValueError('Rail matching requires cited equality constraints.')
            raw = spec['value']
            field = {'key': spec['key'], 'agree': '=='}
            mapping = {'part_id': source['id'], 'source_spec': deepcopy(spec)}
            if spec['key'] == 'width_mm':
                check_rail_reading(raw)
                if (raw.get('unit') != 'mm' or type(raw.get('amount_milli')) is not int
                        or raw['amount_milli'] <= 0):
                    raise ValueError('Rail width requires integer-milli millimetres.')
                exact_width = Decimal(raw['amount_milli']) / 1000
                rounded_width = int(exact_width.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
                field.update(value=rounded_width, unit='mm')
                mapping.update(exact_mm=str(exact_width), projected_mm=rounded_width,
                               rounding_error_mm=str(Decimal(rounded_width) - exact_width))
            else:
                if not isinstance(raw.get('key'), str) or not raw['key']:
                    raise ValueError('Rail colour requires a source token.')
                field['value'] = raw['key']
            parts[-1]['spec'].append(field)
            mapping['private_spec'] = deepcopy(field)
            matching.append(mapping)
        dimensions.append({'part_id': source['id'], 'slot_key': slot['key'],
                           'source_spec': deepcopy(height),
                           'original_part_specs': deepcopy(source['spec']),
                           'consumer_key': 'thickness_mm',
                           'datum': 'vertical face height of horizontal rail, not wall thickness',
                           'exact_mm': str(exact), 'projected_mm': projected,
                           'rounding_error_mm': str(Decimal(projected) - exact),
                           'rounding_policy': 'nearest whole millimetre, half up'})
    identity_parts, identity_mappings = author_identity_parts(package, model)
    parts.extend(identity_parts)
    inventories = [i for i in package['packaged_assembly_inventory']
                   if i['component_key'] == 'end_u_channel']
    if len(inventories) != 1:
        raise ValueError('Expected one end U-channel inventory record.')
    inventory = inventories[0]
    edges = ['first_board_tongue', 'last_board_groove']
    if (type(inventory['quantity_each']) is not int or inventory['quantity_each'] != 2
            or inventory['edges'] != edges
            or any(not inventory[key].get('cite') or not inventory[key].get('text_raw')
                   for key in ('evidence', 'count_evidence', 'edge_evidence'))):
        raise ValueError('U-channels require the evidenced two handed end placements.')
    channel_id = model['id'].replace('-emblem-73014714', '/emblem-73014714-end-u-channel')
    parts.append({'id': channel_id, 'version': 1, 'status': 'draft',
                  'type': 'end_channel', 'name_i18n': {'en': 'Emblem end U-channel'}, 'spec': []})
    if model['default_spec'].get('fixings'):
        raise ValueError('Cannot overwrite existing fixing requirements.')
    placements = []
    for edge in edges:
        key = 'u_channel_' + edge
        placements.append({'slot_key': key, 'part_id': channel_id, 'edge': edge,
                           'quantity_each': 1, 'evidence': deepcopy(inventory['edge_evidence'])})
    model['default_spec']['fixings'] = [
        {'key': p['slot_key'], 'basis': 'per_panel', 'qty_per_basis': p['quantity_each'],
         'edge_binding': {'member_key': model['default_spec']['infill']['pattern'][0]['key'],
                          'position': 'first' if p['edge'].startswith('first') else 'last',
                          'profile_edge': 'tongue' if p['edge'].endswith('tongue') else 'groove'},
         'requirement': {'part_id': channel_id, 'qty': 1}} for p in placements]
    return {'private_parts': parts, 'identity_mappings': identity_mappings,
            'rail_dimension_mappings': dimensions,
            'rail_matching_mappings': matching,
            'u_channel_placements': placements, 'u_channel_inventory_evidence': deepcopy(inventory),
            'scope': 'full panel only; incomplete private component representation',
            'handed_placement_consumed': False, 'kit_purchase_credit_consumed': False,
            'limitations': ['Handed bindings are authored; actual placement remains unverified until panel fitting inputs are sourced.',
                            'Channels ship in the panel kit; separate component demand must not become extra purchases.',
                            'Private rail dimensions and colour constrain matching, but component SKU identities and channel matching specs remain incomplete.',
                            'Board effective width/stock length and cap/channel fit geometry remain unresolved despite closed identity references.']}


def author_kit_membership(package, model, private_parts):
    """Bind the cited kit inventory to Parts without emitting a partial kit."""
    inventory = unique_records(package['packaged_assembly_inventory'], 'component_key')
    frames = {slot['key']: slot['requirement']['part_id']
              for slot in model['default_spec']['frame']}
    board = model['default_spec']['infill']['pattern'][0]
    channels = model['default_spec']['fixings']
    channel_ids = {f['requirement']['part_id'] for f in channels}
    if len(channel_ids) != 1:
        raise ValueError('Kit U-channel inventory must name one component identity.')
    targets = [
        ('bottom_rail', frames['bottom_rail'], ['bottom_rail'], 1),
        ('top_rail', frames['top_rail'], ['top_rail'], 1),
        ('tongue_and_groove_boards', board['requirement']['part_id'], [board['key']], None),
        ('end_u_channel', next(iter(channel_ids)), [f['key'] for f in channels], 2),
    ]
    defined = {p['id'] for p in private_parts}
    relationships = []
    for key, pid, slots, expected in targets:
        entry = inventory[key]
        if (pid not in defined or type(entry['quantity_each']) is not type(expected)
                or entry['quantity_each'] != expected):
            raise ValueError('Kit membership needs defined Parts and the currently evidenced inventory.')
        if not entry['evidence'].get('cite'):
            raise ValueError('Kit membership requires its source evidence.')
        relationships.append({'component_key': key, 'part_id': pid, 'slot_keys': slots,
                              'quantity_each': expected, 'stock_length_mm': None,
                              'source_inventory': deepcopy(entry)})
    identities = [a for a in package['identity_anchors'] if a['text_raw'] == '73014714']
    if len(identities) != 1 or not identities[0].get('cite'):
        raise ValueError('Kit membership requires the exact supplier-model identity anchor.')
    return {'artifact_kind': 'private_authored_kit_membership',
            'supplier_model_number': '73014714', 'identity_anchor': deepcopy(identities[0]),
            'model_id': model['id'], 'authorship': 'third_party_authored',
            'review_status': 'unreviewed_authored', 'relationships': relationships,
            'runtime_requirements_added': False,
            'emission_status': 'blocked_incomplete_inventory_and_stock',
            'remaining_inputs': ['Exact kit board count with applicable source evidence',
                                 'Manufactured rail and board lengths for package credits',
                                 'Applicable channel fit and length semantics'],
            'separately_purchased_part_ids': [model['post']['cap']['part_id']],
            'limitations': ['Membership is authored structure; it is not a complete supplier Product or executable kit requirement.',
                            'Missing board count remains null; fitted demand is never substituted for packaged inventory.',
                            'Post selection remains a separate station-scoped purchase rule.']}


def prepare(package, placement_confirmation=None):
    # Same closed rule shape as purchase_preview; no ignored conditions or packs.
    unique_records(package['purchase_quantity_rules'], 'target')
    for rule in package['purchase_quantity_rules']:
        if (set(rule) != {'id', 'target', 'model_id', 'basis', 'quantity_per_basis',
                         'authorship', 'derivation', 'evidence'}
                or set(rule['quantity_per_basis']) != {'amount_milli', 'unit', 'value_raw'}):
            raise ValueError('Unsupported quantity-rule fields must not be ignored.')
    model = deepcopy(package['model_fragment'])
    source_joints = {}
    for slot in model['default_spec']['frame']:
        joint = slot['joint']
        if joint != {'kind': 'channel'}:
            raise ValueError('Only the documented kind-only channel mapping is supported.')
        source_joints[slot['key']] = deepcopy(joint)
        slot['joint'] = joint['kind']
    bindings = [b for b in package['pending_bindings']
                if b['target'] == '/model_fragment/post/requirement']
    if len(bindings) != 1:
        raise ValueError('Expected one explicit post binding.')
    identities = {p['part_id']: p for p in package['part_identity_anchors']}
    selected, branches, evidence = {}, [], []
    def equal(path, value):
        return {'op': 'cmp', 'cmp': '==', 'left': {'op': 'field', 'path': path},
                'right': {'op': 'lit', 'value': value}}
    for binding in bindings[0]['candidates']:
        role = binding['post_role']
        identity = identities[binding['part_id']]
        if role in selected or identity.get('post_role') != role:
            raise ValueError('Duplicate or contradictory post-role identity.')
        sku = identity['model_number']['text_raw']
        selected[role] = sku
        branches.append({'op': 'and', 'items': [equal('post.kind', role), equal('item.sku', sku)]})
        evidence.extend([identity['description'], identity['model_number']])
    if set(selected) != {'end', 'line', 'corner'} or len(set(selected.values())) != 3:
        raise ValueError('Expected distinct end, line and corner products.')
    quantities = [r for r in package['purchase_quantity_rules'] if r['target'] == 'post']
    if (len(quantities) != 1 or quantities[0]['model_id'] != model['id']
            or quantities[0]['basis'] != 'unique_post_station'
            or quantities[0]['quantity_per_basis']['amount_milli'] != 1000
            or quantities[0]['quantity_per_basis']['unit'] != 'each'):
        raise ValueError('This post selector requires the authored one-post-per-station rule.')
    model['post']['requirement'] = {
        'part_id': '', 'role': 'post',
        'qty': quantities[0]['quantity_per_basis']['amount_milli'] // 1000,
        'eligibility': {'predicate': {'op': 'or', 'items': branches}}}
    result = {
        'artifact_kind': 'private_consumer_model_authoring_candidate',
        'source_package_hash': content_hash(package), 'model': model,
        'source_joints': source_joints, 'post_binding_evidence': evidence,
        'post_quantity_rule': deepcopy(quantities[0]),
        'expected_post_skus': selected,
        'placement_inputs_required': ['bottom_rail centreline offset from panel bottom',
                                      'top_rail centreline offset from panel top'],
        'placement_datum_note': '72-inch panel and 7-inch rails do not explicitly establish rail centre offsets.',
        'private_defaults_are_not_source_facts': [
            'channel depth and insertion margin', 'board engagements/gap/face offset',
            'infill excess and margin policies',
            'requirement length rule and overlap', 'grade and height support'],
        'publishable': False, 'installation_ready': False, 'bom_generation_verified': False,
        'limitations': ['Private SKU predicate is catalog authoring, not a published PartRequirement.',
                        'Exact-SKU Part library and physical geometry remain incomplete.'],
    }
    if placement_confirmation is not None:
        confirmation = placement_confirmation
        if (confirmation.get('source_package_hash') != content_hash(package)
                or confirmation.get('model_id') != model['id']
                or confirmation.get('status') != 'user_confirmed_interpretation'
                or confirmation.get('datum') != 'outside_bottom_rail_to_outside_top_rail'
                or confirmation.get('panel_height_inches') != '72'
                or confirmation.get('rail_vertical_envelope_inches') != '7'
                or not confirmation.get('reviewer')):
            raise ValueError('Placement confirmation must bind the exact package and reviewed datum.')
        exact = Decimal(confirmation['rail_vertical_envelope_inches']) * Decimal('25.4') / 2
        projected = int(exact.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        kinds = {'bottom_rail': 'from_bottom', 'top_rail': 'from_top'}
        slots = model['default_spec']['frame']
        if len(slots) != 2 or {s['key'] for s in slots} != set(kinds):
            raise ValueError('Placement confirmation only covers the two reviewed rails.')
        for slot in slots:
            if slot['orientation'] != 'horizontal' or 'placement' in slot:
                raise ValueError('Placement confirmation cannot override existing or vertical placement.')
            slot['placement'] = {'kind': kinds[slot['key']], 'offset_mm': projected}
        result['placement_confirmation'] = deepcopy(confirmation)
        result['placement_inputs_required'] = []
        result['placement_projection'] = {
            'exact_inward_offset_mm': str(exact), 'consumer_inward_offset_mm': projected,
            'rounding_policy': 'nearest whole millimetre, half up; authored adapter policy',
            'offset_rounding_error_mm': str(Decimal(projected) - exact),
        }
        result['placement_datum_note'] = (
            'User-confirmed interpretation; source pages do not explicitly dimension the endpoints. '
            'Integer-mm approximation is adapter authoring, not a manufacturer tolerance.')
    result['component_authoring'] = author_components(package, model)
    result['assembly_authoring'] = author_assembly_rules(package, model)
    result['kit_membership_authoring'] = author_kit_membership(
        package, model, result['component_authoring']['private_parts'])
    return result


def unconsumed_paths(authored, parsed, path=()):
    """Find authored fields silently discarded by the private consumer parser."""
    missing = []
    if isinstance(authored, dict) and isinstance(parsed, dict):
        for key, value in authored.items():
            child = (*path, key)
            if key not in parsed:
                missing.append(list(child))
            else:
                missing.extend(unconsumed_paths(value, parsed[key], child))
    elif isinstance(authored, list) and isinstance(parsed, list):
        for index, value in enumerate(authored):
            if index >= len(parsed):
                missing.append(list((*path, index)))
            else:
                missing.extend(unconsumed_paths(value, parsed[index], (*path, index)))
    return missing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--consumer-root', type=Path, required=True)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--placement-confirmation', type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.consumer_root.resolve() / 'src'))
    from pydantic import ValidationError
    from fenceai.fencemodel.model import FenceModel, PartRequirement, validate_model
    from fenceai.catalog.model import Catalog
    from fenceai.knowledge.ast import evaluate_expr
    from scripts.emblem_consumer_adapter import inspect_candidate
    confirmation = (json.loads(args.placement_confirmation.read_text())
                    if args.placement_confirmation else None)
    result = prepare(json.loads(args.package.read_text()), confirmation)
    requirement = PartRequirement.model_validate(result['model']['post']['requirement'])
    expected = result['expected_post_skus']
    matrix = {}
    for role in ['end', 'line', 'corner', 'gate', 'junction', 'transition']:
        matches = [sku for sku in [*expected.values(), 'unrelated-product']
                   if evaluate_expr(requirement.eligibility.predicate,
                                    {'post': {'kind': role}, 'item': {'sku': sku}})]
        wanted = [expected[role]] if role in expected else []
        if matches != wanted:
            raise ValueError(f'Post selector mismatch for {role}: {matches}')
        matrix[role] = matches
    try:
        parsed = FenceModel.model_validate(result['model'])
    except ValidationError as exc:
        errors = [{'location': list(e['loc']), 'message': e['msg']} for e in exc.errors()]
    else:
        errors = []
    positions, semantic_errors, unconsumed, component_probe = {}, [], [], {}
    part_aware = {'executed': False,
                  'scope': 'diagnostic copies of draft definitions; empty catalog, not physical-fit proof'}
    if not errors:
        semantic_errors = validate_model(parsed, Catalog(), library=None)
        unconsumed = unconsumed_paths(result['model'], parsed.model_dump())
    if not errors and confirmation is not None:
        from fenceai.fencemodel.resolve import placement_positions
        height = int((Decimal(confirmation['panel_height_inches']) * Decimal('25.4')).quantize(
            Decimal('1'), rounding=ROUND_HALF_UP))
        positions = {s.key: placement_positions(s.placement, 1, height)
                     for s in parsed.default_spec.frame}
        offset = result['placement_projection']['consumer_inward_offset_mm']
        if positions != {'bottom_rail': [offset], 'top_rail': [height - offset]}:
            raise ValueError('Consumer rail positions disagree with the confirmed datum projection.')
        from fenceai.parts.model import Part, PartLibrary
        from fenceai.parts.resolve import resolve_model_parts
        from fenceai.parts.compile import compile_spec
        from fenceai.fencemodel.model import PanelSpec
        from fenceai.fencemodel.resolve import PanelContext, resolve_panel
        # Activate copies only in an isolated diagnostic, never the authored Parts.
        authored = result['component_authoring']
        library = PartLibrary(parts=[Part.model_validate(dict(p, status='active'))
                                     for p in authored['private_parts']])
        part_aware.update(executed=True, errors=validate_model(parsed, Catalog(), library=library),
                          active_parts_are_in_memory_test_copies=True,
                          actual_authored_parts_remain_draft=True)
        matching_checks = {}
        for part in library.parts:
            if part.type != 'rail':
                continue
            item = {s.key: s.value for s in part.spec}
            expr = compile_spec(part)
            checks = {'declared_attributes_match': evaluate_expr(expr, {'item': item}),
                      'wrong_colour_refused': not evaluate_expr(expr, {'item': dict(item, colour='other')}),
                      'wrong_width_refused': not evaluate_expr(expr, {'item': dict(item, width_mm=item['width_mm'] + 1)})}
            if not all(checks.values()):
                raise ValueError('Consumer lost rail matching constraints.')
            matching_checks[part.id] = checks
        probe_model = parsed.model_copy(deep=True)
        probe_model.post = None
        probe_model.default_spec.infill = None
        probe_model.variants = []
        resolved, _ = resolve_model_parts(probe_model, library)
        rail_heights = {s.key: s.thickness_mm for s in resolved.default_spec.frame}
        expected_heights = {m['slot_key']: m['projected_mm'] for m in authored['rail_dimension_mappings']}
        if rail_heights != expected_heights:
            raise ValueError('Consumer lost the sourced vertical rail face height.')
        # Count only channel requirements: no invented panel/infill fit is executed.
        count_fixings = [f.model_copy(update={'edge_binding': None})
                         for f in resolved.default_spec.fixings]
        channels = resolve_panel(PanelSpec(fixings=count_fixings),
                                 PanelContext(centre_width_mm=1, clear_width_mm=1, height_mm=1))
        counts = {s.slot_key: s.qty for s in channels.slots}
        expected_counts = {p['slot_key']: p['quantity_each'] for p in authored['u_channel_placements']}
        if counts != expected_counts:
            raise ValueError('Consumer U-channel count differs from authored end placements.')
        component_probe = {'scope': 'isolated rail dimensions and channel counts, no physical panel fit',
                           'active_parts_are_in_memory_test_copies': True,
                           'edge_bindings_removed_for_count_only_probe': True,
                           'rail_face_heights_mm': rail_heights,
                           'synthetic_rail_attribute_matching': matching_checks,
                           'u_channel_counts_per_panel': counts,
                           'u_channels_for_1_and_7_panels': {str(n): n * sum(counts.values()) for n in (1, 7)},
                           'handed_placement_consumed': False,
                           'kit_purchase_credit_consumed': False}
    report = {
        'consumer_revision': subprocess.check_output(
            ['git', '-C', str(args.consumer_root), 'rev-parse', 'HEAD'], text=True).strip(),
        'consumer_source_diff_sha256': hashlib.sha256(subprocess.check_output(
            ['git', '-C', str(args.consumer_root), 'diff', 'HEAD', '--', 'src'])).hexdigest(),
        'post_requirement_parses': True, 'post_role_matrix': matrix,
        'private_model_parser_errors': errors, 'whole_model_parses': not errors,
        'candidate_hash': content_hash(result),
        'partial_semantic_validation': {
            'executed': not errors, 'errors': semantic_errors,
            'catalog_basis': 'empty diagnostic fixture, not supplier evidence',
            'part_library_basis': 'absent; Part-dependent checks skipped',
        },
        'unconsumed_authored_paths': unconsumed,
        'profile_edges_preserved_by_parser': (not errors and
            parsed.model_dump()['default_spec']['infill']['pattern'][0].get('profile_edges') ==
            result['model']['default_spec']['infill']['pattern'][0]['profile_edges']),
        'component_resolution_probe': component_probe,
        'part_aware_semantic_validation': part_aware,
        'consumer_boundary': inspect_candidate(result, FenceModel),
        'placement_confirmed': confirmation is not None,
        'placement_confirmation_kind': 'user_confirmed_interpretation' if confirmation else None,
        'resolved_centrelines_mm_at_rounded_1829_mm_panel_height': positions,
        'full_model_validation': 'not_run_exact_part_library_and_catalog_incomplete',
        'bom_generation_verified': False,
        'candidate_complete': False,
        'completion_blockers': ['Exact Part library and catalog unavailable',
                                'Authored geometry and fitting policies incomplete',
                                'Published model adapter unavailable'],
    }
    for path, value in [(args.output, result), (args.report, report)]:
        with open_write(path) as handle:
            json.dump(value, handle, indent=2)
            handle.write('\n')
    print(json.dumps(report, indent=2))
    return 2  # No complete model-validation path exists in this draft preparer.


if __name__ == '__main__':
    sys.exit(main())
