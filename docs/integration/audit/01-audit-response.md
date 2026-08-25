# Audit response — `knowledge-datamodel.md` §7

```text
Status:    Response to a proposal. From the Knowledge team (this repo).
Answers:   All ten questions in knowledge-datamodel.md §7. None deferred.
Standard:  A gap per item, with the document and page that motivates it — the
           standard §7 asked for, and the one docs/curation/05-acceptance-criteria.md
           holds this repo to.
Method:    workspace/indexes/evidence.db queried read-only on 2026-08-24 against
           the extraction run of 2026-08-20: 144 documents, 2,147 pages,
           81,794 elements, 1,976 facts, 1,225 table readings. Sources were
           re-read against the PDF, and page images were looked at where the
           page is a scan. Nothing under manuals/, china/, data/ or workspace/
           was modified.
Reads with: 05-acceptance-open-questions.md (every item needing a decision, in one
           list), source-refs-design.md (the unblocked work, now designed).
```

## 0. Before the answers — three things

**The architecture is right and the vocabulary is short in specific, findable
places.** Nothing below asks you to redesign anything. `PanelSpec` really can
express a Chesterfield panel, `ParameterTable` really is the right shape for a
conditional value, and the resolution/discovery split really does make retrieval
quality a curation cost rather than a correctness risk. What we found is that
seven of the ten questions surface a change, and in almost every case the reason
is the same: **the corpus is stranger than either team assumed.** Racking is
stated in six mutually unconvertible units. Reinforcement extent is anchored to a
footing depth that is itself conditional. Four fifths of the warnings in this
corpus are attached to no step. None of that is a flaw in the types; it is what
holding the data tells you and reading the schema does not.

Two of the findings below are large enough to change what a first snapshot can
contain, and both are about *sources* rather than *shapes* — §2.6 and §3.

**`docs/curation/` is not superseded by any of this, and we have not treated it
as a proposal to be overruled.** `knowledge-datamodel.md` §4 places it in tier 3
and says everything there stays ours and is never consumed. We read that as
settled and have acted on it: this response cites the curation schema as our
internals, not as something under negotiation. The one behaviour change that
proposal makes to existing code — removing `cross_family_verified` from
`table_review.PROMOTABLE`, which today lets two agent readings promote a fact
with no person involved — is ours to make, inside the boundary, and we intend to
make it. `rationale.md` §1 is a fair account of what leaving it in costs.

**On the revision.** If anyone read a copy of the integration directory before
2026-08-24, three things moved, and the README records exactly what: the catalog
left the snapshot, definitions are published rather than only claims, and a claim
in `rationale.md` §6 was wrong and is corrected. We want to be explicit that the
corrected claim mattered to this audit. The earlier draft said neither system
could express *"this product can serve as a top rail"* or *"a panel has two post
slots"*. Had that been true, this response would have been a request to design a
structure model. It was not true — `PartType` and `PanelSpec` have always
existed — so this is instead a list of specific, bounded gaps against a model that
works. That is a materially different conversation, and the correction is what
made it possible.

---

## 1. The answers, at a glance

| # | Question | Verdict | Changes tier 1/2? |
|---|---|---|---|
| 1 | Tongue-and-groove pickets | Representable — `gap_after_mm = 0` — but the corpus publishes two widths for one part and never says which is coverage. One real vocabulary gap: **handedness**. | Tier 2, small |
| 2 | Racking | **Needs a tier-2 change.** None of the three homes offered fits: it is conditional, it changes structure, and the corpus states it in six incompatible units. | **Tier 1 and 2** |
| 3 | `Coverage` variants | **A fifth kind is needed and it is neither one you guessed** — both have zero instances. Coverage is an *anchored interval*, sometimes anchored to a conditional value. | **Tier 2** |
| 4 | Bay-scope assembly steps | **`scope: bay` is necessary and insufficient.** 44–51% of steps in real guides are neither panel nor bay. Thirteen other scopes found. | **Tier 2** |
| 5 | Warnings | **Text must be primary.** 226 distinct warnings, 1,038 instances, and only 19.9% are attached to a step. Invariant 5 is false against this corpus. | **Tier 2** |
| 6 | Multi-document definitions | **Necessary, not sufficient.** An opaque `SourceRef` carries zero admissibility bits into a snapshot, and 40.7% of promoted facts already cite a superseded document. | **Tier 2, plus one tier-1 field** |
| 7 | Procedures that are not per-model | **No home.** Four classes found, including cross-manufacturer procedures owned by no product at all. | **Tier 2** |
| 8 | Anything unrepresentable? | **Six things**, largest first: units, validity windows, design basis, jurisdiction, gates, dual lexemes. | **Tier 1 and 2** |
| 9 | Anything over-specified? | **Four fields we would invent data for**, and one invariant that is inverted for this corpus. | Tier 1, one item |
| 10 | Invariants enforceable at publish? | **Five yes, two enforceable-but-wrong, two half, one false.** Invariant 5 is the false one. | Tier 1, one item |

And one finding that is not one of the ten questions and is the most consequential
thing we found: **the shipped source policy has no class for an installation
manual**, which is 44.6% of every fact in this store. §3 below.

---

## 2. The answers

### 2.1 Q1 — Tongue-and-groove pickets

> *`gap_after_mm` may be negative, which covers the pitch of an overlap. Is a T&G
> profile adequately a part spec, or does the interlock need modelling?*

**Verdict: representable, and the premise is inverted.** We found no T&G product
whose pitch is *less* than its published nominal width. The overlap sits outside
the catalogue number, so the correct value is `gap_after_mm = 0`, not a negative.

**Where the arithmetic actually closes.** Once, in one document.
`manuals/barrette-outdoor-living/structural/catalyst-madison-horizontal-privacy-sku-sheet.pdf`
carries three sibling SKUs sharing one rail, with a per-panel bill of material:

| Page | Verbatim | Read as |
|---|---|---|
| p2 | `4' x 6' Madison Horizontal Panel (441/2"H)` … `5 \| T&G Boards \| 7/8" x 7" x 661/2"` | text layer, `element-48fe7a742f-0013` |
| p3 | `5' x 6' Madison Horizontal Panel (581/2"H)` … `7 \| T&G Boards \| 7/8" x 7" x 66 1/2"` | text layer, `element-95b6934074-0013` |
| p4 | `6' x 6' Madison Horizontal Panel (721/2"H)` … `9 \| T&G Boards \| 7/8" x 7" x 66 1/2"` | text layer, `element-0b030f264c-0025` |

Derived by us, stated nowhere: `(58.5 − 44.5) / (7 − 5) = 7.000 in` and
`(72.5 − 58.5) / (9 − 7) = 7.000 in`. **Pitch equals nominal width exactly.**
Back-substituting closes the panel and yields a rail engagement of 1.25 in per
end — also stated nowhere. The Select sub-family on p5–p8 replicates it
independently with a different board and rail.

Independently corroborated on a different manufacturer's sealed drawing:
NOA-23-0314.05 sheet 4 of 9 states `MAXIMUM POST SPACING NOT TO EXCEED 96 1/8"`
with a `5 X 5 X 107 ROUTED POST`, giving a 91.125 in clear opening; and
`manuals/barrette-outdoor-living/catalyst-fence-accents-hardware-sku-sheet.pdf`
p6 (`element-1902ab6556-0004`) sells the fill kit for that span as
`503/4" x 7" (13 T&G Boards)`. `13 × 7 = 91`. Pitch is nominal again.

**The hazard, and it is a real one.** The same manufacturer publishes two widths
for one part on one PE-sealed sheet. On NOA-23-0314.05 p12, bill-of-material item
J reads `.875 X 7 X 62.75 TONGUE AND GROOVE PICKET` (OCR,
`element-eec96ec718-0046`), while the dimensioned elevation of that same item J
on that same sheet reads **`7 3/8"`** — read visually at 300 dpi, because OCR
recovered only the fragment `' DEGREES ENDCUTS`. The 3/8 in is the tongue.
Neither figure is labelled *nominal*, *coverage*, *effective* or *overall*, and
the sheet does not reconcile them. A curator who reads the drawing and sets
`gap_after_mm = 0` builds a panel 5% too wide. A curator who reads the catalogue
and sets `gap_after_mm = 0` is right. **Both validate clean.**

Everywhere else the corpus declines to state a pitch at all: the Bufftech 2014
spec chart has a `Picket Spacing` column and prints **`N/A`** for every T&G style
while printing real spacings for spaced-picket styles.

**What the model cannot express: handedness.** The interlock has a direction, and
the corpus says so:

> `Attach U-Channel to "tongue" side of first board, and "groove" side of last board`
> — `manuals/freedom-outdoor-living/FREEDOM-WEB-PrivacyKit_Ready-to-Assemble-Privacy-Vinyl-Fence-Install.pdf` p4

`Member` has `base_ref`, `top_ref`, `joint`, engagements, `gap_after_mm` and
`face_offset_mm` — no edge vocabulary. `FixingRule.basis = per_end_member` gets
the *count* right (two U-channels) and the *handedness* wrong, and a mirrored
panel validates. Searched `engagement`, `route depth`, `seats into`, `deep into
the rail` for a stated T&G interlock depth: **not stated anywhere in the corpus**.

