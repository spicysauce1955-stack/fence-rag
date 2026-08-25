# Review of v0.4 — the four items

```text
Status:   Reply to `boundary-delta-v0.4.md`. From the Knowledge team.
Verdict:  Two accepted with additions. One accepted in substance and wrong in shape.
          One cannot be confirmed — it is not already true of what we publish.
Standard: Same as the first two rounds. A gap per item, with the document and page.
Counts:   Measured against the store as built 2026-08-24 (144 documents, 2,147 pages,
          1,976 facts, 324 of them human-gated). G31 records a ±6 drift in elements
          and quality issues on rebuild; nothing quoted here sits inside that drift.
```

## At a glance

| | Item | Verdict |
|---|---|---|
| 1 | `Gap` has a shape | **Accept.** `kind` is short by two; `would_close` is writable, but two of your six kinds close in *your* repo, not ours |
| 2 | Planning applies the source policy | **Accept.** The extra volume is nothing. But supersession is on none of your three axes, and it is where 40.7% of our gated facts live |
| 3 | `Member.continuity` | **Accept the field, reject the binary.** You asked to be told before building against two values. It is more than two, in three measured ways |
| 4 | Tables read only whole-project facts | **Cannot confirm.** Two condition keys already in the store break it. The rule you want is a different rule, and it costs you nothing |

---

## 1 · `Gap` finally has a shape — accept

Having a shape to publish into is a net reduction in work, as you say. Two additions.

**`kind` is short by two.** Both recur, both are measured, and neither can be honestly
filed under the six.

**`conflict`** — two admissible readings of the same subject, disagreeing. Add a
discriminator, because it happens in both directions: `conflict{ on: value | conditions }`.

- *on: conditions.* **108 of our 324 human-gated facts (33.3%)** are published carrying
  `"readers did not independently agree on the applicability bracket; see the page crop"`.
  The value is certain; which conditions it applies under is not. `uncovered_condition` is
  a hole in the domain and this is not one; `missing_value` is false; `unquantified` is
  false. Today we bury it in an underscore-prefixed free-text key *inside* `conditions` —
  which under §1.3 would publish as a condition dimension. That is our defect and we are
  disclosing it; it also has nowhere to go among your six.
- *on: value.* `bufftech-simtek-fence-install-guide.pdf` **p28** — *"Use two pieces of ½"
  rebar in each **hinge, latch and end** post"* — against **p35** of the same guide:
  *"USE (2) PIECES OF 1/2" REBAR IN **EACH POST**."* Prose against drawing, one document,
  two different conditions on one value. **All five** guides that carry the drawing line
  also carry the prose line.

**`illegible_source`** — the source states the value and we cannot recover it. **73 pages**
carry `table_not_reconstructed` at 0.588 digit recall; 172 more carry `low_ocr_confidence`
and 81 a mojibake text layer. `missing_value` sends a curator to find another document.
This sends them to open the crop, which is a different work item with a different cost and
a much higher success rate. Collapsing the two is the difference between "nobody wrote it
down" and "we could not read what they wrote".

**`would_close` is writable — for four of your six kinds.** For `uncovered_condition` it
writes itself; for `missing_value` and `unquantified` a curator can name the document that
would settle it. For `unmodellable_entity` and `unmapped_part_kind` the closing action is a
schema change **in your repo** — the gate gap closes when `PanelSpec` gains handedness,
swing direction and a fixed leaf, and no curator here can do that. So keep the field, and
add `closes_by: knowledge | planning`, so your review queue never shows a curator work only
an engineer can do. That is one enum, and it is what makes `would_close` a work item rather
than a wish.

---

## 2 · Planning applies the source policy — accept, with one axis missing

The reasoning is right: only the planner knows the task. `admitted_by` comes off our
`Provenance` and we will publish rejected-by-policy rows.

**The extra volume is not a cost.** The whole fact store is 1,976 rows, 324 of them gated.
Publishing losers alongside winners is not a number worth discussing at this scale, and we
would rather your graph could say *"a spec sheet was inadmissible here"* than have the value
silently not exist.

**But the policy has three axes — task, source class, role — and supersession is on none
of them.** Once you apply it, that becomes your problem, and the numbers are bad:

- **132 of our 324 gated facts (40.7%)** come from a document whose `version_status` is
  `superseded`. Chief among them is `NOA-22-0616.10-CertainTeed-SimTek-molded-fence-2022-2028-superseded.pdf`,
  which supplies most of the height-conditioned footing grid.
- **Only 3 of 144 documents are `active`. 132 (91.7%) are `unknown`** — we have no
  evidence either way. A policy that keyed on supersession without an honest third value
  would reject nearly everything or admit nearly everything.

A superseded NOA and its replacement are the same source class, the same role and the same
task. Your policy ranks them identically. **Ask:** put `version_status` — `active | superseded | unknown`
— on `Provenance` and make it an axis, with `unknown` a real value that ranks below
`active` rather than being coerced to one. We will publish it honestly, which mostly
means `unknown`.

**And one commitment from us, now that class is load-bearing.** We hold 40 `same_content_as`
pairs — byte-identical files filed under different manufacturers — and **18 of them
currently carry a different `doc_type` on each side** (e.g. the same Miami-Dade NOA filed as
`real_miami_dade_noa_vinyl_fence` on one side and `unspecified` on the other). Informational,
that is untidy; load-bearing, it means the same bytes are admissible or not depending on
which filing crossed. We will publish **one source class per content hash**, with the other
filings recorded as `also_filed_as`. Please treat that as a promise you may rely on.

---

## 3 · `Member.continuity` — accept the field, reject the binary

The field is necessary and your evidence for it is ours. You asked to be told before
building against two values if the distinction is more than binary. **It is, three times.**

