# `review_status` — one column name over four vocabularies, and what to do about it

```text
Status:   PLAN, 2026-09-09. Nothing here is implemented. It needs the project
          owner's decision before anything runs, because every option except the
          recommended one writes to a table holding rows that do not regenerate.
Defect:   `docs/naming.md` §5, E-3 — *"`review_status` is one column name over
          four disjoint vocabularies … so a value from the wrong table silently
          scores a curation level."* naming.md calls it "the one worth a
          migration."
Measured: 2026-09-09, against `workspace/indexes/evidence.db` at
          `schema_version = 8`, read-only.
```

## 0. The headline, and it changes the recommendation

**The defect is real as a naming and typing defect. It is NOT currently
producing a wrong curation level.**

`[measured]` all 200 facts that `parameters.CURATION_LEVEL` scores at level 2
have a real human record behind them — 108 promoted from a person-accepted
table reading, 92 with a row in `fact_reviews`, and none with neither. All eight
`CURATION_LEVEL` call sites read `facts.review_status` and nothing else; no
candidate row, no step row, no `verdict` and no `status_before` ever reaches it.

naming.md's *"a value from the wrong table silently scores a curation level"* is
therefore **stronger than the evidence**. Recorded here rather than left
standing, for the same reason G70 bounds CLAUDE.md's "always reliable" claim
about `unit_original`.

What is measurably true is narrower, and still worth acting on:

1. **`facts.review_status` really does hold two vocabularies.** `[measured]` 108
   rows carry `accepted`, which is the `table_read_candidates` vocabulary;
   `store.py`'s own DDL comment for that column enumerates only
   `extracted | flagged | reviewed | rejected`. Two promotion paths disagree:
   `table_review.promote` writes the literal `"reviewed"`, and
   `promote_tables.promote_verified` writes `cell["review_status"]` — the
   candidate's own value.
2. **Two guards are written in the facts vocabulary and so do not cover those
   108 rows.** `reviews.reviewed_without_a_reviewer`, the standing obligation-6
   query, filters `review_status = 'reviewed'`; a fact at `accepted` with a null
   `from_candidate_id` would be invisible to it. And
   `facts.query_facts(include_flagged=False)` narrows to
   `('extracted','reviewed')`, which **excludes all 108 of the store's
   highest-curation facts** from a filter whose purpose is to exclude the
   weakest. `[measured]` 0 orphaned `accepted` rows exist and no caller passes
   `include_flagged=False`, so both are latent, not live.
3. **`CURATION_LEVEL`'s `cross_family_verified: 1` entry is dead in the
   direction it is applied.** It describes the candidates vocabulary; the dict
   is applied only to `facts.review_status`, where no writer can produce that
   value. Its practical effect is to make a future regression *softer* rather
   than refusing it: if `PROMOTABLE` ever regained `cross_family_verified` —
   which it once had, and 324 facts published at a level no person conferred
   (G17, build-plan A1) — those facts would score level 1 instead of being
   refused. **A map that scores an out-of-vocabulary value instead of raising is
   the shape that let A1 happen.**

So this is a guard-and-vocabulary migration, not a value-correction migration.

---

## 1. The measurement

`[measured]` Six tables carry a review-verdict column; three name it
`review_status`, three name it `verdict`, two also carry `status_before`.
`[measured]` **no CHECK constraint exists on any of the eight columns** — the
vocabularies are enforced only by Python constants.

| value | `facts`<br>`.review_status` | `table_read_candidates`<br>`.review_status` | `step_candidates`<br>`.review_status` | `fact_reviews`<br>`.verdict` | `fact_reviews`<br>`.status_before` | `table_reviews`<br>`.verdict` |
|---|---|---|---|---|---|---|
| `accepted` | **108** | **1194** | — | 184 | — | 69 |
| `corrected` | — | 8 | — | — | — | — |
| `cross_family_verified` | — | 524 | — | — | — | — |
| `extracted` | 1492 | — | — | — | — | — |
| `flagged` | 180 | — | — | — | 102 | — |
| `rejected` | 10 | 16 | — | 20 | 10 | 2 |
| `reviewed` | 92 | — | — | — | 92 | — |
| `unreviewed` | — | 185 | 91 | — | — | — |
| **total rows** | **1882** | **1927** | **91** | **204** | 204 | **71** |

