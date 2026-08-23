# Recommended architecture: evidence-first, multimodal, and reversible

Do **not** build a single “clean text corpus.” Build three separate but linked layers:

1. **Canonical evidence layer** — immutable source files, page images, text spans, tables, figures, drawings, coordinates, and parser outputs.
2. **Structured knowledge layer** — normalized products, components, dimensions, constraints, procedures, relationships, conflicts, and document versions.
3. **Retrieval layer** — hierarchical text chunks, table chunks, visual/page units, exact lexical indexes, embeddings, and structured filters.

```text
Web crawl / file drop
        │
        ▼
Immutable source registry
  ├── original bytes
  ├── source URL + crawl metadata
  └── SHA-256 content identity
        │
        ▼
Document and page probe
  ├── MIME / format
  ├── language
  ├── native-text quality
  ├── scan / mixed-page detection
  ├── tables / drawings / image density
  └── suspected document type
        │
        ▼
Per-page parser router
  ├── native structured parsing
  ├── OCR derivative
  ├── table/layout parser
  ├── drawing/figure preservation
  └── exception/VLM parsing
        │
        ▼
Canonical evidence graph
  Document → Version → Page → Element → Asset → Evidence span
        │
        ├── deduplication / translation / supersession graph
        ├── relevance classification
        ├── structured fact extraction
        ├── conflict detection
        └── quality gates / review queue
        │
        ▼
Retrieval units and indexes
  ├── lexical / exact search
  ├── structured fact search
  ├── dense semantic search
  ├── table retrieval
  └── visual page / figure retrieval
```

## Non-negotiable invariants

* The original file is never overwritten or discarded.
* OCR, cleaned text, Markdown, JSON, and embeddings are **derived artifacts**, not canonical sources.
* Every extracted specification must point to a document, physical page, bounding box or table cells, and exact source text.
* Original numeric lexemes such as `5/8"`, `0.625 in`, `±1/16`, `100 mph`, and `20 psf` must be retained even after normalization.
* Deduplication and filtering may suppress items from default retrieval, but must remain reversible.
* LLMs and vision models may create **candidate facts**; deterministic validation promotes them to verified facts.
* Conflicting specifications must be represented explicitly rather than silently resolved.

---

# 1. Ingestion and document parsing

## 1.1 Immutable intake registry

Every downloaded object should receive a content-derived identity before parsing:

```json
{
  "source_object_id": "sha256:<bytes-hash>",
  "source_url": "https://...",
  "retrieved_at": "2026-08-21T...",
  "http_etag": "...",
  "http_last_modified": "...",
  "declared_content_type": "application/pdf",
  "detected_content_type": "application/pdf",
  "file_name": "installation-guide.pdf",
  "byte_size": 4819203,
  "crawl_job_id": "...",
  "raw_object_path": "s3://corpus/raw/sha256/...",
  "source_authority": "manufacturer_site"
}
```

Use MIME sniffing rather than trusting the extension. Store the raw HTML response as well as any extracted main content; otherwise future parser improvements cannot be replayed.

All pipeline outputs should include:

* source-object hash;
* parser name and version;
* parser configuration hash;
* model name/version where applicable;
* pipeline code commit;
* start/end timestamps;
* output content hash.

This gives deterministic replay and makes parser regressions observable.

## 1.2 Recommended parser roles

### Docling: primary local structural parser

Use Docling as the default parser for native PDFs, DOCX, HTML, and common office formats. Its unified document representation supports text, tables, pictures, hierarchy, headers/footers, bounding boxes, and provenance. That makes it suitable as the backbone of the canonical document graph rather than merely a Markdown exporter. ([Docling][1])

Use Docling for:

* section hierarchy and reading order;
* paragraph, list, table, picture, and caption identification;
* page and bounding-box provenance;
* Markdown for human inspection;
* structured JSON as the durable parser output.

Do not assume that Docling—or any general parser—has semantically understood every dimension callout inside an engineering drawing.

### PyMuPDF: forensic sidecar and deterministic verifier

Run PyMuPDF alongside the primary parser for PDFs. It exposes words and text blocks with coordinates, image information, table cells, page geometry, and PDF vector drawings. It is especially valuable for detecting line-art drawings, preserving coordinates, extracting embedded images, and independently verifying table and numeric output. ([PyMuPDF][2])

Use it to produce a page-sidecar such as:

```json
{
  "page_index": 16,
  "printed_page_number": "14",
  "width": 612,
  "height": 792,
  "rotation": 0,
  "words": [],
  "blocks": [],
  "images": [],
  "vector_drawing_regions": [],
  "table_candidates": [],
  "native_numeric_tokens": []
}
```

This sidecar is useful even when Docling supplies the primary reading order.

### OCRmyPDF and Tesseract: scan normalization, not document understanding

Use OCRmyPDF to create an OCR derivative for scanned or mixed PDFs. It can rotate and deskew pages, skip pages that already contain text, or redo defective OCR while preserving visible vector text. Tesseract can produce hOCR/TSV-style outputs containing text positions rather than only flat text. ([OCRmyPDF][3])

Recommended policy:

