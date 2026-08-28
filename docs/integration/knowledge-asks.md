# What this platform needs from Planning, and what it answers back

```text
Status:   v0.2, 2026-08-27. Working list, maintained by the Knowledge platform team.
Mirror of: planning-asks.md, which is the same document pointing the other way.
Note:     Nothing here touches contract.md. It is FROZEN at v1.1 and none of this
          proposes changing a BINDING item. Two entries in §2 are candidate
          amendments already logged in amendments/CANDIDATES.md; they are repeated
          here because they now block work rather than merely waiting.
Reviewed: docs/integration-contract/fixtures/snapshot-example.json and its README,
          as of 2026-08-26. §1 is a defect list against that file.
Measured: Every number is from workspace/indexes/evidence.db and
          workspace/snapshots/02a8833b….json, read 2026-08-27.
```

---

## 1. Your fixture — reviewed

Thank you for building it, and the README's third reason is right: this is worth
more during design than after. It found things on **both** sides. One of your
choices is ahead of our own design and we are adopting it (§1.5).

We ran your fixture against the closed vocabularies and the closure rule our
publish gate already enforces. Eleven findings, in the order they would stop a
load.

### 1.0 The defect list

| # | Where | Finding | Severity |
|---|---|---|---|
| 1 | `parameters[].rows[].provenance.source_class` | `"manufacturer"` and `"engineer_sealed"` are not in the closed vocabulary | **rejects** |
| 2 | `gaps[0].cites[0]` | `belongs_to: "sha256:fixture-doc-c"` has no `SourceDoc` — invariant 12 | **rejects** |
| 3 | `parameters[].task` | `"structural"` / `"descriptive"` are not `TaskCode`s | **rejects** |
| 4 | `warnings[].cites` | a single object; the contract says `cites [SourceRef]`, a list | **rejects** |
| 5 | `parameters[1].rows[0].value` | a bare string `"stepped_only"`; `Token` is `{key, value_raw[]}` | **rejects** |
| 6 | `parameters[0].rows[2]` | `provenance.version_status: "active"` while the `SourceDoc` it cites is `superseded` | inconsistent |
| 7 | `parameters[].scope` | `kind: "product_line"`; the contract says `Part \| FenceModel` | mismatch |
| 8 | `gaps[]` | top-level `code`/`params`/`message` rather than `because {code, params}` | mismatch |
| 9 | `warnings[]` | no `lang_basis` | missing |
| 10 | `gaps[].subject` | `{kind, ref}` vs `EntityRef {kind, id, tenant}` | mismatch |
| 11 | `warnings[5].severity_lexeme` | `""` rather than absent/null | minor |

**1 — `source_class` is a closed vocabulary and neither value is in it.** The eight
are `sealed_approval`, `tested_report`, `industry_standard`,
`manufacturer_installation_instruction`, `spec_sheet`, `marketing`,
`company_authored`, `ai_proposal`. `engineer_sealed` is presumably
`sealed_approval`. **`manufacturer` is the interesting one**, because it is
ambiguous across three real classes — and that exact ambiguity is what §1.4's v0.2
revision was written about: 69 documents and 44.6% of our facts were filed as
`spec_sheet` for want of a class, which made them inadmissible for the very task
they are about. If the fixture means "the manufacturer said it", the class depends
on *which document* said it, and that distinction is load-bearing for admissibility.

**2 — closure is violated, and it is BINDING.** `gaps[0]` cites
`sha256:fixture-doc-c`; `source_docs` holds only `fixture-doc-a` and
`fixture-doc-b`. Our builder makes this unrepresentable — minting a `SourceRef`
registers its `SourceDoc` as a side effect — so a snapshot from us cannot contain
it, and `verify()` refuses one that does. Worth fixing in the fixture so your
loader is not accidentally tolerant of something it will never receive.

