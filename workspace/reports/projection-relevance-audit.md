# Relevance audit — retrieval projection

```text
Status: Audit. Findings only.
Action taken: none. No classification, indexing, weighting or projection
              change has been applied, pending review.
```

Audited: `retrieval_units` and `retrieval_fts` as built by
`store.build_retrieval_units`, over the full-corpus store (144 documents, 2,147
pages, 81,794 canonical elements, 10,886 units). Method: direct measurement
against the store, plus running all 44 gold questions through
`search_evidence` and inspecting the composition of the result lists. Every
number below is reproducible from the queries in §7.

---

## 1. Summary of findings

| # | Severity | Finding | Evidence |
|---|---|---|---|
| F1 | **high** | Heading elements are excluded from the projection, and a third of them are unreachable by any other route | 20,925 headings excluded; 7,097 (33.9%) appear in no unit's `heading_path`; 27 pages consist only of headings and figures and so are absent from the index entirely |
| F2 | **high** | Near-half of all units duplicate another unit's text; boilerplate consumes result slots | 5,060 units (46.5%) share text with another unit; 29.5% of top-10 slots across the gold set hold duplicated text |
| F3 | medium | Result lists repeat pages | 20.2% of top-10 slots are a second (or third) unit from a page already in the list; a 10-result list averages ~8 distinct pages |
| F4 | medium | Unit length distribution is dominated by fragments, which BM25 length normalisation favours | 17.8% of units are under 20 characters, 45.0% under 80; 16.6% of top-10 slots are units under 40 characters |
| F5 | medium | Table units carry an entire grid as one string, diluting the matching row | table units average 381 chars, max 4,532; the CLFMI wind-load table on p17 is a single 3,725-char unit |
| F6 | medium | 30 pages have no unit at all | 27 of them do have canonical elements — headings and figures only (see F1) |
| F7 | low | Residual mojibake reaches the index | 33 units still fail the mojibake test; the per-page check has a 200-character judgement floor, so short corrupted pages slip through |
| F8 | medium | OCR-derived and text-layer units compete on identical terms | 3,693 units (33.9%) are OCR text; word confidence is recorded on the page but is not available to ranking or exposed in the result |
| F9 | info | The metadata columns are doing real work and should not be discarded | all 44 gold queries match more units with `title`/`manufacturer`/`doc_type` in play than against `text` alone |
| F10 | info | The within-page ceiling on unit support is 0.769 | measured; this bounds what a second-stage within-page retrieval can achieve (§5) |

---

## 2. F1 — Excluded headings are a recall hole, not just a ranking choice

Headings were removed from the projection because one- and two-word units won
BM25 length normalisation against the tables and OCR paragraphs that hold
answers. That fixed the ranking problem it was aimed at and remains the right
call for *unit* construction. The unintended consequence was not measured at
the time.

Heading text reaches the index only through the `heading_path` column of units
*beneath* the heading, on the same page, under the same path. Where no such unit
exists, the text is unreachable:

- 20,925 heading elements are excluded, carrying 371,337 characters.
- 7,097 of them (33.9%) appear in no unit's `heading_path` anywhere.
- 27 pages have canonical elements but no unit, because every element on them is
  a heading or a figure. Example: `Digger-Specialties-Polyvinyl-Fence-Brochure`
  page 16 has 28 elements, all headings — `PICKET`, `MODELS`, `Features`,
  `Good Neighbor Bottom`, `Rail H-Channel Aluminum`, `Reinforcement`,
  `Good Neighbor Notched Pickets`, … The page is not searchable.

This is not hypothetical. Two failing gold questions trace directly to it:

| Question | Expected term | Where it lives | Indexed? |
|---|---|---|---|
| gq-102 | `Wellington 6x6 Semi-Privacy Panel` | heading, p1 of `73013822_Wellington6x6Semi-PrivacyPanel_Instructions.pdf` | **no** |
| gq-103 | `Pergola Kits` | heading, p1 of `pergola-kit-installation-instructions.pdf`; also p16/p17 of `classic-product-brochure.pdf` | **no** |

Both questions rank the correct document **first** with page support 1.0 and unit
support 0.333. In this corpus product names live in headings, which is precisely
the vocabulary an `exact_product` query uses.

## 3. F2/F3/F4 — Result lists are spent on redundancy and fragments

Measured over 440 top-10 slots from the 44 gold queries:

| Slot property | Share |
|---|---|
| holds text that is duplicated elsewhere in the index | 29.5% |
| is a unit under 40 characters | 16.6% |
| repeats a page already present in the list | 20.2% |

The duplication is structural, not incidental. The worst offenders:

| Occurrences | Documents | Text |
|---|---|---|
| 178 | 1 | `Illusions Fence ©2020 All Rights Reserved` |
| 150 | 14 | `1. None.` |
| 78 | 1 | `*Required support for gate posts and strength for hardw…` |
| 61 | 7 | `USE (2) PIECES OF 1/2" REBAR IN HINGE,` |
| 44 | 9 | `1, None.` |

`1. None.` is the "Evidence Submitted" boilerplate that appears on every
Miami-Dade NOA. It is legitimate source content and must stay in the canonical
store (prohibition 3), but as an indexed unit it is pure noise: 194 units across
14 documents whose entire text is a two-word negation.

Unit length distribution, for context: min 1, p10 8, median 99, p90 696, max
4,532 characters, mean 255.

## 4. F5/F7/F8 — Three smaller defects

