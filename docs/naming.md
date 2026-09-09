# Naming — the conventions, decided

```text
Status:   DECIDED, 2026-09-09, and partly ENFORCED -- tests/test_naming.py fails
          the build on the rules cheap enough to check mechanically.
          WORKED the same day. Fifteen open items were listed below on
          2026-09-09; five are CLOSED (B-1, B-2, D-5, G108, and
          section 6's `gc.py`, which closed as a collision rather than a
          defect), one is PARTLY closed (section 9's colliding namespaces --
          `F` and `C` closed, `R` went from three senses to two and the
          remaining pair is untouched), one is FILED as amendment 011 (B-4),
          one is ANSWERED and turned up a different live defect (E-1 -> G111),
          one is HALF CLOSED by documenting it (E-2), one is PUT TO THE OWNER
          as a migration plan rather than migrated (E-3), and five stay open
          with a stated reason each (B-3, D-1 to D-4).
          Four figures IN THIS DOCUMENT were wrong and are corrected in place
          with the measurement that settled each -- B-1's count, D-5's "no
          reason is recorded anywhere", D-5's attribution of
          `Combination.members` to `contract.md`, and section 9's "nine lines
          apart". A conventions document that cannot be trusted is worth less
          than no conventions document, so the corrections are marked rather
          than quietly applied.
          Everything here was MEASURED off the code and the published snapshots
          first; almost none of it is new. The repository already had these
          conventions. It did not have them written down, which is why they
          drifted in five places that this document names.
Scope:    Every name this project mints -- data fields, identifiers, code
          vocabularies, Python symbols, tests, documents, and document ids.
Authority: None at the boundary. `contract.md` is frozen and governs what
          crosses; where a name is already published, this document RECORDS the
          rule rather than changing the name. A published id is frozen.
```

## 0. Why this exists

Three defects found in a single session on 2026-09-08/09, all of them a naming
problem wearing another problem's clothes:

- **G108** — `facts._conditions()` emits `fence_height_ft`; the publisher accepts
  only `fence_height`. 18 facts carry the unpublishable name, 24 the publishable
  one. Nothing has broken because none of the 18 is accepted yet.
- **The gold set's `required_conditions`** uses twelve dimension names, three of
  which exist. The same table column is called `post_size_in` in one question
  and `line_post_size_in` in another. Nothing reads the field, so nothing ever
  said.
- **Five colliding document-id namespaces.** `docs/README.md` warned about one
  of them. `R1` meant a retrieval upgrade, an audit recommendation, *or* a
  curation acceptance criterion, depending on the file. **Partly closed
  2026-09-09** by requalifying the curation schemes: `F` and `C` are now
  unambiguous, `R` still means two things -- see §9.

None was a hard failure. All were the same shape: **a name nothing checks
slowly stops meaning what a reader assumes.** The rules below are mostly
descriptive; the value is that they are now checkable.

**And the document did it to itself.** Working these defects on 2026-09-09
found four wrong figures *in this file*, written the day before by the session
that wrote the rules. Each is corrected in place and marked. That is not an
embarrassment to bury: it is the same failure mode one layer up, and the reason
§11 ends the way it does.

---

## 1. One value, one name — unless the name marks a role or a layer

`[measured]` the SHA-256 of a source file appears under **six** names, and every
one holds the identical 64-hex value:

| Name | Where | Why it is not just `sha256` |
|---|---|---|
| `sha256` | `document_versions.sha256`, `assets.sha256` | the store's word. `ids.py`: document identity is derived from the source path so it survives re-ingestion; **content** identity is the file hash, kept separately |
| `content_hash` | `SourceDoc.content_hash` (published) | the contract's word at the boundary |
| `belongs_to` | `SourceRef.belongs_to` | names a **join direction**. `sourcerefs.py`: *"A ref names the bytes; asking 'which document is this?' has no single answer, and picking one filing would make a warning appear or vanish depending on an alphabetical tie-break"* |
| `authority` | `ParameterRow.authority` | names a **role**. `contract.md` §1.3: *"Expiry is a property of the authority, not of the site, and belongs beside the authority"* |
| `contributing_sources[]` | `Part` | plural of the same, for a different relation |
| `superseded_by[]` | `SourceDoc` | content hashes because *"a `doc-…` id is an internal handle Planning cannot resolve"* |

