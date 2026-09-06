"""Check authored open-run product counts and the assembly review trace.

This is a private example check, not a Planning resolver or supplier cart builder.
"""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fence_evidence.paths import open_write


def audit(example):
    errors = []
    stations = example['stations']
    roles = {s['id']: s['role'] for s in stations}
    if len(roles) != len(stations):
        errors.append('duplicate station identity')
    degree = Counter()
    neighbors = {sid: set() for sid in roles}
    edges = set()
    bay_ids = [bay['id'] for bay in example['bays'] if 'id' in bay]
    if len(set(bay_ids)) != len(bay_ids):
        errors.append('duplicate bay identity')
    for bay in example['bays']:
        ends = (bay['from'], bay['to'])
        edge = frozenset(ends)
        if len(edge) != 2 or not edge <= roles.keys() or edge in edges:
            errors.append('invalid or duplicated bay endpoints')
            continue
        edges.add(edge)
        for a, b in (ends, ends[::-1]):
            degree[a] += 1
            neighbors[a].add(b)
        if bay['panel_model_number'] != '73014714':
            errors.append('unsupported panel kit in this example')
    components = []
    remaining = set(roles)
    while remaining:
        visited, pending = set(), [min(remaining)]
        while pending:
            sid = pending.pop()
            if sid not in visited:
                visited.add(sid)
                pending.extend(neighbors[sid] - visited)
        components.append(visited)
        remaining -= visited
    if not components or len(components) != example.get('expected_run_count', 1):
        errors.append('connected run count differs from declared layout')
    for component in components:
        if sum(degree[sid] == 1 for sid in component) != 2:
            errors.append('each open run must have exactly two endpoints')
    positioned = example.get('layout_kind') == 'orthogonal_open_runs'
    points = {s['id']: s.get('schematic_point') for s in stations}
    valid_points = all(isinstance(p, list) and len(p) == 2 and
                       all(type(v) is int for v in p) for p in points.values())
    if positioned and not valid_points:
        errors.append('orthogonal layout needs integer schematic points for every station')
    if positioned and valid_points:
        if len({tuple(p) for p in points.values()}) != len(points):
            errors.append('two station identities occupy the same schematic point')
        for edge in edges:
            a, b = tuple(edge)
            dx, dy = (points[b][i] - points[a][i] for i in (0, 1))
            if (dx == 0) == (dy == 0):
                errors.append('example supports only nonzero orthogonal bays')
        edge_list = list(edges)
        for i, first in enumerate(edge_list):
            a, b = (points[sid] for sid in first)
            for second in edge_list[i+1:]:
                if first & second:
                    continue
                c, d = (points[sid] for sid in second)
                # Axis-aligned segment boxes intersect iff the segments do.
                if all(max(min(a[k], b[k]), min(c[k], d[k])) <=
                       min(max(a[k], b[k]), max(c[k], d[k])) for k in (0, 1)):
                    errors.append('panel bays cross or overlap without a shared station')
    for sid, role in roles.items():
        allowed = {('end', 1), ('line', 2)} | ({('corner', 2)} if positioned else set())
        if (role, degree[sid]) not in allowed:
            errors.append(f'{sid}: post role differs from open-run topology')
        if positioned and valid_points and degree[sid] == 2:
            a, b = sorted(neighbors[sid])
            u = [points[a][i] - points[sid][i] for i in (0, 1)]
            v = [points[b][i] - points[sid][i] for i in (0, 1)]
            dot, cross = sum(x*y for x, y in zip(u, v)), u[0]*v[1]-u[1]*v[0]
            derived = 'line' if cross == 0 and dot < 0 else 'corner' if dot == 0 and cross != 0 else None
            if role != derived:
                errors.append(f'{sid}: post role differs from schematic angle')
    expected = Counter({'73014714': len(example['bays']), '73013956': len(roles)})
    for role in roles.values():
        sku = {'end': '73045785', 'line': '73045783', 'corner': '73045784'}.get(role)
        if sku:
            expected[sku] += 1
    actual = Counter()
    for line in example['purchase_lines']:
        qty = line['quantity_each']
        if type(qty) is not int or qty <= 0:
            errors.append('purchase quantities must be positive integers')
            continue
        actual[line['manufacturer_model_number']] += qty
    if actual != expected:
        errors.append('purchase lines differ from unique-station and full-kit counts')
    if 'build_runs' in example:
        covered_stations, covered_edges = [], []
        run_ids = [run['id'] for run in example['build_runs']]
        if len(set(run_ids)) != len(run_ids):
            errors.append('duplicate build-run identity')
        for run in example['build_runs']:
            path = run['station_order']
            if len(path) < 2 or any(sid not in roles for sid in path):
                errors.append('build run names missing stations or has no bay')
                continue
            if roles[path[0]] != 'end' or roles[path[-1]] != 'end':
                errors.append('open-run assembly must start and finish at end stations')
            covered_stations.extend(path)
            covered_edges.extend(frozenset(pair) for pair in zip(path, path[1:]))
        if Counter(covered_stations) != Counter(roles.keys()):
            errors.append('assembly traversal omits or repeats a station')
        if Counter(covered_edges) != Counter({edge: 1 for edge in edges}):
            errors.append('assembly traversal omits, repeats or invents a panel bay')
    contents = example.get('kit_contents', [])
    channels = [x for x in contents if x.get('component_key') == 'end_u_channel']
    if len(channels) != 1 or channels[0].get('quantity_each') != 2:
        errors.append('kit inventory must account for two end U-channels')
    elif channels[0].get('edges') != ['first_board_tongue', 'last_board_groove']:
        errors.append('end U-channel handedness lost')
    sequence = example.get('assembly_trace', [])
    keys = [step['key'] for step in sequence]
    if len(set(keys)) != len(keys):
        errors.append('duplicate assembly action key')
    required_actions = ['prepare_holes', 'fix_first_post', 'insert_bottom_rail',
                        'attach_end_channels', 'insert_boards', 'place_top_rail',
                        'engage_second_post', 'fix_second_post', 'glue_caps']
    for key in required_actions:
        if key not in keys:
            errors.append(f'missing assembly action: {key}')
    if set(keys) - set(required_actions):
        errors.append('unsupported assembly actions need explicit simulation handling')
    for before, after in zip(required_actions, required_actions[1:]):
        if before not in keys or after not in keys or keys.index(before) >= keys.index(after):
            errors.append(f'assembly constraint violated: {before} before {after}')
    materials = example.get('installation_materials', [])
    material_names = [item.get('item') for item in materials]
    if (len(set(material_names)) != len(material_names) or
            set(material_names) != {'concrete', 'gravel/filler', 'vinyl adhesive'}):
        errors.append('required installation-material registry is missing or unsupported')
    for item in materials:
        if (item.get('required') is not True or 'purchase_quantity' not in item or
                item['purchase_quantity'] is not None or not item.get('blocker')):
            errors.append('installation material must retain its unresolved quantity and blocker')
    if example.get('complete_installation_order') is not False:
        errors.append('unquantified installation materials prevent a complete order claim')
    simulation = []
    if not errors and 'build_runs' in example:
        trace = {step['key']: step for step in sequence}
        def event(key, **scope):
            result = {'action': 'glue_cap' if key == 'glue_caps' else key,
                      'source_trace_key': key, **scope}
            if 'evidence' in trace[key]:
                result['evidence'] = deepcopy(trace[key]['evidence'])
            if 'action' in trace[key]:
                result['instruction'] = trace[key]['action']
            return result

        bay_ids = {frozenset((b['from'], b['to'])): b.get('id', f'bay_{i}')
                   for i, b in enumerate(example['bays'])}
        for run in example['build_runs']:
            path = run['station_order']
            simulation.append(event('prepare_holes', stations=path[:2], run=run['id']))
            simulation.append(event('fix_first_post', station=path[0], run=run['id']))
            for index, (start, end) in enumerate(zip(path, path[1:])):
                bay = bay_ids[frozenset((start, end))]
                if index:
                    simulation.append(event('prepare_holes', stations=[end], run=run['id']))
                for step in sequence:
                    if step['key'] in required_actions[2:-1]:
                        simulation.append(event(step['key'], bay=bay, run=run['id'],
                                                start_station=start, receiving_station=end))
            simulation.extend(event('glue_caps', station=sid, run=run['id']) for sid in path)
    return {'example_checks_passed': not errors, 'errors': errors,
            'expected_catalog_item_counts': dict(expected),
            'connected_runs': len(components), 'unique_stations': len(roles),
            'kit_contained_u_channels': 2 * len(example['bays']),
            'assembly_simulation': simulation,
            'unresolved_installation_materials': deepcopy(materials),
            'installation_ready': False,
            'limitations': ['Authored example only; no fit or structural verification.',
                            'Retailer packaging/multipacks are not established.',
                            'Installation-material quantities remain unresolved.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('example', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    result = audit(json.loads(args.example.read_text()))
    if args.report:
        with open_write(args.report, encoding='utf-8') as handle:
            json.dump(result, handle, indent=2)
            handle.write('\n')
    print(json.dumps(result, indent=2))
    sys.exit(0 if result['example_checks_passed'] else 1)
