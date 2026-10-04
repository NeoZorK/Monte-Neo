"""Metamorphic relations: transformations of the input with a known effect on the result (class A9).

None of these needs a trusted reference value, only the relation between two runs of the verifier.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "traps"))
from trap_data import planted_momentum_ohlcv, universe_ohlcv  # noqa: E402

from monte_neo.backtest import synthetic_ohlcv  # noqa: E402
from monte_neo.verify import model_from_costs, verify_strategy  # noqa: E402

METRICS = ("total_return", "max_drawdown", "sharpe_annualized", "n_closed_trades", "n_fills", "exposure")


def _datasets() -> dict[str, pd.DataFrame]:
    walk = synthetic_ohlcv(2000, seed=1)
    walk["timestamp"] = pd.date_range("2021-01-04", periods=len(walk), freq="h")
    daily = synthetic_ohlcv(1500, seed=5)
    daily["timestamp"] = pd.date_range("2018-01-01", periods=len(daily), freq="1D")
    return {"walk": walk, "planted": planted_momentum_ohlcv(3000), "daily": daily}


DATA = _datasets()


def _signals(df: pd.DataFrame) -> np.ndarray:
    return np.where(df["close"].rolling(10).mean() > df["close"].rolling(40).mean(), 1, -1)


def _run(df: pd.DataFrame, signals: np.ndarray, cost_bps: float = 5.0, **kw) -> dict:  # noqa: ANN003
    model = model_from_costs(commission_bps=cost_bps, slippage_bps=cost_bps, side_mode="long_short", warmup_bars=50, n_bars=len(df))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return verify_strategy(df, signals=signals, model=model, **kw)


def _same(a: dict, b: dict, tol: float = 1e-9) -> None:
    for key in METRICS:
        x, y = a["metrics"][key], b["metrics"][key]
        assert x == pytest.approx(y, rel=tol, abs=tol), (key, x, y)


@pytest.fixture(params=list(DATA), ids=list(DATA))
def case(request: pytest.FixtureRequest) -> tuple[pd.DataFrame, np.ndarray, dict]:
    df = DATA[request.param]
    sig = _signals(df)
    return df, sig, _run(df, sig)


def test_price_scale_does_not_matter(case: tuple) -> None:
    df, sig, base = case
    scaled = df.copy()
    scaled[["open", "high", "low", "close"]] *= 3.7
    _same(base, _run(scaled, sig))


def test_shifting_every_timestamp_does_not_matter(case: tuple) -> None:
    df, sig, base = case
    moved = df.copy()
    moved["timestamp"] = pd.to_datetime(moved["timestamp"]) + pd.Timedelta(days=5)
    _same(base, _run(moved, sig))


def test_volume_scale_changes_only_the_capacity(case: tuple) -> None:
    df, sig, base = case
    if "volume" not in df.columns:
        pytest.skip("this table has no volume")
    scaled = df.copy()
    scaled["volume"] = scaled["volume"] * 10.0
    other = _run(scaled, sig)
    _same(base, other)
    if base["metrics"].get("capacity_5pct"):
        assert other["metrics"]["capacity_5pct"] == pytest.approx(10 * base["metrics"]["capacity_5pct"], rel=1e-6)


def test_an_extra_column_does_not_matter(case: tuple) -> None:
    df, sig, base = case
    _same(base, _run(df.assign(extra=np.arange(len(df)) % 7), sig))


def test_integer_and_float_positions_are_the_same(case: tuple) -> None:
    df, sig, base = case
    _same(base, _run(df, sig.astype(np.float64)))


def test_the_same_inputs_give_the_same_certificate(case: tuple) -> None:
    df, sig, base = case
    again = _run(df, sig)
    assert again["certificate_id"] == base["certificate_id"] and again["verdict"] == base["verdict"]


def test_higher_costs_never_help(case: tuple) -> None:
    df, sig, _ = case
    returns = [_run(df, sig, c)["metrics"]["total_return"] for c in (0.0, 5.0, 20.0)]
    assert returns[0] >= returns[1] >= returns[2]


def test_long_only_positions_are_the_same_in_long_flat_and_long_short(case: tuple) -> None:
    df, sig, _ = case
    long_only = np.maximum(sig, 0)
    out = []
    for side in ("long_short", "long_flat"):
        model = model_from_costs(commission_bps=5, slippage_bps=5, side_mode=side, warmup_bars=50, n_bars=len(df))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            out.append(verify_strategy(df, signals=long_only, model=model))
    _same(out[0], out[1])


def test_negated_positions_pay_the_volatility_drag(case: tuple) -> None:
    """Without costs, ln(equity) of a position and of its negation add up to sum(ln(1 - (position x return)^2)) <= 0."""
    df, sig, _ = case
    up = _run(df, sig, 0.0)["metrics"]["total_return"]
    down = _run(df, -sig, 0.0)["metrics"]["total_return"]
    assert np.log1p(up) + np.log1p(down) <= 1e-9


@pytest.mark.parametrize("period", [2, 5, 17])
@pytest.mark.parametrize("cost_bps", [1.0, 5.0, 25.0])
def test_trading_a_flat_market_costs_the_modelled_costs_per_fill(period: int, cost_bps: float) -> None:
    """Constant prices, positions alternating long/short every ``period`` bars: every fill loses commission + slippage."""
    n = 400
    flat = pd.DataFrame({k: np.full(n, 100.0) for k in ("open", "high", "low", "close")})
    flat["volume"] = 1.0
    flat["timestamp"] = pd.date_range("2022-01-03", periods=n, freq="h")
    sig = np.where((np.arange(n) // period) % 2 == 0, 1, -1)
    report = _run(flat, sig, cost_bps)
    fills = report["metrics"]["n_fills"]
    per_fill = (1 + report["metrics"]["total_return"]) ** (1 / fills) - 1
    assert per_fill == pytest.approx(-2 * cost_bps / 1e4, rel=1e-2)  # commission + slippage, compounding on shrinking equity


def test_a_universe_does_not_care_about_row_order_or_symbol_names() -> None:
    df = universe_ohlcv()

    def rank(d: pd.DataFrame) -> pd.Series:
        mom = d.groupby("symbol")["close"].pct_change(10)
        return mom.groupby(d["timestamp"]).rank(pct=True).sub(0.5).fillna(0.0)

    def run(table: pd.DataFrame) -> dict:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return verify_strategy(table, signal_fn=rank)

    base = run(df)
    shuffled = df.sample(frac=1.0, random_state=4).reset_index(drop=True)
    renamed = df.assign(symbol=df["symbol"].map({s: f"Z{i}" for i, s in enumerate(sorted(df["symbol"].unique()))}))
    for other in (run(shuffled), run(renamed)):
        _same(base, other, tol=1e-6)
