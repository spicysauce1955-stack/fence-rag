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
from .paths import fetch_target

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


def fetch_subset(manifest: dict, subset: str, dest_root: Path,
                 workers: int = 4) -> dict:
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

    result = {"requested": len(targets), "downloaded": 0, "already_present": 0,
              "bytes": 0, "failed": []}

    def one(item):
        f, dest = item
        try:
            got = download_object(base + f["key"], f["sha256"], dest, tmp_dir)
            return f, dest, got, None
        except Exception as e:  # noqa: BLE001 - reported per object, not raised
            return f, dest, False, f"{e.__class__.__name__}: {e}"

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for f, _dest, got, err in pool.map(one, targets):
            if err:
                result["failed"].append({"source_path": f["source_path"], "error": err})
            elif got:
                result["downloaded"] += 1
                result["bytes"] += f["bytes"]
            else:
                result["already_present"] += 1
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