**3 — `task` selects the source-policy row**, so a code outside the vocabulary
silently matches nothing. The four in §1.4 are *Structural parameter*, *Component
dimension*, *Installation step*, *Product description*. We read those as
`structural_parameter`, `component_dimension`, `installation_step`,
`product_description` — **confirm the exact spellings**, because this is a closed
registry we both key on and neither document writes them in code form.

**4 — `cites` is a list.** `Provenance.cites` is `[SourceRef]` and every warning we
publish carries a list, sometimes with more than one entry — a warning printed on
fourteen pages of two documents genuinely cites several.

**5 — a `Token` is not a bare string.** The datamodel is explicit: `Token {key,
value_raw[]}`, *"a token carries its lexeme too"*. Publishing `"stepped_only"`
loses the sentence the document actually used — *"They should be only installed
using the slope method"* — which is what a curator needs beside the token, and it
reintroduces exactly the loss N3 was accepted to prevent.

**6 — the lapsing row contradicts itself, and it also contradicts your covering
note.** Your message described that row as `version_status: superseded`. In the
file it is `"version_status": "active"`, while the `SourceDoc` it cites
(`fixture-doc-b`) is `superseded`. Both cannot be right. This matters more than a
typo, because §1.4 makes `version_status` a **policy axis** — if the row and the
document disagree, which one does your resolver rank on? We would say the row's
`Provenance` must agree with its cited `SourceDoc`, and we can make that a publish
check. Say if you would rather it did not.

**7 — `scope` must be a `Part` or a `FenceModel`.** `product_line` is neither.
Ours had the mirror-image bug: an earlier draft scoped a table to a *part type* id,
which is also neither. §1.3's referent set is narrow on purpose.

**8 — `because {code, params}` versus flat `code`/`params`/`message`.** The
contract nests them under `because`; more importantly it has **no `message`
field**, and adding one is not neutral. `code + params` exists precisely so a gap
*"renders in both locales"*; a free-text English `message` beside it will become
what implementations actually display, and the locale path rots. Your README makes
this argument correctly for warnings — the publisher's `code` overlay is carried
without being promoted, and `text_raw` still renders. For gaps it is the other way
round: there is no `text_raw`, so `because` is the only rendering mechanism, and a
`message` competes with it.

**9 — `lang_basis` is missing**, and it is the field that keeps obligation 10
honest. Every warning we publish carries it, and every one currently reads
`assumed` — **nothing in our corpus is `measured`**. A loader that trusts `lang`
without reading `lang_basis` is trusting an assertion nobody verified.

**10 / 11** — `subject` shape and the empty-string lexeme. On `subject` we are
*worse* than you: ours is currently a bare element-id string. Yours plus a `tenant`
is the right target and we will move to it. On `severity_lexeme`, absent and empty
are different facts: 24 of our 282 warnings have **no** lexeme, and we emit `null`
rather than `""`.

---

Your four questions, answered against the file.

### 1.1 `max_span_mm` — you guessed wrong, in three ways

**(a) It is not a condition → value lookup. It is a table of design points.**

Your table has exactly one row per `(exposure, hvhz)` point. Real ones do not. From
the clean text layer of `doc-1085f7c65c47` p17:

```
Wind Exposure | Footing Depth | Max. Post Spacing
B | 30" | 97" | NON HVHZ            ← the annotation spans
B | 24" | 66" |                        the PAIR, not the row
C | 36" | 88" | HVHZ and NON HVHZ
C | 30" | 68" |
D | 36" | 75" | HVHZ and NON HVHZ
D | 30" | 56" |
```

Each exposure offers **two ways to build it**: a deeper footing buys a wider span.
So at `(C, hvhz false)` **both** 88″ and 68″ are valid — two rows, one domain
point, `hit_policy: unique` violated, and no dimension available to break it.

The physics confirms the reading rather than the layout alone. ASCE 7-10 Kz at
0–15 ft is B 0.57, C 0.85, D 1.03; at fixed footing depth, permissible tributary
width should scale as 1/Kz:

