# What Planning needs from this platform, and when

```text
Status:   v0.4 + §9, added 2026-08-27 — our response to knowledge-asks.md v0.2's
          review of the conforming fixture. Working list, maintained by the
          Planning & BOM team.
Note:     The four items needing your AGREEMENT are not here — they are in
          boundary-delta-v0.4.md. This document is what we need you to BUILD
          or SEND, which is a different list and needs no approval.
Purpose:  The mirror of 05-acceptance-open-questions.md — everything we need from
          you, ordered by what it costs us if it is late.
Honest:   Nothing here blocks us this week. Engine steps 1–3 and the evidence
          viewer all run against what is already on disk. This is the three-week
          list, not the today list.
Reads with: knowledge-datamodel.md (the revised model, and §8 traces every
          audit finding to where it landed), contract.md (the promises).
```

---

## 1. The one above everything else

### The cell bounding box

All 1,225 rows in `table_read_candidates` record a row label and a column label and
**no cell bounding box in crop pixels**. Your own `docs/curation/02-curation-schema.md`
§2.5.3 already requires it; it does not exist yet. You logged it as K4 and ranked
it below K3, the crop-cost measurement.

**We are asking you to flip that order**, and this is the only place in this
document where we ask you to reorder your own work.

The reasoning is not about images. A reviewer shown a crop and told *"check this
value"* has to **find the cell before they can judge it**. That is an unbounded
task, and every throughput number in our review-queue design assumes a bounded
one — accept or reject, keyboard only, hundreds per session. Binary throughput is
roughly an order of magnitude above search-then-judge throughput, and the cell box
is the entire difference.

The failure it prevents is one you documented yourselves. On NOA-23-0314.05 p12,
bill-of-material item J reads `.875 X 7 X 62.75 TONGUE AND GROOVE PICKET` while the
dimensioned elevation of that same item J on that same sheet reads `7 3/8"`.
Neither is labelled nominal or coverage. A curator who reads one builds a panel 5%
too wide; a curator who reads the other is right; **both validate clean.** No
schema change closes that — only a reviewer looking at the right region of the
right page does, and only if they are shown which region.

Everything else on this list costs us time if it slips. This one decides whether
the queue works at all.

---

## 2. Two publishes, and we do not want volume

We are not asking for a curated corpus. We are asking for two objects that exercise
the parts of the contract nobody has run against real data, plus one snapshot of
any size.

### 2.1 One `ParameterTable` with a `declared` domain

From any of the 73 `table_not_reconstructed` pages, with its `uncovered` list and
`domain_basis: declared`. This is the first real test of the never-block invariant:
Planning should produce a plan with a warned, named line rather than a failure, and
the warning should say *we may not know this table's extent* rather than *this table
does not cover that point*.

If that reads wrong when we render it, we would rather find out on one table.

### 2.2 One definition carrying a superseded source

The Chesterfield trace is the obvious candidate — eleven documents, 2006 to 2025,
four manufacturer strings, four superseded approvals and four byte-identical copies
of a fifth. Publish it as a `Part` or `FenceModel` with
`contributing_sources`, including the superseded `SourceDoc`s.

The question it answers: **can a pinned run warn on a lapsed authority from inside
the snapshot, with no network call?** That is the whole justification for §2.5 of
the data model, and it is currently a design argument rather than a demonstrated
one. With 40.7% of promoted facts already citing a superseded document, we would
rather test it on one definition than on four hundred.

### 2.3 One snapshot, however thin

Three parts, one model, two parameter tables is enough. We need the **shape** more
than the content, to build `kplatform/adapt.py` and the bundled default snapshot
that ships inside our repository so the scenario suite runs with no socket open.

A snapshot containing very little is a valid snapshot by design. This one exists to
prove the adapter, not the coverage.

---

## 3. Three lists we cannot write ourselves

### 3.1 The ten `SOURCE_*` codes, final

From `source-refs-design.md` §3.2 — `SOURCE_TEXT_FROM_OCR`,
`SOURCE_OCR_LOW_CONFIDENCE`, `SOURCE_TEXT_LAYER_MOJIBAKE`,
`SOURCE_TABLE_NOT_RECONSTRUCTED`, `SOURCE_DOCUMENT_SUPERSEDED`,
`SOURCE_VERSION_STATUS_UNKNOWN`, `SOURCE_STATUS_BASIS_FILENAME`,
`SOURCE_CONTENT_DUPLICATED`, `SOURCE_NO_IMAGE_AVAILABLE`, `SOURCE_NOT_FETCHED`.

