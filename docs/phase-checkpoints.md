# Phase checkpoints

One entry per phase of `guide.md`, in the form the guide requires: what was
implemented, what was tested, what remains incomplete, known extraction
failures, decisions made, and the evidence that acceptance criteria passed.

Numbers here are measured, not estimated. Where a capability does not work on
this corpus, that is stated rather than omitted.

---

## Phase 0 — Environment and corpus inspection

**Implemented.** `fence_evidence.paths` (read-only corpus guard),
`fence_evidence.ids` (stable identifiers), `fence_evidence.manifest`
(`workspace/catalog/corpus-manifest.jsonl`), and the four inspection reports in
`workspace/reports/`.

**Tested.** `tests/test_safety.py` proves the write guard refuses `manuals/`,
`data/`, `master-dataset.json` and a symlink escape, and that `tools.run`
rejects string commands. `tests/test_units.py` covers id stability and version
status derivation.

**Evidence the plan's counts hold.** The manifest reconciles exactly with
`rag-pipeline-plan.md`: 137 PDFs, 115 with a text layer, 22 scans, 6 CAD PNGs,
1 DOCX. Newly measured: 2140 PDF pages, of which 358 are inside the scanned
documents. 144 corpus files in total, all present on disk, none referenced but
missing.

**What the plan did not capture, found here.** Six documents carry a text layer
that decodes to mojibake; 14 groups of byte-identical duplicates filed under
different manufacturers; one AES-encrypted PDF; 12 documents with a text layer
on some pages and none on others.

**Decisions.** Document identity is derived from the source path so it survives
re-ingestion; content identity is the SHA-256, kept separately as a version.
Version status starts conservative (`unknown` unless the corpus says otherwise)
and is upgraded later from evidence inside the documents.

---

## Phase 1 — Ten-document preservation pilot

**Implemented.** `extract.py` (PDF text layer with word boxes, OCR via hOCR,
DOCX via stdlib zip/XML, CAD raster), `layout.py` (words → lines → blocks →
elements, heading inference, running heading path), `tables.py` (pdfplumber
backend, prose-rejecting validator, OCR word-grid reconstruction, vector-figure
detection), `quality.py` (mojibake detection), `pilot.py` (the ten documents and
their stated reasons).

**Tested.** `tests/test_preservation.py` — 14 assertions over all ten documents:
hierarchy, page images present and non-empty, page count equals the source page
count, OCR text and confidence for scanned inputs, OCR never in the source-text
column, table cells, figures/drawings, drawing labels with boxes, every bbox
inside its page, curated metadata carried, full provenance chain to tool
versions, and superseded/active kept as separate records.

**Evidence.** All 102 tests pass. Pilot store: 10 documents, 314 pages, 13,259
elements, 226 tables, 10,682 table cells, 1,746 image assets, 157 quality
issues.

**Known extraction failures.**
1. Scanned NOA drawing sheets OCR at ~50% mean word confidence. Table cell
   grids cannot be rebuilt from them without inventing values, so they are not:
   a `table_not_reconstructed` issue is recorded and the page image is the
   faithful representation. Raising the render resolution from 300 to 400 and
   500 dpi did not improve confidence.
2. The OCR word-grid table reconstructor, measured across sampled pages of the
   scanned NOAs and Showtech catalogs, accepted **no** grid. It is retained,
   unit-tested, and reported as producing nothing on this corpus.
3. A DOCX has no page geometry and no renderer is available in this
   environment, so it yields no page image and no bounding boxes. Recorded as a
   `no_page_image_for_docx` issue; hierarchy and table extraction still apply.
4. The ARCAT DOCX contains no `<w:tbl>` at all, so the pilot does not assert
   tables for it.

**Defects found and fixed during the pilot.**
- Pages with `/Rotate 90` had text boxes in unrotated coordinates while the
  rendered image was rotated, putting every box outside the page. Fixed by
  reading per-page rotation and transforming boxes into rendered space.
- The scan of a page was being emitted as a "figure" on that page. Suppressed.
- Vector illustrations produced no figures at all because `page.images` is
  empty for vector art. Added grid-based connected-component detection.
