# Remaining Emblem source audit — 2026-09-06

Target: Freedom Emblem Privacy White 6x8, SKU 73014714. Independent bounded research; this report creates no reviewed facts or publication approval. Cross-checks the earlier `emblem-cross-source-findings.md` and `emblem-independent-review.md`.

## Result

The searched sources support explicit assembly relations and quantity semantics. They still do not establish exact target-SKU rail channel depth, top/bottom board engagement, effective tongue-and-groove pitch, or manufactured board length. The search is bounded, not an assertion that such documents do not exist. No numerical substitution is justified merely to make the consumer validate.

## New leads and their limits

| Source | What it supports | Admission decision |
| --- | --- | --- |
| [Barrette Product Expert, May 14 2020](https://www.lowes.com/questions/catalyst-73040830-fence-hardware-parts-and-tools/1000864280/40a8e000-aafe-5ec5-a0f9-89a49441da38) | U-channel SKU 73040830 is stated compatible with Freedom Emblem 6ft privacy fence. | Family compatibility lead. It does not identify the supplied kit channel as that SKU or establish exact legacy kit equivalence. |
| [Barrette Product Expert, August 21 2023](https://www.lowes.com/questions/catalyst-73040830-fence-hardware-parts-and-tools/1000864280/ba0b836a-26b6-5898-950f-c197a31ff3a6), corroborated [April 28 2021](https://www.lowes.com/questions/catalyst-73040830-fence-hardware-parts-and-tools/1000864280/15eec660-7d14-5704-81d6-993a98123500) | SKU 73040830 dimensions are given as 1.02 x 1.379 x 59.5 inches. | Preserve as unordered dimensions of a separate replacement product. Do not infer rail channel depth, axis assignment, or board length. |
| [Barrette Product Expert, April 1 2021](https://www.lowes.com/questions/catalyst-73040830-fence-hardware-parts-and-tools/1000864280/075cbe8b-c8c4-5a77-9c8a-a0805a0b4b3a) | Answer to inside-depth question says approximately 1.379 inches. | This is the vertical end U-channel, not the horizontal rail pocket. Cannot close either rail channel-depth blocker. |
| [Barrette Product Expert, August 14 2026](https://www.lowes.com/questions/freedom-73013949-vinyl-fencing/4008201/6551e852-1cdb-5107-ba20-4b23383ed46e) | Emblem 6x8 kits described with 15 infill boards; replacement SKU 73060329 sold in packs of 8. Page identifies kit SKU 73013949. | Corroborates newer/family inventory. Does not independently prove exact SKU 73014714 component equivalence. Per-kit count must never become requirement multiplicity per fitted board. |
| [Replacement board SKU 73060329](https://www.lowes.com/pd/CATALYST-5-ft-H-x-6-in-W-White-Privacy-Vinyl-Fence-infill-board-No-Dig-Unassembled/5019032119) | Retailer reports actual width 6.37 inches, thickness .87 inches, pack 8; overview scopes it to Catalyst Mixed Material system. | Valuable crosswalk lead, insufficient target-SKU bridge. Physical width is not effective pitch; rounded .87 is not proof of exact 7/8. Title's nominal 5ft is not manufactured stock length. |

## Rejected shortcuts

- [A community U-channel answer](https://www.lowes.com/questions/catalyst-73040830-fence-hardware-parts-and-tools/1000864280/a63bb015-e3d0-5aaf-bfe4-39230cde0380) guesses axis assignments and a .55-inch internal width. It is not a manufacturer statement and cannot reconcile a 7/8-inch board fit.
- A search returned a [municipal permit packet, page 6](https://www.bensenville.gov/DocumentCenter/View/17985/10858_Douglas_Tibble_FOIA_Complete) with a Professional Series drawing labelled 73014713 White. The indexed table ambiguously associates 73014714 with Almond. This conflicts with target identity, so its 94-inch rail-cut and other geometry readings are not transferred. The PDF was opened; a screenshot was requested, but no exact-model identity was established.
- Current branding and shared Emblem names do not prove matching manufactured components across SKU revisions. Retailer Q&A can be syndicated; inspect question wording as well as page header.
- A 3D-printed bracket result explicitly describes reverse engineering a current Catalyst rail; it supplies no manufacturer-certified exact target dimensions and is rejected.

## Assembly rules supported now

The local `FREEDOM-WEB-PrivacyKit_Ready-to-Assemble-Privacy-Vinyl-Fence-Install.pdf` was read with `pdftotext -layout`, including full-privacy steps 4–9, and checked against the prior page-image review.

1. Board length depends on its lower and upper rails. Page 4 step 6 seats boards in the bottom rail; step 7 guides the top rail over the boards. Authoring the consumer's registered `between_frame` rule with explicit bottom/top frame references follows this assembly relation. The numerical engagement and clearance inputs remain unresolved.
2. Two end U-channels are required. Step 5 attaches one to the first board's tongue side and one to the last board's groove side. This supports two ordered end assignments per panel, not an unordered accessory count alone.
3. A fitted board occurrence consumes one physical board. `qty=1` is an explicitly authored counting rule. Kit inventory and fitted board count must remain separate; the source does not define a software quantity field.
4. Privacy tongue-and-groove assembly does not justify distributed visible gaps. Author a policy that refuses unresolved pitch/overlap and requires joined coverage. A zero gap setting alone does not model overlap.
5. The [exact-SKU cutdown answer](https://www.lowes.com/questions/catalyst-73014714-vinyl-fencing/50374104/4d86e6e2-e8e0-5253-9a88-135d46ea38cd) corroborates the [linked manufacturer cutdown guide](https://pdf.lowes.com/productdocuments/54fd70b7-a336-462a-8dbf-5987a4c89506/63852631.pdf): rail cut length is finished panel span plus 3 inches total. That does not establish equal 1.5-inch end engagement, full stock rail length, or the identity of the 94-inch width datum.

Consumer `src/fenceai/fencemodel/lengths.py` was inspected: `between_frame` deliberately resolves later against placed frame geometry. Selecting its name is semantically appropriate but does not resolve missing dimensions.

## Search scope and next evidence needed

Queries covered exact SKU with board length, rail length, drawing and board count; Emblem with channel depth, infill dimensions and CAD; manufacturer domains and exact retailer expert questions. The local installation manual and earlier exact project-sheet/catalog findings were cross-referenced. Current sources need a manufacturer component crosswalk or exact dimensional drawing to establish board effective pitch and stock length, rail pocket depth and engagement/clearance. An ordered dimension triple for an end accessory cannot close those gaps.

No PDF bytes were added, no external messages sent, no ledger or source corpus changed.
