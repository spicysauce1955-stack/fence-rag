"""The review console's step workbench — the surface the sitting happens on.

Before this, the console printed the step candidates as a read-only table: the
sentence, its `segment_kind`, and a character span. A reviewer could read it and
had nowhere to put an answer, which is one reason `step_reviews` has been empty
since the table was built.

What the workbench has to hold, and what these tests pin:

* the **sentence and the page it came from, at the same time** — the decision is
  "is this an installation step or a rationale", and that cannot be made from
  the sentence alone;
* the **evidence anchor** on every row, because the decision file is applied by
  `(element_id, char_start, char_end)` and `candidate_id` is re-minted by every
  re-proposal;
* the **machine proposal where there is one and nothing where there is not** —
  another agent is filling `proposed_kind`/`proposed_scope` and they are NULL
  today, so a console that assumes them renders an empty sitting.

The text tests matter more than they look: a bullet carrying a quote mark has to
survive into a data attribute and back out as the exact bytes, or the echo check
refuses the decision at the end of an hour's work.
"""
import html
import json
import re
import sqlite3
import unittest

import context  # noqa: F401  -- puts the repo root on sys.path
from scripts import build_review_console as console
from test_step_decisions import candidates, scratch


def attr(row_html: str, name: str) -> str:
    m = re.search(rf'{name}="([^"]*)"', row_html)
    return html.unescape(m.group(1)) if m else ""


def rows_of(page_html: str) -> list[str]:
    return re.findall(r'<tr class="cand[^>]*>.*?</tr>', page_html, re.S)


