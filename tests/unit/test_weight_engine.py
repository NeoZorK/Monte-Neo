"""Target-weight engine: exact equivalence with the discrete engine and hand-computed cases."""

from __future__ import annotations

import numpy as np
import pytest

from monte_neo.backtest import ExecutionModel, run_bar_backtest, synthetic_ohlcv
from monte_neo.backtest.weight_engine import normalize_weights, run_weight_backtest

FREE = ExecutionModel(side_mode="long_short", commission_bps=0.0, slippage_bps=0.0, warmup_bars=0)


@pytest.mark.parametrize("seed", range(40))
def test_equals_discrete_engine_on_unit_signals(seed: int) -> None:
    rng = np.random.default_rng(seed)
    n = int(rng.integers(50, 600))
    df = synthetic_ohlcv(n, seed=seed)
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    hold = int(rng.integers(1, 25))
    sig = np.repeat(rng.integers(-1, 2, n // hold + 1), hold)[:n]
    model = ExecutionModel(
        side_mode=str(rng.choice(["long_flat", "long_short"])),
        commission_bps=float(rng.uniform(0, 20)),
        slippage_bps=float(rng.uniform(0, 20)),
        warmup_bars=int(rng.integers(0, 20)),
        fill_policy=str(rng.choice(["next_bar_open", "next_bar_close"])),
        funding_bps_per_bar=float(rng.choice([0.0, 0.3])),
    )
    a = run_bar_backtest(o, h, l, c, sig, model=model)
    b = run_weight_backtest(o, c, sig.astype(np.float64), model=model)
    assert np.array_equal(a["equity"], b["equity"])  # bit for bit
    for key in ("total_return", "max_drawdown", "n_trades", "n_closed_trades"):
        assert a[key] == b[key], key


def _prices(*closes: float) -> np.ndarray:
    return np.array(closes, dtype=np.float64)


def test_half_weight_earns_half_the_move() -> None:
    px = _prices(100, 100, 110, 110)  # open == close: fills at the decision price of the next bar
    out = run_weight_backtest(px, px, np.array([0.5, 0.5, 0.5, 0.5]), model=FREE)
    assert out["total_return"] == pytest.approx(0.05)
    assert out["n_closed_trades"] == 1 and out["n_trades"] == 2  # open once, flatten at the end


def test_resizing_trades_only_the_difference() -> None:
    px = _prices(100, 100, 100, 200, 200)
    out = run_weight_backtest(px, px, np.array([1.0, 0.5, 0.5, 0.5, 0.5]), model=FREE)
    # Full at 100, cut to half at 100, then the price doubles: +50%.
    assert out["total_return"] == pytest.approx(0.5)
    assert out["n_trades"] == 3 and out["n_closed_trades"] == 1


def test_costs_are_charged_on_traded_notional() -> None:
    px = _prices(100, 100, 100, 100)
    model = ExecutionModel(side_mode="long_short", commission_bps=10.0, slippage_bps=0.0, warmup_bars=0)
    out = run_weight_backtest(px, px, np.array([0.5, 0.5, 0.5, 0.5]), model=model)
    # 10 bps on 50% of equity going in and again coming out.
    assert out["total_return"] == pytest.approx(-0.001, rel=1e-3)
    assert out["turnover"] == pytest.approx(1.0, rel=1e-3)


def test_two_instruments_average_their_moves() -> None:
    a = _prices(100, 100, 120, 120)
    b = _prices(50, 50, 45, 45)
    px = np.column_stack([a, b])
    w = np.full((4, 2), 0.5)
    out = run_weight_backtest(px, px, w, model=FREE)
    assert out["total_return"] == pytest.approx(0.5 * 0.2 + 0.5 * -0.1)


def test_order_waits_for_a_price() -> None:
    open_ = np.column_stack([_prices(100, 100, 100, 100, 100), _prices(10, np.nan, 10, 20, 20)])
    close = open_.copy()
    w = np.array([[0.0, 1.0]] * 5)
    out = run_weight_backtest(open_, close, w, model=FREE)
    # No price on bar 1: the buy fills at bar 2 (10), then the price doubles.
    assert out["total_return"] == pytest.approx(1.0)


def test_delisted_position_closes_at_its_last_price() -> None:
    open_ = np.column_stack([_prices(100, 100, 100, 100, 100), _prices(10, 10, 5, np.nan, np.nan)])
    close = open_.copy()
    w = np.array([[0.0, 1.0]] * 5)
    out = run_weight_backtest(open_, close, w, model=FREE)
    assert out["total_return"] == pytest.approx(-0.5)  # bought at 10, last price 5
    assert out["n_closed_trades"] == 1
    assert out["equity"][-1] == pytest.approx(50_000.0)


def test_normalize_weights() -> None:
    w, scaled = normalize_weights(np.array([[1.0, 1.0], [0.2, -0.3], [np.nan, 5.0]]))
    assert scaled == 1 and np.allclose(w, [[0.5, 0.5], [0.2, -0.3], [0.0, 1.0]])
    one, none_scaled = normalize_weights(np.array([2.0, -0.4, np.inf]), long_short=False)
    assert none_scaled == 0 and np.allclose(one, [1.0, 0.0, 1.0])


def test_input_errors() -> None:
    px = _prices(1, 2, 3)
    with pytest.raises(ValueError, match="high and low"):
        run_weight_backtest(px, px, px, model=ExecutionModel(sl_pct=1.0, warmup_bars=0))
    with pytest.raises(ValueError, match="share the shape"):
        run_weight_backtest(px, px, np.ones(2), model=FREE)
    with pytest.raises(ValueError, match="warmup"):
        run_weight_backtest(px, px, px, model=ExecutionModel(warmup_bars=5))
    flat = run_weight_backtest(px, px, np.zeros(3), model=ExecutionModel(side_mode="long_flat", warmup_bars=0))
    assert flat["total_return"] == 0.0 and flat["n_trades"] == 0