| | predicted | actual |
|---|---|---|
| D/C | 0.825 | 56/68 = 0.824 |
| C/B | 0.671 | 68/97 = 0.701 |
| D/B | 0.553 | 56/97 = 0.577 |

Read the other way — depth conditioned on HVHZ — the table has footing depth
*decreasing* 30″ → 24″ as wind load rises at B while *increasing* 30″ → 36″ at C
and D, which no code provision does. See §2.4; we cannot publish this until we know
what you can consume.

**(b) `uncovered` is being asked to carry two different facts.**

You leave exposure D uncovered for both HVHZ values. Our real gap is at
`(B, hvhz true)` — and it is **not a coverage hole, it is a refusal.** Both B rows
are bracketed NON HVHZ; the approval does not extend to exposure B in the
high-velocity hurricane zone at all.

Rendered as `uncovered` that reads *"we may not know this table's extent"* when the
source says *"not approved here."* A planner treating it as a hole and proceeding
is building outside an approval. See §2.3.

**(c) Expiry and supersession are independent axes, and we cannot produce a row
that is both.**

Measured across 144 documents:

```
carry an expiration_date at all ……………… 4    (2028-04-04, and 2029-03-13 ×3)
of those, already lapsed ………………………… 0    every one is in the future
version_status: active / superseded / unknown …… 3 / 9 / 132
superseded AND carrying an expiry ………………… 1
```

`version_status: superseded` is a fact about the **document** — a later NOA named
it as predecessor. `valid_until` is a fact about the **authority** — the approval's
own expiry. Eight of nine superseded documents have no expiry at all, so
superseded-and-unexpired is the normal case, not an edge case. Keep exercising
both; do not assume they move together. And note that **your §2.2
lapsed-authority test cannot be demonstrated against our corpus as it stands** —
there is no lapsed document in it.

### 1.2 Provenance placement — yes, per row, exactly there

Right, and it has to be per-row rather than per-table because one parameter's rows
genuinely come from different documents at different levels. Our Chesterfield
footing values arrive from a sealed NOA *and* from an installation manual.

Three things to change while you are in there:

- **`source_class` values are invalid** — defect 1.
- **`curation_level: 2` on five of your six rows is optimistic.** Ours will be `1`
  on everything for the foreseeable future: the level-2 population is zero and
  stays zero until the review verb ships (§3.2). A fixture that is mostly level 2
  will not exercise the rejection path, which is the path that will actually run.
- **`unknown` is 92% of our corpus** — 132 of 144 documents. Your fixture has no
  `unknown` row. It ranks below `active` and must never be coerced to it.

And confirming a negative: `admitted_by` is correctly **absent**. Per §1.4 as
amended you apply the policy and record it on the run, not on the row.

### 1.3 Warnings — the block is well thought out; four corrections

`attaches_to` has **seven** kinds. You use six — document, step, product,
maintenance, warranty, procedure — and the seventh is **`model`**.

In practice only three occur in what we publish today, and the distribution is
lopsided enough to build for:

```
document …… 267        step …… 13        warranty …… 2
product, model, procedure, maintenance …… 0
```

Then defects 4 (`cites` must be a list), 9 (`lang_basis` missing) and 11
(`severity_lexeme: ""`).

**On your deliberately uncited warning.** Your README argues it is legal and that
counting them is the useful signal, *"§1.1 makes `SourceRef.id` opaque and
unbuildable, so nobody without the Discovery surface can mint one."* That reasoning
is right about warnings **you** author. It does not apply to ours: our publish gate
**refuses** a warning with no `cites`, on obligation 3. So the count you receive
from us will be zero, and if your loader needs the unattributed path exercised, it
will have to come from your own side. Worth agreeing explicitly rather than
discovering.

