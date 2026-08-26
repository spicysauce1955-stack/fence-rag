# Four layers, one claim table, and extraction editions

```text
Status:    Design, APPROVED for planning 2026-08-26. Nothing here is implemented.
Written:   2026-08-26, after a reassessment prompted by two questions —
           "isn't the layering getting too complicated and entangled?" and
           "what if each layer just pointed at the previous one?"
Authority: Advisory on internals. It changes no BINDING contract item and needs
           no amendment. The authorities are unchanged: docs/integration/contract.md
           (FROZEN v1.1) at the boundary, docs/mvp-implementation-spec.md inside
           it, guide.md's twelve prohibitions.
Supersedes: the five-layer taxonomy in docs/layering.md §2 (its RULE is kept
           verbatim); docs/curation/02-curation-schema.md in full;
           docs/integration/source-refs-design.md §1 only (the `sref_` locator).
           That document's §3 response shape, §4.1 crop transform and §7
           fixtures all stand.
Plans:     docs/four-layer-plan-1-refs.md  (plan 1 of 3)
Measured:  every number here comes from the store or the repository. §10 has the
           commands. Measured 2026-08-26 against workspace/indexes/evidence.db.
```

---

## 1. The question, and the honest answer

**The layer count was not the problem. The code is not the problem.**

| | |
|---|---:|
| `fence_evidence/` | **9,075** lines, 21 modules, largest `store.py` at 726 |
| `docs/` | **14,608** lines, 41 files, largest `knowledge-datamodel.md` at 1,611 |
| Design docs that are proposals which partially landed | **14 of 41** |

More design than implementation, and a third of the design provisional. Three
specific causes account for it.

### 1.1 A shelved parallel schema

`docs/curation/02-curation-schema.md` (1,086 lines) proposes **52 `cur_*`
tables** — `cur_claims`, `cur_claim_evidence`, `cur_table_readings`,
`cur_reviews`, `cur_entities`, `cur_gaps`, `cur_procedures`, `cur_page_maps`
and more. It re-models `facts`, `table_read_candidates`, `relations`,
`quality_issues`, `documents`, and the gap/warning/procedure shapes
`snapshot.py` already builds. It is **entirely unimplemented**, and its one
load-bearing idea (C0) shipped as build-plan A1 on 2026-08-25.

The useful fraction landed; the rest remains a *competing* design every reader
must reconcile against the code.

### 1.2 One concept designed twice, because nothing owns it

`ref_id` exists in two incompatible forms:

- **Shipped.** `snapshot.py:166` — `sha256(f"{content_hash}:{page_no}:{bbox}")[:16]`.
  The published snapshot contains **431** of these across 282 warnings, as
  `cites[].id`.
- **Proposed.** `source-refs-design.md` §1 — an `sref_` prefix over a canonical
  seven-field locator including `kind`.

Building the second would produce two identifiers for the same evidence — the
"two definitions of the same picture" failure that the same document rejects
Pillow crops for in §4.2. Cause: **addressing has no owning module**, so it was
designed wherever it was needed.

### 1.3 A claim lives in two tables

| Table | Columns | Written by |
|---|---:|---|
| `facts` | 21 | `facts.py` |
| `table_read_candidates` | 23 | `table_review.py` |
| — | — | `promote_tables.py` and `table_review.promote()` **copy rows from the second into the first** |

That copy caused three recorded incidents:

- **G18** — `cli facts --extract` deleted the whole `facts` table, destroying 324
  promoted rows **silently and unrecoverably**, because the candidates still
  recorded the deleted fact ids.
- **G17** — needed a bespoke `revoke_machine_promotions()` to walk the copy back.
- **The layering fix** — `promoted_fact_id` pointed *up* a layer and had to be
  inverted into `facts.from_candidate_id`, deleting a cleanup statement and a
  test that policed a bug the schema now forbids.

Three incidents, one cause: the same claim exists in two places and moving
between them is a copy.

---

## 2. What we actually need

