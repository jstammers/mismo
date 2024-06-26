"""Utilities for cleaning and preprocessing data."""

from __future__ import annotations

from ..clean._plot import distribution_chart as distribution_chart  # noqa: F401
from ..clean._plot import distribution_dashboard as distribution_dashboard  # noqa: F401
from ._phonetic import double_metaphone as double_metaphone
from ._strings import ngrams as ngrams
from ._strings import norm_whitespace as norm_whitespace