**One thing in that block will never fire, and you should know before you rely on
it.** Your three identical freeze-thaw footnotes exist to prove
`report/annexe.py` collapses duplicates into one entry carrying `instances`. The
repetition is real — we hold 83 instances of one such sentence across fourteen
pages — but **we collapse it before publishing**. Measured on the published
snapshot: all 282 warnings have **distinct** `text_raw`, and the repetition is
carried instead as multiple entries in `cites` — **76 of 282 warnings cite more
than one source**.

So your collapse path will receive nothing from us, and the count you want is
`len(cites)`, not a duplicate count. Either we should publish duplicates and let
you collapse, or you should read the cite list — worth deciding, because right now
both sides implement the same de-duplication and only one of them ever runs.

**Three things in that block we think are right and want to keep.**
`CAUTION` beside `WARNING` unnormalised is right, and it is worth
knowing the real distribution is wider than English: our published lexemes include
**`ADVERTENCIA` (16)** and **`AVERTISSEMENT` (15)**, neither of which is in the
datamodel's enumerated list, and `NOTE` alone is 175 of 282. And a warning attached
to a `procedure` you do not model, returning `unplaceable`, is the right shape.

One measured fact that will affect your loader: **no published warning carries a
`code`.**

```
warnings carrying a code …… 0 of 282
```

The overlay is optional and nothing populates it yet. Everything renders from
`text_raw`, verbatim and untranslated. Your `not_pool_rated` example is the right
*shape* for when we do.

### 1.4 `source_docs` supersession — right shape, right direction, and you found a bug

`superseded_by` on the `SourceDoc` is the contract's shape and it is what we
intend, and **you have the direction right**: the superseded document names its
replacement, not the other way round. Marking the wrong side once labelled every
current NOA in this corpus superseded, so this is worth getting right in a fixture.

**We are not currently publishing the field.** Ours emits six keys:

```
content_hash · expiration_date · issue_date · source_class ·
version_status · version_status_basis
```

`superseded_by` is absent. The edges exist in the store — 24 `supersedes` and 24
`superseded_by` — so this is a publisher defect on our side, not a missing fact. It
is on the fix list ahead of anything that publishes `contributing_sources`.

Two things about the shape when it arrives:

- **`source_docs` is keyed by content hash, and documents collapse into it.** One
  SHA-256 here is filed **four times** under four manufacturers with four
  `doc_type`s, and those map to **two different source classes**. Four documents,
  one `SourceDoc`, one `source_class`. Which class wins is a curation decision on
  our side, not a schema one; the alternates will travel as `also_filed_as`. See
  §3.3.
- Your fixture has `superseded_by` as a single hash. It must be a **list**. At
  document level the fan-out is wide: `doc-8727ba0fd4d4` is superseded by **7**
  successors, and three more documents by 6, 5 and 4. Some of those collapse when
  keyed by content hash, but not all, and one-to-one is not a safe assumption.

### 1.5 What the fixture gets right — including one thing we are adopting

- **`condition_scope` is present on both tables.** It is BINDING, our own draft
  design omitted it, and we found that out from a reviewer rather than from the
  contract. **You are ahead of us here and we are adopting your shape.**
- **The unconditioned fallback row** — `conditions: {}` with `condition_basis:
  "stated"` — is exactly obligation 15 / §3.8.1, and `uncovered: []` beside it is
  right: a fallback covers the whole domain.
- **`disputed` with `on` as a sibling key** rather than nested. The contract writes
  `disputed{on: …}`, but flattening the discriminator is simpler to parse and loses
  nothing. **We will match yours** unless you would rather we nested it.
- `amount_milli` as integers with `value_raw` carrying the lexeme; no float
  anywhere in the file.
- `superseded_by` direction (above).
- Deliberately unmistakable ids — `FIXTURE-*`, `not-a-real-tenant`. That discipline
  is the reason a hypothesis does not quietly become a fact nobody checked, and it
  is worth keeping.

---

## 2. Questions we need answered

Ordered by what it costs us if the answer is late.

### 2.1 Define `curation_level` 0 versus 1

