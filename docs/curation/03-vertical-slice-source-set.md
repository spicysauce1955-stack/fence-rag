# 3 — Selected vertical-slice source set

**Family:** Bufftech extruded-PVC fence — the *Columbia · Imperial ·
Chesterfield · Breezewood · Brookline* line, under the CertainTeed → Barrette
Outdoor Living → Catalyst brand succession.

**Slice id:** `slice-bufftech-extruded-pvc` **Manifest:**
`workspace/catalog/slice-bufftech-extruded-pvc.jsonl` (19 rows, each with its
SHA-256 and its measured counts as of this proposal)

**Size:** 19 documents · 522 pages · 24,088 elements · 79 tables · 70 drawings ·
1,335 figures · 2,006 assets · 1,293 of the corpus's 1,988 facts (65%), being
1,041 `regex-v1` rows and 252 from the unreviewed table-reading pass · 922 of
the 1,225 stored table-read candidates (75%) · **113 pages at
`ocr_risk='high'`** and **773 facts already in a mandatory review class** before
any curation begins.

---

## Why this family

Five candidate families were considered against one requirement: the slice must
exercise *manuals, approvals, catalogs, tables, drawings, and versions* at once,
because a slice that skips a document class proves nothing about it.

| Family | Docs | Approval chain | Catalog | Scanned tables | Verdict |
|---|---|---|---|---|---|
| **Bufftech extruded-PVC** | 19 | **5 generations, 2006→2025** | 3 | 66 pages | **selected** |
| Weatherables | 24 | none | — | CAD PNGs only | no approval chain |
| Illusions | 16 | 1 structural doc | — | few | thin structurally |
| Wam Bam | 17 | 5 structural | — | few | no version lineage |
| SimTek molded | 4 | 2 generations | — | 4 pages | too small; different material class |

Bufftech is the only family in the corpus that carries all six document classes,
and it is the family that generates the most of the corpus's known hard
problems:

1. **A real five-generation approval chain.** NOA 06-1019.01 → 12-1106.11 →
21-0125.07 → 23-0314.05 → 24-0117.05, with `supersedes` edges already derived
from the documents' own "previous approval" language and guarded by a direction
regression test. The chain also spans a corporate transfer (CertainTeed →
Barrette), which is exactly the CAP-1 identity problem.
2. **The corpus's highest-value unreadable data.** 66 of the 73 corpus pages
flagged `table_not_reconstructed` are in this slice. Those pages hold the Table
1 wind / exposure / footing / post-spacing grids that CAP-6 exists to serve, and
blind manual verification measured digit-bearing recall on them at **0.588**.
3. **Every duplication and identity pathology in one place.** Four byte-identical
filings of NOA 24-0117.05 under four different manufacturers with four different
`doc_type` values; two byte-identical pairs of install guides filed under both
CertainTeed and Barrette.
4. **A live version contradiction to resolve on the record.** NOA 23-0314.05 is
stored `version_status='superseded'` while its own curated title says
*"current"*, and **all four** filings of the newer 24-0117.05 are stored
`unknown` — so the family's current approval has no asserted status at all.
5. **Both extremes of extraction quality.** A 96.0%-confidence native manual and
a 100%-scanned 56-page legacy manual sit in the same family, so a curation rule
that only works on clean text will visibly fail here.
6. **Documented curated-data errors to check against.** All four contradictions
found in G16 are in `certainteed-bufftech-structural.json`; three describe this
family and are scored by doc 5's R9, while the fourth (NOA 22-0616.10, SimTek)
is about a Tier-C document and moves to slice 2. The slice is therefore the one
place where curation output can be compared against a known-wrong prior.

---

## Tier A — core curation targets (13 documents, 363 pages, 913 facts)

Full dossier, full page map, full claim curation, full review.

Columns: pages · pages without a text layer · mean OCR confidence · elements ·
table/drawing/figure elements · facts (all extractors) · stored table-read
candidates. Where a document's fact count mixes extractors it is broken out
below the table.

### Installation manuals

| Doc | File | Pg | noTL | OCR% | Elem | T/D/F | Facts | Cand | Issues |
|---|---|---|---|---|---|---|---|---|---|
| `1085f7c65c47` | bufftech-fence-installation-guide-2024.pdf | 50 | 1 | 96.0 | 1533 | 18/1/78 | 105 | 0 | — |
| `6431d597a32d` | bufftech-gate-installation-guide.pdf | 56 | 3 | 93.8 | 2326 | 16/3/73 | 110 | 0 | — |
| `c0fa3df89251` | bufftech-install-semiprivate.pdf | 6 | 0 | — | 384 | 0/0/4 | 20 | 0 | — |
| `24d0ddcfce69` | bufftech-installation-guide-40-40-70743.pdf | 44 | 1 | — | 2001 | 3/0/34 | 93 | 0 | empty page 1, empty after OCR 1 |
| `3a8071e73dba` | bufftech-installation-guide-afence.pdf | 56 | **56** | 87.2 | 3357 | 1/19/313 | 222 | 162 | low OCR 3, table not reconstructed 3 |

