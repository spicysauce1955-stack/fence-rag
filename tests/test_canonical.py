"""Canonical serialisation — the function obligation 1 rests on.

A snapshot is addressed by the sha256 of its own bytes, so *producing the bytes*
is the load-bearing step. Anything that varies between two runs over identical
knowledge — key order, float formatting, a set's iteration order — turns the hash
into a lie that will not surface until someone re-fetches a plan from last year.

The specific trap this repo has already walked near: `dict(row)` key order on a
SQLite row is store-history-dependent. A migrated table carries its added columns
at the end; a freshly built one has them mid-table. Nothing reads those tables
positionally so it is invisible today, but a canonicaliser that inherited field
order from a database row would produce different bytes from the same knowledge
depending on how the store was built.
"""
import json
import unittest

import context  # noqa: F401  -- puts the repo root on sys.path
from fence_evidence.canonical import CanonicalError, canonical_bytes, content_hash


class TestKeyOrder(unittest.TestCase):
    def test_insertion_order_does_not_matter(self):
        a = {"zebra": 1, "apple": 2, "mango": 3}
        b = {"mango": 3, "zebra": 1, "apple": 2}
        self.assertEqual(canonical_bytes(a), canonical_bytes(b))

    def test_keys_come_out_sorted(self):
        out = canonical_bytes({"b": 1, "a": 2, "c": 3}).decode()
        self.assertLess(out.index('"a"'), out.index('"b"'))
        self.assertLess(out.index('"b"'), out.index('"c"'))

    def test_nested_objects_are_sorted_too(self):
        a = {"outer": {"z": 1, "a": 2}}
        b = {"outer": {"a": 2, "z": 1}}
        self.assertEqual(canonical_bytes(a), canonical_bytes(b))


class TestNoFloats(unittest.TestCase):
    """The contract: no floating-point number crosses in either direction."""

    def test_a_float_is_refused(self):
        with self.assertRaises(CanonicalError) as ctx:
            canonical_bytes({"amount": 30.0})
        self.assertIn("float", str(ctx.exception).lower())

    def test_a_nested_float_is_refused(self):
        with self.assertRaises(CanonicalError):
            canonical_bytes({"rows": [{"value": 0.1}]})

    def test_integers_are_fine(self):
        self.assertIn(b"762000", canonical_bytes({"amount_milli": 762000}))

    def test_bool_is_not_mistaken_for_an_int(self):
        """`True` is an int in Python. It must serialise as a boolean."""
        out = canonical_bytes({"hvhz": True}).decode()
        self.assertIn("true", out)
        self.assertNotIn("1", out.split(":")[1])


class TestDeterminism(unittest.TestCase):
    def test_the_same_object_hashes_the_same_twice(self):
        obj = {"a": [1, 2, 3], "b": {"c": "x"}}
        self.assertEqual(content_hash(obj), content_hash(obj))

    def test_a_different_object_hashes_differently(self):
        self.assertNotEqual(content_hash({"a": 1}), content_hash({"a": 2}))

    def test_a_set_is_refused_because_its_order_is_not_defined(self):
        with self.assertRaises(CanonicalError):
            canonical_bytes({"tags": {"b", "a"}})

    def test_list_order_is_preserved_not_sorted(self):
        """Lists carry meaning in their order -- `value_raw` is 'in printed order'.
        Sorting them would destroy that; the CALLER sorts where sorting is right."""
        one = canonical_bytes({"value_raw": ["4 inch", "101 mm"]})
        two = canonical_bytes({"value_raw": ["101 mm", "4 inch"]})
        self.assertNotEqual(one, two)

    def test_unicode_is_not_escaped_away(self):
        """Source lexemes carry real characters -- 3¼" and ® appear in this corpus.
        Escaping them would still be deterministic, but it would make the bytes
        unreadable to a person diffing two snapshots."""
        out = canonical_bytes({"text": 'CertaGrain® 3¼"'})
        self.assertIn("®".encode(), out)


class TestRejectsWhatItCannotOrder(unittest.TestCase):
    def test_a_non_string_key_is_refused(self):
        with self.assertRaises(CanonicalError):
            canonical_bytes({1: "a"})

    def test_an_unknown_type_is_refused(self):
        class Thing:
            pass
        with self.assertRaises(CanonicalError):
            canonical_bytes({"x": Thing()})

    def test_none_is_allowed(self):
        self.assertIn(b"null", canonical_bytes({"x": None}))


class TestOutputShape(unittest.TestCase):
    def test_it_is_valid_json(self):
        obj = {"b": 1, "a": [1, 2], "c": {"d": None}}
        self.assertEqual(json.loads(canonical_bytes(obj)), obj)

    def test_it_is_utf8_bytes_not_str(self):
        self.assertIsInstance(canonical_bytes({"a": 1}), bytes)

    def test_no_incidental_whitespace(self):
        """Whitespace is a byte too. Two serialisers that differ only in spacing
        produce different hashes."""
        self.assertNotIn(b", ", canonical_bytes({"a": 1, "b": 2}))
        self.assertNotIn(b": ", canonical_bytes({"a": 1}))


if __name__ == "__main__":
    unittest.main()
