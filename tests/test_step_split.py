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


if __name__ == "__main__":
    unittest.main()