**Proposed change (tier 2, small).** `Member` gains an optional
`profile_edges { start, end }` over a small open vocabulary
(`tongue | groove | square | ship_lap | none`), and `FixingRule` gains
`per_end_member_by_edge`. Alternatively `InfillSpec` gains a
`pattern_handedness` flag. Either is cheap; nothing else in §3 needs to move.

**Counter-argument.** One document in 2,147 pages lets the pitch be derived, and
handedness appears in one install guide. It is entirely defensible to say a T&G
profile *is* adequately a part spec, publish `gap_after_mm = 0`, and treat
handedness as an assembly-step instruction rather than a structural field. We
would accept that. What we would not accept is publishing a negative
`gap_after_mm` from the `7 3/8"` reading — the model permits it, the corpus does
not support it, and it fails silently.

---

### 2.2 Q2 — Racking

> *A style racks 10° on slope. Is that a `PolicyContribution`, a spec field on
> the model, or something with no home?*

**Verdict: needs a tier-2 change. None of the three fits.** Three separate
reasons, each independently sufficient.

**It is conditional, in a single printed cell.**

> `▼ Racks up to 10 degrees  3' and 4' high, 5 degrees 5' and 6' high`
> — `manuals/certainteed-bufftech/bufftech-catalog-2014.pdf` p29, read visually
> from `workspace/derived/doc-d70644123b57/pages/0029.png`; the OCR of the same
> region renders it as `Racks up | 10 degrees 3' and | 4' high, 5 degrees | and 6' high`
> at 76.52% confidence (`element-0d0c63f057-0005`)

A value that depends on fence height is a `ParameterTable`, not a scalar
`PolicyContribution`. And the same page carries `*Accents will reduce the amount
of rack` — an option-axis dependency the corpus states four times and quantifies
zero times. That is a `Gap`, and a real one.

**It is not a property of the infill.** Chesterfield racks 10° and Galveston 5°
with identical pickets, so it cannot be a picket spec field promoted upward.

**It changes structure, which is what rules out a spec field entirely.**

> `1. Enlarge holes in post to accept rails  2. Enlarge holes in rail to accept
> pickets  3. Shorten picket length`
> and `NOTE: Depending on severity of rack, post centers may need to be decreased`
> — `manuals/certainteed-bufftech/bufftech-fence-installation-guide-2024.pdf` pp42–43

Racking a section changes the routed hole size, the picket length, and — in that
last line — contends with `max_span_mm`, a parameter the engine already
multiplies against. A warning attached to a step cannot reach a parameter.

**The unit problem, which is the tier-1 half.** The corpus states racking in six
mutually unconvertible forms:

| Form | Verbatim | Source |
|---|---|---|
| Degrees, as a method threshold | `Racking Method — 10˚ or Less` | `bufftech-fence-installation-guide-2024.pdf` p42, `element-d5149646d7-0004` |
| Degrees, per style group | `▼ Racks up to 10 degrees` | `bufftech-catalog-2014.pdf` p29, visual |
| Inches of drop per section | `2” Standard` / `10” Standard`, column headed `Racking` | `manuals/industry-standards/Digger-Specialties-Polyvinyl-Fence-Brochure_Racking-Post-Spacing.pdf` pp9, 11, 13, 17, 19 |
| Inches over a named span | `This fence panel can rack up to 6” over an 8 ft. span.` | `manuals/weatherables/weatherables-3-rail-fence-installation-2024.pdf` p6, `element-27e100c8c3-0007` |
| Rise per foot | `• Follows varied terrain - racks 1 inch per foot*` | `manuals/freedom-outdoor-living/2024-Freedom-VF-Catalog-01-24_SpecialOrderCatalog.pdf` p4 |
| Both, with a conversion, for gates | `Rack gate to the desired angle. Max 8º of rack, or 1" per foot of width of gate` | `manuals/barrette-outdoor-living/install-racking-gate.pdf` p2, `element-54113aae09-0015` |
| A named method, no number | `Racking — Method of installing fence on sloped terrain. Fence posts and pickets are plumb, but the rails are secured at an angle so they parallel the grade.` | `bufftech-fence-installation-guide-2024.pdf` p48 |
| A method prohibition, no number | `The exception is the Even Stephen and Simple Simon fence styles. They should be only installed using the slope method` | `manuals/wam-bam/murphys-vinyl-fence-laws.pdf` printed p2 |

`UnitCode` is `mm | mm2 | mm3 | each | gram_milli | cent`. **Degrees cannot cross
the boundary.** Neither can `stepped_only` or `gates are not rackable`, which are
values a planner needs and which have no numeric form at all.

**Our own data disagrees with the source, which is worth showing you.** The 2014
catalogue says Chesterfield racks 10°. `data/certainteed-bufftech.json` line 117
says `"max_rake_angle_deg": "5 (accents reduce amount of rack); pickets
factory/field cut at 5-deg angle…"` — a hand-researched file that promoted a
picket **end-cut angle** into a model **maximum**. Two different quantities, one
field name. That field is also a string here, `null` on line 199 and `"7"` on
line 249. And the extractor's `racking_degrees` fact type holds **five rows in the
entire corpus**, all OCR-derived, all from the same catalogue page, one
mis-attributed and one silently dropping half its conditional.

**Proposed change.**
- *Tier 1:* add `deg_milli` to `UnitCode`, and allow `ParameterTable.rows[].value`
  to be a `Quantity` **or** a member of a closed enum, so `stepped_only` and
  `not_rackable` have a home.
- *Tier 2:* racking is a `ParameterTable` scoped to a `FenceModel`, conditioned on
  height and on option axes, not a `PolicyContribution` and not a spec field.

**Counter-argument.** Planning could require this platform to normalise everything
to degrees at publish time — 1 in/ft is 4.76°, 6 in over 8 ft is 3.58° — and the
unit problem disappears. We reject it for one reason: that conversion is an
`atan` **we** would be performing on a value nobody stated, and the result would
carry a `SourceRef` to a page that does not contain it. `value_raw` would say
`1 inch per foot` and `amount_milli` would say `4763`, and the two would not be
the same claim. Invariant 7 exists to make that visible; here it would hide it.

---

### 2.3 Q3 — `Coverage` variants

> *We proposed four. Does your reinforcement data need a fifth — every N mm, or
> only over gate bays?*

**Verdict: a fifth kind is needed, and it is neither of the two you guessed.**
Both guesses have **zero instances** in this corpus.

- *Every N mm.* Searched `every N feet`, `every other`, `every second`, `every
  third`, `one per`, `per lineal`, `linear foot`, `alternate post` across the 137 PDFs. No periodic-pitch reinforcement exists anywhere. Do not add
  `Periodic(pitch_mm)`.
- *Only over gate bays.* Also zero. What exists is conditioned on **post role** —
  corner, end, line, gate — never on a bay. §2.3.3 below.

**Your three named cases, verified.**

1. **The steel-reinforced bottom rail — confirmed, with a correction.** NOA
   23-0314.05 p12 (sheet 4 of 9), read visually from the page image, states
   `K U-SHAPPED G-60 STEEL CHANNEL X 92 | GALVANIZED STEEL`, leadered only to
   `L (BOTTOM)`. But the host is **94.5″, not 96″**: p10 gives
   `B 3.5 X 3.5 X 94.5 ROUTED RAIL` and `D ALUMINUM CHANNEL X 92 FOR 3.5 SQ. RAIL`.
   The 96⅛″ is the **bay** — `MAXIMUM POST SPACING NOT TO EXCEED 96⅛"` — not the
   rail. So it is a 92″ channel in a 94.5″ rail. And Chesterfield's own rail
   (`2 X 6 DECO RAIL`) carries **no length at all** on its sheet, which makes
   `Fraction(permille)` unauthorable there even in principle.
2. **Post reinforcement conditioned on wind — confirmed, in Weatherables rather
   than in the NOAs.**
   > `If your fence is over 6' tall or located in a high wind area, you must
   > reinforce the post with either concrete or an aluminum insert to at least 22"
   > above grade.` — p3
   The conditions are `over 6' tall` **or** `high wind area`. There is **no
   exposure category, no HVHZ flag and no mph figure on the condition side** — the
   mph figures elsewhere in the corpus are outcomes, not the trigger. So
   `required_by` pointing at a knowledge parameter works only if that parameter is
   `high wind area`, which is a phrase, not a value.
3. **The hat-shaped insert — confirmed, and it is this repo's own gap G16.** Sheet
   8 of 9 (p16) dimensions `D- HAT SHAPED INSERT` at a **2.750″ base with a single
   0.080″ wall**. The 4.500″ recorded against it belongs to items P/P1 and the
   0.036″ to item I.

**The cases that fit none of the four kinds.** All verbatim from PE-sealed
drawing sheets:

| Verbatim | Why no kind fits |
|---|---|
| `POST REINF. FULL LENGTH -1"` (sheets 7/9 and Brookline 2/2) | extent is *host length minus a constant*. `Full()` is wrong, `Fixed()` needs a literal the sheet does not give |
| `ALUMINUM REINFORCEMENT / POST LENGHT-1" - BREEZEWOOD / 48" - ALL OTHERS` | two coverage rules selected by model, in one cell |
| `18" EXCEPT BREEZEWOOD MODELS / POST LENGHT-(DEPTH+7)` | extent anchored to **grade and to footing depth** — and footing depth is itself a `ParameterTable` row, so the coverage depends on a conditional value |
| `PANEL STIFFENER 70 1/4"` inside `SIMTEK PANEL 70"` — SimTek NOA 24-0117.06 p6 | **the insert is longer than its host.** `Full()` has the wrong sign and `Fixed()` would validate a part that does not fit |
| `…to at least 22" above grade` — Weatherables p3 | a *minimum* extent measured from a datum outside the host |

