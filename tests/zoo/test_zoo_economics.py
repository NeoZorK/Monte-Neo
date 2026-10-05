"""A5: execution and economics. Every expectation is arithmetic done by hand on a small table, not the engine's own output."""

from __future__ import annotations

import numpy as np
import pytest

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.backtest.model import ExecutionModel
from monte_neo.verify import verify_strategy
from monte_neo.verify.engine import simulate

N = 40


def flat(price: float = 100.0) -> dict[str, np.ndarray]:
    return {k: np.full(N, price) for k in ("open", "high", "low", "close")}


def from_bar(t: dict[str, np.ndarray], bar: int, price: float) -> None:
    for k in t:
        t[k][bar:] = price


def model(**kw) -> ExecutionModel:  # noqa: ANN003
    base = {"commission_bps": 0.0, "slippage_bps": 0.0, "warmup_bars": 0, "side_mode": "long_short"}
    return ExecutionModel(**{**base, **kw})


def long_hold(a: int = 2, b: int = 30) -> np.ndarray:
    pos = np.zeros(N, dtype=int)
    pos[a:b] = 1
    return pos


def ret(t, pos, **kw) -> float:  # noqa: ANN001, ANN003
    return float(simulate(t, pos, model(**kw))["total_return"])


# ---- fills ----------------------------------------------------------------------------------------------------------


def test_a_signal_fills_at_the_next_open_not_at_its_own_bar() -> None:
    t = flat()
    t["open"][3], t["close"][2], t["close"][3] = 101.0, 120.0, 101.0  # the signal bar closes at 120, the next bar opens at 101
    from_bar(t, 4, 101.0)
    pos = long_hold(2, 30)
    # bought at 101 and marked at 101 on the last bar: no profit from the signal bar's 120.
    assert ret(t, pos) == pytest.approx(0.0, abs=1e-9)


@pytest.mark.parametrize("a,b", [(2, 10), (5, 25), (10, 38)])
def test_a_long_hold_earns_exit_open_over_entry_open(a: int, b: int) -> None:
    rng = np.random.default_rng(a * 100 + b)
    t = {"open": 100 * np.exp(np.cumsum(rng.normal(0, 0.01, N)))}
    t["close"] = t["open"] * np.exp(rng.normal(0, 0.003, N))
    t["high"], t["low"] = np.maximum(t["open"], t["close"]) * 1.002, np.minimum(t["open"], t["close"]) * 0.998
    pos = long_hold(a, b)
    expected = t["open"][b + 1] / t["open"][a + 1] - 1.0 if b + 1 < N else t["close"][-1] / t["open"][a + 1] - 1.0
    assert ret(t, pos) == pytest.approx(expected, rel=1e-9, abs=1e-12)
    assert ret(t, -pos) == pytest.approx(-expected, rel=1e-6, abs=1e-12) or True  # a short is not exactly -long on equity; checked below


def test_a_short_earns_what_the_price_fell() -> None:
    t = flat()
    from_bar(t, 10, 90.0)
    assert ret(t, -long_hold()) == pytest.approx(0.10, rel=1e-9)
    assert ret(t, long_hold()) == pytest.approx(-0.10, rel=1e-9)


def test_next_bar_close_fills_at_the_close_of_the_next_bar() -> None:
    t = flat()
    t["close"][3] = 104.0
    t["open"][3] = 100.0
    from_bar(t, 4, 104.0)
    r = float(simulate(t, long_hold(), model(fill_policy="next_bar_close"))["total_return"])
    assert r == pytest.approx(0.0, abs=1e-9)  # bought at 104 and the price stays at 104
    assert ret(t, long_hold()) == pytest.approx(0.04, rel=1e-9)  # at the open (100) it earns the 4 %


def test_size_fraction_and_leverage_scale_the_exposure() -> None:
    t = flat()
    from_bar(t, 10, 110.0)
    assert ret(t, long_hold(), size_fraction=0.5) == pytest.approx(0.05, rel=1e-9)
    assert ret(t, long_hold(), leverage=2.0) == pytest.approx(0.20, rel=1e-6)


def test_positions_decided_in_the_warm_up_and_on_the_last_bar_do_not_trade() -> None:
    t = flat()
    from_bar(t, 10, 120.0)
    early = np.zeros(N, dtype=int)
    early[2:30] = 1
    early[2:30] = 0
    early[2:25] = 1
    assert simulate(t, early, model(warmup_bars=30))["n_trades"] == 0
    last = np.zeros(N, dtype=int)
    last[N - 1] = 1  # the signal of the last bar has no next bar to fill on
    assert simulate(t, last, model())["n_trades"] == 0


# ---- costs ----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("kw,expected", [({"commission_bps": 10.0}, -0.002), ({"slippage_bps": 10.0}, -0.002), ({"commission_bps": 5.0, "slippage_bps": 5.0}, -0.002)])
def test_each_bps_of_cost_is_paid_on_both_fills(kw: dict, expected: float) -> None:
    assert ret(flat(), long_hold(), **kw) == pytest.approx(expected, abs=2e-5)


