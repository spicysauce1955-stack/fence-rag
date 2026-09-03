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
from .dates import normalize_date
from .lang import detect_lang
from .refs import ref_id
from .store import connect
from .tenancy import TenantLeak, validate_tenant, visible_sql, visible_to

CONTRACT_VERSION = "1.3.0"  # v1.3, ratified 2026-08-31 -- amendments 002-007
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
    r"|^\s*(safety glasses|safety goggles)\s*$"   # a line in a tool inventory
    # Miami-Dade administrative boilerplate, matched by `_HAZARD` only because
    # it contains "failure to comply". `[measured]`: every one of the 15
    # corpus-wide occurrences of that phrase is this identical clause, so
    # excluding it drops 15 false gaps with ZERO collateral. Keyed on the
    # NOA-specific wording rather than on `doc_type`, which spans four values.
    r"|removal of NOA|terminate this NOA",
    re.IGNORECASE)

# A body that stops mid-clause. Publishing it as "verbatim" is technically true
# and practically a lie: a truncated safety instruction is worse than none.
_DANGLING = re.compile(
    r"(?:\b(?:to|the|a|an|and|or|of|in|on|at|as|is|are|be|with|for|from|by|your"
    r"|you|it|this|that|will|may|can|need|needs|into|onto|over|under)\b|-)\s*$",
    re.IGNORECASE)
# A second severity lexeme INSIDE a body means OCR read two columns onto one
# line -- `"Note: Do not over-tighten the Note: Line up and drive the"` is two
# different notes fused word by word. Joining forward makes such a body longer
# without making it true, so it must be gapped rather than published: this is
# the one case where a dangling body is garbled rather than merely split.
_INTERLEAVED = re.compile(rf"\S\s+({_LEXEMES})\s*[:!]", re.IGNORECASE)
MIN_BODY_CHARS = 12
OCR_TRUST_FLOOR = 80.0



def _join_forward(rows, i, body, limit=4):
    """Complete a dangling body from the elements that follow it, or None.

    A warning that ends on a function word is usually SPLIT across layout
    elements rather than cut off by the page. `[measured]` over the 52 gaps
    that claimed truncation: 24 of the 26 real danglers complete within four
    forward elements, and joining them RECOVERS the warning instead of merely
    suppressing a false gap -- `"Note: The latch is designed for"` becomes
    `"Note: The latch is designed for left and right hand applications."`

    Returns `(added_text, anchor_row)` -- only what was APPENDED, never the
    whole rebuilt string. Returning the join caused the caller to splice it back
    on top of text that already contained the body, publishing
    `"Note: The Note: The donut can be The Note: The donut can be ..."`.

    Stops at a page or document boundary, at a new severity lexeme, and as soon
    as the joined text reads as a finished sentence.
    """
    here = rows[i]
    out, added = body, []
    for nxt in rows[i + 1:i + 1 + limit]:
        if (nxt["document_id"] != here["document_id"]
                or nxt["page_no"] != here["page_no"]):
            return None, here
        more = (nxt["text"] or "").strip() or (nxt["ocr_text"] or "").strip()
        if not more or _LEXEME_ONLY.match(more) or _LEXEME_LED.match(more):
            return None, here
        added.append(more)
        out = f"{out} {more}".strip()
        if not _DANGLING.search(out):
            return " ".join(added), nxt
    return None, here


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
    issue_date: dict | None    # amendment 002: {"iso": str|None, "value_raw": [str]}
    expiration_date: dict | None
    # Defect 2. In contract.md §1.1's shape and absent here, while `relations`
    # already held the edges. A LIST because doc-8727ba0fd4d4 fans out to seven
    # successors, and CONTENT HASHES because `belongs_to` is a content hash
    # everywhere else on this wire -- a `doc-...` id is an internal handle
    # Planning cannot resolve. Empty for the three documents that are superseded
    # on a filename keyword with no successor recorded anywhere; suppressing the
    # field there would hide the weakest three of the nine.
    superseded_by: tuple = ()
    # C2, registry-additions.md §5. `source_class` is a property of the BYTES;
    # the filing is a property of the catalogue. 14 groups of byte-identical
    # files are filed under more than one document record here, and 18 of the 40
    # `same_content_as` edges disagree about `doc_type` across the two sides --
    # the same Miami-Dade NOA is `hvhz_noa` under CertainTeed and `unspecified`
    # under Freedom Outdoor Living. Now that Planning applies the source policy,
    # that is not untidiness: identical evidence is admissible or not according
    # to which record this SourceDoc happened to be built from, silently and
    # with no error anywhere. So ONE class per content hash, and every OTHER
    # filing travels here, where a reviewer can see the disagreement instead of
    # inheriting it. `{manufacturer, doc_type}` pairs, in a stable order, since
    # the whole object is hashed. Empty tuple where the bytes are filed once --
    # empty is a statement, absent would read as an oversight.
    also_filed_as: tuple = ()


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
    subject: dict           # amendment 004: EntityRef | ParamRef (SlotRef unemitted)
    because: dict          # {"code": str, "params": dict}
    cites: list            # [SourceRef], empty where there is no region to point at
    would_close: str
    closes_by: str
    severity: str
    on: str | None = None  # `disputed` only


