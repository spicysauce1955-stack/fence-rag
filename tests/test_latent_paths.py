"""G9 — the two latent correctness fixes, driven end to end over synthetic input.

`docs/state-and-gaps.md` G9 records two review findings that were real but
unexercised, because the corpus happens not to contain the input that would
exercise them:

  * **rotation** — no corpus page has both a non-zero ``/Rotate`` *and* a text
    layer, so the "boxes are already in display space; do not transform them"
    decision has never met the combination it is about;
  * **two versions** — no document in the store has two byte-versions, so the
    version scoping in the retrieval projection, ``get_page``,
    ``get_element_context`` and the facts layer has never been run against one.

The corpus is read-only, so neither input can be added to it. What this module
does instead is *manufacture* the input and put it through the production code:

  * a one-page PDF is assembled byte by byte (stdlib only, no writer library)
    with a real ``/Rotate`` entry and a real Type1 text layer, and handed to
    ``extract.extract_pdf`` — the same function ingestion calls;
  * two such PDFs, differing in content, are written to the *same* source path
    in turn and both put through ``store.write_extracted`` — the same writer
    ingestion calls — producing one ``documents`` row with two
    ``document_versions``, which is exactly the shape the store has never held.

Nothing here re-implements a production function or hand-writes SQL against the
schema; the fixtures are inputs, and every assertion is about what the shipped
code did with them.

The rotation assertions are deliberately made against **rendered ink**: each
page is rasterised with the production ``tools.render_page`` and the dark pixels
are located with a small stdlib PNG reader, so the test compares the boxes
``pdftotext -bbox-layout`` reported with where the glyphs actually landed. That
is the regression guard CLAUDE.md asks for — re-adding the word rotation
transform that was found wrong and removed makes
``test_reported_boxes_match_the_rendered_ink`` fail on three of the four
rotations, and ``test_the_removed_word_transform_would_now_be_caught`` states
that in so many words.
"""
from __future__ import annotations

import json
import shutil
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

import context  # noqa: F401  (puts the repository root on sys.path)

import fence_evidence.extract as extract
from fence_evidence import crops, facts, refs, retrieval, store
from fence_evidence.ids import doc_id_for
from fence_evidence.paths import REPO_ROOT, TESTS_DIR, rel
from fence_evidence.tools import render_page

_POPPLER = all(shutil.which(t) for t in ("pdfinfo", "pdftotext", "pdftoppm"))
requires_poppler = unittest.skipUnless(
    _POPPLER, "poppler (pdfinfo/pdftotext/pdftoppm) is not installed")

# The synthetic page is US Letter in PDF user space. Under /Rotate 90 or 270 the
# *display* rectangle is the transpose of this, which is the whole point.
MEDIA_W, MEDIA_H = 612.0, 792.0

# Glyph boxes include ascender and descender space, so the union of the reported
# element boxes is legitimately a little larger than the ink it encloses. Six
# points is comfortably below the ~20pt error any rotation transform introduces.
INK_TOLERANCE_PT = 6.0


# --------------------------------------------------------------------------
# fixture builders — inputs only, never re-implementations of anything shipped
# --------------------------------------------------------------------------
def _write_pdf(path: Path, *, rotate: int, lines) -> Path:
    """Write a one-page PDF with a genuine text layer and a /Rotate entry.

    ``lines`` is ``[(x, y, size, text)]`` in unrotated PDF user space (y up),
    drawn in Helvetica so poppler needs no embedded font. Hand-assembled rather
    than produced by a library because this package has no third-party
    dependency it is allowed to require.
    """
    stream = "".join(
        "BT /F1 %d Tf 1 0 0 1 %.2f %.2f Tm (%s) Tj ET\n" % (size, x, y, text)
        for (x, y, size, text) in lines).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        ("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Rotate %d "
         "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
         % (MEDIA_W, MEDIA_H, rotate)).encode(),
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    buf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(buf))
        buf += ("%d 0 obj\n" % i).encode() + obj + b"\nendobj\n"
    xref = len(buf)
    buf += ("xref\n0 %d\n" % (len(objects) + 1)).encode() + b"0000000000 65535 f \n"
    for off in offsets:
        buf += ("%010d 00000 n \n" % off).encode()
    buf += ("trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
            % (len(objects) + 1, xref)).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(buf))
    return path


