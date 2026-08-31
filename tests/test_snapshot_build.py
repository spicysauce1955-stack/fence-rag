"""The snapshot builder — closure, determinism, and refusing to publish a lie.

The property that matters most is the one the contract calls the closure rule:

  > BINDING. Every `SourceRef.belongs_to` cited anywhere inside a snapshot
  > resolves to a `SourceDoc` in that snapshot's `source_docs`.

It is binding because §3.2.2 forbids Planning from calling Discovery during a run,
so a dangling `belongs_to` carries zero admissibility bits into a pinned object.
The design answer is not to validate closure afterwards but to make it
*unrepresentable*: minting a reference registers its document, so a builder that
skipped the registration could not produce the reference either.
"""
import re
import unittest

import context  # noqa: F401  -- puts the repo root on sys.path
from context import requires_store
from fence_evidence.snapshot import (SnapshotBuilder, SOURCE_CLASS,
                                     build_snapshot)


class TestSourceClassMapping(unittest.TestCase):
    """19 doc_type values collapse into 8 SourceClass values. Lossy, and the
    source policy ranks on the result, so a wrong entry changes admissibility."""

    def test_every_mapped_value_is_a_real_source_class(self):
        legal = {"sealed_approval", "tested_report", "industry_standard",
                 "manufacturer_installation_instruction", "spec_sheet",
                 "marketing", "company_authored", "ai_proposal"}
        self.assertTrue(set(SOURCE_CLASS.values()) <= legal,
                        f"not a SourceClass: {set(SOURCE_CLASS.values()) - legal}")

    def test_an_approval_outranks_a_manual(self):
        self.assertEqual(SOURCE_CLASS["hvhz_noa"], "sealed_approval")
        self.assertEqual(SOURCE_CLASS["installation_manual"],
                         "manufacturer_installation_instruction")

    @requires_store
    def test_every_doc_type_in_the_store_is_mapped(self):
        """An unmapped doc_type must not silently become `marketing` — that would
        make a sealed approval inadmissible for the task it exists to serve."""
        from fence_evidence.store import connect
        conn = connect()
        try:
            seen = {r[0] for r in conn.execute(
                "SELECT DISTINCT doc_type FROM documents WHERE doc_type IS NOT NULL")}
        finally:
            conn.close()
        missing = seen - set(SOURCE_CLASS)
        self.assertEqual(missing, set(), f"unmapped doc_type values: {sorted(missing)}")


