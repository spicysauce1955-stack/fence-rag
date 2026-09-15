# Augusta 8x6 source review — 2026-09-07

Bounded coverage record for batch `augusta-drawing-001` (run metadata, not a
claims store). Target product: Weatherables Augusta privacy panel, 8 ft tall ×
6 ft wide configuration (CAD drawing title "augusta 8x6 privacy").

## Inspected candidates

| Candidate | Path | SHA-256 | Inspection | Disposition |
| --- | --- | --- | --- | --- |
| Augusta 8x6 privacy CAD | `manuals/weatherables/structural/weatherables-cad-augusta-8x6-privacy.png` | `88612b32…` | Canonical OCR (22 labels, mean conf 32.19); diagnostic re-OCR at 3×/6× upscale + region crops (psm 7/8/11); pixel comparison with sibling CADs | Rail callout `1.5" x 5.5" x 71.5"` (top+bottom labels); right-side chain 5.5+39.5+5.5+39.5+5.5 = 95.5 = left-middle overall height; top-center `72"` (pixel pattern of a seven at the 8x8's clean `96"` template position); `U-Channels` component label |
| Augusta 8x8 privacy CAD | `manuals/weatherables/structural/weatherables-cad-augusta-8x8-privacy.png` | `b4fd78f2…` | Canonical OCR (28 labels); top-label pixel comparison | Same rail profile `1.5" x 5.5"` at 95.5" length; clean `96"` width label; same 39.5" sections — corroboration only, not absorbed into the 8x6 scope |
| Augusta gate 44.5in CAD | `manuals/weatherables/structural/weatherables-cad-augusta-gate-44.5in.png` | `a0cf3df5…` | Canonical OCR (18 labels) | Same family rail/U-channel pattern; not in 8x6 scope |
| Master installation instructions 2024 | `manuals/weatherables/weatherables-fencing-master-installation-instructions-2024.pdf` | `db02aeee…` | Text layer read (pages 5–10) | `1.5" U-Channel slides on the T&G picket` (p9) — family-level statement used for the U-channel width spec with declared family scope; three-rail flow corroborates the 8x6 section chain reading |
| Privacy fencing specsheet | `manuals/weatherables/weatherables-privacy-fencing-specsheet.pdf` | `87dea78b…` | Text layer read (page 1) | Augusta™ name column-paired with `Picket Style: 7/8" x 6" / Tongue & Groove .060" / Height: 6',7' & 8' / Width: 6' & 8'` — picket spec source |
| Fencing brochure | `manuals/weatherables/weatherables-fencing-brochure.pdf` | `cb90e6a2…` | Text layer read (pages 7 and 15) | Identical Augusta name/spec pairing (p7) — positional pairing twice-observed; `posts for the Augusta fence will have 3 route holes` (p15, also identically in the full-line catalog p15) corroborates three rails |
| Full-line catalog 2026 | `manuals/weatherables/weatherables-full-line-catalog-2026.pdf` | `505726ef…` | Text layer read (page 7) | Same pairing; `65 lb` average panel weight (not published — no clear per-panel-component attribution) |
| weatherables.json dataset | `data/weatherables.json` | — | Assembly graph read | No Augusta assembly entry exists; membership authoring remains open (not forced in this batch) |

## Interpretation notes

- The CAD raster is a dimensioned drawing (labels are dimension callouts), so
  no NTS inference was needed. No dimension was measured from pixels; pixel
  comparison only disambiguated OCR character readings (`72"` vs `12"`).
- The `72"` reading is the panel's nominal width label; the rails' 71.5" is the
  rail stock/callout length. They are kept as separate facts and neither was
  published as installed geometry or a cut allowance.
- Picket-run segments (39.5") are installed-run extents, not picket stock
  lengths; persisted as flagged facts, deliberately not projected onto the
  picket Part.

## Uninspected / deferred

- `weatherables-cad-pembroke-6ft-privacy.png`, `captiva-*.png`, remaining
  Weatherables manuals (2/3/4-rail, crossbuck, weathergrain, post-mount,
  premium gate, triwest reference): unrelated to the Augusta 8x6 question or
  deferred; not negative evidence.
- Retailer pages / manufacturer website CAD download page: the retained CDN
  copy matches the local bytes' provenance record in
  `data/structural/weatherables-structural.json`; no additional exact-SKU
  statement was sought because no exact SKU is claimed by this batch.

## Adverse checks performed

- Changed anchor OCR → import refuses (test).
- Forged `review_status` without ledger record → publication refuses (test).
- Correction losing milli-mm precision → refused (test); exact corrections
  change Part version.
- Rejected reading → spec withheld, Part persists with remaining specs (test).
- Full-suite regression: 1,608 tests, 1 pre-existing expected failure
  (documented latent page-image collision, unrelated to this batch).
## Assembly slice — 2026-09-07 (batch augusta-assembly-001)

Conversion-work-pending distinctions (not missing evidence):

- **Membership and counts**: `data/weatherables.json` gained the authored
  `wea-augusta-privacy` assembly (post, slotted rail, T&G picket, U-channel)
  with per-panel counts 3 rails / 2 U-channels, each with its recorded basis
  (CAD section chain + brochure route-hole note + master-install mid-rail flow;
  first/last-picket u-channel instruction; the u-channel count 2 stated in this round was superseded to 4 installed segments below). Picket and post per-panel counts
  are absent by design: the sources state none. Digest re-baselined
  deliberately after the edit; `master-dataset.json` regenerated.
- **Assembly sequence**: step candidates proposed mechanically for the master
  installation guide (`cli steps --propose`); 20 candidates await human review
  on 6 pages. Nothing publishes without review; the snapshot carries explicit
  `steps_awaiting_review` gaps naming each page. Only `list`-typed elements
  yield candidates (the flows' paragraph elements are out of the splitter's
  scope — a known, measured limitation that the review queue makes visible
  rather than hiding).
- **Model candidate**: `workspace/catalog/augusta-8x6-model-draft.json`
  authors frame/infill/fixings with all receiving geometry as explicit nulls;
  rail placements are drawing-derived authored choices (CAD section-chain
  boundaries, datum unconfirmed). The preflight excludes it honestly: 11
  invalid_quantity refusals are the missing receiving geometry itself, plus
  the unresolved numeric provenance mapping (Amendment 008 pending). Three
  model gaps publish in the snapshot with correct owners (knowledge/planning).
- **Consumer behavior validated** in the consumer's own environment
  (`/tmp/fence-planning-bom` venv): composition Parts ingest; draft value Parts
  stay inactive; the consumer-dialect candidate parses and `validate_model`
  refuses EXACTLY the undeclared geometry (5 refusals: 3 channel rails, 2
  groove members) and nothing else — negative assurance that fitted
  dimensions/cuts cannot be silently produced. The producer-dialect draft is
  refused by the consumer parser (6/6 checks green).
- Post selection is authored as no opinion: sources state no Augusta post
  identity/geometry beyond the brochure route-hole note; a composition-only
  Part cannot satisfy the model profile's citation requirement, so the model
  fragment carries `post: null` with a recorded reason instead of an
  invented post.

## Correction round — consumer fidelity (2026-09-07, batch augusta-assembly-001)

Three review findings, fixed at their owning layers:

1. **Unit corruption (transformer)**: draft Quantities carry integer
   milli-mm; the consumer `Mm` is integer mm. Offsets now convert by exact
   division (a non-whole millimetre refuses instead of corrupting); verified
   `[0, 1143, 2286]` mm in the parsed consumer model. The height field name
   is fixed (`heights_mm`) and the 95.5 in = 2425.7 mm value floors to 2425
   with the 0.7 mm loss recorded in `transformation_evidence`, never silent.
2. **U-channel count (dataset)**: corrected 2 → **4 installed channel
   segments** — the master-install mid-rail flow places channels on the
   first and last lower-run pickets and repeats the process above the middle
   rail. Purchase-stock quantities are recorded as a separate, unstated
   question. Digest re-baselined; draft fixing count updated to 4 with the
   two-run basis.
3. **Stacked rows (consumer capability)**: the consumer's `fit_pattern`
   repeats one member cycle along one axis — two stacked rows between
   different rail pairs are inexpressible (two pattern members would
   alternate across the width). The candidate now carries only the lower
   run, with the upper run recorded as an explicit consumer-capability
   limitation in both `transformation_evidence.withheld_from_consumer_shape`
   and `limitations`. Proposed improvement: consumer support for per-row
   base_ref/top_ref span derivation.

The consumer probe additionally exercises the real `resolve_panel` on a
synthetic bay: it refuses with "member pattern never advances: widths [0]"
because the draft picket Part is inactive and dimension-less to the resolver.
That refusal — not the earlier parse-only checks — is what demonstrates the
boundary between validated parsing and validated assembly. The report now
carries an explicit `consumer_validation_scope` statement separating what is
proven (ingestion, unit fidelity, honest refusals) from what is not and cannot
be proven yet (assembly, fitting, quantities).

## Probe discipline correction (2026-09-07, batch augusta-assembly-001)

1. **Exception handling**: `panel_resolution_behaves_as_declared` previously
   treated any exception as a declared refusal. The probe now classifies the
   outcome: only `ValueError('member pattern never advances: widths [0]')`
   (the dimension-less inactive draft Part) counts as the expected refusal;
   the resolution record carries `error_type` and
   `expected_dimensionless_draft_refusal`, and any other exception fails the
   check. An adversarial test simulates a foreign `TypeError` and asserts it
   reads as failure.
2. **Upper-row withholding**: the prose limitation became a structured
   `withheld_mappings` entry (`/model/default_spec/infill/pattern/picket_upper`,
   code `consumer_infill_single_cycle`, reason, would-close,
   `closes_by: planning`) plus a `mapping_completeness` invariant — mapped +
   withheld == draft members — enforced by the transformer (refuses on
   violation) and by two tests. Neither row is silently dropped nor
   mis-modeled.
3. **Capability claims**: `capability_validation` carries explicit
   `validated: false` flags with reasons for assembly, fitting, cutting and
   purchasing; the consumer probe re-verifies all four from the candidate
   file (`unvalidated_capabilities_marked`). The report's
   `consumer_validation_scope` names exactly what is proven (ingestion,
   dialect fidelity, mapping completeness, honest refusals) and what is not
   (assembly, fitting, cutting, purchasing — unvalidated until receiving
   geometry and step reviews exist).

Snapshot unchanged (`7508f4e7…`); 12/12 consumer checks; 21 focused tests;
full suite 1,625 OK (1 pre-existing expected failure); checkpoint round 3
`partial_knowledge_verified`.

## Resolver-check rebuild (2026-09-07, batch augusta-assembly-001)

The panel-resolution check had two escape paths: a missing record (probe never
reached the resolver) passed via `not {}.get('refused')`, and an empty resolved
result passed via `all([])`. Rebuilt as a **closed enumeration**:

- `outcome` is exactly one of `resolved`, `expected_dimensionless_draft_refusal`
  or `unexpected_error`, and never absent.
- The check passes ONLY on: the exact dimension-availability refusal —
  `ValueError` startswith-matched to `'member pattern never advances:
  widths [0] with gaps [0]'` (the resolver refusing to invent dimensions for a
  dimension-less Part) — or a genuinely computed nonempty slot list whose
  entries all carry integer `length_mm`.
- Missing records, unexpected errors, unknown outcome keys, empty slot lists
  and non-integer lengths all FAIL.

Adversarially verified by mutation: an empty-pattern candidate and a probe
serialization defect (`'ResolvedSlot' object has no attribute 'key'` — fixed
to `slot_key`) now FAIL the check where they previously passed or crashed. A
frame part-id mutation is indistinguishable at the infill stage (the frame
stage tolerates it), which is the honest limit of the assertion; the check's
`asserted_outcome` states it: the refusal proves the resolver invents no
dimensions — it does NOT evaluate receiving geometry, assembly, fitting,
cutting or purchasing (capability_validation keeps all four validated=false).

Full suite 1,625 OK (1 pre-existing expected failure); 12 focused tests;
12/12 consumer checks; checkpoint round 3 `partial_knowledge_verified`.

## Five-way adversarial review and fixes (2026-09-07, batch augusta-assembly-001)

Five adversarial reviewers (source applicability; schema/layer closure;
assembly/BOM logic; malformed inputs; overclaim audit) attacked the slice
read-only. Their confirmed defects and the fixes applied at owning layers:

1. **Centerline datum (BOM reviewer, CONFIRMED)** — the draft authored
   bottom-edge offsets into the consumer's centerline `offset_mm` field
   (every rail 69.85 mm low; inconsistent with the Emblem precedent's 88.9 mm
   half-envelope). Fixed: the draft now authors CENTERLINES in exact milli-mm
   (69850/1212850/2355850); the transformer floors to whole mm with each loss
   recorded (69/1212/2355, 0.85/0.85/0.85 mm); `placement_datum` records the
   convention and the Emblem parallel.
2. **Exit-code discipline (overclaim auditor, CONFIRMED)** — the advance
   script stored the snapshot and exited 0 even with failed consumer checks.
   Fixed: `put_snapshot` is now unreachable when any check fails; the script
   writes an ABORTED report, exits 2, and `snapshot_stored`/`
   `consumer_checks_passed` are recorded. Verified live: a failing check
   aborted the run with exit 2 before this fix's final green rerun.
3. **Rail length rule (BOM reviewer, CONFIRMED as latent)** — rails slide
   into routed post sockets, but the consumer's routed path needs a
   `PostSlot.receiving_joint` the candidate cannot author (no source states
   socket depth); `clear_between_posts` alone undercounts the known 71.5 in
   stock. Fixed as recorded limitation (no invented engagement), in
   `limitations`, `capability_validation.cutting.why`, and a test.
4. **"Cuts refuse" overclaim (BOM reviewer, CONFIRMED)** — between_frame
   resolves face-to-face with `length_unresolved=False` when the fit happens
   to succeed; refusal was arithmetic luck. Fixed: capability reasons now
   say "a resolved between_frame length today is face-to-face only, not a
   seated-piece cut".
5. **Post-omission reason (BOM reviewer, CONFIRMED)** — "no source states
   Augusta post dimensions" contradicted the dataset's sourced post
   component. Fixed: the reason is now "no post Part with citable values
   exists; socket depth and SKU identity are unstated".
6. **U-channel centre-dot placement (BOM reviewer, CONFIRMED as
   representation defect)** — per_panel qty 4 drew four channels at the
   panel centre. Fixed: two Emblem-shaped edge_binding handed fixings
   (first/tongue, last/groove) for the mapped lower run; the upper run's two
   segments are withheld with it; count completeness enforced
   (mapped 2 + withheld 2 == authored 4).
7. **Anchor None-guard (two reviewers, CONFIRMED)** — `_anchor_rows`
   dereferenced before the None check (TypeError instead of the designed
   ValueError). Fixed; test added.
8. **Silent count truncation (malformed-input reviewer, CONFIRMED)** —
   `int(x/1000)` on quantities could zero a sub-milli count. Fixed: counts
   convert by exact division and REFUSE fractional values; test added.
9. **Legacy duplicate rows (malformed-input reviewer, OBSERVATION)** —
   duplicate v1 rows accumulated silently. Fixed: refuse, matching the
   current-extractor invariant; test added.
10. **Vacuous test assertion (malformed-input reviewer, CONFIRMED)** — the
    `or True` line in the fixing-count test asserted nothing. Removed;
    the test now pins the edge-binding shapes and the dataset basis.
11. **Stale "2 u-channels" (two reviewers, CONFIRMED)** — the advance
    script's hardcoded report text. Fixed to 4 installed segments across two
    runs with the purchase-stock carve-out.
12. **Brochure page citation (source reviewer, CONFIRMED)** — the
    route-holes note is on brochure page 15 (element-a2afc337cb-0021), not
    page 7; also present identically in the full-line catalog p15. Findings
    row corrected.
13. **Membership-pinned probe checks (malformed-input reviewer,
    OBSERVATION)** — count-only checks would stay green through a rename.
    `draft_value_parts_inactive` now pins the three expected IDs.
14. **Upheld by falsification (source reviewer)** — the 72" reading,
    8-tall x 6-wide orientation, rail callouts, three-rail chain closure,
    4-segment U-channel interpretation, family-level 1.5" designation, and
    the twice-observed positional spec pairing all survived independent
    re-OCR, glyph-pixel, and drawing-geometry attacks; the geometry attacks
    corroborated the readings (72.0 in scaled from the 95.5 in line).
15. **Upheld (schema reviewer)** — composition Part shape, integer
    versions, dual-source u-channel provenance, registry-addition blast
    radius (no unrelated gaps closed; 0 existing parts changed), frozen
    boundary integrity, Emblem non-interference, and manifest correctness
    all verified programmatically.

Note (overclaim auditor): the `consumer_validation_scope` text in the
previous report version had been hand-updated beyond what the committed
script could reproduce; the script now carries the full statement and the
report is regenerated by the script on every run, closing that drift. The
snapshot `7508f4e7…` is unchanged by these fixes (the corrected artifacts are
unpublished diagnostics; published Parts, gaps and provenance are identical).

Verification: 27 focused tests (6 new adversarial-hardening tests), full
suite 1,631 OK (1 pre-existing expected failure), 12/12 consumer checks,
advance exit 0 with the gate live.

## Gap-closing round (2026-09-07, batch augusta-assembly-001 revision)

Missing-data inventory across the converted datamodels, and what closed:

### Closed from a NEW retained source (manufacturer 8ft CAD page, HTML)

Bounded web follow-up of the dataset's own CAD-page URL pattern found the
manufacturer's `augusta-8ft-cad` page: per-configuration **Material Lists**
(8x6 and 8x8 panels, gates). Retained through the corpus path — dataset
document entry, `cli manifest`, a new stdlib HTML extractor
(`fence_evidence/extract.py:extract_html`, visible text + real `<table>`
elements, `html_text` origin), `cli ingest --path`. Content-stable across
fetches (page chrome is not); SHA `5586a6d4…`.

| Previously missing | Now closed (8x6 panel list) |
|---|---|
| Picket count (was null) | **22 T&G pickets** (11 per run x 2 runs) |
| Picket stock length (was null) | **43 in** (0.875 x 6 x 43) |
| U-channel profile (designation only) | **1.25 x 1.5 x 39.5 in** |
| U-channel count (interpreted 4) | **4 stated** — independently confirms the two-run reading |
| Metal rail inserts (component unknown) | **3 x 1.25 x 1.75 x 71.5 in** — new Part + dataset component |
| Kit inventory (was "not claimed") | complete per-panel list; **posts NOT in the panel kit** |

Cross-validation before trust: the list's U-channel length (39.5) exactly
equals the drawing-derived run height (95.5 - 3*5.5)/2, and the 6ft list's
27.75 equals (72 - 3*5.5)/2 the same way. The picket 43 - 39.5 = 3.5 in
difference is **implied seating** (config-dependent: 6ft gives 3.25), NOT a
measured engagement — recorded as such; receiving geometry remains open.
Consumer dialect note: pattern-member qty must stay 1 (cycle semantics;
handed edge bindings require it), so the kit count lives in the
draft/dataset, not on the consumer pattern member.

### Closed from previously uninspected LOCAL sources

- Specsheet p1 weights row: **65 lb** in the Augusta column (element-478d468055-0028
  neighborhood; the full-line catalog p7 independently shows 65 lb beside the Augusta
  block), footnote "Average weight ... for a 6'x8' panel".
- Master install p3: post-hole specs — 5" posts need a **12 in diameter hole, 30-36 in
  deep, two 80 lb bags** of concrete; 2 in recommended panel ground clearance; post
  internal markings (line = none, end = red dots, corner = green dots); >6 ft or
  high-wind fences need reinforcement to at least 24 in (concrete or aluminum insert).
- Full-line catalog p15 + master install: post identity family data — 4x4 & 5x5, heights
  72/84/96/105/120/140 in, all colors, gate posts include metal insert; posts custom
  routed per style (Augusta = 3 route holes).
- Warranty doc: residential limited lifetime on extrusions; hardware/connectors 5 yr
  residential / 2 yr commercial; 30-day registration; not transferable; Khaki
  discoloration threshold 8 Delta E. (Dataset `material_grade.warranty` already
  carried this; now verified verbatim.)

### Inspection corrections

- The dataset assembly's color list was copied from the Savannah line (fabrication by
  copy, flagged for follow-up): the specsheet p1 legend and full-line catalog p7 state
  Premium-row colors White/Tan/Khaki/Gray (+ catalog: Cedar/Coastal/Black for
  WeatherGrain styles; brochure p15 lists Augusta under Coastal Gray availability).
  Augusta's own color list needs a per-style verification before being authored.
- Brochure route-holes note correctly on p15 (fixed earlier); full-line catalog p15
  repeats it verbatim (twice-observed).

### Still open (explicit)

- Rail slot depth, picket seating depth (beyond the implied 3.5/3.25 in), post
  rail-socket depth: no source states them; fitted cut lengths remain unvalidated.
- Exact SKU identity for the 8x6 kit; Augusta-specific color availability per style.
- Amendment 008 (model numeric provenance) — models[] still 0 by design.
- 20 step candidates still await human review (procedures 0 by design).

Snapshot: `95c770b8…` (33 parts: +2 metal-insert Parts; picket/U-channel Parts
legitimately updated with material-list specs; Emblem untouched). Full suite
1,633 OK (1 pre-existing expected failure; corpus count pins updated 144→145
paths / 128→129 objects — the delta is exactly the new HTML source).
