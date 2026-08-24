# Acceptance criteria and open questions for the boundary

```text
Status:    Working log, maintained by the Knowledge team (this repo).
Purpose:   Everything the integration work turned up that needs a decision,
           and the criteria by which we would call each piece done.
Companion: audit-response-v0.1.md (the answer to knowledge-datamodel.md §7),
           source-refs-design.md (the endpoint design).
```

This file exists so that nothing found during the integration work is lost
between documents. Three sections: what needs a decision from Planning, what
needs a decision from us, and what "done" means for the two pieces of work that
are actually in flight.

---

## 1. Needs a decision from Planning

Each of these changes tier 1 or tier 2, which by `knowledge-datamodel.md` §7
makes it a negotiation rather than a request. The evidence for each is in
`audit-response-v0.1.md` under the question named.

Ordered by how much of the store each one affects, not by tier.

### 1.1 Tier 1 — the shared vocabulary

| # | Item | Question | Evidence in |
|---|---|---|---|
| N1 | `UnitCode` has no angle, speed, pressure or time unit | 274 facts we hold are in `deg` and `mph` and neither can cross as a `Quantity`; cure times are durations. Extend the closed vocabulary with `deg_milli`, `mph_milli`/`mps_milli`, `pa_milli`, `second_milli` — or rule that these live only in the condition space. | §2.2, §2.8.1 |
| N2 | `ParameterTable.rows[].value` must admit an enum | `stepped_only`, `not_rackable` and `gates are not rackable` are values a planner needs and have no numeric form in any document. | §2.2 |
| N3 | `Quantity` carries one `value_raw` | Dual-unit sources disagree with themselves: `Height: 66 inch (16766 mm)` and `Rail Section: 8 foot (2436 mm)` in one CSI masterspec. Two lexemes, one wrong. Does `value_raw` become a list? | §2.8.6 |
| N4 | Extension part types are `tenant`-namespaced — wrong axis | We invent part types because a *manufacturer's* manual describes one, and manufacturers are not tenants. Proposed: `shared` / `mfr/<manufacturer>` / `<tenant>`. **The one tier-1 change we think is structurally necessary.** | §2.10 |
| N5 | Invariant 2, "a part cannot declare its length" | Rails here are manufactured at fixed nominal lengths per style — 72″, 94″, 96″ — and the rail's length determines the bay. Request: allow a manufactured nominal length distinct from a cut length. | §2.9.5 |
| N6 | `SourceRef` gains one non-opaque field | `belongs_to` (a content hash), so a per-field citation joins to a definition's provenance block. Without it an opaque id carries zero admissibility bits into a pinned snapshot. | §2.6 |

### 1.2 Tier 2 — the published definitions

| # | Item | Question | Evidence in |
|---|---|---|---|
| N7 | `Coverage` becomes an anchored interval | Neither guessed fifth kind exists — periodic pitch and gate-bay-only both have **zero instances**. What exists is `POST LENGHT-(DEPTH+7)`, `FULL LENGTH -1"`, and a stiffener *longer* than its host. Proposed: `Span{from: Anchor, to: Anchor, at_least}`. | §2.3 |
| N8 | `ContainedSlot.relation` vocabulary | `insulates` has zero instances; `fills`, `caps` and `retains` are missing and each has material behind it. | §2.3.1 |
| N9 | `PostSlot` needs role keying | Reinforcement is conditioned on post role — corner, end, line, gate — which is not reachable from `ContainedSlot` → `FrameSlot` → `PanelSpec`. One fix serves §2.3, §2.4 and §2.11. | §2.3.3 |
| N10 | `AssemblyStep` scope, kind, slots and requires | 44–51% of steps in real guides are neither `panel` nor `bay`; thirteen other scopes found. Widen `scope` to `panel\|bay\|post\|run\|site`, widen `kind`, give `slots` a target union, give `requires` an edge kind. | §2.4 |
| N11 | The warning model | 226 distinct warnings, and only 19.9% of resolvable instances sit on a step. Invariant 5 is false against this corpus. Proposed: `text_raw` + `lang` + `attaches_to{kind, ref}` + `severity_lexeme`, with `code`/`params` optional. | §2.5 |
| N12 | The warning registry must split | Platform-authored codes stay closed and require both locale bundles; warnings quoted from a document are verbatim, `lang`-tagged, and exempt. **Zero of 81,794 elements are Hebrew**, and translating a manufacturer's liability sentence is manufacturing a claim. | §2.5 |
| N13 | `Procedure` with `scope: EntityRef \| null` | Four classes of procedure own no panel, including cross-manufacturer ones. Today they duplicate — one guide repeats its run-scope block **sixteen times**, once per style. | §2.7 |
| N14 | `contributing_sources` on `Part` and `FenceModel` | Per-field `cites` cannot tell a pinned run that three of a definition's five sources are superseded. 40.7% of promoted facts already cite one. | §2.6 |
| N15 | `source_class` / `curation_level` on every published value | They sit on `ParameterTable` rows and not on `Part.spec`, yet a rail length has the same admissibility problem. Obligation §3.1.6 says "every row"; invariant §6.8 says "every published value". The invariant is right. | §2.6 |
| N16 | `Member` needs edge handedness | `Attach U-Channel to "tongue" side of first board, and "groove" side of last board`. `per_end_member` gets the count right and the handedness wrong, and a mirrored panel validates. | §2.1 |
| N17 | Gates have no type at all | The largest gap we found. Leaf-vs-opening delta, swing direction, hinge side, latch mounting height, drop rods, cross-brace prohibition, hinge selection by leaf weight — none has a home. **We are not asking for `GateModel` in v0.1; we are asking that it be named as out of scope rather than left implicit**, so a curator does not file a gate as a `FenceModel` and lose all of it silently. | §2.11 |
| N17a | A `gate.*` namespace for eligibility predicates | `item.load_rating_lb >= gate.leaf_weight_lb` is a fact about an assembled gate, which is neither `panel.*` nor `host.*`. This breaks a mechanism rather than lacking a field. | §2.11 |

