# Review of v0.2 — the Knowledge team's response to the disposition

```text
Status:    Review. From the Knowledge team, on contract-v0.2.md,
           knowledge-datamodel-v0.2.md, planning-asks-v0.2.md and
           audit-disposition-v0.1.md.
Verdict:   Approve the direction and the dispositions. Six defects to fix
           before either side authors against the model. None needs a redesign.
Method:    Three independent readers over the contract, the data model, and the
           satellite documents, plus direct measurement against
           workspace/indexes/evidence.db where a claim was testable.
```

## 0. The verdict, and what it is not

**Approve.** Twenty-four accepted, three modified, two decided, none rejected — and
we accept all five modifications, including the one we would have got wrong. The
disposition is a better document than the audit it answers, for a specific reason
worth naming: it checked every decision against the engine's code rather than
against the proposal, and it says so three times where the code disagreed with
Planning's own document. N5 and N9 came back *"you asked for something we already
had"*, which is the most useful kind of answer and the hardest to give.

**What this is not:** none of the six defects below re-opens a decision. Four are
types that are named and never defined, one is a rounding convention nobody
declared, and one is a gap our own N18 acceptance opened. They are all cheap. But
each of them blocks a specific §8 verification, and §8's own instruction is the
right test: *take the artefact and check you could author it.* On six of the
twenty-nine — **N2, N7, N9, N10, N14 and N17** — we cannot, and N9 is an outright
fail rather than an ambiguity.

---

## 1. Blocking — fix before either side authors

### B1 · `Gap` is tier 3 and "never consumed", and the gate decision depends on publishing gates as Gaps

`knowledge-datamodel-v0.2.md` §4 lists `Conflict · Gap` among the private model and
says *"Everything else stays yours and is never consumed."* §9.1 then says a gate is
published *"as a `Gap` with `kind = "unmodellable_entity"`"*, and the disposition
§2.5 says it *"will surface in Planning as a named hole"*. Those cannot both be
true. `insertion_margin_mm`'s absence (§3.3), the unquantified accent effect on
racking (§3.8) and every unrepresentable entity land on the same escape hatch.

`contract-v0.2.md` line 98 settles the intent — `gaps [Gap]` is in the snapshot
payload — so this is a stale sentence in §4 rather than a disagreement. But it is
the sentence that decides whether N17 works at all, and §4's "three crossings" count
is now wrong: the payload carries at least six object kinds.

**Fix:** move `Gap` and `Rule` out of the never-consumed sentence, and reconcile the
crossing count with contract §1.2.

### B2 · `contributing_sources` is absent from the contract, and `ParameterTable` has no join target

Two halves of one problem, found independently by two readers.

`grep contributing_sources contract-v0.2.md` returns nothing. The contract argues
*from* N14 to justify `belongs_to` — line 64, *"an opaque id carries zero
admissibility bits into a pinned snapshot"* — and then omits the field that carries
those bits. The disposition's own early-publish ask (§5: *"one definition with
`contributing_sources` carrying a superseded document"*) is not satisfiable against
the contract as written.

The deeper half: for a `Part` or `FenceModel` the join traces cleanly —
`spec[i].Provenance.cites[j].belongs_to → contributing_sources[k].version_status`.
But **promoted facts become `ParameterTable` rows**, and `ParameterTable` has no
`contributing_sources`. The measurement that motivated N6 and N14 — *132 of 324
promoted facts, 40.7%, already cite a superseded document* — lands entirely in the
one type with nowhere to join. Same for `Warning.cites`, `Procedure.cites`,
`AssemblyStep.cites` and `Combination.cites`.

And there is no closure rule anywhere: nothing requires that a `SourceRef` cited
inside a snapshot has a matching `SourceDoc` in it. Invariant 8 requires a
*resolvable* `SourceRef`, which is a discovery-surface property — exactly the
property §2.5 spends three paragraphs arguing is worthless inside a run. A dangling
`belongs_to` reproduces the original defect with extra fields.

**Fix:** the contract already has the right shape — snapshot-level
`source_docs [SourceDoc]` that `contributing_sources` selects from. Say that in the
data model, add `contributing_sources` to the contract's `Part`/`FenceModel` gloss
and to §3.1's obligations, and add one invariant: *every `belongs_to` in a snapshot
resolves inside that snapshot.*

