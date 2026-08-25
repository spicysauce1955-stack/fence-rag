# Why the contract looks like this

```text
Status:  Informative. Nothing here is binding.
Sources: Every measurement is from this repository — evidence.db queried
         directly on 2026-08-23, docs/state-and-gaps.md, and the curation
         capability matrix. Two cross-references come from the Planning repo.
```

The contract asks for a handful of specific things. Each of them exists because of a
failure that is already present in this store or already documented in it. This document
records which, so the asks can be argued with on the evidence rather than on taste.

---

## 1. Why conditions must ride with the value, and why `unknown` must block

`facts` holds a row that is, today, promoted:

```text
fact_type    footing_depth_in
value        24"
conditions   { fence_height: "Up to 48\"",
               exposure_category: "B",
               hvhz_applicability: "unresolved",
               _applicability_basis: "readers did not independently agree on
                                      the applicability bracket" }
review_status  cross_family_verified          ← promoted, no person involved
source       NOA-22-0616.10-CertainTeed-SimTek-molded-fence-
             2022-2028-superseded.pdf
               version_status  superseded
               product_family  SimTek (molded/composite, not extruded PVC)
```

Three independent disqualifiers in one promoted row. The approval is superseded. The
product family is molded composite, explicitly distinct from the extruded-PVC line. And
the hurricane-zone bracket is unresolved — which the reader recorded honestly and the
promotion rule then ignored.

A consumer reading `facts` directly would pour a SimTek footing under a Bufftech fence on
the authority of an expired document.

This is the same class of failure as G16, where an Exposure B row bracketed `NON HVHZ` on
the page was recorded as *"HVHZ and Non-HVHZ"* — one condition dropped, licensing a 24″
footing in a high-velocity hurricane zone.

**What the contract asks for as a result:** conditions travel as structured rows on every
value, `curation_level` is honest, and the source policy can require level 2 for
structural tasks. An operator of `unknown` on a required dimension should block acceptance
rather than pass quietly — this is `docs/curation/` §2.5.2's existing position and the
contract simply depends on it.

---

## 2. Why `hit_policy` and `domain` are required

Both of these are in `facts` now, for the same parameter under the same conditions:

| Spacing | Exposure | HVHZ applicability |
|---|---|---|
| 97″ | B | `unresolved` |
| 97″ | B | `non-HVHZ only` |

Same value, same condition tuple, opposite resolutions of the safety-critical bracket.

Without a declared hit policy, two rows covering the same input point is a silent bug:
whichever one the consumer's precedence happens to pick becomes the answer, and a
different evaluation order gives a different bill of materials. With `hit_policy = unique`
declared, it is a **build error at publish** — days earlier, and in front of the person who
can resolve it.

`domain` earns its place for the opposite reason. The full set from Table 1 is six rows:

| Spacing | Exposure |
|---|---|
| 97″ | B |
| 88″ | C |
| 75″ | D |
| 68″ | C |
| 66″ | B |
| 56″ | D |

Whether an HVHZ site at Exposure D is covered is not answerable from that list alone. It
is answerable if the table declares the space it is meant to cover. Uncovered points then
become gaps rather than silence — which matters, because silence reads to a consumer as
coverage.

---

## 3. Why every value needs a resolvable image, not just a page citation

Page-and-table granularity is enough when the table is a table. Measured here, it often
is not:

- The five approvals carry **one `table` element between them** — a 4×3 OCR word grid, and
  not a Table 1 wind/exposure grid.
- Blind manual verification of the 44 distinct pages flagged `table_not_reconstructed`
  measured digit-bearing value recall at **0.588**. OCR reads the words on those pages and
  loses the numbers, and the numbers it loses are the footing depths and maximum post
  spacings.
- 73 pages carry a `table_not_reconstructed` issue; 300, 400 and 500 dpi renders all
  produce roughly the same ~50% mean confidence.

So the load-bearing values have no element, no bounding box and no quotable text. They
exist only as pixels. A `SourceRef` that cannot resolve to an image cannot be checked by
the person being asked to accept the value — which is why the contract treats a visual
reading as a first-class kind rather than a row with columns nulled out.

**One thing the contract is careful not to claim.** A source reference proves *where the
system looked*. It does not prove that the source says what was written down. Those are
different guarantees, and the frontend obligation exists to stop them being conflated in
the interface.

---

## 4. Why a review gate, and why it is not absolute

The store's current position: **1,652 facts, none reviewed by a person.** Until
2026-08-25 it was 1,988, of which 324 had been promoted automatically on cross-family
agreement. That mechanism is gone — `table_review.PROMOTABLE` is now `("accepted",
"corrected")`, `state-and-gaps.md` G17 records the change, and what `docs/curation/` C0
proposed landed on its own as build-plan A1. **The level-2 population is zero**, which is
the honest number until human review begins.

That justifies a gate. But an absolute gate would make the whole system unusable before
curation has run, and would couple the two teams' schedules together — a consumer that
cannot plan until this platform's queue is drained cannot be built in parallel with it.