From `contract.md` and `guide.md`, stripped to obligations:

1. Preserve the corpus read-only and record what each page contained, with
   geometry, so evidence can be **shown** to a person.
2. Hold values with their conditions and provenance, and record **who checked
   each one** (obligation 6: nothing reaches curation level 2 without a person
   having compared it to the source image).
3. Publish immutable, content-hashed snapshots where every published value cites
   a **resolvable** `SourceRef` (obligation 3) and every silence is an explicit
   `Gap` (obligation 8).
4. Serve a human-facing discovery surface — search, and `GET /source-refs/{id}`.

Everything else is a means. Four layers cover all four.

---

## 3. The model

### 3.1 Four layers, and the rule kept verbatim

The rule from `docs/layering.md` is **kept exactly as written**:

> Every reference points **down** a layer, never up. A row may name what it was
> derived FROM, never what was derived FROM IT.

| | Layer | Holds | Built by |
|---|---|---|---|
| **S** | Sources | the corpus — 144 files, read-only, content-addressed | `cli fetch` |
| **C** | Canonical | what each page contained — 81,794 elements, boxes, page images | `cli ingest` |
| **K** | Claims | a value, its conditions, its evidence, its author, its review state | `cli facts --extract`, `cli table-review`, `cli review` |
| **P** | Published | the contract's shapes, hashed and immutable | `cli snapshot --build` |

Two cross-cutting modules, each with exactly one owner:

| Module | Owns | Consumed by |
|---|---|---|
| `refs.py` | the evidence identifier, its inverse, and the five kinds | Published, Discovery |
| projections | `retrieval_units` + FTS, and the ref index | Discovery |

Both are **derived and rebuildable**, never a source of truth. That property
already holds for `retrieval_units` — `cli rebuild-index` reproduces it
byte-identically and a test asserts so. It is the strongest property in the
system, and the ref index inherits it.

### 3.2 L4 becomes a function, not a store

`docs/layering.md` names L4 (Entities) and records that **nothing** builds it.
Phase D is blocked on it, and whether it can exist is gated on amendment
candidate **C3**. A named, empty, externally-blocked box mid-stack is a
liability, not a layer.

Its own §5 already decided the substance: the hand-researched dataset's
**composition graph is authored structure** (32 lines, 59 assemblies, 225
components) while its **values are curated like any other source**. Invariant 10
agrees: *structure is authored, not extracted; no table reader produces a
`PanelSpec`.*

So:

```text
Part  =  authored composition graph  ×  accepted claims
```

computed by the publisher at build time. The empty-layer blocker disappears. C3
still governs whether a membership edge needs its own `SourceRef` when
published — it stops gating whether a layer exists, which was the only reason it
blocked design. Nothing is lost, because nothing was there.

---

## 4. The `claims` table

A fact is not a different kind of thing from a reading. It is a claim a person
has accepted.

```sql
CREATE TABLE IF NOT EXISTS claims (
    claim_id        INTEGER PRIMARY KEY AUTOINCREMENT,

    -- locus: points DOWN into canonical, or nowhere for a dataset claim
    document_id     TEXT    REFERENCES documents(document_id),
    version_id      TEXT,
    page_no         INTEGER,
    element_id      TEXT    REFERENCES elements(element_id),
    evidence_ref    TEXT,                  -- refs.py's id; NULL only for `dataset`

    -- what is claimed
    claim_type      TEXT,                  -- NULL = read but not yet typed (§4.2)
    subject         TEXT,
    value_original  TEXT NOT NULL,
    value_normalized REAL,
    unit_original   TEXT,
    unit_normalized TEXT,
    value_alternates TEXT,                 -- obligation 4, JSON

    -- what scopes it
    conditions      TEXT NOT NULL DEFAULT '{}',
    condition_basis TEXT NOT NULL DEFAULT 'unexamined',
    condition_basis_note TEXT,

    -- who claimed it
    author          TEXT NOT NULL,         -- 'regex-v1' | 'calibration-A' | a person | 'dataset'
    author_kind     TEXT NOT NULL,         -- extractor | agent | human | dataset

    -- review state: the single source of curation level
    review_status   TEXT NOT NULL DEFAULT 'unreviewed',
    reviewed_value  TEXT,
    reviewer        TEXT,
    reviewed_at     TEXT,
    reviewed_crop_sha256 TEXT,             -- the image the reviewer actually saw

    -- evidence presentation
    evidence_text   TEXT,
    ocr_derived     INTEGER NOT NULL DEFAULT 0,
    confidence      TEXT,                  -- the author's own stated confidence
    illegible       INTEGER NOT NULL DEFAULT 0,

    created_at      TEXT NOT NULL
);
```

