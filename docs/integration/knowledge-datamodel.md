# Knowledge data model — entities, relationships, invariants

> ## ⚠ SUPERSEDED — v0.1, kept for the audit trail
>
> **Read [`knowledge-datamodel-v0.2.md`](knowledge-datamodel-v0.2.md) instead.**
>
> This document was audited by the Knowledge team in `audit-response-v0.1.md`, and
> seven of its ten §7 questions surfaced a change. It is kept unedited below the
> line so the audit can be read against what it actually reviewed. Everything still
> true is restated in v0.2; where the two disagree, **v0.2 is current**.
>
> Four things here are now known to be wrong, not merely incomplete: invariant 5
> (a warning lives on its step — 19.9% do), invariant 9's namespace axis (tenant,
> not manufacturer), `Coverage`'s four literal kinds, and `scope: panel | bay` for
> assembly steps.

```text
Status:    SUPERSEDED by knowledge-datamodel-v0.2.md. Audited 2026-08-24.
Was:       Proposal, for THIS TEAM to audit. Written by the Planning & BOM team.
Purpose:   so you can check it against the data you actually hold and tell us
           what it cannot express. §7 lists what we most want challenged.
Outcome:   §7 was answered in full. See audit-response-v0.1.md, then
           audit-disposition-v0.1.md, then knowledge-datamodel-v0.2.md §8 for
           the map from each finding to where it landed.
```

---

## 1. The three tiers

Everything below is in exactly one of three tiers, and the tier decides who may
change it.

| Tier | What | Schema owned by | Instances authored by |
|---|---|---|---|
| **1 · Shared vocabulary** | The words both sides use | Planning, negotiated | both |
| **2 · Definitions** | Products and panels, in identical types | Planning | you, for manufacturer things |
| **3 · Private** | Evidence here, commerce there | each side its own | each side its own |

The placement test: *would this be the same answer on a different project, for a
different company?* Yes and yes → tier 2. Yes but only for one company →
private. Neither → private.

**Why Planning owns the schemas that cross.** These types exist because that
engine computes with them — a frame slot carries an engagement depth because the
cut length needs one. A field you invented that Planning cannot consume would be
a field nothing reads. The corollary is a real constraint on them: they cannot
change a shared type unilaterally, because you will have authored instances
against it.

---

## 2. Tier 1 — the shared vocabulary

Small, stable, and imported by both sides as a package.

```text
PartType {
  key          "rail" | "post" | "slat" | "screw" | …
  namespace    "shared" | "<tenant>"     so two companies may both have a "clip"
  parent       PartTypeRef | null        a new kind inherits behaviour
  label_i18n   { en, he, … }
}

SpecField {
  key     "width_mm"
  agree   == | != | <= | >= | in | supplies
  value   38 | null
  unit    "mm" | null
}

Quantity   { amount_milli: int, unit: mm | mm2 | mm3 | each | gram_milli | cent }
SourceRef  { id }                    opaque to Planning; you own what is behind it
Authorship { third_party_authored | manufacturer_approved | manufacturer_uploaded }
VersionRef { object_id, version, content_hash }
```

Three things about `SpecField` that matter when you publish one:

- It reads left to right as a sentence about the item: `item.<key> <agree> <value>`.
  One direction always.
- **`agree = supplies` carries no value.** A part cannot declare its length: the
  same rail serves a 2400 bay and an 1800 one, so the bay resolves it. Publishing
  a length literal on a rail is wrong, not merely unnecessary.
- Dimensions are **derived** from spec fields, never stored beside them. Do not
  publish a `dimensions` map — it would be a second authority over the same number.

`Authorship` exists because there is no fence data feed anywhere. Nobody
publishes a machine-readable panel definition — not through GS1, ETIM, bSDD or
IFC. Everything upstream is a PDF, so a definition you publish is *your reading*
of a manufacturer's document, and a company adopting it should be able to see
that. Default is `third_party_authored`.

---

## 3. Tier 2 — the definitions you publish

These are Planning's existing types. Nothing here was invented for the boundary,
which is why it can work at all.

### 3.1 Part — what a piece is

```text
Part {
  id          "chesterfield.top-rail"
  version     3
  status      draft | active | retired
  type        PartTypeRef              → "rail"
  name_i18n   { en, he }
  spec        [SpecField]
  authorship  Authorship               ← added for publishing
  cites       [SourceRef]              ← added for publishing
}
```