### B3 · The `_mm` fields reintroduce the undeclared rounding that contract §1.1 exists to prevent

Contract §1.1 is BINDING and its reasoning is explicit: *"a float arriving at the
boundary would be rounded somewhere undeclared"*, so quantities are integers in
thousandths with the verbatim lexeme alongside.

Twenty-three distinct field names in the data model end in `_mm` and are none of that.
They are whole millimetres, they carry no lexeme, and every worked example in §3.4
demonstrates the loss:

| Source | Published | Error |
|---|---|---|
| `POST REINF. FULL LENGTH -1"` | `HostEnd(−25)` | 25.4 → 25 |
| `POST LENGHT-(DEPTH+7)` | `Param(footing_depth, +178)` | 177.8 → 178 |
| `PANEL STIFFENER 70 1/4"` in a `70"` panel | `HostEnd(+6)` | 6.35 → 6, a **5.5%** error on the overhang the field exists to make visible |
| `to at least 22" above grade` | `Datum(grade, 559)` | 558.8 → 559 |
| the `92` channel | `HostStart(2337)` | 2336.8 → 2337 |
| §8's own N5 artefact, a 94″ Columbia rail | `nominal_length_mm = 2388` | 2387.6 → 2388 |

Nothing in this corpus is a whole number of millimetres. `7/8"` is 22.225 mm;
`2-7/16"` is 61.9125 mm. And the loss accumulates through exactly the arithmetic the
audit used:

> Thirteen T&G boards at 7″ fill a 91⅛″ clear opening. True: 13 × 177.8 = 2311.4 mm
> against 2314.575 mm — **3.175 mm of slack, which is ⅛″**. At whole millimetres:
> 13 × 178 = 2314 mm — **0.575 mm of slack**. The unit convention eats 82% of the
> fitting clearance, and it eats it silently.

That arithmetic is how `audit-response-v0.1.md` §2.1 proved `gap_after_mm = 0`
rather than a negative. Rounded, it no longer closes, and a curator would conclude
there is a gap where there is none.

This is not a request to change the rule. It is a request to *apply* it: the `_mm`
fields should be `Quantity` — which already carries `amount_milli`, `unit` and
`value_raw` — or be renamed to thousandths and carry the lexeme. Invariants 1, 7 and
8 are unenforceable over them as written.

### B4 · Tied ranks make resolution non-deterministic, against two BINDING promises

`rank` is *"ordering among admissible sources; lower wins"*. The shipped table ties
three times:

- `industry_standard` and `manufacturer_installation_instruction` both **3rd** for component dimension
- `tested_report` and `company_authored` both **2nd** for component dimension
- `manufacturer_installation_instruction` and `company_authored` both **1st** for installation step

No tie-break is defined in either document. This collides with *"Resolution honours
the policy, and the winning row records `admitted_by`"* and with *"a hash resolves to
the same bytes"*: two implementations, or one implementation across two builds, can
pick different winners, stamp different `admitted_by.rank`, and hash differently,
while both honour the policy.

Worth separating: the 3rd/3rd tie comes from the disposition. **The two
`company_authored` ties are new in v0.2** — the disposition's table has no
`company_authored` column at all — so they were never accepted by anyone.
`ai_proposal` is in `SourceClass` and absent from the data model's table with no
note.

**Fix:** break the ties, or state the rule (higher `curation_level`, then later
`issue_date`, then lexicographic `source_class`).

### B5 · Four types are named and never defined, and each blocks a §8 verification

| Type | Where | What it blocks |
|---|---|---|
| `SlotTarget` | §3.6, twice, never enumerated | N10. The string line — §8's own artefact — is not authorable |
| `PostSlot` | referenced, never defined, no `contains` | **N9, the one outright §8 FAIL.** `for_post_roles` landed on `ContainedSlot`, which lives inside a `PanelSpec`; post reinforcement has no slot to live in, and a panel-internal flag cannot say *which* of its two bounding posts it means |
| `Token` | §3.8 and contract §1.3 | N2. And a token row carries no `value_raw`, so `slope_method` publishes no verbatim lexeme — the loss N3 was accepted to prevent, reintroduced by the N2 modification |
| `Param`'s datum | §3.4 `Anchor` | N7. Every other anchor names an origin and a signed offset; `Param(key, delta_mm)` names a value and an offset and no origin |

