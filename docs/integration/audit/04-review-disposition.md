# Response to `03-review-of-v0.2.md`

```text
Status:  Decision. From the Planning & BOM team.
Result:  All six blocking defects fixed in contract.md and
         knowledge-datamodel.md, now v0.2.1. Every non-blocking item fixed
         too — none was worth carrying to v0.3.
Checked: Two of your claims were checkable facts rather than judgements, so we
         checked them instead of accepting them. Both hold. One of your
         questions surfaced a bug in our engine — §3.
```

---

## 0. On the review itself

Six defects, four of them ours in the plainest sense: we wrote a binding rule about
units and then broke it twenty-three times in the same document. Naming that as
*"not a request to change the rule, a request to apply it"* is the correct framing
and it is the one we would have argued for ourselves had we caught it.

Two things about the method are worth recording, because they are why this round
was cheap:

**You used §8 the way it was meant to be used.** The instruction was *take the
artefact and check you could author it*, and six of the twenty-nine came back as
"we cannot" — with the specific artefact each time. That is a different and better
signal than "this looks under-specified", and it is what made `PostSlot` an outright
fail rather than an ambiguity.

**Two of the six were opened by your own acceptances**, not by our drafting: B6 by
accepting N18, and B3's severity by accepting the `Span` worked examples. A review
that only looks for the other side's mistakes would have found neither.

---

## 1. The six, and what changed

| # | Defect | Fix | Where |
|---|---|---|---|
| **B1** | `Gap` is tier 3 "never consumed", and N17 publishes gates as `Gap`s | `Gap` and `Rule` moved out of the never-consumed sentence; the crossing table now lists seven, reconciled with contract §1.2 | datamodel §4 |
| **B2** | `contributing_sources` absent from the contract; `ParameterTable` has no join target; no closure rule | The join is **snapshot-level** — `Provenance.cites[].belongs_to → Snapshot.source_docs`. `contributing_sources` stays as a roll-up. New BINDING closure rule, and invariant 12 | contract §1.2, datamodel §2.5, §6 |
| **B3** | Twenty-three `_mm` fields reintroduce undeclared rounding | Every dimension is a `Quantity`. Invariant 7 rewritten. **And an honest limit stated** — see §2 | datamodel §2.3.1, contract §3.1.4 |
| **B4** | Three tied ranks against two BINDING promises | Ranks unique within a row; `ai_proposal` shown; tie-break rule stated and BINDING | contract §1.4, datamodel §2.6 |
| **B5** | `SlotTarget`, `PostSlot`, `Token`, `Param` named and never defined | All four defined. `Anchor` split into origin + offset expression. `PostSlot` defined with `contains`, and `for_post_roles` moved onto it | datamodel §3.3, §3.4, §3.6, §3.8 |
| **B6** | Unconditioned rows unrepresentable — 66% of the class N18 admits | `condition_basis: stated \| assumed`, with the two rules that make it work: excluded from the `unique` check, and warned on application | datamodel §3.8.1, contract §3.1.13 |

**B5 deserves a note, because your `Param` critique was the sharpest thing in the
review and we had not seen it.** v0.2 made `Param(key, delta)` an anchor — a value
and an offset and **no origin** — while every other anchor named one. So *host
length minus (a parameter plus a constant)* was inexpressible, and the rewrite to
`Span{Datum(grade), Param(footing_depth, +178)}` was an equivalence the document
never proved and which holds only if the post is set to exactly the footing depth.
Splitting `Anchor` into an origin and a small offset expression (`Const | Param |
Sum | Neg`) says what the cell prints. The grammar is deliberately tiny — no
products, no conditionals — because a bigger one would be a second rule engine.

**And B5's `Reused` target answers a non-blocking item at the same time.** Your
temporary-spacer rail — *"Use only one rail as temporary spacer for your entire
fence"* — is a BOM part placed twice and bought once, which invariant 4 as written
made unpublishable. `Reused(slot_path)` names the slot from a second step without a
second placement. §7.3 answered the `unplaced` half of N24 and not that half; it
does now.

---

## 2. B3 — accepted, and one thing we will not pretend is fixed

Every `_mm` field is a `Quantity`. That part is simply applying our own rule.

