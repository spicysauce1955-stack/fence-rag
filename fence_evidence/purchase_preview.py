"""Private, model-backed catalog counts for explicitly authored full-panel bays.

Not a contract Snapshot, commercial catalog, fitting engine or Planning adapter.
Unknown packaging, installation quantities and consumer matching remain unknown.
"""
from collections import defaultdict
from copy import deepcopy
import hashlib
import json

from .canonical import content_hash
from .paths import REPO_ROOT
from .refs import build_index


class PreviewError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise PreviewError(message)


def _unique(items, key, label):
    result = {}
    for item in items:
        value = item.get(key)
        _require(isinstance(value, str) and value and value not in result,
                 f'missing or duplicate {label}')
        result[value] = item
    return result


def _topology(layout, model_id):
    _require(layout.get('kind') == 'full_panel_schematic', 'only full-panel schematics are supported')
    _require(set(layout) <= {'kind', 'scenario', 'coordinates', 'expected_run_count', 'stations', 'bays'},
             'unsupported layout fields must not be silently ignored')
    stations = _unique(layout['stations'], 'id', 'station')
    _require(all(set(s) <= {'id', 'schematic_point', 'role'} for s in stations.values()),
             'unsupported station intent needs an adapter')
    bays = _unique(layout['bays'], 'id', 'bay')
    _require(stations and bays, 'layout must contain stations and bays')
    points = {sid: s.get('schematic_point') for sid, s in stations.items()}
    _require(all(isinstance(p, list) and len(p) == 2 and all(type(v) is int for v in p)
                 for p in points.values()), 'schematic points must be integer pairs, not lengths')
    _require(len({tuple(p) for p in points.values()}) == len(points), 'coincident stations')
    neighbors = defaultdict(set)
    edges = set()
    for bay in bays.values():
        _require(set(bay) == {'id', 'from', 'to', 'model_id', 'supply'},
                 'unsupported bay fields; only explicitly full-panel topology is handled')
        _require(bay.get('model_id') == model_id, 'bay references a different model')
        _require(bay.get('supply') == 'full_kit', 'cut panels and gates are unsupported')
        a, b = bay['from'], bay['to']
        edge = frozenset((a, b))
        _require(a in stations and b in stations and len(edge) == 2 and edge not in edges,
                 'invalid or duplicated bay endpoints')
        dx, dy = (points[a][i] - points[b][i] for i in (0, 1))
        _require((dx == 0) != (dy == 0), 'only orthogonal bays are supported')
        edges.add(edge)
        neighbors[a].add(b)
        neighbors[b].add(a)
    ordered_edges = list(edges)
    for i, first in enumerate(ordered_edges):
        a, b = (points[sid] for sid in first)
        for second in ordered_edges[i+1:]:
            if first & second:
                continue
            c, d = (points[sid] for sid in second)
            intersects = all(max(min(a[k], b[k]), min(c[k], d[k])) <=
                             min(max(a[k], b[k]), max(c[k], d[k])) for k in (0, 1))
            _require(not intersects, 'bays intersect without a shared station')
    roles = {}
    for sid in stations:
        adjacent = sorted(neighbors[sid])
        _require(len(adjacent) in (1, 2), 'isolated stations and junctions are unsupported')
        role = 'end'
        if len(adjacent) == 2:
            u, v = ([points[n][i] - points[sid][i] for i in (0, 1)] for n in adjacent)
            dot, cross = sum(x*y for x, y in zip(u, v)), u[0]*v[1]-u[1]*v[0]
            _require(dot < 0 or cross != 0, 'overlapping bays at station')
            role = 'line' if cross == 0 else 'corner'
        _require('role' not in stations[sid] or stations[sid]['role'] == role,
                 'authored post role contradicts schematic geometry')
        roles[sid] = role
    remaining, runs = set(stations), []
    while remaining:
        root = min(remaining)
        component, pending = set(), [root]
        while pending:
            sid = pending.pop()
            if sid not in component:
                component.add(sid)
                pending.extend(neighbors[sid] - component)
        _require(sum(roles[sid] == 'end' for sid in component) == 2, 'closed loops are unsupported')
        remaining -= component
        runs.append(sorted(component))
    _require(len(runs) == layout.get('expected_run_count'), 'run count differs from declared layout')
    return stations, bays, roles, runs


