"""Document-to-document relations.

Supersession is *discovered from the documents themselves* — Miami-Dade NOAs
name the approval they replace ("EVIDENCE SUBMITTED UNDER PREVIOUS APPROVAL
# 12-1106.11") — and recorded as an edge between two separate document rows.
Superseded and active approvals are never merged (prohibition 5), and
byte-identical files filed under several manufacturers are linked rather than
deduplicated (prohibition 1).
"""
from __future__ import annotations

import hashlib
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


def _content_digest(conn: sqlite3.Connection, document_id: str) -> str | None:
    """A stable digest over one document's own extracted text.

    sha256 on the source bytes only catches byte-for-byte duplicates. A PDF
    that has been re-exported or re-saved (different producer string,
    timestamps, a few KB of container metadata) gets a different sha256 while
    extracting to identical text. This hashes the *extracted* text instead —
    every element's text (falling back to OCR text), in page/ordinal order,
    with runs of whitespace collapsed so line-wrap and spacing differences
    introduced by extraction don't change the digest. Only the latest version
    of the document contributes, matching how facts.py picks candidates.
    """
    rows = conn.execute("""
        SELECT e.text, e.ocr_text FROM elements e
        JOIN (SELECT document_id, version_id,
                     ROW_NUMBER() OVER (PARTITION BY document_id
                                        ORDER BY ingested_at DESC) rn
                FROM document_versions) latest
          ON latest.version_id = e.version_id AND latest.rn = 1
        WHERE e.document_id = ?
        ORDER BY e.page_no, e.ordinal""", (document_id,)).fetchall()
    text = "\n".join((r["text"] or r["ocr_text"] or "") for r in rows)
    normalised = re.sub(r"\s+", " ", text).strip()
    if not normalised:
        return None
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


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
    by_sha_pair: set[tuple[str, str]] = set()
    for sha, docs in by_sha.items():
        if len(docs) < 2:
            continue
        for a in docs:
            for b in docs:
                if a != b:
                    add_relation(conn, a, b, "same_content_as",
                                 basis=f"identical sha256 {sha[:12]}", confidence=1.0)
                    counts["same_content_as"] += 1
                    by_sha_pair.add((a, b))

    # --- content-identical files whose bytes differ -------------------------
    # A second, independent derivation of the same relation type: documents
    # that extract to identical text but were never linked above because
    # their source bytes (and so their sha256) differ. Grouped by
    # _content_digest instead; a pair already linked by sha256 is skipped so
    # the same edge is never asserted twice under two different bases.
    all_doc_ids = [r["document_id"] for r in conn.execute("SELECT document_id FROM documents")]
    by_digest: dict[str, list[str]] = defaultdict(list)
    for doc_id in all_doc_ids:
        digest = _content_digest(conn, doc_id)
        if digest:
            by_digest[digest].append(doc_id)
    for digest, docs_with_digest in by_digest.items():
        if len(docs_with_digest) < 2:
            continue
        for a in docs_with_digest:
            for b in docs_with_digest:
                if a == b or (a, b) in by_sha_pair:
                    continue
                add_relation(conn, a, b, "same_content_as",
                             basis=f"identical extracted text {digest[:12]}", confidence=1.0)
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
    #
    # Edge direction matters and was inverted here once: a `superseded_by` edge
    # reads subject -> object, so its *from* side is the document that has been
    # superseded and its *to* side is the newer approval doing the superseding.
    # Marking the `to` side flagged every current NOA as superseded and left the
    # whole CertainTeed/Barrette chain with no active member at all.
    for r in conn.execute("""SELECT DISTINCT from_document_id AS d FROM relations
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
