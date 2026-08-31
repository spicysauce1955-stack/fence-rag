"""The ParameterTable builder — the `unique` check, and what it must NOT catch.

Everything here runs against a store built from `store.SCHEMA` in memory, with
synthetic facts. That is not only for speed: the live store holds **zero**
promoted facts today, because build-plan A1 un-promoted the 324 that reached it
on machine agreement alone, so there is no real data to assert against and the
shapes still have to be right before there is.

Four scenarios carry the file, and they are the four that decide whether the
`unique` check is worth having:

* a clean table — every point covered once, `uncovered` empty;
* a table with a point no row covers, and one the source deliberately excludes;
* a real collision — two values at one point with overlapping validity;
* a false collision — the same two values whose windows are DISJOINT, which is a
  succession and must publish.
"""
import json
import sqlite3
import unittest

import context  # noqa: F401  -- puts the repo root on sys.path
from fence_evidence.canonical import canonical_bytes
from fence_evidence.promote_tables import NO_BRACKET_PRINTED
from fence_evidence.parameters import (CONDITION_SCOPE, PARAMETER_OF,
                                       _describe, _parse_fence_height,
                                       _round_half_up, _windows_overlap,
                                       build_parameter_tables, quantity)
from fence_evidence.store import SCHEMA

SHA_A = "a" * 64
SHA_B = "b" * 64


def make_store() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def add_document(conn, *, document_id="doc-1", sha256=SHA_A, version_id="v1",
                 doc_type="hvhz_noa", manufacturer="Bufftech",
                 product_family="Chesterfield", version_status="active",
                 issue_date=None, expiration_date=None, page_no=17):
    conn.execute("""INSERT INTO documents(document_id, source_path, file_type,
        corpus_track, manufacturer, product_family, doc_type, title,
        version_status, issue_date, expiration_date)
        VALUES (?,?,'pdf','us',?,?,?,?,?,?,?)""",
        (document_id, f"manuals/x/{document_id}.pdf", manufacturer,
         product_family, doc_type, f"{document_id} title", version_status,
         issue_date, expiration_date))
    conn.execute("""INSERT INTO document_versions(version_id, document_id, sha256,
        ingested_at) VALUES (?,?,?,'2026-08-27T00:00:00+00:00')""",
        (version_id, document_id, sha256))
    conn.execute("""INSERT INTO pages(page_id, version_id, page_no, width, height,
        extraction_method) VALUES (?,?,?,612.0,792.0,'text')""",
        (f"{version_id}-p{page_no}", version_id, page_no))
    conn.execute("""INSERT INTO elements(element_id, page_id, version_id, document_id,
        page_no, ordinal, element_type, text, text_source, bbox)
        VALUES (?,?,?,?,?,0,'table','footing table','pdftotext','[10,20,30,40]')""",
        (f"el-{version_id}", f"{version_id}-p{page_no}", version_id, document_id,
         page_no))
    conn.commit()


_ROW_INDEX = [0]


def _candidate(conn, document_id, version_id, page_no, value, review_status):
    """The reading a fact was promoted from. `facts.from_candidate_id` is a real
    foreign key and `SCHEMA` turns foreign keys ON, so it has to exist."""
    _ROW_INDEX[0] += 1
    cur = conn.execute("""INSERT INTO table_read_candidates
        (document_id, version_id, page_no, crop_path, crop_sha256, reader,
         reader_kind, is_table, row_index, col_index, col_label, value,
         review_status, created_at)
        VALUES (?,?,?,'workspace/derived/c.png',?,'calibration-A','agent',1,?,1,
                'FOOTING DEPTH',?,?,'2026-08-27T00:00:00+00:00')""",
        (document_id, version_id, page_no, "c" * 64, _ROW_INDEX[0], value,
         review_status))
    return cur.lastrowid


def add_fact(conn, *, fact_type="footing_depth_in", value='36"',
             conditions=None, condition_basis="stated",
             condition_basis_note=None, document_id="doc-1",
             version_id="v1", page_no=17, review_status="accepted",
             promoted=True, unit_normalized="in", value_alternates=None):
    """One promoted fact: a table cell carrying its row's conditions."""
    candidate_id = _candidate(conn, document_id, version_id, page_no, value,
                              review_status)
    conn.execute("""INSERT INTO facts(document_id, version_id, page_no, element_id,
        fact_type, subject, value_original, unit_original, unit_normalized,
        conditions, condition_basis, condition_basis_note, value_alternates,
        evidence_text, extractor,
        review_status, created_at, from_candidate_id)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'table row','table-read:accepted',?,
                '2026-08-27T00:00:00+00:00',?)""",
        (document_id, version_id, page_no, f"el-{version_id}", fact_type,
         "FOOTING DEPTH", value, "in" if '"' in value else None, unit_normalized,
         json.dumps(conditions if conditions is not None else {}),
         condition_basis, condition_basis_note,
         json.dumps(value_alternates) if value_alternates else None,
         review_status, candidate_id if promoted else None))
    conn.commit()


def both_hvhz(exposure):
    return {"exposure_category": exposure,
            "hvhz_applicability": "HVHZ and non-HVHZ"}


def non_hvhz(exposure):
    return {"exposure_category": exposure,
            "hvhz_applicability": "non-HVHZ only"}


