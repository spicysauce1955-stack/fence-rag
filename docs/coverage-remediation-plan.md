# Coverage remediation plan — nine items on three tracks

```text
Status:   A PLAN, not a change. Nothing here is implemented. Written 2026-09-14 from an
          adversarial review run by fourteen agents against the store at 250b27e, with
          every load-bearing claim re-verified by hand before it was written down.
Authority: Advisory on sequencing only. `docs/knowledge-loop.md` governs purpose,
          `docs/integration/contract.md` (FROZEN v1.3) governs the boundary, and
          `docs/mvp-implementation-spec.md` governs how this platform works. Where this
          document and `docs/state-and-gaps.md` disagree about a number, that one wins.
Read first: `docs/knowledge-loop.md` §9 (the largest gap), then §10 (build order, which
          this document refines rather than replaces).
Shape:    One item per session, each with its own acceptance test, per knowledge-loop §10.
          Items are grouped by WHO CAN DO THEM, not by size -- see §0b. knowledge-loop §10
          already draws this line ("needs a curator, not an engineer; if no person is
          available, start at item 2") and this plan is ordered to respect it.
```

---

## 0 · The finding this plan exists to act on

`[measured]` 2026-09-14 against `workspace/indexes/evidence.db` (built 2026-09-09 16:40) and
the latest snapshot `0e04d171`. **Provenance caveat:** the store predates branch HEAD
`250b27e` (16:47) by seven minutes, and that commit added 161 lines to `facts.py` and touched
`parameters.py`, `parts.py` and `snapshot.py`. `extract.py` and `layout.py` were **not**
touched, so every element- and document-level count below is unaffected; the fact-type and
published-object counts could shift on a rebuild. Re-measure those before citing them in a
decision. 31 snapshot files are stored, of which 25 carry a payload and 6 are tombstoned.

| | |
|---|---|
| documents ingested | 146 |
| documents with any promoted table fact | **7** |
| documents with any step candidate | **2** |
| step reviews, ever | **0** |
| published knowledge units | **85** — 31 `ParameterRow`s + 54 `SpecField`s, in snapshot `0e04d171` |
| `figure` elements with any text or OCR | **0 of 6,660** |
| published values traceable to a figure or drawing | **0** |
| values published from `data/structural/*.json` | **0 of ~120 engineering claims** |

The extraction works. The publishing does not. Re-run read-only, the step splitter yields
**9,188 content-carrying segments across 112 documents**; the store holds 91, from 2
documents, because nobody ran it anywhere else. 1,882 facts across 48 types sit extracted;
108 are published.

**The pattern, stated once.** Five gates sit in series — *is the text readable · did readers
agree · did a person approve · is the product name certain · will anything read it* — and
every one of them is individually correct. Not one has a budget for how much it may hold
back. Nothing in this system can fail a check for publishing too little, so the safe answer
is always to publish nothing, and that answer compounds five times. **This project measures
"never be wrong" with great care and does not measure "be useful" at all.** The remedy is not
weaker gates; it is making coverage a graded number the way correctness already is.

`cli worklist` reached the same conclusion on 2026-08-26 and nothing acted on it:
`workspace/catalog/unresolved-worklist.jsonl` holds 140 items — **machine 129, human 8,
review 3** — under the docstring *"machine — a vision-capable reader can transcribe it. Not a
human task."*

## 0a · What is NOT wrong

Recorded so the next session does not re-litigate it.

- **Retrieval is not the bottleneck.** `[measured]` document recall@50 = 0.902, recall@200 =
  **1.000** on the 78-question gold set. Hybrid dense retrieval, SPLADE, ColBERT and ColPali
  all improve a column that is already full. Prohibition 9 stands; no measured failure
  category justifies a vector store.
- **The crop → VLM → human-review pattern is right** and was arrived at independently. The
  2026 Enginuity benchmark puts OCR-on-engineering-drawings at **Recall@all 0.012** against a
  VLM 72× higher, and 98.7% item accuracy when reading a *cropped* region. Never ask the model
  for coordinates; the crop carries the provenance.
- **No parser swap.** Changing the geometry source moves `ref_id`, which retroactively breaks
  published citations and obligation 3 with them. Not available until extraction editions
  (G38) exist.

