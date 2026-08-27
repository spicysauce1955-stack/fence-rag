# Phase 2 — the review loop

```text
Status:    Design, approved 2026-08-27. Implements Phase 2 of
           2026-08-27-unblocking-planning-design.md §5.
Scope:     A person can accept or correct a machine reading, and Planning's screen
           can reach the evidence behind it. Nothing publishes differently until
           `promote-tables --apply` stops being a no-op, which this is what enables.
Boundary:  No contract change, no amendment. `POST /reviews`, `GET /source-refs/{id}`
           and `POST /source-refs:batch` are already in contract.md §1.5. The request
           and response *bodies* are undefined there — §1.5 says "this platform owns
           the workflow" — so §5 below defines them, and that is the one part of this
           document Planning builds against.
```

---

## 1. Why this is the critical path

`PROMOTABLE` is `("accepted", "corrected")` and **nothing in the package writes
either**, so `promote-tables --apply` is a no-op and the level-2 population of this
store is zero. Obligation 6 requires level 2 for a `structural_parameter`, so no
footing depth or post spacing can cross the boundary at the level Planning's source
policy demands. The review loop is not the tail of the publishing work; it is the
hole in the middle of it.

`reviewer` is NULL on all 1,225 readings. Not one human review has happened.

---

## 2. What review is actually for — measured

The obvious assumption is that review adjudicates values the machines got wrong.
**Measured, that is not what the data says.**

Of 877 grid positions in the queue, 174 were read by more than one reader:

| | count | share of multi-read |
|---|---:|---:|
| positions read by >1 reader | 174 | — |
| readers disagree on the **value** | **6** | 3.4% |
| readers disagree on the **label** | 24 | 13.8% |

All six value disagreements sit at `col_index 0` — the row-label column — and every
one is the same shape: `'Up to 48"'` against `''`.

**Across 174 independently multi-read cells, the readers never once disagreed about a
number.** All 30 disagreements are about whether a merged cell's value belongs to its
continuation row.

### 2.1 `96 / 168 / 186` was one phenomenon, not three

Those three counts, quoted repeatedly while arguing about review geometry, count the
same 504 readings under three ideas of cell identity:

| | count | what it is |
|---|---:|---|
| by `(row_index, col_index)` | **168** | grid position — the truth |
| by `(row_label, col_label)` | 96 | collapses, because merged labels are shared |
| by both together | 186 | exceeds 168, because readers differ on carrying a merged label down |

The collapse is exact and legible. On `doc-c267c4cd071f` p17, the label pair
`('B', 'FOOTING DEPTH')` addresses **two** grid positions, holding `24"` and `30"` —
both rows are labelled `B`, because exposure B has two design points.

The excess is the same cell from the other side. On `doc-88dcd8a73079` p6, the
`Fence Height` column reads:

```
Up to 48"  ┐   B   24"   12"
           ┘   C   30"   12"      "Up to 48"" is merged across both rows
49" to 76" ┐   B   34"   12"
           ┘   C   36"   12"
```

`calibration-A` and `calibration-B` carry the merged label down to the continuation
row; `codex-C` leaves it blank. Neither is wrong. The table means one thing and the
row model cannot express it.

**So review's job is to confirm values against the image and recover the structure
the machines cannot see** — which is exactly what G41 discards, since `rowspan` and
`colspan` are never written and all 18,472 cells claim to be 1×1.

### 2.2 Honest limits of §2

- 174 of 877 positions are multi-read. This is a claim about a fifth of the queue.
- All three readers are language models reading the same crop. **Agreement is not
  correctness**; shared failure modes are precisely what a human check exists to
  catch. This measurement argues about *what review should ask*, never that review
  is unnecessary.

---

## 3. Decisions

**D1 — The review unit is one table per crop.** 44 crops, one verdict each, with
corrections inline. Not per cell: §5.1 of the parent spec measured that a
label-derived cell box is ambiguous on exactly the tables it targets, and §2.1 above
explains why — a row-label band spans the rows it labels. Not per row either: the
bracket spans a *pair* of rows, so a per-row verdict would record it twice and the
two copies could disagree.