def codes(gaps):
    return sorted(g["because"]["code"] for g in gaps)


class TestQuantity(unittest.TestCase):
    """§1.1: integers in thousandths, the source lexeme alongside, no float."""

    class _Row(dict):
        def __getitem__(self, key):
            return self.get(key)

    def _row(self, value, unit="in", alternates=None):
        return self._Row(value_original=value, unit_original=None,
                         unit_normalized=unit,
                         value_alternates=json.dumps(alternates) if alternates
                         else None)

    def test_inches_convert_exactly(self):
        q = quantity(self._row('36"'))
        self.assertEqual(q["amount_milli"], 914400)      # 36 * 25.4 * 1000
        self.assertEqual(q["unit"], "mm")
        self.assertIs(type(q["amount_milli"]), int)

    def test_a_vulgar_fraction_is_exact(self):
        """7/8" is 22.225 mm — obligation 4's own example of why _mm is wrong."""
        self.assertEqual(quantity(self._row('7/8"'))["amount_milli"], 22225)
        self.assertEqual(quantity(self._row('96 1/8"'))["amount_milli"], 2441575)

    def test_rounding_is_half_up_not_bankers(self):
        """§1.1 BINDING: it rounds, it does not truncate — and round() would
        take 0.5 to the nearer EVEN, which is a third answer again."""
        from fractions import Fraction
        self.assertEqual(_round_half_up(Fraction(5, 2)), 3)      # round() gives 2
        self.assertEqual(_round_half_up(Fraction(7, 2)), 4)
        self.assertEqual(_round_half_up(Fraction(-5, 2)), -3)

    def test_value_raw_is_a_list_and_keeps_both_lexemes(self):
        q = quantity(self._row('66"', alternates=[{"value_original": "1676 mm"}]))
        self.assertEqual(q["value_raw"], ['66"', "1676 mm"])

    def test_no_float_reaches_the_boundary(self):
        canonical_bytes(quantity(self._row('36"')))     # refuses floats itself

    def test_an_unparseable_value_is_refused_not_guessed(self):
        self.assertIsNone(quantity(self._row("see note")))
        self.assertIsNone(quantity(self._row("36", unit="furlong")))


class TestFenceHeightInterval(unittest.TestCase):
    """G57. Amendment 007, ratified into contract v1.3: `fence_height` crosses
    as an `Interval`, not a bare string. Corpus-wide only two labels exist —
    this is a two-label parser, not an open-ended one."""

    def test_up_to_is_unbounded_below(self):
        iv = _parse_fence_height('Up to 48"')
        self.assertIsNone(iv["min"])
        self.assertEqual(iv["max"]["amount_milli"], 1219200)     # 48 * 25.4 * 1000
        self.assertEqual(iv["max"]["unit"], "mm")
        self.assertTrue(iv["max_inclusive"])
        self.assertEqual(iv["value_raw"], ['Up to 48"'])

    def test_a_to_b_is_bounded_both_sides(self):
        iv = _parse_fence_height('49" to 76"')
        self.assertEqual(iv["min"]["amount_milli"], 1244600)     # 49 * 25.4 * 1000
        self.assertEqual(iv["max"]["amount_milli"], 1930400)     # 76 * 25.4 * 1000
        self.assertTrue(iv["min_inclusive"])
        self.assertTrue(iv["max_inclusive"])
        self.assertEqual(iv["value_raw"], ['49" to 76"'])

    def test_read_literally_not_smoothed_into_touching_brackets(self):
        """The 25.4 mm band between these two real brackets (amendment 007
        E2) is exactly what a literal reading produces -- inclusive on both
        sides of both brackets, as written, with no inclusivity invented to
        make them tile."""
        below = _parse_fence_height('Up to 48"')
        above = _parse_fence_height('49" to 76"')
        self.assertLess(below["max"]["amount_milli"], above["min"]["amount_milli"])

    def test_each_bound_keeps_its_own_lexeme_not_the_whole_label(self):
        iv = _parse_fence_height('49" to 76"')
        self.assertEqual(iv["min"]["value_raw"], ['49"'])
        self.assertEqual(iv["max"]["value_raw"], ['76"'])

    def test_no_float_reaches_the_boundary(self):
        canonical_bytes(_parse_fence_height('Up to 48"'))
        canonical_bytes(_parse_fence_height('49" to 76"'))

    def test_unparseable_is_refused_not_guessed(self):
        self.assertIsNone(_parse_fence_height("see chart"))
        self.assertIsNone(_parse_fence_height(""))
        self.assertIsNone(_parse_fence_height(None))


