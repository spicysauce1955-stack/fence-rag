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
from fence_evidence import api
from fence_evidence.cli import main  # noqa: F401  -- import guard
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
