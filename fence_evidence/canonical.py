"""Turn a published object into bytes, the same way every time.

Contract obligation 1: *a snapshot hash resolves to the same bytes forever*. That
promise is made here and nowhere else. Everything upstream can be correct and the
guarantee still fails if two runs over identical knowledge serialise differently.

So this module is deliberately strict, and refuses rather than guesses:

* **Keys are sorted**, at every depth. Insertion order is an accident of how the
  object was built and must not reach the bytes. In particular `dict(row)` on a
  SQLite row carries *store-history-dependent* order -- a migrated table has its
  added columns at the end, a freshly built one has them mid-table -- so an
  object assembled by iterating a row would hash differently on two stores
  holding identical data.
* **Floats are refused.** The contract is explicit that no floating-point number
  crosses in either direction, and the reason is exactly this: ``0.1 + 0.2`` does
  not render identically everywhere, and ``repr`` has changed between Python
  versions. Integers in thousandths, converted at one named point upstream.
* **Sets are refused.** Their iteration order is not defined. The caller decides
  what order a list should be in, because only the caller knows whether the order
  carries meaning -- ``Quantity.value_raw`` is "a list, in printed order", and
  sorting it would destroy the thing it was published to preserve.
* **Whitespace is minimal.** A space is a byte.

Unicode is *not* escaped. Escaping would still be deterministic, but a snapshot is
something a person may have to diff by eye when two builds disagree, and
``CertaGrain\\u00ae`` helps nobody.
"""
from __future__ import annotations

import hashlib
import json


class CanonicalError(TypeError):
    """Raised when a value cannot be serialised deterministically.

    Always a refusal, never a fallback. A canonicaliser that quietly coerced
    something it did not understand would produce bytes that depend on the
    coercion, which is the failure this module exists to prevent.
    """


def _check(value, path: str = "$") -> None:
    """Walk the object and refuse anything whose bytes are not determined."""
    # bool before int: True is an int in Python, and must stay a JSON boolean
    if value is None or isinstance(value, (bool, str)):
        return
    if isinstance(value, float):
        raise CanonicalError(
            f"{path}: a float ({value!r}) cannot cross. No floating-point number "
            f"is published in either direction — integers in thousandths, "
            f"converted at one named point. See contract §1.1.")
    if isinstance(value, int):
        return
    if isinstance(value, (set, frozenset)):
        raise CanonicalError(
            f"{path}: a set has no defined order, so its bytes are not determined. "
            f"Sort it into a list at the call site, where the right order is known.")
    if isinstance(value, (list, tuple)):
        for i, item in enumerate(value):
            _check(item, f"{path}[{i}]")
        return
    if isinstance(value, dict):
        for k, v in value.items():
            if not isinstance(k, str):
                raise CanonicalError(
                    f"{path}: object keys must be strings to sort reliably; "
                    f"got {type(k).__name__} ({k!r})")
            _check(v, f"{path}.{k}")
        return
    raise CanonicalError(
        f"{path}: {type(value).__name__} has no canonical form. Convert it to a "
        f"string, an integer, a list or a dict before publishing it.")


def canonical_bytes(obj) -> bytes:
    """Serialise `obj` to the one byte sequence that represents it."""
    _check(obj)
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def content_hash(obj) -> str:
    """The sha256 of an object's canonical bytes, as hex."""
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def is_object_version(value) -> bool:
    """Is `value` admissible as a published object's `version`?

    A positive integer or a non-empty string, and nothing else. This is the
    weak rule, and it is weak on purpose: `snapshot.verify()` runs over
    write-once snapshots that were published before `part_version` existed, so
    a gate that refused the integer `1` would retroactively invalidate 24
    stored snapshots rather than catching anything. The strong rule -- a new
    build mints a content hash and only a content hash -- belongs at the
    builder, and `tests/test_naming.py` holds it there.

    `type(value) is int` rather than `isinstance`: `True` is an `int` in
    Python, and a boolean version is a caller mistake, not a version 1.

    Both this platform's `authored_models` audit and Planning's own
    `_version_identity` validator already enforce exactly this predicate.
    Same rule, one definition here, so the two cannot drift apart.
    """
    if type(value) is int:
        return value > 0
    return isinstance(value, str) and bool(value.strip())


def part_version(part: dict) -> str:
    """A `Part`'s version: `sha256:` + the content hash of the part WITHOUT it.

    G103, 2026-09-07: *"Part versions no longer stay at 1 when reviewed content
    changes. Each is now a `sha256:` hash of all public Part content except
    version... Hash versions identify content, not chronological order."* The
    integer form it replaced was the literal `1`, minted once and never
    incremented anywhere in this package, so a corrected value shipped under
    the version its predecessor shipped under -- which is precisely what
    `knowledge-datamodel.md`'s `Combination.members == [Part@version]` pins
    against.

    **The version field is excluded from its own hash**, and this function
    exists because doing that by hand went wrong once: `augusta_drawing_claims`
    re-hashed a picket dict that already carried a version, chaining the two so
    the published value could not be recomputed from the published payload.
    `[measured]` 2026-09-09: 14 of 15 string-versioned parts in snapshot
    `0e04d171` reproduced from their own bytes; that picket did not.

    Idempotent: passing a part that already carries its version returns the
    same string. Fails noisily -- `CanonicalError` -- on a part that cannot be
    serialised, rather than minting a version over bytes nobody can reproduce.
    """
    return "sha256:" + content_hash(
        {key: value for key, value in part.items() if key != "version"})
