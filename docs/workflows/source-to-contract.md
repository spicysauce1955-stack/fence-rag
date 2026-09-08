# Source-to-contract conversion workflow

Use this workflow for a bounded product, document group or relationship slice.
Its output is useful contract-valid knowledge with declared limits; complete
fabrication data is a separate outcome. Begin with one product and a few fields.

Authority: [four-layer design](../four-layer-model-design.md),
[frozen contract](../integration/contract.md),
[contract datamodel](../integration/knowledge-datamodel.md), and
[amendment procedure](../integration/AMENDING.md). This document defines an
execution practice, not another internal or public datamodel. The handoff's
successful checks are reused; its private assembly shortcuts are not promoted.

## Start with the next decision

Read the batch manifest, its listed source locations and the declaration for the
entity being authored. Open additional artifacts only to resolve a specific
question. Do not scan the repository or load old conversations. Separate the
batch-specific product IDs, units, source references and known gaps from these
general instructions. The example manifest is
[emblem-conversion-batch.json](../../workspace/catalog/emblem-conversion-batch.json).

Record the intended answer: component properties, assembly explanation, fitted
counts/cuts, or purchasing. That determines which missing inputs actually matter.
Do not demand a full engineering drawing to publish a supported nominal size.

## Check source coverage before declaring a gap

A small conversion slice does not establish that the available sources lack other
answers. Before marking a requested value missing, make a bounded inventory of
relevant product/family documents: project sheets, catalogs, installation and
cutdown/transition guides, component drawings and structural filings. Limit
inspection by the question and product scope, not just filenames or search hits.

For each candidate record its path/URL, content hash, pages inspected, inspection
method, product/configuration scope, findings and disposition. Reuse previous
work where appropriate, but verify that its search actually covered the current
question. Record uninspected candidates explicitly instead of treating them as
negative evidence. The coverage record is run metadata, not a new claims store.

If PDF text is empty or unhelpful, inspect canonical `ocr_text` and page images.
Screen relevant drawing sheets with OCR, then visually verify selected labels,
units, dimensions and datums. OCR is a navigation/extraction aid; its garbled
output must not be silently corrected in canonical storage. Record an attributed
visual reading through the claim lifecycle with its extraction/review status.
Do not infer dimensions by measuring an image marked NTS (not to scale).

Read each drawing's title, sheet number, revision and construction notes. A
manufacturer name or similar approval number is not proof of component identity
or succession. Pre-built, ready-to-assemble, reinforced, gate and transition
configurations may share dimensions while differing in other details. Compare
applicable sources without erasing those distinctions. Useful drawing/family
knowledge can be published in its own scope while exact-SKU transfer remains
unresolved; do not discard it merely because that bridge is missing.

If relevant local sources do not settle a question, use available web/Tavily
tools to follow manufacturer documents, component crosswalks and exact-product
links. Try recovering a known missing download and compare its recorded hash
before asking the user to supply it. A bounded search ending without a result
means “not found in the inspected sources”, not “unavailable anywhere”. User
questions can proceed alongside this work when they help identify the intended
product or configuration; supplying a new document is not automatically the
user's burden.

### Coverage must be product-shaped, not batch-shaped (Augusta lesson)

A limitation is only honest after the inventory has been genuinely
product-scoped. The Augusta slice initially recorded "purchasing quantities
not claimed" and "picket count unknown" as honest boundaries — while the
manufacturer's own CAD web page (reachable by following the URL pattern
already recorded in the dataset's document entries) carried a complete
per-configuration material list that closed both gaps plus an entire unknown
component (metal rail inserts). The failures to avoid:

* **Batch-shaped inspection.** Inspecting only the documents the current
  evidence chain already touches is not a bounded inventory. Walk the
  family's whole document list; inspect or explicitly defer each with a
  reason. A "not found" recorded over an uninspected corpus subset is
  unverified.
* **Unfollowed URL patterns.** The dataset's `documents` entries name real
  URL shapes (e.g. `weatherables.com/pages/<style>-<size>-cad`, CDN asset
  paths). One sibling URL pattern often generalizes to the exact product
  page, spec sheet or material list you are missing. Follow the pattern
  before declaring a gap; a web locator found this way still needs its bytes
  retained through the corpus path before it is evidence.