### 1.3 Registry additions — not breaking, but they need entries

| # | Item | Why | Evidence in |
|---|---|---|---|
| N18 | `SourceClass`: `manufacturer_installation_instruction` | Installation manuals are 69 documents, 1,129 pages, **44.6% of all facts**. Mapped to `spec_sheet` they are inadmissible for structural parameters, which silently removes 370 of the 601 dimensional structural facts we hold. | §3 |
| N19 | `SourceClass`: `industry_standard` | Nine documents — ASTM compilations, two CSI masterspecs, a CLFMI wind-load guideline, an association bulletin. In engineering practice these outrank a manufacturer spec sheet; the ladder has no rung for them. | §3 |
| N20 | Condition dimension: `jurisdiction` | Approvals state validity "in Miami Dade County and other areas where allowed by the Authority Having Jurisdiction". Planning declares what it can bind. | §2.8.4 |
| N21 | Condition dimension: `code_edition` | One manufacturer's two wind tables are computed under `ASCE 7-10` and `ASCE 7-16`. Under `unique` they collide for the wrong reason. | §2.8.3 |
| N22 | Validity window on `Combination` and parameter rows | 271 `approval_id`, 84 `effective_date`, 75 `expiration_date` facts, and no field for any of them. Or model expiry as an `as_of_date` condition, which we would also accept. | §2.8.2 |
| N23 | Warning codes for source honesty | The ten `SOURCE_*` codes in `source-refs-design.md` §3.2, so the frontend can satisfy §3.3.1 without knowing anything about PDFs. | source-refs-design §3.2 |

### 1.4 Clarifications — no change, just confirm our reading

| # | Item | Our reading | Evidence in |
|---|---|---|---|
| N24 | Invariant 4's `unplaced` escape | Real guides leave members unplaced — Bufftech Chesterfield leaves 3 of ~11. We read *"or reported `unplaced`"* as permitting a large `unplaced` list rather than requiring a curator to invent placements. | §2.4 |
| N25 | `uncovered` on an unreadable table | On the 73 `table_not_reconstructed` pages we are **declaring** a domain, not reading one. It must not be read as measured. | §2.10 |
| N26 | `retain_until` for source refs | Source refs cited by a snapshot inherit that snapshot's retention and tombstone. A run never resolves one; a person inspecting an old plan does. | source-refs-design §8.1 |
| N27 | Source-ref tenancy | Corpus source refs are global; tenant-document source refs are tenant-scoped; the two never mix in one response. | source-refs-design §8.2 |
| N28 | Batch source-ref resolution | A review screen showing 50 rows would issue 50 requests. `POST /source-refs:batch` changes no shape in the contract. | source-refs-design §8.3 |
| N29 | The `us` / `china` tracks | Two deliberately separate corpora — Chinese-language, metric, GB rather than ASTM. `Snapshot` has a `tenant` and no locale or standards regime, and nothing in the contract mentions a track. Raised as a question, not a proposal. | source-refs-design §8.5 |

**If only five of these are read, read N1/N2, N10, N11, N14 and N18** — the unit
vocabulary, the step scope, the warning model, definition-level provenance, and
the missing source class. Those are the five where the data contradicts the
proposal rather than merely stretching it. N4 is separate: it is the one change we
think is structurally necessary rather than evidence-driven.

---

## 2. Needs a decision from us

Internal, no negotiation required. Listed so they are not forgotten.

