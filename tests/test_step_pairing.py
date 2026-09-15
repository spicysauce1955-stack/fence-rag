"""Numbered-flow glyph/body pairing into step candidates.

The second extraction seam for assembly information: manuals whose layout
types each step NUMBER as its own element and each step BODY as a separate
paragraph. `propose()` reads only `list` elements, so these flows produced
nothing; `pair_numbered_flow()` joins the elements by bbox overlap.

Every fixture value below is measured against the real store (an in-memory
copy), not invented — the same discipline as test_step_split.py.
"""
import sqlite3
import unittest

from context import ROOT, requires_store  # noqa: F401
from fence_evidence.store import connect
from fence_evidence.steps import pair_numbered_flow

MASTER_INSTALL = 'doc-3e54ae26c66c'   # weatherables-fencing-master-installation-…pdf


def _fresh():
    source = connect(read_only=True)
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    source.backup(conn)
    source.close()
    return conn


class TestNumberedFlowPairing(unittest.TestCase):

    @requires_store
    def test_pairs_the_solid_privacy_flow_bodies(self):
        conn = _fresh()
        self.addCleanup(conn.close)
        pair_numbered_flow(conn, document_id=MASTER_INSTALL)
        rows = conn.execute(
            """SELECT c.text_raw FROM step_candidates c
                JOIN elements e ON e.element_id = c.element_id
               WHERE c.document_id=? AND c.proposal_basis LIKE 'numbered_flow_pair:%'
                 AND e.page_no=7 ORDER BY e.ordinal, c.candidate_id""",
            (MASTER_INSTALL,)).fetchall()
        texts = [r['text_raw'] for r in rows]
        self.assertTrue(any('Follow the layout and post installation' in t for t in texts))
        self.assertTrue(any('Slide the bottom rail (with the aluminum' in t for t in texts))
        self.assertTrue(any('u-channels' in t for t in texts))

    @requires_store
    def test_candidate_anchors_on_the_body_element_with_pairing_provenance(self):
        conn = _fresh()
        self.addCleanup(conn.close)
        pair_numbered_flow(conn, document_id=MASTER_INSTALL)
        row = conn.execute(
            """SELECT element_id, char_start, char_end, proposal_basis, segment_kind
                FROM step_candidates
               WHERE document_id=? AND proposal_basis LIKE 'numbered_flow_pair:%'
               ORDER BY candidate_id LIMIT 1""", (MASTER_INSTALL,)).fetchone()
        self.assertIn('numbered_flow_pair: glyph element element-', row['proposal_basis'])
        # The glyph's own number is recorded for the reviewer.
        self.assertRegex(row['proposal_basis'], r"text '\d{1,2}[.)]'")
        self.assertEqual(row['char_start'], 0)
        self.assertEqual(row['char_end'], len(
            conn.execute('SELECT COALESCE(NULLIF(text,""), ocr_text) FROM elements '
                         'WHERE element_id=?', (row['element_id'],)).fetchone()[0]))
        self.assertEqual(row['segment_kind'], 'step')

    @requires_store
    def test_is_idempotent_and_never_touches_reviewed_rows(self):
        conn = _fresh()
        self.addCleanup(conn.close)
        before = conn.execute(
            'SELECT COUNT(*) FROM step_candidates WHERE document_id=?',
            (MASTER_INSTALL,)).fetchone()[0]
        pair_numbered_flow(conn, document_id=MASTER_INSTALL)
        after_first = conn.execute(
            'SELECT COUNT(*) FROM step_candidates WHERE document_id=?',
            (MASTER_INSTALL,)).fetchone()[0]
        # Simulate a human review on a paired candidate, then re-propose.
        conn.execute(
            """UPDATE step_candidates SET review_status='accepted', reviewer='Test',
                reviewed_at='2026-09-07T00:00:00'
              WHERE document_id=? AND proposal_basis LIKE 'numbered_flow_pair:%'
              LIMIT 1""", (MASTER_INSTALL,))
        conn.commit()
        reviewed = conn.execute(
            'SELECT candidate_id FROM step_candidates WHERE document_id=? AND reviewer=?',
            (MASTER_INSTALL, 'Test')).fetchone()
        pair_numbered_flow(conn, document_id=MASTER_INSTALL)
        after_second = conn.execute(
            'SELECT COUNT(*) FROM step_candidates WHERE document_id=?',
            (MASTER_INSTALL,)).fetchone()[0]
        still_reviewed = conn.execute(
            'SELECT review_status, reviewer FROM step_candidates WHERE candidate_id=?',
            (reviewed['candidate_id'],)).fetchone()
        self.assertEqual(after_first, after_second, 'second run proposes nothing new')
        self.assertGreater(after_first, before, 'the pairing seam adds candidates')
        self.assertEqual(still_reviewed['review_status'], 'accepted')
        self.assertEqual(still_reviewed['reviewer'], 'Test')

    @requires_store
    def test_does_not_steal_section_headings_as_bodies(self):
        # The measured false-pairing: glyph `8.` (y[338,351]) had its real
        # body (`If there is a small gap…`, top 338) and the NEXT section's
        # heading (`Solid Privacy with Lattice`, top 386) both inside the
        # slack window. Closest-first-line wins must pick the body.
        conn = _fresh()
        self.addCleanup(conn.close)
        pair_numbered_flow(conn, document_id=MASTER_INSTALL, page_no=7)
        rows = conn.execute(
            """SELECT c.text_raw FROM step_candidates c
               WHERE c.document_id=? AND c.proposal_basis LIKE 'numbered_flow_pair:%'
                 AND c.text_raw LIKE '%Solid Privacy with Lattice%'""",
            (MASTER_INSTALL,)).fetchall()
        self.assertEqual(len(rows), 0,
                         'a section heading must not become a glyph-paired step body')

    @requires_store
    def test_no_candidate_without_a_pairable_glyph(self):
        conn = _fresh()
        self.addCleanup(conn.close)
        before = conn.execute(
            'SELECT COUNT(*) FROM step_candidates WHERE document_id=?',
            (MASTER_INSTALL,)).fetchone()[0]
        # A page with paragraphs but no bare `N.` glyph elements.
        pair_numbered_flow(conn, document_id=MASTER_INSTALL, page_no=3)
        after = conn.execute(
            'SELECT COUNT(*) FROM step_candidates WHERE document_id=?',
            (MASTER_INSTALL,)).fetchone()[0]
        self.assertEqual(after, before,
                         'a page without glyph elements proposes nothing')


if __name__ == '__main__':
    unittest.main()