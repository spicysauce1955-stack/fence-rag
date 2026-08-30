# LLM-assisted extraction — design

```text
Status:    Design, approved 2026-08-30. Records four manual spikes and the
           plan that follows from them. §8 records Phase 1's execution the
           same day: real code changed (a G55 fix in
           fence_evidence/table_review.py, plus its regression test) and six
           new schema candidates (C9-C14) were filed as a direct result.
Authority: Subordinate to docs/integration/contract.md (FROZEN v1.1),
           docs/integration/knowledge-datamodel.md, docs/layering.md,
           CLAUDE.md. Where this document and any of those disagree, they
           win and this is the defect.
Method:    Four spikes run against ChatGPT (web) on real corpus documents,
           graded against store-verified ground truth wherever one existed.
           Every count in §3 was read from workspace/indexes/evidence.db and
           workspace/snapshots/ on 2026-08-30.
```

---

## 1. What this is for

The user wants to use an LLM (tested here: ChatGPT web) to help parse the
structural and install-guide PDFs in this corpus. That request was scoped,
through four spikes rather than up-front argument, into three distinct
targets that turn out to have very different levels of existing machinery,
existing schema, and existing risk. This document records what the spikes
showed, what is and isn't built for each target, and the phased plan that
follows.

It does not authorize building anything. Phase 1 is ready to move into
implementation planning; Phases 2 and 3 are explicitly not.

## 2. The three targets

- **A — clear the table-reading backlog.** This project already runs an
  LLM-reads-a-scanned-table pipeline (`table_review.py`, `promote_tables.py`):
  multiple readers transcribe a crop, and a value promotes once either a
  human reviews it or two independent model families agree
  (`mark_cross_family_verified`). Of the 37 pages this pipeline has ever
  processed, **27 have only ever been read by one model family** — there is
  no second independent reader to compare against, so none of them can reach
  `cross_family_verified` without one.
- **B — populate the parts/assembly composition model.** `docs/layering.md`
  invariant 10 bars any reader — automated or LLM — from being trusted to
  produce the *hand-authored* composition graph (`data/*.json`,
  `bom-schema.json`). That invariant is untouched by this document. But the
  actual contractual target this platform is meant to publish —
  `PanelSpec`/`FrameSlot`/`Joint`/`Member` in
  `docs/integration/knowledge-datamodel.md` §3.3 — is a different, much more
  precisely specified thing, and it has never been implemented at all (§3).
- **C — get narrative install-instruction content (steps, sequencing,
  warnings) into a usable form.** `docs/curation/` proposed a home for this
  and is paused, unimplemented, under review. Separately, the contract's own
  `Procedure`/`AssemblyStep` type (§3.6 of the same datamodel doc) is exactly
  this, and is equally unbuilt.

## 3. Measured state of the target architecture

Read from the one published snapshot
(`workspace/snapshots/3ae88642ec789f30de43766da57b5e201a58964999ffa6cec65ce1bacb430508.json`)
and `workspace/indexes/evidence.db` on 2026-08-30:

| Array in the snapshot payload | Count | Target's build state |
|---|---|---|
| `parameters` (`ParameterTable`) | 4 | Built and shipping — this is the only Tier-2 type ever populated |
| `models` (`FenceModel`/`PanelSpec`) | 0 | Fully specified (§3.2-3.4), never implemented |
| `parts` (`Part`) | 0 | Fully specified (§3.1), never implemented |
| `part_types` | 0 | Registry defined (contract §2.1), never populated |
| `rules` | 0 | Never implemented |
| `procedures` (`Procedure`/`AssemblyStep`) | 0 | Fully specified (§3.6), never implemented |
| `combinations` | 0 | Never implemented |