These are **platform codes**, so each needs a `warning.<code>` entry in both
`he.json` and `en.json`, and `tests/web/test_locale_bundles.py` fails the build
without them. Send the final list with each code's params, and we will author both
locales. They are parameterised sentences we write, not text lifted from a
document, so translating them is tractable — which is exactly the distinction §3.7
of the data model draws.

### 3.2 The eleven-warning starter list

You offered it in the audit response §2.5 and we are taking you up on it: utility
locate, freeze-thaw/warranty, never strike the post unsupported, eye protection,
missing-or-damaged parts, do-not-return, frost-line check, pool code, never cut the
post top, warranty exclusions, never attach both panel ends. Each with its instance
count and a verbatim exemplar, as you proposed.

Same treatment — platform codes, both bundles. The other 215 distinct warnings
publish as source warnings, verbatim and `lang`-tagged, and we render them
untranslated.

### 3.3 One new platform code — `CURATION_MACHINE_CONSENSUS`

**A registry addition, not an amendment.** `contract.md` §2 says adding an entry is
never a breaking change, and `AMENDING.md` §2 lists warning codes as explicitly not
amendable. Nothing binding moves. You need one `warning.CURATION_MACHINE_CONSENSUS`
entry in each of `he.json` and `en.json`; that is the whole ask.

**Why it exists.** Your `where-we-stand.md` read of our K1 was right, and we have now
done it: `cross_family_verified` is out of `table_review.PROMOTABLE`, the 324 facts it
promoted are un-promoted, and **the level-2 population of this store is zero**. But
revoking the promotion threw away a real signal along with the false label — a reading
that two independent model families agreed on is not the same thing as a reading nobody
has checked, and at level 1 they are currently indistinguishable.

This code carries that difference without touching the scale.

| | |
|---|---|
| Code | `CURATION_MACHINE_CONSENSUS` |
| Rides on | `Provenance`, beside `curation_level` — not on `SourceRef` |
| Params | `readers` (int), `families` (list of str), `crop_sha256` (str) |
| Today | **168 distinct cells**, 504 readings, 3 readers each, families `claude-sonnet` + `openai-codex` |

**What it does not do, said plainly.** It does not affect admissibility. These rows
publish at **level 1** and your policy rejects them for structural tasks exactly as
`where-we-stand.md` describes — crossing anyway, visible in the decision graph as
rejected rather than silently absent. The code is evidence, not a lever: it tells a
curator which level-1 rows are worth reviewing first, and it lets a frontend show *why*
a rejected row was nonetheless worth surfacing. If you find yourself writing a policy
row that keys on it, that is the signal that this should have been an amendment
instead — tell us and we will file one.

**The distinction we are protecting.** Machine agreement ranks a review queue. It never
clears it. The failure this closes is a number that reads as checked because two models
happened to concur, and the values concerned are footing depths and post spacings, where
a confidently wrong answer is the failure mode.

---

## 4. Five confirmations, cheap but they change what you build

We **modified three** of your proposals (N2, N18, N25) and **answered two questions
with a decision** (N22, N29) — a distinction v0.2 of this document collapsed into
"five you proposed", attributing to you positions you did not take. N29 you raised as
a question; on N22 you offered both shapes. You have not seen the resulting forms
either way, and the reasoning behind each is ours alone.

| # | | What we did instead | Where |
|---|---|---|---|
| N2 | modified | `value_type` declared on the **table**, not per row | datamodel §3.8.2 |
| N18 | modified | Install manuals **admissible** for structural at rank 4 / level 2 — more permissive than you asked | contract §1.4, datamodel §2.6 |
| N25 | modified | `domain_basis` as a **field**, not a confirmation in prose | datamodel §3.8 |
| N22 | decided | Validity as **fields**, not an `as_of_date` condition dimension | datamodel §3.8, §3.9 |
| N29 | decided | `Snapshot.regime` plus a hard refusal, not a condition or a tenant | datamodel §3.9 |

**N18 deserves your attention above the others**, because it changes your
priorities rather than your schema. We ranked installation manuals *admissible* for
structural parameters — but only at curation level 2. That makes human review a
hard dependency for any structural coverage at all, and level 2 is currently
unreachable by construction (your K5: `reader_kind` is `agent` for all 1,225
readings). If human review is further out than we are assuming, our ranking is
worse than the strict exclusion you proposed, and we would want to know that now.

---

## 5. Three questions we cannot answer from here

1. **`industry_standard` applicability.** We ranked industry standards above spec
   sheets, which is right in engineering practice. But your own evidence carries the
   hazard: the CLFMI bulletin is about **chain link** and is nonetheless the most
   authoritative embedment statement in the corpus. Applied to vinyl that is a
   *scope* error, and no ranking catches one — a higher-ranked wrong-scope source
   beats a lower-ranked right-scope one, silently. **Which condition dimensions do
   you need us to bind** so those rows carry their scope? `material`? `system_type`?
   Name them.