@requires_store
class TestClosureIsStructural(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fence_evidence.store import connect
        cls.conn = connect()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def _one_element(self):
        row = self.conn.execute(
            "SELECT element_id FROM elements WHERE bbox IS NOT NULL LIMIT 1").fetchone()
        return row["element_id"]

    def test_minting_a_ref_registers_its_document(self):
        b = SnapshotBuilder(self.conn, tenant="t", regime="us_astm")
        self.assertEqual(b.source_docs(), [])
        ref = b.source_ref(self._one_element())
        self.assertTrue(any(d.content_hash == ref.belongs_to for d in b.source_docs()),
                        "a ref was minted whose document is not in the snapshot")

    def test_the_same_element_yields_the_same_ref(self):
        b = SnapshotBuilder(self.conn, tenant="t", regime="us_astm")
        eid = self._one_element()
        self.assertEqual(b.source_ref(eid).id, b.source_ref(eid).id)

    def test_a_ref_id_is_a_function_of_what_it_points_at(self):
        """Not a counter, not a uuid. Two builds must mint identical ids."""
        eid = self._one_element()
        a = SnapshotBuilder(self.conn, tenant="t", regime="us_astm").source_ref(eid)
        b = SnapshotBuilder(self.conn, tenant="t", regime="us_astm").source_ref(eid)
        self.assertEqual(a.id, b.id)

    def test_an_unknown_element_raises_rather_than_minting_a_dangling_ref(self):
        b = SnapshotBuilder(self.conn, tenant="t", regime="us_astm")
        with self.assertRaises(KeyError):
            b.source_ref("element-does-not-exist-0000")


@requires_store
class TestParameterGapsCarryTheirCitations(unittest.TestCase):
    """A dormant defect found while wiring PartType/Part: `build_snapshot`'s
    loop over `parameter_gaps` never passed `cites` through to
    `SnapshotBuilder.gap()`, so any real citation `parameters._Gaps.add()`
    computed was silently dropped before reaching the wire. 0 currently-
    published parameter gaps carry cites, so this was invisible -- the next
    disputed/unquantified gap would have shipped uncited."""

    def test_a_parameter_gaps_citation_survives_into_the_built_snapshot(self):
        from unittest.mock import patch

        from fence_evidence.store import connect
        conn = connect()
        try:
            row = conn.execute(
                "SELECT element_id FROM elements WHERE bbox IS NOT NULL "
                "LIMIT 1").fetchone()
            element_id = row["element_id"]

            def fake_build_parameter_tables(conn, *, tenant, source_ref):
                ref = source_ref(element_id)     # mints through the real closure
                return [], [{
                    "kind": "missing_value",
                    "subject": {"kind": "fact_type", "id": "test_fixture",
                               "tenant": None},
                    "because": {"code": "test_fixture_gap", "params": {}},
                    "cites": [ref],
                    "would_close": "this is a test fixture",
                    "closes_by": "knowledge",
                }]

            with patch("fence_evidence.parameters.build_parameter_tables",
                      side_effect=fake_build_parameter_tables):
                snap = build_snapshot(tenant="t", conn=conn)
        finally:
            conn.close()

        fixture = [g for g in snap["gaps"]
                  if g["because"]["code"] == "test_fixture_gap"]
        self.assertEqual(len(fixture), 1)
        self.assertTrue(fixture[0]["cites"],
                        "the citation build_parameter_tables computed was "
                        "dropped before reaching the published snapshot")


@requires_store
class TestBuiltSnapshot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = build_snapshot(tenant="acme", regime="us_astm")

    def test_it_declares_the_contract_it_was_built_against(self):
        for key in ("snapshot_id", "tenant", "regime", "contract_version",
                    "spine_version", "policy_version", "retain_until"):
            self.assertIn(key, self.snap, f"missing {key}")

    def test_exactly_one_regime(self):
        self.assertIn(self.snap["regime"], ("us_astm", "cn_gb"))

    def test_closure_holds_over_the_finished_object(self):
        """The property asserted end-to-end, not just at the mint site."""
        held = {d["content_hash"] for d in self.snap["source_docs"]}
        dangling = []
        def walk(node, path="$"):
            if isinstance(node, dict):
                if "belongs_to" in node and "id" in node:
                    if node["belongs_to"] not in held:
                        dangling.append((path, node["belongs_to"]))
                for k, v in node.items():
                    walk(v, f"{path}.{k}")
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, f"{path}[{i}]")
        walk(self.snap)
        self.assertEqual(dangling, [], "a SourceRef points outside this snapshot")

    def test_every_warning_carries_the_four_required_fields(self):
        for w in self.snap["warnings"]:
            for field in ("text_raw", "lang", "cites", "attaches_to"):
                self.assertTrue(w.get(field) not in (None, "", []),
                                f"warning missing {field}: {w.get('text_raw','')[:40]!r}")

    def test_no_warning_text_was_normalised(self):
        """Obligation 10: text_raw is verbatim and never normalised."""
        for w in self.snap["warnings"]:
            self.assertEqual(w["text_raw"], w["text_raw"].strip("\x00"))
            self.assertNotIn("  \n  ", w["text_raw"].replace("\n", "\n"))

    def test_every_gap_says_what_would_close_it_and_who_can(self):
        for g in self.snap["gaps"]:
            self.assertTrue(g.get("would_close"), f"gap {g.get('id')} has no would_close")
            self.assertIn(g.get("closes_by"), ("knowledge", "planning"))

    def test_would_close_names_the_gap_it_belongs_to(self):
        """G40: would_close must be a work item, not a template constant.

        contract.md 1.2.1 is BINDING on this field and says what it is for:
        "A gap that only says something is missing sends a curator hunting;
        one that says 'a footing row for exposure C, non-HVHZ, at 6 ft' is a
        work item." Before this landed, 63 gaps carried 4 distinct sentences
        and 51 of those were identical -- compliant with the letter, useless
        for the purpose. Planning now also relies on this field to carry the
        reason a condition point is excluded, which no other field holds.
        """
        gaps = self.snap["gaps"]
        sentences = [g["would_close"] for g in gaps]
        distinct = len(set(sentences))
        # Not "all distinct": two gaps could legitimately coincide. But a
        # handful of constants across dozens of gaps is the defect itself.
        self.assertGreaterEqual(
            distinct, len(gaps) * 0.9,
            f"only {distinct} distinct would_close across {len(gaps)} gaps -- "
            f"these are templates, not work items")
        for g in gaps:
            w = g["would_close"]
            if "parameter" in g["subject"]:      # a ParamRef (amendment 004)
                # A gap about an uncovered point has no page to name: it reports
                # that NO source states the value, so there is no document to
                # send a curator to. The work item is the point itself, and
                # G40's requirement is that the sentence names it.
                parameter = g["because"]["params"]["parameter"]
                self.assertIn(parameter, w,
                              f"uncovered-point gap does not name its parameter: {w!r}")
                for key, value in g["because"]["params"]["point"].items():
                    # A boolean dimension is rendered as a phrase, not as its
                    # value -- hvhz true reads "HVHZ" and false "non-HVHZ" --
                    # so require the dimension by name there and the value
                    # verbatim everywhere else.
                    needle = key.split("_")[0] if isinstance(value, bool) \
                        else str(value).strip('"')
                    self.assertIn(needle.lower(), w.lower(),
                                  f"uncovered-point gap does not name the point "
                                  f"it is about: {key}={value!r} missing from {w!r}")
                continue
            if g["subject"].get("kind") == "component":
                # A component-scoped gap (obligation 14, PartType/Part) can
                # cite several sources across several pages at once -- no
                # single page to name -- so G40's requirement here is that the
                # component itself is named, the same way a ParamRef gap must
                # name its parameter.
                self.assertIn(g["subject"]["id"], w,
                              f"component-scoped gap does not name the "
                              f"component it is about: {w!r}")
                continue
            self.assertTrue(
                re.search(r"\bp\d+\b", w)
                or g["subject"].get("kind") == "source_document",
                f"element-scoped gap does not name its page: {w!r}")

    def test_the_eleven_promised_warning_classes_all_publish(self):
        """G42: five classes were promised to Planning and emitted nothing.

        `planning-asks.md` 3.2 commits this platform to eleven platform warning
        codes. Five of them -- the post-strike rule, the frost-line check, the
        post-top rule, the panel-both-ends rule and warranty exclusions -- are
        written as ordinary bullets or as prose, with no severity lexeme and no
        consequence clause, so neither _LEXEME_* nor _HAZARD saw them. They
        published 0 instances against 16-254 matching elements each.

        The general fix -- treating a bare "never" as a hazard -- is measured at
        248 hits and dominated by ordinary sequencing steps, which is why
        _HAZARD excludes it. These are named individually instead.
        """
        classes = {
            "post strike": r"never strike",
            "frost line": r"codes? for frost line",
            "post top": r"never cut the top",
            "panel both ends": r"never attach both ends",
            "warranty exclusion": r"not covered (?:by|under)[^.]{0,25}warrant",
        }
        for name, pat in classes.items():
            with self.subTest(warning_class=name):
                rx = re.compile(pat, re.IGNORECASE)
                hits = [w for w in self.snap["warnings"]
                        if rx.search(w["text_raw"])]
                self.assertTrue(hits, f"{name} publishes no warning")

    def test_a_rule_warning_publishes_its_bullet_not_the_whole_list(self):
        """The rule is one line of a list; publishing the list is not a warning.

        These bullets sit in installation lists carrying a dozen steps. A
        reader shown all twelve has not been warned, so the publisher extracts
        the matched fragment. The citation still resolves to the containing
        element, which is where the bbox is.
        """
        rx = re.compile(r"never strike", re.IGNORECASE)
        hits = [w for w in self.snap["warnings"] if rx.search(w["text_raw"])]
        self.assertTrue(hits)
        for w in hits:
            self.assertLess(len(w["text_raw"]), 200,
                            "the whole list element was published, not the rule")
            self.assertNotIn("\u2022", w["text_raw"])

    def test_building_twice_produces_the_same_hash(self):
        again = build_snapshot(tenant="acme", regime="us_astm")
        self.assertEqual(self.snap["snapshot_id"], again["snapshot_id"])

    def test_a_different_tenant_produces_a_different_hash(self):
        other = build_snapshot(tenant="other", regime="us_astm")
        self.assertNotEqual(self.snap["snapshot_id"], other["snapshot_id"])

    def test_it_publishes_something(self):
        self.assertGreater(len(self.snap["source_docs"]), 0)
        self.assertGreater(len(self.snap["warnings"]), 0)


