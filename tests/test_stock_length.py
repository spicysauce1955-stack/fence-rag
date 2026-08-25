"""A5 — `stock_length`, obligation 14.

  > A part publishes its manufactured `stock_length` where a document states one.
  > Whether a member runs continuously through an intermediate post is **derived**
  > from stock length against the resolved spacing, not authored: the same rail is
  > continuous in one colour and per-bay in another (16 ft White against 12 ft
  > Blend, at a 97" maximum spacing).

So the value is **conditional, not scalar**, and the condition is colour. A single
number here would licence a continuous rail in a colour that is not supplied long
enough to be one.

Two things the corpus taught that the build plan's example did not:

* The phrases "stock length" and "standard length" have **zero** hits. The real
  wording is *"Standard rails are supplied in 16 foot lengths"*.
* A catalogue is full of `8' Rail Insert Kit` and `1.5in. x 5.5in. x 8ft. Rail`
  SKU lines. Those are product names in a price list, not a statement about what
  length rails are supplied in, and treating them as one would put a manufactured
  length on every accessory in the book.
"""
import unittest

import context  # noqa: F401  -- puts the repo root on sys.path
from context import requires_store
from fence_evidence.facts import stock_lengths


class TestTheUnconditionalCase(unittest.TestCase):
    def test_the_plain_statement(self):
        got = stock_lengths("Standard rails are supplied in 16 foot lengths")
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["value_normalized"], 192.0)      # 16 ft in inches
        self.assertEqual(got[0]["unit_normalized"], "in")
        self.assertEqual(got[0]["conditions"], {})

    def test_the_verbatim_lexeme_is_kept(self):
        """Obligation 4: every verbatim source lexeme alongside the number."""
        got = stock_lengths("Standard rails are supplied in 16 foot lengths")
        self.assertIn("16 foot", got[0]["value_original"])


class TestTheConditionalCase(unittest.TestCase):
    """The case obligation 14 names explicitly."""

    def test_two_colours_two_values(self):
        got = stock_lengths(
            "Standard rails are supplied in 16 foot lengths for White "
            "(12 foot rails for Blend products)")
        by = {f["conditions"].get("colour"): f["value_normalized"] for f in got}
        self.assertEqual(by, {"White": 192.0, "Blend": 144.0})

    def test_the_condition_basis_is_stated_not_assumed(self):
        """The document says 'for White' in the same sentence. That is the source
        stating the condition, which is the one case that earns `stated`."""
        got = stock_lengths("Standard rails are supplied in 16 foot lengths for "
                            "White (12 foot rails for Blend products)")
        for f in got:
            self.assertEqual(f["condition_basis"], "stated")

    def test_a_bare_statement_is_not_claimed_as_stated(self):
        got = stock_lengths("Standard rails are supplied in 16 foot lengths")
        self.assertNotEqual(got[0]["condition_basis"], "stated")


class TestGuards(unittest.TestCase):
    """Each of these was a measured false positive in the corpus."""

    def test_a_sku_line_for_an_accessory_kit_is_not_a_stock_length(self):
        self.assertEqual(stock_lengths("8' Rail Insert Kit (2pk.) For use with "
                                       "5 1/2 in. rails or larger"), [])
        self.assertEqual(stock_lengths("U | 6' Rail Insert Kit | 73024839"), [])

    def test_a_height_is_not_a_length(self):
        self.assertEqual(stock_lengths("available in 57 inch (1448 mm) height"), [])

    def test_a_fill_kit_section_count_is_not_a_stock_length(self):
        self.assertEqual(stock_lengths("PRIVACY FENCE FILL KITS 8' SECTIONS"), [])

    def test_a_cut_length_is_not_a_supplied_length(self):
        """`cut to 95 1/2"` is what an installer does to a rail, not how it ships."""
        self.assertEqual(stock_lengths("For rolling terrain, rails may need to be "
                                       "cut to 95 1/2\""), [])

    def test_empty_and_none(self):
        self.assertEqual(stock_lengths(""), [])
        self.assertEqual(stock_lengths(None), [])


