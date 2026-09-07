# Emblem remaining inputs and safe Part mappings — 2026-09-06

Target: Freedom Emblem Privacy White 6x8, SKU 73014714. This bounded follow-up reads the actual source-bound draft, its identity anchors, earlier primary-source research and the consumer Part resolver. It does not change the original draft, its confirmation hash, source corpus or reviews. No external request was sent.

## Safe private Part definitions now

| Definition | Available evidence | Safe mapping | Must remain unresolved |
| --- | --- | --- | --- |
| Board | Project sheet p1 `element-b540e75926-0007`, cite `e00d82aba830a6eb`: 6in tongue-and-groove boards; white model row `...0016`, cite `5d7cfd7597583e43` | Existing authored ID `mfr/freedom-outdoor-living/emblem-73014714-board`, private type `infill`, colour `white`; retain exact nominal width 152.4 mm and raw 6 in in provenance sidecar | No exact individual board SKU; no executable effective width/pitch, stock length or admitted thickness |
| Cap | Project sheet p1 `element-b540e75926-0051`, cite `a437381210d0e693`: contemporary white nominal 5 in × 5 in top; adjoining `...0052`, cite `1356341c0f1a6c05`: 73013956 | Existing authored ID ending 73013956, private type `post_cap`, exact SKU predicate 73013956, colour white; retain nominal 127 mm × 127 mm with source | Nominal post size is not cap inner clearance or actual outside envelope; no fabrication/cavity dimension inferred |

These source references belong to exact project-sheet SHA `e90a649e0b96895fbc80d438132d5738f10d9b14b1669eb776a61436758f3a23`. Cap description and SKU must be joined as the same source row, not just two strings found somewhere on the page. The existing `part_identity_anchors` records precisely that association and labels it assistant-checked, not Developer-approved.

A board definition containing only supported identity/colour information closes a literal Part-reference gap; it does not close fit geometry or define a purchasable replacement product. Keep these private Parts draft. A broad white-board match must never be reported as exact Emblem product matching.

Consumer verification: `parts/resolve.py` fills `Member.width_mm` from `Part.width_mm`; `parts/model.py` reads only the `width_mm` dimension for that property. Therefore converting the manufacturer's nominal 6 in reading into runtime `width_mm` would feed nominal width into fitted counts. Preserving `nominal_width_mm` as evidence instead avoids that semantic substitution. The private matching compiler treats any copied spec as a literal `item.<key>` constraint; retaining nominal values only in a sidecar also avoids inventing a retailer catalog attribute convention.

The later Freedom manufacturer-family page supports 7/8 in thickness and links the exact model project plan, as recorded in `emblem-cross-source-findings.md`. That is positive evidence pending family-to-model applicability and admission, not evidence that no thickness exists. This follow-up does not manufacture a canonical SourceRef for an un-ingested web page or silently update the historical draft rejection.

## Purchased kit → physical components

The exact project sheet identifies **73014714 as the complete panel kit**, not as each of its rails or boards. Source-supported structure can be authored now:

- One named top rail and one named bottom rail per full panel, from the project description and full-privacy assembly sequence.
- Tongue-and-groove infill boards belong to the kit; the exact legacy-kit count remains unconfirmed.
- Two end U-channels, attached to the first board's tongue and last board's groove, from local manual p4 steps 5–6. Cites `aeaf7e66a05b4d28`, `57482180d5ddbd37`, `e856d15ed6bcbc68`; manual SHA `bd9303b55da9118d79918db3f786d5d62fc3ae0e4b09c5ef075b0c09e5571d24`.
- Posts, caps, adhesive and installation materials are separate requirements; they are not inferred to be in the panel kit simply because the planning sheet lists them.

Represent an incomplete package-membership inventory explicitly, with unresolved board count/stock lengths. Do not populate an executable `Part.contains` list with only the known rails/channels and call it a complete inventory: consumer `parts/model.py` documents that empty contents means the piece is just itself, not unknown, and executable kit credits require real quantities. The synthetic credit engine already refuses unsupported stock lengths; correct Emblem input must satisfy that guard instead of bypassing it.

Two rail positions do not prove different supplier rail SKUs or interchangeability. Maintain provisional A/B identities until the kit BOM or replacement-component crosswalk establishes either distinction or equivalence.

## Smallest useful external request

Send this to the manufacturer or supplier contact who can obtain the manufacturer's drawing; no purchase or physical sample is needed merely to ask:

> Please provide the dimensioned component drawing and kit BOM for Freedom Emblem White 6x8, model 73014714, with revision/date. We need the board's stock length, physical width, installed tongue-and-groove pitch and thickness; top/bottom rail board-pocket depths and required seating/clearance; rail stock lengths and post-end insertion allowances; and kit component quantities. If only Catalyst successor documents are available, please identify which dimensions/components are identical to 73014714 and any changes.

