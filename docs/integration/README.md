# Integration — the boundary with Planning & BOM

```text
Status:    v0.2.1. The §7 audit is answered, dispositioned and folded in; the
           result was then reviewed again and six defects fixed.
Authority: Binding ONLY at the boundary. Silent on everything inside it.
Origin:    Proposed by the Planning & BOM team; audited by the Knowledge team;
           revised by both.
```

## What this directory is

This platform has a consumer. A separate system — **Planning & BOM** — turns a
customer's map into a plan and a bill of materials, and it needs the knowledge this
platform produces.

These documents describe the boundary between them: what crosses it, in what shape,
and what each side promises the other. They exist so that two teams working in two
repositories can build independently without discovering their disagreements at
integration time.

---

## Start here

| If you are… | Read |
|---|---|
| **New to this** | `system-overview.md`, then `knowledge-datamodel-v0.2.md` §0–§3 |
| **Reviewing the revised model** | `knowledge-datamodel-v0.2.md` — §0 says how, §8 maps every finding to where it landed |
| **Planning your next sprint** | `planning-asks-v0.2.md` — what Planning needs, ordered by cost if late |
| **Checking a promise** | `contract-v0.2.md` — the BINDING items, and nothing else binds |

---

## The current documents

| Document | Answers |
|---|---|
| [`system-overview.md`](system-overview.md) | What is being built overall, and where this platform sits in it |
| [`contract-v0.2.md`](contract-v0.2.md) | **What crosses the boundary, and the promises each side makes.** Fourteen obligations, all binding |
| [`knowledge-datamodel-v0.2.md`](knowledge-datamodel-v0.2.md) | **The revised model in full** — every entity, field, relationship and invariant, with §7 (what to challenge now) and §8 (traceability for all 29 findings) |
| [`planning-asks-v0.2.md`](planning-asks-v0.2.md) | **What Planning needs from this platform**, ordered by impact. The mirror of `acceptance-open-questions.md` |
| [`source-refs-design.md`](source-refs-design.md) | `GET /source-refs/{id}` — the design, with `fixtures/source-ref-examples.json` |
| [`knowledge-design.md`](knowledge-design.md) | How this component fits the whole — what it publishes, the workflows, what stays private |
| [`rationale.md`](rationale.md) | Why each binding item exists — mostly measured from this store |

## The audit trail

Kept because the reasoning matters more than the conclusions, and because a later
disagreement is usually a re-run of one of these.

| Document | What it is |
|---|---|
| [`audit-response-v0.1.md`](audit-response-v0.1.md) | **The Knowledge team's answer to the v0.1 §7 challenge.** All ten questions, measured against the store, with a document path, page and verbatim quote behind every claim. Five places where the data contradicted the proposal rather than merely stretching it: §2.2 racking, §2.4 step scope, §2.5 warnings, §2.6 multi-document provenance, §3 source classes |
| [`audit-disposition-v0.1.md`](audit-disposition-v0.1.md) | **Planning's decision on all 29 items.** 24 accepted as written, 3 modified, 2 answered with a decision, none rejected |
| [`acceptance-open-questions.md`](acceptance-open-questions.md) | The Knowledge team's single list of everything needing a decision, and what "done" means for each piece of work in flight |
| [`review-of-v0.2.md`](review-of-v0.2.md) | **The Knowledge team's review of the revision.** Approves the direction; finds six defects that block authoring, and answers Planning's three open questions |
| [`review-disposition-v0.2.md`](review-disposition-v0.2.md) | **Planning's response.** All six fixed, both checkable claims verified — one of which surfaced a real bug in the engine |
| [`knowledge-datamodel.md`](knowledge-datamodel.md) | ⚠ **Superseded v0.1**, kept so the audit can be read against what it reviewed |

---

## What the audit changed, in one paragraph