* `skip` mode for genuine mixed PDFs with good native text;
* `redo` mode when an existing hidden OCR layer is demonstrably corrupted;
* never replace the original PDF with the OCR derivative;
* avoid aggressive image cleaning on drawings with thin dimension lines;
* retain page images both before and after preprocessing for comparison.

OCRmyPDF/Tesseract should supply the textual layer. A layout parser should subsequently reconstruct tables, sections, and figures.

### PaddleOCR PP-StructureV3: difficult scanned layouts and tables

Use PP-StructureV3 as an escalation parser for scanned technical sheets, difficult tables, multi-column layouts, or pages where basic OCR recovered words but not structure. Its pipeline includes layout analysis and OCR, with optional table and formula recognition, reading-order restoration, and Markdown/JSON output. ([paddlepaddle.github.io][4])

Do not run this expensive route over every document. Route only pages that fail native/OCR quality gates.

### Unstructured: broad format adapter and secondary parser

Unstructured is useful as a source connector and general element partitioner. Its PDF strategies include fast, high-resolution, and OCR-oriented paths. Use it as:

* an ingestion adapter for miscellaneous formats;
* a secondary parser for comparison;
* a fallback when its element model integrates naturally with another part of your platform.

It should not be the only authoritative parser for specification-heavy PDFs. ([Unstructured][5])

### LlamaParse: exception queue or benchmark parser

LlamaParse can process scans, PDFs, tables, charts, and images into Markdown, text, or JSON, and provides schema-oriented extraction capabilities. It is a hosted service, so use it only where data governance permits. ([Developer Documentation][6])

A reasonable pattern is:

* local pipeline handles the normal corpus;
* local quality gates identify hard pages;
* selected hard pages are sent to LlamaParse;
* its output is compared against local extraction and the rendered page;
* no LlamaParse-derived value becomes verified without evidence anchoring.

### HTML: dual extraction, not boilerplate removal alone

Use Trafilatura to identify main narrative content and metadata, but also retain and parse the DOM independently. Trafilatura is designed for main-text extraction and boilerplate removal; that means it may intentionally discard material that your domain considers meaningful. ([trafilatura.readthedocs.io][7])

Separately preserve:

* `<table>`;
* `<dl>` specification lists;
* ordered installation steps;
* headings and their DOM paths;
* JSON-LD, microdata, and product schema;
* downloadable-document links;
* image captions and `alt` text;
* product variants and selectors;
* raw HTML.

For repeated manufacturer sites, build site-specific selectors after observing stable templates. Generic main-content extraction alone will often lose specification sidebars and comparison tables.

## 1.3 Per-page PDF routing

Route at the **page level**, not only the document level. A single manual can contain native pages, scanned approvals, bitmap drawings, and vector tables.

```python
for page in document:
    probe = inspect_page(page)

    if probe.native_text_is_valid and not probe.complex_layout:
        primary = parse_with_docling(page)
        sidecar = parse_with_pymupdf(page)

    elif probe.native_text_is_valid and probe.complex_layout:
        primary = parse_with_docling(page, enhanced_tables=True)
        sidecar = parse_with_pymupdf(page)
        secondary = parse_with_paddle_if_quality_fails(page)

    elif probe.is_scanned_or_bad_ocr:
        ocr_page = create_ocr_derivative(page)
        primary = parse_with_docling(ocr_page)
        secondary = parse_with_paddle_if_quality_fails(ocr_page)

    if probe.contains_drawing_or_dense_callouts:
        preserve_page_render(page)
        preserve_vector_paths(page)
        extract_callout_candidates(page)

    validate(primary, sidecar, secondary)
```

The page probe should combine several signals:

* printable-character ratio;
* native characters per page;
* proportion of page occupied by images;
* text boxes outside page boundaries;
* repeated or scrambled glyph ordering;
* vector line density;
* table-like line grids;
* number and unit tokens;
* OCR confidence distribution;
* page rotation;
* differences between visual and extracted text.

A page with only 40 characters may be a scanned page, or it may be a valid engineering drawing. Character count alone is insufficient.

## 1.4 Diagrams and dimensional callouts

There is no general-purpose parser that can be trusted to transform arbitrary engineering drawings into exact structured geometry without verification.

For every drawing-heavy page, preserve:

1. Original page PDF.
2. Full-page render at sufficient resolution.
3. Extracted vector paths or SVG where available.
4. Native text and OCR words with coordinates.
5. Figure and drawing-region crops.
6. Nearby captions and section context.
7. Callout candidates and their bounding boxes.
8. A link from each callout candidate to the referenced component or drawing object where detectable.

A multimodal model can propose:

```json
{
  "callout_text": "5\" TYP.",
  "measurement_type": "post_width",
  "referenced_object": "line_post",
  "text_bbox": [0.41, 0.18, 0.48, 0.21],
  "target_region_bbox": [0.32, 0.20, 0.65, 0.66],
  "confidence": 0.82
}
```

But the exact `5"` token must be recoverable from the page evidence. The system should not accept a visually inferred value that lacks a source crop and coordinate.

## 1.5 Parsing quality gates

A parsed page should not be published merely because the parser returned success.

For core technical pages, calculate:

