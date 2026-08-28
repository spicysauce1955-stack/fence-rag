"""Hold published snapshots. Write once, never overwrite, tombstone rather than delete.

**This is the first thing this system produces that it cannot regenerate**, and
that deserves saying plainly: the corpus is read-only input, and every other
output -- the store, the projection, the page images, the reports -- can be
thrown away and rebuilt from it. A snapshot cannot.

A snapshot is built from the L2/L3 state as it stood at one moment. That state
moves forward: the instant a reviewer accepts one more claim, the previous
snapshot can never be reconstructed by anything, by anyone. And obligation 1 says
fetching it by hash returns the same bytes until `retain_until`.

`workspace/` is often described as disposable, and that is not quite what the
repository actually does: `.gitignore` names the heavy regenerable subdirectories
individually -- `pylibs/`, `derived/`, `indexes/` -- while `reports/` and
`catalog/` are **tracked**. The convention already separates durable output from
disposable output, and a snapshot is durable, so `workspace/snapshots/` is
committed. Git is the durable store: tens of KB per snapshot, content-addressed
and immutable, already backed up wherever the remote is. `retain_until` is what
eventually allows one to be dropped.

Two refusals do the real work:

* **Storing an id that already holds different bytes raises.** Silently
  overwriting is how a hash becomes a lie. Re-storing *identical* bytes is fine,
  so a retried build is not an error.
* **Excision writes a tombstone, never a delete.** A document may have to be
  removed one day. When that happens an old run must report *"this input was
  excised"* rather than 404 (indistinguishable from never existing) or, far
  worse, silently recomputing to a different answer.
"""
from __future__ import annotations

import json
from pathlib import Path

from .canonical import canonical_bytes
from .paths import WORKSPACE, open_write

SNAPSHOT_DIR = WORKSPACE / "snapshots"


class SnapshotExists(RuntimeError):
    """Raised rather than overwriting a stored snapshot with different bytes."""


class SnapshotMissing(KeyError):
    """Raised when an id was never stored. Distinct from an excised one, which
    resolves to a tombstone -- 'never existed' and 'withdrawn' are different
    facts and a caller must be able to tell them apart."""


def _path(snapshot_id: str, root: Path | None = None) -> Path:
    if not snapshot_id or "/" in snapshot_id or ".." in snapshot_id:
        raise ValueError(f"not a snapshot id: {snapshot_id!r}")
    return (root or SNAPSHOT_DIR) / f"{snapshot_id}.json"


# Metadata that is NOT part of the hash and so may legitimately differ between
# two builds of the same content. `retain_until` moves with the clock: hashing it
# would mean two builds over identical knowledge never matched, which is the
# opposite of what obligation 1 asks for.
_UNHASHED = ("retain_until",)


def _hashed_members(snapshot: dict) -> dict:
    return {k: v for k, v in snapshot.items()
            if k != "snapshot_id" and k not in _UNHASHED}


def put_snapshot(snapshot: dict, *, root: Path | None = None) -> Path:
    path = _path(snapshot["snapshot_id"], root)
    payload = canonical_bytes(snapshot)
    if path.exists():
        if path.read_bytes() == payload:
            return path                     # identical rebuild; nothing happened
        stored = json.loads(path.read_bytes())
        if _hashed_members(stored) == _hashed_members(snapshot):
            # Same id, same content, different `retain_until` -- a rebuild on a
            # later day. The ID is the identity, so this IS the same snapshot,
            # and the STORED copy wins: its retain_until is the promise already
            # made to whoever pinned that hash, and a later build must not
            # quietly extend or shorten it.
            return path
        raise SnapshotExists(
            f"{snapshot['snapshot_id']} is already stored with different CONTENT. "
            f"Only unhashed metadata may differ, so if a hashed member changed "
            f"the id should have changed too — either the stored file was "
            f"tampered with or the canonicaliser is not deterministic.")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open_write(path, "wb") as fh:
        fh.write(payload)
    return path


