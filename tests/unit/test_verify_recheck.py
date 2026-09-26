"""Unit tests for certificate re-checks and lazy package imports."""

from __future__ import annotations

import json
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.verify import load_certificate, recheck_certificate, verify_grid, verify_strategy

SMA = "def signal(df, fast=10, slow=40):\n    c = df['close']\n    return (c.rolling(fast).mean() > c.rolling(slow).mean()).astype(int)\n"


@pytest.fixture(scope="module")
def setup(tmp_path_factory) -> dict:
    root = tmp_path_factory.mktemp("recheck")
    df = synthetic_ohlcv(1200, seed=6)
    strat = root / "sma.py"
    strat.write_text(SMA)
    return {"df": df, "strategy": str(strat), "root": root}


def test_recheck_strategy_roundtrip(setup) -> None:
    df, strat = setup["df"], setup["strategy"]
    cert = verify_strategy(df, strategy=strat, n_trials=5)
    path = setup["root"] / "cert.json"
    path.write_text(json.dumps(cert))
    out = recheck_certificate(path, df, strategy=strat)
    assert out["reproduced"] and out["certificate_id_matches"] and out["verdict_matches"]
    assert all(out["inputs_match"].values())


def test_recheck_signals_and_mismatches(setup) -> None:
    df = setup["df"]
    sig = (df["close"] > df["close"].rolling(30).mean()).astype(int).to_numpy()
    cert = verify_strategy(df, signals=sig)
    assert recheck_certificate(cert, df, signals=sig)["reproduced"]
    tampered = df.copy()
    tampered.loc[100, "close"] *= 1.01
    bad = recheck_certificate(cert, tampered, signals=sig)
    assert not bad["reproduced"] and bad["inputs_match"]["data_sha256"] is False
    wrong_verdict = {**cert, "verdict": "PASS" if cert["verdict"] != "PASS" else "REJECT"}
    out = recheck_certificate(wrong_verdict, df, signals=sig)
    assert not out["reproduced"] and out["reason"] == "verdict differs"
    wrong_id = {**cert, "certificate_id": "0" * 16}
    assert recheck_certificate(wrong_id, df, signals=sig)["reason"] == "certificate id differs"
    with pytest.raises(ValueError, match="provide signals or strategy"):
        recheck_certificate(cert, df)


def test_recheck_grid(setup) -> None:
    df, strat = setup["df"], setup["strategy"]
    cert = json.loads(json.dumps(verify_grid(df, {"fast": [5, 10], "slow": [40]}, strategy=strat, folds=2)))
    assert recheck_certificate(cert, df, strategy=strat)["reproduced"]
    old = {**cert, "grid": {k: v for k, v in cert["grid"].items() if k != "spec"}}
    out = recheck_certificate(old, df, strategy=strat)
    assert not out["reproduced"] and "older" in out["reason"]


def test_load_certificate_schema(tmp_path) -> None:
    with pytest.raises(ValueError, match="strategy-verdict/1"):
        load_certificate({"schema": "other"})
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"schema": "strategy-verdict/1"}))
    assert load_certificate(p)["schema"] == "strategy-verdict/1"


def test_lazy_package_import() -> None:
    code = (
        "import sys, monte_neo, monte_neo.verify, monte_neo.cli.app\n"
        "heavy = [m for m in ('monte_neo.core.generator', 'monte_neo.core.mlx_engine', 'mlx') if m in sys.modules]\n"
        "assert not heavy, heavy\n"
        "import monte_neo.core as core\n"
        "assert core.OverfitValidator.__name__ == 'OverfitValidator'\n"
        "assert monte_neo.MetricsCalculator.__name__ == 'MetricsCalculator'\n"
        "for mod in (monte_neo, core):\n"
        "    try:\n"
        "        mod.missing\n"
        "    except AttributeError:\n"
        "        pass\n"
        "    else:\n"
        "        raise SystemExit('missing attribute did not raise')\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_lazy_exports_in_process() -> None:
    import monte_neo
    import monte_neo.core as core

    assert monte_neo.MonteCarloEngine.__name__ == "MonteCarloEngine"
    assert core.ParameterOptimizer.__name__ == "ParameterOptimizer"
    with pytest.raises(AttributeError):
        monte_neo.nope  # noqa: B018
    with pytest.raises(AttributeError):
        core.nope  # noqa: B018
    assert isinstance(np.zeros(1), np.ndarray) and isinstance(pd.DataFrame(), pd.DataFrame)