- pdfplumber's text-alignment strategy sliced prose into fake table cells.
  Added a validator that rejects grids whose adjacent cells look mid-word split.
- Mojibake text layers passed the character-count scan test. Added per-page
  control-character and ASCII-token-ratio detection that routes those pages to
  OCR.
- OCR boxes could exceed the page by a fraction of a point. Clamped.

---

## Phase 2 — Canonical evidence store

**Implemented.** `store.py`: the eleven canonical tables plus the derived
projection, with foreign keys enforced. Canonical rows hold source text and OCR
text in separate columns; `retrieval_units` and `retrieval_fts` are derived and
rebuildable.

**Tested.** `tests/test_idempotency.py` proves an already-ingested version is
recognised as current, a changed tool fingerprint forces re-extraction, no
duplicate element ordinals or page rows exist, every element resolves to a page
and every version to an extraction run, and — the point of the design —
dropping and rebuilding the projection reproduces byte-identical rows without
touching a source file.

**Decision.** Heading elements are canonical but are deliberately **not**
projected as standalone retrieval units; their text reaches the index through
the `heading_path` column of the units beneath them. Indexing them separately
produced one- and two-word units whose BM25 length normalisation outranked the
tables and OCR paragraphs that hold the answers.

---

## Phase 3 — FTS5 retrieval MVP

**Implemented.** All six interfaces from the spec: `search_evidence`,
`get_document`, `get_page`, `get_region`, `get_element_context`,
`resolve_document_version`. Natural-language questions are translated to FTS5
MATCH expressions that re-issue identifiers (`23-0314.05`) and measurements
(`130 mph`) as phrases, because the unicode61 tokenizer splits both, and OR-join
the rest so BM25 ranks partial matches instead of an AND requirement returning
nothing.

**Tested.** `tests/test_contract.py` — every field of the response contract
present and correctly typed, every `page_image_path` resolvable on disk, bboxes
four numbers or null, `matched_terms` derived from the result text rather than
echoed from the query, filters applied, unsupported filters and modes rejected,
accessors returning `None` for unknown ids, and version resolution over the
supersession chain.

---

## Phase 4 — Evaluation gate

**Implemented.** `evaluate.py` and a 44-question annotated gold set
(`eval/gold-questions-structural.json`, `eval/gold-questions-general.json`)
spanning all twelve query categories the guide names, each question verified
against the source page by opening it — including OCR and visual reading of
scanned pages — and recording the command used and a literal quote.

**Tested.** `tests/test_gold_set.py` checks the set is well-formed, spans at
least ten categories, names only paths that exist in the corpus, annotates every
answerable question with answer terms, keeps no-answer questions free of
expected documents, and records a verification method for every question.

**Evidence — pilot gate (18 of 44 questions runnable; the rest name documents
outside the pilot).**

| Metric | Value | Criterion |
|---|---|---|
| document recall@10 | 0.800 | A3 ≥ 0.80 — pass |
| evidence support (terms in the retrieved unit) | 0.723 | A3 ≥ 0.70 — pass |
| page evidence support (terms anywhere on a retrieved page) | 0.867 | reported |
| no-answer precision | 1.000 | A4 ≥ 0.66 — pass *(superseded, see below)* |
| MRR | 0.628 | reported |

**Defect found and fixed by the gate.** The first run scored evidence support
0.624 and no-answer precision 0.000. Inspection of the failures showed short
heading units outranking the table and OCR units on the same page, and an
uncalibrated score floor. Removing heading units from the projection and
calibrating the floor at 17.0 (no-answer questions topped out at 14.2 while
every answerable question scored ≥ 20.0) fixed both. The fix required only a
projection rebuild, no re-extraction — which is the separation working as
intended.

**Caveat stated rather than hidden.** Three no-answer questions is a thin basis
for a threshold. The floor is a reported, tunable number, re-checked against the
full corpus.

