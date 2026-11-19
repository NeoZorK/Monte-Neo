"""Dynamic Monte Carlo for one strategy: does the evidence survive a change of regime, mix or arrow of time?

Three rows, all warn-only (a pass never proves an edge, a warn never rejects):

* ``regime_swap_null`` - is the strategy's return linked to the market regime more than chance allows? The regime
  labels of the usable bars (rising / falling, calm / volatile, as in :func:`monte_neo.verify.breakdown.regime_masks`)
  are circularly shifted against the strategy returns. A circular shift keeps the label runs (regimes persist) and
  breaks only their alignment with the returns, so the observed gap between two regimes is compared with the gaps
  that arise by chance (two pairs tested, Bonferroni x2). The row warns when the gap is significant and the weaker
  regime loses money.
* ``regime_mix_bootstrap`` - what would the Sharpe be if the market spent equal time in each regime? Bars of each
  regime are resampled with a stationary block bootstrap (Politis and Romano, 1994) in equal numbers, so the sample's
  own mix (for example a long bull market) no longer helps. The row warns when the 5 % quantile of that Sharpe is not
  positive although the observed Sharpe is.
* ``time_reversal_null`` - the same strategy code is run on the time-reversed price history (bar order and
  open/close swapped, so the reversed history is a valid OHLC series). Edges that rest on the arrow of time
  (calendar effects, asymmetric volatility, slow reaction to news) vanish; time-symmetric edges (mean reversion on
  a stationary spread) survive. This is a characterisation, so the row informs and never warns; it is skipped
  when the strategy code is not available.

Sources: Politis and Romano (1994), "The stationary bootstrap", JASA 89(428); Ang and Bekaert (2002), regime-conditional
performance, Review of Financial Studies 15(4); the circular-shift idea follows the timing test of this package
(:mod:`monte_neo.verify.timing`).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.verify.checks import check

SEED = 20260509
N_SHIFTS = 500
N_BOOT = 500
MIN_STRATUM_BARS = 40
ALPHA = 0.05
PAIRS = (("rising", "falling"), ("calm", "volatile"))
LOSS_SHARE = 0.20


def _sharpe(r: np.ndarray, ppy: float) -> float:
    if r.size < 2:
        return 0.0
    sd = float(np.std(r, ddof=1))
    return float(np.mean(r) / sd * math.sqrt(ppy)) if sd > 1e-15 else 0.0


def regime_swap_null(
    s_ret: np.ndarray, masks: dict[str, np.ndarray], usable: np.ndarray, *, n_shifts: int = N_SHIFTS, seed: int = SEED
) -> dict[str, Any]:
    """Gap in mean return between two regimes against circularly shifted labels; see the module docstring."""
    idx = np.flatnonzero(usable)
    r = np.asarray(s_ret, dtype=np.float64)[idx]
    out: dict[str, Any] = {}
    rng = np.random.default_rng(seed)
    for a, b in PAIRS:
        if a not in masks or b not in masks:
            continue
        la = masks[a][idx]
        lb = masks[b][idx]  # the complement of la within the usable bars
        if la.sum() < MIN_STRATUM_BARS or lb.sum() < MIN_STRATUM_BARS:
            out[f"{a}_vs_{b}"] = {"status": "skip", "reason": "a regime has too few bars"}
            continue
        gap = float(r[la].mean() - r[lb].mean())
        lo = max(10, r.size // 10)
        offsets = rng.integers(lo, r.size - lo, size=n_shifts)  # two regimes of >= 40 bars leave room: r.size >= 80 > 2 * lo
        null = np.empty(offsets.size)
        for i, k in enumerate(offsets):
            s = np.roll(la, int(k))
            null[i] = r[s].mean() - r[~s].mean()
        p = float((1 + np.count_nonzero(np.abs(null) >= abs(gap))) / (null.size + 1))
        out[f"{a}_vs_{b}"] = {
            "status": "ok", "gap_per_bar": gap, "p_value": p, "p_adjusted": min(1.0, 2 * p),
            f"mean_{a}": float(r[la].mean()), f"mean_{b}": float(r[lb].mean()),
            f"share_{a}": float(la.mean()), f"share_{b}": float(lb.mean()),
        }
    return out


def regime_swap_row(swap: dict[str, Any], total_return: float) -> dict[str, Any]:
    """``regime_swap_null``: warn when the return depends on the regime and the weaker regime loses."""
    if total_return <= 0.0:
        return check("regime_swap_null", "statistics", "skip", "not profitable after costs")
    done = {k: v for k, v in swap.items() if v.get("status") == "ok"}
    if not done:
        return check("regime_swap_null", "statistics", "skip", "too few bars in each regime to test regime dependence", swap)
    problems = []
    for key, v in done.items():
        a, b = key.split("_vs_")
        weak = a if v[f"mean_{a}"] < v[f"mean_{b}"] else b
        if v["p_adjusted"] <= ALPHA and v[f"mean_{weak}"] < 0.0 and v[f"share_{weak}"] >= LOSS_SHARE:
            problems.append(f"loses in {weak} markets and the gap to the other regime is significant (p={v['p_adjusted']:.3f})")
    if problems:
        return check("regime_swap_null", "statistics", "warn", "the return depends on the market regime: " + "; ".join(problems), swap)
    return check("regime_swap_null", "statistics", "pass", "no significant loss tied to a market regime (shifted-label null)", swap)


def _stationary_indices(n: int, size: int, mean_block: int, rng: np.random.Generator) -> np.ndarray:
    """``size`` indices into ``n`` bars: blocks of geometric length that wrap around."""
    out = np.empty(size, dtype=np.int64)
    p = 1.0 / max(mean_block, 1)
    pos = int(rng.integers(n))
    for t in range(size):
        out[t] = pos
        pos = int(rng.integers(n)) if rng.random() < p else (pos + 1) % n
    return out


def regime_mix_bootstrap(
    s_ret: np.ndarray, masks: dict[str, np.ndarray], ppy: float, *, n_boot: int = N_BOOT, seed: int = SEED
) -> dict[str, Any]:
    """Sharpe quantiles when each regime of a pair gets half of the bars; see the module docstring."""
    rng = np.random.default_rng(seed)
    r = np.asarray(s_ret, dtype=np.float64)
    out: dict[str, Any] = {}
    for a, b in PAIRS:
        if a not in masks or b not in masks:
            continue
        ra, rb = r[masks[a]], r[masks[b]]
        if ra.size < MIN_STRATUM_BARS or rb.size < MIN_STRATUM_BARS:
            out[f"{a}_{b}"] = {"status": "skip", "reason": "a regime has too few bars"}
            continue
        total = ra.size + rb.size
        half = total // 2
        block = max(5, round(total ** (1.0 / 3.0)))
        sharpes = np.empty(n_boot)
        for i in range(n_boot):
            x = np.concatenate([ra[_stationary_indices(ra.size, half, block, rng)], rb[_stationary_indices(rb.size, half, block, rng)]])
            sharpes[i] = _sharpe(x, ppy)
        observed = _sharpe(np.concatenate([ra, rb]), ppy)
        out[f"{a}_{b}"] = {
            "status": "ok", "observed_sharpe": observed, "equal_mix_median": float(np.median(sharpes)),
            "equal_mix_q05": float(np.quantile(sharpes, 0.05)), "equal_mix_q95": float(np.quantile(sharpes, 0.95)),
            "prob_positive": float(np.mean(sharpes > 0.0)),
        }
    return out


def regime_mix_row(boot: dict[str, Any], total_return: float) -> dict[str, Any]:
    """``regime_mix_bootstrap``: warn when an equal regime mix leaves no reliably positive Sharpe."""
    if total_return <= 0.0:
        return check("regime_mix_bootstrap", "statistics", "skip", "not profitable after costs")
    done = {k: v for k, v in boot.items() if v.get("status") == "ok"}
    if not done:
        return check("regime_mix_bootstrap", "statistics", "skip", "too few bars in each regime for a regime-mix bootstrap", boot)
    bad = {k: v for k, v in done.items() if v["observed_sharpe"] > 0.0 and v["equal_mix_q05"] <= 0.0}
    if bad:
        txt = "; ".join(f"{k.replace('_', '/')}: Sharpe {v['observed_sharpe']:+.2f} observed, {v['equal_mix_median']:+.2f} median at equal mix (5% quantile {v['equal_mix_q05']:+.2f})" for k, v in bad.items())
        return check("regime_mix_bootstrap", "statistics", "warn", "the Sharpe depends on the sample's regime mix: " + txt, boot)
    return check("regime_mix_bootstrap", "statistics", "pass", "the Sharpe stays positive at 5 % when every regime gets equal time", boot)


def reverse_frame(df: pd.DataFrame) -> pd.DataFrame:
    """The price history run backwards as a valid OHLCV table (bar order reversed, open and close swapped).

    Timestamps are mirrored (``t0 + t_last - t``) so they stay increasing. Other columns are reversed as they are.
    """
    out = df.iloc[::-1].reset_index(drop=True).copy()
    out["open"], out["close"] = df["close"].to_numpy()[::-1].copy(), df["open"].to_numpy()[::-1].copy()
    if "timestamp" in df.columns:
        ts = df["timestamp"]
        try:
            if pd.api.types.is_numeric_dtype(ts):
                vals = ts.to_numpy(dtype=np.float64)
                out["timestamp"] = (vals[0] + vals[-1] - vals[::-1]).astype(ts.dtype)
            else:
                t = pd.to_datetime(ts, utc=False)
                out["timestamp"] = (t.iloc[0] + t.iloc[-1] - t.iloc[::-1]).reset_index(drop=True)
        except (ValueError, TypeError, OverflowError):
            out["timestamp"] = ts.to_numpy()
    return out


def run_reversed(frame: pd.DataFrame, fn: Any, mode: str, model: Any, original_total: float) -> tuple[dict[str, float] | None, str]:
    """Run the strategy code on the reversed history; ``(result or None, reason when None)``."""
    from monte_neo.verify.engine import simulate
    from monte_neo.verify.executor import FULL, evaluate
    from monte_neo.verify.ingest import to_positions

    try:
        rev = reverse_frame(frame)
        values = evaluate(fn, rev, [FULL])[0]
        if values.size != len(rev):
            return None, "the strategy returned a different length on the reversed history"
        pos = to_positions(values, mode)
        ohlc = {k: rev[k].to_numpy(dtype=np.float64) for k in ("open", "high", "low", "close")}
        run = simulate(ohlc, pos, model)
        hold = simulate(ohlc, np.ones(len(rev), dtype=np.int64), model)
    except Exception as exc:  # noqa: BLE001 - the strategy is user code; a failure here is a reason, not a verdict
        return None, f"the strategy could not run on the reversed history ({type(exc).__name__})"
    tr, bh = float(run["total_return"]), float(hold["total_return"])
    return {"total_return": tr, "benchmark_return": bh, "excess_return": tr - bh}, ""


def time_reversal_row(original: dict[str, float], reversed_run: dict[str, float] | None, why: str = "") -> dict[str, Any]:
    """``time_reversal_null``: informative only; compares net return and Sharpe on the reversed history."""
    if reversed_run is None:
        return check("time_reversal_null", "statistics", "skip", why or "needs the strategy code (signal function)")
    details = {"original": original, "reversed": reversed_run}
    if original["total_return"] <= 0.0:
        return check("time_reversal_null", "statistics", "skip", "not profitable after costs", details)
    survives = reversed_run["excess_return"] > 0.0
    kind = (
        "the edge also appears on the reversed history: it does not need the arrow of time (typical of mean reversion; "
        "for a trend or calendar strategy, treat this as a prompt to look for a mechanical edge)"
        if survives
        else "the edge vanishes on the reversed history: it rests on the arrow of time (trend, calendar or asymmetric volatility)"
    )
    return check(
        "time_reversal_null", "statistics", "info",
        f"net return {original['total_return']:+.1%} forward, {reversed_run['total_return']:+.1%} on reversed history "
        f"(buy-and-hold {reversed_run['benchmark_return']:+.1%}); {kind}", details,
    )


__all__ = [
    "ALPHA", "MIN_STRATUM_BARS", "N_BOOT", "N_SHIFTS", "SEED", "regime_mix_bootstrap", "regime_mix_row",
    "regime_swap_null", "regime_swap_row", "reverse_frame", "run_reversed", "time_reversal_row",
]
