"""Statistics of a search, for the report: false discoveries, independent tries, and what the search could ever detect.

* **FDR.** Benjamini-Hochberg and Storey q-values of the one-sided p-values of every validated candidate: of the candidates called
  significant, what share is expected to be false.
* **Independent tries.** Correlated variants (a 20-day and a 21-day average) are one idea tried twice. Candidates whose returns correlate at
  ``|rho| >= cluster_corr`` are joined (connected components); the participation ratio of the correlation eigenvalues is a second estimate.
  The larger of the two is the effective number of tries, so the estimate can only make the search look *more* expensive, never cheaper.
  The ARL still pays for the raw count ``N``; the effective count is shown beside it.
* **Power.** The smallest annual Sharpe the search could detect on this sample with this many tries (Bonferroni level ``alpha / N``, power
  ``power``): ``(z(1 - alpha/N) + z(power)) / sqrt(T)`` per bar. If it is far above any plausible Sharpe the search is pointless before it starts.
"""

from __future__ import annotations

import math
from statistics import NormalDist
from typing import Any

import numpy as np

_N = NormalDist()


def one_sided_p(t: np.ndarray) -> np.ndarray:
    """Normal one-sided p-values of t-statistics (small when the mean is positive)."""
    return np.array([1.0 - _N.cdf(float(x)) for x in np.asarray(t, dtype=float)])