**Proposed change (tier 2): replace the four kinds with an anchored interval.**

```text
Coverage = Span { from: Anchor, to: Anchor, at_least: bool }

Anchor = HostStart(delta_mm) | HostEnd(delta_mm)
       | Datum(grade | hole_base, delta_mm)
       | SiblingSlot(slot_path, delta_mm)
       | Param(key, delta_mm)
```

`Full()` becomes `Span{HostStart(0), HostEnd(0)}`; `Fixed(l)` becomes
`Span{HostStart(0), HostStart(l)}`; `At([offsets])` stays as it is for discrete
inserts. `Fraction(permille)` is dropped — it has no instance in this corpus and,
as case 1 shows, is unauthorable where the host publishes no length. Everything in
the table above becomes expressible, including the over-long stiffener, which
lands as `HostEnd(+6)` and is *visibly* an overhang rather than a silent
validation pass.

#### 2.3.1 The `relation` vocabulary is inadequate

`reinforces | lines | sleeves | insulates`. Measured against the corpus:
**`insulates` has zero instances**, and three relations are missing with material
behind each:

- `fills` — concrete poured inside a post, which the guides treat as
  interchangeable with an aluminium insert (`reinforce the post with either
  concrete or an aluminum insert`).
- `caps` — `F- INTERNAL POST CAP`, a part inside a part whose job is closure.
- `retains` — lock rings and bullet clips, which hold a member in its host and are
  neither reinforcement nor lining.

#### 2.3.2 `host.cavity_width_mm` is never published

The proposed predicate `item.width_mm <= host.cavity_width_mm` is well-formed and
**unusable**. The only `Inside Dimensions` in 2,147 pages belong to storage sheds.
Every profile in the corpus publishes an outside dimension and a wall thickness —
`5X5 POST` is `4.940` OD with a `0.170` wall — and never a cavity.

The predicate should therefore be written against a **derived** cavity
(`OD − 2 × wall`) with `insertion_margin_mm` accounting for the fit, and the
derivation must be visible rather than folded into a field name. Note that this is
the one place where §2.9.1's over-specified `insertion_margin_mm` becomes load
bearing — which is an argument for keeping it, provided its absence publishes as a
`Gap`.

#### 2.3.3 The run-level problem exists, and it is post role rather than gate bay

> `Ready-to-Assemble fence styles require post inserts in most post
> configurations (not needed in corner posts)` … `Pre-Assembled fence styles
> require … post inserts in every post`
> — `manuals/freedom-outdoor-living/2024-Freedom-VF-Catalog-01-24_SpecialOrderCatalog.pdf` p11

and Bufftech contradicts it directly: `Corner posts should be reinforced with
concrete and rebar`.

So whether a post is reinforced depends on its **role in the run** — corner, end,
line, gate — and two manufacturers disagree about the corner case. `ContainedSlot`
hangs off a `FrameSlot` inside a `PanelSpec`, and a panel does not know what kind
of post it is bounded by. Post role is not reachable from where the containment
lives.

**Proposed:** `PostSlot` gains role keying, so a `ContainedSlot` under it can be
conditioned on `corner | end | line | gate`. This is the same shape of problem as
§2.4's shared line post and §2.11's gate post, and one fix would serve all three.

**Counter-argument.** `Span` is more machinery than four literal kinds, and most of
the cases above could be published as `Fixed()` with a curator doing the
arithmetic — 94.5 − 1 = 93.5 — at authoring time. That is genuinely simpler and we
would accept it for the constant cases. It fails on exactly one case and fails
badly: `POST LENGHT-(DEPTH+7)`, where the depth is a conditional value that is not
known until a site is planned. Resolving that at authoring time means publishing
one coverage per footing depth, which is the same collapse-a-table-into-a-scalar
error `rationale.md` §5 argues against for `max_span_mm`.

---

### 2.4 Q4 — Bay-scope assembly steps

> *We propose `scope: bay` so a step can place a post. Does that cover
> installation guides, or do steps need to place things that are neither panel
> nor bay — a footing, a gravel base, a string line?*

**Verdict: adopt `scope: bay`, and it is the wrong lever on its own.** You
anticipated the right problem and under-estimated it by roughly a factor of two.

**The counts.** Five guides from five manufacturers, transcribed bullet by bullet
and classified by what each step acts on:

| Guide | Unit | `panel` | `bay` | **neither** |
|---|---|---|---|---|
| Bufftech Cape Cod — `bufftech-fence-installation-guide-2024.pdf` p8 | 49 bullets | 13 | 11 | **25 = 51%** |
| Weatherables Solid Privacy — `weatherables-fencing-master-installation-instructions-2024.pdf` pp3, 7 | 14 steps | 4 | 3 | **7 = 50%** |
| Barrette — `owners-manual-vinyl-fence-v3.pdf` pp4–7 | 9 steps | 2 | 1 | **4 = 44%** |
| Wam Bam — `nervous-nelly-VF15100-install-guide.pdf` pp10–20 | 10 steps | 2 | 6 | 2–8 (steps are mixed-scope) |
| Illusions — assembled panel p3 | 11 bullets | 1 | 1 | **9** |

**Thirteen scopes that are neither.** Each has a verbatim quote in the working
file; five that make the case:

| Scope | Verbatim | Source |
|---|---|---|
| `run` — string line | `To make sure your fence run is straight, install line stakes and run a string line. The string line should be positioned on the side of the posts and be very tight.` | `weatherables-fencing-master-installation-instructions-2024.pdf` p3 |
| `site` — utility locate | `You must have the utility companies clearly mark your property for electrical, gas or water lines to avoid puncturing any unseen underground utilities.` | `bufftech-fence-installation-guide-2024.pdf` p2 |
| `footing` — gravel base | `If frost line exceeds 30" dig hole to the appropriate depth and then add 6" of gravel for post drainage.` | `owners-manual-vinyl-fence-v3.pdf` p4 |
| `wait` — elapsed time | `Leave gate on blocks for 72 hours to allow concrete to set` | `bufftech-fence-installation-guide-2024.pdf` p8 |
| `temporary` — a product part used as a jig | `Lay out the first rail along your string line … Use only one rail as temporary spacer for your entire fence` | `manuals/wam-bam/structural/important-install-info-thdstatic.pdf` p15 |

That last one is worth pausing on: a **rail**, a real BOM part, is used as a
reusable spacer and then installed. It is placed twice and bought once.

**Where `scope: bay` is not merely insufficient but unsound.**

> `Standard rails are supplied in 16 foot lengths` … `If bottom rail is 16' long,
> slide rail through second post and then insert post in ground` … `The starting
> point for rails should be staggered from post to post for bottom/mid/top rail
> for maximum strength`
> — `bufftech-fence-installation-guide-2024.pdf` p38

A 16 ft rail spans **two bays** and is threaded **through** the intermediate post,
and the staggering rule constrains the sequence across bays. There is no bay this
step belongs to. Similarly:

> `DO NOT pre-dig all post holes. To ensure proper post spacing, install
> post-panel-post-panel-etc. until all fence panels and posts have been
> installed.` … `Do not add concrete to second hole until later in installation.`
> — `owners-manual-vinyl-fence-v3.pdf` p4

A line post is deliberately left unfinished *because it is shared between two
bays*.

**Invariant 4 fails against real documents.** Bufftech Chesterfield leaves 3 of
~11 named members unplaced by any step — the top-rail lock ring, the HVHZ
line-post stiffener, and gravel fill. The stiffener and the gravel appear only in
a figure caption: `EMBEDMENT DETAIL FOR OPTIONAL LINE POST STIFFENER ALUMINUM
INSERT / MINIMUM 48" INSERT REQUIRED TO COMPLY WITH THE HIGH VELOCITY HURRICANE
ZONES` and `GRAVEL FILL` (`bufftech-fence-installation-guide-2024.pdf` p31, figure
only, no step in the sequence mentions either). Weatherables never places its
bottom-rail aluminium insert or its post cap; Freedom places the same insert
explicitly.

So the invariant is satisfiable only by a curator asserting a placement the
document did not state, or by a large `unplaced` list. **We would rather publish
the large `unplaced` list**, and we read *"or reported `unplaced`"* as permitting
exactly that. Please confirm, because the alternative is a curator quietly
inventing placements to turn a check green.

**`requires` is populatable, and needs an edge kind.** Seven asserted dependencies
found — e.g. `fill the inside of the post AFTER THE PANELS ARE INSTALLED`, and
`after installing the fence panel, but before securing the post cap` — against
eight cases of mere print order, two of which **explicitly deny** their own
order: `Assembly may be continued by installing all bottom rails first, or one
section at a time`. So the distinction you want to preserve is real and readable
from documents.

But the corpus also contains **negative** and **maximum** edges — `do not add
concrete… until later`, `before concrete sets` — and mutually exclusive branches
printed as a sequence. A bare `requires: [step_key]` flattens those the same way
list position flattens ordinary prerequisites. Our own `cur_step_requires` has
the identical gap and we would fix it on both sides.