The v0.1 proposal was reviewed by **counting the corpus** rather than by reading
the schema — 144 documents, 2,147 pages, 81,794 elements — and the corpus turned
out to be stranger than either team assumed. Racking is stated in six mutually
unconvertible units. Reinforcement extent is anchored to a footing depth that is
itself conditional. Of the 841 warning instances whose page position could be resolved, only 19.9%
sit inside a step that does something — which **falsified an invariant** outright. And the shipped source
policy had no class for an installation manual — 44.6% of every fact here — so
those facts were silently inadmissible for the very task they were about. None of
that was a flaw in the types; it is what holding the data tells you and reading the
schema does not.

The lesson worth keeping: **a schema review answers whether a model is coherent;
only a census answers whether it fits the data.**

---

## How this relates to the documents you already have

`CLAUDE.md` gives an authority ordering: `mvp-implementation-spec.md` is
authoritative, `guide.md` is the contract it implements, `target-architecture.md`
is informative, `state-and-gaps.md` is the measured snapshot. **Nothing here
displaces any of those.**

The distinction is inside versus outside:

- Those documents govern **how this platform works**. They remain the authority.
- These documents govern **what this platform exposes to a consumer**. They are the
  authority on that, and on nothing else.

**`docs/curation/` is not superseded by any of this.** The data model places it in
tier 3, both teams have read that as settled, and it remains this team's internals.
Where a document here appears to say something about your internals, it is wrong
and should be read as advisory. The contract has a short, explicit list of BINDING
items; everything not on that list is this team's decision.

## What is explicitly not specified here

Storage engine and schema. Whether claims live in one table or twenty. Extraction
pipeline, models, and OCR strategy. How a review queue is ordered and what the
reviewer sees. Whether curation runs as a CLI, a batch job, or a service. Language
and runtime beyond the API shape. Retrieval implementation. Release cadence.

## The one thing worth reading first

The consumer is a **pure function**. Given the same project and the same knowledge
it must produce the same plan, provably, years later — including with this platform
unreachable. That single property explains most of what the contract asks for, and
in particular why knowledge is fetched as one immutable, content-addressed object
before a run rather than queried during one.

The corollary, which is an obligation on Planning rather than on you: **a missing
role, an uncovered condition, or an unsatisfiable requirement produces a plan with
a named, warned line — never a failed run.** So a gap you publish does not break
anybody, and a snapshot containing very little is still a valid snapshot.

---

## Change log

**v0.2.1 · 2026-08-24 — the review, folded in.** `review-of-v0.2.md` found six
defects in the first revision, none needing a redesign: `Gap` was described as never
consumed while gates publish as gaps; `contributing_sources` was argued for and then
omitted from the contract, with no join target for `ParameterTable` rows and no
closure rule; twenty-three `_mm` fields broke §1.1's own binding rule on units; three
source-policy ranks were tied with no tie-break; four types were named and never
defined, of which `PostSlot` made post reinforcement unauthorable; and unconditioned
rows — 66% of the class the new source policy had just admitted — had no
representation. All fixed. `material` is now a bound condition dimension and the
`industry_standard` ranking does not ship without it.

**v0.2 · 2026-08-24 — the audit, folded in.** `contract-v0.1.md` → `contract-v0.2.md`
(eight binding items changed); `knowledge-datamodel.md` superseded by
`knowledge-datamodel-v0.2.md`. The largest changes: four units added to `UnitCode`;
two classes added to `SourceClass`, with installation manuals admissible for
structural work at level 2; `Coverage` replaced by an anchored `Span`; assembly
steps widened to five scopes with typed prerequisite edges; `Warning` became its
own entity with text primary and the code registry split in two; definitions gained
pinned `contributing_sources`; part-type namespaces moved from the tenant axis to
`shared` / `mfr/<manufacturer>` / `<tenant>`; gates named explicitly out of scope.

**v0.1 · 2026-08-23 — first proposal**, revised the following day after reading the
consumer's code properly. Three non-cosmetic corrections then: the catalog left the
snapshot (it is commercial and per-tenant); definitions are published, not just
claims; and a claim in `rationale.md` §6 was wrong — it said neither system could
express *"this product can serve as a top rail"*, when `PartType` and `PanelSpec`
always could. That correction mattered: had it been true, the audit would have been
a request to design a structure model instead of a bounded list of gaps against one
that works.
