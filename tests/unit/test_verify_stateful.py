"""Strategies that keep state or an answer instead of reading their input (stage 8.B)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.verify import verify_strategy
from monte_neo.verify.checks import IMPLAUSIBLE_SHARPE, independence_row, performance_row
from monte_neo.verify.lint import lint_source
from monte_neo.verify.lookahead import foreign_table, probe_data_independence

DF = synthetic_ohlcv(3000, seed=1)
DF["timestamp"] = pd.date_range("2020-01-01", periods=len(DF), freq="h")


def _future(d: pd.DataFrame, k: int = 40) -> np.ndarray:
    """A leak: the sign of the move over the next ``k`` bars, smoothed so that costs do not eat it."""
    pos = np.sign(d["close"].shift(-k) - d["close"]).fillna(0)
    return pos.rolling(10, min_periods=1).mean().round().to_numpy()


def _checks(report: dict) -> dict:
    return {c["id"]: c for c in report["checks"]}


def _cached() -> object:
    cache: dict[str, np.ndarray] = {}

    def signal(d: pd.DataFrame) -> np.ndarray:
        if "full" not in cache or len(d) > len(cache["full"]):
            cache["full"] = _future(d)  # computed once on the longest table, later calls get a prefix
        return cache["full"][: len(d)]

    return signal


ANSWER = _future(DF)
STORED_BY_DATE = pd.Series(ANSWER, index=DF["timestamp"])


@pytest.mark.parametrize(
    "name, fn",
    [
        ("cache between calls", _cached()),
        ("array computed in advance", lambda d: ANSWER[: len(d)]),
        ("table keyed by date", lambda d: STORED_BY_DATE.reindex(d["timestamp"]).fillna(0).to_numpy()),
    ],
)
def test_a_stored_leaky_answer_is_rejected(name: str, fn: object) -> None:
    report = verify_strategy(DF, signal_fn=fn)
    row = _checks(report)["data_independence"]
    assert report["verdict"] == "REJECT" and row["status"] == "fail", (name, row["summary"])
    assert _checks(report)["implausible_performance"]["status"] == "warn"


def test_a_strategy_that_reads_its_input_is_not_accused() -> None:
    sma = lambda d: np.where(d["close"].rolling(20).mean() > d["close"].rolling(80).mean(), 1, 0)  # noqa: E731
    report = verify_strategy(DF, signal_fn=sma)
    assert _checks(report)["data_independence"]["status"] == "pass"
    assert _checks(report)["data_independence"]["details"]["kind"] == "reads the prices"
    assert _checks(report)["implausible_performance"]["status"] == "pass"


def test_calendar_rules_are_legitimate_and_constant_positions_say_nothing() -> None:
    hours = lambda d: pd.to_datetime(d["timestamp"]).dt.hour.between(8, 16).astype(int).to_numpy()  # noqa: E731
    weekdays = lambda d: (pd.to_datetime(d["timestamp"]).dt.dayofweek < 2).astype(int).to_numpy()  # noqa: E731
    for fn in (hours, weekdays):
        row = _checks(verify_strategy(DF, signal_fn=fn))["data_independence"]
        assert row["status"] == "pass" and row["details"]["kind"] == "depends on the calendar only"
    hold = _checks(verify_strategy(DF, signal_fn=lambda d: np.ones(len(d))))["data_independence"]
    assert hold["status"] == "skip"


def test_a_fixed_rule_by_bar_number_is_a_warning_not_a_failure() -> None:
    every_20 = lambda d: ((np.arange(len(d)) // 20) % 2).astype(int)  # noqa: E731
    row = _checks(verify_strategy(DF, signal_fn=every_20))["data_independence"]
    assert row["status"] == "warn" and row["details"]["stored_answer"] is True


def test_without_strategy_code_or_for_universes_the_row_is_skipped() -> None:
    assert _checks(verify_strategy(DF, signals=ANSWER))["data_independence"]["status"] == "skip"
    assert independence_row(None, 0.0)["status"] == "skip"


def test_the_foreign_table_is_valid_deterministic_and_unrelated() -> None:
    a, b = foreign_table(DF), foreign_table(DF)
    assert a.equals(b)
    assert (a["high"] >= a[["open", "close"]].max(axis=1)).all() and (a["low"] <= a[["open", "close"]].min(axis=1)).all()
    assert abs(np.corrcoef(a["close"], DF["close"])[0, 1]) < 0.9 and len(a) == len(DF)
    shifted = foreign_table(DF, shift_dates=True)
    assert (pd.to_datetime(shifted["timestamp"], utc=True) - pd.to_datetime(DF["timestamp"], utc=True)).nunique() == 1
    assert shifted["timestamp"].iloc[0] != DF["timestamp"].iloc[0]
    no_dates = DF.drop(columns="timestamp")
    assert "timestamp" not in foreign_table(no_dates, shift_dates=True).columns


def test_a_strategy_that_cannot_run_on_the_foreign_table_is_skipped() -> None:
    def fragile(d: pd.DataFrame) -> np.ndarray:
        if abs(float(d["close"].iloc[0]) - float(DF["close"].iloc[0])) > 1e-9:
            raise RuntimeError("only works on the original file")
        return ANSWER[: len(d)]

    result = probe_data_independence(fragile, DF, np.asarray(ANSWER, dtype=np.int64))
    assert result["status"] == "skip" and "RuntimeError" in result["reason"]


def test_the_performance_smell_test_has_a_threshold_and_needs_enough_bars() -> None:
    assert performance_row(IMPLAUSIBLE_SHARPE - 0.1, 1000)["status"] == "pass"
    assert performance_row(IMPLAUSIBLE_SHARPE, 1000)["status"] == "warn"
    assert performance_row(50.0, 50)["status"] == "skip" and performance_row(float("nan"), 1000)["status"] == "skip"


def test_a_calendar_rule_with_an_impossible_sharpe_is_a_stored_answer() -> None:
    result = {"status": "warn", "kind": "depends on the calendar only", "stored_answer": False,
              "same_on_foreign_prices": 1.0, "same_on_foreign_prices_and_dates": 0.5, "position_changes": 99}
    assert independence_row(result, 1.0)["status"] == "pass"
    assert independence_row(result, 9.0)["status"] == "fail"


@pytest.mark.parametrize(
    "source, rule",
    [
        ("import functools\n@functools.lru_cache(maxsize=None)\ndef signal(df):\n    return df\n", "cached_signal"),
        ("from functools import cache\n@cache\ndef signal(df):\n    return df\n", "cached_signal"),
        ("from sklearn.linear_model import LogisticRegression\nm = LogisticRegression()\nm.fit(X, y)\ndef signal(df):\n    return m.predict(df)\n", "import_time_fit"),
        ("_c = {}\ndef signal(df):\n    global _c\n    return df\n", "global_state"),
    ],
)
def test_lint_names_state_kept_between_calls(source: str, rule: str) -> None:
    result = lint_source(source)
    assert result["status"] == "warn" and rule in {f["rule"] for f in result["findings"]}


def test_lint_leaves_ordinary_code_alone() -> None:
    quiet = [
        "def signal(df):\n    m = Model()\n    m.fit(df[:100])\n    return df\n",  # fitted inside signal(), on a prefix
        "if __name__ == '__main__':\n    m.fit(1)\ndef signal(df):\n    return df\n",
        "def signal(df):\n    return df['close'].rolling(5).mean()\n",
    ]
    for source in quiet:
        found = {f["rule"] for f in lint_source(source)["findings"]}
        assert not found & {"cached_signal", "import_time_fit", "global_state"}, source