`3a8071e73dba` is the stress case: 56 of 56 pages have no text layer, and it is
nonetheless the single largest fact producer in the corpus at 222 — 114
`regex-v1` rows plus 108 from the unreviewed table-reading pass. **133 of the
222 meet the computed `low_confidence_ocr` rule**; the other 89 sit on pages
that OCR'd above 80% mean confidence and carry no table or mojibake issue, so
they enter review on their attribute alone.

### Catalogs

| Doc | File | Pg | noTL | OCR% | Elem | T/D/F | Facts | Cand | Issues |
|---|---|---|---|---|---|---|---|---|---|
| `d70644123b57` | bufftech-catalog-2014.pdf | 30 | 9 | 86.3 | 1279 | 2/6/385 | 16 | 0 | mojibake text layer 8 |
| `4d19dc91a67f` | bufftech-catalog-brochure-2009.pdf | 28 | 2 | **28.0** | 857 | 1/1/191 | 6 | 0 | empty after OCR 1, low OCR 1 |
| `3572df9d2278` | bufftech-vinyl-catalog-standardfencing.pdf | 22 | **22** | 75.2 | 521 | 3/16/105 | 1 | 0 | low OCR 4 |

The catalogs are where CAP-3 (BOM) and CAP-2 (component selection) get their
panel widths, heights, and SKU tables — and all three are partly or wholly
scanned. `4d19dc91a67f` reads at 28.0% mean confidence on its OCR'd pages, which
is below anything usable; its pages will map to `ocr_risk='high'` and most of
its tables will become `knowledge_gaps` with reason `unreadable_scan` rather
than claims. That is the correct outcome and it should be visible in the bundle.

### Approvals — the supersession chain

| Doc | File | Pg | noTL | OCR% | Elem | T/D/F | Facts | Cand | Issues |
|---|---|---|---|---|---|---|---|---|---|
| `8727ba0fd4d4` | NOA-06-1019.01 | 10 | 10 | 69.9 | 555 | 0/1/0 | 19 | 43 | low OCR 7, table n/r 4 |
| `32e36a07ab44` | NOA-12-1106.11 | 11 | 11 | 69.8 | 940 | 1/6/0 | 65 | 163 | low OCR 6, table n/r 7 |
| `7a08132799a1` | NOA-21-0125.07 | 16 | 16 | 67.0 | 1015 | 0/1/0 | 78 | 190 | low OCR 10, table n/r 8 |
| `3c8ab51045c7` | NOA-23-0314.05 | 17 | 17 | 67.1 | 1164 | 0/4/0 | 87 | 173 | low OCR 10, table n/r 8 |
| `c267c4cd071f` | NOA-24-0117.05 (primary filing) | 17 | 17 | 74.6 | 1058 | 0/2/0 | 91 | 191 | low OCR 9, table n/r 9 |

Four of the five mix extractors: `c267c4cd071f` is 55 `regex-v1` + 36
table-read, `32e36a07ab44` is 29 + 36, `7a08132799a1` is 42 + 36, `3c8ab51045c7`
is 51 + 36. `8727ba0fd4d4` is 19 `regex-v1` only.

All five are 100% scanned, all five read below 75% mean confidence, and all five
carry `table_not_reconstructed`. Between them they hold 760 of the slice's 922
table-read candidates and every structural number CAP-6 needs.

**And between all five there is exactly one `table` element** — a 4×3 OCR
word-grid on 12-1106.11, which is not a Table 1. The wind, exposure, footing and
spacing numbers exist in the store only as pixels on a page image: no element,
no bounding box, nothing quotable. That single fact is what forced the second
evidence kind in document 2 and the restatement of C-F1 in document 5.

Across Tier A the 922 candidate rows resolve to 670 distinct cells on 39
distinct crops: **8 `wind_exposure_footing`** crops — 384 candidate rows over
**132 distinct cells**, the grids CAP-6 needs — plus 24 `bill_of_materials` (531
rows), 6 `drawing_only` and 1 prose. Only **7 of the 39 have more than one
reader**; the other 32 carry a single agent reading, which is why document 5
reports single-reader and multi-reader agreement separately instead of averaging
them.

Existing derived facts about the chain, which curation consumes as candidates
and re-grounds rather than trusting:

```text
06-1019.01   eff 2008-03-13   exp 2013-03-13   expired
12-1106.11   eff 2013-04-04   exp 2018-03-13   expired
21-0125.07   eff 2021-03-18   exp 2024-03-13   expired
23-0314.05   eff 2023-05-04   exp 2029-03-13   in_force
24-0117.05   eff 2025-04-24   exp 2029-03-13   in_force
```

