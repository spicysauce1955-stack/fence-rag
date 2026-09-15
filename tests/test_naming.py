"""The naming conventions, where they are cheap to check — `docs/naming.md`.

That document is mostly descriptive: the repository already had these
conventions, it just never wrote them down, and three defects found on
2026-09-08/09 were all the same shape — **a name nothing checks slowly stops
meaning what a reader assumes.** `fence_height_ft` against `fence_height`
(G108), twelve condition dimension names in the gold set of which three exist,
and five colliding document-id namespaces.

So the point of this file is not style. Each test below closes a specific hole
where a wrong name would reach published data or another team's build, and each
one passes today — a guard added red is a guard somebody disables.

`docs/naming.md` §11 lists what is enforced and what is only recorded, and the
rule for adding to it: **a convention arrives with its check, or with a stated
reason there is none.**
"""
import json
import re
import unittest

import context  # noqa: F401  -- puts the repo root on sys.path
from context import requires_store
from fence_evidence import api
from fence_evidence import snapshot as snapshot_module
from fence_evidence.canonical import part_version
from fence_evidence.cli import main  # noqa: F401  -- import guard
from fence_evidence.parts import build_parts
from fence_evidence.part_types import PartTypeRegistry, build_part_types
from fence_evidence.paths import REPO_ROOT
from fence_evidence.snapshot_store import list_snapshots, get_snapshot

HEX64 = re.compile(r"^[0-9a-f]{64}$")


def published():
    """Every stored snapshot that still carries a payload."""
    for row in list_snapshots():
        if row["tombstoned"]:
            continue
        yield row["snapshot_id"], get_snapshot(row["snapshot_id"])


class TestRule1EveryAuthorityResolves(unittest.TestCase):
    """§1, defect A-1 — `authority` is the only hash-bearing published field
    with no type gate and no closure check.

    `snapshot.HASH_BEARING` covers `superseded_by` and `contributing_sources`,
    and `belongs_to` is refused when it names a document outside `source_docs`.
    `authority` is in neither, so the same value that would be refused in a
    citation publishes cleanly in a row. `tests/test_published_dates.py` already
    joins on it, i.e. the codebase relies on an invariant nothing enforced.

    `[measured]` 2026-09-09: 0 of 7 authorities unresolvable. This keeps it 0.
    """

    def test_every_authority_names_a_document_in_the_same_snapshot(self):
        checked = 0
        for snapshot_id, payload in published():
            docs = {d["content_hash"] for d in payload.get("source_docs", [])}
            for table in payload.get("parameters", []):
                for row in table.get("rows", []):
                    authority = row.get("authority")
                    if authority is None:
                        continue
                    checked += 1
                    with self.subTest(snap=snapshot_id[:12], table=table["parameter"]):
                        self.assertIn(authority, docs,
                                      "an authority naming no published source "
                                      "document; obligation 16 reads this field")
        self.assertGreater(checked, 0, "no authorities were checked at all")

    def test_every_authority_is_a_full_hash_never_truncated(self):
        """§4 — 64 hex, because it is the same value as `content_hash`."""
        for snapshot_id, payload in published():
            for table in payload.get("parameters", []):
                for row in table.get("rows", []):
                    if row.get("authority") is None:
                        continue
                    with self.subTest(snap=snapshot_id[:12]):
                        self.assertRegex(row["authority"], HEX64)


