"""Project the corpus manifest into a distribution manifest.

The corpus manifest already records source_path, sha256 and file_size_bytes for
every file, so it is already a download manifest. This module is the projection:
it never invents data and is regenerated, never hand-edited.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from .paths import MANIFEST_PATH

SUBSETS: dict[str, Callable[[dict], bool]] = {
    "all": lambda r: True,
    "structural": lambda r: bool(r.get("structural_subdir")),
    "bufftech": lambda r: r["source_path"].startswith("manuals/certainteed-bufftech/"),
    "china": lambda r: r["source_path"].startswith("china/"),
}


def object_key(sha256: str) -> str:
    return f"objects/{sha256}"


def load_corpus_manifest(path: Path | None = None) -> list[dict]:
    p = Path(path) if path is not None else MANIFEST_PATH
    if not p.is_file():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_manifest(rows: list[dict], base_url: str, generated_at: str) -> dict:
    # A row with no sha256 is a file the manifest could not hash: not fetched,
    # or referenced by a curated index and absent from disk. Projecting one
    # would publish the key "objects/None" and hand every downloader a
    # manifest entry that cannot be satisfied, so refuse the whole run.
    unhashed = [r["source_path"] for r in rows if not r.get("sha256")]
    if unhashed:
        raise ValueError(
            f"{len(unhashed)} manifest row(s) carry no sha256 and cannot be "
            f"published, e.g. {unhashed[0]}. Fetch the corpus and re-run "
            f"`cli manifest` before publishing.")
    files = []
    for r in rows:
        subsets = sorted(name for name, pred in SUBSETS.items() if pred(r))
        files.append({
            "source_path": r["source_path"],
            "sha256": r["sha256"],
            "bytes": r["file_size_bytes"],
            "key": object_key(r["sha256"]),
            "subsets": subsets,
        })
    summary = {}
    for name, pred in SUBSETS.items():
        sel = [r for r in rows if pred(r)]
        uniq = {r["sha256"]: r["file_size_bytes"] for r in sel}
        summary[name] = {"files": len(sel), "unique": len(uniq),
                         "bytes": sum(uniq.values())}
    return {"schema": 1, "generated_at": generated_at, "base_url": base_url,
            "subsets": summary, "files": sorted(files, key=lambda f: f["source_path"])}


def files_for_subset(manifest: dict, subset: str) -> list[dict]:
    if subset not in manifest["subsets"]:
        raise KeyError(f"unknown subset {subset!r}; known: {sorted(manifest['subsets'])}")
    return [f for f in manifest["files"] if subset in f["subsets"]]
