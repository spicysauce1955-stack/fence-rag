# `GET /source-refs/{id}` — design

```text
Status:    Design, for review. Nothing here is implemented.
Written by: the Knowledge team (this repo), in response to contract.md §4.
Authority: Advisory on internals. The only binding items it satisfies are
           contract.md §3.1.3 ("every value carries at least one resolvable
           SourceRef, and GET /source-refs/{id} returns something a person can
           look at") and §3.3.1-3.3.3 (what the frontend must show).
Reads with: docs/curation/02-curation-schema.md §2.5.3 (evidence kinds) and
           §2.11 (the crop transform), docs/distribution-design.md §6
           (derived/ is a cache).
Companion: fixtures/source-ref-examples.json — seven real records the frontend
           can build against today.
```

## 0. Why this first

The contract names two pieces of work that cross no boundary and need no
agreement. This is the one on our side. It cites nothing, blocks nothing, and a
review queue cannot exist without it: a curator asked to accept a footing depth
that exists only as pixels on a scanned drawing sheet has nothing to accept
*from* until this endpoint returns the pixels.

Two facts from this store set the whole shape of the problem, and they are worth
stating before any schema:

- **73,894 of the 81,794 elements have a bounding box and no crop.** Region
  images exist for `figure` (6,660), `table` (603) and `drawing` (221) — 7,484 in
  total. Every paragraph, heading, list and caption — which is where most
  quotable text lives — has coordinates and no picture. Crops must therefore be
  *generated from the bbox on demand*, not looked up.
- **The load-bearing structural values have no element at all.** 73 pages carry
  `table_not_reconstructed`; on the 44 distinct flagged pages, blind manual
  verification measured digit-bearing recall at 0.588. For those the evidence is
  the page image and nothing else — no bbox, no quote, no cell.

So the endpoint has to serve two genuinely different things through one shape: a
quote with a box around it, and a picture with no quote. Nulling out columns to
fit one into the other is how a system starts claiming provenance it does not
have.

---

## 1. What a source ref is

An immutable, content-addressed pointer to **one piece of evidence in one version
of one document**. It is created when a claim, a definition field or a table row
is written, and it never changes afterwards.

```text
source_ref_id   "sref_" + first 32 hex chars of sha256 over the canonical locator
```

The locator is the canonical JSON of exactly this tuple, keys sorted, no
whitespace:

```text
{ v: <document_versions.sha256>,     the bytes, not the path
  p: <page_no>,
  k: <kind>,
  b: [x0,y0,x1,y1] | null,           bbox in poppler display points, 2dp
  e: <element_id> | null,
  t: [table_id,row,col] | null,
  g: <grid_id> | null }
```

Four properties this buys, and each of them is load-bearing:

1. **Deterministic.** The same evidence gets the same id from any process, in any
   order, on any machine. Publishing a snapshot twice does not churn ids.
2. **Version-pinned by content.** The `v` component is the file's SHA-256. If a
   manufacturer reissues a PDF at the same path, the new bytes produce a
   different version and therefore different ids — a re-ingest can never silently
   repoint an existing citation at different pixels.
3. **Re-derivable.** If the `source_refs` row is lost, it can be recomputed from
   the locator. The row is an index, not the only copy of the truth.
4. **Opaque to the consumer**, as the contract requires. The format above is ours
   and is not part of the contract; Planning must treat the string as a token.

The id is stored in `source_refs(source_ref_id, locator_json, created_at,
retain_until, tenant)` so that the reverse lookup exists and retention is
enforceable.

### 1.1 Why the id does not contain the element id alone

`element_id` is an extraction artefact. A re-extraction with a different layout
pass can renumber elements. The locator therefore records the **bbox** as well,
and §4 renders the crop from `(version, page, bbox, dpi)` without consulting the
element at all. An old source ref whose element has vanished still resolves to
the correct rectangle of the correct page; only the *quote* degrades, and it
degrades to an explicit `quote: null` with a reason, never to a wrong quote.

---

## 2. The five kinds

These are the evidence kinds `docs/curation/02-curation-schema.md` §2.5.3 already
argues for, plus `page`, which that section's whole-page crops imply but do not
name.

