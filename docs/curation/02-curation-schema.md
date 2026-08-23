# 2 — Proposed curation schema

All new tables carry a `cur_` prefix. The prefix is the boundary the write guard
enforces, and the guard is a real chokepoint rather than a convention:
`sqlite3.Connection.set_authorizer` (stdlib, present on the 3.45.1 here) denies
`SQLITE_INSERT`, `SQLITE_UPDATE`, `SQLITE_DELETE` and `SQLITE_DROP_TABLE` on any
table not matching `cur_%`. The authorizer must be cleared before any legitimate
canonical write (`store.build_retrieval_units`), and the curation connection
factory installs it unconditionally.

An authorizer is chosen over the convention `paths.ensure_writable` uses because
that convention is already leaky: `extract.py:122` and `extract.py:595` call
`ensure_writable` before a Pillow `save`, but `noa_tables.py:130` saves a PNG
without it and `tools.render_page` shells out to `pdftoppm` with no guard at
all. A rule enforced at each call site is a rule that will be missed at one; an
authorizer installed on the connection cannot be.

Storage: the same `workspace/indexes/evidence.db`, so a claim joins to its
element without a cross-database attach. `store.SCHEMA_VERSION` goes to 2 and
`curation.migrate_curation(conn)` runs alongside `store.migrate` — today
`store.migrate` is `executescript(SCHEMA)` over `CREATE TABLE IF NOT EXISTS`
with no versioned runner, so leaving `schema_meta.schema_version` at 1 on a
database carrying 27 extra tables is not acceptable.

All `cur_*` tables are created in one `executescript`. Several foreign keys are
forward references and two pairs are genuinely circular
(`cur_claims.conflict_group_id ↔ cur_conflicts.winning_claim_id`; `cur_claims →
cur_claim_conditions → cur_claim_evidence → cur_claims`). SQLite resolves FK
targets at DML time, so this is legal — but only because both sides of each
cycle are nullable, and neither may later be made `NOT NULL`.

A test asserts that a full curation run leaves all eleven canonical tables
(`documents`, `document_versions`, `pages`, `elements`, `tables`, `table_cells`,
`assets`, `relations`, `extraction_runs`, `quality_issues`,
`table_read_candidates`) and `facts` byte-identical.

---

## 2.0 Controlled vocabularies

Every vocabulary is a row in `cur_vocab`, referenced by a composite foreign key,
**not** a `CHECK` constraint. SQLite has no `ALTER TABLE … DROP CONSTRAINT`, so
changing a CHECK means the twelve-step table rebuild with FKs disabled — on
tables that all have inbound FKs. That rebuild will be skipped, and then the
vocabulary is a comment. A table can be edited.

```sql
CREATE TABLE cur_vocab (
  kind   TEXT NOT NULL,
  value  TEXT NOT NULL,
  rank   INTEGER,          -- ordering where the vocabulary is ordered
  label  TEXT,
  PRIMARY KEY (kind, value)
) WITHOUT ROWID;
```

Columns bind to it by carrying a constant discriminator, e.g.

```sql
authority_kind  TEXT NOT NULL DEFAULT 'authority_level',
authority_level TEXT NOT NULL,
FOREIGN KEY (authority_kind, authority_level) REFERENCES cur_vocab(kind, value)
```

Row-level invariants that do **not** need a subquery stay as `CHECK`
constraints, listed per table below. Cross-table invariants are triggers
(§2.5.4); `CHECK` cannot contain a subquery — verified, SQLite raises
*"subqueries prohibited in CHECK constraints"*.

### Source authority (`kind='authority_level'`)

| `rank` | `value` | Slice example |
|---|---|---|
| 100 | `regulatory_approval` | Miami-Dade NOA body and its PE-sealed drawing sheets |
| 90 | `pe_sealed_engineering` | standalone PE letter |
| 80 | `standard_body` | ASTM, ASCE 7, CLFMI |
| 70 | `manufacturer_current_technical` | `bufftech-fence-installation-guide-2024.pdf` |
| 60 | `manufacturer_current_marketing` | current catalog |
| 50 | `manufacturer_legacy_technical` | `bufftech-installation-guide-40-40-70743.pdf` |
| 40 | `manufacturer_legacy_marketing` | `bufftech-catalog-brochure-2009.pdf` |
| 30 | `distributor` | dealer sheets |
| 20 | `curated_dataset` | `data/structural/*.json` — **carries four verified errors, see G16** |
| 10 | `inferred` | produced by curation with no single source sentence |

The rank lives in `cur_vocab.rank` because `ORDER BY authority_level` sorts
alphabetically and would put `curated_dataset` above `regulatory_approval`. Rank
orders a conflict for presentation. It never resolves one silently and it never
promotes a claim.

### Claim status (`kind='claim_status'`)

```text
candidate    default on creation; never returned as an answer
in_review    assigned to a reviewer
accepted     a reviewer agreed; the only status the projection may read
rejected     a reviewer disagreed; retained with the reason
needs_source evidence insufficient to decide; retained
blocked      depends on an unresolved conflict or an unbound subject
superseded   replaced by a later claim; retained and still addressable
```

Nothing is deleted. `rejected` and `superseded` claims stay queryable, which is
what makes the layer reversible.

### Review classes (`kind='review_class'`) — mandatory review

A claim whose `review_class` is one of these **cannot** reach `accepted` without
a `cur_reviews` row where `reviewer_kind='human'` and `decision='accept'`:

```text
dimension  tolerance  wind_condition  footing  spacing
compatibility  version_status  low_confidence_ocr
```

`low_confidence_ocr` is computed, not declared: set when any evidence element
has `ocr_confidence < 80`, or its page has `ocr_mean_confidence < 80`, or its
page carries a `table_not_reconstructed` or `mojibake_text_layer` issue. **On
the slice that rule covers 113 of 522 pages** — not the 66 that carry
`table_not_reconstructed` alone.

`review_mandatory` is a generated column, so it cannot drift from
`review_class`:

```sql
review_mandatory INTEGER GENERATED ALWAYS AS (
  review_class IN ('dimension','tolerance','wind_condition','footing',
                   'spacing','compatibility','version_status','low_confidence_ocr')
) VIRTUAL
```

VIRTUAL, not STORED: `ALTER TABLE` cannot add a STORED generated column later,
and VIRTUAL is still indexable.

### Attributes (`kind='attribute'`), and the migration mapping

`attribute` is a controlled vocabulary, not free text, because doc 1 enumerates
it and because the migration in doc 4 has to map onto it deterministically:

```text
footing_depth  footing_diameter  embedment_depth  post_spacing_max
wall_thickness  panel_width  panel_height  post_size  component_dimension
reinforcement_required  fastener_spec  quantity_per_unit  cure_time
racking_degrees  slope_method  wind_speed_design  exposure_category
approval_scope  tested_configuration  effective_date  expiration_date
use_restriction
```

