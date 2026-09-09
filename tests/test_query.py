"""The query surface — "here is the situation, what applies, and on what evidence?"

`docs/knowledge-loop.md` §3 and §10 item 2. This is the ANSWER side only: a
function, not a route. Planning owes us a request shape (`conversation.md` T58
§3, *"we will send you a request shape rather than assume one"*), so wrapping
this in HTTP now would be building to a guess.

Two things agreed at the boundary are requirements here, not niceties, and each
gets a test that fails without it:

* **The refs come back explicitly, as a list.** T59 §2: *"a query response must
  return its refs explicitly, as a list the caller can hold and compare against,
  not merely embedded in prose or implied by a value. Otherwise your check has
  nothing to match."* Planning's grounding rule is *a claim may only cite what
  that task run's view returned* (T58 §2), so a ref that reaches a finding
  without reaching the list is a citation their check will refuse.
* **The answer names the snapshot it was computed from.** T58 §3: that was the
  single condition on which a served query was admitted at all.

The third property is this repository's own, and it is the one most easily lost
by accident: **conflicts are surfaced, never resolved**
(`docs/target-architecture.md` §5.2). Two published rows disagreeing at one
point must both come back, labelled, with no winner picked.

Applicability is deliberately NOT a number. `docs/knowledge-loop.md` §11 lists
graded applicability as undesigned — *"today the system can say 'exact match' or
'no rule'. It cannot say 'weaker evidence'."* So a finding reports **what
matched and what did not**, and the provenance the row already carries, and
refuses to collapse either into a score.

Everything here runs against synthetic snapshot payloads shaped exactly like
the stored ones. The retrieval half is in `test_query_gold.py`, which needs a
store.
"""
import unittest

import context  # noqa: F401  -- puts the repo root on sys.path
from fence_evidence.query import QueryRefused, Situation, answer_query

SHA_A = "a" * 64
SHA_B = "b" * 64

REF_A1 = {"id": "1111111111111111", "belongs_to": SHA_A}
REF_A2 = {"id": "2222222222222222", "belongs_to": SHA_A}
REF_B1 = {"id": "3333333333333333", "belongs_to": SHA_B}


def quantity(mm: int, raw: str) -> dict:
    return {"amount_milli": mm * 1000, "unit": "mm", "value_raw": [raw]}


def height_range(*, max_mm=None, min_mm=None, raw="Up to 48\""):
    return {"min": quantity(min_mm, raw) if min_mm else None,
            "min_inclusive": True,
            "max": quantity(max_mm, raw) if max_mm else None,
            "max_inclusive": True,
            "value_raw": [raw]}


def row(*, value, conditions, cites, authority=SHA_A, curation_level=2,
        source_class="sealed_approval", version_status="active"):
    return {
        "authority": authority,
        "condition_basis": "stated",
        "conditions": conditions,
        "provenance": {"cites": list(cites), "curation_level": curation_level,
                       "source_class": source_class,
                       "version_status": version_status},
        "valid_from": None,
        "valid_until": None,
        "value": value,
    }


def parameter_table(*, parameter="footing_depth_mm", scope_id="mfr/acme-privacy",
                    rows, task="structural_parameter",
                    condition_scope=None, domain=None):
    dims = condition_scope or {"exposure_category": "site"}
    return {
        "condition_scope": dict(dims),
        "domain": domain or {"exposure_category": ["B", "C", "D"]},
        "domain_basis": "measured",
        "hit_policy": "unique",
        "parameter": parameter,
        "rows": list(rows),
        "scope": {"kind": "fence_model", "id": scope_id, "tenant": None},
        "task": task,
        "uncovered": [],
        "value_type": "quantity(mm)",
    }


def snapshot(*, parameters=(), procedures=(), snapshot_id="s" * 64):
    return {
        "snapshot_id": snapshot_id,
        "contract_version": "1.3.0",
        "tenant": "default",
        "regime": "us_astm",
        "parameters": list(parameters),
        "procedures": list(procedures),
        "parts": [], "part_types": [], "models": [], "rules": [],
        "combinations": [], "source_docs": [], "warnings": [], "gaps": [],
    }


