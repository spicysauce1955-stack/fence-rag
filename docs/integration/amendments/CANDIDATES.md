# Candidate amendments — noticed, not filed

```text
Status:   A running log. Nothing here is filed, and nothing here governs anything.
Purpose:  AMENDING.md §4 says a version is cut "when a batch is ready", and only a
          trigger-A falsification or a trigger-B blocker forces a cut on its own.
          Everything else waits. This is where "everything else" waits, so that
          waiting does not mean forgetting.
Promote:  when a batch is ready and neither side is mid-review, an item here becomes
          `NNN-short-slug.md` beside this file and follows AMENDING.md §3.
Discard:  an item that turns out to be a misreading is struck through with the
          reason, not deleted. Knowing what was considered and rejected is the
          point of keeping a log at all.
```

## How to add one

Name the trigger, quote the text, say what it costs to leave it. If you cannot
name a trigger it is not a candidate — it is a question, and
`docs/integration/planning-asks.md` is where questions go.

Check first whether it forces a cut rather than batching:

- **Trigger A** — measured evidence contradicts a binding item, and someone is
  building against it now. **Cut immediately, do not log it here.**
- **Trigger B** — a binding item cannot be built as written and it is blocking
  work. **Cut immediately.**
- **Trigger C** (scope) and **trigger D** (defect) — batch, unless something is
  blocked.

---

## C1 — `curation_level` 0 versus 1 is never defined

| | |
|---|---|
| **Trigger** | **D** — an obligation depends on something the contract does not define |
| **Raised** | 2026-08-25, while designing the snapshot builder |
| **Blocking?** | **No.** Nothing publishes yet, so nothing is relying on the wrong reading. Batches. |

**The gap.** `curation_level` is declared as `0 \| 1 \| 2` in `knowledge-datamodel.md`
§2.4 and rides on `Provenance` for every published value. The contract pins the
**top** of the scale and only the top — obligation 6: *"Nothing reaches level 2
without a person having compared it to the source image."*

**What separates 0 from 1 is stated nowhere**, in either document.

**Why it is not merely internal.** Three binding mechanisms read the value:

1. `SourcePolicy.min_curation` — *"how checked it must be to count here"*. Planning
   writes rows requiring level ≥ N for a task.
2. The tie-break rule (§1.4, BINDING) resolves ties by **higher `curation_level`**
   before `issue_date`.
3. Obligation 6 requires the value be **honest**, which presupposes a shared meaning.

So if this platform publishes `1` for a regex-extracted, cited, unreviewed value
while Planning's policy rows were written assuming `0` covered that case, values
become admissible for structural tasks that both sides would have refused —
silently, at run time, with no error anywhere.

**Cost of leaving it.** Zero today; nothing publishes. It becomes expensive the
moment the first snapshot ships with a level on every value, because policy rows
will have been written against whatever we happened to choose.

**Possible dispositions**, in rough order of cheapness:

- Planning answers the question directly and it turns out to be settled on their
  side — no amendment needed, and `planning-asks.md` was the right venue.
- One clarifying sentence in §1.1 defining the scale. Trigger D, tiny.
- It was deliberately left to the publisher, in which case the fix is a note
  saying so, not a definition — and this platform declares its own mapping.

**Our current provisional reading**, so it is at least written down: `0` = extracted
by machine, uncited or unchecked; `1` = extracted by machine and carrying a
resolvable `SourceRef`; `2` = a person compared it to the source image. That
mapping is an assumption, not an agreement.

---

## C2 — `Warning.attaches_to.ref` is declared but never typed

| | |
|---|---|
| **Trigger** | **D**, weakly — possibly just an omission a note could close |
| **Raised** | 2026-08-25, building the first `Warning` |
| **Blocking?** | **No.** Batches. |

`knowledge-datamodel.md` §3.7 declares `attaches_to REQUIRED · { kind: step |
procedure | document | product | model | warranty | maintenance, ref }` and gives
`ref` no type. For `kind: document` the obvious value is the `SourceDoc.content_hash`;
for `kind: product` or `model` it would be an `EntityRef`. Both are guesses.

