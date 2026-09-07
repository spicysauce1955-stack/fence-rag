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

## Execute the stages

| Stage | Work and existing owner | Acceptance evidence |
|---|---|---|
| Scope | Identify exact model, size, colour, source editions and target contract entities. Define partial success and unsupported tasks. | Explicit applicability; replacements and family statements are scoped separately. |
| S — Sources | Reuse retained files; fetch additional sources through the existing corpus path. Preserve originals and hashes. | Actual bytes match recorded hashes. A web locator alone is a research lead, not a canonical SourceRef. |
| C — Canonical | Reuse or run existing ingestion. Read text with relevant tables/figures; preserve page, element, region and extraction origin. Use `refs.py` to mint/resolve references. | Raw statements match their addressed edition and page region. Record ambiguous OCR or applicability as uncertainty. |
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
fact recipes. A different extraction convention needs an explicit checked
profile, not silently weakened comparisons. Publication remains owned by the
normal builder; this checker does not introduce a second conversion formula.

## Bounded review and correction

One initial pass and at most two correction passes per batch revision. Inspect
from four perspectives sequentially: source applicability, layer/schema closure,
requested functionality, and an adverse case. No subagents or broad experiments
are required. Pick an adverse case that could falsify this slice: changed source,
rejected reading, correction rounding, missing reference, impossible engagement,
or purchasing credits hiding physical parts.

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
blanket review approval.

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
