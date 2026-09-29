"""Input robustness: broken bars, unhelpful errors, MCP error reporting, fast entry point."""

from __future__ import annotations

import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.cli import entry
from monte_neo.mcp import tools
from monte_neo.mcp.server import reporting_errors
from monte_neo.verify import checks as rows
from monte_neo.verify import verify_strategy


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    return synthetic_ohlcv(400, seed=4)


@pytest.mark.parametrize(("column", "ref", "factor"), [("close", "high", 1.2), ("open", "low", 0.5)])
def test_open_or_close_outside_the_range_fails(df, column: str, ref: str, factor: float) -> None:
    broken = df.copy()
    broken.loc[100, column] = broken.loc[100, ref] * factor
    report = verify_strategy(broken, signals=np.ones(len(df)))
    row = report["checks"][0]
    assert report["verdict"] == "REJECT" and row["details"]["open_close_outside_range"] == 1
    assert "open/close outside high-low" in row["summary"]


def test_rounding_gaps_are_counted_not_failed() -> None:
    ohlc = {"open": np.array([100.0, 100.0]), "high": np.array([101.0, 101.0]),
            "low": np.array([99.0, 99.0]), "close": np.array([101.05, 100.0])}
    row = rows.data_integrity(ohlc)
    assert row["status"] == "pass" and row["details"]["rounding_outside_range"] == 1


