"""Obligation 7 — the tenant axis, and the rule that makes it enforceable.

    > 7. **Tenant isolation is enforced in code**, not by convention. A snapshot
    >    for one tenant contains nothing belonging to another.

`10-ratification-v1.0.md` §3.2 declared this unbuilt, and was blunt about it:
*"There is no tenant concept anywhere in this store — one corpus, no boundary to
enforce in code."* `build_snapshot(tenant=...)` took a tenant, stamped it into
the hashed members, and nothing read it. A label is precisely what obligation 7
says a boundary must not be.

Three decisions, and the reasoning for each, because they are the kind that are
expensive to reverse once a snapshot format is fixed.

**1. Ownership lives on `documents`, and nowhere else.** One nullable column.
Not on `elements`, not on `facts`, not on `retrieval_units`. `docs/layering.md`'s
rule is that every reference points DOWN a layer, so ownership is *derivable*
at every layer above L1: an element belongs to a version belongs to a document.
Copying the tenant onto derived rows would create a second copy of the truth
that a half-finished write could leave disagreeing with the first — the same
reasoning that makes `current_editions` a view rather than a flag column.

**2. NULL means shared, and it is the default.** Everything in this corpus is
manufacturer-derived knowledge belonging to no tenant, which is why
`parameters.py` already mints `{"kind": ..., "tenant": None}` on every
`EntityRef`. The migration therefore arrives on 144 rows and must leave every
one of them NULL: defaulting them to the operator's tenant would hand the whole
corpus to one tenant as private property — obligation 7 inverted, arriving
through a migration rather than through a leak.

**3. The gate is the ref minter, not a filter.** Closure (§1.2.1) is not checked
after the fact: minting a `SourceRef` registers its `SourceDoc`, so a snapshot
citing a document it does not carry cannot be *built*. Tenancy reuses that choke
point — every published value's provenance passes through
`SnapshotBuilder.source_ref` — so a cross-tenant value is unpublishable rather
than filtered out. Selection is scoped too, so the gate is a backstop that
should never fire rather than the thing doing the work; a gate that is load
bearing turns a leak into an outage the first time real data reaches it.

What is deliberately NOT here: any notion of a tenant *reading* through the
Discovery API. `api.py`'s bearer allowlist is authentication, not authorisation,
and mapping a token to a tenant is a separate decision with its own failure
mode. Today every document is shared, so the two questions have the same answer;
they will not once the first upload lands. Recorded rather than guessed.
"""

# A document owned by nobody. Shared knowledge — the entire corpus today.
SHARED = None

# `contract.md` §2.1 namespaces extension ids `shared` / `mfr/<manufacturer>` /
# `<tenant>`. The first two are not available as tenant names: a tenant called
# `shared` would make its private uploads indistinguishable from global
# knowledge in every id that namespaces on it, and the collision would be
# invisible — two different things with one id, which is the failure mode ids
# exist to prevent.
RESERVED_NAMES = frozenset({"shared"})
RESERVED_PREFIXES = ("mfr/",)


class TenantLeak(RuntimeError):
    """One tenant's data was about to reach another's. Raised, never logged.

    Same reasoning as `VerificationFailed`: the failure mode is silent. Planning
    pins a hash and computes locally, so nothing downstream is positioned to
    notice that a row in the object belongs to somebody else.
    """


def validate_tenant(tenant) -> str:
    """The tenant id, or `ValueError`. Called before the store is touched."""
    if not isinstance(tenant, str) or not tenant.strip():
        raise ValueError(f"tenant must be a non-empty string; got {tenant!r}")
    if tenant != tenant.strip():
        raise ValueError(f"tenant {tenant!r} has leading or trailing whitespace; "
                         f"it is used as an id, and two ids differing only in "
                         f"space are two things nobody can tell apart")
    if tenant in RESERVED_NAMES:
        raise ValueError(f"tenant {tenant!r} is a reserved namespace "
                         f"(contract.md §2.1); pick a name that cannot collide "
                         f"with global knowledge")
    for prefix in RESERVED_PREFIXES:
        if tenant.startswith(prefix):
            raise ValueError(f"tenant {tenant!r} is in the reserved "
                             f"{prefix!r} namespace (contract.md §2.1)")
    return tenant


def visible_to(owner, tenant: str) -> bool:
    """True when a document owned by `owner` may appear in `tenant`'s snapshot.

    Shared knowledge is visible to everyone; a tenant's own upload is visible to
    that tenant; nothing else is visible to anybody.
    """
    return owner is SHARED or owner is None or owner == tenant


def visible_sql(alias: str = "d") -> str:
    """The same rule as SQL, for scoping a selection. Binds ONE parameter.

    One definition, used by both the gate and every selection, so the query that
    chooses what to publish and the check that refuses to publish it cannot
    drift apart about what "visible" means.
    """
    return f"({alias}.owner_tenant IS NULL OR {alias}.owner_tenant = ?)"
