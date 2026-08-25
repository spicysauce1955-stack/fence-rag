"""Extractors: source file -> :class:`ExtractedDocument`.

Nothing here writes to the corpus and nothing here touches SQLite.  Derived
images are written under ``workspace/derived/<doc_id>/``.

OCR never overwrites source-layer text (prohibition 6): a page extracted from
the PDF text layer keeps ``text``; a page that has no text layer gets
``ocr_text`` and ``text_source="ocr"``.
"""
from __future__ import annotations

import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from .hocr import mean_confidence, parse_hocr
from .ids import doc_id_for, sha256_file
from .layout import (HeadingClassifier, HeadingStack, build_elements, line_text,
                     parse_bbox_layout, union)
from .model import Element, ExtractedDocument, Page, Table, Cell
from .paths import DERIVED_DIR, REPO_ROOT, ensure_writable, rel
from .quality import is_mojibake
from .tables import TableBackend, detect_ocr_tables
from .tools import ToolError, ocr_hocr, render_page, run, tool_versions

PAGE_DPI = 200          # evidence page images
OCR_DPI = 300           # OCR renders; discarded after use
ALT_OCR_DPI = 400       # second pass for low-confidence pages
OCR_SUPPLEMENT_BELOW = 80.0   # mean word confidence that triggers the second pass
# Some catalog pages in this corpus are physically enormous (one Showtech page
# renders to 134 megapixels at 300 dpi).  A second pass at a higher resolution
# on those costs minutes per page for little gain, so it is skipped and recorded.
MAX_SUPPLEMENT_PIXELS = 90_000_000
OCR_TEXT_THRESHOLD = 100   # chars of source text below which a page is OCR'd
DRAWING_WORD_MAX = 120     # a scanned page with fewer words reads as a drawing sheet
CAPTION_GAP = 40.0         # points below a figure to look for its caption


_ROT_RE = re.compile(r"Page\s+(\d+)\s+rot:\s*(-?\d+)")


def _page_rotations(pdf: Path, n_pages: int) -> dict[int, int]:
    """Per-page /Rotate values, normalised to 0/90/180/270."""
    r = run(["pdfinfo", "-f", "1", "-l", str(n_pages), str(pdf)])
    rots: dict[int, int] = {}
    for m in _ROT_RE.finditer(r.stdout):
        rots[int(m.group(1))] = int(m.group(2)) % 360
    return rots


# NOTE on rotation.  `pdftotext -bbox-layout` emits word boxes already in
# display space — verified by rendering synthetic /Rotate 0/90/180/270 pages at
# 72 dpi and comparing the reported boxes against the rendered ink, which match
# to within a point.  Only the `<page width/height>` attributes stay unrotated.
# So no coordinate transform is applied to words; the page rectangle is swapped
# for 90/270 so that boxes, page size and the rendered image share one space.
# An earlier version rotated the boxes as well, which moved them off the page.


_TABLE_HINT_WORDS = ("table", "exposure", "spacing", "footing", "embedment",
                    "maximum", "depth", "mph")


def _mentions_table(words) -> bool:
    """Does this page's OCR text name conditional/tabular engineering data?"""
    blob = " ".join(w.text.lower() for w in words)
    return sum(1 for k in _TABLE_HINT_WORDS if k in blob) >= 3


def _ocr_supplement(pdf: Path, page_no: int, tmpdir: Path, primary_words,
                    doc, page_width: float = 612.0, page_height: float = 792.0) -> list[str]:
    """Tokens a second-resolution OCR pass finds that the first pass missed."""
    px = (page_width * ALT_OCR_DPI / 72.0) * (page_height * ALT_OCR_DPI / 72.0)
    if px > MAX_SUPPLEMENT_PIXELS:
        doc.issue("info", "ocr_supplement_skipped",
                  f"page would render to {px / 1e6:.0f} megapixels at {ALT_OCR_DPI} dpi, "
                  f"above the {MAX_SUPPLEMENT_PIXELS / 1e6:.0f} MP budget; "
                  "only the primary OCR pass was run", page_no)
        return []
    seen = {w.text.strip().lower() for w in primary_words if w.text.strip()}
    try:
        alt_img = render_page(pdf, page_no, tmpdir / f"alt{page_no:04d}", dpi=ALT_OCR_DPI)
        alt_words, _ = parse_hocr(ocr_hocr(alt_img), scale=ALT_OCR_DPI / 72)
        alt_img.unlink(missing_ok=True)
    except ToolError as e:
        doc.issue("info", "ocr_supplement_failed", str(e)[:200], page_no)
        return []
    extra: list[str] = []
    for w in alt_words:
        t = w.text.strip()
        if not t or t.lower() in seen:
            continue
        if w.confidence is not None and w.confidence < 60:
            continue      # noise the primary pass was right to omit
        seen.add(t.lower())
        extra.append(t)
    return extra


