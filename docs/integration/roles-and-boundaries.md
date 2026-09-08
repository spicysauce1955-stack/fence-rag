# Roles and boundaries — who does which job

```text
Status:     PROPOSED, 2026-09-08, by the Knowledge team. Both dispositions PENDING.
            NOT AN AMENDMENT. It changes no BINDING item and needs no ratification.
Binds:      Nothing, until both sides record acceptance below.
Authority:  NONE at the boundary. `contract.md` is FROZEN at v1.3 and governs what
            crosses. Where this document and the contract touch the same thing, the
            contract wins and this document is the defect. Say so rather than
            working around it.
Purpose:    The contract says what crosses. It deliberately says nothing about who
            does which job. That gap was harmless while there was one consumer and
            one shape; it stopped being harmless on 2026-09-08, when the Knowledge
            side settled a direction that changes what the other side is expected
            to carry.
Reads with: `docs/knowledge-loop.md` (the Knowledge team's purpose and direction)
            and `conversation.md` T46-T55.
```

---

## 0 · Why this exists, and what it must not become

`AMENDING.md` names three things that are **not** amendments; the second is *"anything
internal — pipeline shape, extraction strategy, storage, read models, curation workflow. If it
does not change what crosses, it is not the contract's business."*

This document is the mirror of that clause. It records **which side does which job**, which is
also not the contract's business — and which both sides have nonetheless been assuming, in
writing, differently, for three weeks. Two examples measured this week:

- Planning's `generator.py` falls through to `FALLBACK_MAX_SPAN_MM` because no published table
  has ever matched a run — `[measured]` zero of 6,563 (T51 §2). Neither side owned the join.
- Knowledge published 18 more `Part`s into an unreachable namespace in one session and noticed
  only while writing a commit message (T53 §4). Neither side owned noticing.

Both are role gaps, not contract gaps. The contract was correct throughout.

**The failure mode to avoid:** this document becoming a second authority over the frozen
contract. It has none. If it ever appears to grant, remove or reinterpret a BINDING obligation,
that is a defect in this file, and the fix is here — not an amendment.

---

## 1 · The line, in one sentence

> **Knowledge owns definitions. Planning owns instances.**

That sentence is from `system-overview.md` §2 and predates everything below. It has survived
every reframe and is still the sentence that settles arguments. Everything that follows is an
application of it, not a replacement.

Its corollary, from `docs/superpowers/specs/2026-08-27-unblocking-planning-design.md` §4 and
equally unchanged:

> **No user ever reaches the Knowledge platform directly.** Screens are Planning's; the CLI and
> the API behind them are Knowledge's. Knowledge builds no UI.

---

## 2 · Who owns what

| | Knowledge (fence-rag) | Planning (BOM) |
|---|---|---|
| **Sources** | The document corpus, its extraction and its citations | Its own product catalogue and pricing |
| **Products** | Nothing. **Knowledge is not a parts catalogue** | The products a job is actually built from |
| **What is true** | Values, procedures, conditions, conflicts — all cited | — |
| **What is happening** | — | The map, the job, actions, choices, run state |
| **Method** | The actions the *sources* describe (`Procedure`, `AssemblyStep`) | The commands the *engine* accepts |
| **Geometry** | Published dimensions in thousandths | Placement, fitting, cutting, assembly |
| **The agent** | — | Hosts it; it reads Knowledge and commands the engine |
| **The person** | Never sees one. A curator reviews Knowledge's own readings | Owns every screen, and decides what any person is shown |
| **Identity of a job** | — | Owns it entirely |
| **Learning** | Relevance, from its own query log | — |

**The most consequential line is the second.** Knowledge holds `mfr/*` identities derived from
manufacturer documents. Planning will carry different products. Neither side can author the
join alone: Knowledge cannot assert what a product *is* in Planning's catalogue without
inventing a product identity, and Planning cannot assert what a manufacturer document *means*.
Both sides agreed at T52 §2 / T55 §3 that **the join is per-job configuration and belongs to
neither of us.**

---

## 3 · The surfaces between us

Three, and only three. Two are new and proposed; one exists and is unchanged.

### 3.1 The snapshot — unchanged, and it stays

A pinned, hashed, content-addressed object, fetched before a run. Planning's own statement of
why is still right and is not being revised: *a planning run is a pure function, so this
platform can be unreachable and a plan from last March still renders the same numbers.*

**Nothing below weakens this.** It is the engine's surface and it stays exactly as it is.

### 3.2 The query — proposed, outward

*"Here is the situation. What applies, how strongly, and on what evidence?"* Returns values
**and procedures**, cited, with conflicts surfaced rather than resolved.

This is a **second** surface for a **second** consumer, not a replacement for §3.1. The engine
wants reproducibility; an agent wants applicability. A query answer names the snapshot it was
computed from, so an agent's advice stays as reproducible as an engine's plan.

**Why it is Knowledge's to serve rather than Planning's to compute:** retrieval here is not
fetch-by-id. It means knowing which condition dimensions apply, that currency comes from the
supersession graph rather than the `version_status` label, that five tables agreeing is
corroboration rather than redundancy. Those rules have been implemented on the Planning side
four times and got subtly wrong each time — T46 §2, T49 §6, T50 §3, T55 §7 — and in every case
Planning found and fixed it themselves. That is not a competence claim; it is a claim about
where a subtle rule should live.

