"""Fetch corpus objects from public object storage.

Anonymous: no credentials, no SDK. Every object is verified against the sha256
that is also its storage key, so a corrupted or substituted object cannot land
on disk.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .distribution import files_for_subset
from .paths import CorpusWriteError, fetch_target

CHUNK = 1 << 20

DEFAULT_MANIFEST_URL_ENV = "FENCE_RAG_MANIFEST_URL"

# Cloudflare's r2.dev public host returns 403 Forbidden to the default
# Python-urllib User-Agent; an explicit one is required on every outbound
# request or the entire consumer path is non-functional against the real
# published bucket.
USER_AGENT = "fence-rag/1.0 (+https://github.com/spicysauce1955-stack/fence-rag)"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def download_object(url: str, expected_sha256: str, dest: Path, tmp_dir: Path) -> bool:
    """Download url to dest, verifying sha256. Returns False if already present."""
    if dest.exists() and not dest.is_file():
        raise IsADirectoryError(f"refusing to fetch over a non-regular-file target: {dest}")
    if dest.is_file() and _sha256_file(dest) == expected_sha256:
        return False
    # NOTE: if dest exists but its hash does NOT match (a corrupted or
    # tampered previous download), execution falls through and the block
    # below overwrites it after re-verifying the freshly downloaded bytes.
    # That is deliberate -- it is how a corrupted download gets repaired by
    # re-running `cli fetch` -- but it does mean a hostile manifest that
    # names a legitimate corpus path can cause an existing file at that path
    # to be replaced, since fetch_target does not check for prior existence.
    # The sha256 verification below still guarantees whatever lands on disk
    # matches the manifest's declared hash for that path.
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=tmp_dir, suffix=".part")
    tmp = Path(tmp_name)
    try:
        h = hashlib.sha256()
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with os.fdopen(fd, "wb") as out, urllib.request.urlopen(req, timeout=60) as resp:
            for block in iter(lambda: resp.read(CHUNK), b""):
                h.update(block)
                out.write(block)
        got = h.hexdigest()
        if got != expected_sha256:
            raise ValueError(
                f"sha256 mismatch for {url}: expected {expected_sha256}, got {got}")
        shutil.move(str(tmp), str(dest))
        return True
    finally:
        if tmp.exists():
            tmp.unlink()


def copy_object(source: Path, dest: Path, expected_sha256: str, tmp_dir: Path) -> None:
    """Materialise a sibling path from an already-local copy of the same object.

    Written to a temp file under workspace/ and moved into place, exactly as a
    download is, so a partial copy can never be left at a corpus path. The
    bytes are re-hashed on the way through: every path this module writes is
    verified against the manifest hash before it lands, whether it arrived
    over the wire or from a sibling.

    A copy, not a hardlink. The 55.5 MB saved by linking is not worth making
    two corpus files share an inode: the corpus is meant to look like an
    ordinary checkout, the store deliberately keeps byte-identical files as
    distinct source records (`same_content_as`, never deduplicated), and a
    hardlink silently turns an edit to one into an edit to the other.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=tmp_dir, suffix=".part")
    tmp = Path(tmp_name)
    try:
        h = hashlib.sha256()
        with os.fdopen(fd, "wb") as out, open(source, "rb") as src:
            for block in iter(lambda: src.read(CHUNK), b""):
                h.update(block)
                out.write(block)
        got = h.hexdigest()
        if got != expected_sha256:
            raise ValueError(
                f"sha256 mismatch copying {source} to {dest}: "
                f"expected {expected_sha256}, got {got}")
        shutil.move(str(tmp), str(dest))
    finally:
        if tmp.exists():
            tmp.unlink()


