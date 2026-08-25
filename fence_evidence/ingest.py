"""Ingestion orchestration: manifest -> extraction -> canonical store.

Idempotent and resumable.  A document whose SHA-256 was already extracted by
the same tool versions is skipped without re-reading the file; nothing is
deleted from the corpus at any point.
"""
from __future__ import annotations

import json
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .extract import extract
from .manifest import load_manifest
from .paths import (FETCH_HINT, REPO_ROOT, REPORTS_DIR, is_lfs_pointer,
                    open_write)
from .relations import derive_relations
from .store import (build_retrieval_units, connect, finish_run, migrate, now,
                    start_run, stats, tool_fingerprint, version_exists,
                    write_extracted)
from .tools import tool_versions

PIPELINE_VERSION = __version__


def _extract_one(args):
    """Worker: extract a single document.  Returns (source_path, doc|None, error)."""
    source_path, doc_id = args
    try:
        doc = extract(REPO_ROOT / source_path, doc_id=doc_id)
        return source_path, doc, None
    except Exception:
        return source_path, None, traceback.format_exc(limit=6)


class StaleManifestError(RuntimeError):
    """The manifest disagrees with what is on disk; Phase 0 must be re-run."""


def partition_targets(targets: list[str], manifest: dict[str, dict]) -> dict:
    """Split requested paths into ready / not-fetched / stale / unknown.

    Reads the bytes on disk rather than trusting the manifest row. The two
    disagree in both directions and both matter: a manifest built before
    `cli fetch` describes pointers for files that are now real, and one built
    after a fetch that has since been reverted describes content that is gone.
    Extracting either way produces a document that misreports its own source.
    """
    out: dict[str, list[str]] = {"ready": [], "not_fetched": [], "stale": [],
                                 "unknown": []}
    for sp in targets:
        row = manifest.get(sp)
        if not row:
            out["unknown"].append(sp)
            continue
        pointer_on_disk = is_lfs_pointer(REPO_ROOT / sp)
        row_says_fetched = bool(row.get("sha256"))
        if pointer_on_disk:
            out["not_fetched"].append(sp)
        elif not row_says_fetched:
            # Bytes arrived after the manifest was built. Extracting now would
            # record the document against a null hash.
            out["stale"].append(sp)
        else:
            out["ready"].append(sp)
    return out


