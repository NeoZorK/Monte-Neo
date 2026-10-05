"""Behaviour that the mutation check (scripts/mutation_check.py) found unpinned: exact values, boundaries and defaults."""

from __future__ import annotations

import ast
import json
import math
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd
import pytest

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.verify import lookahead as la
from monte_neo.verify import repaint as rp
from monte_neo.verify.history import History, diff_certificates, render_markdown
from monte_neo.verify.ledger import GENESIS, Ledger, ledger_row, variant_id
from monte_neo.verify.quality import _scale, data_quality, spike_profit_share, time_gaps
from monte_neo.verify.stats import (
    deflated_sharpe,
    expected_max_sharpe,
    infer_periods_per_year,
    lo_adjusted_sharpe,
    sharpe_per_bar,
)

DF = synthetic_ohlcv(600, seed=9)

# ---- lookahead.py ----------------------------------------------------------------------------------------------------


def test_mirror_future_negates_every_later_log_return() -> None:
    mirrored = la.mirror_future(DF, 300)
    before = np.diff(np.log(DF["close"].to_numpy()))[300:]
    after = np.diff(np.log(mirrored["close"].to_numpy()))[300:]
    assert np.allclose(after, -before, atol=1e-12)
    assert np.array_equal(mirrored["close"].to_numpy()[:301], DF["close"].to_numpy()[:301])


def test_the_default_number_of_even_checkpoints_and_the_report_limit() -> None:
    constant = lambda d: np.ones(len(d))  # noqa: E731 - no decision points, so only the even checkpoints remain
    assert la.probe_truncation(constant, DF)["checkpoints"] == 24
    assert la.MAX_REPORTED == 5
    leak = lambda d: (d["close"].shift(-1) > d["close"]).astype(int).to_numpy()  # noqa: E731
    result = la.probe_truncation(leak, DF, n_checks=40)
    assert result["status"] == "fail" and len(result["mismatches"]) == 5 < result["mismatch_count"]


def test_decision_points_respect_the_first_and_last_allowed_bars() -> None:
    first = np.zeros(100, dtype=int)
    first[10:] = 1  # bar 10 = n // 10 is the first allowed checkpoint
    assert 10 in la._decision_points(first, 100, 5, None).tolist()
    assert la._decision_points(first, 100, 5, 11).size == 0 and 10 in la._decision_points(first, 100, 5, 10).tolist()
    last = np.zeros(100, dtype=int)
    last[98:] = 1  # bar 98 = n - 2 is allowed
    assert 98 in la._decision_points(last, 100, 5, None).tolist()
    beyond = np.zeros(100, dtype=int)
    beyond[99:] = 1
    assert la._decision_points(beyond, 100, 5, None).size == 0
    low = np.zeros(40, dtype=int)
    low[2:] = 1
    assert 2 in la._decision_points(low, 40, 5, 2).tolist() and la._decision_points(low, 40, 5, 0).tolist() == [2]
    assert la._decision_points(np.zeros(2, dtype=int), 2, 5, None).size == 0


