# Disposition of the audit — every item in `05-acceptance-open-questions.md` §1

```text
Status:    Decision. From the Planning & BOM team, in reply to
           01-audit-response.md and 05-acceptance-open-questions.md.
Scope:     N1–N29. Nothing deferred, nothing left to a later round.
Effect:    Items marked ACCEPTED change contract.md and
           knowledge-datamodel.md. Those edits follow this document.
Method:    Every disposition was checked against the engine's actual code,
           not against the proposal documents. Where the code and our own
           datamodel document disagreed, the code won and the document is
           wrong — that happened three times and is marked.
```

## 0. Three things before the list

**The audit is accepted almost in full, and the three items we changed are
changes of *shape*, not of direction.** Twenty-four of twenty-nine are accepted as
written. Three are accepted with a modification we argue below (N2, N18, N25).
Two are answered with a decision you asked for rather than proposed (N22, N29).
Nothing is rejected.

**Two of your findings are worth more than the change they ask for**, and we want
to say so plainly rather than bury them in a table:

- **§3 — the missing source class — is the most important thing either team has
  found.** A policy that silently reclassifies 44.6% of a store's facts into
  inadmissibility is not a gap in a vocabulary; it is a policy that would have
  shipped, produced almost-entirely-warned bills of materials, and been diagnosed
  as an extraction problem. You found it by counting rather than by reading, which
  is the only way it was findable.
- **§2.5's census — 19.9% of warnings sit on a step — falsifies an invariant we
  wrote with confidence.** We wrote invariant 5 from the shape of our own read
  model, where a warning *does* live on a step because a step is the only thing
  there is. You measured the corpus. The corpus wins.

**And one correction to your reading, in your favour.** N5 and N9 both ask for
something the engine already has. `SpecField`'s validator forbids a value only on
`agree = "supplies"`; a manufactured nominal length under a different key has
always been legal, and our datamodel document over-stated the invariant. Post
roles already exist as a closed vocabulary in `strategy/model.py`, and it is
*wider* than the four you asked for. Details in §2.

---

## 1. Dispositions at a glance

### Tier 1 — the shared vocabulary

| # | Item | Disposition |
|---|---|---|
| N1 | `UnitCode` extension | **ACCEPTED IN FULL** — all four: `deg_milli`, `mph_milli`, `pa_milli`, `second_milli` |
| N2 | `ParameterTable` row value admits an enum | **ACCEPTED, MODIFIED** — the *table* declares its value type; rows conform. §3.1 |
| N3 | `Quantity.value_raw` becomes a list | **ACCEPTED** — a list, min length 1, ordered as printed |
| N4 | `shared` / `mfr/<manufacturer>` / `<tenant>` namespaces | **ACCEPTED** — you are right and the tenant axis was a mistake |
| N5 | A part may declare a manufactured nominal length | **ACCEPTED — no schema change needed.** Our invariant was mis-stated. §2.1 |
| N6 | `SourceRef.belongs_to` | **ACCEPTED** — one non-opaque field, the content hash |

### Tier 2 — the published definitions

| # | Item | Disposition |
|---|---|---|
| N7 | `Coverage` becomes an anchored `Span` | **ACCEPTED** — including dropping `Fraction` |
| N8 | `ContainedSlot.relation` vocabulary | **ACCEPTED** — drop `insulates`, add `fills`, `caps`, `retains`; registry-extensible |
| N9 | `PostSlot` role keying | **ACCEPTED — the vocabulary already exists on our side.** §2.2 |
| N10 | `AssemblyStep` scope, kind, slots, requires | **ACCEPTED IN FULL**, and your counter-argument is **rejected**. §2.3 |
| N11 | The warning model — text primary | **ACCEPTED**, plus one rendering rule we owe you. §2.4 |
| N12 | The warning registry splits | **ACCEPTED** — this changes a rule in our own CLAUDE.md |
| N13 | `Procedure` with `scope: EntityRef \| null` | **ACCEPTED** |
| N14 | `contributing_sources` on `Part` / `FenceModel` | **ACCEPTED**; your counter-argument is **rejected**, correctly |
| N15 | `source_class` / `curation_level` on every published value | **ACCEPTED** — the invariant was right, the obligation is being fixed |
| N16 | `Member` edge handedness | **ACCEPTED** — `profile_edges` + `per_end_member_by_edge` |
| N17 | Gates named out of scope | **ACCEPTED**, and named. §2.5 |
| N17a | A `gate.*` predicate namespace | **ACCEPTED as part of the recorded target shape**, not v0.1 |

