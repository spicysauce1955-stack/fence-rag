"""Collect orphaned images out of `workspace/derived/`. G11, last bullet.

`workspace/derived/` is a *cache* -- `paths.resolve_asset` re-renders a page
image it cannot find, and `cropcache.ensure_crop` re-renders a crop -- but
nothing has ever removed a file from it. Ingestion is additive: a re-extraction
that moves a bounding box writes `p0007-0005-figure.png` beside the one it
superseded, `store.delete_version_rows` drops the row that named the old file
and the bytes stay on disk forever. 4.4 GB per full run, and no way to tell
which of it is still evidence.

This module answers exactly one question -- *is there a live claim on this
file?* -- and deletes only where the answer is no. Three decisions shape it,
and all three are deliberately conservative.

**Scope is a whitelist, not a blacklist.** Only four subtrees are collectable:
``<doc_id>/pages``, ``<doc_id>/regions``, ``<doc_id>/table-candidates`` and
``crops/``. Those are the four things this pipeline writes and can re-derive.
Everything else under `derived/` -- today a `visualization-tools/` checkout
with a `node_modules/` in it, and a loose `noa-engine-readings.jsonl` -- is
reported as *unmanaged* and never touched. A collector that deleted "anything
unreferenced" would have eaten both on its first run.

**A published citation is a root, and an unreadable snapshot stops the run.**
A snapshot is immutable, so a citation that stops resolving can never be
repaired -- CLAUDE.md and `refs.verify_snapshots` both call that an
obligation-3 violation. Crops are keyed on ``(ref_id, dpi, tool_fingerprint)``
while a citation carries only the ``ref_id``, so *every* dpi and fingerprint of
a cited ref is retained. And if a snapshot file will not parse, we cannot know
what it cites: the run reports `unsafe` and deletes nothing at all, rather than
collecting against a partial root set.

**Reachability is read from four columns, one digest set, and the text of the
workspace's own records.** The columns are `pages.page_image_path`,
`elements.region_image_path`, `assets.path` and
`table_read_candidates.crop_path`. The digest set is `table_reviews.crop_sha256`
(plus `table_read_candidates.crop_sha256`), which names *bytes* and no path:
D6 of the review-loop design makes "this person looked at this image" the one
verifiable claim in a review, so a file whose hash a review recorded is
retained even though nothing points at its name. The text scan covers
`workspace/catalog/`, `workspace/reports/` and `workspace/snapshots/`, because
`noa-table-candidates.jsonl` and `unresolved-worklist.jsonl` both cite derived
paths that no table column holds.

Dry run by default, as `promote-tables --revoke` and `backfill-spans` are.
Deletion goes through `paths.ensure_writable`, so a `derived_dir` outside the
workspace is refused before a single file is listed.
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
from pathlib import Path

from .paths import (CATALOG_DIR, DERIVED_DIR, REPO_ROOT, REPORTS_DIR,
                    CorpusWriteError, ensure_writable, rel)

# The four subtrees this pipeline writes and can re-derive. `extract.py` writes
# the first two (`ddir / "pages"`, `ddir / "regions"`), `noa_tables.export_crops`
# the third, `cropcache.cache_path` the fourth.
MANAGED_DOC_SUBDIRS = ("pages", "regions", "table-candidates")
CROPS_SUBDIR = "crops"

# `cropcache.cache_path` names files `<ref_id>-<dpi>-<fingerprint>.png`, and
# `refs.ref_id` mints a 16-character lowercase hex id.
_CROP_NAME_RE = re.compile(r"^([0-9a-f]{16})-")

# A text root larger than this is not a record of derived paths; skip it rather
# than pull it into memory.
_MAX_TEXT_BYTES = 64 * 1024 * 1024

ROOT_KEYS = (
    "pages.page_image_path",
    "elements.region_image_path",
    "assets.path",
    "table_read_candidates.crop_path",
    "review_crop_sha256",
    "published_snapshot_cites",
    "text_reference",
)

_PATH_COLUMNS = (
    ("pages.page_image_path", "SELECT page_image_path AS p FROM pages"),
    ("elements.region_image_path", "SELECT region_image_path AS p FROM elements"),
    ("assets.path", "SELECT path AS p FROM assets"),
    ("table_read_candidates.crop_path",
     "SELECT crop_path AS p FROM table_read_candidates"),
)

_DIGEST_COLUMNS = (
    "SELECT crop_sha256 AS d FROM table_reviews",
    "SELECT crop_sha256 AS d FROM table_read_candidates",
)


# --------------------------------------------------------------------- roots
def _rows(conn: sqlite3.Connection, sql: str, key: str) -> list:
    """Query, tolerating a store older than the column being asked for.

    A migration-lagging store must make the collector *refuse*, never make it
    see fewer roots than exist -- so the caller records the failure and the
    run is marked unsafe.
    """
    try:
        return [r[key] for r in conn.execute(sql) if r[key]]
    except sqlite3.Error as exc:
        raise _MissingRoot(f"{sql}: {exc}") from exc


class _MissingRoot(RuntimeError):
    """A root set could not be read, so reachability is unknown."""


def referenced_paths(conn: sqlite3.Connection) -> tuple[dict, list]:
    """``({resolved Path: {root key, ...}}, [unreadable root, ...])``."""
    out: dict[Path, set] = {}
    problems: list[str] = []
    for key, sql in _PATH_COLUMNS:
        try:
            values = _rows(conn, sql, "p")
        except _MissingRoot as exc:
            problems.append(str(exc))
            continue
        for value in values:
            out.setdefault(_resolve(value), set()).add(key)
    return out, problems


def referenced_digests(conn: sqlite3.Connection) -> tuple[set, list]:
    """Crop digests a review (or a reading) recorded, which name no path."""
    out: set[str] = set()
    problems: list[str] = []
    for sql in _DIGEST_COLUMNS:
        try:
            out.update(v.lower() for v in _rows(conn, sql, "d")
                       if isinstance(v, str))
        except _MissingRoot as exc:
            problems.append(str(exc))
    return out, problems


def _resolve(value: str) -> Path:
    """A stored path -- always repo-relative -- as an absolute path."""
    p = Path(value)
    return (p if p.is_absolute() else REPO_ROOT / p).resolve()


def published_cites(snapshot_dir: Path) -> tuple[set, list]:
    """Every ``ref_id`` cited by a published (non-tombstoned) snapshot.

    The citation gate mirrors `refs.verify_snapshots` exactly: a dict is a
    citation when it carries an ``id`` AND EITHER a ``belongs_to`` OR a place
    inside a list bound to ``cites``. A bare ``id`` is not enough -- `Gap` has
    one and there are 63 gaps in the shipped snapshot.

    Returns ``(ref_ids, unreadable)``. A non-empty ``unreadable`` makes the
    whole run unsafe: a snapshot we cannot read may cite anything.
    """
    refs: set[str] = set()
    unreadable: list[dict] = []
    base = Path(snapshot_dir)
    if not base.is_dir():
        return refs, unreadable

    def walk(node, in_cites=False):
        if isinstance(node, dict):
            if "id" in node and ("belongs_to" in node or in_cites):
                rid = node.get("id")
                if isinstance(rid, str):
                    refs.add(rid)
            for k, v in node.items():
                walk(v, in_cites=(k == "cites"))
        elif isinstance(node, list):
            for v in node:
                walk(v, in_cites=in_cites)

    import json
    for path in sorted(base.glob("*.json")):
        try:
            payload = json.loads(path.read_bytes())
            if not isinstance(payload, dict):
                raise TypeError(f"top level is {type(payload).__name__}, not an object")
        except Exception as exc:                      # noqa: BLE001 -- reported, not raised
            unreadable.append({"file": rel(path),
                               "error": f"{exc.__class__.__name__}: {exc}"})
            continue
        # A tombstone has no payload by design; it cites nothing.
        if payload.get("tombstoned"):
            continue
        walk(payload)
    return refs, unreadable


def text_references(derived_dir: Path, text_roots) -> set:
    """Derived paths named in the workspace's own JSONL/JSON/Markdown records.

    `workspace/catalog/noa-table-candidates.jsonl` (88 paths) and
    `unresolved-worklist.jsonl` (129) both name crops that no table column
    holds. Those files are the provenance of the runs that produced the
    images; collecting an image one of them cites would orphan the record.
    """
    found: set[Path] = set()
    try:
        derived_rel = os.path.relpath(Path(derived_dir).resolve(), REPO_ROOT)
    except ValueError:                                # pragma: no cover -- other volume
        derived_rel = None
    tail = r"/[A-Za-z0-9._+/-]+"
    patterns = [re.compile(re.escape(str(Path(derived_dir).resolve())) + tail)]
    if derived_rel and not derived_rel.startswith(".."):
        patterns.append(re.compile(re.escape(derived_rel) + tail))

    for root in text_roots or ():
        root = Path(root)
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_symlink() or not path.is_file():
                continue
            try:
                if path.stat().st_size > _MAX_TEXT_BYTES:
                    continue
                text = path.read_bytes().decode("utf-8", "ignore")
            except OSError:
                continue
            for pattern in patterns:
                for hit in pattern.findall(text):
                    found.add(_resolve(hit))
    return found


# -------------------------------------------------------------------- walking
def _classify(parts: tuple) -> "str | None":
    """The managed kind of a derived-relative path, or None if unmanaged."""
    if parts and parts[0] == CROPS_SUBDIR and len(parts) >= 2:
        return CROPS_SUBDIR
    if (len(parts) >= 3 and parts[0].startswith("doc-")
            and parts[1] in MANAGED_DOC_SUBDIRS):
        return parts[1]
    return None


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------------- deleting
def remove_derived_file(path) -> Path:
    """Unlink one file, through the read-only-corpus guard.

    `paths.ensure_writable` is the guard every write in this package goes
    through, and its refusal semantics are exactly right for a delete: a path
    that resolves outside `workspace/` raises `CorpusWriteError` and nothing
    happens. Deletion therefore needed no new guard, only this caller.
    """
    p = Path(path)
    if p.is_symlink():
        raise CorpusWriteError(f"refusing to delete through a symlink: {p}")
    target = ensure_writable(p)
    target.unlink()
    return target


def _prune_empty(start: Path, stop: Path) -> int:
    """Remove directories emptied by this run, upward, never past `stop`."""
    removed = 0
    current = Path(start)
    stop = Path(stop).resolve()
    while True:
        current = current.resolve()
        if current == stop or stop not in current.parents:
            return removed
        try:
            ensure_writable(current)
            current.rmdir()
        except (OSError, CorpusWriteError):
            return removed
        removed += 1
        current = current.parent


# ---------------------------------------------------------------------- entry
def collect(conn: sqlite3.Connection, *, apply: bool = False,
            derived_dir=None, snapshot_dir=None, text_roots=None) -> dict:
    """Find (and with ``apply=True``, delete) unreachable derived images.

    Dry run by default. The report carries before/after totals for the whole
    derived tree, the size of each root set, and one entry per orphan.
    """
    from .snapshot_store import SNAPSHOT_DIR

    base = Path(derived_dir) if derived_dir is not None else DERIVED_DIR
    # Before listing a single file: a derived_dir outside workspace/ is not a
    # derived store, and this function's whole purpose is deleting from it.
    ensure_writable(base)
    snaps = Path(snapshot_dir) if snapshot_dir is not None else SNAPSHOT_DIR
    if text_roots is None:
        text_roots = (CATALOG_DIR, REPORTS_DIR, snaps)

    paths_root, path_problems = referenced_paths(conn)
    digests, digest_problems = referenced_digests(conn)
    cites, unreadable = published_cites(snaps)
    from_text = text_references(base, text_roots)

    report = {
        "derived_dir": rel(base),
        "applied": bool(apply),
        "unsafe": bool(unreadable or path_problems or digest_problems),
        "unreadable_snapshots": unreadable,
        "unreadable_roots": path_problems + digest_problems,
        "roots": {
            "pages.page_image_path": 0,
            "elements.region_image_path": 0,
            "assets.path": 0,
            "table_read_candidates.crop_path": 0,
            "review_crop_sha256": len(digests),
            "published_snapshot_cites": len(cites),
            "text_reference": len(from_text),
        },
        "before": {"files": 0, "bytes": 0},
        "after": {"files": 0, "bytes": 0},
        "in_scope_files": 0, "in_scope_bytes": 0,
        "unmanaged_files": 0, "unmanaged_bytes": 0,
        "reachable_files": 0, "reachable_bytes": 0,
        "orphan_files": 0, "orphan_bytes": 0,
        "orphans": [],
        "by_kind": {},
        "symlinks_skipped": [],
        "deleted_files": 0, "deleted_bytes": 0,
        "dirs_pruned": 0,
        "errors": [],
    }
    for key in ROOT_KEYS[:4]:
        report["roots"][key] = sum(1 for keys in paths_root.values() if key in keys)

    if not base.is_dir():
        return report

    orphans: list[tuple[Path, str, int]] = []
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        here = Path(dirpath)
        for name in sorted(dirnames):
            if (here / name).is_symlink():
                report["symlinks_skipped"].append(rel(here / name))
        dirnames[:] = [d for d in dirnames if not (here / d).is_symlink()]
        for name in sorted(filenames):
            path = here / name
            if path.is_symlink():
                report["symlinks_skipped"].append(rel(path))
                continue
            try:
                size = path.stat().st_size
            except OSError as exc:
                report["errors"].append({"path": rel(path), "error": str(exc)})
                continue
            report["before"]["files"] += 1
            report["before"]["bytes"] += size

            kind = _classify(path.relative_to(base).parts)
            if kind is None:
                report["unmanaged_files"] += 1
                report["unmanaged_bytes"] += size
                continue
            report["in_scope_files"] += 1
            report["in_scope_bytes"] += size

            resolved = path.resolve()
            reachable = resolved in paths_root or resolved in from_text
            if not reachable and cites:
                m = _CROP_NAME_RE.match(name)
                reachable = bool(m and m.group(1) in cites)
            if not reachable and digests:
                try:
                    reachable = _sha256_file(path) in digests
                except OSError as exc:
                    report["errors"].append({"path": rel(path), "error": str(exc)})
                    reachable = True     # unknown means keep
            if reachable:
                report["reachable_files"] += 1
                report["reachable_bytes"] += size
                continue
            orphans.append((path, kind, size))

    for path, kind, size in orphans:
        report["orphan_files"] += 1
        report["orphan_bytes"] += size
        report["by_kind"][kind] = report["by_kind"].get(kind, 0) + 1
        report["orphans"].append({"path": rel(path), "kind": kind, "bytes": size})

    if apply and not report["unsafe"]:
        emptied: set[Path] = set()
        for path, _kind, size in orphans:
            try:
                remove_derived_file(path)
            except (OSError, CorpusWriteError) as exc:
                report["errors"].append({"path": rel(path), "error": str(exc)})
                continue
            report["deleted_files"] += 1
            report["deleted_bytes"] += size
            emptied.add(path.parent)
        for parent in sorted(emptied, key=lambda p: len(p.parts), reverse=True):
            report["dirs_pruned"] += _prune_empty(parent, base)

    if report["unsafe"]:
        removable_files = removable_bytes = 0
    elif apply:
        removable_files, removable_bytes = report["deleted_files"], report["deleted_bytes"]
    else:
        removable_files, removable_bytes = report["orphan_files"], report["orphan_bytes"]
    report["after"] = {"files": report["before"]["files"] - removable_files,
                       "bytes": report["before"]["bytes"] - removable_bytes}
    return report
