"""A scope naming a model we do not publish must say so, not dangle silently.

`[measured]` 2026-09-14 against snapshot `0e04d171`: all 9 published
`ParameterTable`s carry `scope.kind == "fence_model"`, referencing 7 distinct
ids, and the snapshot publishes **0** `FenceModel`s. Every scope reference
points at an object that does not exist, and nothing said so.

Publishing the models is not honestly available: `FENCE_MODEL_SHAPE` requires
`grade`, `height_support` and `default_spec`, and this platform holds none of
them for these products -- they are read off footing tables in Miami-Dade
approvals, which state a schedule and never a panel definition. Inventing them
is the G62 shape.

So the reference stands and the gap is declared, which is what this platform
does everywhere else it cannot complete something: publish at the weakest
honest reading and name what is missing (obligation 8). A consumer can then see
that the product identity is asserted but undefined, instead of resolving it and
finding nothing.
"""
import unittest

from context import ROOT, requires_full_store  # noqa: F401


class TestEveryModelScopeResolvesOrIsDeclared(unittest.TestCase):
    @classmethod
    @requires_full_store
    def setUpClass(cls):
        from fence_evidence.snapshot import build_snapshot
        snap = build_snapshot(tenant="default")
        cls.snap = snap if isinstance(snap, dict) else (
            getattr(snap, "payload", None) or snap.__dict__)

    @requires_full_store
    def test_a_scope_naming_an_unpublished_model_raises_a_gap(self):
        """The measured defect: 9 scope refs, 0 models, 0 gaps about it.

        Fails if a `fence_model` scope is published with neither the model nor
        a gap naming it -- which is a reference a consumer resolves to nothing,
        with no signal that it was ever going to.
        """
        published = {m.get("id") for m in self.snap.get("models") or []}
        declared = {((g.get("because") or {}).get("params") or {}).get("scope_id")
                    for g in self.snap.get("gaps") or []
                    if (g.get("because") or {}).get("code") == "scope_model_undefined"}
        dangling = set()
        for table in self.snap.get("parameters") or []:
            scope = table.get("scope") or {}
            if scope.get("kind") != "fence_model":
                continue
            if scope.get("id") not in published and scope.get("id") not in declared:
                dangling.add(scope.get("id"))
        self.assertEqual(dangling, set(),
                         "scope ids referencing a model that is neither "
                         "published nor declared missing")

    @requires_full_store
    def test_the_gap_names_the_scope_a_consumer_would_try_to_resolve(self):
        """A gap that does not carry the id is not actionable.

        The consumer's question is "what is `mfr/certainteed-…`?" -- the gap has
        to answer with that id, not merely report that some model is missing.
        """
        gaps = [g for g in self.snap.get("gaps") or []
                if (g.get("because") or {}).get("code") == "scope_model_undefined"]
        self.assertTrue(gaps, "no scope_model_undefined gap was raised at all")
        for g in gaps:
            # `params` rides under `because`, not at the top level -- the same
            # shape the published `code` uses, and the same place a first cut of
            # this test looked for it and missed.
            self.assertTrue(((g.get("because") or {}).get("params") or {}).get("scope_id"),
                            "gap carries no scope_id")
            self.assertTrue(g.get("would_close"), "gap says nothing about closing it")


if __name__ == "__main__":
    unittest.main()
