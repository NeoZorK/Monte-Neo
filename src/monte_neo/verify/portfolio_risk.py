"""Portfolio risk of a set of strategy return series: tail loss, risk concentration, correlations.

* **CVaR / expected shortfall** (historical): the mean return in the worst ``alpha`` share of bars (Rockafellar and
  Uryasev 2000, "Optimization of conditional value-at-risk", Journal of Risk 2(3)).
* **Risk contribution** (Euler allocation): ``RC_i = w_i (S w)_i / (w' S w)`` with ``S`` the covariance matrix; the
  contributions sum to 1. **Effective number of bets** is ``exp(entropy)`` of the positive contributions (Meucci 2009,
  "Managing diversification", Risk 22(5), approximated on the asset basis), so one dominant strategy gives about 1.
* **Tail dependence and correlation stress**: see :mod:`monte_neo.verify.portfolio_tail` (``checks`` of the report).
* **Tail correlation**: the average pairwise correlation on the worst 10 % of ensemble bars next to the full-sample one;
  strategies that look independent but fall together are the usual surprise.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

CVAR_ALPHA = 0.05
TAIL_SHARE = 0.10
CONCENTRATION_WARN = 0.5  # one strategy carrying over half of the risk


def cvar(r: np.ndarray, alpha: float = CVAR_ALPHA) -> float:
    """Mean of the worst ``alpha`` share of returns (at least one bar); a negative number is a loss."""
    x = np.sort(np.asarray(r, dtype=np.float64))
    k = max(1, int(math.ceil(alpha * x.size)))
    return float(x[:k].mean())


def _mean_offdiag(c: np.ndarray) -> float:
    k = c.shape[0]
    return float((c.sum() - np.trace(c)) / (k * (k - 1))) if k > 1 else 0.0


def portfolio_risk(mat: np.ndarray, names: list[str], weights: np.ndarray | None = None, alpha: float = CVAR_ALPHA) -> dict[str, Any]:
    """Risk report for ``mat`` (strategies x bars); equal weights unless given.

    Raises:
        ValueError: Fewer than 2 strategies or 20 bars, a weight vector of the wrong size or not summing to a positive number.
    """
    m = np.asarray(mat, dtype=np.float64)
    if m.ndim != 2 or m.shape[0] < 2 or m.shape[1] < 20:
        raise ValueError("need a matrix of at least 2 strategies and 20 bars")
    k = m.shape[0]
    w = np.full(k, 1.0 / k) if weights is None else np.asarray(weights, dtype=np.float64)
    if w.shape != (k,) or w.sum() <= 0 or (w < 0).any():
        raise ValueError("weights must be non-negative, one per strategy, with a positive sum")
    w = w / w.sum()
    ens = w @ m
    cov = np.cov(m)
    var = float(w @ cov @ w)
    rc = (w * (cov @ w) / var) if var > 0 else w.copy()
    pos = np.clip(rc, 1e-12, None)
    pos = pos / pos.sum()
    n_bets = float(np.exp(-np.sum(pos * np.log(pos))))
    corr = np.nan_to_num(np.corrcoef(m), nan=0.0)
    tail = ens <= np.quantile(ens, TAIL_SHARE)
    tail_corr = np.nan_to_num(np.corrcoef(m[:, tail]), nan=0.0) if int(tail.sum()) >= 3 else corr
    top = int(np.argmax(rc))
    from monte_neo.verify.portfolio_tail import (
        correlation_stress_row,
        stressed_cvar,
        tail_dependence,
        tail_dependence_row,
    )

    td = tail_dependence(m)
    stress = stressed_cvar(m, w, alpha)
    return {
        "tail_dependence": td, "correlation_stress": stress,
        "checks": [tail_dependence_row(td), correlation_stress_row(stress)],
        "weights": [float(x) for x in w], "alpha": float(alpha),
        "ensemble_cvar": cvar(ens, alpha), "strategy_cvar": {n: cvar(m[i], alpha) for i, n in enumerate(names)},
        "risk_contribution": {n: float(rc[i]) for i, n in enumerate(names)},
        "effective_bets": n_bets, "top_risk": {"name": names[top], "share": float(rc[top])},
        "concentrated": bool(rc[top] > CONCENTRATION_WARN),
        "mean_correlation": _mean_offdiag(corr), "tail_correlation": _mean_offdiag(tail_corr),
        "tail_bars": int(tail.sum()),
    }


__all__ = ["CONCENTRATION_WARN", "CVAR_ALPHA", "TAIL_SHARE", "cvar", "portfolio_risk"]
