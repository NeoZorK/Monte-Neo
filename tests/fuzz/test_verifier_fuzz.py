"""Property-based fuzzing of the verifier's untrusted inputs (Hypothesis).

Certificates, cost tables, price arrays and position vectors come from outside. Whatever they contain,
the verifier must return a result or raise a ``ValueError``: never another exception type, never a hang.
"""

from __future__ import annotations

import json

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.verify import verify_strategy
from monte_neo.verify.microstructure import corwin_schultz
from monte_neo.verify.recheck import load_certificate
from monte_neo.verify.report_html import render_html
from monte_neo.verify.symbol_costs import parse_symbol_costs

VERDICTS = {"PASS", "PASS_WITH_WARNINGS", "NEEDS_MORE_EVIDENCE", "REJECT"}

json_values = st.recursive(
    st.none() | st.booleans() | st.integers() | st.floats(allow_nan=True, allow_infinity=True) | st.text(max_size=12),
    lambda children: st.lists(children, max_size=4) | st.dictionaries(st.text(max_size=8), children, max_size=4),
    max_leaves=12,
)


@settings(max_examples=200, deadline=None)
@given(st.text(max_size=300))
def test_certificate_text_never_raises_anything_but_value_error(text: str) -> None:
    try:
        load_certificate(text if text.strip().startswith("{") else json.dumps(text))
    except (ValueError, OSError):
        pass


@settings(max_examples=200, deadline=None)
@given(json_values)
def test_certificate_objects_are_accepted_or_refused_cleanly(value: object) -> None:
    if not isinstance(value, dict):
        value = {"schema": value}
    try:
        cert = load_certificate(value)
    except ValueError:
        return
    assert cert["schema"] == "strategy-verdict/1"


@settings(max_examples=200, deadline=None)
@given(json_values)
def test_cost_tables_are_validated_or_refused(spec: object) -> None:
    if not isinstance(spec, dict):
        spec = {"AAA": spec}
    try:
        out = parse_symbol_costs(spec)
    except ValueError:
        return
    for row in out.values():
        assert all(np.isfinite(v) and v >= 0 for v in row.values())


@pytest.mark.filterwarnings("ignore::RuntimeWarning")  # absurd prices overflow the log ratios; the result stays finite or NaN
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    st.lists(st.floats(allow_nan=True, allow_infinity=True), min_size=0, max_size=40),
    st.lists(st.floats(allow_nan=True, allow_infinity=True), min_size=0, max_size=40),
)
def test_spread_estimate_survives_any_prices(high: list[float], low: list[float]) -> None:
    n = min(len(high), len(low))
    est = corwin_schultz(np.array(high[:n]), np.array(low[:n]))
    assert est.shape == (max(n - 1, 0),)
    assert not np.isinf(est).any()


@settings(max_examples=60, deadline=None)
@given(json_values)
def test_html_report_renders_any_certificate_shape(value: object) -> None:
    report = value if isinstance(value, dict) else {"verdict": value}
    page = render_html(report)
    assert isinstance(page, str) and page.lower().startswith("<!doctype html>")


_DF = synthetic_ohlcv(400, seed=5)


@settings(max_examples=12, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(st.integers(min_value=-1, max_value=1), min_size=len(_DF), max_size=len(_DF)))
def test_any_position_vector_gets_a_verdict_and_a_stable_certificate(positions: list[int]) -> None:
    signals = np.array(positions)
    first = verify_strategy(_DF, signals=signals)
    assert first["verdict"] in VERDICTS
    assert verify_strategy(_DF, signals=signals)["certificate_id"] == first["certificate_id"]


@pytest.mark.parametrize("bad", [[np.nan] * 400, [np.inf] * 400, [2.0] * 400])
def test_non_finite_or_out_of_range_positions_are_refused_not_crashed(bad: list[float]) -> None:
    try:
        report = verify_strategy(_DF, signals=np.array(bad))
    except ValueError:
        return
    assert report["verdict"] in VERDICTS
