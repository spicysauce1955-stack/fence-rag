"""Useful knowledge survives incomplete assembly without inventing missing claims."""
import unittest
from context import ROOT
from fence_evidence.emblem_knowledge import completion_code, make_card, quantity_text, render_card


class TestPartialKnowledge(unittest.TestCase):
    def result(self, parts):
        return dict(snapshot_verified=True,snapshot_id='s',published_exact_parts=parts,
            withheld_exact_parts=[{'id':'board'}],full_model_admitted=False,assembly_validated=False)

    def part(self, amount=127000):
        return {'id':'cap','status':'draft','spec':[{'key':'nominal_width_mm',
            'value':{'amount_milli':amount,'unit':'mm','value_raw':['reviewed reading']},
            'provenance':{'cites':[{'id':'ref','belongs_to':'sha'}],'curation_level':0}}]}

    def test_cap_only_can_answer_while_assembly_stays_incomplete(self):
        result=self.result([self.part()])
        self.assertEqual(completion_code(result,'knowledge'),0)
        self.assertEqual(completion_code(result,'assembly'),2)
        card=make_card(result,[])
        text=render_card(card,{'sha':'/source.pdf'})
        self.assertIn('127 mm',text)
        self.assertNotIn('152.4',text)
        self.assertIn('Withheld definitions: board',text)
        self.assertFalse(card['assembly_validated'])

    def test_empty_or_unverified_publication_never_reports_success(self):
        result=self.result([])
        result['published_exact_part_count']=4
        self.assertEqual(completion_code(result,'knowledge'),2)
        result=self.result([self.part()]);result['snapshot_verified']=False
        self.assertEqual(completion_code(result,'knowledge'),2)

    def test_correction_keeps_exact_precision_and_cannot_mutate_publication(self):
        result=self.result([self.part(127001)])
        card=make_card(result,[])
        self.assertIn('127.001 mm',render_card(card,{'sha':'/source.pdf'}))
        card['published_parts'][0]['spec'][0]['value']['amount_milli']=0
        self.assertEqual(result['published_exact_parts'][0]['spec'][0]['value']['amount_milli'],127001)
        self.assertEqual(quantity_text({'amount_milli':-1,'unit':'mm'}),'-0.001 mm')

    def test_readings_are_not_promoted_to_admitted_model(self):
        card=make_card(self.result([self.part()]),[{'relationship':'example'}])
        self.assertIn('not an admitted model',card['assembly_reading_status'])
        self.assertFalse(card['full_model_admitted'])
        self.assertTrue(card['follow_up_by_task'])

    def test_empty_card_does_not_advertise_available_properties(self):
        card=make_card(self.result([]),[])
        text=render_card(card,{})
        self.assertIn('0 component definitions and 0 checked assembly readings',text)
        self.assertNotIn('are available now',text)

    def test_card_displays_original_reading_and_classification(self):
        text=render_card(make_card(self.result([self.part()]),[]),{'sha':'/source.pdf'})
        self.assertIn('reviewed reading',text)
        self.assertIn('curation level 0',text)
