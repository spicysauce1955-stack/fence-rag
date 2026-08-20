"""Document-to-document relations.

Supersession is *discovered from the documents themselves* — Miami-Dade NOAs
name the approval they replace ("EVIDENCE SUBMITTED UNDER PREVIOUS APPROVAL
# 12-1106.11") — and recorded as an edge between two separate document rows.
Superseded and active approvals are never merged (prohibition 5), and
byte-identical files filed under several manufacturers are linked rather than
deduplicated (prohibition 1).
"""
from __future__ import annotations

import re
import sqlite3
from collections import defaultdict

from .store import add_relation

APPROVAL_RE = re.compile(r"\b(\d{2}-\d{4}\.\d{2})\b")
PREVIOUS_RE = re.compile(
    r"previous\s+approval\s*#?\s*(\d{2}\s*-\s*\d{4}\s*\.\s*\d{2})", re.I)
RENEWAL_RE = re.compile(
    r"renew(?:s|al of)?\s+(?:noa\s*)?#?\s*(\d{2}\s*-\s*\d{4}\s*\.\s*\d{2})", re.I)


def _norm_approval(s: str) -> str:
    return re.sub(r"\s+", "", s)


def primary_approval_id(source_path: str, title: str | None) -> str | None:
    """The approval this document *is* (from its filename, else its title)."""
    m = APPROVAL_RE.search(source_path)
    if m:
        return m.group(1)
    if title:
        m = APPROVAL_RE.search(title)
        if m:
            return m.group(1)
    return None


def derive_relations(conn: sqlite3.Connection) -> dict[str, int]:
    counts = defaultdict(int)

    # --- byte-identical files filed under different manufacturers -----------
    by_sha: dict[str, list[str]] = defaultdict(list)
    for r in conn.execute("SELECT document_id, sha256 FROM document_versions"):
        by_sha[r["sha256"]].append(r["document_id"])
    for sha, docs in by_sha.items():
        if len(docs) < 2:
            continue
        for a in docs:
            for b in docs:
                if a != b:
                    add_relation(conn, a, b, "same_content_as",
                                 basis=f"identical sha256 {sha[:12]}", confidence=1.0)
                    counts["same_content_as"] += 1

    # --- approval id -> document -------------------------------------------
    docs = conn.execute("SELECT document_id, source_path, title FROM documents").fetchall()
    by_approval: dict[str, list[str]] = defaultdict(list)
    for d in docs:
        aid = primary_approval_id(d["source_path"], d["title"])
        if aid:
            by_approval[aid].append(d["document_id"])

    # --- supersession stated inside the document text ------------------------
    for d in docs:
        aid = primary_approval_id(d["source_path"], d["title"])
        rows = conn.execute(
            "SELECT text, ocr_text FROM elements WHERE document_id=? AND page_no<=6",
            (d["document_id"],)).fetchall()
        blob = " ".join((r["text"] or "") + " " + (r["ocr_text"] or "") for r in rows)
        cited = {_norm_approval(m) for m in PREVIOUS_RE.findall(blob)}
        cited |= {_norm_approval(m) for m in RENEWAL_RE.findall(blob)}
        for prev in cited:
            if aid and prev == aid:
                continue
            for target in by_approval.get(prev, []):
                add_relation(conn, d["document_id"], target, "supersedes",
                             basis=f"names NOA {prev} as previous approval", confidence=0.9)
                add_relation(conn, target, d["document_id"], "superseded_by",
                             basis=f"named as previous approval by NOA {aid or '?'}",
                             confidence=0.9)
                counts["supersedes"] += 1

    # --- same approval filed in several places ------------------------------
    for aid, ids in by_approval.items():
        if len(ids) < 2:
            continue
        for a in ids:
            for b in ids:
                if a != b:
                    add_relation(conn, a, b, "same_product_as",
                                 basis=f"both carry approval {aid}", confidence=0.8)
                    counts["same_product_as"] += 1

    # --- version_status from discovered edges (never downgrades curated data)
    for r in conn.execute("""SELECT DISTINCT to_document_id AS d FROM relations
                             WHERE relation_type='superseded_by'"""):
        conn.execute("""UPDATE documents SET version_status='superseded',
            version_status_basis='named as a previous approval by a later NOA'
            WHERE document_id=? AND version_status!='superseded'""", (r["d"],))
        counts["status_superseded"] += 1
    conn.commit()
    return dict(counts)


def supersession_chain(conn: sqlite3.Connection, document_id: str) -> list[str]:
    """Ordered chain oldest -> newest through supersedes edges."""
    seen = {document_id}
    back = [document_id]
    cur = document_id
    while True:
        row = conn.execute("""SELECT to_document_id AS d FROM relations
            WHERE from_document_id=? AND relation_type='supersedes' LIMIT 1""",
                           (cur,)).fetchone()
        if not row or row["d"] in seen:
            break
        back.insert(0, row["d"])
        seen.add(row["d"])
        cur = row["d"]
    cur = document_id
    while True:
        row = conn.execute("""SELECT from_document_id AS d FROM relations
            WHERE to_document_id=? AND relation_type='supersedes' LIMIT 1""",
                           (cur,)).fetchone()
        if not row or row["d"] in seen:
            break
        back.append(row["d"])
        seen.add(row["d"])
        cur = row["d"]
    return back
