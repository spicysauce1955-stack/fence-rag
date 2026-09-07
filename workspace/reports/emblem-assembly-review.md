# Emblem assembly check — 2026-09-07

Result: the exact Emblem assembly is not validated. The current private candidate
parses, but semantic checks refuse its missing receiving geometry. No complete
assembly or component BOM was generated.

## What was checked

The actual authored package and bound placement confirmation were rerun through
Planning's current reader and partial semantic validator. The diagnostic exits 2
as intended; see `emblem-assembly-recheck.json` and its separate candidate file.
Original authored inputs were not edited.

38 root assembly, candidate, reference-closure and adapter tests passed. These
include 80 layout transformations across single-panel and seven-panel examples.
Independent review ran 48 Planning tests: 22 Emblem capability cases and 26
post receiving-joint cases, all passing.

## Physical assembly findings

- The rail channels have no authored pocket depths. Parser defaults become zero
  in the diagnostic; zero is rejected and is not a measured Emblem dimension.
- Board installed pitch, groove receiving depth, top/bottom seating and fitting
  allowances remain incomplete. The board count and cuts cannot be validated.
- Rail-to-post engagements, post receiving geometry and shared-post clearance
  need exact-model evidence before validating adjoining panels.
- The isolated component probe resolves two end-channel requirements per panel
  (14 across seven panels). It removes edge bindings and does not prove placement
  or fit. Rail face heights in this diagnostic are rounded to 178 mm; that is
  not proof that exact public quantities survive generation arithmetic.
- Corner assemblies with receiving-post joints are currently unsupported.

## Scope of passing consumer tests

The synthetic kit fixture checks board coverage, handed channels, drawing/count
agreement and physical-component preservation under purchase credits. Its
seven-panel example has nine posts, but does not use receiving-post joints.
The separate receiving-post fixture checks rail cuts and shared clearance using
invented test dimensions; it has rails only, without boards, channels or kits.
These passes cannot be combined into a claim of complete Emblem physical fit.

Next assembly milestone: combine infill, handed channels and receiving-post
joints in one bounded engine fixture, then run the exact-model case when its
geometry and supported public mapping are available. Keep corners as explicit
refusals until their receiving geometry is supported.


## Combined fixture completed

The combined engine fixture now runs all four mechanics together for one, two
and seven straight panels. Each explicitly authored bay has 1420 mm clear
width, two 1465 mm rails, 71 boards cut to 1582 mm, and two handed channels.
Seven panels yield eight posts, 14 rails, 497 boards and 14 channels. Kit
credits preserve these components and drawings while buying seven synthetic
kits. Twelve shared-post rail-band checks each verify 35 mm remaining space.

Negative cases cover excess board/rail engagement, insufficient shared-post
clearance, wrong channel handedness, short kit stock, unsupported corners and
unfitted panel widths. Reversing a neighboring run uses the actual end
engagement and requires a different shared clearance. The successful seven-bay
case uses explicit 1500 mm station spacing; an automatically split 10500 mm
run is separately refused because its selected widths leave an infill residual.

These are test dimensions. This closes the combined engine fixture gap above,
not the exact-model evidence or public mapping gaps. Measured scenario output:
`emblem-combined-assembly-fixture.json`.

Validation: **65 related tests passed**, including 17 combined cases. Independent
review prompted exact-cut and cut-minus-one stock checks and partial kit
coverage. Consumer code is saved in `emblem-consumer-combined-assembly.patch`;
base, SHA-256 and reverse-apply verification are in its companion patch receipt.


## Source cross-reference and adversarial correction

Three independent reviewers checked sources, mechanics and assembly ordering.
All three local PDFs match retained hashes; five selected relation/condition
anchors match canonical text, edition and page region. See
`emblem-assembly-source-check.json` and `emblem-combined-source-audit.md`.
The separately linked revised manual is missing locally; its historical
applicability assertion has not been freshly verified against its bytes.

A concrete unsupported path was closed: negative tongue/groove gaps formerly
generated overlapping boards without groove-capacity geometry. Both authoring
validation and runtime resolution now refuse that case. Zero-gap profile labels
still mean synthetic adjacency, not physical tongue/groove fit. End channels
remain point fixings with unvalidated length and vertical extent.

Panel assembly tests check bottom rail→channels→boards→top rail dependencies
for1,2,7 panels and all24 input-order permutations. Each panel places75 physical
pieces; the kit container and29 surplus boards remain visibly unplaced. The
manual's requirement to engage the second post before concreting it remains
a separate installation-sequencing gap.

22 combined/sequence tests passed independent review;39 related evidence tests
passed, including refusal of changed source text, edition, region and missing
elements. Full consumer results are recorded in the source-sequence patch receipt.
