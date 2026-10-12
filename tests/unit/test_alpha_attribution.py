"""Family B: factor construction and attribution checks."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from monte_neo.alpha.attribution import NEXT_ACTIONS, run_attribution
from monte_neo.alpha.factors import build_factors, load_factors


def _universe(t: int = 600, n: int = 40, seed: int = 0) -> tuple[np.ndarray, np.ndarray, pd.DatetimeIndex]:
    rng = np.random.default_rng(seed)
    ret = rng.normal(0.0003, 0.01, (t, n)) + rng.normal(0, 0.005, (t, 1))
    close = 100 * np.cumprod(1 + ret, axis=0)
    vol = rng.uniform(1e3, 1e5, (t, n))
    return close, vol, pd.bdate_range("2020-01-01", periods=t)


def _by_id(rows: list[dict]) -> dict[str, dict]:
    return {r["id"]: r for r in rows}


def _fake_factors(t: int = 1000, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2018-01-01", periods=t)
    return pd.DataFrame(
        {
            "market": rng.normal(0.0004, 0.01, t),
            "momentum": rng.normal(0.0003, 0.006, t),
            "low_vol": rng.normal(0.0002, 0.005, t),
            "size": rng.normal(0.0001, 0.005, t),
        },
        index=idx,
    )


def test_factor_columns_and_nan_head() -> None:
    close, vol, dates = _universe()
    f = build_factors(close, vol, dates)
    assert list(f.columns) == ["market", "size", "momentum", "reversal", "low_vol"]
    assert f.index.equals(dates)
    assert f["market"].iloc[1:].notna().all()
    assert f["low_vol"].iloc[:60].isna().all() and f["low_vol"].iloc[100:].notna().all()
    assert "size" not in build_factors(close, None, dates).columns


def test_factors_are_causal() -> None:
    close, vol, dates = _universe()
    cut = 400
    base = build_factors(close, vol, dates)
    pert = close.copy()
    pert[cut + 1 :] *= np.random.default_rng(5).uniform(0.5, 1.5, pert[cut + 1 :].shape)
    other = build_factors(pert, vol, dates)
    pd.testing.assert_frame_equal(base.iloc[: cut + 1], other.iloc[: cut + 1])


def test_momentum_factor_loads_on_a_momentum_strategy() -> None:
    f = _fake_factors()
    rng = np.random.default_rng(3)
    r = 0.9 * f["momentum"].to_numpy() + rng.normal(0, 0.0015, len(f))
    rows = _by_id(run_attribution(r, f, 252.0))
    assert rows["residual_alpha"]["status"] == "fail"
    assert "momentum" in rows["residual_alpha"]["summary"]
    assert rows["known_anomaly_match"]["details"]["closest"] == "momentum"
    assert set(NEXT_ACTIONS) == set(rows)


def test_independent_alpha_passes_and_spans() -> None:
    f = _fake_factors()
    r = np.random.default_rng(4).normal(0.0008, 0.004, len(f))
    rows = _by_id(run_attribution(r, f, 252.0))
    assert rows["residual_alpha"]["status"] in ("pass", "warn")
    t = rows["residual_alpha"]["details"]["alpha_t"]
    assert (rows["residual_alpha"]["status"] == "pass") == (t >= 3)
    assert rows["factor_spanning"]["details"]["increase"] > 0.05
    assert rows["factor_spanning"]["status"] == "info"


def test_short_put_payoff_flags_hidden_short_vol() -> None:
    f = _fake_factors(t=2000)
    m = f["market"].to_numpy()
    r = 0.0015 - 3.0 * np.maximum(0.0, -m - 0.018)
    rows = _by_id(run_attribution(r, f, 252.0))
    assert rows["hidden_short_volatility"]["status"] in ("warn", "fail")
    assert rows["hidden_short_volatility"]["details"]["tm_gamma"] != 0
    assert rows["market_timing_beta"]["status"] == "info"


def test_load_factors_alignment_and_min_overlap(tmp_path) -> None:
    f = _fake_factors(t=300)
    p = tmp_path / "f.csv"
    f.rename_axis("date").reset_index().to_csv(p, index=False)
    got = load_factors(p, f.index[50:])
    assert len(got) == 250 and list(got.columns) == list(f.columns)
    with pytest.raises(ValueError, match="overlaps only"):
        load_factors(p, f.index[:30].append(pd.bdate_range("2030-01-01", periods=100)))


def test_too_few_rows_skip() -> None:
    f = _fake_factors(t=1000).iloc[:40]
    rows = run_attribution(np.zeros(40), f, 252.0)
    assert all(r["status"] == "skip" for r in rows)


def test_exact_factor_combination_is_not_alpha() -> None:
    """A return that is exactly a mix of factors has no residual: its alpha t-statistic means nothing."""
    from monte_neo.alpha.attribution import check_residual_alpha

    rng = np.random.default_rng(5)
    f = pd.DataFrame({"market": rng.normal(0.0004, 0.01, 500), "momentum": rng.normal(0.0006, 0.008, 500)})
    row = check_residual_alpha((0.5 * f["market"] + f["momentum"]).to_numpy(), f, 252.0)
    assert row["status"] == "fail" and "no residual" in row["summary"]
