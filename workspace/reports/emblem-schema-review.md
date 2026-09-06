# Emblem schema and relationship review

Independent audit, 2026-09-06. Findings below were reproduced before corrective edits. Draft/private instances are deliberately incomplete; neither is a valid complete public FenceModel.

## Authorities

`docs/integration/knowledge-datamodel.md:107–114` defines SpecField key/agree/Quantity-or-Token; lines 148–195 require dimension Quantities; lines 257–275 define per-value Provenance; lines 499–529 define Part and FenceModel; lines 550–608 define frame/member/fitting/fixings; lines 829–835 define PostSlot; lines 926–945 define PartRequirement. Relationships are explicit at lines 1357–1378. `knowledge-design.md:38–53` requires complete locally executable hashed knowledge; lines 146–149 reserve shared schema changes to both teams. `contract.md:264–270` binds citation/source closure.

## Actual instances

- Draft model (`workspace/catalog/emblem-73014714-model-draft.json:213`) omits grade, height_support, option_axes, variants, layout_policy and assembly. Frame requirements omit qty/length_rule/overlap; frame placements and channel geometry absent. Infill lacks Member Joint/engagement/gaps/face offset and fitting policy. Post lacks requirement and Joint. These are explicit draft omissions, not acceptable publication defaults.
- Draft has seven Part fragments; its four nonempty literal requirement IDs all resolve to those fragments. Role-based post selection remains a pending private binding, not a resolved public requirement.
- Private candidate (`workspace/catalog/emblem-73014714-consumer-model.json:4`) intentionally maps Joint objects to strings, Quantity counts to integers and placement quantities to rounded integer offset_mm. Those are private mappings, not valid public wire representations. Public quantities must retain units/raw readings; the private sidecar preserves readings but does not constitute public ingestion.
- Private candidate fixings (lines 88–115) use explicit `edge_binding` with `per_panel`; public FixingRule vocabulary has `per_end_member_by_edge` but does not declare this same edge_binding object. This is a consumer extension awaiting a negotiated adapter, not a silently interchangeable public shape.
- Private component library (line 366) has only two rails and an empty-spec end channel. The model's board and cap literal IDs do not resolve within that three-Part library. Private rail type strings and bare integer dimensional SpecFields are intentionally private; public Part.type is a PartTypeRef and dimensional values are Quantities.
- Private post predicate authors role + SKU selection with no Part ID. This is a private catalog selector. The literal-Part producer profile cannot consume it; public PartRequirement prose says role is filled from Part.type, not authored (line 932). Do not present the private selector as an already valid public requirement.

## Reproduced preflight defects before fixes

Using `AuthoredModelTests.setUp()`, modify the candidate, issue a fresh synthetic accepted review using make_review(), then call run_gate() (its external validator is a stub returning []). Measured:

| Case | Result before fix | Defect |
| --- | --- | --- |
| Unmodified positive fixture | admitted | Referenced Part omitted version/type/name/authorship/source roll-up; SpecField omitted agree and complete Provenance. Member Joint absent. This tests preflight mechanics, not a valid public model. |
| SpecField `{key: made_up, value: false, provenance: {cites: [...]}}` | admitted | Invalid SpecField shape/provenance not refused. |
| Member top_ref changed to bottom | admitted | Two endpoints incorrectly refer to the same frame. |
| Infill orientation changed to horizontal while both supports horizontal | admitted | Supports no longer run across the infill. |
| Member Joint changed to `{kind: magic, channel_depth: {anything: true}}` | admitted | Joint object ignored entirely. |
| Model version changed from string `1` to integer `1` | refused | Positive integer used by both actual instances and private consumer rejected by invented string-only preflight rule. The public prose does not specify string-only versions. |

Default absent-validator admission still refuses. These defects did not establish a path where Emblem had passed full consumer validation. They do make the positive fixture misleading if described as schema acceptance and leave too much structural responsibility to an arbitrary callback.

## Required corrective direction

Complete and validate Part/Provenance shape; validate Member Joint and shared-host semantics; require distinct perpendicular supports for this framed profile; stop inventing a string-only version requirement; use distinct realistic typed Parts and clearly label the positive callback as a preflight stub. Unknown post-host semantics remain an adapter blocker documented separately in `emblem-public-adapter-boundary.md`.

## Corrective checkpoint

The preflight defects above were corrected after recording the reproductions. `fence_evidence/authored_models.py` now checks complete Part identity/type/source-roll-up fields, SpecField agreement/value and Provenance fields from the frozen contract (source_class, curation_level, version_status), Member Joint, distinct perpendicular supporting frames, and explicit shared-host unsupported behavior. Versions accept positive integers or nonempty strings because this delegated prose does not prescribe a scalar wire representation. Shared-host gap/reason are explicitly refused when populated until their semantics can execute; they are not silently ignored.

The positive fixture now uses distinct typed rail, board, post and cap Parts, explicit meaningful length-rule selection and a supported truncate fitting policy. Its test is named `test_preflight_only_requires_external_semantic_validation`: its callback is a stub, and it still proves no real consumer schema/geometry acceptance. PartType registry closure and full consumer semantics remain external validator obligations.

Measured validation: 17 admission tests pass; combined `test_authored*.py` tests: 22 pass in 1.169 seconds. A fresh malformed-model sweep replaced nested fields with seven malformed values: 1,463 cases, zero crashes. Real Emblem artifacts remain incomplete and were not rewritten to satisfy tests.

## Final publication-boundary correction

Cross-reference found a stale delegated definition: the pre-correction `knowledge-datamodel.md:260–265` put `admitted_by` in Provenance, but frozen `contract.md:102–104` explicitly excludes it, and binding obligation 6 (`contract.md:605–613`) requires source_class, curation_level and version_status on **every published value**, with policy applied by Planning at run time. The frozen contract controls. The preflight and synthetic fixture now require version_status and refuse published admitted_by. The root corrected the mutable datamodel to follow the existing amendment; the frozen contract and amendment instructions were not changed.

A separate publication defect remained even after structural corrections: field_evidence is a private JSON-pointer-to-citations map. The former successful branch returned only deepcopy(model). It neither returned that map nor supplied the required source class, curation level and version status beside quantitative model values. Retaining the complete private authoring record or a content digest does not make those fields available on the published model. Even retaining bare citations would not supply the absent classifications.

The public Quantity and Member declarations do not specify an unambiguous executable serialization of numeric Member/Joint provenance. Inventing a new Quantity.provenance member would silently introduce a shared schema. Therefore this profile now always reports `consumer_numeric_provenance_mapping_unresolved`, including when structural preflight, exact synthetic human review and the external validation callback all pass. This closes through Planning/shared boundary agreement and implementation, not by asking a curator for another manufacturer measurement.

External validation still executes for otherwise structurally valid reviewed input, so its failures remain observable. Tests now assert structural success **with publication blocked**, not a model successfully admitted by a stub. No actual Emblem model, or synthetic model, publishes through this helper until a lossless provenance mapping is implemented. Final focused validation: 23 authored/publication tests pass in 1.177 seconds, including the stale-datamodel provenance refusal.