68% of warnings in this corpus are document-scoped, so this is the common case, not
an edge one. **Lower stakes than C1** — a wrong guess here produces a warning that
renders in the wrong place, not a structural value that is wrongly admissible.

Likely disposition: a note rather than an amendment. Worth carrying in the batch so
it gets an answer either way.

---

## C3 — is a `PanelSpec` member edge a "value"?

| | |
|---|---|
| **Trigger** | **D** — possibly; it may be settled and merely unwritten |
| **Raised** | 2026-08-25, deciding how the hand-researched dataset is treated |
| **Blocking?** | **No**, but it blocks *design* sooner than the others. Batches for now. |

Invariant 8 (`knowledge-datamodel.md`): *"Every published **value** carries a
resolvable `SourceRef`."* Invariant 10, same document: *"**Structure is authored,
not extracted.** No table reader produces a `PanelSpec`."*

Those two are not obviously compatible. If the *membership* edge — this component
belongs to this panel — counts as a "value", then structure needs a `SourceRef`,
and invariant 10 says no such reference can exist because nothing extracts it.
If it does not count, `Authorship` on structure is already legal and there is
nothing to amend.

**Why it matters now.** `docs/layering.md` §5 decides that the dataset's *values*
are curated as an ordinary source while its *composition graph* — 32 lines, 59
assemblies, 225 components — is retained as authored structure. That carve-out is
the only route to a `Part` at all, since no amount of curation over 2,147 pages
establishes that three particular components compose one Chesterfield panel. If
membership is a "value", the carve-out needs an amendment before it can be built.

**Likely disposition:** a clarifying sentence distinguishing an asserted quantity
from an authored relation. Cheap if it is only wording; expensive to discover
after Phase D is built either way.

---

## ~~C4 — no `GapKind` for "the authority explicitly does not extend here"~~ — STRUCK

**Struck 2026-08-27 (`conversation.md` T1→T2).** The premise held — a real footing
table does affirmatively exclude `(exposure_category=B, hvhz=true)`, confirmed
against source by Knowledge — but the fact does not need a new stable-core
`GapKind` to say so. `kind: uncovered_condition` + `domain_basis: measured`
already means "this table really does not cover that point," which IS "checked,
not a guess"; what was missing was only the WHY, and `because{code, params}` —
already a free registry addition per §2 — is exactly the field for that. Agreed
disposition: a new platform code, `parameter_condition_excluded`, carrying the
excluded point the same way `uncovered_parameter_point` already carries `point`.
Needs no amendment. **Implemented on Planning's side 2026-08-27** — the code is
in both locale bundles, guarded by `tests/web/test_locale_bundles.py`'s
`PUBLISHED_GAP_CODES` (codes rendered but never emitted by this engine's own
backend), and the corrected fixture's `(exposure_category=B, hvhz=true)` case
is now `FIXTURE-gap-excluded-1`, published directly rather than left in
`uncovered`. `parameter_condition_excluded` confirmed as the spelling in
`conversation.md` T4 (a).

<details><summary>Original entry, for the record</summary>

`uncovered_condition` means "no row covers this point" or "we may not know the
table's extent." Neither is the fact at `(exposure_category=B, hvhz=true)` in a
real footing table: both non-HVHZ rows are bracketed, and the approval simply
does not extend to HVHZ at exposure B. A planner reading `uncovered` there would
be told "may not know" when the true fact is "checked, and refused" — and would
be free to proceed as though a value might still turn up, which it structurally
cannot.

`GapKind`'s eight values are enumerated inline in the contract's stable-core text
(§1.2.1), not in the free registries (§2), so a ninth value reads as a trigger-D
defect amendment rather than a registry addition.

</details>

---

## C5 — `ParameterTable.value_type` cannot express a paired design point

| | |
|---|---|
| **Trigger** | **D** — real corpus data does not fit the closed `value_type` shape |
| **Raised** | 2026-08-27, same review as C4 |
| **Blocking?** | **No.** Neither side publishes `max_span_mm` against real data yet. Batches. |