| # | Item | Position |
|---|---|---|
| K1 | `cross_family_verified` in `table_review.PROMOTABLE` | Two agent readings currently promote a fact with no human review; 324 facts were promoted this way and `rationale.md` §1 records what one of them cost. `docs/curation/` C0 proposes revoking it. **We intend to revoke it.** It is our behaviour, inside the boundary. |
| K2 | Crop path: poppler windowing vs the existing Pillow crops | `source-refs-design.md` §4.2 chooses poppler and demotes the 7,484 existing region images to a legacy cache. Pillow is optional and git-ignored; `_crop_region` returns `False` without it. Decided, pending the cost measurement in K3. |
| K3 | Render cost is unmeasured | We chose the crop path on correctness and dependency grounds without knowing what a cold paragraph crop costs. Measure before a queue is built on it. |
| K4 | Readers record no cell box | All 1,225 rows in `table_read_candidates` carry row and column labels and **no cell bounding box in crop pixels**, which `docs/curation/` §2.5.3 requires. A reviewer can be shown the crop but not the cell inside it. This is the first concrete gap the source-ref design surfaced in our own store. |
| K5 | No human reading exists | `reader_kind` is `agent` for all 1,225 readings; `review_status = cross_family_verified` means two agents agreed. Curation level 2 is currently unreachable by construction, not by backlog. |
| K6 | Six CAD pages have an image path and no `page_image` asset row | They are registered as `region_image` pointing at a `pages/` path. Harmless today, wrong for an endpoint that resolves assets by type. Flagged, not guessed at. |

---

## 3. What "done" means

### 3.1 The §7 answer

- [x] Every one of the ten questions answered, none deferred.
- [x] Every claim carries a repo-relative document path, a page, and a verbatim quote.
- [x] Values read from a PDF are distinguished from values read from the hand-researched `data/structural/*.json` files.
- [x] "Searched and not stated" is recorded as a finding, naming what was searched, rather than left silent.
- [x] Every proposed change is marked as tier 1, tier 2, or internal, so the negotiation surface is explicit.
- [x] Every proposed change carries a counter-argument, because an over-specified field we must invent data for is as costly as a missing one.

### 3.2 `GET /source-refs/{id}`

Design is complete; nothing is implemented. Acceptance for the implementation,
when it happens:

- [ ] Every one of the seven fixture records resolves, including the three with no quote and the one with no document.
- [ ] `source_ref_id` is stable across two independent snapshot builds of the same store.
- [ ] A crop rendered by the normative transform reproduces the verified case: `bufftech-installation-guide-40-40-70743.pdf` page 5, bbox `[117.69, 271.47, 266.99, 294.03]`, rendering exactly the three lines containing `30" deep`.
- [ ] No crop is produced by a code path that imports Pillow.
- [ ] Deleting `workspace/derived/` entirely changes no response body except `image.status`, and every image still resolves. This is the D6 criterion from `distribution-design.md`, applied to the endpoint.
- [ ] A page with a non-zero `/Rotate` renders a crop that matches the page image, with no rotation transform anywhere in the path.
- [ ] The 72-dpi CAD pages and the one DOCX page return typed, non-crashing responses.
- [ ] Every warning code in `source-refs-design.md` §3.2 exists in both locale bundles.
- [ ] A source ref for another tenant returns 404, not 403.

---

## 4. Assumptions made, so they can be corrected

1. **Direction of the reply.** These documents are written as the Knowledge team's response to the Planning & BOM team's proposal, matching the audience `knowledge-datamodel.md` §7 addresses. Nothing in the substance depends on that framing; if the intended reader is different, the framing changes and the findings do not.
2. **`docs/curation/` is tier 3 and stays there.** `knowledge-datamodel.md` §4 already says so. We have taken it as settled rather than raising it, and said so explicitly in the response cover.
3. **Nothing here is implemented.** The brief was to prepare the design and confirm it is sufficient. No pipeline code was written, no schema created, and the corpus was not modified — `git status` over `manuals/`, `china/`, `data/` and `workspace/` is clean. The evidence store was queried read-only.

---

## 5. How the evidence was gathered

Stated so the numbers can be re-derived and disputed.

Five parallel readers worked disjoint slices of §7 against the store, each
required to produce a document path, a page and a verbatim quote for every claim,
and to record "searched X, Y, Z and the corpus does not say" as a finding rather
than leave silence. Counts were taken from `workspace/indexes/evidence.db` by
direct SQL. Where a page is a scan, the page image was looked at rather than
trusting OCR — several of the load-bearing quotes (the racking conditional, the
`7 3/8"` picket dimension, the `92` steel channel) exist only as pixels and were
read at 300 dpi.

**§2.11 (gates) was researched twice, independently**, by readers that shared no
context — once as part of the Q8 sweep and once as a dedicated pass on a different
model. The two agreed on every finding and the second contributed the citation
set now in the response, including the two quotes that changed the conclusion:
*"The location of your gate will determine the layout of the posts for the fence
line"* and *"Gate(s) must be assembled prior to fence"*. Where the two passes
disagreed with an earlier assumption of ours — the 92″ channel sits in a 94.5″
rail, not a 96″ one — the source won.

The highest-stakes aggregate figures were re-verified by hand against the database
after the fact: the 132/324 superseded-citation count, the 231/601 admissible-class
split, the four-way `same_content_as` group with its 91/55/55/55 fact counts, the
zero Hebrew elements, and the 73,894 boxed-elements-without-a-crop figure in
`source-refs-design.md`.
