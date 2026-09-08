"""Private diagnostic transformation of the Pembroke 6x6 model draft into the
consumer's authored-document dialect. NOT the production route: this mirrors
scripts/prepare_augusta_consumer_model.py. It records transformation evidence
separately and refuses to invent missing geometry: null receiving depths stay
absent in the consumer shape (declared=0 / undeclared), never defaulted.

The consumer FenceModel dialect differs from the producer preflight shape:
placement uses offset_mm ints, joint is a string kind, requirement qty is an
int, and engagements default to 0 (undeclared) rather than Quantity objects.

Unlike the Augusta three-rail panel, this two-rail panel has ONE picket run:
the consumer's single-cycle infill expresses it fully, and no infill member is
withheld. The two u-channel segments map as two handed edge bindings on the
single run's first/last members, covering the whole authored count.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fence_evidence.canonical import content_hash
from fence_evidence.paths import open_write

DRAFT = ROOT / 'workspace/catalog/pembroke-6x6-model-draft.json'
OUT = ROOT / 'workspace/catalog/pembroke-6x6-consumer-model.json'


def main():
    package = json.loads(DRAFT.read_text())
    fragment = package['model_fragment']

    precision_losses = []

    # The consumer's placement `offset_mm` is the member's CENTERLINE (consumer
    # resolve.py _between_frame_extent: "a placement gives a member's
    # centreline"); the draft authors centerlines in exact milli-mm. The
    # conversion is unitary (milli-mm -> mm); a value that is not a whole
    # millimetre floors with the loss recorded, exactly like the height —
    # never silently truncated and never refused (the draft's 5.5in envelope
    # halves to 69.85mm, which is exact only in milli-mm).
    def offset_mm(placement):
        amount = placement['offset']['amount_milli']
        if amount % 1000:
            precision_losses.append({'field': 'placement/offset',
                                     'value_raw': placement['offset']['value_raw'][0],
                                     'exact_mm': amount / 1000,
                                     'published_mm': amount // 1000,
                                     'loss_mm': (amount % 1000) / 1000})
        return amount // 1000

    # Quantities (counts) convert by exact division: a fractional count is a
    # refusal, never a silent zero or truncation (a count is exact knowledge,
    # unlike a measured length).
    def count_mm(quantity_object):
        amount = quantity_object['amount_milli']
        if amount % 1000:
            raise ValueError('quantity is not a whole count: '
                             + str(amount) + ' milli-each')
        return amount // 1000

    def floored_mm(quantity_object, field, path):
        # milli-mm -> mm floor with the loss recorded (lengths and placements).
        amount = quantity_object['amount_milli']
        if amount % 1000:
            precision_losses.append({'field': field,
                                     'value_raw': quantity_object['value_raw'][0],
                                     'exact_mm': amount / 1000,
                                     'published_mm': amount // 1000,
                                     'loss_mm': (amount % 1000) / 1000})
        return amount // 1000

    frame = []
    placement_notes = []
    # The two-rail panel's frame is pinned: exactly 2 rails, each requirement
    # qty 1, zero overlap. A hand-edited draft with a different structure
    # (extra rails, doubled quantities, nonzero overlap) must refuse rather
    # than transform silently — the downstream pins catch offsets/heights/
    # patterns, not frame shape.
    draft_frame = fragment['default_spec']['frame']
    if len(draft_frame) != 2:
        raise ValueError('Pembroke 6x6 draft must author exactly 2 rails: '
                         + str(len(draft_frame)) + ' frame slots')
    for slot in draft_frame:
        qty = count_mm(slot['requirement']['qty'])
        if qty != 1:
            raise ValueError('Pembroke 6x6 rail requirement qty must be 1: ' + str(qty))
        overlap = slot['requirement']['overlap']['amount_milli']
        if overlap != 0:
            raise ValueError('Pembroke 6x6 rail requirement overlap must be 0, not '
                             + str(overlap) + ' (the draft records no overlap; a nonzero '
                             'overlap is unsupported and must not be silently dropped)')
    for slot in draft_frame:
        offset_value = offset_mm(slot['placement'])
        frame.append({
            'key': slot['key'],
            'orientation': slot['orientation'],
            'placement': {'kind': 'from_bottom', 'offset_mm': offset_value},
            # RAILS SLIDE INTO ROUTED POST SOCKETS (master install: "Slide the
            # bottom rail ... and top rail into post A"), they are not
            # bracket-mounted. The consumer's routed-rail path needs a
            # PostSlot.receiving_joint, which the candidate does not author
            # (no source states post socket depth); clear_between_posts alone
            # would undercount the known 71.5in rail stock by the socket
            # engagement. Recorded as a limitation below; the length rule
            # stays clear_between_posts because it is the registry rule the
            # routed path extends, and no invented engagement is added.
            'requirement': {'part_id': slot['requirement']['part_id'], 'qty': 1,
                            'length_rule': 'clear_between_posts'},
            # Receiving geometry is absent from all retained sources; the
            # consumer dialect declares it as 0/undeclared, never invented.
            'channel_depth_mm': 0,
            'insertion_margin_mm': 0,
            'joint': slot['joint']['kind'],
        })
        placement_notes.append({
            'slot': slot['key'],
            'offset_mm': offset_value,
            'basis': slot['placement']['offset']['value_raw'][0],
            'classification': 'drawing-derived authored placement (centerline); unconfirmed datum'})

    # A two-rail panel has ONE picket run between bottom_rail and top_rail:
    # the consumer's single repeating member cycle expresses it fully, and
    # nothing here needs the Augusta batch's consumer_infill_single_cycle
    # withholding.
    members = fragment['default_spec']['infill']['pattern']
    if len(members) != 1:
        raise ValueError('Pembroke 6x6 draft must author exactly one picket run: '
                         + str(len(members)) + ' members')
    run = members[0]
    # PATTERN-MEMBER qty is CYCLE-REPEAT semantics in the consumer dialect: a
    # pattern member with qty=1 repeats to fill the axis, and handed edge
    # bindings require qty==1 on the bound member (validate_model: "handed
    # binding cannot select multiple pieces per position"). The manufacturer's
    # kit count 6 lives in the draft and the dataset, where it is cited
    # inventory, not a consumer cycle multiplier; the axis length reproduces
    # the count only when real picket width and pitch resolve (still
    # undeclared).
    pattern = [{
        'key': run['key'],
        'base_ref': run['base_ref'],
        'top_ref': run['top_ref'],
        # A picket run member sits between two frame slots: measured
        # against the placed frame (between_frame), not panel_height.
        'requirement': {'part_id': run['requirement']['part_id'],
                        'length_rule': 'between_frame', 'qty': 1},
        'profile_edges': run['profile_edges'],
        'joint': run['joint']['kind'],
    }]
    mapped_keys = {run['key']}
    withheld_mappings = []
    for member in members:
        if member['key'] in mapped_keys:
            continue
        withheld_mappings.append({
            'path': f"/model/default_spec/infill/pattern/{member['key']}",
            'draft_base_ref': member['base_ref'],
            'draft_top_ref': member['top_ref'],
            'code': 'consumer_infill_single_cycle',
            'reason': ('the consumer infill fits one repeating member cycle per panel '
                       '(fit.py: member_widths_mm[i % len(pattern)]); two stacked rows between '
                       'different rail pairs cannot be expressed without alternating across the width'),
            'would_close': ('consumer support for per-row span derivation from each member\'s '
                            'base_ref/top_ref, or a multi-row infill capability'),
            'closes_by': 'planning',
            'recorded_in': ['draft model_fragment (both rows)',
                           'dataset composition (both runs, u-channel basis)'],
        })

    # U-channel fixings follow the Emblem/Augusta edge_binding shape: two
    # per_panel fixings for the SINGLE run (first picket/tongue, last
    # picket/groove), each binding exactly one piece (consumer validation:
    # "handed binding requires exactly one per-panel piece"), so the consumer
    # draws them on the actual end members instead of a count at the panel
    # centre. The draft's count (2 installed segments = first and last picket
    # of the single run) is fully mapped: 2 edge bindings == authored 2.
    fixings = []
    for fixing in fragment['default_spec']['fixings']:
        per_panel = count_mm(fixing['qty_per_basis'])
        requirement_qty = count_mm(fixing['requirement']['qty'])
        if per_panel != 2 or requirement_qty != 2:
            raise ValueError('u-channel fixing count is not the authored 2 installed segments: '
                             + str(per_panel) + '/' + str(requirement_qty))
        fixings.append({
            'key': fixing['key'] + '_first',
            'basis': 'per_panel',
            'qty_per_basis': 1,
            'edge_binding': {'member_key': run['key'], 'position': 'first',
                             'profile_edge': run['profile_edges']['start']},
            'requirement': {'part_id': fixing['requirement']['part_id'], 'qty': 1},
        })
        fixings.append({
            'key': fixing['key'] + '_last',
            'basis': 'per_panel',
            'qty_per_basis': 1,
            'edge_binding': {'member_key': run['key'], 'position': 'last',
                             'profile_edge': run['profile_edges']['end']},
            'requirement': {'part_id': fixing['requirement']['part_id'], 'qty': 1},
        })

    def height_mm(quantity_object):
        return floored_mm(quantity_object, 'height', 'height_support')

    if fragment.get('post') is not None:
        post = {
            'key': 'post',
            'requirement': {'part_id': fragment['post']['requirement']['part_id'],
                            'qty': count_mm(fragment['post']['requirement']['qty'])},
        }
    else:
        # The draft authors no post opinion; the candidate carries none either.
        post = None
    # The public PostSlot shape refuses a bare joint; the receiving geometry
    # (rail-socket depth in the post) is absent from all retained sources, so
    # any post present carries no receiving_joint rather than an invented one.
    # The routed-rail length path (ReceivingPostJoint) is therefore unreachable,
    # which is why the rail length limitation below is recorded rather than fixed.

    model = {
        'id': fragment['id'],
        'version': 1,
        'status': 'draft',
        'name_i18n': fragment['name_i18n'],
        'authorship': 'third_party_authored',
        'grade': fragment['grade'],
        'height_support': {'kind': 'discrete',
                           'heights_mm': [height_mm(h) for h in fragment['height_support']['heights']]},
        'option_axes': [],
        'variants': [],
        'layout_policy': [],
        'assembly': [],
        'default_spec': {
            'frame': frame,
            'infill': {
                'orientation': fragment['default_spec']['infill']['orientation'],
                'justification': fragment['default_spec']['infill']['justification'],
                # trim_last needs 2D cutting the planner does not support, and
                # no source states an end-fitting policy: the honest policy is
                # to leave the run as-is and let u-channels cover end gaps.
                'excess': 'space',
                'edge_margin_mm': floored_mm(fragment['default_spec']['infill']['edge_margin'],
                                              'infill/edge_margin', 'infill/edge_margin'),
                'supply': fragment['default_spec']['infill']['supply'],
                'pattern': pattern,
            },
            'fixings': fixings,
        },
        'post': post,
        'cites': fragment['cites'],
        'contributing_sources': fragment['contributing_sources'],
    }
    excess_substitution = {
        'field': 'default_spec/infill/excess',
        'draft_value': fragment['default_spec']['infill']['excess'],
        'candidate_value': 'space',
        'reason': ('the producer profile supports trim_last (cut the final member to fit), but 2D '
                   'trimming is not a supported consumer cut and no source states an end-fitting '
                   'policy; the honest policy leaves the run as-is and lets u-channels cover end '
                   'gaps (master install). The authored draft value is preserved in the draft and '
                   'recorded here; it is not silently dropped.'),
    }

    out = {
        'artifact_kind': 'private_consumer_model_candidate',
        'source_package_hash': content_hash(package),
        'model': model,
        'publishable': False,
        'installation_ready': False,
        'bom_generation_verified': False,
        'transformation_evidence': {
            'placements': placement_notes,
            'placement_datum': (
                'the draft authors rail CENTERLINES (consumer placement semantics; the section '
                'chain gives 5.5in envelope boundaries, halved to centerlines); the Emblem '
                'candidate established the same convention (from_bottom 88.9mm = half its 7in envelope)'),
            'unit_conversions': [
                'draft Quantity objects carry integer thousandths of a millimetre; the consumer Mm is integer millimetres.',
                'Counts (qty, qty_per_basis) convert by exact division: a fractional count REFUSES, never silently truncates.',
                'Lengths and placements floor to whole millimetres with every loss recorded in precision_losses below.',
            ],
            'precision_losses': precision_losses,
            'authored_field_substitutions': [excess_substitution],
            'private_defaults_are_not_source_facts': [
                'channel_depth_mm and insertion_margin_mm: 0 = undeclared, absent from all retained sources',
                'picket engagements: undeclared; a between_frame cut length without engagements is face-to-face only',
                'picket pattern qty=1 is consumer cycle semantics (the pattern repeats to fill the run; handed edge bindings require qty 1); the manufacturer kit count 6 lives in the draft and dataset as cited inventory',
                'rail placements are drawing-derived authored choices from the section chain (5.5 + 61 + 5.5 = 72); datum unconfirmed',
            ],
            'withheld_from_consumer_shape': [
                'all null receiving depths from the producer draft (stayed absent, never defaulted)',
                'per-panel quantity Tokens (counts live in the dataset and the publication report, not the consumer model)',
            ],
        },
        'limitations': package['measurement_limits'] + [
            'Rail length rule: the sources state rails slide INTO routed post sockets, and the draft '
            'knows the 71.5in rail stock, but the consumer\'s routed-rail length path requires a '
            'PostSlot.receiving_joint (post socket depth), which no retained source states and this '
            'candidate does not author. clear_between_posts is therefore published as the registry rule '
            'the routed path extends — with NO invented socket engagement — and any future resolved cut '
            'length will undercount the known stock until a receiving joint is authored from real evidence.',
            'This candidate is a diagnostic input for consumer validation, not the production route.',
            'Consumer validation of this candidate does not admit any FenceModel to the published snapshot.',
        ],
        # Mapping completeness: this two-rail panel has one run, so every draft
        # infill member maps (nothing withheld) and the draft fixing count is
        # fully accounted (2 mapped edge bindings == authored 2). Enforced by
        # the generator and by tests; a silent drop is structurally impossible
        # if these invariants hold.
        'withheld_mappings': withheld_mappings,
        'mapping_completeness': {
            'draft_member_keys': sorted(m['key'] for m in members),
            'mapped_member_keys': sorted(m['key'] for m in pattern),
            'withheld_member_keys': sorted(w['path'].rsplit('/', 1)[-1]
                                           for w in withheld_mappings
                                           if w['path'].startswith('/model/default_spec/infill/')),
            'complete': sorted(m['key'] for m in members)
                        == sorted([m['key'] for m in pattern]
                                  + [w['path'].rsplit('/', 1)[-1] for w in withheld_mappings
                                     if w['path'].startswith('/model/default_spec/infill/')]),
            'draft_u_channel_segments': 2,
            'mapped_u_channel_segments': sum(f['qty_per_basis'] for f in fixings),
            'withheld_u_channel_segments': 0,
            'fixing_count_complete': sum(f['qty_per_basis'] for f in fixings) == 2,
        },
        # Capability claims, explicit and asserted by code, not prose: nothing
        # in this batch validates assembly, fitting, cutting or purchasing.
        # The consumer checks prove ingestion, dialect fidelity and honest
        # refusals only. These flags stay false until a future batch runs the
        # corresponding real consumer behavior against real geometry.
        'capability_validation': {
            'assembly': {'validated': False,
                         'why': 'no FenceModel admitted (Amendment 008 pending) and no procedures published (step reviews outstanding)'},
            'fitting': {'validated': False,
                        'why': 'receiving geometry absent from all retained sources; engagements and channel depths undeclared'},
            'cutting': {'validated': False,
                        'why': ('cut lengths need engagements and socket depths, all undeclared; a resolved between_frame '
                                'length today is face-to-face only, not a seated-piece cut')},
            'purchasing': {'validated': False,
                           'why': 'installed per-panel counts are manufacturer-stated kit inventory for this configuration, but post counts, channel stock lengths beyond the kit entry and multi-panel purchase quantities are not source-stated'},
        },
    }
    if not out['mapping_completeness']['complete']:
        raise ValueError('draft infill members are neither mapped nor withheld: '
                         + json.dumps(out['mapping_completeness']))
    if not out['mapping_completeness']['fixing_count_complete']:
        raise ValueError('u-channel segments are neither mapped nor withheld: '
                         + json.dumps(out['mapping_completeness']))
    with open_write(OUT) as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write('\n')
    print(json.dumps({'candidate': str(OUT.relative_to(ROOT)), 'model_id': model['id']}))


if __name__ == '__main__':
    main()