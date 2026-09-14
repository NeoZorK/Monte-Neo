"""Integration / stress for OMS tick L2 path."""

from __future__ import annotations

import numpy as np
import pytest

from monte_neo.oms import OrderSide, TickL2Engine, synthetic_ticks
from monte_neo.oms.l2_match import L2MatchConfig


def test_tick_engine_buy_sell_roundtrip() -> None:
    ticks = synthetic_ticks(5_000, seed=11)
    eng = TickL2Engine(
        initial_cash=100_000.0,
        l2=L2MatchConfig(commission_bps=2.0),
        device="cpu_numba",
    )
    eng.submit_market(OrderSide.BUY, qty=2.0, tag="buy")
    mid = eng.run_ticks(ticks[:2500])
    assert mid["blotter"]["n_fills"] >= 1
    eng.submit_market(OrderSide.SELL, qty=2.0, tag="sell")
    out = eng.run_ticks(ticks[2500:])
    assert out["ok"] is True
    assert abs(out["account"]["positions"]["SYM"]["qty"]) < 1e-9
    assert np.isfinite(out["total_return"])


@pytest.mark.stress
def test_tick_l2_100k_ticks() -> None:
    ticks = synthetic_ticks(100_000, seed=5)
    eng = TickL2Engine(device="cpu_numba", initial_cash=200_000.0)
    eng.submit_market(OrderSide.BUY, qty=1.0)
    out = eng.run_ticks(ticks)
    assert out["n_ticks"] == 100_000
    assert out["blotter"]["n_fills"] >= 1
