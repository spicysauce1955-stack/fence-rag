"""A render-through cache for source crops. No HTTP, no store writes.

`crops.py` holds the normative transform and was built, measured and left
deliberately unwired. This is the wiring: it turns a `ref_id` into a PNG on
disk, exactly once per `(ref_id, dpi, tool_fingerprint)`, and hands back the
path and the hash of the bytes. Nothing here changes the transform.

Three things decided by measurement, not taste
----------------------------------------------

**Why a cache at all, given a 24.8 ms median.** `k3-crop-render-cost.md` §1
measures the distribution as *bimodal*: 13 of 400 crops exceed one second and
the worst is 7.5 s. A cache does nothing for the median and everything for the
3% -- and §4 measures that a review queue re-reads the same page over and over
(504 readings on 10 pages), so the hit rate on the only consumer that exists is
close to 1 after the first row.

**Why the element and not the page.** K3 §5 says *"cache the page, not the
element"* and the parent spec keys on `(ref_id, dpi, tool_fingerprint)`. Both
hold, for different consumers, and this module is the second one: the review
queue's unit already **is** the page and is materialised elsewhere, while
`GET /source-refs/{id}` is asked about a rectangle. Caching the page here would
mean cutting the rectangle out again on every request with the one library --
Pillow -- that `crops.py` §4.2 refuses to depend on.

**Why `tool_fingerprint` is in the key.** G38. A toolchain upgrade moves the
pixels, and a cache keyed on `ref_id` alone would keep serving the old ones
under an id whose evidence has quietly changed. The fingerprint is taken from
the extraction run that produced the *version this ref belongs to*, not from
the newest run in the store: re-extracting one document must not invalidate the
crops of the other 143.

**No pre-render pass.** K3 §5.2 measured it at ~5 hours single-threaded to
remove a cost the cache removes anyway. `ensure_crop` is the only way a crop
gets written.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import uuid
from pathlib import Path

from . import refs
from .crops import CropError, render_crop
from .paths import DERIVED_DIR, REPO_ROOT, ensure_writable

CROPS_DIR = DERIVED_DIR / "crops"

# `ref_id` and `fingerprint` are both truncated hex digests, and both reach
# this module from outside: the first straight off the wire from Planning, the
# second out of the store. They are interpolated into a *path*, so shape is not
# cosmetic -- an unvalidated `../../../etc/cron.d/x` would make `cache_path` a
# file-write primitive pointed anywhere. Validate, do not sanitise: a caller
# that sends a malformed id has not named any evidence, so the honest answer is
# the same one an unknown id gets.
_REF_ID_RE = re.compile(r"^[0-9a-f]{16}$")
_FINGERPRINT_RE = re.compile(r"^[0-9a-f]{6,64}$")

# 2400 dpi on a US Letter page is ~20,400 px on the long edge. Well past any
# legitimate request and far short of anything that would make poppler allocate
# for minutes; the bound exists so a hostile `dpi` cannot be a denial of
# service, not because any real caller approaches it.
MAX_DPI = 2400


class CropUnavailable(RuntimeError):
    """No picture can be produced for this ref, and no partial one will be.

    `crops.py` trap 3, one layer up: a caller either gets an image or gets an
    exception. Every failure funnels here -- an id that names nothing, a ref
    with no rectangle, a source file that is not on disk, poppler failing --
    because the caller's decision is the same in all four cases and the
    distinction it *does* care about (is this ref real?) it can make by
    resolving the ref itself.
    """


def cache_path(ref_id: str, dpi: int, fingerprint: str) -> Path:
    """Where this crop lives. Pure: no filesystem access, no store access.

    Sharded on the first two characters of the id. `ref_id` is the head of a
    sha256, so the first byte is uniform: 256 directories, and the 81,378
    boxed elements in this store would land ~318 to a directory instead of all
    of them in one. That is the difference between a directory an operator can
    list and one that takes a second to stat.
    """
    if not _REF_ID_RE.match(ref_id or ""):
        raise CropUnavailable(
            f"malformed ref_id {ref_id!r}: expected 16 lowercase hex "
            f"characters, as refs.ref_id mints them")
    if isinstance(dpi, bool) or not isinstance(dpi, int) or not 1 <= dpi <= MAX_DPI:
        raise CropUnavailable(f"dpi must be an integer in 1..{MAX_DPI}, got {dpi!r}")
    if not _FINGERPRINT_RE.match(fingerprint or ""):
        raise CropUnavailable(
            f"malformed tool fingerprint {fingerprint!r}: expected hex, as "
            f"store.tool_fingerprint mints it")
    return CROPS_DIR / ref_id[:2] / f"{ref_id}-{dpi}-{fingerprint}.png"


def relative_url(path: Path) -> str:
    """The path a `SourceRef` publishes: relative to `workspace/derived/`.

    `source-refs-design.md` §5 -- crops traverse Planning's backend, which
    mounts them wherever it likes. An absolute path or a host name published
    here would be a second deployment fact baked into an immutable snapshot.
    """
    return Path(path).resolve().relative_to(DERIVED_DIR.resolve()).as_posix()


def fingerprint_for(conn: sqlite3.Connection, version_sha256: str) -> str:
    """The `tool_fingerprint` of the run that extracted this version.

    Falls back to the newest run in the store when the version does not name
    one -- a store migrated from before `document_versions.extraction_run_id`
    was populated. Refuses rather than inventing a constant when there is no
    run at all: a placeholder would look like a fingerprint and would never
    change, which is precisely the G38 failure this key exists to prevent.
    """
    row = conn.execute(
        """SELECT r.tool_fingerprint
             FROM document_versions v
             JOIN extraction_runs r ON r.run_id = v.extraction_run_id
            WHERE v.sha256 = ? AND r.tool_fingerprint IS NOT NULL
            ORDER BY r.started_at DESC, r.run_id DESC LIMIT 1""",
        (version_sha256,)).fetchone()
    if row is None:
        row = conn.execute(
            """SELECT tool_fingerprint FROM extraction_runs
                WHERE tool_fingerprint IS NOT NULL
                ORDER BY started_at DESC, run_id DESC LIMIT 1""").fetchone()
    if row is None:
        raise CropUnavailable(
            "no extraction run is recorded in this store, so a crop cannot be "
            "keyed to the toolchain that produced it (G38). Run `cli ingest`.")
    return row["tool_fingerprint"]


def _render_source(conn: sqlite3.Connection, locus: refs.Locus):
    """The filing of this content hash we will cut the rectangle out of.

    A content hash can be filed under several document records -- 14 such
    groups here, one of them four deep -- and the bytes are identical by
    definition, so any filing renders the same picture. Prefer one whose file
    is actually on disk (a partial `cli fetch` can leave one copy and not the
    other), then fall back to the lexicographically first so the choice is
    deterministic and the error message names a real path.
    """
    rows = conn.execute(
        """SELECT d.document_id, d.source_path, d.file_type,
                  p.width, p.height, p.page_image_dpi
             FROM document_versions v
             JOIN documents d ON d.document_id = v.document_id
             LEFT JOIN pages p ON p.version_id = v.version_id AND p.page_no = ?
            WHERE v.sha256 = ?
            ORDER BY d.document_id""",
        (locus.page_no, locus.sha256)).fetchall()
    if not rows:
        raise CropUnavailable(
            f"ref names version {locus.sha256[:12]}, which no document row "
            f"claims; the store and the ref index disagree")
    for row in rows:
        if (REPO_ROOT / row["source_path"]).is_file():
            return row
    return rows[0]


def ensure_crop(conn: sqlite3.Connection, ref_id: str, *, dpi: int = 200,
                index: dict | None = None) -> dict:
    """Return the crop for `ref_id`, rendering it only if it is not cached.

    ``{"path": Path, "sha256": <of the PNG bytes>, "dpi": int, "cached": bool}``

    `index` is `refs.build_index`'s output. Pass it: the rebuild is ~220 ms and
    a batch that omits it pays that fifty times to answer one screen.

    `dpi` is the *requested* render resolution and reaches `render_crop`
    unchanged, which is safe here for one measured reason and not by luck: a
    bbox is in PDF points only where the page came from a PDF, and the six
    pages where it is in *pixels* are the CAD PNGs, which this function refuses
    outright a few lines below because poppler does not read PNGs. Do not
    "generalise" that refusal into a rescale -- `crops.py` trap 1 is exactly
    the scale factor that would silently move every one of those windows.
    """
    idx = refs.build_index(conn) if index is None else index
    locus = refs.resolve(idx, ref_id)
    if locus is None:
        raise CropUnavailable(
            f"no such ref_id: {ref_id}. Nothing in this store produces it, so "
            f"there is no rectangle to render.")
    if locus.bbox is None:
        # A whole-page ref. It is not an error in the store -- `ref_id` omits
        # `kind`, so a bbox-less element mints its page's id -- but there is no
        # rectangle, and cropping the whole page would answer a question
        # nobody asked with an image that is not the evidence.
        raise CropUnavailable(
            f"ref {ref_id} names a page, not a rectangle: it carries no bbox. "
            f"See refs.Locus -- the id omits `kind`.")
    try:
        bbox = json.loads(locus.bbox)
    except (json.JSONDecodeError, TypeError) as exc:
        raise CropUnavailable(f"ref {ref_id} carries an unreadable bbox: "
                              f"{locus.bbox!r}") from exc

    src = _render_source(conn, locus)
    if (src["file_type"] or "").lower() != "pdf":
        # The six CAD PNGs and the one DOCX. `crops.py` renders with poppler
        # precisely so that no optional dependency stands between a caller and
        # an image; the cost is that a source poppler cannot open has no crop
        # at all. Say so rather than half-answering.
        raise CropUnavailable(
            f"{src['source_path']} is a {src['file_type']!r}; pdftoppm renders "
            f"PDFs only, and crops.py §4.2 will not take a Pillow dependency "
            f"to cover the seven documents that are not one.")
    if src["page_image_dpi"] is None or not src["width"] or not src["height"]:
        # `crops.py` trap 1: a page with no recorded dpi has no rendered image
        # and its scale cannot be inferred. Refuse here, with the ref in the
        # message, rather than letting `window_px` refuse an argument the
        # caller never supplied.
        raise CropUnavailable(
            f"ref {ref_id} is on page {locus.page_no} of "
            f"{src['source_path']}, which has no recorded page rectangle or "
            f"dpi; its scale cannot be guessed.")

    path = cache_path(ref_id, dpi, fingerprint_for(conn, locus.sha256))
    if path.is_file() and path.stat().st_size > 0:
        return {"path": path, "sha256": _sha256_file(path), "dpi": dpi,
                "cached": True}

    ensure_writable(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Render beside the target under a unique name, hash, then rename. Two
    # workers asked for the same crop at once would otherwise both be writing
    # the bytes a third is reading -- and `render_crop` globs for whatever
    # poppler wrote, so a shared prefix would let one process collect the
    # other's file. `os.replace` is atomic within a directory; the loser of
    # the race overwrites identical bytes.
    tmp = path.with_name(f".{path.name}.{os.getpid()}-{uuid.uuid4().hex[:8]}.png")
    try:
        render_crop(src["source_path"], locus.page_no, bbox,
                    page_w_pt=src["width"], page_h_pt=src["height"],
                    dpi=dpi, out_path=tmp)
    except CropError as exc:
        tmp.unlink(missing_ok=True)
        raise CropUnavailable(f"{ref_id}: {exc}") from exc
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    digest = _sha256_file(tmp)
    os.replace(tmp, path)
    return {"path": path, "sha256": digest, "dpi": dpi, "cached": False}


def _sha256_file(path: Path) -> str:
    """Hash of the PNG *bytes*, which is what `crop_sha256` echoes elsewhere.

    D6 of the review-loop design makes this the one verifiable claim in a
    review: *this person looked at the image we hold*. It must therefore hash
    the file that was served, never the inputs that produced it.
    """
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()
