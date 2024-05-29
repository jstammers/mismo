from __future__ import annotations

from typing import Literal, overload

import ibis
from ibis.expr import types as ir

from mismo._array import array_combinations, array_min
from mismo._util import get_column
from mismo.compare import MatchLevels
from mismo.text import damerau_levenshtein


@overload
def clean_phone_number(phones: ir.Table) -> ir.Table: ...


@overload
def clean_phone_number(phones: ir.ArrayValue) -> ir.ArrayValue: ...


@overload
def clean_phone_number(phones: ir.StringValue) -> ir.StringValue: ...


def clean_phone_number(numbers):
    """Extracts any 10-digit number from a string.

    Drops leading 1 country code if present.

    Parsing failures are returned as NULL.

    Empty strings are returned as NULL

    If a number looks bogus, ie it contains "0000", "9999", or "12345",
    it is set to NULL.
    """
    if isinstance(numbers, ir.Table):
        return numbers.mutate(phones=clean_phone_number(numbers.phones))
    elif isinstance(numbers, ir.ArrayValue):
        return numbers.map(_clean_phone_number).filter(lambda x: x.notnull()).unique()
    elif isinstance(numbers, ir.StringValue):
        return _clean_phone_number(numbers)
    raise ValueError(f"Unexpected type {type(numbers)}")


def _clean_phone_number(numbers: ir.StringValue) -> ir.StringValue:
    x = numbers
    x = x.cast("string")
    x = x.re_replace(r"[^0-9]", "")
    x = x.re_extract(r"1?(\d{10})", 1)
    x = x.nullif("")
    x = _drop_bogus_numbers(x)
    return x


def _drop_bogus_numbers(numbers: ir.StringValue) -> ir.StringValue:
    bogus_substrings = ["0000", "9999", "12345"]
    pattern = "|".join(bogus_substrings)
    is_bogus = numbers.re_search(".*" + pattern + ".*")
    return is_bogus.ifelse(None, numbers)


class PhoneMatchLevels(MatchLevels):
    """How closely two phone numbers match."""

    EXACT = 0
    """The numbers are exactly the same."""
    NEAR = 1
    """The numbers have a small edit distance."""
    ELSE = 2
    """None of the above."""


def match_level(
    p1: ir.StringValue,
    p2: ir.StringValue,
    *,
    native_representation: Literal["integer", "string"] = "integer",
) -> PhoneMatchLevels:
    """Match level of two phone numbers.

    Assumes the phone numbers have already been cleaned and normalized.

    Parameters
    ----------
    p1 :
        The first phone number.
    p2 :
        The second phone number.

    Returns
    -------
    level:
        The match level.
    """

    def f(level: MatchLevels):
        if native_representation == "string":
            return level.as_string()
        else:
            return level.as_integer()

    raw = (
        ibis.case()
        .when(p1 == p2, f(PhoneMatchLevels.EXACT))
        .when(damerau_levenshtein(p1, p2) <= 1, f(PhoneMatchLevels.NEAR))
        .else_(f(PhoneMatchLevels.ELSE))
        .end()
    )
    return PhoneMatchLevels(raw)


class PhonesDimension:
    """A dimension of phone numbers."""

    def __init__(
        self,
        column: str,
        *,
        column_parsed: str = "{column}_parsed",
        column_compared: str = "{column}_compared",
    ):
        """Initialize the dimension.

        Parameters
        ----------
        column :
            The name of the column that holds a array<string> of phone numbers.
        column_parsed :
            The name of the column that will be filled with the parsed phone numbers.
        column_compared :
            The name of the column that will be filled with the comparison results.
        """
        self.column = column
        self.column_parsed = column_parsed.format(column=column)
        self.column_compared = column_compared.format(column=column)

    def prep(self, t: ir.Table) -> ir.Table:
        """Add a column with the parsed and normalized phone numbers."""
        return t.mutate(
            get_column(t, self.column).map(clean_phone_number).name(self.column_parsed)
        )

    def compare(self, t: ir.Table) -> ir.Table:
        """Add a column with the best match between all pairs of phone numbers."""
        le = t[self.column_parsed + "_l"]
        ri = t[self.column_parsed + "_r"]
        pairs = array_combinations(le, ri)
        min_level = array_min(
            pairs.map(lambda pair: match_level(pair.l, pair.r).as_integer())
        ).fillna(PhoneMatchLevels.ELSE.as_integer())
        return t.mutate(
            PhoneMatchLevels(min_level).as_string().name(self.column_compared)
        )