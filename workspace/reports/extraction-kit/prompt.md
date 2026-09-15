You are extracting structured product knowledge from one source PDF for a fence
knowledge base. Work only from the attached document. Do not use any other document,
your own product knowledge, or the web.

## What you have

- The source PDF.
- `registry-card.md` — the closed vocabularies. Every controlled field must take a value
  from it. Nothing else is permitted.

**Open and look at every page as an image, not only as text.** A large part of what this
document carries is printed inside drawings and will never appear in a text layer. If you
cannot view a page, say so for that page rather than guessing what is on it.

## Hard rules

1. **Never invent an identifier.** No IDs, no reference numbers, no hashes, no keys.
   Where a schema wants one, write `null` and name it in `withheld_fields`.

2. **Every claim carries a page and a citation, and declares how you got it.**
   - `citation_kind: "text"` — a character-for-character quote, read from the page.
   - `citation_kind: "visual"` — printed inside a drawing or image: give the page, where it
     sits, what it measures, and the glyphs as you read them.
   - `read_by`: `"eye"` if you looked at the rendered page, `"tool"` if it came from a text
     extractor you ran. **Never label a tool result `visual`.** If you ran an extraction
     tool, say so — the whole point of a `visual` reading is that it is something a tool
     could not give us.

3. **Do not refuse a number because you cannot quote it as text.** A dimension printed as a
   stacked fraction — numerator over denominator with a bar — is a real, readable number.
   Read it, record the composed value, and put the digit fragments in `raw_fragments`.
   Withholding it is a failure, not caution.
   `glyph_form`: `plain` (printed on one line with a slash) · `stacked_fraction` (bar) ·
   `composed_fraction` (one ligature glyph: `½`, `⅞`, `¾`) · `badge` · `null`.
   A fraction is never `plain` unless the page really prints it on one line with a slash.

4. **`value_raw` is what the PAGE PRINTS, not what a text extractor emits.** These differ,
   and the difference is dangerous. A page printing `2½"` frequently reaches a text layer as
   `21/2"` — and the same page can emit `19½"` correctly two lines later. Look at the page
   and write `2½"`. Put the extractor's form in `raw_fragments`.
   **A `value_raw` of `21/2"` is read by the next system as ten and a half inches.**

5. **Keep real inconsistency; never invent it.** If one page genuinely prints `66 1/2"` and
   the next prints `661/2"`, keep both. If one says `Structural Post Channels` and another
   `Structural Post U-Channels`, keep both. But do not record two different forms for two
   places where the page prints the same glyph — that manufactures a difference that is
   not there.

6. **Names matter as much as numbers, and a name needs an identity.** Record every product
   name, style, series, model, tier, rail or profile name, colour, finish, badge and marking
   as its own claim — not only the dimension beside it. A size says how big something is; a
   name is what lets two documents refer to the same thing.
   **Every name record carries `canonical`**: the same entity written one way, for every
   printed form of it. A page that prints `PICKET` in a drawing label, `Picket` in a heading
   and `picket` in prose has named ONE thing three times — keep all three `name` values
   exactly as printed, and give all three the same `canonical`. Same for `Bufftech` and
   `Bufftech®`, `CHESTERFIELD` and `Chesterfield`.
   Without this, a thousand name records collapse to two hundred entities that nothing can
   join, and rule 5 — which correctly tells you to keep the printed forms — becomes the
   reason the output is unusable. `canonical` is how both survive.

7. **A relation is knowledge, not just two strings.** Where the document pairs one thing
   with another — this post code goes with that section, this cap fits that post, this
   hardware belongs to that gate — record the pair as a **`Combination` draft** with both
   members named, not as two separate claims. Transcribing both halves and never joining
   them loses the only thing the page was printed to say.

8. **Draft the thing, not only the words about it.** A parts table row is a `Part` with
   `SpecField`s. A catalogue page naming a style with its heights, colours and post is a
   `FenceModel`. Several of these have no publisher on our side yet — draft them anyway and
   say so in `withheld_fields`. A draft that cannot publish still tells us what the
   publisher has to accept, and that is a question we cannot answer without one.

9. **Never invent a condition.** `conditions` uses only the keys on the registry card, and
   only where the source states the condition. If the source does not say "at Exposure C",
   there is no exposure condition. An unconditioned value is not a universal value — write
   `"conditions_stated": "none stated"`.

