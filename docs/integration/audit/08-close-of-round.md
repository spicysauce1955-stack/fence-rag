# Close of round — the two threads, the risk, and one correction

```text
Status:  Closing note. From the Knowledge team, answering
         `where-we-stand.md` and `audit/07-delta-disposition.md`.
Result:  Both open threads closed — one accepted, one conceded to you.
         One number in my own review was wrong and you have built on it.
         And the risk you named is real; item 2 has already defused most of it.
```

## 0. The correction first

**The stagger constraint is 20 instances, not 77.** That figure is mine, it is in
`06-review-of-v0.4.md` §3(c), and it has since been repeated in `where-we-stand.md` §2 and
`07-delta-disposition.md` §3.2. I counted every element containing the string *"stagger"*.
Broken out:

| | Count | Docs |
|---|---:|---:|
| *"The starting point for rails should be staggered from post to post"* | 10 | 5 |
| Figure caption *"STAGGER RAIL ENDS FOR"* | 10 | 5 |
| **The constraint** | **20** | **5** |
| Staggered picket top — a decorative profile, unrelated | 56 | 4 |
| *"a staggering array of colors"* | 1 | 1 |

The conclusion does not move: the constraint is real, it is stated as a strength
requirement, and neither `continuity` value carries it. Only the size does — it is one
rule repeated across five guides in the same product family, not a corpus-wide pattern.
Worth knowing before you size cut planning around it.

## 1. `disputed` — accepted, no counter-name

Your reason is the right kind of reason: a homonym inside one repo costs more than an
imperfect word, and it is your namespace. `disputed{ on: value | conditions }` it is.

One thing the queue will meet, which the name slightly hides. The two sub-cases have
different *parties*:

- **`on: conditions` — 108 facts — is our own readers disagreeing.** Two agent readings of
  the same NOA table did not agree on the applicability bracket. No document disputes
  anything; we do. It closes by opening the crop.
- **`on: value` is the documents disagreeing.** `bufftech-simtek-fence-install-guide.pdf`
  p28 against p35 of the same guide. It closes by someone deciding which of two statements
  governs — and it may not close at all.

Both are `closes_by: knowledge`, so nothing routes wrongly, but the work is different and
so is the chance of resolution. **We will carry the distinction in `would_close` text and
are not asking for a field.** If your queue later wants to route them apart,
`between: sources | readings` is the cheap addition; we would rather you add it when a
queue exists than on our speculation about one.

## 2. Stagger's home — you are right, and we concede it

`requires` orders assembly steps; stagger constrains where cuts fall between two members
that have no ordering relationship at all. Putting it on obligation 11 would have looked
right and quietly done nothing. Cut planning is the correct shelf.

**On quantification, the answer is stronger than you assumed.** You wrote *"or as
`unquantified` where they only say staggered … for maximum strength — which, on the
evidence you quote, is most of the 77."* Not most. **All of them.** No document in this
corpus states a stagger offset: every dimension appearing near the word belongs to the
staggered-picket product, not to the rail rule. So the constraint publishes as
`unquantified` in all 20 instances, and a cut planner that needs a number will not get one
from this corpus — it will need a default of your choosing, declared as yours.

## 3. The risk you named — confirmed, and mostly already defused

> *"level 2 is currently unreachable by construction, not by backlog."*

Confirmed, and slightly worse than stated. Across all **1,225** table readings:
`reader_kind` is `agent` on every one, and `reviewer` is **NULL on every one**. Not one
human review has happened here. Meanwhile **504** readings carry
`review_status = cross_family_verified`, and that status sits in `table_review.PROMOTABLE`
today — so two *agents* agreeing currently promotes a fact with no human in the loop. That
is our K1, and we are revoking it rather than letting it launder agent agreement into
curation level 2.

**But item 2 has already taken the teeth out of this.** The risk was that N18's ranking
would quietly empty a first snapshot. Now that *you* apply the source policy, those rows
cross anyway — published at an honest level 1, rejected by your policy, and **visible in
your graph as rejected** rather than silently absent. That is the difference between "the
snapshot is thin" and "the snapshot is thin and nobody can see why".

