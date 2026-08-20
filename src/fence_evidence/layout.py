"""Layout analysis: words -> lines -> blocks -> canonical elements.

Input is word-level geometry from either ``pdftotext -bbox-layout`` (source
text layer) or hOCR (OCR).  Output is a list of :class:`Element` with bounding
boxes, inferred heading levels and a running heading path.
"""
from __future__ import annotations

import re
import statistics
import xml.etree.ElementTree as ET

from .model import BBox, Element, Word

_NS = {"x": "http://www.w3.org/1999/xhtml"}
_BULLET_RE = re.compile(r"^\s*(?:[•▪◦\-•●\*]|\(?\d{1,2}[.)]|[a-zA-Z][.)])\s+")
_CAPTION_RE = re.compile(
    r"^\s*(fig(?:ure)?|detail|drawing|photo|diagram|step|table|sheet)\b[\s.:#-]*\d*", re.I)
_HEADING_STOP_RE = re.compile(r"[.;,!?]\s*$")


_INVALID_XML_CHARS = re.compile(
    r"[^\u0009\u000A\u000D\u0020-\uD7FF\uE000-\uFFFD]")


def _strip_doctype(xml: str) -> str:
    """Remove the DOCTYPE and any character XML 1.0 cannot represent.

    Mojibake text layers emit raw C0 control bytes, which make the whole
    document unparseable; dropping them lets the per-page mojibake check run
    and reject only the affected pages instead of losing the document's text.
    """
    xml = re.sub(r"<!DOCTYPE[^>]*>", "", xml, count=1)
    return _INVALID_XML_CHARS.sub("", xml)


def union(boxes: list[BBox]) -> BBox:
    xs0 = min(b[0] for b in boxes)
    ys0 = min(b[1] for b in boxes)
    xs1 = max(b[2] for b in boxes)
    ys1 = max(b[3] for b in boxes)
    return (round(xs0, 2), round(ys0, 2), round(xs1, 2), round(ys1, 2))


def parse_bbox_layout(xml: str) -> list[dict]:
    """Parse ``pdftotext -bbox-layout`` XHTML into per-page block structure."""
    root = ET.fromstring(_strip_doctype(xml))
    pages = []
    for page_el in root.findall(".//x:page", _NS):
        blocks = []
        for block_el in page_el.findall(".//x:block", _NS):
            lines = []
            for line_el in block_el.findall("x:line", _NS):
                words = []
                for w in line_el.findall("x:word", _NS):
                    txt = (w.text or "").strip()
                    if not txt:
                        continue
                    words.append(Word(text=txt, bbox=(
                        float(w.get("xMin")), float(w.get("yMin")),
                        float(w.get("xMax")), float(w.get("yMax")))))
                if words:
                    lines.append(words)
            if lines:
                blocks.append(lines)
        pages.append({
            "width": float(page_el.get("width")),
            "height": float(page_el.get("height")),
            "blocks": blocks,
        })
    return pages


def line_text(words: list[Word]) -> str:
    return " ".join(w.text for w in words)


def line_height(words: list[Word]) -> float:
    return max(w.bbox[3] for w in words) - min(w.bbox[1] for w in words)


def body_text_size(all_lines: list[list[Word]]) -> float:
    """Character-weighted modal line height.

    Weighting by characters rather than by line keeps a document's few large
    display lines from dragging the estimate up: body text is the bulk of the
    characters even when covers and titles are visually dominant.
    """
    from collections import Counter
    weighted: Counter[float] = Counter()
    for ln in all_lines:
        if not ln:
            continue
        weighted[round(line_height(ln), 1)] += sum(len(w.text) for w in ln)
    if not weighted:
        return 10.0
    return weighted.most_common(1)[0][0]


class HeadingClassifier:
    """Infers heading levels from relative text size across a whole document."""

    def __init__(self, all_lines: list[list[Word]]):
        self.body = body_text_size(all_lines)
        sizes = sorted({round(line_height(l), 1) for l in all_lines
                        if l and line_height(l) > self.body * 1.2}, reverse=True)
        # at most four heading levels; larger text -> shallower level
        self.size_levels = {s: min(i + 1, 4) for i, s in enumerate(sizes)}

    def level(self, words: list[Word]) -> int | None:
        text = line_text(words)
        if not text or len(text) > 120 or len(words) > 14:
            return None
        if _HEADING_STOP_RE.search(text) or "@" in text:
            return None
        h = round(line_height(words), 1)
        lvl = self.size_levels.get(h)
        if lvl is None:
            # all-caps short lines act as headings even at body size
            letters = [c for c in text if c.isalpha()]
            if (letters and len(letters) >= 3 and len(text) < 60
                    and all(c.isupper() for c in letters)):
                return 3
            return None
        return lvl


