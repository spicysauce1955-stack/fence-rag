"""The normative crop transform — source-refs-design.md §4.1.

The geometry is tested without poppler because that is where every trap lives:
the dpi that must not be hardcoded, the origin that must not be flipped, the
clamp, and the pad. The render itself is exercised against the real corpus.
"""
import unittest

from context import requires_store
from fence_evidence.crops import CropError, window_px


class TestWindowGeometry(unittest.TestCase):
    """§4.1: scale = dpi/72, top-left origin, PAD_PX = 4, clamped to the page."""

    def test_scales_by_dpi_over_72(self):
        # a 1-inch square at the page origin, rendered at 200 dpi, is 200 px
        w = window_px((0, 0, 72, 72), page_w_pt=612, page_h_pt=792, dpi=200)
        self.assertEqual((w.x0, w.y0), (0, 0))
        # 72pt * 200/72 = 200, plus 4px of pad on the far side
        self.assertEqual(w.w, 204)
        self.assertEqual(w.h, 204)

    def test_dpi_is_never_assumed(self):
        """The six CAD PNGs are 72 dpi and their bbox units are already pixels."""
        at72 = window_px((10, 10, 110, 110), page_w_pt=800, page_h_pt=600, dpi=72)
        at200 = window_px((10, 10, 110, 110), page_w_pt=800, page_h_pt=600, dpi=200)
        self.assertEqual(at72.w, 108)   # 100px of content + 4px of pad each side
        self.assertNotEqual(at72.w, at200.w)

    def test_origin_is_top_left_with_no_flip(self):
        """A box near the top of the page must crop near the top of the image.

        Applying the usual PDF bottom-left flip mirrors every crop vertically.
        CLAUDE.md records that bug being found and removed once.
        """
        near_top = window_px((0, 10, 100, 30), page_w_pt=612, page_h_pt=792, dpi=200)
        self.assertLess(near_top.y0, 100)

    def test_pads_by_four_pixels(self):
        w = window_px((100, 100, 200, 200), page_w_pt=612, page_h_pt=792, dpi=72)
        self.assertEqual(w.x0, 96)
        self.assertEqual(w.y0, 96)

    def test_pad_never_goes_negative(self):
        w = window_px((0, 0, 50, 50), page_w_pt=612, page_h_pt=792, dpi=72)
        self.assertEqual((w.x0, w.y0), (0, 0))

    def test_clamps_to_the_page_rectangle(self):
        """A bbox running to the page edge must not ask poppler for pixels past it."""
        w = window_px((0, 0, 612, 792), page_w_pt=612, page_h_pt=792, dpi=200)
        self.assertLessEqual(w.x0 + w.w, int(612 * 200 / 72))
        self.assertLessEqual(w.y0 + w.h, int(792 * 200 / 72))

    def test_a_degenerate_box_raises_rather_than_returning_false(self):
        """§4.1 trap 3: crop failure raises. It does not return False and carry on."""
        with self.assertRaises(CropError):
            window_px((100, 100, 100, 100), page_w_pt=612, page_h_pt=792, dpi=200)

    def test_a_missing_dpi_raises_rather_than_guessing(self):
        """The DOCX has no page image and no dpi. It is flagged, never guessed."""
        with self.assertRaises(CropError):
            window_px((0, 0, 100, 100), page_w_pt=612, page_h_pt=792, dpi=None)


@requires_store
class TestRenderAgainstTheCorpus(unittest.TestCase):
    def test_renders_a_real_element_to_a_png(self):
        from fence_evidence.crops import render_crop
        from fence_evidence.store import connect
        conn = connect()
        try:
            row = conn.execute("""SELECT e.bbox, e.page_no, p.width, p.height,
                       p.page_image_dpi, d.source_path
                  FROM elements e
                  JOIN pages p ON p.page_id = e.page_id
                  JOIN documents d ON d.document_id = e.document_id
                 WHERE e.bbox IS NOT NULL AND p.page_image_dpi IS NOT NULL
                   AND d.source_path LIKE '%.pdf'
                 LIMIT 1""").fetchone()
        finally:
            conn.close()
        if row is None:
            self.skipTest("no boxed element with a dpi in the store")
        import json
        out = render_crop(row["source_path"], row["page_no"], json.loads(row["bbox"]),
                          page_w_pt=row["width"], page_h_pt=row["height"],
                          dpi=row["page_image_dpi"])
        self.assertTrue(out.is_file(), "render_crop returned a path that is not a file")
        self.assertGreater(out.stat().st_size, 0)
        with open(out, "rb") as fh:
            self.assertEqual(fh.read(8), b"\x89PNG\r\n\x1a\n", "not a PNG")

    def test_a_missing_source_raises(self):
        from fence_evidence.crops import render_crop
        with self.assertRaises(CropError):
            render_crop("manuals/nope/does-not-exist.pdf", 1, (0, 0, 100, 100),
                        page_w_pt=612, page_h_pt=792, dpi=200)


if __name__ == "__main__":
    unittest.main()
