# Parser tool evaluation — six projects, measured against this platform

```text
Status:   FINDINGS, 2026-09-15. No tool adopted. Nothing in this document changes
          how the platform works today.
Scope:    docling · marker · MinerU · ColPali · RAGFlow (+ DeepDoc) · kotaemon
Method:   source, docs, package registries and issue trackers. NONE of the six was
          installed or run. Every claim here is a reading of primary material, not
          a measurement of our corpus.
Prompted: the project owner's judgement that the platform is "working hard and
          staying in place", and a request to simplify by adopting existing tools.
```

The one-line answer: **every one of these tools competes for 7% of this
codebase, and the attrition that stalls publication is entirely downstream of
that 7%.** Adopting one is defensible for a narrow purpose. Adopting one as a
way to make progress is not.

Read `docs/state-and-gaps.md` for the live numbers; this file's figures were
measured on 2026-09-15 and will drift.

---

## 1. What was measured about ourselves first

`[measured]` 2026-09-15, 31,932 lines of code and 1,906 test functions,
classified by purpose:

| Bucket | Code | % | Test fns | % |
|---|---:|---:|---:|---:|
| **PARSE** — text/tables/layout/images out of a PDF | **2,331** | **7.3%** | **104** | **5.5%** |
| RETRIEVE — search, index, ranking, evaluation | 2,885 | 9.0% | 213 | 11.2% |
| CURATE — review loop, ledger, promotion rules, console | 4,592 | 14.4% | 267 | 14.0% |
| PUBLISH — canonical bytes, snapshot, refs, tenancy, API | 4,998 | 15.7% | 463 | 24.3% |
| DOMAIN — facts, parameters, parts, procedures, per-product | 10,894 | 34.1% | 611 | 32.1% |
| PLUMBING — cli, store, paths, fetch, manifest | 6,232 | 19.5% | 248 | 13.0% |

PARSE is `extract` (806), `tables` (637), `layout` (240), `noa_tables` (175),
`assets` (108), `lang` (90), `model` (86), `tools` (72), `quality` (66),
`hocr` (51). Ambiguous calls are recorded in §6.

Note the asymmetry: PUBLISH is 15.7% of the code and **24.3% of the tests**.

### The attrition

```text
82,282 elements  ──÷41──▶  2,003 facts  ──÷19──▶  108 promoted  ──÷12──▶  9 ParameterTables
                                         (needs a person)
```

Four orders of magnitude, **every order downstream of parsing**. Supporting
counts the same day: 275 human review acts ever by one reviewer; 1,927 machine
readings over 44 crops, of which 524 sit at `cross_family_verified` and publish
nothing by design (CUR-S0); **2,312 step candidates and 0 step reviews**;
7 of 146 documents carry any promoted table fact.

### The addressable surface

**73 pages across 13 documents** carry a `table_not_reconstructed` issue — 3.4%
of pages, 8.9% of documents. That is the entire surface any new parser could
address. Parsed perfectly, those 73 pages produce more *unreviewed candidates*,
not more published knowledge.

---

## 2. The cost of a parser swap

`ref_id = sha256("{doc_sha}:{page}:{bbox}")[:16]` hashes `elements.bbox` **as
the stored text**, a JSON list rounded to 2 decimals by `extract._clamp_elements`.

- A measured **0.02 pt** shift changes the id completely.
- **962 distinct published `ref_id`s** across 25 live snapshots; all resolve today.
- **716 of 962 (74%) embed a bbox** and break on any coordinate-convention or
  segmentation change. 246 are page-level and would survive.

**The worse coupling is the human work, not the citations.** `table_reviews` is
keyed on `crop_sha256` — the SHA-256 of the rendered crop PNG — and
`submit_review` re-hashes the file and refuses a mismatch. A different parser
cuts a different rectangle, so the bytes change, so **71 table reviews over 37
crops stop rejoining anything**. The 204 fact reviews anchor on
`(element_id, fact_type, value_before)` and `element_id` carries an ordinal, so
re-segmentation exposes them too.