**Proposed change (tier 2).**
1. Widen `scope` to `panel | bay | post | run | site`.
2. Widen `kind` beyond `assembly | installation` to include `preparation`,
   `part_modification` and `maintenance`.
3. Give `slots` a target union rather than only `PanelSpec` slot paths — there is
   no slot path for a string line, a hole, gravel, concrete, rebar, a wood block
   or a 72-hour wait, and `PostSlot` has no sub-slots either.
4. Give `requires` an edge kind (`after | not_before | before | exclusive_with`).

**Counter-argument.** Everything above the panel could be declared out of scope:
Planning plans a fence, not a construction site, and a `gravel base` step
produces no BOM line the engine can count. That is coherent, and if you take it,
say so explicitly — because then roughly half of every installation guide in this
corpus is knowledge we hold and will never publish, and that should be a stated
decision rather than an emergent one.

---

### 2.5 Q5 — Warnings

> *We propose `code + params` with a text fallback. Your `cur_step_warnings`
> stores raw text and an element id. Is a code vocabulary realistic for warnings
> extracted from prose, or should text be primary?*

**Verdict: text must be primary, and invariant 5 is false against this corpus.**

We ran a census rather than a sample: all 81,794 elements swept for 36
warning-indicative patterns, every hit re-read against the source, page images
read where the warning is a graphic. **1,038 genuine warning instances in 112 of
the 144 documents, resolving to 226 distinct semantic warnings.**

**The distribution is the answer.**

| Coverage | Distinct warnings needed |
|---|---|
| 50% of instances | **11** |
| 80% of instances | **54** |
| 90% of instances | **123** |
| appear exactly once | **142** — 62.8% of all distinct warnings |
| appear at most twice | **167** — 73.9% |

The shape is not "twelve codes cover most of it". It is *eleven codes cover half,
then a tail of 142 one-offs*. A registry buys 50% for eleven entries and then
asymptotes. Codes are worth having; they cannot be primary.

**The scope finding, which is the important one. Of the 841 instances whose exact
page position could be resolved, 19.9% sit inside an installation step that does
something.** About 68% are document-scoped — the front safety box, "BEFORE YOU
BEGIN", "Care of the Product", running footers, and numbered items like "1.
Getting Started" that are checklists rather than steps. 9.4% are
product/certification-scoped (NOA general notes) and 2.7% warranty-scoped. Three
examples, all verbatim:

- **Document-scoped.** `Improper installation of this product can result in
  personal injury. Always wear safety goggles when cutting, drilling and
  assembling the product.` — `bufftech-fence-installation-guide-2024.pdf` p2, in
  the front box, governing the whole guide. 39 instances across 40 documents.
- **A page footer with a referent elsewhere.** `* Caution – In climates that
  experience freeze-thaw cycles, this installation method could result in post
  cracking over time. This would not be covered by the warranty.` — same document
  p12, printed at the foot of **fourteen** pages, its asterisk referring back to
  `b. Concrete and rebar*` inside step 10. 83 instances.
- **Warranty-scoped.** `This limited warranty does not cover damage resulting
  from: misuse, abuse, improper storage or handling, improper installation…` —
  `manuals/barrette-outdoor-living/bufftech-fence-limited-lifetime-warranty.pdf`
  p2. There is no step anywhere for this to attach to; it is in a different
  document from any procedure.

Invariant 5 says *"a warning lives on its step. Never detached."* Enforced
literally, this corpus can publish 19.9% of its warnings and must discard or
misattribute the other 80.1%. Attaching the freeze-thaw footnote to step 10 would
be a curator's inference, and attaching the safety-goggles box to *every* step
would be a fabrication.

**On `params`.** They pay off only when one warning recurs with *different*
values. Measured: that is true of **3 of the 226 distinct warnings — 1.3%**. The
clean case is a slope limit stated three ways by one manufacturer across three
products:

> `If your yard has a severe slope or an elevation change greater than
> approximately 3" to 4" over one panel of fence, you will not be able to install
> this fence.` — `manuals/wam-bam/sturbridge-BL19103…` p3

with `5" to 6"` in `windsor-BL19107` p4 and `7" to 8"` in
`nantucket-spec-sheet-v3-alt` p1. The other two are a support phone number (four
values across 32 documents) and an NOA maximum post spacing.

Everything else is a fixed sentence: 72 hours in all 81 of its occurrences, a 3″
air cavity in both of its, 45 seconds in both of its. `params` is right as an
optional adjunct to a code and wrong as a general mechanism.

**One code would flatten distinctions the sources actually make.** Five wordings
of the utility-locate warning differ in *modality* (`You must have the utility
companies clearly mark your property` versus a highly-recommends phrasing), in
*jurisdiction* (only Wam Bam gives the Canadian routing), and in *mechanism* —
Weatherables says `contact your utility supplier` and never mentions 811. One
code says all three are the same warning. They are not.

And a code can destroy legally operative text. From
`manuals/illusions-vinyl-fence/product-warranty.pdf` p1:

> `This limited warranty is void if any of the following occurs: (a) improper
> application techniques; (b) misuse, neglect or improper storage; (c) altering
> or changing the product by use of applied heat, welding, solvents, epoxies…;
> (d) impact of objects, fire, flood, hurricane…`

A code named `warranty_void_on_improper_installation` captures clause (a) and
deletes (b) through (f).

**On the Hebrew obligation, which is a contract-level problem.** Contract §2
requires both locale bundles for every warning code and §3.3.4 repeats it.
**Zero of the 81,794 elements in this corpus are Hebrew.** The corpus is English,
with `AVERTISSEMENT` in 26 documents and `ADVERTENCIA` in 27 — so French and
Spanish come free for the recurring head, and Hebrew comes free for nothing. A
warning lifted verbatim from a manufacturer's PDF has no Hebrew and we cannot
author one: translating a manufacturer's liability sentence and publishing it as
theirs is manufacturing a claim.

Note the mechanism fails precisely where it is needed — a `text` fallback cannot
satisfy *"every code present in both bundles"*, because the fallback is by
definition the case with no code and therefore no registry entry. So the registry
has to split: **platform warnings** (ours — the source-ref codes in
`source-refs-design.md` §3.2, gap codes, engine warnings) stay closed and require
both bundles; **source warnings** are verbatim, `lang`-tagged, and exempt.

**Proposed change (tier 2).**

```text
Warning {
  text_raw         REQUIRED, verbatim, never normalised
  lang             REQUIRED
  cites            SourceRef, REQUIRED
  attaches_to      { kind: step | procedure | document | product | model
                          | warranty | maintenance, ref }   REQUIRED
  severity_lexeme  the publisher's own word — WARNING | CAUTION | NOTICE |
                   IMPORTANT | NOTE | none — not normalised
  code             OPTIONAL
  params           OPTIONAL, only alongside a code
}
```

`severity_lexeme` is deliberately not normalised: `CAUTION` and `WARNING` are
terms of art with different legal weight in North American product literature,
and collapsing them is a decision we should not make on a manufacturer's behalf.

**Counter-argument.** A code registry has one advantage nothing else gives you:
a warning that must be shown for a *computed* reason — an uncovered condition, an
unfulfilled requirement — has no source document and must be a code. That is
real, and it is why we propose codes stay, as an optional overlay. The mistake is
treating engine-generated warnings and document-quoted warnings as one type. They
have opposite requirements: the first must be translatable and parameterised, the
second must be verbatim and untranslated.

**A constructive offer.** The eleven-warning head is genuinely codeable and we
will supply the starter list — utility locate, freeze-thaw/warranty, never strike
the post unsupported, eye protection, missing-or-damaged parts, do-not-return,
frost-line check, pool code, never cut the post top, warranty exclusions, never
attach both panel ends. Each with its instance count and a verbatim exemplar.

---

### 2.6 Q6 — Multi-document definitions

> *A Chesterfield panel's structure is in the install guide and its wind table is
> in an approval — different documents, different units, no shared identifier.
> Does `cites: [SourceRef]` per field carry enough, or does a definition need
> document-level provenance too?*

**Verdict: per-field `cites` is necessary and not sufficient — for an
architectural reason, not a bookkeeping one.**

**The Chesterfield trace is real and it is worse than your example.** Eleven
documents bear on the family, 2006 to 2025, filed under four different
manufacturer strings: `NOA-06-1019.01` (superseded, expired 03/13/2013) →
`NOA-12-1106.11` → `NOA-21-0125.07` → `NOA-23-0314.05` (all superseded) →
`noa-24-0117.05` (four byte-identical copies, all `version_status = unknown`),
plus three install guides, three catalogues and a gate guide. The last seven are
all `structural = 0` — even though they carry the HVHZ post-spacing table.

**On naming, your suspicion is half right.** Every NOA's product designation is
`DESCRIPTION: Extruded PVC Vinyl Fencing` (p1, OCR 95.4%) and names no style. But
the *drawing sheets inside* do: `MODEL: CHESTERFIELD - 8'X6'` on p12 and
`MODEL: CHESTERFIELD - 6'X6'` on p14 — read visually, because those pages OCR at
61–66%. So the identity is present, at the worst possible legibility, three
levels down. Eight distinct naming strings across the trace and no two identical.

