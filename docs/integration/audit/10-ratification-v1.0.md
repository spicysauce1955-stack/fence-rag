# Ratification — contract v1.0

```text
Purpose:  The countersigned record that closes v1.0. Until BOTH blocks below are
          signed, the contract is FROZEN but NOT RATIFIED — and AMENDING.md §5
          is explicit that "they did not object" is not acceptance.
Status:   Planning & BOM signed 2026-08-25. Knowledge Platform: awaiting.
Action:   Knowledge team — verify, fill in §3, commit. That is the whole ask.
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
| **`AMENDING.md`** | `3190bdf52b8f9c0adc2a4acca9a4a5b5a9602c03952ca9406b2baae2fbd46957` |
| **Copies** | `fence-rag/docs/integration/` and `BOM/docs/integration-contract/`, byte-identical |

```bash
sha256sum -c contract.sha256      # both lines must print OK
```

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

## 3. Knowledge Platform — awaiting

**To sign, replace this block with the same four attestations, plus whatever you
declare.** The two that matter:

- **Your copy verifies** against the manifest in §1 — including `AMENDING.md`, which was
  not covered when you last checked.
- **Any obligation you cannot currently satisfy**, declared here rather than found later.
  Ours are above; the point is symmetry, not confession. Candidates on your side, from
  your own notes: obligation 6's *"nothing reaches level 2 without a person having
  compared it to the source image"* against `reviewer` being NULL on all 1,225 readings
  and `cross_family_verified` still sitting in `PROMOTABLE`.

If any of the 18 reads wrong on a second pass, **do not sign** — file an amendment
instead. A trigger-A falsification is admissible any time, and an unsigned v1.0 with a
real objection is worth more than a signed one with a silent reservation.

```text
Ratified for the Knowledge Platform — [date]
Copies verified: [ ] contract.md   [ ] AMENDING.md
Declared non-compliance: [ … or "none" ]
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