| `facts.fact_type` | → `attribute` |
|---|---|
| `footing_depth_in` | `footing_depth` |
| `footing_diameter_in` | `footing_diameter` |
| `depth_below_grade_in` | `embedment_depth` |
| `post_spacing_in` | `post_spacing_max` |
| `wind_speed_mph` | `wind_speed_design` |
| `exposure_category` | `exposure_category` |
| `racking_degrees` | `racking_degrees` |
| `reinforcement` | `reinforcement_required` |
| `approval_id` | `approval_scope` |
| `effective_date` / `expiration_date` | same |

Doc 1 previously used `post_spacing` and `post_spacing_max` for one thing; the
vocabulary has one name.

### Condition dimensions (`kind='condition_dimension'`)

```text
fence_height        panel_width        post_size          structural_role
exposure_category   wind_speed_mph     hvhz_applicability soil_type
code_edition        jurisdiction       market             installation_method
slope_condition     gate_leaf_width    frost_depth_basis  temperature
```

### Confidence basis (`kind='confidence_basis'`)

```text
two_reader_agreement  single_reader  native_text_layer  regex_match
ocr_above_threshold   ocr_below_threshold  inferred
```

`confidence_value` is a fixed-scale decimal string (`GLOB
'[0-9].[0-9][0-9][0-9][0-9]'`), never a float column. It is a reported property
of the reading method. It is never a promotion threshold — no number promotes a
claim in a mandatory class.

### Lifecycle statuses for everything that is not a claim

This section's rule is that every vocabulary is a `cur_vocab` row, so these are
listed rather than left as untyped `TEXT`:

| `kind` | Table(s) carrying it | Values |
|---|---|---|
| `curation_status` | `cur_document_dossiers`, `cur_page_maps` | `pending` · `in_progress` · `complete` · `blocked` |
| `entity_status` | `cur_entities` | `proposed` · `accepted` · `rejected` · `merged` |
| `alias_status` | `cur_entity_aliases` | `candidate` · `accepted` · `rejected` |
| `relation_status` | `cur_entity_relations` | `candidate` · `in_review` · `accepted` · `rejected` · `needs_source` · `blocked` |
| `grid_status` | `cur_table_readings`, `cur_table_annotations` | `read` · `in_review` · `reviewed` · `rejected` |
| `procedure_status` | `cur_procedures`, `cur_procedure_steps` | `candidate` · `in_review` · `accepted` · `rejected` |
| `conflict_resolution` | `cur_conflicts` | `unresolved` · `resolved_by_authority` · `resolved_by_version` · `resolved_by_review` · `not_a_conflict` |

`grid_status='reviewed'` is the token acceptance criterion F3 counts, so it has
to be a defined value rather than a convention.

### Revision status, and its mapping to what already exists

Three vocabularies describe one idea and they must be mapped, not merged:

| Layer | Values | Where |
|---|---|---|
| dossier `revision_status` | `current` · `superseded` · `historical` · `unknown` | `cur_document_dossiers` |
| canonical `documents.version_status` | `active` · `superseded` · `unknown` | `store.py:44` (3 / 9 / 132 today) |
| resolver verdict | `in_force` · `expired` · `unknown` | `retrieval.resolve_document_version` |

`current` ≡ `active`. The dossier records the stored value it disagreed with
(§2.2) so the disagreement is data, not prose.

---

## 2.1 Run provenance and idempotency

```sql
CREATE TABLE cur_runs (
  run_id            TEXT PRIMARY KEY,   -- content-addressed, see below
  started_at        TEXT NOT NULL,
  finished_at       TEXT,
  stage             TEXT NOT NULL,      -- vocabulary: schema|probe|entity|dossier|
                                        -- pagemap|migrate|backfill|read|procedure|
                                        -- conflict|bundle|audit
  code_commit       TEXT NOT NULL,
  config_hash       TEXT NOT NULL,
  tool_versions     TEXT NOT NULL,      -- JSON
  tool_fingerprint  TEXT NOT NULL,      -- as extraction_runs.tool_fingerprint
  scope             TEXT NOT NULL,      -- canonical JSON of the document_ids in scope
  notes             TEXT
);
```

**`run_id` is derived, not generated:**

```text
run_id = 'cur-' + sha256(stage | code_commit | config_hash |
                         json.dumps(scope, sort_keys=True))[:16]
```

`store.start_run` (`store.py:287`) builds a wall-clock id; copying that here
would make every row differ on a re-run and the idempotency claim would be void.
With a derived id, a re-run with unchanged inputs re-uses the same run row.

**Every `cur_*` table carries `run_id NOT NULL REFERENCES cur_runs(run_id)`** —
including `cur_entity_aliases`, `cur_claim_conditions`, `cur_claim_evidence`,
`cur_conflicts` and `cur_procedure_steps`.

**Every id is content-addressed**, matching `ids.py`, which has no counter and
no uuid anywhere:

```text
dossier_id    = 'dos-'   + sha256(version_id)[:16]
page_map_id   = 'pm-'    + sha256(page_id)[:16]
entity_id     = 'ent-'   + sha256(entity_type | canonical_name)[:16]
alias_id      = 'alias-' + sha256(entity_id | alias | alias_kind)[:16]
relation_id   = 'rel-'   + sha256(from | to | relation_type | method)[:16]
claim_id      = 'claim-' + sha256(version_id | page_no | element_id |
                                  attribute | value_raw_lexeme |
                                  condition_signature)[:16]
condition_id  = 'cond-'  + sha256(claim_id | dimension)[:16]
evidence_id   = 'ev-'    + sha256(claim_id | crop_sha256 | region_key)[:16]
```

`condition_signature` and every JSON blob that feeds a hash use `json.dumps(...,
sort_keys=True, separators=(',',':'))`, the precedent set by
`store.tool_fingerprint` (`store.py:279`).

**The idempotency contract, stated exactly.** A re-run with unchanged inputs and
unchanged `config_hash` produces rows identical on every column *except* the
wall-clock ones: `cur_runs.started_at`/`finished_at`, `created_at`,
`reviewed_at`, `resolved_at`, `generated_at`. That is the same contract Phase 5
meets — `tests/test_idempotency.py:49-60` also compares an explicit column list
and deliberately excludes `built_at`.

---

## 2.2 Document dossiers (requirement 2)

One row per `document_version`, enforced by `UNIQUE(version_id)`.

