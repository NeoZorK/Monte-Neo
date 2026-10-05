"""Trial ledger: variants are counted, formatting does not make a new variant, edits are visible."""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.verify import verify_strategy
from monte_neo.verify.ledger import GENESIS, Ledger, variant_id

DF = synthetic_ohlcv(1500, seed=3)
DF["timestamp"] = pd.date_range("2022-01-03", periods=len(DF), freq="h")


def _sma(fast: int):  # noqa: ANN202
    def signal(d):  # noqa: ANN001, ANN202
        return np.where(d["close"].rolling(fast).mean() > d["close"].rolling(80).mean(), 1, 0)

    return signal


def _src(fast: int, comment: str = "") -> str:
    return (
        f'def signal(df):\n    """Doc {comment}."""\n    # {comment}\n'
        f'    return (df["close"].rolling({fast}).mean() > df["close"].rolling(80).mean()).astype(int).to_numpy()\n'
    )


def _verify(fast: int, path: Path, **kw):  # noqa: ANN003, ANN202
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return verify_strategy(DF, signal_fn=_sma(fast), source=_src(fast), ledger=path, **kw)


def test_formatting_and_comments_do_not_make_a_new_variant() -> None:
    a = variant_id(_src(20, "one"))
    assert a == variant_id(_src(20, "two")) == variant_id("def signal(df):\n    return (df['close'].rolling(20).mean() > df['close'].rolling(80).mean()).astype(int).to_numpy()")
    assert a != variant_id(_src(21))
    assert variant_id(None, np.array([1, 0, 1])) == variant_id(None, np.array([1, 0, 1])) != variant_id(None, np.array([1, 1, 1]))
    assert variant_id(None) is None and variant_id("def (:").startswith("src:")


def test_every_new_variant_raises_the_trial_count_and_a_repeat_does_not(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    counts = [_verify(f, path)["ledger"]["variants_counted"] for f in (10, 15, 20, 15, 10)]
    assert counts == [1, 2, 3, 3, 3]
    report = _verify(25, path)
    assert report["ledger"]["n_trials_used"] == 4 and report["reproducibility"]["n_trials"] == 4
    row = next(c for c in report["checks"] if c["id"] == "trial_ledger")
    assert row["status"] == "pass" and "4 variant" in row["summary"]


def test_declaring_fewer_trials_than_counted_is_noticed_and_deflates_more(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    for fast in (10, 12, 14, 16, 18):
        _verify(fast, path)
    honest = _verify(20, path)
    declared = _verify(22, path, n_trials=2)
    row = next(c for c in declared["checks"] if c["id"] == "trial_ledger")
    assert row["status"] == "info" and "declared as 2" in row["summary"] and row["details"]["counted"] == 7
    assert declared["reproducibility"]["n_trials"] == 7
    assert declared["metrics"]["deflated_sharpe"] <= _verify(22, tmp_path / "other.jsonl")["metrics"]["deflated_sharpe"]
    assert honest["ledger"]["entry"] == 6


def test_the_chain_detects_edits_and_removals(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    for fast in (10, 12, 14):
        _verify(fast, path)
    book = Ledger(path)
    assert book.check() == {"ok": True, "entries": 3, "problem": None}
    lines = path.read_text().splitlines()
    first = json.loads(lines[0])
    assert first["prev"] == GENESIS
    tampered = json.loads(lines[1])
    tampered["sharpe"] = 99.0
    path.write_text("\n".join([lines[0], json.dumps(tampered), lines[2]]) + "\n")
    assert not book.check()["ok"] and "entry 2" in book.check()["problem"]
    path.write_text("\n".join([lines[0], lines[2]]) + "\n")  # a removed line
    assert not book.check()["ok"]
    report = _verify(30, path)
    row = next(c for c in report["checks"] if c["id"] == "trial_ledger")
    assert row["status"] == "info" and report["ledger"]["chain_ok"] is False and "changed" in row["summary"]
    path.write_text("not json\n")
    assert "not valid JSON" in Ledger(path).check()["problem"]


def test_data_scopes_the_count(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    _verify(10, path)
    _verify(12, path)
    other = synthetic_ohlcv(1500, seed=9)
    other["timestamp"] = DF["timestamp"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        report = verify_strategy(other, signal_fn=_sma(10), source=_src(10), ledger=path)
    assert report["ledger"]["variants_counted"] == 1


def test_a_recheck_style_run_without_a_ledger_reproduces_the_certificate(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    for fast in (10, 12, 14):
        _verify(fast, path)
    report = _verify(16, path)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        again = verify_strategy(DF, signal_fn=_sma(16), source=_src(16), n_trials=report["reproducibility"]["n_trials"])
    assert again["certificate_id"] == report["certificate_id"] and again["verdict"] == report["verdict"]


def test_signals_only_runs_are_counted_too(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    sig = _sma(10)(DF)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        counts = [verify_strategy(DF, signals=s, ledger=path)["ledger"]["variants_counted"] for s in (sig, 1 - sig, sig)]
    assert counts == [1, 2, 2]