def _page_lines(depth_in: int, marker: str):
    """Enough prose to clear OCR_TEXT_THRESHOLD, so the text-layer path is taken.

    Below 100 characters ``extract_pdf`` routes the page to OCR and the fixture
    would stop being about the text layer at all.
    """
    body = [
        # The marker rides inside a prose line on purpose. A short line on its
        # own is classified as a heading, and headings are deliberately excluded
        # from `retrieval_units` (store.UNIT_EXCLUDED_TYPES), so a standalone
        # marker would never reach the projection or the FTS index.
        "Chesterfield privacy fence installation instructions for REVISION%s panels."
        % marker,
        "Set each post in a concrete footing and cure it before hanging a panel.",
        "Post embedment depth %d in. for Exposure C at 130 mph design wind speed." % depth_in,
        "Space the posts 96 in. on center measured from the center of each post.",
        "REVISION%s" % marker,
    ]
    return [(72.0, 720.0 - 24.0 * i, 11, text) for i, text in enumerate(body)]


def _png_ink_bbox(path: Path, threshold: int = 128):
    """Where the dark pixels are, in ``(x0, y0, x1, y1)``, plus the image size.

    A ~40-line PNG reader rather than Pillow: Pillow lives in the git-ignored
    ``workspace/pylibs/`` and every third-party package in this repo has to stay
    optional, so a regression guard that only runs when Pillow happens to be
    installed is not a guard. Handles the 8-bit non-interlaced greyscale and
    truecolour images pdftoppm emits and nothing else.
    """
    raw = path.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG: %s" % path)
    pos, idat = 8, bytearray()
    width = height = bit_depth = colour_type = None
    while pos < len(raw):
        length, kind = struct.unpack(">I4s", raw[pos:pos + 8])
        pos += 8
        data = raw[pos:pos + length]
        pos += length + 4          # skip the CRC
        if kind == b"IHDR":
            width, height, bit_depth, colour_type, _c, _f, interlace = \
                struct.unpack(">IIBBBBB", data)
            if bit_depth != 8 or interlace != 0 or colour_type not in (0, 2, 4, 6):
                raise ValueError("unsupported PNG: depth=%s colour=%s interlace=%s"
                                 % (bit_depth, colour_type, interlace))
        elif kind == b"IDAT":
            idat += data
        elif kind == b"IEND":
            break
    bpp = {0: 1, 2: 3, 4: 2, 6: 4}[colour_type]
    body = zlib.decompress(bytes(idat))
    stride = width * bpp
    previous = bytearray(stride)
    x0 = y0 = 1 << 30
    x1 = y1 = -1
    offset = 0
    for y in range(height):
        filt = body[offset]
        offset += 1
        line = bytearray(body[offset:offset + stride])
        offset += stride
        if filt == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif filt == 2:
            for i in range(stride):
                line[i] = (line[i] + previous[i]) & 255
        elif filt == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + previous[i]) >> 1)) & 255
        elif filt == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = previous[i]
                c = previous[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 255
        elif filt != 0:
            raise ValueError("unknown PNG filter %d" % filt)
        for x in range(width):
            if line[x * bpp] < threshold:
                if x < x0:
                    x0 = x
                if x > x1:
                    x1 = x
                if y < y0:
                    y0 = y
                if y > y1:
                    y1 = y
        previous = line
    box = None if x1 < 0 else (float(x0), float(y0), float(x1), float(y1))
    return box, (width, height)


def _element_union(page):
    boxes = [e.bbox for e in page.elements if e.bbox]
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def _scratch(prefix: str) -> Path:
    """A writable directory inside workspace/ — ensure_writable applies to tests."""
    base = TESTS_DIR / "latent-paths"
    base.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=prefix, dir=base))


