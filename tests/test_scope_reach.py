"""reach.py: does anything outside this repository know what we published TO?

Every published `ParameterTable` carries a `scope` naming the product it applies
to, and every published `Part` carries an id. Both are OUR identifiers. The
consumer binds its own — `conversation.md` T51 §2 measured the consequence:
across 6,563 stored generation runs, an `mfr/*` id appears at no path under
`.graph` or `.strategy`, so not one published table has ever governed anything.

Neither system said so. Ours published 18 more Parts into a third unreachable
namespace in one session (T53 §4) and reported nothing, because nothing here
counts identities against what a consumer can resolve.

These tests are that count. The pin in `TestTheKnownSurfaceIsPinned` is the one
that matters: it fails when a NEW identity family is published, which is what
did not happen when `mfr/weatherables` appeared.
"""
import contextlib
import io
import json
import shutil
import tempfile
from pathlib import Path
import unittest

from context import ROOT  # noqa: F401
from fence_evidence import cli, reach
from fence_evidence.snapshot_store import SNAPSHOT_DIR


def _snapshot(*, parameters=(), parts=()):
    """A snapshot document carrying only what `reach` reads."""
    return {
        "parameters": [
            {"parameter": p, "scope": {"kind": "fence_model", "id": s,
                                       "tenant": None}, "rows": []}
            for p, s in parameters
        ],
        "parts": [{"id": i} for i in parts],
    }


class TestTheSurfaceIsCounted(unittest.TestCase):

    def test_a_parameter_scope_is_an_identity(self):
        surface = reach.scope_surface(
            _snapshot(parameters=[("max_span_mm", "mfr/acme-privacy")]))
        self.assertEqual(surface.identities, ("mfr/acme-privacy",))
        self.assertEqual(surface.objects, 1)

    def test_a_part_id_contributes_its_namespace_not_the_whole_id(self):
        """`mfr/acme/rail-white` and `mfr/acme/post-tan` are one family.

        The identity a consumer has to resolve is the manufacturer segment, not
        each SKU; counting SKUs would report 42 problems where there are three.
        """
        surface = reach.scope_surface(
            _snapshot(parts=["mfr/acme/rail-white", "mfr/acme/post-tan"]))
        self.assertEqual(surface.identities, ("mfr/acme",))
        self.assertEqual(surface.objects, 2)

    def test_identities_are_sorted_and_deduplicated(self):
        surface = reach.scope_surface(_snapshot(
            parameters=[("max_span_mm", "mfr/zeta"), ("footing_depth_mm", "mfr/alpha")],
            parts=["mfr/zeta/rail"]))
        self.assertEqual(surface.identities, ("mfr/alpha", "mfr/zeta"))


class TestUnresolvableIsTheAlarm(unittest.TestCase):

    def test_an_identity_with_no_declared_association_is_unresolvable(self):
        surface = reach.scope_surface(
            _snapshot(parameters=[("max_span_mm", "mfr/acme-privacy")]))
        self.assertEqual(reach.unresolvable(surface, associations={}),
                         ("mfr/acme-privacy",))

    def test_a_declared_association_resolves_it(self):
        surface = reach.scope_surface(
            _snapshot(parameters=[("max_span_mm", "mfr/acme-privacy")]))
        self.assertEqual(
            reach.unresolvable(surface, associations={"mfr/acme-privacy": "M-ACME"}),
            ())

    def test_today_nothing_is_declared_so_everything_is_unresolvable(self):
        """The honest default. `DECLARED_ASSOCIATIONS` is empty and says why."""
        self.assertEqual(reach.DECLARED_ASSOCIATIONS, {})
        surface = reach.scope_surface(
            _snapshot(parameters=[("max_span_mm", "mfr/acme")], parts=["shared/x/y"]))
        self.assertEqual(reach.unresolvable(surface), ("mfr/acme", "shared/x"))


class TestTheKnownSurfaceIsPinned(unittest.TestCase):
    """The test that would have caught `mfr/weatherables` on the day it landed.

    A new identity family is not a defect. Publishing one WITHOUT NOTICING is,
    and that is the only thing this pin prevents: it fails, names the new
    family, and makes somebody decide whether a consumer can reach it.
    """

    def _stored(self):
        paths = sorted(SNAPSHOT_DIR.glob("*.json"))
        if not paths:
            self.skipTest("no stored snapshots in this checkout")
        return paths

    def test_no_stored_snapshot_publishes_an_unknown_identity(self):
        unknown = {}
        for path in self._stored():
            surface = reach.scope_surface(json.loads(path.read_text()))
            for ident in surface.identities:
                if ident not in reach.KNOWN_IDENTITIES:
                    unknown.setdefault(ident, []).append(path.name[:8])
        self.assertEqual(
            unknown, {},
            "a snapshot publishes an identity family that is not in "
            "reach.KNOWN_IDENTITIES. That is not automatically wrong -- but "
            "nothing outside this repository can resolve it, so add it there "
            "deliberately and say in `conversation.md` that it exists.")

    def test_every_known_identity_is_still_published(self):
        """The pin decays in the other direction too: a stale entry is a lie."""
        seen = set()
        for path in self._stored():
            seen |= set(reach.scope_surface(json.loads(path.read_text())).identities)
        self.assertEqual(sorted(set(reach.KNOWN_IDENTITIES) - seen), [])