### Registry additions

| # | Item | Disposition |
|---|---|---|
| N18 | `manufacturer_installation_instruction` | **ACCEPTED, MODIFIED — more permissive than you asked for.** §3.2 |
| N19 | `industry_standard` | **ACCEPTED**, ranked above `spec_sheet`, with a scope caveat. §3.3 |
| N20 | `jurisdiction` condition dimension | **ACCEPTED** — Planning will bind it |
| N21 | `code_edition` condition dimension | **ACCEPTED** — registry route, as you preferred |
| N22 | Validity window | **ACCEPTED, CHOICE MADE** — fields, not an `as_of_date` condition. §3.4 |
| N23 | `SOURCE_*` warning codes | **ACCEPTED** — they are platform codes, both bundles, enforced by our test |

### Clarifications

| # | Item | Disposition |
|---|---|---|
| N24 | A large `unplaced` list is permitted | **CONFIRMED, emphatically.** §2.6 |
| N25 | `uncovered` on an unreadable table | **CONFIRMED, and upgraded to a field.** §3.5 |
| N26 | `retain_until` for source refs | **CONFIRMED** |
| N27 | Source-ref tenancy | **CONFIRMED** |
| N28 | `POST /source-refs:batch` | **ACCEPTED** — our review queue needs it; see §4 |
| N29 | The `us` / `china` tracks | **ANSWERED WITH A DESIGN.** §3.6 |

---

## 2. The accepts that need more than a row

### 2.1 N5 — our invariant was over-stated, and the code always allowed this

You read invariant 2 as written and it says what you quote. The code says less:

```python
# parts/model.py — the ONLY enforcement of "a part cannot declare its length"
if self.agree == "supplies":
    if self.value is not None:
        raise ValueError(f"{self.key}: `supplies` carries no value — a part "
                          "cannot declare its length, the bay resolves it")
```

The rule binds `agree = "supplies"` and nothing else. `supplies` is about a **cut**
length: it compiles to `item.stock_length_mm >= 0`, which asks whether a product
has enough material, not how long the article is. A **manufactured nominal
length** under a different key — `nominal_length_mm`, `==`, `unit="mm"` — has
always been legal, becomes a derived dimension through `is_dimension`, and is
exactly the fact your catalogue pages print.

So: publish `nominal_length_mm` on the part. Nothing changes on either side except
our datamodel document, which is being corrected to say what the code says.

**One thing this does not yet give you, and we are not promising it in v0.1.** You
observed that the rail's length *determines the bay* — a Columbia section is 94″
because the Columbia rail is 94″. Publishing the number does not make the engine
derive a span from it; today `max_span_mm` comes from a rule, and a rail's nominal
length is inert data beside it. Making stock length constrain layout is a Planning
change with real consequences for `fit.py`, and it is on our roadmap rather than in
this round. Publish the number anyway — it is right, and it is what the follow-on
needs.

### 2.2 N9 — the role vocabulary exists, and it is wider than you asked for

`strategy/model.py`:

```python
kind: Literal["end", "corner", "line", "gate", "junction", "transition"]
```

Six roles, not four. `junction` is a station where runs meet; `transition` is a
change of style or height mid-run. Both are places where reinforcement rules
plausibly differ and where your corpus may already say something you have filed as
a corner.