---

## 0b · Three tracks, because the blocker differs

An ordering by size sends a session with no curator into a wall. Order by who can act.

| Track | Items | Blocker | Curator needed? |
|---|---|---|---|
| **A — engineer alone** | 0, 1, 2, 3, 5, 6 | nothing; all are code | no |
| **B — engineer, then curator** | 4, 7 | a person must sign off before anything publishes | **yes, after the build** |
| **C — needs the other team** | 8 | Planning must agree the join first | no, but blocked |

**Run track A to exhaustion before starting track B.** Track A items publish coverage without
a person: item 5 alone moves 524 readings from nothing to published, and item 6 makes 6,660
figures reachable for the first time. Track B builds a queue that only a human can clear, so
starting it while track A is unfinished converts an engineering session into a waiting one.

Track C waits regardless. Do not mint identities into a void.

**Recommended running order, one per session:**

```text
0  re-measure            cheap, and everything about published output depends on it
1  the honest ruler      no later measurement means anything until this lands
2  second stage on       five minutes, already built and measured; do it while the
                         ruler is fresh so it is graded honestly the first time
3  publication gates     safety; closes 9 unreviewed published dimensions
5  publish level 1       +524 rows, satisfies a BINDING obligation, no curator
6  link the figures      free; makes 6,660 figures reachable for the first time
------------------------ track A exhausted; a curator is now the constraint
4  page-level review     the leverage change; hands over a queue of ~9,188
7  read the drawings     deprioritised (HVHZ); ~350 items, needs sign-off
------------------------ blocked on Planning
8  one identity          file EntityRef.id stability (012/013) first
```

**Two of these are worth doing even if the plan is otherwise abandoned:** item 1, because
every number this project quotes is currently measured on a query shape production never
sends; and item 3's `source_class` default, because sealed engineering drawings are publishing
as `marketing` today.

## 0c · Item 0 — re-measure before planning against published numbers

**Not optional, and it is cheap.** The store was built 2026-09-09 16:40; branch HEAD landed at
16:47 having added 161 lines to `facts.py` and touched `parameters.py`, `parts.py` and
`snapshot.py` — including the naming work that renamed 13 `*_drawing_*_mm` fact types to
`_in` (B-1). Every element- and document-level number in §0 is unaffected, because
`extract.py` and `layout.py` were not touched. **The fact-type and published-object counts are
not guaranteed to match what current code produces**, and items 3, 5 and 7 all reason about
published output.

**Do:** rebuild the snapshot with current code and diff it against `0e04d171`; re-run the
evaluation; compare the store's distinct `fact_type` values against what `facts.py` now emits.

**Do NOT re-extract facts as a side effect.** `facts` rows carry `review_status`, and a
re-extraction moves every `fact_id`. The review ledger exists to survive exactly that (G49),
but replaying it is a deliberate operation with its own acceptance test — not something to do
while measuring. If the fact types have drifted, that is a finding to file, not a cleanup to
perform in passing.

**Acceptance.** A recorded diff between the stored snapshot and one built from current code;
either "no change" or a named list of what moved. Nothing written to `facts`.

## 1 · Item 1 — grade the evaluation on the query production actually sends  `[track A]`

**Defect.** `evaluate._query_for()` prefers a question's hand-written `query_terms` over the
question itself, and `[measured]` **all 79 gold questions carry them**. The production path
does not: `query.py` passes `situation.question` unchanged. Every acceptance number in this
repo is therefore measured on annotator-authored keyword strings.

`[measured]` re-running the harness on the natural question:

| criterion | keyword hints | natural question |
|---|---|---|
| document recall@10 | 0.805 **pass** | **0.756 fail** |
| evidence support | 0.650 fail | 0.622 fail |
| no-answer precision | 0.324 fail | 0.486 fail |
| false-unsupported rate | 0.146 **pass** | **0.390 fail** |

Both criteria this platform believes it passes are artifacts of the rewrite. **Every
"measured and rejected" decision in this repository was decided on this instrument**, which is
why this item is first and why no other item's measurement means anything until it lands.

**Do:** report both columns on every run and grade the natural-question column, or make
`query_terms` the documented production contract and say so. Pick one; do not leave it
ambiguous.