> ### RULE 1
>
> **A second name for one value is admissible only when it marks a different
> ROLE or a different LAYER, and the reason is recorded here.**
>
> Six names for one hash is not a defect — each of the six answers a different
> question. Seven without a reason would be.

**Beware the homonym.** `canonical.content_hash()` is a *different function*:
sha256 of an object's canonical JSON bytes, not of a file. Same word, same
64-hex shape, different subject. It mints `snapshot_id` and, through
`canonical.part_version`, `Part.version` strings. **`part_version` is the one
definition of the second of those** as of 2026-09-09 -- five call sites minted
it by hand before, and one of them hashed a dict that already carried its own
version, so a published `Part.version` could not be recomputed from the
published payload. See §4, D-5.

**A-1, CLOSED 2026-09-09 by its own check.** `authority` was the only
hash-bearing published field with no type gate and no closure check — `snapshot.HASH_BEARING` omits it, so a value
naming a document absent from `source_docs` would publish, while the same value
in `belongs_to` is refused. `[measured]` 0 of 7 authorities are unresolvable
today. `tests/test_naming.py` now closes it.

---

## 2. Unit suffixes

The rule is already stated in `parameters.py`, and it is load-bearing rather than
cosmetic — `facts.py` dispatches unit normalisation on `fact_type.endswith("_in")`
and `authored_models.py` dispatches value-shape validation on `key.endswith("_mm")`:

> *"`facts.fact_type` is this platform's internal name and **carries the
> source's unit** (`_in`); the published parameter **carries the unit it CROSSES
> in**, which is always mm."*

> ### RULE 2
>
> **A name carries a unit suffix if and only if it is quantity-valued AND its
> unit is not declared somewhere else.**
>
> - `fact_type` → the **source's** unit. `footing_depth_in`.
> - published `parameter` → the **crossing** unit, always mm. `footing_depth_mm`.
> - condition dimension → **declared by the domain form**, so a `range(mm)`
>   dimension takes no suffix and an enumerated one does.
> - not a quantity → no suffix. `exposure_category`, `hvhz`, `approval_id`.

That last clause is why `fence_height` sits correctly beside `wind_speed_mph` in
one dict, which reads as an inconsistency and is not: `fence_height` publishes
`domain: "range(mm)"` and declares its unit there; `wind_speed_mph` publishes an
enumeration, which declares nothing, so the name must.

**The defects, and what happened to each on 2026-09-09:**

| id | defect | status |
|---|---|---|
| B-1 | ~~11~~ **13** `*_drawing_*_mm` fact types whose `unit_original` is `in` | **CLOSED.** Renamed to `_in`. `[measured]` the count in this table was wrong — it is 13, not 11: board (3), end_channel (3), panel (4), rail (3). The fix is a RENAME and not a normalisation, decided on evidence rather than symmetry: `[measured]` `value_normalized` is NULL on all 13 and each recipe's `quantity()` converts by re-parsing `value_original` as an inch string, so writing 25.4× into the store would make it assert a conversion no reader performs — the half of G63 that shipped a number twelve times too small. The published `SpecField.key` stays `_mm`, because that is the unit it CROSSES in. G109 |
| B-2 | 4 `kit_qty_*_in` fact types whose unit is `each` | **CLOSED.** Suffix removed — a count is not a quantity whose unit the name must declare. The unit is declared once, on the `kit_qty` prefix in the two recipes, with a comment saying why |
| B-3 | `u_channel_designation_in` is a designation, not a length | **OPEN, and it passes Rule 2a below**, correctly: `unit_original` is `in` on all 3 rows, so the name claims no unit the row lacks. Still minor, still a designation |
| B-4 | `max_rack` is `quantity(deg_milli)` with no suffix, in ratified `contract.md` | **FILED as amendment 011**, not fixed — a name in a frozen contract moves only through `AMENDING.md`. The proposal reframes it: the unit IS declared elsewhere (`value_type`), so the rule is not "every quantity takes a suffix" but "every published parameter name takes one and this is the only exception". `[measured]` **9 distinct tables** across three parameter names, all suffixed or `paired` (they appear as 225 rows across the 25 non-tombstoned snapshots — 9 x 25; the count Planning has held since 2026-08-31 is 9); `max_rack` tables published: **0** |
| G108 | `fence_height_ft` vs `fence_height` | **CLOSED.** `facts._conditions` writes `fence_height` carrying the source's own lexeme, `parameters._parse_fence_height` gained a point branch (a stated height is an interval whose bounds coincide, both inclusive), and `cli migrate` re-derived the 18 stored rows rather than relabelling them |

