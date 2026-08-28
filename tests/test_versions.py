"""Date-aware, conservative version resolution."""
import sqlite3
import unittest

from context import requires_facts, requires_store
from fence_evidence.retrieval import resolve_document_version
from fence_evidence.store import SCHEMA, connect
from fence_evidence.versions import (ACTIVE_BASIS_KINDS, DATE_CONFIDENCE,
                                     REVIEWED_FACT_STATUSES, chain_for,
                                     document_dates, document_edition, effective_at,
                                     expiry_status, parse_date, parse_edition,
                                     select_active)

CURRENT_NOA = "23-0314.05"
LEGACY_NOA = "12-1106.11"


class TestDateParsing(unittest.TestCase):
    def test_mdy(self):
        self.assertEqual(parse_date("Approval Date: 05/04/2023"), "2023-05-04")

    def test_month_name(self):
        self.assertEqual(parse_date("Approval Date: March 12, 2015"), "2015-03-12")

    def test_iso_passthrough(self):
        self.assertEqual(parse_date("expires 2029-03-13"), "2029-03-13")

    def test_two_digit_year(self):
        self.assertEqual(parse_date("03/13/29"), "2029-03-13")

    def test_impossible_date_is_rejected(self):
        self.assertIsNone(parse_date("Approval Date: 13/45/2023"))

    def test_no_date(self):
        self.assertIsNone(parse_date("Approval Date: pending"))
        self.assertIsNone(parse_date(""))


class TestExpiryVerdict(unittest.TestCase):
    def test_expired(self):
        v = expiry_status({"expiration": {"value": "2018-03-13", "agreement": "unanimous"}},
                          as_of="2026-08-20")
        self.assertEqual(v["status"], "expired")
        self.assertEqual(v["as_of"], "2026-08-20")

    def test_in_force(self):
        v = expiry_status({"expiration": {"value": "2029-03-13", "agreement": "unanimous"}},
                          as_of="2026-08-20")
        self.assertEqual(v["status"], "in_force")

    def test_conflict_yields_no_verdict(self):
        v = expiry_status({"expiration": {"value": None, "agreement": "conflict"}},
                          as_of="2026-08-20")
        self.assertEqual(v["status"], "unknown")
        self.assertIn("disagree", v["basis"])

    def test_absent_yields_no_verdict(self):
        v = expiry_status({}, as_of="2026-08-20")
        self.assertEqual(v["status"], "unknown")

    def test_as_of_is_always_reported(self):
        for dates in ({}, {"expiration": {"value": "2029-03-13", "agreement": "unanimous"}}):
            self.assertIn("as_of", expiry_status(dates, as_of="2026-01-01"))


class TestEffectiveAt(unittest.TestCase):
    def _chain(self):
        return [
            {"document_id": "a", "dates": {"effective": {"value": "2008-01-01"}}},
            {"document_id": "b", "dates": {"effective": {"value": "2013-04-04"}}},
            {"document_id": "c", "dates": {"effective": {"value": "2023-05-04"}}},
        ]

    def test_picks_latest_at_or_before(self):
        self.assertEqual(effective_at(self._chain(), "2015-01-01")["document_id"], "b")
        self.assertEqual(effective_at(self._chain(), "2023-05-04")["document_id"], "c")

    def test_none_before_the_first(self):
        self.assertIsNone(effective_at(self._chain(), "2000-01-01"))

    def test_members_without_dates_are_ignored(self):
        chain = self._chain() + [{"document_id": "d", "dates": {}}]
        self.assertEqual(effective_at(chain, "2030-01-01")["document_id"], "c")


@requires_store
class TestSupersessionDirection(unittest.TestCase):
    """Regression: the status update once marked the wrong side of the edge.

    A `superseded_by` edge reads subject -> object, so its *from* side is the
    superseded document. Marking the *to* side flagged every current NOA as
    superseded and left the CertainTeed/Barrette chain with no active member.
    """

    @classmethod
    def setUpClass(cls):
        cls.conn = connect()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_the_superseding_document_is_not_marked_superseded(self):
        rows = self.conn.execute("""
            SELECT d.source_path, d.version_status
              FROM relations r JOIN documents d ON d.document_id = r.from_document_id
             WHERE r.relation_type='supersedes'
               AND NOT EXISTS (SELECT 1 FROM relations x
                                WHERE x.relation_type='supersedes'
                                  AND x.to_document_id = r.from_document_id)
            """).fetchall()
        self.assertGreater(len(rows), 0, "no un-superseded superseding document found")
        for r in rows:
            self.assertNotEqual(
                r["version_status"], "superseded",
                f"{r['source_path']} supersedes another approval and nothing supersedes "
                "it, yet it is marked superseded")

    def test_the_superseded_document_is_marked(self):
        rows = self.conn.execute("""
            SELECT d.source_path, d.version_status FROM relations r
              JOIN documents d ON d.document_id = r.to_document_id
             WHERE r.relation_type='supersedes'""").fetchall()
        self.assertGreater(len(rows), 0)
        for r in rows:
            self.assertEqual(r["version_status"], "superseded",
                             f"{r['source_path']} is superseded by a later approval but is "
                             f"marked {r['version_status']}")


