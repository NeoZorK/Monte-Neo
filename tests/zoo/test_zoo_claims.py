"""Claims against verified numbers: overclaims fail, equal or modest claims pass, spellings of one value agree (class A7)."""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "traps"))
from trap_data import planted_momentum_ohlcv  # noqa: E402

from monte_neo.verify import verify_strategy  # noqa: E402

DF = planted_momentum_ohlcv()
KEYS = ("sharpe", "total_return", "max_drawdown", "n_trades", "win_rate", "profit_factor")


def _momentum(d):  # noqa: ANN001, ANN202
    return np.where(d["close"].pct_change(1).rolling(8).mean() > 0, 1, -1)


def _verify(claim: dict) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return verify_strategy(DF, signal_fn=_momentum, claim=claim)


def _row(report: dict) -> dict:
    return next(c for c in report["checks"] if c["id"] == "claim_consistency")


@pytest.fixture(scope="module")
def verified() -> dict[str, float]:
    metrics = _row(_verify({k: 0.0 for k in KEYS}))["details"]["metrics"]
    return {k: float(v["verified"]) for k, v in metrics.items()}


def _inflate(key: str, value: float) -> float:
    """A claim clearly better than the verified number."""
    if key == "max_drawdown":
        return value / 4.0
    if key == "win_rate":
        return min(0.99, value + 0.25)
    return value * 2.0 + 1.0 if key in ("sharpe", "profit_factor", "n_trades") else value * 2.0 + 0.2


@pytest.mark.parametrize("key", KEYS)
def test_equal_modest_and_inflated_claims(key: str, verified: dict[str, float]) -> None:
    v = verified[key]
    assert _row(_verify({key: v}))["status"] == "pass", "the verified number itself must match"
    modest = v * 1.5 if key == "max_drawdown" else (v * 0.5 if v > 0 else v - 0.5)
    assert _row(_verify({key: modest}))["status"] == "pass", "a more modest claim is not an overclaim"
    assert _row(_verify({key: _inflate(key, v)}))["status"] == "fail", "an inflated claim must fail"


def test_aliases_and_spellings_of_one_value_agree(verified: dict[str, float]) -> None:
    r = verified["total_return"]
    spellings = [{"total_return": r}, {"return": r}, {"net_return": r}, {"total_return": f"{r * 100:.6f}%"}]
    statuses = {_row(_verify(c))["status"] for c in spellings}
    assert statuses == {"pass"}
    inflated = _inflate("total_return", r)
    for claim in ({"total_return": inflated}, {"return": f"{inflated * 100}%"}):
        assert _row(_verify(claim))["status"] == "fail"
    assert _row(_verify({"sharpe_ratio": _inflate("sharpe", verified["sharpe"])}))["status"] == "fail"
    assert _row(_verify({"drawdown": f"{verified['max_drawdown'] * 100:.6f}%"}))["status"] == "pass"


def test_one_overclaim_among_honest_numbers_fails_the_check(verified: dict[str, float]) -> None:
    claim = {k: verified[k] for k in KEYS}
    claim["sharpe"] = _inflate("sharpe", verified["sharpe"])
    row = _row(_verify(claim))
    assert row["status"] == "fail" and row["details"]["metrics"]["sharpe"]["status"] == "overclaimed"
    assert row["details"]["metrics"]["total_return"]["status"] == "matches"


@pytest.mark.parametrize(
    "claim",
    [{"nonsense": 1}, {"sharpe": float("nan")}, {"sharpe": 1, "sharpe_ratio": 2}, {}, {"sharpe": "abc"}],
)
def test_malformed_claims_are_refused(claim: dict) -> None:
    with pytest.raises(ValueError):
        _verify(claim)