> **Superseded.** The caveat was justified. The negative set was later expanded to
> 18 questions and the no-answer figures here — 1.000 on the pilot and 0.667 on
> the full corpus — did not survive. No lexical feature separates answerable from
> unanswerable questions on a properly built negative set, and the rule that
> produced 0.667 was declaring 24 of 41 *answerable* questions unsupported. The
> detector was rewritten and now scores 0.333 precision at a 0.146
> false-unsupported rate. See the recalibration entry below and G7 in
> `docs/state-and-gaps.md`. Nothing else in this Phase 4 record is affected:
> recall, evidence support and the extraction defects the gate found stand.

---

## Phase 5 — Full-corpus ingestion

**Evidence.** 144 of 144 ingestable files processed, 0 failures, in 1963 s with
ten workers. The ten pilot documents were skipped as already current, which is
the idempotency check doing its job on a real run.

| Measure | Value |
|---|---|
| documents / versions | 144 / 144 |
| pages | 2147 (every document stored exactly as many pages as its source has) |
| elements | 81,794 |
| tables / table cells | 603 / 18,472 |
| assets (page images + region crops) | 9,624 |
| relations | 100 (38 `same_content_as`, 24 `supersedes`, 14 `same_product_as`, 24 inverse edges) |
| retrieval units | 10,886 |
| quality issues | 374 |
| derived image data on disk | 4.4 GB (git-ignored, reproducible) |

**Supersession discovered from the documents themselves.** 24 `supersedes`
edges, and 8 documents had their status upgraded to `superseded` because a later
NOA names them as its previous approval. No merging: both sides keep their own
pages, elements and images.

**Quality issues, by kind.**

| Kind | Count | Meaning |
|---|---|---|
| `low_ocr_confidence` | 172 | pages OCR'd below 70% mean word confidence |
| `mojibake_text_layer` | 81 | pages whose text layer was rejected and re-OCR'd |
| `table_not_reconstructed` | 73 | pages naming conditional/tabular data whose grid OCR could not rebuild |
| `ocr_supplement_failed` | 34 | the second OCR pass exceeded tesseract's image limits on very large pages |
| `empty_page_after_ocr` | 9 | no text layer and OCR found nothing |
| `empty_page` | 3 | no elements at all |
| `encrypted_pdf` | 1 | `extra-strong-hinge-brochure.pdf` (AES, copy denied) |
| `no_page_image_for_docx` | 1 | the DOCX limitation |

Each of the three `empty_page` reports was checked against its rendered page
image: they are genuinely blank pages carrying only a page number. The 34
`ocr_supplement_failed` reports are all one document whose pages render to
27556×19489 pixels at 400 dpi, above what tesseract will allocate; the primary
OCR pass on those pages succeeded, so no content was lost, and a pixel budget
now skips the second pass on such pages with an explicit
`ocr_supplement_skipped` note instead of a failure.

**Second pass for the multi-resolution OCR fix.** 42 documents with any page
below 80% mean OCR confidence were re-ingested with `--force`, adding 202
`ocr_supplement` elements. Re-running the other 102 documents was unnecessary
and was skipped automatically.

See `workspace/reports/coverage-report.md` for the per-document table and
`workspace/reports/full-ingestion-log.jsonl` / `adhoc-ingestion-log.jsonl` for
the run logs.

### Full-corpus evaluation

| Metric | Value | Criterion |
|---|---|---|
| document recall@10 | 0.805 | A3 ≥ 0.80 — **pass** |
| evidence support (terms in the retrieved unit) | 0.623 | A3 ≥ 0.70 — **fail** |
| page evidence support (terms anywhere on a retrieved page) | 0.769 | reported |
| no-answer precision | 0.667 | A4 ≥ 0.66 — **pass** *(superseded: 0.333 on 18 negatives)* |
| MRR | 0.552 | reported |

**A3's support criterion is not met, and this is the honest number.** The gap
between 0.623 unit support and 0.769 page support is the whole story: for most
of the misses the system retrieves the right document and the right page but not
the specific unit that carries the value. A reader looking at the returned page
image has the answer; an automated consumer reading only the matched unit does
not.

Two measurement corrections were made after inspecting failures, both because
they were testing punctuation rather than content:

- Answer terms are matched against everything the result actually returns —
  `text` plus `heading_path` — because product names in these documents live in
  section headings, which the response contract returns.
