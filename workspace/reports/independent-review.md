# Independent review — `fence_evidence` pipeline

```text
Reviewer: read-only audit
Scope:    src/fence_evidence/**, tests/**, checked against
          docs/mvp-implementation-spec.md (authoritative) and guide.md §"prohibitions"
Date:     2026-08-20
State:    a full-corpus ingest was running throughout (98 documents / 1419 pages
          committed at the time of the queries below)
```

## Verdict

The prohibition surface is in good shape: there is no `shell=True`, no `eval`/`exec`/`os.system`,
no string-built SQL that takes document or user text, no path derived from document content, and
no code path in `src/fence_evidence/` that writes, renames or deletes a corpus file — OCR text
provably never reaches `elements.text` (0 rows for both `ocr` and `image_ocr` in the live store),
superseded and active approvals are provably separate `documents` rows, and measurements keep
their original wording alongside the normalised value. The defects are elsewhere: **the page
rotation transform in `extract.py` is a double rotation and is demonstrably wrong** (proven
against rendered ink on synthetic 0/90/180/270 PDFs — it is latent only because no page in this
corpus has both `/Rotate ≠ 0` and a text layer, and a unit test enshrines the wrong arithmetic);
**the retrieval projection can merge elements from two versions of the same document**, producing
a unit whose `element_ids` contradict its `version_id`; **resumability is nominal** — completion is
recorded per *run*, not per document, and the searchable projection is built only at the very end
of `ingest()`, so an interrupted full-corpus run leaves 100+ documents ingested-but-unsearchable
and re-extracts every one of them; one unhandled parser exception on one page discards a whole
document; and `scripts/build_master.py` still overwrites `master-dataset.json` with an unguarded
`open(..., "w")`. Finally, the test suite is not read-only — it rewrites `retrieval_units` in the
live store — and its two most load-bearing gates (Phase 1 preservation, Phase 6 facts) silently
skip themselves when the store or the `facts` table is empty.

## Findings

| # | Severity | Location | Finding |
|---|---|---|---|
| F1 | high | `extract.py:48-63` | `_rotate_word` double-rotates: `pdftotext -bbox-layout` already reports words in display space (**proven**) |
| F2 | medium | `store.py:481-497` | A retrieval unit can merge elements from two versions of one document; `element_ids` then contradict `version_id` (**proven**) |
| F3 | medium | `store.py:287-296`, `ingest.py:100-101` | Completion is stamped per run, not per document, and units are built only at run end — an interrupted run discards all its work |
| F4 | medium | `ingest.py:76` | An OOM-killed worker raises `BrokenProcessPool` out of `fut.result()`, aborting relations, index build, `finish_run` and the run-end log |
| F5 | medium | `extract.py:177,271`, `hocr.py:14` | One page with unparseable hOCR/bbox XML raises past the handlers and discards the entire document (**proven**) |
| F6 | medium | `store.py:218-226` | `connect(..., read_only=True)` skips `ensure_writable` *and* still opens read-write, creating files outside `workspace/` (**proven**) |
| F7 | medium | `scripts/build_master.py:86,120`, `scripts/build_china.py:52,80` | Unguarded `open(..., "w")` over `master-dataset.json` and the curated indexes — prohibition 1 |
| F8 | medium | `facts.py:454-469,527-553` | `unit_original` records the *target* unit, and a bare `8 o.c.` normalises to 8 **inches** unflagged (**proven**) |
| F9 | low | `extract.py:100-122,365` | `_clamp_elements` silently corrects boxes, making the `bbox_out_of_page` quality check dead code |
| F10 | low | `tools.py:56-64`, `extract.py:84-100` | `render_page` writes with no `ensure_writable`; `_crop_region` swallows `CorpusWriteError` |
| F11 | low | `manifest.py:30-31` | Raw `subprocess.run(**kw)` instead of `tools.run`, bypassing the central list-only check |
| F12 | low | `tools.py:59,69`, `manifest.py:48` | poppler/tesseract argv is not `--`-terminated; a corpus filename starting with `-` would parse as an option |
| F13 | low | `retrieval.py:316-324` | `get_element_context` ignores `before`/`after` for adjacent pages and returns every element of both |
| F14 | test | `tests/test_idempotency.py:51,66`, `tests/test_contract.py:321` | The suite writes to the live evidence store (`DELETE`+rebuild of `retrieval_units`, `UPDATE elements`) |
| F15 | test | `tests/context.py:12`, `tests/test_facts.py`, `tests/test_preservation.py:105,165`, `tests/test_units.py:101` | Over-broad skips make the Phase 1 and Phase 6 gates vacuous; three assertions are weaker than the spec section they claim to enforce |

