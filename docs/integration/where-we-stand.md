# Where we stand

```text
Status:  The boundary is agreed. Four review rounds, every item raised by either
         side dispositioned, no open disagreement on what crosses.
From:    The Planning & BOM team, closing out v0.4.1.
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

## Two threads still with you — neither blocking

1. **The name `disputed`.** We renamed your `conflict` because we already have a `Conflict`
   at resolution time and did not want a second homonym in one round. The discriminator and
   the semantics are yours; if the word reads wrong, name a better one.
2. **Where the stagger constraint lives.** You put it on obligation 11's `requires` edge;
   we think that shelf orders *assembly steps* while stagger constrains *where cuts fall*,
   and belongs in cut planning. This is the only live disagreement between us, and it
   decides where 77 instances land. `planning-asks.md` §6d has the argument.

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

1. **The cell bounding box** (your K4). Still the single item most likely to decide whether
   a review queue is a bounded task. Above crop cost.
2. **The ten `SOURCE_*` codes** and **the eleven-warning starter list**, with params and
   verbatim exemplars — both need entries in two locale bundles on our side.
3. **The two early publishes**: one `ParameterTable` with a `declared` domain, one
   definition carrying a superseded `contributing_source`. Both blockers landed in v0.3.
4. **`also_filed_as`** — one source class per content hash. We are relying on it now that
   class is load-bearing.

## The one risk worth naming

Your K5 and our N18 are a chain: **cell box → curation level 2 → any structural coverage at
all in a first snapshot.** We ranked installation manuals admissible for structural work
*only* at level 2, and level 2 is currently unreachable by construction, not by backlog —
`reader_kind` is `agent` on all 1,225 readings. If human review is further out than we are
assuming, that ranking is worse than the strict exclusion you originally proposed, and we
would rather revisit it than have it quietly empty the snapshot.

## An honest note on what is not done

The boundary has been audited four times and is in good shape. **The engine has not moved.**
Everything above the line marked "what we do next" is design; none of it is built, and the
two never-block violations are live in code today. The incompleteness has moved entirely to
our side, which is the right place for it — but it has not got smaller.

## The thing worth keeping from all four rounds

Each round checked the design against a different **substance** — your corpus, a second
reader, our codebase, then our own additions — and each found what the previous could not.
After round two the design was internally consistent and our engine could not implement it.

**Coherence was never the test.** And the asymmetry that showed up three rounds running:
what we *added* to your proposal went unchecked, while what you sent was measured. Both of
the v0.4 items you falsified were ours, and both were assertions we had not tested. That is
the habit we are taking away from this.
