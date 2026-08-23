# Contract v0.1 — what crosses the boundary

```text
Status:    Proposal. Unreviewed by this team.
Authority: Binding at the boundary only. Items marked BINDING are promises a
           consumer relies on. Everything else is this team's decision.
Change:    Registry additions are NOT breaking changes and need no negotiation.
           Changes to the stable core are negotiated between teams.
```

---

## 1. The stable core

Small, and expected to change rarely.

### 1.1 References and quantities

```text
EntityRef    { kind, id, tenant }         a thing in the world
RoleRef      "role:<namespace>/<name>"    a job a part does in a fence
VersionRef   { object_id, version }
SourceRef    { source_ref_id }            opaque to Planning; resolvable via the API
SnapshotRef  { snapshot_id, spine_version, contract_version }

Quantity     { amount_milli: int, unit: UnitCode }
UnitCode     mm | mm2 | mm3 | each | gram_milli | cent
```

> **BINDING.** No floating-point number crosses this boundary in either direction.
> Quantities are integers in thousandths of the named unit. Where a value came from a
> document, the verbatim source lexeme (`88"`) travels alongside the converted number, so
> citations quote the page rather than the arithmetic.

The reason is not fastidiousness. Planning stores integer millimetres and cents at rest as
a foundational rule, and a float arriving at the boundary would be rounded somewhere
undeclared. Sending `2235` and `"88\""` makes the conversion visible and checkable; a
disagreement between them is a bug someone can see.

### 1.2 The snapshot payload

The whole of what Planning receives. Note what is *not* in it: individual claims, review
state, extraction runs, retrieval indexes, conflicts. This platform resolves all of that
internally and publishes the result.

```text
Snapshot {
  snapshot_id       sha256 over the canonical member list
  tenant            TenantId
  spine_version     semver      which role vocabulary this was built against
  contract_version  semver
  policy_version    semver      which source policy resolved it (§1.4)
  retain_until      date        how long this hash is guaranteed resolvable

  roles             [RolePreset]
  products          [ProductDefinition]
  catalog           [CatalogItem]
  assemblies        [AssemblyDefinition]
  parameters        [ParameterTable]
  rules             [Rule]
  gaps              [Gap]
}
```

> **BINDING.** A snapshot fetched by hash resolves to the same bytes until `retain_until`,
> or resolves to an explicit tombstone recording that it was excised and why. Planning
> stamps the hash on every run and re-fetches historical runs *by hash*, never by
> re-resolving to "current".

`retain_until` exists because "immutable forever" is not a property any versioned store
actually provides — every one of them ships a garbage collector. Declaring a retention
period is honest; promising forever is not. The tombstone matters because a document may
eventually have to be removed, and an old run must then report *"this input was excised"*
rather than silently recomputing to a different answer.

### 1.3 ParameterTable — how conditional knowledge crosses

The important object. A value such as maximum post spacing is not one number; it depends
on conditions known only when a specific site is planned. So this platform publishes the
whole small table, and Planning evaluates it at run time against that project's site
conditions — deterministically, from pinned data.

```text
ParameterTable {
  parameter     "max_span_mm"
  scope         EntityRef        which product or assembly this applies to
  task          TaskCode         what this parameter decides — see §1.4
  hit_policy    unique | priority | collect_min | collect_max
  domain        { exposure_category: [B,C,D], hvhz: [true,false] }

  rows [ { conditions    { exposure_category: "C", hvhz: false }
           value         Quantity
           value_raw     "88\""
           source_class  sealed_approval
           curation_level  0 | 1 | 2
           admitted_by   { policy_version, rank }    why this row won
           provenance    [SourceRef] } ]

  uncovered [ { exposure_category: "D", hvhz: true } ]
}
```

> **BINDING.** Within one table, no two rows may match the same point in the domain when
> `hit_policy = unique`. Points in the domain that no row covers are listed in
> `uncovered` — never silently omitted.

Planning treats an uncovered point as a warned, unfulfilled requirement, not as permission
to guess. Declaring the domain is what makes the question *"which sites does this
knowledge not cover?"* answerable at all; a set of independent assertions cannot answer it.

`hit_policy` is a statement of intent about the condition space that can be checked
mechanically. `unique` means "I claim these conditions are disjoint," and the check will
tell you when that is false. See `rationale.md` §2 for the case already present in this
store.