---

## F1 — `_rotate_word` double-rotates every word box on a rotated page (high, **proven**)

`extract.py:48-63` maps "unrotated" text boxes into display coordinates, and `extract.py:200-205`
applies it to every word on a page whose `/Rotate` is 90/180/270. The premise is wrong:
`pdftotext -bbox-layout` **already** emits word coordinates in display space. Only the
`<page width= height=>` attributes are the unrotated MediaBox.

Proof — four synthetic single-word PDFs (identical content stream, `/Rotate` 0/90/180/270),
rendered with `pdftoppm -r 200` exactly as `extract.py` does, with the true position measured
from the ink in the PNG:

```text
rot= 90  pdftotext page=612x792  display=792x612
   pdftotext bbox = (692.5, 72.0, 725.8, 190.0)     <-- already correct
   _rotate_word   = (602.0, 692.5, 720.0, 725.9)    <-- wrong; y1 exceeds the 612pt page
   actual ink     = (699.1,  74.9, 726.1, 188.3)
rot=180
   pdftotext bbox = (422.0, 692.5, 540.0, 725.8)    <-- already correct
   _rotate_word   = ( 72.0,  66.2, 190.0,  99.5)    <-- mirrored to the opposite corner
   actual ink     = (423.0, 699.1, 536.8, 726.1)
rot=270
   pdftotext bbox = ( 66.2, 422.0,  99.5, 540.0)    <-- already correct
   _rotate_word   = (422.0, 512.5, 540.0, 545.9)    <-- wrong
   actual ink     = ( 65.2, 423.0,  92.2, 536.8)
```

Consequences on a rotated text-layer page: every element bbox points at the wrong region, so
every `region_image_path` crops the wrong part of the page (spec §8, prohibition 11 — the image
no longer supports the text); for 90/270 the transformed boxes leave the swapped page rectangle
and `_clamp_elements` flattens them into inverted or degenerate boxes; and `HeadingClassifier`
is built from pre-rotation geometry (`extract.py:180`) while being applied to post-rotation
lines, so heading inference on those pages is decided on stale sizes.

Why it has not corrupted the store: I checked all 115 text-layer PDFs in the manifest with
`pdfinfo -f 1 -l <n>`. Exactly one file has any rotated page
(`manuals/freedom-outdoor-living/structural/Barrette-Privacy-Railing-2021-Engineering-Report-PE.pdf`,
pages 2-3 at 270°) and both of those pages have **zero** words. The corpus's other twelve
rotated documents are pure scans, which take the OCR path where the geometry comes from
`pdftoppm` (which does apply `/Rotate`) and is correct. So this is a latent bug — but it sits
on the NOA/structural documents that the system exists to answer from, and any re-scan or
re-OCR of one of them with a text layer would silently mislocate all of its evidence.

The page-size swap on the same lines (`extract.py:194`) is **correct and necessary** and must be
kept — see the false-alarm section.

Smallest correct fix: delete `_rotate_word` and the `if rot and blocks:` block at
`extract.py:200-205`, keep `rotations`/`_page_rotations` only for the `width, height` swap, and
build `HeadingClassifier` from the (unchanged) line geometry. Then fix
`tests/test_units.py:101-116`, which currently asserts the wrong arithmetic; replace it with
the ink-position property test above.

## F2 — a retrieval unit can span two versions of one document (medium, **proven**)

`store.py:447-448` selects `FROM elements WHERE document_id=? ORDER BY page_no, ordinal` — no
`version_id`. The merge guard at `store.py:492-493` checks `same_page` and `same_head` only.
When a document has more than one version, the two versions' page-1 elements interleave and merge
into a single unit.

Proof, in-memory DB built from the real `store.SCHEMA` and `store.build_retrieval_units`
(one document, versions `doc-A@old` and `doc-A@new`, two paragraphs each):

```text
units built: 1
 unit 1 version_id= doc-A@old
   element_ids: ["el-doc-A@old-0", "el-doc-A@new-0", "el-doc-A@old-1", "el-doc-A@new-1"]
   text: 'paragraph from doc-A@old one\nparagraph from doc-A@new one\n...'
```

