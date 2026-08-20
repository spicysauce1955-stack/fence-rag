"""Phase 4 — the evaluation gate.

Runs the annotated gold questions against the retrieval layer and reports
failures *by category*, which is what decides whether extraction needs fixing
before ranking work begins, and which Phase 7 experiment (if any) is justified.
"""
from __future__ import annotations

import json
import re
import sqlite3
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from .paths import REPO_ROOT, REPORTS_DIR, TESTS_DIR, open_write
from .retrieval import (STOPWORDS, UNIT_WORDS, build_match_expression,
                        search_evidence)
from .store import connect

DEFAULT_K = 10
# Relevance floor below which a result is reported as unsupported rather than as
# an answer.  Calibrated on the pilot: the three no-answer questions topped out
# at 12.2-14.2 while every answerable question scored >=20.0.  Three negatives
# is a thin basis, so this is a reported, tunable threshold rather than a claim
# about the corpus, and it is re-checked in the full-corpus evaluation.
NO_ANSWER_SCORE_FLOOR = 17.0


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


_TYPOGRAPHIC = {
    "\u201c": '"', "\u201d": '"', "\u2033": '"', "\u2032": "'",
    "\u2018": "'", "\u2019": "'", "\u2013": "-", "\u2014": "-",
    "\u00a0": " ", "\u2212": "-",
}


def _norm(s: str) -> str:
    """Normalise for term matching.

    Sources use typographic quotes for inches (8\u201d) while extraction and the
    annotations disagree about which glyph they use, so a literal substring test
    fails on the punctuation rather than on the content. Folding those to ASCII
    compares the words and numbers, which is what the metric is about.
    """
    s = s or ""
    for a, b in _TYPOGRAPHIC.items():
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).lower()


def _returned_evidence(r) -> str:
    """Everything the search result actually hands back to the caller.

    The response contract returns `heading_path` and `caption` alongside `text`,
    and section headings are where product names live in these documents, so
    support is measured against the whole returned record rather than one field.
    """
    parts = [r.text or "", " > ".join(r.heading_path or [])]
    for extra in (getattr(r, "within_page_evidence", None) or []):
        parts.append(extra.get("text") or "")
        parts.append(" > ".join(extra.get("heading_path") or []))
    return _norm("\n".join(parts))


def _document_frequency(conn, term: str) -> int:
    if conn is None:
        return -1
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM retrieval_fts WHERE retrieval_fts MATCH ?",
            ('"' + term.replace('"', '""') + '"',)).fetchone()
        return int(row[0]) if row else 0
    except sqlite3.Error:
        return -1


def _looks_unsupported(query: str, results, conn) -> tuple[bool, str]:
    """Decide whether the corpus actually answers this question.

    Calibrated against 18 negative questions (up from 3), deliberately including
    five "near-miss" cases — the corpus covers the topic and the product but
    never states the asked-for value — and five "adjacent-vocabulary" cases where
    every word occurs, often on one page.

    Measured on that set, no lexical feature separates answerable from
    unanswerable questions. Mean values, answerable vs unanswerable: rarest term
    present in the best result 0.244 vs 0.444 (*wrong* direction), term coverage
    0.733 vs 0.747, score margin 0.248 vs 0.294, top relevance 22.3 vs 20.5. That
    is a property of the question classes, not a tuning failure: a near-miss
    question is one whose words are all present.

    An earlier rule combined a score floor with rarest-term presence and reached
    0.611 precision — while flagging 24 of 41 *answerable* questions as
    unsupported. A verdict that fires on half of all real questions is worse than
    no verdict, so those signals were removed.

    What remains fires only for a reason a reader can check: the query contains a
    word the corpus does not contain anywhere, or there are no results at all.
    Everything else is reported as a continuous coverage number rather than a
    verdict.
    """
    if not results:
        return True, "no results"
    _expr, sources = build_match_expression(query)
    terms = []
    for raw in sources:
        t = raw.strip("\"'").lower()
        if len(t) < 3 or t in STOPWORDS or t in UNIT_WORDS or t in terms:
            continue
        terms.append(t)
    if not terms:
        return True, "query carries no content terms"
    absent = [t for t in terms if _document_frequency(conn, t) == 0]
    if absent:
        return True, f"term(s) absent from the whole corpus: {', '.join(absent[:4])}"
    return False, ""


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