Note that two members read `in_force` simultaneously. Deciding which one a
person should cite is a CAP-8 dossier decision, not a retrieval decision, and
the slice must produce it. Note also that `retrieval.resolve_document_version`
reads these dates correctly today while `documents.version_status` disagrees
with them: 23-0314.05 is stored `superseded` despite reading `in_force`, and all
four filings of 24-0117.05 are stored `unknown`. The dossier is where those two
views get reconciled.

---

## Tier B — duplicates and constraints (6 documents, 159 pages)

Dossier and page map required; their facts migrate as candidates, but **no
independent claim review**: each Tier-B claim carries `duplicate_of_claim_id`
pointing at its Tier-A twin, and none can be accepted on its own. The six
documents hold 380 of the slice's 1,293 facts, all `regex-v1`. The five
duplicates each resolve to a Tier-A twin; the warranty does not, and is here for
a different reason. They are in the slice specifically to prove that
duplicate handling works — that four filings of the same approval produce one
answer and three pointers, not four competing answers.

| Doc | File | Pg | Resolves to | Basis |
|---|---|---|---|---|
| `bcb0feba5856` | NOA-24-0117.05 (CertainTeed filing) | 17 | `c267c4cd071f` | identical sha256 `2f446717ee75` |
| `ba7f4214e3a9` | MiamiDade-NOA-24-0117.05 (Freedom filing) | 17 | `c267c4cd071f` | identical sha256 `2f446717ee75` |
| `9b9c8c07f948` | Miami-Dade-NOA 24-0117.05 (Industry Standards filing) | 17 | `c267c4cd071f` | identical sha256 `2f446717ee75` |
| `700e6e22c440` | bufftech-gate-install-guide.pdf | 56 | `6431d597a32d` | identical sha256 `b39ab4a32b0b` |
| `87db00d364b3` | bufftech-simtek-fence-install-guide.pdf | 50 | `1085f7c65c47` | identical sha256 `71c42837fd50` |
| `9ca2f5e59ed3` | bufftech-fence-limited-lifetime-warranty.pdf | 2 | — | technical-constraint source |

The four filings of NOA 24-0117.05 are stored under four different manufacturers
with four different `doc_type` values — `engineering_approval`, `hvhz_noa`,
`unspecified`, and `real_miami_dade_noa_vinyl_fence`. Curation must produce one
approval entity, one canonical filing, and three duplicate edges, with the
metadata divergence recorded rather than averaged away.

The warranty is Tier B but is **not** a duplicate. It is here because a warranty
paragraph that says a configuration is not covered is a technical constraint on
safe use, and prohibition 3 forbids discarding it. Its claims are
`claim_kind='textual_constraint'`.

---

## Tier C — referenced, deliberately out of scope

Named so that the slice's boundary is explicit rather than accidental. These are
cited by slice documents but are not curated in slice 1; each becomes a
`knowledge_gap` of reason `out_of_scope` where it blocks an answer.

- ASCE 7 terrain-exposure constants (`manuals/industry-standards/`) — the NOAs
reference the standard; the corpus holds a compilation of it.
- CLFMI wind-load / post-spacing guide — chain-link, adjacent domain, and the
source of 143 table-read candidates on a single page.
- Catalyst successor SKU sheets (`catalyst-capecod-sku-sheet.pdf`,
`catalyst-fence-accents-hardware-sku-sheet.pdf`) — the brand successor's current
catalog. Relevant to CAP-1 succession and CAP-3, deferred to slice 2.
- SimTek molded-fence NOAs 22-0616.10 and 24-0117.06 — a *different material
class* that shares the Barrette parent. They are the corpus's other approval
chain, and keeping them out of slice 1 is what makes the slice a test of one
family rather than of a manufacturer.
- `data/structural/certainteed-bufftech-structural.json` — read as a
`curated_dataset` authority-20 source *and as a known-wrong prior*. It is never
a claim source on its own; where it disagrees with a page, the page wins and the
disagreement is recorded as a conflict.

---

## What the slice is expected to prove, and what it cannot

**Can prove:** dossiers and page maps over mixed native/scanned material; entity
and alias resolution across a brand transfer; migration of all 1,293 slice facts
into conditional candidates; the mandatory-review gate under real volume (773
rows / 204 tuples before a table is read); duplicate resolution;
supersession-aware answers; crop generation for element-backed and pixel-only
claims alike.

**Cannot prove:** anything about the China track (deliberately separate), about
non-vinyl materials, or about families with no approval chain. Slice 1 is a
depth test. Breadth is what the corpus-wide phase is for, and it does not start
until this passes.
