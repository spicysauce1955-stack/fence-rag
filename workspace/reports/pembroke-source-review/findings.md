# Pembroke 6x6 source review — 2026-09-07

Bounded coverage record for batch `pembroke-assembly-001` (run metadata, not a
claims store). Target product: Weatherables Pembroke privacy panel, 6 ft tall
× 6 ft wide configuration (manufacturer "Pembroke 6ft Master CAD" page,
"Material List - 6x6 Panel").

## Inspected candidates

| Candidate | Path | SHA-256 | Inspection | Disposition |
| --- | --- | --- | --- | --- |
| Pembroke 6ft privacy CAD raster | `manuals/weatherables/structural/weatherables-cad-pembroke-6ft-privacy.png` | `3fd74eac…` | Canonical OCR (2 garbled whole-image labels, mean conf 0); diagnostic re-OCR at 16–24× upscale (psm 7/8/11/12/13) + glyph-pixel analysis + ASCII density map | Corroborating labels recovered for the closure only: top-center `72` (overall width), left-mid `72"` (overall height), right-edge chain `5.5 / 61" / 5.5`. The chain closes exactly: 5.5 + 61 + 5.5 = 72, and 72 − 2×5.5 = 61 equals the material list's U-channel length. **The canonical OCR is unusable and anchors nothing: no fact, no Part spec, no model field cites this PNG.** Supersedes Augusta's deferral of this file (it listed the PNG as uninspected); the file remains unpublishable as evidence. |
| Pembroke 6ft master CAD page (HTML) | `manuals/weatherables/structural/weatherables-pembroke-6ft-cad-page.html` | `4b763b3c…` | `extract_html` (243 elements: 4 material-list tables + 4 headings); material-list content byte-identical across three fetches (page chrome is not) | **Primary dimension source.** 6x6 Panel list: Top Rail 1 + Bottom Rail 1 (1.5"×5.5"×71.5"), Metal 1 (1.25"×1.75"×71.5"), U-Channel 2 (1.25"×1.5"×61"), T&G Pickets 6 (0.875"×11.3"×64.25"). Cross-validation: U-channel 61 = 72 − 2×5.5 exactly (two-rail single-run chain, no halving — the /2 in Augusta's (95.5 − 3×5.5)/2 applies only to two-run panels); the sibling 6x8 list repeats the same 61" U-channel and 64.25" picket for its own 6 ft height; rails 71.5 for 72-wide panels repeat the 0.25-per-side inset seen in Augusta 8x6 and the 6x8 sibling. Panel kit lists NO posts. Gate lists (6'×42.5", 6'×65") name 4"×4"×76" socket posts — gate-scope evidence only. |
| Master installation instructions 2024 | `manuals/weatherables/weatherables-fencing-master-installation-instructions-2024.pdf` | `db02aeee…` | Text layer read (pp. 3–10) | p7 "Solid Privacy" two-rail flow: bottom rail (with the aluminum insert) + top rail into post A; `1.5" U-channel slides on the T&G picket`; u-channel on the first and last picket (2 segments = single run). **Applicability note: the flow's diagram labels picture 7/8"×6" pickets (Premium family size) — no Pembroke picket dimension is taken from it.** p3 post-hole specs (10" diameter for 4x4 posts) are family-level, not Pembroke-specific. |
| Privacy fencing specsheet | `manuals/weatherables/weatherables-privacy-fencing-specsheet.pdf` | `87dea78b…` | Text layer read (p2 Classic block) | The Pembroke™ positionally paired with Height 4'–8', Width 6'&8', Picket Style 7/8"×11.3", T&G .055", 59 lb (6'×8' average weight — not published). |
| Fencing brochure | `manuals/weatherables/weatherables-fencing-brochure.pdf` | `cb90e6a2…` | Text layer read (p8) | Identical Classic row order and values (Pembroke/Glenshire/Tuscany/Dora; 59/61/59/66 lb) — the specsheet pairing is twice-observed. Not cited by any published Part. |
| Limited warranty | `manuals/weatherables/weatherables-limited-warranty.pdf` | `eed66dadc…` | Text layer read (p1) | "Individual Residential Homeowners … Limited Lifetime Material Warranty for all vinyl extrusions" — warranty-scope statement cited by the model draft's `/grade` field as authored support; no source states a structural grade rating (recorded in the draft's unresolved_fields). |
| weatherables.json dataset | `data/weatherables.json` | — | Assembly graph read | The Pembroke entry existed with 2 components (picket, rail); this batch authored the full composition (post, slotted rail, picket, U-channel, metal insert) with per-panel counts and recorded bases. |