**D2 — A review records `grid` and `spans`.** The HVHZ applicability bracket and the
`Up to 48"` row-label band are **the same shape**: a value covering a range of rows.
One field holds both, because in the source they are one thing. This is the field
§5.1 found missing — the queue has no HVHZ column and no HVHZ row label anywhere,
and all 426 HVHZ mentions live in free-text `notes`.

**D3 — Both storage forms, with one authoritative.** `table_reviews` is written
first and is the record. The annotations on `table_read_candidates` are a
**projection of it**, written in the same transaction, regenerable by
`cli review --rebuild`, with a test asserting the rebuild is byte-identical. This is
the guarantee `rebuild-index` already gives `retrieval_units`. Without it, "both"
means two sources of truth that drift; with it, one source and one cache.

Pointers run **down**: `table_reviews.from_candidates` names the readings it was
derived from. Nothing on `table_read_candidates` points at a review — that would be
`promoted_fact_id` again, which `tests/test_pointer_direction.py` forbids.

**D4 — Three verdicts, not two.** `accepted` · `rejected` · `bracket_unclear`.
The third is not a rejection: the values can be right while the applicability is
unreadable, and on the footing tables that is the commonest failure and the one that
matters most. Only `accepted` and `corrected` are `PROMOTABLE`; `bracket_unclear`
publishes a `Gap` instead.

**D5 — Logic is pure; transport is thin.** Every endpoint's behaviour lives in a
module taking arguments and returning dicts. `api.py` is routing, auth and error
mapping, and holds no logic. The suite runs in 15 seconds with no network and must
keep doing so.

**D6 — The `crop_sha256` echo is the integrity story.** §4 of the parent spec grants
that we never see an end user and cannot verify `reviewer`. The one checkable claim
is *"this person looked at the image we hold."* A mismatch is refused, not recorded.

---

## 4. Schema

`SCHEMA_VERSION` 3 → 4. Additive; `migrate()` is safe to re-run.

```sql
CREATE TABLE IF NOT EXISTS table_reviews (
    review_id       TEXT PRIMARY KEY,   -- sha256(crop_sha256:reviewer:reviewed_at)[:16]
    crop_sha256     TEXT NOT NULL,      -- echoed by the request; the verifiable claim
    document_id     TEXT NOT NULL,
    page_no         INTEGER NOT NULL,
    reviewer        TEXT NOT NULL,      -- asserted by Planning; unverifiable by us
    reviewed_at     TEXT NOT NULL,
    verdict         TEXT NOT NULL,      -- accepted | rejected | bracket_unclear
    grid            TEXT NOT NULL,      -- JSON [{row,col,value}]
    spans           TEXT NOT NULL,      -- JSON [{row_from,row_to,col,text}]
    from_candidates TEXT NOT NULL,      -- JSON [candidate_id] -- points DOWN
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_table_reviews_crop ON table_reviews(crop_sha256);
CREATE INDEX IF NOT EXISTS idx_table_reviews_doc  ON table_reviews(document_id, page_no);
```

No new column on `table_read_candidates`: `review_status`, `reviewed_value`,
`reviewer` and `reviewed_at` already exist and are what the projection writes.

`spans` is `'[]'` when there are none — never NULL, so "no merges seen" and "not
asked" stay distinguishable from a missing review.

---

## 5. The wire shapes

**The only part of this document Planning builds against.** Not an amendment: §1.5
names the calls and leaves the bodies to the workflow owner.

### 5.1 `GET /source-refs/{id}` · `POST /source-refs:batch`

```json
{ "id": "eb2c863494b90243",
  "belongs_to": "<content_hash>",
  "page_no": 47,
  "text": "Call before you dig.",
  "image": { "url": "crops/eb/eb2c863494b90243-200-a1b2c3d4.png",
             "sha256": "<sha256 of the PNG bytes>",
             "dpi": 200 },
  "warnings": [ { "code": "SOURCE_TEXT_FROM_OCR", "params": {"confidence": 95.6} } ] }
```

