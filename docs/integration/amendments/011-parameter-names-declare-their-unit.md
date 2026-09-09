# Amendment 011 — `max_rack` is the one published parameter name that does not say its unit

```text
Obligation   §1.3, the `ParameterTable.parameter` enum. No obligation number is
             edited and no BINDING clause changes; one member of an open enum
             is renamed and the naming rule the other members already follow is
             written down.
Trigger      D — defect. The contract names four parameters and three of them
             carry the unit their `value_type` declares; the fourth does not,
             and nothing in §1.3 says which convention is the rule. A consumer
             cannot tell whether `max_rack` is an angle, a token or a count
             without reading a different field.
Filed by     Knowledge, 2026-09-09
Status       FILED. Governs nothing until ratified (AMENDING.md §3 step 2).
             Not blocking, and not asking for an out-of-turn cut: `max_rack`
             publishes nothing on either side. Batch it behind 009 and 010,
             which are older and also owed.
Promotes     `docs/naming.md` §2, open defect B-4 — *"`max_rack` is
             `quantity(deg_milli)` with no suffix, in ratified `contract.md`;
             cheap now (publishes nothing), expensive once it does."* That
             document is this platform's internals and binds nothing here; this
             is the half of it that has to be negotiated rather than decided.
```

## Why this is filed rather than left in the waiting room

Because the cost is zero **today** and rises the first time a rackable product
is curated, and because the thing that makes it cheap — nothing published —
is exactly the thing that makes it easy to forget. `CANDIDATES.md` is the
right home for an item whose condition is a date or an event; this one's
condition is "before the first `max_rack` table", which is an event nobody
will notice until it has happened. `docs/naming.md` §0's whole argument is
that a name nothing checks slowly stops meaning what a reader assumes, and a
name in a frozen contract is the strongest case of that.

**It is deliberately small.** It renames one enum member and states a rule the
contract's own published names already obey. It does not touch a BINDING
clause, a shape, or a published byte.

---

## The gap

`contract.md:292` declares the parameter enum:

```text
  parameter     "max_span_mm" | "max_rack" | "slope_method" | …
```

and `contract.md:296` declares the type:

```text
  value_type    quantity(<UnitCode>) | token(<closed set>)
                | paired(<parameter>:<UnitCode>, <parameter>:<UnitCode>)   declared ONCE
```

Three of the four names in that enum are self-describing and one is not:

| parameter | `value_type` | unit in the name? |
|---|---|---|
| `max_span_mm` | `quantity(mm)` | yes |
| `footing_depth_mm` (published, not in the enum's short list) | `quantity(mm)` | yes |
| `footing_diameter_mm` (published) | `quantity(mm)` | yes |
| `footing_schedule` (published, amendment 006) | `paired(footing_depth_mm:mm, max_span_mm:mm)` | no — and correctly not, because each member names its own |
| `slope_method` | `token(<closed set>)` | no — and correctly not, because a token has no unit |
| **`max_rack`** | **`quantity(deg_milli)`** | **no** |

`[measured]` 2026-09-09, over all 25 non-tombstoned stored snapshots: 225
published `ParameterTable`s, across exactly three parameter names —
`footing_depth_mm` (50), `footing_diameter_mm` (50) and `footing_schedule`
(125). **`max_rack` tables published: 0.** The rule holds without exception on
every name that has ever crossed, and the only name that breaks it is the only
one that has never crossed.

That is the defect in the trigger-D sense: §1.3 does not say which convention
is the rule, so the enum contains both and a consumer must branch on
`value_type` to learn what a `parameter` name means. The contract refuses that
exact convention everywhere else it appears. `contract.md`'s own reasoning for
naming a `paired` member says so:

> A `paired` member **names its parameter** rather than relying on position:
> `paired(mm, mm)` would distinguish a footing depth from a max span only by
> which slot in the array it occupies, and this contract refuses exactly that
> convention everywhere else — `value_raw` exists so a number cannot mean
> something by implication, and `Quantity` names its own unit rather than
> inferring it.

A parameter whose unit is knowable only from another field is the same
implication, one level up.

---

## Evidence

### E1 · The two conventions are both in the contract, nine lines apart

`contract.md:292` and `contract.md:296`. `max_span_mm` and `max_rack` are
adjacent members of one enum, both `quantity(...)`, and only one of them says
its unit. Neither the enum nor the surrounding prose says which is intended.

### E2 · The published names all follow the suffixed convention

`[measured]` 2026-09-09, `fence_evidence.snapshot_store`, all 25
non-tombstoned snapshots — the table in "The gap" above. Reproduce with:

```bash
python3 - <<'PY'
from fence_evidence.snapshot_store import list_snapshots, get_snapshot
import collections
seen = collections.Counter()
for row in list_snapshots():
    if row["tombstoned"]:
        continue
    for table in get_snapshot(row["snapshot_id"]).get("parameters", []):
        seen[(table["parameter"], table.get("value_type"))] += 1
for key, n in sorted(seen.items()):
    print(n, key)
PY
```

### E3 · Nothing on this side builds a `max_rack` table

`[measured]` 2026-09-09, `grep -rn "max_rack" fence_evidence/ tests/` returns
**one** hit, and it is a comment in `fence_evidence/parameters.py:126`
explaining why `slope_method` has condition scope `param`
(*"another table's value settles it (max_rack on slope_method)"*). There is no
builder, no fact type and no registry row. The rename costs this platform
nothing but the enum member.

The corpus does hold the evidence a `max_rack` table would be built from —
`facts.racking_degrees`, `[measured]` 5 rows, 3 `extracted` and 2 `flagged`,
none reviewed — so this is a parameter that will exist, not one that will not.

---

## Proposed text

### §1.3, the `parameter` enum

```text
  parameter     "max_span_mm" | "max_rack_deg" | "slope_method" | …
```

### §1.3, one added sentence after the `value_type` line

> A `parameter` whose `value_type` is `quantity(<UnitCode>)` **names that unit
> in its own name**, as `max_span_mm` and `footing_depth_mm` do. A `token()`
> parameter carries no unit suffix because it has no unit, and a `paired()`
> parameter carries none because each member names its own. The suffix is the
> unit's short form (`mm`, `deg`, `mph`), not the `UnitCode`'s milli spelling:
> the `UnitCode` says how the integer is scaled, the name says what the
> quantity is.

### Not proposed here, and why

**`max_rack_deg_milli`.** Rejected. The `_milli` in a `UnitCode` is an
encoding decision about the integer — obligation 4's *"integers in thousandths
of the named unit"* — and belongs in `Quantity.unit`, where it already is. Two
places carrying it would make a name that changes if the encoding ever does,
which is the opposite of what a stable published name is for. The published
`_mm` names already read this way: `max_span_mm` is `quantity(mm)`, whose
`amount_milli` is thousandths of a millimetre.

**Renaming anything already published.** Refused outright. `footing_depth_mm`,
`footing_diameter_mm` and `footing_schedule` are **9 distinct tables**, held as
225 rows across the 25 non-tombstoned stored, hashed,
write-once tables. Obligation 1 — *"a snapshot hash resolves to the same bytes
forever"* — is the reason a published name is frozen even when it is wrong,
and none of these three is wrong. This amendment can only reach the name that
has not crossed yet, and that limit is the point rather than a compromise.

**A general rule for every future parameter name.** Not proposed as BINDING.
The sentence above is a naming convention for one field; making it binding
would put a registry addition — a new parameter — through ratification, which
`AMENDING.md` §2's exclusion list exists to prevent.

---

## Cost if this lands

**To Planning:** one string in whatever enumerates parameter names, if
anything does. `[measured]` this platform cannot see a `max_rack` reference on
Planning's side either — it is asked in the disposition below rather than
asserted here.

**To Knowledge:** one comment in `fence_evidence/parameters.py`, and the
`docs/naming.md` §2 B-4 row closes.

**To published data:** nothing. There are no `max_rack` tables.

## In-flight

Nothing. No snapshot on either side carries a `max_rack` table, no fact type
maps to one, and no gold question asks for one. A consumer building against
v1.3 that has hardcoded the string `"max_rack"` in an unreachable branch is
the only breakage available, and this amendment is filed now precisely so that
branch is corrected before it is reachable.

---

## Disposition — Planning & BOM

*Not yet dispositioned.* Three questions, and a no is a legitimate answer to
all three:

1. Do you agree the suffixed convention is the rule, given that every name
   that has crossed follows it?
2. Does anything on your side name `max_rack` today? If it does, say where —
   this platform measured its own side only.
3. Batched behind 009 and 010, or does it wait in `CANDIDATES.md` until a
   `max_rack` table is actually about to be built? Knowledge's view is that
   waiting for the event is what turns cheap into expensive, but the cost of
   waiting is genuinely near zero and this is not worth a cut of its own.