```sql
CREATE TABLE cur_document_dossiers (
  dossier_id              TEXT PRIMARY KEY,
  document_id             TEXT NOT NULL REFERENCES documents(document_id),
  version_id              TEXT NOT NULL UNIQUE REFERENCES document_versions(version_id),
  sha256                  TEXT NOT NULL,
  run_id                  TEXT NOT NULL REFERENCES cur_runs(run_id),

  issuing_org_entity_id   TEXT REFERENCES cur_entities(entity_id),
  brand_entity_id         TEXT REFERENCES cur_entities(entity_id),
  document_role           TEXT NOT NULL,   -- install_manual|gate_manual|catalog|
                                           -- approval|warranty|spec_sheet|drawing_set
  authority_level         TEXT NOT NULL,
  authority_basis         TEXT NOT NULL,
  authority_evidence_id   TEXT REFERENCES elements(element_id),

  jurisdiction            TEXT,
  market                  TEXT,
  language                TEXT NOT NULL,
  revision_status         TEXT NOT NULL,   -- current|superseded|historical|unknown
  revision_basis          TEXT NOT NULL,   -- document_body|approval_chain|unknown
  revision_evidence_id    TEXT REFERENCES elements(element_id),
  revision_quote          TEXT,            -- verbatim substring of that element
  stored_version_status   TEXT NOT NULL,   -- documents.version_status at curation time
  disagrees_with_stored   INTEGER NOT NULL,
  effective_claim_id      TEXT REFERENCES cur_claims(claim_id),
  expires_claim_id        TEXT REFERENCES cur_claims(claim_id),

  duplicate_group_id      TEXT,            -- byte-identical group; from relations
  canonical_for_duplicate_group INTEGER NOT NULL DEFAULT 0,
  duplicate_basis         TEXT,
  approval_lineage_id     TEXT,            -- the supersession lineage, if any

  coverage                TEXT NOT NULL,   -- JSON: page counts per content class
  known_defects           TEXT NOT NULL,   -- JSON: quality_issue kinds and counts
  curation_status         TEXT NOT NULL,
  curator TEXT, reviewed_at TEXT, notes TEXT,

  CHECK (revision_status <> 'current' OR revision_basis = 'document_body'),
  CHECK (disagrees_with_stored IN (0,1)),
  CHECK (canonical_for_duplicate_group IN (0,1))
);
```

Three deliberate decisions:

- **`duplicate_group_id`, not `document_family_id`.** Prohibition 5 forbids
merging superseded and active documents into one source record. A field called
"family" invites a curator to group the five NOA generations and then mark one
`canonical`, demoting four current source records — the prohibited merge, and a
1-per-group check would not notice. `duplicate_group_id` means *byte-identical
only*, and a criterion asserts no two documents with different `sha256` share
one. The supersession lineage is `approval_lineage_id`, which has no canonical
member.
- **`revision_quote`, not just an element id.** Requiring "an element_id" is
passed by citing a cover-page title that repeats the filename. The quote must be
a verbatim substring of the cited element's `text`/`ocr_text` and must *not* be
a substring of the filename or `documents.title`.
- **`disagrees_with_stored` is a column.** `documents.version_status` says
NOA 23-0314.05 is `superseded` while the resolver reads it `in_force`, and all
four filings of 24-0117.05 are `unknown`. That disagreement is queryable, not
narrated.

`duplicate_group_id` and `approval_lineage_id` are *derived from* the canonical
`relations` edges (38 `same_content_as`, 24 `supersedes`) rather than
re-asserted, and a test checks they agree — including the direction trap
CLAUDE.md warns about, where a `superseded_by` edge's *from* side is the
superseded one.

---

## 2.3 Page content maps (requirement 2)

```sql
CREATE TABLE cur_page_maps (
  page_map_id        TEXT PRIMARY KEY,
  page_id            TEXT NOT NULL UNIQUE REFERENCES pages(page_id),
  document_id        TEXT NOT NULL REFERENCES documents(document_id),
  page_no            INTEGER NOT NULL,
  run_id             TEXT NOT NULL REFERENCES cur_runs(run_id),

  has_reviewable_table INTEGER NOT NULL DEFAULT 0,
  table_kind         TEXT,
  flag_disposition   TEXT,           -- confirmed | false_positive_cross_reference |
                                     -- false_positive_index_sheet | not_flagged
  drawing_present    INTEGER NOT NULL DEFAULT 0,
  ocr_risk           TEXT NOT NULL,  -- none|low|medium|high
  ocr_risk_basis     TEXT NOT NULL,
  derived_from_page_map_id TEXT REFERENCES cur_page_maps(page_map_id),
                                     -- set when copied from a byte-identical twin
  curation_status    TEXT NOT NULL,
  curator TEXT, reviewed_at TEXT, notes TEXT,
  CHECK (has_reviewable_table IN (0,1)), CHECK (drawing_present IN (0,1))
);

CREATE TABLE cur_page_map_classes (
  page_map_id   TEXT NOT NULL REFERENCES cur_page_maps(page_map_id),
  content_class TEXT NOT NULL,
  PRIMARY KEY (page_map_id, content_class)
) WITHOUT ROWID;

CREATE TABLE cur_page_map_entities (
  page_map_id TEXT NOT NULL REFERENCES cur_page_maps(page_map_id),
  entity_id   TEXT NOT NULL REFERENCES cur_entities(entity_id),
  PRIMARY KEY (page_map_id, entity_id)
) WITHOUT ROWID;
```

Content classes are a child table rather than a JSON array because the page
queue filters on them ("every `wind_exposure_footing_table` page"), and because
a JSON array cannot be constrained — `CHECK (NOT EXISTS (SELECT … json_each …))`
is rejected by SQLite. The same argument this document makes for conditions in
§2.5 applies here.

Content-class vocabulary (`kind='content_class'`):

```text
cover  toc  marketing  product_gallery  colour_chart  component_diagram
dimension_table  sku_table  spacing_table  wind_exposure_footing_table
bill_of_materials_table  procedure_steps  warning_block  tools_materials
warranty_terms  approval_cover  approval_conditions  pe_seal  drawing_sheet
index_sheet  contact_boilerplate  blank  unreadable
```

`page_image_path` is **not** copied here. It is read through
`pages.page_image_path`; denormalizing it would desynchronize the moment a page
is re-rendered at another dpi.

`flag_disposition` is typed because the seven known false-positive
`table_not_reconstructed` pages are not one thing: five are cross-references
(`SEE TABLE 1 ON SHEET n` above a drawing) and two are index sheets carrying
**per-model maximum post-spacing labels** — real CAP-6 data that must not be
reclassified away as decoration.

---

## 2.4 Domain entities, aliases, relations (requirement 3)