### 1.4 Source policy — what a source is worth, and to whom

A source is not worth the same everywhere. A manufacturer's marketing catalog is a fine
source for a product's colour and an inadmissible one for a footing depth. And an actor —
a person in a role, or an extraction agent doing a job — should see only the sources their
role permits.

So authority is not a number stored on a claim. It is derived at resolution time from one
configurable table:

```text
SourcePolicy {
  task           TaskCode         what is being decided
  source_class   SourceClass      what kind of source it is
  role           RoleCode | null  who is asking; null = any
  admissible     bool             may this source back an accepted value here?
  rank           int              ordering among admissible sources; lower wins
  min_curation   0 | 1 | 2        how checked it must be to count here
}
```

The shipped default:

| Task | Sealed approval | Tested report | Spec sheet | Marketing | Company-authored | AI proposal |
|---|---|---|---|---|---|---|
| Structural parameter | 1st, level 2 | 2nd, level 2 | **inadmissible** | **inadmissible** | inadmissible | proposal only |
| Component dimension | 1st | 2nd | 3rd | inadmissible | 2nd | proposal only |
| Installation step | 2nd | — | 1st | 4th | 1st | proposal only |
| Product description | ok | — | ok | 1st | 1st | proposal only |

`TaskCode`, `SourceClass` and `RoleCode` are closed vocabularies in the registries; the
rows are configurable by the operator.

One mechanism covers four things that would otherwise be separate concerns: which sources
an actor can see, which sources may back an accepted value, how competing sources rank,
and how checked a value must be before it counts.

> **BINDING.** Resolution honours the policy, and the winning row records `admitted_by`,
> so Planning can render *why* a value was chosen without re-deriving it. `policy_version`
> is part of the snapshot hash.

**Unreviewed knowledge is allowed into a snapshot.** Gating it entirely would mean a new
tenant with an empty review queue could not plan at all, and the two teams could not work
independently. `min_curation` decides where a value may actually be relied upon; Planning
warns on any line that used a value below the bar.

### 1.5 The three API surfaces

| Surface | Calls | Character |
|---|---|---|
| Resolution | `POST /snapshots/resolve` → `{snapshot_id}`<br>`GET /snapshots/{id}` → `Snapshot` | Deterministic. Immutable, cacheable forever. Never called during a run. |
| Discovery | `GET /search`<br>`GET /source-refs/{id}`<br>`GET /claims` | Human-facing. Results carry source refs. Never an input to a plan. |
| Authoring | `POST /reviews`<br>`POST /roles`<br>`POST /documents`<br>`POST /gaps` | Writes, proxied from the frontend through Planning. This platform owns the workflow. |

Transport, framework, authentication mechanism, pagination style, and whether these are
one service or several are **not specified**. The shapes are the contract; the plumbing is
not.

`GET /source-refs/{id}` must return something a person can look at — the quoted text where
one exists, and an image of the region. How that image is produced is yours; note that
`distribution-design.md` establishes `workspace/derived/` as a regenerable cache rather
than hosted content, so rendering on demand from the fetched corpus is likely the natural
implementation.

---

## 2. The registries

These grow constantly. **Adding an entry is never a breaking change** — that property is
what lets two teams move at different speeds.

| Registry | Holds | Who adds |
|---|---|---|
| Roles | The job a part does. Ten to start, plus tenant extensions. | Spine: Planning. Extensions: Knowledge. |
| Warning & gap codes | Every user-visible problem, as `code + params`. | Whoever raises it; both locale bundles required. |
| Condition dimensions | What a claim may be conditioned on: exposure, HVHZ, height, soil… | Planning declares what it can bind. |
| Interfaces | How parts connect: routed, bracketed, screwed. | Knowledge. |
| Consumption models | How a product is obtained: discrete, cut from stock, packaged, by area. | Planning — this is engine behaviour. |
| Tasks, source classes, roles | The three axes of the source policy. | Knowledge; the operator configures rows. |

### 2.1 Roles: the spine, and extensions

A role is the job a part does. Planning has a counting rule for each spine role — how many
are needed and how big — so **a role Planning has no rule for cannot produce a BOM line**.

