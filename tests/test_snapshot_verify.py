"""The obligations as a gate, not a report.

A snapshot that fails an obligation is not returned. That is the difference
between a check and a gate, and it matters because the failure mode of a bad
snapshot is silent: Planning pins a hash, computes against it, and produces
numbers. Nothing downstream is in a position to notice.

What this can and cannot establish is worth stating plainly at the top, because
conflating the two is the exact error the promotion gate was moved to close:

  Structural validity is testable.  Semantic correspondence is reviewable.

Every check below passes on a snapshot that confidently attributes the wrong
footing depth to the wrong post, because the builder faithfully published what a
person accepted and the person was wrong. A green verify proves the object is
well-formed. It proves nothing about whether it is true.
"""
import unittest

import context  # noqa: F401  -- puts the repo root on sys.path
from context import requires_store
from fence_evidence.snapshot import VerificationFailed, verify


def _ok():
    return {
        "snapshot_id": "a" * 64, "tenant": "t", "regime": "us_astm",
        "spine_version": "0.1.0", "contract_version": "1.1.0",
        "policy_version": "0.1.0", "retain_until": "2028-01-01",
        "source_docs": [{"content_hash": "h1", "source_class": "spec_sheet",
                         "version_status": "unknown", "version_status_basis": None,
                         "issue_date": None, "expiration_date": None}],
        "warnings": [{"text_raw": "CAUTION: wear eye protection at all times.",
                      "lang": "en", "severity_lexeme": "CAUTION",
                      "attaches_to": {"kind": "document", "ref": "h1"},
                      "cites": [{"id": "r1", "belongs_to": "h1"}]}],
        "gaps": [], "part_types": [], "parts": [], "models": [],
        "procedures": [], "parameters": [], "combinations": [], "rules": [],
    }


class TestVerifyAccepts(unittest.TestCase):
    def test_a_well_formed_snapshot_passes(self):
        verify(_ok())                       # must not raise

    def test_an_empty_snapshot_passes(self):
        """A snapshot containing very little is still a valid snapshot."""
        s = _ok()
        s["warnings"] = []
        s["source_docs"] = []
        verify(s)


class TestVerifyRefuses(unittest.TestCase):
    def _fails(self, mutate, expect):
        s = _ok()
        mutate(s)
        with self.assertRaises(VerificationFailed) as ctx:
            verify(s)
        self.assertIn(expect, str(ctx.exception).lower())

    def test_closure_a_cite_outside_the_snapshot(self):
        def m(s):
            s["warnings"][0]["cites"] = [{"id": "r1", "belongs_to": "not-here"}]
        self._fails(m, "closure")

    def test_obligation_3_a_value_with_no_source_ref(self):
        self._fails(lambda s: s["warnings"][0].update(cites=[]), "obligation 3")

    def test_obligation_10_a_warning_with_no_lang(self):
        self._fails(lambda s: s["warnings"][0].update(lang=""), "obligation 10")

    def test_obligation_10_a_warning_with_no_attaches_to(self):
        self._fails(lambda s: s["warnings"][0].pop("attaches_to"), "obligation 10")

    def test_obligation_10_an_illegal_attaches_to_kind(self):
        def m(s):
            s["warnings"][0]["attaches_to"] = {"kind": "elephant", "ref": "h1"}
        self._fails(m, "attaches_to")

    def test_obligation_8_a_gap_with_no_would_close(self):
        def m(s):
            s["gaps"] = [{"id": "g", "kind": "missing_value", "subject": "x",
                          "would_close": "", "closes_by": "knowledge",
                          "severity": "warns_line"}]
        self._fails(m, "obligation 8")

    def test_obligation_8_an_unknown_gap_kind(self):
        def m(s):
            s["gaps"] = [{"id": "g", "kind": "vibes", "subject": "x",
                          "would_close": "y", "closes_by": "knowledge",
                          "severity": "warns_line"}]
        self._fails(m, "gap kind")

    def test_a_regime_that_is_not_one_of_the_two(self):
        self._fails(lambda s: s.update(regime="eu_en"), "regime")

    def test_a_source_class_outside_the_closed_vocabulary(self):
        self._fails(lambda s: s["source_docs"][0].update(source_class="vibes"),
                    "source_class")

    def test_version_status_coerced_to_active(self):
        """`unknown` is a real value ranking below `active`, never coerced to it."""
        self._fails(lambda s: s["source_docs"][0].update(version_status="probably"),
                    "version_status")

    def test_a_float_anywhere(self):
        """No floating-point number crosses in either direction."""
        self._fails(lambda s: s["warnings"][0].update(confidence=0.87), "float")

    def test_a_duplicate_source_doc(self):
        self._fails(lambda s: s["source_docs"].append(dict(s["source_docs"][0])),
                    "duplicate")

    def test_a_missing_declared_list(self):
        """An absent key reads as an oversight; an empty list reads as a decision."""
        self._fails(lambda s: s.pop("parameters"), "parameters")


@requires_store
class TestTheRealBuildPasses(unittest.TestCase):
    def test_the_built_snapshot_verifies(self):
        from fence_evidence.snapshot import build_snapshot
        verify(build_snapshot(tenant="acme"))

    def test_build_runs_verify_itself(self):
        """The gate is inside the builder, so a caller cannot skip it."""
        import inspect
        from fence_evidence import snapshot
        self.assertIn("verify(", inspect.getsource(snapshot.build_snapshot))


if __name__ == "__main__":
    unittest.main()
