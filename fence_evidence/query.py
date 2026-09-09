"""The query surface — *"here is the situation, what applies, and on what
evidence?"* — as a function.

`docs/knowledge-loop.md` §3 and §10 item 2. This is the only real interface to
the agent that lives in Planning's backend, and it is deliberately **not** an
HTTP route yet: Planning owes us a request shape (`conversation.md` T58 §3,
*"we will send you a request shape rather than assume one"*), and wrapping this
in a route before it arrives would be building to a guess. `Situation` is this
module's own reading of the question, replaceable when their shape lands; the
answer side is not, because both of its properties were agreed:

* **The refs come back explicitly.** T59 §2: *"a query response must return its
  refs explicitly, as a list the caller can hold and compare against, not merely
  embedded in prose or implied by a value. Otherwise your check has nothing to
  match."* Their grounding rule is *a claim may only cite what that task run's
  view returned* (T58 §2). `QueryAnswer.refs` is that list, and it is exactly
  the set of refs reachable from the rest of the answer — nothing more, so a
  fabricated citation cannot hide in it, and nothing less, so an honest one
  cannot be refused.
* **The answer names the snapshot it was computed from.** T58 §3 made that the
  single condition on which a served query was admitted at all. There is no
  "latest snapshot" here and deliberately so: a snapshot carries no build time,
  and picking one by mtime would make an agent's advice depend on the order
  files landed on a disk. The caller names one or is refused.

### What this does NOT do

**It does not resolve conflicts.** `docs/target-architecture.md` §5.2 lists
automatic conflict resolution as a *never*, and `knowledge-loop.md` §8 keeps it
that way under the learning layer. Two published rows disagreeing at one point
both come back and the disagreement is named. The source policy ranks; it does
not delete.

**It does not grade applicability.** `knowledge-loop.md` §11: *"today the system
can say 'exact match' or 'no rule'. It cannot say 'weaker evidence'. That is
real, and it is not yet designed."* So a finding reports what matched and what
did not — two closed vocabularies, no number — plus the provenance the row
already carries. Inventing a score here would be exactly the silent weighting
§1 says may never destroy the property that every number can be shown to an
inspector.

**It does not read the query log.** There is no query log yet; it is item 3.

### Why a table for another product still comes back

`knowledge-loop.md` §1: *"A footing table from one manufacturer is not
inapplicable to a different vinyl fence; it is weaker evidence, and one of the
open problems below is that the system has no way to say so."* Dropping it would
be this platform deciding; returning it labelled `scope: "other"` leaves the
decision where the evidence is. A stated condition the row **contradicts** is a
different matter — Exposure B is not weak evidence about Exposure C, it is a
different question — and those rows are excluded.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from typing import Any

from .parameters import CONDITION_SCOPE
from .refs import ref_id
from .tenancy import visible_to


class QueryRefused(ValueError):
    """The query cannot be answered honestly, so it is not answered.

    Every use is a case where guessing would produce a plausible answer: an
    unnamed snapshot, a condition dimension we do not carry, a tombstoned
    payload. Refusing is `guide.md`'s rule applied at the only surface an
    outside system sees.
    """


# The dimensions a claim may be conditioned on. `parameters.CONDITION_SCOPE` is
# the live registry -- one definition, so the query cannot accept a dimension
# the publisher would refuse, or refuse one it publishes.
KNOWN_DIMENSIONS = frozenset(CONDITION_SCOPE)

SCOPE_MATCH = ("exact", "other", "not_requested")
CONDITION_MATCH = ("stated_and_satisfied", "unstated")


# ------------------------------------------------------------------ request

@dataclass(frozen=True)
class Situation:
    """What the caller says about the job. Deliberately not a job blob.

    `knowledge-loop.md` §3 cuts whole-job storage with its reasoning, and T58 §3
    names this as *"the field where an agent would most easily start shipping
    you a job blob"*. So every field here is something this platform can
    actually reason with, and an unrecognised condition dimension is refused
    rather than ignored.
    """

    question: str | None = None
    conditions: dict[str, Any] = field(default_factory=dict)
    scope: dict[str, Any] | None = None
    task: str | None = None
    role: str | None = None
    limit: int = 10


# ------------------------------------------------------------------ answer

@dataclass(frozen=True)
class ValueFinding:
    parameter: str
    scope: dict | None
    task: str | None
    value: Any
    value_type: str | None
    conditions: dict
    condition_basis: str | None
    valid_from: dict | None
    valid_until: dict | None
    applicability: dict
    strength: dict
    currency: dict
    cites: list

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ProcedureFinding:
    id: str
    scope: dict | None
    steps: list
    cites: list
    applicability: dict

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class QueryAnswer:
    snapshot_id: str
    refs: list
    values: tuple
    procedures: tuple
    conflicts: tuple
    evidence: tuple
    unstated_conditions: tuple
    outside_domain: tuple
    basis: dict

    def to_dict(self) -> dict:
        return {
            "snapshot_id": self.snapshot_id,
            "refs": [dict(r) for r in self.refs],
            "values": [v.to_dict() for v in self.values],
            "procedures": [p.to_dict() for p in self.procedures],
            "conflicts": [dict(c) for c in self.conflicts],
            "evidence": [dict(e) for e in self.evidence],
            "unstated_conditions": list(self.unstated_conditions),
            "outside_domain": list(self.outside_domain),
            "basis": dict(self.basis),
        }


# ------------------------------------------------------------------ matching

def _key(obj) -> str:
    """A stable comparison key for a published fragment, without floats."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), default=str)