```sql
CREATE TABLE cur_entities (
  entity_id        TEXT PRIMARY KEY,
  entity_type      TEXT NOT NULL,   -- manufacturer|brand|product_line|product_style|
                                    -- configuration|component|material|hardware|
                                    -- fastener|approval|authority|jurisdiction|standard
  canonical_name   TEXT NOT NULL,
  structural_role  TEXT,            -- line_post|end_post|corner_post|gate_post|
                                    -- blank_post|top_rail|bottom_rail|picket|
                                    -- cap|bracket|insert|reinforcement
  parent_entity_id TEXT REFERENCES cur_entities(entity_id),
  attributes       TEXT NOT NULL DEFAULT '{}',  -- JSON, non-authoritative
  status           TEXT NOT NULL,   -- proposed|accepted|rejected|merged
  merged_into      TEXT REFERENCES cur_entities(entity_id),
  run_id           TEXT NOT NULL REFERENCES cur_runs(run_id),
  curator TEXT, reviewed_at TEXT,
  UNIQUE(entity_type, canonical_name)
);

CREATE TABLE cur_entity_aliases (
  alias_id      TEXT PRIMARY KEY,
  entity_id     TEXT NOT NULL REFERENCES cur_entities(entity_id),
  alias         TEXT NOT NULL,
  alias_kind    TEXT NOT NULL,   -- observed_in_source|catalog_spelling|sku|
                                 -- legacy_brand|abbreviation|ocr_variant|curator_label
  document_id   TEXT REFERENCES documents(document_id),
  element_id    TEXT REFERENCES elements(element_id),
  page_no       INTEGER,
  status        TEXT NOT NULL,   -- candidate|accepted|rejected
  run_id        TEXT NOT NULL REFERENCES cur_runs(run_id),
  UNIQUE(entity_id, alias, alias_kind),
  CHECK (element_id IS NOT NULL OR alias_kind = 'curator_label'),
  CHECK (status <> 'accepted' OR element_id IS NOT NULL)
);

CREATE TABLE cur_entity_relations (
  relation_id      TEXT PRIMARY KEY,
  from_entity_id   TEXT NOT NULL REFERENCES cur_entities(entity_id),
  to_entity_id     TEXT NOT NULL REFERENCES cur_entities(entity_id),
  relation_type    TEXT NOT NULL,
  method           TEXT,          -- for attaches_to: routed|bracketed|screwed|snap
  authority_level  TEXT NOT NULL,
  confidence_basis TEXT NOT NULL,
  review_class     TEXT,          -- 'compatibility' on compat edges → mandatory
  review_mandatory INTEGER GENERATED ALWAYS AS (review_class IS NOT NULL) VIRTUAL,
  status           TEXT NOT NULL, -- candidate|in_review|accepted|rejected|
                                  -- needs_source|blocked
  run_id           TEXT NOT NULL REFERENCES cur_runs(run_id)
);
```

Relation vocabulary:

```text
style_of  variant_of  part_of  fits  attaches_to  requires  excludes
compatible_with  incompatible_with  brand_succeeds  approved_under
issued_by  tested_to  references_standard  supersedes
```

Relation conditions reuse `cur_claim_conditions` keyed on `relation_id`, so
there is one condition model, not two. Relation evidence reuses
`cur_claim_evidence`.

`incompatible_with` is a safety statement and carries
`review_class='compatibility'`. The relation status vocabulary includes
`needs_source` and `blocked` so a reviewer's `needs_source` decision has
somewhere to land.

An alias with no `element_id` must be `curator_label` and can never be
`accepted` — both CHECKs above. That is what stops the seventeen free-text
manufacturer spellings, ten of which name one corporate group, from being
laundered into truth.

*Note on prohibition 9.* `cur_entities` + `cur_entity_relations` is a typed edge
store. It is not a graph database: it is four tables in the existing SQLite
file, queried with joins, with no new service, process, or dependency. It is in
scope for the same reason `relations` already is.

---

## 2.5 Claims (requirements 4, 5, 10)

A claim is a *conditional, sourced, reviewable proposition* — not a fact.

```sql
CREATE TABLE cur_claims (
  claim_id           TEXT PRIMARY KEY,
  run_id             TEXT NOT NULL REFERENCES cur_runs(run_id),

  subject_entity_id  TEXT REFERENCES cur_entities(entity_id),
  subject_text_raw   TEXT NOT NULL,   -- verbatim from source
  subject_binding    TEXT NOT NULL,   -- bound|unbound|ambiguous
  attribute          TEXT NOT NULL,   -- vocabulary, §2.0
  claim_kind         TEXT NOT NULL,   -- measurement|enumeration|boolean|
                                      -- procedure_ref|scope|date|textual_constraint

  value_raw_lexeme   TEXT NOT NULL,   -- '30" deep', '5/8"', '±1/16', '180 mph'
  value_kind         TEXT NOT NULL,   -- scalar|range|fraction|enum|boolean|text
  numeric_num        INTEGER,
  numeric_den        INTEGER,
  value_decimal      TEXT,            -- fixed 4-place decimal string, e.g. '0.6250'
  value_decimal_max  TEXT,
  value_milli        INTEGER,         -- thousandths of unit_norm; the sortable copy
  value_milli_max    INTEGER,
  unit_raw TEXT, unit_norm TEXT, si_decimal TEXT, si_unit TEXT,
  conversion_exact   INTEGER,
  qualifier          TEXT,            -- nominal|actual|min|max|typical|recommended
  tolerance_raw      TEXT,

  authority_level    TEXT NOT NULL,
  jurisdiction TEXT, market TEXT,
  valid_from TEXT, valid_until TEXT,
  validity_basis     TEXT NOT NULL,   -- approval_dates|document_revision|none
  revision_status    TEXT NOT NULL,

  confidence_value   TEXT NOT NULL,
  confidence_basis   TEXT NOT NULL,

  origin             TEXT NOT NULL,   -- regex_fact_migration|table_read_candidate|
                                      -- curator_reading|dossier_derivation|
                                      -- curated_dataset|calculated
  source_fact_key    TEXT,            -- natural key, see below
  source_candidate_key TEXT,          -- natural key, see below
  derived_from_claims TEXT,           -- canonical JSON array, origin='calculated'
  duplicate_of_claim_id TEXT REFERENCES cur_claims(claim_id),

  review_class       TEXT,
  review_mandatory   INTEGER GENERATED ALWAYS AS (...) VIRTUAL,   -- §2.0
  tuple_signature    TEXT NOT NULL,   -- sha256(document_id|attribute|
                                      --        value_raw_lexeme|condition_signature)
  status             TEXT NOT NULL DEFAULT 'candidate',
  conflict_group_id  TEXT REFERENCES cur_conflicts(conflict_group_id),
  superseded_by      TEXT REFERENCES cur_claims(claim_id),
  created_at         TEXT NOT NULL,

  CHECK (status <> 'accepted' OR subject_binding = 'bound'),
  CHECK (conversion_exact IS NULL OR conversion_exact IN (0,1)),
  CHECK (numeric_den IS NULL OR numeric_den <> 0),
  CHECK (confidence_value GLOB '[0-9].[0-9][0-9][0-9][0-9]')
);
```

