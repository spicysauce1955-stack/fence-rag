# Emblem BOM checkpoint — 2026-09-06

**Historical G98 checkpoint.** The subsequent datamodel/relationship review found
and repaired additional preflight and synthetic coverage defects. Current results:
`emblem-datamodel-validation-review.md`. The patch file is cumulative and has
advanced; the checksum below identifies the historical G98 patch.

Target: Freedom Emblem Privacy White 6×8, model 73014714.
This is an implementation and evidence checkpoint, not installation approval.

| Work | Measured outcome | Remaining boundary |
| --- | --- | --- |
| Assembly quantity rules | Explicit one rail per named slot, one board per fitted occurrence, one cap per station; board length rule `between_frame` tied to both assembly steps | Numeric fitting and stock dimensions still absent; authoring is unreviewed |
| Rail matching | Exact 7-inch face height and 2¼-inch width retained with source readings and declared whole-mm projections; real matching rejects wrong colour/width | Exact component identities/library incomplete; rounding is diagnostic authoring |
| End U-channels | Candidate carries first-board tongue and last-board groove bindings | Real panel cannot yet fit; count-only probe removes bindings explicitly |
| Consumer geometry and purchasing | Synthetic generation, demand, fulfillment and elevation preserve drawn rails/boards/channels while kit credits reduce purchases; stock-length and identity guards apply | Consumer changes delivered as a patch against a named revision; synthetic dimensions are not Emblem evidence |
| Authored snapshot admission | Content-bound external review, cited fields, published Parts, explicit fitting and semantic callback required; exclusion gaps retain resolved citations | CLI supplies preflight records, not trusted review import or a completed public consumer adapter |
| Exact source cross-reference | Manufacturer manual/project sheet and replacement-product leads checked independently | No established exact rail-pocket depths, board engagement, installed pitch, manufactured board length or complete component crosswalk |
| Actual publication | Dry-run succeeds and publishes actionable Knowledge and Planning gaps | `models` remains empty; no physical Emblem BOM has passed |

## Review findings and disposition

- Corrected dropped gap citations and exclusion details that gap deduplication could
  hide; page references are now minted against the cited document version.
- Review hashes cover referenced Part definitions. Duplicate Part IDs and nested
  containment are refused until transitive review binding is implemented.
- Adversarial review found missing grade/height field evidence, unsupported assembly
  and requirement containment, malformed Part specs and inactive Parts could reach
  admission. Focused negative controls now refuse those paths.
- Quantity authoring refuses conflicting existing values, conditional purchase rules,
  duplicate inventory/relations and rail dimensions inconsistent with raw inch tokens.
- Consumer review found known tongue/groove profiles could neighbour unclassified
  profiles. The consumer patch adds refusal and a negative control.
- `trim_last` was not implemented by the fitting engine. Profiled/handed direct
  resolution now refuses it, as well as unsupported extension-clip fitting, rather
  than treating a residual opening as a completed privacy panel.

The source request in `emblem-measurement-request.md` is prepared but unsent.
The public adapter boundary is separately documented: parser acceptance does not
establish consumption of the contract's post-joint semantics.

## Reproduce

From the evidence repository root, use the consumer's Pydantic-v2 environment:

```sh
/tmp/fence-planning-bom/.venv/bin/python scripts/prepare_emblem_consumer_model.py \
  --consumer-root /tmp/fence-planning-bom \
  --package workspace/catalog/emblem-73014714-model-draft.json \
  --placement-confirmation workspace/catalog/emblem-73014714-placement-confirmation.json \
  --output workspace/catalog/emblem-73014714-consumer-model.json \
  --report workspace/reports/emblem-73014714-consumer-model-check.json
python3 -m fence_evidence.cli snapshot --dry-run \
  --authored-model workspace/catalog/emblem-73014714-model-draft.json
python3 tests/run_tests.py
```

The preparation command deliberately exits 2: actual model completeness is false.
The snapshot command examines the original public draft, while the preparation
command produces a private diagnostic candidate. Neither changes the original
source package, user confirmation or fact review ledger.

## Final validation and delivery

- Evidence suite: 1,529 tests, one existing expected failure; 41 final focused tests pass.
- Consumer full suite: 2,549 tests pass, 7 existing warnings. After that run a new
  complex-layout test was added; all 15 capability tests pass. The seven-panel
  L-shaped plus detached fixture has 9 posts, 7 kit purchases, 14 physical rails
  and 14 physical U-channels, without duplicate component purchases.
- Consumer patch base: `9de94eb06d8e997d9be098dedd5b6a6b2eb4024d`.
- Patch SHA-256: `d8a1af72c44bc5ba685d99b2090bdcc8a453de0658927ec09ed43d670a6e82ee`.
- Patch includes nine files, including the new tests. Reverse apply-check succeeds
  against the modified consumer checkout. No consumer commit or deployment occurred.
- Frozen contract and amendment checksums pass; whitespace diff checks pass.