class TestRule1OneConditionAxisOneName(unittest.TestCase):
    """§1 and G108 — the store held `fence_height_ft` and the publisher accepts
    only `fence_height`, and the only thing between them was a refusal at
    publish time.

    `[measured]` 2026-09-09: 18 facts carried the unpublishable name (none
    accepted) and 24 carried the publishable one (all accepted).
    `_translate_conditions({"fence_height_ft": 8.0})` returned
    `('condition_scope_undeclared', 'fence_height_ft')` -- a message naming a
    scope rather than a misspelt key, fired at the moment a curator accepted
    one of the 18 rather than at extraction. Same shape as the
    `lang`/`corpus_track` shortcut `tests/test_basis_columns.py` guards: one
    axis, two vocabularies, and a guard in only one of the two places.

    The static check is the load-bearing one. A functional check can only see
    the keys the evidence strings happen to trigger; reading the assignments
    out of the source sees every key the function CAN emit, which is what the
    rule says.
    """

    def emitted_keys(self):
        """Every literal key `facts._conditions` assigns into its dict."""
        import ast
        source = (REPO_ROOT / "fence_evidence" / "facts.py").read_text()
        tree = ast.parse(source)
        function = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_conditions")
        keys = set()
        for node in ast.walk(function):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if (isinstance(target, ast.Subscript)
                        and isinstance(target.value, ast.Name)
                        and isinstance(target.slice, ast.Constant)
                        and isinstance(target.slice.value, str)):
                    keys.add(target.slice.value)
        self.assertTrue(keys, "did not parse any condition key out of _conditions")
        return keys

    def test_every_key_the_extractor_can_emit_is_a_declared_dimension(self):
        from fence_evidence.parameters import CONDITION_SCOPE
        for key in sorted(self.emitted_keys()):
            with self.subTest(key=key):
                self.assertIn(key, CONDITION_SCOPE,
                              "obligation 13: a key with no declared scope is "
                              "refused at publish, so extracting it writes a "
                              "fact no review can make publishable")

    def test_a_height_the_extractor_writes_parses_back_into_an_interval(self):
        """The two ends must agree about the VALUE too, not only the key.
        `_parse_fence_height` reads a label; a bare float in feet would fail it
        just as surely as the wrong key failed `CONDITION_SCOPE`."""
        from fence_evidence.facts import _conditions
        from fence_evidence.parameters import _parse_fence_height
        for text in ("Rated for 130 mph on an 8' tall fence",
                     "6 feet tall, Exposure C",
                     "10ft. height at 90 mph",
                     "3.5ft high panels"):
            with self.subTest(text=text):
                conditions = _conditions(text, [])
                self.assertIn("fence_height", conditions)
                interval = _parse_fence_height(conditions["fence_height"])
                self.assertIsNotNone(interval, conditions["fence_height"])
                self.assertEqual(interval["min"], interval["max"],
                                 "a stated height is a point, not a band")
                self.assertTrue(interval["min_inclusive"])
                self.assertTrue(interval["max_inclusive"])

    def test_no_condition_the_extractor_emits_is_refused_by_the_publisher(self):
        """The end-to-end statement of the same thing, through the real gate."""
        from fence_evidence.facts import _conditions
        from fence_evidence.parameters import _translate_conditions
        conditions = _conditions(
            "Exposure C, 130 mph, HVHZ, 8' tall", [])
        _published, _dimensions, problem, height = _translate_conditions(conditions)
        self.assertIsNone(problem, f"the publisher refused {conditions}")
        self.assertIsNotNone(height)

    @requires_store
    def test_no_stored_fact_still_carries_the_retired_height_name(self):
        """The 18 rows were re-derived by `cli migrate`, not left to be fixed
        by a re-extraction that has not happened."""
        from fence_evidence.store import connect
        conn = connect(read_only=True)
        try:
            stale = conn.execute(
                "SELECT COUNT(*) FROM facts "
                "WHERE conditions LIKE '%\"fence_height_ft\"%'").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(stale, 0, "a fact still names the unpublishable axis")



# The unit tokens a `fact_type` name may end in, mapped to the spelling the
# `unit_original`/`unit_normalized` columns use. A closed set on purpose: a
# fact type ending in `_pickets` or `_inserts` is naming a component, not a
# unit, and must not be dragged into a unit check by a loose rule.
_SUFFIX_UNIT = {"in": "in", "mm": "mm", "cm": "cm", "ft": "ft",
                "mph": "mph", "deg": "deg", "degrees": "deg"}


def _canonical_unit(raw):
    """One spelling for a unit column's value. `in.` and `in` are one unit."""
    from fence_evidence.parameters import _UNIT_ALIASES
    text = (raw or "").strip().rstrip(".").lower()
    return _UNIT_ALIASES.get(text, text)


