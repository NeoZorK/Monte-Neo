"""A12: defects of a quote table (the input of the arrival-time audit) and what the quote check says about them."""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

from monte_neo.verify.quotes import synthetic_quotes
from monte_neo.verify.quotes_verdict import verify_quotes
from monte_neo.verify.verdict import model_from_costs

MODEL = model_from_costs(commission_bps=0.2, slippage_bps=0.15)
BASE = synthetic_quotes(20_000, seed=1, rho=0.0)


def three_bar_trend(df: pd.DataFrame) -> np.ndarray:
    return np.sign(df["close"].diff(3).fillna(0.0).to_numpy())


def _crossed(q: pd.DataFrame) -> pd.DataFrame:
    q = q.copy()
    q.loc[q.index[::50], "bid"] = q.loc[q.index[::50], "ask"] + 0.5
    return q


def _negative_latency(q: pd.DataFrame) -> pd.DataFrame:
    return q.assign(latency_ms=q["latency_ms"] - 500.0)  # a clock offset between the exchange stamp and the receive time


def _non_positive(q: pd.DataFrame) -> pd.DataFrame:
    q = q.copy()
    q.loc[q.index[:100], "bid"] = -1.0
    return q


def _duplicates(q: pd.DataFrame) -> pd.DataFrame:
    return pd.concat([q, q.iloc[:200]])


def _frozen(q: pd.DataFrame) -> pd.DataFrame:
    q = q.copy()
    q.loc[q.index[1000:3000], ["bid", "ask"]] = q.loc[q.index[999], ["bid", "ask"]].to_numpy()
    return q


def _nan_bid(q: pd.DataFrame) -> pd.DataFrame:
    q = q.copy()
    q.loc[q.index[::997], "bid"] = np.nan
    return q


def _bursty(q: pd.DataFrame) -> pd.DataFrame:
    q = q.copy()
    q.loc[q.index[::40], "latency_ms"] = 5000.0  # a queue that releases in bursts
    return q


DEFECTS = [
    ("crossed_quotes", _crossed),
    ("negative_latency", _negative_latency),
    ("non_positive_price", _non_positive),
    ("duplicate_rows", _duplicates),
    ("frozen_feed", _frozen),
    ("unparseable_prices", _nan_bid),
    ("bursty_latency", _bursty),
]


def _quality(q: pd.DataFrame) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        report = verify_quotes(q, signal_fn=three_bar_trend, bar_ms=1000.0, model=MODEL, samples=4)
    return next(c for c in report["checks"] if c["id"] == "quote_quality")


@pytest.mark.parametrize("case", DEFECTS, ids=lambda c: c[0])
def test_each_quote_defect_is_flagged(case: tuple) -> None:
    name, make = case
    row = _quality(make(BASE))
    assert row["status"] == "warn", f"{name}: {row['summary']}"


def test_a_clean_table_and_a_shuffled_one_pass() -> None:
    assert _quality(BASE)["status"] == "pass"
    assert _quality(BASE.sample(frac=1.0, random_state=1))["status"] == "pass"  # the order of rows is not a defect


def test_a_missing_latency_needs_an_assumption_and_is_refused_otherwise() -> None:
    with pytest.raises(ValueError, match="latency_ms"):
        verify_quotes(BASE.drop(columns="latency_ms"), signal_fn=three_bar_trend, bar_ms=1000.0, model=MODEL, samples=4)
    report = verify_quotes(BASE.drop(columns="latency_ms"), signal_fn=three_bar_trend, bar_ms=1000.0, model=MODEL, samples=4, latency_model="constant:20")
    assert report["verdict"] in ("PASS", "PASS_WITH_WARNINGS", "NEEDS_MORE_EVIDENCE")


def test_a_huge_constant_latency_is_priced_by_the_latency_checks() -> None:
    q = BASE.assign(latency_ms=5000.0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        report = verify_quotes(q, signal_fn=three_bar_trend, bar_ms=1000.0, model=MODEL, samples=4)
    assert report["verdict"] != "PASS"
