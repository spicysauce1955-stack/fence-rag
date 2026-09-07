"""Useful partial knowledge from current published Parts and checked source readings.

This is an answer document, not a new FenceModel wire representation.
"""
from copy import deepcopy


def knowledge_ready(result):
    return result.get('snapshot_verified') is True and bool(result.get('published_exact_parts'))


def completion_code(result, objective):
    if objective == 'knowledge':
        return 0 if knowledge_ready(result) else 2
    if objective == 'assembly':
        return 0 if (result.get('snapshot_verified') is True
                     and result.get('full_model_admitted') is True
                     and result.get('assembly_validated') is True) else 2
    raise ValueError('Unknown completion objective')


def quantity_text(value):
    if 'amount_milli' not in value:
        return value['key']
    amount = value['amount_milli']
    whole, remainder = divmod(abs(amount), 1000)
    number = str(whole) + (('.' + str(remainder).zfill(3).rstrip('0')) if remainder else '')
    return ('-' if amount < 0 else '') + number + ' ' + value['unit']


def make_card(result, relations):
    return {'product': 'Freedom Emblem White 6×8, SKU 73014714',
        'document_kind': 'partial_knowledge_answer',
        'snapshot_id': result['snapshot_id'], 'knowledge_available': knowledge_ready(result),
        'published_parts': deepcopy(result['published_exact_parts']),
        'withheld_parts': deepcopy(result['withheld_exact_parts']),
        'assembly_readings': deepcopy(relations),
        'assembly_reading_status': 'Source-checked interpretation; not an admitted model or human review',
        'answers': {
            'component_properties': 'Answer from the available published specifications below.',
            'assembly_relationships': 'Explain the checked manual readings below, with their stated applicability.',
            'verified_cuts_and_fit': 'Not established; receiving depths, seating, installed pitch and channel dimensions are incomplete.',
            'complete_purchase_list': 'Not established; exact legacy kit contents and stock lengths remain incomplete.'},
        'follow_up_by_task': [
            {'when': 'User asks for board counts or cut lengths',
             'ask': 'What clear opening are you filling, and do you have a component drawing or measured installed board pitch?',
             'why': 'Nominal board width alone does not determine fitted coverage or cuts.'},
            {'when': 'User asks for exact purchasing quantities',
             'ask': 'Which kit SKU/revision will you buy, and is its package contents list available?',
             'why': 'Current-family inventory cannot silently replace legacy kit inventory.'},
            {'when': 'User asks for installation instructions for a layout',
             'ask': 'Is the layout straight, cornered or sloped, and are any panels being cut down?',
             'why': 'Explain applicable instructions and identify unsupported arrangements.'}],
        'full_model_admitted': result['full_model_admitted'],
        'assembly_validated': result['assembly_validated'],
        'scope_note': 'Missing fit data limits the affected calculations; it does not withhold supported knowledge.'}


def render_card(card, source_paths):
    rows = ['# ' + card['product'], '',
        ('Partial knowledge: ' + str(len(card['published_parts'])) + ' component definitions and ' + str(len(card['assembly_readings'])) + ' checked assembly readings available.'),
        'Draft status and source classifications are retained. This is not a verified fabrication or purchase list.', '',
        '## Component properties', '']
    for part in card['published_parts']:
        rows += ['### ' + part.get('name_i18n',{}).get('en',part['id']), '',
                 'Status: ' + part['status'] + '.', '',
                 '| Property | Value | Original reading | Classification | Evidence |', '|---|---|---|---|---|']
        for spec in part['spec']:
            cites = spec['provenance']['cites']
            paths = list(dict.fromkeys(source_paths[c['belongs_to']] for c in cites))
            links = ', '.join('[Source ' + str(i+1) + '](' + path + ')' for i,path in enumerate(paths))
            provenance = spec['provenance']
            classification = provenance.get('source_class','unspecified') + '; curation level ' + str(provenance.get('curation_level','unspecified'))
            raw = '; '.join(spec['value'].get('value_raw',[])).replace('|','\\|')
            label = spec['key'].replace('_mm','').replace('_',' ')
            rows.append('| ' + label + ' | ' + quantity_text(spec['value']) + ' | ' + raw + ' | ' + classification + ' | ' + links + ' |')
        rows.append('')
    if not card['published_parts']:
        rows += ['No current exact Part specifications are available.', '']
    if card['withheld_parts']:
        rows += ['Withheld definitions: ' + ', '.join(p['id'] for p in card['withheld_parts']) + '.', '']
    rows += ['Nominal sizes are not installed pitch or mating clearance. Curation level 0 means an unreviewed extraction; exact provenance is retained in the companion JSON.', '',
             '## What the manual supports', '', card['assembly_reading_status'] + '.',
             'Applicability: the linked manual supports the full-privacy 6-foot branch; this is an assistant interpretation, not a human review.', '']
    for relation in card['assembly_readings']:
        anchor = relation['evidence_anchor']
        text = ' '.join(anchor['text_raw'].split())
        rows += ['- ' + text + ' [Source, page ' + str(relation['page']) + '](' + source_paths[anchor['cite']['belongs_to']] + ').']
    rows += ['', '## When more information is needed', '']
    for question in card['follow_up_by_task']:
        rows += ['- **' + question['when'] + ':** ' + question['ask'] + ' ' + question['why']]
    rows += ['', card['scope_note'], '',
             'Verified cuts/fit: ' + card['answers']['verified_cuts_and_fit'],
             'Complete purchases: ' + card['answers']['complete_purchase_list'], '']
    return '\n'.join(rows)
