"""G76 — one warning is one `Warning`, and unreadable text is not published.

Two fixes to `warnings()`, both measured before being written.

**Fragmentation.** The dedup key was `" ".join(text.split())` over the RAW
element text, so page-number bleed and delimiter variance each minted a
separate identity. The corpus's most-repeated warning — the code's own comment
calls it *"83 instances"* and says the design is *"one warning with several
citations"* — published as 12 objects: `'30 * Caution – …'`, `'36 * Caution –
…'`, `'42 * caution - …'`, `'4A. * Caution - …'`, `'30 + Caution - …'`.

**Undecodable text.** Two warnings published binary control characters as
"verbatim, untranslated" text. `quality.is_mojibake` cannot see it: the cipher
substitutes letters onto OTHER printable ASCII, so `ascii_token_ratio` lands
just above its 0.85 limit on every affected page (0.857–0.958) even though
`control_ratio` trips 2–4× over.
"""
import unittest

from context import ROOT  # noqa: F401
from fence_evidence.snapshot import _undecodable_ratio, _warning_key


class TestOneWarningIsOneWarning(unittest.TestCase):
    """`[measured]`: this key merges 24 objects into 7 with ZERO false merges,
    checked against all 289 published warnings."""

    CAUTION = ("In climates that experience freeze-thaw cycles, this installation "
               "method could result in post cracking over time. This would not be "
               "covered by the warranty.")

    def test_page_number_bleed_is_not_an_identity(self):
        a = _warning_key(f"30 * Caution – {self.CAUTION}")
        b = _warning_key(f"36 * Caution – {self.CAUTION}")
        self.assertEqual(a, b)

    def test_the_footnote_delimiter_is_not_an_identity(self):
        self.assertEqual(_warning_key(f"30 * Caution - {self.CAUTION}"),
                         _warning_key(f"30 + Caution - {self.CAUTION}"))

    def test_the_dash_variant_is_not_an_identity(self):
        self.assertEqual(_warning_key(f"* Caution – {self.CAUTION}"),
                         _warning_key(f"* Caution - {self.CAUTION}"))

    def test_case_is_not_an_identity(self):
        self.assertEqual(_warning_key(f"42 * caution - {self.CAUTION}"),
                         _warning_key(f"42 * Caution - {self.CAUTION}"))

    def test_an_alphanumeric_step_marker_is_not_an_identity(self):
        self.assertEqual(_warning_key(f"4A. * Caution - {self.CAUTION}"),
                         _warning_key(f"8 * Caution - {self.CAUTION}"))

    def test_a_rewrapped_line_is_not_an_identity(self):
        self.assertEqual(
            _warning_key("NOTE: It is advisable to practice\nrouting on a scrap "
                         "piece\nbefore attempting actual cut."),
            _warning_key("Note: It is advisable to practice\nrouting on a scrap "
                         "piece before\nattempting actual cut."))

    def test_a_space_before_the_colon_is_not_an_identity(self):
        """French typography: `NOTE :` and `NOTE:` are one warning."""
        self.assertEqual(_warning_key("NOTE :\nUtiliser les blocs de 2 po."),
                         _warning_key("NOTE:\nUtiliser les blocs de 2 po."))


class TestItDoesNotMergeWhatDiffers(unittest.TestCase):
    """The dangerous direction. Normalising too hard fuses two distinct
    manufacturer warnings into one and silently loses a safety statement,
    which is worse than the fragmentation being fixed."""

    def test_two_different_warnings_stay_apart(self):
        self.assertNotEqual(_warning_key("CAUTION: wear eye protection"),
                            _warning_key("CAUTION: wear gloves"))

    def test_a_warning_and_a_caution_saying_the_same_thing_stay_apart(self):
        """`[measured]`: 8 pairs share a body but differ in lexeme. They are a
        separate extraction defect — the body element is consumed as a
        heading's body and then re-published bare — and a body-only key cannot
        tell that from a real WARNING and a real CAUTION that coincide. The
        lexeme stays in the identity."""
        self.assertNotEqual(
            _warning_key("WARNING:\n• Improper installation can result in injury."),
            _warning_key("• Improper installation can result in injury."))

    def test_a_number_inside_the_sentence_is_not_stripped(self):
        self.assertNotEqual(_warning_key("NOTE: torque to 30 in-lb"),
                            _warning_key("NOTE: torque to 36 in-lb"))

    def test_an_ocr_split_word_is_not_silently_merged(self):
        """`C\\norner` vs `Corner` is a real defect, but the naive pattern that
        would merge them false-positives at 33% on this corpus — `a\\nvinyl`
        and `y\\nensamblar` are legitimate one-letter words at a line break.
        Left unmerged deliberately; 3 pairs, wanting a targeted repair."""
        self.assertNotEqual(
            _warning_key("NOTE: Corner posts should be reinforced."),
            _warning_key("Note: C\norner posts should be reinforced."))