class TestTheWorkbench(unittest.TestCase):
    def setUp(self):
        self.conn = scratch()

    def workbench(self, **kw):
        return console.step_workbench(self.conn, document_id="doc-1", page_no=8,
                                      **kw)

    def test_it_lists_every_candidate_on_the_chosen_page(self):
        self.assertEqual(len(rows_of(self.workbench())),
                         len(candidates(self.conn)))

    def test_every_row_carries_the_evidence_anchor_a_decision_is_applied_by(self):
        """`candidate_id` moves on every re-proposal; the (element, span) anchor
        does not, so the decision file is keyed on it."""
        row = rows_of(self.workbench())[0]
        cand = candidates(self.conn)[0]
        self.assertEqual(attr(row, "data-element"), cand["element_id"])
        self.assertEqual(int(attr(row, "data-start")), cand["char_start"])
        self.assertEqual(int(attr(row, "data-end")), cand["char_end"])

    def test_the_text_a_reviewer_saw_survives_verbatim_into_the_row(self):
        """The echo check compares it byte for byte. A bullet glyph, a quote or
        a newline mangled here refuses the decision at the end of the sitting,
        after the judgement has already been made."""
        self.conn.execute(
            "UPDATE step_candidates SET text_raw = ? WHERE seq = 0",
            ('• Use a 2" \'spacer\' & <wedge>\n',))
        row = rows_of(self.workbench())[0]
        self.assertEqual(json.loads(attr(row, "data-text")),
                         '• Use a 2" \'spacer\' & <wedge>\n')

    def test_a_machine_proposed_kind_and_scope_preselect_the_controls(self):
        """A proposal is a starting point a person confirms, never a decision:
        it fills the control, and the row is still undecided until a verdict is
        recorded."""
        self.conn.execute("UPDATE step_candidates SET proposed_kind='preparation', "
                          "proposed_scope='site' WHERE seq=0")
        row = rows_of(self.workbench())[0]
        self.assertIn('<option value="preparation" selected', row)
        self.assertIn('<option value="site" selected', row)
        self.assertEqual(attr(row, "data-verdict"), "")

    def test_a_candidate_with_no_proposal_still_renders_its_controls(self):
        """`proposed_kind` and `proposed_scope` are NULL for all 2,312
        candidates today. The workbench has to be usable before they are not."""
        row = rows_of(self.workbench())[0]
        self.assertNotIn("selected", row)
        self.assertIn('name="kind"', row)
        self.assertIn('name="scope"', row)

    def test_a_proposed_repair_is_shown_with_how_much_it_is_worth(self):
        """`repair_confidence` was computed and thrown away once, leaving a
        reviewer no way to tell a trusted newline repair from the
        `A cut panel bracket` false positives."""
        self.conn.execute("UPDATE step_candidates SET text_repair='Insert post in "
                          "hole', repair_confidence='low' WHERE seq=0")
        row = rows_of(self.workbench())[0]
        self.assertIn("Insert post in hole", row)
        self.assertIn("low", row)

    def test_a_proposed_slot_the_console_has_no_preset_for_is_still_offered(self):
        """`step_proposals` writes `{"part": ..., "target": "Footing"}` while the
        review loop's own tests and `knowledge-datamodel.md` §3.6 use a `kind`
        tag. The console must not silently drop a proposal whose shape it does
        not recognise — a dropped proposal is a decision the reviewer has to
        make again from nothing."""
        self.conn.execute("""UPDATE step_candidates
            SET proposed_slot='{"part": "hole", "target": "Footing"}' WHERE seq=0""")
        row = rows_of(self.workbench())[0]
        self.assertIn("Footing", row)
        self.assertIn("selected", row)

    def test_a_proposal_says_how_many_readers_stand_behind_it(self):
        """Two machine readers agreeing is not a review — that is exactly what
        A1/CUR-S0 revoked 324 facts over. The reviewer has to be able to see
        whether the proposal in front of them rests on one reader or two."""
        self.conn.execute("""UPDATE step_candidates SET proposed_kind='assembly',
            proposal_basis='step_proposal: {"kind_agreement": "agreed",
            "readers": [{"reader": "a"}, {"reader": "b"}]}' WHERE seq=0""")
        row = rows_of(self.workbench())[0]
        self.assertIn("2 readers", row)

    def test_the_page_image_is_inlined_beside_the_rows(self):
        out = self.workbench(image="data:image/jpeg;base64,AAAA")
        self.assertIn("data:image/jpeg;base64,AAAA", out)

    def test_a_missing_page_image_says_so_rather_than_rendering_nothing(self):
        """A reviewer who cannot see the page cannot decide, so the console must
        say the image is missing and how to render it — not quietly show a
        one-column page that looks complete."""
        out = self.workbench(image=None)
        self.assertIn("render_console_images.py", out)

    def test_a_decided_candidate_shows_the_verdict_already_recorded(self):
        """A sitting is interrupted and resumed. A row somebody already decided
        must not come back looking untouched."""
        from fence_evidence.reviews import apply_step_decisions
        from test_step_decisions import decision
        d = decision(candidates(self.conn)[0])
        apply_step_decisions(self.conn, [d], reviewer="an-owner", dry_run=False)
        row = rows_of(self.workbench())[0]
        # Whatever was recorded, not a fixed string: the first candidate here
        # carries a proposed repair, so a reviewer answering it lands on
        # `corrected`. What this test is about is that the row comes back
        # showing the decision at all.
        self.assertEqual(attr(row, "data-verdict"), d["verdict"])
        self.assertIn(d["verdict"], ("accepted", "corrected"))


