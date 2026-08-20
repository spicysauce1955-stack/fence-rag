"""Unit tests for parsing, layout inference and id stability."""
import unittest

from context import ROOT
from fence_evidence.hocr import mean_confidence, parse_hocr
from fence_evidence.ids import doc_id_for, element_id_for, page_id_for, version_id_for
from fence_evidence.layout import (HeadingClassifier, HeadingStack, build_elements,
                                   parse_bbox_layout, union)
from fence_evidence.manifest import _version_status
from fence_evidence.model import Word
from fence_evidence.extract import _docx_level_from_style, _rotate_word
from fence_evidence.tables import looks_tabular
from fence_evidence.retrieval import build_match_expression

BBOX_XML = """<!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml"><body><doc>
<page width="612.0" height="792.0"><flow><block xMin="10" yMin="10" xMax="200" yMax="30">
<line xMin="10" yMin="10" xMax="200" yMax="30">
<word xMin="10" yMin="10" xMax="60" yMax="30">FOOTING</word>
<word xMin="65" yMin="10" xMax="200" yMax="30">DEPTH</word>
</line></block></flow></page></doc></body></html>"""

HOCR = """<!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml"><body>
<div class='ocr_page'><span class='ocr_line' title="bbox 0 0 100 20">
<span class='ocrx_word' title='bbox 10 10 60 20; x_wconf 95'>36</span>
<span class='ocrx_word' title='bbox 65 10 120 20; x_wconf 85'>in.</span>
</span></div></body></html>"""


class TestBBoxParsing(unittest.TestCase):
    def test_parse(self):
        pages = parse_bbox_layout(BBOX_XML)
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0]["width"], 612.0)
        words = pages[0]["blocks"][0][0]
        self.assertEqual([w.text for w in words], ["FOOTING", "DEPTH"])
        self.assertEqual(words[0].bbox, (10.0, 10.0, 60.0, 30.0))

    def test_union(self):
        self.assertEqual(union([(1, 2, 3, 4), (0, 5, 9, 6)]), (0, 2, 9, 6))


class TestHocr(unittest.TestCase):
    def test_parse_and_confidence(self):
        words, lines = parse_hocr(HOCR, scale=1.0)
        self.assertEqual([w.text for w in words], ["36", "in."])
        self.assertEqual(len(lines), 1)
        self.assertEqual(mean_confidence(words), 90.0)

    def test_scale_divides_pixel_coordinates(self):
        words, _ = parse_hocr(HOCR, scale=2.0)
        self.assertEqual(words[0].bbox, (5.0, 5.0, 30.0, 10.0))


class TestHeadings(unittest.TestCase):
    def _line(self, text, h=10.0, y=0.0):
        return [Word(text=t, bbox=(i * 20.0, y, i * 20.0 + 18.0, y + h))
                for i, t in enumerate(text.split())]

    def test_larger_text_becomes_heading(self):
        body = [self._line("this is ordinary body text of the document") for _ in range(20)]
        head = self._line("FOOTING REQUIREMENTS", h=20.0)
        cls = HeadingClassifier(body + [head])
        self.assertIsNotNone(cls.level(head))
        self.assertIsNone(cls.level(body[0]))

    def test_sentence_is_not_a_heading(self):
        body = [self._line("ordinary body text here for size baseline") for _ in range(20)]
        sentence = self._line("This sentence happens to be set larger.", h=20.0)
        cls = HeadingClassifier(body + [sentence])
        self.assertIsNone(cls.level(sentence))

    def test_stack_truncates_on_shallower_heading(self):
        st = HeadingStack()
        st.push(1, "PART 1"); st.push(2, "Materials"); st.push(3, "Posts")
        self.assertEqual(st.path, ["PART 1", "Materials", "Posts"])
        st.push(2, "Execution")
        self.assertEqual(st.path, ["PART 1", "Execution"])

    def test_elements_carry_heading_path_and_bbox(self):
        body = [self._line("ordinary body text here for size baseline", y=i * 12.0)
                for i in range(20)]
        head = self._line("INSTALLATION", h=20.0, y=300.0)
        cls = HeadingClassifier(body + [head])
        st = HeadingStack()
        els = build_elements([[head], [body[0]]], cls, st,
                             text_source="pdf_text_layer", page_width=612.0)
        self.assertEqual(els[0].element_type, "heading")
        self.assertEqual(els[1].heading_path, ["INSTALLATION"])
        self.assertEqual(len(els[1].bbox), 4)

    def test_ocr_text_never_lands_in_text_column(self):
        body = [self._line("ordinary body text here for size baseline") for _ in range(20)]
        cls = HeadingClassifier(body)
        els = build_elements([[body[0]]], cls, HeadingStack(),
                             text_source="ocr", page_width=612.0)
        self.assertEqual(els[0].text, "")
        self.assertTrue(els[0].ocr_text)
        self.assertEqual(els[0].text_source, "ocr")


