"""Strategy code in worker processes: same results, time limits, isolation, outside data."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.verify import executor as ex
from monte_neo.verify import recheck_certificate, verify_grid, verify_strategy
from monte_neo.verify.executor import FULL, Head, ProcessRunner, StrategyError, StrategyTimeoutError

TRAPS = Path(__file__).parents[1] / "traps" / "strategies"


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    return synthetic_ohlcv(1200, seed=5)


def _write(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / f"{name}.py"
    path.write_text(body, encoding="utf-8")
    return path


def test_workers_give_the_same_certificate(df) -> None:
    serial = verify_strategy(df, strategy=TRAPS / "sma_cross.py")
    parallel = verify_strategy(df, strategy=TRAPS / "sma_cross.py", jobs=2, timeout=60)
    assert serial["certificate_id"] == parallel["certificate_id"]
    leak = verify_strategy(df, strategy=TRAPS / "lookahead_shift.py", jobs=2)
    assert leak["verdict"] == "REJECT"


def test_time_limit(df, tmp_path: Path) -> None:
    slow = _write(tmp_path, "slow", "import time\n\ndef signal(df):\n    time.sleep(30)\n    return df['close'] * 0\n")
    with pytest.raises(StrategyTimeoutError, match="1 s per call"):
        verify_strategy(df, strategy=slow, timeout=1)


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("import socket\n\ndef signal(df):\n    socket.create_connection(('example.com', 80), timeout=1)\n    return df['close'] * 0\n",
         "network access is blocked"),
        ("def signal(df):\n    open('/nonexistent-dir-monte-neo/x.txt', 'w')\n    return df['close'] * 0\n",
         "writing files is blocked"),
        ("import subprocess\n\ndef signal(df):\n    subprocess.run(['true'])\n    return df['close'] * 0\n",
         "starting processes is blocked"),
        ("import os\n\ndef signal(df):\n    os.remove('/nonexistent-dir-monte-neo/x.txt')\n    return df['close'] * 0\n",
         "changing files is blocked"),
    ],
)
def test_isolation_blocks_side_effects(df, tmp_path: Path, body: str, message: str) -> None:
    with pytest.raises(StrategyError, match=message):
        verify_strategy(df, strategy=_write(tmp_path, "bad", body), isolate=True)


def test_isolation_hides_secrets_and_allows_temp_files(df, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MONTE_NEO_TEST_SECRET", "x")
    body = (
        "import os, tempfile\n\ndef signal(df):\n"
        "    assert 'MONTE_NEO_TEST_SECRET' not in os.environ, 'secret visible'\n"
        "    with open(os.path.join(tempfile.gettempdir(), 'mn-ok.txt'), 'w') as fh:\n        fh.write('ok')\n"
        "    return (df['close'] > df['close'].rolling(20).mean()).astype(int)\n"
    )
    report = verify_strategy(df, strategy=_write(tmp_path, "tidy", body), isolate=True)
    assert report["metrics"]["n_closed_trades"] > 0


def test_worker_errors_and_outside_data(df, tmp_path: Path) -> None:
    broken = _write(tmp_path, "broken", "raise ImportError('no such library')\n")
    with pytest.raises(StrategyError, match="loading the strategy failed: ImportError: no such library"):
        verify_strategy(df, strategy=broken, timeout=30)
    data = tmp_path / "prices.csv"
    df.to_csv(data, index=False)
    reader = _write(tmp_path, "reader", f"import pandas\nFULL = pandas.read_csv({str(data)!r})\n\ndef signal(df):\n    return df['close'] * 0\n")
    report = verify_strategy(data, strategy=reader, timeout=30)
    row = next(c for c in report["checks"] if c["id"] == "external_data")
    assert row["status"] == "fail" and row["details"]["files"] == ["prices.csv"]
    short = _write(tmp_path, "short", "import numpy as np\n\ndef signal(df):\n    return np.ones(3)\n")
    with pytest.raises(ValueError, match="signal length 3"):
        verify_strategy(df, strategy=short, jobs=2)


def test_grid_and_recheck_with_workers(df, tmp_path: Path) -> None:
    sma = TRAPS / "sma_params.py"
    grid = verify_grid(df, {"fast": [5, 10], "slow": [40, 80]}, strategy=sma, jobs=2, timeout=60)
    serial = verify_grid(df, {"fast": [5, 10], "slow": [40, 80]}, strategy=sma)
    assert grid["certificate_id"] == serial["certificate_id"]
    assert recheck_certificate(grid, df, strategy=sma, isolate=True)["reproduced"]
    plain = verify_strategy(df, strategy=TRAPS / "sma_cross.py")
    assert recheck_certificate(plain, df, strategy=TRAPS / "sma_cross.py", timeout=60)["reproduced"]
    short = _write(tmp_path, "gshort", "import numpy as np\n\ndef signal(df, k=1):\n    return np.ones(3)\n")
    with pytest.raises(ValueError, match="signal length 3"):
        verify_grid(df, {"k": [1, 2]}, strategy=short, jobs=2)


def test_options_need_a_strategy_file(df) -> None:
    with pytest.raises(ValueError, match="need strategy code in a file"):
        verify_strategy(df, signal_fn=lambda d: np.ones(len(d)), timeout=5)
    with pytest.raises(ValueError, match="need strategy code in a file"):
        verify_grid(df, {"k": [1]}, signal_fn=lambda d, k=1: np.ones(len(d)), isolate=True)
    with pytest.raises(FileNotFoundError):
        verify_strategy(df, strategy="/no/such/strategy.py", jobs=2)


def test_helpers(df, tmp_path: Path) -> None:
    assert ex.resolve_jobs(None) == ex.resolve_jobs(0) == ex.resolve_jobs("0") == 1
    assert 1 <= ex.resolve_jobs("auto") <= ex.MAX_AUTO_JOBS and ex.resolve_jobs("3") == 3
    with pytest.raises(ValueError, match="jobs must be"):
        ex.resolve_jobs(-2)
    assert ex.split_spec("a/b.py:fn") == (Path("a/b.py"), "fn")
    assert ex.split_spec(str(TRAPS / "sma_cross.py")) == (TRAPS / "sma_cross.py", "signal")
    with pytest.raises(ValueError, match="timeout must be positive"):
        ProcessRunner(TRAPS / "sma_cross.py", "signal", df, timeout=0)
    # The in-process path of evaluate() and the worker functions, called directly.
    fn = lambda d: d["close"].to_numpy() * 0  # noqa: E731
    out = ex.evaluate(fn, df, [FULL, Head(10), df.iloc[:5]])
    assert [v.size for v in out] == [len(df), 10, 5]
    from monte_neo.verify import io_guard

    active = list(io_guard._ACTIVE)  # _init enters a watch meant for a worker; undo it below
    ex._init(str(TRAPS / "sma_cross.py"), "signal", df, (), False, 5.0)
    status, values, _, _ = ex._call((Head(100), {}))
    assert status == "ok" and values.size == 100
    status, message, _, _ = ex._call((df.iloc[:5], {"bogus": 1}))
    assert status == "error" and "bogus" in message
    ex._init(str(tmp_path / "missing.py"), "signal", df, (), False, None)
    assert ex._call((FULL, {}))[0] == "error"
    io_guard._ACTIVE[:] = active
    ex._INIT_ERROR = None
    with ProcessRunner(TRAPS / "sma_cross.py", "signal", df, timeout=30) as runner:
        view = runner.with_params({})
        assert view(df).size == len(df) and runner(df.iloc[:50]).size == 50
    runner.close()  # closing twice is harmless
    os.environ.pop("MONTE_NEO_TEST_SECRET", None)


def test_timeouts_inside_and_outside_the_worker(df, tmp_path: Path, monkeypatch) -> None:
    from monte_neo.verify import io_guard

    with pytest.raises(ex._CallTimeoutError):
        ex._alarm(14, None)
    slow = _write(tmp_path, "nap", "import time\n\ndef signal(df):\n    time.sleep(5)\n    return df['close'] * 0\n")
    active = list(io_guard._ACTIVE)
    ex._init(str(slow), "signal", df, (), False, 0.2)  # this test runs in the main thread: SIGALRM works
    assert ex._call((FULL, {}))[0] == "timeout"
    io_guard._ACTIVE[:] = active
    # A strategy that switches the worker's alarm off is still stopped by the parent's deadline.
    stubborn = _write(
        tmp_path, "stubborn",
        "import signal as sig, time\n\ndef signal(df):\n    sig.signal(sig.SIGALRM, sig.SIG_IGN)\n    time.sleep(30)\n    return df['close'] * 0\n",
    )
    monkeypatch.setattr(ex, "STARTUP_SLACK", 3.0)
    with pytest.raises(StrategyTimeoutError):
        verify_strategy(df, strategy=stubborn, timeout=1)


def test_worker_connections_and_mcp_paths(df, tmp_path: Path) -> None:
    import monte_neo.verify as verify_pkg
    from monte_neo.mcp import tools

    assert "verify_strategy" in dir(verify_pkg)
    data = tmp_path / "prices.csv"
    df.to_csv(data, index=False)
    caller = _write(
        tmp_path, "caller",
        "import socket\n\ndef signal(df):\n    try:\n        socket.create_connection(('127.0.0.1', 9), timeout=0.2)\n"
        "    except OSError:\n        pass\n    return df['close'] * 0\n",
    )
    probe = tools.probe_lookahead(str(data), str(caller))
    assert probe["external_data"]["connections"] == ["127.0.0.1"] and probe["leak_detected"]
    local = tools.probe_lookahead(str(data), str(TRAPS / "sma_cross.py"), timeout=None)
    assert local["truncation"]["status"] == "pass"
    fixed = _write(tmp_path, "fixed", f"import numpy as np\n\ndef signal(df):\n    return np.ones({len(df)})\n")
    with pytest.raises(ValueError, match="signal length"):
        verify_strategy(df, strategy=fixed)  # full length fits, every prefix does not


def test_cli_flags(df, tmp_path: Path, capsys) -> None:
    from monte_neo.cli.verify_cmd import main as cli_main

    data = tmp_path / "prices.csv"
    df.to_csv(data, index=False)
    slow = _write(tmp_path, "slowcli", "import time\n\ndef signal(df):\n    time.sleep(30)\n    return df['close'] * 0\n")
    assert cli_main(["--ohlcv", str(data), "--strategy", str(slow), "--timeout", "1"]) == 3
    assert "time limit" in capsys.readouterr().out
    code = cli_main(["--ohlcv", str(data), "--strategy", str(TRAPS / "sma_cross.py"), "--isolate", "--jobs", "2", "--format", "json"])
    assert code in (0, 1, 2)
