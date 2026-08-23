# System overview — where this platform sits

```text
Status:    Informative. Orientation, not obligation.
Binding:   Nothing in this document. See contract-v0.1.md.
```

## 1. What the whole system does

A customer draws a fence on a map. The system works out what to build and what to buy —
and every number in that answer can be traced back to the page of a manufacturer document
it came from.

Three components, built by different teams:

```text
┌──────────────────────────────────────────────────────────────┐
│  FRONTEND                                                    │
│  map editor · knowledge admin · review queue                 │
│  decision inspection · BOM review                            │
└───────────────────────────┬──────────────────────────────────┘
                            │ one API — never calls Knowledge directly
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  PLANNING & BOM                     (repo: BOM)              │
│  project · topology · planning runs · strategy · decisions   │
│  requirements · product selection · cutting · final BOM      │
│                                                              │
│    ┌────────────────────────────────────────────────┐        │
│    │ pinned snapshot · sha 4f1c9a2e                 │        │
│    │ a planning run reads this and nothing else     │        │
│    └────────────────────────────────────────────────┘        │
└──────────┬────────────────────────────────┬──────────────────┘
           │ GET /snapshots/{hash}          │ search · review · authoring
           │ RESOLUTION — deterministic     │ DISCOVERY — a human is reading
           ▼                                ▼
┌──────────────────────────────────────────────────────────────┐
│  KNOWLEDGE                          (repo: fence-rag)        │
│  documents · evidence · claims · definitions · publishing    │
└──────────────────────────────────────────────────────────────┘
```

## 2. The division of responsibility

The rule that settles most boundary arguments:

> **Knowledge owns definitions. Planning owns instances.**

*What is a post? What can this product be used as? What constraints apply, and under what
conditions?* — Knowledge.

*Which post goes at station 7? What length is it cut to? What must be bought?* — Planning.

When a question is hard to place, ask whether the answer would be the same on a different
project. If yes, it is a definition and belongs here.

## 3. Two kinds of question, and why they are separated

Planning's defining property is that generating a plan is a **pure function**: same
project, same knowledge, same answer — provably, and years later. A pure function cannot
call a search service partway through.

So this platform is asked two very different kinds of question, and only one of them ever
happens during a planning run.

**Resolution.** Before a run, Planning fetches one immutable object addressed by its own
hash, and computes against that copy. It is cached locally, and a default copy ships
inside the Planning repository so that development and the regression suite work with this
platform switched off entirely.

**Discovery.** Search, evidence lookup, review, authoring. A person is in the loop.
Results carry source references; nothing here is ever an input to a plan.

That split is why the contract asks for an immutable, content-addressed snapshot rather
than a query API — and why retrieval quality, which is measured and imperfect, is not a
correctness risk for the plan. Retrieval helps a person find a page. Only what a person
accepts reaches a snapshot.

## 4. What crosses, concretely

**Knowledge → Planning**, once per run, fetched beforehand: role definitions, product
definitions, catalog items, assembly definitions, parameter tables, rules, and gaps —
all inside one hashed snapshot.

**Planning → Knowledge**, asynchronously, never during a run: gap reports, and expert
corrections captured verbatim from the field and forwarded as proposals.

**Frontend → Knowledge**: nothing directly. Authoring and review traffic is proxied
through Planning, which owns authentication and locale. This platform sees one consumer.

## 5. The working mode: gaps are normal

The two components will find gaps in each other continuously, and that is how this gets
built. Knowledge will read a manual describing a part Planning cannot count. Planning will
need a condition dimension Knowledge has never extracted. Neither is a failure.

What matters is that a gap on one side never stops work on the other. One invariant
carries most of it, and it is an obligation on Planning, not on you:

> A missing role, an uncovered condition, or an unsatisfiable requirement produces a plan
> with a named, warned line — never a failed run.

So a gap you publish does not break anybody. It appears in a bill of materials as an
explicit "this is missing, and here is why," and work continues on both sides.

The corresponding obligation on this side is the mirror of it: **publish gaps as gaps.**
When a document describes something that cannot be expressed, record that rather than
approximating it into a shape that nearly fits. An approximation produces a confidently
wrong quantity; a gap produces a visible hole.

## 6. Where the two roadmaps meet

This platform's own measured position is the honest starting point. From
`state-and-gaps.md` and the curation capability matrix:

- The values Planning most needs — maximum post spacing, footing depth — currently sit in
  scanned drawing tables at 0.588 recall on digit-bearing values, and the five approvals
  carry one `table` element between them.
- Component selection, BOM construction and assembly are recorded as absent or
  unrepresented.
- 1,988 facts exist; none has been reviewed by a person.

None of that blocks the integration work. The contract is designed so that a snapshot
containing very little is still a valid snapshot, and Planning still produces a plan from
it — with most lines warned. Coverage grows as curation runs; the boundary does not have
to wait for it.
