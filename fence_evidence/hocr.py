"""hOCR parsing: word text, bounding box and per-word confidence."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from .model import Word

_BBOX_RE = re.compile(r"bbox (\d+) (\d+) (\d+) (\d+)")
_CONF_RE = re.compile(r"x_wconf (\d+)")
_NS = {"x": "http://www.w3.org/1999/xhtml"}


def _strip_doctype(xml: str) -> str:
    return re.sub(r"<!DOCTYPE[^>]*>", "", xml, count=1)


def parse_hocr(xml: str, scale: float = 1.0) -> tuple[list[Word], list[list[Word]]]:
    """Return (words, lines).  ``scale`` converts image pixels to page units."""
    root = ET.fromstring(_strip_doctype(xml))
    words: list[Word] = []
    lines: list[list[Word]] = []
    for line_el in root.iter():
        cls = line_el.get("class", "")
        if cls not in ("ocr_line", "ocr_textfloat", "ocr_header", "ocr_caption"):
            continue
        line_words: list[Word] = []
        for w in line_el.iter():
            if w.get("class") != "ocrx_word":
                continue
            title = w.get("title", "")
            m = _BBOX_RE.search(title)
            if not m:
                continue
            text = "".join(w.itertext()).strip()
            if not text:
                continue
            x0, y0, x1, y1 = (int(g) / scale for g in m.groups())
            c = _CONF_RE.search(title)
            word = Word(text=text, bbox=(x0, y0, x1, y1),
                        confidence=float(c.group(1)) if c else None)
            line_words.append(word)
            words.append(word)
        if line_words:
            lines.append(line_words)
    return words, lines


def mean_confidence(words: list[Word]) -> float | None:
    vals = [w.confidence for w in words if w.confidence is not None]
    return round(sum(vals) / len(vals), 2) if vals else None
