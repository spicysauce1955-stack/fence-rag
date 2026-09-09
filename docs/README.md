# `docs/` — what is here, what governs, what is history

```text
Index rebuilt 2026-09-08, after a five-way audit of every document in this tree.
Every "state" line below was measured on that date against the store and the code.
```

**Start with [`knowledge-loop.md`](knowledge-loop.md).** It says what the project is for.
Everything else describes a part.

---

## The four that govern

| Document | Governs | Status |
|---|---|---|
| **[`knowledge-loop.md`](knowledge-loop.md)** | **Purpose and direction** — what we are building and why | **Agreed 2026-09-08.** Not frozen; correct it when wrong |
| [`integration/contract.md`](integration/contract.md) | What crosses the boundary to Planning/BOM | **FROZEN v1.3**, hashed. Never edit — see `integration/AMENDING.md` |
| [`integration/AMENDING.md`](integration/AMENDING.md) | How the contract changes | **FROZEN**, hashed |
| [`mvp-implementation-spec.md`](mvp-implementation-spec.md) | How this platform works internally | Authoritative for extraction, store, retrieval, prohibitions. **Superseded for scope** — see its §1a |

Verify the frozen pair: `cd docs/integration && sha256sum -c contract.sha256` — both lines must
print `OK`.

## The three you read to know where things stand

| Document | What it is |
|---|---|
| [`state-and-gaps.md`](state-and-gaps.md) | The measured record, G1–G112. **Trust its numbers over any prose, including this file's.** Large; no index; gaps are not in numeric order |
| [`integration/conversation.md`](integration/conversation.md) | The negotiation transcript with Planning, T1–T55. **Live boundary state lives in its per-turn ledgers** |
| [`build-plan.md`](build-plan.md) | Build sequencing. Phases A–E done; §6's ordering is superseded on priority by `knowledge-loop.md` §10 |

## Live working documents

| Document | What it is |
|---|---|
| [`naming.md`](naming.md) | Every name this project mints. **Decided 2026-09-09** and worked the same day — six defects closed, one filed as amendment 011, one put to the owner as a migration plan, and four of its own figures corrected. Nine checks in `tests/test_naming.py` and `tests/test_gold_set.py`; §11 lists what stays unenforced and why |
| [`review-status-migration-plan.md`](review-status-migration-plan.md) | **A PLAN, not a change.** `naming.md` E-3: one column name over four vocabularies. Measured matrix, blast radius, four costed options, and the correction that the defect is not currently producing a wrong curation level. Needs the owner's decision, because every option but the recommended one writes to rows that do not regenerate |
| [`layering.md`](layering.md) | Five layers and one rule — *every reference points down, never up*. The rule is **decided and enforced** by a test; the vocabulary is proposed. §2a carries the hard/soft overlay |
| [`workflows/source-to-contract.md`](workflows/source-to-contract.md) | How new knowledge actually gets published today. The most current document in this tree |
| [`assembly-step-design.md`](assembly-step-design.md) | `Procedure`/`AssemblyStep`. **Built** — the blocker is 91 unreviewed candidates, not code |
| [`integration/knowledge-datamodel.md`](integration/knowledge-datamodel.md) | The entity shapes. The one boundary document a newcomer needs |
| [`integration/registry-additions.md`](integration/registry-additions.md) | The live vocabularies — source classes, warning codes, `curation_level` |
| [`integration/source-refs-design.md`](integration/source-refs-design.md) | §4.2/§4.3 are normative and implemented. §1's `sref_` scheme was never built |
| [`integration/amendments/`](integration/amendments/) | 001–008 and **011**, plus `CANDIDATES.md` (C1–C17). The reasoning behind every contract change. **009 and 010 are agreed and still unfiled** — 011 was numbered around them, not over them |
| [`target-architecture.md`](target-architecture.md) | Informative future direction. §5.2 — *conflicts surfaced, never resolved* — is load-bearing |
| [`distribution-design.md`](distribution-design.md) | How a checkout obtains the corpus. Implemented and accurate |
| [`second-stage-evaluation.md`](second-stage-evaluation.md) | A measurement and a decision not to ship. Does not expire |
| [`project-contract-alignment-review.md`](project-contract-alignment-review.md) | 2026-09-06 review. Self-labelled historical, but carries **two unclosed defects** in the procedure builder |

