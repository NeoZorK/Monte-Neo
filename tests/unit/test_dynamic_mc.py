"""Dynamic Monte Carlo rows: regime-swap null, regime-mix bootstrap, time-reversal null."""

from __future__ import annotations

import numpy as np
import pandas as pd

from monte_neo.backtest import ExecutionModel, synthetic_ohlcv
from monte_neo.verify import verify_strategy
from monte_neo.verify.dynamic_mc import (
    regime_mix_bootstrap,
    regime_mix_row,
    regime_swap_null,
    regime_swap_row,
    reverse_frame,
    time_reversal_row,
)

N = 2000
RNG = np.random.default_rng(1)


def _masks(n: int = N) -> tuple[dict[str, np.ndarray], np.ndarray]:
    usable = np.ones(n, dtype=bool)
    block = (np.arange(n) // 100) % 2 == 0
    vol = (np.arange(n) // 70) % 2 == 0
    return {"rising": block, "falling": ~block, "calm": vol, "volatile": ~vol}, usable


def test_swap_flags_loss_in_one_regime() -> None:  # positive: edge only in rising blocks, loses in falling
    masks, usable = _masks()
    r = np.where(masks["rising"], 0.002, -0.0015) + RNG.normal(0, 0.003, N)
    row = regime_swap_row(regime_swap_null(r, masks, usable), total_return=0.2)
    assert row["status"] == "warn" and "falling" in row["summary"]


def test_swap_passes_on_regime_free_returns() -> None:  # negative: honest edge, same in every regime
    masks, usable = _masks()
    r = 0.0008 + RNG.normal(0, 0.004, N)
    row = regime_swap_row(regime_swap_null(r, masks, usable), total_return=0.2)
    assert row["status"] == "pass"


def test_swap_boundary_too_few_bars_and_losing_strategy() -> None:
    masks, usable = _masks()
    tiny = {k: v & (np.arange(N) < 30) for k, v in masks.items()}
    assert regime_swap_row(regime_swap_null(RNG.normal(0, 0.01, N), tiny, usable), 0.1)["status"] == "skip"
    assert regime_swap_row({}, -0.1)["status"] == "skip"


def test_mix_bootstrap_warns_when_the_sample_mix_carries_the_sharpe() -> None:
    masks, _ = _masks()
    rising = (np.arange(N) % 100) < 85  # 85 % of the bars are rising: the sample's mix flatters the strategy
    masks = {**masks, "rising": rising, "falling": ~rising}
    r = np.where(rising, 0.0012, -0.004) + RNG.normal(0, 0.004, N)
    row = regime_mix_row(regime_mix_bootstrap(r, masks, 365.0, n_boot=200), 0.3)
    d = row["details"]["rising_falling"]
    assert d["observed_sharpe"] > 0 and d["equal_mix_median"] < d["observed_sharpe"]
    assert row["status"] == "warn"


def test_mix_bootstrap_passes_on_stable_edge_and_skips_small() -> None:
    masks, _ = _masks()
    r = 0.002 + RNG.normal(0, 0.004, N)
    assert regime_mix_row(regime_mix_bootstrap(r, masks, 365.0, n_boot=200), 0.3)["status"] == "pass"
    tiny = {k: v & (np.arange(N) < 20) for k, v in masks.items()}
    assert regime_mix_row(regime_mix_bootstrap(r, tiny, 365.0, n_boot=50), 0.3)["status"] == "skip"


def test_reverse_frame_is_valid_ohlc_and_involution() -> None:
    df = synthetic_ohlcv(300, seed=3)
    rev = reverse_frame(df)
    assert (rev["high"] >= rev[["open", "close"]].max(axis=1) - 1e-9).all()
    back = reverse_frame(rev)
    np.testing.assert_allclose(back["close"].to_numpy(), df["close"].to_numpy())
    if "timestamp" in df.columns:
        assert pd.Series(pd.to_datetime(rev["timestamp"])).is_monotonic_increasing or pd.api.types.is_numeric_dtype(rev["timestamp"])


def test_time_reversal_row_states() -> None:
    assert time_reversal_row({"total_return": 0.1}, None, "needs code")["status"] == "skip"
    orig = {"total_return": 0.2}
    lost = time_reversal_row(orig, {"total_return": -0.1, "benchmark_return": 0.0, "excess_return": -0.1})
    kept = time_reversal_row(orig, {"total_return": 0.3, "benchmark_return": 0.0, "excess_return": 0.3})
    assert lost["status"] == kept["status"] == "info" and "vanishes" in lost["summary"] and "also appears" in kept["summary"]


def test_verify_emits_rows_and_never_rejects_honest_trend() -> None:
    df = synthetic_ohlcv(1500, seed=7)

    def sig(d: pd.DataFrame) -> np.ndarray:
        c = d["close"]
        return (c > c.rolling(50).mean()).astype(int).shift(1).fillna(0).to_numpy()

    out = verify_strategy(df, signal_fn=sig, model=ExecutionModel(warmup_bars=60))
    ids = {c["id"]: c for c in out["checks"]}
    for k in ("regime_swap_null", "regime_mix_bootstrap", "time_reversal_null"):
        assert k in ids
    assert all(ids[k]["status"] != "fail" for k in ("regime_swap_null", "regime_mix_bootstrap", "time_reversal_null"))


def test_edge_cases_for_coverage_and_boundaries() -> None:
    from monte_neo.verify.dynamic_mc import _sharpe, run_reversed

    assert _sharpe(np.array([0.01]), 252.0) == 0.0 and _sharpe(np.zeros(10), 252.0) == 0.0
    r = RNG.normal(0, 0.01, N)
    assert regime_swap_null(r, {"rising": np.ones(N, bool)}, np.ones(N, bool)) == {}  # a pair missing: nothing to test
    assert regime_mix_bootstrap(r, {"rising": np.ones(N, bool)}, 252.0) == {}
    df = synthetic_ohlcv(100, seed=1)
    df["timestamp"] = np.arange(100, dtype=np.int64) * 60
    rev = reverse_frame(df)
    assert rev["timestamp"].is_monotonic_increasing
    res, why = run_reversed(df, lambda d: np.ones(len(d) - 1), "sign", ExecutionModel(warmup_bars=2), 0.1)
    assert res is None and "different length" in why
    row = time_reversal_row({"total_return": -0.1}, {"total_return": 0.0, "benchmark_return": 0.0, "excess_return": 0.0})
    assert row["status"] == "skip"


def test_run_reversed_success_and_strategy_failure() -> None:
    from monte_neo.verify.dynamic_mc import run_reversed

    df = synthetic_ohlcv(400, seed=2)
    model = ExecutionModel(warmup_bars=5)
    ok, why = run_reversed(df, lambda d: np.ones(len(d), dtype=int), "sign", model, 0.1)
    assert why == "" and ok is not None and ok["excess_return"] == 0.0  # always long = buy and hold on any history

    def boom(d: pd.DataFrame) -> np.ndarray:
        raise RuntimeError("x")

    bad, why = run_reversed(df, boom, "sign", model, 0.1)
    assert bad is None and "could not run" in why
