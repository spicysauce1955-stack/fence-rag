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
| list elements with **no** bullet (12 section headers + 1 footnote) | 13 |
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

### 3a. What `text.split("•")` actually gets wrong — `[measured]` 2026-09-03

Measured across all 70 installation manuals (6,105 `list` elements, 4,629 bullets) and
then against the slice page specifically. A naive split is wrong in six ways, three of
which are present on p8:

1. **`•` is not the only leader, and the disambiguator is `text_source`.** OCR emits
   **zero** `•` — not once in 834 OCR'd list elements; tesseract renders the glyph as `*`
   (464 leader-shaped uses). But in the *text layer* `*` is a **footnote marker, not a
   bullet** (71 elements, nearly all the same `* Caution – In climates that experience
   freeze-thaw cycles…` string, which is on p8 at ordinal 27). Treating text-layer `*` as
   a bullet manufactures steps; ignoring OCR `*` loses 464 real ones.
2. **`-` is a real second-level bullet** — 753 text-layer elements. On p8, ordinal 5:
   `• Dig holes 30" deep or to frost line` / `- Hole size for 4x4 posts = approximately 10"`.
3. **One `•` segment can contain an entire nested procedure.** p8 ordinal 24 is a single
   871-character bullet holding a two-branch lettered choice (`a. Aluminum gate post
   stiffener`, `b. Concrete and rebar*`) with **13 `-` sub-steps** beneath them, including
   the 72-hour cure the contract quotes. One bullet → one step would publish a 900-character
   "step" that is really thirteen, and would lose the fact that a and b are *alternatives*.
   60 such segments exist corpus-wide.
4. **The whitespace after a leader is three different characters** — U+0020 (2,656),
   **U+2002 EN SPACE (1,921)** and TAB (52). All three occur on p8.
5. **A trailing `Note:` rider is not part of the instruction.** 14 segments end with one,
   never start with one. p8 ordinal 9: `• Insert rail into post` + `Note: Pickets will
   attach to rail on the side with the small (¼") holes`.
6. **834 list elements carry their text only in `ocr_text`** (`text IS NULL`). A splitter
   reading `elements.text` alone silently drops 13.7% of the seam.

**And the damaged-word artifact is five times bigger than §2 reported.** The newline form —
`T\namp`, `L\nevel`, `H\nang` — is **263 occurrences in 221 list elements** against 113 for
the space form, and both are one defect: pdftotext emitting a bullet's leading character
as its own text run. **195 of 4,629 segments (4.2%) begin with a split capital**, which is
precisely the token any verb-based classifier reads first.

Repairing it automatically is *not* safe: of the 20 distinct space-form artifacts, **only 7
are real damage**. The rest are legitimate text the pattern over-matches — `Insert post A
into hole`, `Post B may be loosely laying`, `Coloque el canal en U en el poste`. A naive
normaliser corrupts real text at a 65%-of-distinct false-positive rate. So the splitter
**proposes** a repair and the reviewer disposes, and the proposal's precision is measured
against their decisions like every other proposal here.

**One document is excluded from the seam entirely.** `bufftech-installation-guide-afence.pdf`
is an OCR'd scan of the same two-column layout as the slice document, and the OCR read
*across the gutter*: `1. Getting Started 7. Install Top Rail` is one element, and
`• Clean holes and check for straight walls • Square pickets and rails` merges two
unrelated steps from two sections. It is a redundant scan of a document already held with
a clean text layer, so it is excluded rather than parsed.

### 3b. What the splitter actually produces on p8 — `[measured]`

| | |
|---|---|
| step candidates | **55** |
| — from `•` bullets | 44 |
| — from `-` sub-bullets | 11 (all inside ordinal 24) |
| section headers | 12 |
| lettered branch labels | 2 (`a.`, `b.` in ordinal 24) |
| `Note:` riders | 1 (ordinal 9) |
| footnotes (text-layer `*`) | 1 (ordinal 27) |
| text repairs **proposed** | 10 of 55 steps (18%) |

