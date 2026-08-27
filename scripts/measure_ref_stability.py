#!/usr/bin/env python3
"""Reproduce the measurements docs/four-layer-model-design.md §5.1 rests on:
four numbered sections, printing six figures between them (§3 and §4 each
print a second line beyond their headline number).

Read-only. Run from the repository root:

    python3 scripts/measure_ref_stability.py
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fence_evidence.paths import EVIDENCE_DB  # noqa: E402
from fence_evidence.refs import ref_id  # noqa: E402


def _alt_hash(s: str) -> str:
    """A counterfactual identity scheme's hash -- deliberately NOT ref_id.

    §3 measures schemes that are explicitly not the shipped identifier.
    `ref_id`'s `bbox` argument is "the raw elements.bbox text, passed
    through unchanged" per its own docstring, not a general-purpose payload
    slot, so these are hashed independently rather than minted through
    ref_id with element text stuffed into that argument.
    """
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def main() -> int:
    if not Path(EVIDENCE_DB).exists():
        print("no store at", EVIDENCE_DB, "-- run `cli ingest --all` first")
        return 2
    conn = sqlite3.connect(f"file:{EVIDENCE_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    rows = [dict(r) for r in conn.execute("""
        SELECT e.element_id, e.page_no, e.bbox, e.element_type,
               COALESCE(NULLIF(e.text, ''), NULLIF(e.ocr_text, '')) AS body,
               v.sha256
          FROM elements e
          JOIN document_versions v ON v.version_id = e.version_id""")]

    # 1 -- hash sensitivity: a 0.02pt shift changes the id completely.
    sha = "00c965f58d3030b7e7c8a6c8c0b7e99f1579c5599dc476c8f6a62dd88c6cdd58"
    today, shifted = "[117.69, 271.47, 266.99, 294.03]", "[117.69, 271.47, 266.99, 294.05]"
    print("1. hash sensitivity to a 0.02pt bbox shift (1/3600 inch)")
    print(f"   {today} -> {ref_id(sha, 5, today)}")
    print(f"   {shifted} -> {ref_id(sha, 5, shifted)}")

    # 2 -- index rebuild cost and collision count.
    t0 = time.time()
    idx: dict[str, set[tuple]] = {}
    for r in rows:
        idx.setdefault(ref_id(r['sha256'], r['page_no'], r['bbox']), set()).add(
            (r["sha256"], r["page_no"], r["bbox"]))
    ms = (time.time() - t0) * 1000
    true_collisions = sum(1 for v in idx.values() if len(v) > 1)
    print(f"\n2. index over {len(rows)} elements: {len(idx)} distinct ids "
          f"in {ms:.0f} ms, {true_collisions} true collisions")

    # 3 -- alternative schemes, to show a better hash is not the fix. Only
    # the shipped scheme goes through ref_id; the other two are counterfactual
    # (see _alt_hash) and hash different content (normalised text, and
    # type+text) that ref_id's bbox argument does not accept.
    def norm(t): return re.sub(r"\s+", " ", t or "").strip().lower()
    schemes = {
        "sha:page:bbox (shipped)": lambda r: ref_id(r['sha256'], r['page_no'], r['bbox']),
        "sha:page:text": lambda r: _alt_hash(f"{r['sha256']}:{r['page_no']}:{norm(r['body'])}"),
        "sha:page:type:text": lambda r: _alt_hash(
            f"{r['sha256']}:{r['page_no']}:{r['element_type']}:{norm(r['body'])}"),
    }
    print("\n3. alternative identity schemes")
    for name, fn in schemes.items():
        ids = Counter(fn(r) for r in rows)
        shared = sum(v for v in ids.values() if v > 1)
        print(f"   {name:26} {len(ids):>7} distinct  {shared:>7} elements share an id")
    print(f"   elements with no text at all: "
          f"{sum(1 for r in rows if not norm(r['body']))}")

    # 4 -- the kind collision: a bbox-less element ref equals its page ref.
    pages = {}
    for r in conn.execute("""SELECT p.page_no, v.sha256 FROM pages p
              JOIN document_versions v ON v.version_id = p.version_id"""):
        pages[ref_id(r['sha256'], r['page_no'], None)] = (r["sha256"], r["page_no"])
    hits = [r for r in rows
            if ref_id(r['sha256'], r['page_no'], r['bbox']) in pages]
    print(f"\n4. kind collisions (a bbox-less element ref == its page ref): {len(hits)}")
    for r in hits[:3]:
        # Bound to a name first: nesting same-type quotes inside an f-string is
        # only legal from Python 3.12 (PEP 701) and this repo's floor is 3.10.
        rid = ref_id(r['sha256'], r['page_no'], r['bbox'])
        print(f"   {rid} = element {r['element_id']} "
              f"({r['element_type']}, bbox={r['bbox']}) AND page {r['page_no']}")

    shared_ids = {k for k, v in Counter(
        ref_id(r['sha256'], r['page_no'], r['bbox']) for r in rows
        if r["bbox"]).items() if v > 1}
    print(f"   ids covering more than one element: {len(shared_ids)}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
