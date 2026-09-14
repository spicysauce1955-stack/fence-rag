# Coverage remediation — a measured inventory, not a wish list

```text
Status:   Rewritten 2026-09-14 after four of its own items were attempted. Three of
          the four dissolved on contact: the prescriptions were written from reading,
          not from measuring. What follows is the measured inventory that replaces
          them. [DONE] is merged; [MEASURED] means taken against the store.
Authority: Advisory on sequencing only. `docs/knowledge-loop.md` governs purpose,
          `docs/integration/contract.md` (FROZEN v1.3) the boundary,
          `docs/mvp-implementation-spec.md` how this platform works. Where this and
          `docs/state-and-gaps.md` disagree about a number, that one wins.
Read with: `docs/keyword-ruler-audit.md` (what the instrument change overturned) and
          `docs/level-1-publication-finding.md` (why item 5 was cancelled).
```

---

## 0 · The lesson this document exists to carry

Four items were attempted. **Three were wrong about what the defect was**, while being roughly
right about where it lived:

| item | the plan said | measured |
|---|---|---|
| 2 · second stage | loosen the IDF floor to 0.75 | 0.75 was tuned on the instrument item 1 retires; support **plateaus at 0.40**, and the stated justification was falsified — 0 of 152 marginal attachments carried the terms it named |
| 5 · publish 524 rows | biggest coverage win needing no curator; obligation 6 requires it | **one** reader, **524 of 524** already human-accepted, columns no parameter builder matches → **zero rows**. Obligation 6 does not require it |
| 3 · publication gates | 9 unreviewed Part dimensions; gate `parts.py` like `parameters.py` | **all 54** published `SpecField`s are level 0; only **2 of 54** flow through `parts.py`; `parameters.py`'s real gate is provenance, not review status |

**The rule this buys: measure an item before scheduling it, and price the measurement into the
item.** Each took under an hour to falsify and would have taken a day to build wrong. The
review's diagnosis was sound; its prescriptions were not evidence.

## 1 · Done and merged

| | |
|---|---|
| **Honest ruler** | `evaluate` grades the natural question. All 79 gold questions carried hand-written `query_terms` production never sends. The keyword column is retired, not repaired — it cannot be made trustworthy, because whoever writes search terms already knows the answer |
| **Second stage** | on by default, floor **0.40**. `[MEASURED]` support 0.6219 → 0.6528 on the graded column, 5 questions up, 0 down. **Not a pass** — 0.047 short, recorded as an improvement |
| **Four decisions re-checked** | R3 stands (structurally — and an unfair criticism of it withdrawn), R5 stands (its recorded figure does not reproduce), R1 moot, second stage reversed |
| **Gold set repaired** | `gq-004`/`gq-019` redirected to the NOA actually in force → **recall@10 0.7561 → 0.8049, A3 passes**; two dead pages dropped; all 37 negatives classified |
| **Support scoped** | `evidence_support` and `page_support` no longer credit documents that are not the answer. `[MEASURED]` 0.6528 → **0.5271**, passing 28 → 25 |
| **Source class resolved** | no longer depends on which filing a citation reached first. `[MEASURED]` marketing 13 → 11, industry_standard 1 → 2; three byte-identical groups rescued, all approvals |

**The instrument is now trustworthy. It was not before, and nothing measured before 2026-09-14
should be quoted without checking `docs/keyword-ruler-audit.md`.**

## 2 · The measured inventory — what could actually publish

The section the first draft lacked. Every row is a count against the store.

| population | size | curator? | HVHZ? | state |
|---|---|---|---|---|
| **Figures whose dimensions are already extracted** | ~2,500 useful, ~830 dimensioned | **no** | **no** | unlinked — geometry, not reading |
| Reviewed BOM parts-list rows | **177** rows, 531 readings, 5 docs | no | **yes** | publish nothing; no builder exists |
| Instruction step segments | **9,188** across 112 documents | **yes, after** | no | 91 stored, **0 reviewed** |
| Scanned drawings | 221 + 6 CAD PNGs | yes | mostly | OCR ~ 0 signal; crop+VLM is the tool |
| **Structural parameters awaiting promotion** | **0** | — | — | **empty: 110 accepted cells, 108 promoted facts** |

That last row reorders everything. **There is no parameter coverage sitting behind a review
gate.** The first draft assumed there was.

## 3 · What to do, in order

### Next — item 6 · link dimensions to the diagrams they annotate

**The only coverage win that is real, free, needs no curator, and sits outside the
deprioritised half of the corpus. It should have been first.**

`[MEASURED]` all 6,660 `figure` elements carry empty `text` **and** empty `ocr_text`, produce 0
retrieval units, and are reachable by no query. But they are born-digital vector art and the
dimensions beside them are **already extracted correctly** — `33in.`, `70 3/8in.`, `72in.`,
fractions intact. Nothing was lost in reading them; only the association is missing.

**Design impact: one new additive table.** `relations` cannot hold it — it is
`UNIQUE(from_document_id, to_document_id, relation_type)`, so every intra-document annotation
would collapse to one row.

```sql
CREATE TABLE IF NOT EXISTS element_relations (
    element_relation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_element_id TEXT NOT NULL REFERENCES elements(element_id),
    to_element_id   TEXT NOT NULL REFERENCES elements(element_id),
    relation_type   TEXT NOT NULL,   -- annotates
    document_id     TEXT NOT NULL REFERENCES documents(document_id),
    version_id      TEXT NOT NULL REFERENCES document_versions(version_id),
    page_no         INTEGER NOT NULL,
    basis           TEXT NOT NULL,   -- leader_line | inside_bbox | proximity
    confidence      REAL,
    created_at      TEXT NOT NULL,
    UNIQUE(from_element_id, to_element_id, relation_type)
);
```

