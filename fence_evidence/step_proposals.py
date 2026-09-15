"""Machine proposals onto `step_candidates` — a reader proposes, a person disposes.

`proposed_kind`, `proposed_scope`, `proposed_slot` and `proposal_basis` have been
on `step_candidates` since it shipped and, on 2026-09-15, every row in the store
had all four NULL. That is the whole cost of the empty `Procedure` member made
concrete: `procedures.build_procedures` publishes no step without `step_kind` AND
`step_scope` on a review row, and a reviewer facing 91 candidates with four empty
columns has to type both from scratch, 91 times.

This module fills the *proposal* columns from an independent reading of the same
PDF — an extraction file shaped
`step_4_mapping.procedures[].steps[] {kind, scope, slots, text_en, evidence{page,
quote}}`. It changes nothing about what publishes: a proposal is not a review, no
proposal reaches a snapshot, and `PROPOSABLE` has no counterpart here on purpose.

What it refuses is the design:

* **The anchor is (document, page, normalised text), never the reader's order.**
  A reader's step list is its own segmentation of the page — the gate reading
  emits 51 steps for a page this splitter cuts into 71 candidates — so position
  carries no information. A step no candidate holds is not imported, and is
  counted: the refusal is what makes a landed proposal evidence that the sentence
  really is on that page.
* **A person outranks every reader.** A candidate carrying a `step_reviews` row
  (or the projection of one) is not touched. This is A1/CUR-S0 on a new seam;
  machine agreement was laundered into curation level 2 once already.
* **Two readers disagreeing is information.** Where readings differ, the column
  stays NULL and BOTH readings go into `proposal_basis`. "Reader A says assembly,
  reader B says installation" is a better thing to hand a reviewer than a coin
  flip, and `kind`, `scope` and `slot` are settled one at a time because scope is
  measurably the noisier axis.
* **A `prohibition` gets no step kind.** Both real readers emit `Never strike the
  PVC post…` inside `procedures[].steps[]` because their shape has nowhere else
  to put it; this platform publishes it as a `Warning`. The readers' opinion is
  recorded, the proposal is withheld, and the note says why.

The closed lists are `reviews.STEP_KINDS` / `STEP_SCOPES` — imported, never
re-declared, so a proposal can never offer a value the review path would refuse.

`proposal_basis` is shared with `steps.pair_numbered_flow`, which writes a
`numbered_flow_pair: …` line there and whose count `cli steps --pair-numbered`
reads back with a LIKE prefix. So this module APPENDS one tagged line rather than
overwriting, and strips its own line before re-writing it, which is what makes a
re-import idempotent.
"""
from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from pathlib import Path

from .paths import REPO_ROOT
from .reviews import STEP_KINDS, STEP_SCOPES

# The line prefix that marks this module's own contribution to `proposal_basis`.
# Same shape as `numbered_flow_pair:` so the column stays greppable.
PROPOSAL_TAG = "step_proposal: "

PROPOSER = "step_proposals"


class ProposalRefused(Exception):
    """A reading that cannot be bound to a document in this store."""


# Leaders the splitter records verbatim on the candidate and the reader never
# emits. Stripped from BOTH sides, so the transform stays symmetric.
_BULLETS = "·•‣⁃▪●◦∙*"
_LEADER_RE = re.compile(rf"^[\s{re.escape(_BULLETS)}\-–—]+")
_ORDINAL_RE = re.compile(r"^(?:\d{1,2}|[A-Za-z])[.)]\s+")

# Typography only. Nothing here removes a character that carries meaning: `30"`
# must not normalise onto `30`, or a dimension quietly inherits another line's
# classification.
_PUNCT = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "−": "-", " ": " ",
}


def normalise(text: str | None) -> str:
    """The match key: leader gone, typography folded, words untouched.

    NFKC first, because the text layer prints `\\u2002` between a bullet and its
    sentence and the reader quotes an ordinary space.
    """
    out = unicodedata.normalize("NFKC", text or "")
    for bad, good in _PUNCT.items():
        out = out.replace(bad, good)
    out = _LEADER_RE.sub("", out)
    out = _ORDINAL_RE.sub("", out)
    return re.sub(r"\s+", " ", out).strip().casefold()


def reader_name(path: Path) -> str:
    """A reading is named by its file, because that is what a reviewer can open."""
    return Path(path).stem


