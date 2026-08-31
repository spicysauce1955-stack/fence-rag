"""Amendment 002 -- a typed `Date`: `{iso: str | null, value_raw: [str]}`.

The amendment (docs/integration/amendments/002-typed-date-and-absent-date-ordering.md)
gives the outcome contract -- `iso` is null when the source states no date, or
states one that cannot be normalised without guessing, citing "05/04/2023" as
ambiguous on its face -- but no parsing algorithm. This module is that
algorithm, not a quote from the amendment.

Every date this platform has ever recorded is `MM/DD/YYYY` (the corpus is the
US/ASTM track, never GB) or already ISO (test fixtures, and any future
publisher that writes ISO directly). A day > 12 makes the order unambiguous;
both fields <= 12 is the amendment's own cited case and stays `iso: null`
rather than guess. `value_raw` always keeps the original lexeme, ambiguous or
not, so a curator can read what the source actually said.
"""
from __future__ import annotations

import re
from datetime import date

_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_SLASH = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")


def normalize_date(raw: str | None) -> dict | None:
    """`raw` -> `{"iso": str | None, "value_raw": [str]}`, or `None` if absent."""
    if not raw:
        return None
    if m := _ISO.match(raw):
        year, month, day = (int(g) for g in m.groups())
        iso = raw if _valid(year, month, day) else None
        return {"iso": iso, "value_raw": [raw]}
    if m := _SLASH.match(raw):
        first, second, year = (int(g) for g in m.groups())
        year_s = m.group(3)
        if first == second:
            # symmetric: month/day order cannot matter
            iso = _iso_if_valid(year, first, second, year_s)
        elif second > 12:
            # second token cannot be a month -> MM/DD/YYYY, unambiguous
            iso = _iso_if_valid(year, first, second, year_s)
        elif first > 12:
            # first token cannot be a month under the MM/DD convention this
            # corpus uses -- do not guess DD/MM
            iso = None
        else:
            # both <= 12 and unequal: genuinely ambiguous, the amendment's own
            # cited case ("05/04/2023")
            iso = None
        return {"iso": iso, "value_raw": [raw]}
    return {"iso": None, "value_raw": [raw]}


def _valid(year: int, month: int, day: int) -> bool:
    try:
        date(year, month, day)
        return True
    except ValueError:
        return False


def _iso_if_valid(year: int, month: int, day: int, year_s: str) -> str | None:
    if not _valid(year, month, day):
        return None
    return f"{year_s}-{month:02d}-{day:02d}"