This breaks the spec §4 invariant that every element belongs to exactly one `document_version`
and, downstream, prohibition 11: `search_evidence` reports `page_image_path` from
`LEFT JOIN pages ON p.version_id = u.version_id` (`retrieval.py:182`), i.e. the *old* version's
page image, next to text drawn from both versions. It is the same class of collapse prohibition 5
forbids, one level down (versions of a document rather than separate documents). Answering the
review's question precisely: a unit **cannot** mix two documents or two pages (verified live:
`units spanning >1 page = 0`, `>1 version = 0`), and `element_id` is always `element_ids[0]`,
so those two never disagree — but `element_ids` can contradict `version_id`.

The same omission is in `retrieval.get_page` (`retrieval.py:252-254`, `fetchone()` over
`document_id + page_no` picks an arbitrary version), `retrieval.get_element_context`
(`retrieval.py:316-321`) and `facts._iter_candidates` (`facts.py:496-503`).

Latency: the live store has 98 documents and 98 versions, and
`SELECT document_id, COUNT(*) FROM document_versions GROUP BY 1 HAVING COUNT(*)>1` returns
nothing, because document identity is the source path and the corpus is read-only. It fires the
first time a source file is edited in place or re-downloaded.

Smallest correct fix: add `version_id` to the `SELECT`'s `ORDER BY` and to the merge guard
(`buffer[0]["version_id"] == row["version_id"]`); the same predicate belongs in the three
accessors above.

## F3 — completion is stamped per run, so an interrupted run discards its work (medium)

`store.version_exists` (`store.py:287-296`) returns true only when the version's
`extraction_runs.finished_at` is non-null, and `finish_run` is called once, at the end of
`ingest()` (`ingest.py:101`). `build_retrieval_units` is likewise called once, at
`ingest.py:100`.

Measured on the live store mid-run:

```text
runs: run-...125131 finished 12:54:27
      run-...125514 finished 12:58:07
      run-...130029 finished None      <- in progress
versions whose run has finished_at IS NULL : 88   (of 98)
documents with elements but zero retrieval_units : 130+
```

So if this ingest is killed, 88 already-extracted documents will be re-extracted from scratch on
the next run, and until a run completes none of them is searchable at all. Against spec §3
Phase 5 ("resumable, idempotent, unchanged files skipped") this is idempotent but not resumable:
the per-document work is durable (see the false-alarm note on `write_extracted`'s single
transaction) yet unusable and unrecognised.

Smallest correct fix: record completion per document — either set `finished_at` on a
per-document run row, or add `document_versions.extraction_complete INTEGER` set inside
`write_extracted`'s transaction and test that in `version_exists` instead of `r.finished_at`.
Separately, call `build_retrieval_units(conn, document_id=...)` after each document (that code
path is already correct and currently has no caller) so the store is searchable incrementally.

## F4 — one dead worker aborts the whole run (medium)

`ingest.py:76` calls `fut.result()` with no guard. `_extract_one` catches `Exception` inside the
worker, but a worker that is *killed* (OOM, segfault in a native decoder) makes
`as_completed(...)`/`result()` raise `BrokenProcessPool`, which propagates out of `ingest()`.
`derive_relations`, `build_retrieval_units`, `finish_run` and the `run_end` log line are all
skipped, so the run is both unsearchable and, per F3, entirely re-done next time. During this
review the live run had a worker at 2.1 GB RSS and a `tesseract` child at 3.2 GB on a 300 dpi
render — OOM is a realistic trigger, not a hypothetical.

Smallest correct fix: wrap `fut.result()` in `try/except Exception`, record the same
`extraction_failed` quality issue that the in-worker path records, and continue; re-raise only
if the pool is unusable, after `finish_run`.

## F5 — one unparseable page discards the whole document (medium, **proven**)

Two handlers are too narrow:

* `extract.py:265-273` wraps the OCR block in `except ToolError`. `parse_hocr` does not raise
  `ToolError` — it raises `xml.etree.ElementTree.ParseError`. `hocr._strip_doctype`
  (`hocr.py:14-15`) removes only the DOCTYPE; it lacks the `_INVALID_XML_CHARS` scrub that
  `layout._strip_doctype` (`layout.py:22-34`) has for exactly this reason.
* `extract.py:174-178` catches `ET.ParseError` from `parse_bbox_layout`, but that function also
  raises `TypeError` (a `<page>` or `<word>` missing an attribute → `float(None)`) and
  `ValueError` (a non-numeric attribute).

Proven directly:

```text
hocr with a C0 control char : ParseError  (not a ToolError -> escapes extract.py:271)
<page> without width         : TypeError   (caught by `except ET.ParseError`: False)
word with xMin="NaNq"        : ValueError  (caught by `except ET.ParseError`: False)
```