A part says what the piece **is**. It never says where it goes, how it joins, or
which way up it runs — those are facts about a panel.

### 3.2 FenceModel — a configurable family, not one panel

```text
FenceModel {
  id, version, status
  name_i18n
  grade           residential | commercial | industrial
  height_support  Continuous(min,max,step) | Discrete([heights])
  option_axes     [Axis{key, kind: enum|numeric, values, available_when}]
  default_spec    PanelSpec
  variants        [Variant{condition, spec}]   authored order, first match wins
  layout_policy   [PolicyContribution]
  post            PostSlot | null              null = NO OPINION
  assembly        [AssemblyStep]
  authorship, cites
}
```

A model carries **several panel specs**, chosen by condition. Vertical-or-
horizontal listing is an axis with two variants — same part library underneath,
different assembly.

`PolicyContribution{param, value, knowledge_type, authority}` is the model
publishing its own parameters as knowledge, with authority **per contribution**:
a manufacturer maximum span is a hard constraint, a nominal width is a
preference, and one authority for the whole policy would make one of them wrong.
Your `ParameterTable`s land on the same precedence ladder and may contend with it.

### 3.3 PanelSpec — the structure

```text
PanelSpec {
  frame    [FrameSlot]
  infill   InfillSpec | null
  fixings  [FixingRule]
}

FrameSlot {
  key               "bottom_rail"
  orientation       horizontal | vertical
  placement         FromBottom(offset) | FromTop(offset) | Fraction(permille)
                    | Distributed(count, count_param, insets)
  joint             butt | channel | groove | bracket | overlap
  channel_depth_mm  how deep this member RECEIVES another
  insertion_margin_mm  clearance so a member can be tipped in
  requirement       PartRequirement
  contains          [ContainedSlot]
}

Member {                             one repeat of the infill pattern
  key, base_ref, top_ref             ← which frame slots it runs between
  joint
  base_engagement_mm, top_engagement_mm   ← how far it seats into each
  gap_after_mm                       MAY BE NEGATIVE — that is an overlap
  face_offset_mm                     + front face, − back face (shadowbox)
  requirement, contains
}

InfillSpec {
  orientation    vertical | horizontal
  pattern        [Member]
  justification  start | end | center | spread_to_fit
  excess         truncate | space | trim_last | extension_clip
  edge_margin_mm
  supply         components | assembly     bought as pieces, or as one unit
}

FixingRule {
  key
  basis          per_member_crossing | per_member | per_end_member
                 | per_gap | per_frame_member | per_panel
  qty_per_basis, qty_param
  requirement
}
```

**Orientation is load-bearing, not descriptive.** `per_member_crossing`
multiplies infill members by frame members, which is a real crossing only when
the two run at right angles. Get the orientations wrong and the arithmetic still
produces a number, and the number is a fiction.

**The joint is spent on the cut length, once.** A member cut between two frame
members is `(top_pos − base_pos) − (half each thickness) + engagements`. The
elevation is drawn from the same number, because two calculations would drift.

### 3.4 ContainedSlot — a part inside a part

```text
ContainedSlot {
  key          "channel"
  relation     reinforces | lines | sleeves | insulates   closed vocabulary
  coverage     Full()                    length follows the host
               | Fixed(length_mm)        a 92" channel in a 96" section
               | Fraction(permille)
               | At([offsets_mm])        discrete inserts
  required_by  null = always | a knowledge param a rule may set
  requirement  PartRequirement
  contains     [ContainedSlot]           recursive; depth capped at load
}
```

Your corpus has at least three of these and they are not the same shape: a
steel-reinforced bottom rail (92″ channel in a 96″ section — **not** full
coverage), post reinforcement required only under some wind conditions, and a
hat-shaped insert whose recorded dimensions your own verification found
contradicted by the source.

**The line that keeps this general:** the structure says a rail contains a
channel; the catalog says whether a company buys that as one SKU or two. Do not
model containment as a kit — a pre-reinforced rail and a rail-plus-channel are
the same fence and different purchases.

### 3.5 PartRequirement — which item fills a place

```text
PartRequirement {
  part_id        "" means this slot names no part
  role           filled from Part.type during resolution — never authored
  qty
  length_rule    centre_to_centre | between_frame | panel_height | …
  overlap_mm
  option_axis, sku_by_option
  eligibility    Eligibility{ members | predicate }
}
```

Four shapes, derived from the fields rather than stored:

