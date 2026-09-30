"""Per-symbol trading costs for universes."""

from __future__ import annotations

import json
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from monte_neo.backtest import ExecutionModel, synthetic_ohlcv
from monte_neo.backtest.batch import run_bar_backtest_batch
from monte_neo.backtest.weight_engine import run_weight_backtest
from monte_neo.verify import model_from_costs, recheck_certificate, verify_grid, verify_strategy
from monte_neo.verify.engine import simulate
from monte_neo.verify.symbol_costs import apply_symbol_costs, parse_symbol_costs, resolve_symbol_costs

SYMBOLS = ("AAA", "BBB", "CCC")


def _table(bars: int = 400, symbols: tuple[str, ...] = SYMBOLS) -> pd.DataFrame:
    frames = []
    for k, sym in enumerate(symbols):
        d = synthetic_ohlcv(bars, seed=30 + k)
        d["timestamp"] = pd.date_range("2023-01-01", periods=bars, freq="D")
        d["symbol"] = sym
        frames.append(d)
    return pd.concat(frames).sort_values(["timestamp", "symbol"]).reset_index(drop=True)


def _momentum(df: pd.DataFrame) -> pd.Series:
    mom = df.groupby("symbol")["close"].pct_change(10)
    return mom.groupby(df["timestamp"]).rank(pct=True).sub(0.5).fillna(0.0)


def _matrices(m: int = 3, n: int = 300):
    frames = [synthetic_ohlcv(n, seed=70 + k) for k in range(m)]
    return tuple(np.column_stack([f[key].to_numpy() for f in frames]) for key in ("open", "high", "low", "close"))


