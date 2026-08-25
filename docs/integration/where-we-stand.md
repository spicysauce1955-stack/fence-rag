# Where we stand

```text
Status:  Round CLOSED. contract.md frozen at v1.0. Both open threads resolved in
         audit/08 — `disputed` accepted, stagger conceded to cut planning.
         Nothing open, nothing awaiting a decision from either side.
From:    The Planning & BOM team.
Purpose: The one page to read if you pick this up cold — what is settled, what is
         deliberately parked, what each side does next.
```

## Settled

All four v0.4 items are accepted — see [`audit/07-delta-disposition.md`](audit/07-delta-disposition.md)
for the reasoning. In short: `Gap` gained `disputed`, `illegible_source` and `closes_by`;
`version_status` became a source-policy axis; `continuity` was demoted from an authored
boolean to a property we derive from a published `stock_length`; and obligation 13 was
restated around `condition_scope`, banning *instance references* rather than narrow scopes.

`contract.md` is the authority. Eighteen binding obligations, and nothing outside that list
binds.

## Both threads closed

1. **`disputed`** — accepted, no counter-name. One nuance they raised and we are *not*
   turning into a field yet: the two sub-cases have different parties. `on: conditions`
   (108 facts) is their own readers disagreeing and closes by opening a crop;
   `on: value` is two documents disagreeing and may never close. Both are
   `closes_by: knowledge`, so nothing routes wrongly. `between: sources | readings`
   is the cheap addition **when a queue exists to need it** — not on speculation.
2. **Stagger lives in cut planning** — conceded to us, and the quantification came back
   stronger than we assumed: **all 20 instances are `unquantified`.** No document in the
   corpus states an offset. So the minimum joint offset is a **Planning-authored default,
   declared as ours** — never `attributed_to: "manufacturer"`, which is the unfalsifiable
   string `rationale.md` §5 exists to warn about. The requirement is theirs and cited; the
   number is ours and labelled.

## Parked by agreement — named so nothing is silently dropped

| | Why, and what would reopen it |
|---|---|
| **Gates** | Out of scope, not forgotten. The target `GateModel` shape is recorded in `knowledge-datamodel.md` §9.1 so it is not renegotiated later. Publish a gate as a `Gap`; gate *hardware* stays an ordinary `Part`. |
| **`Combination`** | Pinned but inert — nothing in our engine reads one yet. The `certify()` seam is named. Curating them buys nothing today. |
| **Concrete and gravel** | `site_material` reserved and unimplemented. Your `scope: site` and `scope: footing` steps publish and render; they produce no BOM line yet. |
| **Stock length constraining layout** | Publish it anyway — it is true and the follow-on needs it. A 94″ rail does not yet *determine* a 94″ bay. |
| **`soil_class`** | Not bound. It varies along a run, so it belongs in the topology rather than in site conditions. |

## What we do next, in order

1. **`Gap` as a return type.** Two defects in our engine violate our own never-block
   obligation today: an uncovered `max_span` raises rather than warning, and two published
   rows that tie and disagree raise rather than conflicting. The second gets worse every
   time you publish more knowledge. This is also delta item 1, so one change closes both and
   delivers your approval item.
2. Site conditions, `site.*` binding, and the `site_conditions_changed` guard.
3. Registries for the vocabularies we currently branch on.
4. The `ParameterTable` loader — `value_type`, `domain_basis`, validity, token values.
5. The source policy — which has **zero lines of implementation** today, despite being
   binding and despite us re-ranking it twice.

## What we need from you, in order

1. **The cell bounding box** (their K4) — **re-ranked by their data, and they were right
   to push back.** 973 of 18,472 cells carry a box (5.3%); in structural documents it is
   12 of 721 (1.7%). The 0% on pdfplumber tables is cheap to fix and they are doing it —
   but it bounds the *text-layer catalog* queue, not the structural one, because on the
   73 `table_not_reconstructed` pages **there is no cell to draw a box around.** The grid
   was never recovered. For those the review unit is the page crop, which
   `source-refs-design.md` already returns and which they built first. Crop-first was the
   honest ordering and it is already done.
2. **The ten `SOURCE_*` codes** and **the eleven-warning starter list**, with params and
   verbatim exemplars — both need entries in two locale bundles on our side.
3. **The two early publishes**: one `ParameterTable` with a `declared` domain, one
   definition carrying a superseded `contributing_source`. Both blockers landed in v0.3.
4. **`also_filed_as`** — one source class per content hash. We are relying on it now that
   class is load-bearing.

## The risk we named — confirmed, and defused by a decision already taken

Level 2 is unreachable by construction: `reader_kind` is `agent` on all 1,225 readings and
`reviewer` is NULL on every one. Not one human review has happened. (And 504 readings carry
`cross_family_verified`, which sits in their promotion set today — two *agents* agreeing
promotes a fact with no human in the loop. They are revoking it. That is their K1 and it is
the right call.)

**But delta item 2 already took the teeth out of it.** Now that *Planning* applies the
source policy, those rows cross anyway — published at an honest level 1, rejected by our
policy, and **visible in the decision graph as rejected** rather than silently absent. That
is the difference between *"the snapshot is thin"* and *"the snapshot is thin and nobody can
see why."*

So the ranking stands. Expect the first structural snapshot to be thin: 882 facts — 44.6%
of the store — come from installation manuals and none clears level 2 on day one.

## An honest note on what is not done

The boundary has been audited four times and is in good shape. **The engine has not moved.**
Everything above the line marked "what we do next" is design; none of it is built, and the
two never-block violations are live in code today. The incompleteness has moved entirely to
our side, which is the right place for it — but it has not got smaller.

## The thing worth keeping from all four rounds

Each round checked the design against a different **substance** — your corpus, a second
reader, our codebase, then our own additions — and each found what the previous could not.
After round two the design was internally consistent and our engine could not implement it.

**Coherence was never the test.**

We had been calling the second pattern an asymmetry — our additions going unchecked while
their evidence got measured — and their `audit/08` §6 corrected it into something more
useful. It was never carelessness. **An addition made at the boundary has no substance on
either side to check it against** until someone holds it up to one. `continuity` was
checkable in their corpus and nowhere else; obligation 13 was checkable in their corpus and
nowhere else. Both were sound designs against our engine.

So the habit is not *check our own additions harder*. It is: **anything either side invents
at the boundary goes to the other side to be measured before it is written as binding.**
Which is what these four rounds were, and why they worked — and their own miscount, in the
same note that corrected us, is the same failure in the other direction.
