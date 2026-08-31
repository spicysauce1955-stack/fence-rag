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
                         "issue_date": None, "expiration_date": None,
                         # C2: required, not optional. An absent key is
                         # indistinguishable from "these bytes are filed once".
                         "also_filed_as": []}],
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

    def test_a_typed_date_passes(self):
        """Amendment 002: `issue_date`/`expiration_date` are `Date` dicts, not
        bare strings -- including the ambiguous case, `iso: null` beside the
        lexeme it could not resolve."""
        s = _ok()
        s["source_docs"][0].update(
            issue_date={"iso": "2023-05-04", "value_raw": ["05/04/2023"]},
            expiration_date={"iso": None, "value_raw": ["05/04/2023"]})
        verify(s)                           # must not raise


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


def _gap(**over):
    """A well-formed gap, for tests that break exactly one thing about it."""
    g = {"id": "g1", "kind": "illegible_source", "subject": {"kind": "element", "id": "element-x-0001", "tenant": None},
         "because": {"code": "warning_truncated_mid_clause", "params": {}},
         "cites": [{"id": "r1", "belongs_to": "h1"}],
         "would_close": "read the page image and record the sentence whole",
         "closes_by": "knowledge", "severity": "warns_line", "on": None}
    g.update(over)
    return g


class TestGapCarriesItsReasonAndEvidence(unittest.TestCase):
    """Defect 1: 63 gaps shipped with no `because` and no `cites`.

    `would_close` alone is a sentence in one language. §1.2.1 requires
    `because` as code + params precisely so a gap "renders in both locales",
    and obligation 8 wants the evidence beside it. A snapshot had already been
    published without either, which is why this is a gate and not a report.
    """

    def _fails(self, gap, fragment):
        snap = _ok()
        snap["gaps"] = [gap]
        with self.assertRaises(VerificationFailed) as caught:
            verify(snap)
        self.assertIn(fragment, str(caught.exception))

    def test_a_well_formed_gap_passes(self):
        snap = _ok()
        snap["gaps"] = [_gap()]
        verify(snap)

    def test_a_gap_without_because_is_refused(self):
        self._fails(_gap(because={}), "renders in both locales")
        self._fails(_gap(because={"code": "", "params": {}}), "renders in both locales")

    def test_because_code_must_be_lower_snake_case(self):
        """Planning's four existing gap codes set the convention."""
        self._fails(_gap(because={"code": "WARNING_TRUNCATED", "params": {}}),
                    "lower_snake_case")

    def test_an_element_scoped_gap_must_cite_its_region(self):
        """It names a rectangle of a page, so it has evidence by construction."""
        self._fails(_gap(cites=[]), "names a region")

    def test_a_document_scoped_gap_may_cite_nothing(self):
        """There is no region to point at, and §1.2.1 says "where there is any"."""
        snap = _ok()
        snap["gaps"] = [_gap(subject={"kind": "source_document", "id": "doc-abc123", "tenant": None}, cites=[])]
        verify(snap)

    def test_absent_cites_is_refused_even_though_empty_is_allowed(self):
        g = _gap(subject={"kind": "source_document", "id": "doc-abc123", "tenant": None})
        del g["cites"]
        self._fails(g, "publish [] rather than omitting it")

    def test_disputed_must_say_what_is_disputed(self):
        self._fails(_gap(kind="disputed", on=None), "`on` belongs to `disputed`")

    def test_only_disputed_carries_on(self):
        self._fails(_gap(on="value"), "`on` belongs to `disputed`")

    def test_a_disputed_gap_with_on_passes(self):
        snap = _ok()
        snap["gaps"] = [_gap(kind="disputed", on="conditions")]
        verify(snap)



# A sentinel: "the key is not there at all", which is a different failure from
# "the key is there and empty" and is the one §5 has to refuse.
_ABSENT = object()


