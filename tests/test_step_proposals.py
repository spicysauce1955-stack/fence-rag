"""Machine proposals onto `step_candidates` — `fence_evidence/step_proposals.py`.

`proposed_kind`/`proposed_scope`/`proposed_slot`/`proposal_basis` exist so a
machine can propose and a person can dispose, and on 2026-09-15 every row in the
store had all four NULL: a reviewer typed `kind` and `scope` from scratch for
every instruction, and `procedures.build_procedures` publishes nothing without
both. This module fills the proposal columns from an independent reader's
extraction file — and the interesting part is everything it REFUSES to fill.

Four refusals, each with a test below, each guarding a way a proposal could
become an assertion nobody made:

* a step the store cannot locate is not imported at all. The anchor is
  (document, page, normalised text), never the reader's ordering, so a matched
  proposal is evidence that the text is really on that page;
* a candidate a person has already reviewed is never touched — A1/CUR-S0 on a
  new seam;
* two readers who disagree leave `proposed_kind` NULL and BOTH readings in the
  basis. A reviewer told "reader A says assembly, reader B says installation"
  is better served than one shown a coin flip;
* a `prohibition` gets no step kind however the readers typed it. The design's
  worked example publishes `Never strike the PVC post…` as a `Warning`, and
  typing it `step` was a real defect once.

The fixtures below are synthetic so the tests do not move when somebody re-runs
the splitter (`candidate_id` has moved four times in one day); the two
`requires_store` tests at the end measure the same code against the real store
and the real reader files in `example/`.
"""
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from context import ROOT, requires_store  # noqa: F401
from fence_evidence.paths import TESTS_DIR
from fence_evidence.reviews import STEP_KINDS, STEP_SCOPES, submit_step_review
from fence_evidence.step_proposals import PROPOSAL_TAG, import_proposals, normalise
from fence_evidence.store import SCHEMA

DOC = "doc-test-guide"
VERSION = "ver-test-guide"

# Four candidates that stand in for the four shapes the real page 8 has: a plain
# bullet, a second bullet the readers will disagree about, a bullet whose
# capital the text layer split (`N\never`), and a bullet no reader ever saw.
CANDIDATES = [
    # (seq, segment_kind, leader, text_raw, text_repair)
    (1, "step", "•", "• Stake out the fence line\n", None),
    (2, "step", "•", "• Assemble gates (if necessary)\n", None),
    (3, "prohibition", "•", "• N\never strike the PVC post",
     "Never strike the PVC post"),
    (4, "step", "•", "• Bell bottom of holes", None),
]


def _store() -> sqlite3.Connection:
    """An in-memory store holding one document, one page and four candidates."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute(
        """INSERT INTO documents (document_id, source_path, file_type, corpus_track,
                                  version_status, structural, in_curated_index, title)
           VALUES (?,?,?,?,?,?,?,?)""",
        (DOC, "manuals/test/test-guide.pdf", "pdf", "us", "unknown", 0, 1,
         "Test Guide"))
    start = 0
    for seq, kind, leader, raw, repair in CANDIDATES:
        conn.execute(
            """INSERT INTO step_candidates
                 (document_id, version_id, page_no, element_id, ordinal, seq,
                  char_start, char_end, text_raw, text_repair, segment_kind,
                  leader, depth, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (DOC, VERSION, 8, "element-test-1", 1, seq, start,
             start + len(raw), raw, repair, kind, leader, 0, "2026-09-15T00:00:00+00:00"))
        start += len(raw)
    conn.commit()
    return conn


def _reading(path: Path, steps, *, document="test-guide.pdf") -> Path:
    """Write a reader's extraction file in the shape the two real ones have."""
    payload = {"document": document,
               "step_4_mapping": {"procedures": [{"steps": steps}]}}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _step(text, kind, scope, page=8, slots=None):
    return {"kind": kind, "scope": scope, "slots": slots or [],
            "text_en": text, "evidence": {"page": page, "quote": text}}


def _tmpdir(case: unittest.TestCase) -> Path:
    """A scratch dir for reader files, inside `workspace/` and cleaned up.

    Inside workspace because `paths.ensure_writable` applies to tests too;
    cleaned up because a per-test `mkdtemp` that nothing removes left 120
    directories behind on the first run of this file.
    """
    TESTS_DIR.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="proposals-", dir=TESTS_DIR))
    case.addCleanup(shutil.rmtree, path, True)
    return path


