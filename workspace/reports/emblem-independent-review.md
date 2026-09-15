# Independent Emblem review — 2026-09-06

Scope: source applicability, private geometry mapping, and assembly/BOM logic.
Three independent agents performed read-only reviews. The root reproduced the
semantic refusals and parser field loss and opened the two new manufacturer-labelled
Q&A references recorded in `emblem-cross-source-findings.md`.

## Findings reconciled

| Finding | Evidence / effect | Disposition |
| --- | --- | --- |
| Syntax hides semantic failure | Actual consumer refuses both zero-depth rail channels and the board's absent length rule | Preparer now executes this partial check and exits 2 while incomplete. |
| Authored fields disappear | Actual parser drops `profile_edges`, `authorship`, `cites`, `contributing_sources` | Preparer reports all four missing paths. Original candidate retains the fields. A supported mapping is still needed. |
| Default fitting can open privacy gaps | Consumer defaults to `excess=space`; reviewer diagnostic uses a synthetic 2390 mm opening and 150 mm boards, yielding 15 boards with fourteen 10 mm gaps | These are test dimensions, not Emblem dimensions. Fitting policy and effective pitch need explicit authoring before physical validation. |
| Rail dimensions need an axis-aware adapter | Source draft has rail height 177.8 mm and width 57.15 mm; consumer gets elevation face height from Part.thickness_mm | A direct key transfer loses rail face height. Neither wall thickness nor 57.15 mm should be substituted for the 177.8 mm vertical envelope. No speculative adapter value added. |
| Kit quantity differs from requirement multiplicity | Consumer multiplies fitted board count by requirement.qty | A 15-board kit must not become qty=15 per fitted board. Explicit per-member quantity and kit inventory are separate authoring decisions. |
| U-channels absent from executable model | Two per panel appear in kit inventory and installation evidence, but not in the seven Part fragments/model graph | Component BOM would miss 2 in single-panel or 14 in seven-panel layout; handed end placement also needs representation. |
| Missing specs are not all the same kind | Board width/overlap controls fitting; channel/engagement controls cut length; stock length controls supply/cut planning | Do not insist that every catalog dimension is a prerequisite for every computation, or invent a fixed Part cut length from stock data. |
| Cross-source evidence improves coverage | Manufacturer family page supports 7/8-inch boards and links exact model; manufacturer-labelled Q&A corroborates 3-inch total cut allowance | Record applicability explicitly. Newer 15-board kit transfer remains unresolved. |

## Validation scope

- Root: eight focused candidate tests pass, including real-consumer CLI refusal
  with and without the placement confirmation. Confirmed candidate still parses,
  but yields three semantic errors and four unconsumed authored paths.
- Geometry reviewer: 39 consumer tests pass; an empty Part library immediately
  refuses the missing active rail A. No-library validation skips dimensional checks.
- BOM reviewer: 54 purchase tests and two assembly adversarial tests pass.
  These do not constitute physical assembly verification.
- Single and complex kit purchase counts remain internally consistent. No
  published FenceModel, exact component BOM, or physical fit is validated here.

Consumer revision: `9de94eb06d8e997d9be098dedd5b6a6b2eb4024d`.
Current detailed checker output: `emblem-73014714-consumer-model-check.json`.
The earlier `emblem-semantic-gap-check.json` remains a historical diagnostic.
