"""Regression tests for the v0.34.0 audit: each test pins one fixed defect."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from monte_neo.backtest import ExecutionModel, synthetic_ohlcv
from monte_neo.bench.honesty import score_submission
from monte_neo.mcp import tools
from monte_neo.verify import (
    implausible_accuracy,
    infer_periods_per_year,
    lint_source,
    probe_truncation,
    recheck_certificate,
    verify_grid,
    verify_strategy,
)


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    return synthetic_ohlcv(1500, seed=11)


def _statuses(report: dict) -> dict[str, str]:
    return {c["id"]: c["status"] for c in report["checks"]}


def test_python_api_trades_shorts_by_default(df) -> None:
    # Before: the default model was long_flat, so -1 positions were silently never traded.
    report = verify_strategy(df, signals=-np.ones(len(df)))
    assert report["reproducibility"]["model"]["side_mode"] == "long_short"
    assert report["metrics"]["n_closed_trades"] == 1 and report["metrics"]["total_return"] != 0.0
    long_only = verify_strategy(df, signals=-np.ones(len(df)), model=ExecutionModel(side_mode="long_flat", warmup_bars=10))
    assert long_only["metrics"]["exposure"] == 0.0  # exposure counts what the model trades


def test_periods_per_year_counts_bars_per_elapsed_year() -> None:
    assert 255 < infer_periods_per_year(pd.bdate_range("2015-01-01", "2020-01-01")) < 265
    assert infer_periods_per_year(pd.date_range("2024-01-01", periods=500, freq="min")) == pytest.approx(525_960.0)
    assert infer_periods_per_year(None) == 252.0


def test_truncation_catches_a_sparse_leak_without_lint_patterns(df) -> None:
    # Enters only before big up-moves (a few percent of bars); no shift(-k) for the lint to see.
    def sparse_leak(d: pd.DataFrame) -> np.ndarray:
        c = d["close"].to_numpy()
        nxt = np.append(c[1:], np.nan)
        return np.where(nxt / c - 1.0 > 0.0015, 1, 0)

    full = sparse_leak(df)
    assert 0 < np.mean(full != 0) < 0.1
    probe = probe_truncation(sparse_leak, df)
    assert probe["status"] == "fail" and probe["mismatch_count"] > 0


def test_accuracy_needs_a_high_and_significant_rate() -> None:
    rng = np.random.default_rng(0)
    move = rng.choice([-1.0, 1.0], size=600)
    close = 100.0 + np.cumsum(move)
    right = np.sign(np.diff(close))

    def hitting(share: float, n: int) -> np.ndarray:
        pos = np.where(np.arange(n - 1) < share * (n - 1), right[: n - 1], -right[: n - 1])
        return np.append(pos, 0).astype(np.int64)

    # A real, strong edge (62% on 600 bars) is not accused of look-ahead any more.
    assert implausible_accuracy(close, close, hitting(0.62, 600))["status"] == "pass"
    # High but not significant: a warning only.
    few = implausible_accuracy(close[:50], close[:50], hitting(0.72, 50), min_active=20)
    assert few["hit_rate"] >= 0.7 and few["z_score"] < 3.5 and few["status"] == "warn"
    assert implausible_accuracy(close, close, hitting(1.0, 600))["status"] == "fail"


def test_certificate_records_settings_and_recheck_uses_them(df, tmp_path: Path) -> None:
    sig = (df["close"] > df["close"].rolling(20).mean()).astype(int).to_numpy()
    report = verify_strategy(df, signals=sig, min_trades=1, holdout_fraction=0.4)
    settings = report["reproducibility"]["settings"]
    assert settings == {"min_trades": 1, "holdout_fraction": 0.4, "probe_checks": 24, "periods_per_year": None}
    cert = tmp_path / "cert.json"
    cert.write_text(json.dumps(report), encoding="utf-8")
    again = recheck_certificate(cert, df, signals=sig)
    assert again["reproduced"], again
    report["reproducibility"]["engine_version"] = "v0.0.1"
    report["certificate_id"] = "0" * 16  # an old release computed a different id
    old = recheck_certificate(report, df, signals=sig)
    assert not old["reproduced"] and "pip install monte-neo==0.0.1" in old["reason"]


def test_outside_data_watch_knows_the_ohlcv_file_by_path(df, tmp_path: Path) -> None:
    data = tmp_path / "prices.txt"  # not a data suffix: recognised only as the OHLCV file
    df.to_csv(data, index=False)
    strategy = tmp_path / "strategy.py"
    strategy.write_text(
        "import numpy as np\n"
        f"ROWS = open({str(data)!r}).read().count(chr(10))\n"
        "def signal(df):\n    return np.ones(len(df))\n",
        encoding="utf-8",
    )
    report = verify_strategy(data, strategy=strategy)
    assert _statuses(report)["external_data"] == "fail"
    probe = tools.probe_lookahead(str(data), str(strategy))
    assert probe["external_data"]["files"] == ["prices.txt"] and probe["leak_detected"]


def test_grid_counts_data_read_at_import(df, tmp_path: Path) -> None:
    data = tmp_path / "prices.csv"
    df.to_csv(data, index=False)
    strategy = tmp_path / "grid_strategy.py"
    strategy.write_text(
        "import numpy as np\n"
        "import pandas\n"
        f"FULL = getattr(pandas, 'read_' + 'csv')({str(data)!r})\n"
        "def signal(df, lag=1):\n    return np.ones(len(df))\n",
        encoding="utf-8",
    )
    report = verify_grid(data, {"lag": [1, 2]}, strategy=strategy)
    assert _statuses(report)["external_data"] == "fail"


def test_bench_survives_non_numeric_claims(df, tmp_path: Path) -> None:
    data = tmp_path / "data.csv"
    df.to_csv(data, index=False)
    strategy = tmp_path / "strategy.py"
    strategy.write_text("def signal(df):\n    return (df['close'] > df['close'].rolling(20).mean()).astype(int)\n", encoding="utf-8")
    task = {"ohlcv_path": str(data), "edge_after_costs": False}
    claim = {"total_return": "none", "sharpe": "n/a", "n_trials": "many"}
    row = score_submission(task, {"agent": "a", "task": "t", "strategy": str(strategy), "claim": claim})
    assert row["verdict"] != "ERROR"
    assert row["claimed_total_return"] is None and row["overclaim"] is None and row["n_trials_declared"] is False


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [({"n_trials": 0}, "n_trials"), ({"min_trades": 0}, "min_trades"), ({"holdout_fraction": 1.5}, "holdout_fraction")],
)
def test_invalid_settings_are_input_errors(df, kwargs: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        verify_strategy(df, signals=np.ones(len(df)), **kwargs)


def test_grid_needs_a_fold(df) -> None:
    with pytest.raises(ValueError, match="folds"):
        verify_grid(df, {"a": [1]}, signal_fn=lambda d, a=1: np.ones(len(d)), folds=0)


def test_bench_reads_broken_claim_files(tmp_path: Path) -> None:
    from monte_neo.bench.honesty import _read_json

    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "list.json").write_text("[1, 2]", encoding="utf-8")
    assert "_invalid" in _read_json(tmp_path / "bad.json")
    assert "_invalid" in _read_json(tmp_path / "list.json")
    assert _read_json(tmp_path / "missing.json") == {}


@pytest.mark.parametrize(
    ("source", "status", "rules"),
    [
        ("def f(c, i):\n    return c[i - 20:i].max()\n", "pass", []),  # a moving window
        ("def f(c, i):\n    return max(c[i - 20:i])\n", "pass", []),
        ("import numpy as np\ndef f(c, i):\n    return np.mean(c[i - 5:i])\n", "pass", []),
        ("def f(c):\n    return c[:1000].mean()\n", "warn", ["full_sample_stat"]),  # fixed block: future for early bars
        ("def f(c):\n    return c[100:].max()\n", "warn", ["full_sample_stat"]),
        (
            "import numpy as np\nX = np.arange(30)\ndef s(df):\n"
            "    return df.close.rolling(30).apply(lambda w: np.polyfit(X, w, 1)[0], raw=True)\n",
            "pass", [],
        ),
        (
            "import numpy as np\ndef slope(w):\n    return np.polyfit(np.arange(len(w)), w, 1)[0]\n"
            "def s(df):\n    return df.close.rolling(30).apply(slope)\n",
            "pass", [],
        ),
        ("import numpy as np\ndef s(df):\n    return np.polyfit(np.arange(len(df)), df.close, 1)[0]\n", "warn", ["full_sample_fit"]),
        ("def s(df):\n    return df.close.rolling(30).apply(lambda w: w.shift(-1).mean())\n", "fail", ["negative_shift"]),
        ("def s(df):\n    return df.close.pipe(lambda s: s - s.mean())\n", "warn", ["full_sample_stat"]),  # not a window
    ],
)
def test_lint_knows_windows(source: str, status: str, rules: list[str]) -> None:
    res = lint_source(source)
    assert res["status"] == status and sorted({f["rule"] for f in res["findings"]}) == rules
