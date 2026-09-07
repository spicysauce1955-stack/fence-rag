"""Scanned drawing knowledge remains source-scoped and reviewable."""
import sqlite3
import unittest
from context import ROOT, requires_store
from fence_evidence import emblem_drawing_claims as recipe
from fence_evidence.store import connect
from fence_evidence.parameters import _default_source_ref
from fence_evidence.reviews import submit_fact_review, fact_ref_id
from fence_evidence.snapshot import build_snapshot, verify


@requires_store
class TestDrawingClaims(unittest.TestCase):
    def setUp(self):
        source=connect(read_only=True)
        self.conn=sqlite3.connect(':memory:');self.conn.row_factory=sqlite3.Row
        source.backup(self.conn);source.close();self.addCleanup(self.conn.close)
        self.conn.execute('DELETE FROM fact_reviews WHERE fact_id IN (SELECT fact_id FROM facts WHERE extractor=?)',(recipe.EXTRACTOR,))
        self.conn.execute('DELETE FROM facts WHERE extractor=?',(recipe.EXTRACTOR,));self.conn.commit()

    def parts(self):return recipe.build_parts(self.conn,_default_source_ref(self.conn))

    def test_no_implicit_import_and_flagged_idempotent_readings(self):
        self.assertEqual(self.parts(),[])
        recipe.import_readings(self.conn)
        self.assertFalse(any(r['inserted'] for r in recipe.import_readings(self.conn)))
        rows=list(self.conn.execute('SELECT * FROM facts WHERE extractor=?',(recipe.EXTRACTOR,)))
        self.assertEqual(len(rows),9)
        self.assertTrue(all(r['review_status']=='flagged' and r['ocr_derived']==1 for r in rows))
        parts=self.parts();self.assertEqual(len(parts),3)
        board=next(p for p in parts if p['id'].endswith('-board'))
        specs={s['key']:s['value']['amount_milli'] for s in board['spec']}
        self.assertEqual(specs['drawing_length_mm'],1562100)
        self.assertEqual(specs['drawing_thickness_mm'],22225)
        self.assertNotIn('width_mm',specs)
        self.assertIn('exact SKU unverified',board['name_i18n']['en'])

    def test_correction_and_rejection_use_existing_review_path(self):
        recipe.import_readings(self.conn)
        row=self.conn.execute('SELECT * FROM facts WHERE extractor=? AND fact_type=?',(recipe.EXTRACTOR,'board_drawing_length_mm')).fetchone()
        old=next(p for p in self.parts() if p['id'].endswith('-board'))
        submit_fact_review(self.conn,fact_id=row['fact_id'],reviewer='test',ref_id=fact_ref_id(self.conn,row['fact_id']),verdict='corrected',value='61.501 in.')
        with self.assertRaisesRegex(ValueError,'precision'):self.parts()
        submit_fact_review(self.conn,fact_id=row['fact_id'],reviewer='test',ref_id=fact_ref_id(self.conn,row['fact_id']),verdict='corrected',value='62 in.')
        changed=next(p for p in self.parts() if p['id'].endswith('-board'))
        self.assertNotEqual(old['version'],changed['version'])
        submit_fact_review(self.conn,fact_id=row['fact_id'],reviewer='test',ref_id=fact_ref_id(self.conn,row['fact_id']),verdict='rejected')
        changed=next(p for p in self.parts() if p['id'].endswith('-board'))
        self.assertNotIn('drawing_length_mm',{s['key'] for s in changed['spec']})
        self.assertEqual(len(changed['spec']),2)

    def test_changed_ocr_or_forged_review_refuses(self):
        recipe.import_readings(self.conn)
        self.conn.execute("UPDATE facts SET review_status='accepted' WHERE extractor=?",(recipe.EXTRACTOR,))
        with self.assertRaisesRegex(ValueError,'ledger'):self.parts()
        self.conn.rollback()
        self.conn.execute("UPDATE elements SET ocr_text='another model' WHERE element_id=?",(recipe.ANCHORS['model'][0],))
        with self.assertRaisesRegex(ValueError,'anchor'):recipe.import_readings(self.conn)

    def test_actual_snapshot_builder_contains_only_scoped_new_parts(self):
        before=build_snapshot(tenant='default',conn=self.conn)
        recipe.import_readings(self.conn)
        after=build_snapshot(tenant='default',conn=self.conn);verify(after)
        added={p['id'] for p in after['parts']}-{p['id'] for p in before['parts']}
        self.assertEqual(added,{recipe.PREFIX+c for c in ('rail','board','end-channel')})
        old={p['id']:p for p in before['parts']}
        self.assertTrue(all(p==old[p['id']] for p in after['parts'] if p['id'] in old))