**There is no shared identifier.** NOA numbers and drawing numbers link approvals
to approvals; nothing links an approval to an install guide. No SKU or model
number exists anywhere in the trace, and the bill-of-material item letters are
per-sheet figure legends — `L` is `2 X 6 DECO RAIL` on one sheet and
`2 X 6 X 73.5 DECO RAIL` on another. The one hard identity signal across the
CertainTeed → Barrette transfer is a **shared street address**,
`231 Ship Canal Pkwy, Buffalo, NY 14218`, read from a title block at 65.7% OCR
confidence, together with the sentence `This NOA revises NOA #23-0314.05`.

**Units differ three ways and none of them is metric** (all 34 `mm` hits in the
trace are English words): decimal inches in the bill of material
(`.875 X 7 X 62.75`), stacked fractions in the notes (`96⅛"`, `75½"` — which OCR
read as `964*` and `755"`), and composite feet-and-inches in the catalogue
(`4' 8" plus 1' 4" Accent`).

**Five disagreements, and the strongest is a disagreement about the domain
itself.** The 2006 approval's footing table gives `12" / 24" / 48"`. The 2025
Table 1 gives `B 24" 66"`. That is **48″ against 66″ maximum post spacing at the
same 24″ footing**, both PE-sealed, both approving "Chesterfield". And the 2006
table has **no wind-exposure column at all**, so its rows cannot be placed in the
modern `domain` without inventing a condition that the source never stated. No
per-field citation can express a disagreement about the shape of the condition
space. Also found: 97″ (install guide) against 96⅛″ (approval) for the same 8 ft
bay; 94″ / 95″ / 73.5″ for the rail; and a steel channel present on the 8′×6′ bill
of material and absent from the 6′×6′.

**Supersession, measured.** 9 of 144 documents superseded, 3 active, 132 unknown.
**132 of the 324 promoted facts — 40.7% — already cite a superseded document.**
The `97" at Exposure B` row is promoted from five documents: three superseded,
one the current approval marked `unknown`, and one an installation manual that
the source policy makes inadmissible for structural parameters.

And one finding that bears directly on the source policy: **one SHA-256 is filed
four times under four manufacturers with four different `doc_type`s** —
`engineering_approval`, `hvhz_noa`, `unspecified`, `real_miami_dade_noa_vinyl_fence`.
The *same bytes* therefore map to four different `source_class` values, and yield
91 / 55 / 55 / 55 facts from byte-identical extracted text. A citation naming one
of them is ambiguous about the one thing the policy resolves on.

**Why per-field `cites` cannot close this.** `SourceRef` is opaque to Planning and
resolvable only on the Discovery surface — which contract §3.2.2 forbids Planning
from calling during a run. So an opaque id carries **zero admissibility bits into
the snapshot**. A run holding a definition whose five `cites` include three
superseded approvals cannot tell, from inside the pinned object, that anything is
wrong. The information exists and is on the wrong side of a boundary the contract
deliberately draws.

**Proposed change (tier 2, plus one tier-1 field).**

1. `Part` and `FenceModel` gain `contributing_sources: [SourceDoc]`, keyed on
   `content_hash`, each carrying `source_class`, `version_status`,
   `version_status_basis`, `issue_date`, `expiration_date` and `superseded_by`.
2. `SourceRef` gains exactly **one** non-opaque field — `belongs_to`, the
   `content_hash` — so a field's citation joins to that block. It stays opaque in
   every other respect.

Cost: about 2 KB per definition, fourteen curation decisions on the
`same_content_as` groups, and one tier-1 negotiation.

**The asymmetry is real and worth fixing separately.** `source_class` and
`curation_level` sit on `ParameterTable` rows and not on `Part.spec` fields or on
`FenceModel`. But a Chesterfield rail length would be `derived` (no page),
marketing-grade OCR, or PE-sealed depending on which of the eleven documents it
came from — exactly the same admissibility problem as a parameter row. Contract
obligation §3.1.6 says *"every row"*; invariant §6.8 says *"every published
value"*. The invariant is right and the obligation should match it.

**Counter-argument.** `contributing_sources` duplicates into the snapshot data
that Discovery already serves, and every duplicate is a second authority over the
same fact — the objection §2's own "dimensions are derived, never stored twice"
rule makes against a `dimensions` map. The answer is that this is not a second
authority but a *pinned copy*, and pinning is what the whole snapshot design is:
Planning already pins parameter rows rather than querying them, for the identical
reason. If you would rather not carry it, the alternative is that Planning cannot
warn on a lapsed authority at all, and we would publish that as a standing `Gap`.

---

### 2.7 Q7 — Procedures that are not per-model

> *"Let footings cure overnight" belongs to a manufacturer, not a panel. Where
> does a procedure with no model go?*

**Verdict: no home, and the cost is duplication rather than loss.**
`FenceModel.assembly` is the only published landing site for a procedure, and §4
of the data model names only two crossings into tier 2 — an accepted claim
becomes a `ParameterTable` row, a curated procedure becomes a
`FenceModel.assembly` list.

**Quantified.** In one 50-page guide the identical run-scope block repeats
**sixteen times** (`Stake out the fence line`) and the cure step **twelve times** —
once per style the guide covers. Published as `FenceModel.assembly`, that is one
procedure, sixteen models, sixteen copies and sixteen `SourceRef`s to the same
page. Nothing is lost; everything is duplicated, and a correction to one copy
does not reach the other fifteen.

**Four classes, with evidence.**

1. **Manufacturer-wide.** Concrete quantity tables, the 72-hour cure, expansion
   gaps, material storage, cleaning — and one window-screen remediation procedure
   attached to no product at all.
2. **Cross-manufacturer, owned by nobody.** The corpus carries an ARCAT CSI
   masterspec — `Center and align posts, place concrete around posts and vibrate
   or tamp for consolidation. Recheck vertical and top alignment of posts and
   make necessary corrections.` and `Do not install products under environmental
   conditions outside manufacturer's absolute limits` — and a CLFMI technical
   bulletin: `All posts are considered to be embedded in concrete, minimum 2,500
   psi, air-entrained, of a depth consistent with local soil types and
   conditions`. The CLFMI bulletin is about **chain link**. It has no vinyl model
   to attach to and it is nonetheless the most authoritative statement in the
   corpus on post embedment.
3. **Component-scoped.** Hinge, latch, drop rod, post cap — attached to a part,
   not a panel.
4. **Site-conditioned.** A frost line branches Barrette's footing procedure into
   two alternatives; 100 °F changes post centres; wind exposure sets footing
   depth.

**Proposed change (tier 2).** Make the second crossing a first-class `Procedure`
with `scope: EntityRef | null`, where `null` means *no product owner*, and
`cites` carrying its provenance. `FenceModel.assembly` stays as it is for
procedures that genuinely belong to a panel. This mirrors our own
`cur_procedures.entity_id`, which already keys a procedure to an entity of any
kind, and it needs no `Manufacturer` type in tier 2.

**Counter-argument.** A `Manufacturer` entity in tier 2 is a registry problem
tier 2 deliberately excludes, and `scope: EntityRef | null` smuggles one in
through the back door. The honest answer is that `EntityRef` already exists in the
contract's stable core (`{kind, id, tenant}`) and already admits kinds Planning
does not model; a procedure scoped to one is no worse than a `ParameterTable`
scoped to one. If you disagree, the fallback is to accept the sixteen-fold
duplication and require that duplicated procedures share a stable
`procedure_group_id` so a correction can find its siblings.

---

### 2.8 Q8 — Is anything in §3 unrepresentable for material we already hold?

**Yes. Six things**, in descending order of how much of the store they affect.

#### Q8.1 — `UnitCode` cannot carry 274 of the 1,976 facts we hold

`UnitCode` is `mm | mm2 | mm3 | each | gram_milli | cent`. Measured:

| Unit | Facts | Crosses as a `Quantity`? |
|---|---|---|
| `in` — footing depth, post spacing, depth below grade, footing diameter | 601 | yes → mm |
| `mph` — wind speed | 269 | **no unit exists** |
| `deg` — racking | 5 | **no unit exists** |
| none — `reinforcement`, `approval_id`, dates, `exposure_category` | 1,101 | not quantities at all |

30.4% of what we hold converts cleanly. 13.9% is a number with a unit the
vocabulary cannot name. 55.7% is not a `Quantity` in the first place.

`mph` is not incidental — it is the second-largest numeric fact type in the store
and it is the *design basis* of every structural table:

> `2- DEFINITION: THIS FENCE AND IT'S SUPPORTS ARE DESIGNED FOR 75 MPH` /
> `FASTEST MILE WIND SPEED OR | 15 MPH (ULTIMATE 3 SEC. GUST).`
> — `manuals/barrette-outdoor-living/structural/noa-24-0117.05-vinyl-fencing.pdf`
> p7, `element-0755b422c5-0004` and `-0005`, OCR at 95.33% and 86.83%. The `| 15`
> is OCR losing the leading `1` of `115`; the page is a scan.

Wind speed does cross today as a *condition key* — `hvhz` and `wind_speed_mph`
appear as conditions on 47 facts — but a condition value in `ParameterTable.domain`
is an enum member, not a quantity, so `115` cannot be compared, bracketed or
converted on the other side.

**Proposed (tier 1):** extend `UnitCode` with `mph_milli` (or `mps_milli`),
`deg_milli`, `pa_milli` and `second_milli`. Four entries; the integers-only rule
is untouched — 115 mph is `115000 mph_milli`, 10° is `10000 deg_milli`.

