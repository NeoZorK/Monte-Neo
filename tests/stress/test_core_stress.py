"""Stress and performance guards for the verifier core (generous limits: they catch an order-of-magnitude regression, not noise)."""

from __future__ import annotations

import os
import time

import numpy as np
import pandas as pd
import pytest

from monte_neo.verify import verify_strategy
from monte_neo.verify.lint import lint_source
from monte_neo.verify.pbo import pbo_cscv
from monte_neo.verify.reality import reality_check
from monte_neo.verify.stats import deflated_sharpe

SRC = "import numpy as np\ndef signal(df):\n    return np.sign(df['close'] - df['close'].rolling(20).mean()).fillna(0).to_numpy()\n"


def _frame(n: int, seed: int = 0) -> pd.DataFrame:
    c = 100 * np.exp(np.cumsum(np.random.default_rng(seed).normal(0, 0.001, n)))
    return pd.DataFrame({"timestamp": pd.date_range("2000-01-01", periods=n, freq="min"), "open": c, "high": c * 1.0005,
                         "low": c * 0.9995, "close": c, "volume": 1e5})


def _fn():
    scope: dict = {}
    exec(compile(SRC, "<s>", "exec"), scope)  # noqa: S102 - literal source above
    return scope["signal"]


def _timed(fn, limit: float, label: str):
    start = time.perf_counter()
    out = fn()
    took = time.perf_counter() - start
    assert took < limit, f"{label} took {took:.1f}s, limit {limit}s"
    return out


@pytest.mark.stress
@pytest.mark.performance
def test_statistics_on_a_million_bars_are_fast_and_finite() -> None:
    rets = np.random.default_rng(0).normal(0.0, 0.01, 1_000_000)
    out = _timed(lambda: deflated_sharpe(rets, n_trials=200), 10.0, "deflated_sharpe on 1e6 bars")
    assert np.isfinite(out["deflated_sharpe"]) and 0.0 <= out["deflated_sharpe"] <= 1.0


@pytest.mark.stress
@pytest.mark.performance
def test_pbo_and_reality_check_on_a_wide_matrix() -> None:
    m = np.random.default_rng(1).normal(0.0, 0.01, (40, 100_000))
    assert _timed(lambda: pbo_cscv(m), 30.0, "pbo")["pbo"] >= 0.0
    assert 0.0 <= _timed(lambda: reality_check(m), 60.0, "reality check")["p_spa"] <= 1.0


@pytest.mark.stress
@pytest.mark.performance
def test_lint_of_a_nine_thousand_line_file() -> None:
    src = "\n".join(f"def f{i}(df):\n    x = df.close.rolling({i % 30 + 2}).mean()\n    return x - df.close.shift(1)\n" for i in range(3000))
    assert _timed(lambda: lint_source(src), 30.0, "lint of 9000 lines")["status"] in {"pass", "warn", "fail"}


@pytest.mark.stress
@pytest.mark.performance
def test_full_verification_of_fifty_thousand_bars() -> None:
    rep = _timed(lambda: verify_strategy(_frame(50_000), signal_fn=_fn(), source=SRC), 180.0, "verify 50k bars")
    assert rep["verdict"] in {"REJECT", "NEEDS_MORE_EVIDENCE", "PASS_WITH_WARNINGS", "PASS"}
    assert next(c for c in rep["checks"] if c["id"] == "lookahead_truncation")["status"] == "pass"


@pytest.mark.stress
@pytest.mark.skipif(not os.environ.get("MONTE_NEO_STRESS_1M"), reason="set MONTE_NEO_STRESS_1M=1 for the million-bar verification (minutes)")
def test_full_verification_of_a_million_bars() -> None:
    rep = verify_strategy(_frame(1_000_000), signal_fn=_fn(), source=SRC)
    assert rep["verdict"] in {"REJECT", "NEEDS_MORE_EVIDENCE", "PASS_WITH_WARNINGS", "PASS"}


@pytest.mark.stress
@pytest.mark.parametrize("damage", ["nan", "inf", "duplicates", "reversed", "constant", "zero_volume"])
def test_damaged_tables_get_a_verdict_or_a_clear_error(damage: str) -> None:
    df = _frame(600)
    if damage == "nan":
        df.loc[[10, 50], "close"] = np.nan
    elif damage == "inf":
        df.loc[20, "high"] = np.inf
    elif damage == "duplicates":
        df = pd.concat([df, df.iloc[:5]], ignore_index=True)
    elif damage == "reversed":
        df = df.iloc[::-1].reset_index(drop=True)
    elif damage == "constant":
        df[["open", "high", "low", "close"]] = 100.0
    else:
        df["volume"] = 0.0
    try:
        rep = verify_strategy(df, signal_fn=_fn(), source=SRC)
    except ValueError as exc:  # a refusal must say why
        assert str(exc)
        return
    assert rep["verdict"] in {"REJECT", "NEEDS_MORE_EVIDENCE", "PASS_WITH_WARNINGS", "PASS"}
    if damage in {"nan", "inf", "duplicates", "reversed"}:
        di = next(c for c in rep["checks"] if c["id"] == "data_integrity")
        assert di["status"] in {"warn", "fail"}, damage


@pytest.mark.stress
@pytest.mark.parametrize("frame", [pd.DataFrame(), pd.DataFrame({"close": []})])
def test_empty_or_tiny_tables_raise_a_clear_value_error(frame: pd.DataFrame) -> None:
    with pytest.raises((ValueError, KeyError)) as info:
        verify_strategy(frame, signal_fn=_fn(), source=SRC)
    assert str(info.value)


@pytest.mark.stress
def test_a_three_bar_table_never_earns_a_pass() -> None:
    try:
        rep = verify_strategy(_frame(3), signal_fn=_fn(), source=SRC)
    except ValueError as exc:
        assert str(exc)
        return
    assert rep["verdict"] in {"REJECT", "NEEDS_MORE_EVIDENCE"}
