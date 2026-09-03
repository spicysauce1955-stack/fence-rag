"""Splitting a bullet block into step candidates.

A `list` element in an installation guide holds a whole bullet block, so the
unit an `AssemblyStep` is about does not exist as a row. This is the split, and
every fixture below is verbatim from the store rather than invented — the
hazards are real ones, measured across 70 installation manuals and 4,629
bullets (`docs/assembly-step-design.md` §3a).

The splitter classifies and never discards. A footnote, a `Note:` rider and a
lettered branch label are all emitted with a kind, because a reviewer needs to
see everything on the page and the alternative is a splitter that silently eats
the parts it does not understand.
"""
import unittest

from context import ROOT  # noqa: F401
from fence_evidence.steps import Segment, split_block

# --- verbatim from doc-1085f7c65c47 p8, ordinals 3, 5, 7, 9, 13, 24, 27 -------
ORD3 = ('• Be sure to call underground (811) prior to digging\n'
        '• Assemble gates (if necessary) and decide where they will\nbe located\n'
        '• Stake out the fence line')
ORD5 = ('• Dig holes 30" deep or to frost line\n'
        '- Hole size for 4x4 posts = approximately 10"\n'
        '• Clean holes and check for straight walls')
ORD7 = ('• I nsert post in hole\n• Determine rough height\n• Fill\n'
        'hole around post with concrete mix (sand, gravel\n'
        'and cement) approximately 2" or 4" below grade\n'
        '• Tamp concrete in hole to eliminate air pockets\n• L\nevel and square post')
ORD9 = ('• Insert\nrail into post\n'
        'Note: Pickets will attach to rail on the side with the\nsmall (¼") holes\n'
        '• Insert lock ring in each end of rail')
ORD13 = ('• L\nevel and square fence\n'
         '• T\no lower a post, place a wood block from corner to\n'
         'corner on the post and carefully tap with a mallet\n'
         '• N\never strike the PVC post without a wood support')
ORD24 = ('•\tIt is critical that gate hinge and latch posts are solid\n'
         'to ensure proper gate functionality. Two methods are\navailable:\n'
         'a. Aluminum gate post stiffener\n'
         '- Slide aluminum gate stiffener inside hinge, latch\n'
         'or end posts with open end facing routed hole\n'
         '- Insert post into ground\n'
         'b. Concrete and rebar*\n'
         '- Use two pieces of ½" rebar in each hinge, latch and\nend post\n'
         '- Leave gate on blocks for 72 hours to allow concrete\nto set')
ORD27 = ('* Caution – In climates that experience freeze-thaw cycles, this '
         'installation method could result in post cracking over time.\n'
         'This would not be covered by the warranty.')
ORD6 = '3. Install First Post'


def kinds(segs):
    return [s.kind for s in segs]


def texts(segs):
    """The instruction without its leader — `Segment.body`. `text` stays
    verbatim so the span slices back to it, which the first test class asserts."""
    return [s.body for s in segs]


class TestSpansAreReal(unittest.TestCase):
    """Every segment must be a genuine slice of the source, because the span is
    what the review anchor is keyed on and what a citation is scoped by."""

    def test_every_span_slices_back_to_its_own_text(self):
        for block in (ORD3, ORD5, ORD7, ORD9, ORD13, ORD24, ORD27, ORD6):
            for seg in split_block(block, text_source="pdf_text_layer"):
                self.assertEqual(block[seg.start:seg.end], seg.text,
                                 f"span {seg.start}:{seg.end} does not slice back")

    def test_spans_do_not_overlap_and_advance(self):
        segs = split_block(ORD7, text_source="pdf_text_layer")
        for a, b in zip(segs, segs[1:]):
            self.assertLessEqual(a.end, b.start, "segments overlap")


