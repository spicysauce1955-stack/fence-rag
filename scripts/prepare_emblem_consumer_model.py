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
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fence_evidence.canonical import content_hash
from fence_evidence.paths import open_write


def prepare(package, placement_confirmation=None):
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
            'infill fitting policies', 'rail, board and cap quantity defaults',
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
    positions, semantic_errors, unconsumed = {}, [], []
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
    report = {
        'consumer_revision': subprocess.check_output(
            ['git', '-C', str(args.consumer_root), 'rev-parse', 'HEAD'], text=True).strip(),
        'post_requirement_parses': True, 'post_role_matrix': matrix,
        'private_model_parser_errors': errors, 'whole_model_parses': not errors,
        'candidate_hash': content_hash(result),
        'partial_semantic_validation': {
            'executed': not errors, 'errors': semantic_errors,
            'catalog_basis': 'empty diagnostic fixture, not supplier evidence',
            'part_library_basis': 'absent; Part-dependent checks skipped',
        },
        'unconsumed_authored_paths': unconsumed,
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
