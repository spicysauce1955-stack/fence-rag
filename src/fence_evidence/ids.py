"""Stable identifiers.

Document identity is derived from the *source path*, so a document keeps its
id across re-ingestion.  Content identity (change detection, versioning) is
the file's SHA-256, kept separately in ``document_versions``.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def doc_id_for(rel_path: str) -> str:
    """Stable document id derived from the repo-relative source path."""
    return "doc-" + hashlib.sha256(rel_path.encode("utf-8")).hexdigest()[:12]


def version_id_for(doc_id: str, sha256: str) -> str:
    return f"{doc_id}@{sha256[:12]}"


def page_id_for(version_id: str, page_no: int) -> str:
    return f"{version_id}#p{page_no:04d}"


def element_id_for(page_id: str, ordinal: int) -> str:
    return f"element-{hashlib.sha256(page_id.encode()).hexdigest()[:10]}-{ordinal:04d}"