| Shape | When | Why you would publish it |
|---|---|---|
| `part` | names a `part_id` | the normal case |
| `authored_predicate` | a rule on the slot | facts a part **cannot** state |
| `authored_members` | SKUs named directly | not yours to publish — tenant commerce |
| `unspecified` | neither | refused at load |

**`authored_predicate` is the important one for you**, and there are two
established uses:

```text
# a routed post: the rails pass THROUGH holes punched at the factory
item.routed_at_mm  ==  panel.rail_positions_mm

# a contained part must fit its host's cavity
item.width_mm      <=  host.cavity_width_mm
```

In both, the part must agree with a fact about something it has not been placed
in, so a plain spec field cannot say it. Expressing routing as a literal
`[150, 1650]` would delete every 2100 mm fence.

A slot naming a part may **not** also author what that part is — resolution
overwrites both fields, so a document carrying both validates clean and then has
its authored half deleted silently.

### 3.6 AssemblyStep — how it goes together

```text
AssemblyStep {
  key
  kind        assembly | installation
  scope       panel | bay              ← so a step can place a post
  slots       [slot_path]              "bottom_rail" · "bottom_rail/channel"
  requires    [step_key]               ← what must PRECEDE this
  warnings    [{code, params} | text]  ← attached to the step, never free
  cites       [SourceRef]              ← the figure
  text_i18n
}
```

Three of those fields are additions we are proposing **because your curation
schema already models them and the engine cannot yet hold them**:
`cur_step_requires` is prerequisite edges, `cur_step_warnings` binds a warning to
its step, and your own note says there is no table in which a warning can exist
detached from the action it governs.

Without `requires`, publishing a procedure flattens prerequisite edges into list
position, and the difference between *"must come after"* and *"merely printed
after"* is lost. That distinction is the whole reason the order is not
hard-enforced.

**The governing invariant**, and it is the same shape as `Σ(parts) ≡ BOM`: every
member of the panel — including contained ones — is placed by exactly **one**
step, or reported as `unplaced`. A model that says how it goes together while
quietly omitting half its parts is worse than one that says nothing.

`scope: bay` is a proposed addition, because most of an installation guide is
about posts and footings, and today a step can only place panel slots.

### 3.7 ParameterTable — conditional values

```text
ParameterTable {
  parameter     "max_span_mm"
  scope         EntityRef → Part | FenceModel
  task          TaskCode                    see the source policy
  hit_policy    unique | priority | collect_min | collect_max
  domain        { exposure_category: [B,C,D], hvhz: [true,false] }
  rows [ { conditions, value: Quantity, value_raw: "88\"",
           source_class, curation_level, admitted_by, cites } ]
  uncovered [ { … } ]
}
```

Binding: no two rows may match the same point under `unique`, and every
uncovered point of the domain is listed rather than omitted.

### 3.8 Combination — a certified assembly

```text
Combination {
  id       "chesterfield-6ft-expC-30in"
  members  [PartRef@version]      validity scoped to EXACTLY these
  claims   [ParameterTableRef]
  cites    [SourceRef]
}
```

Borrowed from how matched HVAC systems are certified: the rating applies to the
combination, not the members, and swapping one invalidates it rather than
inheriting it. A Chesterfield 6 ft panel at Exposure C with 30″ footings is that
kind of object.

---

## 4. Tier 3 — your private model (a sketch, binding nothing)

Your `docs/curation/` proposal already covers most of this and is more
considered than anything we would write. For orientation only, what we assume
exists behind the boundary:

```text
documents · document_versions · pages · elements · tables · assets · crops
Claim + conditions + evidence          the sourced rows
Review · promotion rules               the human gate and its scaling escape
Conflict · Gap                         disagreement and absence, both as rows
Procedures + steps + requires + warnings   → become AssemblyStep on publish
Entities · aliases · relations         identity across spellings
Source policy                          task × source class × role
retrieval units / index                discovery only, never cited
```

Two connections to tier 2, and only two:

- An **accepted claim** becomes a `ParameterTable` row.
- A **curated procedure** becomes a `FenceModel.assembly` list.

Everything else in this tier stays yours and is never consumed.

---

## 5. Relationships

