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

# The same two shapes, found INSIDE a longer lexeme. The corpus prints a date
# with its label attached -- "Expiration Date: 03/13/2018" -- and `value_raw`
# keeps that lexeme whole, so the parser has to look inside it. The digit
# lookarounds stop an acceptance number ("12-1106.11") or an over-long year
# ("03/13/20188") from being mined for a date it does not contain.
_ISO_IN = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
_SLASH_IN = re.compile(r"(?<!\d)(\d{1,2})/(\d{1,2})/(\d{4})(?!\d)")


def normalize_date(raw: str | None) -> dict | None:
    """`raw` -> `{"iso": str | None, "value_raw": [str]}`, or `None` if absent."""
    if not raw:
        return None
    if m := _ISO.match(raw):
        return {"iso": _resolve_iso(*m.groups()), "value_raw": [raw]}
    if m := _SLASH.match(raw):
        return {"iso": _resolve_slash(*m.groups()), "value_raw": [raw]}
    return {"iso": _inside(raw), "value_raw": [raw]}


def _inside(raw: str) -> str | None:
    """The one date a longer lexeme contains, or None.

    Two DIFFERENT dates in one lexeme is refused rather than resolved to
    whichever came first: a lexeme carrying both an approval and an expiration
    does not say which one this field means, and picking is guessing. The same
    date printed twice is one candidate, not a conflict.
    """
    found = {("iso",) + m.groups() for m in _ISO_IN.finditer(raw)}
    found |= {("slash",) + m.groups() for m in _SLASH_IN.finditer(raw)}
    if len(found) != 1:
        return None
    kind, *groups = found.pop()
    return _resolve_iso(*groups) if kind == "iso" else _resolve_slash(*groups)


def _resolve_iso(year_s: str, month_s: str, day_s: str) -> str | None:
    year, month, day = int(year_s), int(month_s), int(day_s)
    if not _valid(year, month, day):
        return None
    return f"{year_s}-{month_s}-{day_s}"


def _resolve_slash(first_s: str, second_s: str, year_s: str) -> str | None:
    first, second, year = int(first_s), int(second_s), int(year_s)
    if first == second:
        # symmetric: month/day order cannot matter
        return _iso_if_valid(year, first, second, year_s)
    if second > 12:
        # second token cannot be a month -> MM/DD/YYYY, unambiguous
        return _iso_if_valid(year, first, second, year_s)
    if first > 12:
        # first token cannot be a month under the MM/DD convention this
        # corpus uses -- do not guess DD/MM
        return None
    # both <= 12 and unequal: genuinely ambiguous, the amendment's own
    # cited case ("05/04/2023")
    return None


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
