"""Conditional knowledge, published as tables Planning can evaluate.

`contract.md` §1.3 calls `ParameterTable` *the important object*: a value such
as maximum post spacing is not one number, it depends on conditions known only
when a specific site is planned. So this platform publishes the whole small
table and Planning evaluates it at run time, deterministically, from pinned data.

Like `snapshot.py`, this is **a projection, not an agent**. It reads promoted
`facts` rows -- each one a table cell a person accepted, carrying the conditions
of the row it sat in -- and rewrites them into the shape the contract names. It
selects no winner, applies no source policy (§1.4: Planning does that, at run
time, for a task only it knows) and reads no PDF.

Four decisions carry the design. Each is a reading of a BINDING clause, and each
is recorded here because a later reader will otherwise have to re-derive it.

**1. A row is a PATTERN over the domain, not a point in it.** A condition key a
row does not mention matches every value of that dimension. §1.3's own shape
shows `{exposure_category: "C", hvhz: false}` against a two-dimensional domain,
and obligation 15 makes the limiting case explicit -- a `stated` row with *no*
conditions is a fallback covering everything. Coverage and collision are both
computed against the expanded point set, never against the literal condition
dicts.

**2. `condition_scope` says WHEN a key can be bound**, per obligation 13 as
restated in v0.4.1. `exposure_category` and `hvhz` are `site` facts. What is
banned is an *instance* reference -- station 7, bay 3 -- not a narrow scope, so
`fence_height` (`bay`) and `post_role` (`post`) are publishable: they expand up
front over a closed enumeration and bind later. A key with no declared scope is
not published at all; see `_translate_conditions`.

**3. Two rows at one point are a collision only when their VALUES differ and
their validity windows OVERLAP.** Disjoint windows are a succession, not a
conflict -- the whole reason §1.3 carries expiry as fields rather than as an
`as_of_date` dimension. Equal values are corroboration: whatever order a
consumer evaluates them in it gets the same number, which is the failure
rationale.md §2 says the check exists to prevent, and §1.4 positively *requires*
several rows per point where several sources state it ("a snapshot carries every
admissible row including the ones a policy will reject"). §1.4's BINDING
tie-break -- curation level, then issue date, then source class -- is what makes
that multiplicity resolvable.

**4. Where the collision is real, the table is WITHHELD and gapped.** The
footing tables in this corpus are paired design points -- `(footing depth, max
post spacing)` per exposure, a deeper footing buying a wider span -- so two rows
with different values are valid at one point with no dimension to split them.
Candidate amendment C5 records the agreed fix (a paired `value_type`) and it has
NOT landed, so no paired representation is invented here. The three alternatives
are all worse and all were considered:

* publishing under `unique` anyway would break a BINDING clause;
* `collect_min`/`priority` over the pair was **rejected by both sides** (C5): it
  silently discards the cheaper compliant option -- 7 posts against 9 on a 40 ft
  run at exposure C;
* publishing only the non-colliding rows would discard the same option *and*
  make `uncovered` lie, because the dropped rows cover points the survivors do.

So the whole table is withheld and every colliding point becomes an
`unmodellable_entity` gap naming the parameter, the point, the two values and
the amendment that would close it. Obligation 8: publish the gap rather than
approximate into a type that nearly fits.

Nothing here writes to the store, and nothing outside `workspace/` is touched.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from fractions import Fraction

from .canonical import canonical_bytes
from .refs import ref_id
from .reviews import effective_fact_value
from .tenancy import visible_sql

# --------------------------------------------------------------------------
# What a promoted fact is a parameter FOR.
#
# `facts.fact_type` is this platform's internal name and carries the source's
# unit (`_in`); the published parameter carries the unit it CROSSES in, which is
# always mm -- §1.1's UnitCode vocabulary has no inch. `post_spacing_in` becomes
# `max_span_mm` because that is Planning's name for it in §1.3 and §3.8.
# A fact type absent from this map is not published and raises a gap: a
# parameter nobody named is not a parameter Planning can bind.
PARAMETER_OF = {
    "footing_depth_in": ("footing_depth_mm", "mm"),
    "post_spacing_in": ("max_span_mm", "mm"),
    "footing_diameter_in": ("footing_diameter_mm", "mm"),
}

# §1.4's four TaskCodes, spelling confirmed in planning-asks.md:453. The task is
# what the parameter DECIDES, and it is the axis the source policy ranks on --
# an installation manual is rank 4 and level-2-only for a structural parameter,
# admissible without reservation for a component dimension. Getting this wrong
# does not produce a wrong number; it produces a right number that is admissible
# where it should not be.
TASK_OF = {
    "footing_depth_mm": "structural_parameter",
    "max_span_mm": "structural_parameter",
    "footing_diameter_mm": "structural_parameter",
}

# Obligation 13. A published condition key declares WHEN it can be bound.
#
#   site   the project's location settles it before any geometry exists
#   param  another table's value settles it (max_rack on slope_method)
#   run · post · bay · panel   a narrower object settles it, but the key still
#          expands up front over a closed enumeration; only SELECTION moves later
#
# `fence_height` is `bay` and not `site` or `run` deliberately: audit/06 measured
# that height in the consumer's engine is a `height_intent` interval payload that
# varies *along* a single run -- "6 ft for twelve metres and 4 ft for the last
# four" -- so it is not constant at `run`, and the bay is the first object where
# it resolves to one value. `panel` is the arguable alternative; `bay` is chosen
# because a 16 ft rail threaded through an intermediate post belongs to a run of
# bays and to no single panel (obligation 12's own example).
#
# A key not in this table is NOT published. Dropping the key instead would widen
# the row's applicability silently, which is the failure mode obligation 13
# exists to prevent.
CONDITION_SCOPE = {
    "exposure_category": "site",
    "hvhz": "site",
    "jurisdiction": "site",
    "code_edition": "site",
    "frost_depth_mm": "site",
    "wind_speed_mph": "site",
    "fence_height": "bay",
    "post_role": "post",
    "slope_method": "param",
}

# The domain values a dimension is DECLARED over, where the regulatory universe
# fixes them rather than the page. Exposure B/C/D and the two HVHZ states exist
# whether or not a given table prints a row for them, and that is exactly why
# `domain` earns its place (rationale.md §2): "whether an HVHZ site at Exposure D
# is covered is not answerable from the list of rows alone". A dimension absent
# here is enumerated from the values the rows actually state, and is `measured`.
DECLARED_DOMAIN = {
    "exposure_category": ["B", "C", "D"],
    "hvhz": [False, True],
}

# Dimensions whose stated value is an applicability BRACKET -- a claim about
# where the approval reaches -- rather than a lookup key. `hvhz` is the only one
# in this store: `promote_tables` recovers it from the merged annotation column
# spanning a group of rows, and *NON HVHZ* beside a row means the approval does
# not extend into the high-velocity hurricane zone. See `_excluding_row` for why
# the distinction changes what a gap says.
BRACKET_DIMENSIONS = ("hvhz",)

# facts.review_status -> curation_level, §1.1's Provenance.
#
# Obligation 6: "nothing reaches level 2 without a person having compared it to
# the source image". `accepted` and `corrected` are written only by
# `reviews.submit_review`, which refuses a review whose echoed `crop_sha256` does
# not match the crop that was served -- so they, and only they, mean a person
# looked. `cross_family_verified` is two agents agreeing: real evidence, no
# human, level 1. Anything else is level 0.
CURATION_LEVEL = {
    "accepted": 2, "corrected": 2, "reviewed": 2,
    "cross_family_verified": 1,
}

# Exact integer multipliers into thousandths of a millimetre. No float is
# constructed anywhere on this path: `canonical.canonical_bytes` refuses one, and
# the reason §1.1 gives is precisely that a float would be rounded somewhere
# undeclared. 25.4 mm/inch * 1000 = 25400 exactly.
MILLI_PER_UNIT = {"in": 25400, "ft": 304800, "cm": 10000, "mm": 1000}
_UNIT_ALIASES = {
    "in": "in", "inch": "in", "inches": "in", '"': "in",
    "ft": "ft", "foot": "ft", "feet": "ft", "'": "ft",
    "cm": "cm", "centimeter": "cm", "centimetre": "cm",
    "mm": "mm", "millimeter": "mm", "millimetre": "mm",
}

# A measurement's magnitude: `36`, `36.5`, `96 1/8`, `7/8`. Parsed to a Fraction
# so the conversion is exact. The fraction alternative comes FIRST because
# alternation is ordered at each position: with the plain number first, `7/8"`
# would match `7` and publish an inch where 22.225 mm was meant.
_MEASURE = re.compile(
    r"(?:(?P<whole>\d+)\s+)?(?P<num>\d+)\s*/\s*(?P<den>\d+)"
    r"|(?P<plain>\d+(?:\.\d+)?)")
_EXPOSURE = re.compile(r"\b([BCD])\b", re.IGNORECASE)
_HVHZ_BOTH = re.compile(r"hvhz\s+and\s+non[\s-]?hvhz", re.IGNORECASE)
_NON_HVHZ_ONLY = re.compile(r"non[\s-]?hvhz", re.IGNORECASE)

FACT_QUERY = """
SELECT f.fact_id, f.document_id, f.page_no, f.element_id, f.fact_type,
       f.value_original, f.unit_original, f.unit_normalized, f.value_alternates,
       f.conditions, f.condition_basis, f.condition_basis_note,
       f.review_status, f.from_candidate_id,
       -- G44 at the publishing layer. `curation_level` is set from
       -- `review_status`, so a fact a person CORRECTED publishes at level 2 --
       -- "a person compared this to the source image" -- and without these two
       -- columns it would publish the machine's value under that stamp. That
       -- is the inversion obligation 6 forbids, arriving through the one
       -- section of a snapshot that carries numbers. Every read of a value
       -- below goes through `reviews.effective_fact_value`.
       f.reviewed_value, f.reviewed_value_normalized,
       d.doc_type, d.manufacturer, d.product_family, d.title,
       d.version_status, d.issue_date, d.expiration_date
  FROM facts f
  JOIN documents d ON d.document_id = f.document_id
 WHERE f.from_candidate_id IS NOT NULL
   AND f.review_status <> 'rejected'
{tenant_clause}
 ORDER BY f.fact_id