| `kind` | Has quote | Has bbox | Has image | Backed by |
|---|---|---|---|---|
| `element_quote` | yes | yes | rendered from bbox | an element's `text` / `ocr_text` |
| `table_cell` | yes | yes | rendered from cell bbox | a `table_cells` row |
| `page` | no | no | the whole page | a page with no usable element |
| `visual_reading` | no | in crop pixels | the whole page, plus a cell box | a person or reader looking at pixels |
| `derived` | no | no | **none** | a calculation, or `data/structural/*.json` |

Three things to note about that table, because each one is a promise the
interface has to keep honestly:

- **`derived` returns no image and says so.** A value asserted by a hand-researched
  `data/structural/*.json` file is not in a `documents` row at all. It is real
  knowledge and it is addressable, but there is no page to look at. The curation
  schema already rules that `derived` evidence can never reach `accepted`; the
  API's job is only to make the absence explicit rather than 404.
- **`visual_reading` carries the reader's identity.** There is no quote, so the
  only thing standing behind the number is *who read it and from which pixels*.
  Both travel in the response.
- **`page` and `visual_reading` differ.** `page` says "the evidence is somewhere on
  this page"; `visual_reading` says "a named reader read this cell, at these crop
  pixels, under these row and column labels". The second is much stronger and the
  interface must not let them look alike.

---

## 3. The response

```jsonc
{
  "source_ref_id": "sref_…",
  "kind": "element_quote",
  "contract_version": "0.1.0",
  "retain_until": "2031-08-24",

  "document": {
    "document_id":  "doc-d70644123b57",
    "title":        "Bufftech Vinyl Fence Catalog …",
    "manufacturer": "CertainTeed",
    "product_family": "…",
    "doc_type":     "cut_sheet",
    "corpus_track": "us",
    "structural":   false,
    "source_path":  "manuals/certainteed-bufftech/bufftech-catalog-2014.pdf",

    "version": {
      "version_id":  "doc-d70644123b57@4febd3af8b66",
      "sha256":      "4febd3af8b6667e02c65dd97037a36d574b10dedb3db0d4697cddc0a00fccbed",
      "file_size_bytes": 3931036,
      "page_count":  30
    },

    "status": {
      "version_status":       "unknown",          // active | superseded | unknown
      "version_status_basis": null,
      "issue_date":           null,
      "expiration_date":      null,
      "superseded_by":        [],
      "same_content_as":      []
    }
  },

  "locus": {
    "page_no": 28,
    "page_width_pt": 612.0,
    "page_height_pt": 792.0,
    "bbox_pt": [42.0, 96.96, 564.96, 747.84],
    "bbox_space": "poppler_display_top_left",
    "rotation_already_applied": true
  },

  "text": {
    "quote": "Racks up | 10 degrees 3' and | 4' high, 5 degrees | and 6' high",
    "quote_is_verbatim_substring_of": "elements.ocr_text",
    "text_source": "ocr",                          // pdf_text_layer | ocr | image_ocr | docx_xml
    "ocr_confidence": 76.52,
    "element_id": "element-0d0c63f057-0005",
    "element_type": "table",
    "heading_path": ["…"]
  },

  "image": {
    "status": "available",     // available | source_not_fetched | not_applicable | failed
    "crop": {
      "url":       "/source-refs/sref_…/image",
      "width_px":  1461, "height_px": 1816,
      "dpi":       200,
      "bbox_px":   [112, 265, 1573, 2081],
      "pad_px":    4,
      "sha256":    "4442113960cc…"
    },
    "page": {
      "url":       "/source-refs/sref_…/page-image",
      "width_px":  1700, "height_px": 2200,
      "dpi":       200,
      "sha256":    "…"
    },
    "tool_fingerprint": "poppler-24.02.0;png"
  },

  "warnings": [
    { "code": "SOURCE_TEXT_FROM_OCR",        "params": { "confidence": 76.52 } },
    { "code": "SOURCE_TEXT_LAYER_MOJIBAKE",  "params": { "pages_affected": 8 } },
    { "code": "SOURCE_VERSION_STATUS_UNKNOWN", "params": {} }
  ]
}
```

### 3.1 Why `status` is a block and not a string

`documents.version_status` across this corpus is **3 active, 9 superseded, 132
unknown**. A field that is `unknown` 92% of the time will be rendered as "current"
by any interface that reads it alone, and `rationale.md` §1 is the record of what
that costs: a promoted footing depth backed by a *superseded* SimTek NOA.