def evaluate_question(q: dict, *, k: int = DEFAULT_K, conn=None,
                      second_stage: bool = False) -> dict:
    query = _query_for(q)
    results = search_evidence(query, limit=k, conn=conn, second_stage=second_stage)
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

    joined = "\n".join(_returned_evidence(r) for r in results)
    found_terms = [t for t in terms if _norm(t) in joined]
    support = (len(found_terms) / len(terms)) if terms else None

    # Strict support asks whether the retrieved *unit* carries the answer terms.
    # Page support asks the weaker but still useful question: did the system put
    # the reader in front of the page that carries them?  Both are reported; the
    # acceptance gate uses the strict one.
    page_support = support
    if terms and conn is not None:
        page_text_parts = []
        for r in results:
            for row in conn.execute(
                    """SELECT e.text, e.ocr_text FROM elements e
                        WHERE e.document_id=? AND e.page_no=?""",
                    (r.document_id, r.page)):
                page_text_parts.append(_norm((row["text"] or "") + " " + (row["ocr_text"] or "")))
        page_joined = "\n".join(page_text_parts)
        page_found = [t for t in terms if _norm(t) in page_joined]
        page_support = len(page_found) / len(terms)

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
    unsupported, why_unsupported = _looks_unsupported(query, results, conn)
    attached = sum(1 for r in results
                   if r.retrieval_reason.get("second_stage", {}).get("attached"))
    if answerable:
        passed = doc_rank is not None and (support is None or support >= 0.5)
    else:
        passed = unsupported

    return {
        "id": q.get("id"), "category": q.get("category"), "set": q.get("_set"),
        "question": q.get("question"), "query": query, "answerable": answerable,
        "n_results": len(results),
        "doc_rank": doc_rank, "page_rank": page_rank,
        "expected_documents": sorted(declared_docs),
        "equivalent_documents": sorted(expected_docs - declared_docs),
        "support": None if support is None else round(support, 3),
        "page_support": None if page_support is None else round(page_support, 3),
        "found_terms": found_terms,
        "missing_terms": [t for t in terms if t not in found_terms],
        "element_type_ok": type_ok, "image_evidence_ok": image_ok,
        "top_score": round(top_score, 3),
        "second_stage_attachments": attached,
        "element_types": [r.element_type for r in results],
        "reported_unsupported": unsupported,
        "unsupported_reason": why_unsupported,
        "passed": passed,
        "top_hits": [{"source_path": r.source_path, "page": r.page,
                      "element_type": r.element_type, "score": r.score,
                      "matched_terms": r.retrieval_reason.get("matched_terms", []),
                      "snippet": r.snippet[:220]} for r in results[:3]],
    }


