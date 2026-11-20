"""Unit tests of the pairs mathematics on processes with a known answer (not backtests).

Reference values: MacKinnon (1994, 2010) critical values, Kwiatkowski et al. (1992) Table 1, Johansen trace tables,
Bai & Perron (2003) sup-F table. The simulated sizes check that each test rejects about as often as its level says.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from monte_neo.verify import pairs_breaks as br
from monte_neo.verify import pairs_johansen as jo
from monte_neo.verify import pairs_legging as lg
from monte_neo.verify import pairs_selection as sel
from monte_neo.verify import pairs_stability as st
from monte_neo.verify import pairs_unitroot as ur


def ar1(n: int, phi: float, rng: np.random.Generator, scale: float = 1.0) -> np.ndarray:
    e = scale * rng.standard_normal(n)
    out = np.zeros(n)
    for i in range(1, n):
        out[i] = phi * out[i - 1] + e[i]
    return out


def rw(n: int, rng: np.random.Generator) -> np.ndarray:
    return np.cumsum(rng.standard_normal(n))


def cointegrated(n: int, rng: np.random.Generator, beta: float = 0.8, phi: float = 0.93) -> tuple[np.ndarray, np.ndarray]:
    x = rw(n, rng)
    return 1.0 + beta * x + ar1(n, phi, rng, 0.4), x


# ---- unit root / cointegration -------------------------------------------------------------------------------------


@pytest.mark.parametrize(("tau", "p"), [(-2.8621, 0.05), (-3.4304, 0.01), (-2.5671, 0.10)])
def test_adf_pvalue_reproduces_the_published_critical_values(tau: float, p: float) -> None:
    assert ur.adf_pvalue(tau) == pytest.approx(p, abs=0.002)


def test_adf_pvalue_edges() -> None:
    assert ur.adf_pvalue(3.0) == 1.0 and ur.adf_pvalue(-30.0) == 0.0
    assert 0.5 < ur.adf_pvalue(-1.0) < 1.0


def test_adf_rejects_a_stationary_series_and_not_a_random_walk() -> None:
    rng = np.random.default_rng(1)
    assert ur.adf_test(ar1(1000, 0.7, rng))["pvalue"] < 0.01
    assert ur.adf_test(rw(1000, rng))["pvalue"] > 0.05
    out = ur.adf_test(rw(300, rng), max_lag=2)
    assert out["lag"] <= 2 and out["n_obs"] > 250
    with pytest.raises(ValueError, match="at least 20"):
        ur.adf_test(np.arange(10.0))


def test_engle_granger_finds_a_known_cointegrated_pair() -> None:
    rng = np.random.default_rng(2)
    y, x = cointegrated(1500, rng)
    out = ur.engle_granger(y, x)
    assert out["reject"][0.01] and out["pvalue_bucket"] == "<0.01"
    assert out["beta"] == pytest.approx(0.8, abs=0.02) and out["alpha"] == pytest.approx(1.0, abs=0.5)
    assert out["spread"].shape == y.shape


def test_engle_granger_size_on_independent_random_walks() -> None:
    """Independent walks: the 5 % test must reject about 5 % of the time (MacKinnon 2010 critical value -3.336)."""
    rng = np.random.default_rng(3)
    stats = np.array([ur.engle_granger(rw(800, rng), rw(800, rng))["stat"] for _ in range(300)])
    assert 0.01 <= float(np.mean(stats < ur.EG_CRITICAL[0.05])) <= 0.11
    assert np.quantile(stats, 0.05) == pytest.approx(-3.34, abs=0.2)


def test_engle_granger_buckets_and_errors() -> None:
    rng = np.random.default_rng(4)
    buckets = {ur.engle_granger(rw(400, rng), rw(400, rng))["pvalue_bucket"] for _ in range(120)}
    assert buckets <= {"<0.01", "0.01-0.05", "0.05-0.10", ">0.10"} and ">0.10" in buckets
    assert {"0.01-0.05", "0.05-0.10"} & buckets
    with pytest.raises(ValueError, match="same length"):
        ur.engle_granger(np.zeros(50), np.zeros(60))


def test_kpss_critical_values_and_power() -> None:
    rng = np.random.default_rng(5)
    iid = [ur.kpss_test(rng.standard_normal(1000))["reject"][0.05] for _ in range(200)]
    assert float(np.mean(iid)) < 0.12
    walk = ur.kpss_test(rw(1000, rng), lags=10)
    assert walk["reject"][0.01] and walk["lags"] == 10 and walk["critical"][0.05] == 0.463
    with pytest.raises(ValueError, match="at least 20"):
        ur.kpss_test(np.arange(5.0))


def test_half_life_recovers_the_ornstein_uhlenbeck_value() -> None:
    rng = np.random.default_rng(6)
    phi = 0.95
    out = ur.half_life(ar1(20000, phi, rng))
    assert out["mean_reverting"] and out["half_life"] == pytest.approx(math.log(2) / -math.log(phi), rel=0.15)


def test_half_life_of_a_random_walk_is_not_a_reversion() -> None:
    out = ur.half_life(rw(2000, np.random.default_rng(7)) * 0 + np.arange(2000.0))
    assert not out["mean_reverting"] and out["half_life"] == math.inf
    with pytest.raises(ValueError, match="at least 20"):
        ur.half_life(np.arange(5.0))


def test_long_run_variance_of_white_noise_is_its_variance() -> None:
    x = np.random.default_rng(8).standard_normal(20000)
    assert ur.long_run_variance(x, 5) == pytest.approx(1.0, rel=0.1)
    assert ur.normal_cdf(0.0) == 0.5


# ---- Johansen ------------------------------------------------------------------------------------------------------


def basket(n: int, rng: np.random.Generator) -> np.ndarray:
    f = rw(n, rng)
    return np.column_stack([f + ar1(n, 0.8, rng, 0.3), 0.5 * f + ar1(n, 0.8, rng, 0.3), rw(n, rng)])


def test_johansen_finds_one_relation_among_three_series() -> None:
    ranks = [jo.johansen(basket(1000, np.random.default_rng(s)))["rank"] for s in range(20)]
    assert np.mean(np.array(ranks) >= 1) >= 0.9


def test_johansen_finds_nothing_in_independent_random_walks() -> None:
    rng = np.random.default_rng(9)
    ranks = np.array([jo.johansen(np.column_stack([rw(1000, rng) for _ in range(3)]))["rank"] for _ in range(80)])
    assert np.mean(ranks == 0) >= 0.8


def test_johansen_details_and_levels() -> None:
    rng = np.random.default_rng(10)
    out = jo.johansen(basket(800, rng), k_diff=2, level="99")
    assert out["level"] == "99" and out["vector"][0] == pytest.approx(1.0) and out["trace"].shape == (3,)
    assert out["trace_critical"][0] == jo.TRACE_CRITICAL[3][2]
    assert jo.TRACE_CRITICAL[1][1] == pytest.approx(3.8415, abs=1e-4)  # chi-square(1) 95 % quantile
    two = jo.johansen(np.column_stack(cointegrated(800, rng)))
    assert two["rank"] >= 1


def test_johansen_input_errors() -> None:
    with pytest.raises(ValueError, match="2 to 5"):
        jo.johansen(np.zeros((100, 1)))
    with pytest.raises(ValueError, match="level"):
        jo.johansen(np.zeros((100, 2)), level="80")
    with pytest.raises(ValueError, match="too few"):
        jo.johansen(np.random.default_rng(0).standard_normal((15, 3)))


# ---- stability -----------------------------------------------------------------------------------------------------


def test_hedge_ratio_is_stable_for_a_fixed_relationship_and_not_for_a_changing_one() -> None:
    rng = np.random.default_rng(11)
    y, x = cointegrated(2000, rng)
    stable = st.rolling_hedge_ratio(y, x)
    assert stable["cv"] < 0.15 and stable["median"] == pytest.approx(0.8, abs=0.05) and stable["window"] == 500
    y2 = np.where(np.arange(2000) < 1000, 0.5 * x, 1.5 * x) + ar1(2000, 0.9, rng, 0.2)
    moving = st.rolling_hedge_ratio(y2, x, window=300, step=100)
    assert moving["cv"] > 0.25 and moving["drift"] > 0.5


def test_window_errors_and_default() -> None:
    assert st.default_window(400) == 200 and st.default_window(10000) == 2500 and st.default_window(1200) == 300
    y = np.zeros(300)
    for fn in (st.rolling_hedge_ratio, st.rolling_cointegration):
        with pytest.raises(ValueError, match="window"):
            fn(y, y, window=10)


def test_rolling_cointegration_tracks_when_the_link_held() -> None:
    rng = np.random.default_rng(12)
    n = 3000
    x = rw(n, rng)
    y = np.where(np.arange(n) < 1500, 0.8 * x + ar1(n, 0.9, rng, 0.3), np.cumsum(rng.standard_normal(n)))
    held = st.rolling_cointegration(0.8 * x + ar1(n, 0.9, rng, 0.3), x, window=500, step=250)
    assert held["share"] >= 0.8 and held["last_reject_end"] > 2000
    broken = st.rolling_cointegration(y, x, window=500, step=250)
    assert broken["share"] < held["share"] and broken["last_reject_end"] < 2000
    walks = st.rolling_cointegration(rw(1500, rng) * 5, rw(1500, rng) * 5, window=500, step=500)
    assert walks["share"] <= 0.67


def test_rolling_cointegration_reports_minus_one_when_it_never_holds() -> None:
    walks = st.rolling_cointegration(np.arange(400.0) ** 2, np.cos(np.arange(400.0) / 50) + np.arange(400.0), window=100, step=300)
    assert walks["last_reject_end"] == -1 and walks["share"] == 0.0


# ---- structural breaks ---------------------------------------------------------------------------------------------


def test_break_tests_keep_their_size_on_a_stable_spread() -> None:
    rng = np.random.default_rng(13)
    cu, sw = [], []
    for _ in range(200):
        x = ar1(1500, 0.9, rng)
        cu.append(br.cusum_test(x)["reject"][0.05])
        sw.append(br.sup_wald_test(x)["reject"][0.01])
    assert float(np.mean(cu)) < 0.1 and float(np.mean(sw)) < 0.08


def test_break_tests_find_a_level_shift_and_its_date() -> None:
    rng = np.random.default_rng(14)
    x = ar1(2000, 0.9, rng)
    x[1200:] += 5.0
    cu, sw = br.cusum_test(x), br.sup_wald_test(x)
    assert cu["reject"][0.01] and sw["reject"][0.01]
    assert abs(sw["index"] - 1200) <= 40 and abs(cu["index"] - 1200) <= 80
    assert sw["shift"] == pytest.approx(5.0, abs=1.0) and sw["shift_sd"] > 1.0


def test_chow_test_known_date() -> None:
    rng = np.random.default_rng(15)
    x = ar1(1500, 0.8, rng)
    x[700:] += 4.0
    out = br.chow_test(x, 700)
    assert out["reject"][0.01] and out["index"] == 700 and out["shift"] == pytest.approx(4.0, abs=1.0)
    assert br.chow_test(ar1(1500, 0.8, np.random.default_rng(16)), 400)["stat"] < 25
    with pytest.raises(ValueError, match="at least 5 bars"):
        br.chow_test(x, 2)


def test_break_onset_dates_a_drift_after_the_break_at_its_start() -> None:
    rng = np.random.default_rng(22)
    x = ar1(2000, 0.8, rng, 0.1)
    x[1000:] += 2.0 + np.cumsum(0.01 * np.ones(1000))  # a jump of ~20 sd, then a drift
    k = br.sup_wald_test(x)["index"]
    assert k > 1100 and abs(br.break_onset(x, k) - 1000) <= 10
    calm = ar1(500, 0.8, rng)
    assert br.break_onset(calm, 300) == 300
    assert br.break_onset(np.where(np.arange(300) < 150, 0.0, 9.0) + 0.01 * rng.standard_normal(300), 150) == 150


def test_bai_perron_finds_two_breaks_and_none_in_a_stable_series() -> None:
    rng = np.random.default_rng(17)
    x = ar1(3000, 0.8, rng)
    x[1000:2000] += 6.0
    out = br.bai_perron_means(x)
    assert len(out["breaks"]) == 2 and abs(out["breaks"][0] - 1000) < 50 and abs(out["breaks"][1] - 2000) < 50
    assert len(out["stats"]) == 2
    stable = [len(br.bai_perron_means(ar1(1500, 0.5, rng), level=0.01)["breaks"]) for _ in range(40)]
    assert np.mean(np.array(stable) == 0) >= 0.9
    assert len(br.bai_perron_means(x, max_breaks=1)["breaks"]) == 1


def test_bai_perron_skips_segments_that_are_too_short_to_split() -> None:
    x = np.random.default_rng(23).standard_normal(60) * 0.1
    x[:12] += 5.0
    out = br.bai_perron_means(x)
    assert out["breaks"] == [12]


def test_break_input_errors_and_constants() -> None:
    short = np.arange(10.0)
    for fn in (br.cusum_test, br.sup_wald_test, br.bai_perron_means):
        with pytest.raises(ValueError, match="at least"):
            fn(short)
    with pytest.raises(ValueError, match="level"):
        br.bai_perron_means(np.zeros(100), level=0.1)
    with pytest.raises(ValueError, match="at least"):
        br.chow_test(short, 5)
    assert br.CUSUM_CRITICAL[0.05] == 1.3581 and br.SUPW_CRITICAL[0.05] == 8.58
    assert br.prewhitened_lrv(np.zeros(10)) > 0.0


# ---- legging, borrow, selection ------------------------------------------------------------------------------------


def legs_table(n: int = 600, seed: int = 20) -> pd.DataFrame:
    """A pair that really mean-reverts, traded with a causal z-score rule and a fixed hedge; the legs earn its P&L."""
    rng = np.random.default_rng(seed)
    x = 4.6 + 0.01 * rw(n, rng)
    spread = ar1(n, 0.85, rng, 0.004)
    y = 0.8 * x + spread
    s = pd.Series(y - 0.8 * x)
    z = ((s - s.rolling(60).mean()) / s.rolling(60).std()).to_numpy()
    pos = np.where(z > 1.0, -1.0, np.where(z < -1.0, 1.0, 0.0))
    pos = np.nan_to_num(pos)
    qty_y = np.concatenate([[0.0], pos[:-1]])
    df = pd.DataFrame({"px_y": np.exp(y), "px_x": np.exp(x), "qty_y": qty_y, "qty_x": -0.8 * qty_y}, index=pd.date_range("2024-01-01", periods=n, freq="h"))
    from monte_neo.verify.legs import rederive

    df["reported_return"] = np.concatenate([[0.0], rederive(df)])
    return df


def test_delay_series_whole_and_fractional_bars() -> None:
    q = np.array([1.0, 2.0, 3.0, 4.0])
    assert np.allclose(lg.delay_series(q, 0), q)
    assert np.allclose(lg.delay_series(q, 1), [1, 1, 2, 3])
    assert np.allclose(lg.delay_series(q, 0.5), [1, 1.5, 2.5, 3.5])
    assert np.allclose(lg.delay_series(q, 9), [1, 1, 1, 1])
    with pytest.raises(ValueError, match="negative"):
        lg.delay_series(q, -1)


def test_legging_delay_costs_money_on_a_fast_reversion_and_zero_delay_is_free() -> None:
    scan = lg.legging_scan(legs_table(), (0.0, 1.0, 3.0))
    assert scan[0]["damage"] == 0.0 and scan[0]["damage_share"] == 0.0 and scan[0]["std_ratio"] == 1.0
    assert scan[2]["std_ratio"] != 1.0  # a naked leg changes the risk of the book
    assert scan[0]["total"] > 0.0
    assert scan[2]["damage"] != 0.0 and scan[1]["delay_bars"] == 1.0
    flat = legs_table().assign(qty_y=0.0, qty_x=0.0)
    assert lg.legging_scan(flat, (0.0, 1.0))[1]["damage_share"] == 0.0


def test_borrow_scenario_fee_and_outages() -> None:
    body = legs_table()
    none = lg.borrow_scenario(body)
    assert none["total"] == pytest.approx(none["base_total"]) and none["fee"] == 0.0
    fee = lg.borrow_scenario(body, borrow_bps=500.0, periods_per_year=8760.0)
    assert fee["fee"] > 0.0 and fee["total"] < fee["base_total"] and fee["damage_share"] > 0.0
    out = lg.borrow_scenario(body, unavailable_share=0.5, seed=1)
    assert out["blocked_bars"] > 100 and out["outage_loss"] != 0.0
    assert lg.borrow_scenario(body.assign(qty_y=0.0, qty_x=0.0))["damage_share"] == 0.0
    for bad in ({"borrow_bps": -1.0}, {"unavailable_share": 1.5}):
        with pytest.raises(ValueError, match="borrow_bps"):
            lg.borrow_scenario(body, **bad)


def test_selection_counts_every_pair_and_variant() -> None:
    assert sel.pairs_in_universe(10) == 45 and sel.pairs_in_universe(2) == 1
    assert sel.effective_trials(45, 4, 2) == 360
    with pytest.raises(ValueError, match="at least 2"):
        sel.pairs_in_universe(1)
    with pytest.raises(ValueError, match="at least 1"):
        sel.effective_trials(0)
    r = np.random.default_rng(21).normal(0.0004, 0.01, 1500)
    one, many = sel.selection_report(r, 1), sel.selection_report(r, 2000, variants_per_pair=3)
    assert many["n_trials"] == 6000 and many["deflated_sharpe"] < one["deflated_sharpe"]
    assert many["deflated_sharpe_single"] == pytest.approx(one["deflated_sharpe"])
