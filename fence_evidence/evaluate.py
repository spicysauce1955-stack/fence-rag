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

from .paths import REPO_ROOT, REPORTS_DIR, TESTS_DIR, open_write, resolve_asset
from .relations import APPROVAL_RE
from .retrieval import (DEDUPE_TEXT_DEFAULT, STOPWORDS, UNIT_WORDS,
                        build_match_expression, resolve_document_version,
                        search_evidence)
from .store import connect

DEFAULT_K = 10

# G14 — which interface answers a question natively.
#
# The field is optional and defaults to "search", because every published
# number was measured with the search-only harness and a routing change must not
# move it silently. So routing is *additive*: a question that declares an
# interface is still issued to `search_evidence` and graded exactly as before —
# same denominators, same values — and the routed answer is graded separately in
# `summary["routed"]`, carrying the search result for the same question beside
# it so the before/after is on the page rather than in a commit message.
INTERFACES = ("search", "resolve", "facts")
DEFAULT_INTERFACE = "search"
# Relevance floor below which a result is reported as unsupported rather than as
# an answer.  Calibrated on the pilot: the three no-answer questions topped out
# at 12.2-14.2 while every answerable question scored >=20.0.  Three negatives
# is a thin basis, so this is a reported, tunable threshold rather than a claim
# about the corpus, and it is re-checked in the full-corpus evaluation.
NO_ANSWER_SCORE_FLOOR = 17.0


def question_interface(q: dict) -> str:
    """Which interface answers this question. Absent means ``search``.

    An unrecognised value is a loud failure rather than a silent fallback: a
    typo'd interface would otherwise quietly drop the question back into the
    search harness and the routed block would under-report by one, which is
    exactly the kind of drift G14 exists to prevent.
    """
    raw = q.get("interface")
    if raw is None:
        return DEFAULT_INTERFACE
    if raw not in INTERFACES:
        raise ValueError(
            f"{q.get('id') or '<unidentified question>'}: unknown interface "
            f"{raw!r}; expected one of {', '.join(INTERFACES)}")
    return raw