* **Numeric-token coverage:** proportion of source numeric/unit tokens represented in extracted elements.
* **Table topology agreement:** row/column counts, headers, merged cells, and footnotes.
* **Cross-parser numeric agreement:** whether independent parsers extracted the same values and units.
* **Reading-order validity:** heading → table/caption → body order.
* **Figure coverage:** drawing-heavy pages must have corresponding visual assets.
* **Provenance completeness:** every element has page and coordinates where available.
* **OCR risk:** suspicious substitutions near dimensions and identifiers.
* **Source-render overlay:** extracted boxes can be visually overlaid for inspection.

For specification pages, aim for essentially complete numeric-token retention. A missing marketing statistic is tolerable; an unexplained missing `±1/16"` tolerance is a failed page.

Send pages to a review or escalation queue when:

* parsers disagree about a dimension or unit;
* a table has detached headers;
* OCR confidence is low around digits, fractions, primes, or decimal points;
* a drawing contains many text callouts but few were extracted;
* the parser changes a part number;
* a numeric token appears visually but nowhere in the evidence graph.

---

# 2. Normalization and deduplication

## 2.1 Preserve raw and normalized representations

Each text element should retain at least:

```json
{
  "text_raw": "Post Spacing: 6'-0\" O.C.",
  "text_search": "post spacing 6 ft 0 in on center",
  "text_display": "Post Spacing: 6′-0″ O.C.",
  "normalization_operations": [
    "unicode_quote_normalization",
    "abbreviation_expansion_for_search"
  ]
}
```

Safe normalization includes:

* Unicode normalization;
* whitespace cleanup;
* line-break and hyphenation repair;
* normalized quotation marks for display;
* case-folded search representation;
* standard abbreviations in an additional search field.

Unsafe operations include:

* replacing the raw fraction with a floating-point value;
* silently fixing an OCR digit;
* removing repeated content before determining whether it is a table header;
* treating `nominal` and `actual` as equivalent;
* converting all units and deleting the source units.

## 2.2 Multi-stage deduplication

Use increasingly expensive stages.

### Stage A: exact binary duplicates

Compute SHA-256 over original bytes. This catches the same object downloaded under different URLs or filenames.

Store all source URLs as aliases of the same `source_object_id`.

### Stage B: exact canonical-content duplicates

Calculate separate hashes for:

* normalized document text;
* each page’s normalized text;
* normalized table-cell stream;
* extracted embedded images;
* page renders.

This catches PDFs that differ only in metadata, compression, or download wrappers.

### Stage C: near-duplicate candidate generation

Use:

* SimHash for inexpensive coarse text similarity;
* MinHash over word or character shingles;
* image perceptual hashes for page renders and figures;
* table signatures based on normalized headers and cells;
* sets of part numbers, dimensions, and model identifiers.

`datasketch` MinHash/LSH is suitable for candidate generation, but LSH is approximate and can produce false positives and false negatives. Therefore, never let the LSH result itself perform the canonicalization decision. ([Ekzhu][8])

### Stage D: page/section sequence alignment

Manual revisions often add a cover, remove a warranty page, or insert one table. Whole-document similarity can then be misleading.

Align page or section fingerprints using sequence alignment:

```text
Document A: cover, intro, parts, install-1, install-2, warranty
Document B: cover, intro, parts, install-1, install-2, wind-table, warranty
```

These should become related versions, not unrelated documents and not exact duplicates.

### Stage E: verified relationship classification

Represent relationships explicitly:

```text
exact_duplicate_of
near_duplicate_of
translation_of
localized_variant_of
supersedes
superseded_by
derived_from
reformatted_copy_of
same_document_family
```

The verifier should consider:

* manufacturer and source authority;
* product family;
* part-number overlap;
* page/section alignment;
* exact numeric-token agreement;
* table topology;
* figure/image hashes;
* publication or revision markers;
* language;
* market or jurisdiction.

## 2.3 Cross-format deduplication

For PDF versus DOCX versus HTML, compare a format-independent structural signature:

```json
{
  "headings": ["installation", "post setting", "rail installation"],
  "part_numbers": ["POST-5X5-150", "RAIL-T6"],
  "dimension_tokens": ["5 x 5", ".150", "72 in"],
  "table_headers": ["profile", "width", "height", "wall thickness"],
  "figure_hashes": ["phash:..."],
  "procedure_verbs": ["insert", "level", "secure"],
  "section_count": 12
}
```

A PDF generated from the same DOCX should align strongly even if pagination differs.

## 2.4 Cross-lingual alignment

First detect language per page or section. FastText’s published language-identification models cover 176 languages, making them a practical local first pass. ([fastText][9])

Then use a two-stage alignment process.

### Candidate generation

Require some combination of:

* same manufacturer;
* same product identifiers or SKU family;
* matching diagram/figure hashes;
* similar page counts or section structures;
* matching dimensions;
* multilingual embedding similarity.

LaBSE and multilingual E5 are designed to place semantically corresponding content from different languages into shared embedding spaces and are suitable for candidate generation and section alignment. ([arXiv][10])

### Verification

Do not declare two documents translations solely because multilingual embeddings are close. Verify:

* part numbers;
* dimension values;
* table row/column structures;
* figure order;
* warnings and numbered steps;
* revision and regional scope;
* code references and wind-load conditions.

A Spanish manual with metric-localized dimensions or different regional approval requirements may be a `localized_variant_of`, not an exact `translation_of`.

## 2.5 Canonical-version selection

Canonicalization should happen at the **document-family level**, while all variants remain stored.

Suggested ranking:

1. Official manufacturer or regulator source.
2. Explicitly current revision from the document body.
3. Correct market or jurisdiction for the query.
4. Complete document rather than excerpt.
5. Best extraction quality.
6. Preferred language for retrieval.

Do not infer the latest revision from:

* download timestamp;
* filename;
* website page date alone;
* PDF metadata alone.

Store:

```json
{
  "document_family_id": "family:...",
  "document_version_id": "docver:...",
  "canonical_for_market": ["US"],
  "canonical_for_language": ["en"],
  "revision_status": "current|superseded|historical|unknown",
  "revision_basis": "footer_revision_code",
  "revision_evidence_id": "element:..."
}
```

A duplicate may be excluded from the default index, but it should remain addressable for provenance and source comparison.

---

# 3. Extraction and structural preservation

## 3.1 Canonical evidence data model

A practical relational/document model is:

```text
source_object
  └── document_version
        ├── page
        │     ├── element
        │     ├── visual_asset
        │     ├── table
        │     │     └── table_cell
        │     └── quality_issue
        ├── retrieval_unit
        ├── extracted_fact
        │     └── fact_evidence
        └── document_relation
```

Important separations:

* `element` is what the parser observed.
* `fact` is an interpretation of one or more elements.
* `retrieval_unit` is a search-oriented projection.
* `summary` is generated text and must never be the only evidence for a fact.

## 3.2 Specification fact schema

Use typed schemas rather than arbitrary key-value JSON:

```json
{
  "fact_id": "fact:...",
  "subject": {
    "manufacturer": "Example Fence",
    "brand": "Example",
    "product_family": "Privacy 6",
    "part_number": "PST-5X5-150",
    "component_type": "post",
    "structural_role": "line_post"
  },
  "attribute": "wall_thickness",
  "value": {
    "raw_lexeme": ".150 in nominal",
    "numeric_decimal": "0.150",
    "numeric_fraction": null,
    "unit_original": "in",
    "unit_normalized": "in",
    "si_value_decimal": "0.003810",
    "si_unit": "m",
    "qualifier": "nominal",
    "range": null,
    "tolerance": null
  },
  "conditions": {
    "fence_height": {
      "raw_lexeme": "up to 6 ft",
      "max_value": "6",
      "unit": "ft"
    },
    "installation_type": "embedded_post",
    "jurisdiction": null
  },
  "evidence": [
    {
      "document_version_id": "docver:...",
      "physical_page_index": 16,
      "printed_page_number": "14",
      "element_id": "element:...",
      "table_id": "table:...",
      "cell_ids": ["cell:r4c3"],
      "bbox": [0.14, 0.32, 0.51, 0.36],
      "exact_quote": "5 x 5 Post — .150 in nominal wall"
    }
  ],
  "extraction": {
    "method": "table_rule_plus_llm_context",
    "parser_version": "...",
    "extractor_version": "...",
    "confidence": 0.97
  },
  "verification_status": "verified",
  "conflict_group_id": null
}
```

Use `Decimal` or rational arithmetic for dimensions. Do not use binary floating point as the canonical value representation.

## 3.3 Unit and dimension handling

Store three representations:

1. Exact raw lexeme.
2. Parsed source-unit value.
3. Deterministically converted value.

For example:

```json
{
  "raw_lexeme": "3/16 in",
  "source_value": {
    "numerator": 3,
    "denominator": 16,
    "unit": "in"
  },
  "decimal_source_value": "0.1875",
  "converted_value": "4.7625",
  "converted_unit": "mm",
  "conversion_exact": true
}
```

Preserve distinctions including:

* nominal versus actual;
* minimum, maximum, typical, and recommended;
* clear spacing versus on-center spacing;
* inside versus outside dimensions;
* width × depth × wall thickness;
* design load versus tested load;
* tolerance versus allowed field adjustment;
* component size versus opening size.

Do not automatically convert wind speed to wind pressure. That conversion depends on standards, exposure, height, geometry, and other assumptions. Store the original wind speed, pressure, test standard, exposure/category, fence height, post spacing, embedment, and anchorage as separate scoped facts.

## 3.4 Table preservation

For each table, store all of the following:

* original page and table crop;
* table bounding box;
* parser-native cell grid;
* row/column spans;
* header hierarchy;
* footnotes;
* Markdown for display;
* HTML for merged-cell fidelity;
* CSV only when the table is genuinely rectangular;
* normalized row objects;
* parser and quality metadata.

Markdown is convenient for retrieval but cannot faithfully represent every merged header or footnote relationship. It should therefore be a projection, not the canonical table representation.

Each table cell should retain:

```json
{
  "row": 4,
  "column": 3,
  "row_span": 1,
  "column_span": 1,
  "text_raw": ".150 nominal",
  "bbox": [0.46, 0.32, 0.58, 0.35],
  "header_path": [
    "Post Profiles",
    "Wall Thickness"
  ]
}
```

