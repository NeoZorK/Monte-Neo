"""Cost profiles, spread from quotes, cost gates and the regime-stability row."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from monte_neo.backtest import ExecutionModel, synthetic_ohlcv
from monte_neo.verify import verify_strategy
from monte_neo.verify.cost_profiles import (
    FEE_PROFILES,
    MIN_QUOTES,
    cost_realism_row,
    cost_sensitivity_row,
    quotes_half_spread_bps,
    realism_row,
    side_fee_bps,
    with_profile,
)
from monte_neo.verify.costs import breakeven_cost_bps
from monte_neo.verify.regime_checks import regime_stability_row

N = 1500
DF = synthetic_ohlcv(N, seed=5)
OHLC = {k: DF[k].to_numpy(dtype=np.float64) for k in ("open", "high", "low", "close")}
# a leaky "oracle" position (reads the next close) makes a profit whose size depends only on the costs
SIG = np.sign(np.diff(OHLC["close"], append=OHLC["close"][-1]))
BASE = ExecutionModel(commission_bps=0.0, slippage_bps=0.0, side_mode="long_short", warmup_bars=10)


def _be() -> float:
    return breakeven_cost_bps(OHLC, SIG, BASE)["breakeven_bps"]


def test_fee_profiles_and_maker_share() -> None:
    assert side_fee_bps("binance_usdm") == 5.0  # all taker by default
    assert side_fee_bps("binance_usdm", 1.0) == 2.0
    assert side_fee_bps("binance_usdm", 0.5) == 3.5
    assert side_fee_bps((1.0, 3.0), 0.25) == 2.5
    assert all(m <= t for m, t in FEE_PROFILES.values())


def test_fee_profile_errors() -> None:
    with pytest.raises(ValueError, match="unknown cost profile"):
        side_fee_bps("nope")
    with pytest.raises(ValueError, match="maker_share"):
        side_fee_bps("binance_spot", 1.5)
    with pytest.raises(ValueError, match=">= 0"):
        side_fee_bps((-1.0, 2.0))


def test_with_profile_replaces_commission_only() -> None:
    m = with_profile(replace(BASE, slippage_bps=3.0), "binance_usdm_vip1", 0.5)
    assert m.commission_bps == pytest.approx(2.8) and m.slippage_bps == 3.0


def test_quotes_half_spread() -> None:
    bid = np.full(200, 100.0)
    ask = bid * 1.001
    out = quotes_half_spread_bps(bid, ask)
    assert out["half_spread_bps"] == pytest.approx(5.0, rel=0.01) and out["dropped"] == 0
    ask[:10] = 99.0  # crossed
    bid[10] = np.nan
    out = quotes_half_spread_bps(bid, ask)
    assert out["dropped"] == 11 and out["quotes"] == 189
    with pytest.raises(ValueError, match="usable quotes"):
        quotes_half_spread_bps(bid[: MIN_QUOTES - 1], ask[: MIN_QUOTES - 1])


def test_sensitivity_warns_when_doubling_kills_the_edge() -> None:
    be = _be()
    assert be > 0
    assert cost_sensitivity_row(OHLC, SIG, replace(BASE, commission_bps=0.7 * be))["status"] == "warn"  # 2x = 1.4 * breakeven
    assert cost_sensitivity_row(OHLC, SIG, replace(BASE, commission_bps=0.3 * be))["status"] == "pass"  # 2x = 0.6 * breakeven


def test_sensitivity_skips_unprofitable() -> None:
    row = cost_sensitivity_row(OHLC, -SIG, BASE)
    assert row["status"] == "skip" and "returns" in row["details"]


def test_sensitivity_scales_symbol_costs() -> None:
    m = replace(BASE, symbol_costs=(("AAA", 0.1, 0.1),))
    assert cost_sensitivity_row(OHLC, SIG, m)["status"] in ("pass", "warn")


def test_realism_quotes_fail_and_highlow_warn() -> None:
    be = _be()
    m = replace(BASE, commission_bps=0.2 * be, slippage_bps=0.1 * be)
    wide = 3.0 * be
    row = cost_realism_row(OHLC, SIG, m, wide, "quotes")
    assert row["status"] == "fail" and row["details"]["realistic_return"] <= 0 < row["details"]["modeled_return"]
    assert cost_realism_row(OHLC, SIG, m, wide, "high-low")["status"] == "warn"
    mild = cost_realism_row(OHLC, SIG, m, 0.3 * be, "quotes")  # worse than modeled but still profitable
    assert mild["status"] == "warn" and mild["details"]["realistic_return"] > 0
    assert cost_realism_row(OHLC, SIG, m, 0.05 * be, "quotes")["status"] == "pass"  # covered by modeled slippage
    assert cost_realism_row(OHLC, SIG, m, None, "high-low")["status"] == "skip"


def test_realism_row_picks_source() -> None:
    m = replace(BASE, commission_bps=0.2 * _be())
    assert realism_row(OHLC, SIG, m, {"half_spread_bps": 0.0}, 3.0 * _be())["details"]["source"] == "quotes"
    assert realism_row(OHLC, SIG, m, {"half_spread_bps": 0.0}, None)["details"]["source"] == "high-low"
    assert realism_row(OHLC, SIG, m, {}, None)["status"] == "skip"


def test_verify_strategy_wires_gates_and_profile() -> None:
    rep = verify_strategy(DF, signals=SIG, model=replace(BASE, slippage_bps=1.0), cost_profile="binance_usdm",
                          quotes_half_spread_bps=50.0)
    ids = {c["id"]: c["status"] for c in rep["checks"]}
    assert {"alpha_after_beta", "regime_stability", "cost_sensitivity", "cost_realism"} <= set(ids)
    assert ids["cost_realism"] in ("fail", "warn", "pass")
    settings = rep["reproducibility"]["settings"]
    assert settings["cost_profile"] == "binance_usdm" and settings["quotes_half_spread_bps"] == 50.0
    assert rep["reproducibility"]["model"]["commission_bps"] == 5.0
    pair = verify_strategy(DF, signals=SIG, model=BASE, cost_profile=(2.0, 5.0), maker_share=0.5)
    assert pair["reproducibility"]["settings"]["cost_profile"] == [2.0, 5.0]
    plain = verify_strategy(DF, signals=SIG, model=BASE)
    assert "cost_profile" not in plain["reproducibility"]["settings"]


def _reg(rising: float, falling: float, calm: float, volatile: float, shares=(0.5, 0.5, 0.5, 0.5)) -> dict:
    vals = dict(zip(("rising", "falling", "calm", "volatile"), zip(shares, (rising, falling, calm, volatile)), strict=True))
    return {"regimes": {k: {"bars": 100, "share": s, "return": r, "sharpe_annualized": 1.0} for k, (s, r) in vals.items()}}


def test_regime_untested_bear_market_warns() -> None:
    row = regime_stability_row(_reg(2.0, 0.0, 0.5, 0.5, shares=(0.95, 0.05, 0.5, 0.5)), 2.0)
    assert row["status"] == "warn" and "falling" in row["summary"] and "untested" in row["summary"]


def test_regime_loss_and_concentration_warn() -> None:
    assert "loses in falling" in regime_stability_row(_reg(0.5, -0.1, 0.2, 0.2), 0.3)["summary"]
    row = regime_stability_row(_reg(3.0, 0.01, 0.3, 0.3), 3.0)
    assert row["status"] == "warn" and "of the profit comes from rising" in row["summary"]


def test_regime_balanced_passes_and_skips() -> None:
    assert regime_stability_row(_reg(0.4, 0.3, 0.35, 0.35), 0.7)["status"] == "pass"
    assert regime_stability_row(_reg(0.4, 0.3, 0.35, 0.35), -0.1)["status"] == "skip"
    assert regime_stability_row({"regimes": {}}, 0.5)["status"] == "skip"
    partial = {"regimes": {"rising": _reg(1, 1, 1, 1)["regimes"]["rising"]}}
    assert regime_stability_row(partial, 0.5)["status"] == "pass"  # a pair with a missing side is not judged