**Acceptance.** The evaluation report prints both columns; the graded column is named in the
report; `summary["raw"]` carries unrounded means for both (G65).

**Not in scope.** Making anything pass. The honest numbers are allowed to be worse.

## 2 · Item 2 — switch on the second stage  `[track A]`

**Defect.** `retrieval.search_evidence(second_stage=False)` by default, and
`SECOND_STAGE_MIN_TERM_DF_SHARE = 0.30`. The mechanism is built, tested and off.

`[measured]` second stage on with the floor loosened to ~0.75: evidence support
**0.650 → 0.7062**. The floor was suppressing exactly the headings that carry the missing
terms (`3000 PSI`, `ASCE 7-10`, `EXPOSURE D`), which is also audit finding F1 — 33.9% of
heading text is reachable nowhere else, and the second stage is the remedy that was built for
it. By construction it cannot move document recall, page recall or no-answer precision
(`tests/test_second_stage.py`).

**Honest expectation.** That 0.7062 was measured on the keyword column. The natural-question
baseline is 0.622, so the same lift lands near **0.678** — this item probably does **not**
clear 0.70 on the honest ruler. Ship it because it is a real, significant, invariant-
preserving improvement, not because it turns a criterion green.

**Note the inconsistency it closes.** `docs/second-stage-evaluation.md` rejected this for
missing 0.70 by **0.0054** — one seventh of the metric's own standard error — while R3, whose
paired delta is *not* statistically significant, ships on by default. Two standards were
applied to two changes in opposite directions. Whichever standard is chosen, apply it to both
and record it.

**Acceptance.** Both evaluation columns reported (item 1); recall@10 unchanged; false-
unsupported ≤ 0.20; a human spot-check that newly attached elements are headings and spec
lines rather than footers.

## 3 · Item 3 — close the two publication-gate gaps  `[track A]`

**Defect A.** `parameters.py` gates publication on review status; `parts.py` does not — it
maps `review_status` to a curation level and publishes regardless. `[measured]` nine published
`Part` dimensions (`facts` 22759–22767) are `review_status='flagged'`, `ocr_derived=1`,
`reviewer` NULL, resting on OCR at **25%, 48% and 56%** confidence. They are labelled level 0,
which is honest; a consumer that does not filter on level reads them as ordinary numbers.

**Defect B.** `parameters._source_class()` defaults to `"marketing"` for any unmapped
`doc_type`. Miami-Dade **sealed engineering drawings** therefore publish as marketing. This is
G75's root cause and it also feeds the drawing-claim modules. `source_class` is a registry
(`AMENDING.md`), `sealed_approval` already exists, and a registry addition needs no
negotiation. Adjacent: `snapshot.py` takes a document's class from the first filing a citation
reached, contradicting `registry-additions.md`'s *"the strongest admissible reading of the
bytes"*.

**Defect C.** Crop `c97fe2d5…` (NOA 06-1019.01 p10) carries three conflicting reviews. One
reader recorded an entire footing grid in **feet** where the page printed inches — a 97-foot
post spacing, 12× — and **two of three review passes accepted it**. It never published, so
publication caught what review missed. Reconcile the three reviews and record what the review
step is actually able to catch.

**Acceptance.** No `flagged` fact reaches a published `Part.spec`; a sealed approval publishes
`source_class` naming it as such; the three conflicting reviews on `c97fe2d5…` resolve to one.

**Record with it.** `[measured]` across all 71 table reviews, **1,671 of 1,671 grid values a
reviewer recorded were identical to a value some reader had already produced**. The 8
`corrected` rows are merged-cell recovery; the 16 `rejected` are duplicate grids. **No review
in this store has ever changed a numeric digit.** Human review here is demonstrably a
legibility and structure check, not an arithmetic one. Do not cite the 2% not-accepted rate as
evidence that published numbers are 98% right.

## 4 · Item 4 — give step review the leverage crop review already has  `[track B]`

**The highest-leverage item in this plan, and the one that changes the project's shape.**

`[measured]` one crop review propagates to ~47 readings: 37 human decisions cover 1,202
reading statuses. A step review is keyed `(element_id, char_start, char_end)` and `cli steps
--accept` takes one candidate id per invocation. **One decision, one sentence.** That single
asymmetry is why this base knows numbers and not method.