class TestConditionScope(unittest.TestCase):
    """Obligation 13, BINDING: a published condition key declares its scope."""

    def test_every_declared_scope_is_one_of_the_six_words(self):
        self.assertTrue(
            set(CONDITION_SCOPE.values())
            <= {"site", "param", "run", "post", "bay", "panel"},
            f"outside obligation 13's vocabulary: {set(CONDITION_SCOPE.values())}")

    def test_exposure_and_hvhz_are_site_facts(self):
        self.assertEqual(CONDITION_SCOPE["exposure_category"], "site")
        self.assertEqual(CONDITION_SCOPE["hvhz"], "site")

    def test_a_table_declares_a_scope_for_every_domain_key(self):
        conn = make_store()
        add_document(conn)
        for exposure, value in (("B", '30"'), ("C", '36"'), ("D", '42"')):
            add_fact(conn, conditions=both_hvhz(exposure), value=value)
        tables, _ = build_parameter_tables(conn)
        table, = tables
        self.assertEqual(set(table["condition_scope"]), set(table["domain"]))
        self.assertEqual(table["condition_scope"],
                         {"exposure_category": "site", "hvhz": "site"})
        conn.close()

    def test_a_key_with_no_declared_scope_is_not_published(self):
        """Dropping the key instead would publish the row as applying more
        widely than the source scoped it — the failure obligation 13 prevents."""
        conn = make_store()
        add_document(conn)
        add_fact(conn, conditions={"exposure_category": "C",
                                   "soil_class": "clay"})
        tables, gaps = build_parameter_tables(conn)
        self.assertEqual(tables, [])
        self.assertIn("condition_scope_undeclared", codes(gaps))
        conn.close()