class TestLeaders(unittest.TestCase):
    def test_en_space_after_the_bullet_is_a_leader(self):
        segs = split_block(ORD3, text_source="pdf_text_layer")
        self.assertEqual(kinds(segs), ["step"] * 3)
        self.assertEqual(texts(segs)[0],
                         "Be sure to call underground (811) prior to digging")

    def test_plain_space_after_the_bullet_is_a_leader(self):
        segs = split_block(ORD7, text_source="pdf_text_layer")
        self.assertEqual(len(segs), 5)
        self.assertEqual(kinds(segs), ["step"] * 5)

    def test_tab_after_the_bullet_is_a_leader(self):
        segs = split_block(ORD24, text_source="pdf_text_layer")
        self.assertEqual(segs[0].kind, "step")
        self.assertTrue(texts(segs)[0].startswith("It is critical that gate hinge"))

    def test_a_dash_is_a_second_level_bullet(self):
        segs = split_block(ORD5, text_source="pdf_text_layer")
        self.assertEqual(kinds(segs), ["step", "step", "step"])
        self.assertEqual([s.depth for s in segs], [0, 1, 0])
        self.assertEqual(texts(segs)[1], 'Hole size for 4x4 posts = approximately 10"')

    def test_a_text_layer_asterisk_is_a_footnote_not_a_bullet(self):
        """71 elements corpus-wide, nearly all this same Caution string. Reading
        it as a bullet manufactures a step that the page does not contain."""
        segs = split_block(ORD27, text_source="pdf_text_layer")
        self.assertEqual(kinds(segs), ["footnote"])

    def test_an_ocr_asterisk_is_a_bullet(self):
        """Tesseract never emits U+2022 — zero times in 834 OCR'd list elements
        — so under OCR the asterisk is the bullet glyph, not a footnote."""
        block = "* Hammer or mallet\n* Wooden stakes\n* Level"
        segs = split_block(block, text_source="ocr")
        self.assertEqual(kinds(segs), ["step"] * 3)
        self.assertEqual(texts(segs), ["Hammer or mallet", "Wooden stakes", "Level"])

    def test_a_section_header_yields_no_steps(self):
        segs = split_block(ORD6, text_source="pdf_text_layer")
        self.assertEqual(kinds(segs), ["section"])


class TestTheHazardsOnPageEight(unittest.TestCase):
    def test_a_note_rider_is_split_off_the_instruction(self):
        """14 segments corpus-wide end with one and none starts with one, so it
        is always a trailing rider on the step above — not part of it."""
        segs = split_block(ORD9, text_source="pdf_text_layer")
        self.assertEqual(kinds(segs), ["step", "note", "step"])
        self.assertEqual(texts(segs)[0], "Insert rail into post")
        self.assertTrue(texts(segs)[1].startswith("Note: Pickets will attach"))

    def test_a_lettered_branch_becomes_its_own_segment_with_its_substeps(self):
        """p8 ordinal 24 is one 871-character bullet holding a two-branch choice
        with sub-steps beneath each. One bullet, one step would publish a
        900-character 'step' that is really thirteen, and would lose that a and
        b are alternatives rather than a sequence."""
        segs = split_block(ORD24, text_source="pdf_text_layer")
        self.assertEqual(kinds(segs),
                         ["step", "branch", "step", "step", "branch", "step", "step"])
        self.assertEqual([s.branch for s in segs],
                         [None, "a", "a", "a", "b", "b", "b"])

    def test_the_cure_step_survives_as_its_own_segment(self):
        """The 72-hour cure is one of two cases the contract argues from, and it
        is buried inside ordinal 24's block."""
        segs = split_block(ORD24, text_source="pdf_text_layer")
        cure = [s for s in segs if "72 hours" in " ".join(s.text.split())]
        self.assertEqual(len(cure), 1)
        self.assertEqual(cure[0].branch, "b")
        self.assertEqual(cure[0].depth, 1)


