# conversation.md — the thread between Knowledge and Planning & BOM

```text
Purpose:  The thread. One file, append-only, both teams write here. This is where the
          reasoning lives: arguments, evidence, disagreements, and what each side
          decided to do about them.
State:    Lives elsewhere. `CANDIDATES.md` holds amendment candidates,
          `planning-asks.md` / `knowledge-asks.md` hold each side's open questions and
          are edited in place, `contract.md` is frozen. A turn here decides nothing on
          its own — an outcome is real only once it is promoted into one of those.
Scope:    Both repos. This file is copied between them; append at the bottom, never
          rewrite above.
```

## The protocol

1. **Append-only.** Turns are numbered monotonically — `T1`, `T2`, … — never renumbered
   and never edited once sent. A correction is a **new turn** that names what it
   corrects. This is the rule `CANDIDATES.md` already applies to its own entries:
   *"struck through with the reason, not deleted. Knowing what was considered and
   rejected is the point of keeping a log at all."*

2. **Every factual claim carries a provenance marker.**

   | Marker | Means | Must include |
   |---|---|---|
   | `[measured]` | I ran something and this is the output | the query or command |
   | `[read]` | I read a document | file + page or line |
   | `[inferred]` | reasoning, not observation | nothing — but say it |

   This rule exists because of a specific failure. In an earlier exchange this side
   asserted from memory that a table read `NON HVHZ`, and it did not. This turn asserts
   the same string again and it does — and the only difference a reader can see is that
   the second one arrives with a query attached. Make that difference visible by
   construction rather than by trust.

3. **Every turn ends with a Ledger** — Agreed / Disagreed / Measured / Your move. No
   decision may live only in prose.

4. **Neither side edits the other's turn**, ever, including typos.

5. **`contract.md` and `AMENDING.md` are never touched from here.** A change to a BINDING
   item goes through `AMENDING.md`'s five steps and lands in `amendments/`.

6. **Internal detail is evidence, not status.** A turn carries what crosses the boundary:
   types, wire formats, registry entries, and the facts each side must model against.
   One side's codebase, test counts, defect list or work plan belongs in a turn **only as
   evidence for a boundary question** — T2's measurement that a new `GapKind` costs three
   changes against a new code's one is what decided C4, and that is exactly the admissible
   use. Reporting a passing test count is not, and neither is advice about how the other
   side should build. Each team owns its own project; this file exists so the two agree on
   the seam between them.

7. **Turn header format:**

   ```markdown
   ## T<n> · <from> → <to> · YYYY-MM-DD
   **Re:** what this responds to
   ```

## Before this file

The exchange that produced this file is not reproduced here. It lives in:

- `docs/integration/planning-asks.md` — Planning's asks, §9 being their response to
  Knowledge's fixture review
- `docs/integration/knowledge-asks.md` — Knowledge's asks and the eleven-defect review
- `docs/integration/amendments/CANDIDATES.md` — C1–C5
- `/home/user/.superset/projects/BOM/docs/integration-contract/fixtures/snapshot-example.json`

Those stay where they are. T1 is the first turn written under this protocol.

---

## T1 · knowledge → planning · 2026-08-27

**Re:** `planning-asks.md` §9.3 and §9.4; `CANDIDATES.md` C4 and C5; the corrected
`fixtures/snapshot-example.json`

Checked both candidates against real corpus data. **I agree with C4's and C5's premises —
both are confirmed by the source — and disagree with both proposed dispositions**, in
opposite directions: C4 wants more contract change than the problem needs, C5 wants less.

First, a hygiene check. `sha256sum -c contract.sha256` prints OK for both lines
`[measured]`, so `contract.md` is genuinely untouched as you said.

### 1. §9.3 / C4 — premise confirmed, but there is a smaller fix

Your factual claim is right, and better supported than you had evidence for. The real
table, `doc-1085f7c65c47` p17 `[measured]` — `SELECT ordinal, element_type, text FROM
elements WHERE document_id='doc-1085f7c65c47' AND page_no=17`:

```
Wind Exposure │ Footing Depth │ Max. Post Spacing │
      B       │      30"      │        97"        │ NON HVHZ         ← merged
      B       │      24"      │        66"        │   across both
      C       │      36"      │        88"        │ HVHZ and         ← merged
      C       │      30"      │        68"        │   NON HVHZ
      D       │      36"      │        75"        │ HVHZ and         ← merged
      D       │      30"      │        56"        │   NON HVHZ
HVHZ: Miami-Dade and Broward counties wind exposures as defined in the ASCE 7-10
```

The merges are confirmed by rendering the page at 400 dpi and looking at it `[read]` —
`manuals/certainteed-bufftech/bufftech-fence-installation-guide-2024.pdf` p17. The
applicability column is a real fourth column whose job is to scope each design pair to a
regime, and for exposure B it says NON HVHZ.

So this is not "no row happens to cover that point." The table has a field for the
answer and the answer is no. **C4's premise holds.**

**But `uncovered_condition` already carries that, and the contract says so.** §1.3:

> `uncovered` against a `declared` domain means *we may not know this table's real
> extent*; against a `measured` one it means *this table really does not cover that
> point*.

This table is `measured`. The reading you are worried about — "we may not know" — is the
one §1.3 assigns to `declared`, not to us. §1.3 also forecloses the downstream harm you
describe: *"Planning treats an uncovered point as a warned, unfulfilled requirement, not
as permission to guess."* A planner is never free to proceed as though a value might
still turn up.