## Interpretation notes

- The CAD raster is a dimensioned drawing, but at 397×283 px its canonical
  OCR is unusable (mean confidence 0, two garbled whole-image labels). The
  labels above were recovered by diagnostic re-OCR at 16–24× upscale plus
  glyph-pixel comparison (e.g. the left-mid label's `7`/`2`/`"` glyph shapes
  vs the Augusta `71.5` template), and were used ONLY to corroborate the
  arithmetic closure. Per the trust ladder this is the lowest rung below
  garbled OCR; no value publishes on it, and the panel's published dimensions
  come from the retained HTML material list (text layer) instead.
- The `72` readings are the panel's nominal width and overall height labels;
  rails are 71.5 (0.25 inset each side). They are kept separate, and neither
  is published as installed geometry or a cut allowance.
- The picket stock length 64.25 in exceeds the 61 in run by an implied 3.25 in
  seating — config-dependent (the 6x8 sibling's stock is also 64.25 against
  its own 61 in run), never a measured engagement.
- 6 pickets × 11.3 in nominal width covers 67.8 in of a 72 in run only with
  tongue-and-groove engagement; per-board installed coverage is unstated and
  is not inferred.

## Uninspected / deferred

- 6x8 panel and gate material lists on the same CAD page: out of scope for
  the 6x6 configuration (retained in the same bytes; a future batch can bind
  them without a new fetch).
- `weatherables-cad-captiva-*.png`, Monterey/Chelsea/Captiva CAD pages,
  remaining Weatherables manuals (2/3/4-rail, crossbuck, weathergrain,
  post-mount, premium gate, triwest reference): unrelated to the Pembroke
  6x6 question or deferred; not negative evidence.
- Home Depot product page PWPR-T-G11-3-6X8 (the 6×8 sibling SKU): the
  structural dataset already carries its racking figure; no 6x6-specific
  retailer statement was sought because the manufacturer's own material list
  answers this batch's questions.
- Store classification: the retained HTML ingests as `doc_type: unspecified`
  (→ `source_class: marketing`) while the curated index classifies it
  `cad_detail`; an honest-floor classification gap publishes. Closing it is a
  follow-up slice (same treatment as the Augusta HTML page).

## Adverse checks performed

- Changed anchor text/sha/text_source/owner → import refuses (test).
- Foreign fact_type under the recipe extractor → refuses (test).
- Fractional count → transformer refuses (test); wrong fixing count →
  transformer refuses (test); wrong frame structure (3 rails / qty ≠ 1 /
  nonzero overlap) → transformer refuses.
- Stale consumer candidate (draft edited without re-running the transformer)
  → advance script fails the candidate_matches_current_draft check.
- Duplicate Part identity from the shared Weatherables namespace → found live,
  fixed at the owning layer (recipe scoping by component ids), regression
  test added.
- Emblem non-interference: byte-comparison of all 13 Emblem-owned Parts
  across snapshots gates the snapshot store.
- Full-suite regression: 1,673 tests, 1 pre-existing expected failure.
## Five-way adversarial review and fixes — 2026-09-07 (batch pembroke-assembly-001, rounds 1–2)

Five adversarial reviewers (source applicability; schema/layer closure;
assembly/BOM logic; malformed inputs; overclaim audit) attacked the slice
read-only. Confirmed defects and the fixes applied at owning layers:

1. **Wrong closure formula in the dataset note (two reviewers, CONFIRMED).**
   The retained-HTML note read "(72 − 2×5.5)/2 = 61" — evaluates to 30.5; the
   /2 was copied from Augusta's two-run formula. Fixed to "72 − 2×5.5 = 61
   (two-rail panel, single picket run; no halving)". Digest re-baselined;
   master-dataset.json regenerated.
2. **Dangling evidence pointers (two reviewers, CONFIRMED).** The batch
   limitation and report remaining_gap pointed at a "source-review findings"
   and a "coverage note" that did not exist. Fixed by writing this file
   (workspace/reports/pembroke-source-review/findings.md, carrying the
   diagnostic re-OCR method and labels) and repointing both strings at it.
3. **Grade citation overstated its source (source reviewer, CONFIRMED).**
   `/grade: residential` cited the specsheet block, which states no grade.
   Fixed: the field now cites the warranty's Protection Coverage statement
   (Individual Residential Homeowners), and the draft's unresolved_fields
   records that this is warranty scope, not a structural grade rating. The
   warranty document registers in source_docs through the field-evidence ref.
4. **Stale-candidate binding unverified (malformed-inputs reviewer,
   CONFIRMED).** The advance script validated the candidate and the draft
   fragment independently; a draft edited without re-running the transformer
   could pass every pin. Fixed: a `candidate_matches_current_draft` check
   recomputes the draft's content hash against the candidate's declared
   `source_package_hash`; a mismatch fails the run (now 14 checks).
5. **Transformer accepted hand-edited frame structure silently
   (malformed-inputs reviewer, CONFIRMED).** A 3-rail draft, doubled rail
   qty, or nonzero overlap passed through unguarded. Fixed: the transformer
   refuses frame slot count ≠ 2, rail qty ≠ 1, and nonzero overlap;
   adversarial test added.
6. **trim_last → space substitution unrecorded (malformed-inputs reviewer,
   CONFIRMED).** The consumer's honest end-fitting policy substitution lived
   only in a source comment. Fixed: recorded as a structured
   `authored_field_substitutions` entry (draft value, candidate value,
   reason); test added.
7. **Metal-insert omission unrecorded at model level (BOM reviewer,
   OBSERVATION→FIXED).** The insert (1 per panel) has no model requirement —
   a defensible refusal (a per_panel fixing would draw it at the panel
   centre, the Augusta centre-dot failure mode) — but the refusal was
   unrecorded. Fixed: a `/model_fragment/default_spec` unresolved_fields
   entry and a batch limitation state it; test added.
8. **Minor hardening (malformed-inputs reviewer).** The resolved-slot check
   used `isinstance(x, int)` which admits a forged boolean; now `type(x) is
   int`. The offset/height pins were hardcoded literals; they are now
   derived from the draft (with loss-arithmetic re-verification), so a stale
   draft fails the binding check and the transformer's own arithmetic is
   what's verified. The advance-script docstring no longer overpromises an
   ABORTED report for crash paths (storage discipline holds there either way).
   Weak test pins replaced: the report pin now requires BOTH flags (`and`,
   not `or`), and the gate-ordering pins index the real failure-branch
   statements.
9. **Disclosure of the p7 flow's Premium picket label (source reviewer,
   OBSERVATION→FIXED).** The recipe now notes that the Solid Privacy flow's
   diagram labels picture 7/8×6 pickets and no Pembroke picket dimension is
   taken from it. The metal-insert dataset basis string now separates the
   material-list count from the install-flow placement evidence.