**(a) It is not a property of the member. It is stock length against bay width, and stock
length varies by colour.** `bufftech-gate-install-guide.pdf` **p44**: *"Standard rails are
supplied in 16 foot lengths **for White (12 foot rails for Blend products)**"* — also
`bufftech-installation-guide-40-40-70743.pdf` p38 and `bufftech-gate-installation-guide.pdf`
p44. Our maximum post spacing is 97″ (21 facts). A 16 ft rail spans two bays and threads one
post; a 12 ft rail reaches one and a half, so it cannot thread a post without a mid-bay
joint. **The same member is `continuous` in white and `per_bay` in blend**, and colour is a
condition dimension, not a member field.

**(b) Terrain collapses it.** *"For rolling terrain, rails may need to be cut to 95½""* —
10 elements across 5 guides, `bufftech-simtek-fence-install-guide.pdf` **p38** among them.
95½″ is one bay. So a nominally continuous rail becomes `per_bay` **on the bays that are
graded** — a bay-level fact deciding a member-level field. This is item 4 arriving from the
other direction.

**(c) The constraint that matters is not carried by either value.** Same page, next line:
*"The starting point for rails should be staggered from post to post for bottom/mid/top rail
**for maximum strength**"* — 77 instances, with its own figure (*"STAGGER RAIL ENDS FOR"*,
p39/41/43/45). Three continuous rails in the same bay must **not** share a joint position,
and it is a strength requirement rather than a preference. `per_bay | continuous` cannot say
it. Your obligation 11 already has the right shape — a `requires` edge with
`exclusive_with` — so this needs a home, not a new mechanism.

**Ask:** publish `stock_length: Quantity` and let your side derive continuity from it against
the resolved spacing; keep `continuity` as an authored override for the cases where a guide
states it outright and no length is given. Then colour, terrain and spacing all land where
they already live, instead of being flattened into one boolean at authoring time.

*(One thing that is fine as designed: continuity differs by course within a single assembly —
`CLFMI-Product-Manual-CSI-Section-32-31-13-Chain-Link-Fence-Gates.pdf` **p15**: *"install 21
ft. lengths of rail continuous thru the line post … Bottom rail or intermediate rail shall be
field cut"*. Top continuous, bottom per-bay. That works if the courses are distinct members,
which we read them as. Confirm and it is closed.)*

---

## 4 · Tables read only whole-project facts — cannot confirm

> *"This is already true of everything this platform publishes."*

It is not, and we would rather say so now than after you build the ordering rule around it.
Obligation 13 names its site facts exhaustively — exposure, hurricane zone, jurisdiction,
code edition, material — and then forbids *"a run, a station, a bay or a panel"*. Two keys
already in the store fall outside that list.

**Fence height — 54 facts, including the largest structural grid we hold.** The footing
table on `NOA-22-0616.10-…-superseded.pdf` **p6** is conditioned on `fence_height: "Up to
48\""` and `"49\" to 76\""` — 19 depth and 21 diameter facts. Height is not a site fact. A
project with 6 ft privacy along the back and 4 ft picket at the front — the ordinary case —
has two of them, one per run. Under 13 as drafted, that table is unpublishable.

**Post role — 68 elements across 6 documents.** *"Use two pieces of ½" rebar in each hinge,
latch and end post"* (`bufftech-simtek-fence-install-guide.pdf` **p28**, and 67 more).
*"All hinge and latch posts require concrete to fill the post inside"*
(`bufftech-installation-guide-40-40-70743.pdf` **p5**). And a **wind-code** requirement
conditioned on it: *"Ready-to-Assemble fence styles require post inserts in most post
configurations (**not needed in corner posts**) to pass wind code regulations"*
(`2024-Freedom-VF-Catalog-01-24_SpecialOrderCatalog.pdf` **p11**). Post role is
station-level by your vocabulary.

**Why we think the rule you want is a different rule.** What breaks up-front expansion is a
condition naming **an instance** — station 7, bay 3 — because that instance does not exist
yet. A condition naming a **closed enumeration** does not break it at all: publish one row
per post role, per height bracket, per terrain class, expand the whole product once before
any geometry, and bind the key when the station or bay arrives. The table is still fully
expanded up front; only selection moves later. You lose nothing you named as the reason for
the rule.

**Ask:** restate 13 with the vocabulary you already chose for obligation 12. A condition key
declares `condition_scope: site | run | post | bay | panel`, drawn from the same five. A
table whose keys are all `site` resolves at snapshot expansion; narrower keys bind at their
own scope. What is banned is an **instance reference**, not a narrow scope. The symmetry
with 12 is exact, and 12 is already binding.

If you would rather not widen it, the fallback is that height and post role move into
`scope`, which means one `ParameterTable` per height bracket per post role — the same data,
multiplied out, with the conditions no longer legible as conditions. We will do it if you
decide so, but it is worse, and `uncovered` stops meaning anything useful.

---

## What we are not asking for

Nothing about your internals, your pipeline phases, your fact-space layering, the four
extension seams or the retracted entity. Your rule stands both ways: those are yours, as
`docs/curation/` is ours.

The two corrections you list — the downward truncation and the position-dependent fallback
row — are in our repo and match what we measured. Nothing further from us on either.

## Where this leaves the four

**Items 1 and 2 are agreements**, subject to two `kind` values, one `closes_by` enum and one
`version_status` axis; none is a redesign and all three are additive. **Item 3 is an
agreement about the field and a disagreement about its type** — do not build against two
values. **Item 4 is the only one where we are saying the premise is wrong**, and it is the
one worth ten minutes of your time, because the fix costs you nothing and the fallback costs
us the legibility of every conditional table we hold.

Everything in `audit/05-acceptance-open-questions.md` §6 stays unblocked either way.
