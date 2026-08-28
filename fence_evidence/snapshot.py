"""Build a published snapshot from the store.

The first slice: `source_docs`, `warnings` and `gaps`. Nothing else, deliberately
-- `parts`, `models` and `parameters` need entities the store does not hold, and a
snapshot containing very little is still a valid snapshot by design.

**This is a projection, not an agent and not a parser.** It makes no decisions,
calls no model, reads no PDF, and applies no policy. It rewrites rows that already
exist into the shapes the contract names, and the only way it can be wrong is by
being buggy. Every judgement either happened upstream, when a person accepted
something, or happens downstream, when Planning applies a source policy for a
task it alone knows.

Two properties carry the design:

**Closure is structural.** `source_ref()` registers the document as a side effect
of minting the reference, so a `SourceRef` whose `SourceDoc` is absent cannot be
constructed. The contract makes closure BINDING; making it unrepresentable is
cheaper than checking it.

**Ids are functions of content.** A counter or a uuid would mean two builds over
identical knowledge produced different bytes, and obligation 1 would be a lie.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import date, timedelta

from .canonical import canonical_bytes, content_hash
from .lang import detect_lang
from .refs import ref_id
from .store import connect

CONTRACT_VERSION = "1.1.0"
SPINE_VERSION = "0.1.0"
POLICY_VERSION = "0.1.0"

# How long a hash is guaranteed resolvable. The contract requires a snapshot to
# DECLARE one and deliberately fixes no value -- "immutable forever is not a
# property any versioned store actually provides". Two years is a placeholder
# with no authority behind it; it is an operator decision and is logged as an
# open question in docs/integration/planning-asks.md.
RETAIN_DAYS = 730

# ---------------------------------------------------------------------------
# doc_type -> SourceClass. Nineteen values collapse into eight, which is lossy,
# and the source policy RANKS on the result -- so a wrong entry here does not
# produce a wrong number, it produces a right number that is admissible where it
# should not be. Every value in `documents.doc_type` must appear; a test asserts
# it, because an unmapped type silently defaulting would be exactly that failure.
SOURCE_CLASS = {
    # sealed, stamped, issued by an authority
    "hvhz_noa": "sealed_approval",
    "engineering_approval": "sealed_approval",
    "real_miami_dade_noa_vinyl_fence": "sealed_approval",
    # a test or calculation, not an approval
    "structural_engineering_worked_example": "tested_report",
    # a standards body or trade association
    "industry_spec_reference_guide": "industry_standard",
    "csi_spec": "industry_standard",
    "csi_masterspec_vinyl": "industry_standard",
    "csi_masterspec_template": "industry_standard",
    "astm_standards_compilation": "industry_standard",
    "association_technical_bulletin": "industry_standard",
    # the manufacturer telling an installer what to do
    "installation_manual": "manufacturer_installation_instruction",
    "Installation diagram guide (image-only PDF, no dimensions/text)":
        "manufacturer_installation_instruction",
    # dimensioned manufacturer literature
    "spec_sheet": "spec_sheet",
    "cut_sheet": "spec_sheet",
    "cad_detail": "spec_sheet",
    "manufacturer_brochure_with_engineering_data": "spec_sheet",
    # manufacturer-published, non-engineering
    "warranty": "marketing",
    "astm_compliance_summary_flyer": "marketing",
    # honest floor: we do not know what this document is. `marketing` is the
    # weakest class, so it cannot make anything admissible that should not be --
    # and every document landing here also gets a Gap, because publishing a
    # guess as a classification is the thing obligation 6 forbids.
    "unspecified": "marketing",
}
UNCLASSIFIED = {"unspecified"}

# The publisher's own word, in the publisher's own language. ADVERTENCIA and
# AVERTISSEMENT are real lexemes in this corpus and are NOT in the datamodel's
# enumerated list -- the field is explicitly "not normalised", so they pass
# through as printed. DANGER has zero instances here; it stays for completeness.
_LEXEMES = (r"WARNING|CAUTION|DANGER|NOTICE|IMPORTANT|NOTES?|ATTENTION"
            r"|ADVERTENCIA|AVERTISSEMENT")
# A lexeme ALONE, as the whole element. 30% of warnings in this corpus print the
# word as a heading and the body as the next element; a per-element rule
# publishes 275 warnings whose entire text is "NOTE:".
# A leading bullet or a page-number bleed from the footer must not defeat the
# anchor: the freeze-thaw caution -- 83 instances, the most repeated warning in
# this corpus -- prints as "* Caution -", and "30 * Caution ..." where the page
# number bled into the text layer.
_LEAD = r"[\s*\u2022\u00b7]{0,4}(?:\d{1,3}[A-Z]?\.?\s*[*\u2022]?\s*)?"
_LEXEME_ONLY = re.compile(rf"^{_LEAD}({_LEXEMES})\s*[:!.\u2013-]?\s*$", re.IGNORECASE)
# A lexeme followed by a real delimiter and a body.
_LEXEME_LED = re.compile(rf"^{_LEAD}({_LEXEMES})\s*[:!.\u2013\u2014-]\s*(?=\S)",
                         re.IGNORECASE)

# A warning with no lexeme, recognised by stating a consequence. Kept narrow on
# purpose: bare prohibitions ("do not", "never") were measured at 248 hits and
# are dominated by ordinary instructions that merely contain a negation --
# "dry-assemble all parts. Do not use glue." is a step, not a warning.
_HAZARD = re.compile(
    r"personal injury|bodily injury|serious injury|can result in|may result in"
    r"|failure to comply|void the warranty|not be covered by the warranty"
    r"|underground utilit|call before you dig|always wear|eye protection"
    r"|limitation of liability", re.IGNORECASE)

# G42. Four safety rules this corpus states as ordinary bullets inside
# installation lists, with no lexeme and no consequence clause, so neither
# _LEXEME_* nor _HAZARD sees them:
#
#   * To lower a post, place a wood block ... and carefully tap with a mallet
#   * Never strike the PVC post without a wood support
#
# The general form -- a bare "never" or "do not" -- is measured at 248 hits and
# dominated by ordinary sequencing steps, which is why _HAZARD deliberately
# excludes it. These are named individually instead: each was checked by hand,
# and each is a rule whose violation damages the fence or the installer.
_RULE_WARNING = re.compile(
    r"never strike"
    r"|never cut the top"
    r"|never attach both ends"
    # The actionable form only. A bare "frost line depth" also matches a
    # glossary entry -- "Frost Line  Lowest level in soil that freezes" -- and
    # a definition is not a warning.
    r"|codes? for frost line"
    # The phrasing the warranty documents actually use. _HAZARD carries
    # "void the warranty" and "not be covered by the warranty" and misses
    # "are not covered under this warranty"; it is routed here rather than
    # added there because _HAZARD publishes the whole element, and these sit
    # inside multi-page warranty sections.
    r"|not covered (?:by|under)[^.]{0,25}warrant", re.IGNORECASE)

# Measured false positives, each one checked by hand.
_NOT_A_WARNING = re.compile(
    r"NOTICE OF ACCEPTANCE"                 # 76 hits: a Miami-Dade form header
    r"|never fades|never blisters|never peels"   # marketing copy
    r"|^\s*(safety glasses|safety goggles)\s*$",  # a line in a tool inventory
    re.IGNORECASE)

# A body that stops mid-clause. Publishing it as "verbatim" is technically true
# and practically a lie: a truncated safety instruction is worse than none.
_DANGLING = re.compile(
    r"(?:\b(?:to|the|a|an|and|or|of|in|on|at|as|is|are|be|with|for|from|by|your"
    r"|you|it|this|that|will|may|can|need|needs|into|onto|over|under)\b|-)\s*$",
    re.IGNORECASE)
MIN_BODY_CHARS = 12
OCR_TRUST_FLOOR = 80.0


def _where(row) -> str:
    """`p12 of "Bufftech Gate Installation Guide"` -- a gap's location, in words.

    G40: every would_close used to be a string literal, so 51 of 63 published
    gaps carried the same sentence and a curator could not tell the work items
    apart. contract.md 1.2.1 is BINDING on this field and says why: a gap that
    only says something is missing sends a curator hunting, one that names the
    thing is a work item. All of this was already in scope and simply not used.
    """
    return f"p{row['page_no']} of {_label(row)}"


def _label(row) -> str:
    """A document in a sentence: its title, or its id when it has none.

    Titles are capped because several are curation notes rather than titles --
    one runs to 118 characters explaining which pass the file arrived in -- and
    a would_close is read in a queue, not a catalogue.
    """
    title = " ".join((row["title"] or "").split())
    if not title:
        return row["document_id"]
    if len(title) > 64:
        title = title[:63].rstrip(" ,;(-") + "..."
    return f'"{title}"' 


def _bullet_containing(text: str, rx: re.Pattern) -> str | None:
    """The one bullet a rule matched, not the list it was printed in.

    G42's rules fire inside list elements carrying a dozen bullets. Publishing
    the whole element as `text_raw` would be verbatim and useless -- the
    warning is one line of it, and a reader shown twelve steps has not been
    warned. The citation still resolves to the containing element, which is
    where the bbox is; the text is the rule.
    """
    for part in re.split(r"\n?\s*[\u2022*\u00b7\u00a2\u00ab]\s*|(?<=[.!?])\s+",
                         text):
        # OCR renders the bullet glyph as a cent sign, a guillemet or a stray
        # letter often enough that leaving it in `text_raw` splits one rule
        # into three warnings that no longer dedupe against each other.
        p = " ".join(part.split()).lstrip("\u2022*\u00b7\u00a2\u00ab-\u2013 ").strip()
        if not p or not rx.search(p):
            continue
        # A table of contents can carry the phrase and split into fragments
        # that are dot leaders and page numbers. Publishing one as a safety
        # warning is worse than missing the warning, so a fragment has to look
        # like prose: no dot leaders, and mostly letters.
        if "...." in p:
            continue
        letters = sum(ch.isalpha() or ch.isspace() for ch in p)
        if letters < 0.85 * len(p):
            continue
        return p
    return None


def _tail(text: str, n: int = 55) -> str:
    """The last few words of a truncated warning, so the break point is visible."""
    t = " ".join((text or "").split())
    return t if len(t) <= n else "..." + t[-n:]

# A numbered installation step, for attaches_to. Checklist headings such as
# "1. Getting Started" and "2. Tools" are front matter, not steps.
_STEP_HEADING = re.compile(r"^(?:STEP\s+)?\d{1,2}[.)]\s+[A-Za-z]")
_NOT_A_STEP = re.compile(r"getting started|tools|materials|before you begin"
                         r"|table of contents|parts list", re.IGNORECASE)


@dataclass(frozen=True)
class SourceRef:
    id: str
    belongs_to: str


@dataclass(frozen=True)
class SourceDoc:
    content_hash: str
    source_class: str
    version_status: str
    version_status_basis: str | None
    issue_date: str | None
    expiration_date: str | None
    # Defect 2. In contract.md §1.1's shape and absent here, while `relations`
    # already held the edges. A LIST because doc-8727ba0fd4d4 fans out to seven
    # successors, and CONTENT HASHES because `belongs_to` is a content hash
    # everywhere else on this wire -- a `doc-...` id is an internal handle
    # Planning cannot resolve. Empty for the three documents that are superseded
    # on a filename keyword with no successor recorded anywhere; suppressing the
    # field there would hide the weakest three of the nine.
    superseded_by: tuple = ()


@dataclass(frozen=True)
class Gap:
    """contract.md §1.2.1's shape, which this dataclass did not carry.

    `because` and `cites` were absent, so 63 gaps published with no machine-
    readable reason and no evidence at all -- a live obligation 8 violation on an
    already-shipped snapshot. `because` is `code + params` because §1.2.1 says it
    "renders in both locales", which a prose sentence cannot; `would_close` stays
    the human sentence beside it.

    `on` exists for exactly one kind. §1.2.1 writes `disputed{ on: value |
    conditions }` and no other kind takes a parameter. Planning serialises it as
    a sibling key rather than nested inside `kind`, confirmed against their own
    model in conversation.md T2, so both sides already agree on the shape.
    """
    id: str
    kind: str
    subject: str
    because: dict          # {"code": str, "params": dict}
    cites: list            # [SourceRef], empty where there is no region to point at
    would_close: str
    closes_by: str
    severity: str
    on: str | None = None  # `disputed` only


class SnapshotBuilder:
    def __init__(self, conn: sqlite3.Connection, *, tenant: str, regime: str):
        self.conn = conn
        self.tenant = tenant
        self.regime = regime
        self._docs: dict[str, SourceDoc] = {}
        self._refs: dict[str, SourceRef] = {}
        self._gaps: list[Gap] = []
        self._gap_keys: set[str] = set()

    # -- provenance ---------------------------------------------------------
    def source_ref(self, element_id: str) -> SourceRef:
        """Mint a reference, registering its document. Closure happens here."""
        if element_id in self._refs:
            return self._refs[element_id]
        # Join on version_id, not document_id: an element belongs to exactly
        # one version, and joining by document fans out once a document has
        # two, making .fetchone() return whichever version row SQLite
        # happens to return first -- not the element's own version. Same
        # reasoning as refs.build_index's matching comment; the two joins
        # must agree, or the minting side and the index side can disagree
        # about which version an element belongs to.
        row = self.conn.execute("""
            SELECT e.page_no, e.bbox, v.sha256, d.document_id, d.doc_type,
                   d.title, d.version_status, d.version_status_basis,
                   d.issue_date, d.expiration_date
              FROM elements e
              JOIN document_versions v ON v.version_id = e.version_id
              JOIN documents d         ON d.document_id = e.document_id
             WHERE e.element_id = ?""", (element_id,)).fetchone()
        if row is None:
            # Never mint a ref we cannot back. A dangling belongs_to reproduces
            # the exact defect the closure rule was added to close.
            raise KeyError(f"no such element: {element_id}")

        if row["sha256"] not in self._docs:
            self._docs[row["sha256"]] = SourceDoc(
                content_hash=row["sha256"],
                source_class=SOURCE_CLASS[row["doc_type"]],
                version_status=row["version_status"],
                version_status_basis=row["version_status_basis"],
                issue_date=row["issue_date"],
                expiration_date=row["expiration_date"],
                superseded_by=self._successors(row["document_id"]))
            if row["doc_type"] in UNCLASSIFIED:
                self.gap(kind="missing_value", subject=row["document_id"],
                         code="source_class_unclassified",
                         params={"doc_type": row["doc_type"],
                                 "content_hash": row["sha256"]},
                         would_close=f"classify the source class of {_label(row)} "
                                     f"(filed as {row['doc_type']!r}); it is "
                                     f"published at the weakest class, so it cannot "
                                     f"make anything wrongly admissible until it is",
                         closes_by="knowledge", severity="informational")

        ref = SourceRef(id=ref_id(row["sha256"], row["page_no"], row["bbox"]),
                        belongs_to=row["sha256"])
        self._refs[element_id] = ref
        return ref

    def _successors(self, document_id: str) -> tuple:
        """Content hashes of what supersedes this document, in a stable order.

        Reads the `superseded_by` edge subject-to-object: its *from* side is the
        superseded document. Marking the wrong side once labelled every current
        NOA superseded, which is why tests/test_versions.py guards the direction.
        """
        rows = self.conn.execute("""
            SELECT DISTINCT v.sha256
              FROM relations r
              JOIN document_versions v ON v.document_id = r.to_document_id
             WHERE r.from_document_id = ? AND r.relation_type = 'superseded_by'
             ORDER BY v.sha256""", (document_id,)).fetchall()
        return tuple(r["sha256"] for r in rows)

    def source_docs(self) -> list[SourceDoc]:
        return sorted(self._docs.values(), key=lambda d: d.content_hash)

    # -- gaps ---------------------------------------------------------------
    def gap(self, *, kind: str, subject: str, code: str, would_close: str,
            closes_by: str, severity: str = "warns_line",
            params: dict | None = None, cites: list | None = None,
            on: str | None = None) -> None:
        if kind == "disputed" and on not in ("value", "conditions"):
            raise ValueError("a `disputed` gap must say what is disputed: "
                             "on='value' or on='conditions'")
        if kind != "disputed" and on is not None:
            raise ValueError(f"`on` is only meaningful on `disputed`, not {kind!r}")
        key = f"{kind}:{subject}"
        if key in self._gap_keys:      # one gap per subject per kind
            return
        self._gap_keys.add(key)
        self._gaps.append(Gap(id=hashlib.sha256(key.encode()).hexdigest()[:16],
                              kind=kind, subject=subject,
                              because={"code": code, "params": params or {}},
                              cites=[asdict(c) for c in (cites or [])],
                              would_close=would_close, closes_by=closes_by,
                              severity=severity, on=on))

    def gaps(self) -> list[Gap]:
        return sorted(self._gaps, key=lambda g: g.id)

    # -- warnings -----------------------------------------------------------
    def _attaches_to(self, row, step_heading: str | None) -> dict:
        """Where a warning belongs. Conservative on purpose.

        A measured ladder over this corpus put 19.2% of warnings on a step,
        independently reproducing the contract audit's 19.9% -- but 63% of those
        came from *proximity*: a warning printed after step 3 was assumed to
        belong to step 3. That is a page-layout accident as often as a fact.

        So only an explicit step heading in the element's own `heading_path`
        earns `step`. Everything else is `document`, which is both the corpus's
        actual shape and the honest default -- Planning renders it once in the
        annexe rather than against a line it may not govern.

        `procedure` and `model` are unreachable: this store has no procedure
        entity and no model linkage. Reported as such rather than approximated.
        """
        if row["doc_type"] == "warranty":
            return {"kind": "warranty", "ref": row["sha256"]}
        if step_heading:
            return {"kind": "step", "ref": step_heading}
        return {"kind": "document", "ref": row["sha256"]}

    def warnings(self) -> list[dict]:
        """Safety text from the manuals, republished verbatim.

        Obligation 10: `text_raw` and `lang` are required and never normalised,
        and `severity_lexeme` is the publisher's own word -- CAUTION and WARNING
        carry different legal weight, so normalising them destroys information a
        reader needs.
        """
        rows = self.conn.execute("""
            SELECT e.element_id, e.page_no, e.ordinal, e.text, e.ocr_text,
                   e.text_source, e.ocr_confidence, e.lang, e.heading_path,
                   e.document_id, v.sha256, d.doc_type, d.title
              FROM elements e
              JOIN document_versions v ON v.document_id = e.document_id
              JOIN documents d         ON d.document_id = e.document_id
             ORDER BY e.document_id, e.page_no, e.ordinal""").fetchall()

        def body_of(r):
            return ((r["text"] or "").strip() or (r["ocr_text"] or "").strip())

        seen: dict[str, dict] = {}
        out: list[dict] = []
        for i, r in enumerate(rows):
            text = body_of(r)
            if not text or _NOT_A_WARNING.search(text):
                continue

            lexeme, body, anchor = None, None, r
            if lex_only := _LEXEME_ONLY.match(text):
                # the word is a heading; the body is the next element on the page
                lexeme = lex_only.group(1).upper()
                nxt = rows[i + 1] if i + 1 < len(rows) else None
                if (nxt and nxt["document_id"] == r["document_id"]
                        and nxt["page_no"] == r["page_no"] and body_of(nxt)
                        and not _LEXEME_ONLY.match(body_of(nxt))):
                    body = body_of(nxt)
                    text = f"{text}\n{body}"
                else:
                    self.gap(kind="unquantified", subject=r["element_id"],
                             code="warning_lexeme_without_body",
                             params={"lexeme": lexeme, "page_no": r["page_no"]},
                             cites=[self.source_ref(r["element_id"])],
                             would_close=f"{_where(r)} prints {lexeme!r} with no "
                                         f"instruction after it; a person should "
                                         f"read the page image and record what it says",
                             closes_by="knowledge", severity="informational")
                    continue
            elif m := _LEXEME_LED.match(text):
                lexeme = m.group(1).upper()
                body = text[m.end():].strip()
            elif _HAZARD.search(text):
                lexeme, body = None, text          # a warning without the word
            elif _RULE_WARNING.search(text):
                # G42: a rule stated as a bullet. Publish the bullet, not the
                # list around it; the ref still names the containing element.
                bullet = _bullet_containing(text, _RULE_WARNING)
                if not bullet:
                    continue
                lexeme, body, text = None, bullet, bullet
            else:
                continue

            if len(body) < MIN_BODY_CHARS:
                self.gap(kind="unquantified", subject=r["element_id"],
                         code="warning_body_too_short",
                         params={"lexeme": lexeme, "chars": len(body),
                                 "minimum": MIN_BODY_CHARS},
                         cites=[self.source_ref(r["element_id"])],
                         would_close=f"{_where(r)} prints "
                                     f"{(lexeme or 'a severity word')!r} followed "
                                     f"only by {_tail(body)!r}; read the page image "
                                     f"and record the instruction",
                         closes_by="knowledge", severity="informational")
                continue
            if _DANGLING.search(body) or body[:1].islower():
                # ends on a function word or starts mid-sentence: the column or
                # the page cut it. Verbatim-but-truncated is worse than absent.
                self.gap(kind="illegible_source", subject=r["element_id"],
                         code="warning_truncated_mid_clause",
                         params={"ends_with": _tail(body, 30),
                                 "page_no": r["page_no"]},
                         cites=[self.source_ref(r["element_id"])],
                         would_close=f"the warning on {_where(r)} breaks after "
                                     f"{_tail(body)!r}; a person should read the "
                                     f"page image and record the sentence whole",
                         closes_by="knowledge", severity="warns_line")
                continue
            if (r["text_source"] in ("ocr", "image_ocr")
                    and (r["ocr_confidence"] or 0) < OCR_TRUST_FLOOR):
                self.gap(kind="illegible_source", subject=r["element_id"],
                         code="warning_ocr_below_confidence_floor",
                         # Integers in thousandths: obligation 1 forbids a
                         # float in either direction, and canonical_bytes()
                         # refuses one rather than rounding it silently.
                         params={"confidence_milli": round(r["ocr_confidence"] * 1000),
                                 "floor_milli": round(OCR_TRUST_FLOOR * 1000)},
                         cites=[self.source_ref(r["element_id"])],
                         would_close=f"OCR read the warning on {_where(r)} at "
                                     f"{r['ocr_confidence']:.1f}% against a "
                                     f"{OCR_TRUST_FLOOR:.0f}% floor and produced "
                                     f"{_tail(body)!r}; a person should read the "
                                     f"page image",
                         closes_by="knowledge", severity="warns_line")
                continue
            # Detect on the text actually being published, not on the anchor
            # element's stored tag. Where the lexeme is a heading and the body is
            # the next element, the heading alone is one word -- "AVERTISSEMENT:"
            # -- and carries no grammar to detect. Reading the pair gives the
            # honest answer; obligation 10's lang is a claim about `text_raw`.
            lang, lang_basis = detect_lang(text)
            if lang == "und":
                self.gap(kind="missing_value", subject=r["element_id"],
                         code="warning_language_undetermined",
                         params={"page_no": r["page_no"]},
                         cites=[self.source_ref(r["element_id"])],
                         would_close=f"the warning on {_where(r)} has no "
                                     f"determinable language ({_tail(text)!r}); "
                                     f"obligation 10 requires lang on published text",
                         closes_by="knowledge", severity="informational")
                continue

            path = json.loads(r["heading_path"] or "[]")
            step = next((h for h in reversed(path)
                         if _STEP_HEADING.match(h) and not _NOT_A_STEP.search(h)), None)

            key = " ".join(text.split())       # identity on content, not whitespace
            ref = self.source_ref(anchor["element_id"])
            if key in seen:
                # The same text printed in several documents is one warning with
                # several citations. 14 groups of files here are byte-identical
                # under different manufacturers.
                if ref.belongs_to not in {c["belongs_to"] for c in seen[key]["cites"]}:
                    seen[key]["cites"].append(asdict(ref))
                continue

            w = {"text_raw": text,                  # verbatim, never normalised
                 "lang": lang,
                 # The basis travels with the guess, the same way
                 # `condition_basis` and `version_status_basis` do. `lang` here
                 # is never `measured` -- script is measurable by Unicode range,
                 # language is not -- and publishing the guess without saying so
                 # is the thing obligation 10 exists to prevent.
                 "lang_basis": lang_basis,
                 "severity_lexeme": lexeme,
                 "attaches_to": self._attaches_to(r, step),
                 "cites": [asdict(ref)]}
            seen[key] = w
            out.append(w)

        for w in out:
            w["cites"].sort(key=lambda c: (c["belongs_to"], c["id"]))
        return sorted(out, key=lambda w: (w["attaches_to"]["ref"], w["text_raw"]))


SOURCE_CLASSES = frozenset({
    "sealed_approval", "tested_report", "industry_standard",
    "manufacturer_installation_instruction", "spec_sheet", "marketing",
    "company_authored", "ai_proposal"})
VERSION_STATUSES = frozenset({"active", "superseded", "unknown"})
ATTACHES_TO_KINDS = frozenset({
    "step", "procedure", "document", "product", "model", "warranty", "maintenance"})
GAP_KINDS = frozenset({
    "unmodellable_entity", "uncovered_condition", "unsatisfiable_requirement",
    "unquantified", "missing_value", "unmapped_part_kind", "disputed",
    "illegible_source"})
DECLARED_LISTS = ("source_docs", "warnings", "gaps", "part_types", "parts",
                  "models", "procedures", "parameters", "combinations", "rules")


class VerificationFailed(RuntimeError):
    """A built snapshot broke an obligation and will not be returned.

    Raised, not logged. The failure mode of a bad snapshot is silent: Planning
    pins a hash and computes numbers, and nothing downstream is positioned to
    notice. The gate is the only place it can be caught.
    """


_CODE = re.compile(r"^[a-z][a-z0-9_]*$")


def verify(snapshot: dict) -> None:
    """Run the obligations that are checkable over a finished object.

    What this establishes is narrow and worth naming: **structural validity is
    testable, semantic correspondence is not.** Every check here passes on a
    snapshot that attributes the wrong depth to the wrong post, because the
    builder faithfully published what it was given.
    """
    fail = []

    for key in DECLARED_LISTS:
        if key not in snapshot:
            fail.append(f"`{key}` is absent. Publish it empty rather than omitting "
                        f"it: an absent key reads as an oversight, an empty list "
                        f"reads as a decision.")
    if snapshot.get("regime") not in ("us_astm", "cn_gb"):
        fail.append(f"regime {snapshot.get('regime')!r} is not one of the two. A "
                    f"snapshot serves exactly one standards regime and declares it.")

    held = set()
    for d in snapshot.get("source_docs", []):
        if d["content_hash"] in held:
            fail.append(f"duplicate source_doc {d['content_hash'][:12]}...")
        held.add(d["content_hash"])
        if d.get("source_class") not in SOURCE_CLASSES:
            fail.append(f"source_class {d.get('source_class')!r} is outside the "
                        f"closed vocabulary; the source policy ranks on it")
        if d.get("version_status") not in VERSION_STATUSES:
            fail.append(f"version_status {d.get('version_status')!r} is not "
                        f"active|superseded|unknown")

    def walk(node, path="$"):
        if isinstance(node, dict):
            if "belongs_to" in node and "id" in node and node["belongs_to"] not in held:
                fail.append(f"{path}: closure - SourceRef {node['id']} belongs_to "
                            f"{node['belongs_to'][:12]}..., not in source_docs")
            for k, v in node.items():
                walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")
        elif isinstance(node, float):
            # Checked here as well as in `canonical`, and at every depth: the
            # earlier version tested only dict VALUES, so a float inside a list
            # passed verify and was then refused by the canonicaliser -- a check
            # that gives false assurance is worse than no check.
            fail.append(f"{path}: a float ({node!r}) cannot cross")
    walk(snapshot)

    for i, w in enumerate(snapshot.get("warnings", [])):
        at = f"warnings[{i}]"
        if not w.get("cites"):
            fail.append(f"{at}: obligation 3 - every published value carries at "
                        f"least one resolvable SourceRef")
        if not w.get("text_raw") or not w.get("lang"):
            fail.append(f"{at}: obligation 10 - text_raw and lang are required")
        kind = (w.get("attaches_to") or {}).get("kind")
        if not w.get("attaches_to"):
            fail.append(f"{at}: obligation 10 - a warning declares what it attaches to")
        elif kind not in ATTACHES_TO_KINDS:
            fail.append(f"{at}: attaches_to.kind {kind!r} is not one of the seven")

    for i, g in enumerate(snapshot.get("gaps", [])):
        at = f"gaps[{i}]"
        if not g.get("would_close"):
            fail.append(f"{at}: obligation 8 - a gap says what would close it")
        if g.get("closes_by") not in ("knowledge", "planning"):
            fail.append(f"{at}: obligation 8 - a gap declares who can close it")
        if g.get("kind") not in GAP_KINDS:
            fail.append(f"{at}: gap kind {g.get('kind')!r} is not one of the eight")
        # Defect 1. `because` is what renders in both locales; `would_close` is
        # the sentence beside it, not a substitute. A gap that carries only prose
        # cannot be shown to a Hebrew-speaking curator at all.
        code = (g.get("because") or {}).get("code")
        if not code:
            fail.append(f"{at}: §1.2.1 - a gap carries `because` as code + params, "
                        f"so it renders in both locales")
        elif not _CODE.match(code):
            fail.append(f"{at}: because.code {code!r} is not lower_snake_case; the "
                        f"registry convention is Planning's four existing gap codes")
        # Obligation 8's evidence half. `cites` may be empty -- §1.2.1 says
        # "evidence, where there is any" -- but a gap about a REGION of a page
        # has evidence by construction, and publishing it without is the defect
        # this check was added for.
        if g.get("cites") is None:
            fail.append(f"{at}: `cites` is absent; publish [] rather than omitting it")
        elif not g["cites"] and str(g.get("subject", "")).startswith("element-"):
            fail.append(f"{at}: obligation 8 - an element-scoped gap names a region "
                        f"and so has evidence; cite it")
        if (g.get("kind") == "disputed") != (g.get("on") is not None):
            fail.append(f"{at}: §1.2.1 - `on` belongs to `disputed` and to nothing "
                        f"else; it is value|conditions")

    if fail:
        raise VerificationFailed(
            f"{len(fail)} obligation failure(s); the snapshot is not returned:\n  - "
            + "\n  - ".join(fail))


def build_snapshot(*, tenant: str, regime: str = "us_astm",
                   conn: sqlite3.Connection | None = None) -> dict:
    """Assemble, canonicalise and hash. Provenance first -- closure needs it."""
    own = conn is None
    conn = conn or connect(read_only=True)
    try:
        b = SnapshotBuilder(conn, tenant=tenant, regime=regime)
        warnings = b.warnings()            # mints refs, registers docs, raises gaps

        # The hashed part is the CONTENT plus the coordinates that change its
        # meaning. `retain_until` is deliberately outside it: it moves with the
        # clock, and hashing it would mean two builds over identical knowledge
        # never matched -- which is the opposite of what obligation 1 asks for.
        members = {
            "tenant": tenant,
            "regime": regime,
            "spine_version": SPINE_VERSION,
            "contract_version": CONTRACT_VERSION,
            "policy_version": POLICY_VERSION,
            "source_docs": [asdict(d) for d in b.source_docs()],
            "warnings": warnings,
            "gaps": [asdict(g) for g in b.gaps()],
            # declared and empty rather than absent: an absent key reads as an
            # oversight, an empty list reads as "we publish none of these yet".
            "part_types": [], "parts": [], "models": [], "procedures": [],
            "parameters": [], "combinations": [], "rules": [],
        }
        canonical_bytes(members)           # refuses floats, sets, unsortable keys
        verify(members)                    # the gate: a failure is never returned
        return {"snapshot_id": content_hash(members),
                "retain_until": (date.today() + timedelta(days=RETAIN_DAYS)).isoformat(),
                **members}
    finally:
        if own:
            conn.close()