class TestACleanTable(unittest.TestCase):
    """Three exposures, both HVHZ states, one value each: nothing uncovered."""

    def setUp(self):
        self.conn = make_store()
        add_document(self.conn)
        for exposure, value in (("B", '30"'), ("C", '36"'), ("D", '42"')):
            add_fact(self.conn, conditions=both_hvhz(exposure), value=value)
        self.tables, self.gaps = build_parameter_tables(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_one_table_with_the_contract_shape(self):
        table, = self.tables
        self.assertEqual(
            set(table),
            {"parameter", "scope", "task", "hit_policy", "value_type", "domain",
             "domain_basis", "condition_scope", "rows", "uncovered"})
        self.assertEqual(table["parameter"], "footing_depth_mm")
        self.assertEqual(table["task"], "structural_parameter")
        self.assertEqual(table["hit_policy"], "unique")
        self.assertEqual(table["value_type"], "quantity(mm)")

    def test_the_domain_is_declared_not_read_off_the_page(self):
        """The regulatory universe fixes B/C/D and the two HVHZ states; the page
        only printed rows. §1.3: uncovered against a declared domain means *we
        may not know this table's real extent*."""
        table, = self.tables
        self.assertEqual(table["domain"], {"exposure_category": ["B", "C", "D"],
                                           "hvhz": [False, True]})
        self.assertEqual(table["domain_basis"], "declared")

    def test_nothing_is_uncovered_and_no_gap_is_raised(self):
        table, = self.tables
        self.assertEqual(table["uncovered"], [])
        self.assertEqual([g for g in self.gaps
                          if g["kind"] == "uncovered_condition"], [])

    def test_a_row_omitting_hvhz_covers_both_states(self):
        """A key a row does not mention matches every value of that dimension —
        which is how a bracket reading 'HVHZ and NON HVHZ' is published."""
        table, = self.tables
        self.assertEqual([r["conditions"] for r in table["rows"]],
                         [{"exposure_category": e} for e in ("B", "C", "D")])

    def test_every_row_carries_provenance_and_a_citation(self):
        table, = self.tables
        for row in table["rows"]:
            p = row["provenance"]
            self.assertEqual(p["source_class"], "sealed_approval")
            self.assertEqual(p["curation_level"], 2)    # a person accepted it
            self.assertEqual(p["version_status"], "active")
            self.assertEqual([c["belongs_to"] for c in p["cites"]], [SHA_A])

    def test_the_build_is_deterministic(self):
        again, _ = build_parameter_tables(self.conn)
        self.assertEqual(canonical_bytes(self.tables), canonical_bytes(again))


class TestUncoveredPoints(unittest.TestCase):
    """BINDING: points no row covers are LISTED, never silently omitted."""

    def test_a_missing_exposure_is_listed_and_gapped(self):
        conn = make_store()
        add_document(conn)
        for exposure, value in (("B", '30"'), ("C", '36"')):
            add_fact(conn, conditions=both_hvhz(exposure), value=value)
        table, = build_parameter_tables(conn)[0]
        self.assertEqual(table["uncovered"],
                         [{"exposure_category": "D", "hvhz": False},
                          {"exposure_category": "D", "hvhz": True}])
        conn.close()

    def test_an_uncovered_point_is_not_also_published_as_a_gap(self):
        """T14 (`conversation.md`). Every point no row covers already appears in
        `table.uncovered` -- §1.3's own channel: "Planning treats an uncovered
        point as a warned, unfulfilled requirement." A `condition_point_uncovered`
        gap for the identical point restates the same fact under a second shape;
        Planning's own `expand()` measurably derives an equivalent gap from
        `uncovered` alone, so ingesting both means a curator sees the same missing
        row twice. `uncovered` still carries the point -- the gap channel does not.
        """
        conn = make_store()
        add_document(conn)
        add_fact(conn, conditions=both_hvhz("C"), value='36"')
        table, gaps = build_parameter_tables(conn)
        table = table[0]
        self.assertEqual(len(table["uncovered"]), 4)      # B and D, both states
        self.assertTrue(any("exposure D, HVHZ" in _describe(p)
                            for p in table["uncovered"]))
        self.assertFalse([g for g in gaps
                          if g["because"]["code"] == "condition_point_uncovered"])
        conn.close()

    def test_a_point_the_source_excludes_is_distinguished_from_one_it_never_read(self):
        """G16, the critical finding. Both exposure B rows are bracketed NON
        HVHZ, so (B, HVHZ) is *not approved* — answering it from the B row would
        cite a Miami-Dade NOA for a job its own approval excludes."""
        conn = make_store()
        add_document(conn)
        add_fact(conn, conditions=non_hvhz("B"), value='30"')
        add_fact(conn, conditions=both_hvhz("C"), value='36"')
        table, gaps = build_parameter_tables(conn)
        table = table[0]
        self.assertIn({"exposure_category": "B", "hvhz": True}, table["uncovered"])
        excluded = [g for g in gaps
                    if g["because"]["code"] == "condition_point_excluded_by_source"]
        self.assertEqual(len(excluded), 1)
        self.assertEqual(excluded[0]["because"]["params"]["point"],
                         {"exposure_category": "B", "hvhz": True})
        self.assertIn("not approved", excluded[0]["would_close"])
        # and it cites the row that does the excluding
        self.assertEqual([c["belongs_to"] for c in excluded[0]["cites"]], [SHA_A])
        conn.close()


class TestTheUniqueCheck(unittest.TestCase):
    """The check, and the two things it must NOT fire on."""

    def test_a_real_collision_withholds_the_table_and_gaps_the_point(self):
        """C5: `(36", 88")` and `(30", 68")` at exposure C are paired design
        points — a deeper footing buys a wider span — and no dimension separates
        them. Publishing under `unique` would break a BINDING clause; a
        collect/priority policy would discard the cheaper compliant option."""
        conn = make_store()
        add_document(conn)
        add_fact(conn, conditions=both_hvhz("C"), value='36"')
        add_fact(conn, conditions=both_hvhz("C"), value='30"')
        tables, gaps = build_parameter_tables(conn)
        self.assertEqual(tables, [], "a table that violates `unique` was published")
        clash = [g for g in gaps
                 if g["because"]["code"] == "paired_design_point_unmodellable"]
        self.assertEqual(len(clash), 2)                  # both HVHZ states
        self.assertEqual({g["kind"] for g in clash}, {"unmodellable_entity"})
        self.assertEqual({g["closes_by"] for g in clash}, {"planning"})
        self.assertIn("footing_depth_mm", clash[0]["subject"])
        self.assertIn("C5", clash[0]["would_close"])
        self.assertEqual(clash[0]["because"]["params"]["amount_milli"],
                         [762000, 914400])
        conn.close()

    def test_a_succession_is_not_a_collision(self):
        """Defect 6. Two values at one point under an approval that expired and
        its replacement are a succession — which is exactly why §1.3 carries
        expiry as fields rather than as an `as_of_date` domain dimension."""
        conn = make_store()
        add_document(conn, document_id="doc-old", sha256=SHA_A, version_id="v1",
                     issue_date="2015-01-01", expiration_date="2018-01-01",
                     version_status="superseded")
        add_document(conn, document_id="doc-new", sha256=SHA_B, version_id="v2",
                     issue_date="2019-01-01")
        add_fact(conn, conditions=both_hvhz("C"), value='36"',
                 document_id="doc-old", version_id="v1")
        add_fact(conn, conditions=both_hvhz("C"), value='30"',
                 document_id="doc-new", version_id="v2")
        tables, gaps = build_parameter_tables(conn)
        self.assertEqual(len(tables), 1, "disjoint windows were read as a clash")
        self.assertEqual(len(tables[0]["rows"]), 2)
        self.assertEqual(codes([g for g in gaps
                                if g["kind"] == "unmodellable_entity"]), [])
        self.assertEqual([r["valid_until"] for r in tables[0]["rows"]],
                         sorted([None, "2018-01-01"], key=lambda v: (v is None, v)))
        conn.close()

    def test_overlapping_windows_are_a_real_collision(self):
        """The same two values, with the old approval still live in 2019."""
        conn = make_store()
        add_document(conn, document_id="doc-old", sha256=SHA_A, version_id="v1",
                     issue_date="2015-01-01", expiration_date="2020-01-01")
        add_document(conn, document_id="doc-new", sha256=SHA_B, version_id="v2",
                     issue_date="2019-01-01")
        add_fact(conn, conditions=both_hvhz("C"), value='36"',
                 document_id="doc-old", version_id="v1")
        add_fact(conn, conditions=both_hvhz("C"), value='30"',
                 document_id="doc-new", version_id="v2")
        tables, gaps = build_parameter_tables(conn)
        self.assertEqual(tables, [])
        self.assertIn("paired_design_point_unmodellable", codes(gaps))
        conn.close()

    def test_window_arithmetic(self):
        open_ended = {"valid_from": None, "valid_until": None}
        self.assertTrue(_windows_overlap(open_ended, open_ended))
        self.assertFalse(_windows_overlap(
            {"valid_from": "2015-01-01", "valid_until": "2018-01-01"},
            {"valid_from": "2019-01-01", "valid_until": None}))
        self.assertTrue(_windows_overlap(
            {"valid_from": "2015-01-01", "valid_until": "2020-01-01"},
            {"valid_from": "2019-01-01", "valid_until": None}))
        self.assertFalse(_windows_overlap(
            {"valid_from": "2019-01-01", "valid_until": None},
            {"valid_from": "2015-01-01", "valid_until": "2018-01-01"}))

    def test_the_same_value_twice_is_corroboration_not_a_conflict(self):
        """§1.4 requires every row to be published, including ones a policy will
        reject, so several sources stating 36" at one point is the normal case.
        Any evaluation order returns 36"."""
        conn = make_store()
        add_document(conn, document_id="doc-1", sha256=SHA_A, version_id="v1")
        add_document(conn, document_id="doc-2", sha256=SHA_B, version_id="v2",
                     doc_type="installation_manual")
        add_fact(conn, conditions=both_hvhz("C"), value='36"')
        add_fact(conn, conditions=both_hvhz("C"), value='36"',
                 document_id="doc-2", version_id="v2")
        tables, gaps = build_parameter_tables(conn)
        self.assertEqual(len(tables), 1)
        rows = tables[0]["rows"]
        self.assertEqual(len(rows), 2, "rows of different source_class merged")
        self.assertEqual({r["provenance"]["source_class"] for r in rows},
                         {"sealed_approval", "manufacturer_installation_instruction"})
        self.assertNotIn("paired_design_point_unmodellable", codes(gaps))
        conn.close()

    def test_identical_rows_from_identical_sources_merge_their_citations(self):
        """Fourteen groups of files here are byte-identical under different
        manufacturers; the same warning text is already treated this way."""
        conn = make_store()
        add_document(conn, document_id="doc-1", sha256=SHA_A, version_id="v1",
                     page_no=17)
        # the SAME bytes filed a second time -- one content hash, so one
        # authority and one provenance -- with the table reprinted on page 31
        add_document(conn, document_id="doc-2", sha256=SHA_A, version_id="v2",
                     page_no=31)
        add_fact(conn, conditions=both_hvhz("C"), value='36"')
        add_fact(conn, conditions=both_hvhz("C"), value='36"',
                 document_id="doc-2", version_id="v2", page_no=31)
        table, = build_parameter_tables(conn)[0]
        # same provenance triple, same value, same (null) window -> one row
        self.assertEqual(len(table["rows"]), 1)
        cites = table["rows"][0]["provenance"]["cites"]
        self.assertEqual([c["belongs_to"] for c in cites], [SHA_A, SHA_A])
        self.assertEqual(len({c["id"] for c in cites}), 2, "two rectangles")
        conn.close()

    def test_an_unconditioned_fallback_is_excluded_from_the_check(self):
        """Obligation 15: a `stated` row with empty conditions is a fallback,
        excluded from the overlap check, and covers the whole domain. 66% of the
        structural facts in the class §1.4 admits are this shape; under a literal
        check all of them become publish errors."""
        conn = make_store()
        add_document(conn)
        add_fact(conn, conditions={}, value='30"')
        add_fact(conn, conditions={}, value='36"')
        tables, gaps = build_parameter_tables(conn)
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0]["uncovered"], [])
        self.assertNotIn("paired_design_point_unmodellable", codes(gaps))
        conn.close()