@requires_store
class TestRule2AUnitSuffixNamesAUnitTheRowCarries(unittest.TestCase):
    """§2, defects B-1 and B-2 — a `_in`/`_mm` suffix on a `fact_type` that no
    column of the row agrees with.

    `[measured]` 2026-09-09, before the fix: 17 fact types failed this — 13
    `*_drawing_*_mm` types whose only unit is `in` (B-1; `naming.md` said 11,
    which was itself a miscount) and 4 `kit_qty_*_in` types that count `each`
    (B-2). `_in` is a live dispatch key: `facts._normalise` branches on
    `fact_type.endswith("_in")` and would have multiplied a count of pickets by
    twelve had those rows ever reached it; they survived only by being written
    directly by the `*_claims.py` recipes.

    The check is deliberately "the named unit appears in `unit_original` OR
    `unit_normalized`", not equality with either. `stock_length_in` states feet
    in 33 of its 62 sources and `naming.md` records that as CORRECT — the name
    is the type's canonical unit and `unit_normalized` is `in` on all 62 — so
    an equality rule on `unit_original` would fail the one case the document
    explicitly protects, and an equality rule on `unit_normalized` would fail
    the drawing readings, whose value is never normalised at all.
    """

    def fact_types(self):
        from fence_evidence.store import connect
        conn = connect(read_only=True)
        try:
            return conn.execute(
                """SELECT fact_type, COUNT(*) AS n,
                          GROUP_CONCAT(DISTINCT unit_original) AS originals,
                          GROUP_CONCAT(DISTINCT unit_normalized) AS normalized
                     FROM facts GROUP BY fact_type ORDER BY fact_type""").fetchall()
        finally:
            conn.close()

    def test_no_fact_type_names_a_unit_none_of_its_rows_carries(self):
        checked = 0
        for row in self.fact_types():
            named = _SUFFIX_UNIT.get(row["fact_type"].rsplit("_", 1)[-1])
            if named is None:
                continue
            checked += 1
            carried = {_canonical_unit(v)
                       for column in ("originals", "normalized")
                       for v in (row[column] or "").split(",") if v.strip()}
            with self.subTest(fact_type=row["fact_type"]):
                self.assertIn(named, carried,
                              f"{row['fact_type']} names {named!r} and its "
                              f"{row['n']} rows carry {sorted(carried)}; "
                              f"`facts._normalise` dispatches on this suffix")
        self.assertGreater(checked, 10, "no unit-suffixed fact types were checked")


class TestRule3ANameSignalsAShape(unittest.TestCase):
    """§3 — on a `SpecField`, `_mm` carries a `Quantity` and an unsuffixed key
    carries a `Token`.

    `authored_models.py` dispatches on exactly this and refuses a bad shape, but
    only on the consumer-model audit path: `snapshot.PART_SHAPE` does not type
    `SpecField.value` at all, so a wrongly-shaped value publishes through
    `cli snapshot --build`. `[measured]` 42 published parts, zero exceptions.
    """

    def spec_fields(self):
        for snapshot_id, payload in published():
            for part in payload.get("parts", []):
                for field in part.get("spec", []):
                    yield snapshot_id, part["id"], field

    def test_a_millimetre_key_carries_a_quantity(self):
        checked = 0
        for snapshot_id, part_id, field in self.spec_fields():
            if not str(field.get("key", "")).endswith("_mm"):
                continue
            checked += 1
            with self.subTest(snap=snapshot_id[:12], part=part_id, key=field["key"]):
                value = field.get("value")
                self.assertIsInstance(value, dict)
                self.assertIsInstance(value.get("amount_milli"), int)
                self.assertTrue(value.get("value_raw"),
                                "obligation 4: every verbatim source lexeme "
                                "travels with the number")
        self.assertGreater(checked, 0, "no _mm spec fields were checked")

    def test_an_unsuffixed_key_carries_a_token_not_a_bare_string(self):
        for snapshot_id, part_id, field in self.spec_fields():
            key = str(field.get("key", ""))
            if key.endswith("_mm"):
                continue
            with self.subTest(snap=snapshot_id[:12], part=part_id, key=key):
                value = field.get("value")
                self.assertIsInstance(value, dict,
                                      "a Token is not a bare string")
                self.assertIsInstance(value.get("key"), str)
                self.assertTrue(value.get("value_raw"))

    def test_no_bare_number_crosses_as_a_dimension(self):
        """Obligation 4 is BINDING: nothing in this corpus is a whole number of
        millimetres -- `7/8"` is 22.225 mm."""
        for snapshot_id, part_id, field in self.spec_fields():
            with self.subTest(snap=snapshot_id[:12], part=part_id, key=field.get("key")):
                self.assertNotIsInstance(field.get("value"), (int, float))