Within `docs/integration/knowledge-datamodel.md` §3.3.1 itself: `FrameSlot`,
`Member`, `FixingRule` and `PostSlot{key, requirement, cap}` are stated as
built (on Planning's side); `Joint` as a full object and any part-contains-part
relationship (`ContainedSlot`) are stated as **proposed, not built anywhere**.

Reader-pipeline state (`table_read_candidates`, all `row_index >= 0`): 37
distinct pages processed; 3 human-reviewed (`accepted`/`corrected`); 7 at
`cross_family_verified` (two families agree, no human yet); **27 with exactly
one reader from exactly one family** (`claude-sonnet`), no second-family
reading to compare against, on documents spanning at least 6 distinct source
PDFs (`doc-32e36a07ab44`, `doc-3c8ab51045c7`, `doc-c267c4cd071f`,
`doc-7a08132799a1`, `doc-8727ba0fd4d4`, `doc-f87aa202ef21`, `doc-2b81f4c2925e`
p8).

## 4. What the four spikes showed

All four were run against ChatGPT web, on real corpus PDFs, with a written
briefing per spike (preserved in
`/tmp/claude-1000/-home-user-Workspace-fence-rag/ecadf950-d924-437e-8897-5bc76b7a9af9/scratchpad/`
— a scratch location, not committed; the substance is recorded here).

**Spike 1 — footing table, graded against a human-reviewed ledger entry.**
`noa-24-0117.06-simtek-fence.pdf` pp.6/8, the two crops in
`workspace/catalog/review-ledger.jsonl` reviewed 2026-08-30. All 16 cells
matched exactly. It correctly reported the sheet prints no HVHZ/Non-HVHZ
bracket — the same distinction whose earlier mishandling produced 24 false
`disputed` gaps (G53) — rather than writing `null`/`unknown`.

**Spike 2 — panel/post construction detail and drawing description, no
ground truth available** (SimTek/Allegheny was never researched into the
hand-authored dataset at all). Every transcribed dimension later
cross-checked against the store's own OCR/text fragments and against the
independently human-authored `data/structural/barrette-outdoor-living-structural.json`
(27.5" embedment, 1" grade line — both matched). It correctly declined to
attribute the panel shell's `0.120"`/LLDPE callouts to the post, and
correctly refused to say the panel-stiffener tube (item 2 on the parts
table) runs inside the post — which mattered, because a genuinely separate
post-internal stiffener/bracket detail exists on an adjacent page (page 7)
that neither this spike nor its briefing ever scoped in.

**Spike 3 — four table-read-candidate crops, chosen because they are among
the 27 single-family-only pages** (§3): three NOA parts lists
(`doc-32e36a07ab44` p5, `doc-3c8ab51045c7` p11, `doc-c267c4cd071f` p10) and
one 13×11 dense engineering-coefficient table (`doc-f87aa202ef21` p47,
CLFMI wind-load guideline). Graded against the existing single-family
reading, withheld from the briefing: 32 of 33 rows matched exactly; the one
discrepancy was a spacing variant in one cell
(`"0.875 X6X71.5"` vs `"0.875 X6 X71.5"`) neither reading can be checked
against without a human opening the crop. On the CLFMI table, both readers
independently transcribed a printed anomaly (a non-monotonic `z/Lh` sequence)
identically rather than "correcting" it — a real signal, since **this
result implies the current pipeline can promote all four to
`cross_family_verified` today**, if `chatgpt-web-1` is registered as a
reader family and its readings loaded, per §5.

**Spike 4 — one `FrameSlot`/`Joint`/`PartRequirement`, populated against the
real §3.3 schema (quoted, not paraphrased) from two documents** (the same
NOA plus `bufftech-simtek-fence-install-guide.pdf` pp.20-21). Every cited
fact verified against the store's text (`amount_milli` conversions exact;
quotes verbatim-equivalent to the actual page text pulled from
`retrieval_units`). It correctly declined `channel_depth` and
`insertion_margin` rather than reusing a conditional, differently-scoped
value (a field-cut clearance rule, page 20 step 9) that would have silently
overstated what the documents support. It surfaced a genuine schema gap: a
SimTek panel has two simultaneous connection mechanisms (channel reception,
bracket bearing) and the proposed single-`Joint`-per-`FrameSlot` shape
cannot represent both without either two slots or a compound joint type.

## 5. The plan

### Phase 1 — reader-family backlog (A). Ready for implementation planning.

**Decided and done, 2026-08-30:** `chatgpt-web-1` is registered in
`fence_evidence/table_review.py`'s `READER_FAMILY` as its own family
(`openai-chatgpt`), kept separate from `openai-codex` — no page has been read
by both, so there is no evidence they fail the same way, and defaulting to
"separate" only lets them count as independent once agreement is genuinely
observed. Revisit if a pattern of correlated errors ever turns up; merging
them is a one-line change. This means Spike 3's four crops **will** promote
to `cross_family_verified` on load, not merely add pre-review volume.