def run_evaluation(*, k: int = DEFAULT_K, gold_paths: list[Path] | None = None,
                   only_ingested: bool = False, report_name: str = "evaluation",
                   second_stage: bool = False) -> dict:
    """Run the gold set.

    ``only_ingested`` restricts the run to questions whose expected documents are
    all present in the store, which is what makes the Phase 4 gate meaningful
    against the ten-document pilot before the full corpus is processed.
    """
    questions = load_gold(gold_paths)
    if not questions:
        raise SystemExit("no gold questions found in eval/gold-questions-*.json")
    conn = connect()
    skipped: list[str] = []
    try:
        if only_ingested:
            present = {r[0] for r in conn.execute("SELECT source_path FROM documents")}
            kept = []
            for q in questions:
                docs = set(q.get("expected_documents") or [])
                if docs and not docs & present:
                    skipped.append(q["id"])
                    continue
                kept.append(q)
            questions = kept
        rows = [evaluate_question(q, k=k, conn=conn, second_stage=second_stage)
                for q in questions]
    finally:
        conn.close()

    answerable = [r for r in rows if r["answerable"]]
    unanswerable = [r for r in rows if not r["answerable"]]
    supports = [r["support"] for r in answerable if r["support"] is not None]
    page_supports = [r["page_support"] for r in answerable if r["page_support"] is not None]
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

    false_unsupported = [r for r in answerable if r["reported_unsupported"]]
    summary = {
        "k": k,
        "questions": len(rows),
        "answerable": len(answerable),
        "no_answer": len(unanswerable),
        "recall_at_k": round(recall, 3),
        "page_recall_at_k": round(page_recall, 3),
        "mrr": round(mrr, 3),
        "evidence_support": round(statistics.mean(supports), 3) if supports else None,
        "page_evidence_support": round(statistics.mean(page_supports), 3) if page_supports else None,
        "no_answer_precision": round(
            sum(1 for r in unanswerable if r["passed"]) / len(unanswerable), 3)
        if unanswerable else None,
        # The other half of the picture. A detector can reach high no-answer
        # precision by declaring almost everything unsupported, so the two are
        # always reported together.
        "false_unsupported_rate": round(len(false_unsupported) / len(answerable), 3)
        if answerable else None,
        "false_unsupported_ids": [r["id"] for r in false_unsupported],
        "passed": sum(1 for r in rows if r["passed"]),
        "by_category": {k2: v for k2, v in sorted(by_cat.items())},
        "skipped_not_ingested": skipped,
        "second_stage": second_stage,
        "second_stage_attachments": sum(r.get("second_stage_attachments") or 0 for r in rows),
        "acceptance": {},
    }
    summary["acceptance"] = {
        "A3_recall_at_10_ge_0.80": summary["recall_at_k"] >= 0.80,
        "A3_evidence_support_ge_0.70": (summary["evidence_support"] or 0) >= 0.70,
        "A4_no_answer_precision_ge_0.66": (summary["no_answer_precision"] or 0) >= 0.66,
        "A4b_false_unsupported_le_0.20": (summary["false_unsupported_rate"] or 1.0) <= 0.20,
    }
    out = {"summary": summary, "results": rows}
    with open_write(TESTS_DIR / f"{report_name}-results.json") as f:
        json.dump(out, f, indent=2)
    _write_report(out, report_name)
    return out


# Which Phase 7 experiment a measured failure category would justify.  Nothing
# here is implemented: the guide requires a triggering failure and a stated
# acceptance criterion before an enhancement is built.
PHASE7_TRIGGERS = {
    "paraphrase": (
        "Dense semantic retrieval over the pilot corpus",
        "Improves recall@10 on paraphrase questions by >=0.15 without reducing "
        "recall on exact_identifier or conditional_table_lookup."),
    "visual_evidence": (
        "Visual/page-level retrieval for drawing-heavy documents",
        "Improves recall@10 on visual_evidence questions without reducing lexical "
        "recall elsewhere."),
    "conditional_table_lookup": (
        "Table-aware structured lookup keyed on conditions (wind speed, exposure, "
        "height) resolved against table_cells and facts",
        "Answers the conditional questions with the correct cell, and returns "
        "'outside documented range' rather than a nearest-neighbour value."),
    "table_retrieval": (
        "Field-boosted lexical retrieval that ranks table units above prose when "
        "the query asks for a table",
        "Improves table_retrieval recall@10 without reducing overall recall."),
    "no_answer": (
        "Rarest-term coverage plus a calibrated score floor, reported as an "
        "explicit unsupported-answer response",
        "No-answer precision >=0.66 with no loss of answerable recall."),
    "historical_version": (
        "Version-aware ranking that prefers the member of a supersession chain the "
        "question asks for",
        "Historical questions resolve to the superseded document and current "
        "questions to the active one."),
    "conflict": (
        "Conflict surfacing: return every source that states a value for the same "
        "condition, with its version status",
        "Both conflicting sources appear in the top 10 with their statuses."),
}


def _phase7_section(out: dict) -> list[str]:
    s = out["summary"]
    lines = ["## Phase 7 — experiments this evaluation would justify", "",
             "Only categories that actually failed appear here. Nothing below is built.",
             ""]
    justified = [(cat, c) for cat, c in s["by_category"].items()
                 if c["passed"] < c["n"] and cat in PHASE7_TRIGGERS]
    if not justified:
        lines += ["No failure category reaches the bar for an enhancement; lexical "
                  "retrieval is sufficient for every category measured.", ""]
        return lines
    for cat, c in justified:
        experiment, acceptance = PHASE7_TRIGGERS[cat]
        lines += [f"### {cat} — {c['n'] - c['passed']} of {c['n']} failing", "",
                  f"- **Problem**: {cat} questions fail lexical retrieval "
                  f"(failing ids: {', '.join(c['failures'])}).",
                  f"- **Experiment**: {experiment}.",
                  f"- **Acceptance**: {acceptance}", ""]
    unlisted = [cat for cat, c in s["by_category"].items()
                if c["passed"] < c["n"] and cat not in PHASE7_TRIGGERS]
    if unlisted:
        lines += ["Failing categories with no pre-registered experiment: "
                  + ", ".join(unlisted) + ". These need extraction or annotation "
                  "review first, not a new retrieval mode.", ""]
    return lines


