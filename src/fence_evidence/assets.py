"""Re-render a derived page image from its source PDF.

workspace/derived/ is a cache: every page image is a deterministic render of
one page of a source PDF, produced by the same `render_page` helper ingest
used (see tools.py). Re-rendering here must reproduce the same bytes ingest
wrote, so this module calls that exact function rather than re-invoking
pdftoppm with its own argument list.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .paths import EVIDENCE_DB, REPO_ROOT, ensure_writable
from .tools import ToolError, render_page


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
    pdf = REPO_ROOT / source_path
    if not pdf.is_file() or pdf.suffix.lower() != ".pdf":
        return None
    out = ensure_writable(REPO_ROOT / rel_path)
    stem = out.with_suffix("")
    try:
        img = render_page(pdf, page_no, stem, dpi=dpi or 200)
    except ToolError:
        return None
    return img if img.is_file() else None