`step_reviews` is empty — 91 step candidates, 0 reviews, which is the
`Procedure` gap `CLAUDE.md` opens with.

**The asymmetry that is the whole defect in miniature:** the fact loop
*flattens* a correction (`FACT_STATUS_FOR_VERDICT` maps both `accepted` and
`corrected` to `reviewed`); the step loop *preserves* it
(`STEP_STATUS_FOR_VERDICT` is the identity). Same column name, opposite rule,
neither stated at the point of use.

**Legal sets, from the writers rather than the DDL comments:**

| column | legal |
|---|---|
| `facts.review_status` | `extracted`, `flagged`, `reviewed`, `rejected` — **plus** `accepted`, `corrected` in practice, via `promote_tables` |
| `table_read_candidates.review_status` | `unreviewed`, `agent_verified`, `cross_family_verified`, `accepted`, `corrected`, `rejected`, `bracket_unclear` |
| `step_candidates.review_status` | `unreviewed`, `accepted`, `corrected`, `rejected` |
| `fact_reviews.verdict` | `accepted`, `corrected`, `rejected` |
| `table_reviews.verdict` | `accepted`, `rejected`, `bracket_unclear` — the only one admitting `bracket_unclear` and the only one **excluding** `corrected`, because a correction there lives in the `grid` |
| `step_reviews.verdict` | `accepted`, `corrected`, `rejected` |
| `*_reviews.status_before` | another table's vocabulary **by design** (G47: it is what makes a rejection reversible) |

`[measured]` `READ_STATUSES` omits `bracket_unclear` while `REVIEW_STATUSES`
admits it — a small pre-existing inconsistency worth folding into whatever
lands.

---

## 2. Blast radius

**`CURATION_LEVEL`** — eight call sites (`parameters.py`, `parts.py`, and six in
the four `*_claims.py` modules), every one reading `facts.review_status`.
`[measured]` the cross-vocabulary value does reach it, 108 times a build, and
level 2 is the **correct** answer for those rows because
`table_review.PROMOTABLE` and `promote_tables`' gate both hold.

**`PROMOTABLE` / `PUBLISHABLE`** — both are the literal `("accepted",
"corrected")`, defined twice, and `naming.md` §5 already records that they are
*deliberately* separate. `procedures.py:130` is the sharpest illustration:
`r["review_status"] in PUBLISHABLE and r["verdict"] in PUBLISHABLE` — two
different tables' columns tested against one tuple, correct only because a LEFT
JOIN leaves `verdict` null.

**SQL** — `[measured]` 271 occurrences of the token across `fence_evidence/`,
`scripts/` and `tests/`. Roughly 90 production sites read or write a
`review_status` **column**; a further ~20 mint `"review_status"` as a **Python
dict key**, which no column rename would reach.

**`workspace/catalog/review-ledger.jsonl`** — `[measured]` 276 lines (204 fact
reviews, 71 table reviews, 0 step reviews). It carries **no field named
`review_status`**; its fields are `verdict` and `status_before`. So a column
rename does not touch it. **A change to the VALUE SPACE does**: `status_before`
holds `facts.review_status` values (`flagged` 102, `reviewed` 92, `rejected` 10)
and `rebuild_fact_projection` replays them straight back. Re-spelling any facts
value means rewriting 204 records of what a person decided.

---

## 3. Options

