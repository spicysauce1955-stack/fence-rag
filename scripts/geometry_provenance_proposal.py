#!/usr/bin/env python3
"""Private executable review fixture for pending Amendment 008; never admission."""
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fence_evidence.canonical import canonical_bytes, content_hash
from fence_evidence.paths import open_write
from fence_evidence.snapshot import SOURCE_CLASSES, VERSION_STATUSES


# This is a proposed subset, not an adopted registry or a full owner schema.
TARGETS = {
    'Joint': {
        '/channel_depth': {'unit': 'mm', 'nullable': False},
        '/insertion_margin': {'unit': 'mm', 'nullable': True},
        '/shared_host_gap': {'unit': 'mm', 'nullable': True},
    },
    'FromBottom': {'/offset': {'unit': 'mm', 'nullable': False}},
    'FromTop': {'/offset': {'unit': 'mm', 'nullable': False}},
}
OTHER_FIELDS = {'Joint': {'kind', 'gap_reason'}, 'FromBottom': set(), 'FromTop': set()}


def decode_unique(text):
    """Reject duplicate association keys before JSON parsing can erase them."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=pairs)


def validate_owner(kind, owner, source_refs, source_docs):
    """Check only proposed numeric associations and return an unchanged copy.

    Closure here is against synthetic declared references, not rendered corpus
    evidence. Semantic validity, physical fit and publication remain unproved.
    """
    if not isinstance(kind, str) or kind not in TARGETS or not isinstance(owner, dict):
        raise ValueError('unsupported owner')
    targets = TARGETS[kind]
    allowed = {path[1:] for path in targets} | OTHER_FIELDS[kind] | {'field_provenance'}
    if set(owner) - allowed:
        raise ValueError('unsupported owner field')
    associations = owner.get('field_provenance')
    if not isinstance(associations, dict) or set(associations) - set(targets):
        raise ValueError('missing map or undeclared target')
    docs = {doc['content_hash'] for doc in source_docs}
    refs = {(ref['id'], ref['belongs_to']) for ref in source_refs}
    if len(docs) != len(source_docs) or len(refs) != len(source_refs):
        raise ValueError('ambiguous synthetic evidence registry')
    gaps = []
    for path, schema in targets.items():
        key = path[1:]
        if key not in owner:
            raise ValueError('missing explicit target: ' + path)
        value = owner[key]
        if value is None:
            if not schema['nullable'] or path in associations:
                raise ValueError('null is not a numeric reading: ' + path)
            gaps.append({'target': path, 'meaning': 'explicit_null; no numeric default authorized'})
            continue
        if (not isinstance(value, dict) or set(value) != {'amount_milli', 'unit', 'value_raw'}
                or type(value['amount_milli']) is not int or value['amount_milli'] < 0
                or value['unit'] != schema['unit'] or not isinstance(value['value_raw'], list)
                or not value['value_raw'] or not all(isinstance(x, str) and x.strip() for x in value['value_raw'])):
            raise ValueError('wrong target value kind: ' + path)
        provenance = associations.get(path)
        if (not isinstance(provenance, dict)
                or set(provenance) != {'cites', 'source_class', 'curation_level', 'version_status'}
                or not isinstance(provenance['source_class'], str)
                or provenance['source_class'] not in SOURCE_CLASSES
                or type(provenance['curation_level']) is not int
                or provenance['curation_level'] not in (0, 1, 2)
                or not isinstance(provenance['version_status'], str)
                or provenance['version_status'] not in VERSION_STATUSES
                or not isinstance(provenance['cites'], list) or not provenance['cites']):
            raise ValueError('missing or malformed classification: ' + path)
        seen = set()
        for cite in provenance['cites']:
            if (not isinstance(cite, dict) or set(cite) != {'id', 'belongs_to'}
                    or not all(isinstance(v, str) and v for v in cite.values())):
                raise ValueError('malformed SourceRef')
            identity = (cite['id'], cite['belongs_to'])
            if identity in seen or identity not in refs or cite['belongs_to'] not in docs:
                raise ValueError('duplicate or unresolvable synthetic citation')
            seen.add(identity)
    return {'owner': deepcopy(owner), 'null_obligations': gaps}


def examples():
    fixture = json.loads((ROOT / 'workspace/reports/authored-geometry-provenance-example.json').read_text())
    joint = fixture['proposed_owner_fragment']['joint']
    provenance = deepcopy(joint['field_provenance']['/channel_depth'])
    placement = {'offset': {'amount_milli': 88900, 'unit': 'mm',
                            'value_raw': ['3.5 in. (synthetic precision fixture)']},
                 'field_provenance': {'/offset': provenance}}
    return fixture, joint, placement


def build_packet():
    fixture, joint, placement = examples()
    refs, docs = fixture['source_refs'], fixture['source_docs']
    vectors = []
    for kind, owner in [('Joint', joint), ('FromBottom', placement), ('FromTop', placement)]:
        result = validate_owner(kind, decode_unique(canonical_bytes(owner).decode()), refs, docs)
        assert canonical_bytes(result['owner']) == canonical_bytes(owner)
        vectors.append({'case': kind + '_exact_round_trip', 'result': 'preserved',
                        'owner_hash': content_hash(owner), 'null_obligations': result['null_obligations']})
    for case, mutate in (
        ('dropped_map', lambda x: x.pop('field_provenance')),
        ('unknown_target', lambda x: x['field_provenance'].update({'/offset/amount_milli': {}})),
        ('dropped_classification', lambda x: x['field_provenance']['/offset'].pop('source_class')),
        ('lost_precision', lambda x: x['offset'].update(amount_milli=88.9)),
        ('missing_value_default', lambda x: x.pop('offset')),
        ('null_required_value', lambda x: x.update(offset=None)),
        ('unresolvable_citation', lambda x: x['field_provenance']['/offset']['cites'][0].update(id='absent')),
        ('runtime_admission_on_wire', lambda x: x['field_provenance']['/offset'].update(admitted_by='pretend')),
    ):
        owner = deepcopy(placement)
        mutate(owner)
        try:
            validate_owner('FromBottom', owner, refs, docs)
        except ValueError as exc:
            vectors.append({'case': case, 'result': 'refused', 'reason': str(exc)})
        else:
            raise AssertionError('expected refusal: ' + case)
    count = 15
    pitch = Fraction(152400, 1000)
    return {
        'artifact_kind': 'private_amendment_008_disposition_packet',
        'schema_status': 'pending_both_dispositions_and_ratification',
        'publishable': False, 'consumer_adapter_implemented': False,
        'manufacturer_evidence': False,
        'scope': 'Proposed Joint and FromBottom/FromTop numeric associations only; not complete model validation.',
        'target_registry': TARGETS, 'vectors': vectors,
        'example_owners': {'Joint': joint, 'FromBottom': placement},
        'synthetic_source_refs': refs, 'synthetic_source_docs': docs,
        'precision': {'placement_milli_mm': 88900, 'placement_exact_mm': '88.9',
            'synthetic_repeat_count': count, 'synthetic_pitch_milli_mm': 152400,
            'exact_repeated_milli_mm': int(pitch * count * 1000),
            'rounded_input_repeated_milli_mm': 152 * count * 1000,
            'loss_milli_mm': int((pitch - 152) * count * 1000),
            'limitation': 'Nominal board width is not installed pitch. These synthetic arithmetic vectors prove no Emblem fit.'},
        'remaining': [
            'Both teams must disposition Amendment 008 and its target registry; no acceptance is inferred.',
            'Member, PartRequirement, FixingRule, InfillSpec, HeightSupport and other placement variants remain outside this fixture.',
            'A production public adapter must preserve associations and exact arithmetic; this validator is never called by publication.',
            'Joint kind, host relationships, fitting policy and length rules need independently supported semantics.',
            'Null obligations here are private review diagnostics, not implemented public Gap emission.',
        ],
    }


def main():
    packet = build_packet()
    directory = ROOT / 'workspace/reports'
    with open_write(directory / 'emblem-geometry-disposition.json', encoding='utf-8') as output:
        output.write(json.dumps(packet, indent=2) + '\n')
    markdown = (
        '# Private geometry provenance disposition packet\n\n'
        'Amendment 008 remains pending. This packet changes no boundary and authorizes no publication.\n\n'
        'Run `python3 scripts/geometry_provenance_proposal.py` to regenerate the JSON vectors. '
        'The executable fixture checks proposed Joint and FromBottom/FromTop numeric associations, '
        'synthetic reference closure, and unchanged canonical round trips. It is not a consumer adapter '
        'or a complete geometry validator. Other owners and all physical semantics remain unresolved.\n\n'
        'Every present numeric target requires its own complete classification. Explicit optional nulls '
        'retain private gap obligations; they never become zero. An explicitly authored zero is a numeric '
        'value requiring provenance. Unknown targets, missing maps/classifications, fractional milli-units, '
        'missing values, dangling citations and runtime admission fields are refused. Duplicate JSON keys '
        'are refused before parsing erases them.\n\n'
        'The precision vector preserves 88,900 milli-mm (88.9 mm). A separate synthetic 15-repeat '
        '152.4 mm pitch totals 2,286 mm; rounding each input to 152 mm loses 6 mm. These are arithmetic '
        'fixtures, not Emblem placement approval or installed-pitch evidence. Classification preservation '
        'does not excuse rounding before count-producing arithmetic.\n\n'
        'Review together: `docs/integration/amendments/008-authored-geometry-provenance.md`, '
        '`docs/integration/conversation.md` §9b and its preceding rounding evidence, and '
        '`workspace/reports/emblem-geometry-disposition.json`. Both written dispositions and the '
        'existing version-cut procedure remain outstanding.\n')
    with open_write(directory / 'emblem-geometry-disposition.md', encoding='utf-8') as output:
        output.write(markdown)
    print('Private packet regenerated; publication remains disabled.')


if __name__ == '__main__':
    main()