- Typographic quotes and dashes are folded to ASCII on both sides, because
  sources write inches as `8”` while annotations and extraction disagree about
  the glyph.

**One ranking experiment, measured and rejected.** Raising the `heading_path`
BM25 weight from 0.55 to 1.6 improves recall@10 to 0.854 and MRR to 0.683, but
drops no-answer precision from 0.667 to 0.333 — it makes weak heading matches
look strong. The baseline weights were kept. Recorded here so the trade-off does
not have to be rediscovered:

| weights (text, heading, title, mfr, doc_type) | recall@10 | unit support | MRR | no-answer |
|---|---|---|---|---|
| 1.0, 0.55, 0.45, 0.25, 0.15 (**kept**) | 0.805 | 0.623 | 0.552 | 0.667 |
| 1.0, 1.0, 0.7, 0.3, 0.15 | 0.805 | 0.598 | 0.623 | 0.667 |
| 1.0, 1.6, 1.0, 0.4, 0.2 | 0.854 | 0.619 | 0.683 | 0.333 |

**Known annotation defect, not corrected.** `gq-104` expects the literal string
`Cross Buck Fence Gate Installation Guide`, which does not occur anywhere in the
document it names. It is left as authored: silently editing a benchmark to make
a metric pass would destroy its value. It costs roughly 0.02 of unit support.

---

## Phase 6 — Structured technical facts

**Implemented.** `facts.py`: a documented regex extractor (`extractor='regex-v1'`)
over canonical elements, producing 1,664 facts with mandatory provenance —
document, version, page, element, evidence text — the original wording, the
normalised value beside it, the conditions it holds under, and a review status.
271 are `flagged` rather than `extracted` because they were read from OCR text on
a page below 80% mean word confidence.

| Fact type | Count |
|---|---|
| reinforcement | 656 |
| approval_id | 271 |
| wind_speed_mph | 269 |
| footing_depth_in | 149 |
| depth_below_grade_in | 100 |
| effective_date | 84 |
| expiration_date | 75 |
| footing_diameter_in | 37 |
| exposure_category | 15 |
| racking_degrees | 5 |
| post_spacing_in | 3 |

**Tested.** `tests/test_facts.py`: every fact resolves to a real element, none
lacks a page or evidence text, every low-confidence OCR fact is flagged, the
original value is never discarded, and unit conversion keeps feet-in-the-source
readable as feet.

**Three defects found by spot-checking the output and fixed.**
1. `40 1/2" On Center` yielded a 2-inch post spacing: the number half of a
   fraction was being captured on its own. Fixed with a negative lookbehind.
2. A `wind_speed_mph` fact of 210 mph carried `wind_speed_mph: 105` as its
   *condition*, derived independently from surrounding text. A fact that is its
   own condition no longer re-derives it.
3. `4" below grade` — which in these manuals usually says where the concrete
   stops, not how deep the footing goes — was being stored as
   `footing_depth_in`. It is now its own `depth_below_grade_in` type so the two
   are not conflated.

Per-type plausibility ranges were added so an implausible value is dropped
rather than stored for a reviewer to refute.

**What this layer honestly is not.** `post_spacing_in` yields only 3 facts, and
that is the expected consequence of the scanned-table limitation: the real
post-spacing values live in the NOA drawing tables whose cells were never
recovered. The extractor finds values stated in prose or in a recovered cell,
and nothing else. See `workspace/reports/facts-report.md`.

---

## Phase 7 — Retrieval experiments

**Not entered.** No enhancement is implemented — no vector store, no reranker,
no visual retrieval. `workspace/reports/evaluation-report.md` generates, from the
measured failures only, the experiment each failing category would justify and
the acceptance criterion it would have to meet, in the guide's
Problem/Experiment/Acceptance form.

The three failures with the strongest evidence behind them:

1. **Conditional table lookup** (3 of 7 passing). The values live in scanned
   drawing tables that OCR cannot rebuild into cells. The experiment is
   table-aware structured lookup over `table_cells` and `facts`, with
   "outside documented range" as a first-class answer — noting that the guide's
   own example query (130 mph) is outside the 75 mph fastest-mile / 115 mph gust
   rating these products actually carry.