ONE_TABLE = snapshot(parameters=[parameter_table(rows=[
    row(value=quantity(610, '24"'), conditions={"exposure_category": "B"},
        cites=[REF_A1]),
    row(value=quantity(762, '30"'), conditions={"exposure_category": "C"},
        cites=[REF_A2]),
])])


class TestNamingTheSnapshot(unittest.TestCase):
    """T58 §3 — the condition on which a served query was admitted at all."""

    def test_the_answer_carries_the_id_of_the_snapshot_it_read(self):
        answer = answer_query(Situation(conditions={"exposure_category": "C"}),
                              snapshot=ONE_TABLE)
        self.assertEqual(answer.snapshot_id, "s" * 64)

    def test_a_query_naming_no_snapshot_is_refused(self):
        with self.assertRaises(QueryRefused):
            answer_query(Situation(conditions={"exposure_category": "C"}))

    def test_the_id_survives_serialisation(self):
        answer = answer_query(Situation(conditions={"exposure_category": "C"}),
                              snapshot=ONE_TABLE)
        self.assertEqual(answer.to_dict()["snapshot_id"], "s" * 64)

    def test_naming_both_a_payload_and_an_id_is_refused(self):
        with self.assertRaises(QueryRefused):
            answer_query(Situation(), snapshot=ONE_TABLE, snapshot_id="s" * 64)


class TestRefsAreExplicit(unittest.TestCase):
    """T59 §2 — the list is what Planning's grounding check matches against."""

    def answer(self):
        return answer_query(Situation(conditions={"exposure_category": "C"}),
                            snapshot=ONE_TABLE)

    def test_every_ref_a_finding_cites_appears_in_the_explicit_list(self):
        answer = self.answer()
        listed = {r["id"] for r in answer.refs}
        self.assertTrue(answer.values, "expected at least one applicable value")
        for finding in answer.values:
            for cite in finding.cites:
                self.assertIn(cite["id"], listed,
                              f"{cite['id']} cited but not returned in refs")

    def test_the_list_carries_nothing_the_answer_does_not_cite(self):
        """A ref the caller could not have got from the answer is one their
        grounding check would wrongly admit."""
        answer = self.answer()
        cited = {c["id"] for f in answer.values for c in f.cites}
        cited |= {c["id"] for p in answer.procedures for c in p.cites}
        cited |= {h["ref"]["id"] for h in answer.evidence}
        cited |= {c["id"] for k in answer.conflicts for c in k["cites"]}
        self.assertEqual({r["id"] for r in answer.refs}, cited)

    def test_refs_carry_belongs_to_not_only_an_id(self):
        for ref in self.answer().refs:
            self.assertEqual(sorted(ref), ["belongs_to", "id"])

    def test_refs_are_deduplicated_and_ordered(self):
        """Two rows citing one ref must not list it twice: the caller holds
        this as a set to compare against, and a duplicate is noise."""
        shared = snapshot(parameters=[parameter_table(rows=[
            row(value=quantity(610, '24"'), conditions={"exposure_category": "B"},
                cites=[REF_A1]),
            row(value=quantity(762, '30"'), conditions={"exposure_category": "C"},
                cites=[REF_A1]),
        ])])
        answer = answer_query(Situation(), snapshot=shared)
        ids = [r["id"] for r in answer.refs]
        self.assertEqual(ids, sorted(set(ids)))

    def test_the_ref_list_survives_serialisation_as_a_list(self):
        payload = self.answer().to_dict()
        self.assertIsInstance(payload["refs"], list)
        self.assertTrue(all(sorted(r) == ["belongs_to", "id"]
                            for r in payload["refs"]))