@requires_facts
class TestResolutionUsesDateFacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = connect()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_dates_carry_provenance(self):
        res = resolve_document_version(CURRENT_NOA, as_of="2026-08-20", conn=self.conn)
        self.assertIsNotNone(res)
        eff = res["dates"]["effective"]
        self.assertEqual(eff["agreement"], "unanimous")
        self.assertTrue(eff["value"])
        self.assertGreater(len(eff["sources"]), 0)
        for src in eff["sources"]:
            self.assertTrue(src["element_id"])
            self.assertIsNotNone(src["page"])
            self.assertIn(src["review_status"], ("extracted", "flagged", "reviewed"))

    def test_expiry_verdict_reports_the_date_it_used(self):
        res = resolve_document_version(CURRENT_NOA, as_of="2026-08-20", conn=self.conn)
        self.assertEqual(res["expiry"]["as_of"], "2026-08-20")
        self.assertIn(res["expiry"]["status"], ("in_force", "expired", "unknown"))

    def test_legacy_approval_is_expired(self):
        res = resolve_document_version(LEGACY_NOA, as_of="2026-08-20", conn=self.conn)
        self.assertEqual(res["expiry"]["status"], "expired")

    def test_chain_members_are_enriched(self):
        res = resolve_document_version(CURRENT_NOA, as_of="2026-08-20", conn=self.conn)
        self.assertGreater(len(res["chain"]), 1)
        for member in res["chain"]:
            self.assertIn("dates", member)
            self.assertIn("expiry", member)

    def test_effective_at_resolves_a_historical_date(self):
        res = resolve_document_version(LEGACY_NOA, at="2015-01-01", as_of="2026-08-20",
                                       conn=self.conn)
        member = res.get("effective_at")
        self.assertIsNotNone(member, "no chain member resolved for 2015-01-01")
        self.assertLessEqual(member["dates"]["effective"]["value"], "2015-01-01")

    def test_an_expired_member_is_never_offered_as_active(self):
        for ident in (CURRENT_NOA, LEGACY_NOA):
            res = resolve_document_version(ident, as_of="2035-01-01", conn=self.conn)
            active = res.get("active")
            if active is not None:
                self.assertNotEqual(active["expiry"]["status"], "expired")
            else:
                self.assertTrue(res["active_basis"])

    def test_resolution_does_not_write_to_documents(self):
        before = self.conn.execute(
            "SELECT version_status, version_status_basis FROM documents "
            "WHERE source_path LIKE '%NOA-23-0314.05%'").fetchone()
        resolve_document_version(CURRENT_NOA, as_of="2026-08-20", conn=self.conn)
        after = self.conn.execute(
            "SELECT version_status, version_status_basis FROM documents "
            "WHERE source_path LIKE '%NOA-23-0314.05%'").fetchone()
        self.assertEqual(tuple(before), tuple(after),
                         "resolution mutated stored classification")



def _m(doc_id, status="unknown", expiry="unknown", expiration=None,
       agreement="unanimous", effective=None):
    """A chain member shaped the way ``enrich_chain`` shapes one."""
    exp = {"value": expiration, "agreement": agreement}
    if expiration is None and agreement == "unanimous":
        exp = {"value": None, "agreement": "none", "reason": "no parseable date fact"}
    dates = {"expiration": exp}
    if effective is not None:
        dates["effective"] = {"value": effective, "agreement": "unanimous"}
    verdict = {"status": expiry, "as_of": "2026-08-28"}
    if expiration and expiry in ("in_force", "expired"):
        verdict["expiration"] = expiration
    if expiry == "unknown" and agreement == "conflict":
        verdict["basis"] = "expiration date facts disagree; see candidates"
    return {"document_id": doc_id, "version_status": status,
            "dates": dates, "expiry": verdict}


