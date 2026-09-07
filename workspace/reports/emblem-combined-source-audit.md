# Emblem combined assembly source audit

Read-only source audit, 2026-09-07. No dimensions, human reviews, edition equivalence or assembly admission are established by this report. Pages below are one-based PDF pages.

## Sources and applicability

The three local PDF byte hashes match their canonical store records:

| Label | Local source | SHA-256 |
| --- | --- | --- |
| Manual | `manuals/freedom-outdoor-living/FREEDOM-WEB-PrivacyKit_Ready-to-Assemble-Privacy-Vinyl-Fence-Install.pdf` | `bd9303b55da9118d79918db3f786d5d62fc3ae0e4b09c5ef075b0c09e5571d24` |
| Exact sheet | `manuals/freedom-outdoor-living/73014714-6x8Emblem-White-ProjectPlanning.pdf` | `e90a649e0b96895fbc80d438132d5738f10d9b14b1669eb776a61436758f3a23` |
| Catalog | `manuals/freedom-outdoor-living/2024-Freedom-VF-Catalog-01-24_SpecialOrderCatalog.pdf` | `b26763aef9b2b9ff4f32951d7e0072aa43cc5146a45228549048e534af73570b` |

The manual is a multi-style guide, not itself an exact-SKU declaration. Exact sheet p1 elements `element-b540e75926-0016`, `-0017`, `-0018` bind the White kit description, 72-inch height / 94-inch width and model 73014714. The relevant manual branch is p4 `element-15b181bc58-0018`: full privacy excluding 8-foot-high panels. Do not import the p6 three-rail 8-foot branch.

The source-bound draft retains a 2026-09-06 retailer-to-manufacturer manual link for this exact SKU and four matching statements, explicitly assistant-supported rather than human reviewed. It records a DIFFERENT downloaded edition hash, `20a881589b9f9035b3f6e5bc6c38e80747659cd1c4df0fb0ea3558a058a33a95`. Its recorded file `workspace/catalog/emblem-linked-installation.pdf` is absent in this checkout. The present audit therefore verifies the local canonical manual and its byte content, but cannot independently recheck that external edition or broaden the draft's four-statement equivalence. This is a retained-evidence limitation, not evidence that the two manuals contradict.

## Source-to-relationship mapping

| Relationship | Source/page/element | Supported meaning and limit |
| --- | --- | --- |
| First post fixed before panel assembly | Manual p3 `element-744c97279b-0013` | Concrete and level the first post only. This does not fix both posts before insertion. |
| Bottom rail into first post | Manual p4 `element-15b181bc58-0001` | Insert bottom rail into first-post bottom route only. Receiving geometry is real, but insertion depth is unstated. |
| Two end channels | Manual p4 `element-15b181bc58-0006` | U-channels attach to two end boards; does not establish channel stock length or clearances. |
| First tongue / last groove | Manual p4 `element-15b181bc58-0008` | Bind the first-board tongue and last-board groove. First/last follow installation direction; not a global world-left/right or universal handed supplier SKU. |
| Board base seating | Manual p4 `element-15b181bc58-0015` | Insert boards into bottom rail, retaining channels on both ends; work from first installed post toward second. No numeric board engagement or installed pitch is provided. |
| Top receiving rail | Manual p4 `element-15b181bc58-0020`, branch `-0018` | Insert top rail into first post's upper route, then guide it over board tops. Supports between-frame seating concept, not a measured pocket, overlap or cut length. |
| Engage before fixing second post | Manual p7 `element-66549cef10-0009` | Completed panel enters second-post routes, THEN plumb/level and add concrete. Keeping the second post movable until engagement is an authored sequence inference directly supported by this order and first-post-only instruction. |
| Cap adhesive | Manual p7 `element-66549cef10-0011` | Glue inside cap rims then attach caps. A post/cap count does not fulfill adhesive demand. |
| Ordinary rail-insert exception | Manual p4 `element-15b181bc58-0001`; Exact sheet p1 `element-b540e75926-0008` | Manual exempts panels with 7-inch rails and 8x6 panels from aluminum inserts; exact sheet specifies 7-inch top/bottom rails. This supports the ordinary exception under the manual applicability assumption. It does not certify wind design. |
| Conditional wind requirements | Catalog p11 `element-0a5a50fd45-0001`; Manual p2 `element-efcc3971c4-0010` | Catalog distinguishes post inserts for wind-code configurations and rail inserts for 8-foot Emblem / 6-foot Everton. Do not transfer those rail kits to the exact 6-foot Emblem or claim the ordinary exception waives site-specific wind requirements. |

The source-bound draft's four `connection_evidence` texts and these canonical readings agree. Its `assembly_trace_review` correctly retains “engage second post before fixing it”; the fuller private trace is in `workspace/reports/emblem-73014714-purchase-example.json`.

## Cross-check against the combined fixture

Inspected `workspace/reports/emblem-consumer-combined-assembly.patch` and `workspace/reports/emblem-combined-assembly-fixture.json`. These explicitly describe synthetic engine fixtures and deny exact Emblem validation.

- Between-frame board seating IS tested: synthetic base/top engagement 10/12 mm, rail receiving channels, the `between_frame` rule, 1,582 mm board cuts and matching elevation extents. An overdeep top seat is a refusal case. These numbers have no manufacturer basis in the cited manual.
- End-channel binding IS tested through inherited first-tongue/last-groove configuration, first/last positions and an intentionally wrong-edge refusal. Two counted channels alone would be insufficient; the actual combined patch includes the edge binding.
- Shared-post receiving clearance IS tested geometrically for synthetic straight panels. That is static assembled-state geometry, not a proof that the installation sequence can be performed.
- The combined tests do not demonstrate an executable precedence constraint refusing `fix_second_post` before `engage_second_post`, nor a dependency requiring bottom-rail/board/top-rail completion before that engagement. The private source trace supplies the order, but it is not a published Procedure or an executed installation simulation.
- No combined style/condition test establishes the 7-inch aluminum-insert exception or protects it against the separate 8-foot/wind branch. Add source-scoped eligibility/sequence tests when those semantics cross the durable authoring path; do not add an inferred insert now.

## Contradictions and remaining limits

No contradiction found in the four requested assembly relations. The apparent “no aluminum insert” versus “wind inserts required” conflict disappears when height, product, post-vs-rail and installation regime are retained. The manual's 7-inch rail dimension identifies a branch; it is not a rail pocket depth.

There is a separate foundation ambiguity worth preserving: Manual p3 `element-744c97279b-0017` gives a frost-line example with 12 inches of gravel/filler, while `element-744c97279b-0025` instructs 6 inches. This audit does not choose a universal filler depth. The existing purchase example already identifies this gap.

The next bounded source-backed work is a private, typed precedence graph covering first-post fixation through second-post engagement/fixation, with reversal refusals and exact applicability anchors. Physical dimensions, source classification, public geometry mapping and actual Emblem fit remain independent gates. Restore or re-fetch the retained exact-SKU linked edition under its recorded hash before treating new local-manual statements as freshly cross-checked against that edition.