class TestTheSplitCapitalRepair(unittest.TestCase):
    """195 of 4,629 segments begin with a split capital, which is exactly the
    token a verb-based classifier reads first. The splitter PROPOSES a repair;
    it never applies one, because only 7 of the 20 distinct space-form artifacts
    are real damage and the rest are legitimate text."""

    def test_a_newline_split_capital_is_proposed_for_repair(self):
        segs = split_block(ORD13, text_source="pdf_text_layer")
        self.assertEqual([s.repair for s in segs][0], "Level and square fence")

    def test_a_space_split_capital_is_proposed_for_repair(self):
        segs = split_block(ORD7, text_source="pdf_text_layer")
        self.assertEqual(segs[0].repair, "Insert post in hole")

    def test_the_verbatim_text_is_never_altered(self):
        for block in (ORD7, ORD13):
            for seg in split_block(block, text_source="pdf_text_layer"):
                self.assertEqual(block[seg.start:seg.end], seg.text,
                                 "the source slice was rewritten in place")

    def test_no_repair_is_proposed_when_nothing_is_damaged(self):
        segs = split_block(ORD3, text_source="pdf_text_layer")
        self.assertEqual([s.repair for s in segs], [None, None, None])

    def test_a_soft_wrap_is_not_mistaken_for_a_split_capital(self):
        """`• Fill\\nhole around post` is a wrapped line, not a broken word: the
        capital is a whole word already."""
        segs = split_block(ORD7, text_source="pdf_text_layer")
        fill = [s for s in segs if s.body.startswith("Fill hole")]
        self.assertEqual(len(fill), 1)
        self.assertIsNone(fill[0].repair)


class TestItDiscardsNothing(unittest.TestCase):
    def test_every_character_of_the_block_is_accounted_for(self):
        """A splitter that silently eats what it does not understand is worse
        than one that classifies it, because the loss is invisible."""
        for block in (ORD3, ORD5, ORD7, ORD9, ORD13, ORD24, ORD27):
            segs = split_block(block, text_source="pdf_text_layer")
            covered = "".join(block[s.start:s.end] for s in segs)
            dropped = "".join(block.split()) .replace("".join(covered.split()), "", 1)
            self.assertEqual(dropped.replace("•", "").replace("-", "")
                             .replace("*", "").strip(), "",
                             f"characters went missing from {block[:30]!r}")


class TestSegmentIsAValue(unittest.TestCase):
    def test_segments_compare_by_value(self):
        a = Segment(text="x", start=0, end=1, leader="•", depth=0,
                    kind="step", branch=None, repair=None)
        b = Segment(text="x", start=0, end=1, leader="•", depth=0,
                    kind="step", branch=None, repair=None)
        self.assertEqual(a, b)



