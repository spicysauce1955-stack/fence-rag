# Registry additions — codes, counts, exemplars, and the curation scale

```text
Status:   v1.0, 2026-08-27. Phase 1 of docs/superpowers/specs/2026-08-27-unblocking-planning-design.md.
Purpose:  Everything this platform owes Planning that is a REGISTRY addition rather than
          an amendment. contract.md §2: "adding an entry is never a breaking change."
          Nothing here needs negotiation; it needs locale bundles on Planning's side.
Method:   Every count re-measured against workspace/indexes/evidence.db on 2026-08-27,
          not copied forward. Three published counts did not reproduce; §2.1 lists them.
Reads with: planning-asks.md §3 (the asks), source-refs-design.md §3.2 (the original
          table, now superseded by §2 below), conversation.md T5.
```

---

## 1. The `curation_level` scale, declared

Owed from `conversation.md` T4. Planning's §9.1 said *"Publish against your reading; we'll
build the enforcement against whatever you've written down by the time we get there."*
This is that writing-down. It resolves **C1** without an amendment, per C1's own third
disposition — the contract pins the top of the scale and deliberately leaves the rest to
the publisher.

| Level | Means | This platform emits it when |
|---|---|---|
| **0** | asserted, not cited | a value exists with no resolvable `SourceRef` — today, nothing publishes at 0 |
| **1** | cited, unconfirmed | a machine produced the value and it carries a resolvable `SourceRef` |
| **2** | a person compared it to the source image | **never, today** — see §4 |

Two consequences worth stating plainly, because Planning's `SourcePolicy` reads this as a
gate ordinal and the §1.4 tie-break resolves by higher level before `issue_date`:

- **A level is a claim about process, not about confidence.** A regex that reads a number
  correctly and a model that reads it correctly both publish at 1. Machine agreement does
  not raise the level — that is what §4's code exists for.
- **The level-2 population of this store is zero.** *(Corrected 2026-08-28: an earlier
  revision said it "cannot change until the review loop exists". The loop exists —
  `cli review --accept` and `POST /reviews` write both promotable statuses, and
  `promote-tables --apply` is no longer a no-op.)* What remains true, and is the half that
  matters to you: **`reviewer` is NULL on all 1,225 readings** `[measured]`. The mechanism
  is built and nobody has used it, so nothing has been reviewed and nothing publishes at
  level 2.

---

## 2. The ten `SOURCE_*` codes

Platform codes: parameterised sentences we author, so both locale bundles are required.
These are **not** source warnings (text lifted from a document), which are exempt from the
bundle rule and travel verbatim and `lang`-tagged.

| Code | Params | Fires when | Instances |
|---|---|---|---|
| `SOURCE_TEXT_FROM_OCR` | `confidence` | `text_source` is `ocr`/`image_ocr` | 25,150 elements |
| `SOURCE_OCR_LOW_CONFIDENCE` | `confidence` | page confidence below threshold | 172 pages |
| `SOURCE_TEXT_LAYER_MOJIBAKE` | `pages_affected` | document is one of the six re-OCR'd | 81 page issues, 6 documents |
| `SOURCE_TABLE_NOT_RECONSTRUCTED` | — | page carries the issue; the image *is* the evidence | 73 pages |
| `SOURCE_DOCUMENT_SUPERSEDED` | `superseded_by` (**list**) | `version_status` is `superseded` | **9 documents, 6 with a successor to name** |
| `SOURCE_VERSION_STATUS_UNKNOWN` | — | status is `unknown` | 132 documents |
| `SOURCE_STATUS_BASIS_FILENAME` | — | basis is a filename keyword, not a document assertion | **9 documents** |
| `SOURCE_CONTENT_DUPLICATED` | `also_filed_under` | a `same_content_as` edge exists | 40 edges, **15 groups** |
<!-- `also_filed_under` (this warning's param) and `SourceDoc.also_filed_as` (§5's
     published field) are different objects carrying the same fact: one is a
     warning a viewer renders, the other is a field the policy reads. The names
     are close enough to misread as a typo, so: both are intentional. -->
| `SOURCE_NO_IMAGE_AVAILABLE` | `reason` | DOCX, or `derived` | 1 document |
| `SOURCE_NOT_FETCHED` | `subset` | the corpus subset is not local | deployment-dependent |

### 2.1 Three corrections to a table we called final

`planning-asks.md` §3.1 says these codes are *"final and already published to Planning."*
The codes are. Three of the counts are not, and one of the triggers was wrong.

**`SOURCE_DOCUMENT_SUPERSEDED` — the trigger and the count disagreed.** The published row
said *"fires when a `superseded_by` edge exists"* and reported 9 documents. Measured, those
are different populations: 9 documents carry `version_status = 'superseded'`, but only **6**
have an outgoing `superseded_by` edge. The other three —
`doc-7dd84b27c52e`, `doc-443644944a60`, `doc-79c89a8bd572` — are superseded on the basis of
a **keyword in the filename**, with no successor recorded anywhere.

