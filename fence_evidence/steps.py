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
* **The whitespace after a leader is four characters**: U+0020 (2,656),
  U+2002 EN SPACE (1,921), TAB (52) and U+00A0.
* **A `•` segment can contain a whole nested procedure.** 60 corpus-wide; the
  worst is an 871-character block holding a two-branch lettered choice and 13
  sub-steps. Split, no segment exceeds 587 characters.
* **A trailing `Note:` is a rider, not part of the instruction** — 14 segments
  end with one and none begins with one.
* **319 segments begin with a split capital** (`T\\namp`, `I nsert`) — pdftotext
  emitting a bullet's leading character as its own text run. That is the token
  any verb-based reading looks at first, so it is proposed for repair and NEVER
  repaired in place. The separator carries the confidence: 263 newline-form
  proposals are all real damage, while the 56 space-form ones include the
  English article, so `A cut panel bracket` and `A template can speed
  attachment` are excluded by name and the rest ship as `low`.

Corpus-wide after these rules: 6,105 `list` elements produce 7,931 segments —
6,399 `step`, 791 `branch`, 528 `section`, 131 `prose`, 59 `footnote`, 23
`note` — with **0 span violations and 0 elements losing a character**.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# The three characters that follow a leader. A bare `\s` would also swallow the
# newline that ends the previous segment, and `.lstrip(" ")` misses two of them.
LEADER_GAP = " \t  "

# Which kinds carry an instruction a reader must not lose. `branch` is one:
# `[measured]` 664 segments are branch-kind and 627 of them hold a full
# instruction, so a consumer filtering `kind == "step"` silently drops 8.4% of
# everything. Filter on this, not on a literal.
INSTRUCTION_KINDS = ("step", "branch")

# `N. Title` typed as `list` rather than `heading` — the section spine a bullet
# block hangs off. 783 elements corpus-wide begin with one.
SECTION_RE = re.compile(r"^\s*\d{1,2}\s*[.)]\s+\S")
# ...but only 550 of those 783 are actually headings. The rest are numbered
# INSTRUCTIONS — `3. Insert bottom rail into bottom post route holes.` — from
# manufacturers who number their procedure instead of bulleting it, and
# returning the whole block as one `section` produced zero steps for those
# documents. A heading is short, single-line and unpunctuated; anything else
# numbered is a step. `[measured]`: 233 of 783 are instruction-shaped, 218 of
# them ending in sentence punctuation.
SECTION_MAX_CHARS = 45
# `a.` / `b.` — a lettered alternative inside one bullet. Matched against a
# single line, never against the block: `re.match(block, pos)` does NOT anchor
# `^` at `pos`, so a block-level match silently never fires. That bug shipped
# into the first version of this file and cost the branch scoping entirely.
# Case-insensitive: `[measured]` 123 elements print `A.`/`B.` where the slice
# page prints `a.`/`b.`, and the SAME gate-post instruction appears in the
# corpus both ways. Lowercase-only matching left 118 of them as one
# undifferentiated blob and presented two MUTUALLY EXCLUSIVE methods as a
# sequence -- a reader would do both.
BRANCH_RE = re.compile(r"^([A-Za-z])[.)]\s+\S")
# A rider the guide prints under an instruction; never the start of one.
RIDER_RE = re.compile(r"^(Note|NOTE|Caution|CAUTION|Tip|TIP)\b\s*[:.-]?", re.ASCII)
# pdftotext emitting a leading character as its own run, in both spellings.
# The optional `N. ` prefix lets a numbered section heading be repaired too:
# `10. H ang Gate/Install Hardware` is on the slice page.
SPLIT_CAP_RE = re.compile(r"^(?:\d{1,2}[.)]\s+)?([A-Z])([ \n])([a-z]{2,})\b")
# A capital that is a word on its own, so a space after it is ordinary English
# rather than damage. `[measured]`: the ONLY false-positive families in 320
# proposals are `A cut panel bracket` (9) and `A template can speed
# attachment` (8) -- 17 of 320, and both are the article "A".
#
# `I` is deliberately NOT here. `I nsert` is 48 occurrences and every one is
# real damage; adding the pronoun to this set on symmetry grounds would
# suppress the single largest true-positive family in the corpus.
STANDALONE_CAPITALS = frozenset({"A"})


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
    repair: str | None  # proposed BODY text, when damage is detected
    repair_confidence: str | None = None   # high | low, see `_propose_repair`

    @property
    def is_instruction(self) -> bool:
        return self.kind in INSTRUCTION_KINDS

    @property
    def body(self) -> str:
        """The instruction without its leader glyph, whitespace collapsed.

        `text` stays verbatim because the span and the review anchor depend on
        it; `body` is what a reader and a classifier actually want.
        """
        inner = self.text[1:] if self.leader else self.text
        return " ".join(inner.split())