class SnapshotCliRequiresExactlyOneMode(unittest.TestCase):
    """G39: `cli snapshot` must refuse an ambiguous or absent mode, loudly.

    Two defects sat in one branch. `--build` and `--dry-run` were independent
    store_true flags and only `--build` gated storage, so `--build --dry-run`
    stored anyway -- the one combination whose entire purpose is that it must
    not, against a write-once store with no delete. And a bare `snapshot`
    printed an error and exited 0.

    Exit 2 rather than 1 is argparse's convention for a usage error, and
    matches the refs branch, which refuses the same class. These cases return
    before the builder is reached, so they need neither a corpus nor a store.
    """

    def _run(self, argv):
        import contextlib
        import io

        from fence_evidence.cli import main

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(argv)
        return code, buf.getvalue()

    def test_no_mode_exits_nonzero(self):
        code, out = self._run(["snapshot"])
        self.assertEqual(code, 2)
        self.assertIn("choose one of", out)

    def test_build_with_dry_run_is_refused_rather_than_stored(self):
        """The defect itself: --dry-run was silently ignored and it stored."""
        code, out = self._run(["snapshot", "--build", "--dry-run"])
        self.assertEqual(code, 2)
        self.assertIn("choose one of", out)

    def test_other_mode_pairs_are_refused_too(self):
        for pair in (["--build", "--list"],
                     ["--dry-run", "--list"],
                     ["--list", "--get", "abc123"],
                     ["--build", "--get", "abc123"]):
            with self.subTest(pair=pair):
                code, out = self._run(["snapshot"] + pair)
                self.assertEqual(code, 2)
                self.assertIn("choose one of", out)