This is a **shared-spine vocabulary and it is ours to own**, so key `ContainedSlot`
conditions against these six strings exactly. Two consequences worth having:

- Your Freedom/Bufftech corner-post contradiction (`not needed in corner posts`
  versus `Corner posts should be reinforced with concrete and rebar`) becomes two
  rows keyed on `corner` under two manufacturers, which is a normal conflict with a
  normal resolution rather than a modelling problem.
- `RequirePostReinforcement(context="gate")` already exists in the rule vocabulary
  (`knowledge/model.py`), so gate-post reinforcement has a working mechanism today
  and is the one gate-adjacent thing not blocked by §2.5 below.

### 2.3 N10 — accepted in full, and we reject your counter-argument

Widen `scope` to `panel | bay | post | run | site`. Widen `kind` with
`preparation`, `part_modification`, `maintenance`. Give `slots` a target union.
Give `requires` an edge kind — `after | not_before | before | exclusive_with`.

Your counter-argument was that everything above the panel could be declared out of
scope, since a gravel-base step produces no BOM line. **We decline it, and it is
worth saying why so this does not get re-opened.** The structure sheet is a
fitter-facing document, not only an input to a price. A sheet that omits the string
line, the 72-hour cure and the utility locate is not a smaller sheet; it is a sheet
a fitter cannot work from, which is the failure our own `report/assembly.py`
docstring already argues against for a different reason. Half of every installation
guide is not a rounding error.

**How we will land it, stated so you can plan against it.** `report/assembly.py`
takes `(model, resolved panel)` and therefore *structurally* cannot place a post —
its own docstring names this as "a deliberate next step rather than an oversight."
Widening it needs the bay's elements as a second input. We will do it in two
phases: `panel | bay | post` first, then `run | site`. Publish all five scopes from
the start; the phase-one read model will report `run` and `site` steps as present
and unrendered rather than dropping them.

Your 16 ft rail threaded through an intermediate post is the case that convinced
us, because it is not merely wide-scoped — it belongs to no bay at all, and it
proves the scope field is a genuine dimension rather than a granularity knob.

### 2.4 N11/N12 — accepted, and here is the rendering rule you are owed

Text primary, `attaches_to` required, `severity_lexeme` unnormalised, `code` and
`params` optional. `CAUTION` and `WARNING` stay distinct — you are right that
collapsing them is a legal judgement neither team should make on a manufacturer's
behalf.

The registry splits exactly as you propose. This changes a standing rule in our own
`CLAUDE.md` — *"a new code needs `warning.<code>` entries in BOTH locale bundles"*,
enforced by `tests/web/test_locale_bundles.py`. That rule now binds **platform
codes only**. Source warnings are verbatim, `lang`-tagged, exempt from the test, and
rendered untranslated. Your argument settles it: translating a manufacturer's
liability sentence and publishing it as theirs is manufacturing a claim, and the
zero-Hebrew measurement means the alternative is not "harder" but "fabricated".

**What we owe you in return is a rendering rule, because `attaches_to.kind` is
useless to you without knowing what we do with each value.** A document-scoped
warning shown on every BOM line is noise that trains a reader to ignore warnings —
which is worse than not showing it:

| `attaches_to.kind` | Where Planning renders it |
|---|---|
| `step` | on that step in the structure sheet |
| `procedure` | at the head of that procedure |
| `product`, `model` | on the BOM lines using it, once per line group |
| `document`, `warranty`, `maintenance` | in the plan's **annexe**, once, never on a line |

So the 83 instances of the freeze-thaw footer become one annexe entry, and your
refusal to attribute it to step 10 costs nothing. Attach it to `document` and it
lands correctly.

### 2.5 N17 — gates are out of scope for v0.1, and here is the naming you asked for

Agreed, and stated as bindingly as we can: **`FenceModel` and `PanelSpec` do not
model gates. A gate filed as a `FenceModel` is a defect, not an approximation.**
Publish a gate as a `Gap` with `kind = "unmodellable_entity"`, and it will surface
in Planning as a named hole rather than as a panel that happens to be missing its
hardware.