Either escapes `extract_pdf`, is caught by `_extract_one` (`ingest.py:35`), and the **entire
document** is dropped with a single `extraction_failed` issue — 16 good pages lost because of
one bad one. This is recorded, so it is not a prohibition 12 violation, but it is a large
avoidable content loss and the coverage report will show the document simply as "not ingested".

Corrupt inputs at the *document* level are handled well, verified by extracting a zero-byte PDF,
a garbage PDF, a truncated real PDF and a malformed PNG (with `paths.WORKSPACE` redirected to a
scratch dir so nothing landed in `workspace/`): each returned 0 pages with `unreadable_pdf` /
`image_unreadable` recorded and no exception.

Smallest correct fix: add the `_INVALID_XML_CHARS` scrub to `hocr._strip_doctype`, and change
both handlers to `except Exception as e:` with a per-page quality issue
(`hocr_parse_failed` / `bbox_parse_failed`) so the remaining pages still extract.

## F6 — `connect(read_only=True)` disables the write guard without being read-only (medium, **proven**)

```python
# store.py:218-226
if not read_only:
    ensure_writable(path)
    path.parent.mkdir(parents=True, exist_ok=True)
conn = sqlite3.connect(str(path))          # <- read-write regardless
```

The flag does not open the database read-only; it only skips `ensure_writable`. Proven by
calling `store.connect(<path outside workspace>, read_only=True)` and then
`CREATE TABLE`/`INSERT`/`commit`: an 8192-byte SQLite file appeared outside `workspace/`. On a
corpus path this would create a file inside `manuals/` or `data/` — prohibition 1 — and I did
not run that variant for that reason. `connect(read_only=False)` on `manuals/x.db` correctly
raises `CorpusWriteError`.

No caller passes `read_only=True` today (grep: the only occurrences are the definition itself),
so this is a latent hole, not an active violation.

Smallest correct fix:

```python
if read_only:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
else:
    ensure_writable(path); path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
```

## F7 — the dataset build scripts overwrite protected files unguarded (medium)

```text
scripts/build_master.py:85-87   open(<repo>/master-dataset.json, "w")
scripts/build_master.py:119-121 open(<repo>/data/documents-index.json, "w")
scripts/build_china.py:51-53    open(<repo>/china/china-dataset.json, "w")
scripts/build_china.py:79-81    open(<repo>/china/data/china-documents-index.json, "w")
```

All four are on the read-only side of the spec §2 boundary table, and `paths.py:20-28` lists
`data/`, `china/data/` and the two `documents-index.json` files as read-only roots. Running either
script rewrites them in place with no `ensure_writable`. This matters beyond the prohibition:
`manifest._load_curated_metadata` reads those indexes for all curated document metadata (spec §6
assertion 8), and `tests/test_gold_set.py` grades the gold set against paths in them, so an
accidental re-run can invalidate the pilot metadata and the evaluation gate at once.
`tests/test_safety.py` does not cover `scripts/`, so nothing catches it.

Smallest correct fix: route all four writes through `paths.open_write` and emit to
`workspace/catalog/`; if regenerating the committed corpus dataset is genuinely intended, that
should be an explicit, separately named opt-in (e.g. `--i-am-regenerating-the-corpus`) rather
than the default behaviour of `python3 scripts/build_master.py`.

## F8 — `unit_original` is the target unit, and bare `o.c.` spacings invent inches (medium, **proven**)

`facts.py:551` writes `unit or None` into `unit_original`, where `unit` is the third element of
the `PATTERNS` tuple — the *normalised* unit, not the unit the source used. And the
`post_spacing_in` pattern (`facts.py:418-419`) makes the unit optional
(`{_NUM}\s*(?:{_IN}|{_FT})?\s*(?:on\s*cent(?:er|re)|o\.?\s?c\.?)`), while `_normalise`
(`facts.py:459-464`) treats "no feet marker present" as "inches".

Proven by running `facts.extract_facts` over four synthetic elements in an in-memory store:

```text
"Posts shall be set 8 o.c. maximum."   -> post_spacing_in  value_original="8 o.c"
                                          value_normalized=8.0   unit_original='in'
"Posts shall be set 8' o.c. maximum."  -> post_spacing_in  value_normalized=96.0
"Embed post 3 ft below grade."         -> footing_depth_in value_original="Embed post 3 ft"
                                          value_normalized=36.0  unit_original='in'
```

