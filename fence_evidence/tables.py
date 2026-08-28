"""Table and figure detection.

Two backends:

* ``pdfplumber`` — ruling lines and text alignment, giving a real cell grid.
* ``fallback``  — no structured backend available; the whitespace-column
  heuristic in :mod:`layout` still marks the region as ``table_text`` so the
  content is never lost, and a quality issue records the degraded fidelity.

Prohibition 4: a detected table is stored as cells *and* keeps a region image;
it is never reduced to flowed text alone.
"""
from __future__ import annotations

import json
from pathlib import Path

from .model import BBox, Cell, Table
from .tools import have_pdfplumber

TABLE_SETTINGS_LINES = {"vertical_strategy": "lines", "horizontal_strategy": "lines"}
TABLE_SETTINGS_TEXT = {"vertical_strategy": "text", "horizontal_strategy": "text",
                       "intersection_tolerance": 5, "min_words_vertical": 5,
                       "min_words_horizontal": 3}
MIN_CELLS = 4


def looks_tabular(grid: list[list[str | None]]) -> tuple[bool, str]:
    """Reject text-alignment "tables" that are really prose cut into columns.

    The failure mode to catch is a paragraph sliced mid-word ("For a" | "site lo"
    | "cation with"), which pdfplumber's text strategy produces on dense prose.
    """
    rows = [r for r in grid if any(c and str(c).strip() for c in r)]
    if len(rows) < 2:
        return False, "fewer than 2 non-empty rows"
    n_cols = max(len(r) for r in rows)
    if n_cols < 2:
        return False, "single column"
    texts = [str(c).strip() for r in rows for c in r if c and str(c).strip()]
    if not texts:
        return False, "no cell text"
    filled = len(texts) / (len(rows) * n_cols)
    if filled < 0.35:
        return False, f"only {filled:.0%} of the grid is filled"
    lengths = sorted(len(t) for t in texts)
    median_len = lengths[len(lengths) // 2]
    if median_len > 40:
        return False, f"median cell length {median_len} reads as prose"
    # mid-word splits: cell ends lowercase and the next cell starts lowercase
    splits = adjacent = 0
    for r in rows:
        cells = [str(c).strip() for c in r if c and str(c).strip()]
        for a, b in zip(cells, cells[1:]):
            adjacent += 1
            if a and b and a[-1].islower() and b[0].islower():
                splits += 1
    if adjacent and splits / adjacent > 0.25:
        return False, f"{splits}/{adjacent} adjacent cell pairs look mid-word split"
    return True, "ok"


def spans_from(table, tol: float = 1.0) -> dict[tuple[int, int], tuple[int, int]]:
    """`(row, col) -> (rowspan, colspan)`, read off the ruling lines.

    G41. `rowspan`/`colspan` were columns nothing ever wrote, so all 18,472 cells
    in the store claimed to be 1x1 and every merge was silently flattened. That
    is not a cosmetic loss: on the Bufftech footing table the merged fourth
    column is the applicability bracket, and flattened it attributes "NON HVHZ"
    to the 30" row alone, leaving the 24" row reading as unannotated. Five
    documents carry that table and all five extracted it the same wrong way.

    pdfplumber already knows. A merged cell's rect covers the row bands beneath
    it and the continuation rows report `None`, so the span is measured rather
    than guessed -- no inference from whitespace, no heuristic.

    The one subtlety is columns: a cell spanning the full width contributes its
    own wide band to the candidate set, which would count itself as a column and
    inflate every colspan. Only the narrowest bands -- those containing no other
    band -- are real columns.
    """
    rows = table.rows
    bands = [r.bbox for r in rows]
    tops, bots = [b[1] for b in bands], [b[3] for b in bands]
    seen = {(round(c[0], 2), round(c[2], 2))
            for r in rows for c in r.cells if c is not None}
    cols = sorted(b for b in seen
                  if not any(o != b and b[0] - tol <= o[0] and o[1] <= b[1] + tol
                             for o in seen))
    out: dict[tuple[int, int], tuple[int, int]] = {}
    for i, r in enumerate(rows):
        for j, c in enumerate(r.cells):
            if c is None:
                continue
            rs = sum(1 for k in range(len(rows))
                     if c[1] - tol <= tops[k] and bots[k] <= c[3] + tol)
            cs = sum(1 for (a, b) in cols if c[0] - tol <= a and b <= c[2] + tol)
            out[(i, j)] = (max(1, rs), max(1, cs))
    return out


def cell_bboxes_from(table) -> dict[tuple[int, int], BBox]:
    """`(row, col) -> (x0, top, x1, bottom)` in PDF points, off the same rects.

    C3. `planning-asks.md` §1 calls this "the one above everything else": without
    it a reviewer is told *which table* a reading came from and has to find the
    cell before judging it, which is what makes a review queue unbounded. The
    OCR word-grid path has always set `Cell.bbox`; the pdfplumber path never did,
    so 17,499 of 18,472 stored cells carry none.

    Nothing has to be inferred. :func:`spans_from` already walks
    `table.rows[i].cells[j]`, and that rect *is* the cell box -- for a merged
    cell it is the whole merged region, which is the region a reviewer should be
    shown. Continuation cells report `None` and simply have no box, exactly as
    they have no text.

    Rounded to 2dp to match the OCR path in :func:`detect_ocr_tables` and the
    table bbox in :func:`detect_page_tables_and_figures`; two sources that
    disagreed on rounding would be worse than one source missing.
    """
    out: dict[tuple[int, int], BBox] = {}
    for i, r in enumerate(table.rows):
        for j, c in enumerate(r.cells):
            if c is None:
                continue
            try:
                out[(i, j)] = tuple(round(float(v), 2) for v in c)  # x0, top, x1, bottom
            except (TypeError, ValueError):  # geometry we cannot read is not a box
                continue
    return out


def _grid_to_cells(grid: list[list[str | None]], bbox: BBox,
                   spans: dict[tuple[int, int], tuple[int, int]] | None = None,
                   bboxes: dict[tuple[int, int], BBox] | None = None) -> list[Cell]:
    cells: list[Cell] = []
    spans = spans or {}
    bboxes = bboxes or {}
    for r, row in enumerate(grid):
        for c, val in enumerate(row):
            if val is None:
                continue
            text = " ".join(str(val).split())
            if not text:
                continue
            rs, cs = spans.get((r, c), (1, 1))
            cells.append(Cell(row=r, col=c, text=text, rowspan=rs, colspan=cs,
                              bbox=bboxes.get((r, c))))
    return cells


class TableBackend:
    """Document-scoped table/figure detector.

    Opening the PDF once per document rather than once per page matters: the
    corpus has 2140 pages and pdfplumber's open cost is per-document.
    """

    def __init__(self, pdf: Path):
        self.pdf = Path(pdf)
        self._doc = None
        self.name = "fallback-whitespace"
        self.open_error: str | None = None
        if have_pdfplumber():
            try:
                import pdfplumber
                self._doc = pdfplumber.open(str(self.pdf))
                self.name = "pdfplumber"
            except Exception as e:
                self.open_error = f"{e.__class__.__name__}: {e}"
                self.name = "pdfplumber-open-failed"

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def close(self):
        if self._doc is not None:
            try:
                self._doc.close()
            except Exception:
                pass
            self._doc = None

    def page(self, page_no: int):
        """Return ``(tables, figure_bboxes, backend, notes)`` for one page."""
        return detect_page_tables_and_figures(self.pdf, page_no, _doc=self._doc,
                                              backend_name=self.name,
                                              open_error=self.open_error)


def detect_page_tables_and_figures(pdf: Path, page_no: int, *, _doc=None,
                                   backend_name: str | None = None,
                                   open_error: str | None = None):
    """Return ``(tables, figure_bboxes, backend, notes)`` for one page."""
    notes: list[str] = []
    if open_error:
        return [], [], "pdfplumber-open-failed", [f"could not open document: {open_error}"]
    if not have_pdfplumber():
        return [], [], "fallback-whitespace", ["no structured table backend available"]
    import contextlib
    import pdfplumber
    tables: list[Table] = []
    figures: list[BBox] = []
    try:
        with contextlib.nullcontext(_doc) if _doc is not None else pdfplumber.open(str(pdf)) as doc:
            if page_no > len(doc.pages):
                return [], [], "pdfplumber", ["page out of range"]
            page = doc.pages[page_no - 1]
            found = []
            for settings, label in ((TABLE_SETTINGS_LINES, "lines"),
                                    (TABLE_SETTINGS_TEXT, "text-alignment")):
                try:
                    found = page.find_tables(table_settings=settings)
                except Exception as e:  # malformed page geometry
                    notes.append(f"{label} strategy failed: {e.__class__.__name__}")
                    found = []
                if found:
                    break
            for t in found:
                try:
                    grid = t.extract()
                except Exception as e:
                    notes.append(f"table extract failed: {e.__class__.__name__}")
                    continue
                if not grid:
                    continue
                ok, why = looks_tabular(grid)
                if not ok:
                    notes.append(f"rejected {label} candidate: {why}")
                    continue
                bbox = tuple(round(float(v), 2) for v in t.bbox)  # x0, top, x1, bottom
                try:
                    spans = spans_from(t)
                    boxes = cell_bboxes_from(t)
                except Exception as e:   # geometry we cannot read is not a merge
                    notes.append(f"span read failed: {e.__class__.__name__}")
                    spans, boxes = {}, {}
                cells = _grid_to_cells(grid, bbox, spans, boxes)
                if len(cells) < MIN_CELLS:
                    continue
                tables.append(Table(n_rows=len(grid),
                                    n_cols=max(len(r) for r in grid),
                                    cells=cells, bbox=bbox,
                                    detector=f"pdfplumber:{label}"))
            figures.extend(detect_vector_figures(page))
            for im in page.images:
                try:
                    figures.append((round(float(im["x0"]), 2), round(float(im["top"]), 2),
                                    round(float(im["x1"]), 2), round(float(im["bottom"]), 2)))
                except Exception:
                    continue
    except Exception as e:
        notes.append(f"pdfplumber failed on page: {e.__class__.__name__}: {e}")
        return [], [], "pdfplumber-failed", notes
    return tables, figures, "pdfplumber", notes


# --------------------------------------------------------------------------
# Vector figures
#
# Many install guides draw their illustrations as vector paths, so
# ``page.images`` is empty even though the page is mostly diagram.  Rasterising
# the drawing objects onto a coarse grid and taking connected components finds
# those regions in linear time, which matters at 2140 pages.
CELL_PT = 6.0
MIN_FIGURE_PT = 45.0
MAX_FIGURE_AREA_FRAC = 0.75
MIN_FIGURE_CELLS = 12


def detect_vector_figures(page) -> list[BBox]:
    objs = []
    for kind in ("curves", "rects", "lines"):
        objs.extend(getattr(page, kind, []) or [])
    if not objs:
        return []
    W, H = float(page.width), float(page.height)
    nx, ny = max(1, int(W / CELL_PT) + 1), max(1, int(H / CELL_PT) + 1)
    grid = bytearray(nx * ny)

    def mark(x0, y0, x1, y1, value=1):
        cx0, cx1 = max(0, int(x0 / CELL_PT)), min(nx - 1, int(x1 / CELL_PT))
        cy0, cy1 = max(0, int(y0 / CELL_PT)), min(ny - 1, int(y1 / CELL_PT))
        for cy in range(cy0, cy1 + 1):
            base = cy * nx
            for cx in range(cx0, cx1 + 1):
                grid[base + cx] = value

    for o in objs:
        try:
            x0, y0, x1, y1 = float(o["x0"]), float(o["top"]), float(o["x1"]), float(o["bottom"])
        except (KeyError, TypeError, ValueError):
            continue
        if x1 - x0 > W * 0.98 and y1 - y0 > H * 0.98:
            continue  # page border / background box
        mark(x0, y0, x1, y1)
    # text suppresses drawing cells so paragraphs framed by rules are not figures
    for w in (getattr(page, "chars", []) or []):
        try:
            mark(float(w["x0"]), float(w["top"]), float(w["x1"]), float(w["bottom"]), 0)
        except (KeyError, TypeError, ValueError):
            continue

    seen = bytearray(nx * ny)
    out: list[BBox] = []
    for start in range(nx * ny):
        if not grid[start] or seen[start]:
            continue
        stack = [start]
        seen[start] = 1
        cells = []
        while stack:
            idx = stack.pop()
            cells.append(idx)
            cy, cx = divmod(idx, nx)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny_, nx_ = cy + dy, cx + dx
                    if 0 <= ny_ < ny and 0 <= nx_ < nx:
                        j = ny_ * nx + nx_
                        if grid[j] and not seen[j]:
                            seen[j] = 1
                            stack.append(j)
        if len(cells) < MIN_FIGURE_CELLS:
            continue
        xs = [c % nx for c in cells]
        ys = [c // nx for c in cells]
        bx0, bx1 = min(xs) * CELL_PT, (max(xs) + 1) * CELL_PT
        by0, by1 = min(ys) * CELL_PT, (max(ys) + 1) * CELL_PT
        if (bx1 - bx0) < MIN_FIGURE_PT or (by1 - by0) < MIN_FIGURE_PT:
            continue
        if ((bx1 - bx0) * (by1 - by0)) / max(1.0, W * H) > MAX_FIGURE_AREA_FRAC:
            continue
        out.append((round(bx0, 2), round(by0, 2), round(min(bx1, W), 2), round(min(by1, H), 2)))
    return out


# --------------------------------------------------------------------------
# OCR table reconstruction
#
# pdfplumber needs a text layer, so a scanned wind-load table produces no
# cells at all.  That is exactly the material this corpus exists for, so tables
# on OCR'd pages are rebuilt from hOCR word geometry: words cluster into rows,
# recurring x-positions across rows become columns.
OCR_MIN_ROWS = 3
OCR_MIN_COLS = 3
OCR_MIN_DIGIT_CELL_SHARE = 0.30
OCR_MIN_WORD_CONFIDENCE = 60.0
OCR_MIN_TABLE_CONFIDENCE = 72.0
OCR_MAX_STUB_CELL_SHARE = 0.25
OCR_COL_TOLERANCE = 14.0     # points; column centres within this are the same column
OCR_ROW_TOLERANCE = 8.0      # points; words within this vertical distance share a row


def _cluster_rows(words, tol: float = OCR_ROW_TOLERANCE):
    rows: list[list] = []
    for w in sorted(words, key=lambda w: ((w.bbox[1] + w.bbox[3]) / 2, w.bbox[0])):
        centre = (w.bbox[1] + w.bbox[3]) / 2
        if rows and abs(centre - rows[-1][1]) <= tol:
            rows[-1][0].append(w)
        else:
            rows.append([[w], centre])
    return [sorted(r[0], key=lambda w: w.bbox[0]) for r in rows]


def detect_ocr_tables(words, page_width: float, page_height: float) -> list[Table]:
    """Reconstruct table cells from OCR word boxes.

    Deliberately conservative: it only emits a table when several rows share
    the same column positions, so prose does not become a grid.
    """
    if len(words) < 8:
        return []
    # Low-confidence OCR on drawing sheets clusters into a plausible-looking
    # grid made of noise. Only reasonably-read words may form a table.
    words = [w for w in words
             if w.confidence is None or w.confidence >= OCR_MIN_WORD_CONFIDENCE]
    if len(words) < 8:
        return []
    rows = _cluster_rows(words)
    if len(rows) < OCR_MIN_ROWS:
        return []

    # candidate column starts: left edges that recur across rows
    edges: dict[int, int] = {}
    for row in rows:
        seen_in_row = set()
        for w in row:
            key = int(round(w.bbox[0] / OCR_COL_TOLERANCE))
            if key not in seen_in_row:
                edges[key] = edges.get(key, 0) + 1
                seen_in_row.add(key)
    recurring = sorted(k for k, n in edges.items() if n >= max(3, len(rows) // 3))
    if len(recurring) < OCR_MIN_COLS:
        return []
    col_x = [k * OCR_COL_TOLERANCE for k in recurring]

    # keep only rows that actually populate at least two columns
    grid_rows: list[list] = []
    for row in rows:
        assigned: dict[int, list] = {}
        for w in row:
            ci = min(range(len(col_x)), key=lambda i: abs(w.bbox[0] - col_x[i]))
            if abs(w.bbox[0] - col_x[ci]) > OCR_COL_TOLERANCE * 3:
                continue
            assigned.setdefault(ci, []).append(w)
        if len(assigned) >= OCR_MIN_COLS:
            grid_rows.append(assigned)
    if len(grid_rows) < OCR_MIN_ROWS:
        return []

    cells: list[Cell] = []
    for r, assigned in enumerate(grid_rows):
        for ci, ws in sorted(assigned.items()):
            text = " ".join(w.text for w in sorted(ws, key=lambda w: w.bbox[0]))
            if not text.strip():
                continue
            cells.append(Cell(row=r, col=ci, text=text,
                              bbox=(round(min(w.bbox[0] for w in ws), 2),
                                    round(min(w.bbox[1] for w in ws), 2),
                                    round(max(w.bbox[2] for w in ws), 2),
                                    round(max(w.bbox[3] for w in ws), 2))))
    if len(cells) < MIN_CELLS:
        return []
    grid = [[None] * len(col_x) for _ in range(len(grid_rows))]
    for c in cells:
        grid[c.row][c.col] = c.text
    ok, _why = looks_tabular(grid)
    if not ok:
        return []
    # Prose on a scanned page clusters into short cells just as a table does.
    # The tables this corpus cares about are numeric (spans, depths, speeds),
    # so require real numeric content before calling a region a table.
    digit_cells = sum(1 for c in cells if any(ch.isdigit() for ch in c.text))
    if digit_cells / len(cells) < OCR_MIN_DIGIT_CELL_SHARE:
        return []
    # single-character cells are the signature of OCR noise, not of a table
    stubs = sum(1 for c in cells if len(c.text.strip()) < 2)
    if stubs / len(cells) > OCR_MAX_STUB_CELL_SHARE:
        return []
    confs = [w.confidence for w in words if w.confidence is not None]
    if confs and (sum(confs) / len(confs)) < OCR_MIN_TABLE_CONFIDENCE:
        return []
    boxes = [c.bbox for c in cells if c.bbox]
    bbox = (round(min(b[0] for b in boxes), 2), round(min(b[1] for b in boxes), 2),
            round(max(b[2] for b in boxes), 2), round(max(b[3] for b in boxes), 2))
    return [Table(n_rows=len(grid_rows), n_cols=len(col_x), cells=cells, bbox=bbox,
                  detector="ocr-word-grid")]


def backfill_spans(conn, *, dry_run: bool = True) -> dict:
    """Populate `rowspan`/`colspan` on cells already in the store.

    G41's fix lands in extraction, but the store holds 18,472 cells extracted
    before it existed and a re-ingest is not an option: re-extraction moves
    bboxes, `ref_id` is `sha256(content_hash:page:bbox)`, and
    `delete_version_rows()` removes the rows the old ids named. That is G38, and
    it would break published citations to fix a display defect.

    So this updates two integer columns and touches nothing else. No bbox is
    rewritten, no element or table id changes, and `cli refs --verify` is
    unaffected by construction. Tables are matched back to the page by their
    stored bbox; a table whose geometry no longer matches is skipped and
    counted rather than guessed at.
    """
    from .paths import REPO_ROOT
    rows = conn.execute("""
        SELECT t.table_id, t.bbox, t.detector, e.page_no, d.source_path
          FROM tables t
          JOIN elements e   ON e.element_id = t.element_id
          JOIN documents d  ON d.document_id = e.document_id
         WHERE t.detector LIKE 'pdfplumber:%'
         ORDER BY d.source_path, e.page_no""").fetchall()
    out = {"tables_considered": len(rows), "tables_matched": 0,
           "tables_unmatched": 0, "cells_updated": 0, "merges_found": 0,
           "pdf_open_failures": 0, "dry_run": dry_run}
    if not rows:
        return out
    import pdfplumber
    by_pdf: dict[str, list] = {}
    for r in rows:
        by_pdf.setdefault(r["source_path"], []).append(r)
    for src, group in by_pdf.items():
        path = REPO_ROOT / src
        if not path.exists():
            out["pdf_open_failures"] += 1
            continue
        try:
            pdf = pdfplumber.open(str(path))
        except Exception:
            out["pdf_open_failures"] += 1
            continue
        with pdf:
            for r in group:
                try:
                    page = pdf.pages[r["page_no"] - 1]
                    want = [round(float(v), 2) for v in json.loads(r["bbox"])]
                    match = next((t for t in page.find_tables()
                                  if [round(float(v), 2) for v in t.bbox] == want), None)
                except Exception:
                    match = None
                if match is None:
                    out["tables_unmatched"] += 1
                    continue
                out["tables_matched"] += 1
                for (i, j), (rs, cs) in spans_from(match).items():
                    if rs == 1 and cs == 1:
                        continue
                    out["merges_found"] += 1
                    if dry_run:
                        continue
                    cur = conn.execute(
                        "UPDATE table_cells SET rowspan=?, colspan=? "
                        " WHERE table_id=? AND row=? AND col=?",
                        (rs, cs, r["table_id"], i, j))
                    out["cells_updated"] += cur.rowcount
    if not dry_run:
        conn.commit()
    return out


def backfill_cell_bboxes(conn, *, dry_run: bool = True) -> dict:
    """Populate `bbox` on pdfplumber cells already in the store.

    Same shape, and the same safety argument, as :func:`backfill_spans`: C3's
    fix lands in extraction, but the store holds 17,499 pdfplumber cells
    extracted before `cell_bboxes_from` existed and re-ingesting them is not an
    option. Re-extraction moves element bboxes, `ref_id` is
    `sha256(content_hash:page:bbox)`, and `delete_version_rows()` removes the
    rows the old ids named -- G38 -- so a re-ingest would retract published
    citations to fill in a column.

    So this writes `table_cells.bbox` and nothing else. No element bbox, no
    table bbox, no id of any kind, and therefore `cli refs --verify` cannot be
    affected. It fills only cells whose bbox is NULL, which makes it re-runnable
    and means it can never overwrite a box that extraction itself produced (the
    973 OCR-word-grid cells are outside the query entirely).

    Two guards against writing a box onto the wrong cell:

    * the stored table is re-found by its own bbox, under the *same* detector
      settings it was found with -- `pdfplumber:text-alignment` tables do not
      exist under the lines strategy at all, so matching them with the default
      settings would silently skip 1,199 cells;
    * the re-found grid must have the stored `n_rows`/`n_cols`. Row and column
      indices are the only thing joining a stored cell to a rect, so a table
      whose shape has drifted is counted and skipped, not guessed at.
    """
    from .paths import REPO_ROOT
    rows = conn.execute("""
        SELECT t.table_id, t.bbox, t.detector, t.n_rows, t.n_cols,
               e.page_no, d.source_path
          FROM tables t
          JOIN elements e   ON e.element_id = t.element_id
          JOIN documents d  ON d.document_id = e.document_id
         WHERE t.detector LIKE 'pdfplumber:%'
         ORDER BY d.source_path, e.page_no""").fetchall()
    out = {"tables_considered": len(rows), "tables_matched": 0,
           "tables_unmatched": 0, "tables_shape_mismatch": 0,
           "boxes_found": 0, "cells_updated": 0,
           "pdf_open_failures": 0, "dry_run": dry_run}
    if not rows:
        return out
    if not have_pdfplumber():
        # The rects are pdfplumber's; without it there is nothing to read them
        # from. Degrade to a no-op rather than failing the command.
        out["error"] = "pdfplumber not available"
        return out
    import pdfplumber
    settings_for = {"pdfplumber:lines": TABLE_SETTINGS_LINES,
                    "pdfplumber:text-alignment": TABLE_SETTINGS_TEXT}
    by_pdf: dict[str, list] = {}
    for r in rows:
        by_pdf.setdefault(r["source_path"], []).append(r)
    for src, group in by_pdf.items():
        path = REPO_ROOT / src
        if not path.exists():
            out["pdf_open_failures"] += 1
            continue
        try:
            pdf = pdfplumber.open(str(path))
        except Exception:
            out["pdf_open_failures"] += 1
            continue
        with pdf:
            # find_tables() is the expensive call and several stored tables can
            # share one page and detector, so memoise per (page, detector).
            found: dict[tuple[int, str], list] = {}
            for r in group:
                key = (r["page_no"], r["detector"])
                try:
                    if key not in found:
                        page = pdf.pages[r["page_no"] - 1]
                        found[key] = page.find_tables(
                            table_settings=settings_for.get(r["detector"],
                                                            TABLE_SETTINGS_LINES))
                    want = [round(float(v), 2) for v in json.loads(r["bbox"] or "null")]
                    match = next((t for t in found[key]
                                  if [round(float(v), 2) for v in t.bbox] == want), None)
                except Exception:
                    match = None
                if match is None:
                    out["tables_unmatched"] += 1
                    continue
                try:
                    boxes = cell_bboxes_from(match)
                    shape = (len(match.rows),
                             max((len(x.cells) for x in match.rows), default=0))
                except Exception:
                    out["tables_unmatched"] += 1
                    continue
                if shape != (r["n_rows"], r["n_cols"]):
                    out["tables_shape_mismatch"] += 1
                    continue
                out["tables_matched"] += 1
                out["boxes_found"] += len(boxes)
                for (i, j), box in boxes.items():
                    if dry_run:
                        # Counted with the same predicate the UPDATE uses, so a
                        # dry run reports the number of cells it would fill.
                        out["cells_updated"] += conn.execute(
                            "SELECT COUNT(*) FROM table_cells"
                            " WHERE table_id=? AND row=? AND col=? AND bbox IS NULL",
                            (r["table_id"], i, j)).fetchone()[0]
                        continue
                    cur = conn.execute(
                        "UPDATE table_cells SET bbox=?"
                        " WHERE table_id=? AND row=? AND col=? AND bbox IS NULL",
                        (json.dumps(list(box)), r["table_id"], i, j))
                    out["cells_updated"] += cur.rowcount
    if not dry_run:
        conn.commit()
    return out