**What the edit does not fix, stated plainly rather than left for you to find.**
Planning stores integer millimetres at rest (ADR-0002). So the boundary now carries
22225 and the engine rounds **once**, in `adapt.py`, declared and inspectable
instead of distributed across twenty-three field definitions. That is a real
improvement and it is not a complete answer: rounding a *pitch* and then multiplying
by thirteen reintroduces exactly the loss you measured, one layer in.

Two consequences, and only the first is in this round:

1. **The fitting arithmetic consumes thousandths and rounds only its outputs.**
   `fit.py` takes the micron pitch, computes positions and residual in thousandths,
   rounds what it emits. Storage stays integer mm; *transient* arithmetic moves from
   float to thousandths. ADR-0002 says "float only transient" — this keeps the letter
   and fixes the accumulation you demonstrated.
2. **Elsewhere, a rounded value that gets multiplied has no answer yet.**
   `adapt.py` will emit `warning.rounding_accumulates` when it rounds a value marked
   as a repeat dimension and the residual over the declared repeat count exceeds
   `NUMERIC_TOLERANCE_MM`. Visibly suspect beats quietly wrong, and a real fix is an
   ADR-0002 amendment rather than a document edit.

Publish thousandths and the lexeme. Do not pre-round to be helpful.

---

## 3. Your N18 question — the answer is neither option, and it found a bug

You asked whether the 1800 mm fallback is **silent** (contradicting our never-block
obligation) or already **warned** (making N18 less urgent), because it changes
whether N18 is a fix or a workaround.

We checked the code. It is neither.

**1800 is not hardcoded in the engine.** It is `K-MAXSPAN`, a knowledge object in
the bundled base, `type=hard_constraint`, and it resolves through the ordinary
precedence ladder into the decision graph with an attribution. A real
`ParameterTable` does not compete with it silently — it replaces it. So your bad
case does not apply, and `rationale.md` §5's real complaint stands unchanged:
`attributed_to="manufacturer"` is a bare string, so a reader sees an attribution
that looks legitimate and cannot be checked.

**But if no rule applies at all, the run does not warn. It fails.**

```python
# strategy/generator.py:1521
res = resolve_param(seg_kb, seg_ctx, "max_span_mm")
if res.winner is None:
    raise GenerationFailure(f"no max_span_mm knowledge applies to run {run.id}")
```

That is a **direct violation of contract §3.2.4** — *"Never fail a run over a gap.
Warned, named, unfulfilled lines instead"* — sitting in our engine today, on the
single most important parameter in the system. Publish a snapshot whose
`max_span_mm` table covers Exposure B and C, plan a site at Exposure D, and you do
not get a warned line. You get no plan.

Three things follow:

- **It is ours and it is now our step 0**, ahead of everything in
  `planning-asks.md` §8. There are thirteen `GenerationFailure` raise sites and
  we are auditing all of them against §3.2.4, not just this one.
- **N18 is more urgent, not less.** Your two options both assumed a fallback
  existed. The honest position is that absence is currently fatal, so the argument
  for admitting installation manuals is not "avoid a silently wrong constant" but
  "avoid an unplannable project" — until we fix the failure path, at which point it
  returns to being the milder argument we originally made.
- **We are correcting the disposition's reasoning, not its decision.** N18 §3.2
  argued from *"every span falls back to the hardcoded 1800 mm"*. That sentence was
  wrong about our own engine. The ranking stands; the reason behind it was better
  than we knew.

Thank you for asking it as a question rather than assuming the answer. Neither of
us would have found this from the documents.

---

## 4. The claim we checked and you were right about

Your §2 says our contract line *"obligation 10 — a warning is attached to its step —
was false"* misattributes it, and that v0.1's contract had **eight** obligations,
none about warnings.

We expected to correct you here, because the working copy we revised has eleven.
`git show 98c53f9:docs/integration/contract-v0.1.md` settles it: **eight, ending at
"Gaps that cannot be expressed are published as gaps."** Obligations 9–11 were
written in the same uncommitted batch as the rest of the v0.1 revision — after you
took your copy. So at the time of your audit the contract said nothing about
warnings, and what your census falsified was `knowledge-datamodel.md` **invariant
5**. Corrected in the contract header and in the README.

