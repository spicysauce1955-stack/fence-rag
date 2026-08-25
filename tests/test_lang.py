"""Language tagging — obligation 10, and the assumption it refuses to hide.

`lang` is required and never normalised. The trap this guards is the cheap
implementation: read the language off `corpus_track`. That axis is a standards
regime -- GB rather than ASTM -- not a language, and every China-track element
in this corpus measured as English. See docs/state-and-gaps.md G32.
"""
import unittest

import context  # noqa: F401  -- puts the repo root on sys.path
from fence_evidence.lang import detect_lang


class TestScriptDetection(unittest.TestCase):
    def test_latin_text_is_english_by_assumption_not_measurement(self):
        lang, basis = detect_lang("Standard rails are supplied in 16 foot lengths")
        self.assertEqual(lang, "en")
        self.assertEqual(basis, "assumed",
                         "telling English from another Latin language is not "
                         "something this code can do; it must not claim to")

    def test_cjk_text_is_chinese_by_assumption(self):
        lang, basis = detect_lang("围栏安装说明")
        self.assertEqual(lang, "zh")
        self.assertEqual(basis, "assumed")

    def test_mixed_script_prefers_the_cjk_signal(self):
        """A Chinese page with an English product code is still Chinese."""
        lang, basis = detect_lang("PVC 围栏 model DS-100")
        self.assertEqual(lang, "zh")

    def test_text_with_no_letters_is_undetermined(self):
        for junk in ("", "   ", "30\" 1-1/2 96.125", "-—— e. —— : 4", "|||"):
            lang, basis = detect_lang(junk)
            self.assertEqual(lang, "und", f"guessed a language for {junk!r}")
            self.assertEqual(basis, "unknown")

    def test_none_is_undetermined(self):
        self.assertEqual(detect_lang(None), ("und", "unknown"))

    def test_never_returns_measured(self):
        """`measured` is reserved for a real language identifier. Nothing here is one.

        This test exists to fail loudly if someone wires up a detector and
        forgets that obligation 10 is about the honesty of the claim, not the
        presence of a value.
        """
        for sample in ("hello world", "围栏", "", "123"):
            self.assertNotEqual(detect_lang(sample)[1], "measured")

    def test_the_showtech_catalogue_reads_as_english(self):
        """The real text that falsified the corpus_track shortcut."""
        self.assertEqual(detect_lang("PREFACE 05 OUR ADVANTAGES")[0], "en")
        self.assertEqual(detect_lang("PROFILE QUANTITY LENGTH")[0], "en")


if __name__ == "__main__":
    unittest.main()