class TestApplicability(unittest.TestCase):
    """What matched and what did not — never a score. `knowledge-loop.md` §11."""

    def test_a_stated_condition_the_row_satisfies_reads_as_satisfied(self):
        answer = answer_query(Situation(conditions={"exposure_category": "C"}),
                              snapshot=ONE_TABLE)
        values = [f for f in answer.values
                  if f.conditions.get("exposure_category") == "C"]
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0].applicability["conditions"],
                         "stated_and_satisfied")

    def test_a_row_the_situation_contradicts_is_excluded_not_downgraded(self):
        """Exposure B is a different exposure, not weaker evidence about C."""
        answer = answer_query(Situation(conditions={"exposure_category": "C"}),
                              snapshot=ONE_TABLE)
        self.assertNotIn("B", [f.conditions.get("exposure_category")
                               for f in answer.values])

    def test_an_unstated_dimension_is_reported_rather_than_assumed(self):
        answer = answer_query(Situation(), snapshot=ONE_TABLE)
        self.assertEqual({f.applicability["conditions"] for f in answer.values},
                         {"unstated"})
        self.assertIn("exposure_category", answer.unstated_conditions)

    def test_a_table_scoped_to_another_product_is_labelled_not_dropped(self):
        """`knowledge-loop.md` §1 — a table from another manufacturer is weaker
        evidence, not inapplicable, and the system may not silently decide."""
        answer = answer_query(
            Situation(conditions={"exposure_category": "C"},
                      scope={"kind": "fence_model", "id": "mfr/other-product"}),
            snapshot=ONE_TABLE)
        self.assertTrue(answer.values)
        self.assertEqual({f.applicability["scope"] for f in answer.values},
                         {"other"})

    def test_a_matching_scope_reads_as_exact(self):
        answer = answer_query(
            Situation(conditions={"exposure_category": "C"},
                      scope={"kind": "fence_model", "id": "mfr/acme-privacy"}),
            snapshot=ONE_TABLE)
        self.assertEqual({f.applicability["scope"] for f in answer.values},
                         {"exact"})

    def test_no_declared_scope_says_so_rather_than_claiming_a_match(self):
        answer = answer_query(Situation(conditions={"exposure_category": "C"}),
                              snapshot=ONE_TABLE)
        self.assertEqual({f.applicability["scope"] for f in answer.values},
                         {"not_requested"})

    def test_applicability_carries_no_numeric_score(self):
        answer = answer_query(Situation(conditions={"exposure_category": "C"}),
                              snapshot=ONE_TABLE)
        for finding in answer.values:
            for key, value in finding.applicability.items():
                self.assertNotIsInstance(value, (int, float),
                                         f"applicability[{key!r}] is a score")

    def test_strength_is_the_provenance_the_row_already_carries(self):
        answer = answer_query(Situation(conditions={"exposure_category": "C"}),
                              snapshot=ONE_TABLE)
        strength = answer.values[0].strength
        self.assertEqual(strength["curation_level"], 2)
        self.assertEqual(strength["source_class"], "sealed_approval")
        self.assertEqual(strength["version_status"], "active")


class TestRangeConditions(unittest.TestCase):
    """`fence_height` is published as a bracket, not a scalar, so matching one
    is real arithmetic and must not fall back to string equality."""

    def table(self):
        return snapshot(parameters=[parameter_table(
            condition_scope={"fence_height": "bay"},
            domain={"fence_height": "range(mm)"},
            rows=[
                row(value=quantity(610, '24"'),
                    conditions={"fence_height": height_range(max_mm=1219,
                                                             raw='Up to 48"')},
                    cites=[REF_A1]),
                row(value=quantity(914, '36"'),
                    conditions={"fence_height": height_range(min_mm=1220,
                                                             max_mm=1829,
                                                             raw='49" to 72"')},
                    cites=[REF_A2]),
            ])])

    def test_a_height_inside_a_bracket_selects_that_row(self):
        answer = answer_query(
            Situation(conditions={"fence_height": {"amount_milli": 1_100_000,
                                                   "unit": "mm"}}),
            snapshot=self.table())
        self.assertEqual([f.value["amount_milli"] for f in answer.values],
                         [610000])

    def test_a_height_above_every_bracket_answers_with_nothing_not_the_nearest(self):
        """Phase 7's own criterion: "outside documented range" rather than a
        nearest-neighbour value."""
        answer = answer_query(
            Situation(conditions={"fence_height": {"amount_milli": 3_000_000,
                                                   "unit": "mm"}}),
            snapshot=self.table())
        self.assertEqual(answer.values, ())
        self.assertIn("fence_height", answer.outside_domain)


