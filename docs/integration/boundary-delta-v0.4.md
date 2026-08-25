# v0.4 — four things that need your agreement

```text
Status:   Approval request. From the Planning & BOM team.
Size:     Deliberately short. Four items, and nothing else in it.
Why:      You have done two full review rounds. Most of what changed since is
          internal to our engine and you cannot affect it, so it is not here.
Reads:    contract.md carries the binding text; this is the summary of what moved
          and why, so you can approve or push back without re-reading it.
```

## 0. What happened since v0.3, in one paragraph

We audited our own design against our own codebase — the equivalent of what you did
to our proposal with your corpus. It found seven defects, two of which were in code
we had already given you (both corrected in v0.3 and already in your repo). Then we
audited our own **additions** specifically, on the theory that the things we invented
were the least-checked part of the design. That found six more, and it was right: every
one was in something we added rather than something you asked for.

The outcome for you is small, because most of it was internal. **Four items cross.**

---

## 1 · `Gap` finally has a shape

**What changed.** We have told you six times to publish something *"as a `Gap`"* and
never defined the type. That was not an oversight in wording — you genuinely could not
author one. `contract.md` §1.2.1 now gives it fields.

```text
Gap {
  id
  kind         unmodellable_entity | uncovered_condition
             | unsatisfiable_requirement | unquantified
             | missing_value | unmapped_part_kind
  subject      EntityRef | SlotRef | ParamRef    what is missing, addressably
  because      code + params                     renders in both locales
  cites        [SourceRef]                       evidence, where there is any
  would_close  str    one sentence: what would resolve this
  severity     warns_line | informational
}
```

**What we would ask you to check.** Two things:

- **Is `kind` sufficient for what you actually hold?** We derived the six from your own
  findings — gates, the uncovered footing rows, the unquantified accent effect, the part
  kinds no rule can count. If a seventh shape recurs in your corpus, now is the cheap
  moment.
- **Is `would_close` writable?** It is the field we care most about. A gap that says
  *"footing depth is missing"* sends a curator hunting; one that says *"a footing row for
  exposure C, non-HVHZ, at 6 ft"* is a work item they can pick up. If that sentence is
  hard to produce at publish time, tell us — we would rather relax it than have it
  filled with restatements of `kind`.

**Cost to you:** a shape to publish into where you previously had none. This should be
a net reduction in work.

---

## 2 · Planning applies the source policy, not you

**What changed.** v0.3 said *"resolution honours the policy"* without saying whose
resolution. There are two, and they produce different snapshots. We are choosing ours.

| | If you applied it | **If we apply it — chosen** |
|---|---|---|
| Snapshot carries | winners only | every admissible row, **including the ones a policy rejects** |
| A rejected source | never crosses; the value silently does not exist | crosses, and our graph can say *"a spec sheet was inadmissible for a structural parameter"* |
| `source_class` on a row | informational | load-bearing |
| `admitted_by` | a fact about your document | an output of **our** run — where it belongs |

**Why.** Admissibility depends on the *task* a value is being used for, and only the
planner knows the task. Asking you to decide it was asking you to guess ours.

**What we would ask you to check.** This means **more** data crosses the boundary, not
less — you publish rows a policy will reject rather than filtering them. If that is
expensive at your end, or if it conflicts with something in your publishing pipeline, say
so. `admitted_by` comes off your `Provenance`.

---

## 3 · `Member.continuity`, one new authored field

**What changed.** A new field, and it exists because of evidence *you* produced:

> `Standard rails are supplied in 16 foot lengths` … `If bottom rail is 16' long, slide
> rail through second post and then insert post in ground` … `The starting point for
> rails should be staggered from post to post`

```text
Member {
  …
  continuity   per_bay | continuous      default per_bay
}
```

That rail is **one physical object in two bays**, threaded through the intermediate post.
Published as `per_bay` — which is what the model forces today — it is counted twice and
cut to the wrong length.

**Why it is on you rather than derivable.** Nothing in the geometry says whether a rail
runs through or stops. Only the guide says it, and only for some products.

**What we would ask you to check.** Author it only where a document actually states it.
The default is right for almost everything. If the distinction turns out to be more than
binary in your corpus — a rail continuous over *some* posts but not others — tell us
before we build against two values.

---

## 4 · A published `ParameterTable` reads only whole-project facts

**What changed.** This is a **confirmation being made binding**, not a new restriction.
A table's conditions may name site facts — exposure, hurricane zone, jurisdiction, code
edition, material — and other parameters. Never a run, a station, a bay or a panel.

**Why it matters enough to be binding.** It is what lets us expand every table **once,
up front**, before any geometry exists. A table conditioned on a bay could not be
expanded then, because the bay does not exist yet — and the whole ordering story in our
engine depends on parameters being settled before layout starts.

**What we would ask you to check.** We believe this is already true of everything you
publish. If you hold anything that genuinely conditions on a bay-level fact, it is a real
finding and we need it now rather than after we build the ordering rule around it.

---

## What is NOT in this document, and why

Everything else we changed is internal: pipeline phases, the fact-space layering, four
extension seams, registries for closed vocabularies, and the retraction of an entity we
proposed and then found we did not need. None of it changes a shape you publish, so
sending it would spend your review on things you cannot affect.

**Two corrections you already have**, in your repo since v0.3, listed so nothing is
assumed: the rule expansion we published truncated values downward rather than rounding
(fixed — keep publishing thousandths and the lexeme, and do not pre-round), and the
unconditioned fallback row would have won silently by its position in the table (fixed —
publish rows in any order, order carries no meaning).

**And one thing to be plain about.** Of the six defects the second self-audit found,
every one was in something we *added* to your proposal rather than something you asked
for. Accepted items arrived with your evidence attached; our modifications we invented,
and we had asked you to scrutinise them in v0.2 §7.1 without scrutinising them ourselves.
The four items above are the ones that survived that check and touch you.

---

## How to reply

Same standard as before, and it worked twice: a gap per item, with the document and page
that motivates it. Anything that changes tier 1 or tier 2 changes the contract, which is
a negotiation rather than a request.

If all four are fine, **saying so is enough** — we are not asking for another audit. Your
open items in `audit/05-acceptance-open-questions.md` §6 are unblocked either way; the two
early publishes you were holding on B2 and B6 have had their blockers landed since v0.3.
