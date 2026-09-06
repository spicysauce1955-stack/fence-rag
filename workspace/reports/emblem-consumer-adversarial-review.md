# Emblem consumer: design alignment and adversarial review

Date: 2026-09-06. This review covers the modified Planning checkout based on
`9de94eb06d8e997d9be098dedd5b6a6b2eb4024d`, and the actual private Emblem candidate.
The consumer implementer performed this review; the root agent and the separate
`remaining_sources` agent supplied additional independent mutations. This is not
manufacturer verification or proof that the actual Emblem fence fits.

## Sources and responsibilities checked

- `docs/integration/contract.md`, obligations 8–9: preserve unsupported knowledge
  as evidenced gaps; place each physical member exactly once or report it unplaced.
- `docs/integration/knowledge-datamodel.md`, sections 3.3–3.5: FrameSlot/Member/Joint,
  profile edges, quantity and length rules, PartRequirement identity, and contained
  component coverage. In particular, a quantity of channels does not establish the
  channels' physical length or clearance around their host board.
- Planning `docs/superpowers/specs/2026-08-12-fence-model-design.md`: quantities follow
  fitting; use clear opening rather than post centre spacing; truncate leaves the
  residual, whereas trimming would require an actual cutting behavior.
- Planning `docs/adr/0011-design-and-supply-identity.md` and
  `docs/product/architecture-foundation-v0.1.md`: engineering members, purchased
  material and allocations must remain distinguishable and auditable.
- Executed the real `resolve_panel`, `validate_model`, `generate`, engineering
  demand, supply resolution, fulfillment, elevation and generation API paths.

## Findings reproduced and corrected

### 1. A successful kit-count fixture left an uncovered edge

Before correction, the full-kit positive fixture generated two panels with:

| Property | Measured result |
|---|---:|
| Clear opening | 1420 mm |
| Fitted board count × width | 14 × 100 mm |
| Unallocated residual | 20 mm |
| Last channel position | 1400 mm |

Thus its purchase and member-count assertions passed with an uncovered 20 mm edge.
Calling those tests proof of privacy coverage would have been wrong. This was a
representativeness defect in the synthetic positive fixture, not a measured defect
in the real Emblem product.

Correction: the fixture now explicitly uses synthetic 20 mm boards, synthetic
catalog data agreeing on that width, and 100 boards packaged per synthetic kit.
Each 1420 mm opening fits 71 boards; 29 remain unused kit inventory. Tests assert
zero residual and zero positive openings in addition to purchase counts and drawn
geometry. These are test constants, not Emblem source facts.

The new private `InfillSpec.require_full_coverage` policy defaults to false.
When explicitly true, it requires a nonempty pattern, positive opening, no edge
margin extending outside the opening, no uncovered edge or interior gap, and every
fitted member's entire extent inside the opening. Generic panels may still use
truncate intentionally. The policy is not inferred from a model name or silently
added to the real Emblem candidate.

Independent mutations caught and now refuse: an empty pattern with coverage true;
negative edge margins placing boards from -50 to 550 in a 500 mm opening; and a
zero-residual pattern whose excessive overlap places an intermediate board at
-10 mm. Zero residual alone was insufficient.

### 2. Insufficient packaged stock escaped as the wrong exception

Mutation: set the synthetic kit rail's `stock_length_mm` to 100. Static
`validate_model` returned no errors because the required cut is layout-dependent.
Generation then raised a raw `ValueError`. The generation route only catches
`GenerationFailure`, so this path would not produce the intended domain refusal.

Correction: capability-related runtime failures now use `GenerationFailure`.
Insufficient stock includes the slot, required cut and available stock in a
structured error. A real API test, substituting only stored fixture data and not
mocking the generator, verifies HTTP 422 with:

```json
{"code":"packaged_stock_too_short","params":{"slot":"rail","required_mm":1500,"available_mm":100}}
```

Other new runtime refusals also use the established generation exception rather
than leaking raw implementation exceptions. Static impossibilities remain checked
at model validation; layout-dependent ones are refused during generation.

### 3. A channel length rule was accepted and then discarded

Before correction, changing the handed channel requirement to
`length_rule="panel_height"` resolved it with `length_mm=None`. A stronger mutation
used a length-capable synthetic product and packaged stock length of only 1 mm:
`validate_model` still returned no errors, both channel quantities were credited
away, and no channel cut or purchase was emitted. The stock check was skipped
because the resolved target had no length.

Correction: fixing requirements with a non-null length rule are explicitly refused
by both semantic validation and direct panel resolution. The engine currently has
no fixing cut-extent implementation; it must not claim one through parsing. A
physical end-channel length still needs an appropriate authored relationship and
executable length calculation before actual Emblem fit can be verified.

### 4. A channel placeholder used the wrong Part type