class TestConflictsSurfaced(unittest.TestCase):
    """`target-architecture.md` §5.2 — surfaced, never resolved."""

    def disagreeing(self):
        return snapshot(parameters=[
            parameter_table(scope_id="mfr/acme-privacy", rows=[
                row(value=quantity(610, '24"'),
                    conditions={"exposure_category": "C"}, cites=[REF_A1])]),
            parameter_table(scope_id="mfr/acme-privacy", rows=[
                row(value=quantity(914, '36"'),
                    conditions={"exposure_category": "C"}, cites=[REF_B1],
                    authority=SHA_B,
                    source_class="manufacturer_installation_instruction")]),
        ])

    def test_both_values_come_back(self):
        answer = answer_query(Situation(conditions={"exposure_category": "C"}),
                              snapshot=self.disagreeing())
        self.assertEqual({f.value["amount_milli"] for f in answer.values},
                         {610000, 914000})

    def test_the_disagreement_is_named_as_a_conflict(self):
        answer = answer_query(Situation(conditions={"exposure_category": "C"}),
                              snapshot=self.disagreeing())
        self.assertEqual(len(answer.conflicts), 1)
        self.assertEqual(answer.conflicts[0]["parameter"], "footing_depth_mm")

    def test_a_conflict_cites_every_side_of_it(self):
        answer = answer_query(Situation(conditions={"exposure_category": "C"}),
                              snapshot=self.disagreeing())
        self.assertEqual({c["id"] for c in answer.conflicts[0]["cites"]},
                         {REF_A1["id"], REF_B1["id"]})

    def test_agreement_on_one_value_is_not_a_conflict(self):
        agreeing = snapshot(parameters=[
            parameter_table(rows=[row(value=quantity(610, '24"'),
                                      conditions={"exposure_category": "C"},
                                      cites=[REF_A1])]),
            parameter_table(rows=[row(value=quantity(610, '24"'),
                                      conditions={"exposure_category": "C"},
                                      cites=[REF_B1], authority=SHA_B)]),
        ])
        answer = answer_query(Situation(conditions={"exposure_category": "C"}),
                              snapshot=agreeing)
        self.assertEqual(answer.conflicts, ())

    def test_nothing_is_ranked_away(self):
        """A sealed approval outranks an install guide in the source policy, and
        that ordering must not become a silent deletion here."""
        answer = answer_query(Situation(conditions={"exposure_category": "C"}),
                              snapshot=self.disagreeing())
        self.assertEqual(len(answer.values), 2)

    def test_a_disagreement_across_products_is_not_a_conflict(self):
        """Two products with different footings do not contradict each other."""
        across = snapshot(parameters=[
            parameter_table(scope_id="mfr/acme-privacy", rows=[
                row(value=quantity(610, '24"'),
                    conditions={"exposure_category": "C"}, cites=[REF_A1])]),
            parameter_table(scope_id="mfr/other-product", rows=[
                row(value=quantity(914, '36"'),
                    conditions={"exposure_category": "C"}, cites=[REF_B1],
                    authority=SHA_B)]),
        ])
        answer = answer_query(Situation(conditions={"exposure_category": "C"}),
                              snapshot=across)
        self.assertEqual(answer.conflicts, ())


