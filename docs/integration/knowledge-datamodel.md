# Knowledge data model v0.2 — entities, relationships, invariants

```text
Status:     v0.4. Revised after 03-review-of-v0.2.md (six defects, all fixed) and
            then after Planning audited this design against its own engine and its
            own additions. Four items in v0.4 need this team's agreement — they are
            collected in boundary-delta-v0.4.md; everything else changed on the
            Planning side only.
Supersedes: knowledge-datamodel.md (v0.1). That document is kept for the audit
            trail; where the two disagree, this one is current.
Driven by:  01-audit-response.md — every change below traces to a finding in
            it, and §8 is the map. Nothing here was changed on taste.
Authority:  §2 and §3 are binding (they cross the boundary). §4 is a sketch of
            your internals and binds nothing.
Reads with: contract.md (the promises), 02-audit-disposition.md (the
            reasoning behind each decision), planning-asks.md (what we need
            from you, and when).
```

---

## 0. How to review this

The first round asked *"is this coherent?"* and got back *"here is what the corpus
actually contains."* That was the right answer and it changed seven of ten
sections. This round asks a narrower question:

> **Do the changes in §2 and §3 close the gaps you found — and is anything still
> missing that you now know is there?**

Three things worth knowing before you start.

**The bar for "closed" is that you could author the real instance.** Not that the
type looks adequate. Take the specific artefact you cited — the `92` steel channel
in the `94.5` rail, the `POST LENGHT-(DEPTH+7)` cell, the freeze-thaw footnote at
the foot of fourteen pages, the U-channel handedness sentence — and check that
this model has somewhere to put it, without a curator inventing a value the source
does not state. §8 lists the twenty-nine items and the artefact each one has to
carry.

**Five changes are ours rather than yours**, and they are the ones most likely to
be wrong. Where we modified a proposal instead of accepting it — N2, N18, N22,
N25, N29 — you have not seen the result before, and our reasoning is ours alone.
They are flagged inline with <b>MODIFIED</b> and collected in §7.1.

**We are not asking you to re-audit what did not change.** Sections carrying no
change marker are v0.1 text that survived your first pass. Skim them.

---

## 1. The three tiers

Unchanged from v0.1. The tier decides who may change a thing.

| Tier | What | Schema owned by | Instances authored by |
|---|---|---|---|
| **1 · Shared vocabulary** | The words both sides use | Planning, negotiated | both |
| **2 · Definitions** | Parts and panels, in identical types | Planning | you, for manufacturer things |
| **3 · Private** | Evidence there, commerce here | each side its own | each side its own |

The placement test: *would this be the same answer on a different project, for a
different company?* Yes and yes → tier 2. Yes but only for one company → private.
Neither → private.

**Why Planning owns the schemas that cross.** These types exist because that
engine computes with them — a frame slot carries an engagement depth because the
cut length needs one. A field you invented that Planning cannot consume would be a
field nothing reads. The corollary is a real constraint on us: we cannot change a
shared type unilaterally, because you will have authored instances against it.
This document is that constraint being honoured.

---

## 2. Tier 1 — the shared vocabulary

### 2.1 PartType

```text
PartType {
  key          "rail" | "post" | "slat" | "screw" | "rebar_separator_clip" | …
  namespace    "shared"              Planning only — the negotiated spine
             | "mfr/<manufacturer>"  you, global, tenant-agnostic       ← CHANGED
             | "<tenant>"            a company's own
  parent       PartTypeRef | null    a new kind inherits BEHAVIOUR by sitting in
                                     the same kind of place, not by a per-type rule
  label_i18n   { en, he, … }
}
```

**What changed and why (N4).** v0.1 said extension ids are tenant-namespaced. You
pointed out the axis is wrong: a part type gets invented because a
*manufacturer's* manual describes one — a U-channel, a transition bracket, a
rebar separator clip — and manufacturers are not tenants. A snapshot is per-tenant
and must contain nothing belonging to another, so under the old rule a
manufacturer-derived type had to be either duplicated into every tenant namespace
that stocks that manufacturer, or smuggled into the shared spine that only
Planning may extend. Neither was right.

The parent chain rule is unchanged and still terminates in the spine. The spine to
start: `post`, `post_cap`, `rail`, `bar`, `infill`, `reinforcement`, `bracket`,
`fastener`, `anchor`, `gate_hardware`, plus `site_material` reserved.

### 2.2 SpecField

```text
SpecField {
  key    "width_mm" | "nominal_length_mm" | "colour" | …
  agree  == | != | <= | >= | in | supplies
  value  38 | null
  unit   "mm" | null
}
```

Unchanged. Three things that matter when you publish one:

- It reads left to right as a sentence about the item: `item.<key> <agree> <value>`.
  One direction always.
- **`agree = supplies` carries no value.** That rule is about a **cut** length, and
  it compiles to `item.stock_length_mm >= 0` — a question about whether a product
  has enough material, not about how long the article is.
- Dimensions are **derived** from spec fields, never stored beside them. Do not
  publish a `dimensions` map; it would be a second authority over the same number.

**On N5 — publish the manufactured length.** You asked to relax invariant 2 because
rails here are manufactured at fixed nominal lengths per style (72″, 94″, 96″) and
every catalogue prints them. Reading the engine settled it in your favour with no
schema change: the validator only ever rejected a *value on the `supplies` field*.
A manufactured nominal length under a different key — `nominal_length_mm`, `==`,
`unit="mm"` — has always been legal and becomes a derived dimension. The invariant
was over-stated in prose, not in code, and §6 restates it.

### 2.3 Quantity, and the unit vocabulary

```text
Quantity {
  amount_milli  int
  unit          UnitCode
  value_raw     [str]        A LIST, in printed order                  ← CHANGED
}

UnitCode  mm | mm2 | mm3 | each | gram_milli | cent
        | deg_milli | mph_milli | pa_milli | second_milli              ← CHANGED
```

**N1 — four units added.** All four you asked for, not a subset. `deg_milli`
because racking is a value a planner needs arithmetically and the corpus states it
in six mutually unconvertible forms. `second_milli` because a cure time is a
duration a scheduler needs. `mph_milli` and `pa_milli` because wind speed is the
second-largest numeric fact type you hold and the *design basis* of every
structural table — and a condition enum cannot be compared, bracketed or
converted. The integers-only rule is untouched: 115 mph is `115000 mph_milli`, 10°
is `10000 deg_milli`.

**We are not asking you to normalise units.** Your counter-argument — that
converting `1 inch per foot` to 4.76° is an `atan` performed on a value nobody
stated, producing a number whose `SourceRef` points at a page that does not
contain it — is correct and we adopt it. Publish the form the document uses.

**N3 — `value_raw` is a list.** Because sources state two units themselves and
contradict themselves doing it: `Height: 66 inch (16766 mm)` and `Rail Section:
8 foot (2436 mm)` in one CSI masterspec. One lexeme field would either discard the
document's own contradiction or store an unparseable string. Ordered as printed;
minimum length one.

### 2.3.1 Every dimension crossing the boundary is a `Quantity` — B3

**v0.2 wrote a binding rule and then broke it twenty-three times.** Contract §1.1
says integers in thousandths with the lexeme alongside, *because a float arriving at
the boundary would be rounded somewhere undeclared*. Twenty-three field names in the
v0.2 draft ended in `_mm`, held whole millimetres, and carried no lexeme. Your review
is right, and the arithmetic you used to prove it is the arithmetic that settled Q1:

> Thirteen T&G boards at 7″ fill a 91⅛″ opening. True: 13 × 177.8 = 2311.4 mm against
> 2314.575 — **3.175 mm of slack, which is ⅛″**. At whole millimetres: 13 × 178 =
> 2314 — **0.575 mm**. The convention eats 82% of the clearance, silently.

Nothing in this corpus is a whole number of millimetres. `7/8"` is 22.225 mm.

**Every dimensional field named `*_mm` in v0.2 is now a `Quantity`.** No exceptions,
no "small enough not to matter" — that judgement is what produced the twenty-three.

**One thing we must be straight with you about, because it is ours and it is not
fixed by this edit.** Planning stores **integer millimetres at rest** (ADR-0002).
So the boundary now carries 22225 and the engine rounds once, and the rounding is
declared and inspectable instead of being distributed across twenty-three field
definitions.

**Correction, and it is ours.** v0.2.1 of this section claimed the engine "rounds
once, in `adapt.py`". We then audited the engine against this design rather than
against the documents, and that claim was false in two ways. There was no rounding
in `adapt.py`; the conversion happened inside the rule expansion we published as
reference — and it used **floor division**, not rounding:

```python
value=row.value.amount_milli // 1000      # 177800 → 177, never 178
```

Sub-millimetre, and it is not harmless, because the value passes through a
ceiling. Your `97" / Exposure B` row is 2463.8 mm — floored **2463**, rounded
**2464** — and `n = ceil(run_length / max_span)`:

| Run | posts at 2463 | posts at 2464 |
|---|---|---|
| 9 855 mm | **6** | 5 |
| 12 320 mm | **7** | 6 |

**One millimetre of truncation buys an extra post**, with its footing and its
concrete, on two of three sample runs — systematically in the expensive direction.
Fixed: `round()`, at one named point.

**And the deeper half, which this audit is what surfaced.** Rounding a limit and
*then* multiplying it is the same accumulation you measured, one layer up. So the
rule is not only about the infill fitter: **count-producing arithmetic consumes
thousandths and rounds only its outputs**, in the layout as well as the fit. A
`SetParam` now carries the exact `value_milli` beside the millimetre value and the
layout reads the exact one. Nothing is *stored* in thousandths, so our two-tolerance
rule stands unamended.

Rounding a **pitch** and then multiplying it by thirteen was the case you found;
rounding a **span limit** and then dividing a run by it is the same defect, and we
had it in the code we handed you.

So two things follow, and only the first is in this round:

1. **The fitting arithmetic consumes thousandths and rounds only its outputs.**
   `fit.py` takes the micron pitch, computes positions and residual in thousandths,
   and rounds the positions it emits. Storage stays integer mm; *transient*
   arithmetic moves from float to thousandths. ADR-0002 says "float only transient" —
   this keeps the letter and fixes the accumulation.
2. **Anywhere else a rounded value is multiplied, we do not yet have an answer.**
   We would rather name that than let you discover it. `adapt.py` will emit
   `warning.rounding_accumulates` when it rounds a value whose field is marked as a
   repeat dimension and the residual over the declared repeat count exceeds
   `NUMERIC_TOLERANCE_MM` (1 mm). Where that fires, the number is visibly suspect
   rather than quietly wrong.

**What we ask of you:** publish the thousandths and the lexeme. Do not pre-round to
millimetres to be helpful — `22225` and `"7/8\""` together let us show a curator the
document's own words beside our arithmetic, which is the entire point of invariant 7.

### 2.4 Provenance — new, and it rides on every published value

```text
Provenance {                                                            ← NEW
  cites           [SourceRef]
  source_class    SourceClass
  curation_level  0 | 1 | 2
  admitted_by     { policy_version, rank }    which source-policy row won
}
```

**N15.** v0.1 put `source_class` and `curation_level` on `ParameterTable` rows and
nowhere else, while invariant 8 said "every published value." You were right that
the invariant is the one to keep: a Chesterfield rail length is `derived`,
marketing-grade OCR, or PE-sealed depending on which of the eleven documents it
came from — exactly the same admissibility problem as a parameter row.

`Provenance` is a fragment, not an entity. It attaches to a `SpecField` inside a
published `Part`, to a `ParameterTable` row, to a `Member`'s dimensions, and to
anything else that carries a number read off a page.

### 2.5 SourceRef and SourceDoc

```text
SourceRef {
  id           opaque to Planning; you own everything behind it
  belongs_to   content_hash → SourceDoc     the ONE non-opaque field   ← CHANGED
}

SourceDoc {                                                             ← NEW
  content_hash
  source_class
  version_status         active | superseded | unknown
  version_status_basis   how you know — "named as previous by NOA-24-0117.05"
  issue_date · expiration_date · superseded_by
  also_filed_as   [{ manufacturer, doc_type, source_path }]   optional      ← NEW
}
```

**N6 and N14, and this is the change with the most reach.** Your argument decided
it and is worth restating so it does not get re-opened: a `SourceRef` is opaque and
resolvable only on the discovery surface, which contract §3.2.2 forbids Planning
from calling during a run. So an opaque id carries **zero admissibility bits into
the snapshot**. A run holding a definition whose five citations include three
superseded approvals cannot tell, from inside the pinned object, that anything is
wrong. The information exists and sits on the wrong side of a boundary the contract
deliberately draws. With 40.7% of promoted facts already citing a superseded
document, that is not a hypothetical.

**The mechanism is snapshot-level, and v0.2 got this half-right — B2.** Putting
`contributing_sources` on `Part` and `FenceModel` alone left every other cite-bearing
type with nowhere to join: `ParameterTable` rows, `Warning.cites`,
`Procedure.cites`, `AssemblyStep.cites`, `Combination.cites`. And your review found
the sharp edge — **promoted facts become `ParameterTable` rows**, so the very
measurement that motivated N6 and N14 (132 of 324, 40.7%) lands entirely in the one
type that could not express it.

So the join is uniform and lives on the snapshot:

```text
Snapshot.source_docs [SourceDoc]        the authority, keyed by content_hash
  ↑
Provenance.cites[j].belongs_to          every cite-bearing value joins here
  ↑
Part.contributing_sources               a convenience ROLL-UP, not the mechanism
FenceModel.contributing_sources         — the set of docs behind one definition
```

`contributing_sources` stays, because *"which documents is this definition built
from"* is a question a reviewer asks directly and should not have to compute. But it
is derived from the same `source_docs`, and it is not what makes the join work.

**And one closure rule, which v0.2 was missing entirely.** Nothing required that a
`SourceRef` cited inside a snapshot has a matching `SourceDoc` in it — and invariant
8's *resolvable* is a discovery-surface property, exactly the property §2.5 spends
three paragraphs arguing is worthless inside a run. A dangling `belongs_to`
reproduces the original defect with extra fields. Invariant 12, §6.

**Your counter-argument, answered.** You noted this duplicates into the snapshot
what discovery already serves, and that every duplicate is a second authority.
It is not a second authority; it is a **pinned copy**, which is what the entire
snapshot design is — Planning already pins parameter rows rather than querying
them, for the identical reason.

**One thing this does not solve, and you found it.** One SHA-256 filed four times
under four manufacturers with four `doc_type`s means the same bytes map to four
`source_class` values. `belongs_to` names one of them. Resolving those fourteen
`same_content_as` groups is a curation decision, not a schema one, and it is on
your list (§8, N-obs-1).

### 2.6 SourceClass, and the source policy

```text
SourceClass  sealed_approval
           | tested_report
           | industry_standard                        ← NEW (N19)
           | manufacturer_installation_instruction    ← NEW (N18)
           | spec_sheet
           | marketing
           | company_authored
           | ai_proposal
```

The shipped default policy, revised:

| Task | Sealed approval | Tested report | Industry standard | Install instruction | Spec sheet | Company-authored | Marketing | AI proposal |
|---|---|---|---|---|---|---|---|---|
| Structural parameter | 1, L2 | 2, L2 | **3, L2** | **4, L2** | — | — | — | proposal only |
| Component dimension | 1 | 2 | **3** | **4** | 5 | 6 | — | proposal only |
| Installation step | 3 | — | 4 | **1** | 5 | 2 | 6 | proposal only |
| Product description | 4 | — | 5 | 3 | 2 | 6 | 1 | proposal only |

**Ranks are now unique within a row — B4.** v0.2 tied three times, and `rank` is
*"lower wins"* with no tie-break defined anywhere, which collides with two BINDING
promises at once: resolution recording `admitted_by`, and a hash resolving to the
same bytes. Two implementations could honour the policy and disagree.

Worth separating, because it matters for how it got there: the 3rd/3rd tie came from
the disposition, but **the two `company_authored` ties were introduced in v0.2 and
were never accepted by anyone** — the disposition's table has no `company_authored`
column at all. That was a transcription error on our side, not a decision. `—` is
inadmissible; `ai_proposal` is now shown rather than dropped with no note.

A tie-break rule is still defined, because an operator editing rows will make one:
**higher `curation_level`, then later `issue_date`, then lexicographic
`source_class`.** Deterministic, and it never silently prefers an older document.

**N18 — MODIFIED, and more permissive than you asked for.** You proposed
`manufacturer_installation_instruction` admissible for nothing structural, arguing
that visible exclusion beats silent mis-filing. We agree with the argument and
think the ranking is too strict, for a reason your own numbers give: 231 of 601
dimensional structural facts sit in an admissible class, **and not one of them is
at curation level 2**, because `reader_kind` is `agent` for all 1,225 readings.
Under the strict ranking the admissible set at the required bar is *empty*, and
stays empty until human review exists. A first snapshot then carries no structural
parameter at all, every span falls back to the engine's hardcoded 1800 mm — the
constant `rationale.md` §5 proves is wrong in both directions — and the warning
that fires says "uncovered condition" rather than "we hold this and may not use
it."

So: admissible at rank 4, and **only at curation level 2**. The weaker source class
carries a higher curation bar instead of an inadmissibility flag. The trade is
deliberate — it makes level 2 the thing worth building, which is currently
unreachable *by construction* rather than by backlog. We would rather the
bottleneck be one you have already decided to fix.

Note this also makes install instructions **1st for installation steps**. A spec
sheet outranking an installation manual on how to install something was a defect in
the shipped default, and your §3 is what exposed it.

**N19 — accepted, and the caveat was not a caveat.** v0.2 called the chain-link
hazard *"a curation instruction rather than a schema change"* and asked which
dimensions you needed. Your measurement settles it and reclassifies it:

> Of the facts in this corpus that would carry `industry_standard`, **42 of 43 come
> from the two CLFMI chain-link documents.** The vinyl industry-standard documents —
> the ARCAT masterspec, the ASTM compilations, the Wheatland SpecCheck — yield zero
> facts between them under current extraction.

So the class just promoted above manufacturer spec sheets is, in actual population,
**97.7% wrong-material**. Ship the ranking without a bound `material` and the modal
`industry_standard` row is a chain-link embedment figure outranking a vinyl
manufacturer's own spec sheet, silently — which is not a caveat, it is the default
behaviour.

**`material` is bound (§2.7), and the `industry_standard` ranking does not ship
before it.** Values from your corpus: `vinyl_pvc`, `chain_link`, `wood`,
`composite`, `aluminium`. We take your answer on `system_type` too — one dimension
you can populate beats two you cannot, and if a second is ever needed the registry
takes it without a negotiation.

**A row backed by `industry_standard` and carrying no `material` is refused at
publish**, not warned. This is the one place we make an unconditioned row a hard
error rather than a fallback under §3.8.1, and the reason is the measurement above:
the fallback reading of "no material stated" would be "applies to every material",
which is true of one document in this corpus and false for the other two.

### 2.7 Condition dimensions

What a value may be conditioned on. Planning declares what it can bind; this list
is the current set.

| Dimension | Values | Status |
|---|---|---|
| `exposure_category` | B · C · D | binding this round |
| `hvhz` | true · false | binding this round |
| `fence_height_mm` | numeric | binding this round |
| `frost_depth_mm` | numeric | binding this round |
| `jurisdiction` | free string | **NEW (N20)** |
| `code_edition` | `ASCE 7-10` · `ASCE 7-16` · … | **NEW (N21)** |
| `material` | `vinyl_pvc` · `chain_link` · `wood` · `composite` · `aluminium` | **NEW — blocks the `industry_standard` ranking (§2.6)** |
| `slope_method` | `rackable` · `stepped_only` · `not_rackable` | **NEW** — a parameter that other tables condition on |
| *option axes* | per `FenceModel.option_axes` | **NEW** — bound from the chosen variant |
| `soil_class` | — | not yet bound; varies along a run, so it belongs in the topology |