Prohibition 7's letter is met — `value_original` keeps the source wording and `evidence_text`
keeps the surrounding sentence — so this is not a violation. But `unit_original='in'` on a
"3 ft" match is simply false, and `8 o.c.` → 8 inches is a wrong structural number carrying
`review_status='extracted'` (not `flagged`) whenever the element came from the text layer. The
`facts` table is empty in the live store (0 rows), so nothing is contaminated yet.

Smallest correct fix: set `unit_original` from the matched text (`"ft"` when the `_FT` branch
matched, `"in"` when `_IN` matched, `None` when neither), and for a dimension pattern whose unit
group is absent, either skip the match or emit it with `review_status='flagged'` and
`value_normalized=None`.

## F9 — silent bbox clamping makes the out-of-page check dead code (low)

`_clamp_elements` (`extract.py:100-122`) runs inside the page loop (`extract.py:348`);
`_document_level_checks` (`extract.py:365`) then tests
`el.bbox[2] > p.width + 1` and raises `bbox_out_of_page`. Because clamping happens first, that
branch can never fire. Confirmed on the live store: 0 elements outside their page bounds, and
`bbox_out_of_page` does not appear among the recorded issue kinds
(`low_ocr_confidence` 123, `table_not_reconstructed` 61, `mojibake_text_layer` 8,
`empty_page_after_ocr` 7, `empty_page` 3, `no_page_image_for_docx` 1).

So a bbox that arrives wrong is quietly moved rather than reported — the opposite of what
prohibition 12 asks for, and precisely what would have hidden F1 had a rotated text page existed.
Clamping can also invert a box: if `x0 > page.width`, `max(0, x0)` leaves `x0` alone while `x1`
becomes `page.width`, yielding `x0 > x1` (0 such rows today).

Smallest correct fix: in `_clamp_elements`, when the clamped tuple differs from the original by
more than a rounding epsilon, append a `bbox_clamped` quality issue with the before/after values;
and drop or flag a box that inverts.

## F10 — two write paths sit outside the guard (low)

* `tools.render_page` (`tools.py:56-64`) does `out_prefix.parent.mkdir(...)` and lets `pdftoppm`
  write, with no `ensure_writable`. This is deliberate — the OCR render goes to a `mkdtemp`
  directory outside `workspace/` (`extract.py:183`) — but it means `paths.py`'s docstring claim
  that "every write in this package goes through `ensure_writable`" is not true, and the evidence
  page image (which *is* a workspace write) is unguarded.
* `_crop_region` (`extract.py:84-100`) calls `ensure_writable(out_path)` **inside** a
  `try: ... except Exception: return False`, so a `CorpusWriteError` is downgraded to "no region
  image available" instead of failing loudly as prohibition 1's preamble requires.

Neither is currently reachable with a bad path: `derived_dir` is `DERIVED_DIR / doc_id` and
`doc_id` is `"doc-" + sha256(...)[:12]` (`ids.py:21-23`), so no document-derived string reaches a
path. Fix: split `render_page` into a guarded `render_page` and an explicit
`render_page_to_tempdir`, and move `ensure_writable` out of the `try` in `_crop_region`.

## F11 — `manifest.py` bypasses `tools.run` (low)

`manifest.py:30-31` defines its own `_run(cmd, **kw)` calling `subprocess.run` directly. The two
call sites (`manifest.py:35,48`) pass argument lists and no `shell`, so nothing is injectable
today, but the wrapper accepts arbitrary kwargs (including `shell=True`) and skips the
list-of-strings assertion that `tools.run` exists to enforce and that `tests/test_safety.py`
tests. Fix: delete `_run` and use `tools.run`.

## F12 — argv is not `--`-terminated (low)

`tools.py:59` (`pdftoppm ... str(pdf) str(out_prefix)`), `tools.py:69`
(`tesseract str(image) stdout ...`) and `manifest.py:48` pass a path in argv position. A corpus
file named `-r.pdf` would be consumed as an option by poppler/tesseract. No shell is involved, so
this is option smuggling rather than command injection, and I verified no corpus file begins with
`-` or contains a quote, `$` or `;`. Worth noting because filenames are the one corpus-controlled
value that does reach an argument list. Fix where the tool supports it (`tesseract` does not take
`--`; passing `./` -prefixed absolute paths, which the code already does for `pdftoppm`, is
sufficient).

## F13 — `get_element_context` ignores `before`/`after` across pages (low)

`retrieval.py:316-324`: the `before`/`after` counts bound the ordinal window on the element's own
page, but the second disjunct

```sql
OR (page_no BETWEEN ? AND ? AND page_no != ?)
```