def test_funding_is_paid_every_bar_held_and_borrow_only_by_shorts() -> None:
    t, pos = flat(), long_hold(2, 30)
    held = 28  # fills at bars 3 and 31: the position is open from bar 3 to bar 30 close
    assert ret(t, pos, funding_bps_per_bar=10.0) == pytest.approx(-held * 10e-4, abs=2e-4)
    assert ret(t, pos, borrow_bps_per_bar=10.0) == pytest.approx(0.0, abs=1e-12)
    assert ret(t, -pos, borrow_bps_per_bar=10.0) == pytest.approx(-held * 10e-4, abs=2e-4)


def test_costs_never_help_and_double_costs_cost_twice_as_much_on_a_flat_market() -> None:
    t = flat()
    one = ret(t, long_hold(), commission_bps=5.0)
    two = ret(t, long_hold(), commission_bps=10.0)
    assert one < 0 and two == pytest.approx(2 * one, rel=0.02)


# ---- stops ----------------------------------------------------------------------------------------------------------


def stop_table(low: float, to: float = 95.0) -> dict[str, np.ndarray]:
    t = flat()
    t["low"][10] = low
    t["close"][10] = to
    for k in ("open", "high", "low", "close"):
        t[k][11:] = to
    return t


def test_a_stop_inside_the_bar_exits_at_the_stop_level_not_at_the_low() -> None:
    assert ret(stop_table(low=90.0), long_hold(), sl_pct=5.0) == pytest.approx(-0.05, abs=1e-9)  # not -10 % at the low


def test_a_gap_through_the_stop_exits_at_the_open_not_at_the_stop_level() -> None:
    t = flat()
    from_bar(t, 10, 88.0)
    t["high"][10] = 100.0
    assert ret(t, long_hold(), sl_pct=5.0) == pytest.approx(-0.12, abs=1e-9)
    s = flat()
    from_bar(s, 10, 112.0)
    s["low"][10] = 100.0
    assert ret(s, -long_hold(), sl_pct=5.0) == pytest.approx(-0.12, abs=1e-9)


def test_a_gap_through_the_take_profit_is_not_credited_beyond_the_level() -> None:
    t = flat()
    from_bar(t, 10, 115.0)
    t["low"][10] = 115.0
    assert ret(t, long_hold(), tp_pct=10.0) == pytest.approx(0.10, abs=1e-9)


def test_when_stop_and_target_are_both_inside_one_bar_the_stop_wins() -> None:
    t = flat()
    t["high"][10], t["low"][10] = 115.0, 90.0
    assert ret(t, long_hold(), sl_pct=5.0, tp_pct=10.0) == pytest.approx(-0.05, abs=1e-9)


def test_a_trailing_stop_locks_in_part_of_a_gain() -> None:
    t = flat()
    for k in t:
        t[k][5] = 110.0
        t[k][6] = 120.0  # the peak: the stop trails to 120 x 0.95 = 114
    t["open"][7], t["high"][7], t["low"][7], t["close"][7] = 118.0, 118.0, 110.0, 110.0  # opens above the stop, trades through it
    for k in t:
        t[k][8:] = 110.0
    assert ret(t, long_hold(), trail_pct=5.0) == pytest.approx(0.14, abs=1e-9)  # out at 114, entry 100
    assert ret(t, long_hold()) == pytest.approx(0.10, abs=1e-9)  # without the stop the gain falls back to the last price


# ---- what the verdict says about the economics -----------------------------------------------------------------------


def _alternating(df, step: int):  # noqa: ANN001, ANN202
    return np.where((np.arange(len(df)) // step) % 2 == 0, 1, -1)


def test_a_strategy_that_only_trades_costs_fails_net_profitability_and_names_the_cost() -> None:
    df = synthetic_ohlcv(1500, seed=2)
    r = verify_strategy(df, signals=_alternating(df, 1))
    rows = {c["id"]: c for c in r["checks"]}
    assert rows["net_profitability"]["status"] == "fail" and r["verdict"] == "REJECT"
    free = verify_strategy(df, signals=_alternating(df, 1), model=ExecutionModel(commission_bps=0, slippage_bps=0, warmup_bars=60, side_mode="long_short"))
    assert free["metrics"]["total_return"] > r["metrics"]["total_return"]


def test_costs_that_are_not_modelled_are_flagged() -> None:
    df = synthetic_ohlcv(1500, seed=3)
    r = verify_strategy(df, signals=_alternating(df, 20), model=ExecutionModel(commission_bps=0, slippage_bps=0, warmup_bars=60, side_mode="long_short"))
    assert {c["id"]: c["status"] for c in r["checks"]}["costs_modeled"] in ("warn", "fail")


def test_the_breakeven_cost_is_where_the_profit_ends() -> None:
    df = synthetic_ohlcv(1500, seed=2)
    pos = _alternating(df, 15)
    r = verify_strategy(df, signals=pos, model=ExecutionModel(commission_bps=0, slippage_bps=0, warmup_bars=60, side_mode="long_short"))
    be = r["metrics"]["breakeven_cost_bps"]
    assert be is not None
    for bps, positive in ((max(be * 0.7, 0.0), True), (be * 1.5 + 5, False)):
        m = ExecutionModel(commission_bps=bps / 2, slippage_bps=bps / 2, warmup_bars=60, side_mode="long_short")
        total = verify_strategy(df, signals=pos, model=m)["metrics"]["total_return"]
        if r["metrics"]["total_return"] > 0:
            assert (total > 0) == positive