`warnings` is where the ten `SOURCE_*` codes from `registry-additions.md` §2 are
consumed. The image URL is relative, per `source-refs-design.md` §5, because crops
traverse Planning's backend.

Batch request `{"ids": [...]}`, cap **50**. Response
`{"refs": [...], "not_rendered": ["<id>"], "deadline_exceeded": bool}` — a deadline
returns partial results and never an error, because a reviewer seeing nothing is the
worse failure.

### 5.2 `POST /reviews`

```json
{ "crop_sha256": "<echo of the image we served>",
  "reviewer": "<asserted by Planning>",
  "verdict": "accepted",
  "grid":  [ {"row": 0, "col": 1, "value": "30\""} ],
  "spans": [ {"row_from": 0, "row_to": 1, "col": 3, "text": "NON HVHZ"} ],
  "notes": null }
```

Response `{"review_id": "...", "verdict": "...", "cells_written": 18, "promotable": 18}`.
`promotable` reports what became eligible, because a review whose whole point is to
make something publishable should say whether it did.

Errors are `{"error": {"code": ..., "message": ...}}` with codes in an `error.*`
namespace, **never the warning registry** — defect 5 of the parent spec: Planning's
`test_locale_bundles.py` fails the build on any registry code lacking both bundles,
so a new HTTP error code in that namespace would break their CI.

| HTTP | code | when |
|---|---|---|
| 401 | `error.unauthorized` | missing or unknown bearer token |
| 404 | `error.unknown_ref` | no such `ref_id` |
| 409 | `error.crop_mismatch` | the echo does not match what we would serve |
| 413 | `error.batch_too_large` | more than 50 ids |
| 422 | `error.malformed_review` | bad verdict, bad grid, span outside the grid |

---

## 6. Modules

Four new files, each independently testable. Signatures are fixed here so they can
be built in parallel.

```python
# fence_evidence/reviews.py --- the workflow. No HTTP, no filesystem.
class ReviewRefused(RuntimeError): ...        # carries .code from the table above

def submit_review(conn, *, crop_sha256: str, reviewer: str, verdict: str,
                  grid: list[dict], spans: list[dict], notes: str | None = None,
                  reviewed_at: str | None = None) -> dict
def rebuild_projection(conn) -> dict          # regenerate candidate annotations
def review_queue(conn, *, limit: int = 50) -> list[dict]
def review_summary(conn) -> dict
```

```python
# fence_evidence/cropcache.py --- render-through cache. No HTTP.
class CropUnavailable(RuntimeError): ...

def cache_path(ref_id: str, dpi: int, fingerprint: str) -> Path
def ensure_crop(conn, ref_id: str, *, dpi: int = 200,
                index: dict | None = None) -> dict   # {path, sha256, dpi, cached}
```

```python
# fence_evidence/sourcerefs.py --- the Discovery read model. No HTTP.
def source_ref(conn, ref_id: str, *, dpi: int = 200, index=None) -> dict
def source_refs_batch(conn, ref_ids: list[str], *, dpi: int = 200,
                      deadline_s: float = 10.0, cap: int = 50) -> dict
```

```python
# fence_evidence/api.py --- transport only.
def dispatch(method: str, path: str, body: dict | None, *,
             conn, token: str | None, tokens: set[str]) -> tuple[int, dict]
def serve(host: str, port: int, *, tokens: set[str]) -> None
```

`dispatch` is pure and is what the tests drive. `serve` wraps it in
`ThreadingHTTPServer` and is exercised by one smoke test, not by the suite's bulk.

CLI: `cli review --queue | --accept CROP --reviewer NAME [--grid FILE] | --rebuild`
and `cli serve --port N`.

---

## 7. Crop cache, from measurement

`workspace/reports/k3-crop-render-cost.md`, 400 sampled elements:

| | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| cold crop | **24.8 ms** | 139.4 ms | 307.8 ms | **5,562 ms** | 7,541 ms |

Bimodal — 13 of 400 exceed one second. Consequences, all of which the report already
argued:

- **Batch cap 50**: ~1.2 s at the median, ~6.7 s with one p99 in the batch.
- **The deadline returns partial results.** It must not set the per-render timeout;
  `render_crop`'s existing 120 s subprocess timeout stays, because a short timeout
  shows a reviewer nothing.
- **No pre-render pass.** Pre-cutting all 73,894 uncropped elements costs ~5 hours
  single-threaded to remove a 25 ms median that the cache removes anyway.
- **The 9 heavy documents are identifiable before any request** and none is in the
  current queue. Warm only if a queue lands there.

K3 says *"cache the page, not the element"* while the parent spec's §4 says the key
is `(ref_id, dpi, tool_fingerprint)`. Both hold, for different consumers: the review
queue's unit already **is** the page (44 crops, one per page, materialised), and the
element key belongs to `GET /source-refs/{id}`, which answers a different question.

`tool_fingerprint` is in the key for G38's reason — a toolchain change moves the
pixels, and a cache keyed on `ref_id` alone would serve stale crops after an upgrade.

---

## 8. Out of scope

- **Any UI.** §4 of the parent spec: screens are Planning's.
- **Recovering merges automatically (G41).** Phase 2 routes around it by having a
  person record `spans`. Inferring merges from ruling lines is worth doing and worth
  measuring first.
- **Authentication beyond a bearer allowlist.** §4: one backend, never a browser.
- **`GET /search`, `GET /claims`, `POST /part-types`, `POST /documents`, `POST /gaps`.**
  The other Discovery and Authoring calls are not on this path.

---

## 8.1 What the implementation surfaced

Recorded because the spec did not say, and the code now does.

**A backdated review broke acceptance 3, and did so silently.** `submit_review`
applies reviews as they arrive, last write wins. The first implementation replayed
them ordered by `reviewed_at`, so a review submitted *second* but stamped *earlier*
won live and lost on rebuild — the projection and its own source disagreeing, which
is the single thing D3 exists to prevent. Reproduced, then fixed by replaying in
arrival order (`rowid`). `INSERT OR REPLACE` on a resubmitted `review_id` assigns a
new rowid, which is the wanted semantics: a resubmission is the most recent arrival.
Regression test: `test_a_backdated_review_replays_in_arrival_order`.

**An `accepted` verdict annotates only the positions it submitted.** A position the
reviewer omitted stays `unreviewed` rather than being promoted by omission —
silence is not confirmation. `rejected` and `bracket_unclear` annotate every row of
the crop, because those verdicts are about the table as a whole.

**"Differs" is judged after normalisation.** A curly quote against a straight one is
not a correction, and recording it as one would misreport what review found.

**One crop can belong to two documents.** 14 groups of corpus files are
byte-identical under different manufacturers, so identical pixels can carry two
`document_id`s. `table_reviews` has a single `document_id`; the lowest is stored and
the projection lands on every reading of those pixels. Deterministic and honest, but
it is a real ambiguity the schema cannot express — the same one `also_filed_as`
exists for on the publishing side.

**Non-string cell values are refused, not coerced.** The column is TEXT and
`normalise` takes a string; a client sending `24` rather than `"24\""` gets a 422
rather than a silent stringification.

---

## 9. Acceptance

1. `cli review --accept` writes `table_reviews` and the projection in one transaction.
2. `PROMOTABLE` fires: after a review, `promote-tables --apply` promotes and reports
   a non-zero count, and the level-2 population is no longer zero.
3. `cli review --rebuild` regenerates the projection byte-identically; a test asserts it.
4. A `crop_sha256` mismatch is refused with `error.crop_mismatch` and writes nothing.
5. A span outside the grid is refused with `error.malformed_review`.
6. `dispatch()` is covered without a socket; `serve()` has one smoke test.
7. A batch over 50 is refused; a batch that exceeds the deadline returns partial
   results with `deadline_exceeded: true` and never an error.
8. An unknown or missing bearer token yields 401 before any store access.
9. Error codes are all `error.*` and none reaches the warning registry.
10. `cli refs --verify` still resolves all 431 published citations.
11. The full suite still runs with no network.
