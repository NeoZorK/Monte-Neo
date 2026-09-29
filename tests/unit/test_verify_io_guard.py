"""Strategies that read data outside df: static lint, runtime watch and the verdict."""

from __future__ import annotations

import os
import socket
import sys
import threading
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.verify import checks as rows
from monte_neo.verify import io_guard, lint_source, verify_strategy
from monte_neo.verify.io_guard import IOWatch


def _statuses(report: dict) -> dict[str, str]:
    return {c["id"]: c["status"] for c in report["checks"]}


def test_lint_flags_outside_data() -> None:
    src = """
import numpy as np
import pandas as pd
import requests
from urllib.request import urlopen
DATA = pd.read_csv("prices.csv")
def signal(df):
    x = np.load("x.npy")
    with open("f.bin", "rb") as fh:
        pass
    return df["close"]
if __name__ == "__main__":
    print(signal(pd.read_parquet("local.parquet")))
else:
    y = np.loadtxt("z.txt")
"""
    res = lint_source(src)
    assert res["status"] == "fail"
    lines = sorted(f["line"] for f in res["findings"] if f["rule"] == "external_data")
    assert lines == [4, 5, 6, 8, 9, 15]  # the __main__ body (line 13) is a local run, not signal()
    assert lint_source("import json\nfrom collections import deque\n")["status"] == "pass"
    assert lint_source("if __name__ == '__main__':\n    open('x.csv')\n")["status"] == "pass"
    assert lint_source("if x == '__main__':\n    open('x.csv')\n")["status"] == "fail"


def test_watch_records_data_reads_and_connections(tmp_path: Path) -> None:
    table = tmp_path / "prices.csv"
    pd.DataFrame({"close": [1.0, 2.0]}).to_csv(table, index=False)
    np.save(tmp_path / "x.npy", np.ones(2))
    raw = tmp_path / "raw_prices"  # no suffix: counted only as the declared data file
    raw.write_bytes(b"1,2")
    watch = IOWatch((raw,))
    with watch:
        pd.read_csv(table)
        np.load(tmp_path / "x.npy")
        raw.read_bytes()
        os.close(os.open(os.fsencode(table), os.O_RDONLY))
        pd.DataFrame({"a": [1]}).to_csv(tmp_path / "out.csv")  # writes are not reads
        (tmp_path / "notes.txt").write_text("x")
        (tmp_path / "notes.txt").read_text()  # not a data suffix
        with socket.socket() as sock:
            sock.settimeout(0.2)
            try:
                sock.connect(("127.0.0.1", 9))
            except OSError:
                pass
    assert watch.files == ["prices.csv", "x.npy", "raw_prices"]
    assert watch.connections == ["127.0.0.1"]
    pd.read_csv(table)  # outside the watch
    assert watch.files == ["prices.csv", "x.npy", "raw_prices"]
    assert io_guard._ACTIVE == []


def test_watch_ignores_library_files() -> None:
    watch = IOWatch()
    with watch:
        watch.note_file(os.path.join(os.path.abspath(sys.prefix), "lib", "table.csv"))
    assert watch.files == []


def test_external_data_row() -> None:
    assert rows.external_data_row(None, None)["status"] == "skip"
    assert rows.external_data_row([], [])["status"] == "pass"
    bad = rows.external_data_row(["prices.csv"], ["example.com"])
    assert bad["status"] == "fail" and bad["summary"] == "outside data: reads file prices.csv, network example.com"


@pytest.fixture(scope="module")
def csv_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("data") / "prices.csv"
    synthetic_ohlcv(1200, seed=4).to_csv(path, index=False)
    return path


def test_verify_rejects_a_strategy_that_loads_the_dataset(csv_path: Path, tmp_path: Path) -> None:
    # The probes rewrite df; this strategy ignores df and reads 20 bars ahead from disk.
    loader = "getattr(__import__('pandas'), 'read_' + 'csv')"
    strategy = tmp_path / "strategy.py"
    strategy.write_text(
        "import numpy as np\n"
        f"DATA = {loader}({str(csv_path)!r})\n"
        "def signal(df):\n"
        "    c = DATA['close'].to_numpy()\n"
        "    ahead = np.minimum(np.arange(len(df)) + 20, len(c) - 1)\n"
        "    return np.sign(c[ahead] - c[: len(df)])\n",
        encoding="utf-8",
    )
    report = verify_strategy(csv_path, strategy=strategy)
    statuses = _statuses(report)
    assert statuses["lookahead_truncation"] == "pass" and statuses["lookahead_static_lint"] == "pass"
    assert statuses["external_data"] == "fail" and report["verdict"] == "REJECT"
    row = next(c for c in report["checks"] if c["id"] == "external_data")
    assert row["details"]["files"] == ["prices.csv"]
    assert any(a.startswith("signal() must use only the df") for a in report["next_actions"])


def test_verify_signals_only_skips_external_data(csv_path: Path) -> None:
    report = verify_strategy(csv_path, signals=np.ones(1200))
    assert _statuses(report)["external_data"] == "skip"


def test_hook_called_directly() -> None:
    # CPython pauses tracing inside audit hooks, so coverage needs direct calls.
    io_guard._hook("open", ("ignored.csv", "r", 0))  # no active watch
    watch = IOWatch()
    with watch:
        io_guard._hook("open", (b"/data/a.csv", "rb", 0))
        io_guard._hook("open", ("/data/b.csv", None, os.O_RDONLY))
        io_guard._hook("open", ("/data/c.csv", None, os.O_WRONLY))
        io_guard._hook("open", ("/data/d.csv", "w", 0))
        io_guard._hook("open", (3, "r", 0))  # file descriptor
        io_guard._hook("open", ("/data/a.csv", "r", 0))  # already noted
        io_guard._hook("socket.connect", (None, ("example.com", 443)))
        io_guard._hook("socket.connect", (None, "/tmp/unix.sock"))
        io_guard._hook("socket.connect", (None, ("example.com", 443)))
    assert watch.files == ["a.csv", "b.csv"]
    assert watch.connections == ["example.com", "/tmp/unix.sock"]
    roots = io_guard._roots()
    assert all(r.endswith(os.sep) for r in roots)


def test_watch_sees_only_its_own_thread(tmp_path: Path) -> None:
    table = tmp_path / "other.csv"
    pd.DataFrame({"close": [1.0]}).to_csv(table, index=False)
    watch = IOWatch()
    with watch:
        worker = threading.Thread(target=pd.read_csv, args=(table,))
        worker.start()
        worker.join()
    assert watch.files == []