# --------------------------------------------------------------------------
# 1. the rotation path: a non-zero /Rotate AND a text layer
# --------------------------------------------------------------------------
@requires_poppler
class TestRotatedPageWithTextLayer(unittest.TestCase):
    """The combination the corpus does not contain, put through `extract_pdf`.

    Four pages with identical content and ``/Rotate`` 0, 90, 180 and 270. Every
    assertion below is about what the production extractor returned, compared
    against where poppler actually painted the glyphs.
    """

    ROTATIONS = (0, 90, 180, 270)

    @classmethod
    def setUpClass(cls):
        cls.tmp = _scratch("rotate-")
        # `derived_dir` reads this module global, so redirecting it keeps the
        # fixture's page images out of the real 4.9 GB derived cache.
        cls._derived = extract.DERIVED_DIR
        extract.DERIVED_DIR = cls.tmp / "derived"
        cls.pdfs, cls.docs = {}, {}
        for rot in cls.ROTATIONS:
            pdf = _write_pdf(cls.tmp / ("rot%d.pdf" % rot), rotate=rot,
                             lines=_page_lines(36, "A"))
            cls.pdfs[rot] = pdf
            cls.docs[rot] = extract.extract_pdf(pdf)

    @classmethod
    def tearDownClass(cls):
        extract.DERIVED_DIR = cls._derived
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _page(self, rot):
        doc = self.docs[rot]
        self.assertEqual(len(doc.pages), 1, "fixture is one page")
        return doc.pages[0]

    def test_fixture_is_the_combination_the_corpus_lacks(self):
        """A non-zero /Rotate and a *source* text layer, on the same page."""
        for rot in self.ROTATIONS:
            with self.subTest(rotate=rot):
                self.assertEqual(extract._page_rotations(self.pdfs[rot], 1), {1: rot})
                page = self._page(rot)
                self.assertTrue(page.has_text_layer,
                                "the fixture must exercise the text-layer path, not OCR")
                self.assertEqual(page.extraction_method, "pdftotext-bbox")
                self.assertGreaterEqual(page.text_char_count, extract.OCR_TEXT_THRESHOLD)
                self.assertTrue(all(e.text_source == "pdf_text_layer"
                                    for e in page.elements))

    def test_page_rectangle_is_the_display_rectangle(self):
        """90/270 swap the page rectangle; 0/180 leave it alone."""
        for rot in self.ROTATIONS:
            with self.subTest(rotate=rot):
                page = self._page(rot)
                expected = (MEDIA_H, MEDIA_W) if rot in (90, 270) else (MEDIA_W, MEDIA_H)
                self.assertEqual((page.width, page.height), expected)

    def test_page_rectangle_matches_the_rendered_page_image(self):
        """The stored rectangle and the stored image must describe one space."""
        for rot in self.ROTATIONS:
            with self.subTest(rotate=rot):
                page = self._page(rot)
                self.assertIsNotNone(page.page_image_path)
                # page_image_path is repo-relative, as the store records it
                png = REPO_ROOT / page.page_image_path
                _, (w_px, h_px) = _png_ink_bbox(png)
                scale = page.page_image_dpi / 72.0
                self.assertAlmostEqual(w_px / scale, page.width, delta=1.0)
                self.assertAlmostEqual(h_px / scale, page.height, delta=1.0)

    def test_boxes_are_reported_in_display_space_not_media_space(self):
        """Under /Rotate 90 the boxes leave the MediaBox — they are display-space.

        If `pdftotext -bbox-layout` were reporting media-space boxes, every
        coordinate would fit inside 612x792 and this would be unprovable either
        way. It does not: the reported x extends past 612, which only the
        rotated 792-point-wide display rectangle can contain.
        """
        page = self._page(90)
        union = _element_union(page)
        self.assertIsNotNone(union)
        self.assertGreater(union[2], MEDIA_W,
                           "boxes fit inside the unrotated MediaBox, so they are "
                           "not in display space and this fixture proves nothing")
        self.assertLessEqual(union[2], page.width + 0.01)
        self.assertLessEqual(union[3], page.height + 0.01)

    def test_reported_boxes_match_the_rendered_ink(self):
        """The regression guard: reported geometry vs. where the glyphs landed.

        CLAUDE.md: *"`pdftotext -bbox-layout` already reports word boxes in
        display space; do not add a rotation transform — that bug was found and
        removed once."* Any transform applied to the words moves them away from
        the ink and fails here for 90, 180 and 270.
        """
        for rot in self.ROTATIONS:
            with self.subTest(rotate=rot):
                page = self._page(rot)
                png = render_page(self.pdfs[rot], 1, self.tmp / ("ink%d" % rot), dpi=72)
                ink, (w_px, h_px) = _png_ink_bbox(png)
                self.assertIsNotNone(ink, "the fixture page must have visible ink")
                self.assertEqual((w_px, h_px), (int(page.width), int(page.height)))
                union = _element_union(page)
                for i, (got, want) in enumerate(zip(union, ink)):
                    self.assertAlmostEqual(
                        got, want, delta=INK_TOLERANCE_PT,
                        msg=("rotate=%d coordinate %d: extractor says %.2f, the "
                             "rendered ink is at %.2f — the reported boxes are not "
                             "in the space the page image is in" % (rot, i, got, want)))

    def test_the_removed_word_transform_would_now_be_caught(self):
        """State the regression explicitly: the old transform disagrees with the ink.

        An earlier version of `extract.py` rotated the word boxes as well as the
        page rectangle. This applies that transform to the boxes the current
        code produced and shows the result no longer describes the rendered
        page — so the guard above is not vacuous.
        """
        page = self._page(90)
        ink, _ = _png_ink_bbox(
            render_page(self.pdfs[90], 1, self.tmp / "ink-transform", dpi=72))
        # the transform that was removed: rotate each box about the page centre
        # for /Rotate 90, mapping (x, y) -> (page_h - y, x) in media space
        def rotated(box):
            x0, y0, x1, y1 = box
            return (MEDIA_H - y1, x0, MEDIA_H - y0, x1)
        boxes = [rotated(e.bbox) for e in page.elements if e.bbox]
        union = (min(b[0] for b in boxes), min(b[1] for b in boxes),
                 max(b[2] for b in boxes), max(b[3] for b in boxes))
        worst = max(abs(a - b) for a, b in zip(union, ink))
        self.assertGreater(
            worst, INK_TOLERANCE_PT * 10,
            "the removed transform now agrees with the ink, which would mean the "
            "extractor's convention changed and this guard has stopped guarding")

    def test_crops_cut_the_named_rectangle_from_a_rotated_page(self):
        """`crops.py` trap 2 — the normative source-ref transform, on /Rotate 90.

        `crops.py` claims that for a rotated page "bbox, page rectangle and
        image share one space". Nothing in the corpus could test that. Here the
        crop of the element's own box must contain ink, and a crop of an empty
        corner of the same page must not.
        """
        page = self._page(90)
        marked = [e for e in page.elements
                  if "REVISIONA" in (e.text or "") and e.bbox]
        self.assertTrue(marked, "fixture lost its marker element")
        out = crops.render_crop(rel(self.pdfs[90]), 1, marked[0].bbox,
                                page_w_pt=page.width, page_h_pt=page.height,
                                dpi=page.page_image_dpi,
                                out_path=self.tmp / "crop-marker.png")
        ink, _ = _png_ink_bbox(out)
        self.assertIsNotNone(
            ink, "the crop of a text element on a rotated page came back blank; "
                 "the crop window is not in the same space as the bbox")

        # control: a rectangle the page rectangle contains but the text does not
        empty = (page.width - 120.0, page.height - 90.0,
                 page.width - 20.0, page.height - 20.0)
        blank = crops.render_crop(rel(self.pdfs[90]), 1, empty,
                                  page_w_pt=page.width, page_h_pt=page.height,
                                  dpi=page.page_image_dpi,
                                  out_path=self.tmp / "crop-blank.png")
        self.assertIsNone(_png_ink_bbox(blank)[0],
                          "a corner the fixture leaves empty came back with ink")