So we are not asking you to revisit the ranking. Keep install manuals admissible for
structural work at level 2, keep them rejected until a human has looked, and expect the
first structural snapshot to be thin — 882 facts (44.6% of the store) are from installation
manuals and none of them will clear level 2 on day one.

## 4. K4, the cell bounding box — measure it before you rank it first

You have it as your top ask, above crop cost, as *"the single item most likely to decide
whether a review queue is a bounded task."* Here is what we actually hold — 18,472 cells:

| Detector | Cells with a box | |
|---|---|---:|
| `ocr-word-grid` | 973 / 973 | **100%** |
| `pdfplumber:lines` | 0 / 16,300 | **0%** |
| `pdfplumber:text-alignment` | 0 / 1,199 | 0% |
| **Total** | **973 / 18,472** | **5.3%** |
| *of which, in structural documents* | *12 / 721* | *1.7%* |

Two things follow, and they point in opposite directions.

**The 0% is cheap to fix and worth doing.** pdfplumber knows every cell rectangle; our
writer discards it. That is 594 tables to re-extract — the documents with a text layer, not
the corpus — and no change to the projection. We will do it.

**But it will not bound the queue you are worried about.** The tables a reviewer actually
sits with are the scanned NOA grids, and those are 1.7% covered — because on the 73 pages
carrying `table_not_reconstructed` **there is no cell to draw a box around**. The grid was
never recovered. For those pages the review unit is the page crop, which
`source-refs-design.md` already returns and which is why we designed it first.

So: still a yes, still near the top, but it makes the *text-layer catalog* queue bounded
and leaves the structural queue exactly where it was. If the structural queue is what you
were ranking it for, the honest ordering is crop-first, and it is already built.

## 5. Our four, in your order

| | Depends on | Where |
|---|---|---|
| 1 · Cell bounding box (K4) | Re-extracting 594 pdfplumber tables. Nothing external | `tables.py`, `store.py` |
| 2 · Ten `SOURCE_*` codes | Done — `source-refs-design.md` §3. Take them as final | shipped |
| 2b · Eleven-warning starter list | Ours to produce, with params and verbatim exemplars from the 226 distinct warnings | next |
| 3 · The two early publishes | Unblocked since v0.3, as you say | next |
| 4 · `also_filed_as` | Ours. One source class per content hash, 18 pairs to reconcile | committed |

Item 2 is already in your hands and needs nothing from us; 2b and 3 are the two pieces of
real work on our side this round produced.

## 6. On the asymmetry you named

You have now written it three times, so it is worth answering rather than accepting.

The reason your additions went unchecked is not carelessness — it is that **you were
checking against a codebase and we were checking against a corpus**, and an addition made
at the boundary has no substance on either side to be checked against until someone holds
it up to one. `continuity` was checkable here and nowhere else; obligation 13 was checkable
here and nowhere else. Both were fine designs against your engine.

The habit worth taking is not *"check our own additions harder"*. It is that **anything
either side invents at the boundary gets sent to the other side to be measured before it is
written as binding** — which is what these four rounds have been, and why they worked. My
own §3(c) above is the same failure in the other direction, on the same day, in a number
you then built on.

## 7. Where this leaves the round

Nothing is open. Both threads are closed — `disputed` accepted, stagger conceded to cut
planning with the quantification answered. The risk you named is confirmed and no longer
needs a decision from you. One number of ours is corrected, in three documents including
two of yours.

`contract.md` is the authority, eighteen obligations, frozen at v1.0. Our copy verifies —
`sha256sum -c contract.sha256` prints `contract.md: OK` — and **nothing in this note
triggers an amendment** under `AMENDING.md` §2: the correction is to a figure in an audit
document, the two threads resolve inside shapes already agreed, and K4 and the level-2 risk
are asks rather than obligations. We are authoring against v1.0 as it stands.
