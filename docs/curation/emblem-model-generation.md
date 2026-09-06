# Emblem — model-backed purchase generation

The purchase previews now come from the model package and clean schematic
layouts. They no longer require an example containing the correct purchase
quantities or product numbers. This implements a private preview, not the
unverified Planning contract adapter.

## Inputs and generated results

| Input | Responsibility |
|---|---|
| Model scope and source identity anchors | Identify the complete panel kit |
| Frame/infill Part references and explicit kit coverage | Account for panel slots within one purchased kit |
| Post-role bindings, Part types and product identity anchors | Choose end, line or corner catalog item |
| `model_fragment.post.cap` | Choose cap, or omit caps only for an explicit null decision |
| Clean layout | Full-panel bays and schematic points; no SKUs, quantities or post-role answers |

The new `purchase_projection` metadata and post bindings are private authored
records. They are not contract Product matching or eligibility syntax. Unknown
board counts and supplier pack quantities remain unknown in output. The handed
U-channel inventory remains private until its contract Part/slot mapping is built.

| Generated case | Kits | End posts | Line posts | Corner posts | Caps |
|---|---:|---:|---:|---:|---:|
| Single standalone panel | 1 | 2 | 0 | 0 | 2 |
| Five-panel L plus separate two-panel run | 7 | 4 | 4 | 1 | 9 |

Both results match the independently authored examples and pass the separate
purchase-example checker. Output records its model-package hash and layout hash,
the originating bays/stations for every demand, Part references, citations and
pinned source documents. Source verification checks PDF hashes, canonical anchor
text, reference ownership and the source-row pairing of product descriptions
with manufacturer model numbers.

## Reproduce from repository root

```sh
python3 scripts/preview_purchases.py --model workspace/catalog/emblem-73014714-model-draft.json --layout workspace/catalog/emblem-single-layout.json --output workspace/reports/emblem-single-generated-purchases.json
python3 scripts/preview_purchases.py --model workspace/catalog/emblem-73014714-model-draft.json --layout workspace/catalog/emblem-complex-layout.json --output workspace/reports/emblem-complex-generated-purchases.json
python3 -m unittest discover -s tests -p 'test_purchase*.py'
```

The generator lives in `fence_evidence/purchase_preview.py`. It reads no prior
purchase list. Changing a cap's product identity changes the output; an explicit
null cap removes cap demand; absent cap data fails instead of inventing a default.
SKU identity comes from source anchors, never from an opaque Part ID suffix.

Independent review found and prompted guards against silently ignoring fixings,
containment/reinforcement and surface-mount intent. Conflicting kit/cap product
identities cannot merge into a bogus larger kit count. Missing source manifests
cannot claim that file hashes were verified. An actual-store negative control
pairing a description with a different product row is rejected.

The initial implementation passed 40 focused purchase tests (21 generator tests
plus 19 example checks) and 1,418 full-suite tests with one expected failure.
Current measurements are in `docs/state-and-gaps.md` G85.
The generated results and comparison report are saved under `workspace/reports/`:
[single](../../workspace/reports/emblem-single-generated-purchases.json),
[complex](../../workspace/reports/emblem-complex-generated-purchases.json),
[comparison](../../workspace/reports/emblem-purchase-generation-check.json).

## Authored quantity checkpoint

The model package now carries three `purchase_quantity_rules`: one kit per
explicit full-kit bay, one post per unique station, and one selected cap per
station. The preview requires those rules; it has no implicit multiplier fallback.
Every purchase line carries `quantity_derivations`, including the rule ID,
basis count, Quantity per basis, calculated total, evidence citations and authored
rationale. Numeric multipliers are authored interpretations: the exact source
phrases are preserved, including when the phrase does not print a numeric count.
Source identity verification does not certify the authored arithmetic as a human
reviewed fact. These are private rules, not invented contract rule syntax.

The normal snapshot path now publishes six authored Emblem family Part identities,
bringing the total to 17. Gate components are excluded. These family IDs are not
aliases for the exact white-SKU draft: one dataset rail component represents both
rail positions, and family posts span variants. Exact product binding remains
separate work. No researched dimensions are silently promoted with identity.

The next publication step remains blocked. Current `PartRequirement` documentation
groups `length_rule` as Quantity while its predecessor used named rules. The actual
consumer representation is needed, alongside the missing joint/placement and
infill fitting information. A draft status does not make an incomplete FenceModel
publishable. The audit's absent-field count is a syntactic diagnostic, not a list
of mandatory facts: it currently includes mutually exclusive requirement modes.

## Remaining integration boundary

The frozen contract assigns product matching and packaged consumption to Planning;
the datamodel's kit-credit discussion explicitly identifies consumer work. A
private preview cannot establish that this path already works in that consumer.
Accordingly `publishable`, `contract_consumer_verified` and `installation_ready`
remain false. The main snapshot builder still does not publish an Emblem model.

This implementation deliberately rejects variants, layout policies, additional
requirements and nonempty fixings/containment it cannot consume. It must not be
used as a replacement for Planning when those semantics are introduced. It also
does not derive bay count from lengths, check cuts, or prove physical/structural fit.

The next required input is the actual Planning repository. Verify its Product/kit
coverage representation and loader there, then replace private preview bindings
with the supported adapter and run these same cases through the consumer. The
repository path or URL has been requested from the user. No contract amendment
or new public kit schema was invented to bypass that check.