10. **A prohibition is not a step.** "Never strike the PVC post", "Do not return the product"
   — these are `warnings`, never `AssemblyStep`s. See the registry card.

11. **Print order is not a dependency — but an edge must point somewhere.** `requires` stays
    empty unless the source says one thing must happen before another, and you quote the
    words. When you do record an edge, `step` must name **another step's `key`**; an edge
    with a null target is not a dependency, it is a note. Give every step a `key` that is
    unique within its procedure so edges have something to point at. And when a step names a
    duration or a cure time, give it an `Elapsed` slot carrying a real Quantity —
    `72 hours` is `{"amount_milli": 259200000, "unit": "second_milli"}`.

12. **One claim is one proposition.** A stray character, a repeated table rule, a lone
    hyphen is not a claim. Padding the count is worse than a smaller honest count.

13. **Exact counts only.** Never "approximately", "about", "~". If you cannot count it, say
    so.

14. **Confidence, not deletion.** Anything uncertain stays in the output with
    `confidence: "clear" | "probable" | "unclear"` and a note on what is ambiguous.

15. **`curation_level` is `0` on every record.** You are a machine reading. Never claim a
    human checked anything.


## Do all six steps

Complete every step in one pass. Do not stop to ask whether to continue, do not ask which
step to do next, and do not summarise instead of producing output. If the document is long,
keep going — a partial answer is worse than a slower one.

**Step 1 — Page inventory.** Take the filename from the attached file and count its pages
yourself. Then, for every page: what is on it, how many distinct claims it carries, and
whether any part of it is degraded or unreadable. State the total page count.

**Step 2 — Evidence.** Every distinct claim in the document, with its page and citation.
Do not classify or interpret yet. Include prose, table cells, drawing callouts, captions,
badges, footnotes and marginal notes.

**Step 3 — Names and identity.** Separately list every name the document prints: products,
styles, series, tiers, profiles, colours, finishes, part codes, badges. For each, say what
it names and what it is printed next to. This step exists because names are the most
commonly missed content in this document type.

**Step 4 — Mapping.** Map what you can onto the registry card's shapes. Populate only
fields the source supports. Leave everything else `null` and list it in `withheld_fields`.
Say plainly how many complete, publishable objects you produced — `0` is an honest and
common answer.

**Step 5 — Refusals, warnings and gaps.** Everything you could not map, as a `Gap` using
the card's `kind`, `closes_by` and `severity`. Every prohibition and hazard goes in
`warnings`, never in a procedure's steps.

`registry_proposals` is for a **new registry entry**, not a value you could not place.
Propose one only where a distinct *concept* recurs and the card has no name for it, and say
how many times you saw it. `30" Deep` is a value, not a proposal. Every proposal must name
its `registry`; if you cannot name one, you do not have a proposal. Expect a handful, not
hundreds.

**Step 6 — Self-audit, measured not asserted.** Re-read the document and check your own
output against it. Every number you report here must come from re-checking, not from
counting what you already wrote: **re-verify each quote against its page** and report the
real failure count. A `citations_failed: 0` you did not measure is worse than an honest
non-zero.

Report: pages read, claims found, claims mapped, claims refused, citations re-verified,
citations that failed, warnings found, names found, visual readings, composed and stacked
fractions read. Then answer three questions explicitly:
  - Which of your `clear` readings would you now downgrade?
  - Which `visual` readings could a text extractor have produced? Say so plainly.
  - **What did you not write down?** Name any page, table, drawing or region you skipped or
    only skimmed. A self-check verifies what you wrote; this is the only place a gap in
    coverage can surface.
  - **What did this kit give you no place for?** Name anything the document clearly states
    that the registry card has no shape or field to hold — the concept, how often it
    appeared, and one quoted example. Answer this even if the answer is "nothing". A missing
    shape looks exactly like an absent fact in the output, and you are the only one who can
    tell us which it was.

## Output

Give me **one JSON file** in this shape, then a short markdown summary of Step 6 only.

