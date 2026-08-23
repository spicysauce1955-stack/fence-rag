# Integration — the boundary with Planning & BOM

```text
Status:    Proposal, v0.1. For review by this team.
Authority: Binding ONLY at the boundary. Silent on everything inside it.
Origin:    Written by the Planning & BOM team (the consumer of this platform).
```

## What this directory is

This platform is about to acquire a consumer. A separate system — **Planning & BOM** —
turns a customer's map into a plan and a bill of materials, and it needs the knowledge
this platform produces.

These documents describe the boundary between them: what crosses it, in what shape, and
what each side promises the other. They exist so that two teams working in two
repositories can build independently without discovering their disagreements at
integration time.

| Document | Answers |
|---|---|
| [`system-overview.md`](system-overview.md) | What is being built overall, and where this platform sits in it |
| [`contract-v0.1.md`](contract-v0.1.md) | What crosses the boundary, and the promises each side makes |
| [`rationale.md`](rationale.md) | Why each binding item exists — mostly measured from this store |

## How this relates to the documents you already have

`CLAUDE.md` gives an authority ordering: `mvp-implementation-spec.md` is authoritative,
`guide.md` is the contract it implements, `target-architecture.md` is informative,
`state-and-gaps.md` is the measured snapshot. **Nothing here displaces any of those.**

The distinction is inside versus outside:

- Those documents govern **how this platform works**. They remain the authority.
- These documents govern **what this platform exposes to a consumer**. They are the
  authority on that, and on nothing else.

Where a document here appears to say something about your internals, it is wrong and
should be read as advisory. The contract has a short, explicit list of binding items;
everything not on that list is this team's decision.

## What is explicitly not specified here

Storage engine and schema. Whether claims live in one table or twenty. Extraction
pipeline, models, and OCR strategy. How a review queue is ordered and what the reviewer
sees. Whether curation runs as a CLI, a batch job, or a service. Language and runtime
beyond the API shape. Retrieval implementation. Release cadence. Whether you adopt the
reference sketches referenced in `rationale.md`.

## The one thing worth reading first

The consumer is a **pure function**. Given the same project and the same knowledge it
must produce the same plan, provably, years later — including with this platform
unreachable. That single property explains most of what the contract asks for, and in
particular why knowledge is fetched as one immutable, content-addressed object before a
run rather than queried during one.

## Status of this proposal

v0.1, unreviewed by this team. Items are expected to change. Registry additions are not
breaking changes and need no negotiation; changes to the stable core do.

The two pieces of work that cross no boundary and need no agreement are named at the end
of the contract. One of them is on this side and can start immediately.
