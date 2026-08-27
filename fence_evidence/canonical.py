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