### 3.3 The override — proposed, inward

The only thing that comes back. Four required fields; refused if any is empty.

| Field | Meaning | Who can supply it |
|---|---|---|
| `WHAT` | The value contradicted, **by its citation** — or a whole document (`distrust`) | Planning, from the citation Knowledge issued |
| `WHY` | The reason, verbatim | Only Planning has it |
| `HOW FAR` | Scope: this job / this product / this jurisdiction / always | Only Planning has it |
| `WHO` | The person and their role | Only Planning has it |

`WHY` and `HOW FAR` **cannot be backfilled**. `WHO` and the role can only ever be *asserted* —
Knowledge never observes a person and cannot verify either — which is exactly why they must be
required rather than inferred.

---

## 4 · What each side takes on

### Knowledge undertakes to

1. Publish **values and procedures**, every one resolving to a document, page and region.
2. Serve §3.2, and keep serving §3.1 unchanged.
3. **Surface conflicts, never resolve them.** No silent winner, ever.
4. Report a **blast radius** before accepting a document-level `distrust` — *"this withdraws 30
   values across 9 rules, confirm"* — rather than silently withdrawing evidence.
5. **Never delete.** A distrust is a link pointing at what it withdraws, so a person who was
   mistaken can be un-mistaken.
6. Never write anything into Planning, and never require Planning to model a Knowledge
   internal.
7. Keep `ref_id`s stable, or version them. **This is newly load-bearing:** an override names a
   value by its citation, so an unstable id orphans a person's correction rather than merely
   breaking a citation.
8. Publish the actions the *sources* describe, and never model Planning's command vocabulary.

### Planning undertakes to

1. **Carry Knowledge's citation ids on commands**, opaque and unparsed. This is the hook the
   whole correction loop hangs from: without it an override has nothing to name. Planning's own
   code already treats these ids as opaque and says so, so the discipline exists.
2. Send overrides with all four fields of §3.3, or not at all.
3. **Assert `WHO` and the role.** Knowledge cannot obtain them by any other route.
4. Decide what any person is shown, and whether a person is asked anything at all.
5. Answer a quarantined batch **as a batch** — Knowledge holds an override's questions until
   the batch is resolved, and releases all of it or none.
6. Own the map, the job, the actions, the commands, and the products.
7. Host the agent, and keep the agent's writes inside Planning.

---

## 5 · What is explicitly NOT owed, so it is not re-proposed

| Not owed | By whom | Why |
|---|---|---|
| Whole job blobs sent to Knowledge | Planning | A private structure that changes on every refactor is not a corpus, it is a liability. Knowledge would hold many incompatible shapes with a specification for none. If Knowledge needs a field, it asks for that field. |
| A response to every command | Planning | It is an override with everything useful stripped off — no reason, no scope, no author. The override already carries all of it, explained. |
| A model of Planning's commands | Knowledge | Knowledge publishes the actions the sources describe; the agent maps them. Coupling to a vocabulary still being designed is the one move worth avoiding. |
| A usage/feedback channel | Planning | Knowledge serves the queries, so it can count them itself. Relevance is measurable on Knowledge's side alone. |
| A UI, of any kind | Knowledge | §1's corollary. Unchanged since 2026-08-27. |
| A product mapping | Either side alone | Neither holds both endpoints (§2). |

---

## 6 · What would reopen this

Named now so that neither side has to re-derive them.

- **The agent moving out of Planning.** §2 and §3.2 both assume it is hosted there. If it moves,
  the query's authentication, tenancy and rate story all change.
- **A second Knowledge consumer.** Everything here assumes one counterpart. A second one makes
  "Planning decides what is shown" insufficient as a rule.
- **Knowledge acquiring products of its own**, or Planning wanting Knowledge's `mfr/*`
  identities to *be* its catalogue. Either collapses §2's second row and this document with it.
- **A person reaching Knowledge directly** — a curator console exposed to a customer, say. §1's
  corollary would no longer hold.
- **Overrides needing to write into evidence.** The current rule is that they never do; they are
  read at query time and win on contradiction. If that ever has to change, it is a change to
  what an override *is*, not a tuning.

---

## 7 · Dispositions

Neither side has accepted this. It binds nothing until both entries below are filled in, in
writing, in this file — the same standard `AMENDING.md` §5 sets for an amendment, applied here
by choice rather than by requirement.

- **Knowledge team:** PROPOSED, 2026-09-08. Filing is not acceptance.
- **Planning team:** **PENDING** — accept / accept-modified / reject, with reasoning.

Two things the Knowledge side would specifically like shot at:

1. **§4 Planning item 1** — carrying opaque citation ids on commands is the only real new
   obligation this document places on Planning, and it is placed there because Knowledge cannot
   do it. If it is expensive, say so now: the whole correction loop is designed around it, and
   it is cheaper to redesign than to discover.
2. **§3.2** — whether a served query is acceptable at all, given that `build-plan.md` §1 argues
   for a pre-fetched immutable object *"rather than queried"*. The Knowledge reading is that
   both are right for different consumers. If Planning reads the pure-function property as
   excluding a live query even for an agent, that disagreement should surface here rather than
   in an implementation.