Worse, the basis is often weak. Six of the nine superseded documents were
classified by `keyword in title/filename`. One of them —
`NOA-23-0314.05-CertainTeed-…-current-2023-2029.pdf` — has the word **current** in
its filename and is marked `superseded` on the stronger basis "named as a
previous approval by a later NOA". Status and basis contradict each other at a
glance, and only the basis settles it.

So the response returns `version_status` and `version_status_basis` together,
always, and emits `SOURCE_VERSION_STATUS_UNKNOWN` or
`SOURCE_STATUS_BASIS_FILENAME` as machine-readable warnings. The frontend can
then satisfy contract §3.3.1 — *never present a search result as an answer* —
without knowing anything about NOAs.

### 3.2 `warnings` — the honesty channel

Every measured hazard in this corpus becomes a code, so the interface renders it
without special-casing anything:

| Code | Params | Fires when | Instances here |
|---|---|---|---|
| `SOURCE_TEXT_FROM_OCR` | `confidence` | `text_source` is `ocr`/`image_ocr` | 25,150 elements |
| `SOURCE_OCR_LOW_CONFIDENCE` | `confidence` | page confidence below threshold | 172 pages |
| `SOURCE_TEXT_LAYER_MOJIBAKE` | `pages_affected` | document is one of the six re-OCR'd | 81 page issues, 6 documents |
| `SOURCE_TABLE_NOT_RECONSTRUCTED` | — | page carries the issue; the image *is* the evidence | 73 pages |
| `SOURCE_DOCUMENT_SUPERSEDED` | `superseded_by` | a `superseded_by` edge exists | 9 documents |
| `SOURCE_VERSION_STATUS_UNKNOWN` | — | status is `unknown` | 132 documents |
| `SOURCE_STATUS_BASIS_FILENAME` | — | basis is a filename keyword, not a document assertion | 6 documents |
| `SOURCE_CONTENT_DUPLICATED` | `also_filed_under` | a `same_content_as` edge exists | 40 edges, 14 groups |
| `SOURCE_NO_IMAGE_AVAILABLE` | `reason` | DOCX, or `derived` | 1 document |
| `SOURCE_NOT_FETCHED` | `subset` | the corpus subset is not local | deployment-dependent |

These are additions to the **Warning & gap codes** registry that contract §2
already declares open — *"adding an entry is never a breaking change"* — so none
of this needs negotiation. Both locale bundles are required by §3.3.4; these
codes are parameterised sentences we author, not text lifted from a document, so
translating them is tractable. (Warnings lifted *from* documents are a different
problem, and §7 question 5 of the audit response addresses it.)

`SOURCE_CONTENT_DUPLICATED` deserves a note. Fourteen groups of byte-identical
files are filed under different manufacturers, linked with `same_content_as` and
never deduplicated. A source ref names one of them. A curator shown "CertainTeed"
should be able to see that the identical bytes are also filed under Freedom
Outdoor Living, because "which manufacturer published this" is exactly the
judgement they are being asked to make.

---

## 4. Producing the image

### 4.1 The transform is normative

`docs/curation/02-curation-schema.md` §2.11 already works this out and verified it
against the store; this section pins it as the API's contract with itself.

```bash
pdftoppm -png -r <dpi> -f <page_no> -l <page_no> \
         -x <x0px> -y <y0px> -W <wpx> -H <hpx> <source.pdf> <prefix>
```

```text
scale = dpi / 72
x0px  = max(0, int(x0 * scale) - PAD_PX)
y0px  = max(0, int(y0 * scale) - PAD_PX)
wpx   = min(page_w_px, int(x1 * scale) + PAD_PX) - x0px
hpx   = min(page_h_px, int(y1 * scale) + PAD_PX) - y0px
PAD_PX = 4
```

Four traps, all of which have bitten this repo or are one careless commit from
doing so:

1. **Never hardcode 200 dpi.** The distribution is `{200: 2140 pages, 72: 6,
   NULL: 1}`. The six 72-dpi pages are the Weatherables CAD PNGs, where
   `pages.width/height` are *pixels* rather than points and the arithmetic only
   works because `72/72 = 1`. The one NULL is the DOCX, which has no image; it is
   flagged, never guessed.
2. **Top-left origin, and no rotation transform.** `pdftotext -bbox-layout`
   reports `yMin` from the top, which is what `pdftoppm -y` expects. Applying the
   usual PDF bottom-left flip (`y' = h - y`) mirrors every crop vertically. For
   pages with a non-zero `/Rotate`, `pages.width/height` are already the swapped
   display rectangle and pdftoppm has already applied the rotation, so bbox, page
   rectangle and image share one space. CLAUDE.md records that adding a rotation
   transform here was a real bug, found and removed once.