**Do.** `cli steps --sheet --document PATH --page N` writes one reviewable file per page
through `paths.open_write`; `cli steps --accept-sheet FILE --reviewer NAME` applies it in one
`BEGIN IMMEDIATE`, all-or-nothing.

**No schema change.** `step_reviews` already carries one row per span keyed on the evidence,
so the stored record, ledger export/import and `rebuild_step_projection` are untouched. The
ledger stays `LEDGER_SCHEMA = 2` — 2 exists because the header carries per-kind counts, and a
batch adds no kind. **Do not add a `batch_id`**: it is a store-shaped field of exactly the
class `read_ledger` already refuses, and `(reviewer, reviewed_at)` carries it.

**What must NOT be batched.** `verdict` needs its own tick per row. `step_kind`, `step_scope`,
`slot_target` and `text_final` must never be defaulted from a proposal — G69 measured that on
one page **5 of 54 `segment_kind='step'` rows are not steps** (an ordering permission, a
rationale, a cross-reference, a resulting behaviour, a dimension). `segment_kind` classifies
structure; `step_kind` is semantics; inheriting one from the other publishes five wrong
`AssemblyStep`s per page. A moved span must fail the whole sheet, not skip the row — a
partially applied sheet is a signature on a page the reviewer saw in another state.

**Then widen the input, which is a separate defect.** `steps.propose()` reads **only**
`element_type='list'`. `[measured]` the WamBam Nantucket page 2 — a complete 13-step
illustrated procedure with four dimensions, a prohibition and a warning — holds **14 figures,
33 headings, 35 paragraphs and 0 list elements**, so the splitter returns nothing there even
when run. `pair_numbered_flow()` is the seam for those pages and has **never been run on the
corpus**. The real method population is larger than 9,188, not smaller.

**Acceptance.** A snapshot publishes at least one `Procedure` with cited steps and honest
dependencies; `snapshot --verify-stored` passes; the ledger produced by approving a page is
byte-identical to approving the same spans one at a time.

**This item hands over a queue, not finished output.** Clearing it needs a curator. An agent
may act as a machine *reader*; it may not be the human sign-off.

## 5 · Item 5 — publish the 524 machine-agreed readings at level 1  `[track A]`

**Not a new policy. An unfulfilled obligation.**

CUR-S0 removed `cross_family_verified` from `PROMOTABLE` — that is, from becoming a **level-2**
fact. Publishing those rows at **level 1**, honestly classified, was the agreed replacement in
writing on both sides: obligation 6 is **BINDING** that this platform *"publishes every row it
holds, honestly classified, and Planning applies the policy at run time"*, G17 says these rows
publish at level 1 and are rejected by Planning's source policy for structural tasks, and
`registry-additions.md` already ships `CURATION_MACHINE_CONSENSUS` for exactly this.

`[measured]` **0 facts carry `cross_family_verified`.** Level 1 has never crossed. 524
readings wait, over 24 crops in 5 documents.

**Constraints.** The path must never write `accepted`/`corrected`, never touch `PROMOTABLE`,
and never mint a `reviewer`. It cannot go through `promote_tables._promote` as written, which
stamps `review_status` onto the fact and would trip the test that encodes the A1 commitment —
either narrow that assertion with the commitment restated, or build a separate level-1 path.
**Do not quietly delete the test.**

**Acceptance.** Level-1 rows publish carrying `CURATION_MACHINE_CONSENSUS` with their readers,
families and `crop_sha256`; no row's `curation_level` rises on agreement alone; the A1 test
still passes or its narrowing is recorded.

**Risk, plainly.** Level-1 rows reaching Planning widen the surface on which a footing depth
can be wrong. The mitigation is entirely Planning's `min_curation: 2` policy row for
structural tasks. If that is ever relaxed, this ships 524 unchecked cells into structural
decisions.

## 6 · Item 6 — link dimensions to the diagrams they annotate  `[track A]`

