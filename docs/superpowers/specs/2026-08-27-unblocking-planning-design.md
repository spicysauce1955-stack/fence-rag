# Unblocking Planning — design

```text
Status:   Design, approved 2026-08-27. No code written. Supersedes the track order
          in docs/build-plan.md §2 for the next phase only; the build plan's Phase
          A record and its constraint list stand unchanged.
Authority: Subordinate to docs/integration/contract.md (FROZEN v1.1),
          docs/mvp-implementation-spec.md and guide.md. Where this document and
          any of those disagree, they win and this is the defect.
Method:   Written after a six-angle adversarial review (contract compliance,
          consumer advocate, fence/structural domain, measurement audit, protocol,
          architecture). §2 records what that review broke. Every number here was
          read from workspace/indexes/evidence.db on 2026-08-27.
```

---

## 1. What this is for

The Planning & BOM team is blocked on us. This document decides what we build next
and in what order, and records five decisions taken with the maintainer.

It replaces an earlier draft of the same plan. That draft is not archived, because
§2 is a more useful record of it than the draft itself.

---

## 2. What the adversarial review broke, and what it confirmed

The first version of this plan was reviewed by six independent adversaries. Three
of its central claims did not survive. They are recorded here rather than quietly
corrected, because two of them were wrong in ways that would have shipped.

### 2.1 The footing table is not the shape the draft thought — CRITICAL

The draft published `ParameterTable{parameter: footing_depth_mm, domain:
{exposure_category:[B,C,D], hvhz:[true,false]}, hit_policy: unique}`.

The source table is not a 3×2 lookup. It is **three pairs of `(footing depth, max
post spacing)` design points, one pair per exposure**, with HVHZ applicability as a
merged annotation spanning each pair. From the clean text layer,
`doc-1085f7c65c47` p17:

```
Wind Exposure | Footing Depth | Max. Post Spacing
B | 30" | 97" | NON HVHZ            ← one annotation
B | 24" | 66" |                        for the PAIR
C | 36" | 88" | HVHZ and NON HVHZ
C | 30" | 68" |
D | 36" | 75" | HVHZ and NON HVHZ
D | 30" | 56" |
```

A deeper footing buys a wider span. That is the engineer's trade, and the draft's
shape cannot express it.

**The physics confirms the reading.** ASCE 7-10 Kz at 0–15 ft: B 0.57, C 0.85,
D 1.03. At fixed footing depth, permissible tributary width should scale as 1/Kz:

| | predicted | actual |
|---|---|---|
| D/C | 0.825 | 56/68 = 0.824 |
| C/B | 0.671 | 68/97 = 0.701 |
| D/B | 0.553 | 56/97 = 0.577 |

Under the pair reading the table is coherent. Under the draft's reading, footing
depth *decreases* 30″ → 24″ as wind load rises at exposure B while *increasing*
30″ → 36″ at C and D, which no code provision does.

Three consequences, all of which would have shipped:

1. **`(B, hvhz=true)` is not uncovered — it is not approved.** Both B rows are
   non-HVHZ. The draft would have answered *24″ deep, 66″ spacing* for a
   Miami-Dade job, citing a Miami-Dade NOA that does not approve exposure B in the
   HVHZ. This is `state-and-gaps.md` G16's **critical** finding, reproduced.
2. **`hit_policy: unique` is violated by the real data.** At `(C, false)` both
   36/88 and 30/68 are valid. Neither invariant 6 exclusion covers it.
3. **The cheaper compliant option becomes unreachable.** At exposure C the source
   offers 88″ (7 posts, 36″ footings) or 68″ (9 posts, 30″ footings) on a 40 ft
   run. The draft could only ever return the second.

### 2.2 The worked trace asserted something the page does not say

The draft claimed fact 13378's `conditions {"hvhz": true}` was wrong *because the
page's own row reads NON HVHZ*. Measured: the string `NON HVHZ` occurs **zero**
times on `doc-32e36a07ab44` p11 in any column. All three readers recorded the
reason independently — *"on this page the table has NO bracket/label column at
all … Verified by zooming in"*.

The conclusion holds — the condition is unfounded, `condition_basis` is already
`assumed` with the note *"conditions captured by regex proximity, not asserted by
the document"*. The stated reason was carried over from a different document.

