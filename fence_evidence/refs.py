"""The evidence identifier, and its inverse. One owner.

A ref names **a rectangle of a page of one specific version of one document**,
and nothing else. It is derived from what it points at, so the same evidence
gets the same id from any process, on any machine, in any order -- publishing a
snapshot twice does not churn ids.

Why this module exists: `ref_id` lived in `snapshot.py` and was designed a
second time, incompatibly, in `docs/integration/source-refs-design.md` 1 as an
`sref_` locator over a seven-field tuple. Building that would have produced two
identifiers for the same evidence, which is the "two definitions of the same
picture" failure the same document rejects Pillow crops for in 4.2. Addressing
now has an owner.

Two properties worth knowing before changing anything here:

* **The formula is frozen.** The published snapshot carries 431 cites derived
  from it. `bbox` is interpolated as the **stored text**, verbatim -- it never
  passes through `canonical.canonical_bytes`, so that module's refusal of floats
  never applies here.
* **The inverse is a projection, never a table.** `build_index` reconstructs
  `ref_id -> Locus` from canonical rows in roughly 220 ms. Storing it would
  create a second copy of the truth that could drift; rebuilding it cannot.
  Same discipline as `retrieval_units`.

What this module does NOT yet do, deliberately -- see
`docs/four-layer-model-design.md` 5.2, which is plan 2:

* The id omits `kind`, so a bbox-less element ref is byte-identical to its page
  ref. `build_index` reports that rather than hiding it.
* The id is not injective over elements: 9,929 ids cover more than one element.
  `Locus.element_ids` therefore carries **all** of them and no rule picks one.
"""
from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass


def ref_id(sha256: str, page_no: int, bbox: str | None) -> str:
    """A reference's id, derived from what it points at and nothing else.

    ``bbox`` is the raw ``elements.bbox`` text, passed through unchanged. Do not
    normalise, round or re-serialise it: the 431 published cites were minted
    from the stored string exactly as SQLite returns it.
    """
    return hashlib.sha256(f"{sha256}:{page_no}:{bbox}".encode()).hexdigest()[:16]


@dataclass(frozen=True)
class Locus:
    """What a ref names: a rectangle of a page of one document version.

    ``element_ids`` carries **every** element inside that rectangle, not one.
    9,929 ids cover more than one element -- commonly two paragraphs with an
    identical bbox -- and silently picking one would attribute the wrong quote
    to a citation. Choosing between them is a rule this module deliberately does
    not yet have; see docs/four-layer-model-design.md 5.2.

    ``is_page`` is True when this id is also the whole-page ref for its page.
    That can be true *at the same time* as ``element_ids`` being non-empty,
    because the id omits `kind`: a bbox-less element produces the identical id
    to its own page. One such collision exists in this corpus today.
    """
    sha256: str
    page_no: int
    bbox: str | None
    element_ids: tuple[str, ...]
    is_page: bool


def build_index(conn: sqlite3.Connection) -> dict[str, Locus]:
    """Rebuild ``ref_id -> Locus`` from canonical rows. Roughly 220 ms.

    A projection, not a store. Nothing is written and nothing is cached: an
    index held on disk could disagree with the rows it describes, and one
    rebuilt on demand cannot. Same reasoning as ``retrieval_units``.
    """
    elements: dict[str, list[str]] = {}
    loci: dict[str, tuple[str, int, str | None]] = {}

    for row in conn.execute("""
            SELECT e.element_id, e.page_no, e.bbox, v.sha256
              FROM elements e
              JOIN document_versions v ON v.document_id = e.document_id"""):
        rid = ref_id(row["sha256"], row["page_no"], row["bbox"])
        elements.setdefault(rid, []).append(row["element_id"])
        loci[rid] = (row["sha256"], row["page_no"], row["bbox"])

    page_ids: set[str] = set()
    for row in conn.execute("""
            SELECT p.page_no, v.sha256
              FROM pages p
              JOIN document_versions v ON v.version_id = p.version_id"""):
        rid = ref_id(row["sha256"], row["page_no"], None)
        page_ids.add(rid)
        loci.setdefault(rid, (row["sha256"], row["page_no"], None))

    return {rid: Locus(sha256=sha, page_no=page, bbox=bbox,
                       element_ids=tuple(sorted(elements.get(rid, ()))),
                       is_page=rid in page_ids)
            for rid, (sha, page, bbox) in loci.items()}


def resolve(index: dict[str, Locus], rid: str) -> Locus | None:
    """One lookup. ``None`` means the id names nothing in this store.

    Callers must treat ``None`` as a hard failure, never as an empty result: a
    published value citing an id that resolves to nothing violates contract
    obligation 3.
    """
    return index.get(rid)