When chunking a table, repeat the table title and complete header path with every row or row group.

## 3.5 Installation and assembly order

Do not flatten installation procedures into unordered prose.

Represent steps as an ordered graph:

```json
{
  "procedure_id": "procedure:set-post-and-panel",
  "steps": [
    {
      "step_id": "step:1",
      "ordinal": 1,
      "action": "Set the first post",
      "parts": ["line_post"],
      "requires": [],
      "warnings": ["Verify frost-depth requirement"],
      "figure_refs": ["figure:3"]
    },
    {
      "step_id": "step:2",
      "ordinal": 2,
      "action": "Insert the bottom rail",
      "parts": ["bottom_rail"],
      "requires": ["step:1"],
      "figure_refs": ["figure:4"]
    }
  ]
}
```

Keep warnings, notes, cure times, tool requirements, and referenced figures attached to the corresponding step.

## 3.6 Fact conflicts

Facts should not overwrite one another merely because they share a key.

```text
Fact A:
  post wall thickness = 0.150 in
  source revision = 2023
  product height = 6 ft

Fact B:
  post wall thickness = 0.135 in
  source revision = 2019
  product height = 5 ft
```

These may be versioned or conditional values rather than a true contradiction.

Create conflict groups only after comparing:

* product and part identity;
* revision;
* height or configuration;
* market;
* test standard;
* installation method;
* date;
* authority scope.

Automatic resolution can apply a documented precedence policy, but the losing fact and reasoning must remain visible.

---

# 4. Filtering, cleaning, and chunking

## 4.1 Reversible relevance taxonomy

Use the taxonomy already appropriate for this fence corpus:

```text
core
supporting
mixed
historical
duplicate
irrelevant
uncertain
```

Apply it independently at:

* document level;
* page level;
* element level;
* retrieval-unit level.

Examples:

* A technical installation manual: `core`.
* A brochure with one useful profile table: document `mixed`, profile table `core`, lifestyle text `irrelevant`.
* An old installation manual: `historical`, not irrelevant.
* A warranty paragraph containing approved-installation conditions: `supporting` or `core`.
* A repeated cookie banner: `irrelevant`.
* A low-quality drawing whose purpose is unclear: `uncertain`.

Every exclusion should record:

```json
{
  "classification": "irrelevant",
  "reason_code": "repeated_web_navigation",
  "classifier": "deterministic_site_template",
  "confidence": 0.999,
  "reversible": true
}
```

## 4.2 Cleaning heuristics

Use deterministic rules first:

* repeated header/footer strings across pages;
* recurring website navigation DOM subtrees;
* cookie banners;
* social-sharing components;
* repeated distributor contact blocks;
* empty or decorative elements;
* identical boilerplate across a domain.

Be conservative with:

* warranty limitations;
* regulatory language;
* warnings;
* code-compliance notes;
* “not recommended for” statements;
* maintenance restrictions;
* installation exclusions;
* tested-configuration language.

These often look legal or promotional but materially constrain safe use.

An LLM relevance classifier may handle ambiguous mixed sections, but it should output a label, reason, and confidence—not rewrite or delete the source.

## 4.3 Hierarchical parent-child chunking

Use a hierarchy rather than one universal token splitter:

```text
Document parent
  └── Section parent
        ├── Specification block
        ├── Table row group
        ├── Procedure-step group
        ├── Warning / constraint block
        ├── Figure + callouts
        ├── FAQ pair
        └── Pricing row group
```

The leaf unit is retrieved first. The parent is then expanded to restore context.

### Specification chunks

Keep together:

* component or assembly identity;
* attribute name;
* value and units;
* qualifiers;
* conditions;
* nearby table headers;
* source page.

Do not place specifications for several unrelated part families into one chunk merely because they fit within a token limit.

### Procedure chunks

Group a small coherent sequence of steps, including:

* prerequisites;
* ordered steps;
* warnings;
* referenced parts;
* referenced figures.

Do not split a warning from the step it governs.

### Table chunks

Chunk by complete rows or logical row groups. Include:

* table title;
* all applicable column and super-column headers;
* units;
* footnotes;
* product-family context;
* page and table identifiers.

### Visual chunks

A visual retrieval unit should contain:

* page or figure image reference;
* caption;
* nearby explanatory text;
* extracted callouts;
* component/assembly metadata;
* page and bounding box;
* optional visual embedding.

### Chunk metadata

A practical metadata header is:

```yaml
document_version_id: docver:...
document_family_id: family:...
manufacturer: Example Fence
brand: Example
product_family: Privacy 6
part_numbers:
  - PST-5X5-150
structural_roles:
  - line_post
document_type: technical_cut_sheet
revision: R4
revision_status: current
market:
  - US
language: en
unit_systems:
  - imperial
page_start: 14
page_end: 14
section_path:
  - Structural Components
  - Post Profiles
retrieval_unit_type: table_row_group
canonical_status: canonical_for_market
source_authority: manufacturer
quality_status: passed
```

Do not inject uncertain LLM-inferred metadata as if it were authoritative. Store inferred metadata separately with evidence and confidence.

