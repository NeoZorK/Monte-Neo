"""``monte-neo verify`` end to end: real files, a real process, honest exit codes and no tracebacks."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

HONEST = "import numpy as np\ndef signal(df):\n    return np.sign(df['close'] - df['close'].rolling(20).mean()).fillna(0).to_numpy()\n"
LEAK = "import numpy as np\ndef signal(df):\n    return np.sign(df['close'].shift(-1) - df['close']).fillna(0).to_numpy()\n"


def _frame(n: int = 700) -> pd.DataFrame:
    c = 100 * np.exp(np.cumsum(np.random.default_rng(0).normal(0.0001, 0.01, n)))
    return pd.DataFrame({"timestamp": pd.date_range("2020-01-01", periods=n, freq="h"), "open": c, "high": c * 1.002,
                         "low": c * 0.998, "close": c, "volume": 1e5})


def _verify(tmp: Path, csv: str, strategy: str, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "monte_neo", "verify", "--ohlcv", str(tmp / csv), "--strategy", str(tmp / strategy), *extra],
                          capture_output=True, text=True, timeout=600)


@pytest.fixture()
def files(tmp_path: Path) -> Path:
    _frame().to_csv(tmp_path / "ok.csv", index=False)
    (tmp_path / "empty.csv").write_text("")
    (tmp_path / "header_only.csv").write_text("timestamp,open,high,low,close,volume\n")
    (tmp_path / "honest.py").write_text(HONEST)
    (tmp_path / "leak.py").write_text(LEAK)
    (tmp_path / "broken.py").write_text("def signal(df:\n")
    return tmp_path


@pytest.mark.parametrize("csv,strategy", [("empty.csv", "honest.py"), ("header_only.csv", "honest.py"), ("ok.csv", "broken.py"), ("missing.csv", "honest.py")])
def test_bad_inputs_exit_three_with_a_message_and_no_traceback(files: Path, csv: str, strategy: str) -> None:
    out = _verify(files, csv, strategy)
    text = out.stdout + out.stderr
    assert out.returncode == 3 and "Traceback" not in text and text.strip()


def _status(cert: dict, check_id: str) -> str:
    return next(c["status"] for c in cert["checks"] if c["id"] == check_id)


def test_leaky_strategy_is_rejected_and_certificate_can_be_rechecked(files: Path) -> None:
    cert = files / "cert.json"
    out = _verify(files, "ok.csv", "leak.py", "--out", str(cert))
    assert "Traceback" not in out.stdout + out.stderr and cert.exists()
    data = json.loads(cert.read_text())
    assert data["verdict"] == "REJECT" and _status(data, "lookahead_truncation") == "fail" and out.returncode == 2
    again = subprocess.run([sys.executable, "-m", "monte_neo", "verify", "--recheck", str(cert), "--ohlcv", str(files / "ok.csv"),
                            "--strategy", str(files / "leak.py")], capture_output=True, text=True, timeout=600)
    assert "Traceback" not in again.stdout + again.stderr and again.returncode in (0, 2)


def test_honest_strategy_is_not_accused_of_lookahead(files: Path) -> None:
    cert = files / "honest.json"
    out = _verify(files, "ok.csv", "honest.py", "--out", str(cert))
    assert "Traceback" not in out.stdout + out.stderr
    data = json.loads(cert.read_text())
    assert _status(data, "lookahead_truncation") == "pass" and _status(data, "lookahead_static_lint") == "pass"
