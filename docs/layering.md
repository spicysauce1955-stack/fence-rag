# Layering — five layers, and one rule about direction

```text
Status:   PROPOSED. Nothing here is adopted. It disagrees with CLAUDE.md in one
          place and with docs/curation/ in another, both named in §5.
Scope:    A way of describing what already exists, plus one rule that is new.
          The rule has already been applied once — see §3 — because it caught a
          defect while being written.
Authority: None. contract.md governs the boundary; mvp-implementation-spec.md
          governs how this platform works. This proposes vocabulary, not either.
```

## 1. Why bother naming layers

The system has grown a shape nobody has written down. Sessions rediscover it by
reading `store.py` and `contract.md` side by side, and the two describe
different halves of it. Worse, a question that comes up every time —
*"where does the hand-researched dataset fit?"* — has no answer in any document,
which is how it ended up **outside** the evidence chain entirely.

Naming the layers is cheap. The rule in §2 is the part that earns its keep.

## 2. The five layers, and the rule

| | Layer | Holds | Built by |
|---|---|---|---|
| **L1** | Raw | the corpus — 144 files, read-only, content-addressed | `cli fetch` |
| **L2** | Canonical | what each page contained — 81,794 elements, boxes, images | `cli ingest` |
| **L3** | Assertions | a value, its conditions, and where it was read — 1,652 facts | `cli facts --extract` |
| **L4** | Entities | the things a bill of materials names — parts, panels, slots | *nothing* |
| **L5** | Published | the contract shapes, hashed and immutable | *nothing* |

> ### THE RULE
>
> **Every reference points DOWN a layer. Never up.**
>
> A row may name the thing it was derived FROM. It may never name the thing
> that was derived FROM IT.

Three things follow from it, and they are the reason it is worth stating:

1. **A downward pointer is free.** It is written by the code that performs the
   derivation, at the moment it performs it. `extract_facts` scans element E and
   writes `facts.element_id = E` because it is standing there. Nobody ever
   *matches* anything; the link is a byproduct.
2. **A downward pointer is enforceable.** It can be a real foreign key, so the
   database refuses a dangling one. An upward pointer cannot be — you would not
   be able to delete the derived row.
3. **An upward pointer must be maintained by hand**, and hand-maintenance is
   where the bugs live. §3 is the worked example.

### Layers are lossy on purpose, and the escape is downward

Each layer is a smaller, more useful summary of the one below, and each drops
something. That is fine *because* you can always go down and look — which is
exactly what the contract already requires of the top layer: obligation 3 says
every published value carries a resolvable `SourceRef`, and that resolving it
must return *"something a person can look at."*

**But the descent may never happen inside a planning run.** Contract §3.2.2
forbids Planning from calling Discovery during a run; a run must complete with
this platform unreachable. Agents and readers dive before a run; a person dives
after, while inspecting a decision. That constraint is what makes a plan
reproducible, not a limitation to route around.

## 3. The rule has already paid for itself

`table_read_candidates.promoted_fact_id` pointed **up**: a reading (evidence)
naming the fact derived from it. It cost two things, both of which disappeared
when it was inverted to `facts.from_candidate_id`:

- **`revoke_machine_promotions` had to clean up after itself.** Deleting a fact
  meant a second statement to `SET promoted_fact_id=NULL`, or a dangling id
  survived. That statement is now gone: the pointer lives on the row being
  deleted.
- **A test existed for a bug the schema should not have permitted.**
  `test_no_dangling_promoted_fact_id_after_reextraction` asserted that no
  dangling id survived a re-extraction. It has been replaced by
  `test_a_promoted_fact_names_its_reading`, which asserts the invariant instead
  of policing its violation.

It also could not be a declared foreign key — an FK from candidates to facts
would have blocked deleting facts. Inverted, it is one, on both a fresh store
and a migrated one.

