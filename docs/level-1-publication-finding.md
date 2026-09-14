# The 524 machine-consensus readings publish nothing, and should not

```text
Status:   A MEASUREMENT that cancels a planned item. No code changed. Written
          2026-09-14 while attempting `docs/coverage-remediation-plan.md` item 5
          ("publish the 524 cross_family_verified readings at level 1").
Authority: None. It records why that item was abandoned and what replaces it.
Read first: `docs/keyword-ruler-audit.md` for the session this belongs to.
```

---

## 1 · The item, and why it is cancelled

The plan claimed: *524 machine-agreed readings wait at `cross_family_verified`; publishing them
at level 1 is the biggest coverage win needing no curator, and obligation 6 already requires
it.* **Every clause of that is wrong.** `[measured]` 2026-09-14:

| claim | measured |
|---|---|
| "machine-agreed across families" | **one reader on all 524** — `chatgpt-web-1`, family `openai-chatgpt` |
| "an unreviewed backlog" | **524 of 524 sit on cells a person has already `accepted`** |
| "a coverage win" | 523 of 524 are character-identical to the human verdict; the one difference is a trailing full stop |
| "publishes as parameters" | the columns are `ITEM` (174), `PART DESCRIPTION` (173), `MATERIAL` (177). `promote_tables.VALUE_COLUMNS` matches footing depth, diameter and post spacing. **Zero `ParameterRow`s would result.** |

So *"level 1 has never crossed the boundary"* is true, and not because a path is missing.
**There is nothing at level 1 to cross with.** These rows are the second reader's copy of
already-reviewed cells, retained because `mark_cross_family_verified` stamps the agreeing twin
and skips anything already `accepted`/`corrected` (G55).

## 2 · Obligation 6 does not require it — the plan misread it

Verbatim (`contract.md`, obligation 6): *"**Every published value** carries an honest
`source_class`, `curation_level` and `version_status` … it publishes every row it holds,
honestly classified, and Planning applies the policy at run time per §1.4."*

The subject is **published values**, and the clause forbids *filtering by policy at publish
time* — not *declining to promote an unreviewed reading*. §1.4 says unreviewed knowledge is
**allowed** into a snapshot: permission, not obligation. Obligation 8 already assigns
unexpressible knowledge to `Gap`s.

CUR-S0 is likewise not the blocker. Its commitment is scoped to level **2** —
*"we would rather publish nothing at level 2 than launder agent agreement into it"* — and
`planning-asks.md` promises Planning that such rows *"publish at level 1 and your policy
rejects them for structural tasks."* Level-1 publication was never forbidden. It simply has no
cargo.

## 3 · The near-miss — the obvious implementation recreates the defect A1 closed

`table_review.promote()` gates on `PROMOTABLE` at `table_review.py:278` and then writes, at
`:313`, a **hardcoded `review_status="reviewed"`** — which `parameters.CURATION_LEVEL` maps to
**level 2** — together with `condition_basis="stated"` and an evidence note reading
*"reviewed by … unknown"*.

**Widening `PROMOTABLE` to admit `cross_family_verified`, which is the mechanically obvious way
to implement the cancelled item, would mint level-2 facts annotated as human-reviewed from
machine agreement.** That is exactly the defect CUR-S0 revoked. The `PROMOTABLE` check is the
only guard on that path, and `reviews.rebuild`'s forgery sweep (`reviews.py:802`) re-checks only
facts with `from_candidate_id IS NULL`, so candidate-minted facts are exempt from it.

**If a level-1 path is ever built, it must not go through `PROMOTABLE`.** Route it only through
`promote_verified`, which classifies honestly.

## 4 · What the check confirmed working

Recorded because it is a real guarantee and was doubted:

- **`reader_family` fails CLOSED, not open.** `table_review.py:229` skips any cell whose seen
  families, minus `unknown`, number fewer than two. Proof in the data: `machine-kit-tables-v1`
  (165 rows, absent from `READER_FAMILY`) produced **0** `cross_family_verified` rows. **0 of
  524** rows rest on an inferred family.
- **No machine path reaches level 2 at the candidate layer.** `accepted`/`corrected` are
  writable only by `reviews.submit_review`, which requires a reviewer name and an echoed
  `crop_sha256`.

## 5 · What the review record can and cannot tell us

`[measured]` across all 71 table reviews, **1,671 grid values recorded, 1,671 matched a value
some reader had already produced, 0 novel.** The reviewer *did* discriminate — 8 `corrected`
rows, 2 rejected crops, and on one page chose the source's own typo `U-SHAPPED` over a reader's
tidied `U-SHAPED`.

So the review step is a **genuine adjudicator among machine readings** and **not an independent
transcription**. It can detect that readers disagree and pick correctly; nothing in the record
shows it detecting a value *all* readers got wrong. Since `cross_family_verified` is by
definition the agreement case, **the review record contains no evidence about the failure mode
level-1 publication would expose.** All 71 reviews are also by one reviewer.

Any future level-1 proposal should first obtain a real machine error rate from a blind
transcription by a second reviewer who has not seen any reading.

## 6 · What replaces the item — 177 reviewed parts rows that publish nothing

`[measured]` the same crops carry **531 human-`accepted` BOM readings — 177 distinct parts-list
rows across 5 documents** — every one signed off by a person at level 2, publishing nothing.
They are not parameters; they are `Part` records:

```
.875 X 3 X 71.5 PICKET               P.V.C.
2 X 4 X 95.5 ROUTED RAIL             P.V.C.
5 X 5 X 107 ROUTED POST              P.V.C.
HOURGLASS G-60 STEEL CHANNEL X 92    GALVANIZED STEEL
.5 INCH BULLET CLIP                  NYLON
```

Meanwhile **42 `Part`s publish today, every one from a hand-written Python module**
(`augusta_drawing_claims.py`, `pembroke_cadpage_claims.py`, `emblem_claims.py` — roughly
300-550 lines per product family). So the pattern is: reviewed parts data sits unused in the
store while parts are published by hand transcription.

**The gap is not a gate. It is a missing builder** from reviewed BOM cells to `Part`s.

**Two cautions before anyone takes this on.** The structural parameter backlog is already
empty — 110 distinct accepted cells in `VALUE_COLUMNS` against 108 promoted facts, so there is
no parameter coverage waiting behind review. And all five documents holding these parts lists
are **Miami-Dade NOAs**, which the owner has deprioritised; the win is real but it sits in the
deprioritised half of the corpus. That is the owner's call, not this document's.

## 7 · One registry entry to correct

`docs/integration/registry-additions.md` §4 specifies `CURATION_MACHINE_CONSENSUS` against
*"168 cells, 504 readings, 3 readers, 10 crops"*, naming families `claude-sonnet` +
`openai-codex`. Today it is **524 readings over 24 crops in 5 documents, `chatgpt-web-1` on
every one, `codex-C` on none**. The shape is unchanged and correct — code, then `readers`
(int), `families` (list), `crop_sha256`, riding on `Provenance` beside `curation_level`. Only
its evidence line is stale, and publishing it unchanged would ship a false statement.
