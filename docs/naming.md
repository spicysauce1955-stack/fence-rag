# Naming — the conventions, decided

```text
Status:   DECIDED, 2026-09-09, and partly ENFORCED -- tests/test_naming.py fails
          the build on the four rules cheap enough to check mechanically.
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
- **Five colliding document-id namespaces.** `docs/README.md` warns about one of
  them. `R1` means a retrieval upgrade, an audit recommendation, *or* a curation
  acceptance criterion, depending on the file.

None was a hard failure. All were the same shape: **a name nothing checks
slowly stops meaning what a reader assumes.** The rules below are mostly
descriptive; the value is that they are now checkable.

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
64-hex shape, different subject. It mints `snapshot_id` and `Part.version`
strings.

**Open defect (A-1).** `authority` is the only hash-bearing published field with
no type gate and no closure check — `snapshot.HASH_BEARING` omits it, so a value
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

**Open defects, all measured, none fixed here:**

| id | defect | why it matters |
|---|---|---|
| B-1 | 11 `*_drawing_*_mm` fact types whose `unit_original` is `in` | the exact inversion of Rule 2 — the class of error that produced G63's twelvefold-too-small number |
| B-2 | 4 `kit_qty_*_in` fact types whose unit is `each` | `_in` is a **live dispatch key**; these survive only because they bypass `facts._normalise` |
| B-3 | `u_channel_designation_in` is a designation, not a length | minor |
| B-4 | `max_rack` is `quantity(deg_milli)` with no suffix, in ratified `contract.md` | cheap now (publishes nothing); expensive once it does |
| G108 | `fence_height_ft` vs `fence_height` | see `state-and-gaps.md` |

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

**D-5, the most serious, and it is live:** `[measured]` `Part.version` is the
integer `1` on 27 published parts and the string `"sha256:<64hex>"` on 15, **in
one snapshot**, and `PART_SHAPE` omits the field so nothing catches it. This
becomes load-bearing the moment `Combination` is built — `contract.md` pins
`Combination.members` as `[Part@version]`. No reason for the string form is
recorded anywhere.

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

**Open defects:** `WARN_*` is a declared vocabulary that nothing emits —
`[measured]` **0 of 287** published warnings carry a `code`, while
`registry-additions.md` asks Planning to build 11 locale bundles for codes that
never arrive (E-1). `because.code` carries a `warning_`-prefixed sub-scheme that
reads as a severity and is not, plus three undocumented renames off
`quality_issues.kind` (E-2). And **`review_status` is one column name over four
disjoint vocabularies** across `facts`, `table_read_candidates`, `step_candidates`
and the `*_reviews` tables, with `CURATION_LEVEL` mapping across two of them at
once — so a value from the wrong table scores a curation level silently (E-3).
E-3 is the one worth a migration.

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
`gc.py` shadows the stdlib `gc`; `promote_tables.py` is the only verb+object
module name.

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

**Open defect: five colliding namespaces.** `docs/README.md` warns about one of
them (two `R1`–`R5` schemes). `[measured]` there are at least five: `R` means a
retrieval upgrade, an audit recommendation, *or* a curation criterion; `F` means
an audit defect *or* a curation floor criterion; `C` means an amendment
candidate *or* a curation stage — **and `CLAUDE.md` uses both senses of `C` nine
lines apart**; `A` means a build-plan item *or* a curation group.

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

`tests/test_naming.py` checks the four rules cheap enough to check
mechanically, over the stored snapshots and the code:

| Rule | Check |
|---|---|
| 1 | every `authority` in a published snapshot resolves to a `source_docs` entry — closes A-1 |
| 3 | every `_mm`-suffixed `SpecField` key carries a `Quantity`; every unsuffixed one carries a `Token` |
| 5 | every code in `api.ERROR_CODES` is `error.*`; no registry code is |
| 9 | CLI subcommands and flags are kebab-case; `G<n>` headings are unique |

The rest are recorded, not enforced. A rule that cannot be checked is a rule
that drifts — which is the whole argument of §0 — so **when you add a
convention here, add its check or say why there is none.**