def get_snapshot(snapshot_id: str, *, root: Path | None = None) -> dict:
    path = _path(snapshot_id, root)
    if not path.exists():
        raise SnapshotMissing(snapshot_id)
    return json.loads(path.read_bytes())


def tombstone(snapshot_id: str, *, reason: str, root: Path | None = None) -> Path:
    """Replace a snapshot with a record that it was excised, and why.

    The payload goes; the fact that it existed does not. `reason` is required
    because a tombstone with no reason answers the 404 problem and none of the
    accountability one.
    """
    if not reason or not reason.strip():
        raise ValueError("a tombstone must record why the snapshot was excised")
    path = _path(snapshot_id, root)
    if not path.exists():
        raise SnapshotMissing(snapshot_id)
    stone = {"snapshot_id": snapshot_id, "tombstoned": True, "reason": reason.strip()}
    with open_write(path, "wb") as fh:
        fh.write(canonical_bytes(stone))
    return path


def list_snapshots(*, root: Path | None = None) -> list[dict]:
    """Every id held, with just enough to tell them apart. Never loads payloads."""
    base = root or SNAPSHOT_DIR
    if not base.exists():
        return []
    out = []
    for p in sorted(base.glob("*.json")):
        d = json.loads(p.read_bytes())
        out.append({"snapshot_id": d["snapshot_id"],
                    "tombstoned": bool(d.get("tombstoned")),
                    "tenant": d.get("tenant"), "regime": d.get("regime"),
                    "retain_until": d.get("retain_until"),
                    "warnings": len(d.get("warnings", [])),
                    "gaps": len(d.get("gaps", [])),
                    "bytes": p.stat().st_size})
    return out


def verify_stored(*, root: Path | None = None) -> dict:
    """Re-run the obligations over every snapshot already on disk.

    The gate ran at build time only, so a snapshot published before an obligation
    was implemented stayed non-compliant with nothing able to say so. Measured on
    the first stored snapshot: it fails today's `verify()` with 188 failures --
    63 gaps carrying neither `because` nor `cites`, and every `SourceDoc` missing
    `also_filed_as` -- while `cli refs --verify` passed it happily, because that
    command checks whether citations resolve, not whether the object is
    well-formed. `cli snapshot --list` showed it as an ordinary member.

    A stored snapshot is immutable, so this cannot repair anything. What it can
    do is stop the gap between "the builder was fixed" and "the published
    artifact is fixed" from being invisible, which is how G40 came to be recorded
    as FIXED while the shipped object still carried the defect.

    Exits are the caller's business; this returns the findings. `verify()` is
    total over well-formed JSON but raises rather than returning on malformed
    input, so a snapshot that cannot even be parsed is reported, not fatal.
    """
    from .snapshot import VerificationFailed, verify

    out = {"checked": 0, "passed": 0, "failed": 0, "tombstoned_skipped": 0,
           "unreadable": [], "failures": {}}
    base = (root or SNAPSHOT_DIR)
    if not base.exists():
        return out
    for path in sorted(base.glob("*.json")):
        try:
            payload = json.loads(path.read_text())
        except Exception as exc:
            out["unreadable"].append({"file": path.name,
                                      "error": exc.__class__.__name__})
            continue
        # `tombstoned`, matching what tombstone() writes and what
        # refs.verify_snapshots reads. The two guards must agree about what a
        # withdrawn snapshot looks like, or one of them silently checks a
        # different population than the other.
        if payload.get("tombstoned"):
            out["tombstoned_skipped"] += 1
            continue
        out["checked"] += 1
        try:
            verify(payload)
            out["passed"] += 1
        except VerificationFailed as exc:
            out["failed"] += 1
            lines = [ln.strip(" -") for ln in str(exc).split("\n")[1:] if ln.strip()]
            out["failures"][payload.get("snapshot_id", path.stem)[:16]] = {
                "count": len(lines), "first": lines[:5]}
        except Exception as exc:      # verify() is not total over malformed input
            out["failed"] += 1
            out["failures"][payload.get("snapshot_id", path.stem)[:16]] = {
                "count": 1, "first": [f"verify() raised {exc.__class__.__name__}: {exc}"]}
    return out