class TestAlsoFiledAsIsGated(unittest.TestCase):
    """registry-additions.md §5: one `source_class` per content hash.

    A gate rather than a report, and for the reason §1.4 gives: Planning ranks
    on `source_class`, so where identical bytes are filed twice under different
    `doc_type` values -- 18 of the 40 `same_content_as` edges here -- the same
    evidence is admissible or not according to which record the SourceDoc was
    built from. Nothing downstream can notice, which is what makes it worth a
    refusal rather than a warning.

    What this cannot check is stated in `_also_filed_as`'s docstring and tested
    on the builder side instead: `SourceDoc` publishes no `manufacturer` and no
    `doc_type` of its own, so a finished snapshot carries nothing to compare an
    entry against to see whether it repeats the doc's own filing.
    """

    def _fails(self, also, fragment):
        s = _ok()
        if also is _ABSENT:
            del s["source_docs"][0]["also_filed_as"]
        else:
            s["source_docs"][0]["also_filed_as"] = also
        with self.assertRaises(VerificationFailed) as caught:
            verify(s)
        self.assertIn(fragment, str(caught.exception))

    def test_an_empty_list_passes(self):
        """Bytes filed once. Empty is the normal case, not a degenerate one."""
        verify(_ok())

    def test_a_well_formed_list_passes(self):
        s = _ok()
        s["source_docs"][0]["also_filed_as"] = [
            {"manufacturer": "Barrette Outdoor Living", "doc_type": "hvhz_noa"},
            {"manufacturer": "Freedom Outdoor Living", "doc_type": "unspecified"}]
        verify(s)

    def test_an_absent_field_is_refused(self):
        self._fails(_ABSENT, "Publish [] rather than omitting it")

    def test_an_entry_is_exactly_manufacturer_and_doc_type(self):
        self._fails([{"manufacturer": "Barrette"}], "exactly")
        self._fails([{"manufacturer": "Barrette", "doc_type": "hvhz_noa",
                      "source_path": "manuals/x.pdf"}], "exactly")
        self._fails(["Barrette"], "exactly")

    def test_an_empty_string_is_neither_a_name_nor_a_null(self):
        self._fails([{"manufacturer": "", "doc_type": "hvhz_noa"}],
                    "a filing names it or says null")

    def test_a_doc_type_with_no_source_class_is_refused(self):
        """The defect in miniature: a filing nobody can rank cannot be
        reconciled against the class that was published."""
        self._fails([{"manufacturer": "Barrette", "doc_type": "vibes"}],
                    "maps to no source_class")

    def test_the_same_filing_listed_twice_is_refused(self):
        """The document id is not published, so a repeated pair carries nothing
        and reads as two filings that disagree."""
        pair = {"manufacturer": "Barrette", "doc_type": "hvhz_noa"}
        self._fails([pair, dict(pair)], "listed twice")

    def test_an_unstable_order_is_refused(self):
        """`canonical_bytes` hashes this list as given, so its order is part of
        the snapshot id and is not free."""
        self._fails([{"manufacturer": "Freedom", "doc_type": "unspecified"},
                     {"manufacturer": "Barrette", "doc_type": "hvhz_noa"}],
                    "is not in (manufacturer, doc_type) order")

    def test_a_null_manufacturer_is_allowed_and_sorts_first(self):
        """Both fields are nullable in the store; a catalogue that does not say
        who filed something is a gap in the catalogue, not a malformed field."""
        s = _ok()
        s["source_docs"][0]["also_filed_as"] = [
            {"manufacturer": None, "doc_type": "spec_sheet"},
            {"manufacturer": "Barrette", "doc_type": "hvhz_noa"}]
        verify(s)


class TestTheGateEnforcesWhatTheContractBinds(unittest.TestCase):
    """Holes an adversarial contract pass found in `verify()`.

    Each was a check the contract states and the gate did not make. They are
    not live defects today -- the builder emits neither kind, and every stored
    hash happens to close -- but "happens to" is the distinction a gate exists
    to remove, and the seven unpopulated lists mean the gate passes for the
    wrong reason until the day they are filled.
    """

    def _fails(self, mutate, fragment):
        snap = _ok()
        mutate(snap)
        with self.assertRaises(VerificationFailed) as caught:
            verify(snap)
        self.assertIn(fragment, str(caught.exception))

    def test_a_kind_that_closes_by_a_planning_schema_change_must_say_so(self):
        """§1.2.1 BINDING, and the property a review queue has to have."""
        for kind in ("unmodellable_entity", "unmapped_part_kind"):
            with self.subTest(kind=kind):
                self._fails(lambda s, k=kind: s.__setitem__(
                    "gaps", [_gap(kind=k, closes_by="knowledge")]),
                    "closes by a schema change")

    def test_that_kind_passes_when_it_does_say_so(self):
        snap = _ok()
        snap["gaps"] = [_gap(kind="unmodellable_entity", closes_by="planning")]
        verify(snap)

    def test_severity_is_a_closed_set(self):
        self._fails(lambda s: s.__setitem__("gaps", [_gap(severity="critical")]),
                    "warns_line|informational")

    def test_severity_is_required(self):
        g = _gap()
        del g["severity"]
        self._fails(lambda s: s.__setitem__("gaps", [g]), "warns_line|informational")

    def test_closure_sees_a_hash_carried_as_a_string(self):
        """`superseded_by` exists BECAUSE a doc- id is unresolvable to Planning.

        A walk keyed on the {id, belongs_to} pair could not see it, nor
        `attaches_to.ref`, which is a content hash on every published warning.
        """
        self._fails(lambda s: s["source_docs"][0].__setitem__(
            "superseded_by", ["deadbeef" * 8]), "not in source_docs")

    def test_closure_sees_attaches_to(self):
        self._fails(lambda s: s["warnings"][0]["attaches_to"].__setitem__(
            "ref", "deadbeef" * 8), "attaches_to names")

    def test_closure_sees_contributing_sources(self):
        """§1.2.1 names it as a roll-up of the same source_docs."""
        self._fails(lambda s: s.__setitem__(
            "parts", [{"contributing_sources": ["deadbeef" * 8]}]),
            "not in source_docs")

    def test_a_gap_names_its_subject(self):
        self._fails(lambda s: s.__setitem__("gaps", [_gap(subject={})]),
                    "names its subject")

    def test_because_params_must_be_an_object(self):
        self._fails(lambda s: s.__setitem__(
            "gaps", [_gap(because={"code": "c", "params": "not a dict"})]),
            "must be an object")