# --------------------------------------------------------------------------
# 2. the two-versions path
# --------------------------------------------------------------------------
def _build_two_version_store(tmp: Path) -> dict:
    """One document, two byte-versions, written by the production writers.

    The two PDFs occupy the *same* source path in turn, which is what makes them
    two versions of one document rather than two documents: `doc_id_for` keys on
    the repo-relative path and `document_versions` keys on the SHA-256. That is
    the real-world case — a manufacturer replacing the PDF behind a URL — and
    the case the store has never actually held.

    `ingested_at` is set explicitly afterwards. `store.now()` has one-second
    resolution, both writes land in the same second, and "which version is
    newest" is the whole question these tests ask; two timestamps a month apart
    is what a re-ingest would really look like and removes the tie.
    """
    saved_derived = extract.DERIVED_DIR
    extract.DERIVED_DIR = tmp / "derived"
    try:
        source = tmp / "chesterfield-install.pdf"
        _write_pdf(source, rotate=0, lines=_page_lines(36, "A"))
        first = extract.extract_pdf(source)
        _write_pdf(source, rotate=0, lines=_page_lines(42, "B"))
        second = extract.extract_pdf(source)
    finally:
        extract.DERIVED_DIR = saved_derived
    assert first.sha256 != second.sha256, "fixture versions must differ in bytes"

    conn = store.connect(tmp / "evidence.db")
    store.migrate(conn)
    run_id = store.start_run(conn, first.tool_versions, "test-latent-paths")
    manifest_row = {
        "doc_id": doc_id_for(rel(source)), "source_path": rel(source),
        "file_type": "pdf", "corpus_track": "us", "manufacturer": "fixture",
        "doc_type": "installation_instructions", "title": "Chesterfield Install",
        "file_size_bytes": source.stat().st_size,
    }
    v1 = store.write_extracted(conn, first, manifest_row, run_id)
    v2 = store.write_extracted(conn, second, manifest_row, run_id)
    conn.execute("UPDATE document_versions SET ingested_at=? WHERE version_id=?",
                 ("2026-01-01T00:00:00Z", v1))
    conn.execute("UPDATE document_versions SET ingested_at=? WHERE version_id=?",
                 ("2026-02-01T00:00:00Z", v2))
    conn.commit()
    store.build_retrieval_units(conn)
    return {"conn": conn, "doc_id": manifest_row["doc_id"], "old": v1, "new": v2,
            "source": source}


