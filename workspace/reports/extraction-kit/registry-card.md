# Registry card — the closed vocabularies

Attach this alongside the source PDF. These are the **only** permitted values for the
fields named. If a source concept does not fit one of these, do not invent a value:
record it under `registry_proposals` with the source's own wording, and leave the field
`null`.

Every value below is current as of 2026-09-15.

---

## Units

```
UnitCode        mm | mm2 | mm3 | each | gram_milli | cent
              | second_milli | pa_milli | degree_milli
Quantity        { amount_milli: int, unit: UnitCode, value_raw: [str] }
```

`amount_milli` is **thousandths of the unit**. One inch = `25400` with unit `mm`.
Conversion factors, exact: `1 in = 25.4 mm`, `1 ft = 304.8 mm`, `1 lb = 0.45359237 kg`,
`g = 9.80665 m/s²`, `1 psi = 6894.757293168361 Pa`.
Durations use `second_milli`, pressures `pa_milli`, angles `degree_milli`, plain counts `each`
(so "two pieces" is `{amount_milli: 2000, unit: "each"}`).

`value_raw` always carries the source's own characters, unmodified.

## Source class

```
SourceClass     sealed_approval | tested_report | industry_standard
              | manufacturer_installation_instruction | spec_sheet
              | marketing | company_authored | ai_proposal
```

## Task — what a parameter decides

```
TaskCode        structural_parameter | component_dimension
              | installation_step | product_description
```

## Parameters that already publish

```
footing_depth_mm · footing_diameter_mm · max_span_mm · footing_schedule
```

`max_span_mm` means a **structural maximum**. A nominal or typical post spacing printed
in a catalogue is **not** a `max_span_mm`; record it under `registry_proposals` as
`post_center_spacing` with the source's own words.

## Things — components, models and pairings

**These are draft targets.** Several have no publisher on our side yet. Record them anyway:
a draft tells us what the builder has to accept, and that is a question we cannot answer
without one. Leave every `id`, `version` and `*Ref` as `null` and list them in
`withheld_fields`.

```text
PartType {
  key        "rail" | "post" | "slat" | "screw" | "post_cap" | "hinge" | "latch" | …
  namespace  "shared"              the negotiated spine — never mint into it
           | "mfr/<manufacturer>"  where a manufacturer's manual invents a kind
           | "<tenant>"            a company's own
  parent     PartTypeRef | null    a new kind inherits by sitting in the same
                                   kind of place, not by a per-type rule
  label_i18n { en }
}

Part {
  id                    null — never invent one
  version · status      draft | active | retired
  type                  PartTypeRef → the PartType key above
  name_i18n             { en }          the name as the source prints it
  spec                  [SpecField]
  cites                 [SourceRef]     null here; page + quote instead
}

SpecField {
  key    "width_mm" | "height_mm" | "nominal_length_mm" | "colour" | "material" | …
  agree  == | != | <= | >= | in | supplies
  value  Quantity | Token
}
```

A parts table row — a quantity, an item name and a dimension tuple — is a `Part` with
`SpecField`s, one per dimension. `2" x 6" x 71"` is three fields, not one string, and you
say which axis is which only if the source does. If it does not, record the three values in
printed order and file a `Gap` saying the axes are unlabelled.

```text
FenceModel {
  id · version · status         null
  name_i18n                     { en }
  grade                         residential | commercial | industrial
  height_support                Continuous(min,max,step) | Discrete([heights])
  option_axes                   [Axis{ key, kind: enum|numeric, values }]
  post                          PostSlot | null      null means NO OPINION
  cites                         [SourceRef]
}
```

A catalogue page that names a style and lists the heights, widths, colours and post it
takes **is** a `FenceModel` draft. Record it as one. Its colours and finishes are an
`option_axis`, not loose names.

```text
Combination {
  id       null
  members  [PartRef@version]   validity scoped to EXACTLY these
  claims   [ParameterTableRef]
  cites    [SourceRef]
}
```

**This is where a pairing goes.** A grid headed *"which post goes with which section"*, a
cap that fits one post size, a hinge sold only with one gate — each printed pair is one
`Combination` draft with both members named in the source's own words. Transcribing the two
codes as separate claims and never joining them throws away the only thing the page exists
to say.

```text
ParameterTable {
  parameter    "footing_depth_mm" | "footing_diameter_mm" | "max_span_mm" | …
  scope        EntityRef → Part | FenceModel        null
  task         TaskCode
  hit_policy   unique | priority | collect_min | collect_max
  value_type   quantity(<UnitCode>) | token(<closed set>)     declared ONCE
  domain       { exposure_category: [B,C,D], hvhz: [true,false], … }
  domain_basis measured | declared
  rows [ { conditions · condition_basis: stated|assumed · value · valid_from · valid_until } ]
  uncovered [ … ]
}
```

Do not default `hit_policy` to `unique` or `uncovered` to empty. If the source does not say
which reading wins when two rows match, leave it null and file a `Gap`.

```text
Joint  { kind: butt|channel|groove|bracket|overlap · channel_depth · insertion_margin
         · shared_host_gap · gap_reason }
Member { key · base_ref · top_ref · joint · base_engagement · top_engagement
         · gap_after (MAY BE NEGATIVE — that is an overlap) · face_offset
         · continuity: per_bay|continuous }
```

Use these only where the source actually states how two pieces meet — a channel depth, an
insertion margin, an expansion gap. Do not infer a joint from a drawing that merely shows
two parts touching.

## Condition dimensions — the only keys `conditions` may use

```
code_edition · exposure_category · fence_height · frost_depth_mm · hvhz
jurisdiction · post_role · slope_method · wind_speed_mph
```

`fence_height` carries the source's own lexeme (`8' tall`), not a number.
A condition may be recorded **only** where the source states it. Never infer one.

## Steps

```
AssemblyStep.kind    assembly | installation | preparation | part_modification | maintenance
AssemblyStep.scope   panel | bay | post | run | site
requires[].kind      after | not_before | before | exclusive_with
SlotTarget           PanelSlot(path) | PostSlot(key) | Footing(hole|gravel|concrete|rebar)
                   | SiteFixture(string_line|stake|batter_board) | Elapsed(Quantity)
                   | Reused(slot_path) | None
```

**One step per instruction, not one per heading.** A numbered heading that contains five
bullets is five steps, because scope varies bullet by bullet: "insert post in hole" is
scope `post` and "fill hole with concrete" is scope `post` with slot `Footing(concrete)`.


## Warnings and prohibitions — NOT steps

```
Warning { code · text_i18n · applies_to · cites }
```

An instruction that tells the installer **not** to do something, or names a hazard, is a
`Warning`, **never** an `AssemblyStep`. "Never strike the PVC post without a wood support"
is a Warning. "Do not return the product to the store" is a Warning. Typing either as a
step with `kind: installation` is a defect — it turns a prohibition into an action.

Put them in `step_4_mapping.warnings`, not in a procedure's `steps`.
There is no closed `code` registry yet: leave `code: null` and propose one, once, naming
the class of hazard rather than the sentence.

## Gaps

```
Gap.kind        unmodellable_entity | uncovered_condition | unsatisfiable_requirement
              | unquantified | missing_value | unmapped_part_kind
              | disputed{on: value|conditions} | illegible_source
Gap.closes_by   knowledge | planning | schema
Gap.severity    informational | warns_line | blocks_line
```

## Curation

```
curation_level  0 = machine reading, nobody has checked it     ← always use this
                1 = two independent model families agreed
                2 = a person reviewed it
```

You are producing level **0**. Never claim otherwise.