A real footing/span table is not one value per `(exposure, hvhz)` point — it is
**two** design points per exposure, `(footing depth, max span)`, where a deeper
footing buys a wider span. `value_type: quantity(<UnitCode>) | token(<closed
set>)` — declared once, on the table — cannot express a pair, and `hit_policy:
unique` is violated by the real data as a result (two valid rows at one domain
point, no dimension to split them).

**Disposition flipped 2026-08-27 (`conversation.md` T1→T2).** Planning's original
preference — footing depth as an additional domain dimension — is withdrawn.
Measured against real corpus data, that shape turns one `unique` violation into
**8 of 18 cross-product artifacts**, several actively misleading (a footing
depth below what the table certifies at all reading as an ordinary coverage
hole). More fundamentally, `domain` per §2 is what Planning **binds from site
facts at run time** — footing depth is not a site fact, it is a design decision
a fence gets built to, the same category as choosing between two admissible
SKUs. **Agreed disposition: option (1), a paired/compound `value_type`.** Still
trigger-D — extends the closed `quantity(<UnitCode>) | token(<closed set>)`
union in the stable core — and still needs the amendment process; both sides
are willing co-authors. Worth batching with C1 if both are ready around the same
time, since both touch `Provenance`/`ParameterTable`.

Rejected by both sides: `hit_policy: collect_min`/`priority` over the two rows,
which silently discards the cheaper compliant option — one worked example, 7
posts vs. 9 on a 40 ft run at exposure C.

---

## C6 — no date format is declared, and a BINDING tie-break has to order dates

| | |
|---|---|
| **Trigger** | **D** — a binding rule depends on an ordering the contract never defines |
| **Raised** | 2026-08-30, on cutting the first real `ParameterTable` |
| **Blocking?** | **No.** Planning consumes no snapshot yet. Batches — but it stops batching the day they do. |

**The gap.** §1.4 is BINDING that a policy tie resolves *"by higher `curation_level`,
then later `issue_date`, then lexicographic `source_class`"*. Ordering by `issue_date`
requires knowing what an `issue_date` **is**. The contract types `source_class`,
`curation_level` and every `UnitCode`, and types no date at all — not `issue_date`,
not `expiration_date`, not `ParameterTable.rows[].valid_from` / `valid_until`.

**What this platform actually publishes** `[measured]`, snapshot
`3ae88642`: US-format slash strings, straight from the source document's own
stamp — `"04/24/2025"`, `"05/04/2023"`, `"03/13/2029"`. Three `issue_date` and
two `expiration_date` values in `source_docs`, and now `valid_from` /
`valid_until` on four `ParameterTable` rows, which is the field §1.4's tie-break
reaches through.

**What it costs to leave.** Lexicographic comparison — the obvious reading of a
bare string field, and the one §1.4 already names for `source_class` — orders
`"04/24/2025"` **before** `"05/04/2023"`. The 2025 document loses the tie to the
2023 one. §1.4's own sentence forbids exactly that outcome: *"never silently
preferring an older document."* And `"05/04/2023"` is ambiguous on its face; only
`"04/24/2025"` is self-disambiguating, and only by accident of the day number.

**Not merely this platform's bug to fix.** Publishing ISO-8601 unilaterally would
be the right internal change and would still leave the contract silent, so the
next producer of a date is free to differ. The fix is a typed `Date` in §1.1 —
ISO-8601 `YYYY-MM-DD`, with the source's own lexeme kept beside it where it
differs, the same shape `Quantity` already uses for `value_raw`.

---

## Not candidates — recorded so they are not re-raised

- **`retain_until` has no specified value.** The contract requires a snapshot
  *declare* one and deliberately does not fix it. That is a product decision for the
  operator, not a defect. Belongs in `planning-asks.md`.
- **Adding a curation level 3** (machine-consensus between agent-only and
  human-checked). Considered 2026-08-25 and **rejected**: renumbering an ordinal
  scale that policy rows already reference would silently weaken every existing
  row requiring level 2, with no diff anywhere to show it. Shipped instead as the
  registry addition `CURATION_MACHINE_CONSENSUS` — see `planning-asks.md` §3.3.
  Registry additions are explicitly not amendments.
- **Transport, framework, auth, pagination.** Explicitly unspecified by design.
  Never a candidate.