The ten to start: `post`, `post_cap`, `rail`, `bar`, `infill`, `reinforcement`, `bracket`,
`fastener`, `anchor`, `gate_hardware`. Plus `site_material`, reserved with no rule —
concrete and gravel are out of scope for now, and the id is held so it cannot be reused.

This platform may add extension roles freely, as children of a spine role. A child
inherits its parent's counting rule and cannot change it:

```text
role:fenceco/rebar_separator_clip
  parent  role:fastener      counted per connection — Planning already knows how
  ships as snapshot data · no release · live the same day
```

When no parent's rule fits — a decorative band above the infill is one per span, which no
existing rule produces — that is **not** an extension. It is a gap, raised to Planning,
and Planning grows a rule. This is expected and normal.

> **BINDING.** Extension role ids are tenant-namespaced (`role:fenceco/…`). Every
> extension's parent chain terminates at a spine role. An extension never declares a
> counting rule of its own.

### 2.2 The mechanical test

One question decides whether a new part-kind is a data change or a code change:

> Can this role's quantity and dimensions be derived by an existing rule, unchanged?

**Yes** → extension, ships as snapshot data, same day, no coordination.
**No** → a gap raised to Planning, with evidence. New rule, spine release, gap closes.

Either way, plans still generate in the meantime, with a warned line.

---

## 3. Obligations

### 3.1 What Planning relies on this platform for

This is the complete list. Satisfy these and every internal decision is yours.

1. **A snapshot hash resolves to the same bytes forever**, until `retain_until`, or to an
   explicit tombstone. A plan printed last March must render the same numbers next year.
2. **Every `ParameterTable` declares its hit policy and its domain**, has no overlapping
   rows under `unique`, and lists every uncovered point.
3. **Every value carries at least one resolvable `SourceRef`**, and
   `GET /source-refs/{id}` returns something a person can look at.
4. **Integers only** — thousandths of the named unit, with the verbatim source lexeme
   alongside.
5. **Every role in a snapshot resolves to a spine role** through its parent chain, and
   extension ids are tenant-namespaced.
6. **Every row carries an honest `source_class` and `curation_level`**, nothing reaches
   level 2 without a person having compared it to the source image, and resolution honours
   the source policy, recording `admitted_by` on the winner.
7. **Tenant isolation is enforced in code**, not by convention. A snapshot for one tenant
   contains nothing belonging to another.
8. **Gaps that cannot be expressed are published as gaps**, with evidence, rather than
   approximated into a role that nearly fits.

### 3.2 What this platform relies on Planning for

Stated so the promises are visible in both directions.

1. Pin a snapshot hash on every run; re-fetch historical runs by hash, never re-resolve.
2. Never read knowledge outside the pinned snapshot — no live fallback lookups. A run
   completes with this platform unreachable.
3. Publish the spine and contract versions supported, and refuse a snapshot built against
   an unknown major — loudly, at load, not silently at generate.
4. **Never fail a run over a gap.** Warned, named, unfulfilled lines instead.
5. Convert units once, at the boundary, and keep the source lexeme for display.
6. Report gaps back with evidence, through `POST /gaps`.
7. Capture expert corrections verbatim and immutably before anything interprets them, and
   forward them as proposals — never as accepted knowledge.
8. Own the counting rules. A spine role exists because Planning implements it; growing the
   spine is Planning's job.

### 3.3 What both rely on the Frontend for

1. Never present a search result as an answer. A source reference proves where the system
   looked, not that the source says what was written down.
2. Show curation level and source class wherever a value appears.
3. Show the image when reviewing anything the policy marks `min_curation = 2`.
4. Every string through i18n; every warning code present in both locale bundles.

---

## 4. What is not blocked

Two pieces of work cross no boundary and can begin before any of this is agreed.

**On this side:** the evidence reference and region-crop generation, so
`GET /source-refs/{id}` returns a picture. It cites nothing, blocks nothing, and it is the
thing a review queue cannot exist without. `docs/curation/02-curation-schema.md` §2.11
already works out the crop transform, the dpi handling and the rotation trap.

**On the Planning side:** site conditions on the project model — exposure category, HVHZ,
frost depth, soil class. Until they exist, every `ParameterTable` arrives with nothing to
match against.

Neither waits on the other.