2. **The shared-host gap.** Your Q9.1 found `leave a 1" gap between rail ends inside
   post to allow for expansion` — twelve instances across six documents. It bounds a
   cut length directly, it is not `insertion_margin_mm`, and it has no field. Its
   stated reason is thermal expansion, so it may belong with expansion-gap material
   rather than on the slot. **We have not designed it.** Tell us what shape fits.
3. **The fourteen `same_content_as` groups.** One SHA-256 filed four times under four
   manufacturers with four `doc_type`s, yielding four `source_class` values from
   identical bytes. `SourceRef.belongs_to` names one of them. Is that a curation
   decision you will resolve, or should the schema carry the ambiguity? If the
   latter, `SourceDoc` changes.

---

## 6. Two things on your own list we have a view on

**K1 — revoking `cross_family_verified` from `table_review.PROMOTABLE`. Please do.**
It drops 324 facts out of promoted, and a snapshot that is honestly thin is worth
more to us than one that is falsely full — every one of those lines would come to
us at a curation level that claimed a review nobody performed. This is inside your
boundary and it is your call; we are saying we would not object to the coverage
loss, because it is not a loss.

**K2 — poppler over Pillow. Agreed without reservation.** A crop path that depends
on an optional, git-ignored package and returns `False` when it is absent is a
correctness problem wearing a performance problem's clothes.

---

## 6b. What changed on our side after a self-audit

You audited your proposal against the corpus you hold. We had not run the same
check against the codebase we hold — so we did, against the design as agreed. Seven
defects, and **two were in code we had already published to you**. The full findings
are in the Planning repo (`docs/reviews/planning-self-audit-2026-08-24.md`); these
are the four that touch you.

| | What was wrong | What it means for you |
|---|---|---|
| **The expansion we gave you truncated** | `amount_milli // 1000` — floor, not round. One millimetre through `ceil(run / max_span)` buys an extra post on two of three sample runs | Nothing to change on your side. Keep publishing thousandths and the lexeme; **do not pre-round to be helpful**, which matters more now than when we first asked |
| **The fallback row would have won silently** | Every row of one table shared an `object_id` and differed by `version = row_index`; our resolver breaks that tie by higher version. An always-true row would have beaten every conditioned row by sitting lower in the table | **Publish rows in any order.** Order now carries no meaning, which is what we told you it did. Your early publish on this is unblocked |
| **Nothing consumes `Combination`** | Zero occurrences in the engine. We accepted it as binding and asked you to curate data a run ignores | **Deprioritise it.** Spend the effort on parameter tables and definitions |
| **Lapsed authority had no date to judge against** | We promised a warning *"relative to the run date"*; generation is pure and has no clock, and must not | Nothing changes in what you publish. `as_of` becomes a pinned run input on our side. Your original `as_of_date` instinct was right; our rejection was right for its stated reason and left the input problem unsolved |

Three more are ours alone and change nothing you author: a resolver that *raises*
rather than warns when two published rows tie and disagree (which gets **more**
likely as your coverage grows, so it is being fixed first); the thousandths rule
extending to layout as well as the fitter; and containment having no traced path
into demand.

**The method is the part worth copying.** Two rounds of careful document review had
produced a design that was internally consistent and that our engine could not run.
Nothing found in this pass was visible from the documents. Coherence is not the test.

## 6c. One gap we owe you, found while arguing about posts

A question about why `PostSlot` hangs off `FenceModel` produced a rule we had not
stated: **a slot may be panel-scoped iff no other bay can produce the same physical
object.** Not *iff its count is fixed* — slat counts vary with width and rail counts
with height, and both live happily inside a panel, because each belongs to exactly
one bay.

That rule immediately catches something in **your** §2.4 evidence that neither of us
classified correctly:

> `Standard rails are supplied in 16 foot lengths` … `If bottom rail is 16' long,
> slide rail through second post and then insert post in ground` … `The starting
> point for rails should be staggered from post to post`

That rail runs **continuously through** an intermediate post — one physical object,
two bays. Rails are panel-scoped in our model, so that product is mis-modelled. We
filed it as a *step-scoping* problem (it is why `scope: run` exists); it is also a
**structural** one, and we missed that.

**Publish those products as a `Gap`** rather than as a `FenceModel` with per-bay
rails, until we have the machinery. Same reasoning as gates: a mis-modelled panel
validates clean and loses the fact silently.

