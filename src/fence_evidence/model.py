"""Intermediate representation produced by extractors and consumed by the store.

Extractors never touch SQLite; the store never runs a parser.  This keeps the
canonical schema stable while extraction backends change.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

BBox = tuple[float, float, float, float]  # x0, y0, x1, y1 in PDF points, y down


@dataclass
class Word:
    text: str
    bbox: BBox
    confidence: Optional[float] = None  # 0..100, OCR only


@dataclass
class Element:
    element_type: str          # heading|paragraph|list|table|figure|drawing|drawing_label|caption
    text: str = ""             # source-layer text (never overwritten by OCR)
    ocr_text: Optional[str] = None
    text_source: str = "pdf_text_layer"   # pdf_text_layer|ocr|docx_xml|image_ocr
    bbox: Optional[BBox] = None
    heading_level: Optional[int] = None
    heading_path: list[str] = field(default_factory=list)
    ordinal: int = 0
    ocr_confidence: Optional[float] = None
    caption: Optional[str] = None
    table: Optional["Table"] = None
    region_image_path: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Cell:
    row: int
    col: int
    text: str
    rowspan: int = 1
    colspan: int = 1
    bbox: Optional[BBox] = None


@dataclass
class Table:
    n_rows: int
    n_cols: int
    cells: list[Cell]
    bbox: Optional[BBox] = None
    detector: str = "unknown"


@dataclass
class Page:
    page_no: int
    width: float
    height: float
    extraction_method: str
    elements: list[Element] = field(default_factory=list)
    words: list[Word] = field(default_factory=list)
    page_image_path: Optional[str] = None
    page_image_dpi: Optional[int] = None
    text_char_count: int = 0
    ocr_mean_confidence: Optional[float] = None
    has_text_layer: bool = False
    notes: list[str] = field(default_factory=list)
    extra_text_quality: Optional[dict[str, Any]] = None


@dataclass
class ExtractedDocument:
    source_path: str
    sha256: str
    file_type: str
    pages: list[Page] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    quality_issues: list[dict[str, Any]] = field(default_factory=list)
    tool_versions: dict[str, str] = field(default_factory=dict)

    def issue(self, severity: str, kind: str, detail: str, page_no: int | None = None):
        self.quality_issues.append(
            {"severity": severity, "kind": kind, "detail": detail, "page_no": page_no})
