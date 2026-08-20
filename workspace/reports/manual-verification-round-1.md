# Manual verification, round 1 — scanned table pages

```text
Method: seven concurrent Sonnet agents, blind transcription from page images.
Scope:  the 44 distinct page contents flagged `table_not_reconstructed`
        (73 pages before deduplication), plus a curated-dataset cross-check.
Status: readings stored as review-gated candidates. No fact promoted.
```

Automated tests check that extraction is internally consistent — a bbox inside
its page, a page count matching the source, OCR text present. None of them can
check whether the extracted text says what the page says. That needs eyes on the
image, and this is the first pass that provides them.

## 1. Design

**Blind.** Readers were forbidden from querying the evidence store, running
`pdftotext` or `tesseract`, or reading anything under `workspace/reports/`,
`workspace/tests/` or `eval/`. They transcribed from the page image only. Had
they seen the pipeline's own output they would have anchored on its errors and
the exercise would have confirmed rather than audited.

**Double-read on the pages that matter.** Two readers independently transcribed
the same ten pages — the Table 1 wind/exposure grids — so agent reading could be
measured before being relied on.

**Sonnet throughout, not Haiku.** The failure mode here is a confidently wrong
digit in a footing depth, which is silent. The tasks Haiku would suit — string
presence, page counts, checksums — are SQL, not agents.

**Structured output**, one JSON object per page, so results diff mechanically.

## 2. Do two independent readers agree?

| | |
|---|---|
| cells compared (calibration-A vs calibration-B) | 174 |
| agree | **174** |
| disagree | **0** |
| marked illegible by either | 0 |
| agreement rate | **1.000** |

Both readers independently produced the canonical grid — Exposure B 30″/97″,
B 24″/66″, C 36″/88″, C 30″/68″, D 36″/75″, D 30″/56″ — matching the values the
structural research reported separately, months of context apart.

Perfect agreement between two same-family models on the same prompt is weaker
evidence than it looks; correlated failure is possible. What raises confidence is
that they converged on the same *structural anomaly* without being asked to look
for one (§5), which is a different kind of observation from copying a number.

## 3. What the pipeline actually captured

For every value a reader could see, does the pipeline's stored text for that page
contain it?

| Value class | Values | Present | Missing | Recall |
|---|---|---|---|---|
| contains a digit | 534 | 314 | **220** | **0.588** |
| no digit | 471 | 440 | 31 | 0.934 |
| **all** | **1005** | 754 | 251 | **0.750** |

By table kind:

| Kind | Values | Missing | Recall |
|---|---|---|---|
| bill_of_materials | 528 | 145 | 0.725 |
| wind_exposure_footing | 370 | 99 | 0.732 |
| spec_table | 107 | 7 | 0.935 |

**This is the finding.** OCR reads the words on these pages and loses the
numbers. A quarter of all readable content, and two fifths of every value
containing a digit, is absent from the store. The missing values are exactly the
load-bearing ones — `30"`, `97"`, `24"`, `75"`, `56"` footing depths and maximum
post spacings straight out of Table 1.

The `table_not_reconstructed` flag was therefore accurate but understated: it
said "no cell grid here", when the truth is "no cell grid *and* 41% of the
numbers on this page are not in the store in any form".

## 4. Was the flag itself right?

Of the 44 flagged pages, readers found:

| | Pages |
|---|---|
| bill_of_materials | 24 |
| wind_exposure_footing | 12 |
| spec_table | 1 |
| **no table at all** (drawing_only / prose) | **7** |

So the flag was a true positive on 37 of 44 pages and a false positive on 7.

The false-positive mechanism is now understood, and it is the same on every one
of the seven: the page carries a *caption* reading `SEE TABLE 1 ON SHEET n` or
`MAXIMUM POST SPACING NOT TO EXCEED nn"` above a drawing. Those words trip the
keyword heuristic in `_mentions_table` while the referenced table lives on
another sheet.