# -- C2, also_filed_as -----------------------------------------------------
# registry-additions.md §5: one `source_class` per content hash, every other
# filing named beside it. Load-bearing rather than tidy, because Planning ranks
# on the class: 18 of the 40 `same_content_as` edges here disagree about
# `doc_type` across their two sides, so identical bytes were admissible or not
# according to which record the SourceDoc happened to be built from -- silently,
# with no error anywhere.

SHA_A = "a" * 64
SHA_B = "b" * 64


def _filings_store(*records, sha=SHA_A):
    """A store where one content hash is filed under several document records.

    Built in memory because the behaviour under test is about the *catalogue*,
    not about any PDF: the interesting shapes -- a four-way group, two records
    agreeing on both published fields, a NULL manufacturer -- either do not
    occur in this corpus or occur once, and a test that can only run where the
    corpus does is not a guard on the logic.
    """
    import sqlite3

    from fence_evidence.store import SCHEMA

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute("""INSERT INTO extraction_runs(run_id, started_at, tool_versions,
                        tool_fingerprint, pipeline_version)
                    VALUES ('r1', '2026-08-20T00:00:00+00:00', '{}', 'fp', '1')""")
    for i, (doc_id, manufacturer, doc_type) in enumerate(records):
        conn.execute("""INSERT INTO documents(document_id, source_path, file_type,
                            corpus_track, manufacturer, doc_type, version_status,
                            version_status_basis)
                        VALUES (?, ?, 'pdf', 'us', ?, ?, 'unknown', NULL)""",
                     (doc_id, f"manuals/x/{doc_id}.pdf", manufacturer, doc_type))
        conn.execute("""INSERT INTO document_versions(version_id, document_id,
                            sha256, ingested_at, extraction_run_id)
                        VALUES (?, ?, ?, '2026-08-20T00:00:00+00:00', 'r1')""",
                     (f"v{i}", doc_id, sha))
        conn.execute("""INSERT INTO pages(page_id, version_id, page_no, width,
                            height, extraction_method, page_image_dpi)
                        VALUES (?, ?, 1, 612, 792, 'pdf_text_layer', 200)""",
                     (f"p{i}", f"v{i}"))
        conn.execute("""INSERT INTO elements(element_id, page_id, version_id,
                            document_id, page_no, ordinal, element_type, text,
                            text_source, bbox)
                        VALUES (?, ?, ?, ?, 1, 0, 'paragraph', 'x',
                                'pdf_text_layer', '[1.0, 2.0, 3.0, 4.0]')""",
                     (f"e{i}", f"p{i}", f"v{i}", doc_id))
    conn.commit()
    return conn


