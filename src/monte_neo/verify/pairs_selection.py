"""Pair-selection bias: the pair was picked from many candidates, so the number of candidates is the number of trials.

Statistical arbitrage researchers screen a universe for cointegrated pairs and trade the best. Screening ``N`` assets
tests ``N (N - 1) / 2`` pairs, and each pair is often tried with several windows and thresholds. The Sharpe ratio of the
winner has to be deflated by all of them (Bailey & Lopez de Prado 2014, the same Deflated Sharpe the rest of the verifier
uses), not by the one pair that was kept.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from monte_neo.verify.stats import deflated_sharpe


def pairs_in_universe(n_assets: int) -> int:
    """Number of distinct pairs among ``n_assets`` assets: ``n (n - 1) / 2``."""
    if n_assets < 2:
        raise ValueError("a universe needs at least 2 assets")
    return math.comb(int(n_assets), 2)


def effective_trials(pairs_tested: int, variants_per_pair: int = 1, extra_trials: int = 1) -> int:
    """Trials to charge the Sharpe ratio: pairs tested x parameter variants per pair x other trials already declared."""
    if pairs_tested < 1 or variants_per_pair < 1 or extra_trials < 1:
        raise ValueError("pairs_tested, variants_per_pair and extra_trials must be at least 1")
    return int(pairs_tested) * int(variants_per_pair) * int(extra_trials)


def selection_report(returns: np.ndarray, pairs_tested: int, *, variants_per_pair: int = 1, extra_trials: int = 1, periods_per_year: float = 252.0) -> dict[str, Any]:
    """Deflated Sharpe of a pair's returns with the pair-selection trials counted.

    Returns:
        The :func:`~monte_neo.verify.stats.deflated_sharpe` report plus ``pairs_tested``, ``variants_per_pair`` and
        ``deflated_sharpe_single`` (the same pair if it had been the only one tried), so the cost of the selection is
        visible.
    """
    n = effective_trials(pairs_tested, variants_per_pair, extra_trials)
    rep = deflated_sharpe(np.asarray(returns, dtype=np.float64), n_trials=n, periods_per_year=periods_per_year)
    single = deflated_sharpe(np.asarray(returns, dtype=np.float64), n_trials=1, periods_per_year=periods_per_year)
    return {**rep, "pairs_tested": int(pairs_tested), "variants_per_pair": int(variants_per_pair), "deflated_sharpe_single": single["deflated_sharpe"]}


__all__ = ["effective_trials", "pairs_in_universe", "selection_report"]
