"""``alpha-report/1``: run the family A checks and assemble the report."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from monte_neo._version import __version__
from monte_neo.alpha.implementability_run import NEXT_ACTIONS as D_ACTIONS
from monte_neo.alpha.implementability_run import run_implementability
from monte_neo.alpha.panel import Panel, build_panel, data_sha256
from monte_neo.alpha.signal_power import (
    check_breadth_consistency,
    check_ic,
    check_ic_decay,
    check_long_short_legs,
    check_quantile_monotonicity,
    check_selection_vs_timing,
    check_signal_placebo,
)
from monte_neo.disclaimer import ALPHA_SCOPE, SHORT
from monte_neo.verify.schema import aggregate_verdict, to_jsonable

ALPHA_SCHEMA_ID = "alpha-report/1"

NEXT_ACTIONS: dict[str, str] = {
    "ic": "The score shows no reliable rank link to later returns: test more history or more symbols, or rebuild the signal; do not trade it on this evidence.",
    "ic_decay": "Match the holding period to the horizon where the IC peaks and trade no slower than the half-life.",
    "quantile_monotonicity": "Bucket returns are not ordered: the score may only work in one tail. Test a tail-only rule on new data, or check for outliers driving the extreme bucket.",
    "long_short_legs": "Most profit comes from shorting: re-test long-only, or price borrow cost, short bans and microcap liquidity before trusting the spread.",
    "breadth_consistency": "The claimed IR is above what IC and breadth allow: report the implied IR, or find out which costs, leverage or overlap inflate the claim.",
    "signal_placebo": "Random scores earn about as much as yours: the long-short construction or the market drift earns, not the signal. Re-test with market-neutral returns and more history.",
    "selection_vs_timing": "If the spread survives with dates shuffled, a persistent tilt (a fixed set of winners) earns, not the score: neutralise sector, size and momentum exposures.",
}


def demo_panel(seed: int = 0, n_symbols: int = 40, n_days: int = 750) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Synthetic universe with a weakly predictive score (IC about 0.04) and a pure-noise score.

    Args:
        seed: Random seed.
        n_symbols: Number of symbols.
        n_days: Number of business days.

    Returns:
        (prices, real_scores, noise_scores) as long tables.
    """
    rng = np.random.default_rng(seed)
    z = rng.standard_normal((n_days, n_symbols))
    noise = rng.standard_normal((n_days, n_symbols))
    market = 0.0003 + 0.008 * rng.standard_normal((n_days, 1))
    ret = market + 0.0012 * z + 0.02 * noise  # return from day t to t+1 depends on the score of day t
    close = 100.0 * np.cumprod(1.0 + np.vstack([np.zeros((1, n_symbols)), ret[:-1]]), axis=0)
    dates = pd.bdate_range("2020-01-01", periods=n_days)
    syms = [f"S{i:02d}" for i in range(n_symbols)]
    prices = pd.DataFrame({"timestamp": np.repeat(dates, n_symbols), "symbol": np.tile(syms, n_days), "close": close.ravel(), "volume": 1e6})

    def table(m: np.ndarray) -> pd.DataFrame:
        return pd.DataFrame({"timestamp": np.repeat(dates, n_symbols), "symbol": np.tile(syms, n_days), "score": m.ravel()})

    return prices, table(z), table(rng.standard_normal((n_days, n_symbols)))


def _next_actions(checks: list[dict[str, Any]]) -> list[str]:
    actions = {**NEXT_ACTIONS, **D_ACTIONS}
    return [actions[c["id"]] for s in ("fail", "warn") for c in checks if c["status"] == s and c["id"] in actions]


def run_checks(panel: Panel, *, horizon: int, quantiles: int, claimed_ir: float | None, seed: int, placebos: int) -> list[dict[str, Any]]:
    """Run family A on an aligned panel (forward returns are used only as targets)."""
    fwd = panel.forward_returns(horizon)
    ic = check_ic(panel, fwd, horizon)
    mean_ic = ic["details"].get("mean_ic", float("nan"))
    return [
        ic,
        check_ic_decay(panel),
        check_quantile_monotonicity(panel, fwd, quantiles, seed),
        check_long_short_legs(panel, fwd, quantiles),
        check_breadth_consistency(panel, mean_ic, horizon, claimed_ir),
        check_signal_placebo(panel, fwd, quantiles, seed, placebos),
        check_selection_vs_timing(panel, fwd, quantiles, seed),
    ]


def validate_alpha(
    prices: pd.DataFrame | str | Path,
    scores: pd.DataFrame | str | Path,
    *,
    horizon: int = 1,
    quantiles: int = 5,
    claimed_ir: float | None = None,
    seed: int = 0,
    placebos: int = 200,
    aum: float | None = None,
) -> dict[str, Any]:
    """Check whether a cross-sectional score has real predictive power and whether its portfolio can be traded.

    Args:
        prices: Long table (timestamp, symbol, close[, volume]) or a .csv / .parquet path.
        scores: Long table (timestamp, symbol, score) or a path.
        horizon: Forward-return horizon in bars.
        quantiles: Number of quantile buckets.
        claimed_ir: Claimed annual information ratio (enables the breadth check).
        seed: Seed for bootstraps and placebos.
        placebos: Number of permuted-score placebos.
        aum: Capital for the market-impact and participation checks (family D); ``None`` skips those two.

    Returns:
        An ``alpha-report/1`` dict: verdict, checks, metrics, next_actions, reproducibility.

    Raises:
        ValueError: if the inputs cannot be aligned (duplicates, unknown symbols, late scores, ...).
    """
    if quantiles < 2:
        raise ValueError("quantiles must be >= 2")
    panel = build_panel(prices, scores)
    checks = run_checks(panel, horizon=horizon, quantiles=quantiles, claimed_ir=claimed_ir, seed=seed, placebos=placebos)
    half_life = next((c["details"].get("half_life") for c in checks if c["id"] == "ic_decay"), None)
    checks += run_implementability(panel, quantiles=quantiles, aum=aum, half_life=half_life)
    by = {c["id"]: c["details"] for c in checks}
    metrics = {
        "n_dates": len(panel.dates), "n_symbols": len(panel.symbols),
        "mean_ic": by["ic"].get("mean_ic"), "ic_t_stat": by["ic"].get("t_stat"), "icir": by["ic"].get("icir"),
        "best_horizon": by["ic_decay"].get("best_horizon"), "ic_half_life": by["ic_decay"].get("half_life"),
        "quantile_spread": by["quantile_monotonicity"].get("spread"), "short_leg_share": by["long_short_legs"].get("short_share"),
        "placebo_p_value": by["signal_placebo"].get("p_value"), "implied_ir": by["breadth_consistency"].get("implied_ir"),
        "score_rows_not_on_price_dates": panel.n_unmatched_score_rows,
        "aum_where_sharpe_halves": by["capacity_curve"].get("aum_half"),
    }
    return to_jsonable({
        "schema": ALPHA_SCHEMA_ID,
        "verdict": aggregate_verdict(checks),
        "checks": checks,
        "metrics": metrics,
        "next_actions": _next_actions(checks),
        "reproducibility": {
            "data_sha256": {"prices": data_sha256(prices), "scores": data_sha256(scores)},
            "settings": {"horizon": horizon, "quantiles": quantiles, "claimed_ir": claimed_ir, "seed": seed, "placebos": placebos, "aum": aum},
            "engine_version": __version__,
        },
        "disclaimer": f"{ALPHA_SCOPE} {SHORT}",
    })