**Defect.** `[measured]` all 6,660 `figure` elements carry empty `text` **and** empty
`ocr_text`, produce 0 retrieval units, and are reachable by no query path. But they are
`pdf_text_layer` born-digital line art, and the dimensions beside them **are already extracted
correctly** — `33in.`, `70 3/8in.`, `72in.`, `6FT ( 68in)`, fractions intact. Nothing was lost
in reading them. What is missing is which number belongs to which picture.

**This is geometry, not intelligence.** No model, no API, no new dependency; `pdfplumber` is
vendored and exposes the vector paths.

**Design impact — one new table, fully additive:**

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

`relations` cannot hold this: it is `UNIQUE(from_document_id, to_document_id, relation_type)`,
so every intra-document annotation would collapse into one row. Widening it is a table rebuild,
making "extend `relations`" the least additive option, not the most. A column on `elements`
caps cardinality at one and puts a hand-maintained pointer on the canonical table every
re-extraction rewrites.

**Direction:** `from` = the dimension text, `to` = the figure; `annotates` reads subject →
object, as `superseded_by` does. The layering rule does not bind — neither element is derived
from the other, both are L2 — and `tests/test_pointer_direction.py` inspects only `facts` and
`table_read_candidates`, so it passes. **One non-DDL change is mandatory:**
`delete_version_rows()` must clear `element_relations` for the edition, or re-ingest leaves
dangling rows.

**Honest caveat, measured.** This is not an inside-the-box rule. On WamBam page 2,
`70 3/8in.` at `[442, 375, 472, 387]` and `72in.` at `[444, 393, 461, 405]` sit **outside
every detected figure bbox** on that page — the detector carved out the illustration
sub-regions while the dimensions live in the step panel beside them. Proximity plus leader-line
geometry, and `basis` records which was used per row.

**Acceptance.** Figures become reachable by query; a sampled set of links is checked by eye; a
link whose basis is `leader_line` degrades honestly when `pdfplumber` is absent.

## 7 · Item 7 — read the drawings a vision model can read and OCR cannot  `[track B]`

**Lower priority than items 4 and 6, by the owner's direction** — the HVHZ / Miami-Dade
material is deprioritised. `[measured]` that is a small share anyway: **23 of 221 drawings
(10%)** and 340 of 7,219 instruction lists (4.7%). The bulk is installation manuals — 92
drawings and 6,105 lists — so this item keeps its value while losing its urgency.

**Defect.** All 221 `drawing` elements are `ocr`/`image_ocr` and the output is noise. On a
CertainTeed approval sheet tesseract read the printed `96⅛"` post spacing as **`966”`** — ten
times too large — the adjacent `97"` as `97°`, and the fence pickets as
`SIISSSSSSSSAENSSSSSSSSSS`. `[measured]` 0 published values trace to any drawing.

**Design impact — one additive column:**

```sql
ALTER TABLE table_read_candidates ADD COLUMN element_id TEXT REFERENCES elements(element_id);
```

It points from an L3 reading **down** to an L2 element, the same direction as `facts.element_id`.
**No table rebuild:** `[measured]` 221 drawings sit on 221 distinct pages, **0 pages carry
two**, so `UNIQUE(document_id, page_no, reader, row_index, col_index)` already holds. Figures
would collide (1,205 pages carry more than one, up to 45) — defer that, and note the trap:
165 rows have `crop_sha256 IS NULL` and SQLite treats NULLs as distinct, so widening the key
with that column is silently vacuous until the crops are backfilled.

**No contract change.** `source-refs-design.md` already defines evidence kind `visual_reading`
— no quote, bbox in crop pixels, whole page plus a cell box, *"backed by a person **or reader**
looking at pixels"*. It was written for this case and admits a machine reader by name. A
vision reading is `curation_level` 1 at best; §1.4 requires level 2 for admissible structural
classes, so such a value **publishes and is inadmissible until reviewed** — the designed path.

**`reader_kind` gets no new value.** It is internal, crosses nothing, and feeds nothing —
`CURATION_LEVEL` keys on `review_status` alone. Distinguish the model in `reader`, which is
already free text and already part of the unique key.