Consequence: the gap for that row is **not** `disputed{on: conditions}`. There is
no second admissible reading to dispute. A `disputed` gap citing
`d28ed5f65a38bb76` would publish a citation that fails its own reading.

### 2.3 The draft used an authority-20 source to adjudicate a sealed approval

§10 of the draft "confirmed" two OCR errors against
`post_spacing_rules.concrete_footing_spec` — a free-text prose paraphrase in
`data/certainteed-bufftech.json`, which `docs/layering.md` §5 rates at authority
20, states *"can never reach `accepted`"*, and measures at 13.3% contradicted
(25% in the structural file). `docs/curation/` requires such a claim to **beat a
page**, not adjudicate one.

The two OCR errors are real (`D "36" 7"` → 36/75; `D 30' 36"` → 30/56). The
corroboration should come from the clean text layer on `doc-1085f7c65c47` p31 and
from the 54 agent readings already in the store, both of which read them
correctly — and it corroborates rather than proves, because neither is a human
review.

### 2.4 What survived every attack

Recorded because it is as useful as the failures.

- **The two-items finding.** All 44 review-queue pages carry
  `table_not_reconstructed`; those pages hold **0** `table` elements. Recovering
  pdfplumber geometry for 17,499 cells boxes **zero** rows of the queue. Five of
  six reviewers verified this independently, each trying a different evasion.
- **The G38 mechanism.** `write_extracted()` → `delete_version_rows()` →
  `DELETE FROM elements`; `ref_id = sha256(f"{sha}:{page}:{bbox}")[:16]` over the
  stored bbox string. A `table_cells`-only in-place UPDATE avoids the element
  churn.
- **`gap_after = 0` for tongue-and-groove.** Independently corroborated:
  `doc-c359b5c5c8ce` p6 states `13 T&G Boards` per 8 ft section, and 13 × 7 = 91
  against a 91.185″ clear opening.
- **Keeping the four superseded NOAs as `contributing_sources`.** A fence
  permitted under NOA 12-1106.11 was built to a 119″ post; current drawings
  specify 107″. Merging the chain destroys warranty answerability.
- `ParameterTable.scope` is `Part | FenceModel`; invariant 6's two exclusions;
  the eligibility split; `Combination` deprioritised; gate as a `Gap`;
  30 in → `762000` exactly; namespace-only tenancy; the ten `SOURCE_*` codes
  needing both locale bundles.

---

## 3. Five decisions

### D1 — The review loop comes before the publishing slice

Every admissible source class for `task = structural_parameter` is gated at
curation level 2 (`contract.md` §1.4), obligation 6 requires a person to have
compared the value to the source image, and the level-2 population is **zero** —
`reviewer` is NULL on all 1,225 readings and nothing in the package writes
`accepted` or `corrected`.

Publishing first therefore ships a structural table that the consumer's own policy
rejects on arrival, falling back to their built-in default. Both teams' written
plans already named this the critical path; the draft inverted it.

### D2 — Membership is cited to the sealed bill of material, not to the dataset

The draft treated a `PanelSpec` membership edge as uncitable in principle. That
was wrong, and the correction is the maintainer's.

**A citation is a pointer; the curation level says who checked it.** An agent may
mint a citation — it publishes at level 1 until a person confirms it. The contract
already models this in `Provenance{cites, source_class, curation_level}`.

What is uncited is the *dataset's naming*, not the *fact*. Measured: `BT-POST-5X5`,
`BT-RAIL-CHESTERFIELD` and `BT-PICKET-7-7-TG` appear **0 times** across 81,794
elements. But `doc-3c8ab51045c7` p12 is a PE-sealed sheet headed `MODEL:
CHESTERFIELD - 8'X 6` carrying a bill of material:

```
J | .875 X 7 X 62.75 TONGUE AND GROOVE PICKET | P.V.C.
  | 5 X 5 X 107 ROUTED POST                   | P.V.C.
K | U-SHAPPED G-60 STEEL CHANNEL X 92         | GALVANIZED STEEL
M | LOCK RING                                 | POLYETHYLENE
Q | #8 X .75 SET SCREWS                       | STAINLESS STEEL
```

So membership-of-parts is derivable from a rank-1 `sealed_approval` source, and it
is **more complete** than the dataset: the 92″ steel channel, the set screws and
the picket end channel are absent from `data/certainteed-bufftech.json` entirely.