class TestRule4PartVersionNamesOneThing(unittest.TestCase):
    """§4, defect D-5 — one snapshot published `Part.version` as the integer
    `1` on 27 parts and as `"sha256:<64hex>"` on 15, and `PART_SHAPE` omitted
    the field so nothing caught it.

    The two forms are not two spellings of one idea; they are two different
    jobs. G103 (2026-09-07) records why the string form exists: *"Part versions
    no longer stay at 1 when reviewed content changes. Each is now a `sha256:`
    hash of all public Part content except version."* The integer never moved —
    `[measured]` 2026-09-09, `1` on every int-versioned part in all 24 stored
    snapshots that carry parts, and no bump path exists anywhere in the
    package — so `knowledge-datamodel.md` §1395's `Combination.members ==
    [Part@version]` would pin a version that a correction leaves unchanged.

    So the content hash is the form that does the job, and these guards keep it
    the only one a NEW build can mint. They do not reach the stored snapshots:
    those were well-formed under the rule of their day, they are write-once, and
    `verify()` runs over them unchanged — which is why `PART_SHAPE` carries the
    weaker `positive int | non-empty str` rule that history satisfies and the
    builder carries the strong one. See `docs/naming.md` §4.
    """

    def synthetic_parts(self):
        """Two parts off a synthetic composition — no store, no corpus."""
        components = [
            {"component_id": "guard-line-post", "component_type": "post",
             "component_name": "Guard line post"},
            {"component_id": "guard-rail", "component_type": "rail",
             "component_name": "Guard rail"},
        ]
        registry = PartTypeRegistry("Guard")
        build_part_types(components, registry)
        parts, _ = build_parts(components, registry, conn=None,
                               identity_namespace=registry.namespace,
                               source_ref=lambda element_id: {})
        self.assertTrue(parts, "the fixture built no parts to check")
        return parts

    def test_a_built_part_version_is_the_hash_of_the_part_it_names(self):
        """A counter that never increments pins nothing. Recomputing the hash
        off the published payload is also the only way a consumer can check the
        pin, so it must be reproducible from the part alone."""
        for part in self.synthetic_parts():
            with self.subTest(part=part["id"]):
                self.assertEqual(part["version"], part_version(part))

    def test_two_parts_that_differ_carry_different_versions(self):
        """The property G103 bought: a corrected value must not ship under the
        version its predecessor shipped under."""
        versions = {part["version"] for part in self.synthetic_parts()}
        self.assertEqual(len(versions), 2)

    def test_part_version_excludes_the_version_field_itself(self):
        """Hashing a dict that already carries a version chains the hashes, and
        a chained version cannot be recomputed from the published payload.
        `[measured]` 2026-09-09: 14 of the 15 string-versioned parts in
        snapshot `0e04d171` reproduced from their own bytes; the Augusta picket
        did not, because `augusta_drawing_claims` re-hashed an already-versioned
        dict."""
        part = {"id": "x", "spec": []}
        first = part_version(part)
        part["version"] = first
        self.assertEqual(part_version(part), first)

    def test_the_part_shape_types_the_version_field(self):
        """`PART_SHAPE` is an allowlist: a field absent from it publishes
        whatever type it happens to hold. `version` was absent."""
        shape = {name: ok for name, ok, _ in snapshot_module.PART_SHAPE}
        self.assertIn("version", shape)
        ok = shape["version"]
        self.assertTrue(ok("sha256:" + "a" * 64))
        self.assertTrue(ok(1), "the stored snapshots publish this and stay valid")
        for bad in (0, -1, "", "   ", [], {}, 1.0, True):
            with self.subTest(bad=bad):
                self.assertFalse(ok(bad))

    @requires_store
    def test_every_scoped_recipe_part_reproduces_its_own_version(self):
        """The four `*_claims.py` slices mint their own parts and were the
        original home of the string form; this is the guard that would have
        caught the Augusta picket's chained hash."""
        from fence_evidence.augusta_drawing_claims import build_parts as augusta
        from fence_evidence.emblem_claims import build_emblem_parts as emblem
        from fence_evidence.emblem_drawing_claims import build_parts as emblem_drawing
        from fence_evidence.parameters import _default_source_ref
        from fence_evidence.pembroke_cadpage_claims import build_parts as pembroke
        from fence_evidence.store import connect

        conn = connect(read_only=True)
        try:
            mint = _default_source_ref(conn)
            built = (augusta(conn, mint) + emblem(conn, mint)
                     + emblem_drawing(conn, mint) + pembroke(conn, mint))
            self.assertTrue(built, "no recipe part was built to check")
            for part in built:
                with self.subTest(part=part["id"]):
                    self.assertEqual(part["version"], part_version(part))
        finally:
            conn.close()


