# Plan 1 — `refs.py`: one owner, one index, one guard

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the evidence identifier a single owning module, a rebuildable inverse index, and a command that fails loudly when any published citation stops resolving.

**Architecture:** `ref_id` moves out of `snapshot.py` into a new `fence_evidence/refs.py`, which also gains the inverse — a `ref_id → locus` index rebuilt from canonical rows in ~220 ms and never stored, exactly like `retrieval_units`. On top of that sits `cli refs --verify`, which walks every un-tombstoned published snapshot and asserts every `cites[].id` still resolves. **No schema change, no behaviour change to any published byte.** This plan builds the *detector* for the correctness hole that plan 2 fixes, so that plan 2 has a regression guard from its first commit.

**Tech Stack:** Python 3.10+, standard library only. `sqlite3`, `hashlib`, `unittest`. No third-party packages — every one must stay optional (`guide.md`).

**Spec:** `docs/four-layer-model-design.md` — read §5, §5.1 and §5.2 before starting. This plan implements §8 row 1.

## Global Constraints

Copied verbatim from `CLAUDE.md` and `guide.md`. Every task's requirements implicitly include these.

- **The corpus is read-only.** Never modify, rename, dedupe or delete anything under `manuals/`, `china/manuals/` or `data/`. Write only to `workspace/`, via `paths.open_write` — never a bare `open(..., "w")`.
- **Never `git lfs pull` from CI or from an agent.** Use `python3 -m fence_evidence.cli fetch`.
- **Stdlib plus poppler and tesseract only.** Every third-party package stays optional.
- **Run commands from the repository root**: `python3 -m fence_evidence.cli …`. The package is not installed and is not under `src/`.
- **Test entry point is `python3 tests/run_tests.py`** — it is the only runner that reports skips correctly. A bare `python3 -m unittest` from `tests/` shows a missing store as a failure rather than a skip.
- **Never derive `lang` from `corpus_track`.** Not touched by this plan; listed because it is a standing tripwire (`tests/test_basis_columns.py`).
- **Every reference points DOWN a layer, never up.** `tests/test_pointer_direction.py` enforces it. This plan adds no new pointer.
- **Do not change `ref_id`'s formula.** 431 published cites depend on
  `sha256(f"{content_hash}:{page_no}:{bbox}")[:16]` with `bbox` interpolated as the *stored text*, verbatim. Moving the function must not alter a single output byte.
- **`SCHEMA_VERSION` stays at 3.** This plan adds no table and no column.

---

## File Structure

| File | Responsibility |
|---|---|
| `fence_evidence/refs.py` | **New.** Owns `ref_id`, the `Locus` record, `build_index`, `resolve`, and `verify_snapshots`. The single definition of "what a ref names". |
| `fence_evidence/snapshot.py` | **Modify.** Delete its local `ref_id`, import from `refs`. Nothing else changes. |
| `fence_evidence/cli.py` | **Modify.** Add the `refs` subcommand. |
| `scripts/measure_ref_stability.py` | **New.** Reproduces the four measurements the design rests on. Follows the existing `scripts/measure_crop_cost.py` precedent. |
| `tests/test_refs.py` | **New.** Owns every assertion about identity, the index, and verification. |

---

## Task 0: Make the design's measurements reproducible

The design in `docs/four-layer-model-design.md` §5.1 rests on four numbers that were measured ad hoc. Commit the harness so they can be re-run, in the style of the existing `scripts/measure_crop_cost.py`.