def ingest(source_paths: list[str] | None = None, *, workers: int = 6,
           force: bool = False, log_name: str = "ingestion") -> dict:
    manifest = {r["source_path"]: r for r in load_manifest()}
    targets = source_paths if source_paths is not None else [
        r["source_path"] for r in manifest.values()
        # "not-fetched" rows are deliberately kept in: excluding them here is
        # what made a whole-corpus run over an unfetched checkout look like a
        # complete success. They are counted and reported below instead.
        if r.get("extraction_method") not in (None, "unsupported", "unreadable")
    ]

    parts = partition_targets(targets, manifest)
    if parts["unknown"]:
        raise KeyError(f"{parts['unknown'][0]} is not in the corpus manifest; "
                       f"run Phase 0 first ({len(parts['unknown'])} such paths)")
    if parts["stale"]:
        raise StaleManifestError(
            f"{len(parts['stale'])} file(s) are present on disk but carry no hash in "
            f"the manifest, e.g. {parts['stale'][0]}. The manifest was built before "
            f"these were fetched. Re-run `python3 -m fence_evidence.cli manifest`.")
    not_fetched = parts["not_fetched"]
    targets = parts["ready"]

    conn = connect()
    migrate(conn)
    tv = tool_versions()
    fp = tool_fingerprint(tv)
    run_id = start_run(conn, tv, PIPELINE_VERSION, notes=f"targets={len(targets)}")

    todo, skipped = [], []
    for sp in targets:
        row = manifest[sp]
        if not force and version_exists(conn, row["doc_id"], row["sha256"], fp):
            skipped.append(sp)
            continue
        todo.append((sp, row["doc_id"]))

    log_path = REPORTS_DIR / f"{log_name}-log.jsonl"
    results = {"ingested": [], "skipped": skipped, "failed": [],
               "not_fetched": not_fetched}
    started = datetime.now(timezone.utc)

    with open_write(log_path, "a") as log:
        log.write(json.dumps({"event": "run_start", "run_id": run_id, "at": now(),
                              "targets": len(targets), "to_extract": len(todo),
                              "already_current": len(skipped),
                              "not_fetched": len(not_fetched),
                              "tool_versions": tv}) + "\n")
        if not_fetched:
            print(f"WARNING: {len(not_fetched)} requested file(s) are still "
                  f"unsmudged Git LFS pointers and were NOT ingested, "
                  f"e.g. {not_fetched[0]}\n"
                  f"         fetch the corpus first: {FETCH_HINT}", file=sys.stderr)
        pool_error = None
        try:
            if todo:
                with ProcessPoolExecutor(max_workers=workers) as pool:
                    futures = {pool.submit(_extract_one, t): t[0] for t in todo}
                    for i, fut in enumerate(as_completed(futures), 1):
                        sp, doc, err = fut.result()
                        if err:
                            results["failed"].append({"source_path": sp, "error": err})
                            conn.execute("""INSERT INTO quality_issues(document_id, severity,
                                kind, detail, detected_at) VALUES (?,?,?,?,?)""",
                                         (manifest[sp]["doc_id"], "error", "extraction_failed",
                                          err[-800:], now()))
                            conn.commit()
                            log.write(json.dumps({"event": "extract_failed", "source_path": sp,
                                                  "error": err[-800:]}) + "\n")
                            print(f"[{i}/{len(todo)}] FAILED {sp}", file=sys.stderr)
                            continue
                        version_id = write_extracted(conn, doc, manifest[sp], run_id)
                        # Project this document immediately: an interrupted run
                        # then leaves everything ingested so far searchable
                        # instead of leaving the whole store unindexed.
                        build_retrieval_units(conn, document_id=manifest[sp]["doc_id"])
                        n_el = sum(len(p.elements) for p in doc.pages)
                        results["ingested"].append(sp)
                        log.write(json.dumps({"event": "ingested", "source_path": sp,
                                              "version_id": version_id,
                                              "pages": len(doc.pages), "elements": n_el,
                                              "issues": len(doc.quality_issues)}) + "\n")
                        log.flush()
                        print(f"[{i}/{len(todo)}] {sp}  {len(doc.pages)}p {n_el}el "
                              f"{len(doc.quality_issues)}iss", file=sys.stderr)
        except Exception as e:
            # A worker dying (OOM, BrokenProcessPool) must not skip the
            # bookkeeping below, or the run stays open and unindexed.
            pool_error = f"{e.__class__.__name__}: {e}"
            results["failed"].append({"source_path": "<pool>", "error": pool_error})
            log.write(json.dumps({"event": "pool_error", "error": pool_error}) + "\n")
            print(f"POOL ERROR: {pool_error}", file=sys.stderr)

        rel_counts = derive_relations(conn)
        n_units = build_retrieval_units(conn)
        finish_run(conn, run_id)
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        summary = {"event": "run_end", "run_id": run_id, "at": now(),
                   "pool_error": pool_error,
                   "elapsed_s": round(elapsed, 1), "relations": rel_counts,
                   "retrieval_units": n_units, "store": stats(conn),
                   "ingested": len(results["ingested"]), "skipped": len(skipped),
                   "failed": len(results["failed"]),
                   "not_fetched": len(not_fetched),
                   "not_fetched_paths": not_fetched[:10]}
        log.write(json.dumps(summary) + "\n")
    results["summary"] = summary
    conn.close()
    return results


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Ingest corpus documents into the evidence store")
    ap.add_argument("--pilot", action="store_true", help="ingest only the 10 pilot documents")
    ap.add_argument("--all", action="store_true", help="ingest the whole corpus")
    ap.add_argument("--path", action="append", default=[], help="ingest a specific source path")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--force", action="store_true", help="re-extract even if unchanged")
    args = ap.parse_args()

    if args.pilot:
        from .pilot import PILOT_PATHS
        paths = PILOT_PATHS
        name = "pilot-ingestion"
    elif args.path:
        paths = args.path
        name = "adhoc-ingestion"
    elif args.all:
        paths = None
        name = "full-ingestion"
    else:
        ap.error("choose --pilot, --all or --path")
    res = ingest(paths, workers=args.workers, force=args.force, log_name=name)
    print(json.dumps(res["summary"], indent=2))
