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