class TestSelectActive(unittest.TestCase):
    """The active answer, and what it is allowed to rest on."""

    def test_explicit_mark_is_reported_as_marked(self):
        chain = [_m("a", "superseded", "expired", "2013-03-13"),
                 _m("b", "active", "in_force", "2029-03-13")]
        got = select_active(chain, as_of="2026-08-28")
        self.assertEqual(got["active"]["document_id"], "b")
        self.assertEqual(got["active_basis_kind"], "marked")

    def test_in_force_dates_can_answer_without_an_explicit_mark(self):
        """The open half of G3: a newest member demonstrably in force."""
        chain = [_m("a", "superseded", "expired", "2013-03-13"),
                 _m("b", "superseded", "expired", "2018-03-13"),
                 _m("c", "unknown", "in_force", "2029-03-13")]
        got = select_active(chain, as_of="2026-08-28")
        self.assertIsNotNone(got["active"])
        self.assertEqual(got["active"]["document_id"], "c")
        self.assertEqual(got["active_basis_kind"], "inferred_in_force")
        self.assertIn("2029-03-13", got["active_basis"])
        self.assertIn("2026-08-28", got["active_basis"])

    def test_inferred_is_distinguishable_from_marked(self):
        marked = select_active([_m("b", "active", "in_force", "2029-03-13")],
                               as_of="2026-08-28")
        inferred = select_active([_m("c", "unknown", "in_force", "2029-03-13")],
                                 as_of="2026-08-28")
        self.assertNotEqual(marked["active_basis_kind"], inferred["active_basis_kind"])
        self.assertEqual(marked["active_basis_kind"], "marked")
        self.assertEqual(inferred["active_basis_kind"], "inferred_in_force")

    def test_a_superseded_member_is_never_inferred_active(self):
        """Regression guard for the inverted-edge bug, at the inference site.

        The *from* side of a `superseded_by` edge is the superseded document, so
        a member carrying version_status='superseded' is out of the running even
        when its own expiration date has not yet passed.
        """
        chain = [_m("old", "superseded", "in_force", "2029-03-13"),
                 _m("new", "unknown", "in_force", "2029-03-13")]
        got = select_active(chain, as_of="2026-08-28")
        self.assertEqual(got["active"]["document_id"], "new")

    def test_no_dates_gives_a_weak_positional_answer_not_an_inference(self):
        chain = [_m("only")]
        got = select_active(chain, as_of="2026-08-28")
        self.assertEqual(got["active"]["document_id"], "only")
        self.assertEqual(got["active_basis_kind"], "assumed_newest")
        # The claim narrowed from "no version evidence" to "no EXPIRATION
        # evidence and no explicit status marker", because the broader wording
        # was false for the 31 documents in this branch that print an edition
        # stamp. What the test is pinning is unchanged: this answer must say
        # out loud that it is positional.
        self.assertIn("no EXPIRATION evidence", got["active_basis"])
        self.assertIn("no explicit status marker", got["active_basis"])

    def test_two_members_in_force_is_a_conflict_not_a_pick(self):
        chain = [_m("x", "unknown", "in_force", "2029-03-13"),
                 _m("y", "unknown", "in_force", "2030-01-01")]
        got = select_active(chain, as_of="2026-08-28")
        self.assertIsNone(got["active"])
        self.assertEqual(got["active_basis_kind"], "conflict")
        self.assertEqual(sorted(got["active_candidates"]), ["x", "y"])

    def test_two_explicit_marks_is_a_conflict(self):
        chain = [_m("x", "active", "in_force", "2029-03-13"),
                 _m("y", "active", "in_force", "2030-01-01")]
        got = select_active(chain, as_of="2026-08-28")
        self.assertIsNone(got["active"])
        self.assertEqual(got["active_basis_kind"], "conflict")

    def test_disagreeing_expiration_facts_assert_nothing(self):
        chain = [_m("z", "unknown", "unknown", None, agreement="conflict")]
        got = select_active(chain, as_of="2026-08-28")
        self.assertIsNone(got["active"])
        self.assertEqual(got["active_basis_kind"], "conflict")
        self.assertIn("disagree", got["active_basis"])

    def test_an_expired_member_is_withdrawn_with_the_date_it_was_judged_on(self):
        chain = [_m("e", "active", "expired", "2019-12-09")]
        got = select_active(chain, as_of="2026-08-28")
        self.assertIsNone(got["active"])
        self.assertEqual(got["active_basis_kind"], "withdrawn")
        self.assertIn("2019-12-09", got["active_basis"])
        self.assertIn("2026-08-28", got["active_basis"])

    def test_every_member_superseded_yields_no_answer(self):
        chain = [_m("a", "superseded", "expired", "2013-03-13"),
                 _m("b", "superseded", "expired", "2018-03-13")]
        got = select_active(chain, as_of="2026-08-28")
        self.assertIsNone(got["active"])
        self.assertEqual(got["active_basis_kind"], "none")

    def test_empty_chain(self):
        got = select_active([], as_of="2026-08-28")
        self.assertIsNone(got["active"])
        self.assertEqual(got["active_basis_kind"], "none")

    def test_the_basis_kind_is_always_from_the_declared_vocabulary(self):
        for chain in ([], [_m("a")], [_m("a", "active", "in_force", "2029-03-13")],
                      [_m("a", "unknown", "in_force", "2029-03-13")],
                      [_m("a", "superseded", "expired", "2013-03-13")],
                      [_m("a", "unknown", "unknown", None, agreement="conflict")]):
            got = select_active(chain, as_of="2026-08-28")
            self.assertIn(got["active_basis_kind"], ACTIVE_BASIS_KINDS)
            self.assertTrue(got["active_basis"])


