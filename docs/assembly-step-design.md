# Steps out of installation guides — `Procedure` and `AssemblyStep`

```text
Status:    Design, APPROVED 2026-09-03. Nothing here is implemented at the time
           of writing. The visual companion to this document is an Artifact
           published the same day; this file is the authority if they differ.
Written:   2026-09-03, after "what is left from the overall plan?" produced a
           decomposition rather than a backlog: of the four empty snapshot
           members, one should be built, one is a next slice, one Planning
           asked us not to build, and one has no shape to build.
Authority: Advisory on internals. It changes no BINDING contract item and needs
           no amendment. The authorities are unchanged: docs/integration/contract.md
           (FROZEN v1.3) at the boundary, docs/mvp-implementation-spec.md inside
           it, guide.md's twelve prohibitions, docs/layering.md's one rule.
Scope:     ONE page of ONE guide — bufftech-fence-installation-guide-2024.pdf p8.
           Not a corpus-wide extractor. The numbers from the slice decide
           whether the seam is worth widening.
```

## 0. The decomposition, which is the real finding

Four snapshot members publish nothing: `models`, `procedures`, `combinations`, `rules`.
Reading the contract for each produces four different answers, and treating them as one
backlog item would have been the mistake.

| Member | Verdict | Why |
|---|---|---|
| `procedures` | **Build now** | Specified by N10/N13 and evidence-rich: 70 of 144 documents are installation manuals, holding 6,105 `list` elements. |
| `models` | Next slice | Needs `PanelSpec`. Four of the eight open candidates (C7, C9, C10, and C8's successor) are questions about that shape, so its core is still under negotiation. |
| `combinations` | **Do not build** | Planning asked us to stop, in writing. |
| `rules` | **Blocked** | A BINDING payload member with no defined shape anywhere. |

**`Combination`.** `knowledge-datamodel.md` §3.9: *"`grep -rn "Combination" src/` in the
engine returns **nothing**. We accepted this type as binding, put it in the snapshot
payload, argued for it from the AHRI precedent, and asked you to curate certified
assemblies that a run would **silently ignore**… your effort is better spent on parameter
tables and definitions. We would rather say this than keep accepting data nothing reads."*
Building it would produce data nothing reads against an explicit request. It stays at zero
deliberately, and that is not a gap.

**`Rule`.** `contract.md` §1.2 lists `rules [Rule]` in the snapshot payload. There is no
`Rule { … }` block in `contract.md`, none in `knowledge-datamodel.md`, and no entry in
`amendments/CANDIDATES.md`. It appears only in the payload list, in §4's tier-3 mapping
("derived rule → a `Rule`"), and in one traceability row. A binding member whose shape was
never written down cannot be produced by either side. **Filed as a candidate, not
scheduled as work.**

## 1. What is settled before this document starts

`AssemblyStep` and `Procedure` are frozen at v1.3 and were negotiated in detail. This
design produces them; it does not shape them. From `knowledge-datamodel.md` §3.6:

```text
AssemblyStep { key · kind · scope · slots [SlotTarget] · requires [Edge] · cites · text_i18n }
  kind    assembly | installation | preparation | part_modification | maintenance
  scope   panel | bay | post | run | site
  Edge    { kind: after | not_before | before | exclusive_with, step: key }

SlotTarget = PanelSlot(path) | PostSlot(key) | Footing(part) | SiteFixture(kind)
           | Elapsed(Quantity) | Reused(slot_path) | None

Procedure { id · scope: EntityRef | null · steps [AssemblyStep] · cites }
```

Two provisions bind this slice:

- **All five scopes publish from the start.** Planning rejected this platform's own
  proposal to drop everything above the panel: a structure sheet is a fitter-facing
  document, and one omitting the string line, the cure and the utility locate is a sheet a
  fitter cannot work from. Phase one renders `panel|bay|post` and reports `run`/`site`
  steps as present-and-unrendered rather than dropping them.
- **`requires` carries an edge kind**, because guides state negative and maximum
  dependencies as well as ordinary ones, and two of them explicitly deny their own print
  order (*"Assembly may be continued by installing all bottom rails first, or one section
  at a time"*).

## 2. The evidence, measured

`[measured]` 2026-09-03 against `workspace/indexes/evidence.db`:

| | |
|---|---|
| installation manuals | 70 of 144 documents |
| `list` elements inside them | 6,105 |
| elements beginning with a step number | 1,409 |
| elements on the slice page (p8) | 28 |
| numbered step headings there | 12 |
| bullets (`•`) inside those elements | 44 |
| elements carrying a bbox | 28 of 28 |
| elements with a pre-rendered crop | 0 of 28 — review renders on demand |
| damaged words in the text layer on p8 | 11 (`I nsert`, `T ape`, `L evel`, …) |

**A discrepancy, recorded rather than resolved.** `audit/01-audit-response.md` §2.4 reports
**49 bullets** on this page, classified 13 `panel` / 11 `bay` / 25 neither. Counting `•`
in the store today gives **44**. The difference is not chased here, and neither number is
adopted as fact; reconciling them is a task for the slice. Nothing in this design depends
on which is right.

## 3. The granularity decision

**The bullets are not separate elements.** One `list` element holds a whole bullet block.
This is the real shape of step 3 on p8:

```text
element-cb15881761-0007   bbox [54.14, 290.42, 275.27, 370.50]

• I nsert post in hole • Determine rough height • Fill hole around post with
concrete mix (sand, gravel and cement) approximately 2" or 4" below grade
• Tamp concrete in hole to eliminate air pockets • L evel and square post
```

Three options, and the choice is where the citation lands and how many scopes survive.

| | Steps | Citation | Verdict |
|---|---|---|---|
| **A** bullet steps, block citation | 5 | all cite the containing block's bbox | **Adopted** |
| **B** bullet steps, re-extracted | 5 | each cites its own bbox | Available later |
| **C** one step per heading | 1 | one bbox | Rejected |

**A is adopted.** Split on `•`, one `AssemblyStep` per bullet carrying a character span
into its element; the `SourceRef` names the containing block. The weakness is a *stated
limitation* rather than a wrong number, and the block crop still shows the reviewer the
bullet it is judging.

**B is rejected for now, not forever.** Giving each bullet a real bbox means a new
extraction edition under G38 — and `ref_id` embeds a bbox, which `CLAUDE.md` names as the
one identifier a re-extraction breaks retroactively, taking obligation 3 with it. It stays
a targeted upgrade if the coarse citation ever proves inadequate.

**C is rejected outright.** The block above holds two `post`-scope actions and two
`footing`-scope ones; a single step cannot say that. N10 exists precisely because scope was
measured varying bullet by bullet. C is four times cheaper to review and publishes a shape
Planning argued against.

## 4. The pipeline

Not a new architecture — the path `table_read_candidates → table_review → facts` already
takes, applied to a different seam. Every reference points down a layer
(`docs/layering.md`), and `tests/test_pointer_direction.py` enforces it.

```text
L1 raw          the PDF, never written to
L2 canonical    elements — 28 on p8, each with a bbox        (exists)
L3 assertions   step_candidates — proposed, publish nothing  (new)
                     |  human review  <- the only irreversible step
L4 entities     procedures + steps — reviewed only           (new)
L5 published    the snapshot member `procedures`             (new)
```

A step's `cites` resolves **down** to the element it came from. No element knows what was
derived from it.

## 5. Where the human gate sits, exactly

**On the judgement, not on the text.** A step's text is verbatim from a cited element:
mechanical, exact, needing no opinion. What is not mechanical is `kind`, `scope`, `slots`
and the `requires` edges. So the proposer offers a classification and a person accepts or
corrects it — the accept/correct path `cli review` already implements.

Three consequences, each with a standing reason in this repo:

1. **Proposals never publish on their own.** A1/C0 is the precedent: machine agreement
   between two readers was being laundered into curation level 2, and 324 facts had to be
   un-promoted. A `step_candidate` with no reviewer publishes nothing, ever.
2. **Proposer precision is measured and reported before anything publishes.** The rules
   come from the audit's own thirteen observed scopes — `811`/utility → `site`, string
   line and stakes → `run`, dig/gravel/concrete → `post`, rail and picket → `panel`,
   `72 hours` → `Elapsed`. The last time this repo guessed at a pattern without measuring
   it, the guess ran at 18.6% precision (A5, `stock_length`). The number gets reported
   whatever it is.
3. **Damaged source text is a review outcome, not an extractor fix.** The text layer holds
   `I nsert`; the page says `Insert`. The reviewer sees the crop and records `corrected`,
   exactly as table readings do. No OCR overwrites a source text layer (prohibition).

**`requires` edges come from the numbering.** The 12 numbered headings give an `after`
chain, and that is a *stated* order, not an inferred one. Anything else — `not_before`,
`exclusive_with` — is recorded by a reviewer against quoted text.

## 6. One block, worked through

Step 6's block is the most instructive on the page, because it is not uniformly steps:

```text
element-cb15881761-0013   bbox [54.14, 651.06, 273.20, 703.07]

• L evel and square fence
• T o lower a post, place a wood block from corner to corner on the post and
  carefully tap with a mallet
• N ever strike the PVC post without a wood support
```

| Bullet | Becomes | Classification |
|---|---|---|
| 1 | `AssemblyStep` | `installation` · scope `bay` · slot `None` · text corrected |
| 2 | `AssemblyStep` | `installation` · scope `post` · slot `PostSlot` · text corrected |
| 3 | **`Warning`** | not a step — a prohibition, `attaches_to` the step above |

Block-level splitting would have published a prohibition as part of an instruction.
Bullet-level splitting lets the third become a `Warning` whose `attaches_to` names the step
it governs — which is exactly the case candidate **C14** says has no scope between "one
step" and "the whole document". The slice exercises that candidate against real evidence
instead of arguing it in the abstract.

## 7. What publishes, and what becomes a gap

Only reviewed steps publish. Three gaps ship with them, because silence must never read as
coverage:

- **The unreviewed remainder of the page** — any bullet the reviewer did not reach.
- **The other 143 documents** — 70 are installation manuals and none has a published
  procedure.
- **The procedure's owner.** `Procedure.scope` is `null` for this slice. The shape permits
  it (`EntityRef | null`, "owned by no product at all") and it is honest: the guide's
  `FenceModel` does not exist yet, so a gap says so rather than inventing a referent.

## 8. Acceptance

The slice is done when all of these hold, and not before:

1. Proposer precision measured against the reviewed set and **reported** in
   `docs/state-and-gaps.md`, whatever it is.
2. `requires` edges form a DAG. A cycle is a data error, not a rendering quirk.
3. Every published step's `cites` resolves under `cli refs --verify`.
4. A step whose text a reviewer repaired never claims to be verbatim.
5. The review round-trips through `review --export` / `--import`. A human judgement is the
   one thing here that does not regenerate, so it must survive a rebuilt store.
6. Two builds over identical knowledge produce byte-identical snapshot members.
7. The full suite passes.

## 9. Deliberately out of scope

`FenceModel`, `PanelSpec`, `Combination`, and any corpus-wide step extraction. One page,
reviewed properly, publishing real `Procedure`s with resolvable citations — then the
numbers decide whether the seam is worth widening.

Raised to Planning in parallel, as agreements rather than tasks: **`Rule`'s missing shape**
(new candidate), and **C11 / C13 / C14** — per-step applicability conditions,
order-independent repeated steps, and warning scope between a step and a document. This
slice exercises all three against real pages, which is a better basis for a batch than the
abstract argument that logged them.
