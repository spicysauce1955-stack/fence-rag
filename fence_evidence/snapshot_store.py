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