is bounded only by `page_no ± 1`, so the whole previous and next page come back. Spec §7 defines
`get_element_context(element_id, *, before=1, after=1)`; returning several hundred elements for
`before=1` is a contract mismatch and, on a large page, a slow response.
`tests/test_contract.py:328` only asserts that `"context"` is present, so nothing catches it. Fix:
order the neighbouring pages' elements and slice to `before`/`after` (trailing elements of the
previous page, leading elements of the next).

## F14 — the test suite writes to the live evidence store (test)

The review brief states that `python3 tests/run_tests.py` "does not write to the DB". It does:

* `tests/test_idempotency.py:51` and `:66` call `build_retrieval_units(self.conn)` on the real
  `workspace/indexes/evidence.db`, which executes `DELETE FROM retrieval_fts`,
  `DELETE FROM retrieval_units` and `DELETE FROM sqlite_sequence WHERE name='retrieval_units'`
  before rebuilding (`store.py:437-439`).
* `tests/test_contract.py:321` → `retrieval.get_region`, which on a cache miss crops a new PNG
  and runs `UPDATE elements SET region_image_path=?` plus `commit()` (`retrieval.py:284-293`).
* `tests/test_safety.py:53-62` creates and removes a symlink inside `workspace/`.

Because a full-corpus ingest was running (PID 995372, `--all --workers 10`), I **did not** run the
full suite: a concurrent `DELETE FROM retrieval_units` would contend with the ingest's writer on
the same WAL database and would rewrite derived state the running job is about to rebuild. I ran
the 42 store-free tests instead — `test_units`, `test_safety`, `test_gold_set`,
plus `TestApprovalIds` and `TestNormalisation` — and all 42 pass.

Fix: have the store-backed tests operate on a copy (`shutil.copy2(EVIDENCE_DB, tmp)` in
`setUpClass`, or a fixture store built from a two-document pilot), so the suite is genuinely
read-only against the live index.

## F15 — over-broad skips and assertions weaker than the spec (test)

* **`context.requires_store` (`tests/context.py:12-15`) gates the whole Phase 1 gate on
  `EVIDENCE_DB.is_file()`.** On a clean checkout `python3 tests/run_tests.py` exits 0 without
  evaluating a single §6 assertion, and reports "OK", not "gate not run". Spec §9 asks for the §6
  assertions "run over the pilot as an automated test"; a skip that reports success is the one
  outcome the Phase 1 gate must not have. Fix: make the absence of the store a *failure* of a
  single explicit `test_pilot_gate_was_run`, and keep the skip only for the optional suites.
* **`tests/test_facts.py` self-skips every store-backed test when `facts` is empty**
  (`if self.n == 0: self.skipTest(...)`, six times). The live `facts` table has 0 rows, so
  acceptance criterion A7 ("every Phase 6 fact carries provenance and a review status") is
  currently asserted by nothing at all. Fix: replace the per-test skips with one
  `test_facts_have_been_extracted` that fails, so the vacuity is visible.
* **`test_bounding_boxes_within_page` (`tests/test_preservation.py:165-179`) cannot fail.** It
  asserts `x1 <= width + 1` and `x0 >= -1` — exactly the interval `_clamp_elements`
  (`extract.py:107-110`) has already forced every box into. It tests the clamp, not the geometry.
  Fix: assert the property that matters instead — for a sample of `table`/`figure` elements,
  that the region crop's pixel size equals `bbox × (page_px / page_pts)` (this is what I used to
  clear the crop-scale false alarm below), which would have caught F1 on a rotated page.
* **`test_ocr_never_overwrites_source_text` (`tests/test_preservation.py:105-108`) checks only
  `text_source='ocr'`.** `image_ocr` — the entire CAD/PNG path, which is one of the ten pilot
  documents — is not covered by the prohibition 6 assertion. Both are clean in the live store
  (0 rows each), so this is a coverage gap, not a defect. Fix:
  `WHERE text_source IN ('ocr','image_ocr') AND text <> ''`.
* **`tests/test_units.py:101-116` (`TestRotation`) asserts the buggy transform of F1** as the
  expected value, so the bug is pinned by a passing test.
* Nothing in `test_idempotency.py` or `test_relations.py` asserts that a retrieval unit stays
  within one version (F2); `test_retrieval_units_rebuild_identically`
  (`tests/test_idempotency.py:123-134`) deliberately excludes `version_id` from the compared
  columns.

