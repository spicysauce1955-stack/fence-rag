"""Exercise a checked-out Planning consumer without publishing probe payloads.

Run with the consumer's Python environment. This probes the snapshot loader and
private requirement parser separately; neither establishes model/BOM support.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fence_evidence.paths import open_write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--consumer-root', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    root = args.consumer_root.resolve()
    sys.path.insert(0, str(root / 'src'))
    from pydantic import ValidationError
    from fenceai.fencemodel.model import PartRequirement, FenceModel
    from fenceai.fencemodel.lengths import LENGTH_RULES
    from fenceai.knowledge.snapshot import load, ingest, canonical_snapshot_id

    revision = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    raw = json.loads(args.snapshot.read_text())
    loaded, defects = load(raw)
    consumed = ingest(loaded, as_of='2026-09-06', gap_defects=defects)
    package = json.loads(args.model.read_text())
    published_ids = {part.id for part in loaded.parts}
    draft_ids = {part['id'] for part in package['part_fragments']}
    actual_model_errors = []
    try:
        FenceModel.model_validate(package['model_fragment'])
    except ValidationError as exc:
        actual_model_errors = [{'location': list(e['loc']), 'type': e['type'], 'message': e['msg']}
                               for e in exc.errors()]
    actual = deepcopy(raw)
    actual['models'] = [package['model_fragment']]
    actual['snapshot_id'] = canonical_snapshot_id(actual)
    actual_loaded, actual_defects = load(actual)
    actual_result = ingest(actual_loaded, as_of='2026-09-06', gap_defects=actual_defects)
    example = {'part_id': 'probe/rail', 'qty': 1, 'length_rule': 'centre_to_centre'}
    requirement = PartRequirement.model_validate(example)
    refusals = {}
    for label, value in [('unknown_name', 'not_a_registered_rule'),
                         ('quantity_object', {'amount_milli': 1000, 'unit': 'mm', 'value_raw': ['1 mm']})]:
        try:
            PartRequirement.model_validate({**example, 'length_rule': value})
        except ValidationError:
            refusals[label] = True
        else:
            refusals[label] = False

    # A hash-valid, deliberately incomplete model exposes carry-vs-consume.
    # It is never written to the snapshot store or used for generation.
    probe = deepcopy(raw)
    probe['models'] = [{'id': 'probe/not-a-valid-model'}]
    probe['snapshot_id'] = canonical_snapshot_id(probe)
    probe_loaded, probe_defects = load(probe)
    probe_result = ingest(probe_loaded, as_of='2026-09-06', gap_defects=probe_defects)
    try:
        FenceModel.model_validate(probe['models'][0])
    except ValidationError:
        private_model_refused = True
    else:
        private_model_refused = False

    report = {
        'probe_kind': 'consumer_boundary_diagnostic_not_assembly_acceptance',
        'consumer_repository': 'https://github.com/spicysauce1955-stack/BOM',
        'consumer_revision': revision, 'snapshot_id': raw['snapshot_id'],
        'snapshot_loaded': True, 'loaded_parts': len(loaded.parts),
        'loaded_part_types': len(loaded.part_types), 'gap_defects': defects,
        'part_defects': consumed.part_defects, 'unconsumed': consumed.unconsumed,
        'inactive_parts': consumed.inactive_parts,
        'published_part_spec_counts': {part.id: len(part.spec) for part in loaded.parts},
        'draft_part_ids_present': sorted(draft_ids & published_ids),
        'draft_part_ids_missing': sorted(draft_ids - published_ids),
        'actual_model_probe': {'private_parser_errors': actual_model_errors,
                               'unconsumed': actual_result.unconsumed},
        'private_requirement_example': example,
        'private_requirement_roundtrip': requirement.model_dump(),
        'registered_length_rules': list(LENGTH_RULES.names()),
        'length_rule_refusals': refusals,
        'invalid_model_probe': {'snapshot_loader_accepted': True,
                                'private_model_parser_refused': private_model_refused,
                                'unconsumed': probe_result.unconsumed},
        'published_models_consumed': False,
        'bom_generation_verified': False,
        'limitations': ['Internal parser shape is not a published-model wire contract.',
                        'The example tests syntax; it does not select an Emblem rail length rule.',
                        'Loaded Part identity does not establish catalog matching or BOM consumption.'],
    }
    if not (all(refusals.values()) and private_model_refused
            and probe_result.unconsumed.get('models') == 1):
        raise RuntimeError('Consumer behavior changed; reassess the adapter boundary before recording success.')
    if defects or consumed.part_defects:
        raise RuntimeError('Snapshot has Part or gap defects; inspect the consumer errors before recording success.')
    with open_write(args.report) as handle:
        json.dump(report, handle, indent=2)
        handle.write('\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