```json
{
  "document": "<the attached file's own name>",
  "pages": 0,
  "curation_level": 0,
  "step_1_pages": [
    {"page": 1, "contents": "", "claim_count": 0, "legibility": "clean|degraded|unreadable"}
  ],
  "step_2_evidence": [
    {
      "page": 1,
      "category": "",
      "citation_kind": "text|visual",
      "quote": "",
      "visual_location": "",
      "statement": "",
      "value_raw": [""],
      "glyph_form": "plain|stacked_fraction|composed_fraction|badge|null",
      "raw_fragments": [],
      "quantity": {"amount_milli": 0, "unit": "mm", "value_raw": [""]},
      "read_by": "eye|tool",
      "confidence": "clear|probable|unclear",
      "curation_level": 0
    }
  ],
  "step_3_names": [
    {"page": 1, "name": "<exactly as printed>", "canonical": "<one spelling for this entity>",
     "names_what": "", "printed_beside": "", "citation_kind": "text|visual"}
  ],
  "step_4_mapping": {
    "warnings": [
      {"code": null, "text_en": "", "applies_to": "",
       "evidence": {"page": 1, "quote": ""}, "curation_level": 0}
    ],
    "relations": [
      {"from": "", "to": "", "relation": "", "evidence": {"page": 1, "quote": ""},
       "curation_level": 0}
    ],
    "source_doc": {"source_class": null, "version_status": "unknown", "issue_date": null},
    "items": [
      {
        "evidence_ref": {"page": 1, "quote": ""},
        "target": "",
        "fields": {},
        "conditions": {},
        "conditions_stated": "none stated",
        "withheld_fields": [],
        "curation_level": 0
      }
    ],
    "parts": [
      {"id": null, "type": "", "name_en": "", "qty": null,
       "spec": [{"key": "", "agree": "==", "value": {"amount_milli": 0, "unit": "mm", "value_raw": [""]}}],
       "evidence": {"page": 1, "quote": ""}, "withheld_fields": [], "curation_level": 0}
    ],
    "models": [
      {"id": null, "name_en": "", "grade": null, "height_support": null,
       "option_axes": [{"key": "", "kind": "enum", "values": []}],
       "evidence": {"page": 1, "quote": ""}, "withheld_fields": [], "curation_level": 0}
    ],
    "combinations": [
      {"id": null, "members": ["", ""], "relation": "",
       "evidence": {"page": 1, "quote": ""}, "withheld_fields": [], "curation_level": 0}
    ],
    "procedures": [
      {
        "scope_source_wording": "",
        "scope_entity_ref": null,
        "steps": [
          {"key": "<a key unique within this procedure, e.g. \"3.2-fill-hole\">",
           "kind": "", "scope": "",
           "slots": [{"target": "Footing", "part": "concrete"}],
           "requires": [{"kind": "after", "step": "<the key of the OTHER step>",
                         "evidence": {"page": 1, "quote": "the words that establish it"}}],
           "text_en": "", "evidence": {"page": 1, "quote": ""}, "curation_level": 0}
        ]
      }
    ],
    "complete_publishable_objects": 0
  },
  "step_5_gaps": [
    {"kind": "", "subject_description": "", "because_description": "",
     "would_close": "", "closes_by": "", "severity": "",
     "evidence": [{"page": 1, "quote": ""}], "withheld_fields": [], "curation_level": 0}
  ],
  "registry_proposals": [
    {"registry": "", "proposal": "", "source_wording": "", "purpose": ""}
  ],
  "step_6_audit": {
    "pages_read": 0,
    "claims_found": 0,
    "claims_mapped": 0,
    "claims_refused": 0,
    "citations_verified": 0,
    "citations_failed": 0,
    "names_found": 0,
    "distinct_canonical_entities": 0,
    "visual_readings": 0,
    "stacked_fractions_read": 0,
    "composed_fractions_read": 0,
    "warnings_found": 0,
    "parts_drafted": 0,
    "models_drafted": 0,
    "combinations_drafted": 0,
    "visual_readings_a_tool_could_have_produced": 0,
    "corrections": [{"page": 1, "was": "", "now": "", "why": ""}],
    "downgraded_readings": [],
    "not_written_down": [],
    "kit_had_no_place_for": [{"concept": "", "occurrences": 0, "example": {"page": 1, "quote": ""}}],
    "human_review": false,
    "curation_level": 0
  }
}
```
