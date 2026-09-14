# What survived the ruler change — an audit of conclusions measured on `query_terms`

```text
Status:   A MEASUREMENT and a triage, not a change. Written 2026-09-14 after
          `evaluate` began grading the natural question (PR #7). Four decisions were
          re-measured on the honest column; the rest is classified, not re-run.
Authority: None. This document records what is now in doubt so that the next session
          does not cite a retired number. `docs/state-and-gaps.md` remains the record.
Read first: `docs/coverage-remediation-plan.md` §1 for why the ruler changed.
```

---

## 0 · The premise

`evaluate._query_for()` preferred a gold question's hand-written `query_terms` over the
question itself, and all 79 gold questions carry them — while `query.py` sends
`situation.question` unchanged. **Every retrieval figure this project has published was
measured on an instrument production never uses.**

`[measured]` 2026-09-14, identical configuration, both columns:

| | recall@10 | evidence support | no-answer prec. | false-unsup. |
|---|---|---|---|---|
| keyword hints (every historical figure) | 0.805 **pass** | 0.695 | 0.324 | 0.146 **pass** |
| natural question (graded) | **0.756 fail** | **0.653 fail** | 0.486 fail | **0.390 fail** |

**No test anywhere asserts a retrieval threshold.** The gate lives in
`evaluate.acceptance_flags` and is *reported*, never asserted — which is why nothing went red
for the project's whole life.

## 1 · The four decisions, re-measured

Three of the four **stand**. That is the important result: the conclusions were mostly right.
What is wrong is the *recorded reasoning*, which is what the next session reads.

| Decision | Verdict | On what grounds |
|---|---|---|
| **Second stage** — rejected for missing 0.70 by 0.0054 | **REVERSED** | Shipped in PR #7. The 0.0054 was a keyword-column number; the honest gap is 0.047. |
| **R3** — cross-document dedupe, shipped on | **STANDS** | Structural, not statistical — see below. |
| **R5** — per-page cap, rejected | **STANDS** | Risk reproduced verbatim; but the recorded figure does not. |
| **R1** — heading re-admission, rejected | **MOOT** | Superseded by the shipped second stage. |

### R3 stands, and my own criticism of it was wrong

`docs/coverage-remediation-plan.md` §2 accused this project of applying "two different
evidentiary standards in opposite directions" — shipping R3 on a weak delta while rejecting
the second stage on a 0.0054 miss. **That accusation is withdrawn.** G64 states in as many
words that R3 was accepted on a proved structural property and the `duplicates_suppressed`
fix, *"not the 0.022"*. Re-verified on the honest column: **144 suppressed rows, 0 unreachable
documents, 0 unreachable elements.** That property is instrument-independent.

R3 also looks *better* on the honest ruler than the keyword column made it look: support
+0.041 (against +0.022), recall@10 +0.024 and MRR +0.011 where the keyword column reported
both flat, and **3 questions improve, 0 regress**. Its confidence interval crosses zero only
because 38 of 41 deltas are exactly 0.0 and all three non-zero ones are positive — a t-interval
on a distribution bounded below by zero is the wrong instrument.

### R5 stands, but its recorded basis does not reproduce

G64 cites *"−0.062 support, 8 worse and 2 better, sign test p ≈ 0.06"*. That was measured
against an **R3-off** baseline. Against what actually ships: 1 better / 4 worse, p = 0.375 —
the significance was already gone before the ruler changed.

The rejection survives on two grounds that do not depend on any ruler. The stated risk
reproduces exactly — all five honest-column regressions are one page holding two genuinely
distinct answers, and `gq-006` loses the **130 MPH** rows while keeping 120 MPH, which is the
condition the question asks for. And R5 targets within-document repetition (5.5% of top-10
slots) while the duplication that spends slots is cross-document (35.4%), which R3 already
handles. Unlike R3, **a capped row is not linked back** — so discarded evidence is
unreachable, which is how `gq-006` lost its governing load silently.

### R1 is moot

Its rejection was mechanism-based — the index doubles to 21,998 rows, median unit length falls
99 → 27 chars — and mechanism survives an instrument change. Measured on the honest column the
top ten is *less* exposed to short units, not more (7.4% vs 10.9% of slots under 40 chars).

Decisively, **the shipped second stage already does R1's job**: 147 heading attachments across
the gold set, 86 of them rows R1 would literally have minted, contributing +0.0081 support.
And it fixes `gq-103` — one of the two questions the audit blamed on the heading hole, and one
G51 showed R1 **could not fix by construction**. The audit predicted this in its own §5.

Residual R1-only gap: **27 pages with no retrievable unit at all.** None appears in any gold
question, so it is invisible to every metric. A targeted fix — project a unit for a page that
would otherwise have none — is far narrower than R1 if it is ever wanted.

## 2 · The gold set is itself unaudited, and this is the deeper problem

