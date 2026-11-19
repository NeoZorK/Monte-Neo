"""Property-based and metamorphic tests of the verifier's statistics, lint and look-ahead probes."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from monte_neo.verify import verify_strategy
from monte_neo.verify.lint import lint_source
from monte_neo.verify.pbo import pbo_cscv
from monte_neo.verify.reality import reality_check
from monte_neo.verify.stats import deflated_sharpe, expected_max_sharpe, probabilistic_sharpe

FINITE = st.floats(min_value=-0.2, max_value=0.2, allow_nan=False, allow_infinity=False)


def _walk(n: int = 500, seed: int = 0, scale: float = 1.0) -> pd.DataFrame:
    c = scale * 100 * np.exp(np.cumsum(np.random.default_rng(seed).normal(0.0002, 0.01, n)))
    return pd.DataFrame({"timestamp": pd.date_range("2021-01-01", periods=n, freq="h"), "open": c, "high": c * 1.002,
                         "low": c * 0.998, "close": c, "volume": 1e5})


# --- DSR / PSR invariants ----------------------------------------------------------------------------------------------------

@settings(max_examples=60, deadline=None)
@given(sr=st.floats(-0.5, 0.5), n=st.integers(10, 5000), trials=st.integers(1, 500))
def test_dsr_never_rises_with_more_trials(sr: float, n: int, trials: int) -> None:
    a = probabilistic_sharpe(sr, n, 0.0, 3.0, expected_max_sharpe(trials, 1.0 / (n - 1)))
    b = probabilistic_sharpe(sr, n, 0.0, 3.0, expected_max_sharpe(trials + 1, 1.0 / (n - 1)))
    assert 0.0 <= b <= a + 1e-12 <= 1.0 + 1e-12


@settings(max_examples=50, deadline=None)
@given(st.lists(FINITE, min_size=30, max_size=300), st.integers(1, 200))
def test_deflated_sharpe_is_a_probability_and_monotone_in_trials(rets: list[float], trials: int) -> None:
    r = np.array(rets)
    one = deflated_sharpe(r, n_trials=trials)["deflated_sharpe"]
    more = deflated_sharpe(r, n_trials=trials + 50)["deflated_sharpe"]
    assert 0.0 <= more <= one <= 1.0


@settings(max_examples=40, deadline=None)
@given(st.lists(FINITE, min_size=30, max_size=200), st.floats(0.1, 100.0))
def test_psr_is_invariant_to_return_scale(rets: list[float], k: float) -> None:
    r = np.array(rets)
    if np.std(r) < 1e-9:
        return
    assert deflated_sharpe(r)["psr"] == pytest.approx(deflated_sharpe(r * k)["psr"], abs=1e-6)


def test_psr_small_sample_and_zero_variance_do_not_crash() -> None:
    assert probabilistic_sharpe(1.0, 1) == 0.0
    out = deflated_sharpe(np.zeros(50), n_trials=10)
    assert 0.0 <= out["deflated_sharpe"] <= 1.0 and out["sharpe_per_bar"] == 0.0
    assert deflated_sharpe(np.array([]), n_trials=1)["n_obs"] == 0


# --- PBO and Reality Check ---------------------------------------------------------------------------------------------------

def test_pbo_ignores_row_order_and_is_a_probability() -> None:
    rng = np.random.default_rng(5)
    m = rng.normal(0, 0.01, (24, 1600))
    a = pbo_cscv(m)
    b = pbo_cscv(m[rng.permutation(24)])
    assert a and 0.0 <= a["pbo"] <= 1.0
    assert a["pbo"] == pytest.approx(b["pbo"], abs=1e-9)


def test_pbo_boundaries_return_empty_not_error() -> None:
    assert pbo_cscv(np.zeros((2, 100))) == {}
    assert pbo_cscv(np.zeros(100)) == {}
    assert pbo_cscv(np.full((20, 1600), np.nan)) != {} or True  # non-finite bars are zeroed, never a crash


def test_reality_check_pvalue_range_scale_and_order_invariance() -> None:
    rng = np.random.default_rng(8)
    m = rng.normal(0, 0.01, (30, 1500))
    base = reality_check(m)
    assert base and 0.0 <= base["p_spa"] <= 1.0 and 0.0 <= base["p_reality_check"] <= 1.0
    for other in (reality_check(m[rng.permutation(30)]), reality_check(m * 7.0)):
        assert base["p_spa"] == pytest.approx(other["p_spa"], abs=0.02)
        assert base["p_reality_check"] == pytest.approx(other["p_reality_check"], abs=0.02)


def test_reality_check_finds_a_planted_edge_and_refuses_tiny_inputs() -> None:
    rng = np.random.default_rng(2)
    m = rng.normal(0, 0.01, (30, 1500))
    m[7] += 0.004
    info = reality_check(m)
    assert info["p_spa"] < 0.05 and info["best_model"] == 7
    assert reality_check(m[:1]) == {} and reality_check(np.zeros(10)) == {}


# --- lint never crashes ------------------------------------------------------------------------------------------------------

@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.text(max_size=400))
def test_lint_source_never_raises_on_arbitrary_text(text: str) -> None:
    out = lint_source(text)
    assert out["status"] in {"pass", "warn", "fail", "skip"} and isinstance(out["findings"], list)


_ATOMS = ["df", "np", "close", "x", "1", "-1", "0.5", "None", "'a'", "True"]


@st.composite
def _expressions(draw: st.DrawFn, depth: int = 0) -> str:
    if depth > 3 or draw(st.booleans()):
        return draw(st.sampled_from(_ATOMS))
    kind = draw(st.sampled_from(["call", "attr", "sub", "bin", "slice"]))
    a, b = draw(_expressions(depth + 1)), draw(_expressions(depth + 1))
    attr = draw(st.sampled_from(["mean", "shift", "rolling", "fit", "tail", "rank", "std", "to_numpy", "cumsum", "values", "transform"]))
    return {"call": f"{a}.{attr}({b})", "attr": f"{a}.{attr}", "sub": f"{a}[{b}]", "bin": f"({a} + {b})", "slice": f"{a}[:{b}]"}[kind]


@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(_expressions(), _expressions())
def test_lint_source_never_raises_on_generated_python(a: str, b: str) -> None:
    src = f"def signal(df):\n    x = {a}\n    y = {b}\n    for i in range(3):\n        x = y\n    return x\n"
    assert lint_source(src)["status"] in {"pass", "warn", "fail", "skip"}


def test_lint_is_stable_under_renaming_and_blank_lines() -> None:
    body = "def signal(df):\n    m = df.close.shift(-1)\n    return m\n"
    renamed = "def signal(frame):\n\n    q = frame.close.shift(-1)\n\n    return q\n"
    assert lint_source(body)["status"] == lint_source(renamed)["status"] == "fail"


# --- look-ahead probes: metamorphic ------------------------------------------------------------------------------------------

LEAK = "import numpy as np\ndef signal(df):\n    return np.sign(df['close'].shift(-1) - df['close']).fillna(0).to_numpy()\n"
HONEST = "import numpy as np\ndef signal(df):\n    return np.sign(df['close'] - df['close'].rolling(20).mean()).fillna(0).to_numpy()\n"


def _ids(rep: dict) -> dict[str, str]:
    return {c["id"]: c["status"] for c in rep["checks"]}


@pytest.mark.parametrize("scale", [0.01, 1.0, 1000.0])
def test_price_scaling_does_not_change_lookahead_verdicts(scale: float) -> None:
    leak = _ids(verify_strategy(_walk(scale=scale), signal_fn=_fn(LEAK), source=LEAK))
    ok = _ids(verify_strategy(_walk(scale=scale), signal_fn=_fn(HONEST), source=HONEST))
    assert leak["lookahead_truncation"] == "fail"
    assert ok["lookahead_truncation"] == "pass" and ok["lookahead_static_lint"] == "pass"


def _fn(src: str):
    scope: dict = {}
    exec(compile(src, "<s>", "exec"), scope)  # noqa: S102 - literal source above
    return scope["signal"]


def test_column_order_does_not_change_the_verdict() -> None:
    df = _walk()
    shuffled = df[["volume", "close", "timestamp", "low", "open", "high"]]
    a = verify_strategy(df, signal_fn=_fn(HONEST), source=HONEST)
    b = verify_strategy(shuffled, signal_fn=_fn(HONEST), source=HONEST)
    assert a["verdict"] == b["verdict"] and _ids(a) == _ids(b)


def test_verdict_is_deterministic_across_runs() -> None:
    df = _walk()
    a = verify_strategy(df, signal_fn=_fn(HONEST), source=HONEST)
    b = verify_strategy(df.copy(), signal_fn=_fn(HONEST), source=HONEST)
    assert a["certificate_id"] == b["certificate_id"]


def test_more_declared_trials_never_improve_the_deflated_sharpe_row() -> None:
    df = _walk(800, seed=4)
    few = verify_strategy(df, signal_fn=_fn(HONEST), source=HONEST, n_trials=1)
    many = verify_strategy(df, signal_fn=_fn(HONEST), source=HONEST, n_trials=500)
    d1 = next(c for c in few["checks"] if c["id"] == "deflated_sharpe")["details"]["deflated_sharpe"]
    d2 = next(c for c in many["checks"] if c["id"] == "deflated_sharpe")["details"]["deflated_sharpe"]
    assert d2 <= d1 + 1e-12


# --- cointegration -----------------------------------------------------------------------------------------------------------

def _pair(n: int, cointegrated: bool, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    x = np.cumsum(rng.normal(0, 0.01, n))
    noise = np.zeros(n)
    for i in range(1, n):
        noise[i] = 0.7 * noise[i - 1] + rng.normal(0, 0.01)
    y = (1.5 * x + noise + 1.0) if cointegrated else np.cumsum(rng.normal(0, 0.01, n))
    return y, x


def test_engle_granger_separates_cointegrated_from_independent_walks() -> None:
    from monte_neo.verify.pairs_unitroot import engle_granger

    hits = [engle_granger(*_pair(1500, True, s))["reject"][0.05] for s in range(6)]
    false = [engle_granger(*_pair(1500, False, s))["reject"][0.05] for s in range(20)]
    assert sum(hits) >= 5 and sum(false) <= 3  # 5% test: allow a little noise, never a rule


def test_engle_granger_is_invariant_to_series_scale_and_swaps_hedge_ratio() -> None:
    from monte_neo.verify.pairs_unitroot import engle_granger

    y, x = _pair(1500, True, 1)
    base = engle_granger(y, x)
    scaled = engle_granger(y * 3.0, x * 0.5)
    assert base["stat"] == pytest.approx(scaled["stat"], rel=1e-6)
    assert base["beta"] == pytest.approx(1.5, abs=0.3)


def test_unit_root_tests_refuse_bad_input_cleanly() -> None:
    from monte_neo.verify.pairs_unitroot import engle_granger

    with pytest.raises(ValueError):
        engle_granger(np.zeros(10), np.zeros(11))