class TestTheReportCountsWhatIsStranded(unittest.TestCase):
    """`reachability_report` is what a person runs. It has to say the number."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)

    def _write(self, name, document):
        (self.dir / f"{name}.json").write_text(json.dumps(document))

    def test_it_counts_objects_no_consumer_can_reach(self):
        self._write("aaaa", _snapshot(
            parameters=[("max_span_mm", "mfr/certainteed-columbia-imperial-chesterfield")],
            parts=["mfr/weatherables/rail", "mfr/weatherables/post"]))
        report = reach.reachability_report(root=self.dir)
        self.assertEqual(report["worst"]["unreachable_objects"], 3)
        self.assertEqual(report["declared_associations"], 0)

    def test_an_unknown_identity_is_named_not_merely_counted(self):
        self._write("aaaa", _snapshot(parameters=[("max_span_mm", "mfr/brand-new-co")]))
        report = reach.reachability_report(root=self.dir)
        self.assertEqual(report["unknown_identities"], ["mfr/brand-new-co"])

    def test_the_named_snapshot_is_the_worst_not_an_arbitrary_one(self):
        """Snapshots are named by content hash, so filename order is arbitrary.

        An earlier cut of this reported `snapshots[-1]` as `latest`; against the
        real store that named a snapshot from four sessions ago with 20 stranded
        objects, while another held 51.
        """
        self._write("ffff", _snapshot(parameters=[("max_span_mm", "mfr/certainteed")]))
        self._write("aaaa", _snapshot(
            parameters=[("max_span_mm", "mfr/certainteed")],
            parts=["mfr/weatherables/rail", "mfr/weatherables/post"]))
        report = reach.reachability_report(root=self.dir)
        self.assertEqual(report["worst"]["snapshot_id"], "aaaa")
        self.assertEqual(report["worst"]["unreachable_objects"], 3)

    def test_a_snapshot_with_no_scoped_objects_is_not_counted_as_reaching(self):
        """An empty snapshot must not read as 'nothing stranded'.

        This is the vacuous-green shape `cli refs --verify` exists to refuse
        (G39): zero objects checked is not zero objects broken.
        """
        self._write("aaaa", {"parameters": [], "parts": []})
        report = reach.reachability_report(root=self.dir)
        self.assertEqual(report["snapshots_with_scoped_objects"], 0)
        self.assertIsNone(report["worst"])

    def test_unreadable_json_does_not_abort_the_sweep(self):
        (self.dir / "bad.json").write_text("{not json")
        self._write("good", _snapshot(parameters=[("max_span_mm", "mfr/certainteed")]))
        report = reach.reachability_report(root=self.dir)
        self.assertEqual(report["snapshots_with_scoped_objects"], 1)


class TestTheCommandsExitCode(unittest.TestCase):
    """`cli reach` is a guard, so its exit code has to mean something.

    Exit 1 is reserved for the one condition a person must act on: an identity
    family was published that nobody declared. Everything being unreachable is
    the CURRENT state, reported at exit 0 -- a guard that always fails is a
    guard everybody learns to ignore.
    """

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)

    def _run(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = cli.main(["reach", "--root", str(self.dir)])
        return code, json.loads(buffer.getvalue())

    def test_a_known_but_unreachable_surface_exits_zero_and_reports_it(self):
        (self.dir / "a.json").write_text(json.dumps(
            _snapshot(parameters=[("max_span_mm", "mfr/certainteed")])))
        code, report = self._run()
        self.assertEqual(code, 0)
        self.assertEqual(report["worst"]["unreachable_objects"], 1)

    def test_an_undeclared_identity_exits_one(self):
        (self.dir / "a.json").write_text(json.dumps(
            _snapshot(parameters=[("max_span_mm", "mfr/brand-new-co")])))
        code, report = self._run()
        self.assertEqual(code, 1)
        self.assertEqual(report["unknown_identities"], ["mfr/brand-new-co"])

    def test_nothing_to_check_is_not_a_pass(self):
        code, _ = self._run()
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