`Param` deserves the extra sentence, because §3.4 stakes the whole case for `Span`
over `Fixed()` on it — *"`Param` is the anchor that earns the machinery"*. The source
reads *host length minus (a parameter plus a constant)*. The grammar cannot say
that: `Param` is a whole anchor, never a delta, so `HostEnd(−(Param(footing_depth) +
178))` is inexpressible. The document's rewrite to `Span{Datum(grade),
Param(footing_depth, +178)}` is an equivalence it never proves, and it holds only if
the post is set to exactly the footing depth.

**Fix:** enumerate `SlotTarget` and `Token` as `Anchor` is already enumerated;
define `PostSlot` with `contains: [ContainedSlot]` and move `for_post_roles` there;
either give `Param` a datum or let any anchor's delta be a small expression.

### B6 · Unconditioned rows have no representation — and N18 just made them admissible

This one is ours, opened by our own acceptance of N18.

Measured across the 601 dimensional structural facts in the store:

| Source class | Facts | With **no** condition keys at all |
|---|---|---|
| `manufacturer_installation_instruction` | 360 | **239 — 66%** |
| `hvhz_noa` | 138 | 5 — 4% |
| `engineering_approval` | 92 | 6 — 7% |

The class N18 admits is precisely the class that states values without the
conditions that make them safe. `Figures based on 4x4 hole=10", 5x5 hole=12", both
30" deep` states no exposure category and no HVHZ bracket.

Publish that row into a domain of `{exposure_category: [B,C,D], hvhz: [true,false]}`
and it asserts six things the source never said. Nothing in the model distinguishes
**"the source stated no conditions"** from **"this row covers every point in the
domain"**. That is `rationale.md` §1's G16 — an Exposure-B row bracketed `NON HVHZ`
recorded as *"HVHZ and Non-HVHZ"* — at a scale of 239 rows.

Note the alternative is no better: under `hit_policy = unique` an unconditioned row
matches every point and therefore collides with every conditioned row, so the 239
become a publish error rather than an honest gap. The model has no *correct* answer
for the commonest shape of fact in the corpus.

**Fix, and it is the shape you already chose for N25:** a row carries
`condition_basis: stated | assumed`, symmetric with `domain_basis: measured |
declared`. `stated` with empty conditions means *the source gave none* — such a row
is a fallback, never an assertion about the points it lands on, and Planning warns
when a value is applied to a condition its source did not state. One field, and the
same argument you made for `domain_basis`: the consumer of the distinction is a
warning renderer, not a reader.

---

## 2. Non-blocking — fix before v0.3

**Contract.** `RoleRef` survives alongside `PartType` with the identical gloss
("the job a part does") and is defined nowhere; the registry row, `POST /roles` and
obligation 5 still use the old noun. · The thirteen §3.1 obligations carry no
BINDING marker while the contract says *"everything else is this team's decision"* —
so N10, N11, N17 and N24's obligations are formally non-binding. · Line 113 sends
the reader to the **superseded** `knowledge-datamodel.md` §3 for types it does not
contain. · *"Eight binding items changed"* does not reconcile: seven BINDING blocks,
five changed. · *"obligation 10 — a warning is attached to its step — was false"*
misattributes it; that was `knowledge-datamodel.md` **invariant 5**, and v0.1's
contract had eight obligations, none about warnings. · `POST /source-refs:batch` is
in §4 prose but not in §1.5, the normative list of calls. · The status line says
*"Reviewed by both teams"* — this review is that review, and it is raising defects. ·
`SourceRef.source_ref_id` versus the data model's `SourceRef.id`; `VersionRef` is
missing `content_hash`. · The registry row labelled *"**Source** warnings … exempt
from the bundle rule"* invites reading the `SOURCE_*` codes as exempt; they are
platform codes and need both bundles.