## History — read for reasoning, never as a work queue

Each of these carries a banner explaining what happened to it.

| Document | Why it is history |
|---|---|
| [`phase-checkpoints.md`](phase-checkpoints.md) | Accurate to 2026-08-28 and stops dead there |
| [`four-layer-model-design.md`](four-layer-model-design.md) | Plans 1–2 shipped; plan 3 (`claims`) was never built. §5.1 is now **blocking** |
| [`four-layer-plan-1-refs.md`](four-layer-plan-1-refs.md) | Executed. Its 33 unticked boxes all shipped |
| [`experiment-noa-table-reading.md`](experiment-noa-table-reading.md) | The method it designs was never built; LLM reading filled the queue instead |
| [`curation/`](curation/) | The `cur_*` schema was never built. Three of its ideas shipped under other names; `emblem-*.md` are build logs misfiled here |
| [`superpowers/specs/`](superpowers/specs/) | Session designs. The review loop shipped in full; the LLM-extraction file became a diary |
| [`integration/where-we-stand.md`](integration/where-we-stand.md) | The state file the conversation thread replaced |
| [`integration/knowledge-asks.md`](integration/knowledge-asks.md) · [`planning-asks.md`](integration/planning-asks.md) | A completed round-trip. **One open item** survives in knowledge-asks §2.3 |
| [`integration/boundary-delta-v0.4.md`](integration/boundary-delta-v0.4.md) | A closed approval request |
| [`integration/audit/`](integration/audit/) | The ordered reasoning behind every boundary decision. Immutable record |
| [`../guide.md`](../guide.md) | The setup instructions that built this repo. **Live content: the twelve prohibitions** |
| [`../rag-pipeline-plan.md`](../rag-pipeline-plan.md) | The original plan. Correctly self-labelled since 2026-08 |

---

## Traps this tree has set before

- **Colliding id namespaces — CLOSED 2026-09-09, and worth knowing about because
  the fix moved 134 citations.** `[measured]` there were five: `R` meant a retrieval upgrade
  (`target-architecture.md` §3), an audit *recommendation*
  (`workspace/reports/projection-relevance-audit.md`), **or** a curation acceptance criterion
  (`curation/05`); `F` an audit defect or a curation floor criterion; `C` an amendment candidate
  or a curation stage — and `CLAUDE.md` used both senses ~~nine~~ **31** lines apart
  (`[measured]` lines 101 and 132; the "nine" was copied between this file and `naming.md`
  rather than counted in either); `A` a build-plan item or a curation group. **The curation
  schemes now carry a `CUR-` prefix** — stages `CUR-S0`…`CUR-S8`, and `CUR-P*` / `CUR-F*` /
  `CUR-R*` for the three acceptance groups. The audit, target-architecture, build-plan and
  amendment-candidate schemes are unchanged, and `curation/05`'s compound `C-A1` form is
  unchanged too, being the precedent. There is **no automated guard** and `naming.md` §9 says
  why: every pattern loose enough to catch a bare id also catches Cloudflare's `R2_BUCKET`, the
  ASCII `C0` range, a PDF `/F1` key and the NOA item code `P1`. `naming.md` §9 has the rule.
- **"Contract" means two things.** Since 2026-08-25 it means `integration/contract.md`. Older
  documents use it for the search *response* shape.
- **Counts drift fast.** Corpus is **146** files (137 PDF, 6 PNG, 2 HTML, 1 DOCX) — but the
  distribution manifest still lists 144 and carries no HTML, so `cli fetch` alone no longer
  reconstructs the corpus; the two HTML sources ship in git.
- **A status line saying "nothing here is implemented" is not evidence.** Four documents said it
  about code that had shipped. Check the module before believing the banner.
