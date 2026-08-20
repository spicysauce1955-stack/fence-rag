# Second-stage within-page element retrieval — evaluation and decision

```text
Status:   Implemented, measured, NOT accepted as default.
Verdict:  Rejected against the stated criterion. Retained behind an opt-in flag.
Criterion: unit support >= 0.70 with no reduction in document recall,
           page support, or no-answer precision.
```

## 1. What it does

The first stage ranks *units* — a projection that merges consecutive paragraphs
and excludes headings entirely. The relevance audit measured the consequence:
7,097 heading elements (33.9% of all headings) are reachable through no unit at
all, and 27 pages consist only of headings and figures and so are absent from the
index. A unit can therefore sit on exactly the right page while the element
naming the product, or holding the dimension, is not in it.

The second stage searches inside each page the first stage already chose, over
**all** canonical elements on that page including the excluded headings, and
attaches the elements that cover query terms the unit missed.

It is a retrieval-time addition. It reads canonical rows and touches no
classification, no indexing and no weighting, which is what allowed it to be
built while the audit is still under review.

```python
search_evidence("...", second_stage=True)   # default is False
```

Each result may carry `within_page_evidence`: a bounded list of elements, each
with its own `element_id`, text, `bbox`, region image, OCR confidence, and the
`adds_terms` it contributed.

## 2. Why it augments rather than replaces

Replacement was the first design and was measured first: pick the best element on
the page and return it instead of the unit. It made things **worse** — unit
support 0.540 against a 0.623 baseline. The reason is structural: a merged unit's
text covers more query terms than any single element, so swapping it out loses
evidence. Augmentation cannot lose anything.

## 3. Invariants, by construction and by test

The document set, page set, ordering, scores and result count are identical with
the second stage on and off. Document recall and page-level support therefore
*cannot* change; they are not measured hopefully, they are structurally fixed.
`tests/test_second_stage.py` asserts each one, plus: every attachment comes from
the same page, no attachment is reused within a result list, no attachment
duplicates a first-stage unit, attachments are bounded in count and characters,
each claims only terms the unit genuinely lacked, and at least one attachment per
run comes from an element absent from the index — proving it reaches canonical
rows rather than the projection.

## 4. Measurement

59 gold questions (41 answerable, 18 no-answer), k = 10, full corpus.

| Metric | Baseline | Second stage | Required |
|---|---|---|---|
| document recall@10 | 0.805 | **0.805** | not reduced — met |
| page evidence support | 0.769 | **0.769** | not reduced — met |
| no-answer precision | 0.333 | **0.333** | not reduced — met |
| false-unsupported rate | 0.146 | **0.146** | not reduced — met |
| MRR | 0.552 | 0.552 | — |
| **unit evidence support** | 0.623 | **0.672** | **≥ 0.70 — not met** |
| questions passing | 27 | 32 | — |
| attachments made | 0 | 130 | — |

Three of the four conditions hold exactly. The threshold does not.

### Variants measured along the way

| Variant | unit support | attachments | note |
|---|---|---|---|
| replacement, length damping 500 | 0.540 | 252 | worse than baseline; discarded |
| replacement, no damping | 0.627 | 189 | barely above baseline |
| augmentation, 1 attachment, no information floor | 0.678 | 315 | best number seen |
| augmentation, ≤2 attachments, no floor | 0.684 | 312 | plateau; ≤3 adds nothing |
| augmentation, ≤2, floor at df-share 0.30 (**kept**) | 0.672 | 130 | −0.012 support for 182 fewer junk attachments |
| augmentation, ≤2, floor at df-share 0.10 | 0.659 | 222 | — |
| augmentation, query-relative floor (½ of rarest) | — | 0 | disabled the mechanism outright |

The information floor exists because without it a common brand token missing
from the unit was enough to attach a phone number: on the Wellington query the
attachments were `TEL: (800) 336-2383`, `FREEDOM-WEB` and two warranty URLs,
each "covering" the missing term *freedom*. The kept setting requires an
attachment to contribute a term rarer than 30% of the index. On a technical query
the same mechanism attaches `MAXIMUM POST SPACING`, `MAXIMUM POST SPACING
WINDZONE™` and `Includes: Chesterfield, Chesterfield with CertaGrain® Texture` —
three headings, none of which is in the index at all.

Even at the most permissive setting measured, 0.684, the threshold is missed.

## 5. Why 0.70 is out of reach for this mechanism

The audit put the within-page ceiling at 0.769: that is what perfect selection
from an already-retrieved page would score. Of the 51 answer terms still
unreached after the second stage:

| Where the term is | Count |
|---|---|
| **not on any retrieved page** — a first-stage recall miss | **38** |
| in a heading on a retrieved page | 6 |
| in a paragraph on a retrieved page | 5 |
| in a table or drawing on a retrieved page | 2 |

Two conclusions follow.

**The dominant residual is first-stage recall, not within-page selection.** 38 of
51 misses are pages that were never retrieved. No within-page stage can reach
them, by definition.

**The remaining 13 are mostly not addressable from the query.** The benchmark
measures whether the *expected answer terms* appear in the returned evidence,
while any honest retrieval stage can only work from the *query*. For gq-102 the
missing terms are `Coarse Gravel` and `on-center`; both sit in small elements on
the retrieved page, and neither word appears in the question. Selecting them
would require knowing the answer. The gap is real, but closing it by targeting
answer terms would be training on the test, and the measurement would then mean
nothing.

## 6. Decision

**Not accepted as default.** `second_stage` stays `False`. The implementation,
its tests and this measurement are kept, so the work is not lost and the decision
is re-checkable.

What would change the answer, in order of expected effect:

1. **The audit's F1 recommendation** — project a heading as a unit when no unit
   beneath it carries it in `heading_path`. This attacks the 38-term first-stage
   deficit directly, which is the only lever large enough to move unit support
   past 0.70. It is an indexing change and is therefore held pending review of
   `workspace/reports/projection-relevance-audit.md`.
2. **The audit's F2/F3 recommendations** — duplicate suppression and a per-page
   result cap. 29.5% of top-10 slots currently hold text duplicated elsewhere and
   20.2% repeat a page already in the list, so a 10-result list averages 7.98
   distinct pages. Recovering those slots is recall the second stage can then
   exploit.
3. **Re-running this measurement afterwards.** The second stage should be
   re-evaluated once the projection changes land, because its headroom is defined
   by what the first stage retrieves. It may pass then without any change to
   itself.
