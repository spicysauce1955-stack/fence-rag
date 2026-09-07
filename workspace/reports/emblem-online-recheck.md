# Emblem online recheck — 2026-09-07

Tavily MCP search and extract were used in this pass. Earlier searches did find
useful data; treating every unresolved field as missing online data was too broad.

- Freedom's manufacturer Emblem page again states 7/8 ×6 inch T&G boards and
  links the White6×8 project plan. Thickness is positive family evidence; it is
  not installed pitch or groove depth.
  https://freedomproduct.com/products/emblem-vinyl-fencing/
- The Freedom cutdown guide again specifies3 inches total added rail length
  relative to finished panel width. It also describes longitudinal board trimming.
  Engine trimming remains unsupported, which is an implementation gap distinct
  from lack of instructions. Neither rule assigns per-end engagement or profile
  clearance.
  https://pdf.lowes.com/productdocuments/54fd70b7-a336-462a-8dbf-5987a4c89506/63852631.pdf
- Catalyst manual34118672 REV5.25 gives2 rails,15 boards,2 U-channels. No exact
  legacy73014714 component-equivalence statement was established here.
  https://www.catalystfence.com/wp-content/uploads/CAT-BOM-34118672-EmblemPanelKit_5-25.pdf

The allegedly missing revised manual was recoverable at its retained URL. Its
SHA-256 exactly matches the previous record,20a881589b9f9035b3f6e5bc6c38e80747659cd1c4df0fb0ea3558a058a33a95.
It is restored at workspace/catalog/emblem-linked-installation.pdf. All four
assembly statements match the page4 text column after whitespace normalization;
full-page text interleaves figure labels, so it was not used to claim mismatches.
See emblem-recovered-manual-check.json. This supersedes earlier local-absence
statements in audit and handoff reports. No canonical ingestion or human review
was created by recovery.

https://pdf.lowes.com/productdocuments/1c328a11-74cb-411d-b7af-c1b2a3513614/64773145.pdf

Still not established in the inspected primary sources: exact legacy board
installed pitch/groove engagement, top/bottom rail pocket depths and board seats,
per-end rail/post engagement and shared clearance. Related replacement-product
sizes must remain scoped to those products. Not having found these values is a
bounded search result, not proof that no documentation exists.