def bh_qvalues(p: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg adjusted p-values (q-values)."""
    p = np.asarray(p, dtype=float)
    m = p.size
    if m == 0:
        return p
    order = np.argsort(p)
    q = p[order] * m / (np.arange(m) + 1.0)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.clip(q, 0.0, 1.0)
    return out


def storey_pi0(p: np.ndarray, lam: float = 0.5) -> float:
    """Share of true nulls among the tests (Storey), clipped to [1/m, 1]: with few tests it stays at 1 (BH)."""
    p = np.asarray(p, dtype=float)
    if p.size < 20:
        return 1.0
    return float(min(1.0, max(float(np.mean(p > lam)) / (1.0 - lam), 1.0 / p.size)))


def storey_qvalues(p: np.ndarray, lam: float = 0.5) -> np.ndarray:
    """Storey q-values: Benjamini-Hochberg scaled by the estimated share of true nulls."""
    return np.clip(bh_qvalues(p) * storey_pi0(p, lam), 0.0, 1.0)


def effective_trials(returns: np.ndarray, cluster_corr: float = 0.95) -> dict[str, Any]:
    """Effective number of independent tries among the rows of a ``(candidates, bars)`` matrix.

    Returns ``n``, ``n_clusters`` (connected components at ``|rho| >= cluster_corr``), ``participation_ratio`` and ``n_eff`` (their maximum, at least 1).
    """
    r = np.asarray(returns, dtype=float)
    if r.ndim != 2 or r.shape[0] < 1:
        raise ValueError("returns must be a (candidates, bars) matrix")
    n = r.shape[0]
    if n == 1 or r.shape[1] < 10:
        return {"n": n, "n_clusters": n, "participation_ratio": float(n), "n_eff": n, "cluster_corr": cluster_corr, "clusters": [[i] for i in range(n)]}
    sd = r.std(axis=1)
    live = sd > 0
    corr = np.corrcoef(r[live]) if live.sum() > 1 else np.ones((1, 1))
    idx = np.flatnonzero(live)
    parent = list(range(n))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a in range(len(idx)):
        for b in range(a + 1, len(idx)):
            if abs(corr[a, b]) >= cluster_corr:
                parent[find(idx[a])] = find(idx[b])
    comps: dict[int, list[int]] = {}
    for i in range(n):
        comps.setdefault(find(i), []).append(i)
    clusters = sorted(comps.values(), key=lambda c: c[0])
    pr = float(n)
    if live.sum() > 1:
        lam = np.clip(np.linalg.eigvalsh(corr), 0.0, None)
        pr = float(lam.sum() ** 2 / np.sum(lam**2)) + float(n - live.sum())
    n_eff = int(min(n, max(len(clusters), math.ceil(pr), 1)))
    return {"n": n, "n_clusters": len(clusters), "participation_ratio": pr, "n_eff": n_eff, "cluster_corr": cluster_corr, "clusters": clusters}


def min_detectable_sharpe(n_trials: int, n_obs: int, periods_per_year: float, *, alpha: float = 0.05, power: float = 0.80) -> dict[str, Any]:
    """Smallest annual Sharpe a search of ``n_trials`` can detect on ``n_obs`` bars (Bonferroni over the tries)."""
    n, t = max(1, int(n_trials)), max(2, int(n_obs))
    z = _N.inv_cdf(1.0 - alpha / n) + _N.inv_cdf(power)
    per_bar = z / math.sqrt(t)
    return {"n_trials": n, "n_obs": t, "alpha": alpha, "power": power, "min_detectable_sharpe_per_bar": per_bar,
            "min_detectable_sharpe_annual": per_bar * math.sqrt(max(periods_per_year, 1.0)), "years": t / max(periods_per_year, 1.0)}


def search_statistics(returns: np.ndarray, ids: list[str], periods_per_year: float, *, fdr_q: float = 0.10, alpha: float = 0.05,
                      power: float = 0.80, cluster_corr: float = 0.95) -> dict[str, Any]:
    """FDR, effective tries and detectable Sharpe of a validated family (``returns`` is ``(candidates, bars)``)."""
    r = np.asarray(returns, dtype=float)
    if r.shape[0] != len(ids):
        raise ValueError("one id per row of the returns matrix")
    n_obs = r.shape[1]
    sd = r.std(axis=1, ddof=1)
    t = np.where(sd > 0, r.mean(axis=1) / np.where(sd > 0, sd, 1.0) * math.sqrt(n_obs), 0.0)
    p = one_sided_p(t)
    bh, st = bh_qvalues(p), storey_qvalues(p)
    eff = effective_trials(r, cluster_corr)
    mde = min_detectable_sharpe(r.shape[0], n_obs, periods_per_year, alpha=alpha, power=power)
    mde_eff = min_detectable_sharpe(eff["n_eff"], n_obs, periods_per_year, alpha=alpha, power=power)
    rows = [{"id": cid, "t_stat": float(t[i]), "p_value": float(p[i]), "q_bh": float(bh[i]), "q_storey": float(st[i]), "fdr_discovery": bool(bh[i] <= fdr_q and t[i] > 0),
             "cluster": next(k for k, c in enumerate(eff["clusters"]) if i in c)} for i, cid in enumerate(ids)]
    return {"candidates": rows, "fdr_q": fdr_q, "fdr_discoveries": [x["id"] for x in rows if x["fdr_discovery"]], "pi0": storey_pi0(p), "effective_trials": eff,
            "detectable": mde, "detectable_effective": mde_eff}


def power_row(n_trials: int, n_obs: int, periods_per_year: float, *, plausible_sharpe: float = 1.5, alpha: float = 0.05, power: float = 0.80) -> dict[str, Any]:
    """Row ``search_power``: can this search detect anything, before it is run?"""
    from monte_neo.verify.checks import check

    d = min_detectable_sharpe(n_trials, n_obs, periods_per_year, alpha=alpha, power=power)
    s = d["min_detectable_sharpe_annual"]
    text = f"{n_trials} tries on {d['years']:.1f} years can only detect an annual Sharpe of {s:.2f} or more (power {power:.0%}, family level {alpha:.0%})"
    if s > plausible_sharpe:
        return check("search_power", "statistics", "warn", text + f": above {plausible_sharpe:g}, which is more than an honest strategy earns; a search this wide on this sample finds nothing real", d)
    return check("search_power", "statistics", "pass", text, d)


__all__ = ["bh_qvalues", "effective_trials", "min_detectable_sharpe", "one_sided_p", "power_row", "search_statistics", "storey_pi0", "storey_qvalues"]