class TestEditionParsing(unittest.TestCase):
    """A printed edition stamp is evidence of an edition, never of a status."""

    def test_printed_stamps(self):
        self.assertEqual(parse_edition("WEB REV 3.21"), "2021-03")
        self.assertEqual(parse_edition("REV. 4.24 BUFFTECH"), "2024-04")
        self.assertEqual(parse_edition("WEB-REV 7.21 CAMERON"), "2021-07")
        self.assertEqual(parse_edition("CAT36-D-634250 | Revised 2/2026"), "2026-02")
        self.assertEqual(parse_edition("CAT25-D-514650 | Rev 12/25"), "2025-12")

    def test_a_cited_drawing_revision_is_not_a_document_edition(self):
        self.assertIsNone(parse_edition(
            "last revision #2 dated November 30, 2020, signed and sealed"))
        self.assertIsNone(parse_edition(
            "with Revision 4 dated 09/16/2009, signed and sealed"))

    def test_prose_and_ocr_noise_are_not_editions(self):
        self.assertIsNone(parse_edition("Review the Project Planning Guide"))
        self.assertIsNone(parse_edition("Description Date [Rev i | 24-0117.05"))
        self.assertIsNone(parse_edition("REV 13.21"))
        self.assertIsNone(parse_edition(""))


@requires_store
class TestEditionOverTheStore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = connect()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def _doc(self, like):
        row = self.conn.execute(
            "SELECT document_id FROM documents WHERE source_path LIKE ? LIMIT 1",
            (f"%{like}",)).fetchone()
        self.assertIsNotNone(row, f"{like} not in the store")
        return row["document_id"]

    def test_an_install_guide_edition_carries_its_provenance(self):
        ed = document_edition(
            self.conn, self._doc("bufftech-simtek-fence-install-guide.pdf"))
        self.assertIsNotNone(ed)
        self.assertEqual(ed["value"], "2024-04")
        self.assertEqual(ed["agreement"], "unanimous")
        self.assertTrue(ed["sources"])
        for src in ed["sources"]:
            self.assertTrue(src["element_id"])
            self.assertIsNotNone(src["page"])
            self.assertTrue(src["marker"])

    def test_a_document_with_no_stamp_reports_none_not_a_guess(self):
        ed = document_edition(self.conn, self._doc(
            "NOA-06-1019.01-fence-columbia-imperial-chesterfield.pdf"))
        self.assertIsNone(ed)

    def test_an_edition_never_becomes_a_version_status(self):
        did = self._doc("install-post-rail-ranch-rail.pdf")
        before = self.conn.execute(
            "SELECT version_status FROM documents WHERE document_id=?",
            (did,)).fetchone()[0]
        chain = chain_for(self.conn, did, as_of="2026-08-28")
        member = [m for m in chain if m["document_id"] == did][0]
        self.assertEqual(member["edition"]["value"], "2021-02")
        after = self.conn.execute(
            "SELECT version_status FROM documents WHERE document_id=?",
            (did,)).fetchone()[0]
        self.assertEqual(before, after)
        self.assertEqual(select_active(chain, as_of="2026-08-28")["active_basis_kind"],
                         "assumed_newest")