class _TwoVersionFixture(unittest.TestCase):
    """Base: each subclass gets its own store, because some of them mutate it."""

    @classmethod
    def setUpClass(cls):
        if not _POPPLER:
            raise unittest.SkipTest("poppler is not installed")
        cls.tmp = _scratch("versions-")
        fixture = _build_two_version_store(cls.tmp)
        cls.conn = fixture["conn"]
        cls.doc_id = fixture["doc_id"]
        cls.old = fixture["old"]
        cls.new = fixture["new"]
        cls.source = fixture["source"]

    @classmethod
    def tearDownClass(cls):
        try:
            cls.conn.close()
        except Exception:
            pass
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def elements_of(self, version_id):
        return {r[0] for r in self.conn.execute(
            "SELECT element_id FROM elements WHERE version_id=?", (version_id,))}


class TestTwoVersionsOfOneDocument(_TwoVersionFixture):
    """Version scoping in the projection, get_page, get_element_context, facts."""

    def test_the_fixture_really_holds_two_versions_of_one_document(self):
        docs = self.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        versions = [r[0] for r in self.conn.execute(
            "SELECT version_id FROM document_versions ORDER BY ingested_at")]
        self.assertEqual(docs, 1)
        self.assertEqual(versions, [self.old, self.new])
        self.assertEqual(
            self.conn.execute("SELECT COUNT(DISTINCT sha256) FROM document_versions"
                              ).fetchone()[0], 2,
            "the two versions must differ in bytes, not merely in extraction run")
        # both are edition 1 of their own bytes: this is the byte-version axis,
        # not the G38 toolchain-edition axis.
        self.assertEqual({r[0] for r in self.conn.execute(
            "SELECT edition FROM document_versions")}, {1})

    def test_projection_covers_both_versions_and_mixes_neither(self):
        """Both byte-versions are projected; no unit straddles the two."""
        rows = self.conn.execute(
            "SELECT unit_id, version_id, element_ids, text FROM retrieval_units").fetchall()
        self.assertTrue(rows, "the projection is empty")
        by_version = {}
        for row in rows:
            by_version.setdefault(row["version_id"], []).append(row)
        self.assertEqual(set(by_version), {self.old, self.new},
                         "both byte-versions must be projected — they are different "
                         "content, not two measurements of the same content")
        for version_id, units in by_version.items():
            owned = self.elements_of(version_id)
            for unit in units:
                self.assertTrue(
                    set(json.loads(unit["element_ids"])) <= owned,
                    "unit %s claims elements outside its own version" % unit["unit_id"])

    def test_each_unit_carries_only_its_own_version_text(self):
        for row in self.conn.execute(
                "SELECT version_id, text FROM retrieval_units").fetchall():
            marker = "REVISIONA" if row["version_id"] == self.old else "REVISIONB"
            other = "REVISIONB" if row["version_id"] == self.old else "REVISIONA"
            with self.subTest(version=row["version_id"]):
                self.assertIn(marker, row["text"])
                self.assertNotIn(other, row["text"])

    def test_search_returns_each_version_under_its_own_marker(self):
        """The FTS index reaches both versions and does not confuse them.

        `SearchResult` names ``document_id``, ``page`` and ``element_id`` but no
        version, so with two versions of one document the *only* thing in a
        result that distinguishes them is the element id. That is enough to
        resolve — the assertion below does exactly that — but it is worth
        knowing that the search surface does not say which version it answered
        from.
        """
        for version_id, marker, depth in ((self.old, "REVISIONA", "36 in"),
                                          (self.new, "REVISIONB", "42 in")):
            with self.subTest(marker=marker):
                hits = retrieval.search_evidence(marker, limit=5, conn=self.conn)
                self.assertTrue(hits, "no hit for %s" % marker)
                owned = self.elements_of(version_id)
                self.assertTrue(
                    all(h.element_id in owned for h in hits),
                    "a search for %s reached the other version" % marker)
                self.assertIn(depth, hits[0].text)

    def test_get_page_returns_the_newest_version(self):
        page = retrieval.get_page(self.doc_id, 1, conn=self.conn)
        self.assertIsNotNone(page)
        self.assertEqual(page["version_id"], self.new)

    def test_get_page_elements_all_belong_to_that_one_version(self):
        page = retrieval.get_page(self.doc_id, 1, conn=self.conn)
        owned = self.elements_of(self.new)
        self.assertTrue(page["elements"])
        for element in page["elements"]:
            self.assertIn(element["element_id"], owned)
        blob = " ".join(e["text"] for e in page["elements"])
        self.assertIn("REVISIONB", blob)
        self.assertNotIn("REVISIONA", blob)
        self.assertNotIn("36 in.", blob)

    def test_get_element_context_never_crosses_a_version_boundary(self):
        """Asked about an *old* version's element, the neighbours stay old."""
        for version_id in (self.old, self.new):
            owned = sorted(self.elements_of(version_id))
            with self.subTest(version=version_id):
                for element_id in owned:
                    ctx = retrieval.get_element_context(
                        element_id, before=10, after=10, conn=self.conn)
                    self.assertIsNotNone(ctx)
                    self.assertTrue(ctx["context"], "context came back empty")
                    for neighbour in ctx["context"]:
                        self.assertIn(
                            neighbour["element_id"], owned,
                            "context for an element of %s reached into the other "
                            "version" % version_id)

    def test_facts_are_asserted_only_from_the_newest_version(self):
        """An older version's values stay in the store but are not re-asserted."""
        result = facts.extract_facts(conn=self.conn)
        self.assertGreater(result["facts"], 0)
        versions = {r[0] for r in self.conn.execute(
            "SELECT DISTINCT version_id FROM facts")}
        self.assertEqual(versions, {self.new})
        depths = [(r["value_normalized"], r["evidence_text"]) for r in self.conn.execute(
            "SELECT value_normalized, evidence_text FROM facts "
            "WHERE fact_type='footing_depth_in'")]
        self.assertEqual([d[0] for d in depths], [42.0],
                         "the superseded 36-inch embedment was re-asserted as a fact")
        self.assertTrue(all(e["element_id"] in self.elements_of(self.new)
                            for e in self.conn.execute(
                                "SELECT element_id FROM facts")))