class TestWhatIsNotPublished(unittest.TestCase):
    def test_only_promoted_facts_are_considered(self):
        """A regex-extracted fact has no table row and no bracket; publishing it
        into a declared domain would assert conditions no source stated."""
        conn = make_store()
        add_document(conn)
        add_fact(conn, conditions=both_hvhz("C"), value='36"', promoted=False,
                 review_status="extracted")
        self.assertEqual(build_parameter_tables(conn), ([], []))
        conn.close()

    def test_a_rejected_fact_is_never_published(self):
        conn = make_store()
        add_document(conn)
        add_fact(conn, conditions=both_hvhz("C"), value='36"',
                 review_status="rejected")
        self.assertEqual(build_parameter_tables(conn)[0], [])
        conn.close()

    def test_an_unresolved_applicability_bracket_becomes_a_disputed_gap(self):
        """§1.2.1: the value is certain and the conditions are not, and none of
        the other seven kinds fits that honestly."""
        conn = make_store()
        add_document(conn)
        add_fact(conn, conditions={"exposure_category": "B",
                                   "hvhz_applicability": "unresolved"},
                 value='97"', fact_type="post_spacing_in")
        tables, gaps = build_parameter_tables(conn)
        self.assertEqual(tables, [])
        disputed, = [g for g in gaps if g["kind"] == "disputed"]
        self.assertEqual(disputed["on"], "conditions")
        self.assertEqual(disputed["because"]["code"],
                         "applicability_bracket_unresolved")
        self.assertTrue(disputed["cites"])
        conn.close()

    def test_a_page_that_prints_no_bracket_publishes_unrestricted(self):
        """The other half of the reading above.

        `unresolved` means readers disagreed and the row is withheld. A page
        that prints no bracket at all is not a disagreement: a reviewer read the
        image and recorded that nothing restricts the row. A bracket is a
        restriction, so its absence leaves the row matching every `hvhz` value
        -- the key is omitted, exactly as for `HVHZ and non-HVHZ` -- while
        `hvhz` stays in the declared domain so `uncovered` stays honest.
        """
        conn = make_store()
        add_document(conn)
        for exposure, value in (("B", '24"'), ("C", '30"'), ("D", '36"')):
            add_fact(conn, conditions={"exposure_category": exposure,
                                       "hvhz_applicability": NO_BRACKET_PRINTED},
                     value=value)
        tables, gaps = build_parameter_tables(conn)
        self.assertEqual([g["because"]["code"] for g in gaps], [])
        table, = tables
        self.assertIn("hvhz", table["domain"])
        self.assertEqual(table["uncovered"], [])
        for row in table["rows"]:
            self.assertNotIn("hvhz", row["conditions"])
        conn.close()

    def test_the_disputed_gap_does_not_invent_a_disagreement(self):
        """`would_close` is the sentence a person acts on, and it hardcoded
        "readers did not independently agree" for every unresolved bracket --
        including rows where no reader read one at all. It must quote the basis
        the promotion actually recorded."""
        conn = make_store()
        add_document(conn)
        add_fact(conn, conditions={"exposure_category": "B",
                                   "hvhz_applicability": "unresolved"},
                 condition_basis_note="no reader read an applicability bracket "
                                      "for this row; the page may print none",
                 value='97"', fact_type="post_spacing_in")
        disputed, = build_parameter_tables(conn)[1]
        self.assertIn("no reader read an applicability bracket",
                      disputed["would_close"])
        self.assertNotIn("did not independently agree", disputed["would_close"])
        conn.close()

    def test_two_values_at_one_point_collide_even_with_no_conditions(self):
        """The fallback exemption must not cover a row we simply could not read.

        Obligation 15's fallback — `stated` with no conditions — is excluded
        from the `unique` overlap check because it "never asserts anything about
        the points it lands on". A row whose conditions are empty because a
        COLUMN WAS DROPPED looks identical, and inherits an exemption it has no
        claim to. Measured on doc-8727ba0fd4d4 p10, where the two dropped
        columns were the only thing separating the rows: 609600 and 762000
        milli-mm published at one point, `hit_policy: unique`, level 2, zero
        gaps. `promote_tables` now writes `assumed` for such a row, which is
        what puts it back inside the check.
        """
        conn = make_store()
        add_document(conn)
        for value in ('24"', '30"'):
            add_fact(conn, conditions={}, condition_basis="assumed",
                     condition_basis_note="columns this platform could not classify "
                                          "were dropped from this row, so its "
                                          "conditions may be incomplete: "
                                          "FOOTING DIAMETER, MAXIMUM POST SPACING.",
                     value=value)
        tables, gaps = build_parameter_tables(conn)
        self.assertEqual(tables, [], "a contradiction must not publish")
        self.assertIn("parameter_point_collision_unread_columns", codes(gaps))
        gap, = [g for g in gaps if g["kind"] == "missing_value"]
        self.assertEqual(gap["closes_by"], "knowledge")
        self.assertIn("FOOTING DIAMETER", gap["would_close"])
        # it must not route this to C5: that amendment is about the SOURCE
        # stating two design points, and this collision is our own misreading
        self.assertNotIn("C5", gap["would_close"])
        conn.close()

    def test_unresolved_bracket_on_an_unread_row_is_not_a_disputed_gap(self):
        """G56. The row above, but with `_row_applicability`'s own verdict
        included -- exactly what `promote_tables` actually wrote for
        doc-8727ba0fd4d4 p10, whose drawing predates this corpus's HVHZ
        column entirely: no exposure, no fence height, no bracket, nothing.

        `_translate_conditions` treated `hvhz_applicability: "unresolved"` as
        a disputed disagreement regardless of WHY it was unresolved, and
        returned early -- so the row never reached `_finish`'s collision
        detector, which already knows how to tell "we misread this" apart
        from a real disagreement. A table with no key columns at all
        (`condition_basis: assumed`, nothing classified) reads exactly like
        the no-conditions case above; it must be gapped the same way, not
        published as `disputed` on a bracket nobody was ever in a position to
        agree or disagree about.
        """
        conn = make_store()
        add_document(conn)
        for value in ('24"', '30"'):
            add_fact(conn, conditions={"hvhz_applicability": "unresolved"},
                     condition_basis="assumed",
                     condition_basis_note="columns this platform could not classify "
                                          "were dropped from this row, so its "
                                          "conditions may be incomplete: "
                                          "FOOTING DIAMETER, MAXIMUM POST SPACING.",
                     value=value)
        tables, gaps = build_parameter_tables(conn)
        self.assertEqual(tables, [], "a contradiction must not publish")
        self.assertIn("parameter_point_collision_unread_columns", codes(gaps))
        self.assertNotIn("applicability_bracket_unresolved", codes(gaps))
        conn.close()

    def test_a_real_unconditioned_fallback_still_publishes(self):
        """The other side of the same line: obligation 15 is not weakened.

        Two rows agreeing at one point is corroboration, and a genuinely
        unconditioned `stated` row is the fallback the contract requires us to
        publish.
        """
        conn = make_store()
        add_document(conn)
        add_fact(conn, conditions={}, condition_basis="stated", value='24"')
        tables, gaps = build_parameter_tables(conn)
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0]["uncovered"], [])
        conn.close()

    def test_an_unmapped_fact_type_is_held_back_and_named(self):
        conn = make_store()
        add_document(conn)
        add_fact(conn, fact_type="rail_length_in", value='96"',
                 conditions=both_hvhz("C"))
        tables, gaps = build_parameter_tables(conn)
        self.assertEqual(tables, [])
        self.assertIn("parameter_name_unmapped", codes(gaps))
        conn.close()

    def test_every_mapped_fact_type_names_a_unit_the_contract_knows(self):
        units = {"mm", "mm2", "mm3", "each", "gram_milli", "cent", "deg_milli",
                 "mph_milli", "pa_milli", "second_milli"}
        for _, unit in PARAMETER_OF.values():
            self.assertIn(unit, units)