**Data model.** §3.5 still presents `item.width_mm <= host.cavity_width_mm` as
established while §3.4 says it is unpublishable — in a section §0 tells the reviewer
to skim. · `coverage: Span` excludes `At([offsets])`, which the prose two paragraphs
later says survives. · N22's validity fields collide with invariant 6: the superseded
2023 approval's row and the current 2025 row sit on the same domain point, which is a
`unique` build error, and §8's own N22 artefact is exactly that row. One sentence
fixes it — *rows differing only in validity window are not a collision, and only rows
valid at the run date participate in the check.* · §6's header says *"Five held, four
changed, one is new"* over eleven invariants; by the annotations it is four, six and
one. · `Procedure` has no id, so `Warning.attaches_to{kind: procedure}` cannot
address one, and N13's whole benefit — *"a correction that reaches the other
fifteen"* — presupposes an identity. · `attaches_to` lost its REQUIRED marker in a
block that annotates everything else. · Invariant 11 (*"a gate is not a
`FenceModel`"*) is listed as publish-enforced and is a human judgement. · Invariant 4
is restated unchanged, and the audit's temporary-spacer rail — *"Use only one rail as
temporary spacer for your entire fence"* — is a BOM part placed twice and bought
once; §7.3 answers the `unplaced` half of N24 and not the placed-twice half. ·
`max_rack` is conditioned on `slope_method` and on option axes, neither of which §2.7
lists as a bindable dimension. · `SourceDoc.version_status` is enumerated `current |
superseded | unknown`; our store and `source-refs-design.md` use `active`. One word.

**Satellite documents.** `knowledge-design.md` was half-revised: its header now
points at `contract-v0.2.md`, but line 8 still routes the reader to the superseded
`knowledge-datamodel.md`, and §9 still solicits the §7 audit — which is answered,
dispositioned and folded in. That is the one document a new reader is most likely to
start from. · `README.md` says the audit found *"four places where the data
contradicted the proposal"* and lists §2.2, §2.4, §2.5, §3; the audit says **five**
and names §2.6 as well, which is one of the two the disposition itself called *"worth
more than the change they ask for"*. · `planning-asks-v0.2.md` §4 says *"we modified
five of your proposals"*, but the disposition correctly separates three modified
(N2, N18, N25) from two **answered with a decision** (N22, N29) — N29 we raised as a
question, not a proposal, and on N22 we offered both shapes. It attributes to us
positions we did not take. · `planning-asks-v0.2.md` §2.2 says the Chesterfield trace
carries *"three superseded approvals"*; it is four. · `README.md`'s *"four fifths of
the warnings … attached to no step at all"* drops the denominator: it is 19.9% of the
**841 positionally resolvable** instances of 1,038.

**One legacy divergence, ours not yours.** `rationale.md` and `system-overview.md`
say **1,988 facts** where everything since says **1,976**. Both numbers are in
`state-and-gaps.md`. We will reconcile it on our side and tell you which is right.

**And one thing we checked specifically:** our own `acceptance-open-questions.md` was
edited by you and nothing in it was softened. §4's assumptions and §5's methodology
survived intact, including the double-blind gates pass and *"where the two passes
disagreed with an earlier assumption of ours, the source won"*. The superseded
`knowledge-datamodel.md` gained a banner and nothing else — §3, §6 and §7 are
verbatim, so every citation in the audit still lands. *"Kept unedited"* is now
inaccurate and harmless; we would rather have the banner.

---

## 3. The three questions you asked us

### 3.1 `industry_standard` applicability — `material`, and it is a blocker rather than a caveat

You ranked `industry_standard` above `spec_sheet` and flagged the chain-link hazard
as *"a curation instruction rather than a schema change"*. Measured, it is worse than
that.

Of the facts in this corpus that would carry `industry_standard`, **42 of 43 come
from the two CLFMI chain-link documents** — 38 from the wind-load guideline, 4 from
the CSI product manual. The remaining one is a material-neutral ASCE 7-16 worked
example. The vinyl industry-standard documents we hold — the ARCAT vinyl masterspec,
the ASTM compilations, the Wheatland SpecCheck — yield **zero** facts between them
under current extraction.

So the class you just promoted above manufacturer spec sheets is, in fact
population, **97.7% wrong-material**. Ship the ranking without a bound `material`
dimension and the modal `industry_standard` row is a chain-link embedment figure
outranking a vinyl manufacturer's own spec sheet, silently, exactly as your §3.3
predicted.

**We need `material` bound before the ranking ships.** Values from this corpus:
`vinyl_pvc`, `chain_link`, `wood`, `composite`, `aluminium`. `system_type` we do
*not* need — `material` carries every case we hold, and we would rather ask for one
dimension we can populate than two we cannot.

### 3.2 The shared-host gap — it belongs on the joint, not the slot

`When installing rails leave a 1" gap between rail ends inside post to allow for
expansion` — twelve instances, six documents.

It is not a property of a slot, because the two members are in **different bays**.
It is a property of the **joint** where a member meets its host, applying when the
host receives two members. So:

```text
Joint {
  kind               butt | channel | groove | bracket | overlap
  shared_host_gap    Quantity | null     the gap between two members sharing this host
  reason             thermal_expansion | tolerance | …
}
```

`FrameSlot.joint` becomes this object rather than a bare enum. Two things fall out:
the gap is a `Quantity`, so it carries `25400` and the lexeme `1"` and B3 does not
bite it; and `joint` gains somewhere to keep the `channel_depth` and engagement data
that already sits loose beside it.

### 3.3 The fourteen `same_content_as` groups — ours, and we will resolve it in curation

Not a schema problem, and we do not want `SourceDoc` to carry the ambiguity.

We will designate **one canonical filing per content hash** and record the others as
an optional `also_filed_as: [{manufacturer, doc_type, source_path}]` on it, so
`belongs_to` stays single-valued. The canonical choice is a real judgement rather
than a coin toss — for the four-way group, the Barrette filing is
`engineering_approval` and the Industry-Standards filing is
`real_miami_dade_noa_vinyl_fence`, and those derive different `source_class` values
from identical bytes. We will pick the filing whose manufacturer matches the
document's own title block, which for that group is Barrette.

The one thing we would ask for: `also_filed_as` visible to a reviewer, because
*"which manufacturer published this"* is exactly the judgement the review queue
exists to make.

---

## 4. On the five you modified

We accept all five. Three notes.

**N2 — `value_type` on the table.** You are right and we were wrong. Splitting
`slope_method` from `max_rack` is better than what we asked for. The one cost is B5's
`Token`: a token row publishes no lexeme today.

**N18 — install manuals admissible at rank 4, level 2.** Accept, and your §7.1
self-assessment names the right risk. We add a second one — B6 — and one question.
Your argument turns on *"every span falls back to the engine's hardcoded 1800 mm"*.
If that fallback is **silent**, it contradicts your own obligation §3.2.4 (*never
fail a run — warned, named, unfulfilled lines instead*) and should be fixed whatever
happens to N18; if it already produces a warned line, N18 is a good decision with
less urgency behind it. Tell us which, because it changes whether N18 is a fix or a
workaround.

Also worth making explicit, because neither document says it: **N18 puts K4 on the
critical path.** Level 2 requires a person comparing a value to a page; a bounded
review requires the cell box; the cell box does not exist. So the chain is *cell box
→ level 2 → any structural coverage at all in a first snapshot*. Your
`planning-asks-v0.2.md` §1 asks us to raise K4 above K3 and we agree — this is the
reason, and it is stronger than the throughput argument you gave for it.

**N22, N25, N29** — accepted without reservation. `Snapshot.regime` with a typed
refusal is better than either option we offered, and the reasoning (a regime is the
frame the rules are written in, not a value they condition on) is one we will reuse.

---

## 5. One clarification we would like

**Gate hardware parts remain publishable.** §9.1 says a gate is published as a
`Gap`; `gate_hardware` is still a spine part type. A curator could reasonably read
the first as excluding the second and drop the one gate table this corpus publishes
cleanly — `Product Description | Available Materials | Support Gates Up To`, with
hinge ratings of 35, 75, 100 and 150 lbs across ten entries. One sentence in §9.1 saying that gate
*hardware* is an ordinary `Part` and only the gate *model* is out of scope would
keep it.

---

## 6. What we are doing now

Reordered per your ask, and unblocked by this review either way.

1. **The cell bounding box** (your §1, our K4) — above crop cost. Agreed.
2. **`GET /source-refs/{id}`**, against the seven fixture records.
3. **Revoke `cross_family_verified`** (K1). It drops 324 facts out of promoted.
4. **The two early publishes** you asked for — one `ParameterTable` with a
   `declared` domain, one definition with a superseded `contributing_source` — held
   until B2 and B6 land, since both exist to test exactly the fields those defects
   name.
5. **The `SOURCE_*` list and the eleven-warning starter list**, with params and
   verbatim exemplars.

Items 1–3 need nothing from you. Item 4 needs B2 and B6.