**Counter-argument.** Wind speed and pressure may belong entirely in the condition
space rather than the value space, in which case they never need to be a
`Quantity` and a closed enum of brackets is enough. `deg` does not survive that
argument: racking is a value a planner needs arithmetically (§2.2), not a bracket.
Neither does cure time (§2.7), which is a duration a scheduler needs.

#### Q8.2 — No published type carries a validity window

We hold 271 `approval_id` facts, 84 `effective_date` and 75 `expiration_date`.
`Combination` is `{id, members, claims, cites}`. An NOA expires; a `Combination`
does not.

`NOA-23-0314.05-…-current-2023-2029.pdf` carries `issue_date 05/04/2023` and
`expiration_date 03/13/2029`, and is `version_status = superseded` on the basis
*"named as a previous approval by a later NOA"*, with four `superseded_by` edges.
Not expired and not current, at the same time, three years apart. Combine that
with §2.6's measurement — 40.7% of promoted facts already cite a superseded
document — and a snapshot pinned today and read in 2030 has no field in which to
say the authority behind a value lapsed. `retain_until` governs the *snapshot's*
resolvability, which is a different thing.

**Proposed (tier 2):** `Combination` and `ParameterTable.rows[]` carry
`valid_from` / `valid_until` / `authority`. Planning warns on a line whose backing
authority has lapsed relative to the run date, exactly as it warns on an uncovered
condition.

**Counter-argument.** Expiry could be modelled entirely as a condition dimension
(`as_of_date`), needing no new field and reusing `uncovered`. That is arguably
cleaner and we would accept it.

#### Q8.3 — `ParameterTable` rows carry no design basis

`data/structural/barrette-outdoor-living-structural.json` records two wind load
tables from one manufacturer:

> `2023 FBC 8th Edition (HVHZ); … wind exposures as defined in ASCE 7-10`
>
> `2023 FBC 1616.2.1, based on wind loads per ASCE 7-16; …`

`ASCE 7-10` and `ASCE 7-16` define exposure categories and gust factors
differently, so `conditions {exposure_category: "C"}` does not mean the same thing
under the two. Under `hit_policy = unique` those rows collide on the same domain
point and the publish check rejects them — for the wrong reason, with no way to
fix it except dropping one. §2.6 found the same failure a generation earlier: the
2006 Chesterfield approval has no exposure column at all.

**Proposed:** add `code_edition` to the condition-dimension registry — a §2
registry addition, therefore not a breaking change — or a `design_basis` field on
the row. We prefer the registry route.

**Counter-argument.** If an operator only ever publishes the current edition the
field is inventory nobody reads. But this corpus holds both, inside one
manufacturer's own supplement, and from inside a table we cannot tell which is
which.

#### Q8.4 — Jurisdiction is not a condition dimension

`data/structural/barrette-outdoor-living-structural.json` records the approval as
valid `to be used in Miami Dade County and other areas where allowed by the
Authority Having Jurisdiction (AHJ)`. And
`data/structural/illusions-vinyl-fence-structural.json` records that
`No Florida Building Code statewide Product Approval (FL#) was found for Illusions
Vinyl Fence / Eastern Wholesale Fence via floridabuilding.org search in this pass.
Only the Miami-Dade County NOA path was found`.

So one value is admissible in one county, conditional on an official's judgement
elsewhere, and unapproved as a statewide matter. Condition dimensions are
Planning's — *"Planning declares what it can bind"* — so this is a request rather
than a proposal: **please add a jurisdiction dimension**, or tell us it will not
be bound and we will publish these as gaps.

#### Q8.5 — Gates

Covered in §2.11. `FenceModel` / `PanelSpec` has no gate concept, and the corpus
has dedicated gate installation guides, gate kits with SKUs and leaf dimensions,
gate-post inserts, and hinge load ratings by leaf weight.

#### Q8.6 — The dual-lexeme problem

Invariant 7 and contract §1.1 say the verbatim source lexeme travels alongside the
converted integer so that a disagreement is visible. This corpus contains sources
that state **both** units themselves, and get it wrong:

> `Height: 66 inch (16766 mm) with New England Accent. Pool.` — `element-e41aee54e9-0232`
>
> `Rail Section: 8 foot (2436 mm).` — `element-e41aee54e9-0080`

both in `manuals/industry-standards/ARCAT-CSI-32-31-23-Vinyl-Fencing-and-Gates-MasterSpec_Superior-Outdoor.docx`,
a CSI masterspec that a specifier copies into a project specification. 66 in is
1676.4 mm, not 16766. 8 ft is 2438.4 mm, not 2436.

The contract's mechanism is exactly right and one field short. There are two
lexemes and `value_raw` holds one. Publishing `"66 inch"` silently discards the
document's own contradictory figure; publishing `"66 inch (16766 mm)"` as the
lexeme makes it unparseable.

**Proposed (tier 1):** `value_raw` becomes a list, or gains
`value_raw_secondary`. Cheap, and it makes a real class of source error visible
rather than hidden.

---

### 2.9 Q9 — Is anything in §3 over-specified?

Four fields we would have to invent data for, and one invariant that is inverted
for this corpus.

#### Q9.1 — `FrameSlot.insertion_margin_mm`, and the clearance the corpus *does* state

*"Clearance so a member can be tipped in."* Searched `clearance`, `margin`, `tip
in`, `play`, `insertion`, `slop` across the installation manuals. **No document
states a tipping-in clearance.** It is a real quantity a fabricator knows and no
manufacturer publishes; a curator filling it would be inventing a number that then
reads as sourced.

What the corpus states instead is a clearance of a different shape, twelve times
across six documents:

> `• When installing rails leave a 1" gap between rail ends`
> `inside post to allow for expansion`
> — `manuals/certainteed-bufftech/bufftech-installation-guide-40-40-70743.pdf`
> p36, `element-88dd3c1287-0055`, bbox `[57.34, 601.84, 264.68, 624.62]`, text
> layer; also p38 of the same guide, and in `bufftech-fence-installation-guide-2024.pdf`,
> `bufftech-simtek-fence-install-guide.pdf`, both gate guides, and
> `bufftech-installation-guide-afence.pdf`

That is not a margin for tipping a member in. It is a gap **between two members
that share one host** — two rails from adjacent bays meeting inside one routed
line post — and it bounds the cut length directly, because each rail's engagement
is at most half the post cavity less half an inch. `FrameSlot` has
`channel_depth_mm` and `insertion_margin_mm`. Neither is this.

**Position:** `insertion_margin_mm` must be legal to omit, and its absence must
publish as a `Gap` rather than default to `0` — a `0` silently asserts "no
clearance required", which no document said. And a field is needed for the
shared-host gap, because the corpus states it plainly and it changes a cut length.
Its stated reason is thermal expansion, so it may belong with the expansion-gap
material rather than on the slot.

#### Q9.2 — `ContainedSlot.coverage = Fraction(permille)`

See §2.3 — of the four proposed coverage kinds, `Fraction` is the one with no
instance behind it in this corpus.

#### Q9.3 — `Authorship = manufacturer_approved | manufacturer_uploaded`

We cannot produce either. Every definition this platform publishes is our reading
of a PDF; there is no fence data feed and no manufacturer in this corpus has
approved anything we wrote. `third_party_authored` is the only value we will ever
set. The enum is right for the system as a whole — a tenant uploading their own
document needs the other two — but nothing this platform authors will use them,
and that is worth saying so the flag is not read as more meaningful than it is.

#### Q9.4 — `Quantity.cent`

The catalogue left the snapshot, deliberately and correctly. Nothing we publish
has a price, so `cent` is unreachable from this side. Harmless; noted only so it
is not later read as an invitation.

#### Q9.5 — Invariant 2 is inverted for this corpus

> *"A part cannot declare its length: the same rail serves a 2400 bay and an 1800
> one, so the bay resolves it. Publishing a length literal on a rail is wrong, not
> merely unnecessary."*

Here, rails are manufactured at fixed nominal lengths per style, and the rail's
length is what determines the bay:

> `Cape Cod | 7/8" x 3" | 2-7/16" 72" | 1-3/4" x 3-1/2" | x 72" | None | White`
> `Danbury | 7/8" x3 | 2-15/16 96 | 1-3/4" x 3-1/2" | x 96 | Bottom | …`
> `Columbia | 7/8" x 6" | 4-9/16 96 | 3-1/2" x 3-1/2" | x 94 | Bottom | White`
> — `manuals/certainteed-bufftech/bufftech-catalog-2014.pdf` p28,
> `element-0d0c63f057-0005`, bbox `[42.0, 96.96, 564.96, 747.84]`, OCR at 76.52%

Three different rail lengths — 72″, 94″, 96″ — across styles on one page. And
stated as an explicit discrete option in the CSI masterspec:
`Rail Section: 6 foot (1829 mm).` / `Rail Section: 8 foot (2436 mm).`
(`element-e41aee54e9-0079`, `-0080`).

`agree = supplies` says the bay resolves the length. Here the *part catalogue*
resolves it: a Columbia section is 94″ because the Columbia rail is 94″, and there
is no 2400 mm Columbia bay to serve. The rail is cut down on site only for end
bays and slopes — and note §2.4's 16 ft rail, which spans two bays and is neither.