2. **Unit granularity** (the 0.623 vs 0.769 support gap). The right page is
   retrieved but not the unit holding the value. The experiment is a second
   retrieval pass within a matched page, accepted only if it raises unit support
   without lowering recall.
3. **Paraphrase** (2 of 5 passing). Exactly the failure category the guide
   predicts for lexical retrieval, and the only one that would justify dense
   semantic retrieval — on the pilot corpus first, accepted only if it does not
   reduce identifier or table lookup performance.

---

## Independent review responses

An independent read-only review of the pipeline is in
`workspace/reports/independent-review.md`. Every finding was re-verified before
acting on it; what changed is recorded here.

### 1. The page-rotation transform was wrong (accepted, fixed)

The review claimed `_rotate_word` double-rotated word boxes because
`pdftotext -bbox-layout` already reports them in display space. I verified this
independently by generating minimal PDFs with `/Rotate` 0, 90, 180 and 270, a
single word at a known position, rendering each at 72 dpi and comparing the
reported box against the rendered ink:

| /Rotate | page attrs | reported word box | rendered size | measured ink |
|---|---|---|---|---|
| 0 | 612×792 | 72.0, 74.8, 141.3, 97.0 | 612×792 | 74, 75, 141, 92 |
| 90 | 612×792 | 695.0, 72.0, 717.2, 141.3 | 792×612 | 700, 74, 717, 140 |
| 180 | 612×792 | 470.7, 695.0, 540.0, 717.2 | 612×792 | 471, 700, 538, 717 |
| 270 | 612×792 | 74.8, 470.7, 97.0, 540.0 | 792×612 | 75, 471, 92, 538 |

The boxes match the ink at every rotation while the page attributes stay
unrotated. The transform was deleted; the page-rectangle swap it sat next to is
correct and kept. The tests that pinned the wrong arithmetic were replaced with
tests of the documented behaviour. The bug was latent — no page in this corpus
has both a non-zero `/Rotate` and a text layer — but it would have corrupted
every box on the first such document.

### 2. Retrieval units could merge across two versions of a document (accepted, fixed)

The merge guard compared page and heading path but not `version_id`, so two
versions of one document could collapse into a unit whose `version_id` named
only one of them. Latent today (every document has exactly one version) and
fixed by adding `version_id` to the guard and to the element ordering.
`get_page`, `get_element_context` and the facts extractor were scoped to the
newest version for the same reason.

### 3. Resumability was nominal (accepted, fixed)

Two real problems. `version_exists` required the extraction *run* to have
finished, so an interrupted run made every document it had already written look
stale and forced a full re-extraction; completion is now judged from the version
row — written in the same transaction as its pages and elements — plus a check
that the version actually carries pages. And the retrieval projection was built
only at the end of a run, so an interrupted run left nothing searchable; it is
now built per document as each one lands, with the whole-store rebuild kept at
the end. A dying worker pool no longer skips relation derivation, projection and
`finish_run`: the pool loop is wrapped so the run is always closed out and the
error is recorded in the log and the summary.

### 4. Tests wrote to the live store (accepted, fixed)

`test_idempotency` rebuilt the projection in place and `test_contract` triggered
`get_region`'s on-demand crop cache, both of which mutate the database someone
else may be using. Those classes now copy the store to a snapshot under
`workspace/tests/snapshots/` — inside the workspace, because the write guard
applies to tests too.

### 5. `scripts/build_master.py` writes to `data/` unguarded (noted, not changed)

Correct as an observation, but out of scope for this system and deliberately
left alone. That script is the repository's pre-existing dataset builder and
those two files are its own generated outputs, documented as such in
`CLAUDE.md`. The prohibition applies to the evidence pipeline, which reads
`data/documents-index.json` and never writes anywhere outside `workspace/` —
enforced by `paths.ensure_writable` and tested in `tests/test_safety.py`. The
boundary is worth stating: if that script is re-run, the manifest's curated
metadata inputs can change, which is why every manifest row records the SHA-256
it was built from.