def fetch_subset(manifest: dict, subset: str, dest_root: Path,
                 workers: int = 4) -> dict:
    """Fetch every path a subset names, transferring each distinct object once.

    The corpus contains 14 groups of byte-identical files filed under
    different manufacturers, so its 144 paths hold only 128 distinct objects.
    Targets are grouped by sha256: the object is downloaded once and copied to
    its siblings. This is the same saving `publish` already takes on the way
    up, where it is reported as `skipped_duplicate_paths`. Iterating paths
    instead cost 55.5 MB on `--subset all` and 48% on `--subset structural`.

    Paths and objects now differ, so the counts say which they are:

      requested        paths the subset names
      objects          distinct sha256 among them
      downloaded       objects actually transferred over the network
      bytes            bytes transferred over the network (unique content only)
      copied           sibling paths written from an already-local copy
      already_present  paths that already held the right bytes
      failed           one entry per path that did not end up correct

    `downloaded` and `bytes` count objects because they measure what crossed
    the wire, which is the number this change exists to reduce; the other
    three count paths, and the four path counts partition `requested`.

    Every target is resolved through `paths.fetch_target` before a single byte
    moves, so a manifest naming a path outside the corpus raises
    CorpusWriteError rather than being reported as a per-object failure.
    """
    wanted = files_for_subset(manifest, subset)
    allowed = {f["source_path"] for f in manifest["files"]}
    base = manifest["base_url"]
    tmp_dir = Path(dest_root) / "workspace" / "tmp-fetch"

    # resolve every target before transferring anything: a manifest naming a
    # path outside the corpus must fail before the first byte is written
    targets = [(f, fetch_target(Path(dest_root) / f["source_path"], allowed))
               for f in wanted]
    for _f, dest in targets:
        if dest.exists() and not dest.is_file():
            raise IsADirectoryError(
                f"refusing to fetch over a non-regular-file target: {dest}")

    groups: dict[str, list] = {}
    for item in targets:
        groups.setdefault(item[0]["sha256"], []).append(item)

    result = {"requested": len(targets), "objects": len(groups), "downloaded": 0,
              "copied": 0, "already_present": 0, "bytes": 0, "failed": []}

    def one(group):
        """Resolve one hash group. Returns (group, outcome-by-path, bytes, err)."""
        first = group[0][0]
        sha, url = first["sha256"], base + first["key"]
        outcomes: dict[str, str] = {}
        transferred = 0
        err = None
        try:
            present, missing = [], []
            for f, dest in group:
                if dest.is_file() and _sha256_file(dest) == sha:
                    present.append((f, dest))
                    outcomes[f["source_path"]] = "already_present"
                else:
                    missing.append((f, dest))
            if missing:
                if present:
                    source = present[0][1]
                else:
                    f0, source = missing.pop(0)
                    download_object(url, sha, source, tmp_dir)
                    outcomes[f0["source_path"]] = "downloaded"
                    transferred = first["bytes"]
                for f, dest in missing:
                    copy_object(source, dest, sha, tmp_dir)
                    outcomes[f["source_path"]] = "copied"
        except CorpusWriteError:
            raise                       # a guard breach is never a soft failure
        except Exception as e:  # noqa: BLE001 - reported per object, not raised
            err = f"{e.__class__.__name__}: {e}"
        return group, outcomes, transferred, err

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for group, outcomes, transferred, err in pool.map(one, groups.values()):
            result["bytes"] += transferred
            for f, _dest in group:
                # exactly one path per group can carry the "downloaded"
                # outcome, so counting outcomes per path still counts
                # downloads per object
                outcome = outcomes.get(f["source_path"])
                if outcome is None:
                    result["failed"].append({"source_path": f["source_path"],
                                             "error": err or "not attempted"})
                else:
                    result[outcome] += 1
    if tmp_dir.is_dir() and not any(tmp_dir.iterdir()):
        tmp_dir.rmdir()
    return result


def load_remote_manifest(url: str | None = None) -> dict:
    """Load the distribution manifest from a URL, or from the local workspace."""
    if url is None:
        url = os.environ.get(DEFAULT_MANIFEST_URL_ENV)
    if url is None:
        from .paths import CATALOG_DIR
        local = CATALOG_DIR / "distribution-manifest.json"
        if not local.is_file():
            raise FileNotFoundError(
                "no manifest URL given and workspace/catalog/distribution-manifest.json "
                "is absent; pass --manifest-url or run `cli publish --manifest`")
        return json.loads(local.read_text(encoding="utf-8"))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))