## 4.4 Retrieval should be multi-path

For an exact specification query, retrieval should be:

```text
Query understanding
  ├── identify manufacturer/product/part filters
  ├── identify requested attribute and unit
  └── identify market/revision constraints
        │
        ▼
Structured fact lookup
        +
Exact lexical search
  - part numbers
  - dimensions
  - standard names
  - section titles
        +
Dense semantic retrieval
  - synonyms
  - descriptive questions
        │
        ▼
Fusion / reranking
        │
        ▼
Parent expansion + source-page evidence
```

Embeddings alone are weak protection for exact identifiers and measurements. The fact store and lexical index should be queried before or alongside dense retrieval.

The answer layer should receive an evidence package such as:

```json
{
  "verified_facts": [],
  "conflicting_facts": [],
  "supporting_chunks": [],
  "table_crops": [],
  "page_images": [],
  "source_documents": []
}
```

The generation model should not need to reconstruct exact dimensions from semantically similar prose when a structured fact exists.

---

# 5. Storage and indexing

## 5.1 Recommended reference deployment

### Object storage

Use S3-compatible object storage such as MinIO for:

* original files;
* OCR derivatives;
* page renders;
* figure and table crops;
* parser JSON;
* Markdown exports;
* SVG/vector extractions;
* model inputs/outputs.

Use content-addressed paths where practical.

### PostgreSQL as system of record

Use PostgreSQL for:

* source and document registries;
* version and duplicate relationships;
* structured metadata;
* elements and evidence spans;
* products/components;
* typed facts;
* quality issues;
* review states;
* retrieval-unit metadata.

PostgreSQL’s JSONB can be GIN-indexed for flexible metadata, and its full-text facilities can support lexical search. pgvector adds vector search with HNSW and IVFFlat index choices. ([PostgreSQL][11])

A practical table set is:

```text
source_objects
document_families
document_versions
document_relations
pages
elements
visual_assets
tables
table_cells
products
components
facts
fact_evidence
fact_conflicts
procedures
procedure_steps
retrieval_units
embeddings
quality_issues
pipeline_runs
review_decisions
```

### Vector layout

Keep embeddings separate from facts:

```sql
retrieval_units
---------------
unit_id
parent_unit_id
document_version_id
unit_type
text
metadata_jsonb
quality_status
canonical_status

embeddings
----------
unit_id
embedding_model
embedding_version
modality
vector
created_at
```

This permits re-embedding without rewriting content.

Useful indexed filter fields include:

* manufacturer;
* brand;
* product family;
* part number;
* structural role;
* document type;
* revision status;
* market;
* language;
* source authority;
* unit system;
* canonical status;
* retrieval-unit type;
* quality status.

### Qdrant scale-out option

Use Qdrant when you need:

* millions of retrieval units;
* multiple named vectors per unit;
* separate text and image vectors;
* dense, sparse, and late-interaction retrieval;
* aggressive low-latency metadata filtering.

Qdrant supports payload filtering and indexes, named vectors, and hybrid queries that fuse dense and sparse results using methods such as reciprocal-rank fusion. ([Qdrant][12])

Even then, keep PostgreSQL as the authoritative metadata and fact store. The vector database should contain retrieval projections, not the only copy of provenance.

## 5.2 Recommendation for your current corpus

Given that your existing pipeline already preserves pages, elements, figures, drawings, tables, assets, retrieval units, and provenance-bearing facts, do **not** replace it with a generic vector-database ingestion framework.

For the present corpus size, a standalone distributed vector database is not the first bottleneck. Continue with:

* SQLite FTS5 or PostgreSQL full-text search for exact retrieval;
* PostgreSQL for the durable production model;
* pgvector when dense retrieval is introduced;
* a visual index only after page/figure retrieval has a measurable evaluation set.

The major value lies in evidence quality, exact retrieval, visual table/drawing interpretation, and revision/conflict handling—not in embedding everything sooner.

---

# 6. Recommended production stack

| Concern                 | Recommended default                             | Escalation or alternative                                 |
| ----------------------- | ----------------------------------------------- | --------------------------------------------------------- |
| Pipeline language       | Python with typed Pydantic models               | Rust worker for high-throughput probing if later required |
| Orchestration           | Dagster for asset-oriented lineage              | Prefect for a lighter Python-first workflow               |
| Raw storage             | MinIO / S3-compatible object store              | Cloud S3 when permitted                                   |
| Metadata and facts      | PostgreSQL                                      | None; keep this authoritative                             |
| Lexical retrieval       | PostgreSQL FTS or current SQLite FTS5           | OpenSearch/Elasticsearch only at larger search scale      |
| Dense retrieval         | pgvector                                        | Qdrant for multi-vector or high-scale workloads           |
| Primary document parser | Docling                                         | Unstructured as secondary adapter                         |
| PDF forensic extraction | PyMuPDF                                         | pdfplumber as an additional table comparator              |
| OCR                     | OCRmyPDF + Tesseract                            | PaddleOCR PP-StructureV3 for difficult pages              |
| Cloud exception parser  | None by default                                 | LlamaParse where governance permits                       |
| HTML extraction         | Trafilatura + raw DOM parser                    | Site-specific selectors                                   |
| DOCX                    | Docling + direct DOCX/media extraction          | `python-docx` sidecar                                     |
| Exact dedupe            | SHA-256                                         | —                                                         |
| Near dedupe             | `datasketch` MinHash LSH + verifier             | SimHash for fast preliminary filtering                    |
| Image dedupe            | perceptual hash + source image hash             | feature embeddings for altered figures                    |
| Language detection      | fastText language identification                | document-source metadata                                  |
| Cross-lingual alignment | multilingual E5 or LaBSE                        | translation-based verification for exceptions             |
| Schema validation       | Pydantic + custom validators                    | Great Expectations for aggregate pipeline checks          |
| Testing                 | pytest, golden parser fixtures, visual overlays | human review UI for exception pages                       |

