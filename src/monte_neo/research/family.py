"""Statistics of the whole family of validated candidates: SPA, Reality Check, Romano-Wolf and the cost of the search."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from monte_neo.alpha.multiple_testing import romano_wolf
from monte_neo.verify.checks import check
from monte_neo.verify.reality import reality_check
from monte_neo.verify.stats import expected_max_sharpe, sharpe_per_bar


def search_cost(n_trials: int, n_obs: int, periods_per_year: float) -> dict[str, Any]:
    """Expected maximum Sharpe among ``n_trials`` skill-free strategies on ``n_obs`` bars (False Strategy Theorem).

    Bailey and Lopez de Prado (2014): under no skill the Sharpe estimate has variance about ``1/(n_obs-1)`` per bar, and the best of
    N such estimates is expected to reach ``expected_max_sharpe``. A Sharpe below this number is what luck alone delivers for this search.
    """
    n, t = max(1, int(n_trials)), max(2, int(n_obs))
    per_bar = expected_max_sharpe(n, 1.0 / (t - 1))
    ann = math.sqrt(max(periods_per_year, 1e-9))
    return {"n_trials": n, "n_obs": t, "periods_per_year": float(periods_per_year), "expected_max_sharpe_per_bar": per_bar,
            "expected_max_sharpe_annual": per_bar * ann, "theorem": "False Strategy Theorem, Bailey and Lopez de Prado 2014"}


def family_stats(returns: np.ndarray, ids: list[str], periods_per_year: float, *, alpha: float = 0.05, spa_level: float = 0.10) -> dict[str, Any]:
    """Per-candidate numbers plus SPA, Reality Check, Romano-Wolf and the search cost for a ``(candidates, bars)`` matrix."""
    r = np.asarray(returns, dtype=float)
    if r.ndim != 2 or r.shape[0] != len(ids) or r.shape[0] < 1:
        raise ValueError("returns must be a (candidates, bars) matrix with one row per id")
    m, n = r.shape
    ann = math.sqrt(periods_per_year)
    sr = np.array([sharpe_per_bar(x) for x in r])
    cost = search_cost(m, n, periods_per_year)
    spa = reality_check(r) if m >= 2 else {}
    rw_sig: list[int] = []
    if m >= 2 and n >= 30 and np.isfinite(r).all():
        rw_sig = [int(i) for i in romano_wolf(r.T, alpha=alpha)["details"]["significant"] if sr[int(i)] > 0]  # the test is two-sided; a significant loser is no edge
    elif m == 1 and n >= 30:  # a family of one: the plain one-sided t-test is the whole family test
        rw_sig = [0] if sr[0] * math.sqrt(n) > 1.645 else []
    null = cost["expected_max_sharpe_annual"]
    cands = []
    for i, cid in enumerate(ids):
        s_ann = float(sr[i] * ann)
        cands.append({"id": cid, "sharpe_annual": s_ann, "sharpe_per_bar": float(sr[i]), "t_stat": float(sr[i] * math.sqrt(n)),
                      "stepdown_significant": i in rw_sig, "beats_search_null": bool(s_ann > null)})
    p_spa = spa.get("p_spa")
    best = int(np.argmax(sr))
    return {"n_candidates": m, "n_bars": n, "periods_per_year": float(periods_per_year), "candidates": cands, "best": ids[best],
            "spa": {k: spa[k] for k in ("p_spa", "p_reality_check", "models", "live_models") if k in spa}, "spa_level": spa_level,
            "spa_passes": bool(p_spa is not None and p_spa <= spa_level), "stepdown_significant": [ids[i] for i in rw_sig],
            "search_cost": cost, "best_sharpe_annual": float(sr[best] * ann)}


def family_rows(stats: dict[str, Any]) -> list[dict[str, Any]]:
    """Check rows for the certificate: ``search_cost`` and ``family_spa`` (information, they never change the verdict)."""
    c = stats["search_cost"]
    best, null = stats["best_sharpe_annual"], c["expected_max_sharpe_annual"]
    rows = [check("search_cost", "statistics", "pass" if best > null else "warn",
                  f"best Sharpe {best:.2f} vs {null:.2f} expected from luck alone among {c['n_trials']} candidates on {c['n_obs']} bars", c)]
    spa = stats["spa"]
    if not spa:
        rows.append(check("family_spa", "statistics", "skip", "SPA needs at least two candidates and 100 bars"))
    else:
        rows.append(check("family_spa", "statistics", "pass" if stats["spa_passes"] else "warn",
                          f"SPA p = {spa['p_spa']:.3f}, Reality Check {spa['p_reality_check']:.3f}, {len(stats['stepdown_significant'])} of "
                          f"{stats['n_candidates']} candidates significant after Romano-Wolf", {**spa, "stepdown_significant": stats["stepdown_significant"]}))
    return rows


__all__ = ["family_rows", "family_stats", "search_cost"]