**What must change in the review model.** `agreement()` joins on grid coordinates and skips
`row_index < 0`, so it never sees a drawing reading: **cross-reader agreement is meaningless
here**, and a misread dimension on a drawing is self-consistent with no row header to
contradict it. A reviewer signing a drawing reading needs the crop **per claimed dimension**
(today three published Augusta specs cite one rectangle, so one signature covers three numbers
and none can be rejected alone) and the unsegmented source lexeme beside the value.

**Guardrail.** Refuse a reading whose crop is missing on disk, so the echo check has something
real to verify. This is what prevents a repeat of the published `width_mm = 38100` whose
citation returns text reading `5'x 5.5" x 71.5"` and `image: null`.

**Cost.** ≈ $19 and ~960 calls for the machine pile, the drawings and a first figure tranche,
assuming two independent readers per crop. **Money is not the constraint; sign-off is.**

## 8 · Item 8 — one identity per product  `[track C]`

**Deferred deliberately. It needs Planning before it is worth doing.**

**Defect.** `parameters._default_scope()` mints a `fence_model` id by slugging
`manufacturer + product_family` — per-document metadata. `[measured]` **117 distinct
(manufacturer, product_family) strings across 146 documents**, 0.8 identities per document. One
published id is a table of contents, not a product. This is the mechanical reason 6,563
Planning runs matched nothing.

**Why it waits.** `reach.py` shows Planning matches scope by plain equality against its own
ids (`M-SLAT`, `M-VINYL`), and no `mfr/*` id has ever appeared in a run. Minting good ids
before the join is agreed publishes into a void. And `snapshot.py` types `ParameterTable.scope`
as a bare dict and checks the models shape only when the list is non-empty, so **nothing today
verifies that a scope id resolves to a published model** — the churn this would introduce is
currently undetectable.

**Not a rename.** Deciding two document titles name one product is a judgement call, and the
current code refuses to invent an entity on purpose. Budget it as curation.

**Boundary work that precedes it.** An `EntityRef.id` stability filing — note **009 is already
taken** (`contributing_sources`), so this is 012/013. File it before minting, for the same
reason 011 was filed while it was cheap.

---

## 9 · What crosses the boundary, and what does not

| Item | Amendment? | Why |
|---|---|---|
| 0, 1, 2 | no | Internal measurement |
| 3 | no | `source_class` is a registry; `sealed_approval` exists |
| 4 | no | `contract.md` §1.2 states review state is *not* in the payload |
| 5 | no | Obligation 6 already requires it |
| 6 | no | L2-internal; nothing published changes shape |
| 7 | no | `visual_reading` already defined |
| 8 | **yes** | `EntityRef.id` stability, trigger D, filed as 012/013 |

**All 31 stored snapshots stay valid** under every item here. `models` sits inside the hashed
member dict, so publishing it mints a new hash rather than invalidating an old one.

**On `Rule`:** mark it RESERVED, using the `SlotRef` precedent, rather than inventing a shape.
`max_rack` is **already** in the `ParameterTable.parameter` enum, so a conditioned max-rack
limit — including `SESGADO MÁXIMO DE 8°`, found printed inside a figure and reachable by no
text query — publishes today through machinery that exists. `ParameterTable` already carries
scope, conditions, `hit_policy`, provenance and uniquely `uncovered`, the only mechanism in
the contract that says what this knowledge does *not* cover. A `Rule` type would rebuild all of
it. **Ordering trap:** amendment 011 renames `max_rack`; publishing a max-rack table before 011
ratifies pins the old name into a write-once snapshot.

## 10 · Three things already designed and never built

The gap is between the design documents and the code, not in the design.

- `visual_reading` — the evidence kind for a machine reading a picture (item 7).
- `CURATION_MACHINE_CONSENSUS` — the warning code for level-1 publication (item 5).
- `derived` — the evidence kind defined as *"a calculation, or `data/structural/*.json`"*, the
  ~120 hand-researched engineering claims that no code path currently reads.

## 11 · What this plan does not decide

- Whether `query_terms` or the natural question is the production contract (item 1 forces the
  choice; it does not make it).
- The audit rate for level-1 publication. Nothing in this store measures blind digit-level
  re-reading, so any rate quoted today would be invented.
- Whether items 6 and 7 widen to the full figure population. Decide after the first tranche.
- Who the curator is. Items 4 and 5 hand over queues; an agent may read, not sign.
