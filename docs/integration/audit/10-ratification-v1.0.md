# Ratification — contract v1.0

```text
Purpose:  The countersigned record that closes v1.0. Until BOTH blocks below are
          signed, the contract is FROZEN but NOT RATIFIED — and AMENDING.md §5
          is explicit that "they did not object" is not acceptance.
Status:   SUPERSEDED. v1.0 was never ratified. Amendment 001 was accepted and
          applied; contract.md is v1.1 and ratification moved to audit/11.
Kept:     Unedited. §3.2 is the Knowledge team's declared non-compliance and is
          referenced by audit/11 rather than restated. §1's hash table carries a
          stale AMENDING.md value and the correction that caught it — both left in
          place, because the correction is the useful half.
```

## 0. Why this file exists

The freeze was done unilaterally. Planning wrote it, generated the hash, wrote the
amendment procedure and placed a copy in this repository. The Knowledge team's
`08-close-of-round.md` §7 says *"we are authoring against v1.0 as it stands"*, which is
acceptance in substance — but there is no artifact both sides have signed, and our own
procedure forbids ratifying by inference.

So: one file, two blocks, and v1.0 is closed when the second is filled in.

**And one gap in the mechanism, found writing this.** `contract.sha256` covered
`contract.md` and not `AMENDING.md` — the document protecting the frozen contract was
itself unprotected, so the protection could be edited away without detection. The manifest
now covers both. Re-verify before signing.

---

## 1. What is being ratified

| | |
|---|---|
| **Document** | `contract.md`, v1.0, 18 BINDING obligations |
| **Procedure** | `AMENDING.md` — four triggers, five steps |
| **Manifest** | `contract.sha256`, covering both files |
| **`contract.md`** | `89ab5c1a5bfcf3c7e2f55b0cbee8d43bae2c453c3426f0e421fe183d24293fcc` |
| **`AMENDING.md`** | `8a8e9cd4b1cdaaa1c507dd080c0bb67486aab8216efa94e9c0b92478f83b13a3` ⟵ *corrected, see below* |
| **Copies** | `fence-rag/docs/integration/` and `BOM/docs/integration-contract/`, byte-identical |

```bash
sha256sum -c contract.sha256      # both lines must print OK
```

> **Correction to this table, made by the Knowledge team at countersignature.** The
> `AMENDING.md` hash written here was `3190bdf5…`, which is the file **as it stood at
> commit `9c60d79`** — before the self-coverage edit that `§0` above describes. That edit
> landed in `7b02c0f`, the same commit as this record, and `contract.sha256` was
> regenerated for it while this table was not. The manifest value is `8a8e9cd4…`, both
> files verify against it, and the diff between the two versions of `AMENDING.md` is
> exactly the self-coverage fix — the `# both lines must print OK` line, the paragraph
> explaining it, and `sha256sum contract.md AMENDING.md` in §3 step 5. No binding text
> moved.
>
> Verified independently rather than assumed:
>
> ```text
> git show 9c60d79:docs/integration/AMENDING.md | sha256sum   →  3190bdf5…  (the stale value)
> git show 7b02c0f:docs/integration/AMENDING.md | sha256sum   →  8a8e9cd4…  (the manifest value)
> sha256sum -c contract.sha256                                →  contract.md: OK
> >                                                              AMENDING.md: OK
> ```
>
> Signing an attestation that *"our copy verifies against the manifest above"* against a
> table naming a file we do not hold is the kind of thing this record exists to prevent,
> so it is corrected here rather than waved through. `contract.md`'s hash was right.

## 2. Planning & BOM — signed

**We attest:**

1. Our copy verifies against the manifest above, and is byte-identical to this one.
2. We have read all 18 obligations and accept them as promises a consumer relies on.
3. We will not edit `contract.md`. A change to a BINDING item goes through
   `AMENDING.md`; registry additions and internal design do not.
4. **We are ratifying a contract we currently violate, and we are declaring it rather
   than letting it be discovered.**

**Known non-compliance at ratification.** Obligation §3.2.4 — *never fail a run over a
gap* — is violated in two places in our engine today:

| | Where | Effect |
|---|---|---|
| An uncovered `max_span` | `strategy/generator.py:1521` | raises `GenerationFailure`; an uncovered exposure category produces **no plan at all** |
| Two published rows tie and disagree | `knowledge/evaluator.py:107` | raises rather than conflicting — and the exposure **grows** as this platform publishes more |

Both close with the same change — `Gap` as a return type — which is also v0.4 delta item 1.
Neither is a reason to delay ratification: the obligation is right, we are not, and saying
so at signature is the point of a ratification record.

**We commit to, before proposing any amendment:**

- `Gap` as a return type across all thirteen `GenerationFailure` sites, and
  `origin: authored | published` on `KnowledgeVersion` so a published tie warns rather
  than raises.
- Site conditions bound, with the `site_conditions_changed` guard.
- A first implementation of the source policy, which today has **zero lines** despite
  being binding and despite our having re-ranked it twice.
- To report progress against this list rather than to send another design document.

```text
Ratified for Planning & BOM — 2026-08-25
Copies verified: contract.md OK · AMENDING.md OK
```

## 3. Knowledge Platform — NOT SIGNED, pending amendment 001

**We are not signing v1.0, and the reason is the instruction in the block this replaces:**

> *If any of the 18 reads wrong on a second pass, do not sign — file an amendment instead.
> A trigger-A falsification is admissible any time, and an unsigned v1.0 with a real
> objection is worth more than a signed one with a silent reservation.*