| Document | Page |
|---|---|
| `noa-24-0117.05-vinyl-fencing.pdf` | 7, 9 |
| `NOA-12-1106.11-extruded-pvc-vinyl-fencing.pdf` | 4 |
| `NOA-21-0125.07-CertainTeed-extruded-pvc-fencing…` | 8 |
| `NOA-23-0314.05-CertainTeed-Chesterfield-Columbia…` | 7 |

A cheap improvement follows directly: require a table hint that is *not* a
cross-reference — suppress the flag when the only trigger is `SEE TABLE … ON
SHEET`. It is a quality-issue heuristic, not indexing, so it is not held by the
audit gate; it is recorded here rather than applied, because it should land with
its own before/after count.

## 5. Corpus findings the readers surfaced

**Table 1 on NOA-12-1106.11 page 11 has no HVHZ bracketing.** Every other
instance of this table brackets the B rows as `NON HVHZ` and the C/D rows as
`HVHZ AND NON HVHZ`. On this page the labels are absent entirely. Both
calibration readers reported it independently, one after a zoomed crop. This
matters because a value's HVHZ applicability is what decides whether it may be
used in a high-velocity hurricane zone.

**Source-document typos, not OCR errors.** `STAILESS STEEL` (missing N) and
`U-SHAPPED` (extra P) are printed on the CertainTeed template sheets themselves,
confirmed under 3–4× zoom on four separate documents, while the Barrette-template
sheets spell both correctly. An earlier reading of `U-SHAPPED G-GO GALVANIZED
S1EEL` from the OCR supplement was therefore *more faithful* than it looked — the
pipeline had correctly transcribed a typo in the source.

**Maximum post spacing varies by model and size** and must not be conflated:
96 1/8″ (Columbia/Chesterfield 8′×6′), 97″ (Breezewood 8′×6′), 75 1/2″
(Chesterfield 6′×6′), 72″ (Brookline 6′×6′).

**Two approval stamps on one sheet.** Several pages carry an older printed
acceptance number overlaid by a newer `PRODUCT RENEWED` stamp, leaving two
different NOA numbers and expiration dates legible on the same page. Readers
recorded both rather than choosing. This is a genuine source of the version
conflicts the store reports.

**An unreadable glyph in the source.** On the Chesterfield-with-Lattice bill of
material, three consecutive ITEM codes are printed as a hollow rectangle — a
plotter or font artefact in the original drawing. The reader recorded `?` and
abstained rather than guessing. This is a gap in the source document, not in
extraction.

**A printed anomaly in the CLFMI topographic-factor table**: a `z/Lh` value reads
`0.50` where the standard ASCE 7 sequence implies `1.50`. Transcribed as printed
and flagged, not corrected.

## 6. Where the readings went

1,051 candidate rows in `table_read_candidates`, covering all 44 pages, every one
carrying its source crop and crop SHA-256.

348 cells where the two calibration readers agreed exactly are marked
`agent_verified`. **That status is not promotable.** `table_review.promote`
refuses anything but `accepted` or `corrected`, and refuses any candidate whose
crop is missing from disk. Two agents agreeing is a better reading, not an
accountable review — a person still signs off before a number becomes a fact.
`tests/test_table_review.py` asserts the refusal, including the specific case of
`agent_verified`.

**No fact has been promoted. The facts table is unchanged at 1,664 rows.**

## 7. What this changes

- The scanned-table experiment (`docs/experiment-noa-table-reading.md`) now has
  real labelled ground truth: 37 pages of transcribed tables, 348 of them
  double-read. Its criterion B, "cell-level accuracy ≥ 0.95 on labelled pages",
  is measurable for the first time.
- Its premise is confirmed and its priority raised. The gap is not marginal:
  41% of numeric values on these pages are missing from the store.
- The experiment's method should be reconsidered in light of this. Per-cell OCR
  was designed for pages assumed hard to read. Readers found them "fully legible
  by eye" at 200 dpi and needed no abstentions on 42 of 44 pages. The binding
  constraint is tesseract, not the scans.

---