The fix is to fire on the status, not the edge, and to let `superseded_by` be empty. A
document we believe is superseded but cannot say by what is exactly the case a curator
needs to see; suppressing the warning because the param is unpopulated would hide the
weakest three of the nine. Note this compounds with the correction already sent in T1:
`superseded_by` must be a **list**, because `doc-8727ba0fd4d4` fans out to seven successors.

**`SOURCE_STATUS_BASIS_FILENAME` — 9 documents, not 6.** `version_status_basis` values
measure as: `keyword in title/filename` **9**, `named as a previous approval by a later
NOA` 3, `no explicit version marker in curated metadata` 127, `reset before re-deriving…` 5.

**`SOURCE_CONTENT_DUPLICATED` — 15 groups, not 14.** 40 edges resolve to **15** connected
components, sized fourteen 2s and one 4. This was already corrected in
`knowledge-asks.md` §3.3; the `source-refs-design.md` table was never updated to match.

---

## 3. The eleven-warning starter list

The eleven classes named in `planning-asks.md` §3.2, each with its instance counts and a
verbatim exemplar carrying a resolvable `ref_id`.

**Published** counts distinct warnings in the current snapshot (289 in total);
**Cites** counts the source references backing them, since one warning printed in several
documents is one warning with several citations. **Elements** counts every element in the
store whose text matches, published as a warning or not — it runs far ahead of Published
because a rule repeated across a product family is one warning, and because the pattern
also matches prose that is not a warning at all. §3.1 is the history of the five rows that
read zero when this list was drafted.

| Code | Published | Cites | Elements | Docs | `ref_id` | Verbatim exemplar |
|---|---|---|---|---|---|---|
| `WARN_UTILITY_LOCATE` | 7 | 18 | 130 | 26 | `eb2c863494b90243` | "Call before you dig." |
| `WARN_FREEZE_THAW` | 12 | 14 | 83 | 6 | `882b1218393c89e8` | "Caution – In climates that experience freeze-thaw cycles, this installation method could result in post cracking over time." |
| `WARN_POST_STRIKE_UNSUPPORTED` | 1 | 5 | 71 | 7 | `021ff5cb7895e64d` | "Never strike the PVC post without a wood support" |
| `WARN_EYE_PROTECTION` | 18 | 52 | 78 | 41 | `9ea589d2ed085734` | "ALWAYS WEAR SAFETY GLASSES." |
| `WARN_PARTS_MISSING_DAMAGED` | 6 | 24 | 35 | 35 | `b8ad6543485400cf` | "DO NOT attempt to assemble the kit if parts are missing or damaged." |
| `WARN_DO_NOT_RETURN` | 5 | 21 | 33 | 33 | `6aa84dabb01fa9c9` | "DO NOT return the product to the store." |
| `WARN_FROST_LINE` | 3 | 15 | 18 | 16 | `6f0e2e1b3206c206` | "Check local codes for frost line depth and regulations" |
| `WARN_POOL_CODE` | 6 | 12 | 117 | 23 | `7593394e9edc8b8b` | "Not pool code approved." |
| `WARN_POST_TOP_CUT` | 1 | 3 | 25 | 5 | `74a8b651f6a3a39c` | "Never cut the top of the post" |
| `WARN_WARRANTY_EXCLUSION` | 1 | 1 | 4 | 4 | `8ad14577225d2658` | "Separate and distinct warranties for hardware and other products are not covered under this warranty." |
| `WARN_PANEL_BOTH_ENDS` | 1 | 3 | 20 | 5 | `e59b70b33b4e1d30` | "Never attach both ends of a panel to posts" |

### 3.1 All eleven publish — five of them only since 2026-08-27

When this list was first measured, **five of the eleven had zero instances in the
published warning set** against 16-254 matching elements each. They were not missing from
the corpus; they were missing from `warnings[]`, because the detector recognises a warning
by a severity lexeme (`WARNING:`, `NOTE:`, `CAUTION:`) or by a consequence clause, and
these are written as ordinary bullets inside installation lists:

> • To lower a post, place a wood block from corner to corner on the post and carefully
>   tap with a mallet
> • **Never strike the PVC post without a wood support**

**Fixed, narrowly.** The general form — treating a bare *never* or *do not* as a hazard —
is measured at 248 hits in this corpus and is dominated by ordinary sequencing steps
(*"dry-assemble all parts. Do not use glue."* is a step, not a warning), so the four rules
are named individually rather than generalised. Warranty exclusions are matched on the
phrasing the warranty documents actually use, which the existing consequence pattern
missed by one preposition.

Two things fell out of doing it, both visible in the table above:

- **A rule publishes as its bullet, not as the list it was printed in.** A reader shown
  twelve installation steps has not been warned. The citation still resolves to the
  containing element, which is where the bounding box is; the text is the rule.
- **Deduplication only works once the bullet glyph is gone.** OCR renders it as a cent
  sign or a guillemet often enough that the same rule arrived as three separate warnings
  that did not dedupe against each other. `Never strike the PVC post without a wood
  support` is now one warning with **five citations** rather than three warnings with one
  each.

One deliberate non-fix: a table of contents can carry the warranty phrase and split into
fragments of dot leaders and page numbers. A fragment must now look like prose — no dot
leaders, mostly letters — because publishing a contents line as a safety warning is worse
than missing the warning.

Logged as **G42**, now closed. The total warning count moved 282 → 289.

---

## 4. `CURATION_MACHINE_CONSENSUS`

Confirmed as specified in `planning-asks.md` §3.3, with one param that cannot be populated.

| | |
|---|---|
| Code | `CURATION_MACHINE_CONSENSUS` |
| Rides on | `Provenance`, beside `curation_level` — not on `SourceRef` |
| Params | `readers` (int), `families` (list of str), `crop_sha256` (str) |
| Measured | **168 cells**, **504 readings**, **3 readers**, 10 distinct crops, across 44 queue pages |

**168 and 504 both reproduce**, but 168 is only stable under one definition of "cell". By
grid position — `(document_id, page_no, row_index, col_index)` — it is 168. By the labels a
reviewer would actually see, it is **96**; by position *and* labels together it is **186**,
because readers disagree about the labels on the same grid position. That 96 / 168 / 186
spread is the same defect §5.1 of the design spec measured from the other side, and it is
Phase 2's problem, not this document's. Publish 168 and mean *positions*.

**`families` is populatable, and this document said otherwise. Correction.** An earlier
revision claimed nothing records which family each reader belongs to. That is wrong:
`table_review.READER_FAMILY` maps `calibration-A` and `calibration-B` to `claude-sonnet`
and `codex-C` to `openai-codex`, and `reader_family()` is already used when writing a
fact's evidence text. The mapping is in code, not in the store, but it exists.

The real weakness is its default. `READER_FAMILY.get(reader, "unknown")` **fails open**: a
reader loaded under a name nobody added to the dict becomes `"unknown"` silently, and two
readers both mapping to `"unknown"` would satisfy a naive cross-family test while being the
same model. For a code whose entire claim is that *two different families* agreed, that
default inverts the guarantee.

So the param ships from `reader_family()`, and the fix owed is not a schema change but a
closed one: an unmapped reader must refuse to count toward cross-family consensus rather
than counting as its own family. Logged on our side; no action needed from Planning, per
T7.

Unchanged from §3.3: this does not affect admissibility. These rows publish at level 1 and
Planning's policy rejects them for structural tasks. The code ranks a review queue; it never
clears one.

---

## 5. `also_filed_as` — one source class per content hash

**The rule.** Where one `content_hash` is filed under more than one document record, the
`SourceDoc` carries **one** `source_class` — the strongest admissible reading of the bytes —
and every other filing travels as `also_filed_as`, an array of `{manufacturer, doc_type}`.
The class is a property of the *bytes*; the filing is a property of the *catalogue*.

**Why it is load-bearing.** Now that Planning applies the source policy, class decides
admissibility. Measured across the 40 `same_content_as` edges:

- **18 of 40 carry a different `doc_type` on each side** — one file is an `hvhz_noa` on one
  side and `unspecified` on the other, or a `real_miami_dade_noa_vinyl_fence` against a
  `spec_sheet`.
- **38 of 40 carry a different manufacturer.**

Without the rule, identical bytes yield different `source_class` values depending on which
record a `SourceRef` happens to name — so the same evidence is admissible or not by
accident of filing. That is a silent, run-time admissibility difference with no error
anywhere, which is the failure class §1.4 exists to prevent.

**This also answers `planning-asks.md` §5 Q3** — the ambiguity is resolved by curation on
our side, not by a schema change on yours. `SourceDoc` grows `also_filed_as`; nothing else
moves. With the §2.1 correction, it is **15 groups**, not 14, and the fifteenth is the hard
one: identical *extracted text* with different bytes, so `same_content_as` does not link it.

---

## 6. What Planning has to do with this

| | |
|---|---|
| Locale bundles | 21 platform codes need `en` + `he` entries: ten `SOURCE_*`, eleven `WARN_*`. Plus `CURATION_MACHINE_CONSENSUS` if not already added, and `parameter_condition_excluded` from T2 |
| Nothing to negotiate | every item here is a §2 registry addition |
| One thing to note | all eleven report non-zero as of 2026-08-27; the five that were empty when this list was drafted are fixed (§3.1) |
| One thing we owe back | a `family` column on the reader table, or a decision to ship reader ids instead (§4) |
