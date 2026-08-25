# Phase 7C — Domain curation

```text
Status:   Proposed. Nothing in this directory is implemented.
Position: between the canonical evidence store and the retrieval projection.
Gate:     no corpus-wide curation, and no projection rebuild, until these five
          documents are reviewed and the vertical slice passes §5 readiness.
```

## Why this phase exists

The system built in Phases 0–6 is good at preserving what a page *contained* and
bad at answering what a product *requires*. That is not a retrieval bug. It is a
missing layer.

> **Baseline note, 2026-08-25.** This proposal was written against a store holding
> **1,988 facts**. Build-plan A1 has since un-promoted the 324 that no person reviewed,
> so the store holds **1,652** and the level-2 population is zero. Fact counts throughout
> these five documents — including `05-acceptance-criteria.md` P3 ("identical, 1,988
> rows") and C-C3's `cross_family_verified` slice — are stated as of authoring and have
> **not** been rewritten: they are the premises the proposal was reasoned from, and
> silently restating them would hide that the ground moved. Re-measure before accepting
> any acceptance criterion that names a row count.

Two measurements make the case, both from `docs/state-and-gaps.md`:

- **G6/G15.** `facts` holds **1,652 rows**, all from `extractor='regex-v1'`.
(It held 1,988 when this was written: 1,664 regex rows plus 324 from an
unreviewed table-reading pass marked `table-read:cross_family_verified`, none of
which a person ever accepted. Those 324 were un-promoted on 2026-08-25 — C0 below
landed as build-plan A1 — but the case this section makes is unchanged, and the
regex rows it turns on were always the larger half.) A
typical regex row reads `footing_depth_in = 30"`, `subject = "FENCING
INSTRUCTIONS > POST"`, `conditions = {}`. The subject is a heading path, not a
product. The condition set is empty because the regex never looked for one. The
same document states 30″ for frost line and a different depth per exposure
category — both become the same undifferentiated "fact".
- **G16.** Four claims in the hand-curated `data/structural/*.json` were checked
against their own sources and contradicted. One licenses a 24″ footing in a
high-velocity hurricane zone where the source brackets the row `NON HVHZ`.

Both failures share a cause: a number was lifted away from the conditions that
make it true. Domain curation is the layer that puts the conditions back,
refuses to call anything a fact until a person has agreed, and keeps every step
of it anchored to the page it came from.

## What is frozen

The extraction and preservation layer is now immutable input:

- `manuals/`, `china/manuals/`, `data/` — read-only corpus, unchanged.
- `documents`, `document_versions`, `pages`, `elements`, `tables`, `table_cells`,
`assets`, `relations`, `extraction_runs`, `quality_issues`,
`table_read_candidates` — the eleven canonical tables, read by curation, never
written by it.
- `facts` — read as *input material*, never updated, never deleted. Curation
copies each row forward into a candidate claim and leaves the original in place.
- `retrieval_units`, `retrieval_fts` — not regenerated during this phase.
- `fence_evidence/{extract,layout,hocr,tables,quality,ingest,manifest}.py` —
not modified.

One deliberate exception, **now closed ahead of this phase**: `PROMOTABLE`
contained `cross_family_verified`, so two agent readings from different model
families promoted without a person — 324 facts entered `facts` that way. **C0 was
taken out of this proposal and landed on its own as build-plan A1, 2026-08-25**,
because it was a ratification commitment rather than a proposal and should not
have waited on a phase still under review. `PROMOTABLE` is now `("accepted",
"corrected")`, the 324 rows are back to being candidates with their crops intact,
and `facts` is 1,652. It was a narrowing of what the frozen layer may assert, not
a rebuild of it. See `docs/state-and-gaps.md` G17.

Curation writes only to new tables in a new namespace and to `workspace/`.

## Paused, per instruction

Retrieval expansion (G1 second stage, F1 heading projection), MCP/HTTP serving,
semantic and dense search, and agent-generated answers. The relevance audit's
recommendations stay unapplied. `docs/experiment-noa-table-reading.md` continues
only as an *input* to curation — its output is candidate readings for review,
not promoted facts.

## The five review deliverables

| # | Document | Answers |
|---|---|---|
| 1 | [`01-capability-matrix.md`](01-capability-matrix.md) | What must the system be able to answer, and what does each answer require? |
| 2 | [`02-curation-schema.md`](02-curation-schema.md) | What tables hold dossiers, page maps, entities, claims, reviews, bundles? |
| 3 | [`03-vertical-slice-source-set.md`](03-vertical-slice-source-set.md) | Which product family and which 19 documents? |
| 4 | [`04-curation-and-review-plan.md`](04-curation-and-review-plan.md) | Who does what, in what order, with which gates? |
| 5 | [`05-acceptance-criteria.md`](05-acceptance-criteria.md) | What counts as done, measured how? |

Machine-readable companion:
`workspace/catalog/slice-bufftech-extruded-pvc.jsonl` — one row per slice
document with its SHA-256 and its measured page, element, fact, table, candidate
and OCR-risk counts as of this proposal, with facts split by extractor and by
mandatory review class.

These five documents were fact-checked against the store in three passes, and
independently reviewed for internal consistency, schema soundness, and
adversarially against their own acceptance criteria. Every correction those
passes produced is applied here; the review findings that changed the *design* —
a second evidence kind for readings that have no element, a floor group so that
gapping everything cannot pass, and an inverted G16 regression test — are called
out where they land.

## The invariant that governs all five

> Every claim the curation layer emits carries an unbroken path back to a
> document, a version SHA-256, a physical page, an element, a bounding box, and
> a pixel crop that a person can look at. A claim that cannot render its own
> evidence is not a claim; it is a defect.