class TestProcedures(unittest.TestCase):
    """§3 — the query returns values AND procedures. The store publishes none
    today, so this asserts the shape carries one when it does."""

    def procedure_snapshot(self, scope_id="mfr/acme-privacy"):
        return snapshot(procedures=[{
            "id": "proc-abc123",
            "scope": {"kind": "fence_model", "id": scope_id, "tenant": None},
            "cites": [REF_A1],
            "steps": [{"key": "step-000000000001", "kind": "step",
                       "scope": "panel", "slots": [], "requires": [],
                       "cites": [REF_A2],
                       "text_i18n": "Set the post before the rail."}],
        }])

    def test_a_published_procedure_comes_back(self):
        answer = answer_query(Situation(), snapshot=self.procedure_snapshot())
        self.assertEqual([p.id for p in answer.procedures], ["proc-abc123"])

    def test_a_step_keeps_its_verbatim_text_and_its_citation(self):
        answer = answer_query(Situation(), snapshot=self.procedure_snapshot())
        step = answer.procedures[0].steps[0]
        self.assertEqual(step["text_i18n"], "Set the post before the rail.")
        self.assertEqual(step["cites"], [REF_A2])

    def test_step_citations_reach_the_explicit_ref_list(self):
        answer = answer_query(Situation(), snapshot=self.procedure_snapshot())
        listed = {r["id"] for r in answer.refs}
        self.assertIn(REF_A1["id"], listed)
        self.assertIn(REF_A2["id"], listed)

    def test_a_procedure_for_another_product_is_labelled_not_dropped(self):
        answer = answer_query(
            Situation(scope={"kind": "fence_model", "id": "mfr/acme-privacy"}),
            snapshot=self.procedure_snapshot(scope_id="mfr/somebody-else"))
        self.assertEqual([p.applicability["scope"] for p in answer.procedures],
                         ["other"])

    def test_an_empty_procedures_member_answers_with_none_rather_than_failing(self):
        answer = answer_query(Situation(), snapshot=ONE_TABLE)
        self.assertEqual(answer.procedures, ())


class TestRefusals(unittest.TestCase):
    def test_an_unknown_condition_dimension_is_refused_not_ignored(self):
        """A dimension we do not carry, silently dropped, turns a narrow
        question into a broad answer with no warning."""
        with self.assertRaises(QueryRefused):
            answer_query(Situation(conditions={"soil_ph": "7"}),
                         snapshot=ONE_TABLE)

    def test_the_refusal_names_the_dimension(self):
        with self.assertRaises(QueryRefused) as caught:
            answer_query(Situation(conditions={"soil_ph": "7"}),
                         snapshot=ONE_TABLE)
        self.assertIn("soil_ph", str(caught.exception))

    def test_a_tombstoned_snapshot_answers_nothing(self):
        stone = {"snapshot_id": "t" * 64, "tombstoned": True,
                 "reason": "excised"}
        with self.assertRaises(QueryRefused):
            answer_query(Situation(), snapshot=stone)

    def test_a_scope_without_a_kind_is_refused(self):
        with self.assertRaises(QueryRefused):
            answer_query(Situation(scope={"id": "mfr/acme-privacy"}),
                         snapshot=ONE_TABLE)


