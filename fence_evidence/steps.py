"""Splitting an installation-guide bullet block into step candidates.

A `list` element holds a whole bullet block — `• Insert post in hole • Determine
rough height • Fill hole…` is ONE row with ONE bounding box. The unit an
`AssemblyStep` is about therefore does not exist in the store, and this module
manufactures it: one segment per bullet, carrying a character span back into the
element it came from.

Nothing here classifies a step into `kind`/`scope`/`slots`; that is judgement and
it belongs to a person (`docs/assembly-step-design.md` §5). This module only
decides where one bullet stops and the next begins, which is mechanical — and
turned out to be much less obvious than it looks.

**It classifies rather than discards.** A footnote, a `Note:` rider and a lettered
branch label are all emitted with a `kind`, because a reviewer needs to see
everything on the page, and a splitter that silently eats the parts it does not
understand loses them invisibly.

`[measured]` 2026-09-03 over 70 installation manuals, 6,105 `list` elements and
4,629 bullets. Every rule below is a measured hazard, not a precaution:

* **`•` is not the only leader, and `text_source` disambiguates.** OCR emits zero
  U+2022 — not once in 834 OCR'd list elements — and renders the glyph as `*`.
  But in the text layer `*` is a FOOTNOTE marker (71 elements, nearly all the
  same `* Caution – In climates that experience freeze-thaw cycles…`). Reading a
  text-layer `*` as a bullet manufactures steps the page does not contain;
  ignoring an OCR `*` loses 464 real ones.
* **`-` is a real second-level bullet** — 753 text-layer elements.
* **The whitespace after a leader is three characters**: U+0020 (2,656),
  U+2002 EN SPACE (1,921) and TAB (52).
* **A `•` segment can contain a whole nested procedure.** 60 corpus-wide; the
  worst is 871 characters holding a two-branch lettered choice and 13 sub-steps.
* **A trailing `Note:` is a rider, not part of the instruction** — 14 segments
  end with one and none begins with one.
* **195 of 4,629 segments begin with a split capital** (`T\\namp`, `I nsert`) —
  pdftotext emitting a bullet's leading character as its own text run. That is
  the token any verb-based reading looks at first, so it is proposed for repair
  and NEVER repaired in place: of the 20 distinct space-form artifacts only 7 are
  real damage, and the rest are legitimate text (`Insert post A into hole`,
  `Coloque el canal en U en el poste`).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# The three characters that follow a leader. A bare `\s` would also swallow the
# newline that ends the previous segment, and `.lstrip(" ")` misses two of them.
LEADER_GAP = " \t  "

# `N. Title` typed as `list` rather than `heading` — the section spine a bullet
# block hangs off. 783 elements corpus-wide begin with one.
SECTION_RE = re.compile(r"^\s*\d{1,2}\s*[.)]\s+\S")
# `a.` / `b.` — a lettered alternative inside one bullet. Matched against a
# single line, never against the block: `re.match(block, pos)` does NOT anchor
# `^` at `pos`, so a block-level match silently never fires. That bug shipped
# into the first version of this file and cost the branch scoping entirely.
BRANCH_RE = re.compile(r"^([a-z])[.)]\s+\S")
# A rider the guide prints under an instruction; never the start of one.
RIDER_RE = re.compile(r"^(Note|NOTE|Caution|CAUTION|Tip|TIP)\b\s*[:.-]?", re.ASCII)
# pdftotext emitting a leading character as its own run, in both spellings.
SPLIT_CAP_RE = re.compile(r"^([A-Z])[ \n]([a-z]{2,})\b")


@dataclass(frozen=True)
class Segment:
    """One classified slice of a bullet block.

    `text` is verbatim — `block[start:end]` reproduces it exactly, which is what
    lets a review anchor on (element, span, text) and a citation stay honest.
    `repair` is a PROPOSAL and never replaces `text`.
    """
    text: str
    start: int
    end: int
    leader: str
    depth: int          # 0 a top-level bullet, 1 a `-` sub-bullet
    kind: str           # step | note | branch | footnote | section | prose
    branch: str | None  # the lettered alternative this sits under, if any
    repair: str | None  # proposed whole-segment text, when damage is detected

    @property
    def body(self) -> str:
        """The instruction without its leader glyph, whitespace collapsed.

        `text` stays verbatim because the span and the review anchor depend on
        it; `body` is what a reader and a classifier actually want.
        """
        inner = self.text[1:] if self.leader else self.text
        return " ".join(inner.split())


def _leaders(text_source: str) -> tuple[str, ...]:
    """Which characters open a bullet, for this element's provenance.

    The asterisk flips meaning on `text_source` and nothing else: a footnote
    marker in the text layer, the bullet glyph under OCR.
    """
    return ("*", "-") if text_source == "ocr" else ("•", "-")


def _propose_repair(text: str) -> str | None:
    """A whole-segment repair when the first word is split, else None.

    Only the first token is considered. The defect is systematically at the
    START of a segment — it is the bullet's leading character emitted as its own
    run — so a match anywhere else is far more likely to be real text.
    """
    flat = " ".join(text.split())
    m = SPLIT_CAP_RE.match(flat)
    if not m:
        return None
    joined = m.group(1) + m.group(2)
    return joined + flat[m.end():]


def _classify(body: str, leader: str, depth: int, branch: str | None) -> str:
    if leader == "*" and depth == 0 and branch is None and RIDER_RE.match(body.lstrip()):
        return "footnote"
    if RIDER_RE.match(body.lstrip()):
        return "note"
    return "step"


def split_block(block: str, *, text_source: str = "pdf_text_layer") -> list[Segment]:
    """Split one element's text into classified segments, discarding nothing.

    Returns segments in source order. Spans never overlap and always slice back
    to their own text.
    """
    if not block or not block.strip():
        return []

    leaders = _leaders(text_source)
    footnote_leader = "*" if text_source != "ocr" else None

    if SECTION_RE.match(block):
        return [Segment(text=block, start=0, end=len(block), leader="",
                        depth=0, kind="section", branch=None, repair=None)]

    # Line-based, because `[measured]` no bullet in this corpus ever starts
    # mid-line inside a `list` element -- 0 of 3,146 bulleted elements. The
    # mid-line separators (`site.com • (800) 336-2383`) are all headings and
    # paragraphs, which this never sees.
    offsets, pos = [], 0
    for line in block.split("\n"):
        offsets.append((pos, line))
        pos += len(line) + 1

    cuts: list[tuple[int, str, int, str | None]] = []
    for start, line in offsets:
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        m = BRANCH_RE.match(stripped)
        if m:
            cuts.append((start + indent, "", 0, m.group(1)))
            continue
        if not stripped:
            continue
        ch = stripped[0]
        if len(stripped) > 1 and stripped[1] in LEADER_GAP:
            if ch in leaders:
                cuts.append((start + indent, ch, 1 if ch == "-" else 0, None))
            elif ch == footnote_leader:
                cuts.append((start + indent, ch, 0, None))

    if not cuts:
        return [Segment(text=block, start=0, end=len(block), leader="", depth=0,
                        kind="prose", branch=None, repair=_propose_repair(block))]

    out: list[Segment] = []
    if cuts[0][0] > 0 and block[:cuts[0][0]].strip():
        head = block[:cuts[0][0]]
        out.append(Segment(text=head, start=0, end=cuts[0][0], leader="",
                           depth=0, kind="prose", branch=None,
                           repair=_propose_repair(head)))

    current_branch: str | None = None
    for n, (start, leader, depth, label) in enumerate(cuts):
        end = cuts[n + 1][0] if n + 1 < len(cuts) else len(block)
        text = block[start:end]
        if label is not None:
            current_branch = label
            out.append(Segment(text=text, start=start, end=end, leader="", depth=0,
                               kind="branch", branch=label, repair=None))
            continue
        body = text[1:].lstrip(LEADER_GAP) if leader else text
        kind = _classify(body, leader, depth, current_branch)
        out.extend(_split_rider(text, start, leader, depth, kind, current_branch))
    return out


def _split_rider(text: str, pos: int, leader: str, depth: int, kind: str,
                 branch: str | None) -> list[Segment]:
    """Peel a trailing `Note:` line off an instruction.

    The rider keeps its own span, so nothing is lost and the reviewer sees both.
    A rider is only ever trailing — no corpus segment begins with one — so a
    match on the first line means the whole segment IS the note.
    """
    lines = text.split("\n")
    cut = None
    for n, line in enumerate(lines):
        if n and RIDER_RE.match(line.strip()):
            cut = n
            break
    body = text[1:].lstrip(LEADER_GAP) if leader else text
    if cut is None:
        return [Segment(text=text, start=pos, end=pos + len(text), leader=leader,
                        depth=depth, kind=kind, branch=branch,
                        repair=_propose_repair(body))]
    head_len = sum(len(l) + 1 for l in lines[:cut])
    head, tail = text[:head_len], text[head_len:]
    head_body = head[1:].lstrip(LEADER_GAP) if leader else head
    return [
        Segment(text=head, start=pos, end=pos + head_len, leader=leader,
                depth=depth, kind=kind, branch=branch,
                repair=_propose_repair(head_body)),
        Segment(text=tail, start=pos + head_len, end=pos + len(text), leader="",
                depth=depth, kind="note", branch=branch, repair=None),
    ]