Hence the compromise in the contract: unreviewed values may enter a snapshot carrying an
honest `curation_level`, and the source policy decides where they may actually be relied
upon. Structural tasks default to requiring level 2. A descriptive value at level 0 flows
and produces a warning.

**The throughput problem is worth naming explicitly**, because it is the documented way
this class of project fails. Google's Freebase import into Wikidata was largely accurate
and stalled anyway: every candidate needed a person, and there were always more candidates
than hours. The escape that has worked elsewhere — UniProt's rule-based propagation — is
that a review produces a *pattern* rather than a single approval, so one reviewed reading
of a templated table promotes its whole family. This corpus is unusually well suited to
that, and it is why the contract carries `curation_level` rather than a boolean: it needs
to distinguish "a person checked this instance" from "a person checked the pattern this
came from."

Nothing in the contract requires a particular mechanism for that. It only requires that
the level reported is honest.

---

## 5. Why parameters cross as tables rather than values

From the Planning repository, two of the twelve rules the engine actually evaluates today:

```text
K-MAXSPAN     SetParam{max_span_mm: 1800}   type=hard_constraint
                                            attributed_to="manufacturer"
K-POST-EMBED  SetParam{post_embed_mm: 600}  type=fact  (no attribution)
```

`attributed_to="manufacturer"` is a string. Which manufacturer, which product, which
exposure category, which document — unanswerable.

Set that single constant against the six conditional rows above:

| Documented | mm | Against the engine's 1800 |
|---|---|---|
| 97″ / B | 2464 | engine stricter by 664 mm |
| 88″ / C | 2235 | engine stricter by 435 mm |
| 75″ / D | 1905 | engine stricter by 105 mm |
| 68″ / C | 1727 | engine **more permissive** by 73 mm |
| 66″ / B | 1676 | engine **more permissive** by 124 mm |
| 56″ / D | 1422 | engine **more permissive** by 378 mm |

The constant is more permissive than three documented rows and more conservative than the
other three. That is what a constant does when the real value is conditional: unsafe on
some sites and uncompetitive on others, with no way to tell which from inside the engine.

This is the whole argument for `ParameterTable`. The consumer cannot collapse a
conditional value into a scalar without knowing the site, and it does not know the site
until run time. So the table crosses whole, and is evaluated against pinned data.

**A prerequisite on the other side, stated so it is not a surprise:** the Planning model
cannot currently bind `exposure_category` at all. Site conditions are being added there
first, precisely because until they exist every `ParameterTable` would arrive with nothing
to match against.

---

## 6. Why the roles registry is split into a spine and extensions

The capability matrix records component selection as unbound, BOM construction as
"Nothing," and assembly as "Not represented in any form."

**Correction to an earlier draft of this document.** It claimed there was "no way in either
system today" to say *this product can serve as a top rail* or *a panel has two post slots
and N infill slots*. That was wrong, and reading the consumer's code properly settled it:
`PartType` is exactly the first, and `PanelSpec` with its frame slots, infill pattern and
fixing rules is exactly the second. Both have been there.

What is missing is **data**, not vocabulary. The types can express a Chesterfield panel
today; nobody has authored one. That is a better position than the draft claimed, and it
moves the work from "design a structure model" to "curate against one that exists".

The spine is the shared filing vocabulary. Extensions let this platform name whatever a
manual actually describes — a `rebar_separator_clip` filed under `fastener` is counted by
a fixing rule exactly as any fastener is, and needs no code on either side.

The split exists so that adding a part-kind is usually a data change. It is deliberately
not *always* a data change: when a manual describes something no existing rule can count —
a decorative band across the span, say — filing it under a role that nearly fits produces a
confidently wrong quantity. Publishing it as a gap produces a visible hole. The contract
asks for the second.

---

## 7. Two reference sketches, non-binding

Two documents from the Planning side argue for a particular internal shape for this
platform. Neither is a specification, and nothing in either is binding.

- **Claims to Concrete** — the reasoning: what shape knowledge needs to take for a value to
  survive the trip to a bill of materials, and which failures each decision prevents. Worth
  reading for the argument even if you reject the conclusions.
- **Twenty-One Tables** — a fully worked internal schema, with a worked example carrying
  real rows from this store through to a BOM line.

They exist because the Planning team had to think through what it was asking for before
asking. Treat them as one team's proposal. Only the items marked BINDING in
`contract.md` are promises.

Links are held by the Planning team; ask if you want them.

---

## 8. What this document does not argue

That the current state is bad. Every measurement above is one this repository produced
about itself, published rather than hidden, which is why the contract could be written at
all. `state-and-gaps.md` naming G17 as a correction to its own earlier claim is the reason
these numbers can be trusted.

The contract is designed so that a snapshot containing very little is still valid, and the
consumer still produces a plan from it. Coverage grows as curation runs. The boundary does
not have to wait for it.