class TestRotation(unittest.TestCase):
    def test_90_degrees(self):
        w = Word(text="x", bbox=(0.0, 0.0, 10.0, 20.0))
        _rotate_word(w, 90, 612.0, 792.0)
        self.assertEqual(w.bbox, (772.0, 0.0, 792.0, 10.0))

    def test_180_degrees_keeps_size(self):
        w = Word(text="x", bbox=(10.0, 20.0, 30.0, 50.0))
        _rotate_word(w, 180, 612.0, 792.0)
        self.assertAlmostEqual(w.bbox[2] - w.bbox[0], 20.0)
        self.assertAlmostEqual(w.bbox[3] - w.bbox[1], 30.0)

    def test_zero_is_identity(self):
        w = Word(text="x", bbox=(1.0, 2.0, 3.0, 4.0))
        _rotate_word(w, 0, 612.0, 792.0)
        self.assertEqual(w.bbox, (1.0, 2.0, 3.0, 4.0))


class TestTableValidator(unittest.TestCase):
    def test_accepts_real_grid(self):
        grid = [["Height", "Exposure B", "Exposure C"],
                ["6 ft", "30 in", "36 in"],
                ["8 ft", "36 in", "42 in"]]
        ok, _ = looks_tabular(grid)
        self.assertTrue(ok)

    def test_rejects_prose_sliced_into_columns(self):
        grid = [["For a", "site lo", "cation with"],
                ["a high wind", "condition an", "d the de"],
                ["sign selection", "of an", "appropriate"]]
        ok, why = looks_tabular(grid)
        self.assertFalse(ok)
        self.assertIn("mid-word", why)

    def test_rejects_single_column(self):
        self.assertFalse(looks_tabular([["a"], ["b"], ["c"]])[0])


class TestDocxStyles(unittest.TestCase):
    def test_arcat_styles(self):
        self.assertEqual(_docx_level_from_style("ARCATTitle"), 1)
        self.assertEqual(_docx_level_from_style("ARCATPart"), 1)
        self.assertEqual(_docx_level_from_style("ARCATArticle"), 2)
        self.assertIsNone(_docx_level_from_style("ARCATParagraph"))
        self.assertIsNone(_docx_level_from_style("ARCATSubPara"))

    def test_word_builtin_styles(self):
        self.assertEqual(_docx_level_from_style("Heading2"), 2)
        self.assertEqual(_docx_level_from_style("heading 3"), 3)


class TestIds(unittest.TestCase):
    def test_document_id_is_path_stable(self):
        a = doc_id_for("manuals/x/y.pdf")
        self.assertEqual(a, doc_id_for("manuals/x/y.pdf"))
        self.assertNotEqual(a, doc_id_for("manuals/x/z.pdf"))

    def test_version_id_carries_content_hash(self):
        vid = version_id_for("doc-abc", "f" * 64)
        self.assertTrue(vid.startswith("doc-abc@"))
        self.assertNotEqual(vid, version_id_for("doc-abc", "e" * 64))

    def test_element_ids_unique_per_ordinal(self):
        pid = page_id_for("doc-abc@ffffffffffff", 3)
        self.assertNotEqual(element_id_for(pid, 1), element_id_for(pid, 2))


class TestVersionStatus(unittest.TestCase):
    def test_superseded_keyword(self):
        status, _ = _version_status("manuals/x/NOA-21-0125.07-superseded.pdf", {})
        self.assertEqual(status, "superseded")

    def test_current_keyword(self):
        status, _ = _version_status("manuals/x/NOA-23-0314.05-current-2023-2029.pdf", {})
        self.assertEqual(status, "active")

    def test_default_unknown(self):
        status, _ = _version_status("manuals/x/install-guide.pdf", {})
        self.assertEqual(status, "unknown")


class TestQueryBuilder(unittest.TestCase):
    def test_identifier_becomes_phrase(self):
        expr, _ = build_match_expression("Find NOA 23-0314.05")
        self.assertIn('"23 0314 05"', expr)

    def test_measurement_becomes_phrase(self):
        expr, _ = build_match_expression("footing depth at 130 mph")
        self.assertIn('"130 mph"', expr)

    def test_stopwords_dropped_and_or_joined(self):
        expr, _ = build_match_expression("what is the footing depth")
        self.assertIn(" OR ", expr)
        self.assertNotIn('"the"', expr)

    def test_empty_query(self):
        self.assertEqual(build_match_expression("the a of")[0], "")


if __name__ == "__main__":
    unittest.main()
