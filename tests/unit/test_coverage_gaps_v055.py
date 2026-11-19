"""Data contract, volume-capped execution, funding/borrow series and portfolio risk."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from monte_neo.verify.data_contract import validate_data_contract
from monte_neo.verify.execution import execution_row, simulate_execution
from monte_neo.verify.funding import funding_borrow_drag, funding_stress_row
from monte_neo.verify.portfolio_risk import cvar, portfolio_risk

# ---- data contract ----


def _frame() -> pd.DataFrame:
    t = pd.date_range("2024-01-01", periods=6, freq="D")
    return pd.DataFrame({"timestamp": t, "event": t - pd.Timedelta(days=2), "pub": t - pd.Timedelta(days=1), "sym": list("AABBAB")})


def _row(rows: list[dict], cid: str) -> dict:
    return next(r for r in rows if r["id"] == cid)


def test_publication_pass_warn_fail() -> None:
    f = _frame()
    ok = validate_data_contract(f, event_col="event", published_col="pub")
    assert _row(ok, "publication_dates")["status"] == "pass" and _row(ok, "publication_dates")["details"]["median_lag_seconds"] == 86400
    assert _row(validate_data_contract(f), "publication_dates")["status"] == "warn"
    late = f.assign(pub=f["timestamp"] + pd.Timedelta(days=1))  # used before it was published
    row = _row(validate_data_contract(late, published_col="pub"), "publication_dates")
    assert row["status"] == "fail" and row["details"]["used_before_published"] == 6
    early = f.assign(pub=f["event"] - pd.Timedelta(days=1))
    assert "before the event" in _row(validate_data_contract(early, event_col="event", published_col="pub"), "publication_dates")["summary"]
    gap = f.assign(pub=f["pub"].where(f.index != 2))
    row = _row(validate_data_contract(gap, published_col="pub"), "publication_dates")
    assert row["status"] == "warn" and row["details"]["missing_published"] == 1


def test_membership_rows() -> None:
    f = _frame()
    assert _row(validate_data_contract(f), "universe_membership")["status"] == "skip"
    assert _row(validate_data_contract(f, symbol_col="sym"), "universe_membership")["status"] == "warn"
    spans = pd.DataFrame({"symbol": ["A", "B"], "start": ["2023-01-01", "2023-01-01"], "end": [None, None]})
    assert _row(validate_data_contract(f, symbol_col="sym", membership=spans), "universe_membership")["status"] == "pass"
    left = pd.DataFrame({"symbol": ["A", "B"], "start": ["2023-01-01", "2024-01-04"], "end": ["2024-01-04", None]})
    row = _row(validate_data_contract(f, symbol_col="sym", membership=left), "universe_membership")
    assert row["status"] == "fail" and row["details"]["rows_outside_membership"] >= 2
    missing = pd.DataFrame({"symbol": ["A"], "start": ["2023-01-01"]})  # no "end" column, B unknown
    row = _row(validate_data_contract(f, symbol_col="sym", membership=missing), "universe_membership")
    assert row["status"] == "fail" and row["details"]["symbols_without_dates"] == 1


def test_contract_errors() -> None:
    with pytest.raises(ValueError, match="not found"):
        validate_data_contract(_frame(), published_col="nope")
    with pytest.raises(ValueError, match="membership needs"):
        validate_data_contract(_frame(), symbol_col="sym", membership=pd.DataFrame({"x": [1]}))


# ---- execution ----


def _market(n: int = 400, vol_scale: float = 1.0, seed: int = 0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0008, 0.01, n)))
    volume = np.full(n, 1_000_000.0 * vol_scale) / close  # traded value ~ 1e6 * scale per bar
    target = np.sign(np.sin(np.arange(n) / 25.0))
    return target, close, volume


def test_small_capital_trades_cleanly() -> None:
    t, c, v = _market()
    r = simulate_execution(t, c, v, capital=10_000, max_participation=0.1)
    assert r["mean_fill_ratio"] == pytest.approx(1.0) and r["mean_position_gap"] < 1e-9
    assert r["max_share_of_volume"] <= 0.1 + 1e-12
    row = execution_row(t, c, v, capital=10_000)
    assert row["status"] in ("pass", "skip")


def test_large_capital_is_volume_capped_and_lags() -> None:
    t, c, v = _market(vol_scale=0.01)
    r = simulate_execution(t, c, v, capital=5_000_000, max_participation=0.05)
    assert r["max_share_of_volume"] <= 0.05 + 1e-9 and r["mean_fill_ratio"] < 0.5 and r["mean_position_gap"] > 0.1
    assert np.all(np.abs(r["held"]) <= 1.0 + 1e-9)
    assert execution_row(t, c, v, capital=5_000_000, max_participation=0.05)["status"] in ("warn", "skip")


def test_execution_warns_on_profitable_strategy_that_cannot_trade() -> None:
    n = 400
    c = 100 * np.exp(np.cumsum(np.full(n, 0.002)))  # steady uptrend: any long profits
    v = np.full(n, 1_000.0)  # tiny volume
    t = np.ones(n)
    row = execution_row(t, c, v, capital=10_000_000, max_participation=0.01)
    assert row["status"] == "warn" and row["details"]["mean_fill_ratio"] < 0.1


def test_execution_validation_and_skip() -> None:
    t, c, v = _market()
    for bad in ({"capital": 0}, {"capital": 1, "max_participation": 0}, {"capital": 1, "fee_bps": -1}, {"capital": 1, "impact_coef": -1}):
        with pytest.raises(ValueError):
            simulate_execution(t, c, v, **bad)
    with pytest.raises(ValueError, match="same length"):
        simulate_execution(t[:-1], c, v, capital=1)
    assert execution_row(-np.ones(400), np.exp(np.linspace(0, 1, 400)), v, capital=1000)["status"] == "skip"
    flat = simulate_execution(np.zeros(50), c[:50], v[:50], capital=1000)
    assert flat["mean_fill_ratio"] == 1.0


# ---- funding / borrow ----


def test_funding_sign_convention() -> None:
    w = np.array([1.0, -1.0, 0.0, 1.0])
    f = np.array([10.0, 10.0, 10.0, -5.0])
    drag = funding_borrow_drag(w, f)
    assert drag == pytest.approx(np.array([10.0, -10.0, 0.0, -5.0]) / 1e4)  # long pays positive funding, short receives
    assert funding_borrow_drag(w, 0.0, 20.0) == pytest.approx(np.array([0.0, 20.0, 0.0, 0.0]) / 1e4)  # only shorts pay borrow
    assert funding_borrow_drag(np.array([2.0, -0.5]), 10.0, 0.0) == pytest.approx(np.array([20.0, -5.0]) / 1e4)  # weights scale it


def test_funding_series_validation() -> None:
    with pytest.raises(ValueError, match="one value per bar"):
        funding_borrow_drag(np.ones(3), np.ones(2))
    with pytest.raises(ValueError, match="non-finite"):
        funding_borrow_drag(np.ones(2), np.array([1.0, np.nan]))
    with pytest.raises(ValueError, match=">= 0"):
        funding_borrow_drag(np.ones(2), 0.0, -1.0)
    with pytest.raises(ValueError, match="same length"):
        funding_stress_row(np.zeros(3), np.ones(4))


def test_funding_stress_rows() -> None:
    n = 250
    r = np.full(n, 0.0004)
    w = np.ones(n)
    assert funding_stress_row(r, w, 1.0)["status"] == "pass"
    row = funding_stress_row(r, w, 6.0)  # 6 bps per bar against 4 bps earned
    assert row["status"] == "warn" and row["details"]["return_after"] < 0 < row["details"]["return_before"]
    assert funding_stress_row(-r, w, 1.0)["status"] == "skip"
    assert funding_stress_row(r, -w, funding_bps=np.full(n, 3.0), borrow_bps=np.full(n, 0.0))["status"] == "pass"  # short earns funding


# ---- portfolio risk ----


def test_cvar_values_and_boundary() -> None:
    x = np.arange(-9, 11, dtype=float)  # 20 values: -9..10
    assert cvar(x, 0.05) == -9.0  # worst 1 of 20
    assert cvar(x, 0.10) == -8.5
    assert cvar(np.array([0.5]), 0.05) == 0.5


def test_risk_of_independent_vs_clones() -> None:
    rng = np.random.default_rng(0)
    ind = rng.normal(0, 0.01, (4, 800))
    r = portfolio_risk(ind, list("abcd"))
    assert 3.5 < r["effective_bets"] <= 4.0 and not r["concentrated"] and abs(r["mean_correlation"]) < 0.1
    assert sum(r["risk_contribution"].values()) == pytest.approx(1.0)
    assert r["ensemble_cvar"] > min(r["strategy_cvar"].values())  # diversification lifts the tail
    clones = np.vstack([ind[0], ind[0] * 1.01, ind[0] * 0.99])
    c = portfolio_risk(clones, list("xyz"))
    assert c["effective_bets"] < 3.01 and c["mean_correlation"] > 0.99


def test_risk_concentration_and_weights() -> None:
    rng = np.random.default_rng(1)
    m = np.vstack([rng.normal(0, 0.05, 600), rng.normal(0, 0.005, 600), rng.normal(0, 0.005, 600)])
    r = portfolio_risk(m, ["big", "s1", "s2"])
    assert r["concentrated"] and r["top_risk"]["name"] == "big" and r["effective_bets"] < 1.5
    w = portfolio_risk(m, ["big", "s1", "s2"], weights=np.array([0.0, 1.0, 1.0]))
    assert w["risk_contribution"]["big"] == pytest.approx(0.0, abs=1e-9) and w["weights"][0] == 0.0


def test_risk_tail_correlation_exceeds_normal_for_joint_crashes() -> None:
    rng = np.random.default_rng(2)
    base = rng.normal(0, 0.01, (3, 1000))
    crash = rng.random(1000) < 0.03
    base[:, crash] -= 0.08  # everyone falls together
    r = portfolio_risk(base, list("abc"))
    assert r["tail_correlation"] > r["mean_correlation"] and r["tail_bars"] >= 100


def test_risk_validation_and_flat() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        portfolio_risk(np.zeros((1, 50)), ["a"])
    with pytest.raises(ValueError, match="weights"):
        portfolio_risk(np.zeros((2, 50)), ["a", "b"], weights=np.array([1.0]))
    with pytest.raises(ValueError, match="weights"):
        portfolio_risk(np.zeros((2, 50)), ["a", "b"], weights=np.array([1.0, -1.0]))
    flat = portfolio_risk(np.zeros((2, 50)), ["a", "b"])  # zero variance: no division by zero
    assert flat["effective_bets"] == pytest.approx(2.0)
    tiny = portfolio_risk(np.random.default_rng(3).normal(0, 1, (2, 20)), ["a", "b"])  # fewer than 3 tail bars -> uses full corr
    assert tiny["tail_bars"] == 2


# ---- verify_portfolio carries the risk block ----


def test_verify_portfolio_has_risk_and_flags_concentration(monkeypatch: pytest.MonkeyPatch) -> None:
    from monte_neo.backtest import synthetic_ohlcv
    from monte_neo.verify import portfolio as pf

    df = synthetic_ohlcv(1200, seed=4)
    strategies = [
        lambda d: (d["close"] > d["close"].rolling(15).mean()).astype(int),
        lambda d: (d["close"] > d["close"].rolling(40).mean()).astype(int),
    ]
    rep = pf.verify_portfolio(df, strategies, names=["fast", "slow"])
    assert {"ensemble_cvar", "risk_contribution", "effective_bets", "tail_correlation"} <= set(rep["risk"])
    assert "carries" not in rep["summary"] or rep["risk"]["concentrated"]
    forced = {**rep["risk"], "concentrated": True, "top_risk": {"name": "fast", "share": 0.9}}
    monkeypatch.setattr(pf, "portfolio_risk", lambda *a, **k: forced)
    assert "fast carries 90% of the risk" in pf.verify_portfolio(df, strategies, names=["fast", "slow"])["summary"]