class TestCurrencyComesFromTheGraphNotTheLabel(unittest.TestCase):
    """`knowledge-loop.md` §3, on why the query lives on this side at all:

        *"retrieval here is not fetch-by-id. It means knowing which condition
        dimensions apply, that currency comes from the supersession graph and
        not from the `version_status` label, that five tables agreeing is
        corroboration rather than redundancy … The semantics stay where the
        expertise is."*

    The first cut did the opposite on every count. It exposed the label and
    never touched the graph, and the effect on real data was not academic: the
    only row graded `scope: "exact"` for Chesterfield is an approval that
    EXPIRED IN 2018, while the in-force 2025 approval for the same lineage
    grades `"other"` -- the same grade as a table for a different product
    entirely. Both are published, both carry identical values, and a caller
    ranking `exact` over `other` (the only ordering the answer offers) picks the
    expired one.

    The cause is upstream and is not fixed here: `parameters._default_scope`
    mints a `fence_model` id by slugging each document's own manufacturer and
    product family, and every edition of one approval lineage names a slightly
    different model list, so each edition lands on a different id. Nothing
    published says those ids are one product line -- `models` and
    `combinations` are both 0.

    What IS fixed here is that the answer stops making the caller do the join.
    The snapshot already carries `source_docs[].superseded_by`, and
    `contract.md` §1.1 says `SourceRef.belongs_to` exists precisely so this join
    is possible -- *"without it an opaque id carries zero admissibility bits
    into a pinned snapshot, and a run cannot tell that three of a definition's
    five citations are superseded approvals."* So the join is made here, from
    the pinned snapshot rather than the live store: deterministic, and it does
    not inherit `relations.supersession_chain`'s DAG bug, which takes one
    arbitrary path per hop and silently drops chain members.
    """

    OLD, NEW = "a" * 64, "b" * 64

    def snapshot(self, *, include_replacement=True, source_docs=True,
                 old_label="superseded"):
        tables = [parameter_table(
            scope_id="mfr/old-model-names",
            rows=[row(value=quantity(762, '30"'),
                      conditions={"exposure_category": "C"},
                      cites=[{"id": "1111111111111111", "belongs_to": self.OLD}],
                      authority=self.OLD, version_status=old_label)])]
        if include_replacement:
            tables.append(parameter_table(
                scope_id="mfr/new-model-names",
                rows=[row(value=quantity(762, '30"'),
                          conditions={"exposure_category": "C"},
                          cites=[{"id": "2222222222222222",
                                  "belongs_to": self.NEW}],
                          authority=self.NEW, version_status="unknown")]))
        snap = snapshot(parameters=tables)
        if source_docs:
            snap["source_docs"] = [
                {"content_hash": self.OLD, "source_class": "sealed_approval",
                 "version_status": "superseded", "superseded_by": [self.NEW],
                 "also_filed_as": []},
                {"content_hash": self.NEW, "source_class": "sealed_approval",
                 "version_status": "unknown", "superseded_by": [],
                 "also_filed_as": []},
            ]
        return snap

    def ask(self, **kwargs):
        return answer_query(
            Situation(conditions={"exposure_category": "C"},
                      scope={"kind": "fence_model", "id": "mfr/old-model-names"}),
            snapshot=self.snapshot(**kwargs))

    def old(self, answer):
        return [f for f in answer.values if f.strength["authority"] == self.OLD][0]

    def test_a_superseded_value_names_what_replaced_it(self):
        self.assertEqual(self.old(self.ask()).currency["superseded_by"],
                         [self.NEW])

    def test_a_value_nothing_supersedes_says_so_with_an_empty_list(self):
        answer = self.ask()
        new = [f for f in answer.values if f.strength["authority"] == self.NEW][0]
        self.assertEqual(new.currency["superseded_by"], [])

    def test_the_replacement_present_in_the_same_answer_is_named(self):
        """The Chesterfield trap: the replacement is right there, under a
        different scope id, graded `other`."""
        self.assertEqual(
            self.old(self.ask()).currency["superseded_by_in_answer"],
            [{"parameter": "footing_depth_mm", "authority": self.NEW,
              "scope_id": "mfr/new-model-names",
              "applicability": {"scope": "other",
                                "conditions": "stated_and_satisfied"}}])

    def test_a_replacement_absent_from_the_answer_is_an_empty_list_not_a_lie(self):
        answer = self.ask(include_replacement=False)
        currency = self.old(answer).currency
        self.assertEqual(currency["superseded_by"], [self.NEW])
        self.assertEqual(currency["superseded_by_in_answer"], [])

    def test_the_graph_wins_over_the_label(self):
        """A row whose own provenance calls itself active is still superseded
        if the snapshot's graph says so. That is the whole rule."""
        answer = self.ask(old_label="active")
        finding = self.old(answer)
        self.assertEqual(finding.strength["version_status"], "active")
        self.assertEqual(finding.currency["superseded_by"], [self.NEW])
        self.assertEqual(finding.currency["basis"], "supersession_graph")

    def test_without_source_docs_it_reports_the_label_and_says_that_is_all(self):
        """A snapshot with no `source_docs` is not an assertion that nothing is
        superseded -- it is an absence, and the answer must not read as the
        former."""
        finding = self.old(self.ask(source_docs=False))
        self.assertEqual(finding.currency["superseded_by"], [])
        self.assertEqual(finding.currency["basis"], "version_status_label_only")

    def test_the_answer_counts_how_many_exact_findings_are_superseded(self):
        """One number that names the trap: every exactly-scoped answer you have
        is out of date."""
        answer = self.ask()
        self.assertEqual(answer.basis["exact_findings"], 1)
        self.assertEqual(answer.basis["exact_findings_superseded"], 1)

    def test_currency_adds_no_refs(self):
        answer = self.ask()
        cited = {c["id"] for f in answer.values for c in f.cites}
        self.assertEqual({r["id"] for r in answer.refs}, cited)


if __name__ == "__main__":
    unittest.main()