3. **Crop failure raises.** It does not return `False` and carry on.
4. **The rounding rule is part of the transform**, not an accident of the
   implementation. `pages.width * dpi/72` matches `assets.width_px` to within one
   pixel across all 2,140 measured pages — 2,040 exactly, 96 by less than a pixel,
   4 by exactly one — so exact equality is the wrong assertion and the transform
   must fix its own rule rather than assume poppler's.

### 4.2 A decision this design has to make, and does

There are two crop paths in this repo and they do not produce the same bytes.

- **Today's path** (`extract.py:107` `_crop_region`) opens the *rendered page PNG*
  with **Pillow**, computes `scale = image_width_px / page_width_pt` from the
  actual image, and pads by 4 pixels. It produced the 7,484 region images now in
  `workspace/derived/`.
- **The §2.11 path** windows the *PDF* with **poppler** at the nominal dpi.

They differ in the scale (measured vs nominal — up to one pixel) and in
everything downstream of the encoder. `crop_sha256` cannot be defined against
both.

**Recommendation: the API serves poppler-windowed crops, and the existing Pillow
crops become a legacy cache that is not served.** Three reasons:

1. Pillow is optional and lives in the git-ignored `workspace/pylibs/`.
   `_crop_region` **returns `False` when it is absent**. An endpoint whose central
   promise is "returns something a person can look at" cannot be backed by a
   dependency that may not be installed, on a machine with no `sudo`, no `apt` and
   no system `pip`.
2. Poppler is a declared dependency and is already how every page image is made.
3. It collapses two code paths into one. The 73,894 boxed elements with no
   pre-cut crop have to be rendered on demand anyway; serving the 7,484
   pre-cut ones from a different code path would mean two definitions of the same
   picture.

The cost is honest and worth stating: rendering a paragraph crop means poppler
touches the PDF rather than an already-decoded PNG. **Now measured** — 24.8 ms at
p50 and about a tenth of a full-page render, against a 5.6 s p99 concentrated in
nine large scanned documents. See §8.4 and
`workspace/reports/k3-crop-render-cost.md`.

### 4.3 Materialisation, not storage

`docs/distribution-design.md` §6 establishes `workspace/derived/` as a
**regenerable cache**, and D6 proved it: deleting the directory entirely changed
no evaluation number, and an evaluation run regenerated 462 MB of the 4.5 GB
store — about 10% — which bounds the cost of a cold cache.

The endpoint inherits that. Resolution order for any image:

```text
cache hit  →  render from the fetched corpus  →  typed failure
```

There is no third store and no hosted image bucket. `image.status` reports which
branch was taken, and `source_not_fetched` names the subset (`structural`,
`bufftech`, `china`, `all`) the operator would have to fetch — the documents where
the image *is* the evidence are exactly the scanned NOA sheets under
`--subset structural`.

### 4.4 Delivery

`GET /source-refs/{id}/image` and `/page-image` return `image/png`.

- `ETag` is the crop's SHA-256; `Cache-Control: public, max-age=31536000, immutable`.
  A source ref is immutable by construction, so this is safe and it is what makes
  a review queue scrolling through hundreds of crops usable.
- `X-Content-Type-Options: nosniff`. PNG only — never SVG, which is script-bearing.
- Image URLs are **relative to the same API base** as the JSON. Planning proxies
  the frontend's authoring and review traffic (contract §1.5), and a relative URL
  proxies identically without signed URLs, expiring tokens, or a second auth
  path for `<img src>`.
- `tool_fingerprint` travels in the JSON because poppler's PNG output is
  version-dependent. Byte-identity of a crop is asserted *within* a fixed
  fingerprint, not across upgrades. The `source_ref_id` does not change when the
  fingerprint does — the id addresses a rectangle of a document, not a rendering
  of it.

---

## 5. Treating the document as untrusted

`guide.md` prohibits treating document contents as instructions, and this
endpoint is the one place where document bytes reach a person's screen.

- `text.quote` is returned as a JSON string and nothing else. The API never
  returns HTML, never returns Markdown, and never returns a link extracted from a
  document. Rendering is the frontend's, and it renders text as text.