class TestWhatIsWaiting(unittest.TestCase):
    def test_every_page_with_an_undecided_candidate_is_counted(self):
        """The console works one page at a time — 2,312 candidates will not fit
        on one — so it has to say what the other pages hold."""
        conn = scratch()
        waiting = console.pages_waiting(conn)
        self.assertEqual(len(waiting), 1)
        self.assertEqual(waiting[0]["document_id"], "doc-1")
        self.assertEqual(waiting[0]["page_no"], 8)
        self.assertEqual(waiting[0]["waiting"], len(candidates(conn)))

    def test_a_fully_decided_page_drops_out_of_the_queue(self):
        from fence_evidence.reviews import apply_step_decisions
        from test_step_decisions import decision
        conn = scratch()
        apply_step_decisions(conn, [decision(r) for r in candidates(conn)],
                             reviewer="an-owner", dry_run=False)
        self.assertEqual(console.pages_waiting(conn), [])

    def test_with_no_page_named_it_opens_on_a_page_that_has_work(self):
        """A console that opens on nothing is a console nobody starts from. The
        preference between pages is documented on `target_page`; what must hold
        is that the page it opens on is one with undecided candidates."""
        conn = scratch()
        target = console.target_page(conn)
        self.assertEqual(target, ("doc-1", 8))
        self.assertIn(target, [(p["document_id"], p["page_no"])
                               for p in console.pages_waiting(conn)])

    def test_a_named_document_wins_over_the_default(self):
        conn = scratch()
        self.assertEqual(console.target_page(conn, "doc-1", 8), ("doc-1", 8))
        self.assertIsNone(console.target_page(conn, "no-such-doc"))


class TestTheWholePage(unittest.TestCase):
    def test_it_names_the_command_that_applies_the_decisions(self):
        """The loop only closes if the reviewer can see how to close it. The
        console has no server behind it: the last step is a copied command."""
        conn = scratch()
        out = console.build_console(conn, snap=None)
        self.assertIn("review --apply-steps", out)
        self.assertIn("--reviewer", out)

    def test_it_says_the_ledger_must_be_exported_after_a_sitting(self):
        """A review is the one thing here that does not regenerate, and
        `tests/test_review_ledger.py` fails the build if one is recorded and not
        exported. An hour of judgement that breaks the build on the next run is
        an hour the owner will resent, so the console says both commands."""
        conn = scratch()
        out = console.build_console(conn, snap=None)
        self.assertIn("review --export", out)

    def test_it_declares_its_encoding(self):
        """Found in a browser: without a charset the page is served as Latin-1
        and every em-dash, bullet and ¾ in the corpus text renders as mojibake —
        including the glyph a reviewer needs to see to judge a bullet. The file
        is opened from disk or a plain static server, neither of which supplies
        one."""
        conn = scratch()
        out = console.build_console(conn, snap=None)
        self.assertIn('<meta charset="utf-8">', out[:200])

    def test_it_renders_before_anything_has_ever_been_published(self):
        """The console reads the latest snapshot for its counters, and a store
        that has published none is exactly the state a first sitting starts
        from."""
        conn = scratch()
        out = console.build_console(conn, snap=None)
        self.assertIn("<title>", out)

    def test_it_reports_the_published_procedure_count_when_there_is_a_snapshot(self):
        conn = scratch()
        out = console.build_console(conn, snap={"procedures": [], "gaps": [],
                                                "parameters": []})
        self.assertIn("procedures", out)


class TestThePageImagesToRender(unittest.TestCase):
    """Which pages the renderer has to shell out to poppler for.

    Tested as a plan rather than a run: the job list is the part that can be
    wrong, and the part that used to be hard-coded to one page — so a reviewer
    who moved to any other page got a console with no image on it and no way to
    tell whether a bullet was a step.
    """

    def test_every_page_with_an_undecided_step_candidate_gets_an_image(self):
        from scripts import render_console_images as render
        conn = scratch()
        jobs = render.step_jobs(conn)
        self.assertEqual(jobs, [("a.pdf", 8, "step-doc-1-p8")])

    def test_a_fully_decided_page_is_not_rendered_again(self):
        from fence_evidence.reviews import apply_step_decisions
        from scripts import render_console_images as render
        from test_step_decisions import decision
        conn = scratch()
        apply_step_decisions(conn, [decision(r) for r in candidates(conn)],
                             reviewer="an-owner", dry_run=False)
        self.assertEqual(render.step_jobs(conn), [])

    def test_one_document_can_be_asked_for_on_its_own(self):
        """Sixty pages of poppler to review one is a reason not to run it."""
        from scripts import render_console_images as render
        conn = scratch()
        self.assertEqual(render.step_jobs(conn, document_id="doc-2"), [])