class TestScopeAndCuration(unittest.TestCase):
    def test_a_document_with_a_product_family_scopes_to_a_namespaced_model(self):
        conn = make_store()
        add_document(conn)
        add_fact(conn, conditions=both_hvhz("C"))
        table, = build_parameter_tables(conn)[0]
        self.assertEqual(table["scope"], {"kind": "fence_model",
                                          "id": "mfr/bufftech-chesterfield",
                                          "tenant": None})
        conn.close()

    def test_a_document_with_no_product_family_gaps_rather_than_inventing_one(self):
        conn = make_store()
        add_document(conn, product_family=None)
        add_fact(conn, conditions=both_hvhz("C"))
        tables, gaps = build_parameter_tables(conn)
        self.assertEqual(tables[0]["scope"]["kind"], "source_document")
        self.assertIn("parameter_scope_is_a_document", codes(gaps))
        conn.close()

    def test_a_scope_resolver_can_override_the_default(self):
        conn = make_store()
        add_document(conn)
        add_fact(conn, conditions=both_hvhz("C"))
        table, = build_parameter_tables(conn, scope_resolver=lambda r: {
            "kind": "part", "id": "shared/post", "tenant": None})[0]
        self.assertEqual(table["scope"]["id"], "shared/post")
        conn.close()

    def test_machine_agreement_alone_never_reaches_curation_level_2(self):
        """Obligation 6: nothing reaches level 2 without a person having
        compared it to the source image. A1 un-promoted 324 facts over this."""
        conn = make_store()
        add_document(conn)
        add_fact(conn, conditions=both_hvhz("C"),
                 review_status="cross_family_verified")
        table, = build_parameter_tables(conn)[0]
        self.assertEqual(table["rows"][0]["provenance"]["curation_level"], 1)
        conn.close()

    def test_an_unclassified_document_publishes_weak_and_says_so(self):
        conn = make_store()
        add_document(conn, doc_type="unspecified")
        add_fact(conn, conditions=both_hvhz("C"))
        table, gaps = build_parameter_tables(conn)
        self.assertEqual(table[0]["rows"][0]["provenance"]["source_class"],
                         "marketing")
        self.assertIn("source_class_unclassified", codes(gaps))
        conn.close()