**Upheld by the reviewers (no action):** the 61-in closure and its single-run
(no-halving) form; the 6x6 scoping everywhere; the twice-observed positional
specsheet pairing; kit-count Tokens; the CAD-PNG quarantine (0 facts, 0
citations across the whole snapshot); centerline placements and the Emblem
88.9 mm precedent; pattern qty-1 cycle semantics with handed edge bindings
(qty 6 would break both bindings — consumer validate code checked); the
mapped 2 == authored 2 u-channel completeness; the rail-length
receiving-joint limitation matching the consumer's actual code; the 3.25 in
implied seating recorded as config-dependent everywhere; the post-omission
reason; script-reproducible report prose; the exit-code gate (put_snapshot
unreachable on failure, emblem byte-comparison gating the same store); and
the fixed duplicate-identity defect (recipe scoping by component ids —
verified firing exactly once per slice, CertainTeed default fires none).

**Deferred to follow-up slices (recorded, not defects):** `verify()` does
not refuse duplicate Part ids structurally (the slice's regression tests and
the batch checker catch it; a verify()-level check is proposed to the next
batch); the retained HTML ingests as `doc_type: unspecified` (marketing
source class, honest floor) while the curated index says `cad_detail`;
Emblem branch should import its component-id constant instead of inlining.

Verification: 25 focused tests (5 new adversarial-hardening tests), full
suite 1,658 OK (1 pre-existing expected failure), 14/14 consumer checks,
advance exit 0 with the gate live, checkpoint round 2
`partial_knowledge_verified`, snapshot `359c314d…` (42 Parts: 5 authored
Pembroke composition, 4 Pembroke value, 9 Augusta, 13 Emblem, 11
CertainTeed spine/stock parts; 0 models, 0 procedures by design).

## Gap-closing round — 2026-09-07 (batch pembroke-assembly-001, round 3)

Missing-data inventory across the converted datamodels (dataset composition,
recipe readings, published Parts, model draft, consumer candidate), and what
closed. Every closure cites already-retained sources; the one new *fact*
goes through the normal recipe path.

### Closed from already-retained LOCAL sources