Dagster models assets and dependencies explicitly, which suits lineage-heavy document pipelines. Prefect provides tracked task states, retries, caching, and concurrency with less framework structure. ([Dagster Docs][13])

---

# 7. Step-by-step implementation plan

## Phase 0: define the gold pilot

Select approximately ten documents covering:

* native technical PDF;
* scanned approval or technical sheet;
* mixed native/scanned manual;
* drawing-heavy document;
* complex table;
* HTML product page;
* DOCX;
* duplicate/revision pair;
* cross-language pair;
* marketing-heavy mixed document.

Create a 30–50-question evaluation set with exact expected evidence:

* exact dimensions;
* tolerance lookup;
* table row lookup;
* drawing-only value;
* installation order;
* exception and warning;
* revision conflict;
* localized variant;
* negative/unanswerable question;
* ambiguous product-family query.

Do not optimize parser settings or embeddings against vague “looks good” inspection. Measure against this set.

## Phase 1: implement immutable intake and manifests

Deliverables:

* source-object registry;
* SHA-256 storage;
* source URL aliases;
* raw object store;
* pipeline-run records;
* idempotent reprocessing;
* parser/config version recording.

Acceptance condition: rerunning ingestion produces no new logical objects unless source bytes or configuration changed.

## Phase 2: build the page probe and parser router

Implement page-level metrics and routing.

Deliverables:

* PDF page probe;
* native/scanned/mixed classification;
* Docling primary parse;
* PyMuPDF sidecar;
* OCR derivative pipeline;
* PaddleOCR escalation;
* page renders and drawing-region extraction.

Acceptance condition: every page has a documented route, parser result, quality status, and preserved visual representation.

## Phase 3: establish the canonical evidence graph

Normalize parser outputs into your own stable schema rather than exposing application code directly to parser-specific models.

Deliverables:

* documents, pages, elements, tables, cells, figures, drawings;
* page and bounding-box provenance;
* raw and normalized text;
* parent/child hierarchy;
* parser-native payload retained as JSON;
* physical and printed page numbers.

Acceptance condition: clicking any element or table cell can locate it on the original rendered page.

## Phase 4: quality gates and exception processing

Implement:

* numeric-token coverage;
* cross-parser comparison;
* OCR-risk patterns;
* table topology validation;
* missing-figure detection;
* visual bounding-box overlay generation;
* review queue.

Acceptance condition: no page containing unresolved numeric disagreement is marked production-ready.

## Phase 5: document families, deduplication, and versions

Implement:

* exact byte dedupe;
* canonical-text/page hashes;
* MinHash candidate index;
* page/section alignment;
* image/table signatures;
* document relationship classifier;
* canonical ranking;
* body-derived revision status.

Acceptance condition: the system distinguishes exact duplicates, reformatted copies, translations, localized variants, and superseding revisions.

## Phase 6: reversible relevance classification

Implement document/page/element labels:

```text
core | supporting | mixed | historical | duplicate | irrelevant | uncertain
```

Deliverables:

* deterministic site-boilerplate signatures;
* domain-specific technical lexicon;
* LLM classifier for ambiguous elements;
* reason codes;
* confidence;
* reversible index inclusion.

Acceptance condition: excluded material remains queryable through an audit path, and every exclusion has a reason.

## Phase 7: structured fact extraction

Begin with high-value schemas:

1. Product identity and part numbers.
2. Post, rail, picket, slat, cap, bracket, and hardware dimensions.
3. Wall thickness.
4. Spacing and tolerances.
5. Fence and panel heights.
6. Post embedment and footing requirements.
7. Installation order and dependencies.
8. Wind/load ratings with conditions.
9. Fastener types and quantities.
10. Compatibility and exclusion rules.

Extraction strategy:

```text
deterministic patterns
        +
table/header interpretation
        +
LLM context binding
        +
evidence-span validation
        +
unit parser and deterministic conversion
```

A fact is promoted to `verified` only when:

* its raw lexeme exists in the linked evidence;
* subject/component context is identifiable;
* unit parsing succeeds;
* conditions are preserved;
* no unresolved parser conflict exists.

## Phase 8: hierarchical chunks and retrieval

Generate typed retrieval units, not generic 500-token slices.

Implement:

* section parents;
* specification leaves;
* procedure groups;
* table row groups;
* warning blocks;
* figure/callout units;
* fact cards;
* parent expansion.