class TestItPassesTheSnapshotGate(unittest.TestCase):
    """The output has to survive `snapshot.verify` — the gate it will meet."""

    def test_tables_and_gaps_verify_inside_a_snapshot(self):
        from fence_evidence.snapshot import DECLARED_LISTS, verify
        conn = make_store()
        add_document(conn, document_id="doc-1", sha256=SHA_A, version_id="v1")
        add_fact(conn, conditions=non_hvhz("B"), value='30"')
        add_fact(conn, conditions=both_hvhz("C"), value='36"')
        add_fact(conn, conditions={"exposure_category": "D",
                                   "hvhz_applicability": "unresolved"},
                 value='42"')
        tables, gaps = build_parameter_tables(conn)
        members = {key: [] for key in DECLARED_LISTS}
        members.update({
            "regime": "us_astm",
            "source_docs": [{"content_hash": SHA_A, "source_class": "sealed_approval",
                             "version_status": "active", "version_status_basis": None,
                             "issue_date": None, "expiration_date": None,
                             "superseded_by": [], "also_filed_as": []}],
            "parameters": tables, "gaps": gaps})
        canonical_bytes(members)       # no float, no set, sortable keys
        verify(members)                # closure, gap shape, because.code, `on`
        self.assertTrue(tables and gaps)
        conn.close()


class TestAPersonsCorrectionIsWhatPublishes(unittest.TestCase):
    """G44 at the publishing layer, and it is the worst place for it.

    `curation_level` is set from `review_status`, so a `corrected` fact
    publishes at level 2 — *"a person compared this to the source image"*. If
    the value beside that stamp is the machine's, the snapshot asserts a number
    under a person's authority that the person explicitly rejected. That is the
    exact inversion obligation 6 exists to prevent, in the one section of a
    snapshot that carries numbers rather than text.
    """

    def _corrected(self, machine='24"', person='36"'):
        conn = make_store()
        add_document(conn)
        add_fact(conn, value=machine, review_status="corrected",
                 conditions=non_hvhz("C"))
        conn.execute("UPDATE facts SET reviewed_value=?, "
                     "reviewed_value_normalized=? WHERE 1",
                     (person, float(person.strip('"'))))
        conn.commit()
        return conn

    def test_the_published_quantity_is_the_persons_number(self):
        conn = self._corrected()
        tables, _ = build_parameter_tables(conn)
        self.assertEqual(len(tables), 1)
        row = tables[0]["rows"][0]
        # 36" = 914.4 mm = 914400 thousandths; 24" would be 609600.
        self.assertEqual(row["value"]["amount_milli"], 914400)

    def test_value_raw_leads_with_the_persons_lexeme(self):
        """Publishing the machine's lexeme beside a corrected magnitude shows a
        reader two different numbers and calls one of them the source."""
        conn = self._corrected()
        tables, _ = build_parameter_tables(conn)
        self.assertEqual(tables[0]["rows"][0]["value"]["value_raw"][0], '36"')

    def test_it_still_publishes_at_curation_level_2(self):
        """The level is right — a person did look. It is the value that had to
        catch up with it."""
        conn = self._corrected()
        tables, _ = build_parameter_tables(conn)
        prov = tables[0]["rows"][0]["provenance"]
        self.assertEqual(prov["curation_level"], 2)

    def test_an_uncorrected_fact_is_untouched(self):
        conn = make_store()
        add_document(conn)
        add_fact(conn, value='24"', review_status="accepted",
                 conditions=non_hvhz("C"))
        tables, _ = build_parameter_tables(conn)
        row = tables[0]["rows"][0]
        self.assertEqual(row["value"]["amount_milli"], 609600)
        self.assertEqual(row["value"]["value_raw"], ['24"'])