### 2.5.1 Lineage keyed on natural keys, not rowids

`facts.fact_id` and `table_read_candidates.candidate_id` are `INTEGER PRIMARY
KEY AUTOINCREMENT`. A foreign key onto either **breaks the existing pipeline**,
verified:

- `facts.py` does `DELETE FROM facts` then re-inserts on every `cli facts
--extract`. With `PRAGMA foreign_keys=ON` (`store.py:268`) an inbound FK makes
that DELETE raise `FOREIGN KEY constraint failed`.
- `table_review.load_reading` (`table_review.py:123`) uses `INSERT OR REPLACE`,
whose implicit DELETE fires the same failure.
- Both reassign ids on every re-run, so a surviving FK would silently repoint at
a different row.

So lineage is a natural key, hashed:

```text
source_fact_key      = sha256(document_id|version_id|page_no|element_id|
                              fact_type|value_original)[:16]
source_candidate_key = sha256(document_id|page_no|reader|row_index|col_index)[:16]
```

The second matches the natural key `table_read_candidates` already declares
(`store.py:223`).

### 2.5.2 Conditions as rows, not as a JSON blob

```sql
CREATE TABLE cur_claim_conditions (
  condition_id   TEXT PRIMARY KEY,
  claim_id       TEXT REFERENCES cur_claims(claim_id),
  relation_id    TEXT REFERENCES cur_entity_relations(relation_id),
  dimension      TEXT NOT NULL,
  operator       TEXT NOT NULL,   -- eq|lte|gte|range|in|not_in|unknown
  value_raw      TEXT NOT NULL,   -- 'Up to 48"', 'C', 'HVHZ'
  value_norm     TEXT,
  value_norm_max TEXT,
  value_milli    INTEGER,         -- thousandths of unit_norm; the sortable copy
  value_milli_max INTEGER,
  unit_raw TEXT, unit_norm TEXT,
  evidence_id    TEXT REFERENCES cur_claim_evidence(evidence_id),
  run_id         TEXT NOT NULL REFERENCES cur_runs(run_id),
  CHECK ((claim_id IS NOT NULL) + (relation_id IS NOT NULL) = 1)
);
CREATE UNIQUE INDEX ux_cur_cond ON cur_claim_conditions(
  COALESCE(claim_id, relation_id), dimension);
```

Rows, not JSON, because the questions in CAP-6 are condition lookups — *exposure
C, HVHZ, 6 ft* is a three-way filter and a JSON blob cannot serve it without a
scan.

**`value_milli` exists because TEXT comparison is lexical.** `'6' > '48'` is
true and `'0.9' > '0.100'` is true, so a `fence_height <= 48"` lookup over
`value_norm` would silently return wrong rows. Decimal strings stay as the
canonical representation — floats are not acceptable for a dimension — and
`value_milli` is the scaled integer that range queries and indexes use.

`operator='unknown'` is first-class: it records that the source did not state
the condition. It blocks acceptance for every mandatory class (§2.5.4). A
footing claim with `exposure_category = unknown` is exactly the G16 failure, and
here it is unacceptable by construction.

### 2.5.3 Evidence — two kinds, because the corpus has two (requirement 10)

This is the change the rest of the phase depends on. The five NOAs have exactly
**one `table` element between them** — a 4×3 OCR word-grid on 12-1106.11, and
not a Table 1. The wind/exposure/footing grids CAP-6 exists to read are
line-work in a scan, the preserved crop is deliberately the *whole page*, and a
large share of the digit-bearing cell values appear in **no element on their
page at all**. An evidence model that requires `element_id` and a text quote
cannot represent the very claims this phase is for — and faking an element link
to hit "100% provenance" is worse than recording the truth.

```sql
CREATE TABLE cur_claim_evidence (
  evidence_id    TEXT PRIMARY KEY,
  claim_id       TEXT REFERENCES cur_claims(claim_id),
  relation_id    TEXT REFERENCES cur_entity_relations(relation_id),
  step_id        TEXT REFERENCES cur_procedure_steps(step_id),
  alias_id       TEXT REFERENCES cur_entity_aliases(alias_id),
  run_id         TEXT NOT NULL REFERENCES cur_runs(run_id),

  evidence_kind  TEXT NOT NULL,   -- element_quote | visual_reading | derived
  document_id    TEXT NOT NULL REFERENCES documents(document_id),
  version_id     TEXT NOT NULL REFERENCES document_versions(version_id),
  version_sha256 TEXT NOT NULL,
  page_id        TEXT REFERENCES pages(page_id),
  page_no        INTEGER,

  -- element_quote
  element_id     TEXT REFERENCES elements(element_id),
  table_id       TEXT REFERENCES tables(table_id),
  cell_row INTEGER, cell_col INTEGER,
  bbox           TEXT,            -- JSON [x0,y0,x1,y1], poppler display space
  exact_quote    TEXT,
  text_source    TEXT,
  ocr_confidence REAL,

  -- visual_reading
  grid_id        TEXT REFERENCES cur_table_readings(grid_id),
  cell_bbox_px   TEXT,            -- JSON [x0,y0,x1,y1] in crop pixels
  row_label TEXT, col_label TEXT,
  reader         TEXT,

  crop_path      TEXT,
  crop_sha256    TEXT,
  crop_dpi       INTEGER,

  CHECK ((claim_id IS NOT NULL)+(relation_id IS NOT NULL)
       + (step_id IS NOT NULL)+(alias_id IS NOT NULL) = 1),
  CHECK (evidence_kind <> 'element_quote'
         OR (element_id IS NOT NULL AND bbox IS NOT NULL
             AND exact_quote IS NOT NULL AND crop_path IS NOT NULL
             AND page_id IS NOT NULL)),
  CHECK (evidence_kind <> 'visual_reading'
         OR (page_id IS NOT NULL AND crop_path IS NOT NULL
             AND cell_bbox_px IS NOT NULL AND row_label IS NOT NULL
             AND col_label IS NOT NULL AND reader IS NOT NULL)),
  CHECK (evidence_kind <> 'derived' OR (element_id IS NULL AND crop_path IS NULL))
);
```

