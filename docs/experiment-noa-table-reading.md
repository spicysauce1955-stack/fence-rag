# Experiment design — reading the scanned NOA table pages

```text
Status: RAN. 1,225 readings loaded; see §'Superseded by measurement'
        below and docs/state-and-gaps.md G13/G17.
Scope:  Table extraction from pages retrieval has already selected.
        Not visual search, not page-level visual retrieval, not embeddings.
Gate:   No numeric fact from this path may be promoted without human review.
```

## 1. Problem, measured

73 pages carry a `table_not_reconstructed` quality issue: the page names
conditional or tabular engineering data, and no cell grid could be recovered.
Those pages are where this corpus keeps the values the system exists to answer
from — maximum post spacing and footing dimensions by wind exposure category.

| | |
|---|---|
| flagged pages | 73 |
| documents involved | 13 |
| **distinct page contents** | **44** (four documents are byte-identical copies of one NOA) |
| mean OCR confidence on those pages | 64.5% (min 47.3, max 87.0) |
| pages in a structural document | 68 of 73 |

Everything already tried and rejected, with the measurement:

- `pdfplumber`, both ruling-line and text-alignment strategies: finds nothing.
  These pages have no text layer for it to work from.
- OCR word-grid reconstruction (implemented, `tables.detect_ocr_tables`): across
  the full corpus it accepts 9 grids, all in scanned *catalog and specification*
  pages, and **none** on an NOA drawing sheet. Every candidate there is rejected
  by the confidence, stub-cell or numeric-content gates that exist to stop it
  inventing values.
- Rendering at 400 and 500 dpi instead of 300: mean word confidence on
  NOA 23-0314.05 page 17 stays at 49–50% at every resolution. Resolution is not
  the limiting factor.
- Whole-page OCR at a second resolution (implemented, `ocr_supplement`):
  recovers scattered tokens — it found the PE licence number `52609` and the
  post-stiffener specification text — but not rows, and not reliably numbers.
  The structural gold-set author independently measured that individual figures
  appear at one resolution and vanish at another.

So the failure is not resolution and not the parser. It is that a value in these
tables is a short numeric string inside dense line-work, and whole-page OCR
reads it at coin-flip reliability.

## 1a. What the manual pass changed about this design

Two premises here were wrong, and the design should be revisited before it is
built:

- **"A value in these tables is a short numeric string inside dense line-work,
  and whole-page OCR reads it at coin-flip reliability."** True of OCR, but the
  pages themselves are not the problem: readers found 42 of 44 fully legible at
  200 dpi and needed no abstentions. The binding constraint is tesseract.
- **The scale of the loss was unknown.** It is now measured: 41% of numeric
  values on these pages are absent from the store, against 7% of non-numeric
  values. That raises this experiment's priority and narrows its target to
  numbers specifically.

Also: 7 of the 44 flagged pages have no table at all, so the experiment's input
set should be the 37 that do.

## 2. Hypothesis

Per-cell OCR is a materially easier problem than per-page OCR. If the grid
geometry can be established first, each cell becomes a small, isolated image
containing one or two tokens, and tesseract can be run on it with a restricted
character set and a single-line page-segmentation mode. The experiment tests
that, and nothing else.

## 3. Input, already built

`python3 -m fence_evidence.cli noa-table-crops` writes, per distinct flagged
page, a preserved full-page crop plus a manifest row:

```text
workspace/derived/<document_id>/table-candidates/pNNNN.png
workspace/catalog/noa-table-candidates.jsonl
```

Each manifest row carries `document_id`, `source_path`, `page_no`,
`document_sha256`, `page_image_path`, `crop_path`, `crop_sha256`, `crop_bytes`,
`page_ocr_mean_confidence`, and `applies_also_to` — the duplicate paths the same
content is filed under, so a result read once is attributed to all four copies
of an NOA rather than read four times. 44 crops, 60 MB, covering all 73 flagged
pages.

**The crop is always the full page.** A ruled-band detector was written and is
recorded per row as `candidate_band_px`, a *hint only*. It found a band on 17 of
44 pages, and on page 17 of the Bufftech installation guide it locked onto the
parallel picket lines of a fence elevation and clipped the real `POST CENTERS`
table off the bottom of the image. Clipping evidence is a worse failure than
handing the next stage a larger picture, so the hint never drives the crop.

## 4. Method to test

Four stages, each producing an inspectable artefact. No stage may write a fact.

**S1 — grid geometry from morphology, not from text.** On the full-page crop:
deskew by the dominant near-horizontal line angle, binarise, then find long
horizontal and vertical runs and keep only *intersecting* pairs. A table cell
boundary is defined by a crossing; a picket is not, because vertical pickets
meet at most two horizontals (top and bottom rail) rather than forming a lattice.
Require at least 3 horizontal and 3 vertical lines with ≥6 intersections before
declaring a grid. Output: candidate grid rectangles with pixel coordinates.

**S2 — per-cell crop and OCR.** For each cell, crop with a small inset to
exclude the rules, upscale ×2, and OCR with `--psm 7` (single line) twice: once
unrestricted, once with `tessedit_char_whitelist` limited to digits, `.`, `/`,
`"`, `'`, `-` and space. Keep both readings, plus per-cell mean confidence.
Output: a cell table with two candidate strings and a confidence per cell.

