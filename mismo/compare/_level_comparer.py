from __future__ import annotations

from typing import Callable, Iterable, Iterator, NamedTuple, overload

from ibis.common.deferred import Deferred
from ibis.expr import types as ir

from mismo import _util


class AgreementLevel(NamedTuple):
    """A level of agreement such as *exact*, *phonetic*, or *within_1_day*.

    A AgreementLevel is a named condition that determines whether a record pair
    matches that level.
    """

    name: str
    """The name of the level. Should be short and unique within a LevelComparer.

    Examples:

    - "exact"
    - "misspelling"
    - "phonetic"
    - "within_1_day"
    - "within_1_km"
    - "within_10_percent"
    """
    condition: bool | Deferred | Callable[[ir.Table], ir.BooleanValue]
    """
    A condition that determines whether a record pair matches this level.

    Note that if this AgreementLevel is used in conjunction with other
    AgreementLevels, the condition is implcitly dependent on the previous
    levels. For example, if the previous level's condition is
    `_.name_l.upper() == _.name_r.upper()`, then if this level's condition is
    `_.name_l == _.name_r`, this level is useless, and will match no records pairs,
    because they all would have been matched by the previous level.

    Examples:

    - `_.name_l == _.name_r`
    - `lambda t: (t.cost_l - t.cost_r).abs() / t.cost_l < 0.1`
    - `True`
    """

    def is_match(self, pairs: ir.Table) -> ir.BooleanColumn:
        """Return a boolean column for if the record pair matches this level."""
        return _util.get_column(pairs, self.condition)


_ELSE_LEVEL = AgreementLevel("else", True)


class LevelComparer:
    """
    Assigns a level of similarity to record pairs based on one dimension, e.g. *name*

    This acts like an ordered, dict-like collection of
    [AgreementLevels][mismo.compare.AgreementLevel].
    You can access the levels by index or by name, or iterate over them.
    The last level is always an `else` level, which matches all record pairs
    if none of the previous levels matched.
    """

    def __init__(
        self,
        name: str,
        levels: Iterable[
            AgreementLevel
            | tuple[str, bool | Deferred | Callable[[ir.Table], ir.BooleanValue]]
        ],
    ):
        """Create a LevelComparer.

        Parameters
        ----------
        name :
            The name of the comparer, eg "date", "address", "latlon", "price".
        levels :
            The levels of agreement. Can be either actual AgreementLevel objects,
            or tuples of (name, condition) that will be converted into AgreementLevels.

            You may include an `else` level as a final
            level that matches everything, or it will be added automatically if
            you don't include one.
        """
        self._name = name
        self._levels, self._lookup = self._parse_levels(levels)

    @property
    def name(self) -> str:
        """The name of the comparer, eg "date", "address", "latlon", "price"."""
        return self._name

    @overload
    def __getitem__(self, name_or_index: str | int) -> AgreementLevel: ...

    @overload
    def __getitem__(self, name_or_index: slice) -> tuple[AgreementLevel, ...]: ...

    def __getitem__(self, name_or_index):
        """Get a level by name or index."""
        if isinstance(name_or_index, (int, slice)):
            return self._levels[name_or_index]
        return self._lookup[name_or_index]

    def __iter__(self) -> Iterator[AgreementLevel]:
        """Iterate over the levels, including the ELSE level."""
        return iter(self._levels)

    def __len__(self) -> int:
        """The number of levels, including the ELSE level."""
        return len(self._levels)

    def __call__(self, pairs: ir.Table) -> ir.StringColumn:
        """Label each record pair with the level that it matches.

        Go through the levels in order. If a record pair matches a level, label ir.
        If none of the levels match a pair, it labeled as "else".

        Parameters
        ----------
        pairs : Table
            A table of record pairs.
        Returns
        -------
        labels : StringColumn
            The labels for each record pair.
        """
        # Skip the ELSE level, do that ourselves. This is to avoid if someone
        # mis-specifies the ELSE level condition so that it doesn't
        # match everything.
        cases = [(level.is_match(pairs), level.name) for level in self[:-1]]
        return _util.cases(cases, "else").name(self.name)

    def __repr__(self) -> str:
        levels_str = ", ".join(repr(level) for level in self)
        return f"{self.__class__.__name__}(name={self.name}, levels=[{levels_str}])"

    @classmethod
    def _parse_levels(
        cls,
        levels: Iterable[AgreementLevel],
    ) -> tuple[tuple[AgreementLevel], dict[str | int, AgreementLevel]]:
        levels = tuple(AgreementLevel(*level) for level in levels)
        rest, last = levels[:-1], levels[-1]
        for level in rest:
            if level.name == "else":
                raise ValueError(
                    f"ELSE AgreementLevel must be the last level in a {cls.__name__}."
                )
        if last.name != "else":
            levels = (*levels, _ELSE_LEVEL)

        lookup = {}
        for i, level in enumerate(levels):
            if level.name in lookup:
                raise ValueError(f"Duplicate level name: {level.name}")
            lookup[level.name] = level
            lookup[i] = level
        return levels, lookup