`workspace/catalog/review-ledger.jsonl` is the only artifact here that does not
regenerate.

**Therefore: any adoption sits behind an extraction edition** — the scheme
`docs/four-layer-model-design.md` §5.1 and G38 already call for. New parsing
produces a new edition; it never moves coordinates under a published citation.

---

## 3. The six

| Project | Verdict | The deciding fact |
|---|---|---|
| **docling** | **adopt, narrowly** | `TableCell` carries `bbox` + `row_span` + `col_span` per cell; `ProvenanceItem` is `page_no` + `bbox` + `charspan`. Default pipeline is discriminative — it never writes text it did not read. MIT code, Apache-2.0 / CDLA-permissive weights. |
| **DeepDoc** (`deepdoc/server`) | **trial** | Standalone CPU ONNX HTTP service, ~100 MB weights, **no database**. `/predict/tsr` returns table structure including **spanning cells**. Out-of-process, so it stays genuinely optional. |
| MinerU | no | Table output is one table-level bbox plus HTML — **no per-cell geometry** — and **no confidence score at all**. |
| marker | no | On scanned pages the VLM path returns block-level HTML with **no sub-block boxes**, which is precisely where we need precision. |
| ColPali | no | No decoder runs. Output is a float tensor and one score per page: it cannot emit a value, and one patch ≈ 19 pt is larger than a table cell. |
| RAGFlow (platform) | no | Four mandatory stateful services, 16 GB RAM, a root `sysctl`, no documented non-Docker path. Chunk edits are destructive and erased on re-parse. |
| kotaemon | no | Discards coordinates during ingestion on purpose. No commit on `main` in 3.5 months; an unfixed cross-user IDOR open since 2026-07. |

### 3.1 Findings that generalise beyond any one tool

**No project in this survey has a human-review layer.** A full-tree grep of
RAGFlow (6,922 paths) returns **zero** hits for `audit` and zero for `approv`;
kotaemon returns one, unrelated. Neither has reviewer identity, an approval
state, or a durable record of a judgement. RAGFlow's advertised "visual chunk
editing" is a destructive `PATCH` into a 92-field schema that has `create_time`
and **no `update_time`, no `updated_by`, no `review_status`**; the edit is
erased when the document is re-parsed.

> Our review loop is not a missing feature we could adopt from the ecosystem.
> It is the part we have that the ecosystem does not.

**An honest failure beats a fluent guess.** Tesseract reporting ~50%
confidence on those 73 pages is *telling the truth*, and that refusal is what
routes the page to `table_not_reconstructed` and then to a person. Fluent
parsers return well-formed output with no confidence attached. MinerU issue
#4001: a government contract PDF where source `$6000.00` became **`$60000.00`**
— correct-looking HTML, silent tenfold error, no signal. For a platform whose
contract is "never publish a number you cannot defend", that is a **downgrade**.

**A model may propose text. It must never propose location.** ViDoRe V3
(ACL 2026, 12,000 hours of human annotation) measured bbox grounding: human
inter-annotator agreement **F1 0.602**; best models **0.089** (Qwen3-VL-30B) and
**0.065** (Gemini 3 Pro); on pages where humans drew boxes the models annotated
the same page only **16–17%** of the time, and **26–27%** of human-annotated
pages received no model annotation at all. Coordinates must keep coming from
`crops.py`, whose transform is matched to `assets.width_px` within 1 px across
2,140 pages.

**Determinism is not free and is measurable.** A pinned community run of
OmniDocBench v1.6 (1,651 pages) found MinerU's `pipeline` backend
**byte-identical across runs** and its VLM backend showing **run-to-run drift**
under vLLM + bf16 — greedy decoding is the default and is not sufficient.
docling's default pipeline is discriminative and has no sampling, but issue
#3329 reports the same PDF yielding a different layout classification on
macOS ARM vs Linux x86_64, and issue #1451 ("Is it possible to make the
processing deterministic?") has been open and unanswered since 2025-04. Our
snapshots are hashed and write-once; this is a first-class constraint, not a
quality preference.

