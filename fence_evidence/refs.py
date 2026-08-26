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


import json
from pathlib import Path


def verify_snapshots(conn: sqlite3.Connection, *,
                     root: Path | None = None) -> dict:
    """Assert every published citation still resolves against this store.

    Contract obligation 3 requires every published *value* -- not every
    *warning* -- to carry a *resolvable* ``SourceRef``. A snapshot is
    immutable, so a citation that stops resolving can never be repaired --
    which makes silent rot the worst possible failure mode and a loud one the
    whole point of this function.

    This walks the ENTIRE payload, not just ``warnings[].cites[]``. Today all
    431 published citations happen to live there, but the snapshot's other
    top-level keys -- ``combinations, models, parameters, part_types, parts,
    procedures, rules`` -- are all declared citation-bearing and currently
    empty. A walk scoped to ``warnings`` would under-count silently the day
    any of those sections gains a citation, which is exactly the failure class
    this command exists to eliminate. The walk mirrors ``snapshot.py``'s own
    ``verify()`` in shape: a recursive ``walk(node, path)`` that accumulates a
    ``$.foo[3].bar`` path as it descends, one file over.

    A dict is a citation when it sits inside a list bound to the key
    ``"cites"`` and carries an ``id``. That is a narrower test than "any dict
    with `id` and `belongs_to`": a well-formed citation is `SourceRef(id,
    belongs_to)` via `asdict`, but so is a `Gap` -- gaps carry a bare `id` too,
    and there are 63 of them in the shipped snapshot outside any `cites` list.
    Gating on shape alone over-counts them. Gating on the `cites` list instead
    of on `belongs_to` being present also means a *malformed* citation --
    missing `belongs_to` entirely -- is still recognised as a citation rather
    than silently skipped; see ``unknown_versions`` below, which is exactly
    for catching that.

    Tombstoned snapshots are skipped: their payload is gone by design, and
    holding them to a resolvability promise would report a deliberate excision
    as damage.
    """
    from .snapshot_store import SNAPSHOT_DIR

    base = Path(root) if root is not None else SNAPSHOT_DIR
    index = build_index(conn)
    known_versions = {r["sha256"] for r in
                      conn.execute("SELECT sha256 FROM document_versions")}

    out = {"snapshots": 0, "tombstoned_skipped": 0, "cites": 0, "resolved": 0,
           "dangling": [], "unknown_versions": []}
    if not base.exists():
        return out

    def walk(node, sid, path="$", in_cites=False):
        if isinstance(node, dict):
            if in_cites and "id" in node:
                out["cites"] += 1
                rid, owner = node.get("id"), node.get("belongs_to")
                if resolve(index, rid) is None:
                    out["dangling"].append(
                        {"snapshot_id": sid, "ref_id": rid, "belongs_to": owner,
                         "at": path,
                         "reason": "no canonical row produces this id; the "
                                   "evidence it named is not in this store"})
                else:
                    out["resolved"] += 1
                # An absent or empty `belongs_to` must be visible, not skipped:
                # `owner and ...` would short-circuit on a falsy owner and the
                # cite would be reported neither dangling nor unknown -- it
                # would simply vanish.
                if not owner or owner not in known_versions:
                    out["unknown_versions"].append(
                        {"snapshot_id": sid, "ref_id": rid, "belongs_to": owner})
            for k, v in node.items():
                walk(v, sid, f"{path}.{k}", in_cites=(k == "cites"))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, sid, f"{path}[{i}]", in_cites=in_cites)

    for snap_path in sorted(base.glob("*.json")):
        payload = json.loads(snap_path.read_bytes())
        if payload.get("tombstoned"):
            out["tombstoned_skipped"] += 1
            continue
        out["snapshots"] += 1
        sid = payload.get("snapshot_id", snap_path.stem)
        walk(payload, sid)
    return out
