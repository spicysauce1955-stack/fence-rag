"""Scanned drawing knowledge remains source-scoped and reviewable."""
import sqlite3
import unittest
from context import ROOT, requires_store
from fence_evidence import emblem_drawing_claims as recipe
from fence_evidence.store import SCHEMA, connect
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
        row=self.conn.execute('SELECT * FROM facts WHERE extractor=? AND fact_type=?',(recipe.EXTRACTOR,'board_drawing_length_in')).fetchone()
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


class TestStaleReadingTypesAreRefused(unittest.TestCase):
    """A reading persisted under a name the recipe no longer knows must stop
    the import, not sit beside its replacement.

    `augusta_drawing_claims._reading_rows` and
    `pembroke_cadpage_claims._reading_rows` both end with a `live - known`
    check; this module had only the per-`fact_type` conflict check, so a store
    holding the pre-rename `*_drawing_*_mm` rows would import 9 more under the
    `_in` names and end with 18 -- nine stale beside nine live -- in a module
    whose own error message calls these readings immutable.

    `[measured]` 2026-09-09 on a copy of the live store with the 9 emblem
    drawing rows restored to their `_mm` names: `import_readings` reported
    `9 inserted` and the store went from 9 rows to 18. Found while reviewing
    the B-1/B-2 fact-type rename, which is precisely the migration that makes
    a stale name possible.
    """

    def store(self, *, stale=None):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        # Parents first: `facts` carries foreign keys, and a fixture that
        # disabled them would be testing a store this system cannot have.
        conn.execute("INSERT INTO documents(document_id, source_path, file_type,"
                     " corpus_track) VALUES('doc-1','manuals/x/a.pdf','pdf','us')")
        conn.execute("INSERT INTO document_versions(version_id, document_id,"
                     " sha256, file_size_bytes, page_count, ingested_at)"
                     " VALUES('v1','doc-1',?,1,1,'2026-09-09T00:00:00Z')",
                     ("d" * 64,))
        conn.execute("INSERT INTO pages(page_id, version_id, page_no, width,"
                     " height, extraction_method, has_text_layer)"
                     " VALUES('pg-1','v1',1,612,792,'text',1)")
        conn.execute("INSERT INTO elements(element_id, page_id, version_id,"
                     " document_id, page_no, ordinal, element_type, text,"
                     " text_source) VALUES('el-1','pg-1','v1','doc-1',1,0,"
                     "'paragraph','x','text')")
        if stale:
            conn.execute(
                "INSERT INTO facts(document_id, version_id, page_no,"
                " element_id, fact_type, subject, value_original, conditions,"
                " condition_basis, evidence_text, extractor, ocr_derived,"
                " review_status, created_at) VALUES('doc-1','v1',1,'el-1',?,"
                "'stale','60','{}','assumed','x',?,1,'extracted',"
                "'2026-09-09T00:00:00Z')", (stale, recipe.EXTRACTOR))
        conn.commit()
        self.addCleanup(conn.close)
        return conn

    def anchors(self):
        """The shape `expected_readings` indexes -- it reads five keys off each
        anchor row and nothing else, so a plain dict is the honest fixture."""
        return {key: {"document_id": "doc-1", "version_id": "v1", "page_no": 1,
                      "element_id": "el-1", "ocr_text": "anchor"}
                for key in recipe.ANCHORS}

    def test_a_reading_under_an_unknown_type_stops_the_import(self):
        conn = self.store(stale="panel_drawing_overall_height_mm")
        with self.assertRaises(ValueError) as caught:
            list(recipe.reading_rows(conn, self.anchors()))
        self.assertIn("panel_drawing_overall_height_mm", str(caught.exception))

    def test_a_store_holding_only_known_types_is_not_refused(self):
        conn = self.store()
        rows = list(recipe.reading_rows(conn, self.anchors()))
        self.assertTrue(rows, "expected the recipe to yield its readings")
        self.assertTrue(all(row is None for _, row in rows))