### 4.1 Row and column labels are conditions, not columns

`row_label`, `col_label`, `row_index`, `col_index`, `table_kind` do **not**
become columns. `table_review.promote()` already writes them into `conditions`
with `condition_basis='stated'` — and A2 records that this is *the one place in
the codebase where `stated` is true*, because a promoted claim's conditions are
the table's own printed row and column labels. The merge makes that the only
representation instead of the second one. Six columns collapse into the field
that already holds them correctly.

### 4.2 `claim_type` may be NULL, and that is the honest state

Of the 703 single-read cells, the frequent values are bill-of-material lines
(`5 X 5 X 107 ROUTED POST` ×24, `#8 X .75 SCREW` ×8), dimensionless coefficients
(`0.00` ×13, `1.00`), and **234 rows whose value merely echoes the row label**.
None maps to a fact type. `claim_type = NULL` means *read, not yet typed*.
Inventing a type would be the same error as calling an unexamined condition
`assumed`.

### 4.3 What the merge deletes

| Goes away | Because |
|---|---|
| `facts.from_candidate_id` | a claim and its reading are one row |
| `PROMOTABLE`, `promote()`, `promote_verified()` | promotion is an UPDATE |
| `revoke_machine_promotions()` | there is nothing to un-copy |
| the `DELETE FROM facts WHERE extractor LIKE 'regex-%'` hazard | scope to `author_kind='extractor'`; reviewed rows become *structurally* unreachable |
| `promote_tables.py` | 228 lines, subsumed |

### 4.4 The review verb, which was the critical path

```sql
UPDATE claims SET review_status=?, reviewed_value=?, reviewer=?,
                  reviewed_at=?, reviewed_crop_sha256=?
 WHERE claim_id=?;
```

`cli review --accept ID --reviewer NAME [--value X]`. No pipeline, no dry-run
split, no `PROMOTABLE` tuple, no second table to keep consistent. **Curation
level becomes a property of a row**, computed from `author_kind` and
`review_status`, rather than a table you graduate between. That is what
obligation 6 describes.

---

## 5. Addressing: `refs.py`

One module owns the evidence identifier. `snapshot.py` imports it rather than
defining it.

- **The shipped id scheme is kept unchanged.**
  `sha256(f"{content_hash}:{page_no}:{bbox}")[:16]`, with `bbox` interpolated as
  the **stored text** verbatim. It never passes through `canonical_bytes`, so
  that module's float refusal never applies. 431 published refs depend on this
  and it does not move.
- **The inverse is a projection, not a table.** Measured: rebuilding the whole
  `ref_id → locus` index takes **~220 ms** over 81,794 elements, yielding 69,306
  distinct ids with **zero** true collisions, plus 1,853 page refs in 4 ms. No
  table, no migration, and it cannot drift from the store because it is derived
  from it.
- **The `sref_` scheme is dropped.**

### 5.1 The ref lifecycle — extraction editions

**This is the correctness hole the reassessment found, and it is the reason
plan 1 comes first.**

`ref_id` is derived from three things. Two are permanent and one is a
measurement:

| Component | Layer | Stable? |
|---|---|---|
| `content_hash` | S · sources | **yes** — content-addressed by construction |
| `page_no` | intrinsic to the bytes | **yes** |
| `bbox` | C · canonical | **no** — produced by `pdftotext -bbox-layout` |

