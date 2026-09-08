# The knowledge loop — what this system is for

```text
╔══════════════════════════════════════════════════════════════════════════╗
║  READ THIS FIRST.                                                        ║
║                                                                          ║
║  This document says what the whole project is for and how the pieces     ║
║  fit. Every other document here describes a part; this one says why the  ║
║  parts exist. If another document contradicts this one about PURPOSE,    ║
║  this one is right and the other is stale — say so rather than working   ║
║  around it.                                                              ║
║                                                                          ║
║  Agreed with the project owner, 2026-09-08, across a full session.       ║
║  It is not frozen. It is not an amendment and binds nothing at the       ║
║  contract boundary. Correct it when it is wrong.                         ║
╚══════════════════════════════════════════════════════════════════════════╝
```

Authority: this document governs **purpose and direction**. `docs/integration/contract.md`
governs **what crosses the boundary** and is frozen; nothing here changes it.
`docs/mvp-implementation-spec.md` governs **how this platform works internally**. Where this
document and those two disagree about a mechanism, they win; where they disagree about *what
we are building and why*, this one does.

---

## 1 · What this is, and what it is not

**This is the foundation knowledge layer that AI agents reason from.** It knows how a fence is
built — the numbers and the method — and every claim it publishes traces to the page it came
from.

It is **not** a parts catalogue and **not** an inventory. The Planning/BOM backend will carry
different products entirely. A footing table from one manufacturer is not *inapplicable* to a
different vinyl fence; it is *weaker evidence*, and one of the open problems below is that the
system has no way to say so.

The long-run goal: the base improves every time the system is used, until it is precise enough
that an agent given a layout can decide how to install, structure and assemble it. The
improvement comes from people correcting it, and from watching which of its knowledge actually
gets used.

**What makes it worth having is that every number can be shown to an inspector.** No learning,
weighting or preference may quietly destroy that. This is the one constraint that outranks
convenience everywhere below.

---

## 2 · The shape

Four parts, and only two of them exchange anything with this system.

```text
   customer's own                                  ┌─────────── BACKEND ───────────┐
   products + sources                              │                               │
          │                                        │   ┌─────────┐   ┌─────────┐   │
          ▼                                        │   │  AGENT  │──▶│ ENGINE  │   │
   ┌──────────────────┐   query: what applies?     │   └─────────┘   └─────────┘   │
   │  KNOWLEDGE BASE  │ ─────────────────────────▶ │        ▲         commands      │
   │                  │   values + procedures,     │        │         carry our     │
   │  values          │   cited, conflicts kept    │        └───query──citation ids │
   │  procedures      │                            │                               │
   │  conditions      │ ◀───────────────────────── │                               │
   └──────────────────┘   overrides:               └───────────────┬───────────────┘
          ▲                what · why · how far · who              │
          │                                          ─ ─ ─ ─ ─ ─ ─ ┼ ─ ─ ─ ─ ─ ─ ─
      curator                                        we never see below here
   (internal to this system)                                       │
                                                               end user
```

**The agent lives in the backend.** The map, the actions and the command vocabulary are native
to it there, and none of them ever crosses into this system. Only our half crosses, and it
crosses through one query endpoint.

**The curator and the end user are different people.** The curator belongs to this system and
reviews its own readings. The end user never touches it — they are a name and a role in a
payload, asserted by the backend, and we can neither observe nor verify them.

---

## 3 · What crosses, and what deliberately does not

### Outward — the query

> *Here is the situation. What applies, how strongly, and on what evidence?*

Returns values **and procedures**, each cited, with conflicts surfaced rather than resolved.
This is the only real interface, and the 78 gold questions in `eval/` already test exactly it.

**The query does not replace the pinned snapshot, and this needs saying because it looks like it
does.** `docs/build-plan.md` states the property the whole publishing design rests on: *"a
planning run is a pure function. It fetches one hashed snapshot beforehand and computes locally,
so this platform can be unreachable and a plan from last March still renders the same numbers.
That is why knowledge is published as an immutable content-addressed object rather than
queried."* That is still true and still right — **for the engine.**

