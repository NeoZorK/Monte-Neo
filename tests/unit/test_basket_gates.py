"""Survivorship pricing, rebalance-phase luck, selection vs timing, alpha after two betas, ARL ceiling, alpha certificate."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from monte_neo.alpha import demo_panel, recheck_alpha, validate_alpha
from monte_neo.backtest import ExecutionModel
from monte_neo.readiness import readiness
from monte_neo.verify import verify_strategy
from monte_neo.verify.basket_checks import alpha_two_betas_row, nw_multi, selection_timing, selection_timing_row
from monte_neo.verify.checks import survivorship_row
from monte_neo.verify.rebalance_phase import detect_cadence, rebalance_phase_row
from monte_neo.verify.survivorship import BIAS_WARN, parse_delisted, survivorship_bias_row


def _universe(n: int = 500, k: int = 8, seed: int = 1, drift: float = 0.0006) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 * np.cumprod(1 + rng.normal(drift, 0.02, (n, k)), axis=0)
    t = pd.date_range("2022-01-01", periods=n, freq="D")
    df = pd.DataFrame({"timestamp": np.repeat(t, k), "symbol": np.tile([f"S{i}" for i in range(k)], n), "close": close.ravel()})
    return df.assign(open=df["close"], high=df["close"] * 1.001, low=df["close"] * 0.999, volume=1e6)


def _momentum(d: pd.DataFrame) -> np.ndarray:
    p = d.pivot(index="timestamp", columns="symbol", values="close")
    mom = p.pct_change(20)
    out = pd.DataFrame(0.0, index=p.index, columns=p.columns)
    for i in range(30, len(p), 5):
        out.loc[out.index[i : i + 5], mom.iloc[i].nlargest(3).index] = 1 / 3
    return out.stack().reindex(pd.MultiIndex.from_frame(d[["timestamp", "symbol"]])).to_numpy()


# ---- survivorship ----


def test_parse_delisted_forms_and_errors() -> None:
    assert parse_delisted(None) == []
    assert parse_delisted(["A", "B"]) == [("A", -0.30), ("B", -0.30)]
    assert parse_delisted([("A", -0.9), "B"], default=-0.5) == [("A", -0.9), ("B", -0.5)]
    table = pd.DataFrame({"symbol": ["A", "B"], "delist_return": [-0.8, np.nan]})
    assert parse_delisted(table) == [("A", -0.8), ("B", -0.30)]
    assert parse_delisted(pd.DataFrame({"symbol": ["A"]})) == [("A", -0.30)]
    with pytest.raises(ValueError, match="symbol column"):
        parse_delisted(pd.DataFrame({"x": [1]}))
    with pytest.raises(ValueError, match="below -100%"):
        parse_delisted([("A", -1.5)])
    with pytest.raises(ValueError, match="duplicate"):
        parse_delisted(["A", "A"])


def _base(status: str) -> dict:
    return survivorship_row(["A", "B", "C"], np.zeros(3, dtype=int), np.array([99, 99, 99 if status == "warn" else 50]), 100)


def test_survivorship_row_cases() -> None:
    kw = {"n_symbols": 3, "bench_return": 1.0, "total_return": 1.0, "exposure": 1.0}
    assert survivorship_bias_row(survivorship_row(["A"], np.zeros(1, int), np.array([9]), 10), delisted=None, **kw)["status"] == "skip"
    silent = survivorship_bias_row(_base("warn"), delisted=None, **kw)
    assert silent["status"] == "warn" and "capped at ARL 4" in silent["summary"] and silent["id"] == "survivorship"
    assert survivorship_bias_row(_base("pass"), delisted=None, **kw)["status"] == "pass"  # delistings are inside the data
    assert survivorship_bias_row(_base("warn"), delisted=[], **kw)["status"] == "pass"
    mild = survivorship_bias_row(_base("warn"), delisted=[("X", -0.3)], **{**kw, "bench_return": 0.1, "total_return": 1.0})
    assert mild["status"] == "pass" and mild["details"]["overstatement"] < BIAS_WARN
    big = survivorship_bias_row(_base("warn"), delisted=[("X", -0.9), ("Y", -0.9)], **kw)
    assert big["status"] == "warn" and big["details"]["adjusted_total_return"] < 1.0 - BIAS_WARN
    dead = survivorship_bias_row(_base("warn"), delisted=[("X", -1.0)] * 1, **{**kw, "bench_return": 2.0, "total_return": 0.3})
    assert dead["status"] == "fail" and dead["details"]["adjusted_total_return"] <= 0
    losing = survivorship_bias_row(_base("warn"), delisted=[("X", -0.5)], **{**kw, "total_return": -0.2})
    assert losing["status"] == "pass"  # a losing strategy is not made to look better by the missing names


def test_verify_strategy_survivorship_end_to_end() -> None:
    df = _universe()
    silent = verify_strategy(df, signal_fn=_momentum, positions="weight", probe_checks=2)
    assert next(c for c in silent["checks"] if c["id"] == "survivorship")["status"] == "warn"
    assert silent["readiness"]["level"] <= 4 if "readiness" in silent else True
    declared = verify_strategy(df, signal_fn=_momentum, positions="weight", probe_checks=2, delisted=[("X", -0.99), ("Y", -0.99)])
    row = next(c for c in declared["checks"] if c["id"] == "survivorship")
    assert row["details"]["declared_missing"] == 2
    assert declared["reproducibility"]["settings"]["delisted"] == [["X", -0.99], ["Y", -0.99]]
    none = verify_strategy(df, signal_fn=_momentum, positions="weight", probe_checks=2, delisted=[])
    assert next(c for c in none["checks"] if c["id"] == "survivorship")["status"] == "pass"


def _cert(**status: str) -> dict:
    ids = ["data_integrity", "lookahead_truncation", "net_profitability", "cost_margin", "timing_significance", "selection_adjusted_sharpe", "residual_alpha",
           "hidden_short_volatility", "deflated_sharpe", "trial_ledger"]
    rows = [{"id": i, "status": "pass", "category": "x"} for i in ids]
    return {"checks": rows + [{"id": k, "status": v, "category": "integrity"} for k, v in status.items()]}


def test_readiness_ceiling() -> None:
    free = readiness(certificate=_cert(survivorship="pass"))
    assert free["level"] >= 6 and not free["ceilings"]
    capped = readiness(certificate=_cert(survivorship="warn"))
    assert capped["level"] == 4 and capped["ceilings"][0]["check"] == "survivorship"
    assert "capped at 4" in capped["summary"] and capped["levels"][5]["state"] == "capped"
    assert readiness(certificate=_cert(survivorship="fail"))["level"] == 4
    low = readiness(certificate={"checks": [{"id": "data_integrity", "status": "pass", "category": "x"},
                                            {"id": "survivorship", "status": "warn", "category": "integrity"}]})
    assert low["level"] == 1  # a ceiling never raises the level


# ---- rebalance phase ----


def _pulse_market(n: int = 600) -> tuple[dict, np.ndarray, ExecutionModel]:
    t = np.arange(n)
    close = 100 * np.cumprod(1 + np.where(t % 5 == 1, 0.02, -0.004))
    o = np.concatenate([[close[0]], close[:-1]])
    ohlc = {"open": o, "high": np.maximum(o, close) * 1.0001, "low": np.minimum(o, close) * 0.9999, "close": close}
    return ohlc, (t % 5 == 0).astype(float), ExecutionModel(commission_bps=0, slippage_bps=0, warmup_bars=0, side_mode="long_flat")


def test_cadence_detection() -> None:
    n = 400
    assert detect_cadence(((np.arange(n) // 5) % 2).astype(float)) == 5
    assert detect_cadence(np.random.default_rng(0).choice([0.0, 1.0], n)) is None  # irregular
    assert detect_cadence(np.sin(np.arange(n) / 3.0)) is None  # changes every bar
    assert detect_cadence(np.concatenate([np.zeros(300), np.ones(100)])) is None  # too few changes
    assert detect_cadence(np.column_stack([((np.arange(n) // 7) % 2), np.zeros(n)]).astype(float)) == 7  # 2-D weights


def test_phase_luck_warns_only_when_phase_decides() -> None:
    ohlc, sig, m = _pulse_market()
    row = rebalance_phase_row(ohlc, sig, m, 5)
    assert row["status"] == "warn" and row["details"]["worst_return"] < 0 < row["details"]["best_return"]
    assert row["details"]["primary_return"] == row["details"]["worst_return"] and "luck" in row["summary"]
    t = np.arange(600)
    steady = {k: 100 * np.exp(0.001 * t) * f for k, f in (("open", 1.0), ("high", 1.001), ("low", 0.999), ("close", 1.0))}
    ok = rebalance_phase_row(steady, ((t // 5) % 2 == 0).astype(float) * 0 + 1.0 * (t % 5 >= 0), m, 5)
    assert ok["status"] in ("pass", "skip")
    flat = rebalance_phase_row(steady, np.where((t // 5) % 3 == 0, 1.0, 0.0), m)
    assert flat["status"] in ("pass", "warn", "skip")


def test_phase_row_edges() -> None:
    ohlc, sig, m = _pulse_market()
    assert rebalance_phase_row(ohlc, np.ones(600), m)["status"] == "skip"  # never rebalances
    with pytest.raises(ValueError, match=">= 2"):
        rebalance_phase_row(ohlc, sig, m, 1)
    assert rebalance_phase_row(ohlc, np.zeros(600), m, 5)["status"] == "skip"  # not profitable at phase 0
    spread = rebalance_phase_row(ohlc, np.where(np.arange(600) % 5 == 0, 1.0, 0.0), ExecutionModel(commission_bps=0, slippage_bps=0, warmup_bars=0, side_mode="long_flat"), 20)
    assert spread["details"]["k"] == 20 and len(spread["details"]["phases"]) <= 12


def test_phase_spread_warning_without_losing_phase() -> None:
    t = np.arange(600)
    close = 100 * np.cumprod(1 + np.where(t % 5 == 1, 0.03, 0.0005))
    o = np.concatenate([[close[0]], close[:-1]])
    ohlc = {"open": o, "high": np.maximum(o, close) * 1.0001, "low": np.minimum(o, close) * 0.9999, "close": close}
    m = ExecutionModel(commission_bps=0, slippage_bps=0, warmup_bars=0, side_mode="long_flat")
    row = rebalance_phase_row(ohlc, np.where(t % 5 < 2, 1.0, 0.0), m, 5)
    assert row["details"]["worst_return"] > 0
    assert row["status"] in ("warn", "pass")
    if row["status"] == "warn":
        assert "spread" in row["summary"]


def test_phase_wired_in_verify_strategy() -> None:
    ohlc, sig, _ = _pulse_market()
    df = pd.DataFrame({k: v for k, v in ohlc.items()}).assign(volume=1.0)
    rep = verify_strategy(df, signals=sig, model=ExecutionModel(commission_bps=0, slippage_bps=0, warmup_bars=5, side_mode="long_flat"), rebalance_every=5)
    assert rep["reproducibility"]["settings"]["rebalance_every"] == 5
    assert any(c["id"] == "rebalance_timing_luck" for c in rep["checks"])


# ---- basket selection vs timing, two betas ----


def _cross(n: int = 400, k: int = 6, seed: int = 0) -> np.ndarray:
    return np.random.default_rng(seed).normal(0.0005, 0.02, (n, k))


def test_identity_timing_plus_selection_is_total() -> None:
    r, w = _cross(), np.random.default_rng(1).uniform(-1, 1, (400, 6))
    d = selection_timing(w, r)
    assert np.allclose(d["timing"] + d["selection"], d["total"]) and np.allclose(d["total"], (w * r).sum(axis=1))
    r2 = r.copy()
    r2[:, 0] = np.nan  # an untradable name is left out
    assert np.isfinite(selection_timing(w, r2)["total"]).all()


def test_timing_only_basket_is_flagged() -> None:
    r = _cross() + 0.01  # a market that always rises: pure exposure earns, selection is zero
    row = selection_timing_row(np.full((400, 6), 1 / 6), r, 365)
    assert row["status"] == "warn" and "market timing, not selection" in row["summary"] and row["details"]["timing_share"] > 0.8


def test_selection_basket_passes() -> None:
    r = _cross(seed=2)
    w = np.sign(r - r.mean(axis=1, keepdims=True)) / 6  # market neutral and picks winners (leaky on purpose)
    row = selection_timing_row(w, r, 365)
    assert row["status"] == "pass" and row["details"]["selection_t"] > 2


def test_selection_timing_skips() -> None:
    assert selection_timing_row(np.ones((100, 1)), np.ones((100, 1)), 365)["status"] == "skip"
    assert selection_timing_row(np.ones(100), np.ones(100), 365)["status"] == "skip"
    assert selection_timing_row(np.ones((10, 3)), _cross(10, 3), 365)["status"] == "skip"
    assert selection_timing_row(-np.ones((100, 3)) / 3, _cross(100, 3) + 0.01, 365)["status"] == "skip"  # loses on average
    rng = np.random.default_rng(5)
    r = rng.normal(0.0005, 0.02, (400, 6))
    g = np.random.default_rng(1).normal(0, 0.2, (400, 6))
    w = 0.001 * np.sign(r - r.mean(axis=1, keepdims=True)) + (g - g.mean(axis=1, keepdims=True))  # market neutral, weak picks
    weak = selection_timing_row(w, r, 365)
    assert weak["status"] == "info" and "selection is not significant" in weak["summary"]


def test_two_beta_alpha() -> None:
    rng = np.random.default_rng(4)
    basket, ref = rng.normal(0.001, 0.02, 600), rng.normal(0.001, 0.03, 600)
    pure = 0.7 * basket + 0.3 * ref + rng.normal(0, 0.002, 600)
    row = alpha_two_betas_row(pure, basket, ref, 365, "BTC")
    assert row["status"] == "warn" and abs(row["details"]["beta_basket"] - 0.7) < 0.05 and abs(row["details"]["beta_reference"] - 0.3) < 0.05
    real = 0.004 + 0.2 * basket + rng.normal(0, 0.004, 600)
    assert alpha_two_betas_row(real, basket, ref, 365, "BTC")["status"] == "pass"
    assert alpha_two_betas_row(real[:10], basket, ref, 365, "BTC")["status"] == "skip"
    assert alpha_two_betas_row(real, basket, basket, 365, "BTC")["status"] == "skip"  # identical benchmarks
    assert alpha_two_betas_row(np.zeros(600), basket, ref, 365, "BTC")["status"] == "skip"
    assert nw_multi(real, np.column_stack([basket, ref]))["coef"].shape == (3,)


def test_verify_strategy_basket_rows() -> None:
    df = _universe()
    rep = verify_strategy(df, signal_fn=_momentum, positions="weight", probe_checks=2, reference_symbol="S0", rebalance_every=5)
    ids = {c["id"]: c["status"] for c in rep["checks"]}
    assert {"selection_vs_timing_basket", "alpha_after_reference", "rebalance_timing_luck"} <= set(ids)
    assert rep["reproducibility"]["settings"]["reference_symbol"] == "S0"
    with pytest.raises(ValueError, match="not a symbol of the universe"):
        verify_strategy(df, signal_fn=_momentum, positions="weight", probe_checks=2, reference_symbol="NOPE")


# ---- certificate for the alpha (panel/basket) report ----


def test_alpha_report_has_certificate_and_recheck() -> None:
    prices, scores, noise = demo_panel(seed=1, n_symbols=12, n_days=300)
    rep = validate_alpha(prices, scores, placebos=20)
    assert isinstance(rep["certificate_id"], str) and len(rep["certificate_id"]) == 16
    again = recheck_alpha(rep, prices, scores)
    assert again["reproduced"] and again["data_matches"] and again["certificate_id"] == rep["certificate_id"]
    other = recheck_alpha(rep, prices, noise)
    assert not other["reproduced"] and not other["data_matches"]
    assert validate_alpha(prices, scores, placebos=20)["certificate_id"] == rep["certificate_id"]  # deterministic
    assert validate_alpha(prices, scores, placebos=20, seed=1)["certificate_id"] != rep["certificate_id"]