def _row(conn, seq):
    return conn.execute(
        "SELECT * FROM step_candidates WHERE seq=?", (seq,)).fetchone()


def _blob(row):
    """The JSON this module appended to `proposal_basis`, parsed."""
    for line in (row["proposal_basis"] or "").splitlines():
        if line.startswith(PROPOSAL_TAG):
            return json.loads(line[len(PROPOSAL_TAG):])
    return None


class TestAProposalIsAnchoredOnText(unittest.TestCase):

    def test_a_step_reaches_the_candidate_holding_its_text_not_the_one_at_its_index(self):
        """Order is the reader's, text is the document's.

        A reader's `procedures[].steps[]` is its own ordering of the page, and
        it is not the splitter's: the real gate reading emits 51 steps for a
        page the splitter cut into 71 candidates. Importing by position would
        put every proposal on the wrong row and nothing would notice, because a
        wrong `kind` on a real instruction still looks like a proposal.
        """
        conn = _store()
        self.addCleanup(conn.close)
        d = _tmpdir(self)
        # Deliberately last in the file; it belongs to the FIRST candidate.
        path = _reading(d / "reader-a.json", [
            _step("Bell bottom of holes", "installation", "post"),
            _step("Stake out the fence line", "preparation", "run"),
        ])
        report = import_proposals(conn, [path])
        self.assertEqual(report["located"], 2)
        self.assertEqual(_row(conn, 1)["proposed_kind"], "preparation")
        self.assertEqual(_row(conn, 1)["proposed_scope"], "run")
        self.assertEqual(_row(conn, 4)["proposed_kind"], "installation")

    def test_a_step_no_candidate_holds_is_refused_and_counted(self):
        """The refusal is the proof that the text is real.

        An import that silently accepted a step the store cannot locate would
        be importing the reader's paraphrase, not the document's sentence — and
        `AssemblyStep.text` is published verbatim from a cited element. Counting
        the misses is how we measure a reader's fidelity rather than assuming it.
        """
        conn = _store()
        self.addCleanup(conn.close)
        d = _tmpdir(self)
        path = _reading(d / "reader-a.json", [
            _step("Stake out the fence line", "preparation", "run"),
            _step("Tighten the flux capacitor", "installation", "post"),
            # Right text, wrong page: the page is part of the anchor.
            _step("Bell bottom of holes", "installation", "post", page=9),
        ])
        report = import_proposals(conn, [path])
        self.assertEqual(report["located"], 1)
        self.assertEqual(report["unlocated"], 2)
        self.assertIsNone(_row(conn, 4)["proposed_kind"])
        self.assertIn("Tighten the flux capacitor",
                      " ".join(report["unlocated_samples"]))

    def test_a_split_capital_is_matched_through_the_repair_the_splitter_proposed(self):
        """`N\\never strike` and `Never strike` are the same instruction.

        The text layer breaks a leading capital off 195 segments, so the reader
        — which reads the PDF, not our store — quotes the repaired sentence.
        Matching only `text_raw` would refuse exactly the rows whose damage is
        already understood, and `text_repair` exists because the splitter
        already worked out what the sentence says.
        """
        conn = _store()
        self.addCleanup(conn.close)
        d = _tmpdir(self)
        path = _reading(d / "reader-a.json", [
            _step("Never strike the PVC post", "installation", "post")])
        report = import_proposals(conn, [path])
        self.assertEqual(report["located"], 1)
        self.assertEqual(report["matched_via_repair"], 1)

    def test_normalise_erases_the_leader_and_the_typographic_spaces_only(self):
        """Matching must survive `\\u2002` and a bullet, not rewrite words.

        The candidate carries its leader (`•\\u2002`) and the reader does not.
        Everything else is left alone: if normalisation started dropping
        punctuation, `30" deep` and `30 deep` would match and a dimension would
        silently acquire somebody else's classification.
        """
        self.assertEqual(normalise("• Stake out the fence line\n"),
                         normalise("Stake out the fence line"))
        self.assertNotEqual(normalise('Dig holes 30" deep'),
                            normalise("Dig holes 30 deep"))


