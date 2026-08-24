# Knowledge Platform — component design

```text
Status:    Orientation. Written by the Planning & BOM team; audited, revised and
           re-reviewed by both. Current as of v0.2.1.
Authority: Advisory throughout. Only the BINDING items in contract-v0.2.md are
           promises; everything here is one team's view of how the pieces fit.
Detail:    knowledge-datamodel-v0.2.md carries the entities and relationships.
```

## 1. What this component is for

Three components. This one turns documents into things a machine can use.

```text
    FRONTEND        map editor · knowledge admin · review queue · BOM review
        │ one API — never calls this platform directly
        ▼
    PLANNING & BOM  project → topology → strategy → requirements → BOM
        │  ▲                      a planning run reads ONE pinned snapshot
        │  └── snapshot, by hash          and nothing else
        ▼
    KNOWLEDGE       documents · evidence · claims · definitions · publishing
```

The division that settles most arguments: **Knowledge owns definitions, Planning
owns instances.** *What is a post? What can this product be used as? What
constraints apply?* — here. *Which post goes at station 7, cut to what length,
bought from whom?* — there.

## 2. What this platform publishes

Not "facts about products". **The products themselves**, and the panels they go
into, in the same types the engine already computes with.

| Published | What it is |
|---|---|
| `Part` + `SpecField` | What a manufacturer's component is — dimensions, material, profile |
| `FenceModel` + `PanelSpec` | How a panel goes together — slots, infill pattern, joints, fixings |
| `AssemblyStep` | The order a person builds it in, scoped `panel｜bay｜post｜run｜site`, with typed prerequisite edges |
| `Procedure` | A step sequence owned by a manufacturer, a component, or nobody at all |
| `Warning` | Verbatim text, its language, and what it attaches to — only one in five is a step |
| `ParameterTable` | Conditional values — maximum span by exposure, footing depth by zone |
| `Combination` | A certified assembly whose validity is scoped to its exact members |
| `Gap` | What is missing, so silence never reads as coverage |

All of it citing pages, all of it carrying an authorship flag, all of it inside
one immutable content-hashed snapshot.

**Why this shape rather than a query API.** A planning run is a pure function:
same project, same knowledge, same answer, provably, years later. A pure function
cannot call a search service partway through. So everything a run needs is
fetched beforehand as one hashed object and computed against locally — which also
means the engine works, and its regression suite runs, with this platform
switched off.

## 3. What stays private here

Documents, pages, elements, crops, claims, conditions, reviews, promotion rules,
conflicts, the retrieval index, the source policy. Planning never models any of
it and never asks for it.

Two things cross, and only two:

- an **accepted claim** becomes a row in a published `ParameterTable`
- a **curated procedure** becomes a published `FenceModel.assembly`

Plus `SourceRef` resolving back the other way when a person asks *why*.

## 4. The two planes

**Resolution — deterministic.** `POST /snapshots/resolve` then
`GET /snapshots/{id}`. Immutable, cacheable forever, never called during a run.
A hash resolves to the same bytes until `retain_until`, or to an explicit
tombstone saying it was excised and why.

**Discovery — human-facing.** `GET /search`, `GET /source-refs/{id}`,
`GET /claims`. Results carry source references. Nothing here is ever an input to
a plan, which is why retrieval quality governs *how much work a curator does*
rather than *whether a bill of materials is right*.

**Authoring** — reviews, roles, documents, gaps — proxied from the frontend
through Planning, which owns authentication and locale. You see one consumer.

## 5. The workflows

### 5.1 From a document to a published definition

1. **Ingest.** Pages, elements, bounding boxes, crops. Nothing interpreted.
2. **Resolve identity.** Ten manufacturer spellings cluster to one group —
   linked, never merged, because four filings of one approval are four filing
   facts.
3. **Read the tables.** Wind, spacing and footing grids become *candidate*
   claims with their crop. None is a fact yet.
4. **Author the structure.** A curator writes the panel — slots, joints,
   engagements, fixing basis — citing guide pages. This is authored, not
   extracted: an install guide describes a joint in prose and figures, and no
   table reader produces a `PanelSpec` from that.
5. **Review.** With the crop on screen. A review may produce a *pattern* rather
   than a single approval, which is the only documented way a curated knowledge
   base has ever outrun its curators.
