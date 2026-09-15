"""Checkpoint refusals protect the layer transition, not product completeness."""
from copy import deepcopy
import sqlite3
import unittest
from context import ROOT
from fence_evidence.refs import ref_id
from scripts.check_conversion_batch import check_bindings, compare_slice


class TestConversionCheckpoint(unittest.TestCase):
    def test_unrelated_snapshot_changes_do_not_block_the_selected_slice(self):
        old={'parts':[{'id':'selected','spec':[]},{'id':'other','version':1}]}
        new=deepcopy(old);new['parts'][1]['version']=2
        self.assertEqual(compare_slice(old,new,{'selected'}),[old['parts'][0]])

    def test_stale_selected_value_or_dropped_part_refuses(self):
        old={'parts':[{'id':'selected','spec':[{'value':10}]}]}
        for new in ({'parts':[]},{'parts':[{'id':'selected','spec':[{'value':11}]}]}):
            with self.subTest(new=new),self.assertRaises(ValueError):
                compare_slice(old,new,{'selected'})

    def test_empty_slice_is_not_invented_and_duplicates_refuse(self):
        self.assertEqual(compare_slice({'parts':[]},{'parts':[]},{'missing'}),[])
        with self.assertRaises(ValueError):
            compare_slice({'parts':[{'id':'x'},{'id':'x'}]},{'parts':[]},{'x'})

    def test_trace_requires_persisted_nonrejected_canonical_claim_and_published_cite(self):
        conn=sqlite3.connect(':memory:');self.addCleanup(conn.close);conn.row_factory=sqlite3.Row
        conn.executescript('''CREATE TABLE elements(element_id,version_id,document_id,page_no,text,bbox,ocr_text);
        CREATE TABLE document_versions(version_id,sha256);
        CREATE TABLE facts(fact_id,extractor,fact_type,element_id,document_id,version_id,page_no,
            review_status,evidence_text,value_original,reviewed_value);
        INSERT INTO elements VALUES('e','v','d',1,'6 inches','[]',NULL);
        INSERT INTO document_versions VALUES('v','sha');
        INSERT INTO facts VALUES(1,'recipe','width','e','d','v',1,'extracted','6 inches','6 in.',NULL);''')
        bindings=[{'part_id':'p','spec_key':'width','extractor':'recipe','fact_type':'width','element_id':'e'}]
        part={'id':'p','spec':[{'key':'width','value':{'amount_milli':152400},
            'provenance':{'cites':[{'id':ref_id('sha',1,'[]'),'belongs_to':'sha'}]}}]}
        self.assertEqual(check_bindings(conn,bindings,[part])[0]['fact_id'],1)
        conn.execute("UPDATE elements SET text='',ocr_text='6 inches'")
        self.assertEqual(check_bindings(conn,bindings,[part])[0]['fact_id'],1)
        with self.assertRaises(ValueError): check_bindings(conn,[],[part])
        changed=deepcopy(part);changed['spec'][0]['provenance']['cites']=[]
        with self.assertRaises(ValueError): check_bindings(conn,bindings,[changed])
        conn.execute("UPDATE facts SET review_status='rejected'")
        with self.assertRaises(ValueError): check_bindings(conn,bindings,[part])
        conn.execute("UPDATE facts SET review_status='extracted',evidence_text='invented'")
        with self.assertRaises(ValueError): check_bindings(conn,bindings,[part])
