"""Phase 4 — the evaluation gate.

Runs the annotated gold questions against the retrieval layer and reports
failures *by category*, which is what decides whether extraction needs fixing
before ranking work begins, and which Phase 7 experiment (if any) is justified.
"""
from __future__ import annotations

import json
import re
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from .paths import REPO_ROOT, REPORTS_DIR, TESTS_DIR, open_write
from .retrieval import search_evidence
from .store import connect

DEFAULT_K = 10
# Below this BM25-derived relevance a hit is reported as unsupported rather
# than as an answer; calibrated against the no_answer questions.
NO_ANSWER_SCORE_FLOOR = 6.0


def load_gold(paths: list[Path] | None = None) -> list[dict]:
    paths = paths or sorted((REPO_ROOT / "eval").glob("gold-questions-*.json"))
    questions: list[dict] = []
    for p in paths:
        with open(p) as f:
            data = json.load(f)
        for q in data.get("questions", []):
            q["_set"] = data.get("set", p.stem)
            questions.append(q)
    return questions


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).lower()


def _query_for(q: dict) -> str:
    terms = q.get("query_terms") or []
    if terms:
        return " ".join(terms) if isinstance(terms, list) else str(terms)
    return q["question"]


def _equivalent_paths(conn, paths: set[str]) -> set[str]:
    """Expand expected paths with byte-identical copies of the same document.

    The corpus files the same NOA under several manufacturer directories; a
    retrieval that returns one copy has found the right evidence, so the grader
    must not mark it wrong for choosing a different path to identical bytes.
    """
    if not conn or not paths:
        return set(paths)
    out = set(paths)
    for path in list(paths):
        rows = conn.execute("""SELECT d2.source_path AS p
              FROM documents d1
              JOIN relations r ON r.from_document_id = d1.document_id
              JOIN documents d2 ON d2.document_id = r.to_document_id
             WHERE d1.source_path = ? AND r.relation_type = 'same_content_as'""",
                            (path,)).fetchall()
        out.update(r["p"] for r in rows)
    return out


def evaluate_question(q: dict, *, k: int = DEFAULT_K, conn=None) -> dict:
    query = _query_for(q)
    results = search_evidence(query, limit=k, conn=conn)
    declared_docs = set(q.get("expected_documents") or [])
    expected_docs = _equivalent_paths(conn, declared_docs)
    expected_pages: dict[str, list[int]] = dict(q.get("expected_pages") or {})
    # a duplicate copy carries the same page numbers as the path it duplicates
    for declared, pages in list(expected_pages.items()):
        for equivalent in expected_docs - declared_docs:
            expected_pages.setdefault(equivalent, pages)
    terms = [t for t in (q.get("expected_answer_terms") or []) if t]

    hit_paths = [r.source_path for r in results]
    doc_rank = next((i + 1 for i, p in enumerate(hit_paths) if p in expected_docs), None)
    page_rank = None
    for i, r in enumerate(results):
        wanted = expected_pages.get(r.source_path)
        if wanted and r.page in wanted:
            page_rank = i + 1
            break

    joined = "\n".join(_norm(r.text) for r in results)
    found_terms = [t for t in terms if _norm(t) in joined]
    support = (len(found_terms) / len(terms)) if terms else None

    type_ok = None
    want_type = q.get("expected_element_type")
    if want_type and want_type != "any":
        type_ok = any(r.element_type == want_type or
                      (want_type in ("figure", "drawing") and
                       r.element_type in ("figure", "drawing", "drawing_label"))
                      for r in results if r.source_path in expected_docs)

    image_ok = None
    if q.get("expects_image_evidence"):
        image_ok = any((r.page_image_path and (REPO_ROOT / r.page_image_path).is_file())
                       for r in results if r.source_path in expected_docs)

    top_score = results[0].score if results else 0.0
    answerable = q.get("answerable", True)
    if answerable:
        passed = doc_rank is not None and (support is None or support >= 0.5)
    else:
        passed = top_score < NO_ANSWER_SCORE_FLOOR

    return {
        "id": q.get("id"), "category": q.get("category"), "set": q.get("_set"),
        "question": q.get("question"), "query": query, "answerable": answerable,
        "n_results": len(results),
        "doc_rank": doc_rank, "page_rank": page_rank,
        "expected_documents": sorted(declared_docs),
        "equivalent_documents": sorted(expected_docs - declared_docs),
        "support": None if support is None else round(support, 3),
        "found_terms": found_terms,
        "missing_terms": [t for t in terms if t not in found_terms],
        "element_type_ok": type_ok, "image_evidence_ok": image_ok,
        "top_score": round(top_score, 3),
        "passed": passed,
        "top_hits": [{"source_path": r.source_path, "page": r.page,
                      "element_type": r.element_type, "score": r.score,
                      "matched_terms": r.retrieval_reason.get("matched_terms", []),
                      "snippet": r.snippet[:220]} for r in results[:3]],
    }