| | changes | cost | catches | misses | touches what does not regenerate |
|---|---|---|---|---|---|
| **(a)** do nothing; add a per-table legal-set guard | one test file | ~1h | that `facts` holds `accepted`; a future `cross_family_verified` leak | a wrong-table read where the value is legal in both spaces; the two `WHERE`-clause gaps | nothing |
| **(b)** rename the column per table | 3 `ALTER … RENAME COLUMN`, 2 indexes, ~150 sites | ~1 day | every wrong-table **column** read, at import time | the ~20 Python-minted dict keys; `status_before` misuse | **DDL on `table_read_candidates`' 1,927 readings, which are NOT in the ledger** |
| **(c)** per-table `frozenset`s; `CURATION_LEVEL` becomes a function that **raises** on an out-of-vocabulary value | one constants block, 10 call sites | ~½ day | the A1 shape in one line; the `promote_tables` cross-write on the first build | the both-legal case | nothing — no DDL, no UPDATE |
| **(d)** split the value spaces so no string is legal in two tables | UPDATE 4,175 rows **and rewrite 204 ledger lines** | days | everything | little | **rewrites the review ledger** |

### Recommended: (c), with (a) folded in as its test, plus one targeted value fix

1. `[measured]` the defect produces no wrong curation level today. An expensive
   migration for a latent defect is the overstatement this repository keeps
   catching — the `unit_normalized` "fix" of 2026-09-03 is the worked example.
2. (c) is the only option that touches nothing which does not regenerate.
3. (c) closes the actual A1-shaped hole: `CURATION_LEVEL.get(status, 0)`
   silently scoring an unknown value is the same failure mode as `PROMOTABLE`
   silently containing `cross_family_verified`. Making it raise is one line, and
   it is the line that matters.
4. (b) buys SQL-level unrepresentability and pays with DDL on the only review
   artifact not in the ledger — and it is half a fix anyway, because a column
   rename does not reach a minted dict key. Keep it as a follow-on after (c) has
   named the vocabularies, and rehearse it on `step_candidates` first: 91 rows,
   0 reviews, the cheapest possible dry run.
5. (d) is disqualified by the ledger rewrite, for a defect that is measurably
   not producing a wrong answer.

**The one value fix**, and it is the source of the confusion: have
`promote_tables.promote_verified` write `"reviewed"`, matching
`table_review.promote` and `reviews.FACT_STATUS_FOR_VERDICT`, and backfill the
108 rows. The candidate's own verdict is not lost — it is already on
`facts.extractor` as `table-read:accepted` and on the candidate the fact points
down at. This makes `facts.review_status` speak one vocabulary and closes both
guard gaps without touching either `WHERE` clause.