def _weights(n: int, m: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.round(np.repeat(rng.uniform(-1, 1, (n // 12 + 1, m)), 12, axis=0)[:n], 1) / m


# ---- the engine ----------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(10))
def test_a_table_of_equal_costs_equals_the_uniform_model_bit_for_bit(seed: int) -> None:
    o, h, l, c = _matrices()
    w = _weights(300, 3, seed)
    uniform = ExecutionModel(side_mode="long_short", commission_bps=3.0, slippage_bps=4.0, impact_bps=1.0, warmup_bars=10)
    table = ExecutionModel(
        side_mode="long_short", commission_bps=99.0, slippage_bps=99.0, impact_bps=1.0, warmup_bars=10,
        symbol_costs=tuple((s, 3.0, 4.0) for s in SYMBOLS),
    )
    a = run_weight_backtest(o, c, w, model=uniform)
    b = run_weight_backtest(o, c, w, model=table)
    assert np.array_equal(a["equity"], b["equity"]) and a["total_return"] == b["total_return"]


def _reference(o, c, w, fees_bps, slips_bps, warmup):
    """Independent shared-cash loop with a cost per instrument (no stops)."""
    n, m = c.shape
    cash, qty, applied = 100000.0, np.zeros(m), np.zeros(m)
    fee, slip = np.array(fees_bps) * 1e-4, np.array(slips_bps) * 1e-4
    for i in range(n):
        if i < warmup or i + 1 >= n:
            continue
        for s in range(m):
            t = w[i, s]
            if t == applied[s]:
                continue
            fill = o[i + 1, s]
            if qty[s] != 0 and (t == 0 or (t > 0) != (qty[s] > 0)):
                side = 1.0 if qty[s] > 0 else -1.0
                pr = qty[s] * fill * (1 - side * slip[s])
                cash += pr - abs(pr) * fee[s]
                qty[s] = 0.0
            if t != 0:
                base = cash + sum(qty[k] * c[i, k] for k in range(m) if k != s) + qty[s] * fill
                if base <= 0:
                    continue
                d = 1.0 if t * base / fill > qty[s] else -1.0
                px = fill * (1 + d * slip[s])
                desired = t * base / px
                cash -= (desired - qty[s]) * px + abs((desired - qty[s]) * px) * fee[s]
                qty[s] = desired
            applied[s] = t
    for s in range(m):
        if qty[s] != 0:
            side = 1.0 if qty[s] > 0 else -1.0
            pr = qty[s] * c[-1, s] * (1 - side * slip[s])
            cash += pr - abs(pr) * fee[s]
    return cash / 100000.0 - 1.0


@pytest.mark.parametrize("seed", range(15))
def test_different_costs_match_an_independent_reference(seed: int) -> None:
    rng = np.random.default_rng(500 + seed)
    o, h, l, c = _matrices()
    w = _weights(300, 3, seed)
    fees, slips = rng.uniform(0, 30, 3), rng.uniform(0, 30, 3)
    model = ExecutionModel(
        side_mode="long_short", warmup_bars=10, impact_bps=0.0,
        symbol_costs=tuple((s, float(f), float(sl)) for s, f, sl in zip(SYMBOLS, fees, slips, strict=True)),
    )
    got = run_weight_backtest(o, c, w, model=model)["total_return"]
    assert got == pytest.approx(_reference(o, c, w, fees, slips, 10), rel=1e-9, abs=1e-12)


def test_a_costlier_symbol_costs_more_and_a_free_one_costs_nothing() -> None:
    o, h, l, c = _matrices(m=1)
    w = _weights(300, 1, 3)
    base = dict(side_mode="long_short", warmup_bars=10, impact_bps=0.0)
    free = run_weight_backtest(o, c, w, model=ExecutionModel(symbol_costs=(("A", 0.0, 0.0),), **base))["total_return"]
    cheap = run_weight_backtest(o, c, w, model=ExecutionModel(symbol_costs=(("A", 1.0, 1.0),), **base))["total_return"]
    dear = run_weight_backtest(o, c, w, model=ExecutionModel(symbol_costs=(("A", 20.0, 20.0),), **base))["total_return"]
    assert free > cheap > dear


def test_stops_and_symbol_costs_work_together() -> None:
    o, h, l, c = _matrices()
    w = _weights(300, 3, 4)
    a = run_weight_backtest(
        o, c, w, high=h, low=l,
        model=ExecutionModel(side_mode="long_short", warmup_bars=10, sl_pct=0.5, tp_pct=1.0, commission_bps=2.0, slippage_bps=3.0),
    )
    b = run_weight_backtest(
        o, c, w, high=h, low=l,
        model=ExecutionModel(
            side_mode="long_short", warmup_bars=10, sl_pct=0.5, tp_pct=1.0, symbol_costs=tuple((s, 2.0, 3.0) for s in SYMBOLS)
        ),
    )
    assert np.array_equal(a["equity"], b["equity"])


def test_the_number_of_rows_must_match_the_instruments() -> None:
    o, h, l, c = _matrices()
    with pytest.raises(ValueError, match="symbols but the table has"):
        run_weight_backtest(o, c, _weights(300, 3, 1), model=ExecutionModel(side_mode="long_short", symbol_costs=(("A", 1.0, 1.0),)))


def test_engines_that_would_ignore_per_symbol_costs_refuse_them() -> None:
    model = ExecutionModel(symbol_costs=(("A", 1.0, 1.0),))
    df = synthetic_ohlcv(200, seed=1)
    ohlc = {k: df[k].to_numpy(dtype=np.float64) for k in ("open", "high", "low", "close")}
    with pytest.raises(ValueError, match="per-symbol costs"):
        simulate(ohlc, np.zeros(200, dtype=np.int64), model)
    with pytest.raises(ValueError, match="per-symbol costs"):
        run_bar_backtest_batch(*(ohlc[k] for k in ("open", "high", "low", "close")), np.zeros((1, 200), dtype=np.int64), model)


def test_the_model_dict_omits_the_rows_when_unset_and_rebuilds_from_json() -> None:
    assert "symbol_costs" not in ExecutionModel().to_dict()
    model = ExecutionModel(symbol_costs=(("A", 1.0, 2.0), ("B", 3.0, 4.0)))
    again = ExecutionModel(**json.loads(json.dumps(model.to_dict())))
    assert again.symbol_costs == model.symbol_costs
    assert model.mean_commission_bps == 2.0 and model.mean_slip_bps == 3.0 and model.mean_side_cost_bps == 5.0
    with pytest.raises(ValueError, match="non-negative"):
        ExecutionModel(symbol_costs=(("A", -1.0, 0.0),))


# ---- resolving and validating the mapping ----------------------------------------------------


def test_a_symbol_takes_its_own_value_then_default_then_the_uniform_costs() -> None:
    model = ExecutionModel(commission_bps=7.0, slippage_bps=8.0)
    rows = resolve_symbol_costs(
        {"default": {"slippage_bps": 20}, "AAA": {"commission_bps": 1}, "CCC": {"commission_bps": 2, "slippage_bps": 3}},
        SYMBOLS, model,
    )
    assert rows == (("AAA", 1.0, 20.0), ("BBB", 7.0, 20.0), ("CCC", 2.0, 3.0))
    no_default = resolve_symbol_costs({"BBB": {"slippage_bps": 1}}, SYMBOLS, model)
    assert no_default == (("AAA", 7.0, 8.0), ("BBB", 7.0, 1.0), ("CCC", 7.0, 8.0))


@pytest.mark.parametrize(
    ("spec", "message"),
    [
        ({"ZZZ": {"slippage_bps": 1}}, "not in the data"),
        ({"AAA": {"commission": 1}}, "unknown cost key"),
        ({"AAA": {"slippage_bps": -1}}, "at least 0"),
        ({"AAA": {"slippage_bps": float("nan")}}, "finite"),
        ({"AAA": {"slippage_bps": True}}, "finite number"),
        ({"AAA": {"slippage_bps": "5"}}, "finite number"),
        ({"AAA": {}}, "must be an object"),
        ({"AAA": 5}, "must be an object"),
        ({}, "non-empty"),
        ("[1, 2]", "non-empty JSON object"),
    ],
)
def test_bad_costs_are_refused_with_a_reason(spec, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        resolve_symbol_costs(spec, SYMBOLS, ExecutionModel())


def test_costs_come_from_a_dict_json_text_or_a_file(tmp_path) -> None:
    spec = {"AAA": {"commission_bps": 2, "slippage_bps": 1}}
    path = tmp_path / "costs.json"
    path.write_text(json.dumps(spec))
    assert parse_symbol_costs(spec) == parse_symbol_costs(json.dumps(spec)) == parse_symbol_costs(str(path)) == parse_symbol_costs(path)
    with pytest.raises(ValueError):
        parse_symbol_costs('{"AAA": {"slippage_bps": 1, "slippage_bps": 2}}')  # a duplicate key is refused


def test_a_single_instrument_cannot_have_per_symbol_costs() -> None:
    from monte_neo.verify.market import market_for

    market = market_for(synthetic_ohlcv(200, seed=1))
    with pytest.raises(ValueError, match="need a universe"):
        apply_symbol_costs(market, ExecutionModel(), {"AAA": {"slippage_bps": 1}})
    assert apply_symbol_costs(market, ExecutionModel(), None).symbol_costs == ()


# ---- through the verifier --------------------------------------------------------------------


def test_verify_strategy_records_the_resolved_table_and_reproduces(tmp_path) -> None:
    df = _table()
    csv, cert = tmp_path / "u.csv", tmp_path / "c.json"
    df.to_csv(csv, index=False)
    strategy = tmp_path / "s.py"
    strategy.write_text(
        "def signal(df):\n"
        "    mom = df.groupby('symbol')['close'].pct_change(10)\n"
        "    return mom.groupby(df['timestamp']).rank(pct=True).sub(0.5).fillna(0.0)\n"
    )
    costs = {"default": {"commission_bps": 2, "slippage_bps": 2}, "CCC": {"slippage_bps": 40}}
    plain = verify_strategy(csv, strategy=strategy, model=model_from_costs(commission_bps=2, slippage_bps=2, n_bars=400))
    priced = verify_strategy(csv, strategy=strategy, model=model_from_costs(commission_bps=2, slippage_bps=2, n_bars=400), symbol_costs=costs)
    rows = priced["reproducibility"]["model"]["symbol_costs"]
    assert rows == [["AAA", 2.0, 2.0], ["BBB", 2.0, 2.0], ["CCC", 2.0, 40.0]]
    assert "symbol_costs" not in plain["reproducibility"]["model"]
    assert priced["metrics"]["total_return"] < plain["metrics"]["total_return"]
    assert priced["certificate_id"] != plain["certificate_id"]
    cert.write_text(json.dumps(priced))
    assert recheck_certificate(cert, csv, strategy=strategy)["reproduced"] is True  # the table is in the certificate


def test_costs_that_name_a_symbol_the_data_lacks_fail_before_any_backtest() -> None:
    with pytest.raises(ValueError, match="not in the data"):
        verify_strategy(_table(), signal_fn=_momentum, symbol_costs={"NOPE": {"slippage_bps": 5}})


def test_grid_search_uses_the_per_symbol_costs(tmp_path) -> None:
    df = _table(300)
    strategy = tmp_path / "g.py"
    strategy.write_text(
        "def signal(df, lookback=10):\n"
        "    mom = df.groupby('symbol')['close'].pct_change(lookback)\n"
        "    return mom.groupby(df['timestamp']).rank(pct=True).sub(0.5).fillna(0.0)\n"
    )
    grid = {"lookback": [5, 10, 20]}
    cheap = verify_grid(df, grid, strategy=str(strategy), symbol_costs={"default": {"commission_bps": 0, "slippage_bps": 0}})
    dear = verify_grid(df, grid, strategy=str(strategy), symbol_costs={"default": {"commission_bps": 30, "slippage_bps": 30}})
    assert len(cheap["reproducibility"]["model"]["symbol_costs"]) == 3
    assert dear["metrics"]["total_return"] < cheap["metrics"]["total_return"]


def test_the_cost_checks_and_the_report_use_the_average(tmp_path) -> None:
    from monte_neo.verify.report_html import render_html

    report = verify_strategy(_table(), signal_fn=_momentum, symbol_costs={"AAA": {"commission_bps": 0, "slippage_bps": 0}, "BBB": {"commission_bps": 10, "slippage_bps": 10}})
    econ = {c["id"]: c for c in report["checks"]}["costs_modeled"]
    assert econ["details"]["per_side_cost_bps"] == pytest.approx((0 + 0 + 10 + 10 + 5 + 5) / 3)  # CCC keeps the uniform 5 + 5
    page = render_html(report)
    assert "by symbol, 3 symbols: 0.00-10.00 bps commission + 0.00-10.00 bps slippage per side" in page


def test_cli_reads_costs_from_a_file_or_inline_json(tmp_path) -> None:
    from monte_neo.cli.verify_cmd import main

    df = _table(300)
    csv = tmp_path / "u.csv"
    df.to_csv(csv, index=False)
    strategy = tmp_path / "s.py"
    strategy.write_text(
        "def signal(df):\n"
        "    mom = df.groupby('symbol')['close'].pct_change(10)\n"
        "    return mom.groupby(df['timestamp']).rank(pct=True).sub(0.5).fillna(0.0)\n"
    )
    costs = tmp_path / "costs.json"
    costs.write_text('{"AAA": {"commission_bps": 1, "slippage_bps": 1}, "default": {"slippage_bps": 9}}')
    out_a, out_b = tmp_path / "a.json", tmp_path / "b.json"
    base = ["--ohlcv", str(csv), "--strategy", str(strategy), "--format", "json"]
    assert main([*base, "--costs-file", str(costs), "--out", str(out_a)]) in (0, 1, 2)
    assert main([*base, "--costs-file", costs.read_text(), "--out", str(out_b)]) in (0, 1, 2)
    a, b = json.loads(out_a.read_text()), json.loads(out_b.read_text())
    assert a["certificate_id"] == b["certificate_id"]
    assert a["reproducibility"]["model"]["symbol_costs"][0] == ["AAA", 1.0, 1.0]
    assert main([*base, "--costs-file", '{"NOPE": {"slippage_bps": 1}}']) == 3


def test_mcp_tool_accepts_costs(tmp_path) -> None:
    from monte_neo.mcp import tools

    csv = tmp_path / "u.csv"
    _table(300).to_csv(csv, index=False)
    strategy = tmp_path / "s.py"
    strategy.write_text(
        "def signal(df):\n"
        "    mom = df.groupby('symbol')['close'].pct_change(10)\n"
        "    return mom.groupby(df['timestamp']).rank(pct=True).sub(0.5).fillna(0.0)\n"
    )
    out = tools.verify_strategy(str(csv), strategy_path=str(strategy), symbol_costs={"AAA": {"slippage_bps": 50}}, compact=False)
    assert out["reproducibility"]["model"]["symbol_costs"][0][2] == 50.0
    with pytest.raises(ValueError, match="not in the data"):  # the server turns this into an error message for the agent
        tools.verify_strategy(str(csv), strategy_path=str(strategy), symbol_costs={"XXX": {"slippage_bps": 1}})


def test_the_pure_python_fallback_gives_the_same_numbers() -> None:
    code = (
        "import numpy as np\n"
        "from monte_neo.backtest import ExecutionModel, synthetic_ohlcv\n"
        "from monte_neo.backtest.weight_engine import run_weight_backtest\n"
        "fr = [synthetic_ohlcv(300, seed=70 + k) for k in range(3)]\n"
        "o, c = (np.column_stack([f[k].to_numpy() for f in fr]) for k in ('open', 'close'))\n"
        "w = np.round(np.sin(np.arange(300)[:, None] / 15.0 + np.arange(3)), 1) / 3\n"
        "m = ExecutionModel(side_mode='long_short', warmup_bars=10, symbol_costs=(('A', 1.0, 2.0), ('B', 10.0, 0.0), ('C', 0.0, 25.0)))\n"
        "print(repr(run_weight_backtest(o, c, w, model=m)['total_return']))\n"
    )
    import os

    slow = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=dict(os.environ, NUMBA_DISABLE_JIT="1"), check=True).stdout
    fast = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
    assert slow == fast and slow.strip()