On the brief's specific question — **could a document with no extracted content pass
`test_preservation.py`?** No. For every non-DOCX pilot document,
`test_page_images_exist_for_every_page` requires at least one page row with an on-disk image over
1000 bytes, `test_bounding_boxes_within_page` requires at least one element with a bbox, and
`test_section_hierarchy` requires at least one element with a non-empty `heading_path` unless the
document is in the explicit `NO_HEADING_EXEMPT` map. A content-free document fails at least two of
those. The gate's weakness is not vacuity, it is the skip in F15's first bullet.

---

## False alarms I ruled out

1. **`retrieval.search_evidence` builds its SQL with an f-string (`retrieval.py:173-186`) — not
   injectable.** Only three things are interpolated: `BM25_WEIGHTS` (a module constant tuple of
   floats), the *values* of `FILTER_COLUMNS` (a closed dict of six literal column names), and
   `','.join('?' * len(value))` for `IN` lists. An unrecognised filter key raises `ValueError`
   (`retrieval.py:165-166`), so a caller-supplied key can never reach the SQL text;
   `source_path_prefix` is bound as `f"{value}%"`. The query string itself is always a bound
   parameter to `MATCH`. `facts.query_facts` (`facts.py:572-588`) appends only fixed clauses with
   bound parameters. No other module builds SQL from input.
2. **FTS5 MATCH-expression injection — not possible.** `_fts_escape` (`retrieval.py:62-63`) wraps
   in double quotes and doubles embedded quotes, and every non-quoted token is reduced to
   `[A-Za-z0-9]+`-and-space before quoting (`retrieval.py:103-109`). I ran five hostile queries
   against the live index through a read-only connection:
   `'footing" OR retrieval_fts MATCH "x'` → `" OR retrieval_fts MATCH " OR "footing"` (a phrase,
   not operators); `"depth'); DROP TABLE elements;--"` → `"depth" OR "drop" OR "table" OR
   "elements"`; `'a" NEAR/5 "b'` → the phrase `" NEAR/5 "` (0 hits). All executed without error
   and without escaping the phrase context.
3. **The page-size swap for rotated pages (`extract.py:194`) is correct and must be kept.**
   `pdftotext` reports the unrotated MediaBox while `pdftoppm` renders rotated, so the swap is
   what makes the two agree. Verified against the live store: for
   `NOA-23-0314.05...` (MediaBox 792×612, `/Rotate 270`) pages 1-6 are stored as 612.0×792.0 with
   a 1700×2200 page image — exactly 200/72 — and pages 7-17 as 1224.0×792.0 with 3400×2200.
