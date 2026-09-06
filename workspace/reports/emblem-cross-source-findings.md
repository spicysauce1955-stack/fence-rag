# Emblem cross-source findings — 2026-09-06

Target: Freedom Emblem White 6x8, model 73014714. Research findings only;
no extracted facts, ledger reviews or published model values are created here.
URLs were opened and their contents inspected. No PDF bytes are added to Git.

## Useful evidence

| Candidate | Source and locator | Applicability and remaining work |
| --- | --- | --- |
| Board thickness 7/8 inch (22.225 mm); nominal width 6 inches | [Freedom Emblem page](https://freedomproduct.com/products/emblem-vinyl-fencing/), Features & Specifications | Manufacturer family assertion. The same page links the exact 73014714 White 6x8 project plan below. Stronger than the previously rejected legacy dataset reading; suitable for an explicitly authored family-to-model applicability decision. Does not establish effective coverage or stock length. |
| Exact SKU identity, 72 x 94 inch panel, 2-1/4 x 7 inch rails, selected post SKUs | [Manufacturer project plan](https://freedomproduct.com/wp-content/uploads/2022/10/73014714-6x8Emblem-White-ProjectPlanning-VinylFence-ReadyToAssemble.pdf), page 1 | Confirms existing readings. Live remote edition includes preassembled gates; do not assume it has the same hash as the local PDF. |
| Cut rails 3 inches longer than finished panel width | [Freedom cutdown guide](https://pdf.lowes.com/productdocuments/54fd70b7-a336-462a-8dbf-5987a4c89506/63852631.pdf), page 1, Reducing Width | Linked as Dimensions Guide by the exact SKU retailer page below. Supports a scoped cutdown rule. Does not independently prove stock rail length, equal 1.5-inch insertion at each end, board engagement depth, or that the project sheet's 94 inches uses the same width datum. |
| 2 decorative rails, 15 boards, 2 U-channels | [Catalyst Emblem manual 34118672 REV 5.25](https://www.catalystfence.com/wp-content/uploads/CAT-BOM-34118672-EmblemPanelKit_5-25.pdf), page 2; Spanish table page 8 agrees | Explicit manufacturer family kit inventory; transfer to legacy SKU 73014714 still requires revision/component equivalence. No board count inferred from panel width. Text inspected; web screenshot retrieval failed. |

## Identity checks and rejected transfers

- [Exact retailer page](https://www.lowes.com/pd/freedom-actual-6-ft-x-7-82-ft-ready-to-assemble-emblem-white-vinyl-flat-top-vinyl-fence-panel/50374104)
  still identifies model 73014714, item 667016, now under CATALYST branding.
  Its documents include the cutdown guide above, a matching exact-model
  [planning sheet](https://pdf.lowes.com/productdocuments/88d53cdf-fb94-4d49-8460-aad844db4391/63852401.pdf),
  and the previously inspected generic Freedom installation manual. This is a
  document applicability link, not proof that all current Catalyst parts are identical.
- [Current Catalyst Emblem page](https://www.catalystfence.com/fence/emblem/)
  links Shop Now to [model 73058414](https://www.lowes.com/pd/CATALYST-Emblem-6-ft-H-x-8-ft-W-White-Privacy-Vinyl-Flat-top-Fence-panel-Unassembled/5016152027).
  That retailer page claims compatibility with 73013949, not explicitly 73014714.
  Do not infer transitive component identity from the common Emblem name.
- The current manufacturer's link labelled Emblem Vinyl Instructions opens
  [Manchester composite instructions](https://www.catalystfence.com/wp-content/uploads/Manchester_Composite-Pre-Built-Instructions_CAT26-D-668873.pdf).
  Rejected for this model based on the PDF's own title and product applicability.
- Retailer structured attributes include zero pickets for the target privacy
  panel and 21 rails for the newer model. These fields cannot supply assembly
  quantities without corroboration. The manufacturer kit table is stronger evidence.

## Remaining gaps and next useful step

Independent review added two manufacturer-labelled Q&A cross-checks:

- [Barrette Product Expert, June 12 2020](https://www.lowes.com/questions/catalyst-73014714-vinyl-fencing/50374104/4d86e6e2-e8e0-5253-9a88-135d46ea38cd)
  repeats the 3-inch total rail allowance. An adjacent community answer instead
  adds 3 inches at each end; that conflicting community transfer is rejected.
  This strengthens the exact-product cutting-rule interpretation, not a stock
  rail length or board seating depth.
- [Barrette Product Expert, February 13 2024](https://www.lowes.com/questions/catalyst-73045783-vinyl-fencing/1002750242/00aa6589-baed-503a-8180-aa35010f58f4)
  answers a question explicitly naming 73013949 and 73014714 by distinguishing
  in-store and online availability and confirming post 73045783 compatibility.
  This is useful identity context, but does not explicitly certify internal
  component equivalence or establish a bridge to newer SKU 73058414.
  The question's text matters: retailer Q&A is syndicated across product pages.

No numerical rail channel depth, board-to-rail engagement, effective board pitch,
or manufactured board length was found in the inspected sources. This is a
bounded search result, not a claim that no such source exists.

First capture the Freedom family page and its exact-model link with content
hashes and source references, then author the applicability of its 7/8-inch
board thickness to this model through a truthful review path. Separately pursue
the revision/component crosswalk for the newer manual's 15-board inventory.
Manufacturer CAD resources are a further lead; no exact Emblem drawing was
established in this pass. User measurements should follow these source checks,
not replace them prematurely.