Remaining to implement: load Spikes 1 and 3's output for real via
`cli readings --load-dir`, confirm movement with `cli review --queue`, then
continue the same way through the other ~23 single-family pages named in §3
— now unblocked, via the Project workflow set up for this (below).

### Phase 2 — more `PanelSpec` worked examples (B). Not ready to build.

Do 2-3 more manual worked examples spanning different `Joint.kind`s (a
routed/groove rail joint from the Chesterfield family — parts lists for
which are already pulled in Spike 3 — a butt joint, a bracket-only case)
before considering any pipeline. The goal is to learn whether Spike 4's
compound-joint finding is systemic or a one-off.

**Resolved 2026-08-30:** the compound-joint finding and the `FrameSlot`-vs-
`Member` ambiguity are both boundary (Tier 2) findings, not this platform's
to fix unilaterally — filed as
`docs/integration/amendments/CANDIDATES.md` C7 and C8, with a third piece of
evidence found while verifying them: page 7 of the SimTek NOA (a generic
post/bracket spec sheet, not panel-specific) gives the panel support
bracket's actual fastener (zinc-plated 1½" #10 hex screws) and confirms three
distinct post-internal stiffener profiles by `PostRole` (corner/end/line).

**Explicitly deferred:** any reader/review pipeline for `PanelSpec`
candidates, analogous to `table_read_candidates`. The schema itself is
partly proposed rather than built (`Joint`, `ContainedSlot`), and one
worked example is not enough evidence to design a pipeline against it.

### Tier 1 fix — ready to implement, not gated on Planning or on Phase 2

Unlike C7/C8, this one is ours to make freely: adding a `PartType` extension
is, by contract §2.1, never a breaking change and needs no negotiation. It
cannot be *shipped* yet — `part_types` is one of the six snapshot arrays at
0 in §3, so there is no live registry to add a row to — but the decision can
be made now and picked up the moment Part/PartType publishing exists.