> ### RULE 2a, added with its check
>
> **A unit token at the end of a `fact_type` must be a unit the row actually
> carries** — in `unit_original` or in `unit_normalized`, after alias
> normalisation.
>
> Not equality with either, and the two near-misses are the reason. An equality
> rule on `unit_original` fails `stock_length_in`, which this section explicitly
> protects: 33 of its 62 sources state feet. An equality rule on
> `unit_normalized` fails the drawing readings, whose value is never normalised
> at all. `[measured]` 2026-09-09 the rule as stated caught exactly B-1 and B-2
> — 17 fact types — and passed everything this document calls correct.

**Not a defect:** `stock_length_in` is named for inches although 33 of 62 sources
state feet. The suffix names the fact type, and `parts._stock_length_quantity`
reads `unit_original`. G63 documents this.

---

## 3. A name signals a value's shape

`[measured]` across all 42 published `Part`s, with zero exceptions:

> ### RULE 3
>
> **On a `SpecField`, a `_mm` key carries a `Quantity`; an unsuffixed key
> carries a `Token`.** A bare number never crosses — obligation 4 is BINDING:
> *"Every dimension is a `Quantity` — integers in thousandths of the named unit,
> with every verbatim source lexeme alongside… nothing in this corpus is a whole
> number of millimetres (`7/8"` is 22.225 mm)."*

Shapes, and where each is legal:

| Shape | Legal as |
|---|---|
| `Quantity {amount_milli, unit, value_raw}` | any measurement, anywhere |
| `Token {key, value_raw}` | a closed-set value. **Never a bare string** |
| `Interval {min, max, min_inclusive, max_inclusive, value_raw}` | inside `conditions`, on a `range()` dimension — **never as a row's value**. `null` on a bound means UNBOUNDED, not absent |
| `[[Quantity, Quantity], …]` | `value_type: paired` only (amendment 006) |

Enforcement gap worth knowing: Rule 3 is checked in `authored_models.py` but
`snapshot.PART_SHAPE` does not type `SpecField.value` at all, so a wrongly-shaped
value would publish through `cli snapshot --build`. `tests/test_naming.py` now
checks it over stored snapshots.

---

## 4. Identifiers

`[measured]` every id this project mints, and the shape it takes:

> ### RULE 4
>
> - **`<prefix>-` + 12 hex** — an entity with its own row you can look up.
>   `doc-`, `proc-`, `step-`, `element-`, `table-`, `run-`.
> - **bare 16 hex** — a content-derived *address*, not a row. `ref_id`,
>   `Gap.id`, `asset_id`, review ids.
> - **bare 64 hex** — a full hash, never truncated. `snapshot_id`,
>   `content_hash` and its five aliases.
> - **`namespace/slug`** — an entity in a namespace. `Part.id`, `EntityRef.id`,
>   `PartType.namespace`.
>
> **Every id is a function of its content.** `phase-checkpoints.md`: *"a counter
> or a uuid would mean two builds over identical knowledge produced different
> bytes."* No random ids, ever.