**S3 — agreement and abstention.** A cell is *read* only when the unrestricted
and restricted passes agree after normalisation, or when one is empty and the
other is confident. Disagreement is an abstention, not a guess. Row and column
headers are read with the unrestricted pass only. Output: a cell grid where
every cell is either a value with two agreeing sources, or an explicit
`abstained`.

**S4 — structural plausibility check.** Reject the whole grid unless it looks
like the tables this corpus contains: a header row or column mentioning an
exposure category (`B`, `C`, `D`) or a wind speed, and numeric cells whose
values fall in the plausible ranges the fact layer already defines
(`footing_depth_in` 6–120, `post_spacing_in` 12–240). A grid that fails goes to
review as a whole rather than contributing cells.

## 5. Review gate — the part that must not be skipped

Nothing from S1–S4 enters `facts` as an assertion. The design adds one table:

```text
table_read_candidates
  candidate_id, document_id, version_id, page_no,
  crop_path, crop_sha256,            -- the preserved page image
  cell_crop_path, cell_bbox_px,      -- the specific cell, croppable and viewable
  row_index, col_index,
  row_header, col_header,            -- as read, for the reviewer's context
  value_unrestricted, value_restricted, agreed,
  cell_confidence, grid_id,
  extractor,                         -- 'noa-cell-ocr-v1'
  review_status,                     -- 'unreviewed' | 'accepted' | 'corrected' | 'rejected'
  reviewed_value, reviewer, reviewed_at
```

Rules, to be enforced in code rather than by convention:

1. A row enters as `unreviewed`. `facts` is written only from rows that are
   `accepted` or `corrected`, and the resulting fact records
   `extractor='noa-cell-ocr-v1'` plus the `candidate_id` it came from.
2. Every candidate must have a `cell_crop_path` that exists on disk. A candidate
   without its crop is invalid and cannot be reviewed or promoted — the reviewer
   must be able to see the pixels the number was read from.
3. `retrieval` and `facts.query_facts` never surface an `unreviewed` candidate as
   an answer. It may be surfaced explicitly as "unreviewed candidate reading",
   with its crop, and never as a value.
4. Promotion is per cell, not per grid. Accepting a footing-depth column does not
   accept the post-spacing column beside it.
5. A corrected value keeps the original OCR strings. The record of what the
   machine read is part of the provenance.

## 6. Acceptance criteria

The experiment is worth adopting only if all of these hold on a labelled subset.

**Ground truth.** Superseded by measurement: a blind manual verification pass
now provides transcriptions of all 37 flagged pages that carry a real table, 348
cells of them double-read with 174/174 inter-reader agreement — see
`workspace/reports/manual-verification-round-1.md`. Use that as the labelled set.
The claim below overstated what was available when this was written: only 4
flagged pages had gold-anchored values, and none was a table cell.

Original text: 8 pages have independently verified values, from the structural
gold questions: the Table 1 wind/exposure grid in NOA 12-1106.11,
23-0314.05 and 24-0117.05 (B 30″/97″, B 24″/66″ non-HVHZ, C 36″/88″, C 30″/68″,
D 36″/75″, D 30″/56″, 12″-diameter footing, 3000 PSI), plus the Barrette
22-0217.05 Ø18″ × 41″ footing. Those readings were confirmed by rendering the
page and reading it visually, and they are recorded in
`eval/gold-questions-structural.json` with the command used.

| # | Criterion | Threshold |
|---|---|---|
| A | Grid detection precision on the 44 crops | ≥ 0.80 of declared grids are genuinely tables, judged by opening the crop |
| B | Cell-level accuracy on the 8 labelled pages, over cells the method does **not** abstain on | ≥ 0.95 |
| C | Silent-error rate — a numeric cell read confidently and wrongly | **0** on the labelled subset. A single silent error fails the experiment outright |
| D | Abstention is honest | every abstained cell has a crop, and the grid is still offered for review |
| E | Coverage | at least 4 of the 8 labelled pages yield a reviewable grid; below that the method is not worth the review effort |
| F | No regression | zero facts promoted without review; the retrieval contract unchanged; `python3 tests/run_tests.py` green |

Criterion C is the one that decides it. A method that abstains often but is never
confidently wrong is useful, because a reviewer can work through abstentions. A
method that is occasionally confidently wrong about a footing depth is worse than
no method at all, because the whole point of the store is that a number can be
trusted back to its page.

## 7. Cost and stopping rule

44 pages, ~30 cells each at the upper end, two OCR passes per cell: roughly
2,600 tesseract invocations on small images, a few minutes of CPU. The review
burden is the real cost — at 30 cells a page and 8 pages for the labelled subset,
expect a couple of hours of human attention before criterion B can even be
judged.

Stop after the labelled subset if criterion C fails. Do not extend to the
remaining 36 pages before B and C pass, for the same reason the pipeline did not
ingest 137 documents before the ten-document pilot passed.

## 8. Explicitly out of scope

Page-level visual retrieval, dense embeddings, a vector database, an HTTP
service, an MCP server, and any model-based page reading that would send corpus
content off this machine. This experiment reads pages that lexical retrieval has
*already* selected; it does not change how pages are found.