- **`element_quote`** — the claim came from parsed text. `exact_quote` must be a
verbatim substring of the cited element's `text`, `ocr_text`, or the cited
`table_cells.text`, at the cited `version_id`. Not merely equal to the claim's
own lexeme: that check is self-satisfying, since the same code writes both.
- **`visual_reading`** — the claim came from a person or a reader looking at
pixels. There is no element and there is no quote, and both absences are
recorded rather than papered over. It carries the page, the crop, the crop hash,
the **cell bounding box in crop pixels** (which the reader must now produce),
the row and column labels, and the reader's identity.
- **`derived`** — `origin='calculated'` (a BOM line) or `curated_dataset` (a
`data/structural/*.json` assertion, which is not a `documents` row at all).
Carries no crop, and **can never reach `accepted`**; it exists so a calculated
quantity or a conflicting curated assertion is addressable.

Requirement 10 is therefore measured as: every claim resolves to document →
version SHA-256 → page → *(element + bbox **or** cell bbox in crop pixels)* →
crop, with the two kinds reported separately.

### 2.5.4 Triggers — the constraints that are not row-local

`CHECK` cannot contain a subquery; a trigger `WHEN` clause can. Four triggers,
not one, because a single accept-gate is trivially unwound:

```sql
-- 1. accept requires a human review row
CREATE TRIGGER cur_claims_gate_ins BEFORE INSERT ON cur_claims
FOR EACH ROW WHEN NEW.status='accepted' AND NEW.review_mandatory=1
 AND NOT EXISTS (SELECT 1 FROM cur_reviews r WHERE r.claim_id=NEW.claim_id
   AND r.reviewer_kind='human' AND r.decision='accept')
BEGIN SELECT RAISE(ABORT,'mandatory review class: needs a human accept'); END;

-- 2. the same, BEFORE UPDATE ON cur_claims -- deliberately NOT
--    'BEFORE UPDATE OF status', which fires only when status is in the SET list

-- 3. an accepted claim may not carry an unknown condition
CREATE TRIGGER cur_claims_gate_unknown BEFORE UPDATE ON cur_claims
FOR EACH ROW WHEN NEW.status='accepted' AND NEW.review_mandatory=1
 AND EXISTS (SELECT 1 FROM cur_claim_conditions c
             WHERE c.claim_id=NEW.claim_id AND c.operator='unknown')
BEGIN SELECT RAISE(ABORT,'mandatory class with an unstated condition'); END;

-- 4. the human review an accepted claim rests on cannot be deleted or downgraded
CREATE TRIGGER cur_reviews_no_unaccept BEFORE DELETE ON cur_reviews
FOR EACH ROW WHEN OLD.reviewer_kind='human' AND OLD.decision='accept'
 AND EXISTS (SELECT 1 FROM cur_claims c
             WHERE c.claim_id=OLD.claim_id AND c.status='accepted')
BEGIN SELECT RAISE(ABORT,'cannot remove the review an accepted claim rests on'); END;
-- plus BEFORE UPDATE ON cur_reviews with the same WHEN on OLD/NEW.decision
```

Equivalents exist for `cur_entity_relations` (accept requires a human review row
for `review_class='compatibility'`; a relation with no evidence row cannot leave
`candidate`).

### 2.5.5 Review workflow (requirement 6)

```sql
CREATE TABLE cur_reviews (
  review_id     TEXT PRIMARY KEY,
  claim_id      TEXT REFERENCES cur_claims(claim_id),
  relation_id   TEXT REFERENCES cur_entity_relations(relation_id),
  entity_id     TEXT REFERENCES cur_entities(entity_id),
  page_map_id   TEXT REFERENCES cur_page_maps(page_map_id),
  reviewer      TEXT NOT NULL,
  reviewer_kind TEXT NOT NULL,   -- human|agent
  decision      TEXT NOT NULL,   -- accept|reject|needs_source|blocked|correct
  corrected_value_raw TEXT,
  corrected_conditions TEXT,
  rationale     TEXT NOT NULL,
  evidence_seen TEXT NOT NULL,   -- JSON: crop sha256s rendered in this session
  session_token TEXT NOT NULL,   -- issued by `cli curate queue` per rendered crop
  duration_ms   INTEGER,
  reviewed_at   TEXT NOT NULL,
  run_id        TEXT NOT NULL REFERENCES cur_runs(run_id),
  CHECK ((claim_id IS NOT NULL)+(relation_id IS NOT NULL)
       + (entity_id IS NOT NULL)+(page_map_id IS NOT NULL) = 1)
);

CREATE TABLE cur_review_propagation (
  claim_id             TEXT PRIMARY KEY REFERENCES cur_claims(claim_id),
  propagated_from_review_id TEXT NOT NULL REFERENCES cur_reviews(review_id),
  tuple_signature      TEXT NOT NULL,
  run_id               TEXT NOT NULL REFERENCES cur_runs(run_id)
);
```

`evidence_seen` plus `session_token` is **attestation, not proof** — the review
tool records which crops it rendered, and the audit checks that every hash in
`evidence_seen` matches a `crop_sha256` on that claim's evidence *and* the file
on disk. It cannot prove a person looked. The readiness report says so rather
than implying otherwise.

`cur_review_propagation` exists because the workload is measured in distinct
tuples (359 in the slice) while status is carried per claim (1,293). One review
decision propagates to every claim sharing its `tuple_signature`, and each
propagated status names the review row it inherited from.

`reviewer_kind='agent'` reviews are permitted and useful, but an agent review
never satisfies a mandatory class. It raises `confidence_basis` to
`two_reader_agreement` and moves the claim to `in_review`; a person still
decides.

> **This is a change to existing behaviour, not a description of it.**
> `table_review.PROMOTABLE` is `("accepted", "corrected", "cross_family_verified")`
> today — two agent readings from *different model families* already promote, and
> 324 facts in the store were written that way with no human in the loop.
> Curation revokes that. C0 removes `cross_family_verified` from `PROMOTABLE`,
> and the 324 existing rows are recorded as a grandfathered exception that
> migrates as `candidate` like everything else.

---

## 2.6 Table readings — the grid as one object (prohibition 4)

Prohibition 4 forbids flattening a table into text and discarding its structure.
Turning each cell into an independent claim would do exactly that, and it would
also destroy the G16 mechanism: a `NON HVHZ` bracket **spanning two rows** is
one observation, not a condition retyped by hand onto each of N cells.