def _milli(value) -> int | None:
    """The comparable magnitude of a published Quantity, or None.

    Quantities are integers in thousandths (`canonical.py` refuses floats), so
    this never introduces a rounding question of its own.
    """
    if isinstance(value, dict) and isinstance(value.get("amount_milli"), int):
        return value["amount_milli"]
    return None


def _is_range(condition) -> bool:
    return isinstance(condition, dict) and (
        "min" in condition or "max" in condition)


def _within(stated, bracket) -> bool | None:
    """Does the stated value fall inside a published bracket?

    Returns None when the comparison cannot be made at all -- a bracket in a
    unit we cannot read, say -- so the caller can report "unstated" rather than
    silently excluding a row on a comparison that never happened.
    """
    amount = _milli(stated)
    if amount is None:
        return None
    low, high = bracket.get("min"), bracket.get("max")
    low_mm, high_mm = _milli(low), _milli(high)
    if low is not None and low_mm is None:
        return None
    if high is not None and high_mm is None:
        return None
    if low_mm is not None:
        if amount < low_mm or (amount == low_mm
                               and not bracket.get("min_inclusive", True)):
            return False
    if high_mm is not None:
        if amount > high_mm or (amount == high_mm
                                and not bracket.get("max_inclusive", True)):
            return False
    return True


def _satisfies(stated, published) -> bool | None:
    """True/False/None -- satisfied, contradicted, or not comparable."""
    if _is_range(published):
        return _within(stated, published)
    if isinstance(published, dict) or isinstance(stated, dict):
        return _key(stated) == _key(published)
    # Scalars: compare as strings, but only after normalising the two ways a
    # published condition legitimately differs from a caller's -- case, and the
    # `130` / `130.0` split `facts.query_facts` still has (see its docstring).
    return _scalar(stated) == _scalar(published)