"""


def _fact_query(tenant: str | None) -> tuple:
    """(sql, params). Obligation 7: scope the SELECTION, not just the mint.

    `source_ref` refuses to mint a citation into another tenant's document, so
    an unscoped scan here would abort a whole build with a `TenantLeak` the
    first time a tenant upload produced a promoted fact -- a leak turned into an
    outage. Scoping means the value is simply not in this tenant's snapshot,
    which is what obligation 7 asks for. `None` is the internal caller that has
    no tenant in hand (`_default_source_ref`'s standalone path) and sees
    everything the store holds.
    """
    if tenant is None:
        return FACT_QUERY.format(tenant_clause=""), ()
    return (FACT_QUERY.format(tenant_clause=f"   AND {visible_sql('d')}"),
            (tenant,))


# --------------------------------------------------------------------------
# quantities

def _round_half_up(f: Fraction) -> int:
    """Round a Fraction to an int, away from zero at the half.

    §1.1 is BINDING that conversion "rounds -- it does not truncate", and says
    why: a floor of one millimetre passes through `n = ceil(run / max_span)` and
    buys an extra post, footing and pour on a 9.8 m run. `round()` would be
    banker's rounding, which turns .5 into the *nearer even* -- a different
    answer for 2463.5 than the clause asks for. Integer arithmetic only.
    """
    n, d = f.numerator, f.denominator
    if n >= 0:
        return (2 * n + d) // (2 * d)
    return -((-2 * n + d) // (2 * d))


def _unit_of(row) -> str | None:
    """The unit a fact is stated in, from the column or from the lexeme."""
    for candidate in (row["unit_normalized"], row["unit_original"]):
        if candidate and str(candidate).strip().lower() in _UNIT_ALIASES:
            return _UNIT_ALIASES[str(candidate).strip().lower()]
    text = effective_fact_value(row) or ""
    if '"' in text:
        return "in"
    if "'" in text:
        return "ft"
    for token, unit in (("mm", "mm"), ("cm", "cm")):
        if re.search(rf"\d\s*{token}\b", text, re.IGNORECASE):
            return unit
    return None


def _magnitude(text: str | None) -> Fraction | None:
    """`96 1/8"` -> Fraction(769, 8). Exact, and None when nothing parses."""
    if not text:
        return None
    m = _MEASURE.search(text)
    if not m:
        return None
    if m.group("plain") is not None:
        return Fraction(m.group("plain"))
    den = int(m.group("den"))
    if den == 0:
        return None
    value = Fraction(int(m.group("num")), den)
    if m.group("whole"):
        value += int(m.group("whole"))
    return value


def _value_raw(row) -> list[str]:
    """Every verbatim source lexeme, in printed order.

    §1.1 is BINDING that `value_raw` is a LIST, because sources state two units
    themselves and contradict themselves doing it. `facts.value_alternates`
    holds the second pair where a document printed one; the primary lexeme stays
    first. Never sorted -- printed order is the thing the field preserves.
    """
    # The person's value leads where there is one: `value_raw` is what the
    # published `Quantity` was read from, and publishing the machine's lexeme
    # beside a corrected magnitude would show a reader two different numbers
    # and call one of them the source.
    out = [(effective_fact_value(row) or "").strip()]
    try:
        alternates = json.loads(row["value_alternates"] or "[]")
    except (TypeError, ValueError):
        alternates = []
    for alt in alternates if isinstance(alternates, list) else []:
        lexeme = (alt or {}).get("value_original") if isinstance(alt, dict) else None
        if lexeme and lexeme.strip() not in out:
            out.append(lexeme.strip())
    return [x for x in out if x]


def quantity(row) -> dict | None:
    """A `Quantity` in thousandths of a millimetre, or None if it will not parse.

    Integers only. §1.1: "No floating-point number crosses this boundary in
    either direction" -- and `facts.value_normalized` is a REAL column, so it is
    deliberately not the input here. The lexeme is.
    """
    unit = _unit_of(row)
    magnitude = _magnitude(effective_fact_value(row))
    if unit is None or magnitude is None:
        return None
    return {"amount_milli": _round_half_up(magnitude * MILLI_PER_UNIT[unit]),
            "unit": "mm",
            "value_raw": _value_raw(row)}


# --------------------------------------------------------------------------
# conditions

def _publish_basis(basis: str | None) -> str:
    """`condition_basis` in the contract's closed set: stated | assumed.

    The store carries a third value, `unexamined` -- nobody looked, the regex
    matched a number and never asked what scoped it. `store.py` records that it
    "publishes as `assumed`", and keeping the distinction internal is the point:
    the store does not assert an inference it never made, and the boundary does
    not gain a third word it has no clause for.
    """
    return "stated" if basis == "stated" else "assumed"


def _translate_conditions(raw: dict) -> tuple[dict, set, tuple | None]:
    """Store conditions -> published conditions, plus the dimensions in play.

    Returns `(conditions, dimensions, problem)`. `dimensions` can be wider than
    `conditions`: a row annotated *"HVHZ and NON HVHZ"* omits the `hvhz` key --
    because a key it does not mention matches every value of that dimension --
    while still putting `hvhz` in the table's domain. Without that, a table whose
    rows all cover both HVHZ states would publish a domain with no HVHZ axis and
    could never report `(B, hvhz=true)` as uncovered at all.

    `problem` is non-None when the row cannot be placed in the domain honestly.
    """
    conditions: dict = {}
    dimensions: set = set()
    for key, value in sorted(raw.items()):
        if key == "hvhz_applicability":
            # The applicability bracket `promote_tables` recovered from the
            # merged annotation column. It is not itself a condition dimension:
            # it says which values of `hvhz` the row's approval extends to.
            dimensions.add("hvhz")
            text = str(value or "")
            if _HVHZ_BOTH.search(text):
                continue                     # both states: key omitted, matches all
            if _NON_HVHZ_ONLY.search(text):
                conditions["hvhz"] = False
                continue
            if text.strip().lower() == "unresolved":
                return {}, dimensions, ("unresolved_applicability", text)
            return {}, dimensions, ("unrecognised_condition_value", f"{key}={text}")
        if key == "hvhz":
            dimensions.add("hvhz")
            if isinstance(value, bool):
                conditions["hvhz"] = value
            elif str(value).strip().lower() in ("true", "1", "yes"):
                conditions["hvhz"] = True
            elif str(value).strip().lower() in ("false", "0", "no"):
                conditions["hvhz"] = False
            else:
                return {}, dimensions, ("unrecognised_condition_value",
                                        f"hvhz={value}")
            continue
        if key == "exposure_category":
            dimensions.add(key)
            m = _EXPOSURE.search(str(value or ""))
            if not m:
                return {}, dimensions, ("unrecognised_condition_value",
                                        f"{key}={value}")
            conditions[key] = m.group(1).upper()
            continue
        if key not in CONDITION_SCOPE:
            # Obligation 13 is BINDING: a published condition key declares its
            # scope. We cannot declare one we have not decided, and dropping the
            # key would publish the row as applying more widely than it does.
            return {}, dimensions, ("condition_scope_undeclared", key)
        dimensions.add(key)
        conditions[key] = " ".join(str(value).split())
    return conditions, dimensions, None


def _points(domain: dict) -> list[dict]:
    """Every point in the domain, in a deterministic order.

    A domain with no dimensions has exactly one point -- the empty one. That is
    not a degenerate case to special-case away: it is the shape of a table whose
    rows are all unconditioned fallbacks, and `uncovered` is correctly empty
    beside it.
    """
    out: list[dict] = [{}]
    for dim in sorted(domain):
        out = [dict(point, **{dim: value}) for point in out for value in domain[dim]]
    return sorted(out, key=canonical_bytes)


def _matches(conditions: dict, point: dict) -> bool:
    """A row matches a point when every key it STATES agrees with it."""
    return all(point.get(k) == v for k, v in conditions.items())


def _is_fallback(row: dict) -> bool:
    """Obligation 15's unconditioned row.

    `condition_basis: stated` with empty conditions means the document gave no
    conditions -- 66% of the structural facts in the class §1.4 admits are this
    shape. Such a row "never asserts anything about the points it lands on", so
    it is excluded from the `unique` overlap check; Planning's own review
    (knowledge-asks.md §1.5) confirms it nevertheless covers the whole domain,
    so `uncovered: []` beside it is right.
    """
    return not row["conditions"] and row["condition_basis"] == "stated"


def _windows_overlap(a: dict, b: dict) -> bool:
    """Do two rows' validity windows intersect? Open ends are unbounded.

    Defect 6 of the unblocking plan: the `unique` check must exclude rows whose
    windows are DISJOINT. Two values at one point under an approval that expired
    in 2019 and its replacement issued in 2020 are a succession, not a
    contradiction -- and §1.3 carries expiry as fields precisely so that a time
    dimension does not have to be enumerated into the domain.
    """
    a_from, a_until = a.get("valid_from"), a.get("valid_until")
    b_from, b_until = b.get("valid_from"), b.get("valid_until")
    # ISO-8601 dates compare correctly as strings, which is why they are stored
    # that way; a null bound is an open one and can never separate the windows.
    if a_until is not None and b_from is not None and a_until < b_from:
        return False
    if b_until is not None and a_from is not None and b_until < a_from:
        return False
    return True


# --------------------------------------------------------------------------
# provenance

def _source_class(doc_type: str | None) -> str:
    """The 19-value `doc_type` vocabulary collapsed onto §1.4's eight classes.

    Imported lazily and on purpose. `snapshot.py` owns that mapping and a test
    asserts every `doc_type` in the store appears in it; duplicating it here
    would create a second answer that could drift, and importing it at module
    level would make the wiring `snapshot -> parameters` a cycle.
    """
    from .snapshot import SOURCE_CLASS
    return SOURCE_CLASS.get(doc_type or "unspecified", "marketing")


def _default_source_ref(conn: sqlite3.Connection):
    """Mint a `SourceRef` from an element id, the way `snapshot.py` does.

    The integrator should pass `SnapshotBuilder.source_ref` instead, which
    registers the document as a side effect and so makes §1.2.1's closure rule
    structural rather than checked. This fallback exists so the module is usable
    -- and testable -- on its own; it mints the identical id, because `ref_id` is
    a pure function of what it points at and has exactly one owner.
    """
    cache: dict[str, dict] = {}

    def mint(element_id: str) -> dict:
        if element_id in cache:
            return cache[element_id]
        # Join on version_id, not document_id: an element belongs to exactly one
        # version, and joining by document fans out once a document has two.
        # snapshot.source_ref and refs.build_index make the same join, and all
        # three must agree or the minting side and the index disagree about
        # which version an element belongs to.
        row = conn.execute("""
            SELECT e.page_no, e.bbox, v.sha256
              FROM elements e
              JOIN document_versions v ON v.version_id = e.version_id
             WHERE e.element_id = ?""", (element_id,)).fetchone()
        if row is None:
            # Never mint a ref we cannot back: a dangling `belongs_to` carries
            # zero admissibility bits into a pinned snapshot, which is the exact
            # defect §1.2.1's closure rule was added to close.
            raise KeyError(f"no such element: {element_id}")
        ref = {"id": ref_id(row["sha256"], row["page_no"], row["bbox"]),
               "belongs_to": row["sha256"]}
        cache[element_id] = ref
        return ref

    return mint


def _default_scope(row) -> dict:
    """Which product or assembly a table applies to, as an `EntityRef`.

    §3.8 says the scope is a `Part` or a `FenceModel`. This store holds neither
    -- invariant 10 is that structure is authored and no reader produces a
    `PanelSpec` -- so where the document names a product family we publish a
    `fence_model` ref in the `mfr/` namespace the contract reserves for
    manufacturer-derived, tenant-agnostic ids (§2.1), and where it does not we
    publish the document and raise a gap rather than invent an entity.

    `tenant` is null because this knowledge belongs to no tenant.
    """
    if row["manufacturer"] and row["product_family"]:
        name = f"{row['manufacturer']} {row['product_family']}".lower()
        slug = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
        return {"kind": "fence_model", "id": f"mfr/{slug}", "tenant": None}
    return {"kind": "source_document", "id": row["document_id"], "tenant": None}


# --------------------------------------------------------------------------
# gaps

class _Gaps:
    """A gap collector in `snapshot.Gap`'s field order, deduplicated.

    Deliberately NOT `snapshot.Gap`: importing it at module level would make the
    wiring a cycle, and the integrator can pass these straight through
    `SnapshotBuilder.gap(**g)` or extend the list. One difference worth knowing:
    `snapshot` keys its dedupe on `kind:subject` alone, while these ids fold in
    `because.code`, so two different findings about one parameter both survive.
    """

    def __init__(self):
        self._by_id: dict[str, dict] = {}

    def add(self, *, kind, subject, code, would_close, closes_by,
            severity="warns_line", params=None, cites=None, on=None) -> None:
        key = f"{kind}:{subject}:{code}"
        gap_id = hashlib.sha256(key.encode()).hexdigest()[:16]
        if gap_id in self._by_id:
            return
        self._by_id[gap_id] = {
            "id": gap_id, "kind": kind, "subject": subject,
            "because": {"code": code, "params": params or {}},
            "cites": sorted(cites or [], key=canonical_bytes),
            "would_close": would_close, "closes_by": closes_by,
            "severity": severity, "on": on}

    def list(self) -> list[dict]:
        return sorted(self._by_id.values(), key=lambda g: g["id"])


def _describe(point: dict) -> str:
    """A domain point as a curator reads it: `exposure C, non-HVHZ`."""
    parts = []
    for dim in sorted(point):
        value = point[dim]
        if dim == "exposure_category":
            parts.append(f"exposure {value}")
        elif dim == "hvhz":
            parts.append("HVHZ" if value else "non-HVHZ")
        else:
            parts.append(f"{dim.replace('_', ' ')} {value}")
    return ", ".join(parts) or "any conditions"


def _subject(parameter: str, scope: dict, point: dict | None = None) -> str:
    """A `ParamRef`, flattened to a string.

    §1.2.1 types `Gap.subject` as `EntityRef | SlotRef | ParamRef`, but
    `snapshot.Gap.subject` is a string and its dedupe key interpolates it, so a
    dict there would break both. The string is addressable and round-trippable,
    which is what "addressably" in §1.2.1 asks for.
    """
    base = f"param:{parameter}@{scope['kind']}/{scope['id']}"
    return base if point is None else f"{base}#{_describe(point)}"


# --------------------------------------------------------------------------
# the builder

def build_parameter_tables(conn: sqlite3.Connection, *, scope_resolver=None,
                           source_ref=None,
                           tenant: str | None = None) -> tuple[list[dict], list[dict]]:
    """Promoted facts -> (`[ParameterTable]`, `[Gap]`), both deterministic.

    Only facts with `from_candidate_id IS NOT NULL` are considered: those are
    the cells promoted out of a reviewed table reading, carrying the conditions
    of the row they sat in. A regex-extracted fact has no row and no bracket,
    and publishing one into a declared domain would assert conditions the source
    never stated (rationale.md §1's G16 at scale).

    `scope_resolver(fact_row) -> EntityRef` overrides how a table's `scope` is
    decided; `source_ref(element_id) -> {id, belongs_to}` overrides how citations
    are minted -- pass `SnapshotBuilder.source_ref` so §1.2.1's closure rule
    holds by construction.
    """
    scope_of = scope_resolver or _default_scope
    mint = source_ref or _default_source_ref(conn)
    gaps = _Gaps()
    groups: dict[bytes, dict] = {}

    sql, params = _fact_query(tenant)
    for fact in conn.execute(sql, params):
        named = PARAMETER_OF.get(fact["fact_type"])
        if named is None:
            gaps.add(kind="missing_value",
                     subject=f"fact_type:{fact['fact_type']}",
                     code="parameter_name_unmapped",
                     params={"fact_type": fact["fact_type"]},
                     would_close=f"decide what published parameter "
                                 f"{fact['fact_type']!r} is, and in which UnitCode "
                                 f"it crosses; until then its values are held back "
                                 f"rather than published under a guessed name",
                     closes_by="knowledge", severity="informational")
            continue
        parameter, unit = named
        scope = scope_of(fact)
        key = canonical_bytes([parameter, scope])
        group = groups.setdefault(key, {
            "parameter": parameter, "unit": unit, "scope": scope,
            "rows": [], "dimensions": set(), "observed": {}})

        cites = [mint(fact["element_id"])]
        conditions, dimensions, problem = _translate_conditions(
            json.loads(fact["conditions"] or "{}"))
        group["dimensions"] |= dimensions

        if problem is not None:
            code, detail = problem
            if code == "unresolved_applicability":
                # §1.2.1: "33.3% of this platform's human-gated facts carry a
                # note that readers did not agree on the applicability bracket --
                # the value is certain and the conditions are not -- and none of
                # the other seven kinds fits that honestly." Publishing the row
                # as covering both HVHZ states would assert an approval regime
                # nobody read off the page.
                gaps.add(kind="disputed", on="conditions",
                         subject=f"fact:{fact['fact_id']}",
                         code="applicability_bracket_unresolved",
                         params={"parameter": parameter,
                                 "page_no": fact["page_no"],
                                 "value_raw": (effective_fact_value(fact) or "").strip()},
                         cites=cites,
                         would_close=f"readers did not independently agree whether "
                                     f"{(fact['value_original'] or '').strip()} on "
                                     f"page {fact['page_no']} of "
                                     f"{fact['title'] or fact['document_id']} applies "
                                     f"in the HVHZ; a person should open the crop and "
                                     f"record the bracket",
                         closes_by="knowledge")
            else:
                gaps.add(kind="missing_value", subject=f"fact:{fact['fact_id']}",
                         code=code, params={"parameter": parameter,
                                            "detail": detail,
                                            "page_no": fact["page_no"]},
                         cites=cites,
                         would_close=f"the condition {detail!r} on page "
                                     f"{fact['page_no']} of "
                                     f"{fact['title'] or fact['document_id']} has no "
                                     f"declared scope or no recognised value, so the "
                                     f"row cannot be placed in a domain; declare it "
                                     f"in parameters.CONDITION_SCOPE or correct the "
                                     f"reading",
                         closes_by="knowledge")
            continue

        value = quantity(fact)
        if value is None:
            gaps.add(kind="unquantified", subject=f"fact:{fact['fact_id']}",
                     code="value_not_a_quantity",
                     params={"parameter": parameter, "page_no": fact["page_no"],
                             "value_raw": (effective_fact_value(fact) or "").strip()},
                     cites=cites,
                     would_close=f"{(fact['value_original'] or '').strip()!r} on page "
                                 f"{fact['page_no']} of "
                                 f"{fact['title'] or fact['document_id']} carries no "
                                 f"parseable magnitude or no convertible unit; a "
                                 f"person should read the crop and record the number "
                                 f"with its unit",
                     closes_by="knowledge")
            continue

        if fact["doc_type"] in (None, "unspecified"):
            # Mirrors snapshot.py: an unclassified document publishes at the
            # weakest class, so it cannot make anything wrongly admissible, and
            # it publishes a gap because a guess presented as a classification
            # is what obligation 6 forbids.
            gaps.add(kind="missing_value", subject=f"document:{fact['document_id']}",
                     code="source_class_unclassified",
                     params={"doc_type": fact["doc_type"],
                             "document_id": fact["document_id"]},
                     cites=cites,
                     would_close=f"classify the source class of "
                                 f"{fact['title'] or fact['document_id']}; its "
                                 f"parameter rows publish at the weakest class until "
                                 f"someone does",
                     closes_by="knowledge", severity="informational")

        for dim, dim_value in conditions.items():
            group["observed"].setdefault(dim, set()).add(dim_value)

        group["rows"].append({
            "conditions": conditions,
            "condition_basis": _publish_basis(fact["condition_basis"]),
            "value": value,
            "provenance": {
                "cites": cites,
                "source_class": _source_class(fact["doc_type"]),
                "curation_level": CURATION_LEVEL.get(fact["review_status"], 0),
                # §1.4 BINDING: `version_status` is a policy axis, and `unknown`
                # is a real value ranking below `active`, never coerced to it.
                "version_status": fact["version_status"] or "unknown",
            },
            # Expiry is a property of the authority, not of the site (§1.3), and
            # the nearest addressable authority this store holds is the document
            # itself -- there is no issuer field. `belongs_to` joins it to the
            # `SourceDoc` in the snapshot, which carries the same dates.
            "valid_from": fact["issue_date"],
            "valid_until": fact["expiration_date"],
            "authority": cites[0]["belongs_to"],
        })

    tables = []
    for key in sorted(groups):
        table = _finish(groups[key], gaps)
        if table is not None:
            tables.append(table)
    return tables, gaps.list()


def _merge(rows: list[dict]) -> list[dict]:
    """Collapse rows identical in everything but their citations.

    Fourteen groups of files in this corpus are byte-identical under different
    manufacturers, and five documents print the same footing table. The same
    value, at the same point, under the same authority and the same provenance
    is ONE row with several citations -- exactly as `snapshot.warnings` treats
    the same warning text printed in several documents. Anything that differs in
    provenance stays a separate row, because §1.4 makes `source_class` on a row
    load-bearing and a merge would have to pick one.
    """
    merged: dict[bytes, dict] = {}
    for row in rows:
        identity = canonical_bytes({k: v for k, v in row.items()
                                    if k != "provenance"}
                                   | {"provenance": {k: v for k, v
                                                     in row["provenance"].items()
                                                     if k != "cites"}})
        if identity in merged:
            held = merged[identity]["provenance"]["cites"]
            known = {canonical_bytes(c) for c in held}
            for cite in row["provenance"]["cites"]:
                if canonical_bytes(cite) not in known:
                    held.append(cite)
            continue
        merged[identity] = row
    out = list(merged.values())
    for row in out:
        row["provenance"]["cites"].sort(key=canonical_bytes)
    return sorted(out, key=canonical_bytes)


def _collisions(rows: list[dict], points: list[dict]) -> list[tuple]:
    """Points where `hit_policy: unique` is genuinely violated.

    Returns `[(point, [rows])]`. Three exclusions, each of them load-bearing:

    * **fallback rows** -- obligation 15 excludes an unconditioned `stated` row
      from the overlap check by name, or the 239 of them in this corpus become
      publish errors instead of honest gaps;
    * **disjoint validity windows** -- a succession, not a conflict (defect 6);
    * **equal values** -- corroboration. Two sources stating 36" at exposure C
      give the same answer in any evaluation order, which is the property
      rationale.md §2 says the check protects, and §1.4 requires both rows to be
      published anyway so a decision graph can say which one a policy rejected.
    """
    found = []
    conditioned = [r for r in rows if not _is_fallback(r)]
    for point in points:
        here = [r for r in conditioned if _matches(r["conditions"], point)]
        clashing = []
        for i, a in enumerate(here):
            for b in here[i + 1:]:
                if a["value"] == b["value"] or not _windows_overlap(a, b):
                    continue
                clashing.extend([a, b])
        if clashing:
            unique_rows = []
            for row in clashing:
                if row not in unique_rows:
                    unique_rows.append(row)
            found.append((point, unique_rows))
    return found


def _finish(group: dict, gaps: _Gaps) -> dict | None:
    """One group of rows -> one `ParameterTable`, or None where it is withheld."""
    parameter, scope = group["parameter"], group["scope"]
    rows = _merge(group["rows"])
    if not rows:
        return None

    # The domain. A dimension the regulatory universe fixes is DECLARED over
    # that universe; anything else is enumerated from what the rows state and is
    # MEASURED. §1.3: "uncovered against a declared domain means *we may not know
    # this table's real extent*; against a measured one it means *this table
    # really does not cover that point*."
    domain, declared = {}, False
    for dim in sorted(group["dimensions"]):
        if dim in DECLARED_DOMAIN:
            domain[dim] = list(DECLARED_DOMAIN[dim])
            declared = True
        elif group["observed"].get(dim):
            domain[dim] = sorted(group["observed"][dim], key=canonical_bytes)
    points = _points(domain)

    if scope["kind"] == "source_document":
        gaps.add(kind="missing_value", subject=_subject(parameter, scope),
                 code="parameter_scope_is_a_document",
                 params={"parameter": parameter, "document_id": scope["id"]},
                 would_close=f"name the product or assembly {parameter} applies to; "
                             f"the source document does not identify a product "
                             f"family, so the table is scoped to the document and "
                             f"Planning cannot attach it to a model",
                 closes_by="knowledge", severity="informational")

    collisions = _collisions(rows, points)
    if collisions:
        # C5, and the whole table goes. See the module docstring for why the
        # three alternatives are worse; the short form is that a paired
        # `value_type` needs an amendment that has not landed, and every way of
        # publishing this table without one either breaks a BINDING clause or
        # silently discards the cheaper compliant design point.
        for point, clashing in collisions:
            lexemes = sorted({lexeme for r in clashing
                              for lexeme in r["value"]["value_raw"]})
            gaps.add(kind="unmodellable_entity",
                     subject=_subject(parameter, scope, point),
                     code="paired_design_point_unmodellable",
                     params={"parameter": parameter,
                             "scope_id": scope["id"],
                             "point": point,
                             "amount_milli": sorted(
                                 r["value"]["amount_milli"] for r in clashing),
                             "value_raw": lexemes},
                     cites=[c for r in clashing for c in r["provenance"]["cites"]],
                     would_close=f"{' and '.join(lexemes)} are both valid for "
                                 f"{parameter} at {_describe(point)} and no condition "
                                 f"dimension separates them -- they are paired design "
                                 f"points, a deeper footing buying a wider span. "
                                 f"Amendment C5 (a paired value_type) would let this "
                                 f"table publish; until it lands the table is "
                                 f"withheld, because publishing it under "
                                 f"hit_policy: unique would break a BINDING clause "
                                 f"and any collect/priority policy would silently "
                                 f"discard the cheaper compliant option",
                     closes_by="planning")
        return None

    covered = any(_is_fallback(r) for r in rows)
    uncovered = [] if covered else [
        p for p in points if not any(_matches(r["conditions"], p) for r in rows)]

    for point in uncovered:
        excluded = _excluding_row(rows, point)
        if excluded is not None:
            # Not a hole in what we read -- a hole in what the source approves.
            # The Bufftech footing table brackets both exposure B rows NON HVHZ,
            # so `(B, HVHZ)` is *not approved*, and answering it from the B rows
            # would cite a Miami-Dade NOA for a job its own approval excludes
            # (state-and-gaps.md G16, measured as critical). §1.3 gives no field
            # for a refusal, so it stays in `uncovered` -- the BINDING clause
            # says every point no row covers is listed there -- and the gap's
            # `because.code` carries the distinction Planning renders on.
            gaps.add(kind="uncovered_condition",
                     subject=_subject(parameter, scope, point),
                     code="condition_point_excluded_by_source",
                     params={"parameter": parameter, "scope_id": scope["id"],
                             "point": point},
                     cites=list(excluded["provenance"]["cites"]),
                     would_close=f"the source states {parameter} at "
                                 f"{_describe(excluded['conditions'])} and brackets it "
                                 f"there, so {_describe(point)} is not approved rather "
                                 f"than unread; an approval covering "
                                 f"{_describe(point)} would close this",
                     closes_by="knowledge")
        else:
            gaps.add(kind="uncovered_condition",
                     subject=_subject(parameter, scope, point),
                     code="condition_point_uncovered",
                     params={"parameter": parameter, "scope_id": scope["id"],
                             "point": point},
                     would_close=f"a {parameter} row for {_describe(point)} on "
                                 f"{scope['id']}; no source in the store states one, "
                                 f"and Planning treats the point as a warned "
                                 f"unfulfilled requirement rather than guessing",
                     closes_by="knowledge")

    return {
        "parameter": parameter,
        "scope": scope,
        "task": TASK_OF[parameter],
        # Every table this module publishes claims `unique`: one value per point.
        # It is a claim that has been CHECKED -- `_collisions` ran and found
        # none. A table that could not honour it is withheld above rather than
        # relabelled with a policy that hides the conflict.
        "hit_policy": "unique",
        "value_type": f"quantity({group['unit']})",
        "domain": domain,
        "domain_basis": "declared" if declared else "measured",
        # Obligation 13, BINDING. One entry per dimension in the domain: when
        # can Planning bind this key?
        "condition_scope": {dim: CONDITION_SCOPE[dim] for dim in sorted(domain)},
        "rows": rows,
        "uncovered": uncovered,
    }


def _excluding_row(rows: list[dict], point: dict) -> dict | None:
    """A row whose stated applicability BRACKET scopes this point out.

    Only `hvhz` counts, and the distinction is the whole point of the function.
    A row reading *36" at exposure C* says nothing whatever about exposure B --
    that is an ordinary hole in what anyone wrote down. A row reading *30" at
    exposure B, NON HVHZ* does say something about `(B, HVHZ)`: the annotation
    `promote_tables` recovered from the merged bracket column is a statement of
    what the approval extends to, so the point is **not approved** rather than
    unread. Answering it from the B row would cite a Miami-Dade NOA for a job
    its own approval excludes -- state-and-gaps.md G16, measured as critical.

    Only a `stated` row counts. An assumed condition is our inference, and
    inferring an exclusion from it would manufacture a refusal the document
    never made.
    """
    for row in rows:
        if row["condition_basis"] != "stated":
            continue
        conditions = row["conditions"]
        if not any(dim in conditions and conditions[dim] != point.get(dim)
                   for dim in BRACKET_DIMENSIONS):
            continue
        if all(v == point.get(k) for k, v in conditions.items()
               if k not in BRACKET_DIMENSIONS):
            return row
    return None
