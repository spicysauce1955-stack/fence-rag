"""Re-render a derived page image from its source PDF or source image.

workspace/derived/ is a cache: every page image is a deterministic render of
one page of a source document. Two source kinds are handled:

- PDF sources: rendered with the same `tools.render_page` helper ingest used
  (see tools.py), so re-rendering here reproduces ingest's exact pdftoppm
  invocation rather than re-deriving its flags.
- Image sources (the CAD PNGs under manuals/*/structural/): ingest does not
  render these with pdftoppm at all — `extract.extract_image` (extract.py
  ~line 591) opens the source with Pillow, converts to RGB, and saves it as
  the page image. This module mirrors that exact operation for the same
  byte-identity reason.

Both renders go to a scratch directory beside the destination and are moved
into place with `os.replace`. Neither writer is atomic on its own — pdftoppm
truncates its output and streams into it, and `Image.save` does the same — so
writing directly to the cache path lets two concurrent processes rendering the
same page leave a truncated PNG behind. `paths.resolve_asset` then trusts that
file forever, because a cache hit is decided by `is_file()` and nothing ever
re-renders a path that exists. `resolve_asset` is reachable from `search`,
`facts`, `evaluate` and `noa_tables`, so concurrent CLI processes are ordinary,
not hypothetical.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

from .paths import EVIDENCE_DB, REPO_ROOT, ensure_writable
from .tools import ToolError, render_page

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}


def render_page_image(rel_path: str) -> "Path | None":
    """Render the page image identified by rel_path, or return None."""
    if not EVIDENCE_DB.is_file():
        return None
    conn = sqlite3.connect(f"file:{EVIDENCE_DB}?mode=ro", uri=True)
    try:
        row = conn.execute(
            """SELECT p.page_no, p.page_image_dpi, d.source_path
                 FROM pages p
                 JOIN document_versions v ON p.version_id = v.version_id
                 JOIN documents d ON v.document_id = d.document_id
                WHERE p.page_image_path = ?""", (rel_path,)).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    page_no, dpi, source_path = row
    source = REPO_ROOT / source_path
    if not source.is_file():
        return None
    suffix = source.suffix.lower()
    if suffix == ".pdf":
        return _render_from_pdf(source, page_no, dpi, rel_path)
    if suffix in IMAGE_SUFFIXES:
        return _render_from_image(source, rel_path)
    return None


def _scratch_dir(out: Path) -> Path:
    """A private directory beside `out`, so the move into place is a rename
    within one filesystem and the temporary name cannot collide."""
    out.parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(dir=out.parent, prefix=".tmp-render-"))


def _render_from_pdf(pdf: Path, page_no: int, dpi: int | None, rel_path: str) -> "Path | None":
    out = ensure_writable(REPO_ROOT / rel_path)
    tmp_dir = _scratch_dir(out)
    try:
        # pdftoppm -singlefile appends .png to the prefix it is given, so the
        # prefix is the destination name with its suffix stripped
        img = render_page(pdf, page_no, (tmp_dir / out.name).with_suffix(""),
                          dpi=dpi or 200)
        if not img.is_file():
            return None
        os.replace(img, out)
    except ToolError:
        return None
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    return out if out.is_file() else None


def _render_from_image(source: Path, rel_path: str) -> "Path | None":
    try:
        from PIL import Image
    except ImportError:
        return None
    out = ensure_writable(REPO_ROOT / rel_path)
    tmp_dir = _scratch_dir(out)
    try:
        tmp = tmp_dir / out.name          # same suffix, so PIL picks the same format
        with Image.open(source) as im:
            im.convert("RGB").save(tmp)
        os.replace(tmp, out)
    except Exception:
        return None
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    return out if out.is_file() else None