**Loud failure beats a quiet empty page.** The same MinerU run measured
**0.12% of pages (2 of 1,651) silently producing empty output** on clean
benchmark material. MinerU's run manifests mark such a page `pending` and fail
the whole run. We file `empty_page_after_ocr` (9 instances) and continue. The
manifest behaviour is worth copying regardless of adoption.

### 3.2 Evidence quality caveats

- **No benchmark covers our documents.** OmniDocBench's categories are academic
  literature, slides, books, textbooks, exam papers, notes, magazines, research
  reports and newspapers. There is **no engineering-drawing, blueprint, form or
  permit category**. ViDoRe v1 is slides, infographics and reports.
- **The one cell we need is empty.** MinerU publishes 33.7 on olmOCR-Bench "Old
  Scans" (that is *text* on scans, 7th of 9 models) and 60.4 / 2.9 on
  OmniDocBench v1.0 borderless / rotated tables (that is *tables* on
  **born-digital** pages, MinerU 1.x). **No published evaluation crosses
  "borderless" with "scanned."** Our 73 pages are that intersection.
- **The maintainer's own view**, MinerU issue #5169: *"it may not perform as
  well for engineering drawings like the ones you provided … Engineering
  drawings like your examples are not the most common document layout type, so
  they are more likely to show quality degradation."* Note the hosted
  mineru.net API is pinned to the `effort=medium` mode named there; any
  evaluation via the hosted demo understates self-hosting.
- **Licensing was assessed and then set aside.** The owner confirmed this
  deployment is personal and non-commercial, so marker's OpenRAIL-M revenue and
  non-compete clauses, the Gemma pass-through terms, and Qwen2.5-VL-3B's
  non-commercial licence do not bind. They *would* bind a commercial
  deployment and are recorded here for that reason. RAGFlow's licence, contrary
  to an assumption made during this review, is **plain Apache-2.0 and has never
  changed** — one commit in `LICENSE` history, 2023-12-12.
- **Issue-tracker sourcing needs author checks.** Several confident technical
  claims in MinerU's tracker come from `dosubot`, an AI assistant, not a
  maintainer. Observed failures still stand; bot *diagnoses* do not.

---

## 4. The proposal for the 73 pages

Our documented failure on those pages is *"tables cannot be rebuilt into
cells"* — a **structure** problem, not a reading problem. That suggests a split
rather than a replacement:

```text
  page image (ours)
        ├──▶ DeepDoc /predict/tsr  ──▶ cell + spanning-cell geometry, with a score
        └──▶ tesseract per cell    ──▶ glyphs, with honest confidence
                                          │
                                          ▼
                             candidate reading ──▶ a person accepts ──▶ published
```

This takes the thing we lack (cell geometry, including spans — what
`backfill-spans` reconstructs by hand for G41) without importing the thing that
would hurt us (fluent output with no confidence). The bbox still comes from our
own crop machinery.

**One caution:** DeepDoc's OSS *text-recognition* endpoint returns
`confidence: 1.0` unconditionally and must not be used. Its layout (`/predict/dla`)
and table-structure (`/predict/tsr`) endpoints do return detection scores.
RAGFlow's FAQ also states the hosted demo's DeepDoc models are *"pre-trained
using proprietary data"* — the OSS weights are the weaker ones.

**This is a hypothesis, not a finding.** It has not been run against a single
page of our corpus.

### The test that would settle it

Run all **73** unreconstructed pages through docling and through
`/predict/tsr`. Three questions, none of which any benchmark answers:

