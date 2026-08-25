# Ratification — contract v1.1

```text
Purpose:  The countersigned record that closes v1.1. Supersedes audit/10, where
          v1.0 was frozen, signed by one side, and correctly NOT signed by the
          other — see §0.
Status:   RATIFIED. Both sides signed 2026-08-25. v1.1 is the version both teams
          build against, and the amendment clock starts here.
Action:   None on the boundary. What each side owes the other is work — §4.
```

## 0. Why there is a v1.1 before anyone signed v1.0

The v1.0 record asked the Knowledge team to read all 18 obligations cold and told them:
*if any reads wrong, do not sign — file an amendment instead.*

One did. **Obligation 6 still carried the clause §1.4 marks as superseded** — binding the
Knowledge Platform to apply a source policy that v0.4 had moved to Planning, to stamp
`admitted_by` where §1.4 puts it on the run, and to select a winner that §1.4 says does not
exist at publish time. Filed as amendment 001, trigger D, accepted in full.

**The defect was ours.** When §1.4 changed we rewrote the BINDING block and never checked
whether an obligation restated the old rule. Obligation 6 did, verbatim, and it survived
four review rounds and a freeze because every round after v0.4 read §1.4 and nobody re-read
§3.1 against it.

**Two things worth recording rather than tidying away:**

- **The mechanism worked on its first real use, and it worked by refusing.** The instruction
  most likely to be treated as boilerplate — *do not sign if something reads wrong* — is the
  one that caught a self-contradiction in a frozen contract.
- **The v1.0 record's §1 table carried a stale hash for `AMENDING.md`**, written by hand
  before an edit landed in the same commit and never re-copied. The Knowledge team caught it
  with `git show` rather than assuming, and declined to attest *"our copy verifies"* against
  a table naming a file they do not hold. Correct call: a hand-copied hash beside a generated
  manifest is a second source of truth, which is the thing the manifest exists to prevent.
  **This record quotes the manifest and copies nothing by hand.**

## 1. What is being ratified

| | |
|---|---|
| **Document** | `contract.md`, v1.1, 18 BINDING obligations |
| **Procedure** | `AMENDING.md` — four triggers, five steps, plus §3a |
| **Manifest** | `contract.sha256` — the authority for both values below |
| **Changed since v1.0** | obligation 6 only (amendment 001), and `AMENDING.md` §3a |
| **Copies** | `fence-rag/docs/integration/` and `BOM/docs/integration-contract/` |

```text
8286daddd5c378a1d9696c483618aea7bc9615b7dd1850608bf6eae91730e308  contract.md
f81646cac52d468e5885dff788fdf1f58aa511bf084408e207ceefdf509c8d47  AMENDING.md
```

```bash
sha256sum -c contract.sha256      # both lines must print OK. Trust this, not a table.
```

## 2. Planning & BOM — signed

**We attest:**

1. Our copy verifies against `contract.sha256`, and is byte-identical to this one.
2. We have read all 18 obligations and accept them as promises a consumer relies on.
3. We will not edit `contract.md`. A change to a BINDING item goes through `AMENDING.md`;
   registry additions and internal design do not.
4. **We are ratifying a contract we currently violate, and declaring it rather than letting
   it be discovered.**

**Known non-compliance.** Obligation §3.2.4 — *never fail a run over a gap* — is violated in
two places in our engine today:

| | Where | Effect |
|---|---|---|
| An uncovered `max_span` | `strategy/generator.py:1521` | raises `GenerationFailure`; an uncovered exposure category produces **no plan at all** |
| Two published rows tie and disagree | `knowledge/evaluator.py:107` | raises rather than conflicting — and the exposure **grows** as this platform publishes more |

Both close with the same change — `Gap` as a return type.

**We commit to, before proposing any amendment of our own:** `Gap` as a return type across
all thirteen `GenerationFailure` sites, with `origin: authored | published` on
`KnowledgeVersion`; site conditions bound with the `site_conditions_changed` guard; a first
implementation of the source policy, which today has zero lines despite being binding; and
to report progress against that list rather than send another design document.

```text
Ratified for Planning & BOM — 2026-08-25, contract v1.1
Copies verified: contract.md OK · AMENDING.md OK  (via contract.sha256)
```

## 3. Knowledge Platform — SIGNED

**We attest:**

1. Our copy verifies against `contract.sha256` — `contract.md: OK`, `AMENDING.md: OK` —
   and the two values §1 quotes are the manifest's own, checked by recomputing both
   digests independently rather than by reading the table.
2. We have read all 18 obligations, and we accept all 18 as promises a consumer relies on.
3. We will not edit `contract.md`. A change to a BINDING item goes through `AMENDING.md`;
   registry additions and internal design do not.
4. We are ratifying a contract we do not yet satisfy, and we have declared where.

**How obligation 6 was verified, since a second cold read of unchanged text proves
nothing.** We diffed v1.0 against v1.1 rather than re-reading it:

```text
git diff 7b22de3 9011f6f -- contract.md   → the version header, and obligation 6. Nothing else.
git diff 7b22de3 9011f6f -- AMENDING.md   → §3a only.
```

The replacement text is amendment 001's proposal verbatim, `version_status` included, plus
a parenthetical recording the change. The cold read behind our v1.0 block therefore still
stands for the other 17, and obligation 6 is now the clause we proposed. Nothing else in
the document moved under us, which is the property the freeze exists to give and the
first time it has been used to check one.

**On `version_status` being kept in** — noted, and your reasoning is the better version of
ours. It is the same clause rather than an adjacent one, and filing it separately would
have been more procedurally pure and less correct.

**Our declared non-compliance stands as filed in `audit/10` §3.2**, unchanged and not
restated: one live violation (obligation 6's level-2 clause — `reviewer` NULL on all 1,225
readings, 504 promoted on two agents agreeing, `cross_family_verified` still in
`PROMOTABLE`, K1 committed to revoking it), twelve obligations unbuilt, three
representational gaps (obligation 4's dual-unit clause, obligation 15's `condition_basis`
with 324 facts carrying an underscore-prefixed key inside `conditions`, obligation 10's
absent `lang`), and one extractor missing for obligation 14's `stock_length`.

Obligation 6's new text does not change any of it. It removes work — no policy evaluator
on this side — and adds one honest field, `version_status`, which we already hold on every
document and will publish as `unknown` for 132 of 144 of them.

```text
Ratified for the Knowledge Platform — 2026-08-25, contract v1.1
Copies verified: [x] contract.md OK   [x] AMENDING.md OK   (via contract.sha256,
                     both digests recomputed independently)
Declared non-compliance: as filed in audit/10 §3.2 — one live violation, twelve
                     obligations unbuilt, three representational gaps, one
                     extractor missing
Amendments open:     none
```

**Nothing reads wrong on this pass.** v1.1 is the version we are building against, and the
next thing from this side should be the cell box, the eleven-warning starter list, the two
early publishes and `also_filed_as` — work, not a document.

## 4. What ratification does and does not do

**Does:** fix v1.1 as the version both sides build against, and start the clock on the
amendment procedure.

**Does not:** mean either side satisfies it. §2 and `audit/10` §3.2 are proof. A contract
states what will be true, and the gap between it and today is what the next stretch of work
is for.

**Does not** end the conversation. Five rounds now: 29 items, then 6, then 13, then 4, then
1 — each found what the previous could not, because each checked against a different
substance. The fifth was a cold re-read of a document everyone believed was finished.
