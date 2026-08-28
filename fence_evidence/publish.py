"""Publish corpus objects to Cloudflare R2. Maintainer-only.

Requires credentials in .env. Consuming the published corpus needs none of
this -- see fetch.py. Defaults to a dry run: nothing uploads unless --apply.
"""
from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path

from .config import R2Config
from .distribution import manifest_bytes, object_key, write_manifest
from .paths import REPO_ROOT
from .sigv4 import sign_request

CONTENT_TYPES = {".pdf": "application/pdf", ".png": "image/png",
                 ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                 ".json": "application/json"}


def _request(cfg: R2Config, method: str, key: str, payload: bytes,
             content_type: str) -> int:
    url = f"{cfg.endpoint}/{cfg.bucket}/{key}"
    headers = sign_request(method, url, {"content-type": content_type}, payload,
                           cfg.access_key_id, cfg.secret_access_key,
                           region="auto", service="s3")
    req = urllib.request.Request(url, data=payload or None, method=method)
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        if method == "HEAD" and e.code == 404:
            return 404
        raise RuntimeError(f"{method} {key} failed: HTTP {e.code}") from None


def head_object(cfg: R2Config, key: str) -> bool:
    return _request(cfg, "HEAD", key, b"", "application/octet-stream") == 200


def publish_objects(cfg: R2Config, rows: list[dict], dry_run: bool = True) -> dict:
    seen: set[str] = set()
    out = {"unique_objects": 0, "uploaded": 0, "already_present": 0,
           "skipped_duplicate_paths": 0, "bytes": 0, "dry_run": dry_run}
    for r in rows:
        sha = r.get("sha256")
        if not sha:
            raise RuntimeError(
                f"{r['source_path']} has no sha256 in the corpus manifest "
                f"(not fetched, or absent from disk); refusing to publish a "
                f"partial corpus. Fetch it and re-run `cli manifest`.")
        if sha in seen:
            out["skipped_duplicate_paths"] += 1
            continue
        seen.add(sha)
        out["unique_objects"] += 1
        key = object_key(sha)
        if not dry_run and head_object(cfg, key):
            out["already_present"] += 1
            continue
        path = REPO_ROOT / r["source_path"]
        payload = path.read_bytes()
        got = hashlib.sha256(payload).hexdigest()
        if got != sha:
            raise RuntimeError(
                f"{r['source_path']} does not match its manifest sha256 "
                f"(expected {sha}, got {got}); re-run `cli manifest`")
        out["bytes"] += len(payload)
        if dry_run:
            continue
        _request(cfg, "PUT", key, payload,
                 CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream"))
        out["uploaded"] += 1
    return out


def publish_manifest(cfg: R2Config, manifest: dict, dry_run: bool = True,
                     path: Path | str | None = None) -> dict:
    """Write the manifest locally, and upload it unless this is a dry run.

    G25. The encoding and the guarded write live in `distribution`, which owns
    the manifest's shape; this function owns only the upload. They were the same
    six lines in two places, and the local half was untestable because it wrote
    to the committed artifact whatever a test did -- so `publish_manifest` had
    no test at all. `path` exists for that: it defaults to the committed
    location and a caller can point it at a scratch directory instead.
    """
    payload = manifest_bytes(manifest)
    out = write_manifest(manifest, path)
    if not dry_run:
        _request(cfg, "PUT", "distribution-manifest.json", payload, "application/json")
    return {"bytes": out["bytes"], "local": out["local"], "dry_run": dry_run}
