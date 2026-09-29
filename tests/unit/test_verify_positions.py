"""Fractional positions (weights) through the verifier, CLI and MCP tools."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.cli.verify_cmd import main as cli_main
from monte_neo.mcp import tools
from monte_neo.verify import (
    delay_signals,
    normalize_signals,
    recheck_certificate,
    resolve_positions,
    to_positions,
    verify_grid,
    verify_strategy,
)


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    return synthetic_ohlcv(1500, seed=21)


def _statuses(report: dict) -> dict[str, str]:
    return {c["id"]: c["status"] for c in report["checks"]}


def _trend_weight(d: pd.DataFrame) -> np.ndarray:
    # Honest: size by the distance of the close from its trailing mean, capped at +-1.
    c = d["close"]
    z = (c - c.rolling(50).mean()) / c.rolling(50).std()
    return np.clip(z.fillna(0.0).to_numpy() / 3.0, -1.0, 1.0)


def _leaky_weight(d: pd.DataFrame) -> np.ndarray:
    nxt = np.append(d["close"].to_numpy()[1:], np.nan)
    return np.tanh(50.0 * (nxt / d["close"].to_numpy() - 1.0))


def test_resolve_positions() -> None:
    assert resolve_positions(np.array([1.0, 0.0, -1.0])) == "sign"
    assert resolve_positions(np.array([0.5, -0.25, np.nan])) == "weight"
    assert resolve_positions(np.array([2.3, -0.5])) == "sign"  # a score, not a weight
    assert resolve_positions(np.array([np.nan])) == "sign"
    assert resolve_positions(np.array([0.5]), "sign") == "sign"
    with pytest.raises(ValueError, match="positions must be one of"):
        resolve_positions(np.array([1.0]), "size")
    with pytest.raises(ValueError, match="'sign' or 'weight'"):
        to_positions(np.array([1.0]), "auto")
    w = normalize_signals([0.5, 2.0, -np.inf, np.nan], positions="weight")
    assert w.dtype == np.float64 and np.allclose(w, [0.5, 1.0, -1.0, 0.0])
    assert normalize_signals([0.5, -3.0]).tolist() == [1, -1]  # default stays sign


def test_weights_and_signs_agree_on_unit_signals(df) -> None:
    sig = np.sign(df["close"].diff().rolling(10).sum().fillna(0)).to_numpy()
    as_sign = verify_strategy(df, signals=sig, positions="sign")
    as_weight = verify_strategy(df, signals=sig, positions="weight")
    for key in ("total_return", "max_drawdown", "n_closed_trades", "sharpe_annualized"):
        assert as_sign["metrics"][key] == as_weight["metrics"][key], key
    assert as_weight["metrics"]["positions"] == "weight" and as_sign["metrics"]["positions"] == "sign"


def test_honest_weight_strategy(df) -> None:
    report = verify_strategy(df, signal_fn=_trend_weight, n_trials=1)
    statuses = _statuses(report)
    assert report["metrics"]["positions"] == "weight"
    assert 0.0 < report["metrics"]["mean_abs_position"] < 1.0
    assert report["reproducibility"]["settings"]["positions"] == "weight"
    for check_id in ("lookahead_truncation", "lookahead_perturbation", "determinism"):
        assert statuses[check_id] == "pass", check_id


def test_leaky_weight_strategy_is_rejected(df) -> None:
    report = verify_strategy(df, signal_fn=_leaky_weight)
    assert report["metrics"]["positions"] == "weight"
    assert report["verdict"] == "REJECT" and _statuses(report)["lookahead_truncation"] == "fail"


def test_half_size_halves_the_exposure(df) -> None:
    sig = np.sign(df["close"].diff().rolling(10).sum().fillna(0)).to_numpy()
    full = verify_strategy(df, signals=sig, positions="weight")
    half = verify_strategy(df, signals=0.5 * sig)
    assert half["metrics"]["positions"] == "weight"
    assert half["metrics"]["mean_abs_position"] == pytest.approx(0.5 * full["metrics"]["mean_abs_position"])
    assert abs(half["metrics"]["max_drawdown"]) < abs(full["metrics"]["max_drawdown"])


def test_delay_keeps_weights() -> None:
    out = delay_signals(np.array([0.5, -0.25, 1.0]), 1)
    assert out.dtype == np.float64 and out.tolist() == [0.0, 0.5, -0.25]
    grid = delay_signals(np.ones((3, 2)), 1)
    assert grid[:, 0].tolist() == [0.0, 1.0, 1.0]


def test_recheck_weights(df, tmp_path: Path) -> None:
    weights = _trend_weight(df)
    path = tmp_path / "weights.npy"
    np.save(path, weights)
    report = verify_strategy(df, signals=str(path))
    assert recheck_certificate(report, df, signals=str(path))["reproduced"]


def test_grid_reads_all_combos_with_one_mode(df) -> None:
    def sized(d: pd.DataFrame, size: float = 1.0) -> np.ndarray:
        return size * np.sign(d["close"].diff().rolling(20).sum().fillna(0)).to_numpy()

    report = verify_grid(df, {"size": [0.5, 1.0]}, signal_fn=sized)
    assert report["reproducibility"]["settings"]["positions"] == "weight"
    with pytest.raises(ValueError, match="signal length"):
        verify_grid(df, {"size": [1.0]}, signal_fn=lambda d, size=1.0: np.ones(3))


def test_cli_and_mcp_positions(df, tmp_path: Path) -> None:
    data = tmp_path / "prices.csv"
    df.to_csv(data, index=False)
    weights = tmp_path / "w.npy"
    np.save(weights, _trend_weight(df))
    out = tmp_path / "cert.json"
    code = cli_main(["--ohlcv", str(data), "--signals", str(weights), "--positions", "weight", "--out", str(out), "--format", "json"])
    assert code in (0, 1, 2)
    assert json.loads(out.read_text())["metrics"]["positions"] == "weight"
    mcp = tools.verify_strategy(str(data), signals_path=str(weights), positions="sign")
    assert mcp["metrics"]["positions"] == "sign"
    stress = tools.cost_stress(str(data), signals_path=str(weights))
    assert "breakeven" in stress and "delay" in stress
    short = tmp_path / "short.npy"
    np.save(short, np.ones(10))
    assert "signal length" in tools.cost_stress(str(data), signals_path=str(short))["error"]


def test_invalid_positions_mode(df) -> None:
    with pytest.raises(ValueError, match="positions must be one of"):
        verify_strategy(df, signals=np.ones(len(df)), positions="size")


def test_timing_and_recheck_edges(df) -> None:
    from monte_neo.backtest import ExecutionModel
    from monte_neo.verify.timing import timing_significance

    ohlc = {k: df[k].to_numpy() for k in ("open", "high", "low", "close")}
    res = timing_significance(ohlc, 0.5 * np.ones(len(df)), ExecutionModel(side_mode="long_short", warmup_bars=10))
    assert res["status"] in ("pass", "warn") and res["n_shifts"] > 0
    with pytest.raises(ValueError, match="signal length"):
        verify_strategy(df, signals=np.ones(10))
    broken = df.copy()
    broken.loc[5, "close"] = np.nan
    stopped = verify_strategy(broken, signals=np.ones(len(df)))
    assert stopped["reproducibility"]["settings"]["positions"] == "auto"  # the signal was never read
    assert recheck_certificate(stopped, broken, signals=np.ones(len(df)))["reproduced"]