class TestAPersonOutranksEveryReader(unittest.TestCase):

    def test_a_candidate_a_person_has_reviewed_is_left_exactly_as_it_was(self):
        """A1/CUR-S0, applied to the step seam.

        Machine agreement was laundered into curation level 2 once and 324 facts
        had to be un-promoted. A proposal landing on a row somebody has already
        judged is the same mistake wearing a different column name: it would
        show the next reviewer a machine's `kind` beside a person's decision
        with nothing saying which is which.
        """
        conn = _store()
        self.addCleanup(conn.close)
        row = _row(conn, 1)
        submit_step_review(
            conn, element_id=row["element_id"], char_start=row["char_start"],
            char_end=row["char_end"], text_seen=row["text_raw"],
            reviewer="tester", verdict="accepted", step_kind="preparation",
            step_scope="site")
        d = _tmpdir(self)
        path = _reading(d / "reader-a.json", [
            _step("Stake out the fence line", "installation", "post")])
        report = import_proposals(conn, [path])
        after = _row(conn, 1)
        self.assertEqual(report["skipped_reviewed"], 1)
        self.assertIsNone(after["proposed_kind"])
        self.assertIsNone(after["proposal_basis"])


class TestTheBasisSaysWhoProposed(unittest.TestCase):

    def test_the_basis_names_the_reader_and_the_file_it_came_from(self):
        """A proposal with no provenance is indistinguishable from a decision.

        `proposal_basis` is the only column that can say "a machine said this,
        and here is which one" — the reviewer console shows the proposal next to
        the text, and without the reader's name a second reader's contradicting
        opinion has nowhere to live either.
        """
        conn = _store()
        self.addCleanup(conn.close)
        d = _tmpdir(self)
        path = _reading(d / "bufftech-simtek-extraction.json", [
            _step("Stake out the fence line", "preparation", "run")])
        import_proposals(conn, [path])
        blob = _blob(_row(conn, 1))
        self.assertEqual(len(blob["readers"]), 1)
        self.assertEqual(blob["readers"][0]["reader"], "bufftech-simtek-extraction")
        self.assertTrue(blob["readers"][0]["source_file"].endswith(
            "bufftech-simtek-extraction.json"))
        self.assertEqual(blob["readers"][0]["kind"], "preparation")

    def test_a_basis_another_proposer_already_wrote_survives_the_import(self):
        """`pair_numbered_flow` writes this column too, and got there first.

        It records which glyph it paired a body with, and `cli steps
        --pair-numbered` counts rows by `proposal_basis LIKE
        'numbered_flow_pair:%'`. Overwriting it would delete the only record of
        how a candidate came to exist and silently zero that count.
        """
        conn = _store()
        self.addCleanup(conn.close)
        prior = "numbered_flow_pair: glyph element element-x text '3.'"
        conn.execute("UPDATE step_candidates SET proposal_basis=? WHERE seq=1",
                     (prior,))
        d = _tmpdir(self)
        path = _reading(d / "reader-a.json", [
            _step("Stake out the fence line", "preparation", "run")])
        import_proposals(conn, [path])
        basis = _row(conn, 1)["proposal_basis"]
        self.assertTrue(basis.startswith("numbered_flow_pair:"))
        self.assertEqual(_blob(_row(conn, 1))["readers"][0]["kind"], "preparation")

    def test_importing_the_same_reading_twice_leaves_one_proposal_not_two(self):
        """The command has to be safe to re-run; every other one here is.

        A reader file gets re-generated and re-imported, and a `proposal_basis`
        that accumulated a JSON line per run would grow without bound and make
        "which readers proposed this" unanswerable.
        """
        conn = _store()
        self.addCleanup(conn.close)
        d = _tmpdir(self)
        path = _reading(d / "reader-a.json", [
            _step("Stake out the fence line", "preparation", "run")])
        import_proposals(conn, [path])
        first = _row(conn, 1)["proposal_basis"]
        import_proposals(conn, [path])
        self.assertEqual(_row(conn, 1)["proposal_basis"], first)
        self.assertEqual(first.count(PROPOSAL_TAG), 1)