6. **Compile.** Claims for one parameter group into a table with a declared hit
   policy; overlaps fail the publish, uncovered points become gaps.
7. **Publish.** One snapshot, hashed, retention declared.

### 5.2 The correction loop

An expert in the field says the gate posts differ here. Planning captures the
words verbatim and immutably, then forwards them as a **proposal** — never as
accepted knowledge. It re-enters at step 5. A correction made once becomes
knowledge that holds next time.

### 5.3 When a manufacturer revises

Runs already pinned are untouched — they hold their own snapshot. Companies that
adopted a definition get a work item offering two doors: take the new structure
while keeping locally overridden values, or take everything. Companies that
forked get a divergence report. Nothing updates silently.

## 6. Integration — what each side relies on

### What Planning relies on you for

The full list is §3.1 of the contract. In short: a hash resolves to the same
bytes forever; parameter tables declare their hit policy and domain and list what
they do not cover; every value carries a resolvable source reference and an
honest curation level; integers only; every part type resolves into the shared
spine; tenant isolation enforced in code; and gaps published as gaps rather than
approximated into a shape that nearly fits.

### What you can rely on Planning for

- A snapshot hash pinned on every run, re-fetched by hash rather than
  re-resolved.
- **No live fallback lookups.** If a value is not in the pinned snapshot, the run
  does not go looking.
- **A gap never fails a run.** A missing definition or an uncovered condition
  produces a warned, named line and a plan that still works. This is what lets
  the two teams iterate without blocking each other.
- Gaps reported back with evidence.
- Corrections captured verbatim before anything interprets them.
- The counting rules. A part type exists because the engine implements it.

### The one place the teams must talk

Tier 1 and tier 2 schemas are owned by Planning but authored against by you.
Neither side changes them alone. Registry additions — a new part type, a warning
code, a condition dimension — are **not** breaking changes and need no
negotiation.

## 7. The mechanical test that decides data or code

A recurring question, with one answer:

> Can this be expressed by an existing rule, unchanged?

**Yes** → data. Ships in the next snapshot, same day, no coordination. A rebar
separator clip filed under `fastener` inherits "counted per connection".

**No** → a gap raised to Planning with evidence. New rule, release, gap closes.
A decorative band across the span is one per bay, which no existing rule
produces.

Either way plans still generate, with a warned line, in the meantime.

## 8. What we know is unresolved

- **Assembly is unrepresented in the corpus today** — recorded in your own
  capability matrix as "not represented in any form". Structure will be curator
  work for a long time, and it is the highest-value thing this platform can hold,
  because it is the half of a bill of materials no table extraction produces.
- **The structural values are hard.** Five approvals carry one table element
  between them; digit recall on the flagged pages is 0.588. The design assumes
  this and does not depend on it improving: a snapshot containing very little is
  still valid, and Planning still plans from it.
- **Curator throughput is unmeasured**, here and in the field generally. Measure
  claims per reviewer-hour on one family before building a queue around an
  assumption.
- **Authorship is uncomfortable and should stay visible.** There is no fence data
  feed anywhere. A definition published here is this platform's reading of a PDF,
  and the flag says so rather than implying a manufacturer stands behind it.
- **Central authoring has been reversed before.** buildingSMART moved from one
  curated dictionary to a distribution platform of independent dictionaries
  mapped by typed relations, in this exact domain. The counter-argument is that a
  fence panel is a manufactured kit rather than a context-dependent abstraction —
  good, but an argument being chosen rather than a settled fact.

## 9. Where the conversation stands

The v0.1 challenge was answered in `audit-response-v0.1.md`, dispositioned in
`audit-disposition-v0.1.md`, folded into v0.2, and reviewed again in
`review-of-v0.2.md`, which found six defects — all fixed in v0.2.1 and recorded in
`review-disposition-v0.2.md`.

**What is still open is short and named**: `knowledge-datamodel-v0.2.md` §7.1 (the
three shapes Planning modified rather than accepted) and §7.2 (what is still
undesigned). `planning-asks-v0.2.md` is the mirror — what Planning needs, ordered
by cost if late.

The standard that made the first round work still applies: a gap per item, with the
document and page that motivates it. Anything that changes tier 1 or tier 2 changes
the contract, and that is a negotiation rather than a request.