**Files:**
- Create: `scripts/measure_ref_stability.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: nothing other tasks import. This is a standalone script run by hand.

- [ ] **Step 1: Write the script**

```python
#!/usr/bin/env python3
"""Reproduce the four measurements docs/four-layer-model-design.md §5.1 rests on.

Read-only. Run from the repository root:

    python3 scripts/measure_ref_stability.py
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fence_evidence.paths import EVIDENCE_DB  # noqa: E402


def _h(s: str) -> str:
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
          JOIN document_versions v ON v.document_id = e.document_id""")]

    # 1 -- hash sensitivity: a 0.02pt shift changes the id completely.
    sha = "00c965f58d3030b7e7c8a6c8c0b7e99f1579c5599dc476c8f6a62dd88c6cdd58"
    today, shifted = "[117.69, 271.47, 266.99, 294.03]", "[117.69, 271.47, 266.99, 294.05]"
    print("1. hash sensitivity to a 0.02pt bbox shift (1/3600 inch)")
    print(f"   {today} -> {_h(f'{sha}:5:{today}')}")
    print(f"   {shifted} -> {_h(f'{sha}:5:{shifted}')}")

    # 2 -- index rebuild cost and collision count.
    t0 = time.time()
    idx: dict[str, set[tuple]] = {}
    for r in rows:
        idx.setdefault(_h(f"{r['sha256']}:{r['page_no']}:{r['bbox']}"), set()).add(
            (r["sha256"], r["page_no"], r["bbox"]))
    ms = (time.time() - t0) * 1000
    true_collisions = sum(1 for v in idx.values() if len(v) > 1)
    print(f"\n2. index over {len(rows)} elements: {len(idx)} distinct ids "
          f"in {ms:.0f} ms, {true_collisions} true collisions")

    # 3 -- alternative schemes, to show a better hash is not the fix.
    def norm(t): return re.sub(r"\s+", " ", t or "").strip().lower()
    schemes = {
        "sha:page:bbox (shipped)": lambda r: _h(f"{r['sha256']}:{r['page_no']}:{r['bbox']}"),
        "sha:page:text": lambda r: _h(f"{r['sha256']}:{r['page_no']}:{norm(r['body'])}"),
        "sha:page:type:text": lambda r: _h(
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
        pages[_h(f"{r['sha256']}:{r['page_no']}:None")] = (r["sha256"], r["page_no"])
    hits = [r for r in rows
            if _h(f"{r['sha256']}:{r['page_no']}:{r['bbox']}") in pages]
    print(f"\n4. kind collisions (a bbox-less element ref == its page ref): {len(hits)}")
    for r in hits[:3]:
        # Bound to a name first: nesting same-type quotes inside an f-string is
        # only legal from Python 3.12 (PEP 701) and this repo's floor is 3.10.
        rid = _h(f"{r['sha256']}:{r['page_no']}:{r['bbox']}")
        print(f"   {rid} = element {r['element_id']} "
              f"({r['element_type']}, bbox={r['bbox']}) AND page {r['page_no']}")

    shared_ids = {k for k, v in Counter(
        _h(f"{r['sha256']}:{r['page_no']}:{r['bbox']}") for r in rows
        if r["bbox"]).items() if v > 1}
    print(f"   ids covering more than one element: {len(shared_ids)}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it and check the numbers match the spec**

Run: `python3 scripts/measure_ref_stability.py`

Expected, against the store as of 2026-08-26:
- hash sensitivity: `cd9f0d9d9c4e300f` then `e25f68cec20de1bc`
- index: `81794` elements, `69306` distinct ids, `0` true collisions
- `sha:page:text` yields `56090` distinct — **fewer** than the shipped scheme
- elements with no text: `6660`
- kind collisions: `416` element rows, all collapsing onto the single id `15d1ceaf5cb24da2`
- ids covering more than one element: `9929`

If any number differs, **stop and report it** rather than editing the spec. A different number means the store was rebuilt and the design's premises need re-checking.

- [ ] **Step 3: Commit**

```bash
git add scripts/measure_ref_stability.py
git commit -m "Make the ref-stability measurements reproducible

The four numbers docs/four-layer-model-design.md 5.1 rests on were measured
ad hoc. Same precedent as scripts/measure_crop_cost.py: the harness is
committed so the claim can be re-checked rather than believed."
```

---

## Task 1: `refs.py` owns `ref_id`, and the snapshot does not change

**Files:**
- Create: `fence_evidence/refs.py`
- Modify: `fence_evidence/snapshot.py:166-168` (delete `ref_id`), and its import block
- Test: `tests/test_refs.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `fence_evidence.refs.ref_id(sha256: str, page_no: int, bbox: str | None) -> str`. Tasks 2 and 3 import it. `snapshot.py` re-exports it so `from .snapshot import ref_id` keeps working for `tests/test_snapshot_build.py:81`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_refs.py`:

```python
"""The evidence identifier, its inverse, and the guard on published citations.

Why this module exists at all: `ref_id` was defined in `snapshot.py` and
proposed a second time, incompatibly, in
`docs/integration/source-refs-design.md` 1 as an `sref_` locator. Two
identifiers for the same evidence is the failure that document itself rejects
Pillow crops for in 4.2. Addressing had no owner, so it got designed wherever
it was needed. It has one now.
"""
import unittest

import context  # noqa: F401  -- puts the repo root on sys.path
from fence_evidence.refs import ref_id


class TestIdentity(unittest.TestCase):
    """The formula is frozen: 431 published cites depend on it."""

    SHA = "00c965f58d3030b7e7c8a6c8c0b7e99f1579c5599dc476c8f6a62dd88c6cdd58"
    BBOX = "[117.69, 271.47, 266.99, 294.03]"

    def test_the_shipped_formula_is_unchanged(self):
        # Measured from the live store on 2026-08-26. If this fails, every
        # published citation has been invalidated.
        self.assertEqual(ref_id(self.SHA, 5, self.BBOX), "cd9f0d9d9c4e300f")

    def test_the_same_evidence_gets_the_same_id(self):
        self.assertEqual(ref_id(self.SHA, 5, self.BBOX),
                         ref_id(self.SHA, 5, self.BBOX))

    def test_a_hundredth_of_a_point_changes_the_id(self):
        """Not a bug -- the reason plan 2 exists. Recorded so it is not a surprise."""
        shifted = "[117.69, 271.47, 266.99, 294.05]"
        self.assertNotEqual(ref_id(self.SHA, 5, self.BBOX),
                            ref_id(self.SHA, 5, shifted))

    def test_different_bytes_give_a_different_id(self):
        other = "2f446717ee750908059bed45ce06552636671944ca8c1cbbe922092e8d769c3c"
        self.assertNotEqual(ref_id(self.SHA, 5, self.BBOX),
                            ref_id(other, 5, self.BBOX))

    def test_a_null_bbox_is_accepted_and_is_the_page_form(self):
        self.assertEqual(len(ref_id(self.SHA, 5, None)), 16)

    def test_snapshot_still_re_exports_it(self):
        """test_snapshot_build.py imports it from there; do not break that."""
        from fence_evidence.snapshot import ref_id as via_snapshot
        self.assertIs(via_snapshot, ref_id)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `cd tests && python3 -m unittest test_refs -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fence_evidence.refs'`

- [ ] **Step 3: Create `refs.py` with just the identifier**

```python
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
```

- [ ] **Step 4: Point `snapshot.py` at it**

In `fence_evidence/snapshot.py`, delete lines 166-168 (the `def ref_id` block, including its docstring) and add to the import block near the top:

```python
from .refs import ref_id
```

Keep the name importable from `snapshot` — `tests/test_snapshot_build.py:81` and
`SnapshotBuilder.source_ref` (line 214) both use it, and the import above
satisfies both. Do not add an alias or a wrapper; the imported name *is* the
re-export.

- [ ] **Step 5: Run the new tests and the snapshot tests**

Run: `python3 tests/run_tests.py 2>&1 | tail -20`
Expected: PASS, with the same skip count as before this task. In particular
`test_snapshot_build` and `test_canonical` must be unchanged.

- [ ] **Step 6: Prove no published byte moved**

Run:

```bash
python3 -m fence_evidence.cli snapshot --build --dry-run > /tmp/after.json
python3 -c "
import json, glob
built = json.load(open('/tmp/after.json'))
onfile = json.load(open(glob.glob('workspace/snapshots/*.json')[0]))
b = {c['id'] for w in built.get('warnings', []) for c in w.get('cites', [])}
o = {c['id'] for w in onfile.get('warnings', []) for c in w.get('cites', [])}
print('cites built:', len(b), 'cites on file:', len(o))
print('IDENTICAL' if b == o else f'DIFFER: {len(b ^ o)} ids moved')
"
```

Expected: `cites built: 431 cites on file: 431` and `IDENTICAL`.

If it prints `DIFFER`, the refactor changed the formula. Revert and find out why
before continuing — this is the one thing this task must not do.

- [ ] **Step 7: Commit**

```bash
git add fence_evidence/refs.py fence_evidence/snapshot.py tests/test_refs.py
git commit -m "Give the evidence identifier one owning module

ref_id was defined in snapshot.py and designed a second time, incompatibly,
in source-refs-design.md 1. Two ids for one piece of evidence is the failure
that document rejects Pillow crops for. The formula is unchanged and the 431
published cites are byte-identical; only the ownership moved."
```

---

## Task 2: the inverse — a rebuildable ref index

**Files:**
- Modify: `fence_evidence/refs.py`
- Test: `tests/test_refs.py`

**Interfaces:**
- Consumes: `ref_id` from Task 1.
- Produces:
  - `Locus` — frozen dataclass with fields `sha256: str`, `page_no: int`, `bbox: str | None`, `element_ids: tuple[str, ...]`, `is_page: bool`.
  - `build_index(conn: sqlite3.Connection) -> dict[str, Locus]`
  - `resolve(index: dict[str, Locus], rid: str) -> Locus | None`
  - Task 3 imports both.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_refs.py`:

```python
from context import requires_full_store
from fence_evidence.refs import Locus, build_index, resolve


@requires_full_store
class TestIndex(unittest.TestCase):
    """The inverse is a projection: rebuilt from canonical rows, never stored."""

    @classmethod
    def setUpClass(cls):
        from fence_evidence.store import connect
        cls.conn = connect(read_only=True)
        cls.index = build_index(cls.conn)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_it_indexes_the_whole_store(self):
        self.assertGreater(len(self.index), 60_000)

    def test_no_two_different_loci_share_an_id(self):
        """A true hash collision would make a citation ambiguous across documents."""
        for rid, locus in self.index.items():
            self.assertIsInstance(locus, Locus)
        # Distinct (sha, page, bbox) triples must map to distinct ids.
        triples = {(l.sha256, l.page_no, l.bbox) for l in self.index.values()}
        self.assertEqual(len(triples), len(self.index))

    def test_a_known_element_resolves_to_its_rectangle(self):
        rid = ref_id(
            "00c965f58d3030b7e7c8a6c8c0b7e99f1579c5599dc476c8f6a62dd88c6cdd58",
            5, "[117.69, 271.47, 266.99, 294.03]")
        locus = resolve(self.index, rid)
        self.assertIsNotNone(locus)
        self.assertEqual(locus.page_no, 5)
        self.assertIn("element-da08178108-0022", locus.element_ids)

    def test_an_unknown_id_resolves_to_none(self):
        self.assertIsNone(resolve(self.index, "0" * 16))

    def test_a_shared_rectangle_carries_every_element_not_one(self):
        """9,929 ids cover more than one element. Picking one silently would be
        a wrong quote; carrying all of them is the honest shape. See 5.2."""
        shared = [l for l in self.index.values() if len(l.element_ids) > 1]
        self.assertGreater(len(shared), 1_000)

    def test_page_refs_are_indexed_and_flagged(self):
        pages = [l for l in self.index.values() if l.is_page]
        self.assertGreater(len(pages), 1_000)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd tests && python3 -m unittest test_refs -v`
Expected: FAIL — `ImportError: cannot import name 'Locus'`

- [ ] **Step 3: Implement the index**

Add to `fence_evidence/refs.py`:

```python
import sqlite3
from dataclasses import dataclass


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
```

- [ ] **Step 4: Run the tests**

Run: `python3 tests/run_tests.py 2>&1 | tail -12`
Expected: PASS, no new skips.

- [ ] **Step 5: Commit**

```bash
git add fence_evidence/refs.py tests/test_refs.py
git commit -m "Add the ref index as a projection, not a table

ref_id is one-way, so GET /source-refs/{id} needs an inverse. Rebuilding it
from canonical rows takes ~320 ms with zero true collisions, so there is no
reason to store it -- and a stored index can drift from the rows it describes
while a rebuilt one cannot. Locus carries every element in a shared rectangle
rather than picking one, because picking would mean a wrong quote."
```

---

## Task 3: `cli refs --verify` — the guard

This is the deliverable that makes plan 2 safe: it turns *silent* citation rot into a non-zero exit.

**Files:**
- Modify: `fence_evidence/refs.py`
- Modify: `fence_evidence/cli.py` (parser block and dispatch chain)
- Test: `tests/test_refs.py`

**Interfaces:**
- Consumes: `build_index`, `resolve`, `Locus` from Task 2.
- Produces: `verify_snapshots(conn: sqlite3.Connection, *, root: Path | None = None) -> dict` returning keys `snapshots`, `tombstoned_skipped`, `cites`, `resolved`, `dangling` (list of dicts with `snapshot_id`, `ref_id`, `belongs_to`, `reason`), and `unknown_versions` (list).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_refs.py`:

```python
from fence_evidence.refs import verify_snapshots


@requires_full_store
class TestVerify(unittest.TestCase):
    """Every published citation must still resolve. Obligation 3 in one command."""

    @classmethod
    def setUpClass(cls):
        from fence_evidence.store import connect
        cls.conn = connect(read_only=True)
        cls.result = verify_snapshots(cls.conn)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_it_looked_at_something(self):
        self.assertGreaterEqual(self.result["snapshots"], 1)
        self.assertGreaterEqual(self.result["cites"], 1)

    def test_every_published_cite_resolves_today(self):
        self.assertEqual(self.result["dangling"], [],
                         "a published value cites evidence that no longer "
                         "resolves; contract obligation 3 is violated and a "
                         "snapshot is immutable, so this cannot be repaired")

    def test_every_belongs_to_names_a_real_version(self):
        self.assertEqual(self.result["unknown_versions"], [])

    def test_resolved_and_dangling_account_for_every_cite(self):
        self.assertEqual(self.result["resolved"] + len(self.result["dangling"]),
                         self.result["cites"])


class TestVerifyDetectsRot(unittest.TestCase):
    """The guard must actually fire. Proven against a fabricated snapshot in a
    temporary directory, so no real published artifact is touched."""

    def test_a_dangling_cite_is_reported(self):
        import json
        import sqlite3
        import tempfile
        from pathlib import Path

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE documents(document_id TEXT);
            CREATE TABLE document_versions(version_id TEXT, document_id TEXT, sha256 TEXT);
            CREATE TABLE elements(element_id TEXT, document_id TEXT, page_no INT, bbox TEXT);
            CREATE TABLE pages(page_id TEXT, version_id TEXT, page_no INT);
            INSERT INTO document_versions VALUES ('v1', 'd1', 'aa');
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "snap1.json").write_text(json.dumps({
                "snapshot_id": "snap1",
                "warnings": [{"cites": [{"id": "f" * 16, "belongs_to": "aa"}]}],
            }))
            result = verify_snapshots(conn, root=root)
        self.assertEqual(result["cites"], 1)
        self.assertEqual(result["resolved"], 0)
        self.assertEqual(len(result["dangling"]), 1)
        self.assertEqual(result["dangling"][0]["ref_id"], "f" * 16)
        conn.close()

    def test_a_tombstoned_snapshot_is_skipped(self):
        import json
        import sqlite3
        import tempfile
        from pathlib import Path

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE document_versions(version_id TEXT, document_id TEXT, sha256 TEXT);
            CREATE TABLE elements(element_id TEXT, document_id TEXT, page_no INT, bbox TEXT);
            CREATE TABLE pages(page_id TEXT, version_id TEXT, page_no INT);
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "snap1.json").write_text(json.dumps({
                "snapshot_id": "snap1", "tombstoned": True,
                "warnings": [{"cites": [{"id": "f" * 16, "belongs_to": "aa"}]}],
            }))
            result = verify_snapshots(conn, root=root)
        self.assertEqual(result["tombstoned_skipped"], 1)
        self.assertEqual(result["cites"], 0)
        self.assertEqual(result["dangling"], [])
        conn.close()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd tests && python3 -m unittest test_refs -v`
Expected: FAIL — `ImportError: cannot import name 'verify_snapshots'`

- [ ] **Step 3: Implement `verify_snapshots`**

Add to `fence_evidence/refs.py`:

```python
import json
from pathlib import Path


def verify_snapshots(conn: sqlite3.Connection, *,
                     root: Path | None = None) -> dict:
    """Assert every published citation still resolves against this store.

    Contract obligation 3 requires every published value to carry a *resolvable*
    ``SourceRef``. A snapshot is immutable, so a citation that stops resolving
    can never be repaired -- which makes silent rot the worst possible failure
    mode and a loud one the whole point of this function.

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

    for path in sorted(base.glob("*.json")):
        payload = json.loads(path.read_bytes())
        if payload.get("tombstoned"):
            out["tombstoned_skipped"] += 1
            continue
        out["snapshots"] += 1
        sid = payload.get("snapshot_id", path.stem)
        for warning in payload.get("warnings", []):
            for cite in warning.get("cites", []):
                out["cites"] += 1
                rid, owner = cite.get("id"), cite.get("belongs_to")
                if resolve(index, rid) is None:
                    out["dangling"].append(
                        {"snapshot_id": sid, "ref_id": rid, "belongs_to": owner,
                         "reason": "no canonical row produces this id; the "
                                   "evidence it named is not in this store"})
                else:
                    out["resolved"] += 1
                if owner and owner not in known_versions:
                    out["unknown_versions"].append(
                        {"snapshot_id": sid, "ref_id": rid, "belongs_to": owner})
    return out
```

- [ ] **Step 4: Add the CLI subcommand**

In `fence_evidence/cli.py`, add a parser block beside the other `sub.add_parser` calls — put it immediately after the `snapshot` block, since it is about published snapshots:

```python
    p = sub.add_parser("refs",
                       help="the evidence identifier: rebuild the index, or "
                            "verify every published citation still resolves")
    p.add_argument("--verify", action="store_true",
                   help="walk every un-tombstoned snapshot; exit non-zero on a "
                        "citation that no longer resolves")
    p.add_argument("--index", action="store_true",
                   help="rebuild the ref index and report its shape")
```

And add to the dispatch chain, beside the other `elif args.cmd == …` branches:

```python
    elif args.cmd == "refs":
        from .refs import build_index, verify_snapshots
        from .store import connect
        conn = connect(read_only=True)
        try:
            if args.verify:
                result = verify_snapshots(conn)
                _print(result)
                if result["dangling"] or result["unknown_versions"]:
                    print(f"FAILED: {len(result['dangling'])} published "
                          f"citation(s) no longer resolve. A snapshot is "
                          f"immutable, so this cannot be repaired -- see "
                          f"docs/four-layer-model-design.md 5.1.",
                          file=sys.stderr)
                    return 1
            else:
                index = build_index(conn)
                shared = [l for l in index.values() if len(l.element_ids) > 1]
                _print({"ref_ids": len(index),
                        "page_refs": sum(1 for l in index.values() if l.is_page),
                        "ids_covering_multiple_elements": len(shared)})
        finally:
            conn.close()
```

- [ ] **Step 5: Run the tests and the command**

Run: `python3 tests/run_tests.py 2>&1 | tail -12`
Expected: PASS.

Run: `python3 -m fence_evidence.cli refs --verify; echo "exit=$?"`
Expected: `"cites": 431`, `"resolved": 431`, `"dangling": []`, `exit=0`.

Run: `python3 -m fence_evidence.cli refs --index`
Expected: `"ref_ids": 71158` (element ids plus page ids, less the one overlap), `"page_refs": 1853`, and
`"ids_covering_multiple_elements": 9930` — one more than the 9,929 in the design, because `build_index` does not filter the bbox-less group.

- [ ] **Step 6: Commit**

```bash
git add fence_evidence/refs.py fence_evidence/cli.py tests/test_refs.py
git commit -m "Add cli refs --verify: published citations must still resolve

Obligation 3 requires every published value to carry a resolvable SourceRef,
and a snapshot is immutable -- so a citation that stops resolving can never be
repaired. Today all 431 resolve. This turns that from a fact somebody checked
once into a command that fails. It is the regression guard plan 2 needs before
it changes how re-extraction works."
```

---

## Task 4: record the two known defects as tripwires, and update the docs

Plan 2 fixes the §5.2 defects. Before then they should be *asserted current state*, so the fix has a measured before and after, and so nobody "fixes" one by accident without noticing.

**Files:**
- Modify: `tests/test_refs.py`
- Modify: `docs/state-and-gaps.md` (add a gap entry)
- Modify: `CLAUDE.md` (module map, commands, and the bite list)

**Interfaces:**
- Consumes: everything from Tasks 1-3.
- Produces: nothing importable.

- [ ] **Step 1: Write the tripwire tests**

Append to `tests/test_refs.py`:

```python
@requires_full_store
class TestKnownDefects(unittest.TestCase):
    """Asserted as *current state*, not as desired behaviour.

    Both are docs/four-layer-model-design.md 5.2 and both are plan 2's work.
    They are pinned here so that fixing one produces a visible failure rather
    than a silent change of meaning.
    """

    @classmethod
    def setUpClass(cls):
        from fence_evidence.store import connect
        cls.conn = connect(read_only=True)
        cls.index = build_index(cls.conn)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_the_id_omits_kind_so_a_page_ref_can_collide(self):
        """A bbox-less element produces the identical id to its own page.

        Measured: all 416 bbox-less elements collapse onto ONE id, which is also
        that page's page-ref. They are all in the ARCAT CSI MasterSpec DOCX at
        page 1 -- the document with no page geometry at all (G4). So its entire
        text is addressable only as "page 1", and a citation to any of the 416 is
        indistinguishable from a citation to any other, or to the whole page.
        """
        collisions = [l for l in self.index.values()
                      if l.is_page and l.element_ids]
        self.assertGreaterEqual(
            len(collisions), 1,
            "expected the known kind collision; if it is gone, plan 2 landed "
            "and this test should be replaced by its inverse")
        worst = max(collisions, key=lambda l: len(l.element_ids))
        self.assertGreater(
            len(worst.element_ids), 100,
            "the DOCX's bbox-less elements should all land on one id; if this "
            "dropped, either the DOCX gained geometry or the id gained `kind`")

    def test_the_id_is_not_injective_over_elements(self):
        """It addresses a rectangle, deliberately -- but a resolver still needs
        a stated rule for which element's text to quote."""
        shared = [l for l in self.index.values() if len(l.element_ids) > 1]
        self.assertGreater(len(shared), 1_000)
        worst = max(shared, key=lambda l: len(l.element_ids))
        self.assertGreater(len(worst.element_ids), 2)
```

- [ ] **Step 2: Run them**

Run: `cd tests && python3 -m unittest test_refs -v`
Expected: PASS, all classes.

- [ ] **Step 3: Add the gap entry to `docs/state-and-gaps.md`**

Insert a new section immediately before `### G10 — Not built at all (deliberate)`:

```markdown
### G38 — a toolchain upgrade silently breaks published citations — DETECTED, NOT FIXED

`ref_id` is `sha256(content_hash:page_no:bbox)[:16]`. Two of those three inputs
are permanent; `bbox` is a measurement produced by `pdftotext -bbox-layout`.
`store.py:475` already treats a version's identity as **bytes × toolchain** —
*"True when this exact content was already extracted by these exact tools"* —
but the fingerprint appears only in that guard, never in the `version_id`. So
when the fingerprint differs, ingest does not skip and `store.py:520`
`delete_version_rows()` **deletes** the canonical rows the old ids named.

Measured: a 0.02pt bbox shift — 1/3600 of an inch — takes `cd9f0d9d9c4e300f` to
`e25f68cec20de1bc`. The citation does not get repointed at wrong pixels; it
stops resolving. A snapshot is immutable, so **obligation 3 breaks
retroactively on an already-published artifact**, with no error anywhere. G31
is proof the event class occurs: a clean rebuild produced 81,788 elements where
the store had 81,794.

**Currently clean.** All **431** published cites resolve, spanning 3 extraction
runs. `python3 -m fence_evidence.cli refs --verify` asserts it and exits
non-zero otherwise, so this is now a detected condition rather than a silent
one.

**A better hash is not the fix** — measured over all 81,794 elements,
`sha:page:text` yields *fewer* distinct ids (56,090 against 69,306) and 6,660
`figure` elements have no text at all. A sub-page identifier cannot be stable
across re-extraction because the rectangle it names is itself produced by
extraction.

**Not closed because** the fix is extraction *editions* — putting the toolchain
fingerprint into the version's identity so re-extraction is additive, and
retaining an edition while any un-tombstoned snapshot cites it. ~31 MB per
edition on a 69 MB store. Designed in `docs/four-layer-model-design.md` §5.1;
plan 2 of `docs/four-layer-plan-1-refs.md`'s sequence.
```

- [ ] **Step 4: Update `CLAUDE.md`**

Three edits.

In the commands block, after the `snapshot --list` line:

```bash
python3 -m fence_evidence.cli refs --verify     # every published citation still resolves
python3 -m fence_evidence.cli refs --index      # rebuild the ref index and report it
```

In the "Publishing, added 2026-08-25" module list, add:

```
`refs.py` (the evidence identifier and its rebuildable inverse — one owner; the
`sref_` scheme in source-refs-design.md §1 is superseded)
```

In "Things that will bite you if you don't know them", add:

```markdown
- **`ref_id` embeds a bbox, and a re-extraction can move it.** A 0.02pt shift
  changes the id completely and `delete_version_rows()` removes the rows the old
  id named, so a toolchain upgrade breaks published citations retroactively and
  obligation 3 with them. All 431 currently resolve; `cli refs --verify` is the
  guard. The fix is extraction editions — see `docs/four-layer-model-design.md`
  §5.1 and G38. **Do not change `ref_id`'s formula**; published snapshots depend
  on it byte-for-byte.
```

- [ ] **Step 5: Run the whole suite one more time**

Run: `python3 tests/run_tests.py 2>&1 | tail -6`
Expected: PASS. Record the new test count for the commit message.

- [ ] **Step 6: Commit**

```bash
git add tests/test_refs.py docs/state-and-gaps.md CLAUDE.md
git commit -m "Pin the two known ref defects, and record G38

The kind collision and the non-injectivity are asserted as current state so
plan 2's fix produces a visible before and after rather than a silent change
of meaning. G38 records the real finding: a toolchain upgrade breaks
obligation 3 retroactively on immutable snapshots, and until editions land
cli refs --verify is what makes it loud."
```

---

## Definition of done

- [ ] `python3 tests/run_tests.py` passes with no new skips.
- [ ] `python3 -m fence_evidence.cli refs --verify` reports 431 cites, 431 resolved, 0 dangling, and exits 0.
- [ ] `python3 scripts/measure_ref_stability.py` reproduces all six numbers in Task 0 Step 2.
- [ ] The rebuilt snapshot's cite ids are byte-identical to the published ones (Task 1 Step 6).
- [ ] `grep -rn "def ref_id" fence_evidence/` returns exactly one hit, in `refs.py`.
- [ ] `SCHEMA_VERSION` is still 3 and `git diff` shows no change to `store.py`.

## What this plan deliberately does not do

Each is named so an implementer does not drift into it.

- **No schema change.** No new table, no new column, `SCHEMA_VERSION` stays 3.
- **No change to `ref_id`'s formula.** Task 1 Step 6 exists to prove that.
- **Does not fix the kind collision or the non-injectivity.** Plan 2. Task 4 pins them instead.
- **Does not implement editions.** Plan 2. This plan only builds the detector.
- **Does not touch `facts` or `table_read_candidates`.** Plan 3.
- **No HTTP surface, no crop rendering, no `GET /source-refs/{id}`.** `crops.py` stays unwired; transport is unspecified by the contract and is a separate decision.
- **Does not delete or re-banner `docs/curation/`.** Open decision 4 in the design.