| From | To | Meaning |
|---|---|---|
| `Part.type` | `PartType` | Filed as. Many parts, one type. |
| `Part.spec` | `[SpecField]` | What it is. Dimensions derive from here. |
| `PanelSpec` | `[FrameSlot]` `InfillSpec` `[FixingRule]` | What the panel is made of. |
| `FrameSlot.requirement` | `Part.id` **unpinned** | Which part. No version — generation resolves latest active and the run stamps what it resolved. |
| `Member.base_ref` / `top_ref` | `FrameSlot.key` | Structure: which frame members it runs between. Sibling reference. |
| `Member.engagement` | `FrameSlot.channel_depth` | Structure: how much disappears into the host. Engagement + margin must fit the depth. |
| `FrameSlot.contains` | `[ContainedSlot]` | Structure: parent-child. Distinct from spanning. |
| `ContainedSlot.requirement.predicate` | `host.*` | Fits inside — checked, not assumed. |
| `PartRequirement.eligibility.predicate` | `panel.*` | Agrees with a fact about the bay. |
| `AssemblyStep.slots` | slot paths | Places a member. Every member placed exactly once. |
| `AssemblyStep.requires` | `[step_key]` | Partial order. List position is presentation. |
| `FenceModel.variants[].condition` | `option_axes` | Which panel spec applies. |
| `ParameterTable.scope` | `Part \| FenceModel` | What the value is about. |
| `Combination.members` | `[Part@version]` | Validity scoped to exactly these. |
| any definition | `[SourceRef]` | Cites. The only reference resolving back into your side. |
| accepted `Claim` | `ParameterTable.rows` | Private → shared. One of two crossings. |
| curated procedure | `FenceModel.assembly` | Private → shared. The other. |

---

## 6. Invariants

1. **Dimensions are derived, never stored twice.** One authority per number.
2. **A part cannot declare its length**, nor any fact about a panel it has not
   been placed in. Those go on the slot as a predicate.
3. **Naming a part and authoring what it is are exclusive** on the same slot.
4. **Every member is placed by exactly one assembly step, or reported unplaced.**
5. **A warning lives on its step.** Never detached.
6. **No two parameter rows match the same domain point** under `unique`; every
   uncovered point is listed.
7. **Integers only across the boundary**, thousandths of the named unit, with the
   verbatim source lexeme travelling alongside.
8. **Every published value carries a resolvable `SourceRef`** and an honest
   `Authorship`.
9. **Extension part types are tenant-namespaced** and their parent chain
   terminates in the shared spine.
10. **Structure is authored, not extracted.** An installation guide describes a
    joint in prose and figures; no table reader produces a `PanelSpec`. Curators
    write these with citations.

---

## 7. What we want you to challenge

This is the section the document exists for. We have not held your data; you
have. Please tell us where it does not fit.

**Specific things we suspect:**

1. **Tongue-and-groove pickets.** `gap_after_mm` may be negative, which covers
   the pitch of an overlap. Is a T&G profile adequately a part spec, or does the
   interlock need modelling?
2. **Racking.** A style racks 10° on slope. Is that a `PolicyContribution`, a
   spec field on the model, or something with no home?
3. **`Coverage` variants.** We proposed four. Does your reinforcement data need a
   fifth — every N mm, or only over gate bays?
4. **Bay-scope assembly steps.** We propose `scope: bay` so a step can place a
   post. Does that cover installation guides, or do steps need to place things
   that are neither panel nor bay — a footing, a gravel base, a string line?
5. **Warnings.** We propose `code + params` with a text fallback. Your
   `cur_step_warnings` stores raw text and an element id. Is a code vocabulary
   realistic for warnings extracted from prose, or should text be primary?
6. **Multi-document definitions.** A Chesterfield panel's structure is in the
   install guide and its wind table is in an approval — different documents,
   different units, no shared identifier. Does `cites: [SourceRef]` per field
   carry enough, or does a definition need document-level provenance too?
7. **Procedures that are not per-model.** "Let footings cure overnight" belongs to
   a manufacturer, not a panel. Where does a procedure with no model go?

**Structural questions:**

8. Is anything in §3 **unrepresentable** for material you already hold?
9. Is anything in §3 **over-specified** — a field you would have to invent data
   for rather than read it?
10. Are the invariants in §6 ones you can actually enforce at publish time, or do
    any of them need information you will not have?

**How to send it back.** A gap per item, with the document and page that
motivates it, is worth more than a general objection — the same standard your own
curation acceptance criteria hold themselves to. Anything you find that changes
tier 1 or tier 2 changes the contract, which is a negotiation rather than a
request.