class TestTwoReadersDisagreeingIsInformation(unittest.TestCase):

    def test_readers_that_agree_write_the_kind_they_agree_on(self):
        """Agreement between independent readings is the case worth proposing."""
        conn = _store()
        self.addCleanup(conn.close)
        d = _tmpdir(self)
        a = _reading(d / "reader-a.json", [
            _step("Stake out the fence line", "preparation", "run")])
        b = _reading(d / "reader-b.json", [
            _step("Stake out the fence line", "preparation", "run")])
        report = import_proposals(conn, [a, b])
        row = _row(conn, 1)
        self.assertEqual(row["proposed_kind"], "preparation")
        self.assertEqual(report["kind_agreed"], 1)
        self.assertEqual(_blob(row)["kind_agreement"], "agreed")
        self.assertEqual(len(_blob(row)["readers"]), 2)

    def test_readers_that_disagree_write_no_kind_and_keep_both_readings(self):
        """A coin flip would be this platform asserting something nobody decided.

        The real files do this on the page-8 quick reference: one reads
        `Assemble gates…` as `assembly`, the other as `installation`. Publishing
        either as THE proposal hides that the question is open; recording both
        turns the reviewer's job from typing into choosing.
        """
        conn = _store()
        self.addCleanup(conn.close)
        d = _tmpdir(self)
        a = _reading(d / "reader-a.json", [
            _step("Assemble gates (if necessary)", "assembly", "panel")])
        b = _reading(d / "reader-b.json", [
            _step("Assemble gates (if necessary)", "installation", "panel")])
        report = import_proposals(conn, [a, b])
        row = _row(conn, 2)
        self.assertIsNone(row["proposed_kind"])
        self.assertEqual(row["proposed_scope"], "panel")
        self.assertEqual(report["kind_disagreed"], 1)
        blob = _blob(row)
        self.assertEqual(blob["kind_agreement"], "disagreed")
        self.assertEqual({r["reader"]: r["kind"] for r in blob["readers"]},
                         {"reader-a": "assembly", "reader-b": "installation"})

    def test_kind_and_scope_are_settled_one_at_a_time(self):
        """Disagreement about scope is not disagreement about kind.

        In the real pair, scope is the noisier axis — one reader withholds it on
        158 steps and the other on 96 — so voiding an agreed `kind` because the
        scopes differ would throw away most of what the two agree on.
        """
        conn = _store()
        self.addCleanup(conn.close)
        d = _tmpdir(self)
        a = _reading(d / "reader-a.json", [
            _step("Bell bottom of holes", "installation", "post")])
        b = _reading(d / "reader-b.json", [
            _step("Bell bottom of holes", "installation", "site")])
        import_proposals(conn, [a, b])
        row = _row(conn, 4)
        self.assertEqual(row["proposed_kind"], "installation")
        self.assertIsNone(row["proposed_scope"])

    def test_a_reader_that_withholds_a_scope_does_not_veto_the_other(self):
        """`scope: null` is an abstention, not a third opinion.

        Both real readers mark withheld fields explicitly rather than guessing,
        so treating a null as a competing value would make every step one reader
        was unsure about unproposable.
        """
        conn = _store()
        self.addCleanup(conn.close)
        d = _tmpdir(self)
        a = _reading(d / "reader-a.json", [
            _step("Bell bottom of holes", "installation", None)])
        b = _reading(d / "reader-b.json", [
            _step("Bell bottom of holes", "installation", "post")])
        import_proposals(conn, [a, b])
        self.assertEqual(_row(conn, 4)["proposed_scope"], "post")


class TestAValueOutsideTheClosedListIsRefused(unittest.TestCase):

    def test_a_kind_outside_the_published_vocabulary_is_refused_and_counted(self):
        """`submit_step_review` refuses these; a proposal must refuse them too.

        Otherwise the column offers a reviewer a value the review path will not
        accept, and the first person to click it gets `error.bad_step_kind` with
        no explanation of where the word came from.
        """
        conn = _store()
        self.addCleanup(conn.close)
        d = _tmpdir(self)
        path = _reading(d / "reader-a.json", [
            _step("Stake out the fence line", "excavation", "run")])
        report = import_proposals(conn, [path])
        self.assertEqual(report["refused_kind"], 1)
        self.assertIsNone(_row(conn, 1)["proposed_kind"])
        self.assertEqual(_row(conn, 1)["proposed_scope"], "run")
        self.assertEqual(_blob(_row(conn, 1))["readers"][0]["kind_refused"],
                         "excavation")

    def test_a_scope_outside_the_published_vocabulary_is_refused_and_counted(self):
        """Same rule on the other axis — and `gate` is the one that shows up.

        One reader annotates 158 steps `Registry has no gate scope`, which is
        the honest answer; a reader that guessed `gate` anyway must not have it
        written into a column Planning eventually reads.
        """
        conn = _store()
        self.addCleanup(conn.close)
        d = _tmpdir(self)
        path = _reading(d / "reader-a.json", [
            _step("Stake out the fence line", "preparation", "gate")])
        report = import_proposals(conn, [path])
        self.assertEqual(report["refused_scope"], 1)
        self.assertEqual(_row(conn, 1)["proposed_kind"], "preparation")
        self.assertIsNone(_row(conn, 1)["proposed_scope"])

    def test_the_closed_lists_are_the_review_paths_own_lists(self):
        """One value, one name: the proposer must not keep a second copy.

        A private tuple here would drift from `reviews.STEP_KINDS` the first
        time a registry addition lands, and the drift would show up as a
        proposal the reviewer cannot accept.
        """
        from fence_evidence import step_proposals
        self.assertIs(step_proposals.STEP_KINDS, STEP_KINDS)
        self.assertIs(step_proposals.STEP_SCOPES, STEP_SCOPES)