The two consumers want opposite things, and both are legitimate:

| | wants | gets |
|---|---|---|
| **the engine** | reproducibility, offline, a plan that renders identically a year later | a pinned, hashed, content-addressed snapshot |
| **the agent** | *"what bears on this situation, and how much should I trust it?"* | a query, answered live, with conflicts surfaced |

So the snapshot stays exactly as it is. The query endpoint is an **additional** surface for a
**different** consumer, and a query answer names the snapshot it was computed from — so an
agent's advice remains as reproducible as an engine's plan. Anyone reading `build-plan.md` §1
and this section together should read them as complementary, not as a reversal.

Keeping the query on this side is deliberate: retrieval here is not fetch-by-id. It means
knowing which condition dimensions apply, that currency comes from the supersession graph and
not from the `version_status` label, that five tables agreeing is corroboration rather than
redundancy. Those rules have been re-implemented on the far side four times and got subtly
wrong each time — see `conversation.md` T46 §2, T49 §6, T55 §7, and the span-limit conversion
in T50 §3. That is not carelessness; it is our domain and it is subtle. **The semantics stay
where the expertise is.**

### Inward — the override

One record, four required fields. Section 4.

### Deliberately cut, with the reasoning, so nobody re-proposes them

| Cut | Why |
|---|---|
| **Storing whole job blobs** | A private structure that changes whenever the backend refactors is not a corpus, it is a liability. By the time we wanted to read it we would hold many incompatible shapes and a specification for none. The PDF analogy that justified it is false: a PDF is a public, stable, self-describing format. If we later need something from a job, we ask for that field, and then it is something we can actually read. |
| **A response to every command** | It is an override with everything useful stripped off. "We said 1676, it became 1780" carries no reason, no scope and no author, and generates a question we then have to chase. The backend already decides what is worth sending, and an override arrives explained. |
| **Any model of the backend's commands** | We publish the actions the *sources* describe. The agent maps those onto whatever the engine accepts. Their vocabulary never crosses, and we never couple to something still being designed. |

### The one thing the backend must carry for us

A command carries **our citation ids**, opaque to the backend — its own code already treats
these ids as opaque and says so. That is the hook the whole loop hangs from: when a person
changes a number, the override's `WHAT` field needs something to point at. Attaching it costs
nothing at emission, because the agent is holding it. It cannot be reconstructed afterwards.

> ### This makes `ref_id` stability blocking, and it was not before
>
> A `ref_id` embeds a bounding box. A 0.02 pt shift from a toolchain upgrade changes it
> completely, and `delete_version_rows()` removes the rows the old id named. Until now the
> worst case was that **published citations break** — bad, and `cli refs --verify` guards it.
>
> Under this design an override *names a value by its citation id*. So an unstable id no longer
> merely breaks a citation: **it orphans a person's correction**, which is the one thing in this
> system that does not regenerate. A human judgement pointing at an id that no longer exists is
> unrecoverable in a way a re-extractable fact never is.
>
> Extraction editions (`docs/four-layer-model-design.md` §5.1, gap G38) therefore move from
> *deferred* to **a precondition of override intake**. Build item 4 below must not ship before
> this is settled.

---

## 4 · The override

The only thing that comes back. Every field required; the record is refused if any is empty.

| Field | Meaning |
|---|---|
| **WHAT** | The value being contradicted, by its citation — **or a whole document** (section 5). |
| **WHY** | The reason, verbatim, in whoever's words they were. |
| **HOW FAR** | The scope it reaches. |
| **WHO** | The person and their role, as the backend asserts them. |

**`WHY` and `HOW FAR` cannot be backfilled.** A year of overrides without them is a year of
unusable data. `WHO` and the role can only ever be asserted — we never observe a person — which
is precisely why they must be required rather than inferred.

### Scope, and why there is no taxonomy of override kinds

Scope runs from *this job only* → *this product* → *this jurisdiction, soil, climate* →
*always*.

