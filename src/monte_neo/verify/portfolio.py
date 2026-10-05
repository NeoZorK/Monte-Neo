"""A set of strategies verified together.

Forty strategies in a quarter: one of them can shine by luck. The portfolio view prices that in: the correlation of
their returns gives the number of independent strategies, Reality Check / SPA test the whole list, the best one is
deflated by the effective number of trials, and an equal-weight ensemble is reported next to them.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.verify.reality import reality_check
from monte_neo.verify.returns import annualized_sharpe, strategy_returns
from monte_neo.verify.stats import deflated_sharpe

CLUSTER_CORR = 0.8


def effective_number(corr: np.ndarray) -> float:
    """Participation ratio of the eigenvalues of the correlation matrix: K independent series give K, K clones give 1."""
    w = np.clip(np.linalg.eigvalsh(np.asarray(corr, dtype=np.float64)), 0.0, None)
    return float(w.sum() ** 2 / np.sum(w**2)) if w.sum() > 0 else 1.0


def _clusters(corr: np.ndarray, threshold: float) -> list[int]:
    labels = [-1] * corr.shape[0]
    nxt = 0
    for i in range(corr.shape[0]):
        if labels[i] < 0:
            for j in range(i, corr.shape[0]):
                if labels[j] < 0 and corr[i, j] >= threshold:
                    labels[j] = nxt
            nxt += 1
    return labels


def verify_portfolio(
    df: pd.DataFrame, strategies: list[str | Path | Callable[..., Any]], *, names: list[str] | None = None, samples: int = 300
) -> dict[str, Any]:
    """Per-strategy Sharpe, correlation clusters, effective number, the best strategy deflated, SPA and the equal-weight ensemble."""
    if len(strategies) < 2:
        raise ValueError("a portfolio needs at least two strategies")
    labels = names or [getattr(s, "__name__", str(s)) for s in strategies]
    if len(labels) != len(strategies):
        raise ValueError("names must match the strategies one to one")
    series, ppy = [], 252.0
    for s in strategies:
        r, ppy, _ = strategy_returns(df, s)
        series.append(r)
    size = min(len(r) for r in series)
    mat = np.vstack([r[-size:] for r in series])
    sharpes = np.array([annualized_sharpe(r, ppy) for r in mat])
    flat = mat.std(axis=1) == 0.0
    corr = np.corrcoef(mat + 0.0) if not flat.all() else np.eye(len(mat))
    corr = np.nan_to_num(corr, nan=0.0)
    np.fill_diagonal(corr, 1.0)
    n_eff = effective_number(corr)
    groups = _clusters(corr, CLUSTER_CORR)
    best = int(np.argmax(sharpes))
    dsr = deflated_sharpe(mat[best], n_trials=max(1, round(n_eff)), periods_per_year=ppy)
    rc = reality_check(mat, samples=samples)
    ensemble = mat.mean(axis=0)
    equity = np.cumprod(1.0 + ensemble)
    drawdown = float(np.max(1.0 - equity / np.maximum.accumulate(equity)))
    luck = bool(rc and rc.get("p_spa", 1.0) > 0.05)
    return {
        "strategies": [{"name": labels[i], "sharpe": round(float(sharpes[i]), 3), "cluster": groups[i]} for i in range(len(labels))],
        "correlation": [[round(float(x), 3) for x in row] for row in corr],
        "effective_number": round(n_eff, 2),
        "clusters": len(set(groups)),
        "best": {"name": labels[best], "sharpe": round(float(sharpes[best]), 3), "deflated_sharpe": dsr.get("deflated_sharpe"), "trials_used": max(1, round(n_eff))},
        "reality_check": {"p_reality_check": rc.get("p_reality_check"), "p_spa": rc.get("p_spa")} if rc else None,
        "ensemble": {"sharpe": round(annualized_sharpe(ensemble, ppy), 3), "max_drawdown": round(drawdown, 4)},
        "luck_risk": luck,
        "summary": (
            f"{len(labels)} strategies behave like {n_eff:.1f} independent ones; "
            + ("the best one is not distinguishable from the luckiest of the list (SPA)" if luck else "the best one beats the luckiest of the list (SPA)")
        ),
    }


__all__ = ["effective_number", "verify_portfolio"]