```sql
CREATE TABLE cur_table_readings (
  grid_id       TEXT PRIMARY KEY,
  page_id       TEXT NOT NULL REFERENCES pages(page_id),
  document_id   TEXT NOT NULL REFERENCES documents(document_id),
  crop_path     TEXT NOT NULL,
  crop_sha256   TEXT NOT NULL,
  crop_dpi      INTEGER NOT NULL,
  table_kind    TEXT NOT NULL,   -- wind_exposure_footing|bill_of_materials|
                                 -- spacing|dimension|sku|prose|drawing_only
  title_raw     TEXT,
  n_rows INTEGER NOT NULL, n_cols INTEGER NOT NULL,
  header_rows   TEXT NOT NULL,   -- canonical JSON: header vectors with spans
  status        TEXT NOT NULL,
  run_id        TEXT NOT NULL REFERENCES cur_runs(run_id)
);

CREATE TABLE cur_table_annotations (
  annotation_id TEXT PRIMARY KEY,
  grid_id       TEXT NOT NULL REFERENCES cur_table_readings(grid_id),
  kind          TEXT NOT NULL,   -- row_bracket|col_bracket|footnote|unit_note
  text_raw      TEXT NOT NULL,   -- 'NON HVHZ'
  applies_rows  TEXT NOT NULL,   -- canonical JSON: [1,2]
  applies_cols  TEXT NOT NULL,
  bbox_px       TEXT NOT NULL,
  status        TEXT NOT NULL,   -- reviewed separately, once, by a person
  run_id        TEXT NOT NULL REFERENCES cur_runs(run_id)
);
```

Every cell claim references its `grid_id`. The bracket is reviewed once, as one
object, and the conditions it implies are generated from it — so a reviewer
cannot accept row 1 as HVHZ and row 2 as non-HVHZ from the same bracket.

---

## 2.7 Conflicts

```sql
CREATE TABLE cur_conflicts (
  conflict_group_id TEXT PRIMARY KEY,
  attribute         TEXT NOT NULL,
  subject_entity_id TEXT REFERENCES cur_entities(entity_id),
  condition_signature TEXT NOT NULL,
  kind              TEXT NOT NULL,    -- contradiction|version_difference|
                                      -- condition_difference|authority_difference|
                                      -- reading_disagreement
  resolution        TEXT NOT NULL DEFAULT 'unresolved',
  resolution_rationale TEXT,
  winning_claim_id  TEXT REFERENCES cur_claims(claim_id),
  resolved_by TEXT, resolved_at TEXT,
  run_id            TEXT NOT NULL REFERENCES cur_runs(run_id),
  UNIQUE(attribute, subject_entity_id, condition_signature, kind)
);
```

Two claims conflict when attribute, subject, and `condition_signature` match and
values differ. **`condition_signature` includes `valid_from` and
`revision_status`** — without them, a `version_difference` across the five NOA
generations can never be detected, because those claims differ in validity, not
in conditions. Different conditions with the same validity are a
`condition_difference`, not a contradiction; that distinction is what would have
prevented the G16 HVHZ error from ever being written.

Nothing is auto-resolved. `cur_vocab.rank` orders the presentation. Losing
claims are never deleted and stay addressable with their evidence.

---

## 2.8 Procedures

```sql
CREATE TABLE cur_procedures (
  procedure_id  TEXT PRIMARY KEY,
  entity_id     TEXT NOT NULL REFERENCES cur_entities(entity_id),
  title         TEXT NOT NULL,
  document_id   TEXT NOT NULL REFERENCES documents(document_id),
  authority_level TEXT NOT NULL,
  status        TEXT NOT NULL,
  run_id        TEXT NOT NULL REFERENCES cur_runs(run_id)
);

CREATE TABLE cur_procedure_steps (
  step_id       TEXT PRIMARY KEY,
  procedure_id  TEXT NOT NULL REFERENCES cur_procedures(procedure_id),
  ordinal       INTEGER NOT NULL,
  action        TEXT NOT NULL,
  status        TEXT NOT NULL,
  run_id        TEXT NOT NULL REFERENCES cur_runs(run_id),
  UNIQUE(procedure_id, ordinal)
);

CREATE TABLE cur_step_parts     (step_id TEXT, entity_id TEXT, role TEXT,
                                 PRIMARY KEY(step_id, entity_id, role)) WITHOUT ROWID;
CREATE TABLE cur_step_requires  (step_id TEXT, requires_step_id TEXT,
                                 PRIMARY KEY(step_id, requires_step_id)) WITHOUT ROWID;
CREATE TABLE cur_step_claims    (step_id TEXT, claim_id TEXT,
                                 PRIMARY KEY(step_id, claim_id)) WITHOUT ROWID;
CREATE TABLE cur_step_warnings  (warning_id TEXT PRIMARY KEY, step_id TEXT NOT NULL,
                                 text_raw TEXT NOT NULL, element_id TEXT NOT NULL);
```

A warning lives on its step. There is no table in which a warning can exist
detached from the action it governs. The edge tables are real tables rather than
JSON arrays for the reason §2.3 gives: an FK edge in a JSON blob is
unenforceable, unindexable, and inconsistent with this document's own argument
for conditions.

---

## 2.9 Knowledge gaps

```sql
CREATE TABLE cur_knowledge_gaps (
  gap_id        TEXT PRIMARY KEY,
  scope_kind    TEXT NOT NULL,   -- capability|entity|document|page|table|
                                 -- attribute|claim
  scope_ref     TEXT NOT NULL,   -- the id of the thing named by scope_kind
  capability    TEXT,            -- CAP-1..CAP-9
  description   TEXT NOT NULL,
  reason        TEXT NOT NULL,   -- not_in_corpus|unreadable_scan|
                                 -- table_not_reconstructed|condition_unstated|
                                 -- conflicting_sources|awaiting_review|out_of_scope
  blocking      INTEGER NOT NULL,
  run_id        TEXT NOT NULL REFERENCES cur_runs(run_id),
  CHECK (blocking IN (0,1))
);
CREATE TABLE cur_gap_evidence (gap_id TEXT, evidence_id TEXT,
                               PRIMARY KEY(gap_id, evidence_id)) WITHOUT ROWID;
```

`scope_ref` is a typed id, not free text, so a criterion like "every claim with
`validity_basis='none'` has a gap" is a join rather than a string search.

A gap is a deliverable, not an admission — *"the corpus does not state the
footing depth for Exposure D"* is a materially different answer from silence.
But see doc 5: a gap must cost something, or gapping everything becomes the
dominant strategy.

---

## 2.10 Bundles

```sql
CREATE TABLE cur_bundles (
  bundle_id      TEXT PRIMARY KEY,
  slice_id       TEXT NOT NULL,     -- 'slice-bufftech-extruded-pvc'
  entity_id      TEXT NOT NULL REFERENCES cur_entities(entity_id),
  generated_at   TEXT NOT NULL,
  run_id         TEXT NOT NULL REFERENCES cur_runs(run_id),
  export_path    TEXT NOT NULL,     -- workspace/bundles/<slice_id>/bundle.json
  export_sha256  TEXT NOT NULL,     -- over the export minus generated_at
  readiness_verdict TEXT NOT NULL
);
CREATE TABLE cur_bundle_members (
  bundle_id  TEXT NOT NULL REFERENCES cur_bundles(bundle_id),
  member_kind TEXT NOT NULL,   -- claim|document|entity|configuration|procedure|
                               -- grid|drawing_evidence|conflict|gap|not_covered
  member_ref TEXT NOT NULL,
  PRIMARY KEY (bundle_id, member_kind, member_ref)
) WITHOUT ROWID;
```

