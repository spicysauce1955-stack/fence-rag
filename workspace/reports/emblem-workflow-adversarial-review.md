# Emblem workflow adversarial review

Date: 2026-09-07. Three independent agents reviewed source integrity, lifecycle
semantics, and verification/reporting. Reproductions used disposable stores;
no synthetic review was added to the live ledger. The parent reproduced and
reconciled findings, implemented fixes, and requested independent rechecks.

## Findings and disposition

| Finding | Evidence and consequence | Disposition |
|---|---|---|
| Fact-review export reordered backdated decisions | Live projection used arrival order, export used timestamps; fresh replay could resurrect a rejected Part | Export preserves arrival order within each evidence anchor. Import refuses incompatible or incomplete chronology, rechecking under its write transaction. Backdated, tied, partial, concurrent and idempotent replay regressions added. |
| Concurrent reading imports created duplicates | Both callers checked absence before starting their write transaction; interleaving produced 14 rows instead of 7 and later publication refused | Acquire the write lock before checking; preserve caller transactions using a savepoint. Concurrent imports and failed-write rollback tested. |
| Unsupported review annotations reached publication | A projected corrected value and level-2 status could publish without any fact-review record | Read-only validation binds projections to the latest authoritative ledger record and refuses unsupported or stale annotations. |
| Review followed moved citation pixels | Changing a reviewed element's bbox caused level-2 publication citing a new region | Compare the ledger's review reference with the current canonical reference; the original reproduction now refuses. |
| Long decimals were silently rounded | Decimal context accepted `6.00000000000000000000000000001 in.` as exactly 152400 milli-mm | Use exact rational arithmetic and refuse nonrepresentable values. Regression covers long corrections. |
| Corrected Parts reused version 1 | Values and classifications changed under the same Part ID/version | Derive public string versions from the full public Part content. Same-content replay is stable; changed content gets a different version. |
| Markdown overstated publication after rejection | JSON withheld board/rails, but prose still claimed all four Parts published | Generate actual published/withheld counts, identities and reasons. Partial/rejected publication tests added. |
| Tests assumed the live store would stay unreviewed | A valid correction or rejection broke the canonical integration fixture; rejection subtests shared state | Reset only this extractor's facts/reviews in a disposable copied store; test each rejection independently. |

## Verified current data

All seven pinned source anchors match the retained exact-model project sheet.
Cap 73013956 matches its own source row. Board/cap measurements remain nominal;
rail A/B identities remain provisional. The seven live facts remain unchanged
and `extracted`. The four Parts match the previous snapshot apart from versions.

Current verified local snapshot:
`b5048772101e18513a9cbd2c913978da05046fced986e03c42afddc5c5b19ec7`.
It contains four exact Parts; full-model admission and assembly validation remain
false. It also verifies using committed HEAD `snapshot.py`, independently of
the pre-existing working-tree verifier changes. The archived version-1 snapshot
is preserved.

## Limits retained

- Already-exported ledgers that lost original arrival order cannot reconstruct
  it without another authoritative record. No historical ordering is fabricated.
- Public preflight accepts string Part versions, but the private Planning Part
  types require integers. A lossless consumer path remains unimplemented; these
  versions do not prove direct consumer compatibility or chronological order.
- Missing receiving/engagement geometry, board pitch, fitting rules, and public
  geometry/provenance mapping still prevent the complete Emblem assembly.
- Pre-existing edits to `snapshot.py` and concurrent integration conversation
  changes were preserved and are not attributed to this review.

## Validation

Independent agents passed 60 Emblem tests and 132 review tests. After the final
two-connection chronology-race regression, the full suite ran **1,579 tests in
59.536 seconds: OK, with one existing expected failure**. The full log is
`workspace/tests/emblem-adversarial-final-suite.log`. Frozen boundary checksums
and diff whitespace checks pass.


## G104 follow-up: public consumer receipt blockers

The previous public ingestion limitation is now closed in the local Planning
checkout: four actual draft Parts round-trip exactly through the public reader
without changing their opaque versions or activating them. Private generation
mapping remains unimplemented. The cumulative patch/base receipt is
`emblem-consumer-public-receipts-patch.json`.

Independent reviewers found two defects: the diagnostic described document
retention too broadly (it now explicitly guarantees typed hash joins, excluding
unknown extensions), and an admission date still aliased input state (fixed by
deep copying the admission result, with a dated-source regression). Six manual
fault probes refuse incomplete/changed receipts. Root: 1,589 tests, OK with one
expected failure. Planning: 2,603 passed, seven warnings. Both frozen checksums
pass. Neither model publication nor assembly validation is claimed.
