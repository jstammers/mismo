from __future__ import annotations

from typing import Literal

import ibis
from ibis.expr import types as ir

from mismo import _util
from mismo.sets import jaccard as _jaccard


def double_metaphone(s: ir.StringValue) -> ir.ArrayValue[ir.StringValue]:
    """Double Metaphone phonetic encoding

    This requires the [doublemetaphone](https://github.com/dedupeio/doublemetaphone)
    package to be installed.
    You can install it with `python -m pip install DoubleMetaphone`.
    This uses a python UDF so it is going to be slow.

    Examples
    --------
    >>> from mismo.text import double_metaphone
    >>> double_metaphone("catherine").execute()
    ['K0RN', 'KTRN']
    >>> double_metaphone("").execute()
    ['', '']
    >>> double_metaphone(None).execute() is None
    True
    """
    s = _util.ensure_ibis(s, "string")
    return _dm_udf(s)


@ibis.udf.scalar.python(signature=(("string",), "array<string>"))
def _dm_udf(s):
    with _util.optional_import("DoubleMetaphone"):
        from doublemetaphone import doublemetaphone

    return doublemetaphone(s)


# TODO: this isn't portable between backends
@ibis.udf.scalar.builtin
def damerau_levenshtein(a: str, b: str) -> int:
    """
    The number of adds, deletes, substitutions, and transposes to get from `a` to `b`.

    This is the levenstein distance with the addition of transpositions as
    a possible operation.
    """


def levenshtein_ratio(s1: ir.StringValue, s2: ir.StringValue) -> ir.FloatingValue:
    """The levenshtein distance between two strings, normalized to be between 0 and 1.

    The ratio is defined as `(lenmax - ldist)/lenmax` where

    - `ldist` is the regular levenshtein distance
    - `lenmax` is the maximum length of the two strings
      (eg the largest possible edit distance)

    This makes it so that the ratio is 1 when the strings are the same and 0
    when they are completely different.
    By doing this normalization, the ratio is always between 0 and 1, regardless
    of the length of the strings.

    Parameters
    ----------
    s1:
        The first string

    s2:
        The second string

    Returns
    -------
    lev_ratio:
        The ratio of the Levenshtein edit cost to the maximum string length

    Examples
    --------
    >>> from mismo.text import levenshtein_ratio
    >>> levenshtein_ratio("mile", "mike").execute()
    np.float64(0.75)
    >>> levenshtein_ratio("mile", "mile").execute()
    np.float64(1.0)
    >>> levenshtein_ratio("mile", "").execute()
    np.float64(0.0)
    >>> levenshtein_ratio("", "").execute()
    np.float64(nan)
    """
    return _dist_ratio(s1, s2, lambda a, b: a.levenshtein(b))


def damerau_levenshtein_ratio(
    s1: ir.StringValue, s2: ir.StringValue
) -> ir.FloatingValue:
    """Like levenshtein_ratio, but with the Damerau-Levenshtein distance.

    See Also
    --------
    - [damerau_levenshtein()][mismo.text.damerau_levenshtein]
    - [levenshtein_ratio()][mismo.text.levenshtein_ratio]
    """
    return _dist_ratio(s1, s2, damerau_levenshtein)


def _dist_ratio(s1, s2, dist):
    s1 = _util.ensure_ibis(s1, "string")
    s2 = _util.ensure_ibis(s2, "string")
    lenmax = ibis.greatest(s1.length(), s2.length())
    return (lenmax - dist(s1, s2)) / lenmax