def _write_report(out: dict, report_name: str = "evaluation") -> None:
    s = out["summary"]
    scope = ("the ten-document pilot" if s.get("skipped_not_ingested")
             else "the full corpus")
    lines = [
        f"# Evaluation report — gold question set against {scope}",
        "",
        f"Questions: **{s['questions']}** ({s['answerable']} answerable, "
        f"{s['no_answer']} no-answer) · k = {s['k']}",
        "",
        (f"{len(s['skipped_not_ingested'])} questions were skipped because none of their "
         f"expected documents are in the store yet: "
         f"{', '.join(s['skipped_not_ingested'])}." if s.get("skipped_not_ingested")
         else "Every gold question was runnable."),
        "",
        "| Metric | Value | Acceptance |",
        "|---|---|---|",
        f"| Document recall@{s['k']} | {s['recall_at_k']:.3f} | A3 ≥ 0.80 — "
        f"{'PASS' if s['acceptance']['A3_recall_at_10_ge_0.80'] else 'FAIL'} |",
        f"| Page recall@{s['k']} | {s['page_recall_at_k']:.3f} | reported |",
        f"| MRR | {s['mrr']:.3f} | reported |",
        f"| Evidence support (terms in the retrieved unit) | {s['evidence_support']} | "
        f"A3 ≥ 0.70 — {'PASS' if s['acceptance']['A3_evidence_support_ge_0.70'] else 'FAIL'} |",
        f"| Page evidence support (terms anywhere on a retrieved page) | "
        f"{s['page_evidence_support']} | reported |",
        f"| No-answer precision | {s['no_answer_precision']} | A4 ≥ 0.66 — "
        f"{'PASS' if s['acceptance']['A4_no_answer_precision_ge_0.66'] else 'FAIL'} |",
        f"| False-unsupported rate (answerable questions wrongly declared unsupported) | "
        f"{s['false_unsupported_rate']} | A4b ≤ 0.20 — "
        f"{'PASS' if s['acceptance']['A4b_false_unsupported_le_0.20'] else 'FAIL'} |",
        "",
        "## By category",
        "",
        "| Category | n | doc hits | passed | mean support | failing ids |",
        "|---|---|---|---|---|---|",
    ]
    for cat, c in s["by_category"].items():
        lines.append(f"| {cat} | {c['n']} | {c['doc_hits']} | {c['passed']} | "
                     f"{c['mean_support']} | {', '.join(c['failures']) or '—'} |")
    lines += [""] + _phase7_section(out) + ["## Failures in detail", ""]
    for r in out["results"]:
        if r["passed"]:
            continue
        lines += [
            f"### {r['id']} — {r['category']}",
            f"*{r['question']}*",
            "",
            f"- query: `{r['query']}`",
            f"- expected: {', '.join(r['expected_documents']) or '(nothing — no-answer question)'}",
            f"- doc rank: {r['doc_rank']} · unit support: {r['support']} · "
            f"page support: {r['page_support']} · missing terms: {r['missing_terms']}",
            f"- top hit: {r['top_hits'][0]['source_path'] + ' p' + str(r['top_hits'][0]['page']) if r['top_hits'] else '(no results)'}"
            f" score {r['top_hits'][0]['score'] if r['top_hits'] else 0}",
            "",
        ]
    with open_write(REPORTS_DIR / f"{report_name}-report.md") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("-k", type=int, default=DEFAULT_K)
    ap.add_argument("--only-ingested", action="store_true")
    ap.add_argument("--second-stage", action="store_true")
    ap.add_argument("--name", default="evaluation")
    args = ap.parse_args()
    out = run_evaluation(k=args.k, only_ingested=args.only_ingested,
                         report_name=args.name, second_stage=args.second_stage)
    print(json.dumps(out["summary"], indent=2)[:3000])