**Two limits, stated so they are not discovered.** The BOM says *which parts*, not
*how many slots* — it lists `2 X 6 DECO RAIL` once for what is two rail positions —
so **slot structure remains authored**. And only some of the 59 assemblies have
sealed drawings. Candidate amendment C3 therefore still needs an answer, but its
blast radius shrinks from "the entire structural half" to "products with no sealed
drawing".

### D3 — Open questions are logged in one register, not sent piecemeal

C1 (`curation_level` 0 vs 1 undefined) joins the register rather than going out as
its own message. §6 is the register.

### D4 — Snapshot bytes move to private object storage; the API surface does not

The bytes Planning depends on are one small immutable file. Serving them from
object storage removes our uptime from their critical path: a planning run cannot
be blocked by our server being down.

**The bucket must be private.** Today's R2 configuration is public
(`R2_PUBLIC_BASE_URL`) — correct for manufacturer PDFs, wrong for per-tenant
knowledge, and incompatible with §4. `sigv4.py` signs *requests*, not URLs, which
is exactly the right shape: a backend holding credentials can fetch; a browser
holding a link cannot.

Of the ten calls in `contract.md` §1.5, **one** moves: `GET /snapshots/{id}`
becomes a private object fetched with credentials. The shape is unchanged, and
withdrawal becomes a stored tombstone body rather than a 410 — closer to the
contract's own wording, *"resolves to an explicit tombstone"*.

The other **nine** stay on the service. `POST /snapshots/resolve` is the
*"anything newer?"* call made at deploy time; if it is unavailable Planning
continues with the snapshot id it already holds, so it cannot block a run. The
remaining eight are human-facing reads or writes, and none is on the path of
producing a plan.

**The bucket's access model is a precondition of Phase 3, not of Phase 4.**
Nothing may be published to a public bucket.

### D5 — The ParameterTable is reshaped to design points

Per §2.1. The published shape must express a `(depth, span)` pair as one row, must
carry the conditions that actually scope it, and must distinguish *not approved*
from *not covered*.

---

## 4. The architecture constraint

**No user ever reaches this platform directly. Every path is
frontend → Planning backend → knowledge.** This is `contract.md` §1.5's model
(*"proxied from the frontend through Planning"*), restated here because it is
load-bearing for three things:

1. **Our service accepts connections from one backend, never a browser.** One
   bearer token on an allowlist; no CORS, no sessions, no per-user rate limiting,
   no public exposure.
2. **Crop images traverse Planning's backend**, so a slow render occupies a
   connection on both sides. A per-batch deadline, a batch cap well below 100, and
   an on-disk crop cache are required, not optional. Relative image URLs in the
   source-ref response were already chosen for this reason
   (`source-refs-design.md` §5) and remain correct.
3. **We never see an end user.** `reviewer` is a name Planning's backend asserts
   and we cannot verify — yet it is the only thing separating "software read this"
   from "a person confirmed it". **Mitigation: a review must echo the
   `crop_sha256` of the image we served.** That is verifiable without knowing who
   the reviewer is.

**Screens are Planning's; the CLI and the API behind them are ours.** We build no
UI. Our own curators work through Planning's frontend, and a local CLI exists so
operators are not blocked on it.

---

## 5. Order of work

### Phase 0 — G39, alone, first

`cli.py:286-297`: both `--build` and `--dry-run` reach the branch and only
`--build` gates storage, so `--dry-run` stores anyway. The sibling defect — bare
`snapshot` with no flag printing an error and exiting 0 — is fixed in the same
commit. This lands before anything iterates `snapshot --build` against a
write-once, tombstone-only store.

### Phase 1 — The register and the paper deliverables

Days, no schema. §6. Sends every outstanding question in one message.

### Phase 2 — The review loop

The critical path (D1). Three parts:

1. **`table-review --accept ID --reviewer NAME [--value CORRECTED]`**, writing
   `review_status`, `reviewed_value`, `reviewer`, `reviewed_at`, and requiring the
   request to echo the served `crop_sha256` (§4.3). `mark_cross_family_verified`
   is orphaned today and no CLI verb reaches it.
2. **`GET /source-refs/{id}` live**, with the crop path from `crops.py`, an on-disk
   crop cache keyed by `(ref_id, dpi, tool_fingerprint)`, a per-batch deadline, and
   a batch cap below 100.