@requires_facts
class TestActiveOverTheCertainTeedChain(unittest.TestCase):
    """The chain the inverted-edge bug once broke, end to end."""

    CURRENT = ("Miami-Dade-NOA_Barrette-Outdoor-Living_"
               "Extruded-PVC-Vinyl-Fencing_24-0117.05.pdf")

    @classmethod
    def setUpClass(cls):
        cls.conn = connect()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def _chain(self, like, as_of="2026-08-28"):
        row = self.conn.execute(
            "SELECT document_id FROM documents WHERE source_path LIKE ? LIMIT 1",
            (f"%{like}",)).fetchone()
        self.assertIsNotNone(row, f"{like} not in the store")
        return chain_for(self.conn, row["document_id"], as_of=as_of)

    def test_the_current_noa_is_inferred_in_force(self):
        chain = self._chain(self.CURRENT)
        got = select_active(chain, as_of="2026-08-28")
        self.assertIsNotNone(got["active"], got["active_basis"])
        self.assertEqual(got["active_basis_kind"], "inferred_in_force")
        self.assertEqual(got["active"]["expiry"]["status"], "in_force")

    def test_the_selected_member_is_not_superseded_by_another_member(self):
        chain = self._chain(self.CURRENT)
        got = select_active(chain, as_of="2026-08-28")
        chosen = got["active"]["document_id"]
        row = self.conn.execute(
            """SELECT 1 FROM relations WHERE relation_type='supersedes'
                 AND to_document_id=?""", (chosen,)).fetchone()
        self.assertIsNone(row, f"{chosen} is superseded by a later approval")

    def test_a_legacy_member_never_becomes_the_active_answer(self):
        chain = self._chain("NOA-12-1106.11-extruded-pvc-vinyl-fencing.pdf")
        got = select_active(chain, as_of="2026-08-28")
        if got["active"] is not None:
            self.assertNotEqual(got["active"]["expiry"]["status"], "expired")
            self.assertNotEqual(got["active"]["version_status"], "superseded")

    def test_past_every_expiry_nothing_is_offered_as_active(self):
        chain = self._chain(self.CURRENT, as_of="2035-01-01")
        got = select_active(chain, as_of="2035-01-01")
        self.assertIsNone(got["active"])
        self.assertIn(got["active_basis_kind"], ("withdrawn", "none", "conflict"))



# --------------------------------------------------------------------------
# What a review does to a date
# --------------------------------------------------------------------------
#
# The fact review loop writes `facts.reviewed_value` and never touches
# `value_original` (G44 is what happens when a reader ignores that). Version
# resolution is the highest-stakes reader in the package -- it decides whether
# an approval is in force -- so it must answer on the person's value, keep the
# machine's visible, and refuse to answer at all on a fact a person rejected.
#
# Everything below runs against a store built from `store.SCHEMA` in memory:
# no corpus, no ingested database, nothing that can be damaged.

SYNTH_SHA = "b" * 64


def _date_store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute("""INSERT INTO documents(document_id, source_path, file_type,
        corpus_track, version_status) VALUES
        ('doc-1','manuals/x/noa.pdf','pdf','us','unknown')""")
    conn.execute("""INSERT INTO document_versions(version_id, document_id, sha256,
        ingested_at) VALUES ('v1','doc-1',?,'2026-08-28T00:00:00+00:00')""",
                 (SYNTH_SHA,))
    conn.execute("""INSERT INTO pages(page_id, version_id, page_no, width, height,
        extraction_method) VALUES ('p1','v1',1,612.0,792.0,'ocr')""")
    for eid, ordinal in (("e1", 1), ("e2", 2)):
        conn.execute("""INSERT INTO elements(element_id, page_id, version_id,
            document_id, page_no, ordinal, element_type, text, text_source,
            ocr_confidence, bbox) VALUES (?, 'p1','v1','doc-1',1,?,'paragraph',
            'expiration date', 'ocr', 41.0, '[72.0, 100.0, 300.0, 120.0]')""",
                     (eid, ordinal))
    conn.commit()
    return conn


