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


def ref_id(sha256: str, page_no: int, bbox: str | None) -> str:
    """A reference's id, derived from what it points at and nothing else.

    ``bbox`` is the raw ``elements.bbox`` text, passed through unchanged. Do not
    normalise, round or re-serialise it: the 431 published cites were minted
    from the stored string exactly as SQLite returns it.
    """
    return hashlib.sha256(f"{sha256}:{page_no}:{bbox}".encode()).hexdigest()[:16]