**FROZEN — do not change these formulas.** `ref_id = sha256(f"{sha256}:{page_no}:{bbox}")[:16]`,
with `bbox` interpolated as the raw stored text, never normalised or re-serialised.
519+ published citations depend on it byte-for-byte, and under the override design
an unstable id orphans a person's correction — the one thing here that does not
regenerate. `snapshot_id` is likewise fixed.

**Open defects:** `element_id` truncates to 10 where the rule says 12 (D-1);
`asset_id` is bare 16-hex and so indistinguishable by eye from a `ref_id` (D-2);
a published page subject is `doc-x#p6` while the internal `page_id` is
`doc-x@sha12#p0004`, so the published form cannot be joined to a `pages` row
without reconstructing the version (D-3); `Part.id` lowercases what a
`component`-kind gap subject publishes verbatim (D-4).

**Open, and each judged rather than merely listed on 2026-09-09.** D-1 through
D-4 all stay open and none is worth doing now, for one reason each: changing
`element_id`'s truncation moves every element id and therefore every row keyed
on one (a re-extraction, for a cosmetic two hex digits); `asset_id`'s shape is
in the filenames under `workspace/derived/`; the published page subject and
`Part.id`'s lowercasing are both **published bytes in write-once snapshots**,
where obligation 1 makes a wrong name frozen rather than fixable. D-3 is the one
with real cost — a consumer cannot join a published page subject to a `pages`
row without reconstructing the version — and it belongs with the extraction-
editions work in G38 rather than with a rename.

**D-5, CLOSED 2026-09-09, and two of the four sentences that described it were
wrong.** `[measured]` `Part.version` was the integer `1` on 27 published parts
and the string `"sha256:<64hex>"` on 15, **in one snapshot**, with `PART_SHAPE`
omitting the field so nothing could catch it. Both of those observations were
right. The other two were not:

- *"No reason for the string form is recorded anywhere"* — **false.** G103,
  written 2026-09-07, two days before this document: *"Part versions no longer
  stay at 1 when reviewed content changes. Each is now a `sha256:` hash of all
  public Part content except version… Hash versions identify content, not
  chronological order."* It is also in `docs/curation/emblem-publication-
  workflow.md` and in the adversarial review that caused it. The search that
  produced this sentence looked in the code and not in the record.
- *"`contract.md` pins `Combination.members` as `[Part@version]`"* — **false.**
  `contract.md` never names `Combination.members`; that pin is
  `knowledge-datamodel.md:1395`, and `contract.md`'s only word on `Combination`
  is obligation 17, which says nothing consumes one yet. The claim was stronger
  than the citation, in exactly the direction that makes a defect sound urgent.

**Resolved toward the hash**, because the two forms are two jobs and only one of
them is done: `[measured]` the integer is `1` on every int-versioned part in all
24 stored snapshots that carry parts, and no bump path exists anywhere in the
package, so a corrected value shipped under its predecessor's version. That is
what G103 fixed for the four recipe slices and never fixed for `parts.py`.
`canonical.part_version` is now the single definition and all five sites call
it.

**`PART_SHAPE` carries the WEAK rule, and that is a finding rather than a
compromise.** `snapshot_store.verify_stored` re-runs `verify()` over stored
payloads, so a gate refusing the integer `1` would mark 24 write-once snapshots
non-compliant for having obeyed the rule of their day. So the shape types
`version` as *a positive integer or a non-empty string* — which is also exactly
the predicate `authored_models`' audit and Planning's own `_version_identity`
already enforce, one definition now serving all three — and the strong rule
lives at the builder, where `tests/test_naming.py` holds it.

**A second, live defect fell out of the same read**, and it is the reason
`part_version` exists as a function: `augusta_drawing_claims` re-hashed a picket
dict that already carried a version, chaining the two. `[measured]` 14 of the 15
string-versioned parts in snapshot `0e04d171…` reproduce from their own bytes;
`mfr/weatherables/augusta-8x6-picket` does not. One published `Part.version` a
consumer cannot verify. Fixed forward; the stored snapshot keeps it, because a
stored snapshot is write-once. See G109.

---

## 5. Code vocabularies — case carries meaning

> ### RULE 5
>
> - **`UPPER_SNAKE`** — a **registry code that crosses to Planning** and needs a
>   locale bundle. `SOURCE_*`, `WARN_*`.
> - **`lower_snake`** — an enum value in a published field. `gap.kind`,
>   `source_class`, `version_status`, `condition_basis`, `severity`,
>   `segment_kind`, `condition_scope`.
> - **`error.*`** — transport only, never a registry code.
>
> The case split is not stylistic; it is the machine-checkable signal that keeps
> the two apart. `api.py`: *"Planning's `test_locale_bundles.py` fails their
> build on any registry code lacking both locale bundles — so an HTTP error code
> that leaked into that namespace would break their CI on our commit."*
> Already enforced by `tests/test_api.py`.

**Correct, do not "fix":** `condition_basis` publishing two of the store's three
values (`unexamined` stays internal — *"the store does not assert an inference it
never made"*); `PROMOTABLE` excluding machine consensus (324 facts once published
at a curation level no person had checked). Two vocabularies may share values
without sharing a definition — `table_review.PROMOTABLE` and
`procedures.PUBLISHABLE` are both `("accepted", "corrected")` and are
**deliberately separate**, because a table reading and a step review are
independent decisions that must be free to diverge. What is forbidden is two
names for **one** vocabulary.

**E-1, ANSWERED 2026-09-09, and the answer is that the document was wrong, not
the code.** `WARN_*` is not a vocabulary nothing emits; it is a **census** of
eleven kinds of sentence this corpus prints, mis-filed as a registry of codes.
`[measured]` `grep -rn "WARN_" --include=*.py .` returns **zero hits** — there
is no such constant anywhere — and across all 31 stored snapshots there are
**7,187 published warnings, 0 carrying a `code`** (this document's "0 of 287"
was right for the largest cohort and understated the population). That is
compliant: obligation 10 makes `code` *"an optional overlay"*, and `contract.md`
§2 puts source warnings in the **exempt** half of the registry — *"Exempt from
the bundle rule. The `SOURCE_*` codes are NOT these."* So
`registry-additions.md` §6's ask for eleven locale bundles contradicted §2 of
the same contract, and `[measured]` Planning had already declined it at
`conversation.md` T7 and never built it. Both documents are corrected;
`docs/build-plan.md` C1's *"Planning still needs the two locale bundles"* was
false for thirteen days and is struck. **The real defect the investigation found
is the opposite one**, and it is open: `[measured]` the two `SOURCE_*` lists
have drifted three codes in each direction, so three codes this platform CAN
emit have no bundle on Planning's side and render as raw English. G111, and
`conversation.md` T61.

**E-2, HALF CLOSED 2026-09-09.** The `warning_`-prefixed sub-scheme and the
three renames off `quality_issues.kind` are now documented at
`snapshot.QUALITY_GAP_KINDS` rather than unwound: `[measured]` exactly three of
the seven kinds change on crossing (`mojibake_text_layer` →
`text_layer_mojibake`, `low_ocr_confidence` → `ocr_below_confidence_floor`,
`empty_page_after_ocr` → `empty_after_ocr`) and four cross unchanged. Under
RULE 1 the second name marks a **layer**, store → published, and the published
spellings are aligned to the noun-first `SOURCE_*` form while the store's are
not. Unwinding either side would rewrite write-once snapshots or rows nothing
re-derives; documenting was the whole available fix.

**E-3, PUT TO THE OWNER 2026-09-09, deliberately not migrated.**
`docs/review-status-migration-plan.md` has the measured matrix, the blast radius
and four costed options. The headline correction: **this document's *"a value
from the wrong table silently scores a curation level"* is stronger than the
evidence.** `[measured]` all 200 level-2 facts have a real human record behind
them and zero are mis-scored; what is true is narrower — `facts.review_status`
really does hold two vocabularies (108 rows carry `accepted`, a candidates
value), and two guards written in the other vocabulary do not cover those rows.
The recommendation is per-table `frozenset`s and a `CURATION_LEVEL` that
**raises** on an out-of-vocabulary value, not a rename: the rename would run DDL
against the 1,927 readings that are not in the review ledger, and a value-space
split would rewrite 204 lines of the ledger itself — the one artifact here that
does not regenerate. A schema migration over the review tables is not a
unilateral change, so it stops at the plan.

---

## 6. Python

> ### RULE 6
>
> - **A module named for a CLI subcommand takes that subcommand's name**, snake
>   for kebab. `[measured]` 18/18.
> - **A module that builds a snapshot member is plural and exposes exactly one
>   `build_<member>`.** `[measured]` 5/5. Outside that set, plural/singular
>   carries no meaning and no rule is imposed.
> - **Verb prefixes each mean one thing.** `build_*` constructs a collection;
>   `ensure_*` is idempotent; `import_*` pulls hand-authored readings in;
>   `verify_*` is a gate that fails loudly; **`get_*` is reserved for a contract
>   read surface** and is not a generic accessor; `_is_*` is a predicate;
>   `_default_*` supplies an overridable fallback.
> - **`conn` is the first positional argument** (`[measured]` 148 sites) —
>   connections are passed, never global.
> - **More than about three inputs, or any input a caller could swap by position
>   and be wrong: the tail goes keyword-only**, required arguments included.
> - **`None` means "no such row"; an exception means "this platform cannot
>   answer honestly".** A library function may return `dict | None`; **the CLI
>   must turn that `None` into `{"error": …}` and a non-zero exit** — a guard
>   that reports a problem and exits 0 is indistinguishable from an empty result
>   (`tests/test_cli_not_found.py`).
> - **Exceptions:** `<Noun>Error` for a fault in the program or its
>   configuration (`CanonicalError`, `ConfigError`, `ToolError`);
>   `<Noun><State>` for a refusal that is a legitimate state of the world
>   (`QueryRefused`, `SnapshotMissing`, `TenantLeak`, `ReviewRequired`).
> - **A closed vocabulary is a `frozenset`; an ordered or concatenated one is a
>   `tuple`; a registry mapping a key to a decision is a `dict`.** Every one
>   carries a comment saying why a value is in or out.
> - **One definition per vocabulary.** `query.KNOWN_DIMENSIONS =
>   frozenset(CONDITION_SCOPE)` is the pattern: *"one definition, so the query
>   cannot accept a dimension the publisher would refuse, or refuse one it
>   publishes."*

**Known deviations, recorded rather than fixed:** five modules in the
`*_claims.py` cluster import `_private` names across module boundaries;
`promote_tables.py` is the only verb+object module name.

**`gc.py` — examined 2026-09-09 and CLOSED as a collision, not a defect.**
`[measured]` it breaks nothing and cannot: Python 3 imports are absolute, the
stdlib `gc` is a builtin, and both resolve correctly in the same process
(`import gc` and `from fence_evidence import gc` give different modules, and
`sys.modules['gc']` is still the builtin inside ours). `[measured]` nothing in
this package imports the stdlib `gc` at all, and the only two importers of ours
name it explicitly (`cli.py`'s `from .gc import collect`,
`tests/test_gc.py`'s `from fence_evidence import gc as gcmod`). Renaming would
cost the CLI wiring, two imports and — the real price — the first rule in this
section, since the subcommand is `gc` and the module would no longer be named
for it. The rule is worth more than the clarity, so the module keeps the name
and this paragraph is the fix.

---

## 7. Tests

> ### RULE 7
>
> - **A test method's name is a sentence stating the BEHAVIOUR.**
>   `[measured]` mean 6.8 words, 51.6% opening with a determiner, and exactly
>   **1 of 1,767** named after a function. `test_a_row_the_situation_contradicts_is_excluded_not_downgraded`,
>   not `test_row_verdict`.
> - **The docstring states WHY, and the name never repeats it.** Cite the
>   authority by id — a gap `G<n>`, an obligation, an amendment, a `file.md:§` —
>   and carry the measurement that motivated the test.
> - **Classes are `Test<Thing>`** (`[measured]` 94.3%); `_`-prefixed for
>   fixtures and stubs.
> - **File naming:** `test_<module>.py` for an API surface, `test_<concept>.py`
>   for an invariant that spans modules. Both are in force.

---

## 8. Docstrings

The strongest convention in the repository, and worth stating so it survives.
`[measured]` 61/61 modules carry one; of 387 def/class docstrings, 21.7% narrate
a past defect, 16.5% quote a document directly, 10.9% cite a gap id.

> ### RULE 8
>
> 1. **First line: one declarative sentence** naming what the thing does or
>    decides. `->` for a transform.
> 2. **Blank line, then the ARGUMENT** — why the code is this way and not the
>    obvious alternative. There is no `Args:`/`Returns:` section anywhere in this
>    repository; state a non-obvious return shape in prose.
> 3. **Cite the authority by id and quote it verbatim.**
> 4. **Carry the measurement that motivated the code**, marked `[measured]` with
>    a date — a figure taken from a run, never an estimate.
> 5. **Name the wrong version explicitly**, including when the wrong version was
>    this repository's own earlier code.
> 6. **Say which way a failure fails** — silent wrong answer, or noisy refusal.

---

## 9. Documents and their ids

> ### RULE 9
>
> - **Filenames are kebab-case.** `SCREAMING_CASE.md` is reserved for a
>   *procedural* document you act on rather than read (`AMENDING.md`,
>   `CANDIDATES.md`, `README.md`). An ordered set takes a zero-padded numeric
>   prefix; a session design takes an ISO-date prefix.
> - **CLI subcommands and flags are kebab-case.** `[measured]` 33 subcommands,
>   zero underscores.
> - **An id namespace is GLOBAL across `docs/`.** A single letter belongs to one
>   scheme. Where a letter is already taken, qualify it — `docs/curation/05`'s
>   compound `C-A1` form is the existing precedent.
> - **`G<n>` is monotonic and never reused.** A recurrence of a closed gap is
>   `G<n>, second instance`, not a new id. `G97` is unallocated and stays that
>   way — renumbering would break every citation.
> - **`T<n>` turns are contiguous and append-only.** Heading:
>   `## T<n> · <sender> → <recipient> · <ISO date>`.