One applicable drawing plus BOM could settle several inputs at once. Common branding or a replacement part working with an Emblem family is not an exact component-equivalence statement. No new promising primary-source lead was found beyond the previously recorded replacement-board/U-channel crosswalks, so this pass did not repeat exhausted searches.

## If an exact labelled sample is already available

Do not buy one for this audit without deciding that separately. One unused full kit, one matching post and two mating boards are sufficient for the following evidence capture:

1. Photograph SKU/lot labels and the complete laid-out contents; count rails, boards and channels. Record any top/bottom rail difference.
2. Measure each rail's board pocket from its entry-lip plane to the internal stop. Separately measure the board's actual seated depth at top and bottom. Do not confuse either with the end U-channel depth or rail insertion into a post.
3. Measure full board and rail stock lengths before cutting. Measure board physical width and thickness. For installed pitch, join at least two boards and measure between corresponding landmarks on adjacent boards; this avoids treating overall width including tongue as coverage.
4. Record post rail-end insertion depth and any separation between opposing rail ends independently. The documented 3 in total cut allowance does not establish equal 1.5 in insertion at each end.

Each reading should include units, datum, instrument resolution and a photo showing the endpoints. A sample measurement establishes that sample; permissible engagement, thermal clearance and tolerances still need manufacturer specification or an explicitly separate design decision. This prevents sample fit from becoming an invented universal rule.

## Independent identity guard verification

The canonical store was queried read-only for the four exact project-sheet elements: `...0007` reports tongue-and-groove boards, `...0016` identifies the white panel kit, `...0051` identifies the white contemporary post top, and `...0052` is 73013956. All are on page 1 of `doc-1e71ed3bf8a5`. Their text matches the retained source anchors.

`author_identity_parts` now rejects contradictory Black-to-white normalization, malformed colour values, invalid SourceRef shapes, hashes absent from the package source list, cap description/SKU references from different source versions, and descriptions inconsistent with a white post top. These are structural and semantic consistency guards; they do not themselves fetch canonical text or establish that an arbitrary well-shaped reference quotes its addressed element. The independent canonical comparison above establishes the actual baseline.

Validation: 19 candidate tests pass, including two new methods covering 13 adverse identity mutations. Original source-bound draft and confirmation remain unchanged.

## Final bounded kit-membership and proposal check

The regenerated candidate now has five private Parts and all literal model references close. This does not make the post predicate a literal Part or establish physical fit. The membership proposal binds bottom rail 1, top rail 1, boards with count null, and end channels 2 to existing Parts. All stock lengths remain null, the cap remains separately purchased, and no executable kit requirement or purchase credit is added. The proposal remains unreviewed and explicitly blocked on inventory/stock evidence. Current candidate tests: 21 pass.

Amendment 008 and its example are explicitly pending, hypothetical and unpublishable. The example uses the recognized `ai_proposal` source class, curation level 0 and version status unknown; its two citations resolve within its own synthetic source-ref/source-doc wrapper. Those synthetic IDs and hashes are illustrative, not canonical corpus evidence. The proposal creates no manufacturer claim, accepted schema or permission to publish. No source or frozen-contract files changed in this review.

## G101 correction: minimum source geometry, not a purchase request

No purchase is required. The first useful document is a dimensioned component
cross-section applicable to exact model **73014714**. For the current authored
assembly, the unresolved nonnullable geometry includes:

| Field under model_fragment | Required interpretation |
| --- | --- |
| default_spec/frame/0/joint/channel_depth | Bottom rail board-pocket entry lip to internal stop |
| default_spec/frame/1/joint/channel_depth | Top rail board-pocket entry lip to internal stop |
| default_spec/infill/pattern/0/base_engagement | Board seating in bottom rail |
| default_spec/infill/pattern/0/top_engagement | Board seating in top rail |
| default_spec/infill/pattern/0/joint/channel_depth | Board groove receiving depth, if that is the authored Member joint; the whole Joint is currently absent |
| post/joint/channel_depth | Post receiving depth for a rail, if publishing the complete post definition |

Insertion margins can explicitly remain null with published Gaps. They must not
be zero by default. These six fields are a bounded geometry list, not a claim
that six measurements alone complete the model: effective pitch, fitting rules,
source-backed quantities and lossless provenance/consumer mapping remain.

Independent rereading of manual p4 and catalog p14 found no numerical depths or
seating amounts. The 3-inch rail cut allowance belongs to the post axis; the
replacement U-channel dimension belongs to an end accessory. Neither fills a
board pocket or groove field. Panel height and outer rail heights cannot derive
these values. A board stock length would at most constrain the sum of top and
bottom engagements, not both independently or their clearances.

Unreviewed evidence is allowed at honest curation levels under the frozen
contract. A human approval is not a substitute for these missing measurements,
and absence of approval alone is not a universal publication blocker.