class TestRule5CaseCarriesMeaning(unittest.TestCase):
    """§5 — `UPPER_SNAKE` is a registry code that crosses to Planning and needs
    a locale bundle; `error.*` is transport and must never enter that namespace.

    `tests/test_api.py` already asserts this over `api.py`. Repeated here
    because `naming.md` states it as a project-wide rule rather than one
    module's, and a reader who changes the rule should fail in both places.
    """

    def test_every_error_code_is_in_the_error_namespace(self):
        for code in api.ERROR_CODES:
            with self.subTest(code):
                self.assertTrue(code.startswith("error."), code)

    def test_no_error_code_is_upper_snake(self):
        """UPPER_SNAKE here would break Planning's CI on our commit."""
        for code in api.ERROR_CODES:
            with self.subTest(code):
                self.assertNotEqual(code, code.upper())


class TestRule9DocumentsAndIds(unittest.TestCase):
    """§9 — kebab-case at the CLI, and `G<n>` never reused."""

    def test_every_cli_subcommand_is_kebab_case(self):
        """`[measured]` 33 subcommands, zero underscores. A `_` here would make
        the module-name-to-subcommand transform ambiguous."""
        import argparse
        import contextlib
        import io

        # Reach the subparser table without running a command.
        parser_holder = {}
        original = argparse.ArgumentParser.add_subparsers

        def capture(self, *args, **kwargs):
            sub = original(self, *args, **kwargs)
            parser_holder["sub"] = sub
            return sub

        argparse.ArgumentParser.add_subparsers = capture
        try:
            with contextlib.suppress(SystemExit), \
                    contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()):
                main(["--help"])
        finally:
            argparse.ArgumentParser.add_subparsers = original

        commands = list(parser_holder["sub"].choices)
        self.assertGreater(len(commands), 20, "did not capture the subcommands")
        for command in commands:
            with self.subTest(command):
                self.assertNotIn("_", command)
                self.assertEqual(command, command.lower())

    def test_gap_ids_are_never_reused(self):
        """A recurrence is `G<n>, second instance`, never a fresh heading with
        the same bare id -- renumbering would break every citation."""
        text = (REPO_ROOT / "docs" / "state-and-gaps.md").read_text()
        headings = re.findall(r"^### (G\d+)([^\n]*)$", text, re.MULTILINE)
        seen: dict = {}
        for gap_id, rest in headings:
            if gap_id in seen:
                with self.subTest(gap_id):
                    self.assertIn("instance", rest.lower(),
                                  f"{gap_id} is defined twice without being "
                                  f"marked as a recurrence")
            seen.setdefault(gap_id, rest)
        self.assertGreater(len(seen), 90, "did not parse the gap headings")

    def test_the_naming_document_exists_and_states_its_status(self):
        """A conventions document nobody can find is the problem it solves."""
        text = (REPO_ROOT / "docs" / "naming.md").read_text()
        self.assertIn("DECIDED", text)
        self.assertIn("RULE 1", text)


if __name__ == "__main__":
    unittest.main()
