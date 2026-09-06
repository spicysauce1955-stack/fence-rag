"""Prepare an explicitly incomplete private Planning model for author review.

Run with Planning's Python environment. This does not publish a Snapshot or
apply private parser defaults as source facts. Rail placements require input.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fence_evidence.canonical import content_hash
from fence_evidence.paths import open_write


def prepare(package):
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
    return {
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--consumer-root', type=Path, required=True)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.consumer_root.resolve() / 'src'))
    from pydantic import ValidationError
    from fenceai.fencemodel.model import FenceModel, PartRequirement
    from fenceai.knowledge.ast import evaluate_expr
    result = prepare(json.loads(args.package.read_text()))
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
        FenceModel.model_validate(result['model'])
    except ValidationError as exc:
        errors = [{'location': list(e['loc']), 'message': e['msg']} for e in exc.errors()]
    else:
        errors = []
    report = {
        'consumer_revision': subprocess.check_output(
            ['git', '-C', str(args.consumer_root), 'rev-parse', 'HEAD'], text=True).strip(),
        'post_requirement_parses': True, 'post_role_matrix': matrix,
        'private_model_parser_errors': errors, 'whole_model_parses': not errors,
        'placement_confirmed': False, 'bom_generation_verified': False,
    }
    for path, value in [(args.output, result), (args.report, report)]:
        with open_write(path) as handle:
            json.dump(value, handle, indent=2)
            handle.write('\n')
    print(json.dumps(report, indent=2))
    return 2 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