And the store **already treats a version's identity as (bytes × toolchain)** —
`store.py:475`:

```python
def version_exists(conn, doc_id, sha256, fingerprint):
    """True when this exact content was already extracted by these exact tools."""
```

But the fingerprint lives only in that guard, never in the row: `version_id` is
`doc-24d0ddcfce69@00c965f58d30` — document id and content hash, no toolchain.
So when the fingerprint differs, ingest does not skip, and `store.py:520` runs:

```python
def delete_version_rows(conn, version_id):
    """Remove all canonical rows for a version so re-extraction is not additive."""
```

which **deletes** `elements`, `pages`, `tables`, `table_cells`, `assets` and
`quality_issues` for that version.

**Consequence.** A poppler upgrade that shifts a bbox by 0.02pt — 1/3600 of an
inch, invisible — changes the id completely (measured: `cd9f0d9d9c4e300f` →
`e25f68cec20de1bc`) and deletes the rows the old id named. The published
citation does not get repointed at wrong pixels; it **ceases to resolve**. And
because a snapshot is immutable, it can never be repaired.

That **retroactively breaks obligation 3** — *every published value carries a
resolvable `SourceRef`* — on an already-published artifact, with no error
anywhere. G31 is proof the event class occurs: a clean rebuild produced 81,788
elements where the store had 81,794. Six elements ceased to exist.

**Currently clean:** all 431 published cites resolve against today's store,
spanning 3 extraction runs. This is a hole to close, not damage to repair.

#### A better hash is not the fix

Measured over all 81,794 elements:

| Scheme | Distinct ids | Elements sharing an id |
|---|---:|---:|
| `sha:page:bbox` — shipped | 69,306 | 22,418 |
| `sha:page:text` | **56,090** | 38,602 |
| `sha:page:type:text` | 56,442 | 37,969 |
| `sha:page:bbox:fingerprint` | 69,306 | 22,418 |

Text-based identity is **worse**, and 6,660 `figure` elements have no text at
all. Adding the fingerprint reduces no collisions; it only makes the dependency
visible. The reason no hash fixes this: **a sub-page identifier cannot be stable
across re-extraction, because the thing it identifies — a rectangle — is itself
produced by extraction.** That is inherent.

#### The fix: editions, not overwrites

Make the store honour what the id already assumes. Put the toolchain fingerprint
into the version's identity and let re-extraction be **additive** — a new
*edition* of canonical rows — rather than delete-and-replace. Retain an edition
while any un-tombstoned snapshot cites it; drop it when none does.

```text
P  snapshot (immutable, content-hashed)
   └→ ref (immutable, content-derived)
        └→ a specific (bytes × toolchain) edition   ← retained while cited
             └→ S  bytes (content-addressed)
```

Every hop pinned. Four properties follow:

1. **The id scheme does not change at all.** All 431 published refs stay valid.
   Consistency comes from keeping the shelf, not from re-labelling.
2. **One rule covers both change cases.** New bytes → new edition. New toolchain
   → new edition. This is what makes the design consistent: the *bytes* case
   already behaves correctly today (different sha, both versions coexist); the
   *toolchain* case is made to behave identically.
3. **Retention reuses machinery that exists.** `retain_until` and the tombstone
   path already do this at P; this extends the same discipline down one layer.
4. **It protects human review, the most expensive thing here.** A reviewed claim
   points at an `element_id`. Today a re-extraction *deletes that element* and
   orphans the review. Under editions the reviewed edition stays shelved and the
   accepted claim keeps its evidence — and can never silently re-point at a
   different edition's element.

**Cost, measured.** One retained edition of canonical rows:

| Table | Size |
|---|---:|
| `elements` | 26.6 MB |
| `assets` | 2.5 MB |
| `table_cells` | 1.1 MB |
| `pages` · `tables` · `quality_issues` | 0.9 MB |
| **per edition** | **~31 MB** on a 69.1 MB store |