class TestDeleteVersionRowsUnderTwoVersions(_TwoVersionFixture):
    """`delete_version_rows` removes one edition and must not touch the other.

    CLAUDE.md warns that this function removes the rows an old `ref_id` named,
    so the property that matters is *scope*: deleting version 1 leaves version 2
    whole, and every ref minted from version 2 still resolves.
    """

    def _counts(self, version_id):
        conn = self.conn
        table_count = conn.execute(
            "SELECT COUNT(*) FROM tables t JOIN elements e ON e.element_id=t.element_id "
            "WHERE e.version_id=?", (version_id,)).fetchone()[0]
        return {
            "pages": conn.execute("SELECT COUNT(*) FROM pages WHERE version_id=?",
                                  (version_id,)).fetchone()[0],
            "elements": conn.execute("SELECT COUNT(*) FROM elements WHERE version_id=?",
                                     (version_id,)).fetchone()[0],
            "assets": conn.execute("SELECT COUNT(*) FROM assets WHERE version_id=?",
                                   (version_id,)).fetchone()[0],
            "tables": table_count,
        }

    def _refs_of(self, version_id):
        sha = self.conn.execute(
            "SELECT sha256 FROM document_versions WHERE version_id=?",
            (version_id,)).fetchone()[0]
        rows = self.conn.execute(
            "SELECT page_no, bbox FROM elements WHERE version_id=?", (version_id,))
        ids = {refs.ref_id(sha, r["page_no"], r["bbox"]) for r in rows}
        ids.add(refs.ref_id(sha, 1, None))          # the whole-page ref
        return ids

    def test_deleting_version_one_leaves_version_two_intact(self):
        before_new = self._counts(self.new)
        before_old = self._counts(self.old)
        self.assertGreater(before_old["elements"], 0)
        self.assertGreater(before_new["elements"], 0)

        new_refs = self._refs_of(self.new)
        index = refs.build_index(self.conn)
        self.assertTrue(all(refs.resolve(index, r) for r in new_refs))

        store.delete_version_rows(self.conn, self.old)
        self.conn.commit()

        self.assertEqual(self._counts(self.old),
                         {"pages": 0, "elements": 0, "assets": 0, "tables": 0})
        self.assertEqual(self._counts(self.new), before_new,
                         "deleting one version's rows disturbed the other's")
        # the version row itself is deliberately not deleted by this function
        self.assertIsNotNone(self.conn.execute(
            "SELECT 1 FROM document_versions WHERE version_id=?",
            (self.old,)).fetchone())

        index = refs.build_index(self.conn)
        for ref in new_refs:
            self.assertIsNotNone(
                refs.resolve(index, ref),
                "a ref minted from the surviving version stopped resolving after "
                "the other version's rows were deleted")

    def test_zz_projection_rebuild_after_the_delete_drops_only_that_version(self):
        """Runs after the delete (alphabetical order) — the projection must follow."""
        if self._counts(self.old)["elements"] != 0:
            store.delete_version_rows(self.conn, self.old)
            self.conn.commit()
        store.build_retrieval_units(self.conn)
        versions = {r[0] for r in self.conn.execute(
            "SELECT DISTINCT version_id FROM retrieval_units")}
        self.assertEqual(versions, {self.new})