3. **The review geometry**, which is *not* what either roadmap said. See §5.1.

### Phase 3 — The publishing slice

Reshaped per D5, with membership cited per D2, and the `Gap` defects in §7 fixed
first. Scope decided at the close of Phase 2, when level-2 values exist.

### Phase 4 — Transport and tenancy

Obligation 7 in code. Unchanged from `build-plan.md` Phase E. Note that the
bucket's access model (D4) is **not** deferred to here — it gates Phase 3.

### 5.1 The review unit is a row-plus-bracket, not a cell

`planning-asks.md` §1 asked for a cell bounding box and called it the one thing
above everything else. Measured, that ask is aimed at the wrong object twice over.

**First**, K4 as scoped delivers nothing to the queue (§2.4).

**Second**, the substitute the draft proposed — deriving a box as row-label y-band
∩ column-label x-band — is ambiguous on exactly the tables it targets:

```
distinct index-cells in the queue ……………………… 870
distinct (row_label, col_label) pairs ……………… 194
pairs addressing more than one cell ……………… 114
readings with an empty row or col label ………… 90

doc-32e36a07ab44 p11, ('B','FOOTING DEPTH'):
   row 0 → 30"      row 1 → 24"       ← one label band, two values
```

A row-label band on "B" spans both B rows. The reviewer is shown a box containing
30″ *and* 24″ and asked to accept 30″ — a *misleadingly* bounded task, worse than
an unbounded crop, on precisely the pair whose confusion is G16's critical error.

**And the queue cannot record the answer even if the geometry were right.**
Distinct `col_label` values across the whole queue contain no HVHZ column and no
HVHZ row label; all 426 HVHZ mentions live in the free-text `notes` field. The
thing under review on these tables is the applicability bracket, and
`table_read_candidates` has no column for it.

Phase 2 therefore delivers: a field that can hold the applicability bracket, a
geometry that is unambiguous on the six-row grid or an honest row-band with the
bracket transcribed, and a three-way verdict (accept / reject / bracket-unclear)
rather than a binary.

---

## 6. The register — everything owed to Planning

Written as one document in Phase 1.

### 6.1 Answers we owe

| | |
|---|---|
| Ten `SOURCE_*` codes | with `params` and measured instance counts |
| Eleven-warning starter list | with counts and verbatim exemplars, each carrying its `ref_id` |
| `CURATION_MACHINE_CONSENSUS` | params `readers`, `families`, `crop_sha256`; 168 cells, 504 readings |
| `also_filed_as` | the curation rule for one source class per content hash |
| §5 Q1 | scope dimensions for `industry_standard` — proposed: `material`, `system_type` |
| §5 Q2 | the shared-host gap shape |
| §5 Q3 | answered by `also_filed_as` — with the correction in §6.3 |

### 6.2 Questions we owe

| | |
|---|---|
| **C1** | define `curation_level` 0 versus 1. Their `min_curation` rows are written against a scale we never defined, and the §1.4 tie-break resolves by higher level before issue date |
| **C3** | is a slot-structure edge a "value" under invariant 8? Narrowed by D2 |
| **NEW** | is there a representation for **not approved** as distinct from **not covered**? `(B, hvhz=true)` is a refusal, not a coverage hole, and `uncovered` cannot say so |
| **NEW** | does a `(depth, span)` design-point pair need a `hit_policy` or value shape they do not have? |

### 6.3 Corrections we owe

- Their §1 ask is aimed at the wrong object; the cell box they need is a different
  change on a disjoint page set (§5.1).
- Deferring the review loop closes N18 — they asked in writing to be told "now" if
  human review was further out than assumed. It is, and D1 fixes it.
- **15** `same_content_as` connected components, not 14. The fifteenth is
  identical *extracted text* with different bytes — the hardest case, and the one
  `also_filed_as` exists for.
- The footing/span table is a design-point pair (§2.1). This may change what they
  can model.
- No document in the store carries a lapsed `expiration_date` — 4 of 144 have one
  at all, and every one is in the future — so their §2.2 lapsed-authority test
  cannot be demonstrated as scoped.

### 6.4 Never answered, from their side

Their five confirmations (N2, N18, N25, N22, N29); §6c (publish continuous-rail
products as a `Gap`); §6d (the stagger constraint).

---

## 7. Defects in shipped code, to fix before publishing more