`retrieval_units` (7.6 MB) is a projection and is rebuilt, never retained.
Derived images need no retention at all — §4.3 of the source-refs design makes
`workspace/derived/` a regenerable cache and D6 proved deleting it changes no
evaluation number.

**Rejected alternative:** keep destructive re-extraction and add a verifier that
fails when a published ref dangles. It converts silent corruption into
*announced* corruption that cannot be fixed, because the pixels the citation
named are already deleted. The verifier is still worth building — as a
**regression guard for editions**, which is exactly what plan 1 does — but not
as the fix.

### 5.2 Three defects in the shipped scheme

Measured, not supposed. These are the substance of plan 2.

1. **`ref_id` omits `kind`, and it is worse than one collision.** The proposed
   locator had seven fields including `k`; the shipped function hashes three. A
   bbox-less element therefore produces the id of its own *page*.

   Measured: **all 416 bbox-less elements collapse onto a single id**,
   `15d1ceaf5cb24da2`, which is also that page's page-ref. Every one of them is
   in `ARCAT-CSI-32-31-23-Vinyl-Fencing-and-Gates-MasterSpec_Superior-Outdoor.docx`
   at `page_no = 1` — the DOCX, which has no page geometry at all (G4).

   So the entire text of that document is addressable only as "page 1", and a
   citation to any of its 416 elements is indistinguishable both from a citation
   to any other and from a citation to the whole page. It is one id today
   because one document has no geometry; it is not a one-element edge case.

   *(An earlier reading of this said "one collision". That counted distinct
   colliding ids and stopped at the first hit. The distinct-id count is 1; the
   number of elements made mutually indistinguishable is 416.)*
2. **`ref_id` is not injective over elements.** **9,929** ids cover more than one
   element; **12,488** elements are involved. Commonest patterns: two paragraphs
   sharing an identical bbox (3,763), headings (2,530), lists (1,813). Addressing
   a *rectangle* is deliberate — but the resolver needs a **stated rule** for
   which element's text to quote, not an arbitrary `LIMIT 1`.
   *Not a defect:* the worst case (8 elements on one id) is three byte-identical
   duplicate filings of one NOA. Same bytes, same ref, correctly.
3. **It expresses one of five kinds.** `source_ref()` takes an `element_id` and
   nothing else, so `table_cell`, `page`, `visual_reading` and `derived` cannot
   be minted. `derived` is hardest: a `data/structural/*.json` assertion has no
   `documents` row to point at.

---

## 6. Migration cost, measured

Both tables are fully reproducible, and neither holds anything irreplaceable
today.

| | |
|---|---|
| `facts` | regenerated by `cli facts --extract` (idempotent since G35/G18) |
| `table_read_candidates` | re-loaded by `cli table-review --load-dir` from 7 committed `agent-read-*.json` files, 130 KB total |
| `fact_id` exposed outside the store | **0** occurrences in the published snapshot |
| Human review decisions to preserve | **0** — `reviewer` is NULL on all 1,225 readings; 0 facts promoted |

So the migration is a **rebuild, not an in-place data migration**: no risky
`ALTER`, no backfill, no id remapping. **This is the cheapest it will ever be** —
the only irreplaceable data these tables can hold is human review decisions, and
the first accepted reading makes the migration expensive.

### 6.1 Blast radius

| | Code refs | Test refs | Modules | Test files |
|---|---:|---:|---:|---:|
| `facts` | 90 | 95 | 12 | 7 |
| `table_read_candidates` | 32 | 25 | 4 | 6 |

Readers of `facts` include `retrieval.py`, `versions.py`, `evaluate.py`,
`reports.py`, `relations.py`, `assets.py`, `snapshot_store.py`.

**Mitigation: keep `facts` as a SQL VIEW over `claims`.**