| Was missing | Now closed | Source (retained) |
|---|---|---|
| Panel width options (dataset recorded only 96 in on-center) | `width_options_in: [72, 96]` with basis | specsheet p2 "Width: 6' & 8'"; master install p3 "72" or 96" center to center… width of all of our fence panels can be reduced"; both CAD-page panel lists (6x6 + 6x8) |
| T&G wall gauge (in dataset prose only; no fact, no Part spec) | New recipe reading `picket_tongue_groove_wall_gauge_in` → picket Part spec `tongue_groove_wall_gauge_mm` = 1397 milli-mm, verbatim raw `.055 in.` | specsheet p2 "Tongue & Groove .055"" (twice-observed: brochure p8, full-line catalog p8) |
| Ground clearance (absent) | `panel_ground_clearance_in: 2 (recommended minimum)` | master install p2 element-d50723c4a6-0009 |
| Wind rating (absent) | `wind_rating_claims` with BOTH conflicting figures reproduced verbatim + conflict note | FAQ 110/130 (≤6 ft standard install; structural dataset quote) vs master install p15 "Panel Privacy - 120 MPH sustained… 137 MPH" with fasteners + post reinforcement (12"×36" hole, 22" min above grade) — both retained, neither reconciled |
| Post family data (composition post had socket note only) | `profile_depth_in` enriched: Blank/Line/End/Corner/Gate posts, 4×4 & 5×5, heights 72–140, all colors, gate posts include metal insert, custom routed per style | brochure p15 + full-line catalog p15 (twice-observed) |

The `.055` parsing note: the specsheet writes the gauge without a leading
zero; the recipe's local `quantity()` accepts that verbatim form so the
published `value_raw` stays `['.055 in.']` — the value is never rewritten as
0.055 (never silently correct canonical readings; here the "correction"
would have been ours, not OCR's, and the parser was widened instead).

### Explicit inspected-not-claimed gaps (added to the dataset assembly)

- **Panel post-height pairing**: no retained source pairs a post length with
  the 6×6 panel (hole depth 30–36 in and post heights 72–140 in are both
  stated; the combination is an install choice, not a product pairing). The
  gate list's 4×4×76 posts are gate scope.
- **Panel-scope post cap**: the panel list names no cap; the gate lists'
  "Post Cap 2 | 4×4" entries are gate scope.
- **Rail slot dimension**: the master install labels the rail "1.5×5.5
  Slotted rail" with no slot width/depth; the "7/8 slot" label belongs to
  the lattice-variant rail, not the solid privacy rail. Receiving geometry
  stays open.
- **U-channel screw note**: N/A — the screw-in instruction is Coastal/Cedar
  WeatherGrain-only; Pembroke is White/Tan/Khaki/Gray smooth.
- **Receiving geometry**: unchanged open gap (slot/seating/socket depths).
- **Wide-board install flow**: master install p8 is the 13.875-in
  wide-board flow (Largo/Clearwater family); no 11.3-in-specific assembly
  flow exists in the retained corpus — the p7 Solid Privacy flow plus the
  material list remain the assembly evidence.

Also verified this round: the CAD page's remaining elements (186–238) are
nav/footer chrome (no additional product content); the p5 glue flow is the
GATE assembly (socket posts, cross brace, glue) — panel assembly names no
glue, fasteners or screws in the retained sources.

Snapshot `0e04d171…` (42 Parts; picket now carries 5 specs incl. the gauge);
17 bindings; checkpoint round 3 `partial_knowledge_verified`; full suite
1,664 OK (1 pre-existing expected failure); 31 focused tests.

## Assembly-extraction unblocking — 2026-09-07

The obstacle "assembly information waits in our datasources" decomposed into
three channels; two mechanical seams were unblocked, measured first:

1. **Numbered-flow steps** (`cli steps --pair-numbered`): manuals that type
   each step number as its own element produced ZERO step candidates — the
   master install's p7 Solid Privacy flow (11 steps) yielded 1 candidate
   from `--propose` because its 22 substantial paragraphs are not `list`
   elements. Corpus measurement: **466 glyph-paired steps across 111 pages
   in 22 documents**. The new `pair_numbered_flow` pairs `N.` glyph elements
   with body paragraphs by bbox overlap (closest-first-line; the naive
   top-most-body variant paired glyph `8.` with the next section's heading —
   found and fixed before commit). On the master install alone: 20 → 106
   candidates, idempotent, never touches reviewed rows, `proposal_basis`
   carries the glyph provenance. Nothing publishes without review — this
   fills the queue the review gate already guards.
2. **Kit/material-list tables** (`scripts/read_kit_tables.py`): the corpus
   holds complete kit lists as canonical `table` elements with real
   `table_cells` — Weatherables CAD pages (Augusta 5 lists, Pembroke 4) and
   Catalyst SKU sheets (Cape Cod 2, Madison 7): **18 kit-shaped tables**,
   none previously in `table_read_candidates`. The machine reader emits the
   `agent-read-*.json` shape `load_reading()` already ingests, with
   `reader_kind='machine'` and row-granular rows (row_label = ITEM).
   **165 candidates** now wait in the EXISTING review lifecycle. The 45-table
   first estimate included Catalyst accents/hardware SKU/color matrices —
   two-row headers with QTY/SKU pairs — which the shape test correctly
   rejects (a catalog is not a BOM).
3. **Recipe scaling (proposal, not built)**: reviewed kit rows become
   addressable by (document, table element, row), so future products can
   bind recipe rows to reviewed readings instead of hand-transcribing
   values. Blocked on review capacity, not extraction — by design.

Pre-existing defect found while wiring the load: `cli table-review
--load-dir` now accepts `--pattern`; reloading the committed agent-read
files fails on a FOREIGN KEY (a document one of them names is missing from
the store — the Madison path moved under structural/) — untouched here,
recorded for its owning slice.

Tests: 5 pairing + 4 reader tests; step modules 88 tests; full suite 1,673
OK (1 pre-existing expected failure).
