"""Conservative authored-model admission; never promotes draft review assertions.

This is a producer preflight, not a public-model adapter or a physical-fit proof.
Reviews must come from a caller-owned trusted ledger, not the candidate payload.
Every used Part is included in the review digest. Unsupported authoring branches
are refused rather than accepted through consumer defaults.
"""
import copy
from fence_evidence.canonical import content_hash as canonical_content_hash
from datetime import datetime


def content_hash(record, parts):
    """Bind authored model, field evidence and entire referenced Part definitions."""
    refs = set()
    def walk(node):
        if isinstance(node, dict):
            if isinstance(node.get('part_id'), str) and node['part_id']:
                refs.add(node['part_id'])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    model = record.get('model', record.get('model_fragment', {}))
    walk(model)
    selected = [p for p in parts if isinstance(p, dict)
                and isinstance(p.get('id'), str) and p['id'] in refs]
    payload = {'model': model, 'field_evidence': record.get('field_evidence', {}),
               'parts': sorted(selected, key=lambda p: (p['id'], canonical_content_hash(p)))}
    return canonical_content_hash(payload)


def admit_authored_models(records, *, parts, source_docs, source_refs, reviews,
                          model_validator=None):
    """Return ``models`` and private ``exclusions``; no mutation or ledger writes.

    Record: {model, field_evidence: {JSON-pointer: [SourceRef]}}. A trusted review
    needs content_hash, decision=accepted, reviewer_kind=human, reviewer,
    reviewed_at (ISO datetime), and review_id. Latest review wins per digest.
    A human's acceptance attests source interpretation; this function cannot.
    """
    models, exclusions = [], []
    part_map = {p.get('id'): p for p in parts if isinstance(p, dict) and isinstance(p.get('id'), str)}
    duplicate_parts = set()
    part_ids = set()
    for part in parts:
        if isinstance(part, dict) and isinstance(part.get('id'), str):
            if part['id'] in part_ids:
                duplicate_parts.add(part['id'])
            part_ids.add(part['id'])
    docs = {d.get('content_hash') for d in source_docs if isinstance(d, dict) and isinstance(d.get('content_hash'), str)}
    known_refs = {(r.get('id'), r.get('belongs_to')) for r in source_refs
                  if isinstance(r, dict) and isinstance(r.get('id'), str)
                  and isinstance(r.get('belongs_to'), str)}
    identity_counts = {}
    for record in records:
        if isinstance(record, dict):
            model = record.get('model', record.get('model_fragment', {}))
            mid = model.get('id') if isinstance(model, dict) else None
            if isinstance(mid, str):
                identity_counts[mid] = identity_counts.get(mid, 0) + 1
    for record in records:
        issues = []
        def fail(path, code, message):
            issues.append({'path': path, 'code': code, 'message': message})
        if duplicate_parts:
            fail('/parts', 'duplicate_part_identity', 'Part library contains ambiguous duplicate IDs: ' + ', '.join(sorted(duplicate_parts)))
        if not isinstance(record, dict):
            exclusions.append({'model_id': None, 'content_hash': None,
                               'issues': [{'path': '/', 'code': 'invalid_shape', 'message': 'Record must be an object.'}],
                               'would_close': 'Supply an authored model record.'})
            continue
        model = record.get('model', record.get('model_fragment', {}))
        if not isinstance(model, dict):
            model = {}
            fail('/model', 'invalid_shape', 'Model must be an object.')
        try:
            digest = content_hash(record, parts)
        except (TypeError, ValueError):
            digest = None
            fail('/', 'invalid_json', 'Record must contain finite JSON data.')
        evidence = record.get('field_evidence', {})
        if not isinstance(evidence, dict):
            evidence = {}
            fail('/field_evidence', 'invalid_shape', 'Field evidence must be an object.')
        def cited(cites, path):
            if not isinstance(cites, list) or not cites:
                fail(path, 'uncited', 'Nonempty source citations are required.')
                return
            for cite in cites:
                if (not isinstance(cite, dict) or not isinstance(cite.get('id'), str)
                        or not isinstance(cite.get('belongs_to'), str)
                        or (cite['id'], cite['belongs_to']) not in known_refs
                        or cite['belongs_to'] not in docs):
                    fail(path, 'citation_closure', 'Citation must resolve to a supplied SourceRef and SourceDoc.')
        def check_tree(node, path):
            if isinstance(node, dict):
                if 'belongs_to' in node:
                    cited([node], path)
                for key, value in node.items():
                    check_tree(value, path + '/' + str(key))
            elif isinstance(node, list):
                for i, value in enumerate(node):
                    check_tree(value, path + '/' + str(i))
            elif isinstance(node, float):
                fail(path, 'float_forbidden', 'Public model quantities use integer thousandths, never floats.')
        check_tree(model, '')
        def field(node, key, path):
            full = path + '/' + key
            if key not in node:
                fail(full, 'missing_value', 'Explicit authored value required; no consumer default is evidence.')
                return None
            cited(evidence.get(full), full)
            return node[key]
        def quantity(value, path, unit='mm', positive=False, signed=False):
            if (not isinstance(value, dict) or type(value.get('amount_milli')) is not int
                    or value.get('unit') != unit or not isinstance(value.get('value_raw'), list)
                    or not value['value_raw'] or not all(isinstance(x, str) and x.strip() for x in value['value_raw'])):
                fail(path, 'invalid_quantity', 'A cited integer-milli Quantity with raw reading is required.')
                return None
            n = value['amount_milli']
            if (n < 0 and not signed) or (positive and n == 0):
                fail(path, 'invalid_quantity', 'Quantity is outside the supported nonnegative range.')
                return None
            return n
        def requirement(req, path, needs_length=False):
            if not isinstance(req, dict):
                fail(path, 'missing_requirement', 'Explicit PartRequirement required.')
                return
            if req.get('contained') or req.get('contains') or req.get('credits'):
                fail(path, 'unsupported_requirement_contents', 'Requirement contents and credits need transitive validation.')
            pid = req.get('part_id')
            if not isinstance(pid, str) or pid not in part_map:
                fail(path + '/part_id', 'unresolved_part', 'This profile requires a published literal Part ID.')
            if req.get('role') or req.get('eligibility') or req.get('option_axis') or req.get('sku_by_option'):
                fail(path, 'unsupported_requirement', 'Part identity cannot also author role, matching or options.')
            n = quantity(field(req, 'qty', path), path + '/qty', 'each', True)
            if n is not None and n % 1000:
                fail(path + '/qty', 'fractional_count', 'Assembly counts must be whole items.')
            lr = field(req, 'length_rule', path)
            if lr not in (None, 'between_frame', 'centre_to_centre', 'clear_between_posts', 'overlap', 'panel_height') or (needs_length and lr is None):
                fail(path + '/length_rule', 'invalid_length_rule', 'Explicit supported length rule required for this member.')
            quantity(field(req, 'overlap', path), path + '/overlap')
            if isinstance(pid, str) and pid in part_map:
                if part_map[pid].get('contains') or part_map[pid].get('contained'):
                    fail(path + '/part_id', 'unsupported_part_contains', 'Contained Part references require transitive review binding; this profile refuses them.')
                if part_map[pid].get('status') != 'active':
                    fail(path + '/part_id', 'inactive_part', 'Referenced Part must be explicitly active.')
                specs = part_map[pid].get('spec', [])
                if not isinstance(specs, list) or not specs or any(not isinstance(sf, dict) for sf in specs):
                    fail(path + '/part_id', 'missing_part_dimensions', 'Identity-only Part cannot establish physical geometry.')
                for spec in specs if isinstance(specs, list) else []:
                    if isinstance(spec, dict):
                        provenance = spec.get('provenance')
                        cited(provenance.get('cites') if isinstance(provenance, dict) else None, path + '/part/spec')
        def joint(node, path):
            if not isinstance(node, dict):
                fail(path, 'missing_joint', 'Explicit Joint object required.')
                return None, None
            kind = field(node, 'kind', path)
            if kind not in ('butt', 'channel', 'groove', 'bracket', 'overlap'):
                fail(path, 'invalid_joint', 'Unsupported joint kind.')
            depth = quantity(field(node, 'channel_depth', path), path + '/channel_depth', positive=kind in ('channel', 'groove'))
            margin = quantity(field(node, 'insertion_margin', path), path + '/insertion_margin')
            if node.get('contains'):
                fail(path, 'unsupported_contains', 'Contained assembly requires a dedicated validator.')
            return depth, margin
        mid = model.get('id')
        if not isinstance(mid, str) or not mid:
            fail('/id', 'missing_identity', 'Model identity required.')
        elif identity_counts.get(mid, 0) > 1:
            fail('/id', 'duplicate_identity', 'Only one definition per model ID may be admitted.')
        for key in ('version', 'status', 'name_i18n', 'authorship', 'grade', 'height_support', 'option_axes', 'variants', 'layout_policy', 'assembly', 'post', 'contributing_sources'):
            if key not in model:
                fail('/' + key, 'missing_value', 'Required model field is absent.')
        for key in ('option_axes', 'variants', 'layout_policy', 'assembly'):
            if not isinstance(model.get(key), list):
                fail('/' + key, 'invalid_shape', 'Explicit list required.')
        for key in ('version', 'authorship'):
            if not isinstance(model.get(key), str) or not model[key].strip():
                fail('/' + key, 'invalid_shape', 'Nonempty authored string required.')
        if not isinstance(model.get('name_i18n'), dict) or not model['name_i18n']:
            fail('/name_i18n', 'invalid_shape', 'Nonempty localized name required.')
        if not isinstance(model.get('height_support'), dict) or not model['height_support']:
            fail('/height_support', 'missing_value', 'Explicit height support required.')
        if model.get('authorship') != 'third_party_authored':
            fail('/authorship', 'unsupported_authorship', 'This producer authors third-party definitions; manufacturer approval requires a separate authenticated path.')
        if model.get('status') != 'active':
            fail('/status', 'inactive_model', 'Only explicitly active models may be admitted.')
        if field(model, 'grade', '') not in ('residential', 'commercial', 'industrial'):
            fail('/grade', 'invalid_grade', 'Explicit supported grade required.')
        height = field(model, 'height_support', '')
        if not isinstance(height, dict) or height.get('kind') != 'discrete' or not isinstance(height.get('heights'), list) or not height['heights']:
            fail('/height_support', 'unsupported_height_support', 'This profile requires explicit discrete supported heights.')
        else:
            for i, value in enumerate(height['heights']):
                quantity(value, '/height_support/heights/' + str(i), positive=True)
        if model.get('assembly'):
            fail('/assembly', 'unsupported_assembly', 'Nonempty assembly procedures require a dedicated validator.')
        if model.get('variants') or model.get('option_axes') or model.get('layout_policy'):
            fail('/', 'unsupported_branch', 'Variant, option and policy authoring needs a dedicated validator.')
        cited(model.get('cites'), '/cites')
        contributions = model.get('contributing_sources')
        if (not isinstance(contributions, list) or not contributions
                or any(not isinstance(h, str) or h not in docs for h in contributions)):
            fail('/contributing_sources', 'citation_closure', 'Nonempty source roll-up must resolve.')
        spec = model.get('default_spec')
        if not isinstance(spec, dict):
            spec = {}
            fail('/default_spec', 'missing_spec', 'Explicit panel spec required.')
        frame = spec.get('frame')
        frames = {}
        if not isinstance(frame, list) or not frame:
            fail('/default_spec/frame', 'empty_frame', 'A nonempty frame is required by this profile.')
            frame = []
        for i, slot in enumerate(frame):
            path = '/default_spec/frame/' + str(i)
            if not isinstance(slot, dict):
                fail(path, 'invalid_shape', 'Frame slot must be an object.')
                continue
            key = slot.get('key')
            if not isinstance(key, str) or not key or key in frames:
                fail(path, 'invalid_key', 'Unique nonempty slot key required.')
            else:
                frames[key] = joint(slot.get('joint'), path + '/joint')
            if field(slot, 'orientation', path) not in ('horizontal', 'vertical'):
                fail(path, 'invalid_orientation', 'Explicit orientation required.')
            placement = field(slot, 'placement', path)
            if not isinstance(placement, dict) or placement.get('kind') not in ('from_bottom', 'from_top'):
                fail(path + '/placement', 'unsupported_placement', 'This profile requires an explicit edge offset.')
            else:
                quantity(placement.get('offset'), path + '/placement/offset')
            requirement(slot.get('requirement'), path + '/requirement', True)
            if slot.get('contains'):
                fail(path, 'unsupported_contains', 'Contained assembly requires a dedicated validator.')
        infill = spec.get('infill')
        if not isinstance(infill, dict):
            infill = {}
            fail('/default_spec/infill', 'missing_infill', 'This profile requires an explicit infill.')
        path = '/default_spec/infill'
        for key, allowed in [('orientation', ('vertical', 'horizontal')), ('justification', ('start', 'end', 'center')), ('excess', ('trim_last', 'truncate')), ('supply', ('components', 'assembly'))]:
            if field(infill, key, path) not in allowed:
                fail(path + '/' + key, 'unsupported_fitting', 'Explicit supported fitting policy required.')
        quantity(field(infill, 'edge_margin', path), path + '/edge_margin')
        pattern = infill.get('pattern')
        if not isinstance(pattern, list) or not pattern:
            fail(path + '/pattern', 'empty_pattern', 'A nonempty infill pattern is required.')
            pattern = []
        member_keys = set()
        for i, member in enumerate(pattern):
            p = path + '/pattern/' + str(i)
            if not isinstance(member, dict):
                fail(p, 'invalid_shape', 'Member must be an object.')
                continue
            key = member.get('key')
            if not isinstance(key, str) or not key or key in member_keys:
                fail(p + '/key', 'invalid_key', 'Unique nonempty member key required.')
            else:
                member_keys.add(key)
            for side in ('base', 'top'):
                ref = member.get(side + '_ref')
                engagement = quantity(field(member, side + '_engagement', p), p + '/' + side + '_engagement', positive=True)
                if not isinstance(ref, str) or ref not in frames:
                    fail(p + '/' + side + '_ref', 'unresolved_slot', 'Member must reference its supporting frame.')
                else:
                    depth, margin = frames[ref]
                    if None not in (depth, margin, engagement) and engagement + margin > depth:
                        fail(p, 'engagement_exceeds_channel', 'Engagement plus insertion margin exceeds receiving depth.')
            quantity(field(member, 'gap_after', p), p + '/gap_after', signed=True)
            quantity(field(member, 'face_offset', p), p + '/face_offset', signed=True)
            edges = field(member, 'profile_edges', p)
            if (not isinstance(edges, dict) or set(edges) != {'start', 'end'}
                    or any(value not in ('tongue', 'groove', 'square', 'ship_lap', 'none') for value in edges.values())):
                fail(p + '/profile_edges', 'invalid_edges', 'Explicit start and end profile edges are required.')
            requirement(member.get('requirement'), p + '/requirement', True)
            if member.get('contains'):
                fail(p, 'unsupported_contains', 'Contained assembly requires a dedicated validator.')
        fixings = spec.get('fixings')
        if not isinstance(fixings, list):
            fail('/default_spec/fixings', 'missing_value', 'Explicit fixing list required.')
            fixings = []
        fixing_keys = set()
        for i, fixing in enumerate(fixings):
            p = '/default_spec/fixings/' + str(i)
            if not isinstance(fixing, dict) or fixing.get('basis') != 'per_panel':
                fail(p, 'unsupported_fixing', 'This profile validates only per-panel fixings.')
                continue
            key = fixing.get('key')
            if not isinstance(key, str) or not key or key in fixing_keys:
                fail(p + '/key', 'invalid_key', 'Unique nonempty fixing key required.')
            else:
                fixing_keys.add(key)
            quantity(field(fixing, 'qty_per_basis', p), p + '/qty_per_basis', 'each', True)
            requirement(fixing.get('requirement'), p + '/requirement')
        post = model.get('post')
        if not isinstance(post, dict):
            fail('/post', 'missing_post', 'This profile requires a complete post definition.')
        else:
            requirement(post.get('requirement'), '/post/requirement')
            joint(post.get('joint'), '/post/joint')
            if post.get('cap') is not None:
                requirement(post['cap'], '/post/cap')
            if post.get('contains'):
                fail('/post', 'unsupported_contains', 'Contained post components need a dedicated validator.')
        eligible = []
        for review in reviews:
            if not isinstance(review, dict) or review.get('content_hash') != digest:
                continue
            try:
                stamp = datetime.fromisoformat(review['reviewed_at'].replace('Z', '+00:00'))
                if stamp.tzinfo is None:
                    raise ValueError('timezone required')
                eligible.append((stamp, str(review.get('review_id', '')), review))
            except (KeyError, TypeError, ValueError, AttributeError):
                fail('/review', 'invalid_review', 'Review timestamp must be a timezone-aware ISO datetime.')
        review = max(eligible, key=lambda row: row[:2])[2] if eligible else {}
        if (review.get('decision') != 'accepted' or review.get('reviewer_kind') != 'human'
                or not isinstance(review.get('reviewer'), str) or not review['reviewer'].strip()
                or not isinstance(review.get('review_id'), str) or not review['review_id'].strip()):
            fail('/review', 'unreviewed_authored_model', 'Trusted human review must accept this exact model, evidence and Part content hash.')
        if model_validator is None:
            fail('/', 'consumer_validation_missing', 'A lossless wire adapter and semantic validator are required before admission.')
        elif not issues:
            try:
                validation_errors = model_validator(copy.deepcopy(model), copy.deepcopy(parts))
                if not isinstance(validation_errors, list) or any(not isinstance(e, str) for e in validation_errors):
                    fail('/', 'invalid_validation_result', 'Semantic validator must return a list of error strings.')
                else:
                    for error in validation_errors:
                        fail('/', 'consumer_validation_failed', error)
            except Exception as exc:
                fail('/', 'consumer_validation_failed', type(exc).__name__ + ': ' + str(exc))
        if issues:
            exclusions.append({'model_id': mid, 'content_hash': digest, 'issues': issues,
                               'would_close': 'Resolve the listed source, geometry and schema gaps, then review the exact authored model and Part digest.'})
        else:
            models.append(copy.deepcopy(model))
    return {'models': models, 'exclusions': exclusions}
