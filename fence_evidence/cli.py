"""Command line interface: python3 -m fence_evidence.cli <command>"""
from __future__ import annotations

import argparse
import json
import sys

from .paths import FETCH_HINT, init_workspace


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def _warn_unfetched() -> int:
    """Say so, once, when part of the corpus is still LFS pointers.

    Every measurement downstream of an unfetched corpus is meaningless, and
    the failure is otherwise invisible -- poppler reports a pointer as a
    zero-page PDF, which is indistinguishable from a corrupt one.
    """
    from .paths import unfetched_corpus_files
    missing = unfetched_corpus_files()
    if missing:
        print(f"WARNING: {len(missing)} corpus file(s) are unsmudged Git LFS "
              f"pointers, not documents (e.g. {missing[0]}).\n"
              f"         Results below cover only what is actually on disk.\n"
              f"         Fetch the corpus first: {FETCH_HINT}", file=sys.stderr)
    return len(missing)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="fence-evidence",
                                 description="Source-preserving evidence system "
                                             "for the vinyl fence corpus")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("manifest", help="Phase 0: (re)build the corpus manifest")

    p = sub.add_parser("ingest", help="Phase 1/5: extract documents into the store")
    p.add_argument("--pilot", action="store_true")
    p.add_argument("--all", action="store_true")
    p.add_argument("--path", action="append", default=[])
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--force", action="store_true")

    p = sub.add_parser("search", help="Phase 3: search the evidence store")
    p.add_argument("query")
    p.add_argument("-k", "--limit", type=int, default=5)
    p.add_argument("--manufacturer")
    p.add_argument("--doc-type")
    p.add_argument("--version-status")
    p.add_argument("--element-type")
    p.add_argument("--full", action="store_true", help="print full element text")
    p.add_argument("--second-stage", action="store_true",
                   help="also search within each retrieved page for elements covering "
                        "query terms the matched unit missed (opt-in: measured at 0.672 "
                        "unit support against a 0.70 acceptance target, see "
                        "docs/second-stage-evaluation.md)")

    p = sub.add_parser("document", help="document record with versions and relations")
    p.add_argument("identifier")

    p = sub.add_parser("page", help="one page with its elements")
    p.add_argument("document_id")
    p.add_argument("page_no", type=int)

    p = sub.add_parser("region", help="image evidence for one element")
    p.add_argument("element_id")

    p = sub.add_parser("context", help="neighbouring elements of one element")
    p.add_argument("element_id")
    p.add_argument("--before", type=int, default=1)
    p.add_argument("--after", type=int, default=1)

    p = sub.add_parser("resolve", help="resolve a document or approval id to its version chain")
    p.add_argument("identifier")
    p.add_argument("--at", help="ISO date: which member was effective then")
    p.add_argument("--as-of", help="ISO date to judge expiry against (default: today)")

    p = sub.add_parser("facts", help="Phase 6: extract or query structured facts")
    p.add_argument("--extract", action="store_true")
    p.add_argument("--type")
    p.add_argument("--manufacturer")
    p.add_argument("--limit", type=int, default=20)

    p = sub.add_parser("evaluate", help="Phase 4: run the gold evaluation set")
    p.add_argument("-k", type=int, default=10)
    p.add_argument("--second-stage", action="store_true")
    p.add_argument("--name", default="evaluation")

    p = sub.add_parser("audit", help="relevance audit of the retrieval projection (read-only)")
    p.add_argument("-k", type=int, default=10)

    p = sub.add_parser("table-review",
                       help="load reader transcriptions of scanned tables and compare them")
    p.add_argument("--load-dir", help="directory of agent-read-*.json files")
    p.add_argument("--agreement", nargs=2, metavar=("READER_A", "READER_B"))
    p.add_argument("--mark-agreed", nargs=2, metavar=("READER_A", "READER_B"),
                   help="flag cells two readers read identically as agent_verified "
                        "(still not promotable)")
    p.add_argument("--compare-pipeline", action="store_true",
                   help="how many reader-visible values the pipeline's OCR actually has")
    p.add_argument("--reader")

    p = sub.add_parser("promote-tables",
                       help="turn human-reviewed table readings into conditioned facts")
    p.add_argument("--apply", action="store_true", help="write them (default is a dry run)")
    p.add_argument("--revoke", action="store_true",
                   help="un-promote facts no person reviewed (build-plan A1); "
                        "keeps every reading and its crop")

    p = sub.add_parser("snapshot",
                       help="build, store and inspect published snapshots")
    p.add_argument("--build", action="store_true", help="build one and store it")
    p.add_argument("--tenant", default="default")
    p.add_argument("--regime", default="us_astm", choices=["us_astm", "cn_gb"])
    p.add_argument("--list", action="store_true", help="what is held")
    p.add_argument("--get", metavar="ID", help="fetch one by hash")
    p.add_argument("--dry-run", action="store_true",
                   help="build and report without storing")
    p.add_argument("--verify-stored", action="store_true",
                   help="re-run the obligations over every snapshot already on "
                        "disk; exits non-zero if any fails. The build-time gate "
                        "cannot see an artifact published before it existed")

    p = sub.add_parser("refs",
                       help="the evidence identifier: rebuild the index, or "
                            "verify every published citation still resolves")
    p.add_argument("--verify", action="store_true",
                   help="walk every un-tombstoned snapshot; exit non-zero on a "
                        "citation that no longer resolves")
    p.add_argument("--index", action="store_true",
                   help="rebuild the ref index and report its shape")

    p = sub.add_parser("review",
                       help="the human review loop: accept or correct a machine "
                            "reading of a scanned table")
    p.add_argument("--queue", action="store_true",
                   help="what is waiting for a person")
    p.add_argument("--accept", metavar="CROP_SHA256",
                   help="record a review of one table crop")
    p.add_argument("--reviewer", help="who reviewed it (required with --accept)")
    p.add_argument("--verdict", default="accepted",
                   choices=["accepted", "rejected", "bracket_unclear"],
                   help="bracket_unclear is not a rejection: the values can be "
                        "right while the applicability is unreadable")
    p.add_argument("--grid", metavar="FILE",
                   help="JSON [{row,col,value}] -- the confirmed cells")
    p.add_argument("--spans", metavar="FILE",
                   help="JSON [{row_from,row_to,col,text}] -- merged cells, which "
                        "is the structure the readers cannot see")
    p.add_argument("--notes")
    p.add_argument("--rebuild", action="store_true",
                   help="regenerate the candidate annotations from table_reviews")

    p = sub.add_parser("serve",
                       help="the read/write API behind Planning's screens")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--token", action="append", default=[],
                   help="bearer token on the allowlist; repeatable. Falls back to "
                        "FENCE_API_TOKENS (comma-separated) in the environment")

    p = sub.add_parser("dataset",
                       help="baseline and verify the hand-researched dataset")
    p.add_argument("--write", action="store_true", help="write the SHA-256 baseline")
    p.add_argument("--verify", action="store_true", help="check the tree against it")

    sub.add_parser("migrate",
                   help="bring an existing store up to the current schema: add any "
                        "missing columns and backfill what they need")

    sub.add_parser("worklist",
                   help="split unresolved material into machine / review / human piles")

    sub.add_parser("noa-table-crops",
                   help="export source crops for the pages whose tables OCR could not rebuild")

    p = sub.add_parser("realign-review-crops",
                       help="point the review queue at the artifact the API serves "
                            "(G46); rewrites crop_path and crop_sha256 only")
    p.add_argument("--apply", action="store_true", help="write them (default is a dry run)")

    p = sub.add_parser("backfill-spans",
                       help="recover merged-cell rowspan/colspan for tables already "
                            "in the store (G41); writes two integer columns and no "
                            "bbox, so published citations are unaffected")
    p.add_argument("--apply", action="store_true", help="write them (default is a dry run)")

    sub.add_parser("rebuild-index", help="rebuild the retrieval projection from canonical rows")
    sub.add_parser("stats", help="store statistics")
    sub.add_parser("report", help="regenerate the workspace reports")

    p = sub.add_parser("fetch", help="download corpus objects from public storage")
    p.add_argument("--subset", default="all",
                   help="all, structural, bufftech, china")
    p.add_argument("--manifest-url", default=None,
                   help="override the distribution manifest URL")
    p.add_argument("--workers", type=int, default=4)

    p = sub.add_parser("publish", help="upload the corpus to public object storage (maintainer)")
    p.add_argument("--apply", action="store_true", help="actually upload; default is a dry run")
    p.add_argument("--manifest-only", action="store_true")

    args = ap.parse_args(argv)
    init_workspace()

    if args.cmd == "manifest":
        from .manifest import build_manifest
        recs = build_manifest()
        not_fetched = [r for r in recs if r.get("processing_state") == "not-fetched"]
        absent = [r for r in recs if r.get("processing_state") == "absent-from-disk"]
        _print({"files": len(recs),
                "inspected": len(recs) - len(not_fetched) - len(absent),
                "not_fetched": len(not_fetched),
                "absent_from_disk": len(absent)})
        if not_fetched:
            print(f"WARNING: {len(not_fetched)} of {len(recs)} corpus files are "
                  f"unsmudged Git LFS pointers and were recorded as 'not-fetched' "
                  f"rather than inspected.\n"
                  f"         Fetch them, then re-run this command: {FETCH_HINT}",
                  file=sys.stderr)
    elif args.cmd == "ingest":
        from .ingest import ingest
        from .pilot import PILOT_PATHS
        if args.pilot:
            paths, name = PILOT_PATHS, "pilot-ingestion"
        elif args.path:
            paths, name = args.path, "adhoc-ingestion"
        elif args.all:
            paths, name = None, "full-ingestion"
        else:
            ap.error("choose --pilot, --all or --path")
        res = ingest(paths, workers=args.workers, force=args.force, log_name=name)
        _print(res["summary"])
        # A run that extracted nothing because the corpus is not on disk is not
        # a successful run, and must not exit 0 into a CI script.
        if res["summary"]["failed"] or res["summary"]["not_fetched"]:
            return 1
    elif args.cmd == "search":
        from .retrieval import search_evidence
        filters = {}
        for key, val in (("manufacturer", args.manufacturer), ("doc_type", args.doc_type),
                         ("version_status", args.version_status),
                         ("element_type", args.element_type)):
            if val:
                filters[key] = val
        results = search_evidence(args.query, limit=args.limit, filters=filters or None,
                                  second_stage=args.second_stage)
        out = []
        for r in results:
            d = r.to_dict()
            if not args.full:
                d["text"] = d["text"][:400]
            out.append(d)
        _print(out)
    elif args.cmd == "document":
        from .retrieval import get_document
        _print(get_document(args.identifier))
    elif args.cmd == "page":
        from .retrieval import get_page
        _print(get_page(args.document_id, args.page_no))
    elif args.cmd == "region":
        from .retrieval import get_region
        _print(get_region(args.element_id))
    elif args.cmd == "context":
        from .retrieval import get_element_context
        _print(get_element_context(args.element_id, before=args.before, after=args.after))
    elif args.cmd == "resolve":
        from .retrieval import resolve_document_version
        _print(resolve_document_version(args.identifier, at=args.at, as_of=args.as_of))
    elif args.cmd == "facts":
        from .facts import extract_facts, query_facts
        if args.extract:
            result = extract_facts()
            from .reports import facts_report
            from .store import connect
            from .paths import REPORTS_DIR, open_write
            conn = connect()
            try:
                body = facts_report(conn)
            finally:
                conn.close()
            with open_write(REPORTS_DIR / "facts-report.md") as f:
                f.write(body)
            _print(result)
        else:
            _print(query_facts(args.type, manufacturer=args.manufacturer, limit=args.limit))
    elif args.cmd == "evaluate":
        _warn_unfetched()
        from .evaluate import run_evaluation
        _print(run_evaluation(k=args.k, second_stage=args.second_stage,
                              report_name=args.name)["summary"])
    elif args.cmd == "audit":
        _warn_unfetched()
        from .audit import run_audit
        _print(run_audit(k=args.k))
    elif args.cmd == "table-review":
        from pathlib import Path as _P
        from . import table_review as tr
        from .store import connect as _c
        conn = _c()
        out = {}
        if args.load_dir:
            out["loaded"] = tr.load_directory(conn, _P(args.load_dir))
        if args.mark_agreed:
            out["marked_agent_verified"] = tr.mark_agent_verified(conn, tuple(args.mark_agreed))
        if args.agreement:
            out["agreement"] = tr.agreement(conn, tuple(args.agreement))
        if args.compare_pipeline:
            out["vs_pipeline"] = tr.compare_with_pipeline(conn, reader=args.reader)
        out["summary"] = tr.summary(conn)
        conn.close()
        _print(out)
    elif args.cmd == "promote-tables":
        if args.revoke:
            from .promote_tables import revoke_machine_promotions
            _print(revoke_machine_promotions(dry_run=not args.apply))
        else:
            from .promote_tables import promote_verified
            _print(promote_verified(dry_run=not args.apply))
    elif args.cmd == "snapshot":
        from .snapshot import build_snapshot
        from .snapshot_store import get_snapshot, list_snapshots, put_snapshot
        # G39. Two defects, one guard. `--build` and `--dry-run` were
        # independent store_true flags and only `--build` gated storage, so
        # `--build --dry-run` stored anyway -- the single combination whose
        # entire purpose is that it must not, against a write-once store with
        # no delete. And a bare `snapshot` printed an error and exited 0, the
        # vacuous-green class the refs branch below already refuses. Both are
        # usage errors; both exit 2, matching refs and argparse's convention.
        # Requiring exactly one mode makes the storage gate below sound: with
        # --build and --dry-run exclusive, `if args.build` can no longer fire
        # on a run the caller asked to be dry.
        modes = (bool(args.build), bool(args.dry_run), bool(args.list),
                 args.get is not None, bool(args.verify_stored))
        if sum(modes) != 1:
            _print({"error": "choose one of --build, --dry-run, --list, --get, "
                             "--verify-stored"})
            return 2
        if args.verify_stored:
            from .snapshot_store import verify_stored
            res = verify_stored()
            _print(res)
            if res["failed"] or res["unreadable"]:
                # Same convention as `refs --verify`: a guard that reports a
                # failure on stdout and exits 0 is the vacuous-green class.
                print(f"FAILED: {res['failed']} stored snapshot(s) do not meet "
                      f"the obligations they were published under.",
                      file=sys.stderr)
                return 1
            return 0
        if args.get:
            _print(get_snapshot(args.get))
        elif args.list:
            _print(list_snapshots())
        else:
            snap = build_snapshot(tenant=args.tenant, regime=args.regime)
            summary = {"snapshot_id": snap["snapshot_id"],
                       "tenant": snap["tenant"], "regime": snap["regime"],
                       "retain_until": snap["retain_until"],
                       "source_docs": len(snap["source_docs"]),
                       "warnings": len(snap["warnings"]),
                       "gaps": len(snap["gaps"]),
                       "stored": False}
            if args.build:
                put_snapshot(snap)
                summary["stored"] = True
            _print(summary)
    elif args.cmd == "review":
        # Same shape as snapshot's and refs' guards: require exactly one mode and
        # exit 2 on a usage error rather than printing an error and exiting 0.
        # Checked before the imports, so a usage error does not depend on a
        # module being importable.
        modes = (bool(args.queue), args.accept is not None, bool(args.rebuild))
        if sum(modes) != 1:
            _print({"error": "choose one of --queue, --accept, --rebuild"})
            return 2
        import json as _json
        from pathlib import Path as _P
        from . import reviews
        from .store import connect as _c
        conn = _c()
        try:
            if args.queue:
                _print({"queue": reviews.review_queue(conn),
                        "summary": reviews.review_summary(conn)})
            elif args.rebuild:
                _print(reviews.rebuild_projection(conn))
            else:
                if not args.reviewer:
                    _print({"error": "--accept requires --reviewer: the name is the "
                                     "only thing separating 'software read this' "
                                     "from 'a person confirmed it'"})
                    return 2
                load = lambda f: _json.loads(_P(f).read_text()) if f else []
                try:
                    _print(reviews.submit_review(
                        conn, crop_sha256=args.accept, reviewer=args.reviewer,
                        verdict=args.verdict, grid=load(args.grid),
                        spans=load(args.spans), notes=args.notes))
                except reviews.ReviewRefused as e:
                    _print({"error": e.code, "message": str(e)})
                    return 1
        finally:
            conn.close()
    elif args.cmd == "serve":
        import os
        from . import api
        tokens = set(args.token) or {
            t.strip() for t in os.environ.get("FENCE_API_TOKENS", "").split(",")
            if t.strip()}
        if not tokens:
            # An open write endpoint is worse than no endpoint. contract.md 1.5's
            # Authoring surface is proxied from one backend, never a browser.
            _print({"error": "no bearer token configured; pass --token or set "
                             "FENCE_API_TOKENS"})
            return 2
        print(f"serving on {args.host}:{args.port} "
              f"({len(tokens)} token(s) on the allowlist)", file=sys.stderr)
        api.serve(args.host, args.port, tokens=tokens)
    elif args.cmd == "realign-review-crops":
        from .cropcache import realign_review_crops
        from .store import connect as _c
        conn = _c()
        try:
            _print(realign_review_crops(conn, dry_run=not args.apply))
        finally:
            conn.close()
    elif args.cmd == "backfill-spans":
        from .tables import backfill_spans
        from .store import connect as _c
        conn = _c()
        try:
            _print(backfill_spans(conn, dry_run=not args.apply))
        finally:
            conn.close()
    elif args.cmd == "refs":
        from .refs import build_index, verify_snapshots
        from .store import connect
        # Require a choice and refuse to silently resolve the combination,
        # rather than the previous `if args.verify: ... else:
        # build_index(...)`, under which a bare `cli refs` silently rebuilt
        # the index and `--verify --index` silently ignored `--index`. For a
        # CI guard, an error on stdout with a green exit is the vacuous-green
        # failure class refs --verify exists to close, so this exits 2 --
        # argparse's own convention for a usage error, distinct from 1 ("the
        # guard fired"). See G39 in docs/state-and-gaps.md. The snapshot
        # branch above was the sibling that still fell through to exit 0 on
        # this same class; it no longer does, and both now agree.
        if args.verify == args.index:
            _print({"error": "choose one of --verify, --index"})
            return 2
        conn = connect(read_only=True)
        try:
            if args.verify:
                result = verify_snapshots(conn)
                _print(result)
                if result["snapshots"] == 0 and result["tombstoned_skipped"] == 0:
                    print("FAILED: nothing was verified -- 0 snapshots found "
                          "(0 tombstoned, 0 live) under workspace/snapshots/. "
                          "A green exit here would mean zero citations were "
                          "checked, not that they resolved; that is not a "
                          "pass.", file=sys.stderr)
                    return 1
                # unknown_versions is the distinguishing signal: a dangling
                # cite whose belongs_to names a version this store does not
                # have at all means the store is incomplete (e.g. built from
                # `cli ingest --pilot`), not that the citation rotted. A
                # dangling cite whose version IS present, and no longer
                # resolves anyway, is genuine, irreparable rot. Conflating
                # the two turns a routine partial-store run into an alarming
                # and wrong "cannot be repaired" diagnosis.
                unknown_ref_ids = {u["ref_id"] for u in result["unknown_versions"]}
                rot = [d for d in result["dangling"]
                      if d["ref_id"] not in unknown_ref_ids]
                failed = False
                if result["unreadable"]:
                    names = ", ".join(u["file"] for u in result["unreadable"])
                    print(f"FAILED: {len(result['unreadable'])} snapshot "
                          f"file(s) under workspace/snapshots/ could not be "
                          f"parsed, and were skipped rather than verified: "
                          f"{names}.", file=sys.stderr)
                    failed = True
                if rot:
                    print(f"FAILED: {len(rot)} published citation(s) no "
                          f"longer resolve, and the document version they "
                          f"name IS present in this store -- genuine rot. A "
                          f"snapshot is immutable, so this cannot be "
                          f"repaired -- see docs/four-layer-model-design.md "
                          f"5.1.", file=sys.stderr)
                    failed = True
                if result["unknown_versions"]:
                    print(f"FAILED: {len(result['unknown_versions'])} "
                          f"published citation(s) name a document version "
                          f"this store does not have at all. That is almost "
                          f"always an incomplete store, not rot -- run `cli "
                          f"fetch` and `cli ingest --all`, then re-run `cli "
                          f"refs --verify`.", file=sys.stderr)
                    failed = True
                if result["mismatched_owner"]:
                    print(f"FAILED: {len(result['mismatched_owner'])} "
                          f"published citation(s) resolve to a different "
                          f"document version's evidence than they claim. A "
                          f"snapshot is immutable, so this cannot be "
                          f"repaired -- see docs/four-layer-model-design.md "
                          f"5.1.", file=sys.stderr)
                    failed = True
                if failed:
                    return 1
            else:
                index = build_index(conn)
                shared = [l for l in index.values() if len(l.element_ids) > 1]
                _print({"ref_ids": len(index),
                        "page_refs": sum(1 for l in index.values() if l.is_page),
                        "ids_covering_multiple_elements": len(shared)})
        finally:
            conn.close()
    elif args.cmd == "dataset":
        from .dataset import DatasetChanged, verify_dataset, write_digests
        if args.write:
            _print({"baseline": str(write_digests())})
        else:
            try:
                _print(verify_dataset())
            except DatasetChanged as exc:
                print(str(exc))
                return 1
    elif args.cmd == "migrate":
        from .store import (backfill_lang, connect as _c, migrate as _m,
                            SCHEMA_VERSION)
        conn = _c()
        try:
            result = _m(conn)
            _print({"schema_version": SCHEMA_VERSION,
                    "columns_added": result["added"],
                    "columns_retired": result["retired"],
                    "lang": backfill_lang(conn)})
        finally:
            conn.close()
    elif args.cmd == "worklist":
        from .worklist import build
        _print(build())
    elif args.cmd == "noa-table-crops":
        from .noa_tables import export_crops
        _print(export_crops())
    elif args.cmd == "rebuild-index":
        from .store import build_retrieval_units, connect
        conn = connect()
        _print({"retrieval_units": build_retrieval_units(conn)})
        conn.close()
    elif args.cmd == "stats":
        from .store import connect, stats
        conn = connect()
        _print(stats(conn))
        conn.close()
    elif args.cmd == "report":
        from .reports import write_all_reports
        _print(write_all_reports())
    elif args.cmd == "fetch":
        from .fetch import fetch_subset, load_remote_manifest
        from .paths import REPO_ROOT
        manifest = load_remote_manifest(args.manifest_url)
        result = fetch_subset(manifest, args.subset, REPO_ROOT, workers=args.workers)
        _print(result)
        if result.get("downloaded") or result.get("copied"):
            # The index still holds each file's stat data from when it was a
            # 131-byte pointer, so `git status` calls every fetched file
            # modified even though `git diff` is empty. Say so here: the
            # obvious tidy-up -- `git checkout .` -- would revert the corpus
            # back to pointers.
            print("note: `git status` will list the fetched files as modified "
                  "until you run\n      `git add --renormalize .` -- their "
                  "content is correct and `git diff` is\n      already empty. "
                  "Do NOT `git checkout` them; that restores the pointers.",
                  file=sys.stderr)
        if result.get("failed"):
            return 1
    elif args.cmd == "publish":
        from .config import load_env, R2Config
        from .distribution import build_manifest, load_corpus_manifest
        from .publish import publish_objects, publish_manifest
        from datetime import datetime, timezone
        cfg = R2Config.from_env(load_env())
        rows = load_corpus_manifest()
        manifest = build_manifest(
            rows, cfg.public_base_url,
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        out = {"config": cfg.redacted(),
               "manifest": publish_manifest(cfg, manifest, dry_run=not args.apply)}
        if not args.manifest_only:
            out["objects"] = publish_objects(cfg, rows, dry_run=not args.apply)
        _print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