def _source_file(path: Path) -> str:
    path = Path(path).resolve()
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------- documents


def _basename_key(name: str) -> str:
    """`bufftech-gate-install-guide(2).pdf` and `…-guide.pdf` are one file.

    A browser download suffix is not a different document, and the readings in
    `example/` carry those suffixes in their `document` field.
    """
    stem = Path(str(name)).name
    return re.sub(r"\((\d+)\)(?=\.[A-Za-z0-9]+$|$)", "", stem).strip().casefold()


def resolve_documents(conn: sqlite3.Connection, name: str,
                      *, follow_same_content: bool = True) -> list[str]:
    """Every document id a reading of `name` may legitimately land on.

    Accepts a `document_id`, a `source_path`, or a bare filename. The corpus
    holds 14 groups of byte-identical files under different manufacturers, linked
    `same_content_as` and never deduplicated, so a reading of one is a reading of
    all of them — the 2024 Bufftech guide and the Barrette SimTek filing share a
    sha256 and each carries its own candidate rows.
    """
    row = conn.execute(
        "SELECT document_id FROM documents WHERE document_id=? OR source_path=?",
        (name, name)).fetchone()
    found = row[0] if row else None
    if found is None:
        key = _basename_key(name)
        hits = [r[0] for r in conn.execute("SELECT document_id, source_path FROM documents")
                if _basename_key(r[1]) == key]
        if len(hits) == 1:
            found = hits[0]
        elif len(hits) > 1:
            found = hits[0]          # same basename; same_content_as picks up the rest
    if found is None:
        raise ProposalRefused(
            f"no document in this store matches {name!r}; pass an explicit "
            f"document_id if the reading is of a file filed under another name")
    ids = [found]
    if follow_same_content:
        seen, queue = {found}, [found]
        while queue:
            current = queue.pop()
            for peer, in conn.execute(
                    """SELECT to_document_id FROM relations
                        WHERE from_document_id=? AND relation_type='same_content_as'""",
                    (current,)):
                if peer not in seen:
                    seen.add(peer)
                    queue.append(peer)
                    ids.append(peer)
    return ids


# ---------------------------------------------------------------- readings


def read_steps(path) -> "tuple[list[dict], str | None]":
    """(every `steps[]` entry flattened, the file's own `document` name).

    Flattened because a reader's grouping into `procedures` is its own reading
    of the page and carries no anchor; the page and the text do.
    """
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    mapping = payload.get("step_4_mapping") or {}
    out = []
    for procedure in mapping.get("procedures") or []:
        for step in procedure.get("steps") or []:
            evidence = step.get("evidence") or {}
            out.append({
                "page": evidence.get("page"),
                "text": step.get("text_en") or evidence.get("quote") or "",
                "kind": step.get("kind"),
                "scope": step.get("scope"),
                "slot": _canonical_slot(step.get("slots")),
            })
    return out, payload.get("document")


def _canonical_slot(slots):
    """One `SlotTarget`, in one shape, whatever shape the reader wrote it in.

    The two real readers disagree about the *form*: one emits the string
    `"Footing(hole)"` and the other `{"target": "Footing", "part": "hole"}`.
    Folding them lets an agreement be recognised as one; the raw forms stay in
    the basis so a reviewer can see what each actually said.
    """
    if not slots or len(slots) != 1:
        return None
    slot = slots[0]
    if isinstance(slot, str):
        match = re.match(r"^\s*([^()]+?)\s*\(\s*([^()]*?)\s*\)\s*$", slot)
        if match:
            return {"target": match.group(1), "part": match.group(2)}
        return {"target": slot.strip()} if slot.strip() else None
    if isinstance(slot, dict):
        out = {k: v for k, v in slot.items()
               if k not in ("curation_level", "withheld_fields") and v is not None}
        return out or None
    return None


# ---------------------------------------------------------------- matching


def _candidate_index(conn: sqlite3.Connection, document_ids) -> dict:
    """(page, normalised text) -> {candidate_id: (row, which column matched)}.

    Indexes `text_repair` as well as `text_raw`, because the reader read the PDF
    and not our store: where the text layer split a leading capital (`N\\never`),
    the reader quotes the repaired sentence and only the repair can match it.
    `text_raw` wins a tie — a candidate is what the page prints.
    """
    marks = ",".join("?" * len(document_ids))
    index: dict = {}
    for row in conn.execute(
            f"SELECT * FROM step_candidates WHERE document_id IN ({marks})",
            tuple(document_ids)):
        for column in ("text_raw", "text_repair"):
            text = row[column]
            if not text:
                continue
            bucket = index.setdefault((row["page_no"], normalise(text)), {})
            if column == "text_raw" or row["candidate_id"] not in bucket:
                bucket[row["candidate_id"]] = (row, column)
    return index