### Extraction improvement adopted from the gold-set work

While annotating the benchmark, the structural question set showed that OCR on
these scans is resolution-unstable: individual numbers and dimension callouts
appear at one render resolution and vanish at another. Pages whose mean word
confidence is below 80 now get a second OCR pass at 400 dpi, and tokens found
only there are stored as an additive `ocr_supplement` element with its own
provenance — never merged into or over the primary pass. On the current
CertainTeed NOA this recovered, among others, the post-stiffener specification
text and the PE licence number `52609`, neither of which the 300 dpi pass found.

---

## Post-MVP work

### Relevance audit of the retrieval projection

**Implemented.** `fence_evidence.audit` and
`workspace/reports/projection-relevance-audit.md`, re-runnable with
`python3 -m fence_evidence.cli audit` (read-only, opens the store `mode=ro`).

**Findings, ten, all measured.** The two with consequences: heading elements are
excluded from the projection and 7,097 of them (33.9%) are reachable through no
unit's `heading_path` either, leaving 27 pages absent from the index entirely;
and 46.5% of units duplicate another unit's text, which spends 29.5% of top-10
slots on duplicated text and 20.2% on pages already in the list, so a 10-result
list averages 7.98 distinct pages.

**Not applied.** Nine recommendations are recorded with the risk that argues
against each, and none has been acted on: classification and indexing are held
pending review of the audit.

### Second-stage within-page element retrieval — rejected

**Implemented** at retrieval time only, so it touches no indexing. **Measured**
at unit support 0.672 against a 0.70 acceptance target, with document recall
(0.805), page support (0.769), no-answer precision (0.333) and the
false-unsupported rate (0.146) all unchanged to three decimals. **Rejected** as
default and retained behind `second_stage=False`; `--second-stage` opts in on
`cli search` and `cli evaluate`. Full trail, including the replacement design
that scored 0.540 and the information-floor trade-off, in
`docs/second-stage-evaluation.md`.

### No-answer category expanded, then recalibrated

**Implemented.** `eval/gold-questions-no-answer.json`: 15 new negatives in three
classes — absent-subject, adjacent-vocabulary and near-miss — each with proven
absence, taking the negative set from 3 to 18 and the benchmark to 59 questions.

**Measured.** No lexical feature separates the classes. Answerable vs
unanswerable means: rarest query term present in the best result 0.244 vs 0.444
(the wrong direction), term coverage 0.733 vs 0.747, score margin 0.248 vs
0.294, top relevance 22.3 vs 20.5 on a 9–50 range.

**Changed.** The score floor and rarest-term heuristics were removed as
measurably non-discriminative. What remains fires only for a checkable reason.
A4b was added to the spec so the two sides are always reported together.

### Date-aware conservative version resolution

**Implemented.** `fence_evidence.versions`, read at query time from the Phase 6
`effective_date` and `expiration_date` facts, which cover all 17 NOA documents.
Disagreeing facts yield a conflict rather than a value; every date carries its
element, page and review status; an expiry verdict always echoes the date it was
judged against; an expired member is never offered as active; stored
classification is never written from resolution.

**Bug found and fixed.** The status update marked the `to` side of a
`superseded_by` edge, which is the *newer* approval. Every current NOA was
therefore labelled superseded and the CertainTeed→Barrette chain resolved with no
active member at all. After the fix, NOA 24-0117.05 and its three duplicate
filings are no longer superseded and the 2006 approval 06-1019.01 correctly is.
`tests/test_versions.py` asserts the direction in both directions.

### Scanned NOA table reading — designed, not run

**Designed.** `docs/experiment-noa-table-reading.md`: four stages, per-cell OCR
with abstention on disagreement, a `table_read_candidates` table, and a review
gate that forbids promoting any numeric fact without a human accepting that
specific cell against its crop. One confidently-wrong numeric cell fails the
experiment outright.

**Input built.** `cli noa-table-crops` writes 44 full-page crops with SHA-256s
and a manifest; the 73 flagged pages deduplicate to 44 distinct contents. No
values are read.