def load_gold(paths: list[Path] | None = None) -> list[dict]:
    paths = paths or sorted((REPO_ROOT / "eval").glob("gold-questions-*.json"))
    questions: list[dict] = []
    for p in paths:
        with open(p) as f:
            data = json.load(f)
        for q in data.get("questions", []):
            q["_set"] = data.get("set", p.stem)
            question_interface(q)  # reject an unknown interface at load time
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
                      second_stage: bool = False,
                      dedupe_text: bool = DEDUPE_TEXT_DEFAULT,
                      page_cap: int | None = None) -> dict:
    query = _query_for(q)
    results = search_evidence(query, limit=k, conn=conn, second_stage=second_stage,
                              dedupe_text=dedupe_text, page_cap=page_cap)
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
        image_ok = any((r.page_image_path and resolve_asset(r.page_image_path) is not None)
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


# ---------------------------------------------------------------------------
# G14 — the non-search interfaces
#
# Two things have to be true of these graders at once. They must be *separate*
# from the search harness, so that no published search number moves; and they
# must be *comparable* to it, so that "resolve answers what search missed" is a
# measurement rather than an assertion. They are therefore graded with the same
# formulas — document rank, term support, and the same pass rule
# (`doc_rank is not None and support >= 0.5`) — over what the interface actually
# returns.
#
# The one real difference is what "support" is measured against. Search returns
# a *unit*, so `evidence_support` asks whether that unit carries the answer
# terms. Resolution and the fact layer return *documents and records*, so the
# graded number is `answer_support`: are the annotated answer terms in the text
# of the ONE document the interface asserts as its answer?
#
# It used to be `document_support`, measured over the concatenated text of every
# document returned, and that was an overclaim. `resolve` hands back a whole
# supersession chain, so a term printed in a *superseded* member counted as
# support for the current one: gq-011 scored 1.0 over its four-document union
# and the pass rule inherited it. The union figure is still reported, under a
# name that says what it is (`returned_documents_support`), and nothing is
# graded on it. On the tightened measure gq-011 still scores 1.0 — every one of
# its five terms is in the active NOA itself — which is the point: the number
# now means what its label says.
#
# `record_support` — terms visible in the returned record itself — is reported
# beside both, because a resolution answer that names the right document is not
# the same as one that quotes the page.
#
# `page_rank` is reported only by an interface that actually knows a page. See
# `_grade_returned_documents`.
# ---------------------------------------------------------------------------

def _expected_documents(q: dict, conn) -> tuple[set[str], set[str], dict[str, list[int]]]:
    declared = set(q.get("expected_documents") or [])
    expected = _equivalent_paths(conn, declared)
    pages: dict[str, list[int]] = dict(q.get("expected_pages") or {})
    for _declared, page_nos in list(pages.items()):
        for equivalent in expected - declared:
            pages.setdefault(equivalent, page_nos)
    return declared, expected, pages


def _document_text(conn, source_paths: list[str]) -> str:
    """All extracted text of the named documents, normalised for term matching."""
    if conn is None or not source_paths:
        return ""
    parts = []
    for path in source_paths:
        for row in conn.execute(
                """SELECT e.text, e.ocr_text FROM elements e
                     JOIN documents d ON d.document_id = e.document_id
                    WHERE d.source_path = ?""", (path,)):
            parts.append(_norm((row["text"] or "") + " " + (row["ocr_text"] or "")))
    return "\n".join(parts)


NO_PAGE = ("not reported: this interface answers with documents, not pages")


def _grade_returned_documents(q: dict, conn, candidates: list[dict],
                              record_text: str,
                              answer_paths: list[str] | None = None) -> dict:
    """Shared grading tail for the interfaces that return documents.

    ``candidates`` is the interface's answer as an ordered list of
    ``{"source_path": ..., "page": ...}`` — most-confident first, so rank means
    the same thing it means for search.  A candidate whose ``page`` is None is
    saying it does not know a page, and is skipped for ``page_rank``.

    ``answer_paths`` is the document (or documents) the interface *asserts* as
    the answer, which is what ``answer_support`` is measured over.  It defaults
    to the highest-ranked candidate, because that is the interface's answer
    unless it says otherwise.

    Two things this deliberately no longer does:

    * It does not report a ``page_rank`` an interface did not measure.  Resolve
      used to stamp page 1 on every member of a chain, so ``page_rank`` recorded
      only whether the annotation happened to name page 1 — a tautology dressed
      as a measurement.  Absent, with the reason in ``page_rank_basis``, is the
      honest form.
    * It does not grade on the union of every returned document.  See the block
      comment above.
    """
    declared, expected, expected_pages = _expected_documents(q, conn)
    terms = [t for t in (q.get("expected_answer_terms") or []) if t]

    doc_rank = next((i + 1 for i, c in enumerate(candidates)
                     if c["source_path"] in expected), None)
    paged = [c for c in candidates if c.get("page") is not None]
    page_rank = None
    for i, c in enumerate(candidates):
        if c.get("page") is None:
            continue
        wanted = expected_pages.get(c["source_path"])
        if wanted and c["page"] in wanted:
            page_rank = i + 1
            break
    page_rank_basis = ("the page the interface cited" if paged
                       else NO_PAGE)

    returned_paths: list[str] = []
    for c in candidates:
        if c["source_path"] not in returned_paths:
            returned_paths.append(c["source_path"])

    if answer_paths is None:
        answer_paths = returned_paths[:1]
    answer_paths = [p for p in answer_paths if p]

    record_joined = _norm(record_text)
    record_found = [t for t in terms if _norm(t) in record_joined]
    record_support = (len(record_found) / len(terms)) if terms else None

    answer_joined = _document_text(conn, answer_paths)
    answer_found = [t for t in terms if _norm(t) in answer_joined]
    answer_support = (len(answer_found) / len(terms)) if terms else None

    union_joined = _document_text(conn, returned_paths)
    union_found = [t for t in terms if _norm(t) in union_joined]
    union_support = (len(union_found) / len(terms)) if terms else None

    passed = doc_rank is not None and (answer_support is None
                                       or answer_support >= 0.5)
    return {
        "id": q.get("id"), "category": q.get("category"), "set": q.get("_set"),
        "question": q.get("question"),
        "answerable": q.get("answerable", True),
        "n_results": len(candidates),
        "doc_rank": doc_rank,
        "page_rank": page_rank, "page_rank_basis": page_rank_basis,
        "expected_documents": sorted(declared),
        "equivalent_documents": sorted(expected - declared),
        "returned_documents": returned_paths,
        "answer_documents": answer_paths,
        "record_support": None if record_support is None else round(record_support, 3),
        # graded: the terms in the document the interface asserts as the answer
        "answer_support": None if answer_support is None else round(answer_support, 3),
        # reported, never graded: the same terms anywhere in ANY document
        # returned, which for `resolve` is the whole supersession chain
        "returned_documents_support": (None if union_support is None
                                       else round(union_support, 3)),
        "found_terms": answer_found,
        "missing_terms": [t for t in terms if t not in answer_found],
        "found_terms_anywhere_returned": union_found,
        "passed": passed,
    }


def _resolve_identifier(q: dict) -> str:
    """What to hand `resolve_document_version`.

    Explicit `interface_input.identifier` wins. The fallback reads an approval
    number out of the question text, which is enough for the NOA questions but
    is deliberately a fallback: a routed question should say what it resolves.
    """
    given = (q.get("interface_input") or {}).get("identifier")
    if given:
        return str(given)
    haystack = " ".join([q.get("question") or ""] + list(q.get("query_terms") or []))
    m = APPROVAL_RE.search(haystack)
    if m:
        return m.group(1)
    raise ValueError(
        f"{q.get('id')}: interface 'resolve' needs interface_input.identifier "
        f"(a document id, source path, or approval number)")


def _evaluate_resolve(q: dict, *, conn) -> dict:
    ii = q.get("interface_input") or {}
    identifier = _resolve_identifier(q)
    answer = resolve_document_version(identifier, at=ii.get("at"),
                                      as_of=ii.get("as_of"), conn=conn)
    if answer is None:
        row = _grade_returned_documents(q, conn, [], "", answer_paths=[])
        row.update({"interface": "resolve", "identifier": identifier,
                    "active_document": None, "active_basis": None,
                    "chain_length": 0,
                    "note": f"resolution returned nothing for {identifier!r}"})
        return row

    # Order the answer the way a reader reads it: the member the interface says
    # is in force, then the rest of the chain oldest-first.
    candidates: list[dict] = []
    seen: set[str] = set()
    for member in ([answer["active"]] if answer.get("active") else []) + \
                  list(answer.get("chain") or []):
        path = member.get("source_path")
        if not path or path in seen:
            continue
        seen.add(path)
        # `page` is None on purpose: resolution answers with a document, and a
        # stamped page 1 made `page_rank` a tautology (see the grading tail).
        candidates.append({"source_path": path, "page": None, "member": member})

    record_text = json.dumps(answer, default=str)
    active = answer.get("active") or {}
    # The chain is the evidence; the ACTIVE member is the answer, and it is the
    # only document `answer_support` may be measured over.
    row = _grade_returned_documents(q, conn, candidates, record_text,
                                    answer_paths=[active.get("source_path")]
                                    if active.get("source_path") else [])
    row.update({
        "interface": "resolve",
        "identifier": identifier,
        "active_document": active.get("source_path"),
        "active_basis": answer.get("active_basis"),
        # the machine-readable half of the same statement; G3 exists to provide
        # it, and dropping it left only the prose
        "active_basis_kind": answer.get("active_basis_kind"),
        "chain_length": len(answer.get("chain") or []),
        "chain": [{"source_path": m.get("source_path"),
                   "version_status": m.get("version_status")}
                  for m in (answer.get("chain") or [])],
        "note": "",
    })
    return row


def _evaluate_facts(q: dict, *, k: int, conn) -> dict:
    from .facts import query_facts

    ii = q.get("interface_input") or {}
    fact_type = ii.get("fact_type")
    if not fact_type:
        raise ValueError(f"{q.get('id')}: interface 'facts' needs "
                         f"interface_input.fact_type")
    conditions = ii.get("conditions") or q.get("required_conditions") or None
    rows = query_facts(fact_type, conditions=conditions,
                       manufacturer=ii.get("manufacturer"),
                       limit=int(ii.get("limit") or k), conn=conn)
    candidates = [{"source_path": r["source_path"], "page": r.get("page_no")}
                  for r in rows if r.get("source_path")]
    record_text = "\n".join(
        " ".join(str(r.get(field) or "") for field in
                 ("value_original", "value_normalized", "unit", "title",
                  "source_path", "review_status"))
        + " " + json.dumps(r.get("conditions") or {}) for r in rows)
    # A fact cites one document and one page. The highest-ranked one is the
    # layer's answer; the rest are its other matches.
    row = _grade_returned_documents(q, conn, candidates, record_text,
                                    answer_paths=[candidates[0]["source_path"]]
                                    if candidates else [])
    row.update({
        "interface": "facts",
        "fact_type": fact_type,
        "conditions": conditions or {},
        "values": [{"value": r.get("value_original"),
                    "normalized": r.get("value_normalized"),
                    "review_status": r.get("review_status"),
                    "source_path": r.get("source_path"),
                    "page": r.get("page_no")} for r in rows[:5]],
        "note": "" if rows else f"no {fact_type} facts matched",
    })
    return row


def evaluate_routed_question(q: dict, *, k: int = DEFAULT_K, conn=None) -> dict:
    """Answer one question through the interface it declares.

    Never called for a `search` question — those go through `evaluate_question`,
    unchanged. Asking for a routed grading of a search question is a caller bug
    and says so.
    """
    interface = question_interface(q)
    if interface == "search":
        raise ValueError(
            f"{q.get('id')}: interface 'search' is graded by evaluate_question")
    own = conn is None
    conn = conn or connect()
    try:
        if interface == "resolve":
            return _evaluate_resolve(q, conn=conn)
        return _evaluate_facts(q, k=k, conn=conn)
    finally:
        if own:
            conn.close()


def _mean(values: list[float]) -> float | None:
    return round(statistics.mean(values), 3) if values else None


def _routed_metrics(rows: list[dict]) -> dict:
    return {
        "n": len(rows),
        "passed": sum(1 for r in rows if r["passed"]),
        "doc_recall": _mean([1.0 if r["doc_rank"] else 0.0 for r in rows]),
        "mrr": _mean([1 / r["doc_rank"] if r["doc_rank"] else 0.0 for r in rows]),
        "answer_support": _mean([r["answer_support"] for r in rows
                                 if r["answer_support"] is not None]),
        "returned_documents_support": _mean(
            [r["returned_documents_support"] for r in rows
             if r["returned_documents_support"] is not None]),
        "record_support": _mean([r["record_support"] for r in rows
                                 if r["record_support"] is not None]),
        "page_rank_reported": sum(1 for r in rows
                                  if r.get("page_rank_basis") != NO_PAGE),
    }


def _routed_summary(routed_rows: list[dict], search_rows: list[dict]) -> dict:
    """The separately-labelled block, with the search result of the same
    question beside every routed one.

    Deliberately compact: `cli evaluate` prints the summary, so the full routed
    rows live in `out["routed_results"]` and only the before/after is here.
    """
    search_by_id = {r["id"]: r for r in search_rows}
    by_interface: dict[str, list[dict]] = defaultdict(list)
    for r in routed_rows:
        by_interface[r["interface"]].append(r)
    questions = []
    for r in routed_rows:
        before = search_by_id.get(r["id"]) or {}
        questions.append({
            "id": r["id"], "category": r["category"], "interface": r["interface"],
            "doc_rank": r["doc_rank"],
            "record_support": r["record_support"],
            "answer_support": r["answer_support"],
            "returned_documents_support": r["returned_documents_support"],
            "answer_documents": r["answer_documents"],
            "page_rank": r["page_rank"], "page_rank_basis": r["page_rank_basis"],
            "missing_terms": r["missing_terms"],
            "passed": r["passed"], "note": r.get("note") or "",
            "search": {
                "doc_rank": before.get("doc_rank"),
                "page_rank": before.get("page_rank"),
                "support": before.get("support"),
                "page_support": before.get("page_support"),
                "passed": before.get("passed"),
            }})
    out = _routed_metrics(routed_rows)
    out["by_interface"] = {name: _routed_metrics(rs)
                           for name, rs in sorted(by_interface.items())}
    out["questions"] = questions
    out["comparability"] = (
        "answer_support is the graded number: the annotated answer terms in "
        "the text of the ONE document the interface asserts as its answer -- "
        "the active member for `resolve`, the top-ranked fact's document for "
        "`facts`. It is narrower than page_evidence_support (a document, not a "
        "page) and wider than evidence_support (a document, not a unit), so it "
        "is the analogue of neither and must not be averaged with either. "
        "returned_documents_support is the same terms anywhere in ANY document "
        "returned -- for `resolve` that is the whole supersession chain, so a "
        "term printed only in a superseded member counts. It is reported and "
        "never graded. page_rank is reported only where the interface knows a "
        "page; `resolve` answers with documents and reports none. The pass rule "
        "is the search harness's own, applied to answer_support. These numbers "
        "are NOT part of the headline metrics and are not averaged into them.")
    return out


def run_evaluation(*, k: int = DEFAULT_K, gold_paths: list[Path] | None = None,
                   only_ingested: bool = False, report_name: str = "evaluation",
                   second_stage: bool = False, db_path: Path | None = None,
                   write: bool = True, dedupe_text: bool = DEDUPE_TEXT_DEFAULT,
                   page_cap: int | None = None) -> dict:
    """Run the gold set.

    ``only_ingested`` restricts the run to questions whose expected documents are
    all present in the store, which is what makes the Phase 4 gate meaningful
    against the ten-document pilot before the full corpus is processed.

    ``db_path`` measures a store other than ``workspace/indexes/evidence.db``,
    and ``write=False`` suppresses the results JSON and the report. Both exist
    so a projection experiment can be measured on a copy without overwriting
    the committed numbers for the projection that is actually shipped.
    """
    questions = load_gold(gold_paths)
    if not questions:
        raise SystemExit("no gold questions found in eval/gold-questions-*.json")
    # An experiment copy lives outside workspace/, which the write guard refuses,
    # and migrating a store that is not this repository's would be wrong anyway.
    # The harness only reads, so measuring a named store opens it as a reader.
    conn = connect(db_path, read_only=db_path is not None)
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
        rows = [evaluate_question(q, k=k, conn=conn, second_stage=second_stage,
                                  dedupe_text=dedupe_text, page_cap=page_cap)
                for q in questions]
        # The routed pass is a *second* pass over the same questions. Nothing
        # here feeds back into `rows`; the search harness above is untouched.
        interface_counts: dict[str, int] = defaultdict(int)
        routed_rows = []
        for q in questions:
            interface = question_interface(q)
            interface_counts[interface] += 1
            if interface == DEFAULT_INTERFACE:
                continue
            routed_rows.append(evaluate_routed_question(q, k=k, conn=conn))
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
    raw_support = statistics.mean(supports) if supports else None
    raw_no_answer_precision = (sum(1 for r in unanswerable if r["passed"]) / len(unanswerable)
                               if unanswerable else None)
    raw_false_unsupported = (len(false_unsupported) / len(answerable)
                             if answerable else None)
    summary = {
        "k": k,
        "questions": len(rows),
        "answerable": len(answerable),
        "no_answer": len(unanswerable),
        "recall_at_k": round(recall, 3),
        "page_recall_at_k": round(page_recall, 3),
        "mrr": round(mrr, 3),
        "evidence_support": round(raw_support, 3) if raw_support is not None else None,
        "page_evidence_support": round(statistics.mean(page_supports), 3) if page_supports else None,
        "no_answer_precision": round(raw_no_answer_precision, 3)
        if raw_no_answer_precision is not None else None,
        # The other half of the picture. A detector can reach high no-answer
        # precision by declaring almost everything unsupported, so the two are
        # always reported together.
        "false_unsupported_rate": round(raw_false_unsupported, 3)
        if raw_false_unsupported is not None else None,
        "false_unsupported_ids": [r["id"] for r in false_unsupported],
        "passed": sum(1 for r in rows if r["passed"]),
        "by_category": {k2: v for k2, v in sorted(by_cat.items())},
        "skipped_not_ingested": skipped,
        # G14. Every metric above is the search harness over every question,
        # routed ones included, which is what keeps them comparable with the
        # figures published before routing existed.
        "search_scope": ("every gold question, routed ones included; the metrics "
                         "above are the search harness and nothing else"),
        "interfaces": dict(sorted(interface_counts.items())),
        "routed": _routed_summary(routed_rows, rows),
        "second_stage": second_stage,
        # The projection audit's R3 and R5. Recorded on every run, including the
        # baseline, so a results file always says which configuration produced it.
        "dedupe_text": dedupe_text,
        "page_cap": page_cap,
        "second_stage_attachments": sum(r.get("second_stage_attachments") or 0 for r in rows),
        "acceptance": {},
        # The values the gate was applied to, unrounded. `evidence_support`
        # above is rounded for reading and 0.699512 reads as 0.700; a reader
        # checking a verdict needs the number the verdict was made on.
        "raw": {"recall_at_k": recall, "mrr": mrr, "evidence_support": raw_support,
                "no_answer_precision": raw_no_answer_precision,
                "false_unsupported_rate": raw_false_unsupported},
    }
    # Graded on the measured means, never on the three-decimal display values
    # in `summary`. Reading the rounded number let 0.699512 report as a pass
    # against a 0.70 threshold, which is how this was found.
    summary["acceptance"] = acceptance_flags(
        recall_at_k=recall, evidence_support=raw_support,
        no_answer_precision=raw_no_answer_precision,
        false_unsupported_rate=raw_false_unsupported)
    out = {"summary": summary, "results": rows, "routed_results": routed_rows}
    if write:
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


def _routed_section(out: dict) -> list[str]:
    """The separately-labelled block G14 asks for. Never folded into the table
    above it."""
    s = out["summary"]
    routed = s.get("routed") or {}
    counts = s.get("interfaces") or {}
    lines = ["## Routed interfaces", "",
             "Every metric above is the **search** harness over every gold "
             "question, routed ones included — same denominators, same values as "
             "before routing existed. The block below is separate and is not "
             "averaged into it.", "",
             "Declared interfaces: "
             + (", ".join(f"`{name}` {n}" for name, n in counts.items()) or "—"),
             ""]
    if not routed.get("n"):
        lines += ["No question declares a non-search interface.", ""]
        return lines
    lines += [
        f"{routed['n']} question(s) are additionally answered through the "
        f"interface they declare. The graded number is **`answer_support`**: "
        f"the annotated answer terms in the text of the *one* document the "
        f"interface asserts as its answer — the active member for `resolve`, "
        f"the top-ranked fact's document for `facts`. It is the analogue of "
        f"neither headline support metric (narrower than a page, wider than a "
        f"unit) and is averaged with neither. `returned documents support` is "
        f"the same terms anywhere in **any** document returned — for `resolve` "
        f"that is the whole supersession chain, so a term printed only in a "
        f"superseded member counts — and it is reported, never graded. The "
        f"pass rule is the search harness's own (`doc_rank` found and "
        f"`answer_support` ≥ 0.5).", "",
        f"`page_rank` is reported only by an interface that knows a page "
        f"({routed['page_rank_reported']} of {routed['n']} routed question(s) "
        f"here). `resolve` answers with a document and reports none: it used to "
        f"stamp page 1 on every chain member, which measured only whether the "
        f"annotation happened to name page 1.", "",
        "| Interface | n | doc recall | MRR | answer support | returned-docs support | "
        "record support | passed |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, m in routed["by_interface"].items():
        lines.append(f"| {name} | {m['n']} | {m['doc_recall']} | {m['mrr']} | "
                     f"{m['answer_support']} | {m['returned_documents_support']} | "
                     f"{m['record_support']} | {m['passed']}/{m['n']} |")
    lines += ["", "### Before and after, question by question", "",
              "| id | category | interface | doc rank search → routed | "
              "support search unit → routed answer document | passed search → routed |",
              "|---|---|---|---|---|---|"]
    for r in routed["questions"]:
        b = r["search"]
        lines.append(
            f"| {r['id']} | {r['category']} | {r['interface']} | "
            f"{b['doc_rank']} → {r['doc_rank']} | "
            f"{b['support']} → {r['answer_support']} | "
            f"{'PASS' if b['passed'] else 'FAIL'} → "
            f"{'PASS' if r['passed'] else 'FAIL'} |")
    lines += ["",
              "The search rows for these questions are unchanged and still "
              "appear in the by-category table and the failure list above; a "
              "routed question is not removed from the search denominator.", ""]
    for r in out.get("routed_results") or []:
        if r["interface"] != "resolve":
            continue
        lines += [f"#### {r['id']} — resolved `{r.get('identifier')}`", "",
                  f"- active: {r.get('active_document') or '(none)'}",
                  f"- basis: {r.get('active_basis') or '—'}",
                  f"- basis kind: `{r.get('active_basis_kind') or '—'}`",
                  f"- chain: {r.get('chain_length')} member(s)",
                  f"- answer support is measured over the active member alone; "
                  f"terms found there {r.get('answer_support')}, terms found "
                  f"anywhere in the chain {r.get('returned_documents_support')}",
                  f"- page rank: {r.get('page_rank_basis')}"]
        for m in (r.get("chain") or []):
            lines.append(f"    - {m['version_status']}  {m['source_path']}")
        if r.get("note"):
            lines.append(f"- note: {r['note']}")
        lines.append("")
    return lines


def acceptance_table(s: dict) -> list[str]:
    """The acceptance table's markdown rows.

    Graded rows print the unrounded value, because the verdict was made on it:
    a row reading `0.700 | A3 >= 0.70 - FAIL` gives the reader no way to tell a
    formatting bug from a measurement 0.0005 short. Ungraded rows keep the
    three-decimal reading precision. Results files written before `raw` existed
    fall back to the rounded values.
    """
    raw = s.get("raw") or {}

    def graded(key, criterion, flag):
        value = raw.get(key, s.get(key))
        shown = f"{value:.4f}" if isinstance(value, (int, float)) else value
        return f"{shown} | {criterion} — {'PASS' if s['acceptance'][flag] else 'FAIL'} |"

    return [
        "| Metric | Value | Acceptance |",
        "|---|---|---|",
        f"| Document recall@{s['k']} | "
        + graded("recall_at_k", "A3 ≥ 0.80", "A3_recall_at_10_ge_0.80"),
        f"| Page recall@{s['k']} | {s['page_recall_at_k']:.3f} | reported |",
        f"| MRR | {s['mrr']:.3f} | reported |",
        "| Evidence support (terms in the retrieved unit) | "
        + graded("evidence_support", "A3 ≥ 0.70", "A3_evidence_support_ge_0.70"),
        f"| Page evidence support (terms anywhere on a retrieved page) | "
        f"{s['page_evidence_support']} | reported |",
        "| No-answer precision | "
        + graded("no_answer_precision", "A4 ≥ 0.66", "A4_no_answer_precision_ge_0.66"),
        "| False-unsupported rate (answerable questions wrongly declared unsupported) | "
        + graded("false_unsupported_rate", "A4b ≤ 0.20", "A4b_false_unsupported_le_0.20"),
    ]


def acceptance_flags(*, recall_at_k: float, evidence_support: float | None,
                     no_answer_precision: float | None,
                     false_unsupported_rate: float | None) -> dict:
    """The Phase 4 gate, graded on measured values rather than displayed ones.

    `summary` rounds every metric to three decimals for reading. Grading that
    rounded number is a different question from grading the measurement: mean
    unit support of 0.699512 displays as 0.700 and would report PASS against a
    0.70 threshold it does not reach. Take the raw means here and round only for
    display.

    `None` means the run measured nothing -- no answerable questions, or no
    no-answer questions -- and never grades as a pass. The ceiling criterion is
    the same: an unmeasured rate is not evidence that the ceiling was respected.
    """
    return {
        "A3_recall_at_10_ge_0.80": recall_at_k >= 0.80,
        "A3_evidence_support_ge_0.70": evidence_support is not None
        and evidence_support >= 0.70,
        "A4_no_answer_precision_ge_0.66": no_answer_precision is not None
        and no_answer_precision >= 0.66,
        "A4b_false_unsupported_le_0.20": false_unsupported_rate is not None
        and false_unsupported_rate <= 0.20,
    }


def default_report_name(explicit: str | None, second_stage: bool, *,
                        dedupe_text: bool = DEDUPE_TEXT_DEFAULT,
                        page_cap: int | None = None) -> str:
    """Where a run's artifacts land, when the caller did not say.

    Configurations that measure different things must not share a path -- 0.650
    unit support against 0.6995 -- and all of these are committed artifacts, so
    sharing one means the file says whatever the last run happened to be. Every
    switch that changes what is measured therefore changes the name. An explicit
    `--name` still wins; this only supplies the default nobody should have to
    remember.
    """
    if explicit:
        return explicit
    parts = ["evaluation"]
    if second_stage:
        parts.append("second-stage")
    # Named by deviation from the shipped configuration, so `evaluation` always
    # means "what this platform actually returns" however the defaults move.
    if dedupe_text != DEDUPE_TEXT_DEFAULT:
        parts.append("dedupe" if dedupe_text else "nodedupe")
    if page_cap is not None:
        parts.append(f"pagecap{page_cap}")
    return "-".join(parts)


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
        *acceptance_table(s),
        "",
        "## By category",
        "",
        "| Category | n | doc hits | passed | mean support | failing ids |",
        "|---|---|---|---|---|---|",
    ]
    for cat, c in s["by_category"].items():
        lines.append(f"| {cat} | {c['n']} | {c['doc_hits']} | {c['passed']} | "
                     f"{c['mean_support']} | {', '.join(c['failures']) or '—'} |")
    lines += [""] + _routed_section(out) + _phase7_section(out) + \
        ["## Failures in detail", ""]
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
