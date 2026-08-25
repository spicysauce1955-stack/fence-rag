# Disposition of `06-review-of-v0.4.md` — all four

```text
Status:  Decision. From the Planning & BOM team.
Result:  All four accepted, including the one where you say our premise is wrong.
         It is wrong, and the check made it worse than you measured.
Checked: Every claim below was verified against this engine before answering —
         which is how two of your asks turned out cheaper than you thought and
         one of your findings turned out sharper.
```

## At a glance

| | Item | Disposition |
|---|---|---|
| 1 | `Gap` kinds + `closes_by` | **ACCEPTED IN FULL.** One naming collision to settle — §1.1 |
| 2 | `version_status` as a policy axis | **ACCEPTED.** And your `also_filed_as` commitment is taken as relied upon |
| 3 | Reject the binary; publish `stock_length` | **ACCEPTED — and cheaper than you proposed.** The mechanism already exists. One home corrected — §3.2 |
| 4 | Obligation 13's premise is false | **ACCEPTED. You understated it** — height is not per-run, it is per-interval — §4 |

---

## 1 · `Gap` kinds — accepted in full

`conflict{on: value \| conditions}`, `illegible_source` and `closes_by` all go in.

**`closes_by` is the best thing in this review and I should have caught it.** I designed
`would_close` and never asked *who closes it*. Showing a curator *"this closes when
`PanelSpec` gains handedness, swing direction and a fixed leaf"* is showing them work they
cannot do, in a queue whose entire value is that every item is actionable. One enum, and it
changes what the queue is.

**`illegible_source` earns its place on the work-item argument**, not the taxonomy one.
*"Nobody wrote it down"* sends a curator to find another document; *"we could not read what
they wrote"* sends them to open a crop. Different cost, different success rate, and your
own source-refs design already produces exactly what the second one needs.

**33.3% is the number that settles `conflict`.** 108 of 324 gated facts carrying *"readers
did not independently agree on the applicability bracket"* is not an edge case, and you are
right that none of the six fits: the value is certain, the domain has no hole, nothing is
missing and nothing is unquantified. Thank you for disclosing the underscore-prefixed
free-text key rather than leaving us to find it — under §1.3 it would indeed have published
as a condition dimension, which would have been a silent mess.

### 1.1 One naming collision, and it is ours to fix

We already have a `Conflict` — a decision-graph node kind, produced when two rules fire,
tie on authority and disagree **at resolution time**. Yours is a different animal: two
admissible readings disagreeing, known **at publish time**, before any run exists.

Same word, two meanings, and we have been bitten by exactly this once already this round
(we used *"stage"* for both a pipeline step and a knowledge layer, which cost a review
cycle). So: the `Gap` kind is **`disputed`**, with your discriminator unchanged —
`disputed{ on: value | conditions }`. The decision-graph `Conflict` keeps its name.

If `disputed` reads wrong to you, name it — the discriminator and the semantics are yours
and we are only avoiding the homonym.

---

## 2 · `version_status` as a policy axis — accepted

Task, source class and role, and supersession on none of them. You are right, and the
consequence is worse than a missing axis: **once we apply the policy, a superseded NOA and
its replacement are indistinguishable to it** — same class, same role, same task, identical
rank. With 40.7% of your gated facts coming from a superseded document, that is not a
refinement, it is the policy failing on the plurality case.

`version_status: active | superseded | unknown` goes on `Provenance` and becomes a policy
axis. **`unknown` is a real value ranking below `active`, never coerced to it** — with 132
of 144 documents unknown, coercion in either direction would be a fiction, and the honest
ranking is what lets an operator decide how much unknown provenance they will tolerate for
a given task.

**Note this is data we already pin and were not using.** `SourceDoc.version_status` has
been in the snapshot since v0.3 (it is why `belongs_to` exists). Having the data and having
the policy rank on it are different things, and we had the first without the second.

**Your `also_filed_as` commitment is taken as relied upon**, and the 18-of-40 figure is why
it matters now rather than later: the same bytes being admissible or not depending on which
filing crossed is precisely the class of silent defect the policy exists to prevent. This
closes the open question we left in `knowledge-datamodel.md` §7.2.

---

## 3 · Continuity — accepted, and the mechanism already exists

You asked to be told before we built against two values. You were right to, and all three
arguments hold:

- **Colour changes it** — 16 ft for White, 12 ft for Blend, against a 97″ maximum spacing.
  The same member is `continuous` in one colour and `per_bay` in another, and colour is an
  option axis, not a member field.
- **Terrain collapses it** — a rail cut to 95½″ for rolling terrain is one bay. A bay-level
  fact deciding a member-level field, which is item 4 arriving from the other direction, as
  you say.
- **Neither value carries the stagger constraint** — 20 instances across 5 guides, with its
  own figure, stated as a strength requirement rather than a preference. *(Their §3(c) said
  77; corrected to 20 in `08-close-of-round.md` §0. The conclusion is unchanged; the size
  is not.)*

**`continuity` as an authored boolean was me flattening a derived property into a fact** —
the same collapse-a-conditional-into-a-scalar error the first audit taught us about
`max_span_mm`, committed by me two rounds later on a field I invented.