Worth noting the mechanism, since it will recur: **we were revising uncommitted
files while you were auditing a commit.** Neither of us was wrong; we were reading
different documents. Committing before asking for a review is cheaper than
reconciling afterwards, and we will.

---

## 5. Your three answers

**§3.1 — `material`, and you upgraded it from caveat to blocker correctly.** 42 of
43 `industry_standard` facts come from the two CLFMI chain-link documents, and the
vinyl industry-standard documents yield zero. A class 97.7% wrong-material,
promoted above manufacturer spec sheets, is not a hazard to warn about — it is the
default behaviour. `material` is bound with your five values; `system_type` is not
(one dimension you can populate beats two you cannot, and the registry takes a
second later without a negotiation). **The `industry_standard` ranking does not ship
before `material` is bound**, and a row of that class carrying no `material` is
*refused at publish* rather than treated as a §3.8.1 fallback — the fallback reading
would be "applies to every material", true of one document here and false for the
other two.

**§3.2 — `Joint`, adopted as you designed it.** You are right that the gap is a
property of the joint rather than the slot, because the two members are in different
bays. `FrameSlot.joint` is now an object, `shared_host_gap` is a `Quantity` so B3
does not bite it, and it absorbs `channel_depth` and `insertion_margin`, which were
sitting loose beside it and describe the same relationship. We added `gap_reason`,
because the corpus states the reason explicitly and it is not always expansion — and
`1"` with no reason does not tell a curator whether it scales with temperature range
or is a fixed fabrication tolerance.

**§3.3 — `also_filed_as`, accepted, and it is on `SourceDoc`.** Optional, on the
canonical filing, so `belongs_to` stays single-valued. Your canonical rule — the
filing whose manufacturer matches the document's own title block — is better than
anything we would have specified, because it is a judgement with a criterion rather
than a convention. And yes: it is **visible to the reviewer**. *"Which manufacturer
published this"* is exactly the judgement the queue exists to make, and hiding four
filings behind one hash would be the queue lying to the person using it.

---

## 6. Non-blocking — all fixed

Every item in your §2. The substantive ones: `RoleRef` removed and the registry row,
`POST /roles` and obligation 5 moved to part-type language · the thirteen (now
fourteen) obligations marked **BINDING** · the stale pointer to the superseded
datamodel · the binding-item count reconciled · `POST /source-refs:batch` added to
§1.5 · `SourceRef.source_ref_id` → `id` and `VersionRef` given `content_hash` · the
registry row reworded so the `SOURCE_*` codes cannot be read as bundle-exempt ·
§3.5's cavity predicate marked as derived · `At([…])` restored as a sibling of
`Span` under `Coverage` · invariant 6 given the two exclusions it needed (validity
windows are not collisions; unconditioned `stated` rows are excluded) · §6's counts
corrected and invariant 11 reclassified as a curation rule rather than a publish
check · `Procedure.id` added · `attaches_to` marked REQUIRED · `max_rack`'s
conditions (`slope_method`, option axes) bound in §2.7 · `version_status` uses
`active` · `knowledge-design.md`'s header and §9 brought current · the README's
"four places" → five and the warning denominator restored ·
`planning-asks.md` §4 no longer attributes N22 and N29 to you as proposals, and
the Chesterfield trace says four superseded approvals.

Two we did not change:

- **The 1,988 / 1,976 divergence** is yours to reconcile, as you said. Tell us which
  is right and we will follow.
- **`knowledge-datamodel.md`'s "kept unedited"** — you are right that the banner
  makes it inaccurate, and right that you would rather have the banner. Reworded to
  "kept so the audit can be read against what it reviewed."

---

## 7. Where this leaves the two blocked items

Your §6 holds items 4 and 5 pending B2 and B6. **Both landed in this revision**, so
the two early publishes are unblocked:

- The `declared`-domain `ParameterTable` now has `condition_basis` as well, which
  most of the install-manual rows will need.
- The superseded-source definition now has a snapshot-level `source_docs` to join
  into, and invariant 12 to check it.

Everything else in your §6 needs nothing from us. We would still rather have one of
each than a hundred of either.

**And one thing that changed on our side because of your question:** step 0 is now
auditing thirteen `GenerationFailure` sites against the never-block obligation,
ahead of the work in `planning-asks.md` §8. A snapshot that produces no plan
would have made every other item on that list untestable.
