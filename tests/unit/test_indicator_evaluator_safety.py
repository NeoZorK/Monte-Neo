"""Dynamic indicator expressions run in a restricted namespace."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from monte_neo.indicators.evaluator import _check_expression, compile_source


@pytest.fixture()
def data() -> pd.DataFrame:
    close = pd.Series(np.linspace(1.0, 2.0, 60))
    return pd.DataFrame({"open": close, "high": close, "low": close, "close": close, "volume": 1.0})


def test_normal_expressions_still_compile(data: pd.DataFrame) -> None:
    fn = compile_source("np.where(sma(data, 5) > data['close'].shift(1), 1, 0)")
    assert len(fn(data, np, pd)) == 60
    fn = compile_source("max(len(data), 3) * data['close']")
    assert float(fn(data, np, pd).iloc[-1]) == pytest.approx(120.0)


@pytest.mark.parametrize(
    "source",
    [
        "().__class__.__bases__[0].__subclasses__()",
        "__import__('os').system('true')",
        "data.__class__",
        "np.__dict__",
    ],
)
def test_escapes_fall_back_to_the_safe_expression(source: str, data: pd.DataFrame) -> None:
    fn = compile_source(source)
    assert fn(data, np, pd).equals(data["close"])  # the documented safe fallback


@pytest.mark.parametrize("source", ["data.__class__", "__import__('os')", "np._core"])
def test_the_checker_names_the_reason(source: str) -> None:
    with pytest.raises(ValueError, match="not allowed"):
        _check_expression(source)


@pytest.mark.parametrize("source", ["open('/etc/passwd').read()", "eval('1')", "exec('1')", "compile('1', 'x', 'eval')"])
def test_dangerous_builtins_do_not_exist_in_the_namespace(source: str, data: pd.DataFrame) -> None:
    fn = compile_source(source)
    with pytest.raises(NameError):
        fn(data, np, pd)
