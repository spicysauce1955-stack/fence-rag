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

## 6a · Settled 2026-09-14 — the gold set repaired, and three code defects filed

**The keyword column is retired.** `query_terms` stays in the gold files as the annotator's
record of salient terms; nothing computes a metric from it, nothing searches with it, and
`_query_for` takes **no `form` argument** — a seam with a keyword default is exactly how
`audit.py` shipped a caller measuring the wrong thing for weeks. The column could not be made
trustworthy by construction: whoever writes search terms for a question already knows its
answer.

**Repairs made** (evidence in the commit; every one re-verified against the store):

| what | why |
|---|---|
| `gq-004`, `gq-019` → `noa-24-0117.05` p17 | both ask what is **in force**; the store marks 23-0314.05 superseded with four `superseded_by` edges. **recall@10 0.7561 → 0.8049 — A3 passes**, because these questions were marking the *correct, current* document wrong |
| `gq-002` drop p16, `gq-015` drop p1 | the page carries **none** of its question's answer terms |
| `gq-233` near-miss → absent-subject | `st101` df 0 and no element hit; the corpus carries ST1001 |
| `gq-215` absent-subject → adjacent-vocabulary | `pet` df 9, `dog` df 69 — only the compound is absent |
| `gq-116/117/118` classified | three negatives outside the dedicated file carried no class, and `test_gold_set.py` only polices that file. **All 37 are now classified: 13 adjacent-vocabulary, 13 near-miss, 11 absent-subject** |

**Deliberately NOT repaired — the annotation is right and the store is wrong.** Repairing
these would hide an extraction defect behind a corrected answer key:

- `gq-104` — `Cross Buck Fence Gate Installation Guide` is printed on page 1 and reaches the
  store as two elements reading `weatherables`. The title is unreachable anywhere.
- `gq-110` — the source prints `285 lbs`; table extraction truncates the column to `285`.
- `gq-018` — the CAD drawing prints `72"`; OCR reads `12"`. The question's own
  `verification.notes` claim the term "comes through"; **the store falsifies that note**.

**Left for the owner**, flagged not decided: `gq-009` and `gq-122` (is "the current
**CertainTeed** NOA" the superseded CertainTeed-branded one, or the Barrette successor?);
`gq-015`'s "two live NOAs" premise (the store marks 22-0217.05 superseded with no supersession
relations); `gq-228` and `gq-204`.

### Three code defects found while repairing, none fixed here

1. **`evidence_support` is credited from documents that are not the expected one.**
   `evaluate.py:242` joins `_returned_evidence` over **all ten results**, while the
   element-type and image checks at `:269`/`:274` are scoped to `expected_docs`. Consequence:
   `gq-004`, `gq-009` and `gq-019` each scored a perfect **1.0 with `doc_rank: None`** — their
   terms are NOA boilerplate any sibling sheet supplies. **The headline support number credits
   evidence from the wrong document.** Fixing this will move 0.6528 downward and is the single
   most important outstanding change to the instrument.
2. **Term matching is an unanchored substring test.** `_norm(term) in joined`, so `88` matches
   inside `1988` and `12` inside `73011754`. Roughly a dozen terms across eight questions are
   bare two-digit numbers or corpus-wide boilerplate (`CONCRETE` df 717). Anchor on word
   boundaries, or require the unit-bearing form (`36"`, `140 lbs`).
3. **`expected_element_type` names types the store can never return** for 9-11 questions —
   `gq-101` wants `heading`, which is excluded from `retrieval_units` by design; `gq-004/009/017`
   want `table` on a scanned drawing sheet that has none. It is scored at `:264`.

**And the annotation is not where the deficit lives.** Of 160 answer terms, 76 are ANSWER,
61 LOCATOR, 3 UNVERIFIABLE, 20 borderline. Re-scoring on ANSWER terms only moves support
0.6528 → **0.7105** — annotation accounts for about **17% of the gap**. The questions scoring
0.0 do so because the expected document was never returned, and no re-annotation rescues those.

### A4 and A4b are the same rule, and the target is unreachable as annotated

`no_answer_precision` is exactly *"the fraction of negatives containing a df-0 token"* —
18 of 37 fire, and 18/37 = 0.486, the reported figure to three decimals. **7 of those 18
detections (39%) rest on a morphological artifact**, not on absence: `carry` (df 0, `carrying`
6), `e84` (df 0, `"e 84"` 6), `e90` (df 0 while the corpus prints `STC 21`), `concrete-filled`,
`tightened`. True *semantic* precision is **0.297**, not 0.486.

0.66 requires 25 of 37 flagged. Only 11 questions carry a genuinely absent token; reaching 25
means firing on 14 of the 26 questions whose defining property is that *every word occurs* —
which `_looks_unsupported`'s own docstring says no lexical feature can separate. **Fixing the
tokenizer moves A4b toward its target and A4 away from its own**, to roughly 0.35. The two
gates are in direct conflict. Either A4 is renegotiated against the corrected class mix, or
the detector needs a signal that is not term presence.

## 7 · What to do, in order

1. ~~**Audit and repair the gold set**~~ — **DONE 2026-09-14**, see §6a. `query_terms` demoted,
   the keyword column retired, six questions repaired, three code defects filed.
2. **Scope `evidence_support` to the expected documents** (§6a defect 1). The headline number
   currently credits evidence from the wrong document; three questions score 1.0 having
   retrieved nothing expected. Nothing else about support means anything until this lands.
3. **Fix the no-answer tokenizer defect** (§3), and settle A4 against the corrected class mix
   at the same time — the two gates are one rule and cannot both be satisfied by tuning it.
3. **Re-run `cli audit`** and correct `projection-relevance-audit.md`'s figures.
4. **Re-measure paraphrase** and settle prohibition 9 on evidence (§4).
5. Correct the overturned figures in the four documents named in §6 *when they are next
   touched* — not as a sweep, which would be a large diff carrying no new knowledge.