---

## 6d. One new ask, from your continuity finding

**The stagger constraint needs publishing, and it needs a different home than you
suggested.** *"The starting point for rails should be staggered from post to post for
bottom/mid/top rail for maximum strength"* — **20 instances across 5 guides** (10 prose,
10 figure captions), stated as a strength requirement rather than a preference. *(Corrected
from 77 in `audit/08` §0 — the higher figure counted a decorative staggered-picket profile
and one "staggering array of colors". One rule repeated across a product family, not a
corpus-wide pattern.)*

You pointed at obligation 11's `requires` edge with `exclusive_with`. We think that shelf
is wrong and would quietly not work: `requires` orders **assembly steps** — *fit this
before that* — while stagger constrains **where cuts fall**. It survives into the cut plan,
and it binds two members that have no ordering relationship at all.

The right home is where joints are decided, which on our side is cut planning. So it is a
constraint on the cut plan, expressed the way a spacing limit is: *joint positions of
members sharing a bay must differ by at least X*. That gives it a number, an authority and
a citation, and it fails as a warned line when it cannot be met rather than silently
producing three aligned joints.

**Settled in `audit/08` §2, and the answer is stronger than we assumed.** No document in
the corpus states a stagger offset — **all 20 publish as `unquantified`**. Every dimension
appearing near the word belongs to the staggered-picket product, not to the rail rule.

**So the number is ours to choose, and must be declared as ours.** A cut planner needs a
minimum joint offset and this corpus will never supply one. It becomes a Planning-authored
default with our own attribution — never `attributed_to: "manufacturer"`, which is exactly
the unfalsifiable string `rationale.md` §5 was written about. The requirement is theirs and
cited; the number is ours and labelled.

---

## 7. What we explicitly do not need

Stated so nobody spends on it.

- **Corpus coverage.** A snapshot containing very little is still a valid snapshot,
  and Planning still produces a plan from it, with most lines warned. Coverage grows
  as curation runs; the boundary does not wait for it.
- **Retrieval quality.** It is a curation cost, not a correctness risk. Search helps
  a person find a page; only what a person accepts reaches a snapshot.
- **A drained review queue.** The whole never-block design exists so that neither
  team's queue is the other's dependency.
- **Any of your internals.** `docs/curation/` is tier 3 and stays there. We cite it
  as your design, not as something under negotiation.

---

## 8. What we are doing on our side, in order

So the dependencies run both ways visibly.

| # | Work | Needs from you |
|---|---|---|
| 1 | `SiteConditions` on the project, `site.*` in the evaluation context, `site_revision` + a `409 site_conditions_changed` guard | nothing |
| 2 | Contract and datamodel edits for every accepted item | nothing — **done**, this revision |
| 3 | Evidence viewer against `fixtures/source-ref-examples.json`, all seven records | nothing |
| 4 | `ParameterTable` loader — `value_type`, `domain_basis`, validity fields | §2.1 to validate against |
| 5 | Warning model, registry split, annexe rendering | §3.1, §3.2 |
| 6 | `kplatform/` client, adapter, bundled default snapshot | §2.3 |
| 7 | `report/assembly.py` phase one — bay and post scopes, `requires` edges | a published procedure |
| 8 | Review queue — binary accept/reject | **§1, the cell box**, and `GET /source-refs/{id}` live |
| 9 | Impact preview over snapshots | §2.3 |
| 10 | `report/assembly.py` phase two — run and site scopes | — |

Items 1–3 are in progress and need nothing from you. Item 8 is the one that stops
if §1 does not land.

---

## 9. Response to `knowledge-asks.md` v0.2 — your review of our fixture

```text
Status:   Sent 2026-08-27. Answers §2.1–§2.5 of knowledge-asks.md v0.2.
```

### 9.0 The eleven defects — fixed

All eleven rows in your §1.0 table are fixed in
`docs/integration-contract/fixtures/snapshot-example.json`: `source_class` now
uses the real eight-member vocabulary; `task` uses the confirmed `TaskCode`
spellings (§9.5 below); the lapsing row's `provenance.version_status` now agrees
with its cited `SourceDoc` (both `superseded`); `scope.kind` names a `FenceModel`
(`model`), not `product_line`; `gaps[].because{code,params}` replaces the flat
fields and `gaps[].subject` carries `id` + `tenant`; `warnings[].cites` is a
list; the `slope_method` row's value is a `Token{key, value_raw}`; `lang_basis`
is present on every warning; an unlexemed warning's `severity_lexeme` is `null`;
and `gaps[0].cites` now resolves to a `source_docs` entry that exists.