**Oversized table units.** A table becomes one unit containing its whole grid
flattened to `cell | cell | cell` rows. For a 31×20 wind-load table that is a
3,725-character unit in which the one relevant row is 2% of the text. BM25 then
penalises the unit for length while the matching row is diluted. The cells exist
individually in `table_cells` and are not searchable there.

**Residual mojibake.** 33 units still fail the mojibake test on their own text.
The per-page detector requires 200 characters before it will judge a page, so a
short page of corrupted text passes through. Low volume, but these units are
unreadable and cannot be relevant to anything.

**No confidence signal in ranking.** 33.9% of units are OCR text, 3,693 of them,
and 177 pages were OCR'd below 70% mean word confidence. A garbled unit from a
50%-confidence drawing sheet is ranked identically to clean text-layer prose, and
the result object does not carry the page's OCR confidence, so a consumer cannot
discount it either.

## 5. F10 — What a within-page second stage can and cannot reach

Measured over the 41 answerable gold questions that carry answer terms:

| | Value |
|---|---|
| unit support as built | 0.623 |
| support if the best element on each already-retrieved page could be chosen | **0.769** |
| headroom | 0.147 |
| questions where a better element exists on an already-retrieved page | 13 of 41 |
| questions already at full support | 16 of 41 |

Two consequences for the second-stage work:

1. The 0.70 acceptance target is reachable but not comfortably — it requires
   capturing roughly half the available headroom (0.077 of 0.147). A partial or
   conservative implementation will miss it.
2. The ceiling is only attainable if the second stage may select from **all**
   canonical elements on the page, headings included. Restricted to elements that
   are currently indexed as units, gq-102 and gq-103 stay unreachable (§2). This
   is a retrieval-time selection over canonical rows, so it does not require any
   change to the projection.

## 6. Recommendations — not applied

Listed for review. Each carries the risk that argues against it, because two of
them cut against a trade-off already measured: raising the `heading_path` BM25
weight from 0.55 to 1.6 lifted recall@10 to 0.854 and MRR to 0.683 but halved
no-answer precision, 0.667 → 0.333.

| # | Recommendation | Addresses | Risk |
|---|---|---|---|
| R1 | Project a heading as a unit only when no other unit on that page would carry it in `heading_path` — a fallback, not a general re-admission | F1, F6 | reintroduces some short units; needs the no-answer metric watched, per the weight experiment |
| R2 | Alternatively, attach the nearest heading text to the *first* unit beneath it as a prefix, rather than indexing headings separately | F1 | duplicates heading text into unit `text`, double-counting it against the `heading_path` column |
| R3 | Collapse exact-duplicate unit text within a document to one unit, linking the others; keep every canonical element | F2 | none to canonical data; changes result ids, so anything caching them must be rebuilt |
| R4 | Suppress units whose text is below a minimum information threshold (e.g. under 12 characters, or matching known boilerplate) from the *index only* | F2, F4 | a hard threshold will drop some genuine short answers such as a bare dimension |
| R5 | Cap results per page in `search_evidence` (one unit per page, or two) | F3 | reduces recall for pages that genuinely hold two distinct answers |
| R6 | Add row-level table units alongside the whole-grid unit, from `table_cells` | F5 | multiplies unit count for large tables; needs the duplicate-suppression of R3 to avoid flooding |
| R7 | Lower the mojibake judgement floor from 200 characters, or apply the check to unit text at projection time | F7 | more false positives on short legitimate pages; would need re-extraction to take effect on canonical rows |
| R8 | Carry `ocr_mean_confidence` into the result object, and consider it as a ranking signal | F8 | ranking on confidence risks burying the scanned NOAs, which are the highest-value documents |
| R9 | Keep the metadata columns and the current weights | F9 | none; this is a recommendation to *not* act |

R1–R7 are indexing or classification changes and are therefore held until this
audit is reviewed. R8's reporting half (exposing confidence in the result) is
additive and touches no indexing.

## 7. Reproducing these numbers

```sql
-- F1: headings not reachable through any unit's heading_path
CREATE TEMP TABLE hp(t TEXT);
INSERT INTO hp SELECT DISTINCT j.value FROM retrieval_units u, json_each(u.heading_path) j;
SELECT COUNT(*) FROM elements e WHERE e.element_type='heading'
  AND NOT EXISTS (SELECT 1 FROM hp WHERE hp.t = COALESCE(NULLIF(e.text,''), e.ocr_text));

-- F1/F6: pages with canonical elements but no unit
SELECT COUNT(*) FROM pages p
 WHERE NOT EXISTS (SELECT 1 FROM retrieval_units u
                    WHERE u.version_id=p.version_id AND u.page_no=p.page_no)
   AND (SELECT COUNT(*) FROM elements e WHERE e.page_id=p.page_id) > 0;

-- F2: duplicate unit text
SELECT COUNT(*) groups, SUM(n) units FROM
  (SELECT text, COUNT(*) n FROM retrieval_units GROUP BY text HAVING n>1);

-- F4: unit length distribution
SELECT length(text) FROM retrieval_units ORDER BY 1;

-- F8: OCR share of the index
SELECT text_source, COUNT(*) FROM retrieval_units GROUP BY 1;
```

Every figure in this audit, including the top-10 composition and the within-page
ceiling, is produced by:

```bash
python3 -m fence_evidence.cli audit          # writes workspace/tests/projection-audit.json
```

`fence_evidence/audit.py` is read-only by construction — it opens the store with
`mode=ro` — so the audit can be re-run after any accepted change and these
numbers checked rather than trusted.