Your `GateModel` sketch is recorded as **the agreed target shape**, not as a
proposal awaiting a verdict — so when it comes into scope it is not renegotiated.
The four things you identified as unrepresentable by the `FenceModel`-with-an-axis
workaround — handedness, swing direction, the fixed leaf, and hinge selection by
leaf weight — are the four we consider decisive, and three of them are
pool-barrier-safety relevant, which is the argument that closes it.

We accept the honesty of our own position here: gates are also missing from the
**engine**, not only from the contract. This is a product gap on both sides, and
naming it as out of scope is a way of not losing the data, not a way of pretending
the hole is small.

### 2.6 N24 — confirmed, and please do not do the other thing

Read *"or reported `unplaced`"* exactly as you did. A large `unplaced` list is the
correct output. Our own read model says so in its docstring: `unplaced` exists
because "a model that describes how it goes together while quietly leaving out half
its parts is worse than one that says nothing."

Bufftech leaving 3 of ~11 members unplaced, with the line-post stiffener and the
gravel fill appearing only in a figure caption, is a **true fact about the
document** and we want it. A curator inventing a placement to turn a check green
converts a visible gap into an invisible error, which is the failure mode the whole
never-block invariant exists to prevent.

---

## 3. The five where we changed the shape, or made a choice

### 3.1 N2 — the table declares its value type, not the row

Your ask is right and the form invites a type error. If any row's value may be a
`Quantity` **or** an enum member, then one table can hold `10000 deg_milli` and
`not_rackable` in the same column, and every consumer must branch on the type of
every cell.

`not_rackable` is not an angle. It is a different parameter:

```text
ParameterTable {
  parameter    "slope_method"
  value_type   token { rackable | stepped_only | not_rackable }
  ...
}

ParameterTable {
  parameter    "max_rack"
  value_type   quantity(deg_milli)
  domain       ... conditioned on height AND on slope_method = rackable
}
```

**ACCEPTED, MODIFIED:** `ParameterTable` gains `value_type`, either
`quantity(<UnitCode>)` or `token(<closed set>)`, declared once per table; every row
conforms and the publish check enforces it. This gives you everything you asked for
— `stepped_only`, `not_rackable`, `gates are not rackable` all have a home — and
costs you one field.

It also improves the Bufftech cell you quoted. `▼ Racks up to 10 degrees 3' and 4'
high, 5 degrees 5' and 6' high` becomes two rows of one `max_rack` table
conditioned on height, and the Even Stephen / Simple Simon prohibition becomes a
row of `slope_method`, rather than both being crammed into one column with
different types.

### 3.2 N18 — accepted, and ranked more permissively than you asked for

You proposed `manufacturer_installation_instruction` admissible for nothing
structural, on the argument that visible exclusion beats silent mis-filing. We
agree with the argument and think the ranking is too strict, for a reason your own
numbers give:

231 of 601 dimensional structural facts sit in an admissible class, **and none of
them is at curation level 2**, because `reader_kind` is `agent` for all 1,225
readings. Under your proposed ranking, the admissible set at the required bar is
**empty**, and stays empty until human review exists. A first snapshot then carries
no structural parameter at all, every span falls back to the engine's hardcoded
1800 mm — the constant `rationale.md` §5 spends a section proving is wrong in both
directions — and the warning that fires says "uncovered condition" rather than "we
hold this and cannot use it."

**ACCEPTED, MODIFIED:**

| Task | Sealed approval | Tested report | **Industry standard** | **Install instruction** | Spec sheet | Marketing |
|---|---|---|---|---|---|---|
| Structural parameter | 1st, L2 | 2nd, L2 | **3rd, L2** | **4th, L2** | inadmissible | inadmissible |
| Component dimension | 1st | 2nd | **3rd** | **3rd** | 4th | inadmissible |
| Installation step | 2nd | — | 3rd | **1st** | 2nd | 4th |
| Product description | ok | — | ok | ok | ok | 1st |