One does. **Obligation 6's final clause is the wording §1.4 marks as superseded** —
*"resolution honours the source policy, recording `admitted_by` on the winner"* — which
binds this platform to apply the policy that §1.4 assigns to Planning, to stamp
`admitted_by` where §1.4 puts it on the run, and to select a winner that §1.4 says does not
exist at publish time. Filed as
[`amendments/001-obligation-6-superseded-clause.md`](../amendments/001-obligation-6-superseded-clause.md),
**trigger D**, with the proposed replacement text and a cost of nothing to either side.

This is not a disagreement — both teams accepted the substance twice, in
`06-review-of-v0.4.md` §2 and `07-delta-disposition.md` §2. Only the obligation text was
missed when §1.4 changed. Per `AMENDING.md` §3 step 2 the amendment governs nothing, v1.0
still holds, and we keep building against it.

**Everything else is ready.** The attestation below is drafted in full and final; it needs
a disposition on 001 and a date, not another review pass. If Planning would rather ratify
v1.0 as it stands and batch 001 into v1.1, say so and we will sign this as written with 001
noted as pending — but on our reading of §3 that is the choice the instruction was written
to prevent, so we are not making it unilaterally.

### 3.1 What we attest (drafted, unsigned)

1. Our copy verifies against the manifest in §1 — **both files**, with the §1 table
   corrected above. `contract.md: OK`, `AMENDING.md: OK`.
2. We have read all 18 obligations cold. We accept 17 of them as promises a consumer
   relies on. Obligation 6 is amendment 001.
3. We will not edit `contract.md`. A change to a BINDING item goes through `AMENDING.md`;
   registry additions and internal design do not.
4. We are ratifying a contract we do not yet satisfy, and we are declaring where, rather
   than letting it be discovered.

### 3.2 Declared non-compliance

**One live violation.** Obligation 6 — *"nothing reaches level 2 without a person having
compared it to the source image"*:

| | Measured |
|---|---|
| Table readings | **1,225**, `reader_kind = agent` on every one |
| Human reviews | **0** — `reviewer` is NULL on all 1,225 |
| Promoted on `cross_family_verified` | **504** readings → **324** facts |
| Which is | two *agents* agreeing, and it sits in `table_review.PROMOTABLE` today |

Published as-is, 324 facts would carry a curation level no person has checked. The remedy
is ours and is already committed as K1: revoke `cross_family_verified` from `PROMOTABLE`,
which takes the level-2 population to **zero** until human review begins. We would rather
publish nothing at level 2 than launder agent agreement into it.

**Twelve obligations are unbuilt rather than violated** — 1, 2, 3, 5, 7, 8, 9, 11, 12, 13,
15 and 18 all describe a publishing layer that does not exist here: no snapshot, no
`ParameterTable`, no part-type spine, no assembly model, no tenancy. Two are worth naming
rather than hiding in the class:

- **Obligation 3.** `GET /source-refs/{id}` has a complete design and seven fixture records
  and **zero lines of implementation**. 73,894 of 81,794 boxed elements have no crop, so it
  must render on demand rather than serve a cache.
- **Obligation 7.** There is no tenant concept anywhere in this store — one corpus, no
  boundary to enforce in code. *Enforced by convention* would be a generous description of
  something that does not exist at all.

**Three representational gaps we will hit at publish time**, declared now because they are
exactly the kind of thing found later:

- **Obligation 4's dual-unit clause** — *"where a source states two units and they
  disagree, publish both"*. The corpus has **48 distinct such statements across 12
  documents** (36 in the two CSI masterspecs), disagreeing by 0.1–0.6 mm: `4 inch (101 mm)`
  where 4″ is 101.600 mm, `3-1/4 inch (83 mm)` where it is 82.550. Our `facts` schema holds
  exactly **one** `value_original` / `unit_original` pair per row and cannot represent a
  disagreeing second. Our schema change, no contract impact.
- **Obligation 15's `condition_basis`** — no such field exists here, and there is a live
  defect behind it: **324 facts carry `_applicability_basis`**, an underscore-prefixed
  free-text key sitting *inside* `conditions`, which under §1.3 would publish as a
  condition dimension. Disclosed in `06-review-of-v0.4.md` §1, not yet fixed.
- **Obligation 10's `lang`** — required and never normalised, and **no language field
  exists anywhere in this store**. We would publish `en` by assertion. For these 226
  warnings that is almost certainly right, and it is still an assumption rather than a
  measurement, which is the distinction obligation 10 exists to hold.

**And one that is only work:** obligation 14's `stock_length` has no extractor — *"Standard
rails are supplied in 16 foot lengths"* is text in the store, not a fact. Curation, not a
contract problem.

### 3.3 Signature block

```text
Ratified for the Knowledge Platform — NOT YET
Copies verified: [x] contract.md OK   [x] AMENDING.md OK  (against contract.sha256,
                     with the §1 table corrected — see the note under §1)
Blocking:        amendment 001 — obligation 6 carries a clause §1.4 superseded
Declared non-compliance: §3.2 above — one live violation (obligation 6, curation
                 level 2 asserted by agents), twelve unbuilt, three representational
                 gaps, one extractor missing
Signs on:        a disposition of 001. Nothing else outstanding on this side.
```

---

## 4. What ratification does and does not do

**Does:** fix v1.0 as the version both sides build against, and start the clock on the
amendment procedure. Every later change dates from here.

**Does not:** mean either side satisfies it yet. §2 is proof of that. A contract is a
statement of what will be true, and the gap between it and today is what the next stretch
of work is for.

**Does not** end the conversation either. Four rounds produced 29 items, then 6, then 13,
then 4 — and every round found things the previous could not because each checked against
a different substance. The amendment procedure exists so a fifth round is cheap, not so it
is discouraged.
