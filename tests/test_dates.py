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


if __name__ == "__main__":
    unittest.main()