**15 of 78 questions leak an answer term into their own search terms** — a string in
`query_terms` that is also an `expected_answer_term` and does **not** appear in the question:
`gq-101` (`BL19110`), `gq-003`/`gq-012` (`24-0729.04`), `gq-121` (`ST001`), `gq-013`
(`12-048`), `gq-021` (`17.71`), `gq-022` (`42485`), `gq-010` (`GOVERNING LOAD`), plus
gq-105, gq-120, gq-008, gq-009, gq-011, gq-016, gq-019.

Since support is the fraction of answer terms found in returned text, **searching with the
answer guarantees the hit**:

| | keyword support | natural support |
|---|---|---|
| the 15 leaking questions | **0.793** | 0.529 |
| the 26 non-leaking | 0.638 | **0.724** |

**The entire published support advantage of the keyword ruler is answer leakage.** On
questions that do not leak, the plain question scores better.

A further 12 questions have terms that actively misdirect. `gq-121`'s `ST001` appears nowhere
in its expected document and drags search to the wrong catalogue year. `gq-102`'s `73013822`
is absent from the expected sheet. `gq-006` is pulled to a **chain-link** guide — a different
product family. `gq-011` names the **superseded** NOA `23-0314.05`, which is how the routed
block came to record *"search cannot find this"* as routing's justification.

**Consequence: re-measure nothing else until `query_terms` are either repaired or formally
demoted to documentation.** Both rulers are being read on an answer key nobody has audited.

## 3 · Two live defects, not history

**Fixed here:** `audit.py` called `_query_for(q)` with no form, so the next `cli audit` would
have re-published keyword numbers into `projection-audit.json`. It now passes
`GRADED_QUERY_FORM`. Note this means the committed `projection-relevance-audit.md` figures
will move when it is next run — F2 measures **35.4%** on the honest ruler, not the recorded
29.5%.

**Not fixed — needs its own item.** The no-answer detector's collapse (false-unsupported
0.146 → 0.390) is substantially a **tokenizer defect**, not a corpus result. `_looks_unsupported`
fires when any query term has document frequency 0, and `retrieval_fts` uses `unicode61` with
no stemmer: `veka's` df=0 while `veka` df=58; `expire` df=0 while `expires` df=368; `drops`
df=0 while `drop` df=138. **16 of 41 answerable questions are declared unsupported this way.**
The keyword column concealed it because an annotator copies the corpus's own surface forms.
`evaluate.py`'s docstring — *"fires only for a reason a reader can check: the query contains a
word the corpus does not contain anywhere"* — is false as written. Cheapest recovery: strip
possessives and require df=0 under a stem before firing.

## 4 · The prohibition-9 question

`guide.md` forbids a vector or graph database *"until a measured failure category justifies
it"*. `docs/target-architecture.md` names the trigger explicitly: *if BM25 alone already
answers the paraphrase set, dense retrieval is not built.*

`[measured]` paraphrase, keyword → natural: doc-hits **3/5 → 1/5**, mean support **0.6 → 0.2**.
It is now the weakest answerable category.

**The trigger has arguably fired. Do not act on it yet.** n = 5. Five questions cannot justify
a vector store, and prior research put the achievable gain at roughly two questions. More to
the point, the gold set is the instrument under suspicion (§2). **Repair the gold set, then
re-measure paraphrase, then decide.** Recorded here so the refusal is re-examined on evidence
rather than inherited.

## 5 · What survives untouched

Everything that never issued a query: the projection censuses (F1's 33.9% of headings
reachable nowhere else — re-measured 34.0%, store churn not instrument; F4–F8), corpus facts
(supersession lineage, OCR confidence, document text), determinism and equivalence assertions
(rebuild byte-identity, routing additivity, D6's zero differences), and the grading rules
(G65's unrounded means; reporting both no-answer metrics together).

## 6 · What is overturned

Every acceptance figure, category breakdown, no-answer statistic and tuning-variant table in
`state-and-gaps.md`, `phase-checkpoints.md`, `second-stage-evaluation.md` and
`projection-relevance-audit.md`, plus the baselines pinned to Planning in
`conversation.md`. None reproduces. Specifically worth correcting when touched:

- **Phase 4's completion** rested on recall@10 ≥ 0.80. It is 0.756.
- **"conditional table lookup is the weakest category"** — it is not; on the honest column it
  is 6/7 with support 0.762. The weakest are **paraphrase** (0.2) and **conflict** (0.298).
- **The within-page ceiling** that justified further projection work: 0.769 → **0.697**, i.e.
  *below* the 0.70 target it was supposed to make reachable.
- **Three documents still record the second stage as rejected.** It ships.

## 7 · What to do, in order

1. **Audit and repair the gold set** (§2). Nothing else is worth measuring first. Either fix
   the 15 leaking questions and the 12 misdirecting ones, or demote `query_terms` to
   documentation and delete the column.
2. **Fix the no-answer tokenizer defect** (§3). 16 of 41 questions are affected and it is a
   contained change.
3. **Re-run `cli audit`** and correct `projection-relevance-audit.md`'s figures.
4. **Re-measure paraphrase** and settle prohibition 9 on evidence (§4).
5. Correct the overturned figures in the four documents named in §6 *when they are next
   touched* — not as a sweep, which would be a large diff carrying no new knowledge.
