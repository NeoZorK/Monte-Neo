"""Execution calibration: impact fit from fills, decay, participation, rebates."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from monte_neo.backtest import ExecutionModel
from monte_neo.verify.cost_profiles import side_fee_bps, with_profile
from monte_neo.verify.execution import simulate_execution
from monte_neo.verify.execution_calib import (
    calibrate_impact,
    decay_factor,
    participation_stats,
    rebate_fee_bps,
)

RNG = np.random.default_rng(4)


def _fills(coef: float, n: int = 300, noise: float = 1.0) -> pd.DataFrame:
    sigma = RNG.uniform(20, 80, n)
    share = RNG.uniform(0.001, 0.2, n)
    return pd.DataFrame({"sigma_bps": sigma, "share": share, "slippage_bps": coef * sigma * np.sqrt(share) + RNG.normal(0, noise, n)})


def test_calibration_recovers_coefficient_and_exponent() -> None:
    r = calibrate_impact(_fills(0.7))
    assert r["coef"] == pytest.approx(0.7, abs=0.05) and r["ci95"][0] < 0.7 < r["ci95"][1]
    assert r["share_exponent"] == pytest.approx(0.5, abs=0.1)


def test_calibration_refuses_noise_few_fills_and_missing_columns() -> None:
    with pytest.raises(ValueError, match="do not support"):
        calibrate_impact(_fills(0.0, noise=5.0))
    with pytest.raises(ValueError, match="at least 30"):
        calibrate_impact(_fills(0.7, n=10))
    with pytest.raises(ValueError, match="missing"):
        calibrate_impact(pd.DataFrame({"share": [0.1] * 40}))


def test_calibration_drops_bad_rows() -> None:
    f = _fills(0.7)
    f.loc[0, "share"] = 2.0
    f.loc[1, "sigma_bps"] = np.nan
    assert calibrate_impact(f)["dropped"] == 2


def test_calibrated_coefficient_changes_simulated_cost() -> None:
    n = 400
    close = 100 * np.cumprod(1 + RNG.normal(0, 0.01, n))
    vol = np.full(n, 1e4)
    target = np.where((np.arange(n) // 20) % 2 == 0, 1.0, 0.0)
    lo = simulate_execution(target, close, vol, capital=2e5, impact_coef=0.2)
    hi = simulate_execution(target, close, vol, capital=2e5, impact_coef=2.0)
    assert hi["cost"].sum() > lo["cost"].sum()


def test_decay_factor() -> None:
    assert decay_factor(1.0) == pytest.approx(0.5) and decay_factor(0.0) == 0.0
    with pytest.raises(ValueError):
        decay_factor(-1.0)


def test_decay_raises_cost_of_repeated_same_direction_trades() -> None:
    n = 200
    close = 100 * np.cumprod(1 + RNG.normal(0, 0.01, n))
    vol = np.full(n, 5e3)
    target = np.minimum(np.arange(n) * 0.05, 1.0)  # a long staircase of same-direction buys
    base = simulate_execution(target, close, vol, capital=2e5, max_participation=0.05)
    slow = simulate_execution(target, close, vol, capital=2e5, max_participation=0.05, decay_half_life_bars=10.0)
    fast = simulate_execution(target, close, vol, capital=2e5, max_participation=0.05, decay_half_life_bars=0.0)
    assert slow["cost"].sum() > base["cost"].sum()
    assert fast["cost"].sum() == pytest.approx(base["cost"].sum())


def test_participation_stats() -> None:
    s = participation_stats(np.array([1.0, 5.0, 0.0]), np.array([100.0, 100.0, 100.0]), assumed=0.02)
    assert s["fills"] == 2 and s["max"] == pytest.approx(0.05) and s["share_above_assumed"] == pytest.approx(0.5)
    assert participation_stats(np.zeros(3), np.ones(3), 0.1)["fills"] == 0


def test_rebate_needs_flag_and_stays_realistic() -> None:
    with pytest.raises(ValueError):  # no flag: negative fee still refused
        side_fee_bps((-0.5, 4.0), 0.3)
    assert side_fee_bps((-0.5, 4.0), 0.3, allow_rebate=True) == pytest.approx(-0.5 * 0.3 + 4.0 * 0.7)
    with pytest.raises(ValueError, match="capped"):
        side_fee_bps((-0.5, 4.0), 0.8, allow_rebate=True)
    with pytest.raises(ValueError, match="realistic"):
        side_fee_bps((-3.0, 4.0), 0.1, allow_rebate=True)


def test_rebate_never_pays_the_strategy_and_charges_adverse_selection() -> None:
    r = rebate_fee_bps(-1.0, 0.0, 0.5)
    assert r["fee_bps"] == 0.0 and r["floored"]
    assert rebate_fee_bps(-0.5, 4.0, 0.5, adverse_selection_bps=1.0)["fee_bps"] == pytest.approx(-0.25 + 2.0 + 0.5)
    m = with_profile(ExecutionModel(), (-0.5, 4.0), 0.3, allow_rebate=True)
    assert m.commission_bps > 0


def test_verify_accepts_rebate_only_with_flag() -> None:
    from monte_neo.backtest import synthetic_ohlcv
    from monte_neo.verify import verify_strategy

    df = synthetic_ohlcv(600, seed=3)
    sig = np.where(np.arange(600) % 40 < 20, 1, 0)
    with pytest.raises(ValueError):
        verify_strategy(df, signals=sig, cost_profile=(-0.5, 4.0), maker_share=0.3)
    out = verify_strategy(df, signals=sig, cost_profile=(-0.5, 4.0), maker_share=0.3, allow_rebate=True, adverse_selection_bps=0.5)
    assert out["reproducibility"]["settings"]["allow_rebate"] is True and out["reproducibility"]["settings"]["adverse_selection_bps"] == 0.5


def test_rebate_boundaries_rejected() -> None:
    with pytest.raises(ValueError, match=">= 0"):
        rebate_fee_bps(-0.5, -1.0, 0.2)
    with pytest.raises(ValueError, match="between 0 and 1"):
        rebate_fee_bps(-0.5, 4.0, 1.5)