class TestUndecodableTextIsNotPublished(unittest.TestCase):
    """`[measured]` X = 0.015 rejects 176 of 49,984 elements and 3 of 289
    warnings, with zero legitimate rejections among the warnings."""

    def test_the_cited_defect_is_caught(self):
        text = "Note: See next page on\n_o\x89|orovbࢼomv1u;\x89vom\nthe post side of the hinge."
        self.assertGreater(_undecodable_ratio(text), 0.015)

    def test_accented_text_is_legitimate(self):
        for text in ("ADVERTENCIA: La instalación incorrecta puede resultar en lesiones",
                     "AVERTISSEMENT : Vérifier le code du bâtiment avant l'installation",
                     "A continuación, deslice el panel"):
            self.assertLessEqual(_undecodable_ratio(text), 0.015, text)

    def test_typographic_marks_are_legitimate(self):
        for text in ("• Dig holes 30\" deep — or to frost line",
                     "Cut to 95½\" and 1¼\" for the rail",
                     "Illusions Fence ©2020 All Rights Reserved",
                     "Set posts at 36° from the fence line"):
            self.assertLessEqual(_undecodable_ratio(text), 0.015, text)

    def test_a_ligature_is_legitimate(self):
        """InDesign-typeset PDFs emit `ﬁ`; `Chesterﬁeld` must not be rejected."""
        self.assertLessEqual(_undecodable_ratio("Chesterﬁeld beneﬁts"), 0.015)

    def test_empty_text_is_not_a_ratio_error(self):
        self.assertEqual(_undecodable_ratio(""), 0.0)


class TestTheForwardJoinDoesNotCorruptWhatItJoins(unittest.TestCase):
    """Both of these were found by measuring the built snapshot, not by a
    failing test, which is why they are written down here now.

    The join returned the whole rebuilt string and the caller spliced it back
    on top of text that already contained the body, publishing
    `'Note: The Note: The donut can be The Note: The donut can be level should
    sit...'`. It now returns only what it APPENDED.
    """

    def test_the_join_returns_only_what_it_added(self):
        from fence_evidence.snapshot import _join_forward
        rows = [{"document_id": "d", "page_no": 1,
                 "text": "Note: The latch is designed for", "ocr_text": None},
                {"document_id": "d", "page_no": 1,
                 "text": "left and right hand applications.", "ocr_text": None}]
        added, anchor = _join_forward(rows, 0, "Note: The latch is designed for")
        self.assertEqual(added, "left and right hand applications.")
        self.assertNotIn("designed for", added, "the join re-emitted the body")

    def test_it_stops_at_a_page_boundary(self):
        from fence_evidence.snapshot import _join_forward
        rows = [{"document_id": "d", "page_no": 1, "text": "Note: ends with the",
                 "ocr_text": None},
                {"document_id": "d", "page_no": 2, "text": "next page's text",
                 "ocr_text": None}]
        added, _ = _join_forward(rows, 0, "Note: ends with the")
        self.assertIsNone(added)


class TestInterleavedColumnsAreGappedNotJoined(unittest.TestCase):
    """A second severity lexeme inside a body means OCR read two columns onto
    one line — `'Note: Do not over-tighten the Note: Line up and drive the'` is
    two different notes fused word by word. Joining forward makes such a body
    longer without making it true, so it must gap.

    Measured on the built snapshot: without this, four of the five genuinely
    garbled bodies stopped being gapped and published as joined nonsense — the
    forward-join fix silently trading a false gap for a false warning."""

    def test_a_fused_pair_of_notes_is_detected(self):
        from fence_evidence.snapshot import _INTERLEAVED
        self.assertTrue(_INTERLEAVED.search(
            "Do not over-tighten the Note: Line up and drive the"))
        self.assertTrue(_INTERLEAVED.search("The Note: The donut can be"))

    def test_an_ordinary_warning_is_not_detected(self):
        from fence_evidence.snapshot import _INTERLEAVED
        for text in ("Improper installation of this product can result in injury.",
                     "Always wear safety goggles when cutting and drilling.",
                     "Pickets will attach to rail on the side with the small holes"):
            self.assertIsNone(_INTERLEAVED.search(text), text)


if __name__ == "__main__":
    unittest.main()
