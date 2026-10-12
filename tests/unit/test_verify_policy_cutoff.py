"""Risk policy as code (``policy``) and the model training cutoff check (``model_cutoff``)."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.verify import recheck_certificate, verify_strategy
from monte_neo.verify.cutoff import cutoff_row, parse_cutoff
from monte_neo.verify.policy import TEMPLATE, apply_policy, load_policy, policy_row

STRICT = """
[policy]
name = "strict"
version = "1"
on_breach = "reject"
[inputs]
min_trades = 40
cost_multiplier = 2.0
[rules]
allow_warnings = false
min_deflated_sharpe = 0.95
required_checks = ["lookahead_truncation"]
"""
LENIENT = """
[policy]
name = "lenient"
[rules]
allow_warnings = true
"""


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    return synthetic_ohlcv(800, seed=5)


def _momentum(df: pd.DataFrame) -> pd.Series:
    return pd.Series(np.sign(df["close"].pct_change(10).fillna(0.0)).to_numpy())


def test_template_loads_and_hash_is_stable() -> None:
    a, b = load_policy(TEMPLATE), load_policy(TEMPLATE)
    assert a["sha256"] == b["sha256"] and a["policy"]["name"] == "my-policy"
    assert load_policy(a)["sha256"] == a["sha256"]  # a recorded policy reloads to the same hash


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("[rules]\nallow_warnings = true", "name is required"),
        ("[policy]\nname='x'\n[odd]\na=1", "unknown policy section"),
        ("[policy]\nname='x'\n[rules]\nmin_sharpe='high'", "must be float"),
        ("[policy]\nname='x'\non_breach='maybe'", "on_breach"),
        ("[policy]\nname='x'\n[inputs]\ncost_multiplier=0", "cost_multiplier"),
        ("not = = toml", "not valid TOML"),
    ],
)
def test_bad_policies_are_explained(text: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        load_policy(text)


def test_same_strategy_two_policies_two_verdicts(df: pd.DataFrame) -> None:
    strict = verify_strategy(df, signals=_momentum(df), policy=STRICT, probe_checks=4)
    lenient = verify_strategy(df, signals=_momentum(df), policy=LENIENT, probe_checks=4)
    row = next(c for c in strict["checks"] if c["id"] == "policy")
    assert row["status"] == "fail" and strict["verdict"] == "REJECT"
    assert any("required check lookahead_truncation" in b for b in row["details"]["breaches"])  # no code: probe skipped
    assert next(c for c in lenient["checks"] if c["id"] == "policy")["status"] == "pass"
    assert strict["reproducibility"]["policy"]["policy"]["name"] == "strict"
    assert strict["reproducibility"]["settings"]["min_trades"] == 40  # inputs applied before the run
    assert strict["reproducibility"]["model"]["commission_bps"] == pytest.approx(2 * lenient["reproducibility"]["model"]["commission_bps"])
    assert strict["certificate_id"] != lenient["certificate_id"]


def test_needs_more_evidence_mode_and_reapplication(df: pd.DataFrame) -> None:
    report = verify_strategy(df, signals=_momentum(df), probe_checks=4)
    soft = apply_policy(report, STRICT.replace('on_breach = "reject"', 'on_breach = "needs_more_evidence"'))
    assert next(c for c in soft["checks"] if c["id"] == "policy")["category"] == "statistics"
    again = apply_policy(soft, soft["reproducibility"]["policy"])  # applying twice keeps one policy row
    assert [c["id"] for c in again["checks"]].count("policy") == 1
    assert again["certificate_id"] == soft["certificate_id"]


def test_policy_certificate_rechecks(df: pd.DataFrame, tmp_path) -> None:
    sig = _momentum(df).to_numpy()
    cert = json.loads(json.dumps(verify_strategy(df, signals=sig, policy=STRICT, probe_checks=4)))
    result = recheck_certificate(cert, df, signals=sig)
    assert result["reproduced"], result


def test_policy_metric_limits() -> None:
    report = {"checks": [], "metrics": {"deflated_sharpe": 0.5, "sharpe_annualized": 1.2, "max_drawdown": -0.4}}
    rules = load_policy("[policy]\nname='p'\n[rules]\nmin_deflated_sharpe=0.9\nmin_sharpe=1.0\nmax_drawdown=0.25")
    breaches = policy_row(report, rules)["details"]["breaches"]
    assert len(breaches) == 2 and any("Deflated Sharpe" in b for b in breaches) and any("drawdown" in b for b in breaches)


def _stamps(n: int) -> pd.DatetimeIndex:
    return pd.date_range("2022-01-01", periods=n, freq="D")


def test_cutoff_catches_an_edge_that_ends_at_the_cutoff() -> None:
    rng = np.random.default_rng(1)
    n = 600
    rets = rng.normal(0.0, 0.01, n)
    rets[:300] += 0.004  # a strong edge only in the "remembered" period
    rets[300:] -= 0.001
    row = cutoff_row(rets, _stamps(n), str(_stamps(n)[300].date()), 252.0)
    assert row["status"] == "fail" and row["category"] == "lookahead"
    assert row["details"]["sharpe_before"] > 2 and row["details"]["sharpe_after"] <= 0


def test_cutoff_passes_an_edge_that_survives_and_skips_short_sides() -> None:
    rng = np.random.default_rng(2)
    rets = rng.normal(0.002, 0.01, 600)
    assert cutoff_row(rets, _stamps(600), "2022-09", 252.0)["status"] == "pass"
    assert cutoff_row(rets, _stamps(600), "2021-01", 252.0)["status"] == "skip"


def test_cutoff_in_verify_and_recheck(df: pd.DataFrame) -> None:
    sig = _momentum(df).to_numpy()
    stamps = pd.to_datetime(df["timestamp"]) if "timestamp" in df else df.index
    middle = str(pd.Timestamp(stamps.iloc[len(df) // 2] if hasattr(stamps, "iloc") else stamps[len(df) // 2]).date())
    report = json.loads(json.dumps(verify_strategy(df, signals=sig, model_cutoff=middle, probe_checks=4)))
    assert any(c["id"] == "model_cutoff" for c in report["checks"])
    assert report["reproducibility"]["settings"]["model_cutoff"] == middle
    assert recheck_certificate(report, df, signals=sig)["reproduced"]
    plain = verify_strategy(df, signals=sig, probe_checks=4)
    assert "model_cutoff" not in plain["reproducibility"]["settings"]  # old certificates keep their ids


def test_parse_cutoff() -> None:
    assert parse_cutoff("2024-06") == pd.Timestamp("2024-06-01")
    with pytest.raises(ValueError, match="YYYY-MM"):
        parse_cutoff("June 2024x")