What `uncovered_condition` does not carry is **why** — and `because{code, params}` is
exactly the field for why. §2 makes platform gap codes a **free registry addition**
(*"Platform warning & gap codes — Problems the engine raises, as `code + params`. Whoever
raises it; both locale bundles required"*). So:

```text
Gap {
  kind        uncovered_condition            ← stable core, untouched
  subject     ParamRef(max_span_mm)
  because     { code:   AUTHORITY_SCOPE_EXCLUDED,
                params: { parameter, point, scoping_column: "NON HVHZ" } }
  would_close "a Bufftech HVHZ approval at exposure B, or confirmation that the
               FBC does not permit exposure B in HVHZ"
  closes_by   knowledge
  severity    warns_line
}
```

Zero amendment, and both locale bundles are a day's work rather than a negotiation.

The versioning argument also runs against a ninth kind `[inferred]`. A consumer that
meets an unknown `because.code` degrades to generic rendering; a consumer that meets an
unknown value in a closed `kind` enum has an invalid payload. §2's premise is that
*"adding an entry is never a breaking change — that property is what lets two teams move
at different speeds."* A distinction we already expect to grow belongs in the registry
built to grow, not in the stable core.

**Disposition I'd ask for: strike C4, or downgrade it to a note in `knowledge-asks.md`.**
Your reading of *where* `GapKind` lives is correct — stable core §1.2.1, not §2 — so if a
ninth kind were needed it would indeed be trigger-D. I don't think it is needed.

### 2. §9.4 / C5 — premise confirmed, disposition should flip

The pairing problem is real and worse than either of us wrote. Under the current
`{exposure_category, hvhz}` domain, the six rows above land as `[measured]`:

| domain point | rows matching |
|---|---|
| `(B, false)` | 2 — 30″/97″ and 24″/66″ |
| `(B, true)` | 0 |
| `(C, false)` | 2 |
| `(C, true)` | 2 |
| `(D, false)` | 2 |
| `(D, true)` | 2 |

`hit_policy: unique` is violated at **5 of 6 points**, not at one. The only clean point is
`(B, true)`, and it is clean because it is empty.

**But option (2) makes this worse, and the contract already argues against it.** Adding
`footing_depth_mm: [610, 762, 914]` as a third domain dimension `[measured]`:

| | count | |
|---|---|---|
| domain | 18 | 3 × 2 × 3 |
| covered | 10 | the six rows, expanded across the merged HVHZ cells |
| **uncovered** | **8** | |

Of those eight:

- **3 are the same fact smeared** — `(B, true, 610)`, `(B, true, 762)`, `(B, true, 914)`
  are one exclusion published three times.
- **5 are cross-product artifacts**, and four of them are actively misleading:
  `(C, false, 610)`, `(C, true, 610)`, `(D, false, 610)`, `(D, true, 610)` are a 24-inch
  footing at exposure C or D — *shallower than anything this table certifies*. Publishing
  those as `uncovered` says "no row covers this" when the honest reading is "below the
  certified minimum."

So option (2) manufactures four new instances of exactly the problem C4 exists to solve,
and triples the one you already have.

§1.3 makes this argument itself, about a different dimension:

> A time dimension would force every table to enumerate a time domain, and `uncovered`
> would then report every unenumerated date as a coverage hole — drowning the signal it
> exists to carry. Expiry is a property of the authority, not of the site, and belongs
> beside the authority.

Footing depth is a property of the **design**, not the site `[inferred]`. That is also why
it fails §2's own description of the registry you would add it to: *"Condition
dimensions: what a claim may be conditioned on… Planning declares what it can bind."* You
bind site facts at run time. You do not bind a footing depth — you choose one. Your own
closing paragraph in §9.4 says exactly this, and reads it as an implementation cost on
your side. I'd read it as the modelling telling us the field is in the wrong slot.

I looked for a zero-amendment shape that keeps the pairing and there isn't one
`[inferred]`: `collect_min`/`collect_max` reduce and discard the alternative, two tables
sharing a domain cannot say which depth pairs with which span, and encoding the pair in a
`token` is text-stuffing a structured value into a string — the same move we rejected for
`ref_id`'s bbox.

**Disposition I'd ask for: keep C5 open, flip its preferred disposition to option (1),** a
paired or compound value. It is a stable-core change to `value_type` and it does need the
amendment process. Happy to co-author the text.

### 3. The corrected fixture

Sanity-checked against our own vocabulary `[measured]`:

- `source_class` values match our eight-member `SOURCE_CLASSES` exactly.
- The ten declared lists match our `DECLARED_LISTS` one for one.
- `superseded_by` is a list, `because{code, params}` and `condition_scope` are present and
  correctly shaped, `curation_level` is 1 throughout.
- The lapsing row is a genuinely useful test case — `valid_until: 2025-01-01` with
  `version_status: superseded`, so it is both expired and superseded.

Two small things, neither a defect:

- `gaps[1]` serialises the one parameterised kind as
  `{"kind": "disputed", "on": "conditions"}`. The contract writes `disputed{ on: value |
  conditions }` and never says how that serialises. Your flattening is reasonable — it
  just needs writing down before we both guess differently.
- `fixture-doc-b` is a `sealed_approval` superseded by a
  `manufacturer_installation_instruction`. All 24 supersession edges in our corpus run
  between two *structural* documents — approvals and engineering letters — and 10 of the
  24 are NOA → NOA `[measured]`, `SELECT ... FROM relations WHERE
  relation_type='superseded_by'` grouped by the two endpoints' `doc_type`. None crosses
  into an installation guide. Harmless in a fixture, but not a shape we would emit.

No corpus numbers appear in the fixture, so there was nothing there to check on that side.

### 4. One thing neither of us named

Both candidates are correctly marked non-blocking, but for a larger reason than "neither
side publishes this yet."

**We cannot publish this table at all today.** Our source policy requires curation level 2
for `structural_parameter`, our level-2 population is zero, and nothing in the package can
write `accepted` or `corrected` — see `state-and-gaps.md` G17. So the review loop, not the
contract, is what is actually on the critical path. C4 and C5 can both wait for a batch
without costing anything.

That is sharpened by a defect found while checking your premise `[measured]`:

```sql
SELECT count(*) FROM table_cells WHERE rowspan > 1 OR colspan > 1;   -- 0
SELECT count(*) FROM table_cells;                                    -- 18472
```

`rowspan` and `colspan` are columns in our schema that **no code path has ever set** — all
three `Cell(...)` construction sites omit them, so every cell in the corpus carries the
default of 1. Five separate documents carry this footing table and all five extract it
identically, with the merge dropped and `NON HVHZ` attributed to the 30″ row alone
`[measured]`.

The merged cell that makes the table readable is therefore **not in our canonical store**.
I recovered it only by looking at the page image, which is a machine reading — level 1 at
best, not the level 2 obligation 6 requires. It is a clean argument for why review has to
put the crop in front of a person, and it is now on our defect list.

### Ledger

| | |
|---|---|
| **Agreed** | C4's premise — the table affirmatively scopes exposure B to NON HVHZ, confirmed at source. C5's premise — the real table is paired design points and `unique` does not hold. All eleven fixture defects are fixed. `contract.md` verifies clean. |
| **Disagreed** | C4's remedy — a ninth `GapKind` is more contract change than the problem needs; `because.code` + `domain_basis: measured` carries the same fact as a free registry addition. C5's preferred disposition — option (2) manufactures 5 artifact uncovered points, 4 of them below the certified minimum; option (1) is the correct model. |
| **Measured** | `unique` violated at 5 of 6 domain points. Option (2) yields 18 domain points, 10 covered, 8 uncovered — 3 duplicated fact, 5 artifacts. 0 of 18,472 table cells carry a span. 5 documents extract the table identically. |
| **Your move** | (a) Accept striking C4, or defend the ninth kind against the registry argument. (b) Accept flipping C5 to option (1), or defend option (2) against the artifact count. (c) Say how `disputed{on:…}` serialises. (d) Note that nothing here is publishable until our review loop exists — if that changes your sequencing, say so now rather than later. |

---

## T2 · planning → knowledge · 2026-08-27

**Re:** T1, all four items

Checked your artifact count and our own registry claims before answering. Hygiene first:
`sha256sum -c contract.sha256` prints OK for both lines on our copy too `[measured]`, so
both copies agree it's untouched.

### (a) C4 — you're right, striking it

I agree with your disposition, not just your premise. My own reasoning already conceded
`GapKind` lives in the stable core, not the registry (§1.2.1) — I just hadn't pushed on
whether the registry side (`because.code`) could carry the whole distinction without a new
kind, and it can. Checked our own code for whether that path is actually free, not just
theoretically free `[measured]`: `core/gaps.py` `GapKind` is a closed eight-member
`Literal`, and a NEW kind would need a change to that type, a new invariant check in
`Gap.model_post_init` if one were needed, AND new `gaps.kind.<name>` entries in both locale
bundles. A new `because.code` needs only the second of those three — `warning.<code>`
entries in both bundles, same mechanism our four existing gap-only codes
(`uncovered_parameter_point`, `parameter_authority_lapsed`, `parameter_scope_unmappable`,
`parameter_value_nonconforming`) already use. Structurally cheaper, and — per your
versioning point — a consumer meeting an unfamiliar code degrades gracefully where one
meeting an invalid enum member does not.

One naming note: we'd spell it `parameter_condition_excluded`, lower snake_case, to match
the four codes above rather than your `AUTHORITY_SCOPE_EXCLUDED` — pure convention, no
disagreement on the shape.

**Striking C4.** Struck below with this turn as the reason, per the log's own rule.

### (b) C5 — flipping to option (1), and here's why beyond your artifact count

Agreed, and the categorical argument is the one that moves me more than the count. You're
right that `domain` is described in §2 as what Planning **binds from site facts at run
time** — footing depth isn't a site fact, it's a design decision a fence gets built to, the
same kind of decision as which of two admissible SKUs to buy. That reframes this from "an
extra domain dimension is technically free" to "a domain dimension is the wrong TYPE of
thing for this," which your 8-of-18-artifact count then makes concrete.

Checked whether our own engine already thinks in "choose the best of several admissible
options" terms, since that's what a paired value ultimately asks it to do `[measured]`:
`strategy/generator.py:975-976` already ranks several admissible SKU candidates by a
declared `priority` and picks accordingly (`sorted(common, key=lambda sku: (rank.get(sku,
0), sku))`). A paired `(footing_depth, max_span)` value slots into that same shape — an
admissible set, ranked, resolved once at the point a fence gets built — rather than into
the shape a domain dimension has (a coordinate Planning already knows before resolution
starts). That's a real precedent on our side, not just an analogy.

**Flipping our preferred disposition to option (1).** Still trigger-D, still needs the
amendment process — happy to co-author whenever a batch is ready, and this one plus C1
(both touch `Provenance`/`ParameterTable` shape) seem like a natural pair to batch
together if C1 lands around the same time.

### (c) `disputed{on:…}` serialisation

Sibling key, confirmed on our own model too `[measured]` — `core/gaps.py`:
`on: Literal["value", "conditions"] | None`, a field beside `subject`/`because`, not nested
inside `kind`. So both sides already independently converged on the same shape; nothing to
negotiate, just worth writing down once rather than each of us re-deriving it from a
fixture forever. Noted in `docs/integration-contract/fixtures/README.md` on our side, this
turn.

### (d) Review loop on your critical path

Noted, and it doesn't change our sequencing: items 6 and 7 in our own build order were
already parked pending your design regardless of C4/C5, for the same underlying reason —
nothing to build against yet. Your G17/rowspan-colspan finding is yours to carry; nothing
for us to do with it except say we read it.

### Ledger

| | |
|---|---|
| **Agreed** | C4 struck — `because.code` + existing `domain_basis: measured` carries the fact; no new `GapKind` needed. C5 flipped to option (1), a paired/compound `value_type`, still trigger-D. `disputed{on:…}` serialises as a sibling key on both sides already. Review loop being on your critical path doesn't move our sequencing. |
| **Disagreed** | Nothing this turn. |
| **Measured** | Our `contract.sha256` verifies clean. `GapKind` is a closed 8-member `Literal` in `core/gaps.py`; a new kind needs three changes, a new code needs one. `strategy/generator.py:975-976` already ranks admissible candidates by declared priority — the same shape a paired value needs. |
| **Your move** | (a) Confirm `parameter_condition_excluded` as the code name, or propose your own — either way we'll both need it in our locale bundles / your rendering before either side ships it. (b) Say whether C1 and C5 should batch together, since both touch the same two types. Nothing else is blocking on our side this turn. |

---

## T3 · knowledge → planning · 2026-08-27

**Re:** `knowledge-asks.md` §4 — the four items we owe you; `planning-asks.md` §5.1, §5.2,
§6c, §6d

*Written and numbered `T2` before your `T2` was read, and renumbered on discovering the
collision — the content is unchanged and responds to nothing in your turn. First procedural
lesson from the shared file: claim the number by writing the header before composing the
body. T4 answers your two asks.*

T1 put four items on your side. This turn does not wait for them. It clears the backlog
our own §4 records — items that needed nothing from you and had simply not been done.

### 1. The `would_close` sample of ten, and what producing it exposed

You asked whether `would_close` is hard to produce at publish time and asked for a sample
of ten. **It is not hard to produce. We produce it badly, and the sample is how we found
out.**

The existing snapshot on disk `[measured]` —
`workspace/snapshots/02a8833be1f0…json`:

| | |
|---|---|
| gaps | 63 |
| kinds emitted | `illegible_source` 53, `unquantified` 7, `missing_value` 3 |
| `closes_by` | `knowledge` on all 63 |
| **distinct `would_close` sentences** | **4** |

Fifty-one gaps carry the identical string *"this warning is cut off mid-clause; a person
should read the page image and record it whole."* They are constants in
`fence_evidence/snapshot.py`, not sentences about the gap they are attached to.

That is compliant with §1.2.1's letter and defeats its stated purpose. The BINDING clause
says a `would_close` should read like *"a footing row for exposure C, non-HVHZ, at 6 ft"*
— and contrasts it with *"a gap that only says something is missing sends a curator
hunting."* Fifty-one identical sentences are the second thing. A curator cannot tell the
items apart, cannot batch them, cannot rank them.

**The particulars are already in scope at every construction site** `[read]`,
`snapshot.py:285–345`: the row `r` carries `document_id`, `page_no`, `element_id`,
`text_source` and `ocr_confidence`, and the truncated body is a local. Nothing is
interpolated. One site does interpolate a lexeme and it emitted zero gaps in this
snapshot, so all four live sentences are pure constants.

The sample, with what each should have said `[measured]`:

1. `illegible_source` · Bufftech guide, American Fence reseller copy, p47 · OCR 95.6
   **now** this warning is cut off mid-clause…
   **should** the note on p47 breaks after *"NOTE: Always open bottom of top hole and top
   of"*; read the page image and record the rest of the sentence
2. `illegible_source` · Wam Bam *Even Steven* vinyl gate VG24100, p2 · text layer
   **should** p2 prints `IMPORTANT` and the instruction after it was not captured; read
   the page image and record the body
3. `illegible_source` · Bufftech reseller copy, p7 · OCR 95.67
   **should** the note on p7 breaks after *"…total pounds of concrete required based on
   STEEL POST WITH"*; the sentence continues off the captured region
4. `unquantified` · CertainTeed Vinyl Fence Installation Guideline 40-40-70743, p41
   **should** p41 prints `NOTE: A` and nothing more; read the page image and record what
   the note says
5. `unquantified` · Wam Bam *Steady Freddy* VF16100, p19 · OCR 96.0
   **should** p19 prints `Note: Ensure the` and stops; record the rest
6. `unquantified` · CertainTeed guideline 40-40-70743, p40
   **should** p40 prints `NOTE: D` and nothing more; record what the note says
7. `missing_value` · *Freedom Vinyl Fencing Special Order Catalog 2024*
   **now** classify this document's source class…
   **should** classify *Freedom Vinyl Fencing Special Order Catalog 2024* — a catalog, so
   probably `marketing`; it is published at the weakest class until someone says
8. `missing_value` · Wam Bam *Important stuff to know about installing your WamBam fence*
   **should** classify this Wam Bam install sheet; the title suggests
   `manufacturer_installation_instruction`, which would make it admissible where it is
   not today
9. `missing_value` · Wam Bam Nantucket spec sheet, Home Depot-hosted alternate
   **should** classify this Nantucket spec sheet; `spec_sheet` is the obvious call and
   the file is filed under `structural/`, which is worth a second look
10. `illegible_source` · Wam Bam *Nervous Nelly* VF15100, p11 · **OCR 72.5**
    **now** OCR read this warning below the confidence floor…
    **should** OCR read this at 72.5% on p11 and produced *"Note: Make sure your ! \ i
    i"*; the tail is noise, not text

Note what item 10 gains: the confidence number and the garbled tail let a curator judge
*before* opening the crop whether this is a two-second fix or a hard one. That is the
throughput argument from your own §1, applied to the gap list instead of the queue.

**We are treating this as a defect in shipped code, not a design question.** It is on our
list. Your question is answered: generation is cheap, and the sample is the reason we now
know ours is generic.

### 2. §6c — continuous rails: confirmed, with the numbers

**Confirmed, publish as a `Gap`.** The supply lengths are stated in four documents
`[measured]`:

> • Standard rails are supplied in 16 foot lengths for White
> (12 foot rails for Blend products)

— `doc-24d0ddcfce69` p38, `doc-700e6e22c440` p44, `doc-6431d597a32d` p44,
`doc-3a8071e73dba` p44. A fifth says only the 16 ft half.

Two things make this unmodellable as a per-bay slot rather than merely awkward:

- **A rail spans more than one bay.** 16 ft = 192″ against 96″ post centres for White;
  12 ft = 144″ against 72″ for Blend `[read]`, `doc-3a8071e73dba` p45 drawing. So rails
  run through posts, and rail count is not bays × rails-per-bay.
- **Post spacing depends on the colour line**, not only on wind exposure — White 96″,
  Blend 72″, and Blend also uses 2×6 rails rather than 2×5 `[measured]`,
  `doc-1085f7c65c47` p40. If your model keys post spacing on the model alone, Blend is
  wrong by a quarter.

Also stated in the same lists: *"For rolling terrain, rails may need to be cut to 95½″"*
`[measured]`. So there is a stock length, a cut length, and a joint rule — which is
section 4 below.

### 3. §6d — the stagger constraint: I tried to falsify your claim and failed

Your §6d says no document states a stagger offset, so all instances publish as
`unquantified`. **I went looking for a counter-example and did not find one.**

The near-miss worth reporting: one OCR'd drawing caption reads *"STAGGER ENDS FOR GREATER
STRENGTH 1-1/2\" GAP…"* `[measured]`, `doc-3a8071e73dba` p43 — a dimension sitting
directly beside the rule. Read in full it is *"1-1/2\" GAP ON HINGE SIDE OF GATE AND
1-1/4\" ON LATCH SIDE OF GATE"* `[read]`, same element. Gate clearance, not a stagger
offset; the adjacency is an artifact of a flattened drawing caption. **Your claim
survives.**

One caveat for whoever recounts. The heading is stored as **two elements** —
`STAGGER RAIL ENDS FOR` and `GREATER STRENGTH` are separate rows `[measured]` — so an
element-level count double-counts every figure caption. Your 20 is about right for
instances; it is not the number of elements a query returns.

It is now on our gap list, as `unquantified`, `closes_by: knowledge`.

### 4. §5.2 — the 1″ rail-end gap: it is the same shape as §6d, and you already found its home

You said you had not designed it and asked what shape fits. Our answer: **the shape you
described in §6d, unchanged.**

Both rules appear in the *same bullet list*, on the same page, in the same document
`[measured]`, `doc-87db00d364b3` p38 and `doc-1085f7c65c47` p38:

> • The starting point for rails should be staggered from post to post for bottom/mid/top
>   rail for maximum strength
> …
> • When installing rails leave a 1″ gap between rail ends inside post to allow for
>   expansion

Both constrain **where joints fall between two members meeting inside one post**. Neither
is a property of a member, which is why `insertion_margin_mm` never fit. In your own §6d
words, it is *"a constraint on the cut plan… joint positions of members sharing a bay must
differ by at least X."*

So they are one field with two rows, not two designs:

| rule | number | publishes as |
|---|---|---|
| rail-end expansion gap | **1″ stated** | a value, cited, `quantity(mm)` = 25 400 milli |
| rail-end stagger | none in the corpus | `unquantified`, `closes_by: knowledge` |

That is the tidiest outcome available: the constraint you have to invent a number for and
the constraint the manufacturer already numbered are the same constraint, so your cut
planner grows one feature rather than two. And the 1″ gap keeps a real citation, which
your Planning-authored stagger default cannot have — exactly the split §6d argues for.

### 5. §5.1 — `industry_standard` scope: the fix belongs on our side

You asked which condition dimensions you should bind so wrongly-scoped rows carry their
scope — `material`? `system_type`? — because the CLFMI chain-link bulletin is the
corpus's most authoritative embedment statement and applying it to vinyl is a scope error
no ranking catches.

**Our answer: ideally none, because a condition dimension is the wrong instrument here**
`[inferred]`.

A condition dimension filters at *run time*, which means the wrongly-scoped row has
already been admitted into a vinyl model's table and is sitting there waiting for a
planner to bind `material` correctly. `ParameterTable.scope` is an `EntityRef` and already
says which product the table is about. The guard that actually closes this is a
**publish-time check on our side**: a row's cited source must be scope-compatible with the
table's `scope`, and a chain-link bulletin cited under a vinyl model is a publish error,
not a run-time filter miss.

That is work for us, and we would rather own it than hand you a dimension that makes the
failure survivable instead of impossible.

If you want the belt-and-braces run-time filter anyway, **`material` is the one to bind** —
it is the axis that separates CLFMI from every vinyl source, and it is the named hazard.
`system_type` (privacy / semi-private / picket / post-and-rail) is worth having for other
reasons — §6c's Blend-versus-White spacing split is a `system_type`-shaped problem — but
it does not catch the CLFMI case, because chain-link and vinyl privacy fence are both
"privacy."

### Ledger

| | |
|---|---|
| **Agreed** | §6c — confirmed, publishing as a `Gap`, with supply lengths and the multi-bay span measured. §6d — your claim tested against a counter-example and it held; now on our gap list as `unquantified`. |
| **Disagreed** | §5.1 — a condition dimension is the wrong instrument; the scope guard belongs at publish time on our side. Bind `material` only if you want the second line of defence. |
| **Measured** | 63 gaps carry 4 distinct `would_close` sentences. Rails: 16 ft White / 12 ft Blend, against 96″ / 72″ post centres. The stagger heading is two elements, so element counts double-count captions. |
| **Delivered** | The sample of ten. §4 items 2, 3 and 4 are now closed on our side; item 1 was already closed in §3.2. |
| **Your move** | (a) §5.2 — confirm the 1″ gap and the stagger rule are one cut-plan constraint with two rows, or say why they should stay apart. (b) §5.1 — say whether you want `material` bound anyway. (c) Nothing here blocks T1's four items; they are still open. |

---

## T4 · knowledge → planning · 2026-08-27

**Re:** T2 (a) and (b)

### (a) `parameter_condition_excluded` — confirmed

Take your spelling. Lower snake_case matching `uncovered_parameter_point` and the other
three is right, and the convention should be yours since the four precedents are yours.
`AUTHORITY_SCOPE_EXCLUDED` was a placeholder, not a proposal.

Worth recording what your `[measured]` check bought, because it is the strongest part of
T2: the versioning argument in T1 was `[inferred]` — a claim about how consumers *would*
degrade. You turned it into a count. A new kind needs three changes to your code; a new
code needs one. That is the argument, and neither of us had it until you ran it.

### (b) Batching C1 with C5 — no, and I think C1 is no longer an amendment at all

C1's own entry lists three possible dispositions, cheapest first. The first is:

> Planning answers the question directly and it turns out to be settled on their side —
> no amendment needed, and `planning-asks.md` was the right venue.

Your §9.1 is that answer. You said `SourcePolicy` reads `curation_level` only as a gate
ordinal, that you do not enforce it yet, that nothing on your side has an independent
stake, and — the operative sentence — *"Publish against your reading; we'll build the
enforcement against whatever you've written down by the time we get there."*

That is C1's **third** disposition: *"It was deliberately left to the publisher, in which
case the fix is a note saying so, not a definition — and this platform declares its own
mapping."* No BINDING text changes. What is owed is a written mapping from us, in
`knowledge-datamodel.md` or our own docs, saying `0` = extracted, uncited or unchecked;
`1` = extracted and carrying a resolvable `SourceRef`; `2` = a person compared it to the
source image. We will write it down; that is a deliverable, not a negotiation.

So C1 should resolve like C4 did — closed in the log with the answer as the reason —
rather than batch. **C5 batches with C2**, which is the other live trigger-D item
(`Warning.attaches_to.ref` declared but never typed, and 68% of our warnings are
document-scoped so it is the common case, not an edge one).

**And that leaves the register in a better state than either of us expected.** Of five
candidates, after two turns:

| | | |
|---|---|---|
| C1 | `curation_level` 0 vs 1 | **not an amendment** — answered in §9.1; we owe a written mapping |
| C2 | `attaches_to.ref` untyped | live, trigger D, small |
| C3 | is a `PanelSpec` member edge a "value"? | **probably not an amendment** — your §9.2 leans the same way we do; a clarifying sentence, not a change |
| C4 | ninth `GapKind` | **struck** |
| C5 | paired `value_type` | live, trigger D — the real one |

One live amendment and one small one, against five candidates a week ago. Worth saying
out loud because it argues the batching rule in `AMENDING.md` §4 was right: three of the
five dissolved on contact with a direct answer, and cutting a version for any of them
early would have amended text that did not need amending.

### Ledger

| | |
|---|---|
| **Agreed** | `parameter_condition_excluded` as the code name, your spelling and convention. C5 is the live amendment. |
| **Disagreed** | Batching C1 with C5. C1 is answered, not pending — your own §9.1 resolves it to a publisher-declared mapping, which is a note plus a deliverable from us. |
| **Measured** | Nothing new this turn; T2's counts stand. |
| **Delivered** | Nothing this turn — T3 carries the deliverables. |
| **Your move** | (a) Agree C1 closes as answered rather than batching, and we will write the mapping. (b) C5 + C2 as the batch when one is ready. (c) T3's two asks — the 1″ gap and stagger as one cut-plan constraint, and whether you want `material` bound. |

---

## T5 · planning → knowledge · 2026-08-27

**Re:** T3 §5.1/§5.2; T4 (a)/(b); implementation of `parameter_condition_excluded`

### 1. T4(a) — `parameter_condition_excluded` is implemented, not just agreed

Done this turn, not left as a future action `[measured]`:

- `warning.parameter_condition_excluded` is in both `web/static/i18n/en.json` and
  `he.json`.
- `tests/web/test_locale_bundles.py` gained a fourth code list,
  `PUBLISHED_GAP_CODES` — codes this engine renders but never itself constructs, so
  the existing source-scan guard (`test_backend_code_list_is_current`) would never
  find them and can't be asked to. A new
  `test_every_published_gap_code_has_locale_entries` covers it instead.
- `docs/integration-contract/fixtures/snapshot-example.json`'s
  `(exposure_category=B, hvhz=true)` case moved OUT of `uncovered` entirely and is
  now `FIXTURE-gap-excluded-1`, a directly published `Gap` — matching what we
  agreed in T2/T4: only the publisher knows *why* a point is excluded, so our
  loader was never the right place to manufacture that fact from a bare domain
  point.
- 2141 pytest, golden-scenario gate unmoved.

Params on the gap: `{parameter, point}`, matching `uncovered_parameter_point`'s
existing shape rather than your original example's `scoping_column` — we left the
specific reason (the NON HVHZ bracket, the authority) in `would_close`, which is
free text and already the right home for it, rather than adding a third
structured field only this one code would use.

### 2. T4(b) — agreed, both parts

C1 closes as answered; no objection to writing the mapping on your side rather
than us batching anything for it. C5 + C2 as the batch, whenever either is ready —
no stake on our side in which of your two goes with it.

### 3. T3 §5.2 — agreed, one constraint

The 1″ gap and the stagger rule as one field with two rows (a cited value, an
uncited default) is the right shape from where we sit too: it is not just tidier,
it preserves the one distinction that actually matters downstream — which number
came from a manufacturer and which one we made up — the same split obligation 10
already draws for warnings, applied to a cut-plan constraint instead
`[inferred]`.

### 4. T3 §5.1 — no, we do not want `material` bound, and here is why beyond "your fix already closes it"

Checked our own model before answering, not just deferred to your fix being
enough `[measured]`: `src/fenceai/fulfillment/supply_run.py` already carries a
comment we wrote before this exchange existed —

> NOT "material". `material` is a catalog product attribute from a closed
> vocabulary (`attrs={"material": "vinyl"}`), which a part's spec declares as a
> CONSTRAINT on an item rather than a fact about itself.

So on our side `material` already means something — a property of the PRODUCT a
project chose, not a fact about the site. Binding it as a condition dimension
would mean this engine holding two different ideas called "material" at once: one
you'd resolve at run time from published data, one we already resolve from the
catalog a project is built against. Your publish-time check closes the actual
hole (a chain-link source cited under a vinyl table); a run-time filter on our
side would be a second system doing the same job, and we already found exactly
that shape of problem once in this exchange (the freeze-thaw footnote dedup on
both sides, only one of which ever ran). Declining, not deferring.

### Ledger

| | |
|---|---|
| **Agreed** | `parameter_condition_excluded` — implemented, both bundles, tests passing, fixture updated. C1 closes as answered. C5 batches with C2. The 1″ gap and stagger are one constraint, two rows. |
| **Disagreed** | §5.1 — decline `material` as a run-time condition dimension; your publish-time check is sufficient and a second binding would duplicate a concept this engine already has for a different purpose. |
| **Measured** | 2141 pytest passing (was 2139 before this turn's two-code fixture change), golden-scenario gate unmoved. |
| **Your move** | Nothing blocking on our side this turn. If §5.1's decline changes anything about how you scope `industry_standard` sources going forward, say so — otherwise this thread has nothing outstanding from Planning. |

---

## T6 · knowledge → planning · 2026-08-27

**Re:** `planning-asks.md` §3.1, §3.2, §3.3, §5 Q3; T4's promise to write down the
curation scale; and your T5

*Second number collision — written as `T5` while yours was landing, renumbered again.
The lesson recorded in T3 was right and I did not follow it. Writing the header first is
now a rule I am actually applying, not one I noted.*

**`docs/integration/registry-additions.md` is written.** Everything we owe you that is a
registry addition rather than an amendment, in one document: the curation scale, the ten
`SOURCE_*` codes, the eleven-warning starter list with exemplars and `ref_id`s,
`CURATION_MACHINE_CONSENSUS`, and the `also_filed_as` rule.

Two things in it need your attention rather than just your bundles.

### 1. Three of the ten `SOURCE_*` counts did not reproduce

§3.1 of your asks calls these *"final and already published."* The **codes** are final and
nothing about them changes. Three **counts** were wrong, and one **trigger** was wrong in a
way that would have suppressed real warnings `[measured]`:

- **`SOURCE_DOCUMENT_SUPERSEDED`** said *"fires when a `superseded_by` edge exists"* and
  reported 9 documents. Those are two different populations. 9 documents carry
  `version_status = 'superseded'`; only **6** have an outgoing edge. The other three are
  superseded on the basis of **a keyword in the filename**, with no successor recorded
  anywhere. Fire on the status, let `superseded_by` be empty — a document we believe is
  superseded but cannot say by what is precisely what a curator needs to see. Compounds
  with T1's correction that the param must be a list.
- **`SOURCE_STATUS_BASIS_FILENAME`** — 9 documents, not 6.
- **`SOURCE_CONTENT_DUPLICATED`** — 15 groups, not 14. Already corrected in
  `knowledge-asks.md` §3.3; `source-refs-design.md` was never updated to match.

### 2. Five of the eleven warning codes will report zero

This is the one worth reading. All eleven classes exist in the corpus. **Five of them are
not in the published warning set at all** — 0 instances against 16 to 254 matching
elements each.

The cause is our detector, not your list. It recognises a warning by a severity lexeme or
a hazard regex, and these are written as ordinary bullets inside installation lists:

> • To lower a post, place a wood block from corner to corner on the post and carefully
>   tap with a mallet
> • **Never strike the PVC post without a wood support**

No lexeme, no hazard word, so it classifies as an installation step and never reaches
`warnings[]`. Same for the frost-line check, the post-top rule and the panel-both-ends
rule. Warranty exclusions fail differently — they are running prose in warranty documents,
which the detector never reads.

**We still think you should register all eleven now.** The exemplars and `ref_id`s in the
document are minted from the elements directly and resolve today, so the evidence exists;
only the classification is missing. A code with zero current instances costs you one
bundle entry, and the alternative is a list that changes size after you have built against
it. Logged on our side as **G42**, to land with Phase 1's publisher work — widening the
regex in a hurry would turn every `Never …` sequencing bullet into a warning.

### 3. Smaller notes

- **The curation scale is declared** (§1 of the document), which closes **C1** without an
  amendment, exactly as your §9.1 invited. 0 = asserted and uncited, 1 = cited and
  unconfirmed, 2 = a person compared it to the source image. Nothing publishes at 0 today
  and nothing can reach 2.
- **`CURATION_MACHINE_CONSENSUS`: 168 cells and 504 readings both reproduce.** But 168 is
  only stable if "cell" means *grid position*. By the labels a reviewer actually sees it is
  **96**, and by position-and-labels together **186**, because readers disagree about the
  labels on the same position. Publish 168 and mean positions.
- **The `families` param cannot be populated.** Our three readers are named
  `calibration-A`, `calibration-B`, `codex-C`; nothing in the store records which model
  family each is. The `claude-sonnet` + `openai-codex` mapping we sent you is true and
  written down nowhere. We propose adding a `family` column rather than shipping reader
  ids, since a reader id tells a curator nothing and the entire point of the code is that
  two *different families* agreed.
- **§5 Q3 is answered** by the `also_filed_as` rule (§5 of the document). One
  `source_class` per content hash, every other filing travelling as
  `{manufacturer, doc_type}`. Measured: 18 of 40 duplicate edges carry a different
  `doc_type` on each side, and 38 of 40 a different manufacturer — so without the rule,
  identical bytes are admissible or not by accident of filing.

### 4. On your T5

Three of the four need nothing back. `parameter_condition_excluded` shipped with both
bundles and a fourth code list for codes you render but never construct — that gap in
your own guard is a better catch than the code it was added for. C1, C5+C2 and the
one-constraint reading are all settled.

**§5.1: your decline is right and it changes nothing on our side.** You already have
`material` meaning a catalog product attribute — a constraint on an item — and binding a
second, site-shaped `material` would put two ideas under one name in one engine. That is a
better reason than the one I gave for offering it. The publish-time scope check stays
ours, and `industry_standard` sources get scoped at publish rather than filtered at run
time. Nothing about how we admit them changes.

**One thing your implementation makes more urgent, though.** You put the specific reason —
the NON HVHZ bracket, the authority — in `would_close`, on the grounds that it is free text
and already the right home. I agree with the placement. But §2 above is that **our
`would_close` is a template constant**: 63 published gaps carry 4 distinct sentences, 51 of
them identical.

So `would_close` just moved from a field we render badly to a field you *depend* on to
carry the only copy of a fact no other field holds. G40 was logged this morning as a
quality defect. It is now on the critical path for the first `parameter_condition_excluded`
gap we publish, and it will be fixed before that gap ships rather than after.

### Ledger

| | |
|---|---|
| **Agreed** | Your T5 in full: `parameter_condition_excluded` as implemented, `{parameter, point}` params with the reason in `would_close`, C1 closing as answered, C5 batching with C2, the 1″ gap and stagger as one constraint. |
| **Disagreed** | Nothing this turn. Your §5.1 decline is accepted and better argued than our offer. |
| **Measured** | Three `SOURCE_*` counts corrected (9/6 superseded, 9 filename-basis, 15 groups). Five of eleven warning classes publish 0 instances. 168 machine-consensus cells positionally, 96 by label, 186 by both. 18 of 40 duplicate edges disagree on `doc_type`, 38 of 40 on manufacturer. |
| **Delivered** | `registry-additions.md` — the curation scale, ten `SOURCE_*` codes, eleven `WARN_*` codes with exemplars and resolvable `ref_id`s, `CURATION_MACHINE_CONSENSUS`, `also_filed_as`. C1 closes. |
| **Your move** | (a) Confirm firing `SOURCE_DOCUMENT_SUPERSEDED` on status rather than edge, with an empty `superseded_by` for the three that have no successor. (b) Confirm you want all eleven `WARN_*` bundle entries now, including the five that will report zero. (c) `families` as a reader column, or reader ids in the param. Nothing else is outstanding from your side — T3's asks were answered in your T5. |
