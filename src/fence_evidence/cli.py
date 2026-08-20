"""Command line interface: python3 -m fence_evidence.cli <command>"""
from __future__ import annotations

import argparse
import json
import sys

from .paths import init_workspace


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


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
    p.add_argument("--at", help="ISO date")

    p = sub.add_parser("facts", help="Phase 6: extract or query structured facts")
    p.add_argument("--extract", action="store_true")
    p.add_argument("--type")
    p.add_argument("--manufacturer")
    p.add_argument("--limit", type=int, default=20)

    p = sub.add_parser("evaluate", help="Phase 4: run the gold evaluation set")
    p.add_argument("-k", type=int, default=10)

    sub.add_parser("rebuild-index", help="rebuild the retrieval projection from canonical rows")
    sub.add_parser("stats", help="store statistics")
    sub.add_parser("report", help="regenerate the workspace reports")

    args = ap.parse_args(argv)
    init_workspace()

    if args.cmd == "manifest":
        from .manifest import build_manifest
        recs = build_manifest()
        _print({"files": len(recs)})
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
    elif args.cmd == "search":
        from .retrieval import search_evidence
        filters = {}
        for key, val in (("manufacturer", args.manufacturer), ("doc_type", args.doc_type),
                         ("version_status", args.version_status),
                         ("element_type", args.element_type)):
            if val:
                filters[key] = val
        results = search_evidence(args.query, limit=args.limit, filters=filters or None)
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
        _print(resolve_document_version(args.identifier, at=args.at))
    elif args.cmd == "facts":
        from .facts import extract_facts, query_facts
        if args.extract:
            _print(extract_facts())
        else:
            _print(query_facts(args.type, manufacturer=args.manufacturer, limit=args.limit))
    elif args.cmd == "evaluate":
        from .evaluate import run_evaluation
        _print(run_evaluation(k=args.k)["summary"])
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