**The last two close a hole you found in v0.2's own text**: `max_rack` was described
as conditioned on height *and on option axes*, and on `slope_method`, and §2.7 listed
neither as bindable. A parameter conditioned on something the engine cannot bind
resolves to nothing on every run.

`slope_method` is the first case of a table conditioning on **another table's
value**. Resolution is ordered: token-valued tables with no parameter dependencies
resolve first, then tables that condition on them. A cycle is a publish error. We do
not expect a second level of this and would rather find out now if you do.

**N20.** Approvals state validity *"to be used in Miami Dade County and other areas
where allowed by the Authority Having Jurisdiction"*, and one manufacturer has no
statewide Florida approval at all. Bound.

**N21.** One manufacturer's two wind tables are computed under `ASCE 7-10` and
`ASCE 7-16`, which define exposure categories and gust factors differently — so
`exposure_category: "C"` is not the same condition under each, and under
`hit_policy = unique` those rows collide and fail the publish check for the wrong
reason. Bound, via the registry route you preferred.

**Not a condition dimension: the standards regime.** See §3.9.

### 2.8 The rest of tier 1

```text
EntityRef    { kind, id, tenant }
VersionRef   { object_id, version, content_hash }
Authorship   third_party_authored | manufacturer_approved | manufacturer_uploaded
PostRole     end | corner | line | gate | junction | transition          ← EXPOSED
```

**`PostRole` is not new; it was not previously exposed.** It already exists as a
closed vocabulary in the engine, and it is *wider* than the four you asked for in
N9. `junction` is a station where runs meet; `transition` is a change of style or
height mid-run. Both are places where reinforcement rules plausibly differ, and
you may already have filed something as a corner that is one of these.

**On `Authorship` (your Q9.3).** You are right that everything this platform
publishes is `third_party_authored` and the other two values are unreachable from
your side. They stay for a tenant uploading their own document. Noted so the flag
is not read as more meaningful than it is.

---

## 3. Tier 2 — the definitions you publish

### 3.1 Part

```text
Part {
  id                    "chesterfield.top-rail"
  version · status      draft | active | retired
  type                  PartTypeRef → "rail"
  name_i18n             { en, he }
  spec                  [SpecField + Provenance]                        ← CHANGED
  authorship            Authorship
  cites                 [SourceRef]
  contributing_sources  [SourceDoc]                                     ← NEW
}
```

A part says what the piece **is**. It never says where it goes, how it joins, or
which way up it runs — those are facts about a panel.

### 3.2 FenceModel

```text
FenceModel {
  id · version · status · name_i18n
  grade                 residential | commercial | industrial
  height_support        Continuous(min,max,step) | Discrete([heights])
  option_axes           [Axis{ key, kind: enum|numeric, values, available_when }]
  default_spec          PanelSpec
  variants              [Variant{ condition, spec }]   authored order, first match wins
  layout_policy         [PolicyContribution]
  post                  PostSlot | null                null = NO OPINION
  assembly              [AssemblyStep]
  authorship · cites
  contributing_sources  [SourceDoc]                                     ← NEW
}

PolicyContribution { param, value, knowledge_type, authority }
```

A model carries **several panel specs**, chosen by condition. Vertical-or-
horizontal listing is an axis with two variants — same part library underneath,
different assembly.

Authority is **per contribution**: a manufacturer maximum span is a hard
constraint, a nominal width is a preference, and one authority for the whole policy
would make one of them wrong. Your `ParameterTable`s land on the same precedence
ladder and may contend with these.

### 3.3 PanelSpec — the structure

```text
PanelSpec { frame [FrameSlot] · infill InfillSpec | null · fixings [FixingRule] }

FrameSlot {
  key                  "bottom_rail"
  orientation          horizontal | vertical
  placement            FromBottom(Quantity) | FromTop(Quantity)
                       | FractionOfHeight(permille)
                       | Distributed(count, count_param, insets)
  joint                Joint                    now an object — see below   ← CHANGED
  requirement          PartRequirement
  contains             [ContainedSlot]
}

Joint {                                                                     ← NEW
  kind              butt | channel | groove | bracket | overlap
  channel_depth     Quantity           how deep this slot RECEIVES another
  insertion_margin  Quantity | null    OPTIONAL — null publishes a Gap, never 0
  shared_host_gap   Quantity | null    between two members sharing this host
  gap_reason        thermal_expansion | tolerance | …
}

Member {                        one repeat of the infill pattern
  key · base_ref · top_ref      which frame slots it runs between
  joint            Joint
  base_engagement · top_engagement    Quantity
  gap_after        Quantity     MAY BE NEGATIVE — that is an overlap
  face_offset      Quantity     + front face, − back face (shadowbox)
  continuity       per_bay | continuous     default per_bay             ← NEW v0.4
  profile_edges  { start, end }  tongue | groove | square | ship_lap | none  ← NEW
  requirement · contains
}

InfillSpec {
  orientation    vertical | horizontal
  pattern        [Member]
  justification  start | end | center | spread_to_fit
  excess         truncate | space | trim_last | extension_clip
  edge_margin    Quantity
  supply         components | assembly
}

FixingRule {
  key
  basis          per_member_crossing | per_member | per_end_member
                 | per_gap | per_frame_member | per_panel
                 | per_end_member_by_edge                              ← NEW
  qty_per_basis · qty_param · requirement
}
```

**Orientation is load-bearing, not descriptive.** `per_member_crossing` multiplies
infill members by frame members, which is a real crossing only when the two run at
right angles. Get the orientations wrong and the arithmetic still produces a
number, and the number is a fiction.

**`continuity` — new in v0.4, and it comes from your own evidence.** `Standard rails
are supplied in 16 foot lengths` … `slide rail through second post` … `staggered from
post to post`. That rail is **one physical object in two bays**, and published as
`per_bay` — which is what the model forced until now — it is counted twice and cut to
the wrong length. Nothing in the geometry reveals this; only the guide says it, and
only for some products. Author it where a document states it; the default is right for
almost everything.

The general rule behind it, which is worth having because it is not obvious: **a member
belongs inside a panel if and only if no other bay can produce the same physical
object.** Not *if its count is fixed* — a slat count varies with bay width and lives
happily inside the panel, because each slat belongs to exactly one bay.

**N16 — handedness.** `Attach U-Channel to "tongue" side of first board, and
"groove" side of last board`. `per_end_member` gets the *count* right (two
channels) and the *handedness* wrong, so a mirrored panel validates clean. The
vocabulary is small and open.

**N-Q1 — tongue-and-groove, and one thing we ask you not to do.** Your finding
that pitch equals nominal width — derived exactly once in 2,147 pages, and
corroborated by `13 × 7 = 91` on a different manufacturer's fill kit — means the
correct publication is `gap_after = 0`, not a negative. **Do not publish a negative
`gap_after` from the `7 3/8"` reading.** The model permits it, the
corpus does not support it, and it fails silently: a panel 5% too wide that
validates clean. That artefact — two widths for one part on one PE-sealed sheet,
neither labelled nominal or coverage — is now the worked example in our review-queue
design, because no schema change closes it and only a reviewer does.

**N9.1 — `insertion_margin` stays, and must be omittable.** You searched and found
no document states a tipping-in clearance. It is a real quantity a fabricator knows
and nobody publishes. It stays because §3.4's derived-cavity predicate needs it, and
its absence must publish as a `Gap` — a `0` silently asserts "no clearance required",
which no manufacturer said.

**The shared-host gap — your §3.2 answer is adopted, and it is better than the
question.** `leave a 1" gap between rail ends inside post to allow for expansion`,
twelve instances across six documents. You are right that it is not a property of a
slot: the two members are in **different bays**, and it is a property of the
**joint** where a member meets a host that receives two of them. So `joint` becomes
`Joint`, and it absorbs `channel_depth` and `insertion_margin`, which were sitting
loose beside it and describe the same relationship. `shared_host_gap` is a
`Quantity`, so it carries `25400` and the lexeme `1"` and B3 does not bite it.

`gap_reason` is separate from the number because the corpus gives the reason
explicitly and it is not always expansion — and a curator reading `1"` with no reason
cannot tell whether it scales with temperature range or is a fixed fabrication
tolerance.

### 3.3.1 Part, slot, requirement — how the three relate

Asked twice by readers of v0.2, and answered nowhere in it.

**A part and a slot never reference each other.** `PartRequirement` is the join, and
it runs one way only:

```text
Slot ──requirement──> PartRequirement ──part_id (UNPINNED)──> Part ──match──> Product
```

Each holds exactly what the others cannot:

| | Holds | Never holds |
|---|---|---|
| `Part` | what a piece **is** — spec fields, shared, versioned | where it goes, how many, how long |
| a slot | a **place** in a structure, keyed within its model | what fills it |
| `PartRequirement` | `qty` · `length_rule` · `eligibility` · which part | what the part *is* |

`role` is filled from `Part.type` **during resolution and never authored** — a slot
names a part and the role falls out. A part never knows where it goes; that
asymmetry is what invariant 2 protects, and it is why a slot naming a part may not
also author what that part is.

**Five authoring shapes carry a `PartRequirement`, and all five collapse to one
resolved shape.** This is the consistency that matters, and it is not visible from
the type names:

| Authoring shape | Lives in | Quantity comes from | `slot_kind` |
|---|---|---|---|
| `FrameSlot` | `PanelSpec.frame` | its `placement` — may be `Distributed` | `frame` |
| `Member` | `InfillSpec.pattern` | the infill fitter | `infill` |
| `FixingRule` | `PanelSpec.fixings` | a `basis` | `fixing` |
| `PostSlot` + its `cap` | `FenceModel.post` | one per station | *bay-level* |
| `ContainedSlot` | `contains` on any of the above | its host | *proposed* |