class TestTheSkuSeam(unittest.TestCase):
    """`1-1/2" x 5-1/2" x 16\' Rail` — 735 instances, the seam where the data is.

    A survey measured the naive `N ft <part>` pattern at 18.6% precision: 127 of
    156 matches wrong, dominated by `8' Picket` (89 times), which is a *section
    width* followed by the field name "Picket Style". The guards below are each
    a measured false-positive class, not a precaution.
    """

    def test_a_dimension_triple_yields_its_third_dimension(self):
        got = stock_lengths('1-1/2" x 5-1/2" x 16\' Rail (STANDARD)')
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["value_normalized"], 192.0)
        self.assertEqual(got[0]["conditions"].get("part"), "rail")

    def test_inches_in_a_triple(self):
        got = stock_lengths('5in. x 5in. x 108in. Line Post')
        self.assertEqual(got[0]["value_normalized"], 108.0)
        self.assertEqual(got[0]["conditions"].get("part"), "post")

    def test_a_colour_suffix_is_carried_as_a_condition(self):
        """Freedom lists 5x5 posts at different lengths per colour, and the ONLY
        thing expressing that is which SKU rows exist."""
        got = stock_lengths('1.5in. x 5.5in. x 8ft. Rail - White')
        self.assertEqual(got[0]["conditions"].get("colour"), "White")

    def test_a_spacer_block_is_not_a_part(self):
        self.assertEqual(stock_lengths('2in. x 2in. x 6in. Inch Wood "Spacer" Block'), [])

    def test_a_post_spacing_nearby_disqualifies_it(self):
        self.assertEqual(stock_lengths("installing Blend products on 6' post centers"), [])

    def test_a_height_label_disqualifies_it(self):
        self.assertEqual(stock_lengths("Available in 4', 5', and 6' heights"), [])

    def test_the_field_label_collision(self):
        """The worst measured false positive: 89 hits of `8' Picket`, where the
        value belongs to `Gate Width` and the noun belongs to `Picket Style`."""
        self.assertEqual(
            stock_lengths("Gate Width: Single 4', 5' Double 8' & 10' Picket Style: Flat top"),
            [])

    def test_an_implausible_length_is_a_parse_not_a_length(self):
        self.assertEqual(stock_lengths('5"X5"X9" HEAVY WALL POST'), [])   # OCR: 9' as 9"
        self.assertEqual(stock_lengths("NOT TO EXCEED 964' RAIL RETAINER"), [])

    def test_ocr_and_drawings_are_refused(self):
        """176 false positives came from scanned NOA drawings whose OCR looks
        exactly like a SKU triple but states the tested specimen's members."""
        self.assertEqual(
            stock_lengths('2"X6"X92.5" AS MIDDLE AND BOTTOM RAILS',
                          element_type="drawing", text_source="ocr"), [])


@requires_store
class TestAgainstTheStore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fence_evidence.store import connect
        cls.conn = connect()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_the_extractor_found_the_conditional_case(self):
        rows = self.conn.execute("""
            SELECT conditions, value_normalized FROM facts
             WHERE fact_type='stock_length_in'""").fetchall()
        if not rows:
            self.skipTest("facts not re-extracted since A5 landed")
        import json
        colours = {json.loads(r["conditions"]).get("colour") for r in rows}
        self.assertIn("Blend", colours,
                      "the 12 ft Blend rail is the case obligation 14 names")

    def test_every_stock_length_is_plausible(self):
        """A manufactured rail is between 4 and 24 feet. Anything outside that is
        a parse, not a length."""
        rows = self.conn.execute("""
            SELECT value_normalized v FROM facts
             WHERE fact_type='stock_length_in' AND value_normalized IS NOT NULL""")
        for r in rows:
            self.assertTrue(48 <= r["v"] <= 288,
                            f"{r['v']} inches is not a manufactured rail length")


if __name__ == "__main__":
    unittest.main()
