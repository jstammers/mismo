from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from typing import Any, Callable, Iterable, Literal, TypeVar

import ibis
from ibis import _
from ibis.common.deferred import Deferred
from ibis.expr.types import Column, IntegerColumn, Table

from mismo import _join


def get_name(x) -> str:
    """Find a suitable string representation of `x` to use as a blocker name."""
    if isinstance(x, Deferred):
        return x.__repr__()
    try:
        return x.get_name()
    except AttributeError:
        pass
    if isinstance(x, tuple):
        return "(" + ", ".join(get_name(y) for y in x) + ")"
    if is_iterable(x):
        return "[" + ", ".join(get_name(y) for y in x) + "]"
    return str(x)


def sample_table(
    table: Table,
    n_approx: int,
    *,
    method: Literal["row", "block"] | None = None,
    seed: int | None = None,
) -> Table:
    """Sample a table to approximately n rows.

    Due to the way ibis does sampling, this is not guaranteed to be exactly n rows.
    This is a thin wrapper around
    [ibis's sample method](https://ibis-project.org/reference/expression-tables#ibis.expr.types.relations.Table.sample)
    , which is a wrapper
    around the SAMPLE functionality in SQL. It is important to understand the
    behaviors and limitations of `seed`, the different sampling methods,
    and how they relate to `n_approx`.

    In addition, using `seed` does not guarantee reproducibility if the input
    table is not deterministic, which can happen unexpectedly. For example,
    if you use `.read_csv()` with duckdb, by default it uses a parallel CSV
    reader, which does not guarantee row order. So if you pass that table into
    this function, you could get different results each time. To fix this,
    you can pass `parallel=False` to `.read_csv()`, or use `.order_by()`.

    Parameters
    ----------
    table
        The table to sample
    n_approx
        The approximate number of rows to sample
    method
        The sampling method to use. If None, use "row" for small tables and "block" for
        large tables.

        See [Ibis's documentation on .sample()](https://ibis-project.org/reference/expression-tables.html#ibis.expr.types.relations.Table.sample)
        for more details.
    seed
        The random seed to use for sampling. If None, use a random seed.
    """
    if method is None:
        method = "row" if n_approx <= 2048 * 8 else "block"
    n_available = table.count().execute()
    fraction = n_approx / n_available
    return table.sample(fraction, method=method, seed=seed)


def group_id(keys: str | Column | Iterable[str | Column]) -> IntegerColumn:
    """Number each group from 0 to "number of groups - 1".

    This is equivalent to pandas.DataFrame.groupby(keys).ngroup().
    """
    return ibis.dense_rank().over(ibis.window(order_by=keys)).cast("uint64")


def unique_column_name(t: Table) -> str:
    """Return a column name that is not already in the table"""
    i = 0
    while True:
        name = f"__unique_column_name_{i}__"
        if name not in t.columns:
            return name
        i += 1


def intify_column(t: Table, column: str) -> tuple[Table, Callable[[Table], Table]]:
    """
    Translate column to integer, and return a restoring function.

    This is useful if you want to use integer codes to do some operation, but
    then want to restore the original column.
    """
    if t[column].type().is_integer():
        return t, lambda x: x

    int_col_name = unique_column_name(t)
    augmented = t.mutate(group_id(column).name(int_col_name))
    mapping = augmented.select(int_col_name, column).distinct()
    augmented = augmented.mutate(**{column: _[int_col_name]}).drop(int_col_name)

    def restore(with_int_labels: Table) -> Table:
        return _join.join(
            with_int_labels,
            mapping,
            with_int_labels[column] == mapping[int_col_name],
            how="left",
            lname="{name}_int",
            rname="",
        ).drop(column + "_int", int_col_name)

    return augmented, restore


@contextmanager
def optional_import():
    """
    Raises a more helpful ImportError when an optional dep is missing.

    with optional_import():
        import some_optional_dep
    """
    try:
        yield
    except ImportError as e:
        raise ImportError(
            f"Package `{e.name}` is required for this functionality. "
            "Please install it separately."
        ) from e


V = TypeVar("V")


def promote_list(val: V | Sequence[V]) -> list[V]:
    """Ensure that the value is a list.

    Parameters
    ----------
    val
        Value to promote

    Returns
    -------
    list
    """
    if isinstance(val, list):
        return val
    elif isinstance(val, dict):
        return [val]
    elif is_iterable(val):
        return list(val)
    elif val is None:
        return []
    else:
        return [val]


def is_iterable(o: Any) -> bool:
    """Return whether `o` is iterable and not a :class:`str` or :class:`bytes`.

    Parameters
    ----------
    o : object
        Any python object

    Returns
    -------
    bool

    Examples
    --------
    >>> is_iterable("1")
    False
    >>> is_iterable(b"1")
    False
    >>> is_iterable(iter("1"))
    True
    >>> is_iterable(i for i in range(1))
    True
    >>> is_iterable(1)
    False
    >>> is_iterable([])
    True
    """
    if isinstance(o, (str, bytes)):
        return False

    try:
        iter(o)
    except TypeError:
        return False
    else:
        return True