def run_evaluation(*, k: int = DEFAULT_K, gold_paths: list[Path] | None = None) -> dict:
    questions = load_gold(gold_paths)
    if not questions:
        raise SystemExit("no gold questions found in eval/gold-questions-*.json")
    conn = connect()
    try:
        rows = [evaluate_question(q, k=k, conn=conn) for q in questions]
    finally:
        conn.close()

    answerable = [r for r in rows if r["answerable"]]
    unanswerable = [r for r in rows if not r["answerable"]]
    supports = [r["support"] for r in answerable if r["support"] is not None]
    recall = (sum(1 for r in answerable if r["doc_rank"]) / len(answerable)) if answerable else 0.0
    page_recall = (sum(1 for r in answerable if r["page_rank"]) / len(answerable)) if answerable else 0.0
    mrr = (statistics.mean([1 / r["doc_rank"] if r["doc_rank"] else 0.0 for r in answerable])
           if answerable else 0.0)

    by_cat: dict[str, dict] = defaultdict(lambda: {"n": 0, "doc_hits": 0, "passed": 0,
                                                   "support": [], "failures": []})
    for r in rows:
        c = by_cat[r["category"] or "uncategorised"]
        c["n"] += 1
        c["doc_hits"] += 1 if r["doc_rank"] else 0
        c["passed"] += 1 if r["passed"] else 0
        if r["support"] is not None:
            c["support"].append(r["support"])
        if not r["passed"]:
            c["failures"].append(r["id"])
    for c in by_cat.values():
        c["mean_support"] = round(statistics.mean(c["support"]), 3) if c["support"] else None
        c.pop("support")

    summary = {
        "k": k,
        "questions": len(rows),
        "answerable": len(answerable),
        "no_answer": len(unanswerable),
        "recall_at_k": round(recall, 3),
        "page_recall_at_k": round(page_recall, 3),
        "mrr": round(mrr, 3),
        "evidence_support": round(statistics.mean(supports), 3) if supports else None,
        "no_answer_precision": round(
            sum(1 for r in unanswerable if r["passed"]) / len(unanswerable), 3)
        if unanswerable else None,
        "passed": sum(1 for r in rows if r["passed"]),
        "by_category": {k2: v for k2, v in sorted(by_cat.items())},
        "acceptance": {},
    }
    summary["acceptance"] = {
        "A3_recall_at_10_ge_0.80": summary["recall_at_k"] >= 0.80,
        "A3_evidence_support_ge_0.70": (summary["evidence_support"] or 0) >= 0.70,
        "A4_no_answer_precision_ge_0.66": (summary["no_answer_precision"] or 0) >= 0.66,
    }
    out = {"summary": summary, "results": rows}
    with open_write(TESTS_DIR / "evaluation-results.json") as f:
        json.dump(out, f, indent=2)
    _write_report(out)
    return out


def _write_report(out: dict) -> None:
    s = out["summary"]
    lines = [
        "# Evaluation report — gold question set",
        "",
        f"Questions: **{s['questions']}** ({s['answerable']} answerable, "
        f"{s['no_answer']} no-answer) · k = {s['k']}",
        "",
        "| Metric | Value | Acceptance |",
        "|---|---|---|",
        f"| Document recall@{s['k']} | {s['recall_at_k']:.3f} | A3 ≥ 0.80 — "
        f"{'PASS' if s['acceptance']['A3_recall_at_10_ge_0.80'] else 'FAIL'} |",
        f"| Page recall@{s['k']} | {s['page_recall_at_k']:.3f} | reported |",
        f"| MRR | {s['mrr']:.3f} | reported |",
        f"| Evidence support | {s['evidence_support']} | A3 ≥ 0.70 — "
        f"{'PASS' if s['acceptance']['A3_evidence_support_ge_0.70'] else 'FAIL'} |",
        f"| No-answer precision | {s['no_answer_precision']} | A4 ≥ 0.66 — "
        f"{'PASS' if s['acceptance']['A4_no_answer_precision_ge_0.66'] else 'FAIL'} |",
        "",
        "## By category",
        "",
        "| Category | n | doc hits | passed | mean support | failing ids |",
        "|---|---|---|---|---|---|",
    ]
    for cat, c in s["by_category"].items():
        lines.append(f"| {cat} | {c['n']} | {c['doc_hits']} | {c['passed']} | "
                     f"{c['mean_support']} | {', '.join(c['failures']) or '—'} |")
    lines += ["", "## Failures in detail", ""]
    for r in out["results"]:
        if r["passed"]:
            continue
        lines += [
            f"### {r['id']} — {r['category']}",
            f"*{r['question']}*",
            "",
            f"- query: `{r['query']}`",
            f"- expected: {', '.join(r['expected_documents']) or '(nothing — no-answer question)'}",
            f"- doc rank: {r['doc_rank']} · support: {r['support']} · "
            f"missing terms: {r['missing_terms']}",
            f"- top hit: {r['top_hits'][0]['source_path'] + ' p' + str(r['top_hits'][0]['page']) if r['top_hits'] else '(no results)'}"
            f" score {r['top_hits'][0]['score'] if r['top_hits'] else 0}",
            "",
        ]
    with open_write(REPORTS_DIR / "evaluation-report.md") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("-k", type=int, default=DEFAULT_K)
    args = ap.parse_args()
    out = run_evaluation(k=args.k)
    print(json.dumps(out["summary"], indent=2)[:3000])
