"""
Blocking is the process of selecting which pairs of records should be further compared.

Because pairwise comparisons is an O(n^2) operation, it is infeasible to compare all
pairs of records. Therefore, we use blocking to reduce the number of pairs that need
to be compared, hopefully to a manageable level.
"""
from __future__ import annotations

from mismo.block._base import Blocking as Blocking
from mismo.block._base import CartesianBlocker as CartesianBlocker
from mismo.block._base import FunctionBlocker as FunctionBlocker
from mismo.block._base import PBlocker as PBlocker
from mismo.block._base import PBlocking as PBlocking