def _is_heading(block: str) -> bool:
    """A numbered line that titles a section rather than instructing.

    Short and not a sentence. `1. Getting Started` is a heading;
    `3. Insert bottom rail into bottom post route holes.` is a step that happens
    to be numbered.

    Judged on the FLATTENED text, deliberately. An earlier version required a
    heading to be one physical line, which let the split-capital artifact decide
    the classification: the slice page prints `10. H\nang Gate/Install
    Hardware`, where the newline is the damage rather than a line break, and it
    was dropped to `prose`. Length and punctuation already exclude the
    multi-instruction blocks the line test was aimed at.
    """
    flat = " ".join(block.split())
    return len(flat) <= SECTION_MAX_CHARS and not flat.endswith((".", ";", ":"))


def _leaders(text_source: str) -> tuple[str, ...]:
    """Which characters open a bullet, for this element's provenance.

    The asterisk flips meaning on `text_source` and nothing else: a footnote
    marker in the text layer, the bullet glyph under OCR.
    """
    return ("*", "-") if text_source == "ocr" else ("•", "-")


def _propose_repair(text: str) -> tuple[str | None, str | None]:
    """A repair for a split first word, with how much to trust it.

    Returns `(repair, confidence)`. The repair is the **body** text — it does
    not carry the leader glyph, so it can never be substituted for `Segment.text`
    wholesale.

    Only the first token is considered: the defect is pdftotext emitting a
    bullet's leading character as its own run, so it is systematically at the
    START of a segment and a match anywhere else is far more likely to be real
    text.

    **The separator is the signal, and an earlier version destroyed it** by
    flattening whitespace before matching, which made the `[ \n]` alternation
    dead. `[measured]` over 320 proposals: all 249 newline-form repairs are real
    damage; of the 71 space-form ones, 17 are the English article in `A cut
    panel bracket` and `A template can speed attachment`. So a newline split is
    `high`, a space split is `low`, and a space after a capital that is a word
    in its own right is not proposed at all.
    """
    stripped = text.lstrip()
    m = SPLIT_CAP_RE.match(stripped)
    if not m:
        return None, None
    cap, sep, tail = m.group(1), m.group(2), m.group(3)
    if sep == " " and cap in STANDALONE_CAPITALS:
        return None, None
    prefix = stripped[:m.start(1)]
    repaired = prefix + cap + tail + stripped[m.end():]
    return " ".join(repaired.split()), ("high" if sep == "\n" else "low")


def _classify(body: str, leader: str, depth: int, branch: str | None,
              text_source: str) -> str:
    """A `*`-led rider is a footnote only where `*` is NOT the bullet glyph.

    Under OCR the asterisk IS the bullet, so an OCR bullet opening with
    `Caution` is an ordinary note. Keying this on the leader alone was right by
    luck on the one line it hit and wrong as a mechanism.
    """
    if not RIDER_RE.match(body.lstrip()):
        return "step"
    if leader == "*" and depth == 0 and branch is None and text_source != "ocr":
        return "footnote"
    return "note"


