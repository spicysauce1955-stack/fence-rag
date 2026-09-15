# Proposed per-value provenance serialization for authored geometry

Status: reviewable proposal only, 2026-09-06. No shared schema was changed and publication remains refused. Companion object: `workspace/reports/authored-geometry-provenance-example.json`. Every number and source identity in that object is explicitly synthetic; none is an Emblem finding.

## Authority and procedural decision

- Frozen `contract.md:102–104` defines Provenance as cites, source_class, curation_level and version_status. `admitted_by` is expressly a run output.
- Binding obligation 6, `contract.md:605–613`, requires those classifications on every published value. A private review digest or citations-only map does not supply them to a run.
- `contract.md:51` and `:204` delegate full entity shapes to knowledge-datamodel. Its authority block, lines 16–18, makes sections 2 and 3 binding.
- Corrected `knowledge-datamodel.md:281–284` already says Provenance fragments attach to Member dimensions and other numeric values. `SpecField + Provenance` (section 3.1) and `ParameterTable.rows[].provenance` (frozen contract line 311) are concrete owner-level precedents. Quantity itself has only amount_milli/unit/value_raw; no additional Quantity member is currently specified.
- `knowledge-design.md:146–149` says neither side changes the shared schemas alone. `AMENDING.md:59–68` excludes registry additions and internals, not a new serialized owner-field map. The clarification exception explicitly says uncertainty about changed meaning must be treated as defect trigger D.

**Decision:** representing existing Provenance on owners is semantically intended, but the owner-to-field association for multiple differently sourced dimensions is undefined. There is no documented generic extension mechanism authorizing a new map unilateral publication. This proposal adds a binding wire member with consumer obligations; treat adoption conservatively as a D boundary-definition proposal requiring both sides' disposition and the applicable ratification path. Do not amend the frozen Quantity, Provenance or obligation 6 merely to prototype. If both teams disposition the exact owner representation as a delegated clarification changing no meaning, record that disposition explicitly before enabling it; the agent cannot infer that agreement from the general delegation sentence.

Frozen hash verification performed: contract.md OK; AMENDING.md OK.

## Proposed exact representation

Add the following to the delegated definition of each supported numeric owner (initially Joint, Member, Placement, InfillSpec, PartRequirement and FixingRule):

```text
field_provenance: { <relative JSON pointer>: Provenance }
```

The pointer addresses a semantic value inside that owner, not a SourceRef, metadata field or the provenance map itself. A Quantity is addressed as a whole (`/channel_depth`), never only `/channel_depth/amount_milli`. Owner-local pointers permit a future explicitly supported list element such as `/heights/0` without forcing one classification on all heights. The supported pointer set is schema-declared, not arbitrary traversal permission. This proposal does not add provenance to Quantity or change its exact thousandths representation.

Concrete example from the companion object:

```json
{
  "kind": "channel",
  "channel_depth": {"amount_milli": 25000, "unit": "mm", "value_raw": ["25 mm (synthetic)"]},
  "insertion_margin": {"amount_milli": 1000, "unit": "mm", "value_raw": ["1 mm (synthetic)"]},
  "shared_host_gap": null,
  "gap_reason": null,
  "field_provenance": {
    "/channel_depth": {
      "cites": [{"id": "synthetic-reference-for-proposal-only", "belongs_to": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}],
      "source_class": "ai_proposal", "curation_level": 0, "version_status": "unknown"
    },
    "/insertion_margin": {
      "cites": [{"id": "synthetic-reference-for-proposal-only", "belongs_to": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}],
      "source_class": "ai_proposal", "curation_level": 0, "version_status": "unknown"
    }
  }
}
```

The two provenance blocks happen to match only because this example is synthetic. Real depth and margin may come from different documents/classes/curation levels; a single Joint.provenance would falsely conflate them. Source-class policy is not applied here. An AI proposal stays level 0 and carries no admitted_by; Planning decides usability at run time.

## Exact obligations to disposition together

1. Numeric owner values must each have exactly one in-snapshot provenance association. Omission is refused or represented as an explicit missing value Gap; no owner-wide fallback silently covers unsourced fields.
2. Each pointer must resolve to a declared semantic field and match the schema's value kind. Refuse absent targets, malformed escapes, array indices outside bounds, duplicate associations, map-recursive targets and numeric metadata such as version identifiers.
3. Preserve existing SpecField.provenance and ParameterTable row provenance unchanged. Do not generate duplicate map records for their already classified values. No consumer may silently discard a map under permissive unknown-field parsing.
4. Classifications come from trusted authoring/review records with known evidence applicability. Copying a SourceDoc's class blindly is insufficient where source classification depends on the cited material. A human review must identify the actual field and image to claim level 2.
5. Every cite resolves in the snapshot and every contributed source joins its source_docs. Hash the whole published model including the map and referenced Part definitions. Private source records remain private; the classifications and references required to evaluate the model cross with it.
6. The consumer adapter must retain the map on a versioned immutable model or run evidence object and expose it when applying source policy; preserving it only in a producer sidecar does not satisfy execution. This proposal does not solve post-host geometry, shared-host gap arithmetic or handed fixing mapping.
7. Null remains missing/no supported value according to the owning field's existing semantics. Provenance does not turn null into zero, authorize an AI proposal or settle an unknown engagement depth.

## Bounded implementation after agreement

Implement a schema-declared pointer registry; a draft-to-wire serializer combining reviewed quantities with complete classifications; source-closure and pointer-coverage validation; consumer preservation and policy evaluation; round-trip tests through the real consumer; adversarial missing-target/duplicate/null/unknown-source tests. Use the synthetic example to make the review executable, then use actual reviewed source records for Emblem. No serializer was added now because no currently authorized wire extension implements this map, and a serializer targeting an unagreed shape would look more complete than it is.

## Proposed filing text

Obligation: 6 and the delegated geometry definitions.
Trigger: D — the numeric provenance obligation depends on an unspecified owner-to-field serialization when an owner has multiple differently sourced values.
Evidence: the present private field_evidence map contains only citations and is dropped by the former successful publication return; Joint/Member public shapes omit an executable per-field provenance association; actual consumer private parsers ignore unknown metadata.
Proposed change: adopt the owner-local field_provenance representation and seven obligations above without changing Quantity or Provenance primitives.
Cost: producer serializer/preflight changes; consumer map preservation, field-policy association and refusal tests.
In-flight effect: existing Part and ParameterTable provenance unchanged; authored FenceModels remain blocked until both sides agree and implement the new association.
