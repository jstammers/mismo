from __future__ import annotations

from typing import NamedTuple

import numpy as np
import numpy.typing as npt
import pandas as pd


class SetScore(NamedTuple):
    set: LinkSet
    new_covers: npt.NDArray[np.int32]
    n_new_covers: int
    cost: float


# TODO: This still uses pandas and numpy, we should move to ibis if possible.
# Heavily inspired by Dedupe's BlockLearner
# https://github.com/dedupeio/dedupe/blob/f72d4a161bfc66c9e1de9b39e2bd7e01bcad3c49/dedupe/training.py#L36
class LinkSet:
    def __init__(self, links: pd.Series, n_extra_covers: int) -> None:
        self.links = links.drop_duplicates()
        self.n_extra_covers = n_extra_covers

    def cost(self, n_new_covers: int) -> float:
        """The cost of adding this set to our solution.

        See `Greedy Set-Cover Algorithms (1974-1979, Chvatal, Johnson, Lovasz, Stein`
        for details. https://www.cs.ucr.edu/~neal/Young08SetCover.pdf

        We choose the set with the lowest cost.

        If two sets both don't add any extra covers, then this seems like a tie.
        But it's not, we want to pick the set that adds the most new covers.
        So in this case the cost is -n_new_covers.

        If we do add extra covers, then we have to think about the "marginal cost",
        ie how much extra covers are we adding per new cover. Therefore the cost is
        n_extra_covers / n_new_covers.
        """
        if n_new_covers == 0:
            return float("inf")
        if self.n_extra_covers == 0:
            return float(-n_new_covers)
        else:
            return self.n_extra_covers / n_new_covers

    def score(self, uncovered: npt.ArrayLike) -> SetScore:
        new_covers = np.intersect1d(self.links, uncovered)
        n_new_covers = len(new_covers)
        cost = self.cost(n_new_covers)
        return SetScore(self, new_covers, n_new_covers, cost)

    @classmethod
    def make(cls, links: pd.Series, universe: pd.Series) -> LinkSet:
        links = pd.Series(links).drop_duplicates()
        extra_covers = np.setdiff1d(links, universe)
        n_extra_covers = len(extra_covers)
        return cls(links, n_extra_covers)


def set_cover(universe: pd.Series, sets: list[pd.Series]) -> list[int]:
    """
    Solve the Set Cover Problem.

    Takes a universe of elements to cover (in our case these represent DataFrame)
    and a collection of sets (one set for each fingerprinter, each set is the DataFrame
    that that fingerprinter covers). Returns the indexes of the sets whose union
    is the universe, while minimizing the cost. The cost is the number of links
    covered that aren't part of the universe.
    """
    universe = pd.Series(universe).drop_duplicates()
    candidates = [LinkSet.make(s, universe) for s in sets]

    uncovered = universe
    result: list[int] = []
    while True:
        scores = [c.score(uncovered) for c in candidates]
        if not any(score.n_new_covers for score in scores):
            break
        best_set_idx = np.argmin([score.cost for score in scores])
        result.append(best_set_idx)  # type: ignore[arg-type]
        del candidates[best_set_idx]
        best_set = scores[best_set_idx]
        uncovered = np.setdiff1d(uncovered, best_set.new_covers)
    return result