@pytest.mark.parametrize(
    ("fn", "message"),
    [
        (lambda d: None, "returned None"),
        (lambda d: 1, "single value"),
        (lambda d: np.array(["buy"] * len(d)), "positions must be numbers"),
    ],
)
def test_signal_errors_say_what_to_fix(df, fn, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        verify_strategy(df, signal_fn=fn)


def test_universe_rows_without_symbol(df) -> None:
    uni = pd.concat([df.assign(symbol="A"), df.assign(symbol="B")], ignore_index=True)
    uni.loc[3, "symbol"] = None
    with pytest.raises(ValueError, match="1 rows have no symbol"):
        verify_strategy(uni, signals=np.ones(len(uni)))


def test_mcp_errors_reach_the_agent() -> None:
    wrapped = reporting_errors(tools.verify_strategy)
    out = wrapped("/no/such/file.csv", strategy_path="x.py")
    assert out["tool"] == "verify_strategy" and out["error"].startswith("FileNotFoundError")
    assert wrapped.__wrapped__ is tools.verify_strategy  # the SDK reads the signature through it
    assert reporting_errors(lambda: {"ok": 1})() == {"ok": 1}


def test_entry_point_dispatch(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["monte-neo", "--version"])
    assert entry.main() == 0 and capsys.readouterr().out.startswith("monte-neo v")
    calls = []
    import monte_neo.cli.bench_cmd as bench_cmd
    import monte_neo.cli.verify_cmd as verify_cmd
    import monte_neo.mcp.server as server
    from monte_neo.cli import app

    monkeypatch.setattr(verify_cmd, "main", lambda argv: calls.append(("verify", argv)) or 0)
    monkeypatch.setattr(bench_cmd, "main", lambda argv: calls.append(("bench", argv)) or 0)
    monkeypatch.setattr(server, "main", lambda argv: calls.append(("mcp", argv)) or 0)
    monkeypatch.setattr(app, "main", lambda: calls.append(("app", [])) or 0)
    for argv in (["verify", "--schema"], ["bench", "x"], ["mcp"], []):
        monkeypatch.setattr(sys, "argv", ["monte-neo", *argv])
        assert entry.main() == 0
    assert [c[0] for c in calls] == ["verify", "bench", "mcp", "app"]
    assert calls[0][1] == ["--schema"]


def test_cli_package_is_lazy() -> None:
    code = "import sys, monte_neo.cli.verify_cmd; print('monte_neo.cli.menu' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"
    import monte_neo.cli as cli

    assert cli.ProgressTracker.__name__ == "ProgressTracker"
    with pytest.raises(AttributeError):
        cli.nothing_here  # noqa: B018


def test_journal_free_engine_matches_full_backtest() -> None:
    """The verifier's journal-free path returns the same numbers as the full backtest, bit for bit."""
    from monte_neo.backtest import synthetic_ohlcv
    from monte_neo.backtest.bar_engine import run_bar_backtest, run_bar_equity
    from monte_neo.backtest.model import ExecutionModel

    df = synthetic_ohlcv(2000, seed=4)
    ohlc = [df[k].to_numpy() for k in ("open", "high", "low", "close")]
    signal = np.where(np.arange(len(df)) % 3 == 0, 1, -1)
    model = ExecutionModel(commission_bps=5.0, slippage_bps=5.0, side_mode="long_short", warmup_bars=20)
    full = run_bar_backtest(*ohlc, signal, model=model)
    lean = run_bar_equity(*ohlc, signal, model=model)
    assert np.array_equal(full["equity"], lean["equity"])
    for key in ("total_return", "max_drawdown", "n_trades", "n_closed_trades", "final_cash"):
        assert full[key] == lean[key]
    assert lean["n_closed_trades"] > 500


def test_engines_compile_without_a_writable_cache(monkeypatch) -> None:
    """No writable cache location (read-only container): compile in memory instead of failing."""
    import monte_neo.backtest.jit as jit

    real = jit.numba.njit
    calls = []

    def no_cache(*args, **kwargs):
        calls.append(kwargs.get("cache"))
        if kwargs.get("cache"):
            raise RuntimeError("cannot cache function: no locator available")
        return real(*args, **kwargs)

    monkeypatch.setattr(jit.numba, "njit", no_cache)

    def add_one(x):
        return x + 1

    compiled = jit.njit_cached(add_one)
    assert compiled(1) == 2
    assert compiled.py_func is add_one
    assert calls[:2] == [True, False]

    def other(x):
        return x

    with pytest.raises(RuntimeError):  # only cache errors are absorbed
        monkeypatch.setattr(jit.numba, "njit", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
        jit.njit(parallel=True)(other)


_NO_NUMBA_SCRIPT = """
import sys
{block}
import warnings
warnings.simplefilter("ignore")
import numpy as np
from monte_neo.backtest import synthetic_ohlcv
from monte_neo.backtest.jit import HAS_NUMBA
from monte_neo.verify import verify_strategy
df = synthetic_ohlcv(1500, seed=3)
sig = np.sign(np.sin(np.arange(len(df)) / 9.0)).astype(np.int64)
a = verify_strategy(df, signals=sig, n_trials=3)
b = verify_strategy(df, signals=0.5 * sig)
print(HAS_NUMBA, a["certificate_id"], b["certificate_id"], a["metrics"]["total_return"], b["metrics"]["total_return"])
"""


def test_verifier_without_numba_gives_identical_results() -> None:
    """The plain-Python engines produce the same certificates bit for bit (no Numba installed)."""
    import subprocess
    import sys

    def run(block: str) -> list[str]:
        script = _NO_NUMBA_SCRIPT.format(block=block)
        out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True)
        return out.stdout.split()

    with_numba = run("")
    without = run('sys.modules["numba"] = None  # makes "import numba" fail')
    assert with_numba[0] == "True" and without[0] == "False"
    assert with_numba[1:] == without[1:]


def test_slow_hint_only_without_numba_on_large_runs(monkeypatch) -> None:
    import warnings

    import monte_neo.backtest.jit as jit

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        monkeypatch.setattr(jit, "HAS_NUMBA", True)
        jit.warn_if_slow(10**6)  # with Numba: silent
        monkeypatch.setattr(jit, "HAS_NUMBA", False)
        jit.warn_if_slow(jit.SLOW_BARS - 1)  # small: silent
    with pytest.warns(RuntimeWarning, match=r"monte-neo\[fast\]"):
        jit.warn_if_slow(jit.SLOW_BARS)


def test_jit_helpers_without_numba(monkeypatch) -> None:
    """Without Numba the decorators return the plain function and ``prange`` is ``range``."""
    import monte_neo.backtest.jit as jit

    monkeypatch.setattr(jit, "HAS_NUMBA", False)

    def f(x):
        return x

    assert jit.njit(f) is f
    assert jit.njit(cache=True, parallel=True)(f) is f
    assert jit.njit_cached(f) is f
