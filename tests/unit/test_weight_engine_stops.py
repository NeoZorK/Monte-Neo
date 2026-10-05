"""Stops inside the bar for target weights: equal to the discrete engine, and to an independent reference."""

from __future__ import annotations

import subprocess
import sys

import numpy as np
import pytest

from monte_neo.backtest import ExecutionModel, run_bar_backtest, synthetic_ohlcv
from monte_neo.backtest.weight_engine import run_weight_backtest


def _bars(n: int, seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    df = synthetic_ohlcv(n, seed=seed)
    return tuple(df[k].to_numpy() for k in ("open", "high", "low", "close"))  # type: ignore[return-value]


@pytest.mark.parametrize("seed", range(60))
def test_stops_equal_the_discrete_engine_bit_for_bit(seed: int) -> None:
    rng = np.random.default_rng(1000 + seed)
    n = int(rng.integers(80, 700))
    o, h, l, c = _bars(n, seed)
    hold = int(rng.integers(1, 40))
    sig = np.repeat(rng.integers(-1, 2, n // hold + 1), hold)[:n]
    model = ExecutionModel(
        side_mode=str(rng.choice(["long_flat", "long_short"])),
        commission_bps=float(rng.uniform(0, 20)),
        slippage_bps=float(rng.uniform(0, 20)),
        warmup_bars=int(rng.integers(0, 20)),
        fill_policy=str(rng.choice(["next_bar_open", "next_bar_close"])),
        funding_bps_per_bar=float(rng.choice([0.0, 0.3])),
        borrow_bps_per_bar=float(rng.choice([0.0, 0.4])),
        sl_pct=float(rng.choice([0.0, 0.05, 0.2, 1.0])),
        tp_pct=float(rng.choice([0.0, 0.05, 0.3, 2.0])),
        trail_pct=float(rng.choice([0.0, 0.1, 0.5])),
        size_fraction=float(rng.choice([1.0, 0.6])),
        leverage=float(rng.choice([1.0, 2.0])),
    )
    a = run_bar_backtest(o, h, l, c, sig, model=model)
    b = run_weight_backtest(o, c, sig.astype(np.float64), model=model, high=h, low=l)
    assert np.array_equal(a["equity"], b["equity"])
    for key in ("total_return", "max_drawdown", "n_trades", "n_closed_trades"):
        assert a[key] == b[key], key


def test_the_stop_level_and_the_take_profit_level_are_where_the_arithmetic_says() -> None:
    o = np.array([100.0, 100.0, 100.0, 100.0, 100.0])
    c = np.array([100.0, 100.0, 100.0, 100.0, 100.0])
    h = np.array([100.0, 100.0, 100.0, 103.0, 100.0])
    l = np.array([100.0, 100.0, 100.0, 99.0, 100.0])
    free = dict(side_mode="long_short", commission_bps=0.0, slippage_bps=0.0, warmup_bars=0)
    # Long from bar 1's open at 100: a 2% take-profit sits at 102 and the bar-3 high (103) reaches it.
    tp = run_weight_backtest(o, c, np.ones(5), model=ExecutionModel(tp_pct=2.0, **free), high=h, low=l)
    assert tp["total_return"] == pytest.approx(0.02)
    # A 0.5% stop sits at 99.5 and the bar-3 low (99) reaches it: a 0.5% loss.
    sl = run_weight_backtest(o, c, np.ones(5), model=ExecutionModel(sl_pct=0.5, **free), high=h, low=l)
    assert sl["total_return"] == pytest.approx(-0.005)
    # Both touched on one bar: the stop is tested first.
    both = run_weight_backtest(o, c, np.ones(5), model=ExecutionModel(sl_pct=0.5, tp_pct=2.0, **free), high=h, low=l)
    assert both["total_return"] == pytest.approx(-0.005)


def test_a_short_stops_out_on_the_high() -> None:
    n = 6
    o = c = np.full(n, 100.0)
    h = np.array([100, 100, 100, 101.5, 100, 100.0])
    l = np.array([100, 100, 100, 99.9, 100, 100.0])
    model = ExecutionModel(side_mode="long_short", commission_bps=0.0, slippage_bps=0.0, warmup_bars=0, sl_pct=1.0)
    out = run_weight_backtest(o, c, -np.ones(n), model=model, high=h, low=l)
    assert out["total_return"] == pytest.approx(-0.01)


def test_stops_need_high_and_low() -> None:
    px = np.full(10, 100.0)
    with pytest.raises(ValueError, match="high and low"):
        run_weight_backtest(px, px, np.ones(10), model=ExecutionModel(sl_pct=1.0, warmup_bars=0))
    with pytest.raises(ValueError, match="shape"):
        run_weight_backtest(px, px, np.ones(10), model=ExecutionModel(sl_pct=1.0, warmup_bars=0), high=px[:5], low=px[:5])


def test_without_stops_high_and_low_change_nothing() -> None:
    o, h, l, c = _bars(300, 3)
    w = np.round(np.sin(np.arange(300) / 20.0), 1)
    model = ExecutionModel(side_mode="long_short", warmup_bars=10)
    a = run_weight_backtest(o, c, w, model=model)
    b = run_weight_backtest(o, c, w, model=model, high=h, low=l)
    assert np.array_equal(a["equity"], b["equity"]) and a["total_return"] == b["total_return"]


def _reference(o, h, l, c, w, model):
    """An independent shared-cash reference: instruments in column order, levels set when a position is opened."""
    n, m = c.shape
    fee, slip = model.commission_bps * 1e-4, model.effective_slip_bps * 1e-4
    scale = model.size_fraction * model.fill_fraction * model.leverage
    cash = model.initial_cash
    qty, applied = np.zeros(m), np.zeros(m)
    sl, tp, peak = np.zeros(m), np.zeros(m), np.zeros(m)
    use_sl, use_tp, use_tr = model.sl_pct > 0, model.tp_pct > 0, model.trail_pct > 0
    for i in range(n):
        for s in range(m):
            if qty[s] == 0.0:
                continue
            side = 1.0 if qty[s] > 0 else -1.0
            level = None
            if side > 0:
                if use_tr and h[i, s] > peak[s]:
                    peak[s] = h[i, s]
                    trail = peak[s] * (1 - model.trail_pct * 0.01)
                    if not use_sl or trail > sl[s]:
                        sl[s] = trail
                if (use_sl or use_tr) and l[i, s] <= sl[s]:
                    level = min(sl[s], o[i, s])  # a gap through the stop: the position leaves at the open
                elif use_tp and h[i, s] >= tp[s]:
                    level = tp[s]
            else:
                if use_tr and l[i, s] < peak[s]:
                    peak[s] = l[i, s]
                    trail = peak[s] * (1 + model.trail_pct * 0.01)
                    if not use_sl or trail < sl[s]:
                        sl[s] = trail
                if (use_sl or use_tr) and h[i, s] >= sl[s]:
                    level = max(sl[s], o[i, s])
                elif use_tp and l[i, s] <= tp[s]:
                    level = tp[s]
            if level is not None:
                proceeds = qty[s] * level * (1 - side * slip)
                cash += proceeds - abs(proceeds) * fee
                qty[s], applied[s] = 0.0, 0.0
        if i < model.warmup_bars or i + 1 >= n:
            continue
        for s in range(m):
            target = w[i, s] * scale
            if target == applied[s]:
                continue
            fill = o[i + 1, s]
            if qty[s] != 0 and (target == 0 or (target > 0) != (qty[s] > 0)):
                side = 1.0 if qty[s] > 0 else -1.0
                proceeds = qty[s] * fill * (1 - side * slip)
                cash += proceeds - abs(proceeds) * fee
                qty[s] = 0.0
            if target != 0:
                others = sum(qty[t] * c[i, t] for t in range(m) if t != s)
                base = cash + others + qty[s] * fill
                if base <= 0:
                    continue
                direction = 1.0 if target * base / fill > qty[s] else -1.0
                px = fill * (1 + direction * slip)
                desired = target * base / px
                opening = qty[s] == 0
                cash -= (desired - qty[s]) * px + abs((desired - qty[s]) * px) * fee
                qty[s] = desired
                if opening:
                    peak[s] = px
                    up = desired > 0
                    if use_sl:
                        sl[s] = px * (1 - model.sl_pct * 0.01) if up else px * (1 + model.sl_pct * 0.01)
                    elif use_tr:
                        sl[s] = px * (1 - model.trail_pct * 0.01) if up else px * (1 + model.trail_pct * 0.01)
                    if use_tp:
                        tp[s] = px * (1 + model.tp_pct * 0.01) if up else px * (1 - model.tp_pct * 0.01)
            applied[s] = target
    for s in range(m):
        if qty[s] != 0:
            side = 1.0 if qty[s] > 0 else -1.0
            proceeds = qty[s] * c[n - 1, s] * (1 - side * slip)
            cash += proceeds - abs(proceeds) * fee
    return cash / model.initial_cash - 1.0


@pytest.mark.parametrize("seed", range(30))
def test_fractional_weights_over_several_instruments_match_an_independent_reference(seed: int) -> None:
    rng = np.random.default_rng(2000 + seed)
    m, n = int(rng.integers(1, 4)), int(rng.integers(120, 400))
    frames = [_bars(n, 50 * seed + k) for k in range(m)]
    o, h, l, c = (np.column_stack([f[j] for f in frames]) for j in range(4))
    hold = int(rng.integers(3, 30))
    w = np.round(np.repeat(rng.uniform(-1, 1, (n // hold + 1, m)), hold, axis=0)[:n], 1) / m
    model = ExecutionModel(
        side_mode="long_short",
        commission_bps=float(rng.uniform(0, 10)),
        slippage_bps=float(rng.uniform(0, 10)),
        warmup_bars=int(rng.integers(0, 20)),
        sl_pct=float(rng.choice([0.0, 0.1, 0.5])),
        tp_pct=float(rng.choice([0.0, 0.2, 1.0])),
        trail_pct=float(rng.choice([0.0, 0.2])),
        size_fraction=float(rng.choice([1.0, 0.7])),
    )
    got = run_weight_backtest(o, c, w, model=model, high=h, low=l)["total_return"]
    assert got == pytest.approx(_reference(o, h, l, c, w, model), rel=1e-9, abs=1e-12)


def test_the_pure_python_fallback_gives_the_same_numbers() -> None:
    code = (
        "import numpy as np\n"
        "from monte_neo.backtest import ExecutionModel, synthetic_ohlcv\n"
        "from monte_neo.backtest.weight_engine import run_weight_backtest\n"
        "df = synthetic_ohlcv(400, seed=9)\n"
        "o, h, l, c = (df[k].to_numpy() for k in ('open', 'high', 'low', 'close'))\n"
        "w = np.round(np.sin(np.arange(400) / 15.0), 1)\n"
        "m = ExecutionModel(side_mode='long_short', warmup_bars=10, sl_pct=0.3, tp_pct=0.6, trail_pct=0.2)\n"
        "print(repr(run_weight_backtest(o, c, w, model=m, high=h, low=l)['total_return']))\n"
    )
    import os

    env = dict(os.environ, NUMBA_DISABLE_JIT="1")
    slow = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, check=True).stdout
    fast = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
    assert slow == fast and slow.strip()


# ---- through the verifier ------------------------------------------------------------------


def _weights(n: int) -> np.ndarray:
    return np.round(np.sin(np.arange(n) / 25.0), 1)


def test_verify_strategy_applies_stops_to_weights_and_records_them() -> None:
    from monte_neo.verify import model_from_costs, verify_strategy

    df = synthetic_ohlcv(1200, seed=6)
    w = _weights(len(df))
    plain = verify_strategy(df, signals=w, model=model_from_costs(n_bars=len(df)), positions="weight")
    stopped = verify_strategy(
        df, signals=w, model=model_from_costs(n_bars=len(df), sl_pct=0.4, tp_pct=0.8, trail_pct=0.3), positions="weight"
    )
    model = stopped["reproducibility"]["model"]
    assert (model["sl_pct"], model["tp_pct"], model["trail_pct"]) == (0.4, 0.8, 0.3)
    assert stopped["metrics"]["total_return"] != plain["metrics"]["total_return"]
    assert stopped["certificate_id"] != plain["certificate_id"]
    assert stopped["metrics"]["n_closed_trades"] > plain["metrics"]["n_closed_trades"]  # stops close positions early


def test_the_benchmark_is_a_plain_buy_and_hold_even_with_stops() -> None:
    from monte_neo.verify import model_from_costs, verify_strategy

    df = synthetic_ohlcv(1200, seed=6)
    w = _weights(len(df))
    plain = verify_strategy(df, signals=w, model=model_from_costs(n_bars=len(df)), positions="weight")
    stopped = verify_strategy(df, signals=w, model=model_from_costs(n_bars=len(df), sl_pct=0.2), positions="weight")
    assert stopped["benchmark"] == plain["benchmark"]


def test_a_universe_with_stops_verifies_and_reproduces() -> None:
    import pandas as pd

    from monte_neo.verify import model_from_costs, verify_strategy

    frames = []
    for k, sym in enumerate(("AAA", "BBB", "CCC")):
        d = synthetic_ohlcv(500, seed=20 + k)
        d["timestamp"] = pd.date_range("2023-01-01", periods=500, freq="D")
        d["symbol"] = sym
        frames.append(d)
    table = pd.concat(frames).sort_values(["timestamp", "symbol"]).reset_index(drop=True)

    def strategy(df: pd.DataFrame) -> pd.Series:
        mom = df.groupby("symbol")["close"].pct_change(10)
        return mom.groupby(df["timestamp"]).rank(pct=True).sub(0.5).fillna(0.0)

    model = model_from_costs(n_bars=500, sl_pct=1.0, tp_pct=2.0)
    a = verify_strategy(table, signal_fn=strategy, model=model)
    b = verify_strategy(table, signal_fn=strategy, model=model)
    assert a["certificate_id"] == b["certificate_id"]
    assert a["metrics"]["positions"] == "weight"


def test_cli_and_report_carry_the_stops(tmp_path) -> None:
    import json

    from monte_neo.cli.verify_cmd import main

    csv, sig, cert, page = tmp_path / "p.csv", tmp_path / "s.npy", tmp_path / "c.json", tmp_path / "r.html"
    synthetic_ohlcv(600, seed=8).to_csv(csv, index=False)
    np.save(sig, _weights(600))
    code = main([
        "--ohlcv", str(csv), "--signals", str(sig), "--positions", "weight", "--sl-pct", "0.5", "--tp-pct", "1", "--trail-pct", "0.4",
        "--out", str(cert), "--html", str(page), "--format", "json",
    ])
    assert code in (0, 1, 2)
    model = json.loads(cert.read_text())["reproducibility"]["model"]
    assert (model["sl_pct"], model["tp_pct"], model["trail_pct"]) == (0.5, 1.0, 0.4)
    text = page.read_text()
    assert "stop-loss 0.50%" in text and "take-profit 1.00%" in text and "trailing stop 0.40%" in text
    assert main(["--ohlcv", str(csv), "--signals", str(sig), "--sl-pct", "abc"]) == 3