**This is not a request to delete the rule.** `supplies` is right for a
cut-from-stock part and this corpus has those too. It is a request to let a part
declare a **manufactured nominal length** distinct from its **cut length**: the
first is a fact about the part and every catalogue prints it, the second is what
the bay resolves. Collapsing them means either publishing a length literal the
invariant forbids, or discarding a number the source states plainly.

---

### 2.10 Q10 — Are the invariants in §6 enforceable at publish time?

**Five are enforceable as written. Two are enforceable and wrong for this corpus.
Two are only half-enforceable, because the missing half is in the documents rather
than in us. One is false.**

| # | Invariant | Enforceable? |
|---|---|---|
| 1 | Dimensions derived, never stored twice | **Yes** — a structural check on the published object |
| 2 | A part cannot declare its length | **Yes, and wrong for this corpus as written** — §2.9.5 |
| 3 | Naming a part and authoring what it is are exclusive | **Yes** — row-local |
| 4 | Every member placed by exactly one step, or reported `unplaced` | **On us, yes. Derivable from documents, no** — §2.4 |
| 5 | A warning lives on its step | **No — false against this corpus** — §2.5 |
| 6 | No two rows match one domain point under `unique`; uncovered listed | **Yes**, and we already have a violation to show |
| 7 | Integers only, thousandths, verbatim lexeme alongside | **Yes for the arithmetic, one field short for the lexeme** — §2.8.6 |
| 8 | Every value carries a resolvable `SourceRef` and honest `Authorship` | **Yes** — that is what `source-refs-design.md` is for |
| 9 | Extension part types tenant-namespaced, chain terminates in the spine | **Yes mechanically, wrong axis** — below |
| 10 | Structure is authored, not extracted | **Yes** — a statement about our process, and we accept it |

Two that need discussion beyond the sections already cited.

**Invariant 6 — already violated, which is the point.** Two rows in `facts` today,
same parameter, same condition tuple, opposite resolutions of the safety-critical
bracket: 97″ at Exposure B with `hvhz_applicability: unresolved`, and 97″ at
Exposure B with `non-HVHZ only`. Under `unique` that is a build error at publish
rather than a silent, precedence-dependent answer. The invariant works and we want
it.

One thing to be explicit about: `uncovered` requires enumerating the domain, and
on a scanned table whose grid could not be reconstructed we may not know how many
rows the table had. 73 pages are in that state. On those, *"every uncovered point
is listed"* is a promise about a domain we are **declaring**, not one we read off
the page. We will declare it and say so; it must not be read as measured.

**Invariant 9 — the namespace is on the wrong axis.** *"Extension part-type ids
are tenant-namespaced (`fenceco/…`)."* We invent a part type because a
**manufacturer's** manual describes one — a rebar separator clip, a U-channel, a
transition bracket. Manufacturers are not tenants. A `Snapshot` is per-tenant and
must contain nothing belonging to another (obligation 7). So a
manufacturer-derived extension must either be duplicated into every tenant
namespace that stocks that manufacturer, or live in the shared spine that only
Planning may extend. Neither is right.

