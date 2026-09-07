"""Source-bound Emblem facts use the shipped review and publication lifecycle."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import sqlite3
import json
import tempfile
import threading
from pathlib import Path
import unittest

from context import ROOT, TESTS_DIR, requires_store
from fence_evidence import emblem_claims as ec, reviews
from fence_evidence.refs import ref_id
from fence_evidence.store import SCHEMA, connect
from fence_evidence.snapshot import SnapshotBuilder, build_snapshot, verify


def fixture():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("INSERT INTO documents(document_id,source_path,file_type,corpus_track,doc_type) VALUES ('d','manuals/test.pdf','pdf','us','cut_sheet')")
    conn.execute("INSERT INTO document_versions(version_id,document_id,sha256,ingested_at) VALUES ('v','d',?,'2026-09-07T00:00:00Z')", (ec.SOURCE_SHA,))
    conn.execute("INSERT INTO pages(page_id,version_id,page_no,width,height,extraction_method) VALUES ('p','v',1,612,792,'text')")
    for i, (eid, text) in enumerate(ec.ANCHORS.values()):
        conn.execute("""INSERT INTO elements(element_id,page_id,version_id,document_id,page_no,ordinal,element_type,text,text_source,bbox)
            VALUES (?,'p','v','d',1,?,'paragraph',?,'text',?)""", (eid, i, text, f'[0, {i}, 100, {i+1}]'))
    conn.commit()
    return conn


def parts(conn):
    def mint(eid):
        row = conn.execute('SELECT bbox FROM elements WHERE element_id=?', (eid,)).fetchone()
        return {'id': ref_id(ec.SOURCE_SHA, 1, row['bbox']), 'belongs_to': ec.SOURCE_SHA}
    return ec.build_board_parts(conn, mint)


class TestEmblemClaims(unittest.TestCase):
    def setUp(self):
        self.conn = fixture()
        self.addCleanup(self.conn.close)

    def test_publication_never_imports_a_reading_as_a_side_effect(self):
        self.assertEqual(parts(self.conn), [])
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM facts').fetchone()[0], 0)

    def test_idempotent_import_retains_original_and_has_no_human_review(self):
        first = ec.import_readings(self.conn)
        second = ec.import_readings(self.conn)
        self.assertEqual([r['fact_id'] for r in first], [r['fact_id'] for r in second])
        self.assertTrue(all(r['inserted'] for r in first))
        self.assertFalse(any(r['inserted'] for r in second))
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM fact_reviews').fetchone()[0], 0)
        board = parts(self.conn)[0]
        self.assertEqual(board['id'], ec.BOARD_ID)
        self.assertEqual(board['status'], 'draft')
        specs = {sf['key']: sf for sf in board['spec']}
        self.assertEqual(set(specs), {'nominal_width_mm', 'colour'})
        self.assertEqual(specs['nominal_width_mm']['value'], {'amount_milli': 152400, 'unit': 'mm', 'value_raw': ['6 in.']})
        for sf in specs.values():
            self.assertEqual(sf['provenance']['curation_level'], 0)
            self.assertEqual(sf['provenance']['source_class'], 'spec_sheet')
            self.assertGreaterEqual(len(sf['provenance']['cites']), 3)

    def test_import_preserves_the_callers_transaction_and_rolls_back_its_own_failure(self):
        self.conn.execute("UPDATE documents SET title='caller change'")
        ec.import_readings(self.conn)
        self.assertTrue(self.conn.in_transaction)
        self.conn.rollback()
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM facts').fetchone()[0], 0)
        self.conn.execute("""CREATE TRIGGER reject_last_reading BEFORE INSERT ON facts
            WHEN NEW.fact_type='cap_colour' BEGIN SELECT RAISE(ABORT,'test failure'); END""")
        self.conn.execute("UPDATE documents SET title='caller change'")
        with self.assertRaises(sqlite3.IntegrityError):
            ec.import_readings(self.conn)
        self.assertTrue(self.conn.in_transaction)
        self.assertEqual(self.conn.execute('SELECT title FROM documents').fetchone()[0], 'caller change')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM facts').fetchone()[0], 0)

    def test_concurrent_imports_create_only_one_copy_of_each_reading(self):
        TESTS_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=TESTS_DIR) as directory:
            path = Path(directory) / 'concurrent.db'
            target = sqlite3.connect(path)
            self.conn.backup(target)
            target.close()
            start = threading.Barrier(4)
            def run():
                conn = sqlite3.connect(path, timeout=10)
                conn.row_factory = sqlite3.Row
                try:
                    start.wait(timeout=10)
                    return ec.import_readings(conn)
                finally:
                    conn.close()
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(lambda _: run(), range(4)))
            self.assertEqual(sum(r['inserted'] for result in results for r in result), len(ec.READINGS))
            self.assertTrue(all([r['fact_id'] for r in result] == [r['fact_id'] for r in results[0]]
                                for result in results))

    def test_changed_source_text_hash_scope_or_owner_refuses_before_writing(self):
        for sql in (
            "UPDATE elements SET text='73058414' WHERE text='73014714'",
            "UPDATE document_versions SET sha256='wrong'",
            "UPDATE documents SET owner_tenant='other'",
            "UPDATE elements SET text_source='ocr'",
            "UPDATE elements SET page_no=2 WHERE text='73014714'",
        ):
            with self.subTest(sql=sql):
                conn = fixture()
                try:
                    conn.execute(sql)
                    with self.assertRaises(ValueError):
                        ec.import_readings(conn)
                    self.assertEqual(conn.execute('SELECT COUNT(*) FROM facts').fetchone()[0], 0)
                finally:
                    conn.close()

    def test_conflicting_persisted_reading_is_not_overwritten_or_published(self):
        ec.import_readings(self.conn)
        self.conn.execute("UPDATE facts SET value_original='7 in.' WHERE fact_type='nominal_board_width_in'")
        for action in (ec.import_readings, parts):
            with self.assertRaises(ValueError):
                action(self.conn)
        self.assertEqual(self.conn.execute("SELECT value_original FROM facts WHERE fact_type='nominal_board_width_in'").fetchone()[0], '7 in.')

    def all_parts(self):
        builder = SnapshotBuilder(self.conn, tenant='default', regime='us_astm')
        return ec.build_emblem_parts(self.conn, lambda eid: asdict(builder.source_ref(eid)))

    def test_rail_fractions_remain_exact_and_cap_dimensions_remain_nominal(self):
        ec.import_readings(self.conn)
        published = self.all_parts()
        self.assertEqual(len(published), 4)
        for part in published:
            specs = {sf['key']: sf['value'] for sf in part['spec']}
            if part['type']['key'] == 'rail':
                self.assertEqual(specs['width_mm']['amount_milli'], 57150)
                self.assertEqual(specs['height_mm']['amount_milli'], 177800)
                self.assertNotIn('stock_length_mm', specs)
            elif part['type']['key'] == 'post_cap':
                self.assertEqual(set(specs), {'nominal_width_mm', 'nominal_depth_mm', 'colour'})
                self.assertEqual(specs['nominal_depth_mm']['amount_milli'], 127000)

    def test_cap_axes_have_independent_review_records(self):
        self.review('corrected', '6in.', index=4)
        cap = next(p for p in self.all_parts() if p['type']['key'] == 'post_cap')
        specs = {sf['key']: sf for sf in cap['spec']}
        self.assertEqual(specs['nominal_width_mm']['value']['amount_milli'], 152400)
        self.assertEqual(specs['nominal_depth_mm']['value']['amount_milli'], 127000)
        self.assertEqual(specs['nominal_depth_mm']['provenance']['curation_level'], 0)

    def test_duplicate_fact_identity_refuses_instead_of_choosing_a_reading(self):
        ec.import_readings(self.conn)
        row = dict(self.conn.execute('SELECT * FROM facts LIMIT 1').fetchone())
        del row['fact_id']
        columns = ','.join(row)
        placeholders = ','.join('?' for _ in row)
        self.conn.execute(f'INSERT INTO facts ({columns}) VALUES ({placeholders})', tuple(row.values()))
        for action in (ec.import_readings, parts):
            with self.assertRaises(ValueError):
                action(self.conn)

    def review(self, verdict, value=None, index=0):
        fid = ec.import_readings(self.conn)[index]['fact_id']
        reviews.submit_fact_review(self.conn, fact_id=fid, reviewer='synthetic-test-reviewer',
            verdict=verdict, value=value, ref_id=reviews.fact_ref_id(self.conn, fid))
        return fid

    def test_corrected_value_replays_through_existing_ledger(self):
        fid = self.review('corrected', '6.5 in.')
        expected = deepcopy(parts(self.conn))
        sf = expected[0]['spec'][0]
        self.assertEqual(sf['value']['amount_milli'], 165100)
        self.assertEqual(sf['provenance']['curation_level'], 2)
        self.assertEqual(self.conn.execute('SELECT value_original FROM facts WHERE fact_id=?', (fid,)).fetchone()[0], '6 in.')
        TESTS_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=TESTS_DIR) as directory:
            ledger = Path(directory) / 'reviews.jsonl'
            reviews.export_reviews(self.conn, ledger)
            fresh = fixture()
            try:
                # IDs are store-local; replay must bind the evidence instead.
                fresh.execute("INSERT INTO sqlite_sequence(name,seq) VALUES ('facts',100)")
                ec.import_readings(fresh)
                result = reviews.import_reviews(fresh, ledger, dry_run=False)
                self.assertEqual(result['unresolvable'], 0)
                self.assertEqual(parts(fresh), expected)
                ec.import_readings(fresh)
                self.assertEqual(parts(fresh), expected)
            finally:
                fresh.close()

    def test_public_part_version_changes_with_content_and_is_stable_on_reimport(self):
        ec.import_readings(self.conn)
        original = parts(self.conn)[0]
        self.review('accepted')
        accepted = parts(self.conn)[0]
        self.assertNotEqual(original['version'], accepted['version'])
        self.review('corrected', '6.5 in.')
        corrected = parts(self.conn)[0]
        self.assertNotEqual(accepted['version'], corrected['version'])
        ec.import_readings(self.conn)
        self.assertEqual(corrected, parts(self.conn)[0])

    def test_forged_or_stale_review_projections_refuse_without_mutating_input(self):
        ec.import_readings(self.conn)
        for assignment in ("review_status='reviewed'", "reviewed_value='99 in.'",
                           "review_status='rejected'", "review_status='cross_family_verified'"):
            with self.subTest(assignment=assignment):
                self.conn.execute('SAVEPOINT forged')
                self.conn.execute("UPDATE facts SET " + assignment + " WHERE fact_type='nominal_board_width_in'")
                before = [dict(r) for r in self.conn.execute('SELECT * FROM facts')]
                with self.assertRaises(ValueError):
                    parts(self.conn)
                self.assertEqual(before, [dict(r) for r in self.conn.execute('SELECT * FROM facts')])
                self.conn.execute('ROLLBACK TO forged')
                self.conn.execute('RELEASE forged')
        self.review('corrected', '6.5 in.')
        self.conn.execute("UPDATE facts SET reviewed_value='99 in.' WHERE fact_type='nominal_board_width_in'")
        with self.assertRaises(ValueError):
            parts(self.conn)

    def test_review_does_not_follow_a_moved_source_region(self):
        self.review('corrected', '6.5 in.')
        self.conn.execute('UPDATE elements SET bbox=? WHERE element_id=?',
                          ('[400,400,450,450]', ec.ANCHORS['board'][0]))
        with self.assertRaisesRegex(ValueError, 'current source reading'):
            parts(self.conn)

    def test_rejection_survives_reimport_and_removes_the_bound_part(self):
        for index in (0, 1):
            with self.subTest(index=index):
                previous = self.conn
                self.conn = fixture()
                try:
                    self.review('rejected', index=index)
                    ec.import_readings(self.conn)
                    self.assertEqual(parts(self.conn), [])
                finally:
                    self.conn.close()
                    self.conn = previous

    def test_correction_cannot_change_units_identity_or_drop_precision_silently(self):
        for value, index in (('7', 0), ('152 mm', 0), ('0 in.', 0), ('6.000001 in.', 0),
                             ('6.00000000000000000000000000001 in.', 0), ('Black', 1)):
            with self.subTest(value=value):
                conn = self.conn
                self.conn = fixture()
                try:
                    self.review('corrected', value, index)
                    with self.assertRaises(ValueError):
                        parts(self.conn)
                finally:
                    self.conn.close()
                    self.conn = conn

    @requires_store
    def test_real_canonical_slice_crosses_the_actual_snapshot_boundary(self):
        source = connect(read_only=True)
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        try:
            source.backup(conn)
            # Isolate this canonical integration fixture from legitimate live reviews.
            conn.execute('DELETE FROM fact_reviews WHERE fact_id IN (SELECT fact_id FROM facts WHERE extractor=?)', (ec.EXTRACTOR,))
            conn.execute('DELETE FROM facts WHERE extractor=?', (ec.EXTRACTOR,))
            conn.commit()
            ec.import_readings(conn)
            snapshot = build_snapshot(tenant='default', conn=conn)
            verify(snapshot)
            board = next(p for p in snapshot['parts'] if p['id'] == ec.BOARD_ID)
            self.assertEqual(board['spec'][0]['value']['amount_milli'], 152400)
            self.assertEqual(snapshot['models'], [])
            builder = SnapshotBuilder(conn, tenant='default', regime='us_astm')
            self.assertEqual(board, ec.build_board_parts(conn, lambda eid: asdict(builder.source_ref(eid)))[0])
            from scripts.advance_emblem import report
            catalog = ROOT / 'workspace/catalog'
            records = [json.loads((catalog / name).read_text()) for name in (
                'emblem-73014714-model-draft.json', 'emblem-73014714-consumer-model.json',
                'emblem-73014714-placement-confirmation.json')]
            _, progress = report(conn, *records)
            self.assertEqual(len(progress['published_exact_parts']), 4)
            self.assertFalse(any(i['code'] == 'citation_closure'
                for e in progress['publication_exclusions'] for i in e['issues']))
        finally:
            source.close()
            conn.close()