@requires_store
class TestPartTypeSpineOverTheRealStore(unittest.TestCase):
    """`part_types.py`/`parts.py` against the live corpus -- the milestone,
    the determinism guard every hash-bearing addition needs, and the closed
    build on a tampered dataset baseline."""

    @classmethod
    def setUpClass(cls):
        cls.snap = build_snapshot(tenant="acme", regime="us_astm")

    def test_part_types_and_parts_are_no_longer_the_empty_declared_lists(self):
        self.assertGreater(len(self.snap["parts"]), 0,
                           "obligation 5 milestone: the first Part ever published")
        self.assertGreater(len(self.snap["part_types"]), 0)

    def test_every_part_type_is_an_mfr_extension_never_shared(self):
        for pt in self.snap["part_types"]:
            self.assertNotEqual(pt["namespace"], "shared")
            self.assertTrue(pt["namespace"].startswith("mfr/"))
            self.assertEqual(pt["parent"]["namespace"], "shared")

    def test_obligation_14_is_gapped_not_guessed_for_the_known_ambiguity(self):
        specfield_gaps = [g for g in self.snap["gaps"]
                          if g["because"]["code"] == "specfield_wire_shape_unresolved"]
        self.assertEqual(len(specfield_gaps), 2)
        for g in specfield_gaps:
            self.assertTrue(g["cites"])

    def test_building_twice_produces_byte_identical_part_types_and_parts(self):
        from fence_evidence.canonical import canonical_bytes
        second = build_snapshot(tenant="acme", regime="us_astm")
        self.assertEqual(canonical_bytes(self.snap["part_types"]),
                         canonical_bytes(second["part_types"]))
        self.assertEqual(canonical_bytes(self.snap["parts"]),
                         canonical_bytes(second["parts"]))


@requires_store
class TestDatasetTamperFailsTheBuildClosed(unittest.TestCase):
    def test_a_forged_baseline_raises_and_returns_no_snapshot(self):
        from unittest.mock import patch

        from fence_evidence.dataset import DatasetChanged
        with patch("fence_evidence.part_types.dataset.verify_dataset",
                  side_effect=DatasetChanged("forged for the test")):
            with self.assertRaises(DatasetChanged):
                build_snapshot(tenant="acme", regime="us_astm")