Members are rows, not a JSON blob with a `-- accepted only` comment: a trigger
asserts that every `member_kind='claim'` row names a claim with
`status='accepted'`. `not_covered` is a member kind, so the bundle's tenth
section has somewhere to live.

The exported JSON is a projection of these tables and is regenerable from them.
It is never the system of record.

---

## 2.11 Crop generation — poppler, not Pillow

`crop_path` is required for `element_quote` and `visual_reading` evidence, so
crop generation cannot depend on an optional package. `extract._crop_region`
(`extract.py:109-112`) uses Pillow and **returns `False` when it is absent**,
and Pillow lives in the git-ignored, explicitly-optional `workspace/pylibs/`. A
`NOT NULL` crop backed by an optional dependency fails on a clean checkout.

Crops are cut with poppler, which is a declared dependency:

```bash
pdftoppm -png -r <pages.page_image_dpi> -f <page_no> -l <page_no> \
         -x <int((x0-pad)*d/72)> -y <int((y0-pad)*d/72)> \
         -W <int((x1-x0+2*pad)*d/72)> -H <int((y1-y0+2*pad)*d/72)> \
         <source_pdf> <out_prefix>
```

Four things this fixes or pins:

1. **Never hardcode 200 dpi.** The corpus is `{200: 2140 pages, 72: 6, NULL: 1}`.
The six 72-dpi pages are the CAD PNGs, where `pages.width/height` are pixels
rather than points and the formula only works because `72/72 = 1`. The dpi comes
from `pages.page_image_dpi` and is stored in `cur_claim_evidence.crop_dpi`. The
one NULL-dpi page is flagged, not guessed.
2. **Top-left origin, poppler display space — and no rotation transform.**
`pdftotext -bbox-layout` reports `yMin` from the *top*, which matches pdftoppm's
`-y`. An implementer who reads "PDF points" and applies the usual bottom-left
origin (`y' = height - y`) mirrors every crop vertically. For pages with a
non-zero `/Rotate`, `pages.width/height` are already the swapped display
rectangle and pdftoppm has already applied the rotation, so bbox, page rectangle
and image share one space. CLAUDE.md records that adding a rotation transform
here was a real bug, found and removed once.
3. **The transform is normative**, not descriptive: the pad, the `int()`
truncation, the dpi, and the encoder are fixed and recorded in
`cur_runs.tool_versions` / `tool_fingerprint`. Poppler's PNG output is
version-dependent, so byte-identity is asserted *within* a fixed tool
fingerprint, and `crop_sha256` is compared alongside it.
4. **Crop failure raises.** It does not return `False` and carry on.

Verified on this corpus: 2,146 pages carry an image path and 2,140 have a
`page_image` asset row; on all 2,140, `pages.width * page_image_dpi/72` matches
`assets.width_px` **to within one pixel** — 2,040 match exactly, 96 differ by
less than a pixel, 4 differ by exactly one pixel, and none by more. Exact
equality is therefore the wrong assertion — the transform must fix its own
rounding rule rather than assume poppler's. The six pages with an image path and
no asset row are flagged, not guessed at. And a test crop of a paragraph bbox on
`bufftech-installation-guide-40-40-70743.pdf` page 5 renders exactly the three
lines containing `30" deep`, confirming the origin and scale.

---

## 2.12 Indexes

SQLite does not auto-index foreign-key child columns, so every `REFERENCES`
column below is a full scan without these.

```sql
-- condition lookup: exposure C + HVHZ + 6 ft is a self-join on dimension+value
CREATE INDEX ix_cur_cond_lookup ON cur_claim_conditions(dimension, value_norm, claim_id);
CREATE INDEX ix_cur_cond_range  ON cur_claim_conditions(dimension, value_milli);

CREATE INDEX ix_cur_claims_subject  ON cur_claims(subject_entity_id, attribute, status);
CREATE INDEX ix_cur_claims_queue    ON cur_claims(status, review_class, review_mandatory);
CREATE INDEX ix_cur_claims_tuple    ON cur_claims(tuple_signature);
CREATE INDEX ix_cur_claims_conflict ON cur_claims(conflict_group_id);
CREATE INDEX ix_cur_claims_run      ON cur_claims(run_id);

CREATE INDEX ix_cur_ev_claim  ON cur_claim_evidence(claim_id);
CREATE INDEX ix_cur_ev_owner  ON cur_claim_evidence(relation_id, step_id, alias_id);
CREATE INDEX ix_cur_ev_page   ON cur_claim_evidence(document_id, page_no);
CREATE INDEX ix_cur_ev_grid   ON cur_claim_evidence(grid_id);

-- the accept-gate trigger runs this EXISTS on every accept
CREATE INDEX ix_cur_rev_claim ON cur_reviews(claim_id, reviewer_kind, decision);

CREATE INDEX ix_cur_pm_queue  ON cur_page_maps(curation_status, ocr_risk);
CREATE INDEX ix_cur_pm_doc    ON cur_page_maps(document_id, page_no);
CREATE INDEX ix_cur_pmc_class ON cur_page_map_classes(content_class);

CREATE INDEX ix_cur_alias_lookup ON cur_entity_aliases(alias COLLATE NOCASE);
CREATE INDEX ix_cur_rel_from  ON cur_entity_relations(from_entity_id, relation_type);
CREATE INDEX ix_cur_rel_to    ON cur_entity_relations(to_entity_id, relation_type);
CREATE INDEX ix_cur_dossier_dup ON cur_document_dossiers(duplicate_group_id);
CREATE INDEX ix_cur_gaps      ON cur_knowledge_gaps(blocking, capability, scope_kind);
```

`cur_entity_aliases`' declared `UNIQUE(entity_id, alias, alias_kind)` is
entity-first and useless for the alias→entity direction that CAP-1 needs, hence
`ix_cur_alias_lookup`.

---

## 2.13 What is deliberately *not* in this schema

- **No embedding column, no vector table.** Prohibition 9 stands; nothing
measured here needs one.
- **No `verified` status.** The word invites exactly the promotion this phase
exists to prevent. The strongest status is `accepted`, and it names the person
who accepted it.
- **No automatic conflict resolution.** `resolution` may become
`resolved_by_authority`, but only through a review row, never by an unattended
rule.
- **No writes to `facts`, and no foreign key onto it.** The 1,988 existing rows
stay exactly as they are, as the immutable input to the migration in doc 4.
- **No nullable-everything evidence.** Each `evidence_kind` has its own
completeness CHECK, so "provenance complete" cannot be satisfied by leaving
columns empty.