* **Limitations written where gap states belong.** "X not claimed" is a
  boundary only after inspection; before that it is `not found after
  (incomplete) inspection`, which the gap-state table already forbids.
* **Numbers that echo each other are corroboration, not truth.** The
  strongest gap-closers cross-validate: the Augusta material list's
  U-channel length (39.5 in) exactly equaled the drawing-derived run height
  (95.5 − 3×5.5)/2, and the 6 ft list closed the same way (27.75). Prefer
  evidence that closes arithmetically against what you already hold; record
  the closure check in the coverage note.
* **Implied values are not measurements.** A stated stock length minus a
  derived run height (43 − 39.5 = 3.5 in) is *implied seating*, and it can
  be configuration-dependent (6 ft gives 3.25 in). Record the implication
  and its dependence explicitly; never publish it as an engagement.

### Retaining a web source through the corpus path

A web locator alone is not a canonical SourceRef. When a bounded search
finds a manufacturer source worth trusting, retain it the established way:
add the document entry to the owning dataset file (with title, url,
local_path and a note recording content stability), download the bytes under
`manuals/`, record the sha256, rebuild the manifest (`cli manifest`),
and ingest (`cli ingest --path ...`). Web-page HTML needs an extractor:
`extract_html` (stdlib, `html_text` origin, real `<table>` elements) exists
for this. Then the page's tables and paragraphs are canonical elements and
can anchor facts like any other source. Verify the material content is
stable across fetches when the page chrome is not, and say so in the note.

Classify each open question explicitly:

| State | Meaning and next action |
|---|---|
| Not yet inspected | A relevant source exists; inspect it or record the deferred scope. |
| Found, applicability unresolved | Retain the scoped finding; investigate the product/revision/configuration bridge. |
| Found, interpretation unresolved | Inspect the drawing or clarification needed to establish units or datums. |
| Found, conversion pending | Persist/project through the owning layer; do not call this missing evidence. |
| Found, consumer support pending | Implement or explicitly refuse the requested behavior; do not invent a source gap. |
| Not found after bounded inspection | Record searched sources/pages and the specific remaining request. |

When a discovery changes a gap, update the current coverage and handoff records.
Keep historical runs immutable and identify which earlier conclusions are
superseded. The checkpoint script verifies the declared conversion slice; it
**does not establish search completeness or adjudicate applicability**. Those
remain evidence-backed review duties in this workflow.

## Execute the stages

| Stage | Work and existing owner | Acceptance evidence |
|---|---|---|
| Scope | Identify exact model, size, colour, source editions and target contract entities. Define partial success and unsupported tasks. | Explicit applicability; replacements and family statements are scoped separately. |
| S — Sources | Reuse retained files; fetch additional sources through the existing corpus path. Preserve originals and hashes. | Actual bytes match recorded hashes; bounded coverage and uninspected leads are recorded. A web locator alone is not a canonical SourceRef. |
| C — Canonical | Reuse or run existing ingestion. Read text, canonical OCR and relevant page images; preserve page, element, region and extraction origin. Use `refs.py` to mint/resolve references. | Raw statements match their addressed edition and page region. Record ambiguous OCR or applicability as uncertainty. |
| K — Claims | Use the existing facts/table-reading import and review lifecycle. Retain original value, conditions, source, author/extractor and review state; corrections use the existing ledger. | A persisted claim exists; review projection agrees with its ledger. No generated JSON becomes a substitute claim store. |
| Authored composition | Name entities and relationships through existing dataset/authoring structures. Map required fields to claims; label authored conventions separately from measured facts. | PartType, Part, support/member references and scopes close. Counts, stock contents, nominal dimensions and installed geometry are not conflated. Unsupported mappings remain proposals. |
| P — Published | Use the existing publisher and snapshot verifier/store. Classification belongs on values; preserve exact Quantity units/raw text and source references. | Contract shape, identity, provenance and reference closure pass. Rejections/corrections appear in the actual output; source facts never point upward to generated objects. |
| Consumption, if requested | Exercise the actual consumer parser and the specific requested behavior. Compare incoming/outgoing values, classifications and unsupported fields. | Parser acceptance alone is insufficient. Distinguish knowledge access from fit, cuts, drawings, assembly sequence and purchases. Synthetic cases establish mechanics only. |
| Checkpoint | Run the bounded checkpoint below, inspect its traces and log lessons. | Explicit accepted slice, failed checks, unresolved capabilities, commands rerun and historical evidence reused. |

