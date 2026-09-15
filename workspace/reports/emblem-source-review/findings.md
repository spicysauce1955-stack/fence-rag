# Emblem source coverage and newly recovered geometry

The previous missing-data assessment was incomplete. The retained2022 approval
contains a6×8 Emblem component drawing, missed by text-only inspection. Its
existing canonical elements already held OCR under `ocr_text`, while `text` was
empty. An empty PDF text extraction was not evidence that the drawing lacked data.

## What the drawing answers

Source: `manuals/freedom-outdoor-living/structural/MiamiDade-NOA-22-0217.05-Barrette-Extruded-PVC-Vinyl-Fence.pdf`,
PDFpage7, drawing001 sheet4of9, dated3/6/2022. [Rendered drawing](noa22-drawing-07.png).
It explicitly names **6×8 Emblem**, under **pre-built panel style**.

| Question | Drawing reading | Exact conversion | Disposition |
|---|---|---|---|
| Board length |61.5in|1562.1mm|Found for this drawing; no longer globally “not found”.|
| Board thickness |0.875in|22.225mm|Found; agrees with the previously read manufacturer family webpage.|
| Board profile width |6in|152.4mm|Found; installed pitch is not automatically established.|
| Rail length |94in|2387.6mm|Found for this drawing.|
| Rail width×height |2.25×7in|57.15×177.8mm|Matches exact-model project-sheet outer dimensions.|
| U-channel width×depth×length |0.99×1.34×53.875in|25.146×34.036×1368.425mm|Found; these are end-channel dimensions, not rail-pocket depths.|
| Post dimensions |5×5×108in|127×127×2743.2mm|Drawing and exact-model catalog agree in their size designations; not imported in this batch.|

The two board alternatives have the same stated outer size but different profile
sections. Do not choose a profile or convert small section labels into groove
capacity without resolving their datums. SectionA-A andB-B supply connection
information, but their labels were not treated as unrestricted usable seating or
per-end insertion allowances. No dimensions were inferred by scaling an NTS image.

## Applicability and construction distinctions

The exact RTA73014714 project sheet and catalog corroborate the family/height,
rail designation and post size. They do not explicitly identify their component
revision as this pre-built drawing. The drawing calls for aluminum rail/post
reinforcement and screws, whereas the ordinary installation manual contains a
7-inch-rail insert exception. Those are different construction contexts; neither
instruction is erased. The drawing is useful evidence with scoped applicability,
not a source to discard, and not authority to overwrite exact-SKU geometry.

The2024 approval is not automatically the successor geometry for this Emblem
sheet: its cover explicitly names Columbia, Imperial, Chesterfield, Breezewood
and Brookline. Its PDFpage7 drawing is Brookline. Existing document metadata's
“superseded” label on the2022 record is inherited from a title keyword; its
lineage/classification needs separate curation. No compliance conclusion or
universal site instructions are made here.

## What changed through the layers

1. **S:** checked retained2022 PDF hash `13041c76330a3e6c6fb27f73bab982b2cd71c89f6eea842f30c174a4831a2a0b`.
2. **C:** reused original OCR elements, regions and edition. Auxiliary OCR/image
   renders were used for inspection only. Canonical OCR was not silently fixed.
3. **K:** persisted9 visual-transcription readings in `facts`, all `flagged`,
   `ocr_derived=1`; original OCR evidence retained. No human reviews created.
4. **P:** normal snapshot builder emits3 separate drawing-scoped draft Parts:
   rail, board and end-channel. Values use `drawing_*` keys and explicit names
   stating pre-built drawing scope/exact-SKU uncertainty. Existing exact-model
   Parts are unchanged. No engine pitch, model or purchasing data was filled.

Snapshot and Parts: [publication receipt](../emblem-drawing-publication.json).
Layer checks: [batch run](../conversion-runs/f0193bf7e3914cb5a6845ad16ec7b1d4.json).
The existing document metadata maps to its existing source classification; no
PE-sealed or human-reviewed classification was fabricated to raise confidence.

## Additional supported answers

- **Emblem sell sheet:** racks1inch per foot; gate leaf widths2in below opening;
  gate-post inserts required. Family-scoped findings, not newly published facts.
- **Transition guide:**6-to5ft panels use15boards;6-to4ft use14. These counts must
  not become the standard level-panel kit count. Decorative-route enlargement
  instructions also exist; route height is not rail insertion depth.
- **Cutdown guide:** total rail allowance and trimming procedures are available.
  Missing implementation of those rules is not missing source information.

See [coverage.json](coverage.json) for all8 files, hashes, actual inspection
methods, findings and disposition. No external search was necessary to recover
this evidence. Source-backed research answers above are distinguished from the
three objects actually converted through K→P.

## Still unresolved

Exact RTA73014714 applicability of the pre-built drawing, installed pitch for a
chosen profile, unambiguous usable receiving depths/seats, and complete fitted
assembly/purchase validation. These are narrower gaps than “board/rail/channel
dimensions unavailable”. Next: identify the component/revision bridge and resolve
profile/connection datums, preserving the useful drawing-scoped knowledge now.

Reproduce conversion and its acceptance checks:

```bash
python3 scripts/advance_emblem_drawing.py
python3 scripts/check_conversion_batch.py workspace/catalog/emblem-drawing-conversion-batch.json --round 1
```

The importer is idempotent and preserves reviews. Corrections/rejections use the
existing fact-review path; the publisher reflects them rather than rewriting
original readings. The checkpoint now reads canonical OCR when text is empty,
matching the canonical representation instead of bypassing it.

Validation:70 focused tests passed in11.054s, including existing Emblem claim
projection, snapshot verification and new drawing import/review/refusal checks.
Log: `../../tests/emblem-drawing-focused.log`. No full-suite or consumer assembly
run was performed for this batch.