class HeadingStack:
    """Running section hierarchy across the pages of one document."""

    def __init__(self):
        self._stack: list[tuple[int, str]] = []

    def push(self, level: int, text: str) -> None:
        self._stack = [(l, t) for (l, t) in self._stack if l < level]
        self._stack.append((level, text))

    @property
    def path(self) -> list[str]:
        return [t for _, t in self._stack]


def looks_like_table_block(lines: list[list[Word]], page_width: float) -> bool:
    """Whitespace-column heuristic used when no table backend is available."""
    if len(lines) < 3:
        return False
    gap_signatures = []
    for words in lines:
        if len(words) < 3:
            continue
        gaps = []
        for a, b in zip(words, words[1:]):
            gap = b.bbox[0] - a.bbox[2]
            if gap > page_width * 0.03:
                gaps.append(round(b.bbox[0] / (page_width / 40)))
        if len(gaps) >= 1:
            gap_signatures.append(tuple(gaps))
    if len(gap_signatures) < 3:
        return False
    # at least three lines sharing a column start position
    from collections import Counter
    starts = Counter(g for sig in gap_signatures for g in sig)
    return any(c >= 3 for c in starts.values())


def build_elements(blocks: list[list[list[Word]]], classifier: HeadingClassifier,
                   stack: HeadingStack, *, text_source: str,
                   page_width: float, start_ordinal: int = 0,
                   table_regions: list[BBox] | None = None) -> list[Element]:
    """Turn one page's blocks into canonical elements."""
    elements: list[Element] = []
    ordinal = start_ordinal
    table_regions = table_regions or []

    def inside_table(bbox: BBox) -> bool:
        for t in table_regions:
            # element is mostly inside a detected table region
            ox = max(0.0, min(bbox[2], t[2]) - max(bbox[0], t[0]))
            oy = max(0.0, min(bbox[3], t[3]) - max(bbox[1], t[1]))
            area = max(1e-6, (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))
            if (ox * oy) / area > 0.6:
                return True
        return False

    for lines in blocks:
        block_bbox = union([union([w.bbox for w in ln]) for ln in lines])
        if inside_table(block_bbox):
            continue  # its content is preserved as table cells instead
        pending: list[list[Word]] = []

        def flush(kind: str = "paragraph"):
            nonlocal ordinal, pending
            if not pending:
                return
            bbox = union([union([w.bbox for w in ln]) for ln in pending])
            text = "\n".join(line_text(ln) for ln in pending)
            el = Element(element_type=kind, text=text if text_source != "ocr" else "",
                         ocr_text=text if text_source == "ocr" else None,
                         text_source=text_source, bbox=bbox,
                         heading_path=list(stack.path), ordinal=ordinal)
            if text_source == "ocr":
                confs = [w.confidence for ln in pending for w in ln
                         if w.confidence is not None]
                el.ocr_confidence = round(sum(confs) / len(confs), 2) if confs else None
            elements.append(el)
            ordinal += 1
            pending = []

        is_table_block = (not table_regions) and looks_like_table_block(lines, page_width)
        for words in lines:
            lvl = None if is_table_block else classifier.level(words)
            if lvl is not None:
                flush()
                text = line_text(words)
                stack.push(lvl, text)
                bbox = union([w.bbox for w in words])
                el = Element(element_type="heading",
                             text=text if text_source != "ocr" else "",
                             ocr_text=text if text_source == "ocr" else None,
                             text_source=text_source, bbox=bbox,
                             heading_level=lvl, heading_path=list(stack.path),
                             ordinal=ordinal)
                if text_source == "ocr":
                    confs = [w.confidence for w in words if w.confidence is not None]
                    el.ocr_confidence = round(sum(confs) / len(confs), 2) if confs else None
                elements.append(el)
                ordinal += 1
            else:
                pending.append(words)
        if is_table_block:
            flush("table_text")
        else:
            first = line_text(lines[0]) if lines else ""
            if _BULLET_RE.match(first):
                flush("list")
            elif _CAPTION_RE.match(first) and len(lines) <= 2:
                flush("caption")
            else:
                flush("paragraph")
    return elements
