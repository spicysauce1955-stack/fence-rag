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
- **The level-2 population of this store is zero and cannot change** until the review loop
  exists. `PROMOTABLE` is `("accepted", "corrected")` and nothing in the package writes
  either; `reviewer` is NULL on all 1,225 readings `[measured]`.

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

**Published** counts the 282 warnings in the current snapshot. **Elements** counts every
element in the store whose text matches, published as a warning or not. The gap between
those two columns is the finding in §3.1.

| Code | Published | Elements | Docs | `ref_id` | Verbatim exemplar |
|---|---|---|---|---|---|
| `WARN_UTILITY_LOCATE` | 7 | 130 | 26 | `eb2c863494b90243` | "Call before you dig." |
| `WARN_FREEZE_THAW` | 12 | 83 | 6 | `882b1218393c89e8` | "Caution – In climates that experience freeze-thaw cycles, this installation method could result in post cracking over time." |
| `WARN_POST_STRIKE_UNSUPPORTED` ⚠ | **0** | 71 | 7 | `ec094805f6f9e8b2` | "Never strike the PVC post without a wood support" |
| `WARN_EYE_PROTECTION` | 18 | 78 | 41 | `9ea589d2ed085734` | "ALWAYS WEAR SAFETY GLASSES." |
| `WARN_PARTS_MISSING_DAMAGED` | 6 | 35 | 35 | `b8ad6543485400cf` | "DO NOT attempt to assemble the kit if parts are missing or damaged." |
| `WARN_DO_NOT_RETURN` | 5 | 33 | 33 | `6aa84dabb01fa9c9` | "DO NOT return the product to the store." |
| `WARN_FROST_LINE` ⚠ | **0** | 254 | 28 | `382abfe6174ee952` | "Check local codes for frost line depth and regulations." |
| `WARN_POOL_CODE` | 6 | 117 | 23 | `7593394e9edc8b8b` | "Not pool code approved." |
| `WARN_POST_TOP_CUT` ⚠ | **0** | 25 | 5 | `9a87439073cfe499` | "Never cut the top of the post" |
| `WARN_WARRANTY_EXCLUSION` ⚠ | **0** | 16 | 11 | `8ad14577225d2658` | "Separate and distinct warranties for hardware and other products are not covered under this warranty." |
| `WARN_PANEL_BOTH_ENDS` ⚠ | **0** | 20 | 5 | `7eac16268355bea3` | "Never attach both ends of a panel to posts" |

### 3.1 Five of the eleven cannot currently be emitted

The five marked ⚠ have **zero instances in the published warning set** and between 16 and
254 in the store. They are not missing from the corpus — they are missing from the
*warnings*.

The cause is the detector. `snapshot.py` recognises a warning by a severity lexeme
(`WARNING:`, `NOTE:`, `CAUTION:`) or a hazard regex. All five of these are written as
ordinary bullet points inside installation lists:

> • Level and square fence
> • To lower a post, place a wood block from corner to corner on the post and carefully
>   tap with a mallet
> • **Never strike the PVC post without a wood support**

No lexeme, no hazard word — so it is an `installation_step`, not a warning, and it never
reaches `warnings[]`. The same is true of the frost-line check, the post-top rule and the
panel-both-ends rule. `WARN_WARRANTY_EXCLUSION` fails differently: warranty exclusions live
in warranty documents as running prose, and the detector never looks there.

**This is ours to fix and it is not a code change to the registry.** The eleven codes are
right; the publisher cannot yet produce five of them. The exemplars and `ref_id`s above are
minted from the elements directly and resolve today, so the *evidence* exists — only the
classification does not. Registering all eleven now is still correct: a code with zero
current instances costs Planning one bundle entry and nothing else, and the alternative is
shipping a list that changes size later.

Filed as a defect against the publisher, not against this list.

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

**`families` cannot be populated from the store.** The three readers are named
`calibration-A`, `calibration-B` and `codex-C` `[measured]`; nothing records which model
family each belongs to. The mapping asserted in §3.3 — `claude-sonnet` + `openai-codex` —
is true and lives only in the heads of the people who ran the readings. Either the reader
table grows a `family` column or the param ships as a list of reader ids and Planning
renders those. **We propose the column**, since a reader id is meaningless to a curator and
the whole point of the code is that *two different families* agreed.

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
| One thing to note | five `WARN_*` codes will report zero instances until the publisher's detector is fixed; the bundle entries are still worth adding now |
| One thing we owe back | a `family` column on the reader table, or a decision to ship reader ids instead (§4) |