class TestTiedIngestTimestamps(_TwoVersionFixture):
    """When two versions share an `ingested_at`, the readers must not disagree.

    `store.CURRENT_EDITION_PREDICATE` breaks its ordering ties on purpose —
    "`now()` has one-second resolution and two editions written in the same
    second would otherwise tie". `retrieval.get_page` (`ORDER BY v.ingested_at
    DESC LIMIT 1`) and `facts._iter_candidates` (`ROW_NUMBER() OVER (... ORDER BY
    ingested_at DESC)`) have no such tie-break, so on a tie each picks whichever
    row SQLite hands it first.

    This asserts the property that actually matters — the two readers agree — and
    not *which* version wins, because nothing specifies that. A failure here is a
    real inconsistency; a pass does not prove the ordering is determinate. See
    the note filed with G9.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.conn.execute("UPDATE document_versions SET ingested_at='2026-01-01T00:00:00Z'")
        cls.conn.commit()

    def test_get_page_and_facts_choose_the_same_version(self):
        page = retrieval.get_page(self.doc_id, 1, conn=self.conn)
        facts.extract_facts(conn=self.conn)
        fact_versions = {r[0] for r in self.conn.execute(
            "SELECT DISTINCT version_id FROM facts")}
        self.assertEqual(len(fact_versions), 1,
                         "facts were asserted from more than one version")
        self.assertEqual(fact_versions, {page["version_id"]},
                         "get_page and the facts layer disagree about which of two "
                         "equally-timestamped versions is current")


class TestPerVersionEvidenceImages(_TwoVersionFixture):
    """A defect this fixture found. See the G9 entry in docs/state-and-gaps.md.

    `extract.derived_dir` is keyed on the *document*, not the version, so both
    byte-versions of one document render their page image to the identical path
    and the second ingest overwrites the first. Version 1's `pages.page_image_path`
    then names a picture of version 2, and its `assets.sha256` no longer matches
    the file it names. Nothing in the corpus can reach this today — it needs two
    byte-versions of one source path, which is exactly what G9 says the store has
    never held — so it is recorded here rather than fixed, because the fix moves
    every path in a 4.9 GB cache and every `pages.page_image_path` in the store.
    """

    @unittest.expectedFailure
    def test_each_version_has_its_own_page_image(self):
        paths = [r[0] for r in self.conn.execute(
            "SELECT page_image_path FROM pages ORDER BY version_id")]
        self.assertEqual(len(set(paths)), 2,
                         "both versions point at one page image: %s" % paths[0])

    def test_the_collision_is_at_least_visible_in_the_asset_rows(self):
        """Not a workaround — just a record of what a reader can currently detect."""
        rows = list(self.conn.execute(
            "SELECT version_id, path, sha256 FROM assets WHERE asset_type='page_image'"))
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({r["path"] for r in rows}), 1,
                         "if this now holds two paths the defect above was fixed; "
                         "delete this test and the expectedFailure above with it")
        self.assertEqual(len({r["version_id"] for r in rows}), 2)


if __name__ == "__main__":
    unittest.main()