class TestDefectsFoundByAdversarialValidation(unittest.TestCase):
    """Eight defects found by running the splitter over all 6,105 `list`
    elements rather than the one page it was written against. Spans, coverage
    and crash-safety held everywhere — every failure was in what gets
    *recognised*."""

    def test_an_uppercase_branch_is_a_branch(self):
        """123 elements print `A.`/`B.` where p8 prints `a.`/`b.`, and 118 of
        them collapsed into a single undifferentiated prose blob. The same
        gate-post instruction appears in the corpus in both cases; the
        lowercase copy segmented perfectly and the uppercase copy presented two
        MUTUALLY EXCLUSIVE methods as one sequential procedure. A consumer
        reading that tells an installer to do both."""
        block = ("• Two methods are available:\n"
                 "A. Aluminum gate post stiffener\n"
                 "- Slide aluminum gate stiffener inside hinge\n"
                 "B. Concrete and rebar*\n"
                 "- Use two pieces of rebar in each post")
        segs = split_block(block, text_source="pdf_text_layer")
        self.assertEqual(kinds(segs), ["step", "branch", "step", "branch", "step"])
        self.assertEqual([s.branch for s in segs], [None, "A", "A", "B", "B"])

    def test_a_numbered_instruction_is_not_a_section_heading(self):
        """`SECTION_RE` returned the whole block as one `section` and split
        nothing. 233 of 783 such blocks are instruction-shaped, so whole
        documents that number their procedure instead of bulleting it produced
        zero steps."""
        segs = split_block("3. Insert bottom rail into bottom post route holes.",
                           text_source="pdf_text_layer")
        self.assertEqual(kinds(segs), ["step"])

    def test_a_short_numbered_title_is_still_a_section(self):
        for title in ("1. Getting Started", "2. Dig Holes", "3. Install First Post"):
            self.assertEqual(kinds(split_block(title, text_source="pdf_text_layer")),
                             ["section"], title)

    def test_a_heading_broken_by_the_split_capital_is_still_a_heading(self):
        """The slice page prints `10. H\\nang Gate/Install Hardware` — the
        newline is the pdftotext artifact, not a line break. Judging
        heading-ness on the raw text made the damage decide the classification
        and dropped it to `prose`."""
        segs = split_block("10. H\nang Gate/Install Hardware",
                           text_source="pdf_text_layer")
        self.assertEqual(kinds(segs), ["section"])

    def test_a_section_still_gets_its_repair_proposed(self):
        """`10. H ang Gate/Install Hardware` is on the slice page and was
        getting `repair=None`, because the section path returned early."""
        segs = split_block("10. H ang Gate/Install Hardware",
                           text_source="pdf_text_layer")
        self.assertEqual(segs[0].repair, "10. Hang Gate/Install Hardware")

    def test_a_newline_split_is_higher_confidence_than_a_space_split(self):
        """The separator is the signal, and flattening destroyed it. Measured:
        all 249 newline-form repairs are real damage; of 71 space-form ones, 17
        are the English article `A` in `A cut panel bracket` and `A template can
        speed attachment`. 94.7% precision overall, ~100% on the newline form."""
        newline = split_block("• T\namp concrete in hole", text_source="pdf_text_layer")
        self.assertEqual(newline[0].repair, "Tamp concrete in hole")
        self.assertEqual(newline[0].repair_confidence, "high")
        # `I nsert` is the space form and real damage — 48 occurrences — so it
        # is still proposed, just not with the same confidence behind it.
        space = split_block("• I nsert post in hole", text_source="pdf_text_layer")
        self.assertEqual(space[0].repair, "Insert post in hole")
        self.assertEqual(space[0].repair_confidence, "low")

    def test_the_article_a_is_not_proposed_for_repair(self):
        """The two false-positive families, quoted verbatim from the corpus."""
        for text in ("• A cut panel bracket is required on top and bottom cut panels.",
                     "• A template can speed attachment for level installations"):
            segs = split_block(text, text_source="pdf_text_layer")
            self.assertIsNone(segs[0].repair, text)

    def test_a_real_space_form_repair_is_still_proposed(self):
        """`I nsert` is 48 occurrences and unambiguous damage. Suppressing the
        article must not suppress the rest of the space form."""
        segs = split_block("• I nsert post in hole", text_source="pdf_text_layer")
        self.assertEqual(segs[0].repair, "Insert post in hole")

    def test_an_ocr_bullet_note_is_a_note_not_a_footnote(self):
        """`_classify` keyed the footnote rule on `leader == "*"` alone. Under
        OCR the asterisk IS the bullet, so an OCR bullet whose body opens with
        `Caution` was typed `footnote`. The answer happened to be right for the
        one line it hit; the mechanism was wrong for all OCR."""
        segs = split_block("* Caution: wear goggles", text_source="ocr")
        self.assertEqual(kinds(segs), ["note"])

    def test_two_ocr_bullets_on_one_line_are_two_steps(self):
        """The line-based cut is right for the text layer — 0 of 3,146 elements
        put a bullet mid-line — but OCR merges columns, and 10 elements carry
        two unrelated instructions on one line."""
        segs = split_block(
            "* Clean holes and check for straight walls * Square pickets and rails",
            text_source="ocr")
        self.assertEqual(kinds(segs), ["step", "step"])
        self.assertEqual(texts(segs), ["Clean holes and check for straight walls",
                                       "Square pickets and rails"])

    def test_a_text_layer_bullet_mid_line_is_not_split(self):
        """The mirror of the case above: in the text layer a mid-line `•` is a
        separator in a footer (`site.com • (800) 336-2383`), never a bullet."""
        segs = split_block("• Insert rail • into post", text_source="pdf_text_layer")
        self.assertEqual(len(segs), 1)

    def test_the_instruction_kinds_are_named_so_a_filter_cannot_miss_one(self):
        """664 segments (8.4%) are `kind="branch"` and 627 of those carry a full
        instruction, so anything filtering `kind == "step"` silently drops them."""
        from fence_evidence.steps import INSTRUCTION_KINDS
        self.assertEqual(set(INSTRUCTION_KINDS), {"step", "branch"})

    def test_the_leader_gap_is_declared_not_accidental(self):
        from fence_evidence.steps import LEADER_GAP
        self.assertEqual([hex(ord(c)) for c in LEADER_GAP],
                         ["0x20", "0x9", "0x2002", "0xa0"])

if __name__ == "__main__":
    unittest.main()