def _date_fact(conn, *, fact_type="expiration_date", value="03/13/2019",
               status="flagged", reviewed_value=None, reviewer=None,
               element_id="e1", page_no=1):
    """One date fact, with the review projection set the way `reviews` sets it.

    `reviews._project_fact` writes exactly these columns: `review_status`,
    `reviewed_value`, `reviewed_value_normalized`, `reviewer`, `reviewed_at`.
    A rejection is `review_status='rejected'` with `reviewed_value` NULL --
    checked against `reviews.FACT_STATUS_FOR_VERDICT`, not assumed.
    """
    cur = conn.execute("""INSERT INTO facts(document_id, version_id, page_no,
        element_id, fact_type, value_original, value_normalized, conditions,
        evidence_text, extractor, ocr_derived, review_status, created_at,
        reviewed_value, reviewer, reviewed_at)
        VALUES ('doc-1','v1',?,?,?,?,NULL,'{}','...','regex-v1',1,?,
                '2026-08-28T00:00:00+00:00',?,?,?)""",
        (page_no, element_id, fact_type, value, status, reviewed_value, reviewer,
         "2026-08-28T00:00:00+00:00" if reviewer else None))
    conn.commit()
    return cur.lastrowid


class TestReviewedDateFacts(unittest.TestCase):
    def setUp(self):
        self.conn = _date_store()

    def tearDown(self):
        self.conn.close()

    # ---------------------------------------------------------- the value
    def test_a_corrected_expiration_resolves_on_the_persons_value(self):
        """G44, one reader out. The machine read 2019; the person read 2029."""
        _date_fact(self.conn, value="Expires 03/13/2019", status="reviewed",
                   reviewed_value="Expires 03/13/2029", reviewer="J. Curator")
        exp = document_dates(self.conn, "doc-1")["expiration"]
        self.assertEqual(exp["value"], "2029-03-13")
        self.assertEqual(exp["agreement"], "unanimous")

    def test_the_correction_flips_the_expiry_verdict(self):
        _date_fact(self.conn, value="Expires 03/13/2019", status="reviewed",
                   reviewed_value="Expires 03/13/2029", reviewer="J. Curator")
        verdict = expiry_status(document_dates(self.conn, "doc-1"),
                                as_of="2026-08-28")
        self.assertEqual(verdict["status"], "in_force")
        self.assertEqual(verdict["expiration"], "2029-03-13")

    def test_an_accepted_fact_answers_exactly_as_it_did_before_review(self):
        before = _date_store()
        _date_fact(before, value="Expires 03/13/2029", status="flagged")
        _date_fact(self.conn, value="Expires 03/13/2029", status="reviewed",
                   reviewer="J. Curator")
        was = document_dates(before, "doc-1")["expiration"]
        now = document_dates(self.conn, "doc-1")["expiration"]
        before.close()
        self.assertEqual(was["value"], now["value"])
        self.assertNotIn("corrected_from", now,
                         "an acceptance corrects nothing and must not claim to")
        self.assertNotIn("corrected", now["sources"][0])

    # ------------------------------------------------- the original survives
    def test_the_machine_value_is_still_reachable_after_a_correction(self):
        _date_fact(self.conn, value="Expires 03/13/2019", status="reviewed",
                   reviewed_value="Expires 03/13/2029", reviewer="J. Curator")
        exp = document_dates(self.conn, "doc-1")["expiration"]
        src = exp["sources"][0]
        self.assertEqual(src["original"], "Expires 03/13/2019")
        self.assertEqual(src["corrected"], "Expires 03/13/2029")
        self.assertEqual(src["reviewer"], "J. Curator")

    def test_the_correction_is_visible_without_opening_the_sources(self):
        """A caller reading only the verdict must still see that the date it is
        acting on is not the one the machine read."""
        _date_fact(self.conn, value="Expires 03/13/2019", status="reviewed",
                   reviewed_value="Expires 03/13/2029", reviewer="J. Curator")
        dates = document_dates(self.conn, "doc-1")
        self.assertEqual(dates["expiration"]["corrected_from"],
                         ["Expires 03/13/2019"])
        verdict = expiry_status(dates, as_of="2026-08-28")
        self.assertEqual(verdict["corrected_from"], ["Expires 03/13/2019"])

    # -------------------------------------------------------- the rejection
    def test_a_rejected_date_does_not_answer(self):
        _date_fact(self.conn, value="Expires 03/13/2019", status="rejected",
                   reviewer="J. Curator")
        exp = document_dates(self.conn, "doc-1")["expiration"]
        self.assertIsNone(exp["value"])
        self.assertEqual(exp["agreement"], "none")
        self.assertEqual(exp["rejected"], 1)
        self.assertIn("reject", exp["reason"])

    def test_a_rejection_is_never_silent_when_another_fact_answers(self):
        _date_fact(self.conn, value="Expires 03/13/2019", status="rejected",
                   reviewer="J. Curator")
        _date_fact(self.conn, value="Expires 03/13/2029", status="extracted",
                   element_id="e2")
        exp = document_dates(self.conn, "doc-1")["expiration"]
        self.assertEqual(exp["value"], "2029-03-13")
        self.assertEqual(exp["rejected"], 1)

    def test_a_rejected_date_never_makes_a_member_active(self):
        _date_fact(self.conn, value="Expires 03/13/2029", status="rejected",
                   reviewer="J. Curator")
        chain = chain_for(self.conn, "doc-1", as_of="2026-08-28")
        got = select_active(chain, as_of="2026-08-28")
        self.assertEqual(got["active_basis_kind"], "assumed_newest",
                         "a rejected date must not be evidence of being in force")

    def test_rejection_is_the_status_reviews_actually_writes(self):
        from fence_evidence import reviews
        self.assertEqual(reviews.FACT_STATUS_FOR_VERDICT["rejected"], "rejected")
        self.assertEqual(reviews.FACT_STATUS_FOR_VERDICT["accepted"], "reviewed")
        self.assertEqual(reviews.FACT_STATUS_FOR_VERDICT["corrected"], "reviewed")

    # -------------------------------------------------------- the confidence
    def test_flagged_still_means_review_required(self):
        _date_fact(self.conn, value="Expires 03/13/2029", status="flagged")
        self.assertEqual(document_dates(self.conn, "doc-1")["expiration"]["confidence"],
                         "review_required")

    def test_extracted_still_means_extracted(self):
        _date_fact(self.conn, value="Expires 03/13/2029", status="extracted")
        self.assertEqual(document_dates(self.conn, "doc-1")["expiration"]["confidence"],
                         "extracted")

    def test_a_reviewed_date_is_not_merely_extracted(self):
        """`reviewed` is a person having compared it to the source image. It is
        a different claim from `extracted`, and flattening the two is what let a
        corrected fact read as confident on the machine's number."""
        for reviewed_value in (None, "Expires 03/13/2030"):
            with self.subTest(reviewed_value=reviewed_value):
                conn = _date_store()
                _date_fact(conn, value="Expires 03/13/2029", status="reviewed",
                           reviewed_value=reviewed_value, reviewer="J. Curator")
                self.assertEqual(
                    document_dates(conn, "doc-1")["expiration"]["confidence"],
                    "reviewed")
                conn.close()

    def test_one_unreviewed_flagged_source_keeps_the_whole_date_review_required(self):
        _date_fact(self.conn, value="Expires 03/13/2029", status="reviewed",
                   reviewer="J. Curator")
        _date_fact(self.conn, value="Expires 03/13/2029", status="flagged",
                   element_id="e2")
        self.assertEqual(document_dates(self.conn, "doc-1")["expiration"]["confidence"],
                         "review_required")

    def test_a_reviewed_source_beside_an_unreviewed_one_is_not_reviewed(self):
        _date_fact(self.conn, value="Expires 03/13/2029", status="reviewed",
                   reviewer="J. Curator")
        _date_fact(self.conn, value="Expires 03/13/2029", status="extracted",
                   element_id="e2")
        self.assertEqual(document_dates(self.conn, "doc-1")["expiration"]["confidence"],
                         "extracted",
                         "the weakest source is what the whole date rests on")

    def test_confidence_is_always_from_the_declared_vocabulary(self):
        for status in ("extracted", "flagged", "reviewed", "accepted", "corrected",
                       "unreviewed"):
            with self.subTest(status=status):
                conn = _date_store()
                _date_fact(conn, value="Expires 03/13/2029", status=status)
                got = document_dates(conn, "doc-1")["expiration"]["confidence"]
                conn.close()
                self.assertIn(got, DATE_CONFIDENCE)

    def test_the_reviewed_statuses_match_curation_level_two(self):
        """`parameters.CURATION_LEVEL` is the authority on which statuses mean a
        person looked. If a status is added there and not here, a level-2 fact
        would be reported as machine-extracted."""
        from fence_evidence.parameters import CURATION_LEVEL
        self.assertEqual(set(REVIEWED_FACT_STATUSES),
                         {s for s, lvl in CURATION_LEVEL.items() if lvl >= 2})

    def test_the_expiry_verdict_echoes_the_reviewed_confidence(self):
        _date_fact(self.conn, value="Expires 03/13/2029", status="reviewed",
                   reviewer="J. Curator")
        verdict = expiry_status(document_dates(self.conn, "doc-1"), as_of="2026-08-28")
        self.assertEqual(verdict["confidence"], "reviewed")

    # ------------------------------------------------------------ no clocks
    def test_no_basis_string_embeds_todays_date(self):
        """A version basis that carries `date.today()` makes every committed
        artifact churn daily. `as_of` is passed in for exactly that reason."""
        from datetime import date as _date
        today = _date.today().isoformat()
        _date_fact(self.conn, value="Expires 03/13/2029", status="reviewed",
                   reviewed_value="Expires 03/13/2030", reviewer="J. Curator")
        # A stated day that is deliberately not today, so a wall-clock leak has
        # nowhere to hide.
        stated = "2026-01-15"
        self.assertNotEqual(stated, today, "pick a stated day that is not today")
        chain = chain_for(self.conn, "doc-1", as_of=stated)
        got = select_active(chain, as_of=stated)
        blob = repr(got) + repr(chain)
        self.assertNotIn(today, blob, "a resolution basis embedded the wall clock")

    def test_a_correction_is_named_in_the_active_basis(self):
        _date_fact(self.conn, value="Expires 03/13/2019", status="reviewed",
                   reviewed_value="Expires 03/13/2029", reviewer="J. Curator")
        chain = chain_for(self.conn, "doc-1", as_of="2026-08-28")
        got = select_active(chain, as_of="2026-08-28")
        self.assertEqual(got["active_basis_kind"], "inferred_in_force")
        self.assertIn("corrected", got["active_basis"].lower())
        self.assertIn("Expires 03/13/2019", got["active_basis"])