def test_independence_needs_four_changes_and_names_the_three_kinds() -> None:
    df = DF.assign(timestamp=pd.date_range("2022-01-03", periods=len(DF), freq="h"))
    few = np.zeros(len(df), dtype=int)
    few[100:] = 1
    assert la.probe_data_independence(lambda d: few[: len(d)], df, few)["status"] == "skip"
    three = np.zeros(len(df), dtype=int)
    three[[100, 200, 300]] = 1
    three = np.cumsum(np.isin(np.arange(len(df)), [100, 200, 300])) % 2  # up, down, up: three changes
    four = np.cumsum(np.isin(np.arange(len(df)), [100, 200, 300, 400])) % 2  # four changes
    assert la.probe_data_independence(lambda d: three[: len(d)], df, three)["status"] == "skip"
    assert la.probe_data_independence(lambda d: four[: len(d)], df, four)["position_changes"] == 4
    assert la.probe_data_independence(lambda d: four[: len(d)], df, four)["status"] in ("warn", "pass")
    stored = (np.arange(len(df)) // 20 % 2).astype(int)
    out = la.probe_data_independence(lambda d: stored[: len(d)], df, stored)
    assert out["kind"] == "ignores prices and dates" and out["status"] == "warn" and out["stored_answer"]
    calendar = lambda d: (pd.to_datetime(d["timestamp"]).dt.hour < 12).astype(int).to_numpy()  # noqa: E731
    cal = la.probe_data_independence(calendar, df, calendar(df))
    assert cal["kind"] == "depends on the calendar only" and cal["status"] == "pass" and not cal["stored_answer"]
    reads = lambda d: (d["close"] > d["close"].rolling(5).mean()).astype(int).to_numpy()  # noqa: E731
    assert la.probe_data_independence(reads, df, reads(df))["kind"] == "reads the prices"
    no_dates = la.probe_data_independence(lambda d: stored[: len(d)], DF.drop(columns="timestamp"), stored)
    assert no_dates["same_on_foreign_prices_and_dates"] is None and no_dates["stored_answer"] is True


def test_the_foreign_dates_are_shifted_by_exactly_the_documented_step() -> None:
    df = DF.assign(timestamp=pd.date_range("2022-01-03", periods=len(DF), freq="h"))
    shifted = la.foreign_table(df, shift_dates=True)
    assert (pd.to_datetime(shifted["timestamp"]).dt.tz_localize(None) - pd.to_datetime(df["timestamp"]).dt.tz_localize(None)).eq(la.DATE_SHIFT).all()
    assert la.DATE_SHIFT == pd.Timedelta(days=37, hours=7, minutes=13)
    assert la.DATE_SHIFT % pd.Timedelta(days=7) != pd.Timedelta(0) and la.DATE_SHIFT % pd.Timedelta(days=1) != pd.Timedelta(0)
    prices = la.foreign_table(df)
    assert (prices["high"] >= prices[["open", "close"]].max(axis=1)).all() and (prices["low"] <= prices[["open", "close"]].min(axis=1)).all()


def test_the_accuracy_z_score_the_better_of_two_rates_and_the_short_input() -> None:
    n = 400
    close = 100 + np.cumsum(np.ones(n) * 0.1 * np.where(np.arange(n) % 2 == 0, 1, -1))
    open_ = close.copy()
    sig = np.where(np.arange(n) % 2 == 1, 1, -1)  # right on every bar
    out = la.implausible_accuracy(open_, close, sig)
    assert out["hit_rate"] == 1.0 and out["z_score"] == pytest.approx((1.0 - 0.5) * 2.0 * math.sqrt(out["active_bars"]))
    assert out["status"] == "fail"
    assert la.implausible_accuracy(open_[:2], close[:2], sig[:2])["status"] == "skip"
    three = la.implausible_accuracy(open_[:3], close[:3], sig[:3])
    assert three["status"] == "skip" and three["active_bars"] == 2  # three bars are enough to read, too few to judge
    # body (open to close) hit rate higher than the close-to-close one: the better is reported
    c = np.array([100.0, 101.0, 100.0, 101.0, 100.0] * 40)
    o = np.array([100.0, 100.0, 101.0, 100.0, 101.0] * 40) - 0.5 * 0
    s = np.ones(200)
    r = la.implausible_accuracy(o, c, s)
    assert r["hit_rate"] == max(r["hit_rate_close_to_close"], r["hit_rate_next_bar_body"])


# ---- repaint.py ------------------------------------------------------------------------------------------------------


def _bar(o: float, h: float, l: float, c: float) -> pd.DataFrame:
    return pd.DataFrame({"open": [100.0, o], "high": [101.0, h], "low": [99.0, l], "close": [100.0, c], "volume": [10.0, 40.0]})


@pytest.mark.parametrize(
    "fraction,expected",
    [
        (0.0, (100.0, 100.0, 100.0, 100.0)),
        (0.25, (100.0, 100.0, 92.5, 92.5)),  # up bar: a quarter of the bar is 3/4 of the way from the open (100) to the low (90)
        (0.5, (100.0, 105.0, 90.0, 105.0)),  # halfway: past the low, half way from the low to the high
        (0.75, (100.0, 120.0, 90.0, 117.5)),  # three quarters: a quarter of the way from the high (120) to the close (110)
    ],
)
def test_the_snapshot_follows_open_low_high_close_for_an_up_bar(fraction: float, expected: tuple) -> None:
    snap = rp.snapshot(_bar(100.0, 120.0, 90.0, 110.0), 1, fraction).iloc[-1]
    assert (snap["open"], snap["high"], snap["low"], snap["close"]) == pytest.approx(expected)
    assert snap["volume"] == pytest.approx(40.0 * fraction)


def test_the_snapshot_of_a_down_bar_goes_to_the_high_first_and_a_flat_bar_counts_as_up() -> None:
    snap = rp.snapshot(_bar(100.0, 120.0, 90.0, 95.0), 1, 0.5).iloc[-1]  # open -> high (1/3), then half way down to the low
    assert snap["high"] == pytest.approx(120.0) and snap["close"] == pytest.approx(105.0) and snap["low"] == pytest.approx(100.0)
    flat = rp.snapshot(_bar(100.0, 120.0, 90.0, 100.0), 1, 0.25).iloc[-1]  # c == o: the path visits the low first
    assert flat["low"] == pytest.approx(92.5) and flat["high"] == pytest.approx(100.0)


def test_the_repaint_constants_and_the_extension_length() -> None:
    assert rp.FRACTIONS == (0.0, 0.25, 0.5, 0.75) and rp.REVISED_BARS == 3 and rp.MODES == ("off", "auto", "strict")
    steady = lambda d: (d["close"] > d["close"].rolling(5).mean()).astype(int).to_numpy()  # noqa: E731
    for n, k in ((60, 3), (200, 10), (1500, 50)):
        d = synthetic_ohlcv(n, seed=2)
        r = rp.probe_repaint_history(steady, d, steady(d))
        assert r["extension_bars"] == k and r["status"] == "pass"


def test_the_repaint_rate_the_depth_and_the_strict_live_checkpoints() -> None:
    d = synthetic_ohlcv(1200, seed=4)
    centred = lambda df: (df["close"] > df["close"].rolling(11, center=True).mean()).astype(int).to_numpy()  # noqa: E731
    r = rp.probe_repaint_history(centred, d, centred(d), mode="strict")
    assert r["max_depth"] == 4
    assert r["repaint_rate"] == pytest.approx(r["moved_bars"] / (len(d) - 1), abs=1e-6) and 0 < r["repaint_rate"] < 1
    steady = lambda df: (df["close"] > df["close"].rolling(5).mean()).astype(int).to_numpy()  # noqa: E731
    auto = rp.probe_repaint_live(steady, d, steady(d), mode="auto")
    strict = rp.probe_repaint_live(steady, d, steady(d), mode="strict")
    assert strict["bars_checked"] > auto["bars_checked"] and strict["snapshots"] == strict["bars_checked"] * 4
    hist_auto = rp.probe_repaint_history(steady, d, steady(d), mode="auto")
    hist_strict = rp.probe_repaint_history(steady, d, steady(d), mode="strict")
    assert hist_strict["checkpoints"] > hist_auto["checkpoints"] > 10


# ---- stats.py --------------------------------------------------------------------------------------------------------


def test_periods_per_year_of_a_calendar_year_of_daily_bars_is_the_calendar_count() -> None:
    stamps = pd.date_range("2022-01-01", periods=730, freq="D")
    assert infer_periods_per_year(stamps) == pytest.approx(365.25, rel=2e-3)


def test_the_sharpe_needs_three_returns_and_the_expected_maximum_matches_the_formula() -> None:
    from monte_neo.verify.stats import _moments

    assert _moments(np.array([0.1, 0.2])) == (0.0, 3.0) and _moments(np.array([0.1, 0.2, 0.9])) != (0.0, 3.0)
    assert _moments(np.ones(10)) == (0.0, 3.0) and sharpe_per_bar(np.array([0.1, 0.2, 0.3])) != 0.0
    nd = NormalDist()
    gamma, n, var = 0.5772156649015329, 10, 1.0
    expected = (1 - gamma) * nd.inv_cdf(1 - 1 / n) + gamma * nd.inv_cdf(1 - 1 / (n * math.e))
    assert expected_max_sharpe(n, var) == pytest.approx(expected, rel=1e-12)
    r = np.random.default_rng(1).normal(0.001, 0.01, 501)
    assert deflated_sharpe(r, n_trials=2)["expected_max_sharpe_per_bar"] == pytest.approx(expected_max_sharpe(2, 1.0 / 500))


def test_the_correction_floor_caps_the_factor_for_differenced_noise() -> None:
    noise = np.random.default_rng(2).normal(0.0, 0.01, 4001)
    r = np.diff(noise) + 0.0004  # r_t = e_t - e_{t-1}: lag-1 correlation -0.5 and nothing else, so the spread is far below the floor
    out = lo_adjusted_sharpe(r, 252.0)
    assert out["rho1"] < -0.4 and out["factor"] == pytest.approx(1.0 / math.sqrt(0.05), rel=1e-6)


# ---- quality.py ------------------------------------------------------------------------------------------------------


def test_the_robust_scale_of_a_normal_sample_is_its_standard_deviation() -> None:
    x = np.random.default_rng(3).normal(0.0, 0.02, 20_000)
    assert _scale(x) == pytest.approx(0.02, rel=0.03)


def test_missing_bars_in_a_market_that_never_closes_are_counted_exactly() -> None:
    stamps = pd.date_range("2022-01-01", periods=1000, freq="D").delete(np.arange(50, 1000, 100))
    gaps = time_gaps(stamps)
    steps = len(stamps) - 1
    assert gaps["missing_share"] == pytest.approx(10 / steps, rel=1e-9)
    weekdays = pd.bdate_range("2022-01-03", periods=1000)
    assert time_gaps(weekdays)["missing_share"] == 0.0  # a calendar with weekends is not "missing" every Monday


def test_long_gaps_in_a_market_with_nights_report_only_the_outage() -> None:
    hours = pd.date_range("2022-01-03", periods=3000, freq="h")
    hours = hours[~((hours.hour >= 21) | (hours.hour < 7))]  # closed every night
    outage = hours.delete(np.arange(1000, 1100))  # and a hundred missing bars
    clean, hole = time_gaps(hours), time_gaps(outage)
    assert clean["count"] == 0 and hole["count"] == 1 and hole["largest_hours"] > 90


def test_a_split_that_only_the_open_shows_is_found_and_examples_are_capped() -> None:
    n = 300
    close = 100 + np.cumsum(np.random.default_rng(5).normal(0, 0.1, n))
    open_ = np.r_[close[0], close[:-1]].copy()
    open_[150] = close[149] / 2.0  # the open gaps to half the previous close, then the day recovers
    ohlc = {"open": open_, "high": np.maximum(open_, close) + 0.1, "low": np.minimum(open_, close) - 0.1, "close": close}
    assert data_quality(ohlc)["split_jumps"] >= 1
    spikes = close.copy()
    spikes[20:200:5] *= 1.5
    out = data_quality({"open": spikes, "high": spikes, "low": spikes, "close": spikes})
    assert out["spikes"] > 10 and len(out["spike_examples"]) == 10


def test_the_profit_share_of_spikes_is_none_without_equity_or_profit() -> None:
    mask = np.zeros(10, dtype=bool)
    mask[4] = True
    assert spike_profit_share(np.array([1.0, 1.1]), mask[:2]) is None  # fewer than three points
    assert spike_profit_share(np.ones(10), mask) is None  # no profit at all
    assert spike_profit_share(np.cumprod(np.r_[1.0, np.full(9, 1.01)]), np.zeros(10, dtype=bool)) is None  # no spike bar
    short = spike_profit_share(np.array([1.0, 1.1, 1.21]), np.array([False, True, False]))
    assert short is not None and 0.0 < short <= 1.0  # three points are enough
    assert spike_profit_share(np.array([1.0, 0.9, 0.81]), np.array([False, True, False])) is None  # a loss has no profit share


# ---- ledger.py -------------------------------------------------------------------------------------------------------


def test_variant_ids_name_their_kind_and_the_first_entry_chains_to_the_genesis(tmp_path: Path) -> None:
    assert variant_id("def f():\n    return 1\n").startswith("ast:") and variant_id("def (:").startswith("src:")
    assert variant_id(None, np.arange(5)).startswith("pos:") and variant_id(None) is None
    assert len(variant_id("x = 1\n")) == len("ast:") + 16 and len(variant_id(None, np.arange(3))) == len("pos:") + 16
    book = Ledger(tmp_path / "l.jsonl")
    entry = book.record(variant="ast:1", data_id="d", sharpe=1.0, verdict="PASS", certificate_id="c")
    assert entry["prev"] == GENESIS == "0" * 64


def test_a_declared_count_equal_to_the_counted_one_is_not_a_warning() -> None:
    chain = {"ok": True, "entries": 3, "problem": None}
    assert ledger_row(3, 3, chain, Path("x"))["status"] == "pass"
    assert ledger_row(3, 2, chain, Path("x"))["status"] == "warn"


# ---- history.py ------------------------------------------------------------------------------------------------------


def _summary(verdict: str, checks: dict[str, str], metrics: dict[str, float] | None = None, cid: str = "a") -> dict:
    return {"verdict": verdict, "checks": checks, "metrics": metrics or {}, "certificate": cid, "n_trials": 1}


@pytest.mark.parametrize(
    "old,new,worse",
    [("pass", "warn", True), ("warn", "fail", True), ("pass", "fail", True), ("info", "pass", False), ("skip", "pass", False), ("fail", "warn", False), ("warn", "warn", False)],
)
def test_check_status_ranks(old: str, new: str, worse: bool) -> None:
    d = diff_certificates(_summary("PASS", {"x": old}), _summary("PASS", {"x": new}, cid="b"))
    changed = [c for c in d["checks"] if c["id"] == "x"]
    assert (bool(changed) and changed[0]["worse"]) is worse
    assert d["regression"] is (new == "fail" and old != "fail")


def test_a_check_that_appears_or_disappears_is_listed_and_a_new_failure_is_a_regression() -> None:
    d = diff_certificates(_summary("PASS", {}), _summary("PASS", {"new": "fail"}, cid="b"))
    assert d["checks"] == [{"id": "new", "old": None, "new": "fail", "worse": True}] and d["regression"]
    gone = diff_certificates(_summary("PASS", {"old": "warn"}), _summary("PASS", {}, cid="b"))
    assert gone["checks"][0]["worse"] is False and not gone["regression"]


@pytest.mark.parametrize("old,new,worse", [("PASS", "PASS_WITH_WARNINGS", True), ("PASS_WITH_WARNINGS", "NEEDS_MORE_EVIDENCE", True), ("NEEDS_MORE_EVIDENCE", "REJECT", True), ("REJECT", "PASS", False), ("PASS", "PASS", False)])
def test_verdict_ranks(old: str, new: str, worse: bool) -> None:
    assert diff_certificates(_summary(old, {}), _summary(new, {}, cid="b"))["verdict"]["worse"] is worse


def test_metrics_deltas_equal_values_and_non_numbers() -> None:
    a = {"verdict": "PASS", "checks": {}, "metrics": {"total_return": 0.1, "sharpe_annualized": 1.0}, "certificate": "a", "n_trials": 1}
    b = {**a, "certificate": "b", "metrics": {"total_return": 0.1234567891, "sharpe_annualized": 1.0}}
    d = diff_certificates(a, b)
    assert list(d["metrics"]) == ["total_return"] and d["metrics"]["total_return"]["delta"] == pytest.approx(0.0234567891, abs=1e-6)
    only_new = diff_certificates(_summary("PASS", {}), _summary("PASS", {}, {"total_return": 0.5}, cid="b"))
    assert only_new["metrics"]["total_return"] == {"old": None, "new": 0.5, "delta": None}
    report = {"verdict": "PASS", "certificate_id": "z", "checks": [], "metrics": {"total_return": True, "max_drawdown": "x", "psr": 0.5}}
    assert diff_certificates(report, report)["metrics"] == {}
    from monte_neo.verify.history import summarize

    assert summarize(report)["metrics"] == {"psr": 0.5}
    assert summarize({"verdict": "PASS", "checks": [], "metrics": None})["n_trials"] is None


def test_the_markdown_marks_worse_checks_and_the_history_defaults_to_the_project_folder(tmp_path: Path, monkeypatch) -> None:
    d = diff_certificates(_summary("PASS", {"x": "pass"}), _summary("PASS", {"x": "fail"}, cid="b"))
    text = render_markdown(d)
    assert "| x | pass | fail (worse) |" in text and "regressed" in text
    ok = render_markdown(diff_certificates(_summary("PASS", {"x": "warn"}), _summary("PASS", {"x": "pass"}, cid="b")))
    assert "| x | warn | pass |" in ok and "No regression" in ok and "(worse)" not in ok
    monkeypatch.chdir(tmp_path)
    History().add({"verdict": "PASS", "certificate_id": "c", "checks": [], "metrics": {}})
    assert (tmp_path / ".monte-neo" / "history.jsonl").exists()
    assert json.loads((tmp_path / ".monte-neo" / "history.jsonl").read_text().splitlines()[0])["certificate"] == "c"
    _ = ast