Start with lexical and structured retrieval. Add dense embeddings afterward and evaluate the incremental recall.

## Phase 9: retrieval and answer evaluation

Measure separately:

### Parsing

* numeric-token recall;
* unit exactness;
* table cell accuracy;
* reading-order accuracy;
* figure/caption association;
* provenance completeness.

### Deduplication

* candidate recall;
* relationship-classification precision;
* canonical-selection correctness.

### Fact extraction

* exact value match;
* unit match;
* qualifier match;
* condition binding;
* source-link correctness;
* conflict detection.

### Retrieval

* Recall@k for exact specifications;
* table-row recall;
* drawing-page recall;
* revision-aware recall;
* negative-question abstention;
* conflict retrieval rate.

### Answer generation

* unsupported-claim rate;
* exact numeric accuracy;
* citation/page correctness;
* whether conflicts and uncertainty are disclosed;
* whether the answer used the correct product and market.

## Phase 10: production hardening

Add:

* incremental crawl ingestion;
* source-change detection;
* parser regression tests;
* reprocessing by parser/config version;
* concurrency and retry policies;
* dead-letter queues;
* observability dashboards;
* review workflows;
* backup and object-retention policies;
* API/MCP endpoints for facts, search, evidence, and document inspection.

---

# 8. Critical pitfalls and controls

| Pitfall                                        | Required control                                                           |
| ---------------------------------------------- | -------------------------------------------------------------------------- |
| OCR reads `1/8` as `118`                       | Fraction-aware parser, risky-token detection, crop re-OCR, visual evidence |
| `O` versus `0`, `I` versus `1` in part numbers | Part-number dictionaries, checksum/pattern validation, exact page crop     |
| Prime symbols lost from feet/inches            | Preserve raw Unicode and ASCII variants; parse contextual patterns         |
| `1-1/2"` interpreted as `11/2"`                | Domain grammar for mixed fractions                                         |
| Decimal point disappears from `.150`           | Cross-parser numeric comparison and plausibility checks                    |
| Metric conversion introduces rounding          | Store exact source value and deterministic Decimal conversion              |
| Nominal and actual values merged               | Explicit qualifier field                                                   |
| `O.C.` spacing confused with clear gap         | Typed measurement semantics                                                |
| Table row detached from headers                | Canonical cell grid and repeated header path in chunks                     |
| Merged table headers flattened incorrectly     | Store HTML/cell spans and table image, not Markdown alone                  |
| Table continues across pages                   | Multi-page table identity and repeated-header recognition                  |
| Drawing callout detached from component        | Preserve text/target bounding boxes and drawing crop                       |
| Warning separated from installation step       | Procedure graph and bounded step groups                                    |
| Latest website copy assumed latest revision    | Revision evidence from document body                                       |
| Spanish copy assumed exact translation         | Numeric, table, part-number, figure, and market verification               |
| Historical document deleted as duplicate       | `superseded` relationship and reversible retrieval policy                  |
| Warranty text removed as legal boilerplate     | Technical-restriction classifier                                           |
| Marketing brochure fully discarded             | Element-level filtering; retain product identity and technical tables      |
| Wind speed converted directly to pressure      | Preserve standard, exposure, height, spacing, and anchorage context        |
| Dense retrieval misses exact dimensions        | Structured fact and lexical retrieval in parallel                          |
| LLM invents normalized value                   | Recompute normalization deterministically from raw evidence                |
| Generated summary becomes “source”             | Summaries remain derived retrieval aids only                               |
| Conflicting sources silently merged            | Conflict groups and explicit authority/version policy                      |
| Price from an old guide appears current        | Separate price facts with currency, market, and effective date             |
| Regional approval treated as universal         | `authority_scope`, jurisdiction, and tested-configuration metadata         |

---

# Recommended priority for the existing fence pipeline

Because the current implementation already preserves the corpus, pages, elements, figures, drawings, tables, assets, retrieval units, and provenance-bearing facts, the next work should be ordered as follows:

1. **Unit-granularity retrieval:** independently retrieve fact cards, table rows, procedure groups, figures, and parent sections.
2. **Visual interpretation of high-value drawings and approval tables:** especially drawing-only dimensions and configuration tables, with evidence-box validation.
3. **Document-body revision and canonical status:** reliably distinguish current, historical, translated, localized, and superseded material.
4. **Expanded gold evaluation:** include negative questions, conflicting revisions, similar product families, and drawing-only answers.
5. **Structured fact coverage:** wall thickness, rail profiles, spacing, tolerances, hardware, assembly order, and conditional load configurations.
6. **Hybrid dense retrieval:** add only after exact lexical and fact retrieval are measurable and correct.
7. **Visual page retrieval:** add after the drawing-heavy evaluation set is established.
8. **Agent API/MCP:** expose separate operations for structured fact lookup, document search, evidence retrieval, conflict inspection, and source-page rendering.

The resulting system should behave less like a conventional “PDF-to-vectors” RAG and more like a **versioned, multimodal technical evidence database with RAG projections**. That architecture is what preserves exact engineering specifications while still supporting flexible LLM reasoning.