**PARTLY CLOSED 2026-09-09 by requalifying the curation schemes.** `F` and `C`
are now unambiguous. **`R` is not**: `docs/target-architecture.md:179` still
numbers retrieval upgrades `R1`-`R5` and
`workspace/reports/projection-relevance-audit.md:158` still numbers
recommendations `R1`-`R9`, and `CLAUDE.md` uses the audit sense. Three senses
became two; the trap `docs/README.md` originally warned about is the one that
survives. `[measured]` there were four collisions, not five -- `docs/curation/05`'s
groups are P, C, F and R, so the `A` collision this document asserted never
existed: `R` meant a retrieval upgrade, an audit
recommendation, *or* a curation criterion; `F` an audit defect *or* a curation
floor criterion; `C` an amendment candidate *or* a curation stage — and
`CLAUDE.md` used both senses of `C` ~~nine~~ **31** lines apart (`[measured]`
2026-09-09: lines 101 and 132; the "nine" was written into this document and
into `docs/README.md` without being counted, then copied between them rather
than re-measured — a small instance of the exact failure §0 describes); `A` a
build-plan item *or* a curation group.

**The curation schemes moved, and only they**, being the newest and least cited:
stages `C0`–`C8`/`C0.5`/`C4b` → `CUR-S0`…`CUR-S8` (an `S` for stage, because
bare `C` was taken twice already — once by amendment candidates and once by
Group C's own subgroups), Group P → `CUR-P*`, Group F → `CUR-F*`, Group R →
`CUR-R*`. `[measured]` 134 id occurrences across 22 files, including 15 inbound
citations from outside `docs/curation/`: four production modules and four tests
cite the `A1/CUR-S0` precedent in their docstrings, and `dataset.py` cites
`CUR-P1b`. The audit, target-architecture, build-plan and amendment-candidate
schemes were left alone.

**`C-A1`…`C-G7` did NOT move.** They are the precedent this rule cites, and
`[measured]` they collide with nothing. §9's trigger is *"where a letter is
already taken"*, and the compound form is not taken by anybody.

**No permanent guard, and that is a decision rather than an omission.** A check
would have to scan every document under `docs/` for a heading-or-table-row
shaped id, and the shapes are not closed: R/F/C/A ids appear as headings, as
table rows, and as bare prose mentions. A pattern loose enough to catch all
three also catches Cloudflare's `R2_BUCKET`, the ASCII `C0` control range, a PDF
`/F1` font key and the NOA drawing item code `P1` — all four are in this
repository, and a mechanical pass during this very change ate `C-C1`–`C-C9`
before diff review caught it. The invariant is unbounded too: "which letters are
taken" changes every time anybody adds a heading, so the guard would go red on
the next legitimate id, which is what §11 says not to ship. The citation map
built for the rename is the verification, and it was a one-time one.

---

## 10. What is frozen

Changing any of these breaks published data or another team's build:

- `ref_id`'s formula, including the raw `bbox` interpolation.
- `snapshot_id` = `sha256(canonical_bytes(hashed members))`, and `retain_until`
  staying outside it.
- Every name in `contract.md`. It is frozen and hashed; a change goes through
  `AMENDING.md`.
- The `error.*` / `UPPER_SNAKE` split, which Planning's CI depends on.

---

## 11. Enforcement

`tests/test_naming.py` checks the rules cheap enough to check mechanically,
over the stored snapshots and the code, and `tests/test_gold_set.py` carries the
one that belongs to the gold set:

| Rule | Check |
|---|---|
| 1 | every `authority` in a published snapshot resolves to a `source_docs` entry — closes A-1 |
| 1 | every key `facts._conditions()` **can** emit is in `parameters.CONDITION_SCOPE`, read out of the source with `ast` rather than sampled — closes G108. The static form is the point: a functional check sees only the keys the fixtures happen to trigger |
| 1 | a height the extractor writes parses back through `parameters._parse_fence_height` into an `Interval`, and the publisher does not refuse the conditions it emits — the two ends agreeing about the VALUE, not only the key |
| 2a | no `fact_type` names a unit none of its rows carries — closes B-1 and B-2 |
| 3 | every `_mm`-suffixed `SpecField` key carries a `Quantity`; every unsuffixed one carries a `Token` |
| 4 | every built `Part.version` is the content hash of the part it names, and `PART_SHAPE` types the field — closes D-5 |
| 5 | every code in `api.ERROR_CODES` is `error.*`; no registry code is |
| 9 | CLI subcommands and flags are kebab-case; `G<n>` headings are unique |
| — | every gold-set `required_conditions` key is a declared dimension; the schema's `propertyNames.enum` equals `sorted(CONDITION_SCOPE)`; a quantity-valued condition carries its unit; one source column is not two names |

`[measured]` 2026-09-09: 1,797 tests pass, 1 expected failure. Every guard added
that day was written red, watched fail for the right reason, and then
**mutation-checked** — the implementation broken deliberately and the guard
confirmed to fail. Several guards in this repository were added green and only
mutation proved they discriminate; these are not among them.

**What stayed unenforced, and why**, so the list is honest: §9's namespace rule
(no non-brittle check exists — see §9); §6's Python conventions (a style check
over 61 modules would go red on the next legitimate exception); §7's and §8's
test-and-docstring conventions (`[measured]` 2026-09-09 **1,798 of 1,799**
test names already state a behaviour rather than a function -- §7's figure
counts the ONE violation, not the compliance -- and 61 of 61 modules carry a
docstring; a lint for prose is a lint somebody argues with); and E-3's per-table vocabulary check, which fails today and lands
with the migration rather than before it.

The rest are recorded, not enforced. A rule that cannot be checked is a rule
that drifts — which is the whole argument of §0 — so **when you add a
convention here, add its check or say why there is none.**
