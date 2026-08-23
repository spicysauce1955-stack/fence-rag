"""Task 3 input: locate and crop the scanned table regions that OCR could not rebuild.

This module does **not** read any values. It selects the pages the pipeline
already flagged `table_not_reconstructed`, finds the ruled region on each one,
and writes a crop plus a manifest row with a SHA-256. That is the preserved
source evidence the experiment in `docs/experiment-noa-table-reading.md` reads
from, and the artefact any promoted number must be checkable against.

Deduplication matters here: 73 flagged pages sit in 13 documents, but four of
those documents are byte-identical copies of one NOA. Work is done once per
distinct page content and attributed to the copies through `same_content_as`.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import defaultdict
from pathlib import Path

from .paths import CATALOG_DIR, DERIVED_DIR, open_write, rel, resolve_asset
from .store import connect

MANIFEST = CATALOG_DIR / "noa-table-candidates.jsonl"
# Ink-profile thresholds for finding a ruled region.
#
# The band this finds is recorded as a *hint*, never used to crop. Measured
# reason: on these pages a fence elevation drawing is a dense field of parallel
# picket lines, which reads as ruling to any ink-profile test. On page 17 of the
# Bufftech installation guide the detector locked onto the pickets and clipped
# the real "POST CENTERS" table off the bottom of the crop. Losing part of a
# table is a worse failure than handing the experiment a larger image, so the
# preserved crop is always the full page.
INK_ROW_SHARE = 0.35      # a ruling line covers this share of the page width
BAND_PAD_PX = 24


def candidate_pages(conn: sqlite3.Connection) -> list[dict]:
    """Flagged pages, one row per page, carrying the content hash of its document."""
    rows = conn.execute("""
        SELECT d.document_id, d.source_path, d.structural, q.page_no,
               v.sha256, p.page_image_path, p.width, p.height,
               p.ocr_mean_confidence
          FROM quality_issues q
          JOIN documents d ON d.document_id = q.document_id
          JOIN document_versions v ON v.document_id = d.document_id
          LEFT JOIN pages p ON p.version_id = v.version_id AND p.page_no = q.page_no
         WHERE q.kind = 'table_not_reconstructed'
         ORDER BY d.source_path, q.page_no""").fetchall()
    return [dict(r) for r in rows]


def distinct_work(pages: list[dict]) -> tuple[list[dict], dict[tuple[str, int], list[dict]]]:
    """Split into (one page per distinct content, duplicates keyed to it)."""
    groups: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for p in pages:
        groups[(p["sha256"], p["page_no"])].append(p)
    primaries = []
    for key, members in sorted(groups.items()):
        members.sort(key=lambda m: m["source_path"])
        primaries.append(members[0])
    return primaries, groups


def _find_ruled_band(image_path: Path) -> tuple[int, int, int, int] | None:
    """Bounding box of the ruled region, from horizontal ink runs. None if unclear."""
    try:
        from PIL import Image
    except Exception:
        return None
    try:
        with Image.open(image_path) as im:
            g = im.convert("L")
            w, h = g.size
            # downscale for speed; the band only needs to be located, not measured
            scale = max(1, w // 1200)
            if scale > 1:
                g = g.resize((w // scale, h // scale))
                w, h = g.size
            px = g.point(lambda v: 255 if v < 160 else 0).load()
            rows_with_rule = []
            for y in range(h):
                ink = sum(1 for x in range(0, w, 2) if px[x, y])
                if ink * 2 >= w * INK_ROW_SHARE:
                    rows_with_rule.append(y)
            if len(rows_with_rule) < 2:
                return None
            top, bottom = min(rows_with_rule), max(rows_with_rule)
            if bottom - top < h * 0.05:
                return None
            cols = []
            for x in range(w):
                ink = sum(1 for y in range(top, bottom, 2) if px[x, y])
                if ink * 2 >= (bottom - top) * 0.5:
                    cols.append(x)
            left, right = (min(cols), max(cols)) if len(cols) >= 2 else (0, w - 1)
            box = (max(0, left * scale - BAND_PAD_PX), max(0, top * scale - BAND_PAD_PX),
                   min(w * scale, (right + 1) * scale + BAND_PAD_PX),
                   min(h * scale, (bottom + 1) * scale + BAND_PAD_PX))
            if box[2] - box[0] < 80 or box[3] - box[1] < 40:
                return None
            return box
    except Exception:
        return None


def export_crops(conn: sqlite3.Connection | None = None) -> dict:
    """Write one crop per distinct flagged page, plus the manifest. Reads only."""
    own = conn is None
    conn = conn or connect()
    try:
        pages = candidate_pages(conn)
        primaries, groups = distinct_work(pages)
        written = 0
        no_band_hint = 0
        rows_out = []
        for p in primaries:
            if not p["page_image_path"]:
                continue
            src = resolve_asset(p["page_image_path"])
            if src is None:
                continue
            out = (DERIVED_DIR / p["document_id"] / "table-candidates"
                   / f"p{p['page_no']:04d}.png")
            box = _find_ruled_band(src)
            try:
                from PIL import Image
                with Image.open(src) as im:
                    out.parent.mkdir(parents=True, exist_ok=True)
                    im.copy().save(out)      # full page: never clip evidence
            except Exception as e:
                rows_out.append({"source_path": p["source_path"], "page_no": p["page_no"],
                                 "error": f"{e.__class__.__name__}: {e}"})
                continue
            if box is None:
                no_band_hint += 1
            written += 1
            data = out.read_bytes()
            duplicates = [m["source_path"] for m in groups[(p["sha256"], p["page_no"])]
                          if m["source_path"] != p["source_path"]]
            rows_out.append({
                "document_id": p["document_id"],
                "source_path": p["source_path"],
                "page_no": p["page_no"],
                "structural": bool(p["structural"]),
                "document_sha256": p["sha256"],
                "page_image_path": p["page_image_path"],
                "crop_path": rel(out),
                "crop_sha256": hashlib.sha256(data).hexdigest(),
                "crop_bytes": len(data),
                "crop_basis": "full page; never clipped",
                "candidate_band_px": list(box) if box else None,
                "candidate_band_basis": ("horizontal ink-run detection; a HINT only, known to "
                                         "lock onto picket line-work" if box else
                                         "no ruled band found"),
                "page_ocr_mean_confidence": p["ocr_mean_confidence"],
                "applies_also_to": duplicates,
            })
        with open_write(MANIFEST) as f:
            for r in rows_out:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        return {
            "flagged_pages": len(pages),
            "distinct_pages": len(primaries),
            "crops_written": written,
            "pages_without_a_band_hint": no_band_hint,
            "manifest": rel(MANIFEST),
        }
    finally:
        if own:
            conn.close()


if __name__ == "__main__":
    print(json.dumps(export_crops(), indent=2))