def _scalar(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        text = f"{float(value):.6f}".rstrip("0").rstrip(".")
        return text or "0"
    return str(value).strip().lower()


def _row_verdict(row_conditions: dict, stated: dict) -> tuple[bool, str, set]:
    """(admitted, conditions verdict, dimensions that excluded this row)."""
    excluded: set[str] = set()
    unstated = False
    for dimension, published in (row_conditions or {}).items():
        if dimension not in stated:
            unstated = True
            continue
        verdict = _satisfies(stated[dimension], published)
        if verdict is False:
            excluded.add(dimension)
        elif verdict is None:
            unstated = True
    if excluded:
        return False, "excluded", excluded
    return True, ("unstated" if unstated else "stated_and_satisfied"), excluded


def _scope_verdict(published_scope, requested) -> str:
    if requested is None:
        return "not_requested"
    if published_scope is None:
        return "other"
    if (published_scope.get("kind") == requested.get("kind")
            and published_scope.get("id") == requested.get("id")):
        return "exact"
    return "other"


# ------------------------------------------------------------------ the query

def answer_query(situation: Situation, *, snapshot: dict | None = None,
                 snapshot_id: str | None = None,
                 conn: sqlite3.Connection | None = None,
                 snapshot_root=None) -> QueryAnswer:
    """Answer one situation against one named snapshot.

    Exactly one of `snapshot` (a loaded payload) and `snapshot_id` (loaded from
    the store) must be given. `conn` is only needed for the retrieval half --
    without it a question searches nothing and the published half still answers.
    """
    if (snapshot is None) == (snapshot_id is None):
        raise QueryRefused(
            "a query answer names the snapshot it was computed from: pass "
            "exactly one of snapshot= or snapshot_id= (conversation.md T58 §3)")
    if snapshot is None:
        from . import snapshot_store  # lazy: the published half only
        snapshot = snapshot_store.get_snapshot(snapshot_id, root=snapshot_root)
    if snapshot.get("tombstoned"):
        raise QueryRefused(
            f"snapshot {snapshot.get('snapshot_id')} was excised: "
            f"{snapshot.get('reason')!r}")

    stated = dict(situation.conditions or {})
    unknown = sorted(set(stated) - KNOWN_DIMENSIONS)
    if unknown:
        raise QueryRefused(
            "unrecognised condition dimension(s) "
            + ", ".join(repr(u) for u in unknown)
            + "; a dimension dropped silently would turn a narrow question into "
              "a broad answer. Known: " + ", ".join(sorted(KNOWN_DIMENSIONS)))
    requested_scope = situation.scope
    if requested_scope is not None and not (
            requested_scope.get("kind") and requested_scope.get("id")):
        raise QueryRefused("a scope must carry both a kind and an id")

    values, unstated, outside = _applicable_values(snapshot, stated,
                                                   requested_scope)
    procedures = _applicable_procedures(snapshot, requested_scope)
    conflicts = _conflicts(values)
    evidence, tenancy_suppressed = _evidence(situation, snapshot, conn,
                                            _cited_documents(values, procedures))

    refs = _collect_refs(values, procedures, conflicts, evidence)
    return QueryAnswer(
        snapshot_id=snapshot["snapshot_id"],
        refs=refs,
        values=values,
        procedures=procedures,
        conflicts=conflicts,
        evidence=evidence,
        unstated_conditions=tuple(sorted(unstated)),
        outside_domain=tuple(sorted(outside)),
        basis={
            "conditions_stated": sorted(stated),
            "scope_requested": bool(requested_scope),
            "searched": bool(situation.question) and conn is not None,
            "tenancy_suppressed": tenancy_suppressed,
            "conflicts_resolved": False,
            "evidence_support_claimed": False,
            "exact_findings": _exact(values),
            "exact_findings_superseded": _exact(values, superseded=True),
            "applicability_is_graded": False,
        },
    )


def _exact(values, *, superseded: bool = False) -> int:
    """How many findings matched the caller's product exactly -- and how many of
    those a later document replaced. One number that names the trap: every
    exactly-scoped answer you have is out of date."""
    exact = [f for f in values if f.applicability["scope"] == "exact"]
    if not superseded:
        return len(exact)
    return sum(1 for f in exact if f.currency["superseded_by"])


def _supersession(snapshot) -> dict:
    """`content_hash -> what replaced it`, read from the snapshot's own
    `source_docs`.

    Read from the PINNED SNAPSHOT rather than the live store on purpose: it is
    deterministic, the same answer a year from now, and a pinned answer must not
    depend on anything outside its own pin.

    This was also written to avoid `relations.supersession_chain`'s `LIMIT 1`
    per hop, which returned one arbitrary path through what is really a DAG and
    silently dropped chain members. **That defect is fixed as of 2026-09-09
    (G110)**, so only the first reason still stands -- but it is the load-bearing
    one, and this comment said otherwise in the present tense for a day.
    """
    return {doc["content_hash"]: list(doc.get("superseded_by") or [])
            for doc in (snapshot.get("source_docs") or [])
            if doc.get("content_hash")}


def _link_replacements(findings) -> None:
    """Say which superseding document is ALSO in this answer, and how it graded.

    This is the Chesterfield trap made visible: the in-force approval is right
    there, under a different `fence_model` id, graded `other`, while the only
    `exact` row expired in 2018.
    """
    by_authority: dict = {}
    for finding in findings:
        by_authority.setdefault(finding.strength.get("authority"),
                                []).append(finding)
    for finding in findings:
        for replacement in finding.currency["superseded_by"]:
            for other in by_authority.get(replacement, []):
                entry = {"parameter": other.parameter,
                         "authority": replacement,
                         "scope_id": (other.scope or {}).get("id"),
                         "applicability": dict(other.applicability)}
                if entry not in finding.currency["superseded_by_in_answer"]:
                    finding.currency["superseded_by_in_answer"].append(entry)


def _applicable_values(snapshot, stated, requested_scope):
    findings, unstated, outside = [], set(), set()
    graph = _supersession(snapshot)
    # An absent `source_docs` is an ABSENCE, not an assertion that nothing is
    # superseded, and the answer must not read as the latter.
    basis = "supersession_graph" if graph else "version_status_label_only"
    for table in snapshot.get("parameters", []) or []:
        declared = set(table.get("condition_scope") or {})
        scope_match = _scope_verdict(table.get("scope"), requested_scope)
        admitted_any = False
        excluded_by: dict[str, int] = {}
        rows = table.get("rows") or []
        for row in rows:
            ok, verdict, excluded = _row_verdict(row.get("conditions") or {},
                                                 stated)
            if not ok:
                for dimension in excluded:
                    excluded_by[dimension] = excluded_by.get(dimension, 0) + 1
                continue
            admitted_any = True
            if verdict == "unstated":
                unstated |= (set(row.get("conditions") or {}) - set(stated))
            provenance = row.get("provenance") or {}
            findings.append(ValueFinding(
                parameter=table.get("parameter"),
                scope=table.get("scope"),
                task=table.get("task"),
                value=row.get("value"),
                value_type=table.get("value_type"),
                conditions=row.get("conditions") or {},
                condition_basis=row.get("condition_basis"),
                valid_from=row.get("valid_from"),
                valid_until=row.get("valid_until"),
                applicability={"scope": scope_match, "conditions": verdict},
                currency={
                    # `knowledge-loop.md` §3: "currency comes from the
                    # supersession graph and not from the `version_status`
                    # label". The label is still reported next door in
                    # `strength`; it is not what this reads.
                    "version_status": provenance.get("version_status"),
                    "superseded_by": list(graph.get(row.get("authority"), [])),
                    "superseded_by_in_answer": [],
                    "basis": basis,
                },
                strength={
                    "curation_level": provenance.get("curation_level"),
                    "source_class": provenance.get("source_class"),
                    "version_status": provenance.get("version_status"),
                    "authority": row.get("authority"),
                    "hit_policy": table.get("hit_policy"),
                },
                cites=list(provenance.get("cites") or []),
            ))
        # A dimension the caller stated that excluded every row of a table
        # declaring it is the "outside documented range" answer Phase 7 asked
        # for by name -- not a reason to hand back the nearest row.
        if rows and not admitted_any:
            for dimension, count in excluded_by.items():
                if count == len(rows) and dimension in declared:
                    outside.add(dimension)
        unstated |= (declared - set(stated)) if admitted_any else set()
    findings.sort(key=lambda f: (f.parameter or "", _key(f.scope),
                                 _key(f.conditions), _key(f.value)))
    _link_replacements(findings)
    return tuple(findings), unstated, outside


def _applicable_procedures(snapshot, requested_scope):
    out = []
    for procedure in snapshot.get("procedures", []) or []:
        out.append(ProcedureFinding(
            id=procedure.get("id"),
            scope=procedure.get("scope"),
            steps=list(procedure.get("steps") or []),
            cites=list(procedure.get("cites") or []),
            applicability={
                "scope": _scope_verdict(procedure.get("scope"),
                                        requested_scope),
                "conditions": "unstated",
            },
        ))
    out.sort(key=lambda p: p.id or "")
    return tuple(out)


def _conflicts(values):
    """Two applicable values for one parameter, one product and one set of
    conditions, that do not agree. Named, never resolved."""
    groups: dict[str, list] = {}
    for finding in values:
        scope_id = (finding.scope or {}).get("id")
        key = _key([finding.parameter, scope_id, finding.conditions])
        groups.setdefault(key, []).append(finding)
    out = []
    for group in groups.values():
        distinct = {_key(f.value) for f in group}
        if len(distinct) < 2:
            continue
        cites, seen = [], set()
        for finding in group:
            for cite in finding.cites:
                if cite["id"] not in seen:
                    seen.add(cite["id"])
                    cites.append(dict(cite))
        out.append({
            "parameter": group[0].parameter,
            "scope": group[0].scope,
            "conditions": group[0].conditions,
            "values": [f.value for f in group],
            "authorities": sorted({f.strength.get("authority")
                                   for f in group if f.strength.get("authority")}),
            "cites": sorted(cites, key=lambda c: (c["belongs_to"], c["id"])),
            "resolution": None,
            "basis": "surfaced, not resolved (target-architecture.md §5.2)",
        })
    out.sort(key=lambda c: (c["parameter"] or "", _key(c["conditions"])))
    return tuple(out)


# ------------------------------------------------------------------ retrieval

def _cited_documents(values, procedures) -> dict:
    """Which documents the published half of this answer already cites.

    Keyed on `belongs_to` -- the document version hash -- which both a
    published citation and a live-minted evidence ref already carry, so the
    join is identity and not a guess.
    """
    out: dict[str, list] = {}

    def add(sha, kind, ident):
        if not sha:
            return
        entry = {"kind": kind, "id": ident}
        bucket = out.setdefault(sha, [])
        if entry not in bucket:
            bucket.append(entry)

    for finding in values:
        for cite in finding.cites:
            add(cite.get("belongs_to"), "value", finding.parameter)
    for procedure in procedures:
        for cite in procedure.cites:
            add(cite.get("belongs_to"), "procedure", procedure.id)
        for step in procedure.steps:
            for cite in step.get("cites") or []:
                add(cite.get("belongs_to"), "procedure", procedure.id)
    for bucket in out.values():
        bucket.sort(key=lambda e: (e["kind"], e["id"] or ""))
    return out


def _evidence(situation: Situation, snapshot: dict, conn,
              cited_by: dict | None = None):
    """The passages behind the question, each carrying a mintable ref.

    Delegates to `search_evidence` with its shipped defaults and changes
    nothing about the ranking: R3 stays on, no filters are added, and the order
    is the order search returned. That is deliberate -- the acceptance test for
    this item is that the gold set scores no worse than the retrieval baseline,
    and the only way to guarantee that is to not touch retrieval.
    """
    if not situation.question or conn is None:
        return (), 0
    from .retrieval import search_evidence  # lazy: the published half only

    results = search_evidence(situation.question, limit=situation.limit,
                              conn=conn)
    if not results:
        return (), 0
    loci = _loci(conn, [r.element_id for r in results])
    tenant = snapshot.get("tenant")
    out, suppressed = [], 0
    for result in results:
        locus = loci.get(result.element_id)
        if locus is None:
            # No version row for the element the projection returned. A hit we
            # cannot cite is a hit we must not hand to a grounding check.
            suppressed += 1
            continue
        if not visible_to(locus["owner_tenant"], tenant):
            suppressed += 1
            continue
        record = result.to_dict()
        record["ref"] = {"id": ref_id(locus["sha256"], result.page,
                                      locus["bbox"]),
                         "belongs_to": locus["sha256"]}
        # Document identity, and deliberately nothing more. `evidence` and
        # `values` arrived as two parallel lists with nothing joining them --
        # a sealed approval's number beside passages from an installation
        # guide, and no way to tell which passages were even in the same
        # document as the number. This says they share one. It does NOT say
        # the passage states the value: that is support, this platform has not
        # verified it, and asserting it beside a value whose whole worth is
        # that it WAS verified is exactly the wrong place to guess.
        shared = (cited_by or {}).get(locus["sha256"], [])
        record["from_cited_document"] = bool(shared)
        record["cited_by"] = [dict(entry) for entry in shared]
        out.append(record)
    return tuple(out), suppressed


def _loci(conn, element_ids):
    """The raw bbox text and version hash each ref is minted from.

    `elements.bbox` is read as stored -- `refs.ref_id` interpolates it verbatim
    and the published cites were minted from that exact string.
    """
    if not element_ids:
        return {}
    marks = ",".join("?" * len(element_ids))
    rows = conn.execute(
        f"""SELECT e.element_id, e.bbox, v.sha256, d.owner_tenant
              FROM elements e
              JOIN document_versions v ON v.version_id = e.version_id
              JOIN documents d ON d.document_id = e.document_id
             WHERE e.element_id IN ({marks})""", list(element_ids)).fetchall()
    return {r["element_id"]: {"bbox": r["bbox"], "sha256": r["sha256"],
                              "owner_tenant": r["owner_tenant"]}
            for r in rows}


def _collect_refs(values, procedures, conflicts, evidence):
    """Exactly the refs the rest of the answer cites -- nothing more, nothing
    less. T59 §2: this list is what a grounding check matches against, so a ref
    in it that nothing cites would admit a citation the caller never saw."""
    seen: dict[str, dict] = {}

    def add(cite):
        if isinstance(cite, dict) and cite.get("id"):
            seen.setdefault(cite["id"], {"id": cite["id"],
                                         "belongs_to": cite.get("belongs_to")})

    for finding in values:
        for cite in finding.cites:
            add(cite)
    for procedure in procedures:
        for cite in procedure.cites:
            add(cite)
        for step in procedure.steps:
            for cite in step.get("cites") or []:
                add(cite)
    for conflict in conflicts:
        for cite in conflict["cites"]:
            add(cite)
    for hit in evidence:
        add(hit.get("ref"))
    return [seen[key] for key in sorted(seen)]
