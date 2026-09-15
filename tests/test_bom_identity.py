"""One piece gets one id, and a piece we cannot type gets none at all.

The drawings spell the same part several ways -- `.875` and `7/8`, `U-SHAPED`
and `U-SHAPPED` (the reviewer confirmed the misspelling is in the drawing and
corrected *toward* it). A fork would publish one piece twice; a silent repair
would lose evidence about the source.

And a type phrase this platform has no spine mapping for publishes nothing.
Guessing that `SNAP CAP` is a `post_cap` is the G62 shape -- an invented
attribution that shipped before and had to be reversed.
"""
import unittest

from context import ROOT  # noqa: F401
from fence_evidence.bom_parse import parse_description
from fence_evidence.bom_parts import bom_part_id, spine_type


class TestOnePieceOneId(unittest.TestCase):
    def _id(self, description, manufacturer="CertainTeed"):
        return bom_part_id(parse_description(description), manufacturer)

    def test_the_same_dimension_written_two_ways_mints_one_id(self):
        """`.875` and `7/8` are one thickness; exact Fractions make them equal."""
        self.assertEqual(self._id(".875 X 3 X 71.5 PICKET"),
                         self._id("7/8 X 3 X 71.5 PICKET"))

    def test_a_misspelling_in_the_drawing_does_not_fork_the_part(self):
        """The reviewer corrected toward `U-SHAPPED`; it is the drawing's own."""
        self.assertEqual(self._id("U-SHAPED G-60 STEEL CHANNEL X 92"),
                         self._id("U-SHAPPED G-60 STEEL CHANNEL X 92"))

    def test_two_manufacturers_never_share_an_id(self):
        """Identical strings in two companies' filings are not one part.

        No document says Barrette's picket and CertainTeed's are the same
        piece, so the namespace keeps them apart.
        """
        self.assertNotEqual(self._id(".875 X 3 X 71.5 PICKET", "CertainTeed"),
                            self._id(".875 X 3 X 71.5 PICKET", "Barrette Outdoor Living, Inc."))

    def test_the_family_an_id_falls_into_is_the_manufacturer(self):
        """`reach._part_family` takes `rsplit("/", 1)[0]`.

        Asserting the family directly, not a slash count -- the first cut of
        this test counted slashes and failed a correct id. What matters is that
        the part lands in an identity family something already declares an
        association with; a new family reaching nobody is G106 from the other
        end.
        """
        from fence_evidence.part_types import mfr_namespace
        part_id = self._id(".875 X 3 X 71.5 PICKET")
        self.assertEqual(part_id.rsplit("/", 1)[0], mfr_namespace("CertainTeed"))


class TestAnUntypedPhrasePublishesNothing(unittest.TestCase):
    def test_a_known_phrase_maps_to_its_spine_type(self):
        self.assertEqual(spine_type("ROUTED POST"), "post")
        self.assertEqual(spine_type("RIBBED PICKET"), "picket")
        self.assertEqual(spine_type("SET SCREWS"), "fastener")

    def test_an_unknown_phrase_returns_none_rather_than_a_guess(self):
        """`SNAP CAP` is a screw cover. Mapped to `post_cap` it would assert a
        role no document states -- the G62 invention, which shipped once and
        had to be reversed."""
        self.assertIsNone(spine_type("SNAP CAP"))
        self.assertIsNone(spine_type("BULLET CLIP"))


if __name__ == "__main__":
    unittest.main()