```sql
CREATE VIEW facts AS
  SELECT claim_id AS fact_id, document_id, version_id, page_no, element_id,
         claim_type AS fact_type, subject, value_original, value_normalized,
         unit_original, unit_normalized, conditions, evidence_text,
         author AS extractor, ocr_derived, review_status, created_at,
         condition_basis, condition_basis_note, value_alternates
    FROM claims
   WHERE author_kind IN ('extractor', 'dataset')
      OR review_status IN ('accepted', 'corrected');
```

The 90 read references keep working; only the three writers change. The view's
`WHERE` clause is the first written-down definition of "what counted as a fact".

Limits, stated: a view is read-only, so any test that INSERTs into `facts` must
be repointed; and the view drops `from_candidate_id` deliberately (§7).

### 6.2 The acceptance criterion, and it is exact

Because nothing is promoted today, `facts` holds **only** the 1,652 `regex-v1`
rows. So:

> The `facts` view over migrated `claims` must return **exactly** the rows the
> `facts` table holds today — same count, same values, same ids — and
> `table_read_candidates` must reproduce all **1,225** readings with their
> `crop_sha256` intact.

Both sides are computable before and after, so this is a diff, not a judgement.
Compare **values, not serialised rows**: G35 records that a migrated table and a
fresh one agree on the set of columns but not their order, so `dict(row)` key
order is store-history-dependent and byte-comparing serialised rows between a
migrated and a re-ingested store is invalid.

If the diff is not empty, the migration is wrong and gets reverted — the store
is rebuildable, so reverting costs a rebuild and nothing else.

---

## 7. What this does to `test_pointer_direction.py`

That file has **seven tests**, five of which pin `from_candidate_id` as a
required, declared foreign key. The merge removes the column, so those five must
be rewritten. This needs justifying, because the file exists to stop a pointer
regressing.

**The merge is the next step in the same argument the file already makes.** Its
own docstring records that inverting the pointer *deleted* a cleanup statement
and a test, and calls that test "a test for a bug the schema should not permit".
The merge finishes the thought: the inversion made the pointer *safe*; the merge
makes it *unnecessary*, because there is no cross-table derivation to record.

The five are replaced by one stronger invariant:

> There is no cross-table claim derivation at all — so there is no direction for
> a claim pointer to get wrong.

Plus the two that survive in spirit: `claims.element_id` and
`claims.document_id` are declared foreign keys pointing down into canonical, and
no claim names a row that does not exist. `RETIRED_COLUMNS` gains
`("facts", "from_candidate_id")`; `retire_columns()` already refuses to drop a
column that still holds data, which is the safety net for doing this in the
wrong order.

---

## 8. Three plans, in order

Each produces working, testable software on its own. The order is chosen so each
step de-risks the next.

| | Plan | Delivers | Why here |
|---|---|---|---|
| **1** | `docs/four-layer-plan-1-refs.md` — **refs.py: one owner, one index, one guard** | `refs.py` owning `ref_id`; the rebuildable ref index; `cli refs --verify` walking every un-tombstoned snapshot | Lowest risk (no schema change). Builds the **detector** for the §5.1 hole before fixing it, which is then the regression guard for plan 2. |
| **2** | editions — **version identity = bytes × toolchain** | additive re-extraction, edition retention + GC, and the three §5.2 id defects | Fixes the correctness hole. Must precede plan 3, because `version_id` gains a component and `claims` carries `version_id`. |
| **3** | claims — **the merge and the review verb** | one `claims` table, the `facts` view, `cli review --accept` | Biggest change; benefits from a settled version identity. Unblocks curation level 2. |

---

## 9. Decisions deliberately NOT taken

Recorded so a plan must take them explicitly rather than by accident.

1. **The quote-selection rule for the 9,929 shared ids.** Needs a stated rule.
   Plan 2.
2. **How `kind` enters `ref_id`.** Under editions this is **demoted** — the id
   scheme is no longer what needs deciding, because old editions are retained.
   Options remain: append only for non-`element_quote` kinds; accept a one-time
   rewrite while nothing outside `workspace/snapshots/` consumes them; or
   disambiguate at resolve time. Plan 2, with a measurement.