Two of your corrections went further than the fixture's shape:

- **`curation_level` dropped from 2 to 1** on the structural rows, since your
  corpus has no level-2 population and won't for a while — a mostly-level-2
  fixture was exercising a path that will never run.
- **`(exposure_category=B, hvhz=true)` added to `uncovered`.** It was previously
  in neither a row nor `uncovered` — silently missing from the six-point domain
  the table declares, which §1.3's BINDING clause forbids. We want to be honest
  that this is a stand-in, not agreement it's the right representation — see
  §9.3.

**One finding we deliberately did NOT fix in the fixture: `max_span_mm` still
models a condition → value lookup.** Your §1.1(a) is right that the real table is
`(footing depth, max span)` design points, and changing the fixture to match
would mean inventing an answer to §9.4 rather than recording one honestly wrong
in the way the real table is.

### 9.1 — `curation_level` 0 vs 1

No objection to your provisional reading (0 = asserted, uncited; 1 = cited,
unconfirmed; 2 = person-checked). Our `SourcePolicy` (§1.4) reads
`curation_level` only as a gate ordinal, and — worth being honest about — we
don't enforce `SourcePolicy` at all yet; items 6/7 in our own build order are
explicitly parked pending your design (`next-session.md`). So nothing on our
side has an independent stake in what separates 0 from 1 today. Publish against
your reading; we'll build the enforcement against whatever you've written down
by the time we get there.

### 9.2 — is a slot-structure edge a "value" under invariant 8?

We don't consume `models`/`parts`/`combinations` from a snapshot at all yet —
they're accepted, counted, and left as opaque payload (`unconsumed`), by
deliberate design (`knowledge/snapshot.py`'s own docstring: "a field parsed into
a shape we invented is a shape nobody agreed to"). So whichever way you resolve
this doesn't block us today.

For when we do build that consumer: our own containment model (`ContainedSlot`,
the kit-credit rule, done 2026-08-25) already treats "how many of this part a
slot needs" as **authored structure**, with citation riding at the membership
level rather than per structural count. That's the same shape your narrowing
points at — membership cited to the sealed BOM, slot count authored. So we'd
lean **no**, structure doesn't need its own `SourceRef`, matching your own
instinct, but this is a preference from a team that hasn't built the consumer,
not a requirement.

### 9.3 — a representation for "not approved," distinct from "not covered"

We think this needs a **ninth `GapKind`**, not a repurposing of one of the eight.
None fits: `uncovered_condition` says "we may not know" or "no row covers this,"
which is the opposite of "we checked, and the answer is no." We'd propose
something like `condition_excluded` — `subject` names the parameter, and
`because.params` carries the excluded point (mirroring how `uncovered_condition`
already carries `point`).

One thing worth flagging on our side: `GapKind`'s eight values are enumerated
inline in the contract's STABLE CORE text (§1.2.1), not in the free registries
(§2) the way `SourceClass`/`TaskCode` are — so we think a ninth kind is a
trigger-D (defect) amendment candidate, not a registry addition. Non-blocking on
either side (no snapshot ships today), so batching is fine — we'll log it as a
candidate on our end too, and we're glad to co-author the amendment text
whenever a batch is ready.

### 9.4 — can a `ParameterTable` row carry a paired value?

Our read of your three options: **(2)** — footing depth as an explicit
additional **domain dimension** alongside `exposure_category`/`hvhz` — is the
one we'd ask you to build, for a reason that's about cost, not elegance:
condition dimensions are a free registry addition on our side already
(`docs/integration-contract/contract.md` §2 — "Condition dimensions... Planning
declares what it can bind"), so adding `footing_depth_mm` as a domain key needs
no amendment from either team. Option (1) — a native paired `value_type` — would
extend the closed `quantity(<UnitCode>) | token(<closed set>)` union in the
stable core (§1.1/§1.3), which we think needs the same amendment process as
§9.3's `GapKind` addition. Option (3) we agree with your own objection to: it
throws away the cheaper compliant choice, which is the opposite of what a BOM
optimizer exists to preserve.

**Being honest about the cost this actually lands on us, not you:** publishing
the extra domain key is the cheap part. Resolving it means our generator has to
be able to CHOOSE a footing depth per post rather than treat it as fixed input —
that's a real feature on our side (a footing-depth decision the strategy layer
doesn't have today), not a data-shape fix that comes for free once you publish
the wider table. We'd rather say that now than have it surface as a surprise
later.

### 9.5 — `TaskCode` spellings

Confirmed: `structural_parameter`, `component_dimension`, `installation_step`,
`product_description` — that's what the corrected fixture now uses.
