"""White's Reality Check and Hansen's test for Superior Predictive Ability (SPA) for a parameter search.

The Deflated Sharpe prices the *number* of trials. These two tests answer the direct question of a
search: "the best of these combinations beat cash. Is that more than luck, given that all of them
were tried?" They use the per-bar returns of every combination that ``verify_grid`` already has.

* **Reality Check** (White, 2000): the statistic is the largest scaled mean return over the
  combinations; its null distribution comes from a block bootstrap of the returns re-centred on
  their means.
* **SPA** (Hansen, 2005): the same idea with studentised statistics and a re-centring that drops
  clearly bad combinations from the null, so a pile of junk combinations does not hide a real edge.

The benchmark is cash (zero return). Blocks are circular with the cube-root length used elsewhere
in the verifier, the seed is fixed and resampling uses prefix sums in chunks, so a search of 512
combinations over 100 000 bars stays within a few hundred megabytes.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from monte_neo.verify.checks import check
from monte_neo.verify.confidence import block_length

SAMPLES = 1000
SEED = 20260930
MIN_BARS = 100
MIN_MODELS = 2
WARN_AT = 0.10
CHUNK_CELLS = 8_000_000  # (models x resamples x blocks) cells per chunk


def reality_check(returns: np.ndarray, *, samples: int = SAMPLES, seed: int = SEED) -> dict[str, Any]:
    """Reality Check and SPA p-values for a ``(models, bars)`` matrix of per-bar returns; ``{}`` if not computable."""
    r = np.asarray(returns, dtype=np.float64)
    if r.ndim != 2:
        return {}
    r = np.where(np.isfinite(r), r, 0.0)
    models, n = r.shape
    length = block_length(n)
    blocks = n // length
    if models < MIN_MODELS or n < MIN_BARS or blocks < 5:
        return {}
    ext = np.concatenate([r, r[:, : length - 1]], axis=1)  # a block may wrap around the end
    prefix = np.concatenate([np.zeros((models, 1)), np.cumsum(ext, axis=1)], axis=1)
    total = blocks * length
    mean = r.mean(axis=1)
    scale = math.sqrt(total)
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, n, size=(int(samples), blocks))
    step = max(1, CHUNK_CELLS // max(1, models * blocks))
    boot = np.empty((models, int(samples)))
    for lo in range(0, int(samples), step):
        idx = starts[lo : lo + step]
        sums = (prefix[:, idx + length] - prefix[:, idx]).sum(axis=2)  # models x chunk
        boot[:, lo : lo + idx.shape[0]] = sums / total
    spread = scale * (boot - mean[:, None])  # bootstrap distribution of the centred, scaled means
    omega = spread.std(axis=1, ddof=1)
    live = omega > 1e-12  # a model that never trades has no variance and cannot beat cash
    if not live.any():
        return {}
    stat_rc = float(np.max(scale * mean[live]))
    null_rc = spread[live].max(axis=0)
    p_rc = (1.0 + float(np.sum(null_rc >= stat_rc))) / (int(samples) + 1.0)

    t_k = scale * mean[live] / omega[live]
    stat_spa = float(max(0.0, t_k.max()))
    poor = t_k <= -math.sqrt(2.0 * math.log(math.log(max(total, 3))))
    centre = np.where(poor, mean[live], 0.0)
    z = scale * (boot[live] - mean[live][:, None] + centre[:, None]) / omega[live][:, None]
    null_spa = np.maximum(z.max(axis=0), 0.0)
    p_spa = (1.0 + float(np.sum(null_spa >= stat_spa))) / (int(samples) + 1.0)
    best = int(np.flatnonzero(live)[int(np.argmax(t_k))])
    return {
        "method": "White Reality Check and Hansen SPA, circular block bootstrap",
        "models": int(models),
        "live_models": int(live.sum()),
        "bars": int(n),
        "block_bars": int(length),
        "samples": int(samples),
        "p_reality_check": round(p_rc, 4),
        "p_spa": round(p_spa, 4),
        "best_model": best,
        "best_t": round(float(t_k.max()), 3),
    }


def reality_row(info: dict[str, Any]) -> dict[str, Any]:
    """``reality_check``: the best combination against the whole search (warn when luck cannot be excluded)."""
    if not info:
        return check("reality_check", "statistics", "skip", "reality check needs at least two combinations and 100 bars")
    p_spa, p_rc, n = info["p_spa"], info["p_reality_check"], info["models"]
    if p_spa >= WARN_AT:
        return check(
            "reality_check", "statistics", "warn",
            f"SPA p = {p_spa:.3f} (Reality Check {p_rc:.3f}): with {n} combinations tried, luck cannot be excluded as the source of the best result",
            info,
        )
    return check(
        "reality_check", "statistics", "pass",
        f"SPA p = {p_spa:.3f} (Reality Check {p_rc:.3f}): the best of {n} combinations beats cash by more than the search explains", info,
    )


__all__ = ["SAMPLES", "WARN_AT", "reality_check", "reality_row"]