def derived_dir(doc_id: str) -> Path:
    return DERIVED_DIR / doc_id


def _crop_region(page_image: Path, page_width: float, bbox, out_path: Path) -> bool:
    """Crop a region of the rendered page image.  Returns False if unavailable."""
    try:
        from PIL import Image
    except Exception:
        return False
    try:
        with Image.open(page_image) as im:
            scale = im.width / page_width if page_width else 1.0
            x0, y0, x1, y1 = (v * scale for v in bbox)
            pad = 4
            box = (max(0, int(x0) - pad), max(0, int(y0) - pad),
                   min(im.width, int(x1) + pad), min(im.height, int(y1) + pad))
            if box[2] - box[0] < 4 or box[3] - box[1] < 4:
                return False
            ensure_writable(out_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            im.crop(box).save(out_path)
        return True
    except Exception:
        return False


def _clamp_elements(page) -> None:
    """Clip element boxes to the page rectangle.

    OCR boxes arrive in image pixels and are divided by the render scale, so a
    box on the last column can land a fraction of a point outside the page.
    A bounding box that is not inside its page is not usable as evidence.
    """
    for el in page.elements:
        if not el.bbox:
            continue
        x0, y0, x1, y1 = el.bbox
        el.bbox = (round(max(0.0, x0), 2), round(max(0.0, y0), 2),
                   round(min(page.width, x1), 2), round(min(page.height, y1), 2))
        if el.table is not None and el.table.bbox:
            tx0, ty0, tx1, ty1 = el.table.bbox
            el.table.bbox = (round(max(0.0, tx0), 2), round(max(0.0, ty0), 2),
                             round(min(page.width, tx1), 2), round(min(page.height, ty1), 2))
            for c in el.table.cells:
                if c.bbox:
                    cx0, cy0, cx1, cy1 = c.bbox
                    c.bbox = (round(max(0.0, cx0), 2), round(max(0.0, cy0), 2),
                              round(min(page.width, cx1), 2), round(min(page.height, cy1), 2))


def _attach_captions(elements: list[Element]) -> None:
    captions = [e for e in elements if e.element_type == "caption" and e.bbox]
    for fig in elements:
        if fig.element_type not in ("figure", "drawing") or not fig.bbox:
            continue
        best, best_d = None, CAPTION_GAP
        for cap in captions:
            if cap.bbox[0] > fig.bbox[2] or cap.bbox[2] < fig.bbox[0]:
                continue  # no horizontal overlap
            d = cap.bbox[1] - fig.bbox[3]
            if 0 <= d < best_d:
                best, best_d = cap, d
        if best is not None:
            fig.caption = (best.text or best.ocr_text or "").strip() or None


# --------------------------------------------------------------------------- PDF
def extract_pdf(path: Path, *, doc_id: str | None = None,
                pages_limit: int | None = None) -> ExtractedDocument:
    path = Path(path)
    rp = rel(path)
    doc_id = doc_id or doc_id_for(rp)
    doc = ExtractedDocument(source_path=rp, sha256=sha256_file(path), file_type="pdf",
                            tool_versions=dict(tool_versions()))

    info = run(["pdfinfo", str(path)])
    meta = {}
    for line in info.stdout.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    doc.metadata = meta
    try:
        n_pages = int(meta.get("Pages", "0"))
    except ValueError:
        n_pages = 0
    if n_pages == 0:
        doc.issue("error", "unreadable_pdf",
                  f"pdfinfo reported no pages: {info.stderr.strip()[:200]}")
        return doc
    if meta.get("Encrypted", "no").startswith("yes"):
        doc.issue("warning", "encrypted_pdf",
                  f"document is encrypted ({meta.get('Encrypted')}); "
                  "extraction may be partial")
    if pages_limit:
        n_pages = min(n_pages, pages_limit)

    rotations = _page_rotations(path, n_pages)

    # One pdftotext call for the whole document: word geometry for every page.
    bbox_pages: list[dict] = []
    r = run(["pdftotext", "-bbox-layout", "-f", "1", "-l", str(n_pages), str(path), "-"])
    if r.returncode == 0 and r.stdout.strip():
        try:
            bbox_pages = parse_bbox_layout(r.stdout)
        except ET.ParseError as e:
            doc.issue("warning", "bbox_parse_failed",
                      f"pdftotext -bbox-layout output unparseable: {e}")
    else:
        doc.issue("warning", "text_layer_unavailable",
                  f"pdftotext returned nothing: {r.stderr.strip()[:200]}")

    all_lines = [ln for pg in bbox_pages for blk in pg["blocks"] for ln in blk]
    classifier = HeadingClassifier(all_lines) if all_lines else HeadingClassifier([])
    stack = HeadingStack()
    ddir = derived_dir(doc_id)
    tmpdir = Path(tempfile.mkdtemp(prefix="fenceocr-"))

    try:
        with TableBackend(path) as backend:
            if backend.open_error:
                doc.issue("warning", "table_backend_unavailable", backend.open_error)
            for pno in range(1, n_pages + 1):
                src = bbox_pages[pno - 1] if pno - 1 < len(bbox_pages) else None
                raw_w = float(src["width"]) if src else float(
                    (meta.get("Page size") or "612 x 792").split()[0] or 612)
                raw_h = float(src["height"]) if src else 792.0
                rot = rotations.get(pno, 0)
                # pdftoppm applies /Rotate, and pdftotext reports word boxes in
                # that same display space but the page attributes unrotated, so
                # only the page rectangle needs swapping (see the note above).
                width, height = ((raw_h, raw_w) if rot in (90, 270) else (raw_w, raw_h))
                page = Page(page_no=pno, width=width, height=height,
                            extraction_method="pdftotext-bbox")

                # page image (evidence) --------------------------------------
                try:
                    img = render_page(path, pno, ddir / "pages" / f"{pno:04d}", dpi=PAGE_DPI)
                    page.page_image_path = rel(img)
                    page.page_image_dpi = PAGE_DPI
                except ToolError as e:
                    doc.issue("error", "page_render_failed", str(e)[:300], pno)

                blocks = src["blocks"] if src else []
                # A text layer that decodes to mojibake is worse than none:
                # reject it and take the OCR path instead (recorded, not hidden).
                raw_page_text = "\n".join(line_text(ln) for blk in blocks for ln in blk)
                bad_text, tq = is_mojibake(raw_page_text)
                if bad_text:
                    blocks = []
                    page.notes.append(f"text layer rejected as mojibake: {tq}")
                    doc.issue("warning", "mojibake_text_layer",
                              f"source text layer rejected (control_ratio="
                              f"{tq['control_ratio']}, ascii_token_ratio="
                              f"{tq['ascii_token_ratio']}); page routed to OCR", pno)
                page_text_len = sum(len(line_text(ln)) for blk in blocks for ln in blk)
                page.extra_text_quality = tq
                page.text_char_count = page_text_len
                page.has_text_layer = page_text_len >= OCR_TEXT_THRESHOLD

                # tables and figures -----------------------------------------
                tables, figures, tbackend, tnotes = backend.page(pno)
                if bad_text and tables:
                    # cells read through the same unusable font encoding
                    page.notes.append(f"discarded {len(tables)} text-layer table(s) on a "
                                      "page whose text layer was rejected as mojibake")
                    tables = []
                for n in tnotes:
                    page.notes.append(n)

                # elements from the source text layer -------------------------
                ordinal = 0
                if page.has_text_layer:
                    els = build_elements(blocks, classifier, stack,
                                         text_source="pdf_text_layer",
                                         page_width=width, start_ordinal=ordinal,
                                         table_regions=[t.bbox for t in tables if t.bbox])
                    page.elements.extend(els)
                    ordinal = (els[-1].ordinal + 1) if els else ordinal
                    page.words = [w for blk in blocks for ln in blk for w in ln]
                else:
                    # no usable text layer on this page -> OCR it
                    page.extraction_method = ("pdftoppm+tesseract"
                                              if not bad_text else
                                              "pdftoppm+tesseract(mojibake-text-layer-rejected)")
                    ocr_words, ocr_lines = [], []
                    try:
                        ocr_img = render_page(path, pno, tmpdir / f"{pno:04d}", dpi=OCR_DPI)
                        hocr = ocr_hocr(ocr_img)
                        ocr_words, ocr_lines = parse_hocr(hocr, scale=OCR_DPI / 72)
                        ocr_img.unlink(missing_ok=True)
                    except ToolError as e:
                        doc.issue("error", "ocr_failed", str(e)[:300], pno)
                    page.words = ocr_words
                    page.ocr_mean_confidence = mean_confidence(ocr_words)
                    words_per_line = (len(ocr_words) / len(ocr_lines)) if ocr_lines else 0.0
                    # A drawing sheet's scattered callouts cluster into short
                    # rows exactly as a table's cells do, so grid reconstruction
                    # is not attempted there — it produced only false tables.
                    drawing_sheet = (len(ocr_lines) >= 8 and words_per_line < 4.0)
                    if not tables and ocr_words and not drawing_sheet:
                        tables = detect_ocr_tables(ocr_words, width, height)
                        for t in tables:
                            page.notes.append(
                                f"table reconstructed from OCR: {t.n_rows}x{t.n_cols}")
                    if not tables and ocr_words and _mentions_table(ocr_words):
                        doc.issue("warning", "table_not_reconstructed",
                                  "page names a table or conditional wind/exposure data "
                                  "but no cell grid could be recovered from OCR; the page "
                                  "image is the only faithful representation", pno)
                    ocr_blocks = [[ln] for ln in ocr_lines]  # one block per line
                    els = build_elements(ocr_blocks, classifier, stack,
                                         text_source="ocr", page_width=width,
                                         start_ordinal=ordinal,
                                         table_regions=[t.bbox for t in tables if t.bbox])
                    page.elements.extend(els)
                    ordinal = (els[-1].ordinal + 1) if els else ordinal
                    # OCR on these scans is resolution-unstable: individual
                    # numbers and dimension callouts appear at one render
                    # resolution and vanish at another. A second pass at a
                    # different resolution recovers some of them. It is stored
                    # as an additive supplement with its own provenance, never
                    # merged into or over the primary pass.
                    if ocr_words and page.ocr_mean_confidence is not None \
                            and page.ocr_mean_confidence < OCR_SUPPLEMENT_BELOW:
                        extra_words = _ocr_supplement(path, pno, tmpdir, ocr_words, doc,
                                                      page_width=width, page_height=height)
                        if extra_words:
                            page.elements.append(Element(
                                element_type="ocr_supplement", text="",
                                ocr_text=" ".join(extra_words), text_source="ocr",
                                bbox=(0.0, 0.0, width, height),
                                heading_path=list(stack.path), ordinal=ordinal,
                                ocr_confidence=page.ocr_mean_confidence,
                                extra={"dpi": ALT_OCR_DPI, "primary_dpi": OCR_DPI,
                                       "reason": "terms recovered only at the alternate "
                                                 "OCR resolution",
                                       "word_count": len(extra_words)}))
                            ordinal += 1
                            page.notes.append(
                                f"{len(extra_words)} token(s) recovered only at "
                                f"{ALT_OCR_DPI} dpi")
                    if ocr_words and (len(ocr_words) < DRAWING_WORD_MAX or drawing_sheet):
                        page.elements.append(Element(
                            element_type="drawing", text="",
                            ocr_text=" ".join(w.text for w in ocr_words),
                            text_source="ocr", bbox=(0.0, 0.0, width, height),
                            heading_path=list(stack.path), ordinal=ordinal,
                            ocr_confidence=page.ocr_mean_confidence,
                            extra={"reason": f"scanned page with {len(ocr_words)} words "
                                             f"in {len(ocr_lines)} lines "
                                             f"({words_per_line:.1f} words/line)"}))
                        ordinal += 1
                    if not ocr_words:
                        doc.issue("warning", "empty_page_after_ocr",
                                  "no text layer and OCR produced no words", pno)

                # table elements ----------------------------------------------
                for t in tables:
                    # cell text comes from whatever produced the grid, so the
                    # source label follows the detector rather than the page
                    from_ocr = t.detector.startswith("ocr-")
                    el = Element(element_type="table", text="",
                                 text_source="ocr" if from_ocr else "pdf_text_layer",
                                 bbox=t.bbox, heading_path=list(stack.path),
                                 ordinal=ordinal, table=t)
                    grid_text = "\n".join(
                        " | ".join(c.text for c in sorted(
                            [c for c in t.cells if c.row == r], key=lambda c: c.col))
                        for r in range(t.n_rows))
                    if from_ocr:
                        el.ocr_text = grid_text
                        el.ocr_confidence = page.ocr_mean_confidence
                    else:
                        el.text = grid_text
                    el.extra["detector"] = t.detector
                    page.elements.append(el)
                    ordinal += 1

                # figure elements ---------------------------------------------
                page_area = max(1.0, width * height)
                for fb in figures:
                    if (fb[2] - fb[0]) < 40 or (fb[3] - fb[1]) < 40:
                        continue  # rules, logos, spacer images
                    if not page.has_text_layer and \
                            ((fb[2] - fb[0]) * (fb[3] - fb[1])) / page_area > 0.85:
                        # the scan of the page itself is not a figure on the page
                        continue
                    page.elements.append(Element(
                        element_type="figure", text="", text_source="pdf_text_layer",
                        bbox=fb, heading_path=list(stack.path), ordinal=ordinal))
                    ordinal += 1

                _clamp_elements(page)
                _attach_captions(page.elements)

                # region crops for anything visual ----------------------------
                if page.page_image_path:
                    page_img = REPO_ROOT / page.page_image_path
                    for el in page.elements:
                        if el.element_type not in ("table", "figure", "drawing") or not el.bbox:
                            continue
                        out = ddir / "regions" / f"p{pno:04d}-{el.ordinal:04d}-{el.element_type}.png"
                        if _crop_region(page_img, width, el.bbox, out):
                            el.region_image_path = rel(out)

                doc.pages.append(page)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    _document_level_checks(doc)
    return doc


def _document_level_checks(doc: ExtractedDocument) -> None:
    if not doc.pages:
        doc.issue("error", "no_pages_extracted", "extraction produced no pages")
        return
    for p in doc.pages:
        if not p.page_image_path:
            doc.issue("error", "missing_page_image", "page image not produced", p.page_no)
        if not p.elements:
            doc.issue("warning", "empty_page", "no elements extracted from page", p.page_no)
        if p.ocr_mean_confidence is not None and p.ocr_mean_confidence < 70:
            doc.issue("warning", "low_ocr_confidence",
                      f"mean OCR word confidence {p.ocr_mean_confidence}", p.page_no)
        for el in p.elements:
            if el.bbox and (el.bbox[0] < -1 or el.bbox[1] < -1
                            or el.bbox[2] > p.width + 1 or el.bbox[3] > p.height + 1):
                doc.issue("warning", "bbox_out_of_page",
                          f"element bbox {el.bbox} outside page {p.width}x{p.height}",
                          p.page_no)


# -------------------------------------------------------------------------- DOCX
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _docx_par_text(par) -> str:
    return "".join(t.text or "" for t in par.iter(f"{_W}t"))


_DOCX_STYLE_LEVELS = (
    # No \b anchors: real style names concatenate words ("ARCATArticle"),
    # so a word boundary would never match the second half.
    (re.compile(r"heading\s*(\d)", re.I), None),   # Heading1..4 -> that level
    (re.compile(r"title", re.I), 1),
    (re.compile(r"part", re.I), 1),
    (re.compile(r"article|section", re.I), 2),
    (re.compile(r"subsub\d*", re.I), 3),
)


def _docx_level_from_style(style: str) -> int | None:
    """Map a paragraph style name to a heading level.

    Word documents in the wild rarely use the built-in Heading styles; the CSI
    MasterSpec in this corpus uses ARCATTitle / ARCATPart / ARCATArticle.  The
    patterns below are generic enough to cover both conventions.
    """
    if not style:
        return None
    for rx, level in _DOCX_STYLE_LEVELS:
        m = rx.search(style)
        if m:
            if level is None:
                try:
                    return min(int(m.group(1)), 4)
                except (IndexError, ValueError):
                    return 2
            return level
    return None


def _docx_style(par) -> str:
    pPr = par.find(f"{_W}pPr")
    if pPr is None:
        return ""
    st = pPr.find(f"{_W}pStyle")
    return (st.get(f"{_W}val") or "") if st is not None else ""


def extract_docx(path: Path, *, doc_id: str | None = None) -> ExtractedDocument:
    """DOCX via stdlib zipfile + ElementTree.

    Page geometry does not exist in a DOCX, so elements carry no bbox; the
    section hierarchy comes from paragraph styles instead of text size.
    """
    path = Path(path)
    rp = rel(path)
    doc_id = doc_id or doc_id_for(rp)
    doc = ExtractedDocument(source_path=rp, sha256=sha256_file(path), file_type="docx",
                            tool_versions=dict(tool_versions()))
    page = Page(page_no=1, width=612.0, height=792.0, extraction_method="docx-xml")
    stack = HeadingStack()
    ordinal = 0
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml")
            try:
                core = z.read("docProps/core.xml").decode("utf-8", "replace")
                for tag in ("title", "creator", "lastModifiedBy", "revision"):
                    m = re.search(rf"<[a-z]*:?{tag}>([^<]*)<", core, re.I)
                    if m:
                        doc.metadata[tag] = m.group(1)
            except KeyError:
                pass
    except zipfile.BadZipFile as e:
        doc.issue("error", "unreadable_docx", str(e))
        return doc
    root = ET.fromstring(xml)
    body = root.find(f"{_W}body")
    if body is None:
        doc.issue("error", "unreadable_docx", "no <w:body> in word/document.xml")
        return doc

    for child in body:
        if child.tag == f"{_W}p":
            text = _docx_par_text(child).strip()
            if not text:
                continue
            style = _docx_style(child)
            level = _docx_level_from_style(style)
            if level is None and re.match(r"^(PART|SECTION)\s+\d", text):
                level = 1
            if level is None and re.match(r"^\d+\.\d+\s+[A-Z]", text):
                level = 2
            if level is not None:
                stack.push(min(level, 4), text)
                page.elements.append(Element(
                    element_type="heading", text=text, text_source="docx_xml",
                    heading_level=min(level, 4), heading_path=list(stack.path),
                    ordinal=ordinal, extra={"style": style}))
            else:
                page.elements.append(Element(
                    element_type="paragraph", text=text, text_source="docx_xml",
                    heading_path=list(stack.path), ordinal=ordinal,
                    extra={"style": style}))
            ordinal += 1
        elif child.tag == f"{_W}tbl":
            cells: list[Cell] = []
            n_rows = 0
            n_cols = 0
            for r, tr in enumerate(child.findall(f"{_W}tr")):
                n_rows += 1
                tcs = tr.findall(f"{_W}tc")
                n_cols = max(n_cols, len(tcs))
                for c, tc in enumerate(tcs):
                    txt = " ".join(_docx_par_text(p).strip()
                                   for p in tc.findall(f"{_W}p")).strip()
                    if txt:
                        cells.append(Cell(row=r, col=c, text=txt))
            if cells:
                table = Table(n_rows=n_rows, n_cols=n_cols, cells=cells,
                              detector="docx-w:tbl")
                el = Element(element_type="table", text="\n".join(
                    " | ".join(c.text for c in sorted(
                        [c for c in cells if c.row == r], key=lambda c: c.col))
                    for r in range(n_rows)),
                    text_source="docx_xml", heading_path=list(stack.path),
                    ordinal=ordinal, table=table)
                page.elements.append(el)
                ordinal += 1
    page.text_char_count = sum(len(e.text) for e in page.elements)
    page.has_text_layer = True
    doc.pages.append(page)
    doc.issue("info", "no_page_image_for_docx",
              "a DOCX has no page geometry and no document renderer is available in "
              "this environment, so no page image or bounding boxes are produced; "
              "section hierarchy and table cells are preserved instead", 1)
    if not page.elements:
        doc.issue("error", "no_elements", "DOCX produced no elements")
    return doc


# ------------------------------------------------------------------------- image
def extract_image(path: Path, *, doc_id: str | None = None) -> ExtractedDocument:
    """Raster drawing (CAD PNG): OCR labels with bounding boxes."""
    path = Path(path)
    rp = rel(path)
    doc_id = doc_id or doc_id_for(rp)
    doc = ExtractedDocument(source_path=rp, sha256=sha256_file(path),
                            file_type=path.suffix.lstrip("."),
                            tool_versions=dict(tool_versions()))
    ddir = derived_dir(doc_id)
    width = height = 0.0
    try:
        from PIL import Image
        with Image.open(path) as im:
            width, height = float(im.width), float(im.height)
            out = ddir / "pages" / "0001.png"
            ensure_writable(out)
            out.parent.mkdir(parents=True, exist_ok=True)
            im.convert("RGB").save(out)
        page_image = rel(out)
    except Exception as e:
        doc.issue("error", "image_unreadable", f"{e.__class__.__name__}: {e}")
        return doc

    page = Page(page_no=1, width=width, height=height,
                extraction_method="tesseract-ocr", page_image_path=page_image,
                page_image_dpi=72)
    try:
        words, lines = parse_hocr(ocr_hocr(path, psm=11), scale=1.0)
    except ToolError as e:
        doc.issue("error", "ocr_failed", str(e)[:300], 1)
        words, lines = [], []
    page.words = words
    page.ocr_mean_confidence = mean_confidence(words)

    ordinal = 0
    for ln in lines:
        text = line_text(ln)
        if not text.strip():
            continue
        confs = [w.confidence for w in ln if w.confidence is not None]
        page.elements.append(Element(
            element_type="drawing_label", text="", ocr_text=text, text_source="image_ocr",
            bbox=union([w.bbox for w in ln]), ordinal=ordinal,
            ocr_confidence=round(sum(confs) / len(confs), 2) if confs else None))
        ordinal += 1
    page.elements.append(Element(
        element_type="drawing", text="",
        ocr_text=" ".join(w.text for w in words), text_source="image_ocr",
        bbox=(0.0, 0.0, width, height), ordinal=ordinal,
        ocr_confidence=page.ocr_mean_confidence,
        region_image_path=page_image,
        extra={"reason": "whole-image drawing"}))
    page.text_char_count = 0
    _clamp_elements(page)
    doc.pages.append(page)
    if not words:
        doc.issue("warning", "no_ocr_labels", "OCR produced no drawing labels", 1)
    return doc


EXTRACTORS = {
    "pdf": extract_pdf,
    "docx": extract_docx,
    "png": extract_image, "jpg": extract_image, "jpeg": extract_image,
    "tif": extract_image, "tiff": extract_image,
}


def extract(path: Path, **kw) -> ExtractedDocument:
    suffix = Path(path).suffix.lower().lstrip(".")
    fn = EXTRACTORS.get(suffix)
    if fn is None:
        raise ValueError(f"no extractor for {suffix!r}: {path}")
    if suffix != "pdf":
        kw.pop("pages_limit", None)
    return fn(Path(path), **kw)
