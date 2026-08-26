# K3 — what a cold crop costs

```text
Question:  docs/integration/source-refs-design.md §8.4 — "§4.2 chooses poppler
           windowing over cached Pillow crops on correctness and dependency
           grounds without knowing what a cold paragraph crop costs. That number
           should exist before a queue is built on it."
Measured:  2026-08-25, against the fetched corpus, on the reference machine.
Harness:   scripts/measure_crop_cost.py — re-runnable, seeded (20260825).
Answer:    Render on demand, as designed. Cache by PAGE, not by element.
           No pre-render pass is needed.
```

## 1. The number

`fence_evidence.crops.render_crop` — the real code path, not a shell
approximation. 400 boxed elements sampled at random across the corpus:

| | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| **Cold crop** | **24.8 ms** | 139.4 ms | 307.8 ms | 5,562 ms | 7,541 ms |

**Crops over one second: 13 of 400 — 3.2%.**

The mean (245 ms) is four times the median and describes nothing that happens.
The distribution is **bimodal, not a smooth tail**: almost everything is fast,
and a small identifiable set is very slow. Quote the median and the p99
together; either alone misleads.

## 2. Windowing is a real optimisation, not an illusion

The worry worth testing: poppler might decode the whole page and then discard
everything outside the window, making `-x -y -W -H` cosmetic. It does not.
Same page, same dpi, window versus full-page render, 60 pairs:

| | p50 | p95 | max |
|---|---:|---:|---:|
| Windowed crop | 27.9 ms | 1,299 ms | 6,227 ms |
| Full page render | 394.0 ms | 15,220 ms | 35,230 ms |
| **ratio** | **0.1** | 0.2 | 0.6 |

**A windowed crop costs about a tenth of a full page**, for a window that is
typically well under 1% of the page area. The saving is real but sublinear —
poppler still pays a fixed cost to open, parse and seek. That fixed cost is what
the p99 is made of.

So §4.2's choice of poppler windowing over the cached Pillow crops stands on
cost as well as on correctness and dependency grounds. It was argued without
this number; the number agrees.

## 3. The tail is two documents, and they are on the other track

The slowest 8 of 400 crops were all the same file:

| Document | Size | Pages | Boxed elements | Crop cost |
|---|---:|---:|---:|---|
| `china/manuals/showtech/PVC-fence-catalog-2024.pdf` | 20 MB | 24 | 1,582 | 4.3–7.5 s |
| `china/manuals/showtech/PVC-fence-catalog-2022.pdf` | 11 MB | 14 | 967 | ~1.1 s |

These are the Showtech China catalogs that `CLAUDE.md` already names as among the
hardest things in the corpus: large, scanned, image-only, no text layer. Cost
tracks **page image complexity**, not window size and not page count — crops from
page 26+ were *faster* than crops from pages 1–5, because which document a page
is in dominates where in it.

Sizing the affected class: **9 scanned documents over 10 MB hold 11,308 boxed
elements — 13.9% of the 81,378 in the store.** That is the population where a
cache earns its keep, and it is knowable in advance from `has_text_layer` and the
file size, without measuring anything at request time.

Two of the three worst are on the **China track**, which is deliberately separate
from US/Western and which `source-refs-design.md` §8.5 already flags as an open
question in the contract. Worth noting that the worst-case latency in this system
sits behind a boundary that has not been drawn yet.

## 4. The review queue — the number that actually decides Phase B

This is the population that matters, because A1 has just made human review the
only path back to curation level 2. The queue's front is the 504
`cross_family_verified` readings.

**They sit on 10 distinct pages.**

| | value |
|---|---|
| Readings awaiting review | 504 |
| Distinct cells | 168 |
| **Distinct pages** | **10** |
| Crop cost, p50 / max | **164.5 ms / 173.4 ms** |
| A 50-row screen, sequential, no cache | **1.3 s** |
| A 50-row screen, cached by page | **10 renders, ~1.6 s, once** |

The queue is far cheaper than the corpus-wide p99 suggests, and the reason is
structural rather than lucky: **table readings cluster onto table pages.** A
reviewer works down a page, and every row after the first is a cache hit.

## 5. What this means for the design

**Render on demand, as §4.2 specifies. Do not build a pre-render pass.**

1. **Cache the page, not the element.** Every measurement here says the unit of
   cost is *the page image*, and the unit of reuse in a review queue is also the
   page. An element-keyed cache would miss the thing that makes the queue cheap.
2. **A pre-render pass is not justified.** Pre-cutting all 73,894 uncropped
   elements costs roughly **5 hours single-threaded** (at the measured mean) or
   about 30 minutes at the 10 workers ingestion already uses — to eliminate a
   cost that is 25 ms at the median and that a page cache removes anyway.
   §4.3's "regenerable cache" position holds.
3. **Budget the p99 explicitly, and do not let it set the timeout.** A 15-second
   worst case is real but affects ~3% of requests, concentrated in 9 knowable
   documents. `render_crop` currently uses a 120 s subprocess timeout, which is
   ~20× the worst case measured — deliberately generous, since the failure mode
   of a short timeout is a reviewer seeing nothing.
4. **Warm the 9 heavy documents if a queue ever lands on them.** They are
   identifiable from `has_text_layer = 0` and file size before any request
   arrives. Nothing in the current queue touches them.

## 6. Honest limits of this measurement

- **The OS page cache is warm for repeated documents.** These numbers are cold
  for the *renderer* — a new poppler process, no crop on disk — but not cold for
  the kernel. A first-touch-per-document subset (n=77) showed p50 29.3 ms against
  the overall 24.8 ms, so the effect is small at the median; it is not
  characterised at the tail.
- **One machine, one poppler build.** `workspace/reports/environment-report.md`
  records the toolchain. Re-run before relying on these for capacity planning on
  different hardware.
- **Rendering only.** Nothing here measures HTTP, serialisation, or the
  `SourceRef` assembly around the image.
- **The review-queue figure is 10 pages.** It is a true measurement of today's
  queue and a poor predictor of a corpus-wide one. Re-measure when review extends
  past the cross-family set.