All five mint a `slot_key` and resolve into
`ResolvedSlot{ slot_key, role, qty, length, sku }`. That flat list is what the bill
of materials, the structure sheet and the assembly plan each read, and
`Σ(parts) ≡ BOM` is an identity over it.

**Two asymmetries, stated because they are load-bearing rather than tidy.**

*The `*Slot` suffix carves nothing.* `FrameSlot`, `ContainedSlot` and `PostSlot`
carry it; `Member` and `FixingRule` do not — yet all five are slots after
resolution. The tempting rule ("a slot is a singular authored position, the others
are generative") fails on `FrameSlot` with `Distributed`, which is generative too.
The suffix is historical. **`slot_kind` is the real taxonomy**; author against it,
not against the names.

*A slot has a **scope**, and that is the whole of it.* The model already carries
this vocabulary on the step side — `AssemblyStep.scope` is
`panel | bay | post | run | site` — and v0.2 failed to connect the two, describing
the slot side and the step side as unrelated ideas when they are the same one.

| Scope | Slots at that scope | Swapped by a variant? |
|---|---|---|
| `panel` | `FrameSlot` · `Member` · `FixingRule` | yes — the variant changes the `PanelSpec` |
| `bay` | `PostSlot` and its `cap` · a footing | **no** — it hangs off `FenceModel` |
| `run` · `site` | a string line, a utility locate | no |

Nothing about a post's *relationship* to its part differs: same `PartRequirement`,
same derived `role`, same eligibility match, same one-way rule that a part never
knows where it goes. What differs is its **scope**, and the four consequences in
§3.4 all follow from that one fact rather than from four separate exceptions. It is
also why the wider `SlotTarget` variants (§3.6) are not exotic: `Footing`,
`SiteFixture` and `Elapsed` are slots at bay, site and run scope.

Two consequences a curator needs:

1. **`Σ(parts) ≡ BOM` over a panel's slots does not account for posts.** They are
   counted separately. A panel that balances is not a bay that balances.
2. **A slot path is scoped**, which is why `SlotTarget` (§3.6) names the scope in
   the variant — `PanelSlot(path)` versus `PostSlot(key)` — rather than pretending
   to one flat path space.

**What is shipped and what is proposed**, since this section reads as though it all
exists. `FrameSlot`, `Member`, `FixingRule` and `PostSlot{key, requirement, cap}`
are built. `Joint` as an object, `contains` anywhere, and `ContainedSlot` in its
entirety are **proposed** — containment is step 3 of Planning's build order and no
part currently contains another.

---

### 3.4 ContainedSlot — a part inside a part

```text
ContainedSlot {
  key             "channel"
  relation        reinforces | lines | sleeves | fills | caps | retains   ← CHANGED
  coverage        Coverage                                                ← CHANGED
  required_by     null = always | a knowledge param a rule may set
  requirement     PartRequirement
  contains        [ContainedSlot]     recursive; depth capped at load
}

Coverage = Span { from: Anchor, to: Anchor, at_least: bool }              ← NEW
         | At  ( [Quantity] )        discrete inserts — unchanged from v0.1

Anchor { origin: Origin, offset: Offset }                                 ← NEW

Origin = HostStart | HostEnd | Datum(grade | hole_base) | SiblingSlot(slot_path)

Offset = Const(Quantity)
       | Param(key)        resolves against a ParameterTable at RUN time
       | Sum([Offset])
       | Neg(Offset)
```

**N7 — coverage is an anchored interval.** `Fraction(permille)` is dropped: zero
instances, and unauthorable in principle where the host publishes no length at all,
which Chesterfield's own `2 X 6 DECO RAIL` does not. Both variants v0.1 *guessed*
at — periodic pitch, gate-bay-only — also have zero instances and are not added.
What exists is an interval with two ends:

| Your verbatim | v0.1 | v0.2.1 |
|---|---|---|
| `POST REINF. FULL LENGTH -1"` | no kind fits | `Span{ HostStart+0, HostEnd+Neg(25400) }` |
| `POST LENGHT-(DEPTH+7)` | no kind fits | `Span{ HostStart+0, HostEnd+Neg(Sum[Param(footing_depth), 177800]) }` |
| `PANEL STIFFENER 70 1/4"` in `SIMTEK PANEL 70"` | `Fixed()` validates a part that does not fit | `Span{ HostStart+0, HostEnd+6350 }` — a *visible* overhang |
| `…to at least 22" above grade` | no kind fits | `Span{ Datum(grade)+558800, …, at_least }` |
| the `92` channel in the `94.5` rail | `Fixed(2337)` | `Span{ HostStart+0, HostStart+2336800 }` |

`Full()` becomes `Span{HostStart+0, HostEnd+0}`; `At([…])` survives as a sibling of
`Span` under `Coverage` rather than as an anchor kind — v0.2 wrote `coverage: Span`
and then said `At` survived, which was a contradiction you caught.

**The `Param` grammar was a category error, and your reading of it is exactly
right.** v0.2 made `Param(key, delta)` an anchor: a value plus an offset and **no
origin**, while every other anchor named an origin. So the source — *host length
minus (a parameter plus a constant)* — was inexpressible, and the document's rewrite
to `Span{Datum(grade), Param(footing_depth, +178)}` was an equivalence it never
proved and which holds only if the post is set to exactly the footing depth.

Splitting `Anchor` into an **origin** and an **offset expression** says what the
sheet says. `Param` becomes an offset, never an anchor, and `Sum`/`Neg` let the
offset be the arithmetic the cell actually prints. The grammar is deliberately tiny —
no products, no conditionals — because everything in this corpus is a sum of
constants and parameters, and a bigger grammar would be a second rule engine.

**Your counter-argument, answered.** You said most cases could be published as
`Fixed()` with a curator doing the arithmetic at authoring time, and that this is
simpler. It is, and we would take it but for one case: `POST LENGHT-(DEPTH+7)`,
where the depth is a conditional value not known until a site is planned. Resolving
it at authoring time means publishing one coverage per footing depth — the same
collapse-a-table-into-a-scalar error that made a single `max_span_mm = 1800`
simultaneously unsafe on three documented sites and uncompetitive on three others.
`Param` is the anchor that earns the machinery.

**N8 — the relation vocabulary.** `insulates` dropped (zero instances). `fills`
(concrete poured inside a post, which the guides treat as interchangeable with an
aluminium insert), `caps` (`F- INTERNAL POST CAP`) and `retains` (lock rings,
bullet clips) added. Closed, but registry-extensible: a new word is a row, not a
release.

**N9 — post-role keying. v0.2 put it in the wrong place and your review is right
to call it an outright fail.**

Reinforcement is conditioned on a post's **role in the run**, and two manufacturers
disagree about the corner case — Freedom says inserts are `not needed in corner
posts`, Bufftech says `Corner posts should be reinforced with concrete and rebar`.
v0.2 hung `for_post_roles` on `ContainedSlot`, and on `FrameSlot` as well, which are
both **inside a `PanelSpec`**. A panel does not know what kind of post bounds it,
and a panel-internal flag cannot say *which of its two bounding posts* it means. So
post reinforcement had no slot to live in. `PostSlot` was named in
`FenceModel.post` and never defined at all.

```text
PostSlot {                                                              ← DEFINED
  key
  joint        Joint
  requirement  PartRequirement
  cap          PartRequirement | null    NESTS, deliberately — see below
  contains     [ContainedSlot]           the insert, the concrete, the rebar
}
```

**Why a post hangs off `FenceModel` and is not a slot in `PanelSpec`.** Worth
stating, because it is the first question anyone asks of this shape and v0.2 never
answered it. Four reasons, and they compound:

1. **A post is shared between two bays** — the *same physical object* with two
   owners. Note the reason is **exclusivity, not variability**: a slat count varies
   with bay width and a rail count with height, and both live happily inside the
   panel, because each slat and each rail belongs to exactly one bay and sums
   without double-counting. A post does not.

   The rule that follows is general, and it is the one to author against:

   > A slot may be panel-scoped **iff no other bay can produce the same physical
   > object.** Not *iff its count is fixed*.

   **This rule already catches something the model gets wrong**, which is why it is
   worth stating rather than treating posts as a special case. Your own §2.4
   finding — `Standard rails are supplied in 16 foot lengths` … `slide rail through
   second post and then insert post in ground`, with joints staggered from post to
   post — is a rail that runs *continuously through* an intermediate post. One
   physical object, two bays. Rails are panel-scoped today, so that product is
   mis-modelled, and it is a **structural** gap rather than only the step-scoping
   one that `scope: run` addresses. Publish it as a `Gap` until Planning has the
   machinery.
2. **The two bays may be different models.** At a `transition` station the left bay
   is one product line and the right is another. Two panel slots would each assert
   *my post*, with no rule for which wins. The engine instead collects **claims**
   and **intersects** them — both lines' specs must be satisfied by the one post
   that actually stands there. Note this **generalises** ordinary resolution rather
   than opposing it: with a single claimant the intersection is the identity, which
   is why panel slots are unaffected by the mechanism existing.
3. **The cycle rule, and the locality it protects.** Resolution is a DAG:
   `height → rail positions → post → clear width → infill fit`. A bay's clear
   opening is measured *to the post faces*, so a post chosen by that opening would
   be choosing itself. A post's eligibility predicate may therefore read only facts
   settled from the bay's **height** — a closed set, refused at authoring rather
   than at generation, where the same mistake is either a hang or an arbitrary
   answer that reads as measured.

   The consequence is stronger than ordering. `resolve_panel(spec, ctx)` is a pure
   function of **one bay**: its context is *"everything a panel needs to know about
   the bay it is being laid into"*, and `clear_width_mm` arrives already settled.
   Move the post inside the panel and resolution must first resolve the post, which
   requires the *neighbouring* bay's model — so the context would have to carry the
   neighbour and panel resolution would stop being local. That is the argument the
   count anomaly was standing in front of.
4. **`null` means NO OPINION.** The field is a *contribution*, not a composition,
   the same shape as `layout_policy`. A model silent about posts is valid, and the
   company's own post standard applies.

`cap` **nests inside `PostSlot`** rather than sitting beside it, because a cap
exists *because* a post does and its predicate reads the post it caps — which is
only answerable because the post is chosen first. That ordering is what keeps every
relation here one-directional. (v0.2 dropped this field; it is restored.)

A `PostSlot` is resolved **per station**, and a station has exactly one role — so
`for_post_roles` is well defined there and nowhere else. It is therefore removed
from `FrameSlot` entirely, and on a `ContainedSlot` it is **meaningful only under a
`PostSlot`**; publishing it under a panel-internal slot is a validation error rather
than a no-op, because the alternative is a flag that silently means nothing.

```text
ContainedSlot.for_post_roles  [PostRole]    empty = every role
                                            LEGAL ONLY under a PostSlot
```

This is the shape that reaches your §2.4 shared-line-post case and your §2.11
gate-post case as well, and it is why `PostRole` has six values rather than four
(§2.8).

**One thing we owe you before you author containment, because we had not traced
it.** A published `ContainedSlot` reaches a bill of materials only if panel
resolution **flattens it into the panel's slot list** under a path key
(`bottom_rail/channel`) — demand derivation is a single loop over that list and knows
nothing else. Our design never said it does. Worse, the crediting rule we specified
(*if the host's SKU is a kit already listing the contained part, credit it rather
than buying it twice*) has nowhere to live: a demand line has no notion of one line
covering another. That is a new concept in demand derivation, not an adjustment to
it. **The shapes below are safe to author against** — none of them changes — but the
consumption path is ours to build, and we had not checked it existed.

**N9.2 — `host.cavity_width_mm` is never published, and you are right.** The only
"Inside Dimensions" in 2,147 pages belong to storage sheds; every profile publishes
an outside dimension and a wall thickness (`5X5 POST` is `4.940` OD, `0.170` wall)
and never a cavity. The predicate must be written against a **derived** cavity
(`OD − 2 × wall`) with the derivation visible rather than folded into a field name,
or a reader cannot tell a measured cavity from a computed one.

### 3.5 PartRequirement

```text
PartRequirement {
  part_id      "" means this slot names no part
  role         filled from Part.type during resolution — never authored
  qty · length_rule · overlap    Quantity
  option_axis · sku_by_option
  eligibility  Eligibility{ members | predicate }
}
```

Unchanged. Four shapes, derived from the fields rather than stored: `part`,
`authored_predicate`, `authored_members` (tenant commerce, not yours to publish),
and `unspecified` (refused at load).

Two established predicate namespaces, for facts a part **cannot** state about
itself:

```text
item.routed_at     ==  panel.rail_positions      a factory-routed post
item.width         <=  host.cavity_width          a contained part must fit —
                                                  DERIVED, see §3.4
```

**`host.cavity_width` is not a published field.** §3.4 establishes that no profile in
the corpus publishes a cavity, so this predicate reads a value derived as
`OD − 2 × wall`. It is written here as though it were ordinary because the *predicate*
is ordinary; the derivation behind it is not, and must stay visible.

A slot naming a part may **not** also author what that part is — resolution
overwrites both fields, so a document carrying both validates clean and then has
its authored half deleted silently.

### 3.6 AssemblyStep and Procedure

```text
AssemblyStep {
  key
  kind      assembly | installation
            | preparation | part_modification | maintenance             ← CHANGED
  scope     panel | bay | post | run | site                             ← CHANGED
  slots     [SlotTarget]                                                ← CHANGED
  requires  [Edge{ kind: after | not_before | before | exclusive_with,  ← CHANGED
                   step: key }]
  cites     [SourceRef]
  text_i18n
}

SlotTarget =                                                            ← ENUMERATED
    PanelSlot(path)        "bottom_rail" · "bottom_rail/channel"
  | PostSlot(key)          the post, its cap, its insert
  | Footing(part)          hole | gravel | concrete | rebar
  | SiteFixture(kind)      string_line | stake | batter_board
  | Elapsed(Quantity)      a 72-hour cure — placed by no part
  | Reused(slot_path)      a real BOM part used as a jig, then installed
  | None                   the step names no part at all

Procedure {                                                             ← NEW
  id      stable across revisions — a correction must find its siblings
  scope   EntityRef | null      null = owned by no product at all
  steps   [AssemblyStep]
  cites   [SourceRef]
}
```

**N10 — five scopes, and your counter-argument is rejected.** You measured
44–51% of steps as neither panel nor bay, and offered us the option of declaring
everything above the panel out of scope, since a gravel-base step produces no BOM
line. We decline, and state why so it does not get re-opened: the structure sheet
is a **fitter-facing document**, not only an input to a price. A sheet that omits
the string line, the 72-hour cure and the utility locate is not a smaller sheet; it
is a sheet a fitter cannot work from. Half of every installation guide is not a
rounding error.

Your 16 ft rail is the case that convinced us — `slide rail through second post`,
spanning two bays, threaded *through* the intermediate post. It belongs to no bay
at all, which proves `scope` is a genuine dimension rather than a granularity knob.

**How we will land it, so you can plan against it.** The read model takes
`(model, resolved panel)` and structurally cannot place a post. Two phases:
`panel | bay | post` first, then `run | site`. **Publish all five from the start** —
phase one reports `run` and `site` steps as present and unrendered rather than
dropping them.

**N10, `requires`.** An edge kind is needed because the corpus states negative and
maximum dependencies as well as ordinary ones — `do not add concrete… until later`,
`before concrete sets` — and two guides explicitly deny their own print order:
`Assembly may be continued by installing all bottom rails first, or one section at
a time`. A bare `requires: [key]` flattens those exactly the way list position
flattens ordinary prerequisites. Your `cur_step_requires` has the identical gap.

**N13 — `Procedure`, because duplication is not free.** In one 50-page guide the
identical run-scope block repeats **sixteen times** and the cure step twelve —
once per style. As `FenceModel.assembly` that is one procedure, sixteen copies,
sixteen `SourceRef`s to the same page, and a correction to one that reaches none of
the other fifteen. `scope: null` covers the cross-manufacturer case: the CLFMI
bulletin is about chain link, has no vinyl model to attach to, and is nonetheless
the most authoritative statement on post embedment in the corpus.

`FenceModel.assembly` stays as it is for procedures that genuinely belong to a
panel.

**`Procedure.id` was missing and you were right that it is load-bearing.** Without
it `Warning.attaches_to{kind: procedure}` cannot address one, and N13's whole benefit
— *a correction that reaches the other fifteen* — presupposes an identity. It must be
stable across revisions, or the correction still cannot find its siblings.

**`Reused` in `SlotTarget` answers the half of N24 that §7.3 did not.** Your
temporary-spacer rail — `Use only one rail as temporary spacer for your entire
fence` — is a real BOM part **placed twice and bought once**. Invariant 4 as written
("exactly one step") makes that unpublishable. `Reused(slot_path)` names the same
slot from a second step without a second placement: the fulfilment side counts the
original slot, and the read model shows both steps. Invariant 4 is restated in §6 to
say *placed by exactly one `PanelSlot` or `PostSlot` target*, with `Reused` explicitly
not a placement.

### 3.7 Warning — now its own entity

```text
Warning {                                                               ← RESHAPED
  text_raw         REQUIRED · verbatim · never normalised
  lang             REQUIRED
  cites            SourceRef · REQUIRED
  attaches_to      REQUIRED · { kind: step | procedure | document | product
                                      | model | warranty | maintenance, ref }
  severity_lexeme  the publisher's own word — WARNING | CAUTION | NOTICE |
                   IMPORTANT | NOTE | none. NOT normalised.
  code             OPTIONAL — an overlay, not the primary key
  params           OPTIONAL, only alongside a code
}
```

**N11 — your census falsified invariant 5 and we accept it without reservation.**
1,038 instances, 226 distinct warnings, and **19.9% of resolvable instances sit
inside a step that does something**. Enforced literally, v0.1 publishes one warning
in five and discards or misattributes the rest. Attaching the freeze-thaw footnote
to step 10 would be a curator's inference; attaching the safety-goggles box to
every step would be a fabrication.

Codes stay as an optional overlay because a warning fired for a *computed* reason —
an uncovered condition, an unfulfilled requirement — has no source document and
must be a code. The mistake in v0.1 was treating engine-generated and
document-quoted warnings as one type. They have opposite requirements: the first
must be translatable and parameterised, the second must be verbatim and
untranslated.

`severity_lexeme` is deliberately not normalised. You are right that `CAUTION` and
`WARNING` are terms of art with different legal weight in North American product
literature, and collapsing them is a decision neither team should make on a
manufacturer's behalf.

**N12 — the registry splits, and this changes a standing rule on our side.**

| Registry | Rule |
|---|---|
| **Platform codes** — engine warnings, gap codes, the `SOURCE_*` set | Closed. Both locale bundles required, enforced by our `test_locale_bundles.py`. |
| **Source warnings** — quoted from a document | Verbatim, `lang`-tagged, **exempt**. Rendered untranslated. |

Zero of the corpus's 81,794 elements are Hebrew, and translating a manufacturer's
liability sentence to satisfy a key-set test would be manufacturing a claim. Note
the old rule failed precisely where it was needed: a text fallback is by definition
the case with no code, so it could never satisfy "every code in both bundles."

**What Planning does with each attachment kind** — you need this to make
`attaches_to` usable:

| `attaches_to.kind` | Rendered |
|---|---|
| `step` | on that step in the structure sheet |
| `procedure` | at the head of that procedure |
| `product` · `model` | on the BOM lines using it, once per line group |
| `document` · `warranty` · `maintenance` | in the plan's **annexe**, once — never on a line |

So the freeze-thaw footer's 83 instances become one annexe entry, and your refusal
to attribute it to step 10 costs nothing. A document-scoped warning shown on every
BOM line is noise that trains a reader to ignore warnings, which is worse than not
showing it.

**We are taking up your constructive offer.** Send the eleven-warning head as a
starter code list with instance counts and a verbatim exemplar each. Those become
platform codes and go into both bundles.

### 3.8 ParameterTable

```text
ParameterTable {
  parameter     "max_span_mm" | "footing_depth_mm" | "max_rack" | "slope_method"
  scope         EntityRef → Part | FenceModel
  task          TaskCode
  hit_policy    unique | priority | collect_min | collect_max
  value_type    quantity(<UnitCode>) | token(<closed set>)   declared ONCE  ← NEW
  domain        { exposure_category: [B,C,D], hvhz: [true,false],
                  jurisdiction: […], code_edition: […], material: […] }
  domain_basis  measured | declared                                      ← NEW
  rows [ { conditions
           condition_basis  stated | assumed                             ← NEW
           value            Quantity | Token     conforming to value_type
           provenance       Provenance                                   ← CHANGED
           valid_from · valid_until · authority                          ← NEW
         } ]
  uncovered [ { … } ]
}

Token { key: str, value_raw: [str] }        a token carries its lexeme too  ← NEW
```

**`Token` is not a bare string** — that was B5's fourth undefined type, and leaving
it bare would have reintroduced through the N2 modification exactly the loss N3 was
accepted to prevent. `stepped_only` publishes with the words the document actually
used (`They should be only installed using the slope method`), so a curator sees the
sentence beside the token.

### 3.8.1 Unconditioned rows — B6

**Your finding, opened by your own acceptance of N18, and the model had no correct
answer for the commonest shape of fact in the corpus.** 239 of the 360 install-manual
structural facts — **66%** — carry no condition keys at all, against 4–7% for the
sealed classes. The class N18 admits is precisely the class that states values
without the conditions that make them safe.

Publish `Figures based on 4x4 hole=10", 5x5 hole=12", both 30" deep` into a domain of
`{exposure_category: [B,C,D], hvhz: [true,false]}` and it asserts six things the
source never said — which is `rationale.md` §1's G16 at a scale of 239 rows. And your
observation that the alternative is no better is the part that makes this a defect
rather than a preference: under `unique` an unconditioned row matches every point,
collides with every conditioned row, and becomes a publish error instead of an
honest gap.

**`condition_basis` is adopted as you proposed it**, symmetric with `domain_basis`,
and with two consequences that need stating because they are what make it work:

```text
condition_basis: stated    the source gave these conditions — including
                           "gave none", when conditions is empty
condition_basis: assumed   a curator supplied them; the source did not
```

1. **A `stated` row with empty conditions is a fallback, not an assertion.** It is
   **excluded from the `unique` overlap check** and consulted only where no
   conditioned row matches. Otherwise the 239 become publish errors, which is the
   failure you named.
2. **Planning warns whenever such a row is applied**, naming the conditions the
   source did not state — `warning.unconditioned_source_applied`, with the site's
   actual conditions as params. The value is used; the reader is told the document
   never scoped it.

`assumed` exists so that a curator who *does* supply a bracket is distinguishable
from a source that stated one. G16 was a reader recording an inference as a reading;
this makes that difference publishable rather than lost.

**The mechanism is now settled on our side, and it very nearly was not.** When we
accepted this we had no way to express a fallback tier, and the expansion we
published would have produced a *silent wrong answer* rather than a missing feature:
every row of one table shared a single `object_id` and differed only by
`version = row_index`, and our resolver breaks a same-id tie by **higher version**.
An unconditioned row compiles to an always-true condition, so it fires alongside
every conditioned row of its own table — and would have won on all of them, on every
site, purely by sitting lower in the table. No conflict raised, nothing warned, and
the decision graph attributing the answer to a real source.

Fixed by two changes, both ours: each row now mints its **own `object_id`**, so row
position can never decide anything; and a `stated` row with empty conditions is
published at a **weaker authority** than its conditioned siblings, so any conditioned
row beats it and a tie between two fallbacks lands outside our hard-failure band.
**Publish the rows in whatever order suits you** — order now carries no meaning,
which is what we told you it did.

### 3.8.2 Why the value type sits on the table

**N2 — MODIFIED.** You asked that a row's value admit an enum, so `stepped_only`,
`not_rackable` and `gates are not rackable` have a home. Right ask, and the form
invites a type error: if *any row* may be a quantity or a token, one table can hold
`10000 deg_milli` and `not_rackable` in the same column, and every consumer must
branch on the type of every cell.

`not_rackable` is not an angle. It is a different parameter. So the declaration
sits on the **table**, and the publish check enforces it:

```text
ParameterTable { parameter "slope_method"
                 value_type token{ rackable | stepped_only | not_rackable } }

ParameterTable { parameter "max_rack"
                 value_type quantity(deg_milli)
                 domain     conditioned on height AND on slope_method = rackable }
```

This costs you one field and gives you everything you asked for. It also improves
the cell you quoted: `▼ Racks up to 10 degrees 3' and 4' high, 5 degrees 5' and 6'
high` becomes two rows of one height-conditioned `max_rack` table, and the Even
Stephen / Simple Simon prohibition becomes a row of `slope_method` — rather than
both being crammed into one column with different types.

**N-Q2 — racking is a `ParameterTable`, not a `PolicyContribution` and not a spec
field.** All three of your reasons hold: it is conditional on height, it is not a
property of the infill (Chesterfield racks 10° and Galveston 5° with identical
pickets), and it changes structure — `Enlarge holes in post`, `Shorten picket
length`, and `post centers may need to be decreased`, which contends with
`max_span_mm`, a parameter the engine already multiplies against. A warning
attached to a step cannot reach a parameter. Scope it to the `FenceModel`,
condition it on height and on option axes. `*Accents will reduce the amount of
rack` — stated four times, quantified zero times — is a `Gap`, and a real one.

**N25 — MODIFIED from a confirmation to a field.** You asked us to confirm that
`uncovered` on one of the 73 unreadable pages must not read as measured. Confirming
it in prose is not enough, because the consumer of that distinction is a warning
renderer, not a reader. So `domain_basis` is a field. Planning renders an
`uncovered` hit differently under each: *we may not know this table's real extent*
is a different fact from *this table really does not cover that point*.

**N22 — MODIFIED: fields, not an `as_of_date` condition.** You offered both and
said you would accept either. We choose fields, because modelling expiry as a
condition dimension means every table must declare a time domain — and then
`uncovered`, one of the mechanisms we most rely on, reports every unenumerated date
as a coverage hole and drowns the signal it exists to carry. Expiry is also not a
property of the *site* the way exposure and jurisdiction are; it is a property of
the **authority**, and it belongs beside the authority. Planning warns on a line
whose backing authority has lapsed relative to the run date, in the same family as
an uncovered condition and a below-bar curation level.

### 3.9 Combination, and the standards regime

```text
Combination {
  id       "chesterfield-6ft-expC-30in"
  members  [PartRef@version]      validity scoped to EXACTLY these
  claims   [ParameterTableRef]
  cites    [SourceRef]
  valid_from · valid_until · authority                                   ← NEW
}
```

Borrowed from how matched HVAC systems are certified: the rating applies to the
combination, not to the members, and swapping one **invalidates** it rather than
inheriting it.

**Deprioritise curating these, and the reason is embarrassing.** `grep -rn
"Combination" src/` in the engine returns **nothing**. We accepted this type as
binding, put it in the snapshot payload, argued for it from the AHRI precedent, and
asked you to curate certified assemblies that a run would **silently ignore**. A
swapped member would invalidate nothing, because there is no checker.

The type stays and the shape is right. The seam is named: a `certify()` step in
fulfilment comparing a run's resolved parts against each pinned `Combination`,
raising `warning.combination_uncertified` when a member differs — a warning rather
than a constraint, so it stays inside the never-block rule. Until that exists a
`Combination` is **pinned but inert**, and your effort is better spent on parameter
tables and definitions. We would rather say this than keep accepting data nothing
reads.

**N29 — MODIFIED, and answered with a design rather than a choice.** You raised the
`us` / `china` tracks as a question: two deliberately separate corpora, Chinese
language, metric, GB rather than ASTM, and nothing in the contract mentions a
track.

**A snapshot serves exactly one standards regime, and declares it.** `Snapshot`
gains `regime` — `us_astm`, `cn_gb`. A project declares its regime, and Planning
**refuses** to generate against a mismatched snapshot, with a typed 409 in the same
family as the topology and site-conditions guards.

Not a condition dimension, because a regime is not a value a rule conditions on —
it is the frame the whole rule set is written in. GB and ASTM do not merely
disagree about a number; they disagree about what the conditions *mean*, which is
the same class of problem your §2.8.3 found between ASCE 7-10 and 7-16 one level
down. A condition dimension would let a GB row and an ASTM row coexist in one table
and be *selected between*, which is exactly the silent wrong answer we should
refuse.

Not tenancy, because a single tenant may operate in both. Regime and tenant are
orthogonal — collapsing them would be the same mistake as v0.1's tenant-namespaced
part types, which you caught.

---

## 4. Tier 3 — your private model

**Unchanged, and not under negotiation.** `docs/curation/` is yours, it is more
considered than anything we would write, and this document cites it as your
internals rather than as a proposal to be overruled.

```text
documents · document_versions · pages · elements · tables · assets · crops
Claim + conditions + evidence           the sourced rows
Review · promotion rules                the human gate and its scaling escape
Conflict · Gap                          disagreement and absence, both as rows
Procedures + steps + requires + warnings
Entities · aliases · relations          identity across spellings
Source policy                           task × source class × role
retrieval units / index                 discovery only, never cited
```

**What crosses into tier 2 — B1.** v0.2 said *"everything else stays yours and is
never consumed"* while §9.1 published gates **as `Gap`s** and contract §1.2 carried
`gaps [Gap]` in the payload. You are right that those cannot both be true, and that
it is the sentence N17 depends on. `Gap` and `Rule` are **published**, not private,
and the crossing count was wrong:

| Tier 3 object | Becomes |
|---|---|
| accepted `Claim` | a `ParameterTable` row |
| curated procedure | `FenceModel.assembly`, or a `Procedure` |
| curated warning | a `Warning`, with its `attaches_to` |
| curated definition | a `Part` or `FenceModel` |
| `Gap` | a `Gap` — **published as-is** |
| derived rule | a `Rule` |
| `SourceDoc` metadata | `source_docs` in the snapshot |

`Gap` is the escape hatch the whole never-block design rests on: an unmodellable
gate, an absent `insertion_margin`, the unquantified accent effect on racking, and
every part-kind no existing rule can count all land on it. It has to cross.

**Everything not in that table stays yours and is never consumed** — evidence,
elements, crops, reviews, promotion rules, conflicts, retrieval indexes, and the
source policy's internals.

---

## 5. Relationships

| From | To | Meaning |
|---|---|---|
| `Part.type` | `PartType` | Filed as. Namespace decides who may extend. |
| `Part.spec` | `[SpecField + Provenance]` | What it is. Dimensions derive from here. |
| `Part.contributing_sources` | `[SourceDoc]` | **NEW.** Pinned, so a run can see a lapsed authority. |
| `SourceRef.belongs_to` | `SourceDoc.content_hash` | **NEW.** Joins a per-field citation to the provenance block. |
| `FrameSlot.requirement` | `Part.id` **unpinned** | Generation resolves latest active; the run stamps what it resolved. |
| `Member.base_ref` / `top_ref` | `FrameSlot.key` | Sibling reference: which frame members it runs between. |
| `Member.engagement` | `FrameSlot.channel_depth` | Engagement + margin must fit the depth. |
| `Member.profile_edges` | edge vocabulary | **NEW.** Which way the interlock faces. |
| `FrameSlot.contains` | `[ContainedSlot]` | Parent–child. Distinct from spanning. |
| `ContainedSlot.coverage` | `Span` → `Anchor` | **CHANGED.** An interval with two ends. |
| `Anchor.Param` | `ParameterTable` | **NEW.** Extent conditional on a value not known until run time. |
| `ContainedSlot.for_post_roles` | `PostRole` | **NEW.** Conditioned on the post's role in the run. |
| `…requirement.predicate` | `host.*` / `panel.*` | Agrees with a fact about something it has not been placed in. |
| `AssemblyStep.slots` | `[SlotTarget]` | **CHANGED.** A union, not only panel slot paths. |
| `AssemblyStep.requires` | `[Edge]` | **CHANGED.** A partial order with a kind. List position is presentation. |
| `Warning.attaches_to` | seven kinds | **CHANGED.** Only one in five is a step. |
| `Procedure.scope` | `EntityRef \| null` | **NEW.** `null` = owned by no product. |
| `FenceModel.variants[].condition` | `option_axes` | Which panel spec applies. |
| `ParameterTable.scope` | `Part \| FenceModel` | What the value is about. |
| `Combination.members` | `[Part@version]` | Validity scoped to exactly these, pinned by version. |

---

## 6. Invariants

Twelve. Four held unchanged, six changed, two are new. Eleven are enforced at
publish time; **invariant 11 is a curation rule, not a check** — you were right that
"a gate is not a `FenceModel`" is a human judgement, and calling it publish-enforced
overstated what a validator can do.

1. **Dimensions are derived, never stored twice.** One authority per number.
2. **A part cannot declare its *cut* length** — `agree = supplies` carries no
   value. *(Restated. A manufactured `nominal_length_mm` is a fact about the
   article, every catalogue prints it, and it was always legal.)*
3. **Naming a part and authoring what it is are exclusive** on the same slot.
4. **Every member is placed by exactly one `PanelSlot` or `PostSlot` step target, or
   reported `unplaced`.** A `Reused` target is *not* a placement, so a rail used as a
   spacer and then installed is placed once and bought once. *(A long `unplaced` list
   is a correct outcome — §7.3.)*
5. ~~A warning lives on its step.~~ → **A warning declares what it attaches to, and
   its text is primary.** *(Falsified by census.)*
6. **No two rows match one domain point under `unique`; every uncovered point is
   listed — and the domain declares its basis.** Two exclusions, both of which v0.2
   was missing and both of which its own §8 artefacts required: **rows differing only
   in validity window are not a collision**, and only rows valid at the run date
   participate in the check — otherwise the superseded 2023 approval and the current
   2025 one, which is §8's own N22 artefact, is a build error. And a `stated` row with
   **empty** conditions is a fallback, excluded from the check entirely (§3.8.1).
7. **Every dimension crossing the boundary is a `Quantity`** — integers in
   thousandths of the named unit, with *every* verbatim source lexeme alongside. No
   bare `_mm` field, and no exceptions for values that look small enough not to
   matter; that judgement is what produced twenty-three of them in v0.2.
8. **Every published value carries a resolvable `SourceRef`, an honest
   `Authorship`, and its `source_class` and `curation_level`.**
9. **Extension part types are namespaced `shared` / `mfr/<manufacturer>` /
   `<tenant>`**, and the parent chain terminates in the spine. *(Axis corrected.)*
10. **Structure is authored, not extracted.** No table reader produces a
    `PanelSpec`.
11. **A gate is not a `FenceModel`.** *(A curation rule, not a publish check — see
    §9.1.)*
12. **Every `belongs_to` in a snapshot resolves inside that snapshot.** *(New.)* A
    citation whose `SourceDoc` is absent carries no admissibility bits, which is the
    defect §2.5 exists to close; a dangling reference reproduces it with extra
    fields. Checked structurally at publish, like invariant 1.

---

## 7. What we want challenged this round

### 7.1 The five we modified rather than accepted

You have not seen these forms before, and our reasoning is ours alone. If any is
wrong, it is cheaper to know now than after you have authored against it.

**All five were accepted in `03-review-of-v0.2.md` §4**, including N2, where the review
says *"you are right and we were wrong."* They are recorded here because the
reasoning behind each is still ours alone, and because two of them carry a live risk
that acceptance does not remove.

| # | | What we did instead | Standing risk |
|---|---|---|---|
| N2 | modified | `value_type` on the **table**, not the row | Closed. `Token` now carries its lexeme, which was the one cost the review named. |
| N18 | modified | Install manuals admissible for structural at rank 4, level 2 | **Live.** Level 2 is a hard dependency for any structural coverage and is unreachable until the cell box exists. The review made the chain explicit: *cell box → level 2 → any structural coverage at all.* |
| N25 | modified | `domain_basis` as a field | Closed. |
| N22 | decided | Validity as **fields**, not an `as_of_date` condition | Closed, once invariant 6 excluded validity-window rows from the collision check. |
| N29 | decided | `Snapshot.regime` + a refusal | Closed. |

### 7.2 Three things we know are still open

**All three from v0.2 are now answered** — the shared-host gap became `Joint`
(§3.3), `material` is bound and gates the `industry_standard` ranking (§2.6), and
`also_filed_as` resolves the duplicate filings (§2.5). What replaces them is
shorter, and two of the three are ours:

1. **Rounding that accumulates past `adapt.py`** (§2.3.1, ours). The fitting
   arithmetic moves to thousandths this round. Anywhere else a rounded value is
   multiplied, we warn rather than fix, and a real fix is an ADR amendment. **If you
   publish a repeat dimension, mark it as one** so the warning can fire.
2. **Chained parameter tables** (§2.7, ours to implement). `max_rack` conditioning on
   `slope_method` is the first table that conditions on another table's value.
   Resolution is ordered and a cycle is a publish error. We do not expect a second
   level of chaining — tell us now if you do.
3. **A repeat-dimension marker, and any other field where thousandths are not
   enough.** `Quantity` is integers in thousandths of a millimetre. If anything in
   your corpus needs finer than a micron, or is genuinely a ratio rather than a
   length, say so — we would rather add a unit than watch a curator scale one.

### 7.3 One confirmation we want in writing

**Invariant 4's `unplaced` escape.** We read your N24 exactly as you meant it, and
we want it recorded: a large `unplaced` list is the **correct** output. Bufftech
Chesterfield leaving 3 of ~11 named members unplaced — the top-rail lock ring, the
HVHZ line-post stiffener, and gravel fill, two of which appear only in a figure
caption — is a *true fact about the document* and we want it. A curator inventing a
placement to turn a check green converts a visible gap into an invisible error,
which is the failure the whole never-block invariant exists to prevent. Our
knowledge-admin UI is being built so it cannot nudge an author toward clearing the
list.

### 7.4 The standing question

Same as v0.1 §7.8–7.10, against the revised model:

- Is anything in §2 or §3 **unrepresentable** for material you already hold?
- Is anything **over-specified** — a field you would have to invent data for?
- Are the invariants in §6 enforceable at publish time?

Same standard as last time: a gap per item, with the document and page that
motivates it. It worked.

---

## 8. Traceability — every finding, and how to verify it closed

Take the artefact in the right-hand column and check you could author it.

### Tier 1

| # | Your finding | Landed | Verify with |
|---|---|---|---|
| N1 | `UnitCode` cannot carry 274 facts | §2.3 — four units added, all four | `10 degrees` as `10000 deg_milli`; `115 mph`; the 72-hour cure |
| N2 | Row value must admit an enum | §3.8.2 — **MODIFIED**, `value_type` on the table; `Token` **defined**, and carries its lexeme | `stepped_only` in a `slope_method` table, with the sentence the document used; `max_rack` stays an angle |
| N3 | `Quantity` carries one `value_raw` | §2.3 — a list | `Height: 66 inch (16766 mm)` — both lexemes, neither discarded |
| N4 | Extension types on the wrong axis | §2.1 — three namespaces | `mfr/barrette/u_channel`, parented to `bracket`, in no tenant |
| N5 | A part cannot declare its length | §2.2 — no schema change; always legal | `nominal_length_mm = 2388` on the Columbia rail |
| N6 | `SourceRef` carries no admissibility | §2.5 — `belongs_to` | a rail-length citation joining to its `SourceDoc` |

### Tier 2

| # | Your finding | Landed | Verify with |
|---|---|---|---|
| N7 | `Coverage` needs a fifth kind | §3.4 — `Coverage = Span \| At`; `Anchor` = origin + offset expression; `Fraction` dropped | all five rows of the §3.4 table, especially `POST LENGHT-(DEPTH+7)` — which v0.2's grammar could not express |
| N8 | `relation` vocabulary inadequate | §3.4 — `insulates` dropped; `fills`, `caps`, `retains` added | concrete poured in a post; `F- INTERNAL POST CAP`; a lock ring |
| N9 | `PostSlot` needs role keying | §3.4 — `PostSlot` **defined**, with `contains`; `for_post_roles` moved onto it and removed from `FrameSlot` | Freedom `not needed in corner posts` vs Bufftech `Corner posts should be reinforced` — as two rows, not a contradiction |
| N10 | Step scope, kind, slots, requires | §3.6 — all four; `SlotTarget` **enumerated**; counter-argument rejected | the 16 ft rail through the intermediate post; the string line; the 72-hour cure; the reused spacer rail |
| N11 | The warning model | §3.7 — text primary, seven attachment kinds | the freeze-thaw footer (83 instances, no step); the Illusions warranty clause (a) through (f) |
| N12 | The warning registry must split | §3.7 — platform closed, source exempt | `AVERTISSEMENT` published untranslated with `lang: fr` |
| N13 | Model-less procedures | §3.6 — `Procedure{scope: EntityRef\|null}` | the CLFMI chain-link embedment bulletin; the 16× repeated run block, once |
| N14 | Definition-level provenance | §2.5 — snapshot-level `source_docs` is the join; `contributing_sources` is a roll-up; invariant 12 closes it | the Chesterfield trace: eleven documents, four manufacturer strings, four superseded — **and a `ParameterTable` row**, which v0.2 could not join |
| N15 | Provenance on every value | §2.4 — the `Provenance` fragment | a rail length carrying its own `source_class` |
| N16 | `Member` needs handedness | §3.3 — `profile_edges` + `per_end_member_by_edge` | `tongue side of first board, groove side of last` |
| N17 | Gates have no type | §9.1 — named out of scope; `Gap` confirmed as a published type (§4); **gate hardware stays publishable** | a gate published as a `Gap`; the hinge load table published as ordinary `Part`s |
| N17a | A `gate.*` namespace | §9 — recorded in the agreed target shape | deferred with N17 |

### Registry additions

| # | Your finding | Landed | Verify with |
|---|---|---|---|
| N18 | No class for an installation manual | §2.6 — **MODIFIED**, admissible at rank 4 / L2 | `Figures based on 4x4 hole=10"… both 30" deep` backing a structural row, at L2 only |
| N19 | No class for an industry standard | §2.6 — added above `spec_sheet`; **`material` bound, and the ranking does not ship without it** | the CLFMI chain-link bulletin NOT winning a vinyl embedment question |
| N20 | `jurisdiction` | §2.7 — bound | `Miami Dade County and other areas where allowed by the AHJ` |
| N21 | `code_edition` | §2.7 — bound | `ASCE 7-10` and `ASCE 7-16` rows coexisting without a `unique` collision |
| N22 | Validity window | §3.8, §3.9 — **MODIFIED**, fields | `NOA-23-0314.05`: issued 2023, expires 2029, superseded now |
| N23 | `SOURCE_*` codes | accepted — platform codes, both bundles | all ten from `source-refs-design.md` §3.2 |

### Clarifications

| # | Your reading | Our answer |
|---|---|---|
| N24 | A large `unplaced` list is permitted | **Confirmed in writing** — §7.3 |
| N25 | `uncovered` on an unreadable table | **MODIFIED** — upgraded to `domain_basis`, §3.8 |
| N26 | `retain_until` for source refs | Confirmed — they inherit the snapshot's retention and tombstone |
| N27 | Source-ref tenancy | Confirmed — corpus refs global, tenant refs scoped, never mixed in one response |
| N28 | `POST /source-refs:batch` | Accepted — our queue needs it; designing the data layer around it now |
| N29 | The `us` / `china` tracks | **MODIFIED** — `Snapshot.regime` + a refusal, §3.9 |

### From `03-review-of-v0.2.md` — the six that blocked authoring

| # | Defect | Landed | Verify with |
|---|---|---|---|
| B1 | `Gap` "never consumed" vs gates as `Gap`s | §4 — seven crossings, `Gap` and `Rule` published | an unmodellable gate reaching a plan as a named hole |
| B2 | No join target, no closure rule | §2.5, §6 inv. 12 | a `ParameterTable` row whose source is superseded, warned from inside a pinned run |
| B3 | Twenty-three `_mm` fields | §2.3.1, §6 inv. 7 | `7/8"` as `22225` + lexeme; 13 × 177.8 closing on 2314.575 |
| B4 | Tied ranks | §2.6 | two builds of one store producing one hash |
| B5 | Four undefined types | §3.3, §3.4, §3.6, §3.8 | the string line; a post insert keyed to `corner`; `POST LENGHT-(DEPTH+7)` |
| B6 | Unconditioned rows | §3.8.1 | `Figures based on 4x4 hole=10"… both 30" deep` as a fallback, warned, not asserting six brackets |

### Your own list, for completeness

| # | Yours | Our position |
|---|---|---|
| K1 | Revoke `cross_family_verified` | **Please do.** It drops 324 facts out of promoted; an honestly empty set is worth more to us than a falsely full one. |
| K2 | poppler over Pillow | Agreed without reservation. A crop path depending on an optional, git-ignored package that returns `False` when absent is a correctness problem wearing a performance problem's clothes. |
| K3 | Render cost unmeasured | Yours. But see K4. |
| K4 | No cell bounding box on any reading | **The single item we most want prioritised — above K3.** A reviewer shown a crop without the cell outlined is doing an unbounded task, and the entire throughput argument for the review queue assumes a binary one. |
| K5 | No human reading exists | Understood, and it is why N18 is ranked the way it is. |
| K6 | Six CAD pages with no `page_image` row | Yours. Flagged, not guessed at — the right call. |
| N-obs-1 | Fourteen `same_content_as` groups | §7.2 — schema or curation? Your call, but tell us which. |

---

## 9. Deliberately not closed

### 9.1 Gates — out of scope, and named

`FenceModel` and `PanelSpec` model **no gate**. A gate filed as a `FenceModel` is a
**defect**, not an approximation. Publish one as a `Gap` with
`kind = "unmodellable_entity"`.

This is exactly what you asked for and we want to be explicit that we understood
why: if gates are left implicit, a curator files one as a fence model, it validates
clean, and every fact you listed is silently lost — including swing direction and
latch height, the two that matter for pool-barrier compliance.

**Gate *hardware* is an ordinary `Part` and stays publishable.** Only the gate
**model** is out of scope. `gate_hardware` is a spine part type; hinges, latches,
drop rods and gate posts publish exactly as any other part does, with their spec
fields and provenance. Your review is right that a curator could read §9.1 as
excluding them and drop the one gate table this corpus publishes cleanly —
`Product Description | Available Materials | Support Gates Up To`, with ratings of
35, 75, 100 and 150 lbs across ten entries. **Publish it.** What is missing is not
the hinge; it is the `gate.*` namespace that would let a predicate compare a hinge's
rating to an assembled leaf's weight. The parts are data we want now; the selection
mechanism is what waits.

Your `GateModel` sketch is recorded as the **agreed target shape**, not a proposal
awaiting a verdict, so it is not renegotiated when it comes into scope:

```text
GateModel {
  leaf          PanelSpec                    this half already works
  leaves        [Leaf{ role: active | fixed }]
  opening_rule  leaf-to-opening delta, by leaf count
  clearances    { hinge_mm, latch_mm, between_leaves_mm, ground_mm }
  operation     { swing, handing, hinge_side, latch_side }
  hardware      [HardwareSlot{ kind, mounted_on, side_or_leaf_role,
                               placement, quantity_rule, requirement }]
  bracing       variant axis, with an explicit prohibited value
  post_role     gate → §3.4's for_post_roles
}
+ a gate.* predicate namespace
+ compliance_regime as a condition dimension (pool_barrier, self_closing, …)
```

The four things a `FenceModel`-with-an-option-axis workaround cannot carry —
handedness, swing direction, the fixed leaf, hinge selection by leaf weight — are
the four we consider decisive, and three are pool-barrier safety facts.

**We accept the honesty of our own position:** gates are missing from the *engine*,
not only from the contract. Naming them out of scope is a way of not losing the
data, not a way of pretending the hole is small.

### 9.2 Stock length does not yet constrain layout

A part may now declare `nominal_length_mm`, and you should publish it — every
catalogue prints it and it is true. But making a 94″ Columbia rail *determine* a
94″ bay is a change to the fitting arithmetic with real consequences, and it is a
follow-on rather than part of this round. You observed the relationship correctly;
we are not implementing it yet.

### 9.3 Site materials

`site_material` stays reserved and unimplemented. Concrete and gravel appear in
your `scope: site` and `scope: footing` steps, and those steps will publish and
render — but they produce no BOM line yet. Stated so it is a decision rather than
something you discover.