def split_block(block: str, *, text_source: str = "pdf_text_layer") -> list[Segment]:
    """Split one element's text into classified segments, discarding nothing.

    Returns segments in source order. Spans never overlap and always slice back
    to their own text.
    """
    if not block or not block.strip():
        return []

    leaders = _leaders(text_source)
    footnote_leader = "*" if text_source != "ocr" else None

    numbered = bool(SECTION_RE.match(block))
    if numbered:
        repair, confidence = _propose_repair(block)
        # A numbered line is a heading only if it reads like one. Otherwise it
        # is an instruction that happens to be numbered, and returning it as a
        # `section` produced zero steps for every manufacturer who numbers a
        # procedure instead of bulleting it.
        kind = "section" if _is_heading(block) else "step"
        if kind == "section" or "\n" not in block.strip():
            return [Segment(text=block, start=0, end=len(block), leader="",
                            depth=0, kind=kind, branch=None, repair=repair,
                            repair_confidence=confidence)]

    # Line-based, because `[measured]` no bullet in this corpus ever starts
    # mid-line inside a `list` element -- 0 of 3,146 bulleted elements. The
    # mid-line separators (`site.com • (800) 336-2383`) are all headings and
    # paragraphs, which this never sees.
    offsets, pos = [], 0
    for line in block.split("\n"):
        offsets.append((pos, line))
        pos += len(line) + 1

    cuts: list[tuple[int, str, int, str | None]] = []
    # A mid-line leader is a bullet only under OCR. `[measured]`: in the text
    # layer 0 of 3,146 bulleted elements put one mid-line, and the mid-line `•`
    # that does occur is a footer separator (`site.com • (800) 336-2383`). Under
    # OCR, 10 elements carry two unrelated instructions on one line because the
    # scan read across a two-column gutter.
    split_mid_line = text_source == "ocr"
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
        if split_mid_line:
            for m in re.finditer(r"(?<=\S)[" + re.escape("".join(LEADER_GAP)) + r"]+"
                                 r"([" + re.escape("".join(leaders)) + r"])"
                                 r"[" + re.escape("".join(LEADER_GAP)) + r"]", line):
                pos = start + m.start(1)
                if pos > start + indent:
                    cuts.append((pos, m.group(1), 0, None))

    cuts.sort(key=lambda c: c[0])
    if not cuts:
        repair, confidence = _propose_repair(block)
        return [Segment(text=block, start=0, end=len(block), leader="", depth=0,
                        kind="prose", branch=None, repair=repair,
                        repair_confidence=confidence)]

    out: list[Segment] = []
    if cuts[0][0] > 0 and block[:cuts[0][0]].strip():
        head = block[:cuts[0][0]]
        repair, confidence = _propose_repair(head)
        out.append(Segment(text=head, start=0, end=cuts[0][0], leader="",
                           depth=0, kind="prose", branch=None, repair=repair,
                           repair_confidence=confidence))

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
        kind = _classify(body, leader, depth, current_branch, text_source)
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
        repair, confidence = _propose_repair(body)
        return [Segment(text=text, start=pos, end=pos + len(text), leader=leader,
                        depth=depth, kind=kind, branch=branch, repair=repair,
                        repair_confidence=confidence)]
    head_len = sum(len(l) + 1 for l in lines[:cut])
    head, tail = text[:head_len], text[head_len:]
    head_body = head[1:].lstrip(LEADER_GAP) if leader else head
    repair, confidence = _propose_repair(head_body)
    return [
        Segment(text=head, start=pos, end=pos + head_len, leader=leader,
                depth=depth, kind=kind, branch=branch, repair=repair,
                repair_confidence=confidence),
        Segment(text=tail, start=pos + head_len, end=pos + len(text), leader="",
                depth=depth, kind="note", branch=branch, repair=None),
    ]


# --------------------------------------------------------------- proposing
def ensure_step_candidates(conn) -> None:
    """Create `step_candidates` if this store predates it.

    `store.connect` runs `ensure_columns` but never `executescript(SCHEMA)`, so
    a new *table* is invisible to an existing store until `cli migrate` runs.
    Same reasoning, and same shape, as `reviews.ensure_fact_reviews`.
    """
    from .store import STEP_CANDIDATES_DDL
    conn.executescript(STEP_CANDIDATES_DDL)


def propose(conn, *, document_id: str, page_no: int | None = None) -> int:
    """Write step candidates for one document, or one page of it.

    Returns the number of candidates now on record for that scope. Idempotent
    and **non-destructive**: a candidate is keyed on `(element_id, char_start,
    char_end)`, so re-proposing over reviewed rows leaves their review alone.
    That matters more than it looks -- a review is the one thing here that does
    not regenerate, and a proposer that cleared the queue would destroy exactly
    the work it cannot reproduce.

    Only `list` elements are read. `[measured]` 46 `paragraph` elements in the
    corpus also carry real bulleted steps that the layout classifier did not
    type as `list`; they are out of scope for this slice and a gap names them.
    """
    from .store import now
    ensure_step_candidates(conn)
    where = "e.document_id = ? AND e.element_type = 'list'"
    params: list = [document_id]
    if page_no is not None:
        where += " AND e.page_no = ?"
        params.append(page_no)
    rows = conn.execute(
        f"""SELECT e.element_id, e.version_id, e.page_no, e.ordinal, e.text_source,
                   COALESCE(NULLIF(e.text,''), e.ocr_text) AS body
              FROM elements e
             WHERE {where}
             ORDER BY e.page_no, e.ordinal""", params).fetchall()
    stamp = now()
    for row in rows:
        if not row["body"]:
            continue
        segments = split_block(row["body"], text_source=row["text_source"] or "")
        for seq, seg in enumerate(segments):
            conn.execute(
                """INSERT OR IGNORE INTO step_candidates
                   (document_id, version_id, page_no, element_id, ordinal, seq,
                    char_start, char_end, text_raw, text_repair, segment_kind,
                    leader, depth, branch, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (document_id, row["version_id"], row["page_no"], row["element_id"],
                 row["ordinal"], seq, seg.start, seg.end, seg.text, seg.repair,
                 seg.kind, seg.leader, seg.depth, seg.branch, stamp))
    conn.commit()
    scope = "AND page_no = ?" if page_no is not None else ""
    args = [document_id] + ([page_no] if page_no is not None else [])
    return conn.execute(
        f"SELECT COUNT(*) FROM step_candidates WHERE document_id = ? {scope}",
        args).fetchone()[0]