**The gap this closes.** Spike 2 found the corpus's own `reinforcement`
label doing double duty: page 7 (verified above, not the earlier garbled OCR
read) shows a **panel-frame stiffener** (top/bottom tube framing the molded
shell, pp.6/8's parts-table item "PANEL STIFFENER", 1½"×1½"×18ga wall, 5 lbs
/ 70¼") is a physically different component from a **post-internal
stiffener**, which itself varies by the already-shared `PostRole` vocabulary
(§1.1): corner posts get a 1½"×1½"×.065 16ga steel tube, end posts a
2"×3"×.065 16ga steel stiffener, line posts a 17ga HSLAS galvanized steel
Z-beam grade 60 class 2. One label cannot honestly cover both, and the
post-internal case cannot honestly be one id either, since its spec changes
with role.

**Proposed extensions**, both children of the shared spine `reinforcement`:

- `mfr/simtek/panel_stiffener` — the panel-frame tube. One id; its spec does
  not vary by condition in what's been read so far.
- `mfr/simtek/post_stiffener` — the post-internal member. **One id, not
  three** — `PostRole` already exists as shared vocabulary for exactly this
  kind of role-conditioned difference, so the three profiles are authored as
  `Part.spec` variants selected by `PostRole` (the same pattern
  `FenceModel.variants` already uses), not as three separate part-type ids.

**Explicitly not proposed:** an extension for the panel support bracket.
Nothing manufacturer-specific separates it from the shared spine `bracket`
type's existing counting/placement behaviour — the mechanical test (§2.2)
says this stays a spine type, not an extension.

**Where this is recorded until it can be built:** here, and in C7/C8's
citations. No code changes today — `fence_evidence` has no `PartType`
registry to add these rows to yet. This becomes a Phase 2 (or earlier, if
`Part`/`PartType` publishing lands independently) implementation item.

### Phase 3 — `Procedure`/`AssemblyStep` spike (C). Cheapest next test.

Same rigor as Phase 2 (real schema, quoted verbatim; cite-or-declare-inferred
per field), targeting `Procedure`/`AssemblyStep` instead of `PanelSpec`,
using the install guide's numbered steps and explicit ordering language.
Not yet run. Likely fast, given how clean that document's text already is
(born-digital, no OCR involved) and how directly its content maps onto
`AssemblyStep.requires{kind: after|not_before|before|exclusive_with}`.

### The delivery mechanism — a persistent ChatGPT Project, not one-off prompts

Decided 2026-08-30. Rather than a fresh scratch briefing per test, all three
phases now run through one ChatGPT web Project with:

- **Source documents:** the vertical-slice family only (16 of its 19 listed
  documents — 3 are byte-identical NOA 24-0117.05 copies filed under
  different manufacturers, skipped to avoid wasting Project space).
- **One persistent reference file** (not re-explained per prompt): the real
  `Quantity` type, the real `Gap` type, and the three tasks' output shapes
  (table-reading grid, `FrameSlot`/`Joint`/`Member`, `Procedure`/
  `AssemblyStep`), quoted from the schema docs rather than paraphrased.
- **`Gap` in place of free text for "couldn't determine this"** on Tasks 2
  and 3 — the fix named in §3's tier discussion, upgraded from Spike 4's ad
  hoc "not supported by either document" strings into the real, enumerated
  type. Task 1 keeps its own existing `illegible` cell marker, which is
  already the right convention for that case.
- **Phase 1's first real task: all 25 in-scope backlog pages in one batch**,
  not a sample — the whole single-family backlog that falls inside this
  slice (2 of the 27 total, on documents outside the slice, are deferred).

Work order agreed: Phase 1 at scale first, then Phase 2's remaining worked
examples, then Phase 3. Setup files staged for the user to upload/paste; not
committed to this repo (session scratch), reproducible from this record if
lost.

## 6. Explicitly out of scope

- Revisiting `docs/layering.md` invariant 10 as it applies to the *existing*
  hand-authored dataset (`data/*.json`). Untouched by everything above —
  Phase 2 targets a different, newer schema that dataset was never designed
  against.
- Any code change. `READER_FAMILY` registration and a `PanelSpec` review
  pipeline remain future work items, not authorized by this document. The
  one exception, already done: filing C7/C8 in
  `docs/integration/amendments/CANDIDATES.md`, which is itself a running log
  meant to be added to, not a frozen document.
- Deciding the reader-family-identity question in §5. Named as open and left
  to the user; the upstream-communication question is resolved — see §5's
  Phase 2 update.

## 7. Traceability

- Reader-pipeline counts: `workspace/indexes/evidence.db`,
  `table_read_candidates`, queried by `(document_id, page_no)` grouped by
  distinct `reader`/family, 2026-08-30.
- Tier 1 fix and C7/C8 evidence: `retrieval_units` text for
  `doc-88dcd8a73079` p.7 (`noa-24-0117.06-simtek-fence.pdf`), the
  `"4 LINE POST 30LBS. 102\""`/`"NTS |"` heading-path rows, queried
  2026-08-30 — supersedes the earlier, incomplete OCR-fragment read of that
  page used in Spike 2.
- Snapshot array counts: `workspace/snapshots/3ae88642ec789f30de43766da57b5e201a58964999ffa6cec65ce1bacb430508.json`,
  top-level array lengths, 2026-08-30.
- Schema quotes: `docs/integration/knowledge-datamodel.md` §3.1-3.6, §2.3;
  `docs/integration/contract.md` §1.1-1.2, §2.1.
- Ground truth for Spike 1: `workspace/catalog/review-ledger.jsonl`, entries
  for `doc-88dcd8a73079` pp.6/8.
- Cross-check for Spikes 2 and 4: `retrieval_units` text for
  `doc-88dcd8a73079` (pp.1-8) and `doc-87db00d364b3` (pp.2,5,7,11,12,20,21),
  and `data/structural/barrette-outdoor-living-structural.json`.

## 8. Phase 1 executed, 2026-08-30 — a real bug, found and fixed

The Project workflow (§5) ran all three phases the same day it was set up.
Full grading is in the session record; this section is what changed the
repository.

**Phase 1: 25 pages, 537 cells, loaded for real.** 527 matched the existing
single-family reading exactly. Of the 10 that didn't, 6 are very likely
`chatgpt-web-1` catching a real pre-existing error (a footing table read in
foot marks by the existing reader, `97'`, where 97 inches — `97"`, this
run's reading — is the only physically sensible value); the other 4 are
typo-preservation/whitespace nuances needing a human to open the crop, not
transcription errors either way. See `docs/state-and-gaps.md` G54's
2026-08-30 update for the full numbers.

**A real defect, found while loading and fixed the same session.**
`mark_cross_family_verified` has no CLI wiring and no guard against
overwriting an already-`accepted`/`corrected` row. Running it across the
full reader roster (needed so genuine new cross-family agreement would be
found anywhere it existed, not just on the 25 new pages) downgraded three
already-human-reviewed pages' review status. Caught immediately by
cross-checking the post-run summary against the documented 138/6
accepted/corrected baseline; fixed by replaying
`workspace/catalog/review-ledger.jsonl` (which restored the exact baseline)
and then by closing the actual defect — `table_review.py`'s `UPDATE` now
excludes `accepted`/`corrected` rows, with a regression test
(`test_cross_family_marking_never_overwrites_a_human_verdict`) seeding
exactly this scenario. Full account: `docs/state-and-gaps.md` G55. All 1,074
tests pass after the fix.

**Phase 2 and 3 surfaced six new Tier 2 candidates**, filed to
`docs/integration/amendments/CANDIDATES.md`: C9 (`Joint.kind` has no
spring-retained/snap-lock value), C10 (no way to hold alternative fastening
methods, plus an unresolved cap-profile ambiguity), C11 (`AssemblyStep` has
no per-step condition field), C12 (one `AssemblyStep` can't hold two
alternative methods, and `requires` can't target an elapsed event), C13 (no
relation for "either order is fine" across repeated bay instances), and C14
— which turned out not to be a schema gap at all: `knowledge-datamodel.md`
§3.7 N11 already settles that exact case, and the run only re-discovered it
as open because the extraction contract gave the `Warning` type's fields
without the reasoning behind them. Fixed in the contract file (session
scratch, not this repo) and recorded in C14 as a process note: a compact
schema reference will keep re-triggering this specific rediscovery until
`knowledge-datamodel.md` itself carries a one-line pointer, which is worth
doing once real curation work begins rather than now. C7 gained a second,
independent worked example (a Chesterfield picket-end channel) confirming
its finding isn't SimTek-specific.

**Also found, not yet acted on:** page 31 of
`bufftech-simtek-fence-install-guide.pdf` carries diagram callouts
(`"HOLD TOP RAILS IN POST WITH LOCK RING"`, `"ATTACH END CHANNEL TO POST
WITH 4 SCREWS"`) that this platform's own text extraction never captured,
confirmed only by opening the rendered page image directly — a born-digital
PDF, not a scan, so this is a distinct defect from the documented OCR/scan
problems. Not yet filed as its own gap; worth one if it recurs on another
diagram-heavy page.

## 9. Session closed here, 2026-08-30

Seven open decisions were worked through one at a time after §8: Phase 2/3
stays manual (no pipeline yet); C7-C13 stay batched; the Tier 1 fix stays
parked pending a `PartType` registry; the two deferred backlog pages stay
deferred; the diagram-blind-spot finding stays a note pending a second
occurrence; and two of the three live reader conflicts were resolved for
real — the footing-table unit-mark misread and the "U-SHAPPED" typo, both
confirmed against the rendered page image before recording, taking the
reviewed-crop count from 3 to 7 and `accepted`/`corrected` from 138/6 to
222/15.

Reviewing the first of those two triggered `promote-tables`, which surfaced
**G56** — first written up wrong (a guard-clause fix that wasn't needed,
since `e6d1aed` already built the right handling earlier the same day) and
then corrected: the real defect is `_row_applicability` collapsing "no HVHZ
bracket exists on this table" and "readers disagreed about a real one" into
one `"unresolved"` string, which routes past an already-correct
collision-detector into a false claim about a bracket that was never
printed. See `docs/state-and-gaps.md` G56 for the full account. **Not
patched** — it's real design surface (a third answer for
`_row_applicability`, and gap-path ordering in `parameters.py`), not a
guard clause, and this session already had two self-caused mistakes (G55,
and G56's own first wrong diagnosis) worth not risking a third on top of.

Stopping here by request. Next session should treat G56 as its own
brainstorm from scratch, not a continuation — it deserves the same
unhurried treatment §1-§8 got, not a tail-end patch.
