"""Relevance audit of the retrieval projection.

Read-only measurement, so the audit can be re-run after any accepted change and
the numbers in `workspace/reports/projection-relevance-audit.md` can be checked
rather than trusted.  Nothing here writes to the store.
"""
from __future__ import annotations

import json
import sqlite3
import statistics
from collections import Counter

from .paths import EVIDENCE_DB, TESTS_DIR, open_write
from .quality import ascii_token_ratio, control_ratio
from .store import connect

TINY_UNIT_CHARS = 40


def _ro_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{EVIDENCE_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _projected_element_ids(conn: sqlite3.Connection) -> None:
    """Temp table of every element id that reaches the index."""
    conn.execute("CREATE TEMP TABLE IF NOT EXISTS proj(element_id TEXT PRIMARY KEY)")
    conn.execute("DELETE FROM proj")
    conn.execute("INSERT OR IGNORE INTO proj "
                 "SELECT j.value FROM retrieval_units u, json_each(u.element_ids) j")


def coverage(conn: sqlite3.Connection) -> dict:
    _projected_element_ids(conn)
    total = conn.execute("SELECT COUNT(*) FROM elements").fetchone()[0]
    projected = conn.execute("SELECT COUNT(*) FROM proj").fetchone()[0]
    excluded = {r["element_type"]: {"elements": r["n"], "chars": r["chars"] or 0}
                for r in conn.execute("""
        SELECT e.element_type, COUNT(*) n,
               SUM(length(COALESCE(e.text,'') || COALESCE(e.ocr_text,''))) chars
          FROM elements e LEFT JOIN proj p ON p.element_id = e.element_id
         WHERE p.element_id IS NULL GROUP BY 1 ORDER BY n DESC""")}

    conn.execute("CREATE TEMP TABLE IF NOT EXISTS hp(t TEXT)")
    conn.execute("DELETE FROM hp")
    conn.execute("INSERT INTO hp SELECT DISTINCT j.value "
                 "FROM retrieval_units u, json_each(u.heading_path) j")
    headings = conn.execute(
        "SELECT COUNT(*) FROM elements WHERE element_type='heading'").fetchone()[0]
    unreachable = conn.execute("""
        SELECT COUNT(*) FROM elements e WHERE e.element_type='heading'
          AND NOT EXISTS (SELECT 1 FROM hp
                           WHERE hp.t = COALESCE(NULLIF(e.text,''), e.ocr_text))
        """).fetchone()[0]

    pages = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
    pages_indexed = conn.execute(
        "SELECT COUNT(DISTINCT version_id || '#' || page_no) FROM retrieval_units").fetchone()[0]
    unit_less_with_content = conn.execute("""
        SELECT COUNT(*) FROM pages p
         WHERE NOT EXISTS (SELECT 1 FROM retrieval_units u
                            WHERE u.version_id=p.version_id AND u.page_no=p.page_no)
           AND (SELECT COUNT(*) FROM elements e WHERE e.page_id=p.page_id) > 0
        """).fetchone()[0]
    return {
        "elements": total, "projected": projected,
        "projected_share": round(projected / total, 4) if total else None,
        "excluded_by_type": excluded,
        "headings": headings, "headings_unreachable": unreachable,
        "headings_unreachable_share": round(unreachable / headings, 4) if headings else None,
        "pages": pages, "pages_with_units": pages_indexed,
        "pages_without_units": pages - pages_indexed,
        "pages_without_units_but_with_elements": unit_less_with_content,
    }


def unit_shape(conn: sqlite3.Connection) -> dict:
    lens = sorted(r[0] for r in conn.execute("SELECT length(text) FROM retrieval_units"))
    n = len(lens)
    by_type = {r["element_type"]: {"n": r["n"], "min": r["mn"], "avg": r["av"], "max": r["mx"]}
               for r in conn.execute("""SELECT element_type, COUNT(*) n,
                  MIN(length(text)) mn, CAST(AVG(length(text)) AS INT) av,
                  MAX(length(text)) mx FROM retrieval_units GROUP BY 1 ORDER BY n DESC""")}
    per_unit = Counter(r[0] for r in conn.execute(
        "SELECT json_array_length(element_ids) FROM retrieval_units"))
    dup = conn.execute("""SELECT COUNT(*) g, COALESCE(SUM(n),0) rows FROM
        (SELECT text, COUNT(*) n FROM retrieval_units GROUP BY text HAVING n>1)""").fetchone()
    worst = [{"occurrences": r["k"], "documents": r["docs"], "text": r["t"]}
             for r in conn.execute("""SELECT substr(text,1,60) t, COUNT(*) k,
                COUNT(DISTINCT document_id) docs FROM retrieval_units
                GROUP BY text HAVING k>4 ORDER BY k DESC LIMIT 8""")]
    texts = [r[0] for r in conn.execute("SELECT text FROM retrieval_units")]
    mojibake = sum(1 for t in texts
                   if control_ratio(t) > 0.005 and ascii_token_ratio(t) < 0.85)
    ocr_units = conn.execute(
        "SELECT COUNT(*) FROM retrieval_units WHERE text_source='ocr'").fetchone()[0]
    return {
        "units": n,
        "length": {"min": lens[0], "p10": lens[n // 10], "median": lens[n // 2],
                   "p90": lens[9 * n // 10], "max": lens[-1],
                   "mean": round(statistics.mean(lens), 1)} if n else {},
        "under_20_chars": sum(1 for l in lens if l < 20),
        "under_80_chars": sum(1 for l in lens if l < 80),
        "over_1400_chars": sum(1 for l in lens if l > 1400),
        "by_type": by_type,
        "elements_per_unit": dict(sorted(per_unit.items())[:12]),
        "duplicate_text_groups": dup["g"], "units_with_duplicate_text": dup["rows"],
        "duplicate_share": round((dup["rows"] or 0) / n, 4) if n else None,
        "worst_duplicates": worst,
        "residual_mojibake_units": mojibake,
        "ocr_units": ocr_units,
        "ocr_share": round(ocr_units / n, 4) if n else None,
    }


def result_list_composition(conn: sqlite3.Connection, k: int = 10) -> dict:
    """What the top-k is actually spent on, across the gold questions."""
    from .evaluate import _query_for, load_gold
    from .retrieval import search_evidence
    dup_texts = {r[0] for r in conn.execute(
        "SELECT text FROM retrieval_units GROUP BY text HAVING COUNT(*)>1")}
    slots = Counter()
    total = tiny = dup = repeat_page = 0
    distinct_pages = []
    for q in load_gold():
        results = search_evidence(_query_for(q), limit=k, conn=conn)
        seen = set()
        for r in results:
            total += 1
            slots[r.element_type] += 1
            if len(r.text) < TINY_UNIT_CHARS:
                tiny += 1
            if r.text in dup_texts:
                dup += 1
            key = (r.document_id, r.page)
            if key in seen:
                repeat_page += 1
            seen.add(key)
        distinct_pages.append(len(seen))
    return {
        "queries": len(load_gold()), "slots": total,
        "by_element_type": dict(slots.most_common()),
        "slots_with_duplicated_text": dup,
        "duplicated_share": round(dup / total, 4) if total else None,
        "slots_under_40_chars": tiny,
        "tiny_share": round(tiny / total, 4) if total else None,
        "slots_repeating_a_page": repeat_page,
        "repeat_page_share": round(repeat_page / total, 4) if total else None,
        "mean_distinct_pages_per_list": round(statistics.mean(distinct_pages), 2)
        if distinct_pages else None,
    }


def within_page_ceiling(conn: sqlite3.Connection, k: int = 10) -> dict:
    """Upper bound on unit support if the best element on a retrieved page could be chosen."""
    from .evaluate import _norm, _query_for, _returned_evidence, load_gold
    from .retrieval import search_evidence
    now, ceil = [], []
    improvable = at_full = 0
    for q in load_gold():
        if not q.get("answerable") or not q.get("expected_answer_terms"):
            continue
        terms = q["expected_answer_terms"]
        results = search_evidence(_query_for(q), limit=k, conn=conn)
        returned = "\n".join(_returned_evidence(r) for r in results)
        cur = sum(1 for t in terms if _norm(t) in returned) / len(terms)
        parts = []
        for doc, page in {(r.document_id, r.page) for r in results}:
            for row in conn.execute("""SELECT text, ocr_text, heading_path FROM elements
                    WHERE document_id=? AND page_no=?""", (doc, page)):
                parts.append(_norm(" ".join([row["text"] or "", row["ocr_text"] or "",
                                             row["heading_path"] or ""])))
        page_blob = "\n".join(parts)
        top = sum(1 for t in terms if _norm(t) in page_blob) / len(terms)
        now.append(cur)
        ceil.append(top)
        if top > cur + 1e-9:
            improvable += 1
        elif cur >= 0.999:
            at_full += 1
    return {
        "questions": len(now),
        "unit_support_now": round(statistics.mean(now), 4) if now else None,
        "within_page_ceiling": round(statistics.mean(ceil), 4) if ceil else None,
        "headroom": round(statistics.mean(ceil) - statistics.mean(now), 4) if now else None,
        "questions_improvable": improvable,
        "questions_already_at_full_support": at_full,
    }


def run_audit(k: int = 10) -> dict:
    conn = _ro_connect()
    try:
        out = {
            "coverage": coverage(conn),
            "unit_shape": unit_shape(conn),
            "result_list_composition": result_list_composition(conn, k=k),
            "within_page_ceiling": within_page_ceiling(conn, k=k),
        }
    finally:
        conn.close()
    with open_write(TESTS_DIR / "projection-audit.json") as f:
        json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    print(json.dumps(run_audit(), indent=2))