An earlier draft proposed three named kinds of override. That was inventing categories before
seeing any. **Scope alone carries the distinction**: an override reaching everywhere is "this is
wrong"; a narrow one is "not here". *"The ground was full of rubble"* and *"56 inches is simply
wrong"* sit at opposite ends of one honest field. The categories can be derived later from the
scopes people actually pick, which is evidence rather than a guess.

Scope needs no new machinery either. Every rule already carries **conditions** — exposure
category, fence height, HVHZ, frost line — which is precisely *under what circumstances does
this hold*. An override is a rule with conditions, and *this job only* is a very narrow one.

### The role axis already exists

An engineer's override and an apprentice's should not weigh the same. `RoleCode` is already a
registry in the contract (`contract.md:394`), currently meaning *who is asking* and deciding
which sources rank for whom. Adding roles needs no negotiation. It is simply not yet attached
to who an override is attributed to. Today's reviews carry a bare `reviewer` name that
`reviews.py` itself notes is unverifiable, and no role at all.

---

## 5 · Distrusting a document

A rule found false is sometimes evidence that its *source* should not be relied on. So `WHAT`
accepts a document reference as well as a value reference. The other three fields are unchanged.

Three rules:

- **It is called `distrust`, not delete or discard.** Nothing is ever removed. A distrust is a
  link pointing at what it withdraws, so somebody who was mistaken can be un-mistaken.
- **It reports its blast radius before being accepted.** One mis-read row is a poor reason to
  throw away a sealed approval backing thirty other values. *"This withdraws 30 values across 9
  rules — confirm."* The citation graph already computes this; `cli refs --verify` walks it.
- **It is scoped like any other override.** Distrust *for this customer* and distrust
  *everywhere* are both sensible, which is another reason the word is not "discard".

---

## 6 · The quarantine

An override arrives already explained, but it is not automatically safe. *Is this really
global? Does it contradict a sealed approval?* Those are questions, and a question is an object
this system has never produced — not a fact, not a `Gap`.

**Overrides are held with their questions until a batch is answered, and then the whole batch
releases or none of it does.** A half-understood correction can never partly leak in.

Two constraints on how questions are used:

- **The backend decides whether a human ever sees one.** We require an answer before the batch
  counts; we do not require that anybody was asked.
- **The first version publishes no questions at all.** Generate them, look at a hundred
  yourself, and only then decide what a good question is. Bad questions spend trust, and an
  unanswered queue is already a live failure here — 387 low-value items currently drown this
  system's own review queue.

---

## 7 · Learning, and where the signal comes from

Two inputs, and neither needs anyone's cooperation beyond what already crosses.

**Disagreement** comes from overrides — deliberate, reasoned, attributed.

**Relevance** comes from **our own query log**. If the agent asks us what applies, we serve that
request; we already know what was asked and what we returned. Which knowledge is load-bearing
and which is never touched is measurable on this side of the boundary, for free. It does not
need a feedback channel and must not be built as one.

---

## 8 · The hard/soft boundary

This repository's whole character is *refuse rather than guess*. A learning layer must be the
opposite: lenient, provisional, willing to be wrong. They coexist only if the direction of
writing is settled once, explicitly.

```text
  HARD · evidence, cited, immutable        │      SOFT · provisional, revisable
                                           │
  sources ─▶ canonical ─▶ claims ─▶        │      overrides    (scoped, reasoned, attributed)
                          published        │      learned relevance   (from the query log)
                             │             │              │
                             └────────▶  what a query returns  ◀──────┘
                                    both sides, ranked
                                    contradictions surfaced, never resolved
```

**The rule: soft reads hard at query time and wins on contradiction. Soft never writes into
hard.**

An override wins because a person said so, in writing, with a reason and a scope — that is not
a silent contradiction, it is an attributed one, and it extends the citation chain rather than
breaking it. Learned relevance may **reorder, prefer and add**. It may never silently overwrite
a number an inspector can be shown, because a learned weight has no citation.

`docs/target-architecture.md` §5.2 already lists automatic conflict resolution as a *never*.
That survives contact with the learning layer unchanged.

---

## 9 · Where we actually are

`[measured]` 2026-09-08 against the current store.