**And it is cheaper than you proposed.** `stock_length_mm` is already a first-class product
capability in this engine — the matcher reads it, and a `supplies` predicate already
compares against it. So *"publish stock length and let your side derive continuity against
the resolved spacing"* lands on a mechanism that exists rather than one we would build.
Publish it as a `Quantity`; `continuity` stays as an authored override for the case where a
guide states it outright and gives no length.

**Confirmed on your parenthetical:** courses are distinct members. A top rail and a bottom
rail are separate `FrameSlot`s with separate requirements, so *"21 ft lengths continuous
thru the line post … bottom rail shall be field cut"* publishes correctly as top-continuous
and bottom-per-bay. Closed.

### 3.2 The stagger constraint needs a different home than you suggested

You pointed at obligation 11's `requires` edge with `exclusive_with`. We think that is the
wrong shelf, and it matters because putting it there would quietly not work.

`requires` orders **assembly steps** — *fit this before that*. Stagger is a constraint on
**where cuts fall**: three rail courses in one bay must not share a joint position. It
survives into the cut plan, and it binds two members that have no ordering relationship at
all.

The right home is where the joints are actually decided, which on our side is cut planning.
So it is a **constraint on the cut plan**, expressed as a rule the same way a spacing limit
is: *joint positions of members sharing a bay must differ by at least X*. That gives it a
number, an authority and a citation, and it fails as a warned line when it cannot be met
rather than silently producing three aligned joints.

**What we need from you** is the constraint, not the mechanism. *(Answered in `08` §2: all
20 are `unquantified` — no document states an offset. The minimum joint offset therefore
becomes a Planning-authored default, declared as ours rather than attributed to a
manufacturer.)*

---

## 4 · Obligation 13 — accepted, and you understated it

> *"This is already true of everything this platform publishes."*

That sentence was mine, it was not checked, and it is false. Worse: I wrote *"we believe
this is already true"* and asked you to confirm — which is asking someone to verify an
assertion I had not verified myself, dressed as a confirmation request.

**And the check makes your first example stronger than you measured.** You say fence height
is per-run — *"6 ft privacy along the back and 4 ft picket at the front"*. In this engine
height is a **`height_intent` interval payload on the topology**, so it varies *along a
single run*, not merely between runs. A run can be 6 ft for twelve metres and 4 ft for the
last four. So the footing grid conditioned on `fence_height: "Up to 48\""` is not just
unpublishable under 13 as drafted — it is conditioned on something finer than the scope I
banned.

**Your restatement is right, and it is the rule I should have written.** What breaks
up-front expansion is a condition naming an **instance** — station 7, bay 3 — because that
instance does not exist yet. A condition naming a **closed enumeration** does not break it:
expand one row per post role, per height bracket, up front, and bind the key when the
station or the bay arrives. Expansion stays whole; only *selection* moves later.

**Obligation 13, restated:**

```text
A published condition key declares its scope:

  condition_scope   site | param | run | post | bay | panel

A table whose keys are all `site` or `param` resolves at snapshot expansion.
Narrower keys expand up front and BIND at their own scope.

BANNED: an instance reference — station 7, bay 3, this run's id.
NOT banned: a narrow scope over a closed enumeration.
```

Five of those six are obligation 12's step scopes exactly, as you asked. **`param` is the
one addition**, and it is not a loosening: it is the scope a table conditioned on another
table's value already has — `max_rack` on `slope_method`, which both sides agreed two
rounds ago. Without it that table has no legal scope to declare.

**This also converges with something on our side**, which is a good sign rather than a
coincidence: our internal resolution layers already order facts by when they become
knowable, and `condition_scope` *is* that layer, published. We will use your five words
rather than our own for the shared ones.

**The fallback you offered is refused, and you were right to argue against it.** One
`ParameterTable` per height bracket per post role is the same data multiplied out with the
conditions no longer legible as conditions — and `uncovered` stops meaning anything, which
is one of the few mechanisms both teams have relied on since round one.

---

## What changes, and where

| | Document |
|---|---|
| `Gap` gains `disputed{on}`, `illegible_source`, `closes_by` | `contract.md` §1.2.1 |
| `Provenance` gains `version_status`; it becomes a policy axis | `contract.md` §1.1, §1.4 |
| `stock_length` published; `continuity` demoted to an override | `contract.md` obl. 14, `knowledge-datamodel.md` §3.3 |
| Stagger published as a cut-plan constraint | `planning-asks.md` |
| Obligation 13 restated around `condition_scope` | `contract.md` obl. 13 |

None is a redesign. Three are additive fields, one is a rewritten obligation, and one
demotes a field I should not have invented.

## One observation about this round

Every item you raised was measured, and two of the four were things we asserted without
measuring — *"already true of everything you publish"* and *"continuity is binary"*. Both
were mine, both were about **our** additions rather than your data, and both would have
been caught by applying our own standard to ourselves before sending.

That is now three rounds where the same asymmetry showed up. It is not a process problem
any more; it is a habit, and the fix is that anything we add to your proposal gets checked
the way we check the things you send us.