An install-guide footing depth may back a structural parameter, ranked below both
sealed sources, **and only at curation level 2** — a person checked it against the
page. The source class is weaker, so the curation bar carries the weight instead of
the admissibility flag.

The trade is deliberate: it makes level 2 the thing worth building, which is
currently unreachable *by construction* rather than by backlog (your K5). We would
rather the bottleneck be one you have already decided to fix than one that silently
empties the snapshot.

Note this makes install instructions **1st** for installation steps, which they
plainly are — a spec sheet ranked above an installation manual for how to install
something was a defect in the shipped default, and your §3 is what exposed it.

### 3.3 N19 — accepted, above `spec_sheet`, with a scope caveat

`industry_standard` outranks a manufacturer's spec sheet. That is right in
engineering practice and your CLFMI post-embedment example demonstrates it.

**The caveat, which is a curation instruction rather than a schema change.** Your
own evidence contains the hazard: the CLFMI bulletin is about **chain link** and is
nonetheless the most authoritative embedment statement in the corpus. Applied to a
vinyl fence it is a *scope* error, and no ranking catches a scope error — a
higher-ranked wrong-scope source beats a lower-ranked right-scope one and wins
silently.

So a row backed by `industry_standard` must carry its applicability on the
condition side (`material`, `system_type` — tell us what you need and we will bind
it) or be published as a gap. Authority and applicability are different axes, and
this is the one place where raising a class's rank makes a scope error *more*
dangerous rather than less.

### 3.4 N22 — fields, not an `as_of_date` condition

You offered both and said you would accept either. We choose **fields**:
`valid_from`, `valid_until`, `authority` on `Combination` and on
`ParameterTable.rows[]`.

The reason is `uncovered`. Modelling expiry as a condition dimension means every
table must declare a time domain, and then `uncovered` — which is one of the
mechanisms we most rely on — reports every unenumerated date as a coverage hole.
That drowns the signal that `uncovered` exists to carry. Expiry is also not a
property of the *site* the way exposure and jurisdiction are; it is a property of
the *authority*, and it belongs beside the authority.

Planning warns on a line whose backing authority has lapsed relative to the run
date, in the same family as an uncovered condition and a below-bar curation level.

### 3.5 N25 — confirmed, and it needs a field rather than a convention

You are right that a declared domain on one of the 73 unreadable pages must not
read as a measured one. Confirming it in prose is not enough, because the consumer
of that distinction is a warning renderer, not a reader.

**`ParameterTable.domain` gains `basis: measured | declared`.** `declared` means
"we asserted the shape of this space; we did not read it off the page." Planning
renders an `uncovered` hit against a `declared` domain differently from one against
a `measured` domain — the first says *we may not know the table's real extent*, the
second says *the table really does not cover this point*. Those are different facts
and a planner needs the difference.

### 3.6 N29 — the `us` / `china` tracks

Raised as a question; here is a design.

**A snapshot serves exactly one standards regime, and declares it.** `Snapshot`
gains `regime: str` — `us_astm`, `cn_gb` — as declared metadata inside the hashed
object. A project declares its regime, and Planning **refuses** to generate against
a snapshot whose regime does not match, with a typed 409 in the same family as
`topology_changed` and the `site_conditions_changed` guard we are adding this
round.

Why not a condition dimension: a regime is not a value a rule conditions on, it is
the *frame the whole rule set is written in*. GB and ASTM do not merely disagree
about a number; they disagree about what the conditions mean, which is the same
class of problem your §2.8.3 found between ASCE 7-10 and 7-16 one level down. A
condition dimension would let a GB row and an ASTM row coexist in one table and be
selected between, which is exactly the silent wrong answer we should refuse.

