"""The source checker must bind text, edition and exact page region together."""
from copy import deepcopy
import sqlite3
import unittest
from context import ROOT
from fence_evidence.refs import ref_id
from scripts.check_emblem_assembly_sources import check_anchor


class TestAssemblyAnchorCheck(unittest.TestCase):
    def test_changed_text_source_or_region_never_verifies(self):
        with sqlite3.connect(':memory:') as conn:
            conn.row_factory = sqlite3.Row
            conn.executescript('''CREATE TABLE elements(element_id TEXT,version_id TEXT,
                page_no INTEGER,text TEXT,bbox TEXT);
                CREATE TABLE document_versions(version_id TEXT,sha256 TEXT);
                INSERT INTO elements VALUES('e','v',4,'source reading','[1,2,3,4]');
                INSERT INTO document_versions VALUES('v','sourcehash');''')
            anchor = {'element_id':'e','text_raw':'source reading',
                'cite':{'belongs_to':'sourcehash','id':ref_id('sourcehash',4,'[1,2,3,4]')}}
            keys = ('text_matches','source_matches','region_matches')
            self.assertTrue(all(check_anchor(conn,anchor)[k] for k in keys))
            for fault in ('text','source','region','missing'):
                with self.subTest(fault=fault):
                    changed = deepcopy(anchor)
                    if fault == 'text': changed['text_raw'] = 'invented reading'
                    elif fault == 'source': changed['cite']['belongs_to'] = 'another edition'
                    elif fault == 'region': changed['cite']['id'] = ref_id('sourcehash',5,'[1,2,3,4]')
                    else: changed['element_id'] = 'missing'
                    self.assertFalse(all(check_anchor(conn,changed)[k] for k in keys))