`amendments/CANDIDATES.md` C1. Never defined, and three binding mechanisms read it.
Your `min_curation` rows are written against a scale we have not specified, and
§1.4's tie-break resolves by higher `curation_level` **before** `issue_date`.

Our provisional reading, which we will publish against unless you object:

| | |
|---|---|
| **0** | asserted, with no resolvable citation |
| **1** | cited — a citation exists and resolves — but no person has confirmed it supports the claim |
| **2** | a person compared the value to the source image |

**Cost of leaving it:** zero until we publish, then unrecoverable. Rows minted under
one reading cannot be re-levelled afterwards, because the snapshot is write-once.

### 2.2 Is a slot-structure edge a "value" under invariant 8?

`amendments/CANDIDATES.md` C3, narrowed since it was logged, and the narrowing is
good news.

**Membership of parts is citable.** We had assumed it was not. It is: a PE-sealed
drawing sheet carries a bill of material naming the components —
`doc-3c8ab51045c7` p12, `MODEL: CHESTERFIELD - 8'X 6`, listing the routed post, the
tongue-and-groove picket, a 92″ galvanised steel channel, lock rings and set
screws. Rank-1 `sealed_approval`, and **more complete** than our own
hand-researched graph, which omits three of those parts.

So the question is narrower: the BOM says *which parts*, not *how many slots* — it
lists `2 X 6 DECO RAIL` once for what is two rail positions. **Does the slot
structure — two rail positions, an infill pattern, a fixing basis — count as a
value needing its own `SourceRef`?** If yes we cannot publish it without an
amendment; if no we publish it as authored structure and cite the BOM for
membership.

### 2.3 Is there a representation for *not approved*, distinct from *not covered*?

New, from §1.1(b). `uncovered` says *"no row covers this point."* We need to say
*"the authority explicitly does not extend here."*

They render differently and they should plan differently: an uncovered point may be
closed by finding another document; a refusal cannot be, and a planner must not
proceed as though a value might turn up. Does your evaluator have a shape for it,
or should it publish as a `Gap` — and if so, which kind? None of the eight fits
cleanly.

### 2.4 Can a `ParameterTable` row carry a paired value?

From §1.1(a). The source publishes `(footing depth, max span)` as one design point;
an installer picks the pair, not the span. Three options we can see:

1. one table whose value is a pair, which `value_type` cannot currently express;
2. two tables where footing depth is an input **dimension** of the span table;
3. one table with `hit_policy: collect_min` / `priority` over the pairs, losing the
   coupling.

We can publish any of the three. Only you know which your evaluator can consume,
and **(3) silently discards the cheaper compliant option** — at exposure C on a
40 ft run that is 7 posts versus 9.

### 2.5 Confirm the `TaskCode` spellings

Defect 3. Closed registry, both sides key on it, and neither document writes the
codes in machine form.

---

## 3. Corrections we owe you

### 3.1 Your §1 ask is aimed at the wrong object

You asked for a **cell bounding box**, called it the one thing above everything
else, and asked us to reorder for it. We did the measurement and it does not do
what you need.

```
review-queue pages …………………………………………… 44
of those carrying `table_not_reconstructed` …… 44   (all of them)
`table` elements on those pages ………………………… 0
readings sitting on a reconstructed table …… 0 of 1,225
```

The geometry recovery you asked us to prioritise applies to 594 pdfplumber tables
on an entirely **disjoint** page set. It would box 17,499 cells and **not one row
of the queue you are building**.

The obvious substitute does not work either. Deriving a box from the row label's
band intersected with the column label's band is ambiguous on exactly these tables:

```
distinct (row_label, col_label) pairs ……………… 194
pairs addressing more than one cell ……………… 114
readings with an empty row or column label …… 90

doc-32e36a07ab44 p11, ('B','FOOTING DEPTH'):
   row 0 → 30"     row 1 → 24"     ← one band, two values
```

