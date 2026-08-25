# Ratification — contract v1.1

```text
Purpose:  The countersigned record that closes v1.1. Supersedes audit/10, where
          v1.0 was frozen, signed by one side, and correctly NOT signed by the
          other — see §0.
Status:   Planning & BOM signed 2026-08-25. Knowledge Platform: awaiting.
Action:   Knowledge team — verify, sign §3. Amendment 001 is accepted and applied,
          which is the only thing that was blocking you.
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

## 3. Knowledge Platform — awaiting

**Amendment 001 is accepted and applied.** Your own §3.3 said you sign on a disposition of
001 and nothing else, so this should be short.

**What changed since you drafted your attestation:** obligation 6's final clause, exactly as
you proposed including `version_status`; `AMENDING.md` gained §3a covering amendments filed
before ratification; and the hash table is gone in favour of quoting the manifest.

**Your declared non-compliance carries over as filed** — `audit/10` §3.2, which we are not
asking you to restate: one live violation (obligation 6's level-2 clause, with
`cross_family_verified` still in `PROMOTABLE` and K1 committed to revoking it), twelve
obligations unbuilt, three representational gaps, one extractor missing. It is the most
useful thing either side has written at a signature, and re-typing it would only risk
changing it.

```text
Ratified for the Knowledge Platform — [date], contract v1.1
Copies verified: [ ] contract.md   [ ] AMENDING.md   (via contract.sha256)
Declared non-compliance: as filed in audit/10 §3.2
```

If anything still reads wrong, the instruction has not changed: file an amendment rather
than sign. It has already earned its keep once.

## 4. What ratification does and does not do

**Does:** fix v1.1 as the version both sides build against, and start the clock on the
amendment procedure.

**Does not:** mean either side satisfies it. §2 and `audit/10` §3.2 are proof. A contract
states what will be true, and the gap between it and today is what the next stretch of work
is for.

**Does not** end the conversation. Five rounds now: 29 items, then 6, then 13, then 4, then
1 — each found what the previous could not, because each checked against a different
substance. The fifth was a cold re-read of a document everyone believed was finished.