4. **`_crop_region`'s single-axis scale (`extract.py:86-87`) is correct.** `scale = im.width /
   page_width` is applied to y as well, which is only valid if the aspect ratios match — they do,
   because the same `pdftoppm -r` produces both. Verified on six real region assets: measured crop
   sizes were 975×1308, 308×308, 2024×691, 491×174, 2024×391, 258×1375 against predicted
   975×1308, 308×308, 2025×691, 491×175, 2025×391, 258×1375 (±1 px from `int()` truncation).
5. **`hocr.parse_hocr(scale=OCR_DPI/72)` (`extract.py:268`) is the right conversion.** `pdftoppm`
   applies `/Rotate`, so hOCR pixel space *is* display space; dividing by 300/72 lands in display
   points, the same frame as the swapped `page.width`/`height`. The `extract_image` path correctly
   uses `scale=1.0` because there the page "points" are pixels.
6. **OCR text cannot reach `elements.text` (prohibition 6).** Every construction site sets
   `text=""` on the OCR branch — `layout.build_elements:197-199` and `:218-220`,
   `extract.py:311-314` (OCR table grid goes to `ocr_text`), `extract.py:307-317` (drawing),
   `extract.py:555-566` (`drawing_label`/`drawing`). Live store:
   `text_source='ocr' AND text<>''` → 0 rows; `text_source='image_ocr' AND text<>''` → 0 rows;
   elements carrying both a non-empty `text` and a non-empty `ocr_text` → 0 rows. The mojibake
   path is the interesting case and it is handled the safe way: the unusable text layer is
   *dropped* and the page re-routed to OCR with a recorded `mojibake_text_layer` issue
   (8 occurrences), rather than OCR being written over it.
7. **Superseded and active documents cannot collapse (prohibition 5).** `document_id` is
   `sha256(source_path)` (`ids.py:21-23`) and `documents.source_path` is `UNIQUE`, so two files
   are always two rows; supersession lives entirely in `relations`
   (`relations.py:316-334`), and `derive_relations` only ever *sets* `version_status='superseded'`,
   never merges rows. Live store: 5 active / 7 superseded / 130 unknown, the two CertainTeed NOAs
   distinct. Near-duplicate handling matches spec §11 too — byte-identical files are linked with
   `same_content_as` (`relations.py:294-306`), never removed.
8. **130+ documents with elements but zero `retrieval_units` is not a bug.**
   `build_retrieval_units` runs once, at the end of `ingest()`, and the run is still in progress.
   (It is, however, the direct evidence for F3.)
9. **No shell, no dynamic execution.** `grep -rn "shell=True|os.system|eval\(|exec\("` over
   `src/`, `tests/` and `scripts/` returns only the two `subprocess.run` definitions and a comment
   in `test_safety.py`. `tools.run` (`tools.py:17-21`) asserts a list of `str` and passes
   `shell=False` explicitly.
10. **No path is derived from document content, and no region filename can escape its directory.**
    Region crops are `ddir / "regions" / f"p{pno:04d}-{el.ordinal:04d}-{el.element_type}.png"`
    (`extract.py:357`) — two zero-padded integers and one value from a closed vocabulary of
    element types — under `DERIVED_DIR / doc_id` with `doc_id` a hex digest. `get_region`'s
    on-demand crop (`retrieval.py:286-287`) uses the same shape from DB integers. No traversal is
    constructible.
11. **Per-document writes are atomic; `delete_version_rows` is correct.** `write_extracted`
    (`store.py:334-394`) issues its `delete_version_rows` + all inserts in one implicit
    transaction with a single `commit()` at the end, so a crash mid-document rolls back rather
    than leaving a half-written version. `delete_version_rows` (`store.py:321-331`) removes
    `table_cells`, `tables`, `assets`, `elements`, `pages` and `quality_issues` for the version in
    dependency order, so re-extraction is replacing rather than additive.
12. **Foreign keys are enforced and currently intact.** `connect` executes
    `PRAGMA foreign_keys=ON` on every connection (`store.py:225`) in addition to the pragma in
    `SCHEMA`; `PRAGMA foreign_key_check` on the live store returns no rows. `retrieval_units` and
    `retrieval_fts` deliberately carry no FKs (they are the rebuildable projection), and
    `retrieval_fts` has no orphan rowids (0) and no unit referencing a missing element (0). The
    per-document rebuild branch (`store.py:429-435`) deletes the FTS rows by rowid before deleting
    the units, which is the correct order — it just has no caller yet.
13. **`retrieval_reason.matched_terms` is genuinely derived from the result.**
    `_matched_terms` (`retrieval.py:123-133`) filters the query's source terms by substring
    presence in the unit's own text, so `tests/test_contract.py:263-268` is not tautological — it
    would fail if the implementation regressed to echoing the query. Its residual weakness is that
    a term is reported as "matched" when it merely occurs in the text, even if the BM25 hit came
    from `title` or `manufacturer`; that is a fair reading of spec §8 but not the only one.
14. **pdfplumber table/figure coordinates need no rotation adjustment.** pdfplumber 0.11.10
    (`workspace/pylibs/pdfplumber/page.py:161-285`) normalises the MediaBox and rotates every
    object point itself, so its bboxes are already in display space — the same frame as the
    `pdftotext` words. This independently corroborates F1's conclusion that a second rotation in
    `extract.py` is wrong.
15. **Prohibitions 2, 9 and 11 are respected.** Nothing generates summary or answer text; the only
    index is stdlib SQLite FTS5 and `search_evidence` rejects any `mode != "fts5"`
    (`retrieval.py:149-150`); every `SearchResult` carries `document_id`, `source_path`, `page`,
    `element_id`, `bbox`, `page_image_path` and `region_image_path`, and a spot check of the top
    10 for "footing depth exposure C" found every non-DOCX `page_image_path` present on disk.

## Areas that are simply correct

Worth stating plainly so they are not re-litigated: the write guard itself (`paths.ensure_writable`
resolves symlinks before the `relative_to` check, and `tests/test_safety.py:53-62` covers the
symlink escape); id stability (`ids.py`); the mojibake gate in `quality.py`, which is the right
shape — reject, record, re-route, never silently keep bad text; the conservatism of
`tables.looks_tabular` and `tables.detect_ocr_tables` (digit share, stub-cell share, confidence
floor) and the `table_not_reconstructed` issue that fires when a scanned table cannot be rebuilt
(61 occurrences), which is exactly what prohibition 12 asks for; `evaluate.py`'s separation of
strict unit support from page support with the gate on the strict one; and `pilot.py`'s exemptions,
which are recorded by id with a stated reason rather than applied silently.