| Component | State | Note |
|---|---|---|
| machine-only boundary | **built** | The only external surface is a small API behind a bearer allowlist. No session, no screen, no user record — section 2's shape is already what the code does. |
| citable values | **built** | Every published number resolves to a document, page and region. This is what `WHAT` points at and what a command's citation ids name. |
| tenancy | **built** | `documents.owner_tenant`; NULL is shared; isolation enforced at the ref minter. The container for a customer's own products and sources. |
| review ledger | **built** | Curator corrections, durable and replayable, keyed on evidence rather than row ids — so they survive re-extraction. The correction loop's hard problem, solved at small scale. |
| source precedence | **built** | Configurable ranking per task and source class. |
| conditions | **built** | Already the scope field; not yet pointed at overrides. |
| supersession | **built** | The graph that would compute a distrust's blast radius. |
| role axis | *half* | `RoleCode` exists and ranks sources for *who is asking*; not attached to who an override is attributed to. |
| attribution | *half* | `reviewer` is a bare name the code calls unverifiable; no role. |
| per-value provenance | agreed, unratified | Amendment 008 — accepted by both sides 2026-09-08, waiting on a batch with 009 and 010. |
| **procedures** | **built, publishing nothing** | The pipeline shipped — `steps.py`, `procedures.py`, `step_candidates`, `step_reviews`, `cli steps`, ledger schema 2. It publishes `[]` for want of **reviews**, not for want of code. See below. |
| **`Rule`** | **missing** | No shape anywhere — not in the contract, not in the datamodel. `CANDIDATES.md` C16 raises it and it is unfiled. |
| query endpoint | missing | The retrieval machinery exists; the endpoint does not. |
| query log | missing | Entirely ours. The only honest source of relevance. |
| override intake | missing | No path for one to arrive, and no document-level target. |
| quarantine | missing | No held-until-adjudicated concept, no bulk answer. |

### The largest gap: this base knows numbers, not method

`[measured]` the current snapshot publishes **9 parameter tables** and **42 part definitions**,
every one cited to a page — and **0 procedures, 0 assembly steps, 0 rules**.

The corpus is full of installation guides that say *what to do* — *set the post before the
rail*, *never strike the PVC post directly* — and none of it is published. A spec sheet knows a
footing depth; building a fence needs both. An agent asked *"how do I install this?"* can
currently be told a dimension and nothing else.

**But the cause is not what it looks like, and this correction matters for the build order.**
`[measured]` 2026-09-08 against `evidence.db`:

- The **pipeline is complete and shipped** — `steps.py` (the splitter), `procedures.py` (the
  snapshot member), the `step_candidates` and `step_reviews` tables, `cli steps
  --propose/--queue/--accept`, the `verify()` refusals, and review-ledger schema 2.
- `step_candidates` holds **91 rows across 2 documents** — 74 `step`, 12 `section`, 2 `branch`,
  1 `prohibition`, 1 `note`, 1 `footnote`.
- `step_reviews` holds **0 rows**. Not one has been reviewed by anybody.

So `procedures` publishes `[]` **for want of reviews, not for want of code**. This is a
curation-capacity problem wearing an engineering problem's clothes, and it is exactly the shape
the quarantine and bulk-answer mechanism in section 6 exists to attack. `docs/build-plan.md`
still says *"there is no assembly-step model in this codebase yet to build on"* — that is false
and should be corrected rather than acted on.

Two live defects in the shipped builder, found by the 2026-09-06 alignment review and closed by
nothing since — both must be fixed before a `Procedure` publishes:

- `procedures.build_procedures()` synthesizes an `after` edge to each preceding published step.
  The contract requires **empty dependencies** when a page merely lists steps in order, and a
  test currently endorses the mismatch.
- It always sets `Procedure.scope` to null, which the contract defines as **owned by no
  product** — not *product unknown*.

**`Rule` is different and genuinely unbuilt**: it has no shape anywhere, in the contract or the
datamodel. `CANDIDATES.md` C16 raises it and it is still unfiled.

### And nothing has ever consumed any of it