| | Defect | Evidence |
|---|---|---|
| 1 | `Gap` has no `because` and no `cites`; `disputed` has no `on:` discriminator | `contract.md` §1.2.1 defines all three; `snapshot.Gap` has six fields. 63 gaps already published with no evidence — a live obligation 8 violation |
| 2 | `SourceDoc` omits `superseded_by` | In the contract's §1.1 shape; `relations` already holds the edges |
| 3 | `verify()` checks `cites` on warnings only | Obligations 3 and 6 require it on every published value |
| 4 | `condition_scope` is absent from the design and the gate | BINDING; `build-plan.md:146` already named it for this deliverable |
| 5 | Error codes must not share the warning registry | Their `test_locale_bundles.py` fails the build on any registry code lacking both bundles — a new HTTP error code would break their CI. Separate `error.*` namespace |
| 6 | The `unique` check must exclude *disjoint* validity windows, not merely differing ones | Overlapping windows are a real collision, and their resolver raises on a tie |
| 7 | ~~Every `would_close` is a template constant~~ **FIXED (G40)** | 63 published gaps carry 4 distinct sentences; 51 share one. §1.2.1's BINDING clause wants *"a footing row for exposure C, non-HVHZ, at 6 ft"* and warns against the generic form. `document_id`, `page_no`, `ocr_confidence` and the body are all in scope at `snapshot.py:285-345` and none is interpolated |
| 9 | ~~The warning detector cannot see 5 of the 11 promised warning classes~~ **FIXED (G42)** | It recognises a severity lexeme or a hazard regex. `Never strike the PVC post without a wood support`, the frost-line check, the post-top rule and the panel-both-ends rule are ordinary bullets in installation lists; warranty exclusions are running prose in warranty documents. 0 published instances against 16-254 elements each. `registry-additions.md` §3.1 |
| 8 | `table_cells.rowspan`/`colspan` are never written | All three `Cell(...)` sites omit them, so all 18,472 cells default to 1. The merged applicability column of the Bufftech footing table is lost corpus-wide across all 5 documents carrying it — the field that scopes exposure B to non-HVHZ is attributed to one row instead of two |

---

## 8. Explicitly out of scope

- Corpus coverage, retrieval quality, a drained review queue — all named by
  Planning as things they do not need.
- `Combination` curation — pinned but inert; nothing in their engine reads one.
- A user interface of any kind (§4).
- Extraction editions (G38's fix). **Open question flagged, not decided:** whether
  edition-stamping must precede publishing a second wave of citations. Phase 3
  adds cites on parameters, parts and members, all hostage to a bbox measurement,
  into a store with no delete.

---

## 9. Acceptance criteria

| | Criterion |
|---|---|
| A1 | `snapshot --build --dry-run` stores nothing; bare `snapshot` exits non-zero |
| A2 | The register exists and has been sent as one message |
| A3 | A person can accept a reading from the CLI, and it moves to `curation_level` 2 |
| A4 | A review is refused when its echoed `crop_sha256` does not match the served crop |
| A5 | `GET /source-refs/{id}` round-trips the seven fixture records in `docs/integration/fixtures/source-ref-examples.json`. **The fixtures must first be re-minted**: they carry `sref_` ids, and that scheme is superseded by `refs.ref_id` — so "byte-for-byte" cannot be asserted against the file as it stands |
| A6 | The queue can record an applicability bracket, and a reviewer can answer *bracket-unclear* |
| A7 | One `ParameterTable` publishes `(depth, span)` design points with `condition_scope` on every key, a refusal at `(B, hvhz=true)`, and `uncovered` listing only genuinely uncovered points |
| A8 | Every published value carries `cites`, `source_class`, `curation_level`, `version_status`; `verify()` fails if not |
| A9 | Membership cites the sealed bill of material where one exists, and publishes a `Gap` where none does |
| A10 | `cli refs --verify` reports 0 dangling after the publish |

---

## 10. What this document does not settle

- The scope of Phase 3 — decided when Phase 2 produces level-2 values.
- Whether extraction editions gate Phase 3 (§8).
- C1 and C3, which are questions, not decisions.
- Whether a second product and second manufacturer join the slice. Reviewers
  argued one Chesterfield panel exercises neither a namespace collision, nor a
  `token`-valued table, nor validity fields, nor `hit_policy` other than `unique`.
  Deferred to the close of Phase 2.
