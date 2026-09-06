"""Amendment 002: `normalize_date()` against the corpus's real values and the
amendment's own cited edge cases."""
import unittest

import context  # noqa: F401
from fence_evidence.dates import normalize_date


class TestAbsent(unittest.TestCase):
    def test_none_stays_none(self):
        self.assertIsNone(normalize_date(None))

    def test_empty_string_is_absent(self):
        self.assertIsNone(normalize_date(""))


class TestRealCorpusValues(unittest.TestCase):
    """The five (issue_date, expiration_date) values actually in the store."""

    def test_symmetric_day_and_month_normalises(self):
        self.assertEqual(normalize_date("04/04/2013"),
                         {"iso": "2013-04-04", "value_raw": ["04/04/2013"]})

    def test_unambiguous_because_day_exceeds_twelve(self):
        self.assertEqual(normalize_date("04/24/2025"),
                         {"iso": "2025-04-24", "value_raw": ["04/24/2025"]})
        self.assertEqual(normalize_date("03/13/2029"),
                         {"iso": "2029-03-13", "value_raw": ["03/13/2029"]})
        self.assertEqual(normalize_date("04/04/2028"),
                         {"iso": "2028-04-04", "value_raw": ["04/04/2028"]})

    def test_the_amendments_own_cited_ambiguous_example(self):
        # 05/04/2023 -- both fields <= 12, unequal: could be May 4 or April 5.
        self.assertEqual(normalize_date("05/04/2023"),
                         {"iso": None, "value_raw": ["05/04/2023"]})


class TestAlreadyIso(unittest.TestCase):
    def test_iso_passes_through(self):
        self.assertEqual(normalize_date("2015-01-01"),
                         {"iso": "2015-01-01", "value_raw": ["2015-01-01"]})

    def test_invalid_iso_calendar_date_is_null(self):
        self.assertEqual(normalize_date("2015-02-30"),
                         {"iso": None, "value_raw": ["2015-02-30"]})


class TestUnparseable(unittest.TestCase):
    def test_month_over_twelve_is_not_guessed_as_day_month(self):
        self.assertEqual(normalize_date("13/05/2023"),
                         {"iso": None, "value_raw": ["13/05/2023"]})

    def test_invalid_calendar_date_is_null_not_raised(self):
        # 30 can't be a month, so this parses as month=02, day=30 -- which
        # doesn't exist.
        self.assertEqual(normalize_date("02/30/2020"),
                         {"iso": None, "value_raw": ["02/30/2020"]})

    def test_garbage_lexeme_keeps_value_raw(self):
        self.assertEqual(normalize_date("sometime in spring"),
                         {"iso": None, "value_raw": ["sometime in spring"]})


class TestLabelledLexeme(unittest.TestCase):
    """A source prints its date with the label attached, and `value_raw` keeps
    the lexeme whole. Requiring the WHOLE string to be a date made every
    published `SourceDoc` date `iso: null` -- 16 of 24 of them unambiguous --
    so obligation 16's lapse check could not run on anything. See G87."""

    def test_the_lexeme_the_corpus_actually_prints(self):
        self.assertEqual(
            normalize_date("Expiration Date: 03/13/2018"),
            {"iso": "2018-03-13",
             "value_raw": ["Expiration Date: 03/13/2018"]})

    def test_value_raw_keeps_the_whole_lexeme_not_the_extracted_date(self):
        got = normalize_date("Approval Date: 05/25/2027")
        self.assertEqual(got["value_raw"], ["Approval Date: 05/25/2027"])
        self.assertEqual(got["iso"], "2027-05-25")

    def test_a_labelled_iso_date_also_resolves(self):
        self.assertEqual(normalize_date("Issued 2015-01-01"),
                         {"iso": "2015-01-01", "value_raw": ["Issued 2015-01-01"]})

    def test_ambiguity_still_refuses_when_labelled(self):
        # Amendment 002's own cited case; the label must not change the answer.
        self.assertEqual(
            normalize_date("Approval Date: 05/04/2023"),
            {"iso": None, "value_raw": ["Approval Date: 05/04/2023"]})

    def test_two_dates_in_one_lexeme_are_refused_not_guessed(self):
        raw = "Approval Date: 03/13/2018 Expiration Date: 03/13/2023"
        self.assertEqual(normalize_date(raw), {"iso": None, "value_raw": [raw]})

    def test_the_same_date_twice_is_one_candidate(self):
        raw = "Expiration 03/13/2018 (03/13/2018)"
        self.assertEqual(normalize_date(raw),
                         {"iso": "2018-03-13", "value_raw": [raw]})

    def test_an_invalid_calendar_date_stays_null_when_labelled(self):
        self.assertEqual(normalize_date("Expiration Date: 02/30/2020"),
                         {"iso": None, "value_raw": ["Expiration Date: 02/30/2020"]})

    def test_a_day_first_lexeme_is_still_not_guessed(self):
        self.assertEqual(normalize_date("Approval Date: 13/05/2023"),
                         {"iso": None, "value_raw": ["Approval Date: 13/05/2023"]})

    def test_a_longer_digit_run_is_not_mined_for_a_date(self):
        # An acceptance number must not become a date.
        raw = "Acceptance No 12-1106.11"
        self.assertEqual(normalize_date(raw), {"iso": None, "value_raw": [raw]})

    def test_a_five_digit_year_is_not_a_date(self):
        raw = "Expiration Date: 03/13/20188"
        self.assertEqual(normalize_date(raw), {"iso": None, "value_raw": [raw]})


if __name__ == "__main__":
    unittest.main()