class TestAProhibitionIsNotAStep(unittest.TestCase):

    def test_a_prohibition_gets_no_step_kind_however_the_readers_typed_it(self):
        """`Never strike the PVC post…` publishes as a `Warning`, not a step.

        Both readers emit it inside `procedures[].steps[]` because their shape
        has nowhere else to put it. Accepting that would re-introduce the defect
        `segment_kind='prohibition'` was added to fix, and it would do so
        through a column a reviewer is being invited to trust.
        """
        conn = _store()
        self.addCleanup(conn.close)
        d = _tmpdir(self)
        a = _reading(d / "reader-a.json", [
            _step("Never strike the PVC post", "installation", "post")])
        b = _reading(d / "reader-b.json", [
            _step("Never strike the PVC post", "installation", "post")])
        report = import_proposals(conn, [a, b])
        row = _row(conn, 3)
        self.assertIsNone(row["proposed_kind"])
        self.assertEqual(report["withheld_prohibition"], 1)
        blob = _blob(row)
        self.assertEqual(blob["kind_agreement"], "withheld_prohibition")
        self.assertEqual([r["kind"] for r in blob["readers"]],
                         ["installation", "installation"])
        self.assertIn("warning", blob["note"].lower())


class TestTheRealReadersAgainstTheRealStore(unittest.TestCase):

    GATE = ROOT / "example" / "bufftech-gate-install-guide-2-extraction.json"
    SIMTEK = ROOT / "example" / "bufftech-simtek-extraction.json"

    @requires_store
    def test_a_dry_run_locates_most_of_a_real_reading_and_refuses_the_rest(self):
        """The measurement this module exists to produce, on real bytes.

        Both files are independent readings of guides this corpus holds, and
        neither was produced from our store — so the located/unlocated split is
        a real fidelity number for the reader, not a self-fulfilling one. A dry
        run must reach it without writing, because the first thing anyone does
        with a new proposer is ask how much of it lands.
        """
        if not self.SIMTEK.is_file():
            self.skipTest("example/ readings not present")
        from fence_evidence.store import connect
        source = connect(read_only=True)
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        source.backup(conn)
        source.close()
        self.addCleanup(conn.close)
        before = conn.execute(
            "SELECT COUNT(*) FROM step_candidates WHERE proposed_kind IS NOT NULL"
        ).fetchone()[0]
        report = import_proposals(conn, [self.SIMTEK], apply=False)
        self.assertGreater(report["located"], 0)
        self.assertEqual(report["located"] + report["unlocated"],
                         report["steps_read"])
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM step_candidates "
                         "WHERE proposed_kind IS NOT NULL").fetchone()[0],
            before)

    @requires_store
    def test_the_two_real_readers_disagree_on_the_shared_quick_reference_page(self):
        """The disagreement case has to be real before it is worth a column.

        Page 8 of the 2024 guide is printed in both PDFs, so both readers cover
        it — and they differ there on `Assemble gates…`, on `Clean holes…` and
        on the scope of several bullets. If this ever returns zero
        disagreements, the two files have stopped being independent and the
        agreement signal is worth nothing.
        """
        for path in (self.GATE, self.SIMTEK):
            if not path.is_file():
                self.skipTest("example/ readings not present")
        from fence_evidence.store import connect
        source = connect(read_only=True)
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        source.backup(conn)
        source.close()
        self.addCleanup(conn.close)
        row = conn.execute(
            "SELECT document_id FROM documents WHERE source_path LIKE "
            "'%bufftech-fence-installation-guide-2024.pdf'").fetchone()
        if row is None:
            self.skipTest("2024 Bufftech guide not ingested")
        report = import_proposals(conn, [self.GATE, self.SIMTEK],
                                  document=row["document_id"], apply=False)
        self.assertGreater(report["kind_disagreed"], 0)
        self.assertGreater(report["kind_agreed"], report["kind_disagreed"])


if __name__ == "__main__":
    unittest.main()