The arithmetic is the argument for splitting nested bullets: 44 + 11 = 55. Ordinal 24's
single 871-character bullet becomes 1 step plus 2 branch labels plus 11 sub-steps, and the
**72-hour cure the contract argues from is one of those 11** — a naive `split("•")` would
have buried it inside a 900-character blob along with the other twelve.

The slice's review is therefore **55 judgements, not 44**. That is the honest number and it
is the one to plan the sitting against.

**Also measured, and it changes nothing but should be recorded:** 46 `paragraph` elements
contain real bulleted steps the layout classifier did not type as `list`, so a `list`-only
splitter drops them. Out of scope for this slice; a gap names it.

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
2. **Proposer precision is measured and reported before anything publishes.** The last
   time this repo guessed at a pattern without measuring it, the guess ran at 18.6%
   precision (A5, `stock_length`). The number gets reported whatever it is.

   **Correction, made while researching this design: only five of the audit's thirteen
   scopes are recoverable.** `audit/01-audit-response.md` §2.4 says *"Thirteen scopes that
   are neither. Each has a verbatim quote in the working file; five that make the case"* —
   and the working file was never committed. Searching the repo, including deleted paths in
   `git log --diff-filter=D`, finds the count in four places and the scopes themselves in
   one: the five published in that table. **Eight scope names and all their quotes are
   lost.** An earlier draft of this section claimed the rules "come from the audit's own
   thirteen observed scopes"; they cannot, and this slice starts from five:

   | Audit scope | Verbatim trigger | Lands as |
   |---|---|---|
   | `site` — utility locate | *"have the utility companies clearly mark your property"* | scope `site` |
   | `run` — string line | *"install line stakes and run a string line"* | scope `run`, slot `SiteFixture(string_line)` |
   | `footing` — gravel base | *"add 6" of gravel for post drainage"* | scope `post`, slot `Footing(gravel)` |
   | `wait` — elapsed time | *"Leave gate on blocks for 72 hours"* | scope `post`, slot `Elapsed` |
   | `temporary` — part as jig | *"Use only one rail as temporary spacer"* | slot `Reused(slot_path)` |

   Note that three of the five are **not** scopes in the ratified model — `footing`, `wait`
   and `temporary` became `SlotTarget` variants. The audit's vocabulary predates N10 and
   must be translated, not copied.

   The eight lost scopes are a reason to **derive the rest of the rule set from the slice
   itself** rather than reconstruct it: the reviewer's corrections on 44 real bullets are
   better evidence than a half-remembered list, and they are recorded in the ledger where
   the working file was not.
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

## 7a. Two decisions this design did not anticipate

Both surfaced during research and are recorded here rather than discovered mid-build.

**The review ledger's schema has to go to 2.** `reviews.LEDGER_SCHEMA = 1`, and
`read_ledger` hard-refuses any other value. The header line carries per-kind counts
(`{"fact_reviews":204,"kind":"ledger","schema":1,"table_reviews":71}`), so adding a
`step_reviews` count changes the header shape. `workspace/catalog/review-ledger.jsonl` is
committed and `tests/test_review_ledger.py` fails the build when it disagrees with the
store, so this is a deliberate, tested migration — not a field that can be slipped in.

**The anchor cannot be a crop digest or a `ref_id`.** Table reviews key on `crop_sha256`;
that does not apply here, because `[measured]` 0 of 28 elements on p8 have a pre-rendered
crop — review renders on demand. `ref_id` embeds a bbox and does not survive a
re-extraction (G38), which is the same reason §3 rejected option B. The anchor is therefore
`(element_id, char_span, bullet_text)` — the element, the character span option A already
requires, and the verbatim text the reviewer actually saw — resolved on import by the
one-and-only-one rule `reviews._facts_matching` already uses, reporting
`ambiguous` / `value_changed` / `orphaned` rather than guessing.

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