A reviewer shown that band sees 30″ *and* 24″ and is asked to accept 30″ — a
*misleadingly* bounded task, worse than an unbounded crop, and those two rows are
precisely the pair whose confusion is our own G16 critical finding.

**And the queue cannot record the answer even with perfect geometry.** No column
label in the whole queue is HVHZ; all 426 HVHZ mentions live in a free-text notes
field. The thing under review on these tables is the applicability bracket, and
there is nowhere to put it.

We are building: a field that can hold the bracket, an honest row band with the
bracket transcribed, and a three-way verdict — accept / reject / **bracket-unclear**
— rather than a fast binary on the wrong region.

### 3.2 N18: human review is further out than you assumed, and you asked to be told

Your §4 said, in writing: *"If human review is further out than we are assuming,
our ranking is worse than the strict exclusion you proposed, and we would want to
know that now."*

It is. `reviewer` is NULL on all 1,225 readings, nothing in our package writes
`accepted` or `corrected`, and the level-2 population is zero. Every admissible
class for `structural_parameter` is gated at level 2, so **the admissible set is
empty and stays empty until we ship the review verb.**

We have reordered: the review loop now comes before the publishing slice. That is a
change from what we told you at ratification, and it is the direct consequence of
your N18 note.

### 3.3 Fifteen duplicate-content groups, not fourteen

Our own notes say fourteen. Measured: 40 `same_content_as` edges over 32 documents
form **15** connected components — fourteen keyed on an identical SHA-256, and one
keyed on **identical extracted text with different bytes**. The fifteenth is the
hard case, and it is the one `also_filed_as` exists for.

### 3.4 Two defects in what we have already published

- **`Gap` carries no evidence.** The contract defines `because` and `cites`; our
  published gaps have neither, and `disputed` has no `on:` discriminator. 63 gaps
  have already crossed this way. `illegible_source` tells a curator to open a crop
  and gives them no crop to open. Your fixture is **ahead of ours** on this shape.
- **`SourceDoc` omits `superseded_by`** — §1.4 above.

Both are on our fix list ahead of the next publish.

---

## 4. Still open from your side

Logged without pressure; none of it blocks us this week.

**All four are now closed. Delivered in `conversation.md` T2, 2026-08-27.**

1. **Your five confirmations** — N2, N18, N25, N22, N29. ~~We have never responded.~~
   **CLOSED.** N18 answered in §3.2; the other four accepted as stated.
2. **§6c** — publish continuous-rail products as a `Gap` until the machinery
   exists. **CLOSED — confirmed** in T2 §2. The supply lengths are stated in four
   documents (16 ft White, 12 ft Blend). Two measured findings went back with it:
   a rail spans more than one bay (192″ against 96″ centres; 144″ against 72″), and
   **post spacing depends on the colour line**, not only on wind exposure — Blend
   runs 72″ centres on 2×6 rails. A model keying spacing on the product alone is
   wrong by a quarter for Blend.
3. **§6d** — the stagger constraint, 20 instances, all publishing as
   `unquantified`. **CLOSED — now in our gap list.** We tried to falsify their
   claim first and failed: the one dimension sitting beside the rule in an OCR'd
   caption is gate clearance, not a stagger offset. One caveat sent back — the
   heading is stored as two elements, so element-level counts double-count captions.
4. **`would_close` quality.** You asked whether that sentence is hard to produce at
   publish time and asked for a sample of ten. **CLOSED — sample delivered**, and
   producing it exposed a defect of ours: 63 published gaps carry **4 distinct
   `would_close` sentences**, 51 of them identical. Not hard to produce; we produce
   it badly. Logged as **G40**.

Two of their §5 questions were answered in the same turn, though they were never
on this list: §5.2 (the 1″ rail-end gap — same cut-plan constraint as §6d's
stagger, and the two appear in the same bullet list) and §5.1 (`industry_standard`
scope — we argue the guard belongs at publish time on our side, not as a condition
dimension they bind at run time).