def generate(package, layout, *, conn=None):
    """Read model references, never existing example purchase lines or SKU literals."""
    model = package['model_fragment']
    _require(not model.get('variants') and not model.get('option_axes'),
             'variant selection needs the Planning adapter')
    _require(not model.get('layout_policy'), 'layout policies need the Planning adapter')
    _require(not model['default_spec'].get('fixings'), 'panel fixings need explicit purchase coverage')
    stations, bays, roles, runs = _topology(layout, model['id'])
    parts = _unique(package['part_fragments'], 'id', 'Part')
    identities = _unique(package['part_identity_anchors'], 'part_id', 'Part product identity')
    sources = _unique(package['source_docs'], 'content_hash', 'SourceDoc')
    def cited(anchor):
        cite = anchor.get('cite', {})
        _require(cite.get('id') and cite.get('belongs_to') in sources, 'identity has no pinned source')
        return cite

    rules = _unique(package.get('purchase_quantity_rules', []), 'target', 'quantity-rule target')
    _require(set(rules) == {'panel_kit', 'post', 'post_cap'},
             'explicit quantity rules are required for kit, post and cap')
    _unique(list(rules.values()), 'id', 'quantity-rule id')
    for target, rule in rules.items():
        _require(set(rule) == {'id', 'target', 'model_id', 'basis', 'quantity_per_basis',
                              'authorship', 'derivation', 'evidence'},
                 'unsupported quantity-rule fields must not be silently ignored')
        _require(rule.get('model_id') == model['id'], 'quantity rule belongs to another model')
        expected_basis = 'full_panel_bay' if target == 'panel_kit' else 'unique_post_station'
        _require(rule.get('basis') == expected_basis, 'unsupported quantity-rule basis')
        quantity = rule.get('quantity_per_basis', {})
        _require(set(quantity) == {'amount_milli', 'unit', 'value_raw'},
                 'unsupported quantity fields must not be silently ignored')
        amount = quantity.get('amount_milli')
        _require(type(amount) is int and amount > 0 and amount % 1000 == 0
                 and quantity.get('unit') == 'each', 'quantity rule must specify positive whole items')
        _require(rule.get('evidence') and rule.get('derivation') and
                 rule.get('authorship') == 'third_party_authored',
                 'quantity rule needs evidence and an explicit authored derivation')
        for anchor in rule['evidence']:
            cited(anchor)
        _require(quantity.get('value_raw') == [a['text_raw'] for a in rule['evidence']],
                 'quantity-rule lexemes must preserve their evidence')

    kit_sku = package['scope']['model_number']
    kit_anchors = [a for a in package['identity_anchors'] if a['text_raw'] == kit_sku]
    _require(len(kit_anchors) == 1, 'kit identity is missing or ambiguous')
    kit_anchor = kit_anchors[0]
    _require(kit_anchor['text_raw'] == kit_sku, 'kit identity differs from source anchor')
    cited(kit_anchor)
    kit_description = package['scope'].get('product_description')
    description_anchors = [a for a in package['identity_anchors']
                           if a['text_raw'] == kit_description]
    _require(isinstance(kit_description, str) and kit_description and len(description_anchors) == 1,
             'kit product description anchor is missing or ambiguous')
    kit_description_anchor = description_anchors[0]
    cited(kit_description_anchor)
    coverage = package.get('purchase_projection', {}).get('panel_kit_covers', [])
    _require(model['default_spec']['frame'] and model['default_spec']['infill']['pattern'],
             'supported panel shape requires nonempty frame and infill')
    for kind, slots in [('frame', model['default_spec']['frame']),
                        ('infill', model['default_spec']['infill']['pattern'])]:
        _unique(slots, 'key', f'{kind} slot')
        _require(all(set(slot['requirement']) == {'part_id'} for slot in slots),
                 'additional panel requirement semantics need the Planning adapter')
        _require(all(not slot.get('contains') for slot in slots),
                 'contained panel parts need explicit purchase coverage')
    expected = {(kind, slot['key'], slot['requirement']['part_id'])
                for kind, slots in [('frame', model['default_spec']['frame']),
                                    ('infill', model['default_spec']['infill']['pattern'])]
                for slot in slots}
    claimed = [(x['slot_kind'], x['slot_key'], x['part_id']) for x in coverage]
    _require(len(claimed) == len(set(claimed)) and set(claimed) == expected,
             'kit coverage does not match every frame and infill slot')
    _require(all(part_id in parts for _, _, part_id in expected), 'kit covers an unknown Part')
    post = model.get('post')
    _require(isinstance(post, dict), 'model has no post opinion; a company default is needed')
    _require(not post.get('contains'), 'post reinforcement or containment needs purchase coverage')
    _require('requirement' not in post, 'contract post eligibility needs the Planning adapter; private bindings must not override it')
    bindings = [b for b in package.get('pending_bindings', [])
                if b.get('target') == '/model_fragment/post/requirement']
    _require(len(bindings) == 1, 'post selection binding is missing or ambiguous')
    candidates = _unique(bindings[0]['candidates'], 'post_role', 'post-role candidate')
    _require('cap' in post, 'cap requirement is missing, not an explicit no-cap decision')

    def product(part_id, required_type, role=None):
        _require(part_id in parts and part_id in identities, 'Part or explicit product identity missing')
        part, identity = parts[part_id], identities[part_id]
        _require(part.get('type') == {'namespace': 'shared', 'key': required_type}, 'wrong Part type for slot')
        if role:
            _require(identity.get('post_role') == role, 'post-role binding differs from product identity')
            _require(f'{role} post' in identity['description']['text_raw'].lower(),
                     'post-role identity differs from source description')
        sku = identity['model_number']['text_raw']
        _require(isinstance(sku, str) and sku.strip() == sku and sku, 'empty product identity')
        cited(identity['model_number'])
        cited(identity['description'])
        return part, identity, sku

    lines = {}
    def demand(sku, description, origins, cites, rule_target, part_id=None, covered_slots=None):
        rule = rules[rule_target]
        multiplier = rule['quantity_per_basis']['amount_milli'] // 1000
        cites = cites + [cited(anchor) for anchor in rule['evidence']]
        key = sku
        if key in lines:
            _require(lines[key]['description'] == description and
                     (covered_slots is not None) == ('covers_panel_slots' in lines[key]),
                     'one product identity is assigned incompatible purchase meanings')
        line = lines.setdefault(key, {'manufacturer_model_number': sku, 'description': description,
                                     'quantity_each': 0, 'origins': [], 'part_ids': [], 'cites': [],
                                     'supplier_pack_quantity': None, 'quantity_derivations': []})
        line['quantity_each'] += len(origins) * multiplier
        line['quantity_derivations'].append({
            'rule_id': rule['id'], 'basis': rule['basis'], 'basis_count': len(origins),
            'quantity_per_basis': deepcopy(rule['quantity_per_basis']),
            'quantity_each': len(origins) * multiplier,
            'authorship': rule['authorship'], 'derivation': rule['derivation'],
            'cites': [cited(anchor) for anchor in rule['evidence']]})
        line['origins'].extend(origins)
        if part_id and part_id not in line['part_ids']:
            line['part_ids'].append(part_id)
        for cite in cites:
            if cite not in line['cites']:
                line['cites'].append(cite)
        if covered_slots is not None:
            line['covers_panel_slots'] = deepcopy(covered_slots)
    demand(kit_sku, model['name_i18n']['en'],
           [{'kind': 'bay', 'id': bid, 'model_id': model['id']} for bid in sorted(bays)],
           [cited(kit_description_anchor), cited(kit_anchor)], 'panel_kit', covered_slots=coverage)
    for role in sorted(set(roles.values())):
        _require(role in candidates, f'no product binding for post role {role}')
        part_id = candidates[role]['part_id']
        part, identity, sku = product(part_id, 'post', role)
        demand(sku, part['name_i18n']['en'],
               [{'kind': 'post_station', 'id': sid, 'post_role': role} for sid in sorted(roles) if roles[sid] == role],
               [cited(identity['description']), cited(identity['model_number'])], 'post', part_id)
    if post['cap'] is not None:
        _require(set(post['cap']) == {'part_id'}, 'additional cap requirement semantics need the Planning adapter')
        part_id = post['cap']['part_id']
        part, identity, sku = product(part_id, 'post_cap')
        demand(sku, part['name_i18n']['en'],
               [{'kind': 'post_cap', 'id': sid} for sid in sorted(stations)],
               [cited(identity['description']), cited(identity['model_number'])], 'post_cap', part_id)
    verified = False
    if conn is not None:
        manifest = _unique(package.get('sources', []), 'content_hash', 'source manifest entry')
        _require(set(manifest) == set(sources) and manifest, 'source manifest does not cover every SourceDoc')
        index = build_index(conn)
        for source in manifest.values():
            path = REPO_ROOT / source['path']
            _require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == source['content_hash'],
                     'source file hash mismatch')
            row = conn.execute('SELECT 1 FROM document_versions WHERE document_id=? AND sha256=?',
                               (source['document_id'], source['content_hash'])).fetchone()
            _require(row is not None, 'source document/version identity mismatch')
        def check_evidence(node):
            if isinstance(node, dict):
                if 'belongs_to' in node:
                    locus = index.get(node.get('id'))
                    _require(node['belongs_to'] in sources and locus is not None and
                             locus.sha256 == node['belongs_to'], 'citation points elsewhere or lacks a SourceDoc')
                if 'element_id' in node and 'text_raw' in node:
                    locus = index.get(node.get('cite', {}).get('id'))
                    _require(locus is not None and node['element_id'] in locus.element_ids,
                             'evidence anchor citation points elsewhere')
                    row = conn.execute('SELECT text FROM elements WHERE element_id=?', (node['element_id'],)).fetchone()
                    _require(row is not None and row['text'] == node['text_raw'], 'evidence text differs from source')
                for value in node.values():
                    check_evidence(value)
            elif isinstance(node, list):
                for value in node:
                    check_evidence(value)
        check_evidence(package)
        kit_identity = {'description': kit_description_anchor, 'model_number': kit_anchor}
        for identity in [kit_identity, *identities.values()]:
            description = index[identity['description']['cite']['id']]
            number = index[identity['model_number']['cite']['id']]
            _require(description.sha256 == number.sha256 and description.page_no == number.page_no
                     and description.bbox and number.bbox,
                     'product description and model number have no shared source row')
            left, right = json.loads(description.bbox), json.loads(number.bbox)
            _require(left[2] <= right[0] and max(left[1], right[1]) < min(left[3], right[3]),
                     'product description and model number are on different source rows')
        verified = True
    return {'artifact_kind': 'private_model_backed_purchase_preview', 'publishable': False,
            'model_id': model['id'], 'model_package_hash': content_hash(package),
            'layout_hash': content_hash(layout), 'source_docs': deepcopy(package['source_docs']),
            'source_identity_verified': verified,
            'quantity_rule_admission': 'unreviewed_authored',
            'quantity_semantics_verified': False,
            'purchase_lines': [lines[sku] for sku in sorted(lines)],
            'station_roles': roles, 'connected_runs': runs,
            'authored_kit_inventory_per_bay': deepcopy(package['packaged_assembly_inventory']),
            'inventory_validation': 'unreviewed_authored',
            'inventory_completeness_verified': False,
            'installation_ready': False, 'contract_consumer_verified': False,
            'limitations': ['Private post bindings and kit coverage are not contract eligibility or Product matching.',
                            'Source identity checks do not approve quantity derivations or inventory claims; these remain unreviewed authored inputs.',
                            'Supplier pack sizes, material quantities and physical fit remain unresolved.']}