The root review found that the first synthetic full-kit fixture reused a hinge Part
and its catalog SKU for the handed channel slots. That exercised generic credits
but was not an adequate positive example of an end-channel relationship.
Correction: the fixture now has a distinct `synthetic-end-channel` Part with
`type="end_channel"`, matching contained Part IDs, and a clearly synthetic
`SYNTHETIC-END-CHANNEL` catalog item. Assertions check the resolved channel role as
well as edge binding, physical quantity and purchase credit. No actual supplier
identity or manufacturer channel dimension was invented.

### 5. The new API error needed locale integration

The complete suite caught the new `packaged_stock_too_short` code missing from the
consumer's maintained refusal-code list. The code now has English and Hebrew
messages using the user's display-unit placeholder, with the existing locale
registry and unit-format tests passing. A structured API response alone was not
complete integration into the consumer UI.

## Checks that now hold

- Profile metadata survives parsing. A known tongue/groove edge cannot mate to an
  unknown or incompatible neighbor or a positive fitted gap.
- Handed bindings resolve the actual first/last fitted member and its edge, not
  merely a named slot or a label. Empty and ambiguous bindings refuse.
- Geometry credits require the exact target Part identity. Drawn rail/board and
  edge-bound channel quantities remain physical quantities; `purchase_qty` records
  the remainder to buy. Supplied contained pieces are not duplicated physically.
- Missing/short stock refuses; partial credits buy the remainder; surplus stock
  remains visible. Unsupported continuous targets and nested drawn contents refuse.
- A synthetic five-panel L plus a disconnected two-panel run generates seven
  panels and nine posts; it buys seven kits, retains fourteen rails and fourteen
  handed channels, and does not separately purchase kit boards/rails/channels.
- Editor serialization has defaults for the new geometry-credit and full-coverage
  policies; API/schema key-set regression tests remain applicable.

## Actual Emblem remains incomplete

The real candidate still explicitly records `publishable=false`,
`installation_ready=false`, and `bom_generation_verified=false`. It has authored
handed bindings, board qty=1 and `between_frame`, but lacks rail channel depth,
board engagement, complete repeat geometry, rail length rules and actual packaged
stock constraints. Its infill fitting policy is also incomplete. The new consumer
capabilities do not supply those manufacturer facts.

The private `edge_binding`, `geometry_credits`, `stock_length_mm`, and
`require_full_coverage` fields are consumer authoring extensions. They are not
proof of a complete public-contract adapter or reviewed model publication.
Handed marker placement proves an edge association; it does not prove that a
channel's interior cross-section fits over the board or that a real tongue seats
inside a groove. The synthetic profiles deliberately do not claim those dimensions.

A remaining documentation/implementation mismatch also deserves explicit tracking:
the mutable datamodel's precision discussion says repeat arithmetic consumes
thousandths, but this pinned consumer's fitter takes integer-millimetre widths.
A synthetic 2285 mm opening fits 14 pitches of 152.4 mm, but rounding the pitch to
152 mm first fits 15. This is a boundary example, not an Emblem board-count claim.
An adapter must refuse unsupported fractional repeat geometry or implement exact
repeat arithmetic; rounding first cannot establish BOM correctness.

## Validation

22 capability tests passed after the independent mutations. The separate
`remaining_sources` agent independently reran all 22 and reproduced the corrected
empty-pattern and negative-margin refusals. The real API refusal test passed.
Final complete consumer suite: **2,558 passed**, seven existing warnings,
71.74 seconds. Command: `timeout 120 .venv/bin/python -m pytest -q`, run outside
the filesystem/network sandbox so the browser-stack tests could start. The focused capability/API group passed 33 tests, and the
locale/capability group passed 69 tests after the final locale correction. No consumer commits or pushes were made.

## Exported consumer patch

- Base HEAD: `9de94eb06d8e997d9be098dedd5b6a6b2eb4024d`.
- Artifact: `workspace/reports/emblem-consumer-capabilities.patch`.
- SHA-256: `652aba57120ba192735be6c60de8a1ece297d68520752f9ab07955237b6c00f1`.
- Size: 51,074 bytes. Includes the untracked capability tests. Blank patch-context
  whitespace was normalized; `git apply --reverse --check` succeeds.
- Consumer files changed:
  - `src/fenceai/demand/derive.py`
  - `src/fenceai/fencemodel/model.py`
  - `src/fenceai/fencemodel/resolve.py`
  - `src/fenceai/parts/model.py`
  - `src/fenceai/report/elevation.py`
  - `src/fenceai/strategy/generator.py`
  - `src/fenceai/web/static/i18n/en.json`
  - `src/fenceai/web/static/i18n/he.json`
  - `src/fenceai/web/static/js/panel-model.js`
  - `tests/api/test_authoring_gaps.py`
  - `tests/web/test_locale_bundles.py`
  - `tests/fencemodel/test_emblem_capabilities.py`

The final suite initially encountered browser-stack startup errors because an
interrupted earlier run left its server/browser on ports 8800/9400. The exact
orphaned test process groups were identified and stopped before the final retry;
these were environment setup errors, not additional product-code failures.

Final complete consumer validation succeeded: **2,558 tests passed**, with seven existing warnings, in 71.74 seconds. The exported patch above matches that tested code and fixture state.