def _reviewed_anchors(conn: sqlite3.Connection) -> set:
    try:
        return {(r[0], r[1], r[2]) for r in conn.execute(
            "SELECT element_id, char_start, char_end FROM step_reviews")}
    except sqlite3.OperationalError:
        return set()


def _is_reviewed(row, anchors) -> bool:
    if (row["element_id"], row["char_start"], row["char_end"]) in anchors:
        return True
    return bool(row["reviewer"]) or (row["review_status"] or "unreviewed") != "unreviewed"


# ---------------------------------------------------------------- settling


def _settle(values):
    """(agreed value, agreement word) over the readers that expressed one.

    A reader that withheld a field abstains; it is not a third opinion. Both real
    readers mark withheld fields explicitly rather than guessing, and counting a
    null as a vote would make every step one reader was unsure about
    unproposable.
    """
    stated = [v for v in values if v is not None]
    if not stated:
        return None, "none"
    distinct = {json.dumps(v, sort_keys=True) for v in stated}
    if len(distinct) > 1:
        return None, "disagreed"
    return stated[0], ("agreed" if len(stated) > 1 else "single")


def _split_basis(basis: str | None) -> str:
    """Whatever another proposer wrote here, minus any line of ours."""
    if not basis:
        return ""
    kept = [ln for ln in basis.splitlines() if not ln.startswith(PROPOSAL_TAG)]
    return "\n".join(kept).strip("\n")


# ---------------------------------------------------------------- the import


