# Integration — the boundary with Planning & BOM

```text
Status:    v0.4. Three review rounds done. Four items await this team's
           agreement; everything else is settled or internal to Planning.
Authority: Binding ONLY at the boundary. Silent on everything inside it.
Origin:    Proposed by Planning & BOM; audited by Knowledge; revised by both.
```

A separate system — **Planning & BOM** — turns a customer's map into a plan and a bill
of materials, and it needs the knowledge this platform produces. These documents describe
the boundary: what crosses it, in what shape, and what each side promises the other.

---

## Start here

| If you are… | Read |
|---|---|
| **Deciding whether to approve v0.4** | [`boundary-delta-v0.4.md`](boundary-delta-v0.4.md) — four items, one page, nothing else in it |
| **New to this** | [`system-overview.md`](system-overview.md), then [`knowledge-datamodel.md`](knowledge-datamodel.md) §0–§3 |
| **Checking a promise** | [`contract.md`](contract.md) — eighteen BINDING obligations; nothing else binds |
| **Planning your sprint** | [`planning-asks.md`](planning-asks.md) — what Planning needs, ordered by cost if late |
| **Wondering why a decision went that way** | [`audit/`](audit/) — every round, with the evidence |

---

## Current documents

| Document | Answers |
|---|---|
| [`boundary-delta-v0.4.md`](boundary-delta-v0.4.md) | **The open ask.** The four v0.4 items needing agreement, and what to check on each |
| [`contract.md`](contract.md) | What crosses the boundary, and the promises each side makes |
| [`knowledge-datamodel.md`](knowledge-datamodel.md) | Every entity, field, relationship and invariant, with a traceability map from each audit finding |
| [`planning-asks.md`](planning-asks.md) | What Planning needs from this platform, ordered by impact |
| [`source-refs-design.md`](source-refs-design.md) | `GET /source-refs/{id}` — the design, with [`fixtures/`](fixtures/) |
| [`system-overview.md`](system-overview.md) | What is being built overall, and where this platform sits in it |
| [`knowledge-design.md`](knowledge-design.md) | How this component fits — what it publishes, the workflows, what stays private |
| [`rationale.md`](rationale.md) | Why each binding item exists — mostly measured from this store |

## The audit trail — [`audit/`](audit/)

Kept in order, because a later disagreement is usually a re-run of an earlier one.

| | |
|---|---|
| [`00-datamodel-v0.1-superseded.md`](audit/00-datamodel-v0.1-superseded.md) | The original proposal, unedited. Its §7 is what round one answered |
| [`01-audit-response.md`](audit/01-audit-response.md) | **Knowledge's answer**, measured against the corpus — a document path, page and verbatim quote behind every claim |
| [`02-audit-disposition.md`](audit/02-audit-disposition.md) | **Planning's decision** on all 29 items: 24 as written, 3 modified, 2 decided, none rejected |
| [`03-review-of-v0.2.md`](audit/03-review-of-v0.2.md) | **Knowledge's review** of the revision: six defects that blocked authoring |
| [`04-review-disposition.md`](audit/04-review-disposition.md) | **Planning's response.** All six fixed; one of its questions found a bug in the engine |
| [`05-acceptance-open-questions.md`](audit/05-acceptance-open-questions.md) | Knowledge's working list — everything needing a decision, and what "done" means |

---

## How the boundary got to v0.4

Each round checked the design against a different **substance**, and each found what the
previous could not:

| Round | Checked against | Found |
|---|---|---|
| 1 · audit | this platform's **corpus** — 144 documents, 81,794 elements | 29 items. Seven of ten §7 questions surfaced a change; one invariant was falsified |
| 2 · review | the revision, read by a **second party** taking §8 literally | 6 defects that blocked authoring — including a mechanism argued for and then omitted |
| 3 · self-audit | Planning's own **codebase** | 7 more, two in code already published here. Then 6 more, every one in something Planning had *added* rather than accepted |

**The lesson, worth keeping.** After round two the design was internally consistent and
the engine could not implement it. Coherence is not the test — a design has to be checked
against a substance outside itself, and each substance catches a different class of error.

---

## How this relates to your own documents

`CLAUDE.md` gives an authority ordering: `mvp-implementation-spec.md` is authoritative,
`guide.md` is the contract it implements, `target-architecture.md` is informative,
`state-and-gaps.md` is the measured snapshot. **Nothing here displaces any of those.**

- Those documents govern **how this platform works**. They remain the authority.
- These govern **what it exposes to a consumer**, and nothing else.

**`docs/curation/` is not superseded by any of this.** It sits in tier 3, both teams have
read that as settled, and it remains this team's internals. Where a document here appears
to say something about your internals, it is wrong and should be read as advisory.

## Not specified here

Storage engine and schema. Whether claims live in one table or twenty. Extraction
pipeline, models, OCR strategy. How a review queue is ordered and what the reviewer sees.
Whether curation runs as a CLI, a batch job or a service. Language and runtime beyond the
API shape. Retrieval implementation. Release cadence.

## The one thing worth reading first

The consumer is a **pure function**. Given the same project and the same knowledge it
produces the same plan, provably, years later — including with this platform unreachable.
That property explains most of what the contract asks for, and in particular why
knowledge is fetched as one immutable, content-addressed object *before* a run rather
than queried during one.

Its corollary is an obligation on Planning, not on you: **a missing role, an uncovered
condition or an unsatisfiable requirement produces a plan with a named, warned line —
never a failed run.** A gap you publish does not break anybody, and a snapshot containing
very little is still a valid snapshot.
