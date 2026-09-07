# Emblem instance validation against the design — 2026-09-06

**Historical G99 review.** G100 closes private board/cap identities and adds bounded
post receiving mechanics; see `emblem-blocker-progress.md` for current status.

**Result at this checkpoint: no complete Emblem FenceModel instance was valid for publication and consumption.**
This review supersedes G98's test-fixture coverage claims where stated below; it
preserves the original source-bound draft and user confirmation.

The authority is the frozen contract plus binding sections 2–3 of
`docs/integration/knowledge-datamodel.md`. `knowledge-design.md` and the four-layer
design establish ownership and provenance direction. Private consumer classes
are checked separately: their acceptance does not redefine the public contract.
Three agents reviewed schema, source/relationship semantics and adversarial
consumer behavior. Because some reviewers also implemented earlier changes, root
and a separate agent independently reproduced the key refusals and fixes. Root
also audited actual reference joins and reran the resulting checks.

| Instance or relationship | Actual result | Consequence |
| --- | --- | --- |
| Three source PDF files → recorded SHA-256 | All match the stored bytes | Source identity holds; this is not review of every interpretation |
| 26 cited SourceRefs → canonical locus/document hash | All resolve to the expected bytes | Addressing closure holds |
| Seven public draft Parts → shared PartType | All seven use valid shared types | Type vocabulary is valid, while draft status and incomplete numeric provenance remain |
| Public slot requirement → draft Part | Existing literal references resolve within the draft | This does not resolve the missing post requirement or publish any Part |
| Board base/top references → named rails | Both named supporting frames exist | Exact engagement, pocket depth and physical fit remain unresolved |
| Private requirements → private Part library | Board and cap definitions are missing | The three-Part diagnostic library is not a complete product library |
| Public `Member.joint`, `PostSlot.joint`, explicit quantity/fitting fields | Required definitions absent from actual fragments | They cannot be accepted as complete wire instances |
| Public PostSlot Joint → private consumer | Consumer silently drops it | Rail board-receiving geometry cannot substitute for a post receiving rails |
| Exact repeat quantities → integer-mm private fitter | Fractional pitch can change fitted counts if rounded first | A lossless adapter must preserve arithmetic or refuse unsupported precision |
| Exact kit → contained physical components → purchase credit | Actual candidate has no kit requirement/credit relationship | Synthetic kit accounting is software evidence only |
| Private integer quantities, joint strings and `edge_binding` → public shapes | Intentional private representation; no lossless public adapter | Do not publish the private JSON as the contract datamodel |
| Source-bound draft → generated candidate | Deterministic regeneration matches | Mutating a quantity while preserving the copied source hash is detected |
| Actual snapshot build + verify | Model remains excluded with Knowledge and Planning gaps | A valid delivery envelope is not proof of a valid Emblem model |

## Corrected defects

Cross-referencing the documents exposed a stale definition: the delegated
datamodel included `admitted_by` in published Provenance, while frozen contract
v1.1 Amendment 001 explicitly forbids that and requires `version_status`. The
mutable definition and preflight checks now follow the frozen contract. The
frozen files were not changed.

The numeric model evidence has another boundary problem: `field_evidence` lives
in a private sidecar, but the returned model would lose per-value source class,
curation level and version status. The current profile now refuses publication
even with a successful caller callback until that public provenance mapping is
defined and implemented. Citations in a sidecar are not sufficient.

The previous preflight positive fixture omitted complete Part definitions and
Member Joint, used inappropriate length rules, and reused one artificial Part
across unrelated roles. The gate also admitted same-frame or parallel-frame
support relationships and wrongly required a string version. It now checks the
missing shape/provenance/relationship conditions, uses distinct typed fixture
Parts and accepts the version scalar forms the available definitions support.
The positive test is explicitly a **preflight test with a stub semantic callback**,
not a claimed end-to-end consumer acceptance. Shared-host behavior without a
lossless mapping is refused.

The previous synthetic full-kit panels also reused hinge Part IDs for their
channel surrogates. Distinct synthetic channel Parts now make that entity role
explicit; they still do not establish physical channel cross-section fit.

The previous synthetic full-kit panels had a 20 mm residual opening. Their tests
proved accounting, not privacy coverage. New fixtures use declared synthetic
20 mm boards and assert no positive fitted openings. An explicit private
`require_full_coverage` policy is tested separately from generic truncation; it
is not silently authored into the real Emblem model as a manufacturer fact.
Independent tests also exposed empty-pattern and negative-margin bypasses.

A fixing's authored length rule was silently ignored, and an insufficient stock
length raised an unhandled `ValueError` during generation. Unsupported fixing
cut extents now refuse explicitly; stock/slot failures use `GenerationFailure`
with context. These are software correctness repairs, not new product dimensions.

## Reproducible evidence

- `emblem-instance-validation.json`: current artifact/design hashes, source-file
  checks, canonical references with JSON paths, Part and frame joins, snapshot gaps.
- `emblem-schema-review.md`: binding definitions, preflight reproductions and fixes.
- `emblem-relationship-review.md`: source-to-entity semantics and missing joins.
- `emblem-consumer-adversarial-review.md`: consumer reproductions, fixes and limits.
- `emblem-consumer-capabilities.patch`: cumulative consumer changes against the
  recorded base revision, including tests; delivery as a patch, not deployment.

Run `python3 scripts/validate_emblem_instances.py` from the repository root.
Exit 2 is expected while the real model is not admitted. It writes the complete
machine-readable audit without publishing a snapshot or changing source/review data.

The next required product inputs remain exact rail-pocket depth, board engagement,
effective installed pitch, stock dimensions and component equivalence. The next
required software boundary remains public post-host/shared-bay joint semantics,
a lossless wire adapter, and the real kit-to-component relationship. A new review
must accept the completed source-bound definitions before model publication.

## Final repository verification

The complete repository suite passes: **1,540 tests**, with one existing expected
failure (57.733 seconds). Final focused authored/publication coverage has 23 passing
tests; the instance audit adds eight passing relationship/derivation controls.
An independent reviewer reproduced the unconditional numeric-provenance refusal
with a fresh synthetic review and a callback returning success. Both frozen-file
checksums pass. The original model draft and placement confirmation were unchanged.

The 31 authored/publication/instance tests also pass using the committed snapshot
implementation, loaded in isolation from the concurrent unstaged verifier edits.
The fixes do not depend on that separate work.

Cumulative consumer patch SHA-256:
`652aba57120ba192735be6c60de8a1ece297d68520752f9ab07955237b6c00f1`.
Base revision: `9de94eb06d8e997d9be098dedd5b6a6b2eb4024d`.
The patch includes 12 files, including tests/localization, and passes reverse
apply-check against the tested checkout. No consumer deployment was performed.

Final consumer regression: **2,558 tests pass**, seven existing warnings
(71.74 seconds), including a real HTTP 422 insufficient-stock refusal test.
The 22 focused capability tests were also independently rerun; typed synthetic
channels, zero-opening fixtures and the adverse coverage cases passed.