**Proposed (tier 1):** three namespaces — `shared` (Planning), `mfr/<manufacturer>`
(Knowledge, global, tenant-agnostic) and `<tenant>` (a company's own). The parent
chain rule is unchanged and still terminates in the spine. This is the only tier-1
change in this response we think is structurally necessary rather than merely
useful.

---

### 2.11 Gates — the largest single thing §3 cannot express

Not one of your ten questions, and it belongs under Q8. `Part`, `FenceModel`,
`PanelSpec`, `AssemblyStep`, `ParameterTable` and `Combination` contain **no gate
concept at all**. The corpus has dedicated gate installation guides — the Bufftech
gate guide alone yields 110 facts — gate kits with SKUs and leaf dimensions,
gate-post inserts, hinge load ratings, drop rods, and a regulatory regime that
applies to gates and not to panels. This section was researched independently of
the rest of the response, by a second reader, and the two passes agreed.

**A gate leaf is nearly a panel.** It has rails, uprights and infill, and it is
assembled the same way — `Slide the boards into the bottom rail` /
`Slide the top rail over the boards` /
`Apply provided vinyl cement to all inside surfaces of the uprights where the
rails will be installed` (`manuals/freedom-outdoor-living/VF-Privacy-Gate-Install_HingesLatchDropRod.pdf`
p4, text layer). `PanelSpec` handles that half. Everything below is the other
half.

#### The opening, which a panel does not have

| Fact | Verbatim | Source |
|---|---|---|
| Leaf is narrower than its opening | `Gate widths 2" under actual opening (46" wide for 4' opening and 58" wide for 5' opening)` | `manuals/freedom-outdoor-living/structural/2023_Conway-Sell-Sheet.pdf` p2, `element-9bd5542499-0010` |
| …and the rule differs by leaf count | `For a single gate, measure the actual width of the gate and add 2". … For double gates, measure the actual total width of both gates and add 3".` | `manuals/illusions-vinyl-fence/gate-installation-instructions.pdf` p1, `element-616eb9a1da-0010` |
| The clearances are **handed** | `As a general rule, the hinge and the latch require a 1" gap each. An additional 1" gap is required for a double gate.` | `manuals/weatherables/weatherables-fencing-master-installation-instructions-2024.pdf` p6, `element-6c72fa562f-0003` |
| Ground clearance | `• Gate requires 2" clearance under bottom rail on level ground` | `bufftech-simtek-fence-install-guide.pdf` p7 and two other guides |

A `FrameSlot` has one `channel_depth_mm` and one `insertion_margin_mm`. A gate
opening needs a different number on the hinge side than on the latch side, and a
third number when there are two leaves. There is no side.

#### Operation — no field of any kind

> `Double check before adding hinges that desired swing direction and latch
> position is correct.` — Illusions p1, `element-616eb9a1da-0018`
>
> `If installing around a pool, check local codes to determine the direction the
> gate should swing. Typically, it should swing outward, away from the pool.`
> — Weatherables p6, `element-6c72fa562f-0011`

Swing direction, handing, hinge side and latch side are facts about an opening,
not about a panel, and none of them has anywhere to live. The bracing inherits the
handedness: `The brace should run at an angle starting at the lower corner of the
gate on the hinge side and run at an upward angle towards the top. Be sure to
secure the cross brace to the rails (not the posts).` (Weatherables p5,
`element-8e457d3019-0049`). So does the reinforcement: `Install aluminum insert on
the hinge side prior to the installation of the gate.`
(`weatherables-2-rail-gate-installation.pdf` p4).

#### Hardware slots, and the one place the model's mechanism breaks

Hinges, latch, drop rod and stop all have mounting positions the corpus states —
`Add hinges to gate frame … 6" from top and 6" from bottom`,
`Determine latch height`, `Opening mechanism of the latch must be at least 54"
above the ground` — and `FixingRule` has six bases, none of which is a position.

The **drop rod** is worse than a missing field. `For double gates, install the drop
rod to the socket post of the fixed gate.` (Weatherables p6,
`element-6c72fa562f-0020`) and
`For walk gates, it is strongly recommended to use a drop rod. For double drive
gates, use a drop rod on each leaf of the gate.` (Illusions p1). A double gate has
an **active leaf and a fixed leaf**, and the hardware count depends on which. There
is no leaf, no leaf role, and no `per_leaf` / `per_fixed_leaf` / `per_opening`
basis.

**Hinge selection is where a mechanism, not a field, is missing.** The source
table exists — `Product Description | Available Materials | Support Gates Up To`,
with `Standard Strap Hinge | Steel | 35 lbs`, `Heavy-Duty Strap Hinge Steel 75
lbs`, `Heavy-Duty Butterfly Hinge - Pair | Aluminum | 100 lbs`,
`Heavy-Duty Modern Wrap Hinge - Pair Steel, Stainless Steel 150 lbs`
(`2024-Freedom-VF-Catalog-01-24_SpecialOrderCatalog.pdf` p106,
`element-6b617d46b4-0047`). Choosing among them requires
`item.load_rating_lb >= gate.leaf_weight_lb` — a fact about an *assembled gate*,
which is neither `panel.*` nor `host.*`, and which is itself the sum of the leaf's
members. There is no `gate.*` namespace and no derived-property mechanism.

**An honest negative on hinge count.** Searched `three hinges`, `3 hinges`,
`additional hinge`, `number of hinges`, `hinge weight`, `gate weight`. The corpus
gives **style-specific counts, never a function**: `Galveston gate requires 3
hinges` (`bufftech-gate-installation-guide.pdf` p34). So the load table above and
the count rule are not connected by anything a document states. That is a data gap
to publish, not a modelling problem.

#### Gate posts are a different part with a different footing

| Fact | Verbatim | Source |
|---|---|---|
| Different part | `Use Heavy Duty Gate Posts 5" x 5" (VH55_ _ _) or Majestic Entryway Gate Posts 8" x 8" (V88_ _ _)` | Illusions p1, `element-616eb9a1da-0025` |
| Different length | `102" Gate Post 142" Gate Post` | `bufftech-gate-installation-guide.pdf` p4 |
| Different hole | `Dig post holes 12" to 16" in diameter and 36" to 42" deep` — against the 30″ used everywhere else | Illusions p1, `element-616eb9a1da-0012` |
| Different concrete | a `Concrete Usage for Posts` table with separate `End Line or Corner Posts` and `Gate Posts` columns: `5x5 \| 6' \| 140 lbs \| 240 lbs \| 285` | `bufftech-gate-installation-guide.pdf` p7, `element-1071dc70f2-0045` |
| Mandatory reinforcement, anchored to hardware | `All hinge and latch posts require reinforcement using aluminum post inserts high enough to attach gate hardware (or concrete and rebar).` | `bufftech-gate-installation-guide.pdf` p7, `element-1071dc70f2-0003` |
| …and it must be bought separately | `Vinyl gate posts require an internal support system for weight-bearing purposes therefore a post stiffener is required. Post stiffener needs to be purchased separately.` | `VF-Privacy-Gate-Install_HingesLatchDropRod.pdf` p2 |

That reinforcement quote is worth pausing on: the insert must be *"high enough to
attach gate hardware"* — an extent anchored to the position of a part that is not
its host. It is precisely the `Anchor` case §2.3 proposes, arriving from a
completely different direction.

#### Gate procedures run the fence, not the other way round

This is the finding we did not expect.

> `The location of your gate will determine the layout of the posts for the fence
> line. The width of your gate will determine the spacing between your gate posts.`
> — `weatherables-fencing-master-installation-instructions-2024.pdf` p3,
> `element-d033d3b49e-0006`
>
> `Gate(s) must be assembled prior to fence to accurately establish space between
> hinge and latch posts and height of fence`
> — `bufftech-gate-installation-guide.pdf` p7, `element-1071dc70f2-0035`

Gate placement is an **input to the whole run's layout**, and the gate is built
first so the run can be set out from it. `AssemblyStep` scopes to a panel, and
§2.4 asks to widen that to a run. Gates are the reason it is not optional: a gate
procedure that cannot address the run is not merely under-scoped, it is
back-to-front.

#### And a compliance regime that panels do not carry

From `2024-Freedom-VF-Catalog-01-24_SpecialOrderCatalog.pdf` p10, under the
heading `National Pool Code Gate Specifications:`

> `Must have self-closing hinges.` · `Must have self-closing latches.` ·
> `Must open out (away from pool area)` · `Opening mechanism of the latch must be
> at least 54" above the ground.` · `Must not use a cross brace on gates.`

and, on a different product, the flat contradiction: `Not pool code approved.`
(`manuals/barrette-outdoor-living/install-racking-gate.pdf` p2). The *panel*-level
pool rules on the same page — `Spacing between pickets must be less than 4".`,
`Space from the bottom of the bottom rail to the ground must be less than 4".`,
`Distance from the top of the bottom rail to the top of the next highest rail must
be at least 45".` — **are** expressible as authored predicates. So the panel half
of pool compliance works and the gate half does not, and the gate half is the part
that keeps children out of pools.

Note also that `Must not use a cross brace on gates` is a *prohibition on a
component*, not an option. The same corpus sells cross-braced gates
(`Every gate comes with an x-brace`), brace-free gates as an aesthetic choice
(`No cross brace for a cleaner aesthetic`), and height-triggered double bracing
(`Please note, 8 ft. high panels require 2 cross braces. See CAD for placement.`).
Three different reasons for the same field to take three different values.

#### What we are asking for

**Not `GateModel` in v0.1.** We are asking that gates be **named as out of scope**
rather than left implicit. If they are left implicit, a curator will file a gate as
a `FenceModel`, the model will validate, and every fact above will be silently
lost — including swing direction and latch height, which are the two that matter
for pool-barrier compliance.

When it is in scope, the minimal shape from both passes agrees:

```text
GateModel {
  leaf            PanelSpec              reuse it — this half already works
  leaves          [Leaf{role: active | fixed}]
  opening_rule    leaf-to-opening delta, by leaf count
  clearances      { hinge_mm, latch_mm, between_leaves_mm, ground_mm }
  operation       { swing, handing, hinge_side, latch_side }
  hardware        [HardwareSlot{kind, mounted_on, side_or_leaf_role,
                                placement, quantity_rule, requirement}]
  bracing         variant axis, with an explicit prohibited value
  post_role       gate                   → §2.3.3's post-role keying
}
```

plus a `gate.*` namespace for eligibility predicates, and `compliance_regime` as a
condition dimension (`pool_barrier`, `self_closing`, `self_latching`) alongside
§2.8.4's `jurisdiction`.

**Counter-argument, argued properly.** A gate could be a `FenceModel` with an
option axis `kind: panel | gate`, a `PanelSpec` whose `FixingRule`s carry the
hardware, and a `ParameterTable` for hinge selection. Most of it genuinely would
work — the leaf, the infill, the fixings, the bracing-by-height variant. Four
things would not, and they are not marginal: the **handedness** (1″ hinge, 3/4″
latch — a `FrameSlot` has one number), the **swing direction** (no field of any
kind), the **fixed leaf** (drop-rod count depends on it), and **hinge selection by
leaf weight** (no `gate.*` to predicate against). Three of those four are
safety-relevant under pool code, which is the argument that decides it.

---

## 3. The finding that is not one of the ten questions

**The shipped source policy has no class for an installation manual, and that is
44.6% of every fact in this store.**

Contract §1.4 admits, for a **structural parameter**, only `sealed_approval`
(1st, level 2) and `tested_report` (2nd, level 2). Spec sheets, marketing and
company-authored sources are inadmissible. Measured against the 601 dimensional
structural facts we hold — footing depth, post spacing, depth below grade,
footing diameter:

| Source `doc_type` | Facts | Nearest `SourceClass` |
|---|---|---|
| `installation_manual` | 360 | none fits; nearest is `spec_sheet` → **inadmissible** |
| `hvhz_noa` + `engineering_approval` + `real_miami_dade_noa` | 231 | `sealed_approval` → admissible |
| `cut_sheet`, `csi_masterspec_template`, `unspecified`, `association_technical_bulletin` | 10 | marketing / none |

**231 of 601 — 38.4% — sit in an admissible class. The other 61.6% are
inadmissible for the very task they are about.** And none of the 231 is at
curation level 2: `reader_kind` is `agent` for all 1,225 rows in
`table_read_candidates`, and there is not one human reading in this corpus. Level
2 is currently unreachable by construction, not by backlog.

We think the **policy is correct**. A manufacturer's install guide saying
`Figures based on 4x4 hole=10", 5x5 hole=12", both 30" deep`
(`bufftech-installation-guide-40-40-70743.pdf` p5, `element-da08178108-0022`,
text layer) really is weaker evidence than a PE-sealed NOA drawing. The problem
is that the vocabulary has no name for it, so it gets filed as `spec_sheet` and
disappears without anyone deciding that it should.

Two gaps in `SourceClass`, both with material behind them:

- **Installation manuals** — 69 documents, 1,129 pages, 882 facts. Not a spec
  sheet, not marketing, not company-authored.
- **Industry standards** — 9 documents: ASTM compilations, two CSI masterspecs, a
  CLFMI wind-load guideline, an association technical bulletin, an industry spec
  reference guide. Roughly 96 pages and 39 facts. In engineering practice these
  *outrank* a manufacturer's spec sheet, and the ladder has no rung for them at
  all.

**Proposed change: a registry addition, therefore not breaking.** Add
`manufacturer_installation_instruction` and `industry_standard` to `SourceClass`
and let the operator rank them. We are not asking for a permissive ranking.
Ranked below `sealed_approval` and admissible for nothing structural, they would
still be an improvement, because then those 360 facts are *visibly excluded*
rather than silently mis-filed.

One note on granularity, in the policy's favour: `source_class` sits on the
`ParameterTable` **row**, not on the document, and that is right. This corpus
mixes marketing and engineering data inside single files —
`manufacturer_brochure_with_engineering_data` is literally a `doc_type` here, and
`bufftech-catalog-2014.pdf` carries both style photography and the only racking
figures in the corpus. Per-row classification works. It does mean the classifier
is a curator's judgement about a *region of a page*, not a lookup on a filename.

---

## 4. What we are doing, and what we are not

**Doing now: source references and crops.** Contract §4 names it as the piece on
this side that crosses no boundary and blocks nothing, and it is the thing a
review queue cannot exist without. `source-refs-design.md` is the design, and
`fixtures/source-ref-examples.json` carries seven records built from real rows in
this store — every kind and every failure mode — so your frontend can build
against a shape rather than a guess.

Two things that design surfaced in our own store, both logged:

- **All 1,225 table readings record row and column labels and no cell bounding
  box in crop pixels.** A reviewer can be shown the crop and not the cell inside
  it. Our own `docs/curation/` §2.5.3 requires that box; it does not exist yet.
- **The existing 7,484 region crops were cut with Pillow**, which is optional and
  git-ignored, and `_crop_region` returns `False` without it. The endpoint will
  cut crops with poppler, which is a declared dependency, and the existing crops
  become a legacy cache. On the one case we checked, the two agree exactly.

**Not doing yet: claims, parameter tables, snapshots.** All three wait on this
audit, because the answers above change their shape. Q2 changes what a
`ParameterTable` row may hold. Q5 changes what a published warning is. §3 changes
which sources may back a row at all. Building any of them now would mean building
them twice.

**Not asking you to do anything yet either**, except read §2.2, §2.4, §2.5, §2.6
and §3 — the five places where our data contradicts the proposal rather than
merely stretching it. Everything needing a decision is in one list in
`05-acceptance-open-questions.md` §1, so the negotiation has a single surface.