def jaccard(
    s1: ir.StringValue,
    s2: ir.StringValue,
    *,
    tokenize: Literal["by_character", "on_whitespace"],
) -> ir.FloatingValue:
    """The Jaccard similarity between two strings.

    This is a measure of the overlap of the number of elements in two sets of unique
    tokens, where tokenization is defined by `tokenize`. Tokenization by character is
    most suited for situations where character-level variations are important,
    such as with typos, short text or languages without clear word boundaries
    (e.g. Japanese and Chinese).
    In contrast, word-level similarity is preferred when the semantic content of the
    text is more important, rather than minor variations in the spelling or syntax.

    Examples
    --------
    >>> import ibis
    >>> from mismo.text import jaccard

    `tokenize='by_character'` replicates the implementation built into duckdb.
    >>> jaccard(ibis.literal("foo"),
    ... ibis.literal("foo"), tokenize='by_character').execute()
    np.float64(1.0)
    >>> jaccard(ibis.literal("foo"),
    ... ibis.literal("food"), tokenize='by_character').execute()
    np.float64(0.6666666666666666)
    >>> jaccard(ibis.null(str),
    ... ibis.literal("food"), tokenize='by_character').execute()
    np.float64(nan)

    word-level similarity can be achieved using `tokenize='on_whitespace'`.
    >>> jaccard(ibis.literal("Paris is the capital of France"),
    ... ibis.literal("The largest city in France is Paris"),
    ... tokenize='on_whitespace').execute()
    np.float64(0.3)

    """
    if tokenize == "by_character":
        reg = ""
    elif tokenize == "on_whitespace":
        reg = r"\s+"
    #
    t1 = s1.re_split(reg).unique()
    t2 = s2.re_split(reg).unique()
    return _jaccard(t1, t2)


@ibis.udf.scalar.builtin(name="jaro_similarity")
def _jaro_similarity(s1: str, s2: str) -> float:
    ...


def jaro_similarity(s1: ir.StringValue, s2: ir.StringValue) -> ir.FloatingValue:
    """The jaro similarity between `s1` and `s2`.

    This is a number between 0 and 1, defined as
    `sj = 1/3 * (m/l_1 + m/l_2 + (m-t)/m)`

    where `m` is the number of matching characters between s1 and s2 and `t` is the
    number of transpositions between `s1` and `s2`.

    Examples
    --------
    >>> import ibis
    >>> from mismo.text import jaro_similarity
    >>> jaro_similarity(ibis.literal("foo"), ibis.literal("foo")).execute()
    np.float64(1.0)
    >>> jaro_similarity(ibis.literal("foo"), ibis.literal("food")).execute()
    np.float64(0.9166666666666666)
    >>> jaro_similarity(ibis.null(str), ibis.literal("food")).execute()
    np.float64(nan)

    Be aware: comparing to an empty string always has a similarity of 0:

    >>> jaro_similarity(ibis.literal("a"), ibis.literal("")).execute()
    np.float64(0.0)
    >>> jaro_similarity(ibis.literal(""), ibis.literal("")).execute()
    np.float64(0.0)
    """
    return _jaro_similarity(s1, s2)


# TODO: This isn't portable between backends
@ibis.udf.scalar.builtin(name="jaro_winkler_similarity")
def _jaro_winkler_similarity(s1: str, s2: str) -> float:
    ...


def jaro_winkler_similarity(s1: ir.StringValue, s2: ir.StringValue) -> ir.FloatingValue:
    """The Jaro-Winkler similarity between `s1` and `s2`.

    The Jaro-Winkler similarity is a variant of the Jaro similarity that
    measures the number of edits between two strings
    and places a higher importance on the prefix.

    It is defined as `(sjw = sj + l * p * (1-sj)`
    where `sj` is the Jaro similarity, `l` is the length of the common prefix  (up to a
    maximum of 4) and `p` is a constant scaling factor (up to a maximum of 0.25, but
    typically set to 0.1)

    Examples
    --------
    >>> import ibis
    >>> from mismo.text import jaro_winkler_similarity
    >>> jaro_winkler_similarity(ibis.literal("foo"), ibis.literal("foo")).execute()
    np.float64(1.0)
    >>> jaro_winkler_similarity(ibis.literal("foo"), ibis.literal("food")).execute()
    np.float64(0.9416666666666667)
    >>> jaro_winkler_similarity(ibis.null(str), ibis.literal("food")).execute()
    np.float64(nan)

    Be aware: comparing to an empty string always has a similarity of 0:

    >>> jaro_winkler_similarity(ibis.literal("a"), ibis.literal("")).execute()
    np.float64(0.0)
    >>> jaro_winkler_similarity(ibis.literal(""), ibis.literal("")).execute()
    np.float64(0.0)
    """
    return _jaro_winkler_similarity(s1, s2)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
