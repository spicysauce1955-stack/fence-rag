# Emblem entity and relationship review — 2026-09-06

Independent source/design/code cross-reference for model 73014714. Code was read-only. Reproductions used the actual private candidate and consumer environment; synthetic mutations below are explicitly not manufacturer dimensions.

## Governing design

- `docs/four-layer-model-design.md:108–153`: references point downward; publication combines authored composition with accepted claims. Authored structure is legitimate, but a draft adapter does not create an accepted claim or reviewer record.
- `docs/target-architecture.md:276–310`: keep normalized and raw values together; a reviewed value requires a person comparing the evidence region. `:133–154` distinguishes document identity, content version, and typed document relationships.
- `docs/integration/knowledge-design.md:26–47`: Knowledge owns definitions, Planning owns instances; Parts, models, procedures and gaps publish in a pinned snapshot. `:87–105` separates authoring, review and compilation.
- `docs/integration/knowledge-datamodel.md:545–595`: frame and member geometry, fitting and quantities have distinct fields. `:665–695` establishes Slot → PartRequirement → Part → Product, and quantities come from placement, fitting or station identity. `:829–894` locates shared posts outside panels. `:1409–1425` distinguishes cited quantities from authored membership edges.

These design texts contain proposals and historical descriptions, not proof that the consumer implements every listed type. In particular, the datamodel itself warns at `:939–946` that private parser types are not a public-wire adapter.

## Source → entity → relationship

| Source assertion / anchor | Correct entity or relationship | Current implementation and limit |
| --- | --- | --- |
| Exact project sheet p1 row A, `element-b540e75926-0016/0017/0018`: kit 73014714, 72in H × 94in W | Purchased panel-kit identity and stated panel dimensions | Draft model name identifies the kit; physical rails/board have provisional authored Part IDs. This is appropriate only while these are not advertised as separately orderable manufacturer SKUs. |
| Project sheet p1 `element-b540e75926-0008`: 2¼in × 7in top/bottom rails | Two rail slot occurrences and source cross-section readings | `model-draft.json:248–269` gives two slots; private candidate `:44–65` assigns qty1 and placement. `consumer-model.json:527–532` explicitly records vertical face-height projection. The 7in value is not wall thickness, cavity depth or rail-end insertion. |
| Manual p4 step6, `element-15b181bc58-0015`, cite `e856d15ed6bcbc68`: boards go into bottom rail | Board base_ref → bottom rail; bottom rail receives board | Candidate board `base_ref`, `length_rule=between_frame` match the relation. Receiving depth and engagement remain absent; selecting the rule name does not supply its operands. |
| Manual p4 step7, `element-15b181bc58-0020`, cite `d3ce088342977ece`: top rail enters post route and is guided over boards | TWO relations: top rail receives board; post receives rail end | Candidate represents only the first receiving relationship. The source sentence must not collapse both into one rail-channel depth. |
| Manual p4 step5, `element-15b181bc58-0006/0008`, cites `aeaf7e66a05b4d28` and `57482180d5ddbd37` | One end channel at first board's tongue and one at last board's groove | Candidate fixings have explicit handed bindings. These are assembly roles, not evidence of two handed manufacturer channel SKUs. Both appropriately use one provisional channel Part ID. |
| Project sheet p1 post rows and counting key; line73045783, corner73045784, end73045785 | One selected post per unique topology station, shared by adjacent panels | Candidate post predicate implements private SKU selection by `post.kind`. It does not implement post-host receiving geometry, and it is private catalog authoring rather than a published literal-Part requirement. |
| Manual p7 step9, `element-66549cef10-0011`, cite `f67db6fc7eef1aa8` | Cap on each post, glued after assembly | Candidate cap requirement qty1 follows per-post scope. Glue remains a separate installation material; the cap requirement does not buy or quantify adhesive. |

The local exact project sheet was re-read using `pdftotext -f 1 -l 1 -layout`; the local manual's complete full-privacy steps were read in the preceding source audit. Hashes and exact source references are retained in the draft. The generic manual's applicability uses the retailer-linked edition cross-reference; it is not falsely labelled byte-identical to the local edition (`model-draft.json:1780–1789`).

## Reproduced boundaries and inconsistencies

### 1. Two different host joints remain distinct — correct draft caution, missing executable relationship

`knowledge-datamodel.md:563` defines channel depth as how deeply this slot receives another. The horizontal rail receives the board; the post receives a rail end. `:648–658` additionally places shared-host separation between rail ends at the post joint.

Draft `connection_mapping_notes` at `model-draft.json:1791–1794` correctly refuses to force routed post retention into the rail channel type. Private `FrameSlot.joint=channel` therefore must not be reported as completing the post joint.

Reproduction in the consumer environment:

```text
PostSlot.model_fields == ['key', 'requirement', 'cap']
PostSlot.model_validate({...actual candidate post..., 'joint': synthetic_joint})
'joint' in parsed.model_dump() == False
```