class TestUnreviewedStoreIsUntouched(unittest.TestCase):
    """Nothing is reviewed today, and the routing must be invisible until it is."""

    def test_the_shape_of_an_unreviewed_date_is_exactly_what_it_was(self):
        conn = _date_store()
        _date_fact(conn, value="Expires 03/13/2029", status="flagged")
        exp = document_dates(conn, "doc-1")["expiration"]
        conn.close()
        self.assertEqual(set(exp), {"value", "agreement", "confidence",
                                    "occurrences", "sources"})
        self.assertEqual(set(exp["sources"][0]),
                         {"element_id", "page", "original", "review_status",
                          "ocr_derived"})

    def test_the_shape_of_an_absent_date_is_exactly_what_it_was(self):
        conn = _date_store()
        exp = document_dates(conn, "doc-1")["expiration"]
        conn.close()
        self.assertEqual(set(exp), {"value", "agreement", "reason", "unparsed",
                                    "sources"})
        self.assertEqual(exp["reason"], "no parseable date fact for this document")


class TestTheBasisStringDoesNotDenyWhatTheMemberCarries(unittest.TestCase):
    """`assumed_newest`'s basis used to say the choice rests on "no version
    evidence -- the document states no date and carries no marker".

    Measured, that is false for 31 of the 125 documents this branch answers
    for: they print an edition stamp, `document_edition` reads it at 33/33
    precision, and `enrich_chain` attaches it to the very member being
    described. The decision is still right -- an edition says which printing
    this is, not whether it is in force -- but a published basis must not deny
    something the object it describes is carrying.
    """

    def _member(self, **kw):
        member = {"document_id": "doc-x", "version_status": "unknown",
                  "expiry": {"status": "unknown"}, "dates": {}}
        member.update(kw)
        return member

    def test_it_no_longer_claims_the_document_carries_no_marker(self):
        got = select_active([self._member()])
        self.assertEqual(got["active_basis_kind"], "assumed_newest")
        self.assertNotIn("carries no marker", got["active_basis"])
        self.assertIn("no EXPIRATION evidence", got["active_basis"])

    def test_an_edition_is_named_and_explicitly_not_treated_as_a_status(self):
        got = select_active([self._member(
            edition={"value": "2025-12", "agreement": "unanimous",
                     "is_version_status": False})])
        self.assertIn("2025-12", got["active_basis"])
        self.assertIn("not whether it is in force", got["active_basis"])
        self.assertEqual(got["active_basis_kind"], "assumed_newest",
                         "an edition must not promote the answer to evidence")

    def test_a_member_with_no_edition_says_nothing_about_one(self):
        got = select_active([self._member()])
        self.assertNotIn("prints edition", got["active_basis"])


if __name__ == "__main__":
    unittest.main()