def import_proposals(conn: sqlite3.Connection, sources, *,
                     document: str | None = None, apply: bool = True) -> dict:
    """Write `proposed_*` onto the candidates that hold each reader's text.

    `sources` is read as ONE pass on purpose: agreement between readers can only
    be computed with all of them in hand, and importing them one at a time would
    let the last file silently overwrite the first.
    """
    sources = [Path(s) for s in sources]
    readings, documents, steps_read = [], {}, 0
    located = unlocated = refused_kind = refused_scope = 0
    via_repair = 0
    by_reader: dict = {}
    unlocated_samples: list[str] = []
    per_candidate: dict = {}

    ids_all: list[str] = []
    parsed = []
    for path in sources:
        steps, declared = read_steps(path)
        target = document or declared or path.name
        ids = resolve_documents(conn, target)
        documents[reader_name(path)] = ids
        ids_all.extend(i for i in ids if i not in ids_all)
        parsed.append((path, steps))

    index = _candidate_index(conn, ids_all)
    anchors = _reviewed_anchors(conn)

    for path, steps in parsed:
        reader = reader_name(path)
        readings.append(reader)
        for step in steps:
            steps_read += 1
            tally = by_reader.setdefault(
                reader, {"steps_read": 0, "located": 0, "unlocated": 0})
            tally["steps_read"] += 1
            bucket = index.get((step["page"], normalise(step["text"])))
            if not bucket:
                unlocated += 1
                tally["unlocated"] += 1
                if len(unlocated_samples) < 20:
                    unlocated_samples.append(step["text"].replace("\n", " ")[:90])
                continue
            located += 1
            tally["located"] += 1
            if all(column == "text_repair" for _, column in bucket.values()):
                via_repair += 1
            kind, scope = step["kind"], step["scope"]
            entry = {"reader": reader, "source_file": _source_file(path),
                     "page": step["page"]}
            if kind in STEP_KINDS:
                entry["kind"] = kind
            else:
                entry["kind"] = None
                if kind is not None:
                    entry["kind_refused"] = kind
                    refused_kind += 1
            if scope in STEP_SCOPES:
                entry["scope"] = scope
            else:
                entry["scope"] = None
                if scope is not None:
                    entry["scope_refused"] = scope
                    refused_scope += 1
            if step["slot"] is not None:
                entry["slot"] = step["slot"]
            for candidate_id, (row, column) in bucket.items():
                entry_here = dict(entry, matched_via=column)
                per_candidate.setdefault(candidate_id, (row, []))[1].append(entry_here)

    skipped_reviewed = written = 0
    kind_agreed = kind_disagreed = 0
    scope_agreed = scope_disagreed = 0
    slot_written = slot_disagreed = withheld_prohibition = 0

    for candidate_id, (row, entries) in sorted(per_candidate.items()):
        if _is_reviewed(row, anchors):
            skipped_reviewed += 1
            continue
        kind, kind_word = _settle([e["kind"] for e in entries])
        scope, scope_word = _settle([e["scope"] for e in entries])
        slot, slot_word = _settle([e.get("slot") for e in entries])
        note = None
        if row["segment_kind"] == "prohibition":
            # The readers had nowhere else to put it; this platform does.
            kind, kind_word = None, "withheld_prohibition"
            note = ("the readers typed this as a step; this platform types a "
                    "prohibition as a Warning, not an AssemblyStep, so no step "
                    "kind is proposed")
            withheld_prohibition += 1
        if kind_word == "agreed":
            kind_agreed += 1
        elif kind_word == "disagreed":
            kind_disagreed += 1
        if scope_word == "agreed":
            scope_agreed += 1
        elif scope_word == "disagreed":
            scope_disagreed += 1
        if slot is not None:
            slot_written += 1
        elif slot_word == "disagreed":
            slot_disagreed += 1
        blob = {"proposer": PROPOSER, "readers": entries,
                "kind_agreement": kind_word, "scope_agreement": scope_word,
                "slot_agreement": slot_word}
        if note:
            blob["note"] = note
        prior = _split_basis(row["proposal_basis"])
        line = PROPOSAL_TAG + json.dumps(blob, sort_keys=True, ensure_ascii=False)
        basis = f"{prior}\n{line}" if prior else line
        written += 1
        if apply:
            conn.execute(
                """UPDATE step_candidates
                      SET proposed_kind=?, proposed_scope=?, proposed_slot=?,
                          proposal_basis=?
                    WHERE candidate_id=?""",
                (kind, scope,
                 json.dumps(slot, sort_keys=True) if slot is not None else None,
                 basis, candidate_id))
    if apply:
        conn.commit()
    return {
        "readers": readings,
        "documents": documents,
        "apply": apply,
        "steps_read": steps_read,
        "located": located,
        "unlocated": unlocated,
        "matched_via_repair": via_repair,
        "candidates_matched": len(per_candidate),
        "skipped_reviewed": skipped_reviewed,
        "candidates_written": written,
        "refused_kind": refused_kind,
        "refused_scope": refused_scope,
        "kind_agreed": kind_agreed,
        "kind_disagreed": kind_disagreed,
        "scope_agreed": scope_agreed,
        "scope_disagreed": scope_disagreed,
        "slot_proposed": slot_written,
        "slot_disagreed": slot_disagreed,
        "by_reader": by_reader,
        "withheld_prohibition": withheld_prohibition,
        "unlocated_samples": unlocated_samples,
    }


def disagreements(conn: sqlite3.Connection, *, document_id: str | None = None,
                  limit: int = 20) -> list[dict]:
    """Every candidate where the readers differ, for a person to look at.

    This is the output the whole disagreement rule exists to produce: a short
    list of instructions where two independent readings of the same sentence
    reached different answers, which is where a reviewer's minute is worth most.
    """
    sql = ("SELECT * FROM step_candidates WHERE proposal_basis LIKE ?"
           + (" AND document_id=?" if document_id else ""))
    args = [f"%{PROPOSAL_TAG}%"] + ([document_id] if document_id else [])
    out = []
    for row in conn.execute(sql, args):
        blob = None
        for line in (row["proposal_basis"] or "").splitlines():
            if line.startswith(PROPOSAL_TAG):
                blob = json.loads(line[len(PROPOSAL_TAG):])
        if not blob or "disagreed" not in (blob["kind_agreement"],
                                           blob["scope_agreement"]):
            continue
        out.append({
            "candidate_id": row["candidate_id"],
            "document_id": row["document_id"],
            "page": row["page_no"],
            "text": (row["text_repair"] or row["text_raw"]).replace("\n", " ").strip(),
            "kind_agreement": blob["kind_agreement"],
            "scope_agreement": blob["scope_agreement"],
            "readers": [{"reader": e["reader"], "kind": e.get("kind"),
                         "scope": e.get("scope")} for e in blob["readers"]],
        })
        if len(out) >= limit:
            break
    return out