The synthetic Joint used depth25mm solely to detect loss. The entire object disappears without a parser error. Existing report `emblem-public-adapter-boundary.md` correctly exposes this. A source-backed post-depth value alone cannot close the implementation gap.

### 2. Buying the kit is not yet connected to the actual component graph

`model-draft.json:1924–1933` declares the user's delivery objective as purchase_complete_kits. Both original and private infill nevertheless carry `supply: components` (`model-draft.json:286`; `consumer-model.json:85`). The actual private model contains no kit requirement, packaged component inventory or requirement credits. Counting a separate preview's kit SKU is not a graph edge connecting purchased supply to these physical occurrences.

Reproduction: traversing all candidate `part_id` values found no kit requirement; changing infill supply to `assembly` and calling the real validator yielded:

```text
infill supply='assembly' is not yet supported (phase 2): resolve_panel always emits per-member component slots, so the panel would be bought as its parts rather than as one unit
```

The newer synthetic geometry-credit engine tests demonstrate infrastructure. They do not instantiate exact Emblem kit inventory/stock lengths. Do not present synthetic credits as an implemented Emblem package BOM.

### 3. The private Part library does not close all actual member references

The candidate's `component_authoring.private_parts` contains rail A, rail B and an end channel. Traversing the actual model and subtracting these IDs leaves:

```text
mfr/freedom-outdoor-living/emblem-73014714-board
mfr/freedom-outdoor-living/73013956
```

The post uses a private predicate, so it is not counted as a missing literal Part in that subtraction. This two-ID result understates full completeness requirements: post products, matching dimensions and physical board specs still must resolve. The isolated rail/channel check deliberately removes post and infill, and therefore cannot validate this relationship closure.

### 4. Historical draft search scope is superseded by later findings

`model-draft.json:1898–1899` rejects 7/8in board thickness as unsupported by inspected source pages, and `:1914` still lists board thickness as not found. Later `emblem-cross-source-findings.md` identifies the manufacturer family page linking this exact model as positive thickness evidence, pending truthful applicability/admission. Likewise `model-draft.json:1920` says an external consumer is needed, while that consumer is now available and repeatedly executed.

These are historical findings in the original hash-bound draft, not current exhaustive research claims and not grounds to silently promote the thickness to reviewed. Do not mutate the original draft or invalidate its user-confirmation hash to update this prose. This report explicitly supersedes that search scope: manufacturer-family thickness evidence now exists pending applicability/admission, the external consumer is available, and the exact-product 3in total allowance is corroborated. Stock length/datum and exact fitting geometry remain unresolved.

### 5. Rail A/B are positional authored distinctions, not established different supplier products

Both provisional rail Parts copy the same section and colour evidence (`model-draft.json:303–496`), while one fills bottom and one top. The source supports two positions and their section; it does not establish that the two stock products differ or are interchangeable. Keep the provisional identity qualifier. Do not buy two separate SKUs, unify the Parts as interchangeable, or infer distinct stock lengths without a component crosswalk. This is an identity gap, not a proven current arithmetic bug.

## Axis conversion check

The 7in →177.8mm →178mm rail mapping is correct for the private consumer geometry convention. Consumer `parts/resolve.py:209–210` gives only Member a `width_mm`, but gives frame holders `thickness_mm`; that frame dimension is used for the elevation face and receiving-face calculation. The source remains `height_mm` with the original 7in lexeme, avoiding a claim that PVC wall thickness is178mm.

The 2¼in →57.15mm →57mm conversion is arithmetically correct. In the current consumer it becomes a literal `item.width_mm` matching constraint through `parts/compile.py`; it is not applied as a frame geometry dimension. No exact Emblem retailer Product with a verified `width_mm` axis convention is present in this candidate. Therefore synthetic wrong-width rejection verifies predicate execution only; actual product-catalog axis compatibility remains unverified. I found no proven wrong numerical conversion, but treating this as a completed exact catalog match would exceed the evidence.

## What is aligned

- Counts belong on requirements/placement rules, not Part definitions. One board per fitted occurrence is separate from the unverified kit board inventory.
- Shared posts and their caps remain outside PanelSpec, avoiding per-panel double counting.
- Channel handedness is a relationship to first/last physical boards, not a fabricated handed product identity.
- Source lexemes and exact quantities survive whole-mm rail projections in the private sidecar; the sidecar does not pretend to be public consumption.
- Drafts remain unreviewed and unpublished. Source pointers demonstrate traceability, not reviewed acceptance. The generic manual's different edition is explicitly recorded.

## Required next design decisions

Complete the purchased kit → supplied components → placed occurrences relation using exact inventory and stock evidence; implement post receiving geometry separately from board-receiving rail channels; close the board/cap/post library; preserve the historical draft and carry the superseding evidence status in current reports. Then validate the actual exact model with the complete library and public adapter, followed by shared-post and kit-credit BOM checks. Further geometry guesses or syntactically valid objects cannot substitute for those relations.
