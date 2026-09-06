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

Forty focused purchase tests pass: 21 generator tests plus 19 example checks.
The final full suite passes **1,418 tests**, with one expected failure. Local
HTTP tests required the previously authorized run outside the socket sandbox.
The generated results and comparison report are saved under `workspace/reports/`:
[single](../../workspace/reports/emblem-single-generated-purchases.json),
[complex](../../workspace/reports/emblem-complex-generated-purchases.json),
[comparison](../../workspace/reports/emblem-purchase-generation-check.json).

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
