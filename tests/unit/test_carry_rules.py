"""Carry rules derived from the economics of carry: accuracy on the basis, effective accrual sample, future-funding probe, margin, basket."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from monte_neo.verify.carry import carry_future_probe, carry_table, decomposition_row, verify_carry
from monte_neo.verify.carry_market import (
    CarryMarket,
    effective_sample,
    entries,
    few_decisions_row,
    is_carry,
    margin_rows,
    sample_row,
)
from monte_neo.verify.market import market_for
from monte_neo.verify.verdict import verify_strategy

N = 4000
HEAD = "import numpy as np\ndef signal(df):\n"
HONEST = HEAD + "    f = df['funding_rate'].rolling(9).mean().shift(1).to_numpy()\n    return np.where(np.nan_to_num(f) > 0.0, 1.0, 0.0)\n"
PEEK_FUNDING = HEAD + "    f = df['funding_rate'].shift(-1).to_numpy()\n    return np.where(np.nan_to_num(f) > 0.0, 1.0, 0.0)\n"
PEEK_BASIS = HEAD + "    b = df['basis_pnl'].shift(-1).to_numpy()\n    return np.where(np.nan_to_num(b) > 0.0, 1.0, 0.0)\n"
STORED = HEAD + "    return np.tile(np.array([1.0] * 40 + [0.0] * 40), len(df) // 80 + 1)[: len(df)]\n"
ALWAYS = HEAD + "    return np.ones(len(df))\n"


def _raw(funding_mean: float = 3e-4, seed: int = 4, n: int = N, sym: str | None = None) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    spot = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.004, n)))
    perp = spot * (1.0 + rng.normal(0, 0.0005, n))
    regime = np.repeat(rng.choice([-1.0, 1.0], size=n // 100 + 1, p=[0.3, 0.7]), 100)[:n]
    df = pd.DataFrame({"timestamp": pd.date_range("2022-01-01", periods=n, freq="8h", tz="UTC"), "spot_close": spot, "perp_close": perp,
                       "funding_rate": funding_mean * regime + rng.normal(0, 3e-5, n)})
    if sym:
        df["symbol"] = sym
    return df


RAW = _raw()


def _margin(*a, **k):
    return margin_rows(*a, **k)[0]


def _strategy(tmp_path, name: str, body: str):
    f = tmp_path / f"{name}.py"
    f.write_text(body)
    return f


def _by_id(rep):
    return {c["id"]: c for c in rep["checks"]}


# ---------------------------------------------------------------- traps and an honest control
def test_honest_carry_is_not_rejected_and_the_generic_path_would_reject_it(tmp_path) -> None:
    strong = _raw(funding_mean=1.5e-3, seed=7)
    f = _strategy(tmp_path, "honest", HONEST)
    rep = verify_carry(strong, strategy=f, n_trials=1)
    ids = _by_id(rep)
    assert rep["verdict"] != "REJECT" and ids["implausible_accuracy"]["status"] == "pass"
    assert ids["implausible_accuracy"]["details"]["measured_on"].startswith("basis")
    generic = carry_table(strong)[["timestamp", "open", "high", "low", "close", "funding_rate"]]  # no carry columns: the generic rules
    from monte_neo.verify.ingest import load_signal_fn

    gen = _by_id(verify_strategy(generic, signal_fn=load_signal_fn(f)[0], source=HONEST, n_trials=1))
    assert gen["implausible_accuracy"]["status"] == "fail"  # structurally positive accrual looks like leakage to the generic rule


@pytest.mark.parametrize(("name", "code"), [("peek_funding", PEEK_FUNDING), ("peek_basis", PEEK_BASIS)])
def test_traps_are_rejected(tmp_path, name, code) -> None:
    rep = verify_carry(RAW, strategy=_strategy(tmp_path, name, code), n_trials=1)
    ids = _by_id(rep)
    assert rep["verdict"] == "REJECT" and ids["carry_future_probe"]["status"] == "fail" and ids["lookahead_truncation"]["status"] == "fail"


def test_peeking_at_the_next_basis_also_fails_the_accuracy_check(tmp_path) -> None:
    assert _by_id(verify_carry(RAW, strategy=_strategy(tmp_path, "pb", PEEK_BASIS)))["implausible_accuracy"]["status"] == "fail"


def test_future_probe_pass_skip_and_stored_answer(tmp_path) -> None:
    from monte_neo.verify.ingest import load_signal_fn

    honest = load_signal_fn(_strategy(tmp_path, "h", HONEST))[0]
    assert carry_future_probe(honest, RAW)["status"] == "pass"
    assert carry_future_probe(honest, RAW.head(100))["status"] == "skip"
    ids = _by_id(verify_carry(RAW, strategy=_strategy(tmp_path, "stored", STORED)))
    assert ids["data_independence"]["status"] in ("warn", "fail") and "ignores" in ids["data_independence"]["summary"]
    assert _by_id(verify_carry(RAW, strategy=_strategy(tmp_path, "h2", HONEST)))["data_independence"]["status"] in ("pass", "skip")
    assert _by_id(verify_carry(RAW, strategy=_strategy(tmp_path, "al", ALWAYS)))["data_independence"]["status"] == "skip"  # never changes position


# ---------------------------------------------------------------- effective sample
def test_effective_sample_for_white_noise_and_for_autocorrelated_accrual() -> None:
    rng = np.random.default_rng(0)
    white = effective_sample(rng.normal(0, 1, 3000))
    assert white["ratio"] > 0.6
    e = rng.normal(0, 1, 6000)
    ar = np.zeros(6000)
    for i in range(1, 6000):
        ar[i] = 0.9 * ar[i - 1] + e[i]
    slow = effective_sample(ar)
    assert slow["n_eff"] < 0.25 * slow["n"] and slow["n_eff"] >= 1.0  # theory: (1-0.9)/(1+0.9) = 0.053; never more than a quarter here
    assert effective_sample(np.array([1.0, 2.0]))["n_eff"] == 2.0 and effective_sample(np.ones(50))["ratio"] == 1.0


def test_sample_row_counts_accrual_periods_not_trades() -> None:
    rng = np.random.default_rng(1)
    r = rng.normal(0.0005, 0.001, 500)
    held = np.ones(500, dtype=bool)
    ok = sample_row(r, held, n_closed=3, min_effective=30)
    assert ok["status"] == "pass" and ok["details"]["n_closed_trades"] == 3 and "accrual" in ok["summary"]
    assert sample_row(r, np.zeros(500, dtype=bool), 0, 30)["status"] == "fail"  # never held
    few = held.copy()
    few[20:] = False
    assert sample_row(r, few, 1, 5)["status"] == "fail"  # fewer than 30 held bars, whatever the threshold
    assert sample_row(r, held, 3, 10_000)["status"] == "fail"


def test_few_decisions_is_a_separate_warning_at_the_boundary() -> None:
    assert few_decisions_row(9, 5.0)["status"] == "warn" and few_decisions_row(10, 5.0)["status"] == "pass"
    assert few_decisions_row(0, 0.0)["details"]["per_year"] == 0.0
    w = np.zeros((10, 2))
    w[2:5, 0] = 1
    w[7:, 0] = 1
    w[0, 1] = 1
    assert entries(w) == 3 and entries(np.array([0.0, 1.0, 1.0, 0.0, 1.0])) == 2


def test_honest_carry_has_the_accrual_sample_and_the_decision_warning(tmp_path) -> None:
    ids = _by_id(verify_carry(RAW, strategy=_strategy(tmp_path, "h", HONEST)))
    assert ids["sample_size"]["details"]["basis"].startswith("effective independent accrual") and ids["sample_size"]["status"] == "pass"
    assert ids["few_decisions"]["status"] in ("warn", "pass")


# ---------------------------------------------------------------- benchmark is the underlying
def test_beta_reference_is_the_spot_and_not_the_pair() -> None:
    t = carry_table(RAW)
    m = market_for(t)
    assert isinstance(m, CarryMarket) and is_carry(t)
    ref = m.reference_returns(60)
    assert ref.size == len(t) - 61 and np.allclose(ref, t["spot_close"].pct_change().to_numpy()[61:])
    assert m.reference_returns(len(t) - 1).size == 0
    assert np.array_equal(m.market_close(), t["spot_close"].to_numpy())


def test_data_hash_covers_funding(tmp_path) -> None:
    f = _strategy(tmp_path, "al", ALWAYS)
    a = verify_carry(RAW, strategy=f)["certificate_id"]
    b = verify_carry(RAW.assign(funding_rate=RAW["funding_rate"] * 0.5), strategy=f)["certificate_id"]
    assert a != b


# ---------------------------------------------------------------- margin, capital cost, capacity
def test_margin_row_states_and_input_errors() -> None:
    perp = np.concatenate([np.full(10, 100.0), np.linspace(100, 130, 20), np.full(10, 100.0)])
    w = np.ones(40)
    assert _margin(w, perp, 1.0, perp_high=perp)["status"] == "pass"  # 1x: the buffer is 99.5%, a +30% rise is far from it
    assert _margin(w, perp, 1.0)["status"] == "warn"                  # no bar highs given: closes only, said so
    assert _margin(w, perp, 2.0)["status"] == "warn"           # 49.5% buffer, 30% is above 60% of it
    r = _margin(w, perp, 4.0)                                    # 24.5% buffer: liquidated
    assert r["status"] == "fail" and r["details"]["topup_needed_share_of_perp_notional"] == pytest.approx(0.30 - 0.245, abs=1e-6)
    assert _margin(np.zeros(40), perp, 4.0)["status"] == "skip"  # never held
    two = _margin(np.vstack([w, np.zeros(40)]).T, np.vstack([perp, perp]).T, 3.0)  # a basket: columns are coins
    assert two["details"]["worst_rise_while_held"] == pytest.approx(0.30)
    with pytest.raises(ValueError, match="leverage"):
        _margin(w, perp, 0.5)
    with pytest.raises(ValueError, match="maintenance"):
        _margin(w, perp, 2.0, maintenance=1.0)
    nan = perp.copy()
    nan[12] = np.nan
    assert _margin(w, nan, 4.0)["status"] == "fail"  # a gap in the prices does not hide the rise


def test_capital_cost_capacity_and_margin_in_the_certificate(tmp_path) -> None:
    f = _strategy(tmp_path, "al", ALWAYS)
    free = verify_carry(RAW, strategy=f, capital_cost_apr=0.0)
    dear = verify_carry(RAW, strategy=f, capital_cost_apr=0.20)
    assert dear["metrics"]["total_return"] < free["metrics"]["total_return"] and dear["carry"]["capital_cost_apr"] == 0.20
    with pytest.raises(ValueError, match="non-negative"):
        verify_carry(RAW, strategy=f, capital_cost_apr=-0.1)
    assert "capacity" not in _by_id(free)
    assert any(c["id"] == "capacity" for c in verify_carry(RAW.assign(volume=5e6), strategy=f)["checks"])
    assert _by_id(verify_carry(RAW, strategy=f, perp_leverage=50.0))["carry_margin"]["status"] == "fail"


def _basket(n: int = 1500) -> pd.DataFrame:
    return pd.concat([_raw(seed=s, n=n, sym=c) for s, c in ((11, "AAA"), (12, "BBB"), (13, "CCC"))], ignore_index=True)


BASKET_HONEST = HEAD + ("    f = df.groupby('symbol')['funding_rate'].transform(lambda x: x.rolling(9).mean().shift(1))\n"
                        "    return np.where(f.fillna(0).to_numpy() > 0.0, 1.0, 0.0)\n")
BASKET_PEEK = HEAD + "    f = df.groupby('symbol')['funding_rate'].shift(-1)\n    return np.where(f.fillna(0).to_numpy() > 0.0, 1.0, 0.0)\n"


def test_basket_runs_as_a_universe_with_carry_rules(tmp_path) -> None:
    t = carry_table(_basket())
    assert set(t["symbol"]) == {"AAA", "BBB", "CCC"} and is_carry(t)
    rep = verify_carry(_basket(), strategy=_strategy(tmp_path, "bh", BASKET_HONEST), n_trials=1)
    ids = _by_id(rep)
    assert rep["carry"]["basket"] is True and ids["sample_size"]["details"]["basis"].startswith("effective")
    assert ids["implausible_accuracy"]["details"]["measured_on"].startswith("basis")
    assert ids["carry_decomposition"]["details"]["funding_pnl"] > 0 and "carry_margin" in ids
    assert rep["verdict"] != "REJECT", [c["id"] for c in rep["checks"] if c["status"] == "fail"]
    peek = verify_carry(_basket(), strategy=_strategy(tmp_path, "bp", BASKET_PEEK), n_trials=1)
    assert peek["verdict"] == "REJECT" and _by_id(peek)["carry_future_probe"]["status"] == "fail"


def test_basket_helpers_reference_and_data_hash() -> None:
    m = market_for(carry_table(_basket()))
    assert m.reference_returns(60).size == m.n_bars - 61 and m.market_close().size == m.n_bars
    assert m.reference_returns(m.n_bars - 1).size == 0
    assert m.held(np.ones((m.n_bars, 3)), 60, 100).all() and not m.held(np.zeros((m.n_bars, 3)), 60, 100).any()
    f, b, p = m.parts()
    assert f.shape == b.shape == p.shape == (m.n_bars, 3)
    flat = market_for(carry_table(_basket()).assign(funding_rate=0.0))
    assert flat.data_bytes() != m.data_bytes()


def test_decomposition_accepts_a_weight_matrix_for_a_basket() -> None:
    t = carry_table(_basket())
    m = market_for(t)
    w = np.zeros((m.n_bars, 3))
    w[:, 0] = 1.0
    row = decomposition_row(t, w)
    assert row["details"]["held_bars"] == m.n_bars - 1 and row["status"] in ("pass", "warn")


def test_funding_in_bps_and_a_strategy_that_fails_on_foreign_data(tmp_path) -> None:
    bps = RAW.assign(funding_bps=RAW["funding_rate"] * 1e4).drop(columns="funding_rate")
    a = verify_carry(bps, strategy=_strategy(tmp_path, "h", HONEST))
    assert _by_id(a)["carry_future_probe"]["status"] == "pass"
    first = RAW["funding_rate"].iloc[0]

    def fussy(df):
        if df["funding_rate"].iloc[0] != first:
            raise RuntimeError("different data")
        f = df["funding_rate"].rolling(9).mean().shift(1).to_numpy()
        return np.where(np.nan_to_num(f) > 0.0, 1.0, 0.0)

    ind = _by_id(verify_carry(RAW, signal_fn=fussy))["data_independence"]
    assert ind["status"] == "skip" and "failed on the foreign table" in ind["summary"]