3. **Whether `claims` is one wide table or a core plus an extension.** §4
   proposes one wide table on the strength of §4.1 collapsing six columns.
   Plan 3.
4. **Whether `docs/curation/` is deleted or banner-archived.**
   `rag-pipeline-plan.md` set the stale-banner precedent, and
   `state-and-gaps.md` records that stale invocations were deliberately *not*
   rewritten where they document how something was verified.
5. **Tenancy** (Phase E). Untouched. Must be settled before the snapshot format
   is fixed.
6. **The rebuild wall-clock** for `facts --extract` and `table-review
   --load-dir`. **Unmeasured.** Plan 3 must measure it before relying on it.

---

## 10. Verification

```bash
# documentation and code mass
find docs -name '*.md' | wc -l && wc -l $(find docs -name '*.md') | tail -1
wc -l fence_evidence/*.py | tail -1

# the 52 cur_* tables
grep -o 'cur_[a-z_]*' docs/curation/02-curation-schema.md | sort -u | wc -l

# the shipped refs, and that no sref_ exists
python3 -c "import json;d=json.load(open([__import__('glob').glob('workspace/snapshots/*.json')][0][0]));\
print('warnings',len(d['warnings']),'cites',sum(len(w.get('cites',[])) for w in d['warnings']))"
grep -o 'sref_' workspace/snapshots/*.json | wc -l

# nothing external depends on fact_id
grep -o 'fact_id' workspace/snapshots/*.json | wc -l

# no human review state to preserve
python3 -c "import sqlite3;c=sqlite3.connect('file:workspace/indexes/evidence.db?mode=ro',uri=True);\
print('reviewed readings:', c.execute('SELECT COUNT(*) FROM table_read_candidates WHERE reviewer IS NOT NULL').fetchone()[0]);\
print('promoted facts:', c.execute(\"SELECT COUNT(*) FROM facts WHERE extractor LIKE 'table-read%'\").fetchone()[0])"

# canonical row sizes, for the edition retention cost
python3 -c "import sqlite3;c=sqlite3.connect('file:workspace/indexes/evidence.db?mode=ro',uri=True);\
[print(f'{t:16}', round((c.execute('SELECT SUM(pgsize) FROM dbstat WHERE name=?',(t,)).fetchone()[0] or 0)/1e6,1),'MB')\
 for t in ('elements','pages','tables','table_cells','assets','quality_issues','retrieval_units')]"
```

The hash-sensitivity demonstration (`cd9f0d9d9c4e300f` → `e25f68cec20de1bc` on a
0.02pt bbox change), the ref-index rebuild (~220 ms for the full index, 0 true collisions), the
`15d1ceaf5cb24da2` kind collision, and the 9,929 shared ids are all reproduced
by the scripts in plan 1's Task 0.

---

## 11. What this is worth, and what it does not change

**Worth:** four layers instead of five with one empty; one claim table instead of
two plus a shelved third; three writers reduced to one plus a review verb; one
owner for addressing instead of two competing designs; the review verb reduced
to a single UPDATE; ~2,000 lines of provisional design retired; and a live
correctness hole closed — a toolchain upgrade currently breaks obligation 3
retroactively on published snapshots. Three recorded incident classes (G17, G18,
the inverted pointer) become structurally impossible rather than tested against.

**Costs:** ~215 references touched, mitigated to ~35 by the `facts` view; five
tests in `test_pointer_direction.py` rewritten with the §7 justification;
`version_id` gains a fingerprint component, touching every table carrying it;
~31 MB per retained edition; a full rebuild whose wall-clock is unmeasured; and
`SCHEMA_VERSION` moving to 4.

**Does not change:** the read-only corpus guard, the canonical store's contents,
the byte-identical projection rebuild, the pointer-direction *rule*, the shipped
`ref_id` scheme, the published snapshot, `crops.py`, or any BINDING contract
item. **No amendment is required.**