Why not tenancy: a single tenant may operate in both. Regime and tenant are
orthogonal, and collapsing them would be the same mistake as N4's tenant-namespaced
part types — which you correctly caught.

---

## 4. What changes on our side, and in what order

| # | Work | Driven by |
|---|---|---|
| 1 | `SiteConditions` on `Project`; `site.*` in the evaluation context; `site_revision` on `GenerationRun` with a `site_conditions_changed` 409; two warning codes in both bundles | already planned; N20/N21 add `jurisdiction` and `code_edition` as keys |
| 2 | Contract and datamodel edits for every ACCEPTED item above | this document |
| 3 | Correct invariant 2's wording; correct obligation §3.1.6 to match invariant §6.8 (N15) | N5, N15 |
| 4 | `ParameterTable` loader: `value_type`, `domain.basis`, validity fields | N2, N22, N25 |
| 5 | Warning model: platform/source registry split; `tests/web/test_locale_bundles.py` scoped to platform codes; annexe rendering for document-scoped warnings | N11, N12 |
| 6 | `report/assembly.py` phase one — bay and post scopes, `requires` edges as a partial order | N10 |
| 7 | Frontend: evidence viewer against `fixtures/source-ref-examples.json`, including the three records with no quote and the one with no document | your §4 |
| 8 | `report/assembly.py` phase two — run and site scopes | N10 |

Items 1–3 are not blocked by anything. Item 7 is not blocked by anything either,
and is the thing that will tell you fastest whether `source-refs-design.md` returns
what a reviewer actually needs.

**On your K4 — no cell bounding box on any of the 1,225 readings.** This is the
first thing our review queue will hit, and it is worth prioritising above crop
performance (your K3). A reviewer shown a crop and told "check the value" without
the cell outlined does not do a bounded task; they do an unbounded one, and the
throughput argument in `frontend-design.md` §0 collapses. The crop is necessary;
the cell box is what makes the review binary.

**On your K2 — poppler over Pillow.** Agreed without reservation. A crop path that
depends on an optional, git-ignored package and returns `False` when it is absent
is a correctness problem wearing a performance problem's clothes.

---

## 5. What is unblocked for you now

Everything you listed as waiting. Specifically:

- **`ParameterTable` rows** — shape settled by N2, N15, N18, N21, N22, N25.
- **Warnings** — shape settled by N11, N12, N23, and the rendering table in §2.4.
- **Snapshots** — settled by N4, N6, N14, N29.
- **Part and model definitions** — settled by N5, N7, N8, N9, N16, and the gate
  exclusion in §2.5.

Two things we would ask you to publish early even though they are small, because
they exercise the parts of the contract nobody has tested against real data:

1. **One `ParameterTable` with a `declared` domain**, from one of the 73 unreadable
   pages, with its `uncovered` list. It is the first thing that will tell us whether
   the never-block invariant behaves the way both documents claim.
2. **One definition with `contributing_sources` carrying a superseded document.**
   The Chesterfield trace is the obvious candidate. If a pinned run cannot warn on
   a lapsed authority from inside the snapshot, we would rather find that out on
   one definition than on four hundred.

---

## 6. On the two documents themselves

The standard the audit was held to — a document path, a page and a verbatim quote
for every claim, and *"searched X, Y, Z and the corpus does not say"* recorded as a
finding rather than left silent — is the reason twenty-four items could be accepted
without a second round. Several of the findings are ones no amount of reading the
schema would have produced: the 19.9% figure, the 40.7% superseded-citation rate,
the 61.6% inadmissibility split, and the two width readings of item J on one sealed
sheet.

The last of those is worth repeating back, because it is the sharpest thing in the
response and it is not a modelling problem at all: *"A curator who reads the drawing
and sets `gap_after_mm = 0` builds a panel 5% too wide. A curator who reads the
catalogue and sets `gap_after_mm = 0` is right. Both validate clean."* No schema
change closes that. It is an argument for the review queue, and it belongs in front
of whoever is deciding how much that queue is worth.