- No URL, path, or filename found *inside* a document is ever placed in a field
  the interface would make clickable. `document.source_path` is a repo-relative
  path we assigned, not something the PDF said.
- `source_ref_id` is a digest. It is never a path fragment, so there is no
  traversal surface on `{id}`.
- Tenant isolation is enforced in the query, not in the caller (contract §3.1.7):
  the `source_refs` row carries `tenant`, and a mismatch is a 404, not a 403 — a
  403 would confirm the id exists.

---

## 6. What this endpoint does *not* prove

Worth stating in the design because the frontend obligation depends on it and it
is easy to lose.

> A source reference proves **where the system looked**. It does not prove that
> the source says what was written down.

Those are different guarantees. This endpoint delivers the first one completely
and the second one not at all — which is the entire reason contract §3.3.1 exists
and why `visual_reading` carries a reader identity rather than pretending to be a
quote.

---

## 7. The fixture

`fixtures/source-ref-examples.json` carries **seven records built from real rows
in this store**, chosen to cover every kind and every failure mode the frontend
will actually hit. Values — ids, hashes, pixel dimensions, confidences, bboxes —
are the real ones, so a component that renders all seven correctly will render
the corpus.

| # | Kind | What it exercises |
|---|---|---|
| 1 | `element_quote` | text-layer paragraph, bbox, **no pre-cut crop** — the majority case |
| 2 | `element_quote` | OCR'd table with a crop, low confidence, mojibake document |
| 3 | `page` | scanned NOA sheet, `table_not_reconstructed`, no quote at all |
| 4 | `visual_reading` | a reader's cell reading with crop-pixel box and row/col labels |
| 5 | `element_quote` | **superseded** document whose filename says "current" |
| 6 | `element_quote` | CAD PNG at 72 dpi, where page units are pixels |
| 7 | `derived` | a `data/structural/*.json` assertion — no document, no image |

Records 3 and 7 are the two the frontend is most likely to get wrong, and both
are common here: 3 is where the structural numbers live, and 7 is a large share of
the hand-researched material.

---

## 8. Open, and what we would want agreed

Logged in `05-acceptance-open-questions.md`; repeated here so the design is readable
alone.

1. **Does `retain_until` apply to source refs?** The contract pins it on
   snapshots. A source ref is Discovery, never an input to a run, so a run's
   determinism does not depend on it — but a plan printed last March that a person
   later inspects does. Our position: source refs cited by any snapshot inherit
   that snapshot's `retain_until`, and are excised with the same tombstone
   mechanism. Needs Planning's agreement because it is a retention promise.
2. **Is a source ref tenant-scoped or global?** The corpus is manufacturer
   documents, which are not tenant property. But contract §3.1.7 requires a
   snapshot for one tenant to contain nothing belonging to another. Our reading:
   source refs over the shared corpus are global; source refs over a
   tenant-uploaded document are tenant-scoped, and the two never mix in one
   response. Worth confirming, since it is an isolation promise.
3. **Batch resolution.** A review screen showing 50 rows would issue 50 requests.
   We would like `POST /source-refs:batch` taking up to N ids. Adding it does not
   change any shape in the contract.
4. ~~**Render cost is unmeasured.**~~ **MEASURED 2026-08-25** —
   `workspace/reports/k3-crop-render-cost.md`, harness at
   `scripts/measure_crop_cost.py`. A cold crop is **24.8 ms at p50, 308 ms at
   p95, 5.6 s at p99**; 3.2% of crops exceed one second. Windowing costs about a
   **tenth** of a full-page render, so §4.2's choice holds on cost as well as on
   correctness. The p99 is two documents — the 20 MB and 11 MB Showtech China
   catalogs — and 9 scanned documents over 10 MB hold 13.9% of all boxed
   elements. **Render on demand as designed; cache the page, not the element; no
   pre-render pass.** The review queue specifically: its 504 readings sit on
   **10 distinct pages** at 164 ms each, so a 50-row screen is 1.3 s cold and
   almost entirely cache hits after the first row of each page.
5. **The `us` / `china` tracks.** The two corpora are deliberately separate:
   Chinese-language, metric, GB standards rather than ASTM. Nothing in the
   contract mentions a track, and `Snapshot` has a `tenant` but no locale or
   standards regime. `corpus_track` is returned on every source ref so the
   distinction is at least visible; where it belongs in the contract is an open
   question rather than a proposal.