Direction: `from` = the dimension text, `to` = the figure. Both are L2, so the layering rule
does not bind; `tests/test_pointer_direction.py` inspects only `facts` and
`table_read_candidates` and passes. **`delete_version_rows()` must learn to clear it**, or a
re-ingest leaves dangling rows.

**Honest caveat, measured:** not an inside-the-box rule. On WamBam page 2, `70 3/8in.` at
`[442, 375, 472, 387]` and `72in.` at `[444, 393, 461, 405]` sit **outside every detected
figure bbox** — the detector carved the illustration sub-regions while the dimensions live in
the step panel beside them. Proximity plus leader-line geometry; `basis` records which, per row.

**Acceptance.** Figures become reachable by query; a sampled set of links checked by eye; a
`leader_line` link degrades honestly when `pdfplumber` is absent.

### Then — item 4 · page-level step review

Still the largest population (9,188). No schema change: `step_reviews` is already anchored per
span, so the sheet is an input format only and ledger replay is untouched. **Must not batch**
the verdict tick, `step_kind`, `step_scope`, `slot_target` or `text_final` — G69 measured 5 of
54 `segment_kind='step'` rows are not steps.

**Widen the input too.** `steps.propose()` reads only `element_type='list'`, and the WamBam
page — a complete 13-step illustrated procedure — holds 14 figures, 33 headings, 35 paragraphs
and **0 list elements**. `pair_numbered_flow()` is the seam for those pages and has never been
run on the corpus.

**This item hands over a queue, not output.** An agent may act as a machine *reader*; it may
not be the human sign-off.

### Then — item 7 · read the scanned drawings

Deprioritised by the owner (HVHZ). `[MEASURED]` 23 of 221 drawings (10%) and 340 of 7,219
lists (4.7%) are HVHZ, so deprioritising costs little. No contract change — `visual_reading`
already admits a machine reader by name. No table rebuild: 221 drawings sit on 221 distinct
pages. ~$19.

### Blocked — item 8 · one identity per product

`[MEASURED]` 117 distinct `(manufacturer, product_family)` strings across 146 documents. But
`reach.py` shows Planning matches by plain equality against its own ids and **no `mfr/*` id has
ever appeared in a run** — minting good ids before the join is agreed publishes into a void.
File `EntityRef.id` stability first (**012/013 — 009 is already taken**).

## 4 · Cancelled

**Item 5 — publish the 524 machine-consensus readings.** Cancelled on measurement; see
`docs/level-1-publication-finding.md`. One reader, 524/524 already human-accepted, BOM columns
no parameter builder matches. The obvious implementation would have recreated the defect CUR-S0
closed: `table_review.promote()` hardcodes `review_status="reviewed"` (level 2) with a note
reading *"reviewed by ... unknown"*, and `PROMOTABLE` is the only guard.

**Item 3 defects A and C** — reframed, not scheduled. See §5.

## 5 · Decisions that are the owner's, not an engineer's

1. **The A4 target.** `no_answer_precision` and `false_unsupported_rate` are **the same rule**
   pulling opposite ways. `[MEASURED]` 18 of 37 negatives fire, and 18/37 = 0.486 exactly — the
   metric is "fraction of negatives containing a df-0 token". **7 of the 18 fire on a
   morphological artifact** (`carry` df 0 while `carrying` is 6); true semantic precision is
   **0.297**. Fixing the tokenizer moves A4b toward 0.20 and A4 away from 0.66, to ~0.35. Only
   11 negatives carry a genuinely absent term. **Either A4 is renegotiated against the corrected
   class mix, or the detector needs a signal that is not term presence.**
2. **54 of 54 published `SpecField`s are curation_level 0.** No published `Part` dimension has
   ever been signed by a person. Gating would empty the payload; reviewing them is a curation
   campaign. Publishing at level 0 is defensible *if chosen* — and §1.4 gives
   component-dimension tasks **no `min_curation` floor**, so this is the class with no gate.
3. **Four gold questions** turn on one judgement: is "the current **CertainTeed** NOA" the last
   CertainTeed-branded one, or the Barrette approval that superseded it? (`gq-009`, `gq-122`,
   `gq-015`'s "two live NOAs" premise, `gq-228`.)
4. **Crop `c97fe2d5`** carries three conflicting reviews — a whole footing grid recorded in feet
   where the page printed inches, accepted by two of three passes. Reconciling it edits human
   judgements, the one artifact here that does not regenerate.
5. **Two NOAs still publish as `marketing`**, single-filed as `unspecified`. The fix is in
   `data/*.json` and re-running `build_master.py` is unsafe today (G71).

## 6 · Still true, and still the point

`[MEASURED]` 7 of 146 documents publish any fact · 0 procedures · 0 rules · 0 values from any
figure or drawing · 0 of ~120 hand-researched engineering claims in `data/structural/`.

Five refusal gates sit in series, each individually correct, and **not one has a budget for how
much it may hold back.** Nothing here can fail a check for publishing too little. That is the
finding the whole review rests on, and nothing measured since has weakened it — every
correction above is about *which* lever to pull, never about whether the wall is there.