class SnapshotBuilder:
    def __init__(self, conn: sqlite3.Connection, *, tenant: str, regime: str):
        self.conn = conn
        self.tenant = validate_tenant(tenant)
        self.regime = regime
        self._docs: dict[str, SourceDoc] = {}
        self._refs: dict[str, SourceRef] = {}
        self._gaps: list[Gap] = []
        self._gap_keys: set[bytes] = set()

    # -- provenance ---------------------------------------------------------
    def _document_dates(self, row) -> tuple[dict | None, dict | None, str]:
        """`(issue_date, expiration_date, evidence_note)` for one document.

        Evidence beats the curated column. Every value is re-normalised through
        `dates.normalize_date` before publication, and that is not belt and
        braces: `versions.parse_date` and `dates.normalize_date` are two
        independent parsers that DISAGREE. `normalize_date` implements
        amendment 002 -- when both day and month are <= 12 and unequal, refuse
        to guess -- and `versions.parse_date` guesses unconditionally.
        Publishing its ISO output directly would override a ratified
        amendment's refusal with a confident guess on four documents, one of
        which correctly publishes `iso: null` today.

        `version_status` itself is deliberately NOT derived here.
        `select_active` distinguishes `marked` from `inferred_in_force`, and
        collapsing an inference into the same word a document uses about itself
        is the kind of overclaim obligation 6 exists to prevent.
        """
        from .versions import document_dates
        try:
            found = document_dates(self.conn, row["document_id"])
        except sqlite3.Error:
            found = {}
        out, seen = [], []
        for key, column in (("effective", "issue_date"),
                            ("expiration", "expiration_date")):
            raw = None
            entry = (found or {}).get(key) or {}
            for source in entry.get("sources") or []:
                raw = source.get("original") or source.get("value") or raw
                if raw:
                    break
            date = normalize_date(raw) if raw else None
            if date is None:
                date = normalize_date(row[column])
            else:
                seen.append(f"{key} {date['iso'] or 'ambiguous'}")
            out.append(date)
        return out[0], out[1], ", ".join(seen)

    def _register_doc(self, row) -> None:
        """Register the `SourceDoc` a ref belongs to. Idempotent per hash.

        Shared by `source_ref` and `source_ref_page` — the registration IS the
        closure mechanism (§1.2.1), so two minters must not each carry their
        own copy of it and drift.
        """
        if row["sha256"] in self._docs:
            return
        # Dates come from EVIDENCE first, the curated column only as a
        # fallback. `documents.issue_date`/`expiration_date` are blank for most
        # documents and, for one NOA with four byte-identical filings,
        # disagree -- two rows filled, two blank -- and whichever row a
        # citation reached first won. `versions.document_dates` resolves both
        # from the `effective_date`/`expiration_date` facts Phase 6 extracted
        # for every filing independently, so the answer stops depending on
        # arrival order (G75).
        issue_date, expiration_date, evidence = self._document_dates(row)
        self._docs[row["sha256"]] = SourceDoc(
            content_hash=row["sha256"],
            source_class=SOURCE_CLASS[row["doc_type"]],
            version_status=row["version_status"],
            version_status_basis=(
                # The stored basis says "no explicit version marker in curated
                # metadata". That is true about the COLUMN and false about what
                # this platform holds, once its own pages have been read.
                f"{row['version_status_basis']}; dates read from the document: "
                f"{evidence}" if evidence else row["version_status_basis"]),
            issue_date=issue_date,
            expiration_date=expiration_date,
            superseded_by=self._successors(row["document_id"]),
            # The class published above came from THIS record, which is the
            # first filing of these bytes that a citation reached. The other
            # filings travel beside it rather than being dropped.
            also_filed_as=self._other_filings(row["sha256"],
                                              row["document_id"]))

        if row["doc_type"] in UNCLASSIFIED:
                self.gap(kind="missing_value", subject={"kind": "source_document", "id": row["document_id"], "tenant": None},
                         code="source_class_unclassified",
                         params={"doc_type": row["doc_type"],
                                 "content_hash": row["sha256"]},
                         would_close=f"classify the source class of {_label(row)} "
                                     f"(filed as {row['doc_type']!r}); it is "
                                     f"published at the weakest class, so it cannot "
                                     f"make anything wrongly admissible until it is",
                         closes_by="knowledge", severity="informational")

    # Which detected extraction failures publish, and how. Every `kind` in
    # `quality_issues` must appear here: a class that is neither published nor
    # deliberately excluded is the exact defect G78 found, where 73
    # unreconstructed tables produced no gap at all.
    #
    # `because.code` values are registry additions, which `AMENDING.md` §4
    # states are explicitly NOT amendments and need no negotiation.
    QUALITY_GAP_KINDS = {
        "table_not_reconstructed": (
            "illegible_source", "table_not_reconstructed",
            "a person should read the table on this page and record its cells; "
            "the page names conditional data that no cell grid was recovered from"),
        "mojibake_text_layer": (
            "illegible_source", "text_layer_mojibake",
            "the text layer on this page decodes to mojibake and was rejected; "
            "a person should read the page image"),
        "low_ocr_confidence": (
            "illegible_source", "ocr_below_confidence_floor",
            "this page was read by OCR below the confidence floor; a person "
            "should confirm what it says against the page image"),
        "empty_page_after_ocr": (
            "illegible_source", "empty_after_ocr",
            "neither the text layer nor OCR recovered any text from this page"),
        "empty_page": (
            "illegible_source", "empty_page",
            "this page yielded no text at all"),
        "ocr_supplement_failed": (
            "illegible_source", "ocr_supplement_failed",
            "the OCR supplement for this page did not run to completion"),
        "encrypted_pdf": (
            "illegible_source", "encrypted_pdf",
            "this document is encrypted and could not be read"),
    }
    # Detected, and deliberately NOT published: a DOCX has no page image by
    # construction, which is a property of the format rather than a failure to
    # read the source. Named here so the set stays exhaustive.
    QUALITY_NOT_PUBLISHED = frozenset({"no_page_image_for_docx"})

    def quality_gaps(self) -> int:
        """Publish a `Gap` for every extraction failure this platform detected.

        `warnings()` only inspects text that matches a warning lexeme, so until
        G78 an entire class of KNOWN failure was invisible to a consumer
        reading `gaps[]` -- 73 unreconstructed tables across 13 documents, 172
        low-OCR passages, 81 mojibake pages. Silence read as coverage, which is
        the one thing this member exists to prevent.

        The subject carries the page, not just the document: `gap()` dedupes on
        `[kind, subject]`, so a document-scoped subject would collapse every
        affected page of a document into one gap and lose the rest.

        The gap cites the page it is about, which only became expressible with
        `source_ref_page` (G73). A page whose `pages` row is missing, or which
        belongs to another tenant, raises no gap rather than taking the build
        down -- a citation that cannot be minted must not become a citation
        that lies.
        """
        raised = 0
        # Which documents something published already cites. A failure on a
        # page of a document that BACKS a live value is actionable -- it is a
        # sibling page of one a plan depends on -- so it warns a line; a
        # failure on a document nothing cites is background. `[measured]` 11 of
        # the 13 documents carrying an unreconstructed table are documents that
        # back a published `ParameterTable`, which is why the first cut's blanket
        # `informational` was justified by a claim that was false for most of them.
        backing = set(self._docs)
        # No `page_no IS NOT NULL` filter: `encrypted_pdf` is a DOCUMENT-level
        # failure with a null page, and excluding it reproduced in miniature
        # the exact defect this method exists to fix.
        for row in self.conn.execute("""
                SELECT q.document_id, q.page_no, q.kind, q.severity, q.detail,
                       d.title
                  FROM quality_issues q
                  JOIN documents d ON d.document_id = q.document_id
                 ORDER BY q.document_id, q.page_no IS NULL, q.page_no, q.kind"""):
            spec = self.QUALITY_GAP_KINDS.get(row["kind"])
            if spec is None:
                continue
            gap_kind, code, advice = spec
            title = row["title"] or row["document_id"]
            if row["page_no"] is None:
                # Document-level: no page to cite, so the subject is the
                # document and `cites` is empty, which `verify()` permits for a
                # non-element subject.
                self.gap(kind=gap_kind,
                         subject={"kind": "source_document",
                                  "id": row["document_id"], "tenant": None},
                         code=code, params={"detail": row["detail"] or ""},
                         cites=[],
                         would_close=f"\"{title}\": {advice}",
                         closes_by="knowledge", severity="informational")
                raised += 1
                continue
            try:
                ref = self.source_ref_page(row["document_id"], row["page_no"])
            except (KeyError, TenantLeak):
                continue
            self.gap(kind=gap_kind,
                     subject={"kind": "page",
                              "id": f"{row['document_id']}#p{row['page_no']}",
                              "tenant": None},
                     code=code,
                     params={"page_no": row["page_no"], "detail": row["detail"] or ""},
                     cites=[ref],
                     # `pN`, not `page N`: G40's guard looks for `\bp\d+\b`,
                     # and every other gap in the snapshot reads that way.
                     would_close=f"p{row['page_no']} of \"{title}\": {advice}",
                     closes_by="knowledge",
                     # An `info` issue is never a line warning. Otherwise the
                     # question is whether this document already backs a
                     # published value: if it does, this page is a sibling of
                     # one a plan depends on and the curator working that
                     # document needs it; if nothing cites the document, the
                     # gap is background about this platform's own reading.
                     severity=("informational"
                               if row["severity"] == "info"
                               or ref.belongs_to not in backing
                               else "warns_line"))
            raised += 1
        return raised

    def source_ref_page(self, document_id: str, page_no: int) -> SourceRef:
        """Mint a reference to a WHOLE PAGE, registering its document.

        The page is a first-class locus: `refs.ref_id(sha, page_no, None)` is
        its id, `refs.build_index` marks it `is_page`, and `crops.render_crop`
        already reads `bbox=None` as "the whole page, not an error". The only
        thing missing was a way to mint one, and its absence is what produced
        G73: `promote_tables` needed an evidence anchor for a reviewed table,
        had no page-level ref available, and settled for the first element on
        the page in reading order -- the banner on every scanned NOA. 108 of
        108 promoted facts cited a heading.

        A table review in this store is a review of a PAGE crop: `is_page=True`,
        `bbox=None`. A person looked at the page image, so no geometry can
        recover a table rectangle after the fact and the page is the honest
        citation -- it is exactly, and only, what was examined.

        Registers the `SourceDoc` as a side effect, like `source_ref`, so
        closure stays structural rather than checked. Tenancy is enforced
        before registration for the same reason it is there.
        """
        key = f"page:{document_id}:{page_no}"
        if key in self._refs:
            return self._refs[key]
        row = self.conn.execute("""
            SELECT p.page_no, v.sha256, d.document_id, d.doc_type,
                   d.title, d.version_status, d.version_status_basis,
                   d.issue_date, d.expiration_date, d.owner_tenant
              FROM pages p
              JOIN document_versions v ON v.version_id = p.version_id
              JOIN documents d         ON d.document_id = v.document_id
             WHERE d.document_id = ? AND p.page_no = ?""",
            (document_id, page_no)).fetchone()
        if row is None:
            raise KeyError(f"no such page: {document_id} p{page_no}")
        if not visible_to(row["owner_tenant"], self.tenant):
            raise TenantLeak(
                f"page {page_no} of {document_id} belongs to tenant "
                f"{row['owner_tenant']!r}, not {self.tenant!r}")
        self._register_doc(row)
        ref = SourceRef(id=ref_id(row["sha256"], row["page_no"], None),
                        belongs_to=row["sha256"])
        self._refs[key] = ref
        return ref

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
                   d.issue_date, d.expiration_date, d.owner_tenant
              FROM elements e
              JOIN document_versions v ON v.version_id = e.version_id
              JOIN documents d         ON d.document_id = e.document_id
             WHERE e.element_id = ?""", (element_id,)).fetchone()
        if row is None:
            # Never mint a ref we cannot back. A dangling belongs_to reproduces
            # the exact defect the closure rule was added to close.
            raise KeyError(f"no such element: {element_id}")

        # Obligation 7, at the same choke point as the closure rule and for the
        # same reason: a cross-tenant value is made *unpublishable* rather than
        # filtered afterwards. The check precedes registration -- raising after
        # `self._docs[...]` was written would leave the foreign document in a
        # builder whose `source_docs()` is read at the end of the build, so the
        # exception would be caught and the leak would ship anyway.
        if not visible_to(row["owner_tenant"], self.tenant):
            raise TenantLeak(
                f"element {element_id} belongs to a document owned by "
                f"{row['owner_tenant']!r}; this snapshot is for "
                f"{self.tenant!r}. Nothing of one tenant's reaches another's "
                f"snapshot (obligation 7).")

        self._register_doc(row)
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
        rows = self.conn.execute(f"""
            SELECT DISTINCT v.sha256
              FROM relations r
              JOIN document_versions v ON v.document_id = r.to_document_id
              JOIN documents d         ON d.document_id = r.to_document_id
             WHERE r.from_document_id = ? AND r.relation_type = 'superseded_by'
               AND {visible_sql('d')}
             ORDER BY v.sha256""", (document_id, self.tenant)).fetchall()
        return tuple(r["sha256"] for r in rows)

    def _other_filings(self, sha256: str, own_document_id: str) -> tuple:
        """`{manufacturer, doc_type}` for every other record filing these bytes.

        Grouped on `document_versions.sha256`, not on the `same_content_as`
        edges, and the two are not the same set. One of the 40 edges joins two
        documents with *different* content hashes -- identical extracted text,
        different bytes -- and that pair is two SourceDocs, not two filings of
        one. `also_filed_as` is defined per content hash and cannot express it;
        following the edges instead would attach a filing to bytes it is not a
        filing of, which is a worse error than the omission. Registry §5 names
        that pair as the hard one and leaves it to curation.

        Distinct PAIRS, not distinct rows, and the doc's own pair seeds the set
        it is deduplicated against. The document id is not published -- it is an
        internal handle Planning cannot resolve, the same reason `superseded_by`
        publishes content hashes -- so two records agreeing on both fields are
        indistinguishable once it is dropped, and a repeat of the doc's own
        filing says nothing at all. What is left is exactly what a reviewer
        needs: the filings that DISAGREE with the one published.
        """
        rows = self.conn.execute(f"""
            SELECT DISTINCT d.document_id, d.manufacturer, d.doc_type
              FROM document_versions v
              JOIN documents d ON d.document_id = v.document_id
             WHERE v.sha256 = ? AND {visible_sql('d')}
             ORDER BY d.document_id""", (sha256, self.tenant)).fetchall()
        own = next((r for r in rows if r["document_id"] == own_document_id), None)
        seen = {(own["manufacturer"], own["doc_type"])} if own is not None else set()
        keep = []
        for r in rows:
            pair = (r["manufacturer"], r["doc_type"])
            if r["document_id"] == own_document_id or pair in seen:
                continue
            seen.add(pair)
            keep.append((pair, r["document_id"]))
        # Ordered on the fields that are published, with the document id only as
        # a tie-break. Both fields are nullable in the store, so a NULL sorts as
        # "" rather than raising; and without the tie-break two filings whose
        # sort keys collide would be left in whatever order SQLite returned,
        # which is a store-history dependence -- and this list is hashed.
        keep.sort(key=lambda e: (e[0][0] or "", e[0][1] or "", e[1]))
        return tuple({"manufacturer": m, "doc_type": t} for (m, t), _ in keep)

    def source_docs(self) -> list[SourceDoc]:
        return sorted(self._docs.values(), key=lambda d: d.content_hash)

    # -- gaps ---------------------------------------------------------------
    def gap(self, *, kind: str, subject: dict, code: str, would_close: str,
            closes_by: str, severity: str = "warns_line",
            params: dict | None = None, cites: list | None = None,
            on: str | None = None) -> None:
        if kind == "disputed" and on not in ("value", "conditions"):
            raise ValueError("a `disputed` gap must say what is disputed: "
                             "on='value' or on='conditions'")
        if kind != "disputed" and on is not None:
            raise ValueError(f"`on` is only meaningful on `disputed`, not {kind!r}")
        # `subject` is a dict (amendment 004) -- canonical_bytes() gives a
        # deterministic byte key the same way parameters.py's own group key
        # already does for a [parameter, scope] pair.
        # Keyed on `code` as well as `[kind, subject]`, matching
        # `parameters._Gaps.add`. Two collectors with two different rules for
        # one concept is how 53 of 73 unreconstructed tables were silently
        # dropped by the change written to publish them: every quality gap is
        # `illegible_source`, so a page with two distinct failures collapsed to
        # one and the second vanished. One concept, one rule.
        key = canonical_bytes([kind, subject, code])
        if key in self._gap_keys:      # one gap per subject per kind
            return
        self._gap_keys.add(key)
        self._gaps.append(Gap(id=hashlib.sha256(key).hexdigest()[:16],
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
        # Scoped, not merely gated. `source_ref` refuses a foreign element, so
        # an unscoped scan here would turn another tenant's warning text into a
        # raised exception in the middle of a build rather than into a snapshot
        # that simply does not contain it. Both layers use `visible_sql`, so the
        # query that chooses and the check that refuses cannot disagree.
        rows = self.conn.execute(f"""
            SELECT e.element_id, e.page_no, e.ordinal, e.text, e.ocr_text,
                   e.text_source, e.ocr_confidence, e.lang, e.heading_path,
                   e.document_id, v.sha256, d.doc_type, d.title
              FROM elements e
              JOIN document_versions v ON v.document_id = e.document_id
              JOIN documents d         ON d.document_id = e.document_id
             WHERE {visible_sql('d')}
             ORDER BY e.document_id, e.page_no, e.ordinal""",
            (self.tenant,)).fetchall()

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
                    self.gap(kind="unquantified", subject={"kind": "element", "id": r["element_id"], "tenant": None},
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
                self.gap(kind="unquantified", subject={"kind": "element", "id": r["element_id"], "tenant": None},
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
            # A body that dangles is usually SPLIT, not truncated: the sentence
            # continues in the next element on the page. Join forward before
            # judging, which recovers the warning instead of gapping it --
            # `[measured]` 24 of 26 danglers complete within four elements.
            if _DANGLING.search(body):
                added, used = _join_forward(rows, i, body)
                if added is not None:
                    body = f"{body} {added}".strip()
                    text = f"{text} {added}".strip()
                    anchor = used
            if _INTERLEAVED.search(body):
                self.gap(kind="illegible_source",
                         subject={"kind": "element", "id": r["element_id"], "tenant": None},
                         code="warning_columns_interleaved",
                         params={"page_no": r["page_no"], "tail": _tail(body, 30)},
                         cites=[self.source_ref(r["element_id"])],
                         would_close=f"OCR read two columns of {_where(r)} onto one "
                                     f"line, fusing two notes ({_tail(body)!r}); a "
                                     f"person should read the page image and record "
                                     f"them separately",
                         closes_by="knowledge", severity="warns_line")
                continue
            if _DANGLING.search(body):
                # Still dangling after the join: genuinely cut off. `[measured]`
                # the old test also fired on `body[:1].islower()`, which caught
                # ZERO of the 5 real defects (precision 0.000, recall 0.000)
                # and produced 21 false gaps on its own -- a lowercase first
                # character is not evidence of truncation. It fired on a bullet
                # glyph OCR'd as a literal `k`, on a drop cap, and on the maths
                # variable in `q = (0.00256)(K z)...`. Removed.
                self.gap(kind="illegible_source", subject={"kind": "element", "id": r["element_id"], "tenant": None},
                         code="warning_truncated_mid_clause",
                         params={"ends_with": _tail(body, 30),
                                 "page_no": r["page_no"]},
                         cites=[self.source_ref(r["element_id"])],
                         would_close=f"the warning on {_where(r)} breaks after "
                                     f"{_tail(body)!r}; a person should read the "
                                     f"page image and record the sentence whole",
                         closes_by="knowledge", severity="warns_line")
                continue
            # `anchor`, not `r`: where a lexeme heading's body came from the
            # NEXT element, the confidence that matters is that element's.
            # `[measured]` one published gap claimed a warning "was read at
            # 75.5% confidence" -- 75.5% belonged to the two-token heading
            # `IMPORTANT !`, while the body it quoted was read at 95.31%.
            if (anchor["text_source"] in ("ocr", "image_ocr")
                    and (anchor["ocr_confidence"] or 0) < OCR_TRUST_FLOOR):
                self.gap(kind="illegible_source", subject={"kind": "element", "id": r["element_id"], "tenant": None},
                         code="warning_ocr_below_confidence_floor",
                         # Integers in thousandths: obligation 1 forbids a
                         # float in either direction, and canonical_bytes()
                         # refuses one rather than rounding it silently.
                         params={"confidence_milli": round(anchor["ocr_confidence"] * 1000),
                                 "floor_milli": round(OCR_TRUST_FLOOR * 1000)},
                         cites=[self.source_ref(r["element_id"])],
                         would_close=f"OCR read the warning on {_where(r)} at "
                                     f"{anchor['ocr_confidence']:.1f}% against a "
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
                self.gap(kind="missing_value", subject={"kind": "element", "id": r["element_id"], "tenant": None},
                         code="warning_language_undetermined",
                         params={"page_no": r["page_no"]},
                         cites=[self.source_ref(r["element_id"])],
                         would_close=f"the warning on {_where(r)} has no "
                                     f"determinable language ({_tail(text)!r}); "
                                     f"obligation 10 requires lang on published text",
                         closes_by="knowledge", severity="informational")
                continue

            if _undecodable_ratio(body) > UNDECODABLE_LIMIT:
                # The font layer is corrupted and the text decodes to
                # ciphertext. Publishing it as "verbatim, untranslated" is
                # technically true and useless. `quality.is_mojibake` cannot
                # catch it -- the cipher substitutes onto printable ASCII, so
                # `ascii_token_ratio` stays above its limit on every affected
                # page while `control_ratio` trips 2-4x over.
                self.gap(kind="illegible_source",
                         subject={"kind": "element", "id": r["element_id"], "tenant": None},
                         code="warning_text_undecodable",
                         params={"ratio_milli": round(_undecodable_ratio(body) * 1000),
                                 "page_no": r["page_no"]},
                         cites=[self.source_ref(r["element_id"])],
                         would_close=f"the warning on {_where(r)} decodes to "
                                     f"unreadable characters; its font layer is "
                                     f"corrupted and a person should read the "
                                     f"page image",
                         closes_by="knowledge", severity="warns_line")
                continue

            path = json.loads(r["heading_path"] or "[]")
            step = next((h for h in reversed(path)
                         if _STEP_HEADING.match(h) and not _NOT_A_STEP.search(h)), None)

            key = _warning_key(text)           # G76: identity on the warning
            ref = self.source_ref(anchor["element_id"])
            if key in seen:
                # The same text printed in several documents is one warning with
                # several citations. 14 groups of files here are byte-identical
                # under different manufacturers.
                # UNION, not one-per-document. The old cap was safe only while
                # fragmentation kept each object to a single document; now that
                # twelve fragments of one caution merge, capping would drop the
                # citation count from 458 to 448 -- losing evidence to a fix
                # meant to consolidate it.
                if asdict(ref) not in seen[key]["cites"]:
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
SEVERITIES = frozenset({"warns_line", "informational"})
# §1.2.1 BINDING: "Two of the eight kinds -- `unmodellable_entity` and
# `unmapped_part_kind` -- close by a schema change in the Planning repo, not by
# anything a curator can do. A review queue that shows a curator work only an
# engineer can perform is a queue whose items are not actionable, which is the
# one property it has to have."
CLOSED_BY_PLANNING = frozenset({"unmodellable_entity", "unmapped_part_kind"})
GAP_KINDS = frozenset({
    "unmodellable_entity", "uncovered_condition", "unsatisfiable_requirement",
    "unquantified", "missing_value", "unmapped_part_kind", "disputed",
    "illegible_source"})
DECLARED_LISTS = ("source_docs", "warnings", "gaps", "part_types", "parts",
                  "models", "procedures", "parameters", "combinations", "rules")



# --- warning identity, and text we must not publish -------------------------
# `[measured]` 2026-09-03 over the 289 published warnings.

# A lead marker plus a severity lexeme, at the start of a warning. Widened from
# `_LEAD` to cover `+` and the dash variants, because the corpus prints the same
# caution with `*`, `+`, `–` and `-` and with a bled-through page number in
# front of it: `30 * Caution –`, `4A. * Caution -`, `42 * caution -`.
_KEY_LEAD = re.compile(
    r"^\s*(?:[0-9]{1,3}[A-Za-z]?[.)]?\s*)?[*+\u2013\u2014-]?\s*"
    r"(NOTE|NOTES|CAUTION|WARNING|IMPORTANT|NOTICE|DANGER|ATTENTION|"
    r"ADVERTENCIA|AVERTISSEMENT|TIP)\s*[:!]?\s*", re.I)


def _warning_key(text: str) -> str:
    """The identity two warnings share when they are the same warning.

    The old key was `" ".join(text.split())` over the RAW element text, so
    page-number bleed and delimiter variance each minted a separate identity
    and the corpus's most-repeated caution published as TWELVE objects.

    Normalises only what is demonstrably noise: a leading page number and
    footnote marker before a recognised lexeme, the lexeme's own case, dash
    variants, and whitespace. `[measured]`: merges 24 objects into 7 with ZERO
    false merges across all 289.

    What it deliberately does NOT do is drop the lexeme from the identity. 8
    pairs share a body and differ only in whether a `WARNING:` heading is
    present -- a separate extraction defect, where a body consumed as a
    heading's body is then re-published bare -- and a body-only key has no
    principled way to tell that from a real WARNING and a real CAUTION that
    happen to say the same sentence.
    """
    flat = " ".join((text or "").split())
    m = _KEY_LEAD.match(flat)
    if m:
        flat = f"{m.group(1).upper()}||{flat[m.end():]}"
    return flat.replace("\u2013", "-").replace("\u2014", "-").casefold()


# Characters a fence document legitimately prints: ASCII, the Latin supplements
# and extensions (accents, `¼`, `°`, `©`), general punctuation (`•`, `–`, `″`),
# currency/letterlike/arrows/maths, dingbats, Greek (engineering symbols),
# ligatures (`ﬁ` from InDesign), and spacing modifiers (`˚`).
def _is_legible_char(ch: str) -> bool:
    if ch in "\n\t" or ch.isprintable():
        code = ord(ch)
        return not (0xE000 <= code <= 0xF8FF          # private use
                    or 0xFFF0 <= code <= 0xFFFF       # specials, incl. U+FFFD
                    or 0xD800 <= code <= 0xDFFF)      # surrogates
    return False


def _undecodable_ratio(text: str) -> float:
    """Share of characters that no fence document would print.

    A page whose font layer is corrupted decodes to text like
    `_o\x89|orovbࢼomv1u;\x89vom`. `quality.is_mojibake` cannot catch it: the
    cipher substitutes most letters onto OTHER printable ASCII, so
    `ascii_token_ratio` lands just above its 0.85 limit on every affected page
    (0.857-0.958) while `control_ratio` trips 2-4x over. Only ~10-15% of a
    corrupted page's tokens carry a stray byte at all.

    `[measured]` at the 0.015 threshold: 176 of 49,984 elements and 3 of 289
    warnings are rejected, and every rejected warning is genuine ciphertext.
    Known and deliberate recall gap: two elements of the SAME corruption score
    0.0169 and 0.0, because a substitution onto valid ASCII is invisible to any
    character-class test. This bounds the damage; it does not end it.
    """
    if not text:
        return 0.0
    bad = sum(1 for ch in text if not _is_legible_char(ch))
    return bad / len(text)


UNDECODABLE_LIMIT = 0.015


class VerificationFailed(RuntimeError):
    """A built snapshot broke an obligation and will not be returned.

    Raised, not logged. The failure mode of a bad snapshot is silent: Planning
    pins a hash and computes numbers, and nothing downstream is positioned to
    notice. The gate is the only place it can be caught.
    """


_CODE = re.compile(r"^[a-z][a-z0-9_]*$")
_FILING_KEYS = frozenset({"manufacturer", "doc_type"})


def _also_filed_as(doc: dict, fail: list) -> None:
    """Registry §5 as a gate: one source class per content hash, others named.

    The rule is load-bearing because Planning ranks on `source_class`, and the
    failure it prevents is silent — identical bytes admissible under one filing
    and not under another, with no error raised anywhere. So the field is
    required, not optional: **an absent key is indistinguishable from "these
    bytes are filed once"**, which is the same silence in a new place. Empty is
    a statement; missing is an oversight.

    One half of the rule is not checkable here, and saying so is better than a
    check that looks like it covers it. `SourceDoc` publishes no `manufacturer`
    and no `doc_type` of its own — only the `source_class` derived from one —
    so nothing in a finished snapshot can tell whether an entry repeats the
    doc's own filing. The builder drops it; `tests/test_snapshot_build.py`
    asserts that it did. What is checkable from here is shape, vocabulary,
    distinctness and order.
    """
    at = f"source_docs[{str(doc.get('content_hash'))[:12]}...]"
    also = doc.get("also_filed_as")
    if also is None:
        fail.append(f"{at}: `also_filed_as` is absent. Publish [] rather than "
                    f"omitting it: absent is indistinguishable from 'filed "
                    f"once', and one source class per content hash is only a "
                    f"guarantee if the other filings are visible.")
        return
    if not isinstance(also, (list, tuple)):
        fail.append(f"{at}: `also_filed_as` is {type(also).__name__}, not a list")
        return

    pairs = []
    for j, f in enumerate(also):
        where = f"{at}.also_filed_as[{j}]"
        if not isinstance(f, dict) or set(f) != _FILING_KEYS:
            fail.append(f"{where}: a filing is exactly "
                        f"{{manufacturer, doc_type}}; got {f!r}")
            continue
        for k in ("manufacturer", "doc_type"):
            if f[k] is not None and not (isinstance(f[k], str) and f[k]):
                fail.append(f"{where}: {k} is {f[k]!r}; a filing names it or "
                            f"says null, and an empty string says neither")
        # An unmapped doc_type is the defect in miniature: a filing whose class
        # nobody can compute cannot be reconciled against the one published,
        # which is the whole purpose of listing it.
        if isinstance(f["doc_type"], str) and f["doc_type"] not in SOURCE_CLASS:
            fail.append(f"{where}: doc_type {f['doc_type']!r} maps to no "
                        f"source_class, so the filing it names cannot be "
                        f"ranked against the one published")
        pair = (f["manufacturer"], f["doc_type"])
        if pair in pairs:
            fail.append(f"{where}: {pair} is listed twice. A filing is a "
                        f"(manufacturer, doc_type) pair here — the document id "
                        f"is not published — so a repeat carries nothing.")
        pairs.append(pair)

    # Order is part of the payload: `canonical_bytes` hashes this list as given,
    # so an unstable order would move the snapshot id between two builds over
    # identical knowledge. Nulls sort as "" for the same reason the builder
    # sorts them that way.
    if pairs != sorted(pairs, key=lambda p: (p[0] or "", p[1] or "")):
        fail.append(f"{at}: `also_filed_as` is not in (manufacturer, doc_type) "
                    f"order; the list is hashed, so its order is not free")


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
        _also_filed_as(d, fail)

    # Content hashes do not only travel inside a {id, belongs_to} pair. §1.2.1
    # names `contributing_sources` as a roll-up of the same source_docs, and
    # `superseded_by` was added precisely because "a doc-... id is an internal
    # handle Planning cannot resolve" -- so it is exactly the field the closure
    # rule exists for. `attaches_to.ref` is a content hash for every published
    # warning today. All of them were invisible to a walk keyed on the pair.
    HASH_BEARING = {"superseded_by", "contributing_sources"}

    def walk(node, path="$"):
        if isinstance(node, dict):
            if "belongs_to" in node and node["belongs_to"] not in held:
                fail.append(f"{path}: closure - SourceRef {node.get('id')} belongs_to "
                            f"{str(node['belongs_to'])[:12]}..., not in source_docs")
            ref = node.get("ref")
            if (node.get("kind") in ("document", "warranty")
                    and isinstance(ref, str) and ref not in held):
                fail.append(f"{path}.ref: closure - attaches_to names "
                            f"{ref[:12]}..., not in source_docs")
            for key in HASH_BEARING:
                for i, h in enumerate(node.get(key) or []):
                    if isinstance(h, str) and h not in held:
                        fail.append(f"{path}.{key}[{i}]: closure - {h[:12]}... is "
                                    f"not in source_docs")
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
        elif not g["cites"] and (g.get("subject") or {}).get("kind") == "element":
            fail.append(f"{at}: obligation 8 - an element-scoped gap names a region "
                        f"and so has evidence; cite it")
        if g.get("severity") not in SEVERITIES:
            fail.append(f"{at}: severity {g.get('severity')!r} is not "
                        f"warns_line|informational")
        # BINDING, and the gate is the only thing standing between a future
        # emitter and a queue item no curator can action.
        if g.get("kind") in CLOSED_BY_PLANNING and g.get("closes_by") != "planning":
            fail.append(f"{at}: §1.2.1 - {g['kind']!r} closes by a schema change in "
                        f"the Planning repo, so closes_by must be 'planning', not "
                        f"{g.get('closes_by')!r}")
        if not g.get("subject"):
            fail.append(f"{at}: §1.2.1 - a gap names its subject addressably")
        if not isinstance((g.get("because") or {}).get("params", {}), dict):
            fail.append(f"{at}: because.params must be an object")
        if (g.get("kind") == "disputed") != (g.get("on") is not None):
            fail.append(f"{at}: §1.2.1 - `on` belongs to `disputed` and to nothing "
                        f"else; it is value|conditions")

    # Obligation 5: every part type resolves to a spine type through its
    # parent chain, and `shared` is Planning's namespace, never this
    # platform's to emit. Lazy import: part_types.py never imports this
    # module, so this is not a cycle, but keeping the coupling local matches
    # `_source_class`'s own discipline in parameters.py.
    from .part_types import SPINE
    part_type_keys = set()
    for i, pt in enumerate(snapshot.get("part_types", [])):
        at = f"part_types[{i}]"
        namespace = pt.get("namespace")
        if namespace == "shared":
            fail.append(f"{at}: obligation 5 - `shared` is Planning's namespace; "
                        f"this platform only ever emits mfr/<manufacturer>")
        elif not (isinstance(namespace, str)
                 and re.match(r"^mfr/[a-z0-9]+(?:-[a-z0-9]+)*$", namespace)):
            fail.append(f"{at}: namespace {namespace!r} is not mfr/<slug>")
        key = (namespace, pt.get("key"))
        if key in part_type_keys:
            fail.append(f"{at}: duplicate (namespace, key) {key}")
        part_type_keys.add(key)
        parent = pt.get("parent") or {}
        if parent.get("namespace") != "shared" or parent.get("key") not in SPINE:
            fail.append(f"{at}: parent {parent} does not terminate in the spine")

    # `procedures`. The shape is `knowledge-datamodel.md` §3.6 and the
    # vocabularies are closed, so a value outside them is refused here rather
    # than reaching a consumer that has no case for it.
    STEP_KINDS = frozenset({"assembly", "installation", "preparation",
                            "part_modification", "maintenance"})
    STEP_SCOPES = frozenset({"panel", "bay", "post", "run", "site"})
    EDGE_KINDS = frozenset({"after", "not_before", "before", "exclusive_with"})
    procedure_ids = set()
    for i, proc in enumerate(snapshot.get("procedures", [])):
        at = f"procedures[{i}]"
        pid = proc.get("id")
        if not pid:
            fail.append(f"{at}: no id. N13 makes it load-bearing -- without one "
                        f"`Warning.attaches_to{{kind: procedure}}` cannot address "
                        f"this procedure and a correction reaches no siblings")
        if pid in procedure_ids:
            fail.append(f"{at}: duplicate Procedure.id {pid!r}")
        procedure_ids.add(pid)
        keys = {st.get("key") for st in proc.get("steps") or []}
        if len(keys) != len(proc.get("steps") or []):
            fail.append(f"{at}: two steps share a key")
        for j, st in enumerate(proc.get("steps") or []):
            sat = f"{at}.steps[{j}]"
            if st.get("kind") not in STEP_KINDS:
                fail.append(f"{sat}: kind {st.get('kind')!r} is not one of "
                            f"{sorted(STEP_KINDS)}")
            if st.get("scope") not in STEP_SCOPES:
                fail.append(f"{sat}: scope {st.get('scope')!r} is not one of "
                            f"{sorted(STEP_SCOPES)}")
            if not (st.get("cites") or []):
                fail.append(f"{sat}: no cites; a published step must say where "
                            f"it was read from")
            if not (st.get("text_i18n") or "").strip():
                fail.append(f"{sat}: empty text")
            for edge in st.get("requires") or []:
                if edge.get("kind") not in EDGE_KINDS:
                    fail.append(f"{sat}: requires kind {edge.get('kind')!r} is not "
                                f"one of {sorted(EDGE_KINDS)}")
                if edge.get("step") not in keys:
                    fail.append(f"{sat}: requires names {edge.get('step')!r}, which "
                                f"is not a step of this procedure")

    PART_STATUSES = frozenset({"draft", "active", "retired"})
    SPEC_AGREE = frozenset({"==", "!=", "<=", ">=", "in", "supplies"})
    declared_part_types = [{"namespace": pt.get("namespace"), "key": pt.get("key")}
                           for pt in snapshot.get("part_types", [])]
    for i, p in enumerate(snapshot.get("parts", [])):
        at = f"parts[{i}]"
        if p.get("status") not in PART_STATUSES:
            fail.append(f"{at}: status {p.get('status')!r} is not "
                        f"draft|active|retired")
        if p.get("authorship") != "third_party_authored":
            fail.append(f"{at}: authorship {p.get('authorship')!r} -- everything "
                        f"this platform publishes is third_party_authored")
        ptype = p.get("type") or {}
        if ptype.get("namespace") == "shared":
            if ptype.get("key") not in SPINE:
                fail.append(f"{at}.type: {ptype} does not resolve to a spine key")
        elif ptype not in declared_part_types:
            fail.append(f"{at}.type: {ptype} resolves to no part_types[] entry "
                        f"in this snapshot")
        for j, sf in enumerate(p.get("spec") or []):
            sat = f"{at}.spec[{j}]"
            if sf.get("agree") not in SPEC_AGREE:
                fail.append(f"{sat}: agree {sf.get('agree')!r} is not one of "
                            f"the six")
            if not (sf.get("provenance") or {}).get("cites"):
                fail.append(f"{sat}: obligation 3 - a spec value carries a "
                            f"resolvable SourceRef")

    if fail:
        raise VerificationFailed(
            f"{len(fail)} obligation failure(s); the snapshot is not returned:\n  - "
            + "\n  - ".join(fail))


def build_snapshot(*, tenant: str, regime: str = "us_astm",
                   conn: sqlite3.Connection | None = None) -> dict:
    """Assemble, canonicalise and hash. Provenance first -- closure needs it."""
    validate_tenant(tenant)     # before a connection is opened, not after
    own = conn is None
    conn = conn or connect(read_only=True)
    try:
        b = SnapshotBuilder(conn, tenant=tenant, regime=regime)
        warnings = b.warnings()   # mints refs, registers docs, raises gaps

        # Parameter tables are built through the SAME ref minter, so §1.2.1's
        # closure rule stays STRUCTURAL rather than merely checked: minting a
        # reference registers its SourceDoc, so a table that cited a document
        # outside `source_docs` could not be produced in the first place.
        from .parameters import build_parameter_tables
        # `b.source_ref` returns the SourceRef dataclass; the wire wants a dict,
        # and `canonical_bytes` refuses anything else. Minting still goes through
        # the builder, so the closure rule stays structural.
        parameters, parameter_gaps = build_parameter_tables(
            conn, tenant=tenant,
            source_ref=lambda eid: asdict(b.source_ref(eid)),
            source_ref_page=lambda d, pg: asdict(b.source_ref_page(d, pg)))
        for g in parameter_gaps:
            b.gap(kind=g["kind"], subject=g["subject"],
                  code=g["because"]["code"], params=g["because"].get("params") or {},
                  # Defect found while wiring PartType/Part gaps below: this
                  # loop never passed `cites` through, so every real citation
                  # `parameters._Gaps.add()` computed (disputed, unquantified,
                  # unmodellable_entity) was silently dropped before reaching
                  # the wire -- obligation 8's "evidence, where there is any"
                  # violated in spirit though not in verify()'s letter (ParamRef
                  # subjects are never required to cite). Currently dormant --
                  # 0 published parameter gaps carry cites as of this snapshot
                  # -- not yet a live defect, but the next disputed/unquantified
                  # gap would have shipped uncited.
                  cites=[SourceRef(**c) for c in g.get("cites") or []],
                  would_close=g["would_close"], closes_by=g["closes_by"],
                  severity=g.get("severity", "warns_line"), on=g.get("on"))

        # PartType/Part (obligation 5, and the identity half of obligation 14):
        # same ref minter, same closure-is-structural reasoning as above.
        from .part_types import PartTypeRegistry, build_part_types, load_slice_components
        from .parts import build_parts
        components = load_slice_components()      # DatasetChanged -> build fails closed
        part_type_registry = PartTypeRegistry()
        part_types, part_type_gaps = build_part_types(components, part_type_registry)
        parts, part_gaps = build_parts(
            components, part_type_registry, conn=conn,
            source_ref=lambda eid: asdict(b.source_ref(eid)))
        for g in (*part_type_gaps, *part_gaps):
            b.gap(kind=g["kind"], subject=g["subject"],
                  code=g["because"]["code"], params=g["because"].get("params") or {},
                  cites=[SourceRef(**c) for c in g.get("cites") or []],
                  would_close=g["would_close"], closes_by=g["closes_by"],
                  severity=g.get("severity", "warns_line"), on=g.get("on"))

        # The hashed part is the CONTENT plus the coordinates that change its
        # meaning. `retain_until` is deliberately outside it: it moves with the
        # clock, and hashing it would mean two builds over identical knowledge
        # never matched -- which is the opposite of what obligation 1 asks for.
        from .procedures import build_procedures
        procedures, procedure_gaps = build_procedures(
            conn, tenant=tenant,
            source_ref_page=lambda d, pg: asdict(b.source_ref_page(d, pg)))
        for g in procedure_gaps:
            b.gap(kind=g["kind"], subject=g["subject"],
                  code=g["because"]["code"], params=g["because"].get("params"),
                  cites=[SourceRef(**c) for c in g.get("cites") or []],
                  would_close=g["would_close"], closes_by=g["closes_by"],
                  severity=g["severity"], on=g.get("on"))

        # G78. Every extraction failure this platform already DETECTED,
        # published as a gap. Runs LAST of the ref-minting passes, and that
        # ordering is load-bearing: its severity rule asks whether a document
        # already backs a published value, which is only knowable once
        # warnings, parameters and parts have registered theirs.
        b.quality_gaps()

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
            "part_types": part_types, "parts": parts,
            "models": [], "procedures": procedures,
            "parameters": parameters, "combinations": [], "rules": [],
        }
        canonical_bytes(members)           # refuses floats, sets, unsortable keys
        verify(members)                    # the gate: a failure is never returned
        return {"snapshot_id": content_hash(members),
                "retain_until": (date.today() + timedelta(days=RETAIN_DAYS)).isoformat(),
                **members}
    finally:
        if own:
            conn.close()