Landed at `SCHEMA_VERSION = 3`, with `RETIRED_COLUMNS` and `retire_columns()`
added as the symmetric counterpart to `ADDED_COLUMNS` / `ensure_columns()`.
Retirement **refuses to drop a column that still holds data** — these tables are
not all rebuildable, so it reports and leaves it alone rather than destroying
something quietly.

## 4. Where each layer stands

**L1–L3 satisfy the rule already.** `facts.element_id` → `elements.page_id` →
`pages.version_id` → `document_versions.document_id` → sha256. An unbroken chain
of downward, enforced references.

**L4 is the problem, and it is not a small one.** The hand-researched dataset
(`data/*.json` — 32 product lines, 59 assemblies, 225 components) has exactly
the shape L4 wants and **carries no pointer down at all.** Not one field on a
`sub_assembly` names a document, page, element or box. It was written by a person
reading PDFs directly, so it skipped L1–L3 entirely.

That is why `docs/state-and-gaps.md` G16 could find four of its claims
contradicted by their own sources, and why the only way to find them was for a
person to go back to the page by hand. There is no automated check that could
have caught it, because there is nothing to check against.

**L5 does not exist.** No snapshot builder, no `ParameterTable`, no `Part`.

### What anchoring L4 would look like

The dataset is the one input that can be *corrected* — unlike a PDF. So the
cheapest anchoring writes the pointer into it, keeping it git-tracked and
reviewable in a pull request:

```json
"component_id": "BT-POST-5X5",
"component_type": "post",
"nominal_dimensions_in": "5 x 5",
"sources": [
  { "document_id": "doc-700e6e22c440", "page_no": 31,
    "element_id": "element-3a8841b379-0002",
    "reviewed_by": "...", "reviewed_at": "..." }
]
```

Note what this is **not**: it is not a machine matching components to pages. The
correspondence between an entity and its evidence is a judgement, exactly like a
table reading, and it needs the same treatment — a person confirming it with the
crop rendered. Structural validity is testable; semantic correspondence is
reviewable.

## 5. Where this disagrees with what is already written

Both disagreements are real and neither is resolved by this document.

**`CLAUDE.md` places the dataset in L1, not L4.** Verbatim: *"A research corpus
+ dataset — …137 PDFs… plus hand-researched JSON describing their contents.
**This is the read-only input.**"* It groups the JSON *with* the corpus as input.
This document treats it as an intermediate entity layer.

The two readings lead to different work, and the CLAUDE.md one may be the better
of them: **if the dataset is input, it is a source document that happens to be
human-authored**, and the right treatment is to curate it like any other source
— read it, extract claims, check them against harder evidence, record where each
came from — rather than to adopt it as a spine and bolt citations on. That
reading also explains G16 cleanly: those four claims are not corrupt data in a
trusted spine, they are what happens when a source is trusted without being
checked, which is the thing this platform exists to prevent.

**`docs/curation/` positions itself elsewhere.** Its header says *"between the
canonical evidence store and the retrieval projection"* — between L2 and the
projection, not at L4. So the one existing proposal that discusses an
intermediate layer does not use this numbering.

## 6. What adopting this would change

Nothing in the store, and nothing at the boundary. It is vocabulary plus one
schema rule. Concretely:

- `CLAUDE.md` gains a short section naming the layers, and either adopts the L4
  reading of the dataset or states the L1 reading explicitly so the question
  stops being rediscovered.
- `docs/curation/` restates its position in the same numbering.
- New schema work asserts the direction rule, which
  `tests/test_pointer_direction.py` now checks.
- `docs/build-plan.md` Phase D is reworded from *"the publishing layer"* to
  *"anchor L4, then publish"* — because the join is the work and the publisher
  is the small part that follows it.

## 7. What this does not propose

It does not propose adding a layer to the code, a table, a module, or a
directory. There is no `l4/` package and there should not be. The layers are a
way of talking about rows that already exist and rows that do not exist yet.
