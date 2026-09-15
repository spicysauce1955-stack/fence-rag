"""A line the splitter offered to repair does not publish on a bare accept.

`[measured]` 2026-09-15: 176 of 2,312 step candidates carry a `text_repair`,
147 of them at high confidence. `build_procedures` reads `text_final` or falls
back to `_body(text_raw)`, and **never reads `text_repair`** — so an `accepted`
verdict that leaves `text_final` null publishes the damage:

    _body('• B\\ne sure to call underground (811) prior to digging')
      -> 'B e sure to call underground (811) prior to digging'
    _body('• N\\never strike the PVC post without a wood support')
      -> 'N ever strike the PVC post without a wood support'

The second is the one that matters. `N\\never` flattens to `N ever`, which is
the ordering trap CLAUDE.md records — the damage HIDES the word the meaning
turns on — and here it survives all the way to a published `AssemblyStep`.

The console makes the mistake easy rather than unlikely. It renders the raw
text, then a line reading *"proposed repair: **Insert post in hole**"*, then an
`accept` button. A reviewer pressing accept has been shown the repaired words
and has every reason to think they are what gets recorded. They are not.

The fix is a refusal, not a silent substitution. Applying the repair on the
platform's own authority is exactly the laundering CUR-S0 forbids: the splitter
*proposes* and a person *disposes*, and the measured false-positive rate on the
space form of this damage is 65% of distinct patterns. So a step whose candidate
carries an unaddressed repair publishes nothing and raises a gap naming why —
the reviewer resolves it by using `corrected` and supplying the text they mean.

The condition is exact and needs no heuristic: `text_repair IS NOT NULL AND
text_final IS NULL`. Nothing here tries to detect damage in general.
"""
import json
import sqlite3
import unittest

from context import ROOT  # noqa: F401
from fence_evidence.procedures import build_procedures
from fence_evidence.store import SCHEMA

DAMAGED = "• B\ne sure to call underground (811) prior to digging"
REPAIRED = "Be sure to call underground (811) prior to digging"
CLEAN = "• Stake out the fence line"
SHA = "71c42837fd50908464f26980af1c150357340a6d6c4a0a2b7cbec29948aa706b"


def _store(*, text_raw, text_repair, text_final):
    """One reviewed candidate on one page, with the repair state under test."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO documents(document_id, source_path, file_type, "
                 "corpus_track, title) VALUES ('doc-x','manuals/x.pdf','pdf','us','X')")
    conn.execute("INSERT INTO document_versions(version_id, document_id, sha256, "
                 "page_count, ingested_at) VALUES ('doc-x@v1','doc-x',?,1,"
                 "'2026-09-15T00:00:00+00:00')", (SHA,))
    conn.execute("INSERT INTO pages(page_id, version_id, page_no, width, height, "
                 "extraction_method) "
                 "VALUES ('doc-x@v1#p0008','doc-x@v1',8,612,792,'pdftotext-bbox')")
    conn.execute("""INSERT INTO elements(element_id, page_id, version_id, document_id,
        page_no, ordinal, element_type, text, text_source)
        VALUES ('el-1','doc-x@v1#p0008','doc-x@v1','doc-x',8,0,'list',?, 'pdf_text_layer')""",
                 (text_raw,))
    conn.execute("""INSERT INTO step_candidates(document_id, version_id, page_no,
        element_id, ordinal, seq, char_start, char_end, text_raw, text_repair,
        repair_confidence, segment_kind, leader, depth, review_status, created_at)
        VALUES ('doc-x','doc-x@v1',8,'el-1',0,0,0,?,?,?,'high','step','•',0,
                'accepted','2026-09-15T00:00:00+00:00')""",
                 (len(text_raw), text_raw, text_repair))
    conn.execute("""INSERT INTO step_reviews(step_review_id, element_id, char_start,
        char_end, text_seen, document_id, page_no, reviewer, reviewed_at, verdict,
        step_kind, step_scope, text_final, status_before)
        VALUES ('rev-1','el-1',0,?,?, 'doc-x',8,'a-person','2026-09-15T00:00:00+00:00',
                'accepted','preparation','site',?, 'unreviewed')""",
                 (len(text_raw), text_raw, text_final))
    conn.commit()
    return conn


def _cite(document_id, page_no):
    return {"id": "ref-1", "belongs_to": SHA}


def _run(**kw):
    return build_procedures(_store(**kw), source_ref_page=_cite)


class TestAnUnaddressedRepairDoesNotPublish(unittest.TestCase):
    def test_a_bare_accept_on_a_repaired_line_publishes_no_step(self):
        """The measured defect. 176 candidates can reach this state.

        Fails today: the step publishes carrying `B e sure to call…`.
        """
        procs, _ = _run(text_raw=DAMAGED, text_repair=REPAIRED, text_final=None)
        published = [s for p in procs for s in p["steps"]]
        self.assertEqual(published, [])

    def test_it_says_why_rather_than_going_quiet(self):
        """A step that vanishes with no gap is indistinguishable from a bug.

        Everything else this builder declines to publish names itself; so must
        this, or a reviewer who pressed accept sees nothing happen and no reason.
        """
        _, gaps = _run(text_raw=DAMAGED, text_repair=REPAIRED, text_final=None)
        codes = [g["because"]["code"] for g in gaps]
        self.assertIn("step_repair_not_addressed", codes)

    def test_the_reviewers_own_text_publishes(self):
        """`corrected` is the route, and it must stay open.

        The person supplies the words; nothing is inferred on their behalf.
        """
        procs, _ = _run(text_raw=DAMAGED, text_repair=REPAIRED, text_final=REPAIRED)
        published = [s["text_i18n"] for p in procs for s in p["steps"]]
        self.assertEqual(published, [REPAIRED])

    def test_the_platform_never_applies_the_repair_itself(self):
        """The whole reason this is a refusal and not a substitution.

        Reaching for `text_repair` here would let the splitter's guess publish
        on an accept that never mentioned it — the laundering CUR-S0 forbids,
        on a pattern measured to over-match 65% of the time.
        """
        procs, _ = _run(text_raw=DAMAGED, text_repair=REPAIRED, text_final=None)
        self.assertNotIn(REPAIRED, json.dumps(procs))


class TestItDoesNotDisturbTheOrdinaryCase(unittest.TestCase):
    def test_a_line_with_no_repair_proposed_still_publishes(self):
        """2,136 of 2,312 candidates carry no repair at all."""
        procs, _ = _run(text_raw=CLEAN, text_repair=None, text_final=None)
        published = [s["text_i18n"] for p in procs for s in p["steps"]]
        self.assertEqual(published, ["Stake out the fence line"])

    def test_no_gap_is_raised_where_there_was_nothing_to_address(self):
        """The gap must name a real decision the reviewer still owes."""
        _, gaps = _run(text_raw=CLEAN, text_repair=None, text_final=None)
        self.assertNotIn("step_repair_not_addressed",
                         [g["because"]["code"] for g in gaps])


if __name__ == "__main__":
    unittest.main()