The current unified `claims` table is a design proposal. Use `facts`,
`fact_reviews` and the existing reading/review mechanisms where supported.
Do not create a parallel claim table for a batch. Source-supported relationships
that have no durable lifecycle or public mapping yet may be explained as
research findings, but must not be counted as a completed K→P conversion.

## Extracting assembly information (the two unblocked seams)

"Assembly information" in this repository means three different things, and
the obstacle "we cannot extract it" decomposes accordingly — structure is
authored and never extracted (Invariant 10), values flow through readings and
review, and steps flow through candidates and review. Two mechanical seams
were unblocked in 2026-09-07 after the Pembroke slice measured them:

1. **Numbered-flow steps** (`cli steps --pair-numbered --document …`). Some
   manuals — the Weatherables master guide among them — type each step NUMBER
   as its own element and each step BODY as a separate paragraph.
   `--propose` reads only `list` elements, so those flows produced nothing:
   `[measured]` 466 glyph-paired steps across 111 pages in 22 documents sat
   in this channel. `pair_numbered_flow` joins glyph and body by bbox
   overlap (closest-first-line wins — the top-most-body variant paired
   glyph `8.` with the NEXT section's heading), proposes into the SAME
   `step_candidates` queue with `proposal_basis` carrying the glyph's
   provenance, and is idempotent and non-destructive like `--propose`.
   Nothing publishes without the human review; this only fills the queue
   the review already gates.
2. **Kit/material-list tables** (`scripts/read_kit_tables.py` →
   `cli table-review --load-dir workspace/tests --pattern
   machine-read-kit-tables.json`). The corpus holds complete per-
   configuration kit lists ingested as canonical `table` elements with real
   `table_cells` (Weatherables CAD pages, Catalyst SKU sheets): `[measured]`
   18 kit-shaped tables (the 45-table figure included SKU/color matrices,
   which the shape test correctly rejects — a two-row color/SKU header is a
   catalog, not a BOM). The machine reader emits the exact `agent-read-*.json`
   shape `table_review.load_reading()` already ingests, with
   `reader_kind='machine'`, row-granular (row_label = the ITEM cell, one
   candidate row per kit line). 165 candidates now wait in the existing
   review lifecycle. The reader proposes; promotion and classification stay
   human, and composition stays authored.

What remains blocked, deliberately: a table reader will never emit a
`PanelSpec` (Invariant 10); `models[]` waits on Amendment 008; procedures
publish only after review. A future slice can bind reviewed kit-table rows
to recipes by (document, table element, row) — the machine reading made that
addressable — instead of hand-transcribing values into per-product recipe
modules.

## Autonomous execution order

A full slice runs well without user interaction when executed in this order.
Each step names its gate; a failed gate stops the line and is fixed at its
owner before the next step runs.

1. **Bind scope from the dataset first.** Before asking anyone anything,
   read the product family's dataset file: its `documents` list is the
   coverage universe, its URL patterns are the web leads, and its
   assemblies name the components. Ask the user only for what the dataset
   cannot answer (usually: which product/size, and which intended use).
2. **Inventory before reading.** List every document in the family; mark
   each inspected-or-deferred with a reason. Follow sibling URL patterns
   for the exact product page before declaring any gap.
3. **Trust ladder per value.** Text layer > HTML table > clean OCR label >
   garbled OCR (pixel-verify against sibling drawings, record the method) >
   cross-drawing arithmetic closure. Prefer evidence that closes
   arithmetically against evidence already held.
4. **Persist, then author, then publish.** Facts via the recipe import;
   composition via the dataset (counts with recorded bases; digest
   re-baselined deliberately); Parts via the normal publisher. Kit counts
   publish as Tokens; implied values record their dependence.
5. **Consumer semantics before transformer arithmetic.** Grep the consumer's
   docstrings for what each field MEANS (centerline vs edge, cycle vs count,
   handed-binding qty), check precedents in existing candidates, then write
   the conversion. Counts refuse fractional values; lengths floor with
   recorded losses; memberships pin by id, not count.
6. **Gate the snapshot on the checks.** The advance script stores its
   snapshot only when every consumer check passes, and exits nonzero
   otherwise. Then the checkpoint, the full suite, and the run log.

## Evidence tracking and the batch manifest

The manifest is orchestration metadata, not a layer. `sources` pins file paths
and hashes; `bindings` maps selected Part/spec keys to existing extractor,
fact-type and element identities. Values and review decisions are read from the
store, never copied into the manifest as another authority. `snapshot` names an
immutable existing output; `part_ids` identifies the requested slice.
`implementation_files` records the relevant recipe/publisher code in the run
receipt. `historical_evidence` explicitly identifies results not rerun.

Only the `persisted-facts-to-parts-v1` checkpoint profile is implemented. It:

1. Checks declared source bytes and frozen boundary checksums.
2. Verifies the existing snapshot and rebuilds through the normal publisher on a
   read-only database transaction; it does not store the rebuilt snapshot.
3. Compares only selected Parts against the current publisher. Unrelated changes
   do not invalidate a batch; a changed selected value requires a fresh normal
   publication, never editing an archived snapshot.
4. Joins every selected specification to an existing fact and its canonical
   element, edition and region; requires that citation in public provenance.
5. Records withheld requested Parts and succeeds for a nonempty supported slice.
   It does not claim that every requested field, model or assembly is complete.

The original-value/evidence equality check intentionally supports exact canonical
fact recipes. It reads canonical `text`, or `ocr_text` when text is empty; OCR
readings remain separately classified and are never silently promoted. A different extraction convention needs an explicit checked
profile, not silently weakened comparisons. Publication remains owned by the
normal builder; this checker does not introduce a second conversion formula.

## Bounded review and correction

One initial pass and at most two correction passes per batch revision. Inspect
from four perspectives sequentially: source applicability, layer/schema closure,
requested functionality, and an adverse case. No subagents or broad experiments
are required. Pick an adverse case that could falsify this slice: changed source,
rejected reading, correction rounding, missing reference, impossible engagement,
or purchasing credits hiding physical parts. Also challenge an evidence-gap
claim: could an image-only sheet, existing OCR, a differently named filing or
a recoverable download already contain the answer?

Where parallel agents are authorized, a five-way adversarial review paid for
itself on the Augusta slice (source applicability, schema/layer closure,
assembly/BOM logic, malformed inputs, overclaim audit). Findings it produced
that self-review missed, in rough priority order of severity:

* **Datum semantics conversions.** A value that survives a unit conversion can
  still be semantically wrong: a draft authoring bottom-edge offsets into a
  consumer centerline field put every rail 69.85 mm low, contradicting the
  same project's own earlier precedent (the Emblem's half-envelope 88.9 mm).
  When converting between dialects, check what the receiving field MEANS
  (grep the consumer's docstrings), and check it against precedents in your
  own artifacts before trusting the arithmetic.
* **Exception handling that reads as success.** `except Exception: refused`
  passes for any failure, and `all([])` passes for no result. Enumerate
  outcomes in a closed set; pass only on the exact expected failure (matched
  by type AND message start) or a genuinely populated result; treat a missing
  record as failure. Have a test simulate a foreign exception and assert it
  fails.
* **Exit-code discipline.** An advance script that stores its snapshot and
  exits 0 regardless of its own validation results turns every downstream
  honesty claim into prose. Gate `put_snapshot` on all checks passing and
  exit nonzero otherwise (the Emblem `completion_code` pattern).
* **Silent truncation in conversions.** `int(x / 1000)` on a quantity can
  turn a sub-unit count into 0 with no error. Counts are exact knowledge:
  refuse fractional values. Lengths may floor, but only with the loss
  recorded in a table a test reads.
* **Prose drift between script and report.** If a report's honesty statement
  is hand-edited beyond what its generating script produces, the next run
  silently downgrades it. The script must carry the full statement.
* **Overclaims in capability reasons.** "Consumer refuses cuts" was false —
  the resolver produced `length_unresolved=False` whenever the fit happened
  to succeed; the refusals were zero-width arithmetic, not design. Check the
  consumer's code before writing what it does; "no source states X" is false
  when the dataset's own sourced component contradicts you.
* **Small error-contract bugs that hide real failures.** Dereferencing a row
  before its `None` check turns the designed `ValueError` into a `TypeError`
  and misroutes callers. Vacuous assertions (`... or True`) pin nothing.
  Count-only probe checks stay green through renames — pin memberships by
  id.
* **Consumer-dialect traps.** Pattern-member qty is cycle-repeat semantics
  (handed edge bindings require qty 1); two stacked rows cannot be two
  pattern members (they alternate); fixings are the only channel for
  U-channel counts; a post is required for the routed-rail length path.
  Record dialect findings in the candidate's evidence, and withhold with
  structure (path, code, reason, closes_by) rather than dropping.

For each finding, record the failing check, evidence and disposition. Correct
only its owner: source acquisition/ingestion, claim review, authored composition,
or publisher/consumer code. Never repair public JSON by hand. Rerun the affected
check and its necessary dependents. Use `--round 2` or `--round 3`; the option
labels the pass and is not an automatic retry scheduler. If uncertainty remains,
close with a partial result or explicit failed transition. More evidence starts
a new manifest revision, not an endless search or an invented default.

Ask a user only the question needed for the requested capability. A supplier
contents list helps purchasing; measured installed pitch helps fitted counts;
neither is a prerequisite for answering supported identity questions. A user
answer is attributed evidence or an authored choice, not manufacturer truth or
blanket review approval. Ask early, once, with concrete options — most
everything else in this workflow is answerable without interaction if the
coverage and consumer-semantics rules above are followed.

## Run and record

From the repository root, after the slice has been imported and published using
its existing project path:

```bash
python3 scripts/check_conversion_batch.py workspace/catalog/emblem-conversion-batch.json \
  --round 1 \
  --lesson "Record the observed result, not an inferred success." \
  --propose "Record one bounded improvement for a later batch."
```

For the next batch, copy that manifest to `workspace/catalog/<batch>-conversion.json`,
replace the scope, sources, selected IDs, bindings and stored snapshot with the
actual next slice, then invoke:

```bash
python3 scripts/check_conversion_batch.py workspace/catalog/<batch>-conversion.json --round 1
```

Exit 0 means the declared partial Part slice passed. Exit 2 means a checkpoint
failed or no supported slice exists. Per-run JSON receipts and an append-only
JSONL history are written under `workspace/reports/conversion-runs/`; previous
runs are not overwritten. They contain stages, claim traces, input/code hashes,
rerun/reused checks, limitations, lessons and proposed improvements. They are
execution records, not review-ledger decisions. Inspect failure details before
selecting a correction; do not retry unchanged inputs expecting a new result.

## Representative validation

See [the Emblem run](../../workspace/reports/conversion-runs/2e2f343156444c93ac2b0a4e8854bba8.json).
Four existing draft Parts were reproduced from seven persisted readings. Source
hashes, canonical/fact/spec joins, current publisher output, stored snapshot
verification and frozen boundary checks were rerun. No source fetching,
ingestion, claim import, review mutation or consumer experiment was rerun.
Four focused tests in `tests/test_conversion_batch.py` passed.

The consumer receipt and recovered-manual reports were reused as historical
context only. Assembly prose in the earlier answer document is excluded from
this verified slice because its Claims→Published transition is unfinished.
Full FenceModel geometry/provenance mapping, physical fit and purchase inventory
remain separate limitations. This workflow does not ratify Amendment 008 or
claim that the complete model conversion has been proven.

A second representative batch demonstrates the source-coverage correction:
[Emblem drawing manifest](../../workspace/catalog/emblem-drawing-conversion-batch.json)
and [source review](../../workspace/reports/emblem-source-review/findings.md).
The retained 2022 approval's PDF page 7 explicitly names a 6×8 Emblem pre-built
panel. Its canonical OCR already existed despite empty text. Visual inspection
recovered board, rail and U-channel dimensions; nine flagged facts were projected
into three drawing-scoped Parts without changing the original exact-SKU Parts.
The batch passed its layer checkpoint and 70 focused tests. These are recorded
results from that batch, not new validation performed by editing this workflow.

```bash
# Imports the bounded drawing readings; creates no human reviews.
python3 scripts/advance_emblem_drawing.py
python3 scripts/check_conversion_batch.py workspace/catalog/emblem-drawing-conversion-batch.json --round 1
```

This second example does not prove pre-built/RTA equivalence or complete fit.
It demonstrates why source coverage must precede claims that dimensions are
missing, and why scoped publication can proceed while applicability is resolved.