`[measured]` by the Planning team (`conversation.md` T51 §2): across **6,563 stored generation
runs, not one consulted a published value**. `cli reach` reports the same thing from this side —
11 identity families, 0 declared associations, and in the worst snapshot 51 of 51 scoped objects
reaching nobody (`docs/state-and-gaps.md` G106).

The obvious reading — *"our product names don't match theirs, build a mapping"* — is wrong, and
was nearly built. The backend carries different products entirely; matching identifiers was
never the point. The real cause is that everything specified so far is a contract with a
deterministic engine that looks up a value by exact product name, and the consumer we actually
want asks *what bears on this situation, and how much should I trust it?*

---

## 10 · Build order

**One item per session, each with its own acceptance test.** The design must survive between
sessions, which is what this document is for.

The repository has run this play before and it worked: with 137 PDFs it ingested everything,
extracted nothing, measured, and only then wrote the extraction rules. Same order here.

1. **Publish procedures.** The largest gap, and nothing else depends on it.
   **The two builder defects are FIXED as of 2026-09-08** — print order is no longer published
   as an `after` edge (obligation 11), and `scope` now resolves through
   `parameters._default_scope` instead of asserting `null`. What remains is **not code**:
   `[measured]` 91 candidates across 2 documents with **0 reviews**, and `segment_kind` is a
   person's call that must not be fabricated. Review the queue, then widen —
   `docs/workflows/source-to-contract.md` measured 466 glyph-paired steps across 111 pages in
   22 documents waiting behind this one page.
   Acceptance: a snapshot publishes at least one `Procedure` with cited steps and honest
   dependencies, and `snapshot --verify-stored` passes.
   **This item now needs a curator, not an engineer.** If no person is available, start at
   item 2, which is unblocked.
2. **The query endpoint.** The only real interface. Acceptance: it answers the 78 gold questions
   at or above the current retrieval baseline, with citations, and the relevance audit still
   measures what it measured before.
3. **The query log.** Ours alone. Acceptance: every served query is recorded with what was
   returned, and a report can name the least-consulted published objects.
4. **Override intake.** Four required fields, value or document target, blast radius reported
   before a distrust is accepted. Acceptance: an override missing `WHY` or `HOW FAR` is refused,
   and a document distrust names every value it withdraws.
5. **A source class for asserted knowledge**, so an override has somewhere to sit in the
   ranking. A registry addition — no negotiation. Acceptance: an override ranks against a
   manufacturer value through the existing source policy.
6. **Quarantine.** Acceptance: a batch with one unanswered question influences no query result;
   answering the batch releases all of it.
7. **Write the direction of writing down** in the spec, as a rule with a test: soft reads hard,
   soft never writes hard.

Nothing above is blocked by the contract, and none of it is an amendment.

---

## 11 · What this document does not decide

- **Where the agent runs.** It lives in the backend logically; whose repository and release
  cadence is open, and a component that emits commands is coupled to a command vocabulary that
  is not yet designed. Coupling to an undecided thing is the one move worth avoiding.
- **The command vocabulary itself.** Theirs.
- **What a good question looks like.** Deliberately deferred until a hundred have been read.
- **How relevance is weighted.** There is no signal yet. Build the log first.
- **Whether the graded-applicability problem gets a representation.** Today the system can say
  "exact match" or "no rule". It cannot say "weaker evidence". That is real, and it is not yet
  designed.

---

## 12 · Related documents

- `docs/integration/contract.md` — **frozen**, what crosses the boundary. Verify with
  `cd docs/integration && sha256sum -c contract.sha256`.
- `docs/integration/AMENDING.md` — how the contract changes. Also frozen and hashed.
- `docs/integration/conversation.md` — the negotiation transcript with the Planning team, T1–T55.
  Append-only. The reasoning behind sections 3, 7 and 9 above is in T46–T55.
- `docs/state-and-gaps.md` — every measured gap, G1–G106. The live record; trust its numbers
  over this document's if they ever disagree.
- `docs/build-plan.md` — the previous build ordering, which section 10 supersedes on priority.
- `docs/mvp-implementation-spec.md` — how this platform works internally.
- `guide.md` — the twelve prohibitions. Still governing, and nothing here relaxes any of them.