## 8. The curated dataset, checked against its own sources

`data/structural/*.json` is hand-researched engineering data compiled by reading
the source PDFs. Nobody had checked it against them since. One reader verified
30 checkable claims across five of the seven files, reading rendered pages
visually rather than trusting OCR.

| Verdict | Claims |
|---|---|
| confirmed | 25 |
| **contradicted** | **4** |
| unverifiable | 1 |

Four errors in 30 checkable claims, in the file the rest of the corpus leans on
most. Each was confirmed against a rendered page, and three of the four were
cross-checked against Barrette's parallel entry for the same fact, which is
correct — so these are transcription errors in one file, not ambiguity in the
sources.

**Critical — `certainteed-bufftech-structural.json`, `wind_load_tables[0].table[1]`.**
The Exposure B / 24″ footing / 66″ spacing row is labelled `HVHZ and Non-HVHZ`.
Sheet 9 of 9 of NOA 23-0314.05 brackets it under `NON HVHZ` only, together with
the B / 30″ / 97″ row. This is the pre-flagged error, independently re-confirmed,
and it is the kind that matters: it would license a 24″ footing in a
high-velocity hurricane zone where the source does not.

**Major — engineer's licence jurisdiction.** `engineering_letters[2]` records
Robert Nieminen as holding *Connecticut* licence 59166. His seal on the Brookline
drawing, and again on the 2025 Barrette NOA, reads `STATE OF FLORIDA`. The firm's
office is in Oxford, CT; the licence is Florida-issued. For a document whose
whole purpose is Florida code compliance, the jurisdiction of the seal is not a
detail.

**Major — wrong material and product for NOA 22-0616.10.** Recorded as `SimTek
Fence` with material `Cementitious`. The cover page's DESCRIPTION field reads
`Polyethylene Plastic Shell Fence`, and the word "cementitious" appears nowhere
in the document.

**Major — three components conflated.** The hat-shaped insert (item D) is
recorded as `4.500 in wide … 0.080 in / 0.036 in wall`. The drawing dimensions
item D at 2.750″ base width with a single 0.080″ wall; 4.500″ belongs to item
P/P1 and the 0.036″ wall to item I, the hourglass insert.

**Unverifiable, not wrong:** the Weatherables Captiva per-piece BOM breakdown
cites a CAD PNG that shows only overall panel dimensions. Recorded as
unverifiable rather than contradicted, which is the correct call.

### Not corrected

`data/` is read-only corpus. These four entries have **not** been edited, and the
reader was instructed not to edit them. The findings are recorded here and in
`workspace/tests/agent-verify-structural-json.json`, with the page and the quoted
source text for each, so a decision to amend the dataset can be made deliberately
and by whoever owns it.

Two files — `wam-bam-structural.json` and `industry-standards-structural.json` —
carry no local-PDF-backed numeric claims this method can check, and were not
scored. Coverage is therefore 30 claims of roughly 111 list entries: a sample,
not an exhaustive audit.

## 9. Cost

Seven concurrent Sonnet agents, 44 page images plus ~30 source-page renders,
roughly 810k subagent tokens and about 32 minutes of wall clock for the six
page-reading agents; the dataset verifier ran longer at 239k tokens and 32
minutes on its own.

## 10. What round 2 should cover

Unverified material, in the order I would take it:

1. **The 81 mojibake-rejected pages** in six Wam Bam guides. Extraction switched
   them to OCR; nobody has checked that the OCR recovered the content rather than
   different garbage.
2. **The 202 `ocr_supplement` elements.** The second-resolution pass was
   validated on one document by inspection. Whether it adds signal or noise
   across the corpus is unmeasured.
3. **The remaining ~81 curated-dataset claims**, including the two files this
   round could not score.
4. **The six CAD PNGs**, which yield 76 labels between them and are known poor.
5. **The 140 distinct pages OCR'd below 70% confidence** that are *not* in the
   flagged-table set — the largest unexamined block, and now known to be where
   numbers go missing.
