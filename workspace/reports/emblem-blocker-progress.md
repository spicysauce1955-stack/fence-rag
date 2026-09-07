# Emblem blocker progress — G101, 2026-09-07

The source-backed private definition now closes all literal Part references.
The actual Emblem model remains incomplete; unreviewed status alone is not a publication blocker; no public FenceModel
or installation-ready BOM was published.

| Blocker | Work completed | What remains |
| --- | --- | --- |
| Missing board/cap definitions | Added typed draft Parts, board colour and exact cap SKU 73013956, with original source/provenance retained | Board effective width/stock length and cap physical fit are not inferred from nominal sizes |
| Kit-to-component relationships | Bound exact kit identity to bottom rail, top rail, board and U-channel Part IDs; kept cap separate | Board count and stock lengths remain null. No partial executable kit or purchase credits were emitted |
| Post receiving mechanics | Implemented a bounded private engine path using explicit receiving geometry and per-end engagement, shared-post clearance and consistent cuts/drawing extents | Actual Emblem values, corner/tilted/raked/through configurations and a public-wire mapping remain unsupported |
| Numeric model provenance | Filed Amendment 008 with exact proposed text and a concrete synthetic example | The proposed map remains pending. Numeric provenance is already required, but a lossless geometry association is not yet implemented; Amendment 008 is one proposed route, not proof that every model needs that amendment |

## G101: publication validity and generation readiness are different

The frozen contract explicitly permits unreviewed knowledge (section 1.4 and
obligation 6). Identity-only Part definitions and draft/retired entities are not
universally invalid. Exact purchasable SKUs, a complete supplier catalog and
successful physical fitting are generation requirements, not generic publication
requirements. Earlier G98–G100 claims that every model requires a human review,
complete active Parts, and ratification of specifically Amendment 008 overstated
the contract. Their test counts remain historical measurements.

The preflight now separates those readiness diagnostics from structural exclusions.
Optional claimed reviews remain content-bound; explicit rejection is not silently
ignored. Explicit null post, infill and insertion margins use visible gaps;
missing required fields are still errors. This correction does not invent any
Emblem geometry or turn the private parser into a publication adapter.

Three independent reviews confirmed that the missing geometry remains real.
In addition to both rail pockets and both board engagements, **Member.joint is
absent**: tongue/groove handedness is not a receiving-depth measurement. A complete
post definition also needs its own rail-receiving depth. These are different
axes and hosts. Post:null is legal no-opinion knowledge, but dropping required
posts would not complete the user's Emblem BOM.

The datamodel already requires provenance on Member dimensions. It does not
explicitly declare a multi-value owner.provenance association. The actual private
parser discards citations and authorship. We therefore retain the lossless-mapping
refusal, without claiming that our proposed pointer-map amendment is the sole
possible solution. No controlled boundary file or source claim changed.

## Identity and source verification

The private library now contains five draft Parts: two rails, a board, a cap and
an end channel. Existing literal model requirements resolve to them. Post selection
is still a separate station-scoped predicate, not a newly invented literal identity.

The board's 6-inch nominal width remains 152400 thousandths of a millimetre in the
source sidecar, never substituted for the consumer's effective `width_mm`. Cap
nominal 5×5 dimensions are not an internal clearance or measured outer envelope.
The cap selector uses the same-row manufacturer model number 73013956 and white
colour. Canonical project-sheet text was independently checked. Guards refuse
contradictory colour lexemes, malformed/mismatched references and wrong cap identity.

Four source-bound kit membership groups preserve 1 bottom rail, 1 top rail,
unknown board count and 2 end channels. This is an authored private relationship
plan, not a new public `contains` schema or executable partial kit. The cap is
purchased separately; one board per fitted occurrence remains separate from the
number of boards inside a supplied package.

The original draft and placement confirmation remain unchanged. The generated
candidate has a new content hash and reproduces from those checked inputs.

## Stronger actual-instance diagnostic

The consumer validator now also runs against in-memory copies of all five draft
Parts. Their stored statuses remain draft. This exposes previously skipped
Part-dependent failures: effective board width is absent and the channel spec is
empty. The empty diagnostic catalog also produces expected no-eligible-product
failures; those are not findings that the manufacturer lacks products. Both rail
pocket depths remain unresolved. This is a failing diagnostic, not model approval.

## Receiving-joint scope and independent review

Supported: explicit level, horizontal, individually placed rails meeting plumb
end/line posts, with known outside face widths and explicit start/end engagements.
Cuts add both engagements to clear opening; drawing extents use those same values.
Shared clearance is checked by physical station and world-height relationship.

Independent review found and corrected tilted-host handling, an ineffective
width mutation, and a cross-row collision where different rail thicknesses allowed
diagonal overlap despite individually valid same-height clearances. Unsupported
staggered/crossing bands refuse. Private geometry fields do not create public
FrameSlot engagement fields; no symmetric split is inferred from a total allowance.
See `emblem-post-receiving-independent-review.md` and the consumer implementation
report for the precise bounded behavior.

## Help that would unblock the remaining work

1. Obtain an applicable manufacturer component drawing and kit BOM for **73014714**,
   including rail pockets, required board engagement, effective board pitch,
   stock lengths and kit quantities. The concise request and sample-measurement
   procedure are in `emblem-remaining-inputs.md`. Nothing has been sent externally.
2. Have the Knowledge and Planning owners review
   `docs/integration/amendments/008-authored-geometry-provenance.md` and its synthetic
   example. This is a concrete proposal, not a claimed agreement. Frozen
   `AMENDING.md` §3 requires recorded acceptance from both teams before ratification;
   the current contract remains in force.

A physical sample can establish sample measurements. Manufacturer tolerances and
required thermal/engagement allowances still need applicable specifications or an
explicitly separate design decision. No sample, review or missing dimension is
fabricated by this implementation.

## Validation

G101: full evidence suite **1,553 tests pass**, one existing expected failure
(56.279 seconds). After the final conflicting-review regression was added,
**30 focused authored-model/publication tests pass**, including an independent
adversarial rerun. The actual instance audit resolves **26 canonical SourceRefs**
and still reports complete_model_admitted=false. Frozen contract hashes pass.
No consumer code changed in G101; the consumer measurements below are G100.

Historical G100 evidence suite: **1,547 tests pass**, one existing expected failure (58.828 seconds).
After adding the Part-aware diagnostic, all **21 candidate tests pass** again.
Independent source/kit checks and instance graph tests pass. Consumer full suite:
**2,584 tests pass**, seven existing warnings (73.39 seconds). Consumer changes are
saved as a cumulative patch against the recorded base, not deployed.

Cumulative consumer patch: `emblem-consumer-capabilities.patch`, based on
`9de94eb06d8e997d9be098dedd5b6a6b2eb4024d`; SHA-256
`458d55806fa8fb8d04350666f06c9570c878ac406c1eb3d53be4f68ef416cc6d`.
It includes 14 files and passes reverse apply-check. Public PostSlot.joint input
now refuses explicitly instead of being silently discarded; this is not a wire
adapter. Both frozen-file checksums pass. This checkpoint is committed in the
evidence repository; the consumer changes remain a patch and local tested checkout.
