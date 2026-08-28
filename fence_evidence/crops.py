"""Render a rectangle of a source page, on demand, with poppler.

The normative transform of `docs/integration/source-refs-design.md` §4.1, which
`docs/curation/02-curation-schema.md` §2.11 worked out and verified against the
store. `GET /source-refs/{id}` is backed by this and nothing else.

Why poppler and not the Pillow crops already in `workspace/derived/`: Pillow is
optional and lives in the git-ignored `workspace/pylibs/`, and `extract.py`'s
`_crop_region` returns ``False`` when it is absent. An endpoint whose whole
promise is *"returns something a person can look at"* cannot be backed by a
dependency that may not be installed. The 7,484 pre-cut crops become a legacy
cache that is not served; the other 73,894 boxed elements were always going to
render on demand.

Four traps, each of which has bitten this repo or is one careless commit away:

1. **Never hardcode 200 dpi.** The distribution is ``{200: 2140, 72: 6, NULL: 1}``.
   The six 72-dpi pages are the Weatherables CAD PNGs, whose ``pages.width``
   is in *pixels*; the arithmetic survives only because ``72/72 == 1``. The NULL
   is the DOCX, which has no image and is refused rather than guessed.
2. **Top-left origin, no rotation transform.** ``pdftotext -bbox-layout`` reports
   ``yMin`` from the top, which is what ``pdftoppm -y`` expects. The usual PDF
   bottom-left flip would mirror every crop. For a page with a non-zero
   ``/Rotate``, ``pages.width/height`` are already the swapped display rectangle
   and poppler has already applied the rotation, so bbox, page rectangle and
   image share one space.
3. **Failure raises.** It does not return ``False`` and carry on.
4. **The rounding rule is part of the transform.** ``pages.width * dpi/72``
   matches ``assets.width_px`` to within one pixel across all 2,140 measured
   pages, so the transform fixes its own rule rather than assuming poppler's.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .paths import REPO_ROOT, ensure_writable

PAD_PX = 4
MIN_SIDE_PX = 4


class CropError(RuntimeError):
    """Raised when a rectangle of a page cannot be produced.

    Trap 3. A caller that gets a picture back knows it is the picture; a caller
    that gets an exception knows it has nothing. There is no third state.
    """


@dataclass(frozen=True)
class Window:
    """A pixel rectangle in page-image space, ready for ``pdftoppm -x -y -W -H``."""
    x0: int
    y0: int
    w: int
    h: int


def window_px(bbox, *, page_w_pt: float, page_h_pt: float, dpi: int | None) -> Window:
    """Convert a bbox in page units to the pixel window poppler will cut.

    ``bbox`` is ``(x0, y0, x1, y1)`` with y measured from the top — trap 2.
    """
    if dpi is None:
        raise CropError(
            "page has no page_image_dpi; it has no rendered image and its scale "
            "cannot be inferred. The DOCX is the known case — flag it, never guess.")
    if not page_w_pt or not page_h_pt:
        raise CropError("page rectangle is unknown; cannot clamp a window to it")

    scale = dpi / 72.0
    page_w_px = int(page_w_pt * scale)
    page_h_px = int(page_h_pt * scale)

    x0, y0, x1, y1 = (float(v) for v in bbox)
    if x1 < x0 or y1 < y0:
        raise CropError(f"bbox is inverted: {tuple(bbox)}")

    # The minimum applies to the box itself, before padding. Padding is
    # presentation: it must not rescue a degenerate bbox into looking valid,
    # because a zero-area box padded by 4 on each side is an 8px square of
    # whatever happened to be next to nothing.
    content_w = int(x1 * scale) - int(x0 * scale)
    content_h = int(y1 * scale) - int(y0 * scale)
    if content_w < MIN_SIDE_PX or content_h < MIN_SIDE_PX:
        raise CropError(
            f"bbox covers {content_w}x{content_h}px before padding, below the "
            f"{MIN_SIDE_PX}px minimum — there is nothing there for a person to "
            f"look at. bbox={tuple(bbox)} dpi={dpi}")

    left = max(0, int(x0 * scale) - PAD_PX)
    top = max(0, int(y0 * scale) - PAD_PX)
    right = min(page_w_px, int(x1 * scale) + PAD_PX)
    bottom = min(page_h_px, int(y1 * scale) + PAD_PX)
    return Window(left, top, right - left, bottom - top)


def render_crop(source_path: str | Path, page_no: int, bbox, *,
                page_w_pt: float, page_h_pt: float, dpi: int | None,
                out_path: Path | None = None) -> Path:
    """Cut one rectangle out of one page of a PDF. Returns the PNG's path.

    ``source_path`` is repo-relative, as ``documents.source_path`` stores it.
    With no ``out_path`` the crop lands in a temporary directory the caller owns
    and is responsible for removing — §4.3 treats every image as a regenerable
    cache, so nothing here writes into the store on its own.
    """
    src = Path(source_path)
    if not src.is_absolute():
        src = REPO_ROOT / src
    if not src.is_file():
        raise CropError(f"source document is not on disk: {source_path}. "
                        "An unfetched checkout is the usual cause — run `cli fetch`.")

    # A bbox of None means the whole page, not an error. `refs.ref_id` omits
    # `kind`, so a page ref is a first-class reference -- and for the 73
    # `table_not_reconstructed` pages the page image IS the evidence, which is
    # exactly what a reviewer has to be shown. Refusing it here left the
    # endpoint that serves evidence unable to serve the hardest cases.
    win = None if bbox is None else window_px(
        bbox, page_w_pt=page_w_pt, page_h_pt=page_h_pt, dpi=dpi)

    tmpdir = None
    if out_path is None:
        tmpdir = Path(tempfile.mkdtemp(prefix="crop-"))
        prefix = tmpdir / "crop"
    else:
        out_path = Path(out_path)
        ensure_writable(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        prefix = out_path.with_suffix("")

    cmd = ["pdftoppm", "-png", "-r", str(dpi),
           "-f", str(page_no), "-l", str(page_no)]
    if win is not None:
        cmd += ["-x", str(win.x0), "-y", str(win.y0),
                "-W", str(win.w), "-H", str(win.h)]
    cmd += [str(src), str(prefix)]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=120)
    except FileNotFoundError as exc:
        raise CropError("pdftoppm is not installed; poppler is a declared "
                        "dependency of this pipeline") from exc
    except subprocess.TimeoutExpired as exc:
        raise CropError(f"pdftoppm timed out on {source_path} page {page_no}") from exc

    if proc.returncode != 0:
        raise CropError(
            f"pdftoppm failed on {source_path} page {page_no} "
            f"(exit {proc.returncode}): {proc.stderr.decode('utf-8', 'replace').strip()}")

    # poppler appends its own page-number suffix, whose width varies with the
    # document's page count. Take whatever it actually wrote.
    produced = sorted(prefix.parent.glob(f"{prefix.name}*.png"))
    if not produced:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)
        raise CropError(f"pdftoppm wrote no image for {source_path} page {page_no}")

    got = produced[0]
    if out_path is not None and got != out_path:
        got.replace(out_path)
        return out_path
    return got