class TestAlsoFiledAsIsBuilt(unittest.TestCase):
    def _doc(self, conn, element_id):
        b = SnapshotBuilder(conn, tenant="t", regime="us_astm")
        b.source_ref(element_id)
        return b.source_docs()[0]

    def test_bytes_filed_once_carry_an_empty_tuple(self):
        """Empty is a statement. Omitting the field would read as an oversight
        and, worse, would be indistinguishable from 'filed once'."""
        conn = _filings_store(("doc-1", "CertainTeed", "hvhz_noa"))
        try:
            self.assertEqual(self._doc(conn, "e0").also_filed_as, ())
        finally:
            conn.close()

    def test_the_other_filings_of_the_same_bytes_are_named(self):
        conn = _filings_store(("doc-1", "CertainTeed", "hvhz_noa"),
                              ("doc-2", "Freedom Outdoor Living", "unspecified"))
        try:
            self.assertEqual(
                self._doc(conn, "e0").also_filed_as,
                ({"manufacturer": "Freedom Outdoor Living",
                  "doc_type": "unspecified"},))
        finally:
            conn.close()

    def test_the_docs_own_filing_is_never_repeated(self):
        """The half of §5's rule that `verify()` cannot see.

        A finished snapshot publishes no `manufacturer` and no `doc_type` for
        the doc itself -- only the `source_class` derived from one -- so the
        gate cannot tell whether an entry repeats the doc's own filing. It is
        asserted here instead, from both sides of the same group.
        """
        conn = _filings_store(("doc-1", "CertainTeed", "hvhz_noa"),
                              ("doc-2", "Freedom Outdoor Living", "unspecified"))
        try:
            self.assertNotIn({"manufacturer": "CertainTeed",
                              "doc_type": "hvhz_noa"},
                             self._doc(conn, "e0").also_filed_as)
            self.assertNotIn({"manufacturer": "Freedom Outdoor Living",
                              "doc_type": "unspecified"},
                             self._doc(conn, "e1").also_filed_as)
        finally:
            conn.close()

    def test_a_second_record_with_the_same_pair_is_not_listed_twice(self):
        """The document id is not published, so a repeated pair carries nothing
        -- and it would read to a reviewer as two disagreeing filings."""
        conn = _filings_store(("doc-1", "Barrette", "installation_manual"),
                              ("doc-2", "Barrette", "installation_manual"),
                              ("doc-3", "Freedom", "installation_manual"))
        try:
            self.assertEqual(
                self._doc(conn, "e0").also_filed_as,
                ({"manufacturer": "Freedom", "doc_type": "installation_manual"},))
        finally:
            conn.close()

    def test_the_order_does_not_depend_on_insertion_order(self):
        """The list is hashed. Two stores holding the same catalogue in a
        different row order must produce the same snapshot id."""
        forward = (("doc-1", "CertainTeed", "hvhz_noa"),
                   ("doc-2", "Freedom", "unspecified"),
                   ("doc-3", "Barrette", "engineering_approval"))
        a = _filings_store(*forward)
        b = _filings_store(forward[0], *reversed(forward[1:]))
        try:
            self.assertEqual(self._doc(a, "e0").also_filed_as,
                             self._doc(b, "e0").also_filed_as)
            self.assertEqual(
                [f["manufacturer"] for f in self._doc(a, "e0").also_filed_as],
                ["Barrette", "Freedom"])
        finally:
            a.close()
            b.close()

    def test_a_null_manufacturer_sorts_rather_than_raising(self):
        """Both fields are nullable in the store. A catalogue that does not say
        who filed something is a gap, not a crash in the publisher."""
        conn = _filings_store(("doc-1", "CertainTeed", "hvhz_noa"),
                              ("doc-2", None, "spec_sheet"),
                              ("doc-3", "Barrette", "spec_sheet"))
        try:
            self.assertEqual(
                [f["manufacturer"] for f in self._doc(conn, "e0").also_filed_as],
                [None, "Barrette"])
        finally:
            conn.close()

    def test_bytes_that_differ_are_not_filings_of_one_document(self):
        """One of the 40 `same_content_as` edges joins two DIFFERENT content
        hashes -- identical extracted text, different bytes. Those are two
        SourceDocs, and `also_filed_as` is defined per content hash, so it
        must not reach across. Registry §5 leaves that pair to curation."""
        conn = _filings_store(("doc-1", "CertainTeed", "hvhz_noa"))
        conn.execute("""INSERT INTO documents(document_id, source_path, file_type,
                            corpus_track, manufacturer, doc_type, version_status)
                        VALUES ('doc-9', 'manuals/x/9.pdf', 'pdf', 'us',
                                'Freedom', 'unspecified', 'unknown')""")
        conn.execute("""INSERT INTO document_versions(version_id, document_id,
                            sha256, ingested_at, extraction_run_id)
                        VALUES ('v9', 'doc-9', ?, '2026-08-20T00:00:00+00:00',
                                'r1')""", (SHA_B,))
        conn.execute("""INSERT INTO relations(relation_id, from_document_id,
                            to_document_id, relation_type, basis)
                        VALUES (1, 'doc-1', 'doc-9', 'same_content_as',
                                'test')""")
        conn.commit()
        try:
            self.assertEqual(self._doc(conn, "e0").also_filed_as, ())
        finally:
            conn.close()