class TestFenceHeightPublishing(unittest.TestCase):
    """G57. The real corpus shape: two non-overlapping fence_height brackets,
    each carrying a different footing depth. Before the fix they were
    compared as opaque strings and happened not to collide by accident of
    being unequal text; this pins the Interval-based mechanism that replaced
    it, which is correct rather than merely lucky.
    """

    def _two_heights(self, conn):
        add_document(conn)
        add_fact(conn, conditions={**non_hvhz("B"), "fence_height": 'Up to 48"'},
                 value='24"')
        add_fact(conn, conditions={**non_hvhz("B"), "fence_height": '49" to 76"'},
                 value='30"')

    def test_two_non_overlapping_brackets_do_not_collide(self):
        conn = make_store()
        self._two_heights(conn)
        tables, gaps = build_parameter_tables(conn)
        self.assertEqual(len(tables), 1, "a real, disjoint-height pair must publish")
        self.assertFalse([g for g in gaps if g["kind"] == "unmodellable_entity"])
        conn.close()

    def test_domain_shows_range_not_an_enumerated_list(self):
        conn = make_store()
        self._two_heights(conn)
        table = build_parameter_tables(conn)[0][0]
        self.assertEqual(table["domain"]["fence_height"], "range(mm)")
        self.assertEqual(table["condition_scope"]["fence_height"], "bay")
        conn.close()

    def test_each_row_publishes_its_own_interval(self):
        conn = make_store()
        self._two_heights(conn)
        table = build_parameter_tables(conn)[0][0]
        by_value = {r["value"]["amount_milli"]: r["conditions"]["fence_height"]
                    for r in table["rows"]}
        below = by_value[609600]                       # 24"
        above = by_value[762000]                       # 30"
        self.assertIsNone(below["min"])
        self.assertEqual(below["max"]["amount_milli"], 1219200)
        self.assertEqual(above["min"]["amount_milli"], 1244600)
        self.assertEqual(above["max"]["amount_milli"], 1930400)
        conn.close()

    def test_overlapping_brackets_at_the_same_height_still_collide(self):
        """The safety this whole mechanism exists for: an actual conflict —
        same bracket, two different values — must still be caught, not waved
        through because fence_height is now special-cased."""
        conn = make_store()
        add_document(conn)
        for value in ('24"', '30"'):
            add_fact(conn, conditions={**non_hvhz("B"), "fence_height": 'Up to 48"'},
                     value=value)
        tables, gaps = build_parameter_tables(conn)
        self.assertEqual(tables, [])
        self.assertIn("paired_design_point_unmodellable", codes(gaps))
        conn.close()

    def test_the_25_4mm_band_is_reportable_as_an_uncovered_interval(self):
        """Amendment 007 E2, the half that makes it possible at all: a real
        band between two stated brackets, invisible under the old bare
        string, now lands in `uncovered` as an `Interval` instead of nowhere.
        Read literally -- both brackets inclusive as written, so the gap is
        exclusive on both ends of the space between them."""
        conn = make_store()
        self._two_heights(conn)
        table = build_parameter_tables(conn)[0][0]
        band, = [u["fence_height"] for u in table["uncovered"]
                 if "fence_height" in u]
        self.assertEqual(band["min"]["amount_milli"], 1219200)   # 48"
        self.assertEqual(band["max"]["amount_milli"], 1244600)   # 49"
        self.assertFalse(band["min_inclusive"])
        self.assertFalse(band["max_inclusive"])
        conn.close()

    def test_no_band_reported_when_only_one_bracket_is_stated(self):
        conn = make_store()
        add_document(conn)
        add_fact(conn, conditions={**non_hvhz("B"), "fence_height": 'Up to 48"'},
                 value='24"')
        table = build_parameter_tables(conn)[0][0]
        self.assertFalse([u for u in table["uncovered"] if "fence_height" in u])
        conn.close()

    def test_an_unparseable_fence_height_gaps_rather_than_guesses(self):
        conn = make_store()
        add_document(conn)
        add_fact(conn, conditions={**non_hvhz("B"), "fence_height": "see chart"},
                 value='24"')
        tables, gaps = build_parameter_tables(conn)
        self.assertEqual(tables, [])
        self.assertIn("unrecognised_condition_value", codes(gaps))
        conn.close()


if __name__ == "__main__":
    unittest.main()