1. Does the page come back as one undifferentiated image? (MinerU #1084 /
   #5169 mode — A0 scanned sheets recognised as a single image.)
2. Do cells come back with geometry, and do the boxes land on actual cells?
3. Are the **numbers right**, not merely present? (#4001 is a correct-looking
   tenfold error; #4941 drops row labels while numbers parse fine.)

Roughly a day. If it fails, we stop, having spent a day.

---

## 5. What the evaluation says to do instead

Ordered by what moves a published count — which reverses the order these were
investigated in.

1. **Run the step review sitting.** 559 machine proposals are imported against
   `bufftech-gate-install-guide.pdf` and were proven end-to-end on a throwaway
   copy of the store: applied as reviews they produced **26 Procedures, 514
   AssemblySteps, `verify()` PASS**. This is the only measured path from zero to
   a published `Procedure`. Cost: one sitting.
2. **Build the parts builder and delete the bespoke modules.** 17,792 collected
   names have nowhere to go, which is why 42 `Part`s are hand-written Python.
   `scripts/advance_*` + `scripts/prepare_*_consumer_model.py` (2,393 lines) and
   `{augusta,pembroke,emblem}_*.py` (1,459 lines) = **3,852 lines producing 26
   published Parts across three products** — about 148 lines per Part, reusable
   on zero other documents. Against that, `step_proposals.py` is **464 generic
   lines that produced 514 published steps** and works on the next document with
   no new Python. Every bespoke module is a pipeline that did not get built.
3. **Then, and only then, test a parser on the 73 pages.**

---

## 6. Classification calls a reader may disagree with

- `model.py` (86) → PARSE; arguably PLUMBING. Immaterial.
- `assets.py` (108) → PARSE (it drives poppler), not PLUMBING.
- `noa_tables.py` (175) → PARSE, because a better parser would eliminate it.
  Counting it CURATE drops PARSE to 6.7%.
- `crops.py` / `cropcache.py` (503) → PUBLISH, because they exist to back
  `GET /source-refs/{id}`, despite being poppler-shaped.
- `query.py` (633) → RETRIEVE; as PUBLISH the split is 7.0% / 17.7%.
- `versions.py` + `relations.py` (890) → DOMAIN (the Miami-Dade approval
  lifecycle is fence-specific), not PLUMBING.
- `steps.py` (634) → DOMAIN vs `step_proposals.py` (464) → CURATE. A coin flip.

None of these calls moves PARSE far enough to change the conclusion.

---

## 7. Sources

Everything above is traceable to primary material. The load-bearing ones:

- docling — `github.com/docling-project/docling`, `docling-core` type
  definitions, the technical report `arXiv:2408.09869`, issues #1451, #3329,
  #4217, #2756, #2076, #4083
- marker — `github.com/datalab-to/marker` (v2.0.0, 2026-07-20; the
  `VikParuchuri/marker` URL redirects), `datalab-to/surya` `MODEL_LICENSE`,
  issues #1081, #1069, #1084, #1105
- MinerU — `github.com/opendatalab/MinerU`, `arXiv:2509.22186`, the output-files
  reference, issues #5288 (determinism), #5169 (maintainer on drawings), #1084,
  #3612, #4001, #4023, #4311, #4941, #5438, #5472
- ColPali — `github.com/illuin-tech/colpali`, `arXiv:2407.01449`, ViDoRe V3
  `arXiv:2601.08620`, patch-to-region `arXiv:2512.02660`, engineering-drawing
  result `arXiv:2602.14162` (single-author preprint, ColPali v1.2, unreviewed),
  issues #274, #11, #384
- RAGFlow — `github.com/infiniflow/ragflow`, `deepdoc/server/README.md`,
  `ragflow.io/docs/http_api_reference`, issues #19350, #12309, #18354, #18628
- kotaemon — `github.com/Cinnamon/kotaemon`, `flowsettings.py`,
  `unstructured_loader.py`, issues #846, #380, #786

A rendered summary of these findings was published as an artifact on
2026-09-15; this file is the durable record.
