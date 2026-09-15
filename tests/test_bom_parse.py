"""A BOM part description says what the piece is; the parse must not invent more.

`[measured]` 2026-09-14: 177 reviewed parts-list rows across 5 Miami-Dade NOAs,
every one signed off by a person. The `PART DESCRIPTION` column encodes a type
and, usually, dimensions in one string. 174 of 177 parse; the 3 that do not are
refused, never guessed.

The ordering of the patterns is load-bearing, which is what this module pins.
"""
import unittest
from fractions import Fraction

from context import ROOT  # noqa: F401
from fence_evidence.bom_parse import parse_description


class TestAGaugeIsNeverALength(unittest.TestCase):
    def test_a_screw_gauge_does_not_become_inches(self):
        """`#8` is a wire gauge. Read as inches it publishes a 3/4" screw as 8".

        This is the G63 shape -- a unit misread that ships a number an order of
        magnitude wrong -- and it is why the gauge pattern must be tried before
        the two-dimension one, which would otherwise match `#8 X 1 1/2"`.
        """
        p = parse_description('#8 X 1 1/2" SET SCREWS')
        self.assertEqual(p["gauge"], "#8")
        self.assertEqual(p["length_in"], Fraction(3, 2))
        self.assertEqual(p["type_phrase"], "SET SCREWS")
        self.assertIsNone(p["section"], "a gauge is not a cross-section")


class TestTheStatedDimensionsAndNoOthers(unittest.TestCase):
    def test_three_dimensions_keep_the_section_unsplit(self):
        """`2 X 4` must not become width and height.

        Naming them asserts which way up the rail runs, and
        knowledge-datamodel.md says a Part "never says ... which way up it
        runs". The pair publishes as a token; only the trailing length is a
        quantity.
        """
        p = parse_description(".875 X 3 X 71.5 PICKET")
        self.assertEqual(p["section"], ".875 X 3")
        self.assertEqual(p["length_in"], Fraction(143, 2))
        self.assertEqual(p["type_phrase"], "PICKET")

    def test_a_trailing_length_after_the_type_is_still_the_length(self):
        """The drawing sometimes puts the length last and the type first."""
        p = parse_description("HOURGLASS G-60 STEEL CHANNEL X 92")
        self.assertEqual(p["type_phrase"], "HOURGLASS G-60 STEEL CHANNEL")
        self.assertEqual(p["length_in"], 92)
        self.assertIsNone(p["section"])

    def test_a_bare_size_is_not_a_length(self):
        """`.5 INCH BULLET CLIP` states a size whose role the string never gives."""
        p = parse_description(".5 INCH BULLET CLIP")
        self.assertEqual(p["type_phrase"], "BULLET CLIP")
        self.assertEqual(p["size_in"], Fraction(1, 2))
        self.assertIsNone(p["length_in"])

    def test_a_description_with_no_dimension_parses_as_a_type(self):
        p = parse_description("SNAP CAP WASHER")
        self.assertEqual(p["type_phrase"], "SNAP CAP WASHER")
        self.assertIsNone(p["length_in"])


class TestWhatCannotBeParsedIsRefused(unittest.TestCase):
    def test_a_relational_length_is_refused_not_guessed(self):
        """`POST REINF. FULL LENGTH -1"` is a rule about another part.

        It states no magnitude of its own. Publishing 1 inch, or the post's
        length, would both be inventions; the builder raises a gap instead.
        """
        self.assertIsNone(parse_description('POST REINF. FULL LENGTH -1"'))

    def test_an_empty_description_is_refused(self):
        self.assertIsNone(parse_description("   "))


if __name__ == "__main__":
    unittest.main()