@requires_store
class TestAlsoFiledAsOverTheCorpus(unittest.TestCase):
    """The measured shape, against the real catalogue."""

    @classmethod
    def setUpClass(cls):
        from fence_evidence.store import connect
        cls.snap = build_snapshot(tenant="acme", regime="us_astm")
        cls.conn = connect()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_every_source_doc_declares_the_field(self):
        for d in self.snap["source_docs"]:
            self.assertIn("also_filed_as", d, d["content_hash"])

    def test_the_duplicate_filings_actually_publish(self):
        """11 of the 14 byte-identical groups in this store have a cited member;
        a build that named none of them would pass every other check here."""
        nonempty = [d for d in self.snap["source_docs"] if d["also_filed_as"]]
        self.assertGreater(len(nonempty), 0)

    def test_each_list_is_the_group_minus_exactly_one_filing(self):
        """One class per content hash: the group's OTHER filings are published,
        and the one that is not is the one whose class was."""
        for d in self.snap["source_docs"]:
            group = {(r["manufacturer"], r["doc_type"]) for r in self.conn.execute(
                """SELECT d.manufacturer, d.doc_type
                     FROM document_versions v
                     JOIN documents d ON d.document_id = v.document_id
                    WHERE v.sha256 = ?""", (d["content_hash"],))}
            published = {(f["manufacturer"], f["doc_type"])
                         for f in d["also_filed_as"]}
            with self.subTest(content_hash=d["content_hash"][:12]):
                self.assertTrue(published <= group, "a filing of other bytes")
                missing = group - published
                self.assertEqual(len(missing), 1,
                                 "exactly one filing is the published one")
                self.assertEqual(SOURCE_CLASS[missing.pop()[1]],
                                 d["source_class"],
                                 "the withheld filing is not the one whose "
                                 "class was published")

    def test_a_group_disagreeing_on_doc_type_still_publishes_one_class(self):
        """The failure the rule exists to prevent, in the corpus that has it: a
        Miami-Dade NOA filed as `hvhz_noa` under one manufacturer and
        `unspecified` under another maps to `sealed_approval` and `marketing` --
        admissible for a structural parameter, and inadmissible."""
        disagreeing = [
            d for d in self.snap["source_docs"]
            if any(SOURCE_CLASS[f["doc_type"]] != d["source_class"]
                   for f in d["also_filed_as"])]
        self.assertTrue(disagreeing, "no group disagrees; the fixture moved")
        for d in disagreeing:
            self.assertIsInstance(d["source_class"], str)


if __name__ == "__main__":
    unittest.main()