`[inferred]` it publishes identically (`CURATION_LEVEL['accepted'] ==
CURATION_LEVEL['reviewed'] == 2`; `versions.REVIEWED_FACT_STATUSES` holds both;
`parameters.FACT_QUERY`'s `<> 'rejected'` admits both) — **and that must be
verified by rebuilding a snapshot before and after and comparing bytes, not
assumed. If the bytes differ, the change is bigger than this plan says and
should stop.**

---

## 4. Migration sketch, if (c) is chosen

Order, and every step is load-bearing:

1. `cli review --export` and diff it. The ledger is the rollback. `[measured]`
   it is current today (header 204/71/0 against the store's 204/71/0).
2. `snapshot --build`; record the id and hash. This is step 6's baseline.
3. **Code-only changes land first** — the frozensets, `curation_level()` as a
   function, the widened guards. They are inert: the function raises only on a
   value that cannot currently occur.
4. Then the value backfill, in one transaction, as a new step in
   `store.migrate()` beside `rename_fact_types` and `backfill_condition_keys` —
   which are the same shape and already live there. **Add it to `migrate()`'s
   step list in the docstring, or that docstring becomes a lie.**
5. `cli refs --verify` — `[measured]` 25,961 citations must still resolve.
   `review_status` does not enter `ref_id`, so this should be a no-op; run it
   because "should" is not a measurement.
6. Rebuild a snapshot and compare bytes to step 2. **Identical bytes is the
   acceptance criterion.**
7. `cli snapshot --verify-stored` last.

```python
def unify_fact_review_vocabulary(conn) -> dict:
    """Re-spell the promoted facts into the `facts` vocabulary (naming.md E-3).

    `promote_tables.promote_verified` copied the CANDIDATE's status into
    `facts.review_status`, so one column carried two vocabularies. The
    candidate's own verdict is not lost: it stays on `facts.extractor` as
    `table-read:<verdict>` and on the candidate this fact points down at.

    Idempotent: the WHERE clause is empty on the second run.
    """
    orphans = [r["fact_id"] for r in conn.execute(
        """SELECT fact_id FROM facts
            WHERE review_status IN ('accepted','corrected')
              AND from_candidate_id IS NULL""")]
    if orphans:
        # Refuse rather than launder. A fact at `accepted` with no candidate
        # behind it is the level-2-with-nobody-behind-it case (G17/A1), and
        # re-spelling it to `reviewed` would hide it. `retire_columns` refuses
        # to drop a column still holding data for the same reason.
        raise ValueError(
            f"{len(orphans)} facts carry a candidate-vocabulary status with no "
            f"candidate behind them: {orphans[:10]}. These are obligation-6 "
            f"violations, not spelling. Resolve them before migrating.")
    moved = conn.execute(
        """UPDATE facts SET review_status = 'reviewed'
            WHERE review_status IN ('accepted','corrected')
              AND from_candidate_id IS NOT NULL""").rowcount
    return {"facts_respelled": moved}
```

`[measured]` the orphan check passes today: 108 `accepted`, all with
`from_candidate_id NOT NULL`; 0 `corrected`.

**Re-entrancy hazard, and it is the one that would undo the work:**
`promote_tables.promote_verified` re-introduces `accepted` on its next run
unless its write is changed in the SAME commit. A backfill without the code
change is undone by the next `promote-tables --apply`.

**Rollback**, three layers: revert the commit and re-derive from
`facts.extractor` (`[measured]` all 108 rows carry the `table-read:` prefix);
or re-derive from the candidate through `from_candidate_id`; or a full
re-extract plus `cli review --import --apply`, the path already proven on
2026-08-30 (G49). Published snapshots are unaffected in every case — they are
write-once files and carry `curation_level: 2` either way.

**`migrate()` cannot carry option (b).** There is no `rename_columns`
counterpart to `ensure_columns`/`retire_columns`, and adding one would mean
declaring that the old name is gone from every SQL string in the tree — which a
migration function cannot check. (b) needs a one-shot script plus a grep-based
test.

---

## 5. The test that would have caught it

Specified, not added — it fails today, and `tests/test_naming.py`'s own preamble
says a guard added red is a guard somebody disables. It lands with the fix.

The shape: a `VOCABULARIES` mapping of `(table, column) -> frozenset`, covering
all eight columns including the two `status_before`s (whose whole job is to hold
*another* table's vocabulary — legal, and the only place it is legal, so it is
pinned rather than left to be rediscovered), and three methods:

- `test_no_column_holds_a_value_from_another_tables_vocabulary` — `[measured]`
  fails today with exactly one offender, `facts.review_status='accepted'` (108
  rows). That is the defect reduced to one line of output.
- `test_the_curation_map_only_scores_the_vocabulary_it_is_applied_to` — the
  `cross_family_verified: 1` entry, which describes a vocabulary the map is
  never handed.
- `test_a_status_outside_the_vocabulary_is_refused_not_scored_zero` — the
  specification of what (c) must provide. `.get(status, 0)` answers 0 for a
  value it has never heard of, which is indistinguishable from `extracted`.

---

## 6. What is being asked

A decision on (c) versus (b) versus doing nothing, and specifically on the one
value fix — 108 rows of `facts.review_status`, in a table whose review
*annotations* regenerate but whose 1,927 sibling readings in
`table_read_candidates` do not. Nothing in the recommended path writes to a
`*_reviews` row or to `review-ledger.jsonl`, and that is deliberate.
