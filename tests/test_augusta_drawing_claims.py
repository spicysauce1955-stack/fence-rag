"""Augusta drawing readings stay source-scoped, reviewable and unpublished
where no component Part owns the value."""
import sqlite3
import unittest
from context import ROOT, requires_store
from fence_evidence import augusta_drawing_claims as recipe
from fence_evidence.store import connect
from fence_evidence.parameters import _default_source_ref
from fence_evidence.reviews import submit_fact_review, fact_ref_id
from fence_evidence.snapshot import build_snapshot, verify


@requires_store
class TestAugustaDrawingClaims(unittest.TestCase):
    def setUp(self):
        source=connect(read_only=True)
        self.conn=sqlite3.connect(':memory:');self.conn.row_factory=sqlite3.Row
        source.backup(self.conn);source.close();self.addCleanup(self.conn.close)
        for extractor in (recipe.CAD_EXTRACTOR,recipe.INSTALL_EXTRACTOR,recipe.LEGACY_INSTALL_EXTRACTOR,
                         recipe.SPECSHEET_EXTRACTOR,recipe.CADPAGE_EXTRACTOR):
            self.conn.execute('DELETE FROM fact_reviews WHERE fact_id IN (SELECT fact_id FROM facts WHERE extractor=?)',(extractor,))
            self.conn.execute('DELETE FROM facts WHERE extractor=?',(extractor,));self.conn.commit()

    def parts(self):return recipe.build_parts(self.conn,_default_source_ref(self.conn))

    def test_no_implicit_import_and_idempotent_readings(self):
        self.assertEqual(self.parts(),[])
        recipe.import_cad_readings(self.conn)
        recipe.import_install_readings(self.conn)
        recipe.import_specsheet_readings(self.conn)
        again=(recipe.import_cad_readings(self.conn),recipe.import_install_readings(self.conn),
            recipe.import_specsheet_readings(self.conn))
        self.assertTrue(all(not r['inserted'] for group in again for r in group))
        cad=list(self.conn.execute('SELECT * FROM facts WHERE extractor=?',(recipe.CAD_EXTRACTOR,)))
        self.assertEqual(len(cad),7)
        self.assertTrue(all(r['review_status']=='flagged' and r['ocr_derived']==1 for r in cad))
        for extractor in (recipe.INSTALL_EXTRACTOR,recipe.SPECSHEET_EXTRACTOR):
            rows=list(self.conn.execute('SELECT * FROM facts WHERE extractor=?',(extractor,)))
            self.assertTrue(rows and all(r['review_status']=='extracted' and r['ocr_derived']==0 for r in rows))
        parts=self.parts();self.assertEqual(len(parts),3)
        rail=next(p for p in parts if p['id'].endswith('-rail'))
        specs={s['key']:s['value']['amount_milli'] for s in rail['spec']}
        self.assertEqual(specs,{'width_mm':38100,'height_mm':139700,'length_mm':1816100})
        picket=next(p for p in parts if p['id'].endswith('-picket'))
        pspecs={s['key']:s['value']['amount_milli'] for s in picket['spec']}
        self.assertEqual(pspecs,{'nominal_thickness_mm':22225,'nominal_width_mm':152400})
        uchan=next(p for p in parts if p['id'].endswith('-u-channel'))
        self.assertEqual(len(uchan['spec']),1)
        spec=uchan['spec'][0]
        self.assertEqual(spec['key'],'nominal_designation')
        self.assertEqual(spec['value'],{'key':'designation','value_raw':['1.5 in.']})
        self.assertNotIn('amount_milli',spec['value'])
        # The CAD membership label is cited alongside the install-guide statement.
        cited_shas={c['belongs_to'] for c in spec['provenance']['cites']}
        self.assertEqual(cited_shas,{recipe.INSTALL_SHA,recipe.CAD_SHA})
        self.assertEqual(set(uchan['contributing_sources']),{recipe.INSTALL_SHA,recipe.CAD_SHA})
        # Overall panel dimensions and picket-run segments stay unpublished.
        self.assertFalse(any('panel' in p['id'] for p in parts))
        self.assertNotIn('overall_width_mm',{s['key'] for p in parts for s in p['spec']})

    def test_names_carry_no_measured_values(self):
        recipe.import_cad_readings(self.conn)
        recipe.import_install_readings(self.conn)
        recipe.import_specsheet_readings(self.conn)
        for p in self.parts():
            for token in ('1.5','5.5','71.5','7/8','39.5','95.5','72'):
                self.assertNotIn(token,p['name_i18n']['en'])

    def test_correction_and_rejection_use_existing_review_path(self):
        recipe.import_cad_readings(self.conn)
        row=self.conn.execute('SELECT * FROM facts WHERE extractor=? AND fact_type=?',
            (recipe.CAD_EXTRACTOR,'rail_drawing_length_mm')).fetchone()
        old=next(p for p in self.parts() if p['id'].endswith('-rail'))
        submit_fact_review(self.conn,fact_id=row['fact_id'],reviewer='test',
            ref_id=fact_ref_id(self.conn,row['fact_id']),verdict='corrected',value='71.501 in.')
        with self.assertRaisesRegex(ValueError,'precision|explicit'):self.parts()
        submit_fact_review(self.conn,fact_id=row['fact_id'],reviewer='test',
            ref_id=fact_ref_id(self.conn,row['fact_id']),verdict='corrected',value='72 in.')
        changed=next(p for p in self.parts() if p['id'].endswith('-rail'))
        self.assertNotEqual(old['version'],changed['version'])
        specs={s['key']:s['value']['amount_milli'] for s in changed['spec']}
        self.assertEqual(specs['length_mm'],1828800)
        submit_fact_review(self.conn,fact_id=row['fact_id'],reviewer='test',
            ref_id=fact_ref_id(self.conn,row['fact_id']),verdict='rejected')
        changed=next(p for p in self.parts() if p['id'].endswith('-rail'))
        self.assertNotIn('length_mm',{s['key'] for s in changed['spec']})
        self.assertEqual(len(changed['spec']),2)
        # A rejected dimension must not survive anywhere in the published Part.
        self.assertNotIn('71.5',changed['name_i18n']['en'])

    def test_u_channel_rejection_cannot_silence_the_review_ledger(self):
        recipe.import_install_readings(self.conn)
        row=self.conn.execute('SELECT * FROM facts WHERE extractor=?',(recipe.INSTALL_EXTRACTOR,)).fetchone()
        submit_fact_review(self.conn,fact_id=row['fact_id'],reviewer='test',
            ref_id=fact_ref_id(self.conn,row['fact_id']),verdict='rejected')
        self.assertEqual(self.parts(),[])
        # A rejected verdict stamped onto the row without its ledger record refuses.
        self.conn.execute("UPDATE facts SET review_status='rejected',reviewer='forged',reviewed_at='2026-09-07T00:00:00' WHERE fact_id=?",(row['fact_id'],))
        self.conn.commit()
        with self.assertRaisesRegex(ValueError,'ledger|projection'):self.parts()

    def test_partial_picket_evidence_publishes_supported_remainder(self):
        recipe.import_specsheet_readings(self.conn)
        self.conn.execute('DELETE FROM facts WHERE extractor=? AND fact_type=?',
            (recipe.SPECSHEET_EXTRACTOR,'picket_width_in'))
        self.conn.commit()
        parts=self.parts()
        picket=[p for p in parts if p['id'].endswith('-picket')]
        self.assertEqual(len(picket),1)
        specs={s['key']:s['value']['amount_milli'] for s in picket[0]['spec']}
        self.assertEqual(specs,{'nominal_thickness_mm':22225})
        # Deleting the last supported reading publishes no picket, not a crash.
        self.conn.execute('DELETE FROM facts WHERE extractor=?',(recipe.SPECSHEET_EXTRACTOR,))
        self.conn.commit()
        parts=self.parts()
        self.assertEqual([p for p in parts if p['id'].endswith('-picket')],[])

    def test_superseded_v1_install_reading_is_preserved_not_required_to_clean(self):
        # A store holding v1's superseded width reading imports and publishes v2
        # alongside it; the v1 row is never deleted and never publishes.
        row=self.conn.execute('''SELECT * FROM elements WHERE element_id=?''',
            (recipe.INSTALL_ANCHORS['u_channel_designation'][0],)).fetchone()
        self.conn.execute('''INSERT INTO facts (document_id,version_id,page_no,element_id,fact_type,subject,
            value_original,unit_original,conditions,condition_basis,evidence_text,extractor,ocr_derived,
            review_status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (row['document_id'],row['version_id'],row['page_no'],row['element_id'],'u_channel_width_in',
             'Weatherables master installation instructions: u-channel (superseded)','1.5 in.','in','{}','assumed',
             row['text'],recipe.LEGACY_INSTALL_EXTRACTOR,0,'extracted','2026-09-07T00:00:00'))
        self.conn.commit()
        legacy_before=self.conn.execute('SELECT COUNT(*) FROM facts WHERE extractor=?',
            (recipe.LEGACY_INSTALL_EXTRACTOR,)).fetchone()[0]
        result=recipe.import_install_readings(self.conn)
        self.assertTrue(result[0]['inserted'])
        legacy_after=self.conn.execute('SELECT COUNT(*) FROM facts WHERE extractor=?',
            (recipe.LEGACY_INSTALL_EXTRACTOR,)).fetchone()[0]
        self.assertEqual(legacy_before,legacy_after)
        parts=self.parts()
        uchan=next(p for p in parts if p['id'].endswith('-u-channel'))
        self.assertEqual({s['key'] for s in uchan['spec']},{'nominal_designation'})
        # An unrecognized legacy v1 shape refuses rather than silently carrying.
        self.conn.execute("INSERT INTO facts (document_id,version_id,page_no,element_id,fact_type,subject,"
            "value_original,unit_original,conditions,condition_basis,evidence_text,extractor,ocr_derived,"
            "review_status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (row['document_id'],row['version_id'],row['page_no'],row['element_id'],'u_channel_depth_in',
             'unknown legacy shape','1.5 in.','in','{}','assumed',row['text'],
             recipe.LEGACY_INSTALL_EXTRACTOR,0,'extracted','2026-09-07T00:00:00'))
        self.conn.commit()
        with self.assertRaisesRegex(ValueError,'legacy'):recipe.import_install_readings(self.conn)
        with self.assertRaisesRegex(ValueError,'legacy'):self.parts()

    def test_cad_membership_citation_requires_independent_validation(self):
        recipe.import_install_readings(self.conn)
        # Intact pinned CAD label: the membership cite is present and scoped.
        parts=self.parts()
        uchan=next(p for p in parts if p['id'].endswith('-u-channel'))
        cited={c['belongs_to'] for c in uchan['spec'][0]['provenance']['cites']}
        self.assertEqual(cited,{recipe.INSTALL_SHA,recipe.CAD_SHA})
        self.assertIn('CAD panel membership',uchan['name_i18n']['en'])
        # Changed label text: no membership cite; the Part keeps only the
        # family-level designation with its single supported source.
        self.conn.execute("UPDATE elements SET ocr_text='V-Channels' WHERE element_id=?",
            (recipe.CAD_ANCHORS['u_channels'][0],))
        self.conn.commit()
        parts=self.parts()
        uchan=next(p for p in parts if p['id'].endswith('-u-channel'))
        cited={c['belongs_to'] for c in uchan['spec'][0]['provenance']['cites']}
        self.assertEqual(cited,{recipe.INSTALL_SHA})
        self.assertEqual(set(uchan['contributing_sources']),{recipe.INSTALL_SHA})
        self.assertNotIn('CAD panel membership',uchan['name_i18n']['en'])
        self.assertIn('family level',uchan['name_i18n']['en'])

    def test_changed_ocr_or_forged_review_refuses(self):
        recipe.import_cad_readings(self.conn)
        self.conn.execute("UPDATE facts SET review_status='accepted' WHERE extractor=?",(recipe.CAD_EXTRACTOR,))
        with self.assertRaisesRegex(ValueError,'ledger'):self.parts()
        self.conn.rollback()
        self.conn.execute("UPDATE elements SET ocr_text='another drawing' WHERE element_id=?",
            (recipe.CAD_ANCHORS['rail_callout_top'][0],))
        with self.assertRaisesRegex(ValueError,'anchor'):recipe.import_cad_readings(self.conn)

    def test_actual_snapshot_builder_contains_only_scoped_new_parts(self):
        before=build_snapshot(tenant='default',conn=self.conn)
        recipe.import_cad_readings(self.conn)
        recipe.import_install_readings(self.conn)
        recipe.import_specsheet_readings(self.conn)
        after=build_snapshot(tenant='default',conn=self.conn);verify(after)
        added={p['id'] for p in after['parts']}-{p['id'] for p in before['parts']}
        self.assertEqual(added,{recipe.PREFIX+c for c in ('rail','u-channel','picket')})
        old={p['id']:p for p in before['parts']}
        self.assertTrue(all(p==old[p['id']] for p in after['parts'] if p['id'] in old))

@requires_store
class TestCadPageMaterialList(unittest.TestCase):
    """The manufacturer's 8ft CAD page material list closes kit-content gaps."""

    def setUp(self):
        source = connect(read_only=True)
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        source.backup(self.conn)
        source.close()
        self.addCleanup(self.conn.close)
        self.conn.execute('DELETE FROM fact_reviews WHERE fact_id IN (SELECT fact_id FROM facts WHERE extractor=?)',
                          (recipe.CADPAGE_EXTRACTOR,))
        self.conn.execute('DELETE FROM facts WHERE extractor=?', (recipe.CADPAGE_EXTRACTOR,))
        self.conn.commit()

    def parts(self):
        return recipe.build_parts(self.conn, _default_source_ref(self.conn))

    def test_material_list_import_and_scoped_parts(self):
        self.assertEqual([p for p in self.parts() if 'metal-insert' in p['id']], [])
        imported = recipe.import_cadpage_readings(self.conn)
        self.assertEqual(len(imported), 11)
        self.assertFalse(any(r['inserted'] for r in recipe.import_cadpage_readings(self.conn)))
        parts = self.parts()
        by_id = {p['id']: p for p in parts}
        # Metal insert appears with kit count and dimensions.
        metal = by_id['mfr/weatherables/augusta-8x6-metal-insert']
        specs = {s['key']: s['value'] for s in metal['spec']}
        self.assertEqual(specs['kit_count_per_panel']['value_raw'], ['4 each'] if False else ['3 each'])
        self.assertEqual(specs['width_mm']['amount_milli'], 31750)
        self.assertEqual(specs['length_mm']['amount_milli'], 1816100)
        self.assertEqual(metal['type'], {'namespace': 'shared', 'key': 'reinforcement'})
        # U-channel upgraded to configuration-specific values.
        uchan = by_id['mfr/weatherables/augusta-8x6-u-channel']
        uspecs = {s['key']: s['value'] for s in uchan['spec']}
        self.assertEqual(uspecs['length_mm']['amount_milli'], 1003300)
        self.assertEqual(uspecs['depth_mm']['amount_milli'], 38100)
        self.assertEqual(uspecs['kit_count_per_panel']['value_raw'], ['4 each'])
        self.assertIn('material list', uchan['name_i18n']['en'])
        # Picket gains stock length and kit count.
        picket = by_id['mfr/weatherables/augusta-8x6-picket']
        pspecs = {s['key']: s['value'] for s in picket['spec']}
        self.assertEqual(pspecs['stock_length_mm']['amount_milli'], 1092200)
        self.assertEqual(pspecs['kit_count_per_panel']['value_raw'], ['22 each'])
        self.assertEqual(sorted(set(picket['contributing_sources'])),
                         sorted({recipe.SPECSHEET_SHA, recipe.CADPAGE_SHA}))
        # Kit counts are Tokens, never dimensional Quantities.
        for part in parts:
            for s in part['spec']:
                if s['key'] == 'kit_count_per_panel':
                    self.assertNotIn('amount_milli', s['value'])

    def test_material_list_anchor_and_forged_state_refuse(self):
        recipe.import_cadpage_readings(self.conn)
        self.conn.execute("UPDATE elements SET text='Material List - 8x8 Panel' WHERE element_id=?",
                          (recipe.CADPAGE_ANCHORS['panel_8x6_heading'][0],))
        self.conn.commit()
        with self.assertRaisesRegex(ValueError, 'anchor'):
            recipe.import_cadpage_readings(self.conn)
