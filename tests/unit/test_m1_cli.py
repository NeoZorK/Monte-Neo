"""CLI wiring: verify --policy / --trials-from / --model-cutoff, monte-neo policy, monte-neo alpha with family D."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from monte_neo.alpha import validate_alpha
from monte_neo.alpha.report import demo_panel
from monte_neo.backtest import synthetic_ohlcv
from monte_neo.cli import entry, verify_cmd


def _files(tmp_path: Path) -> tuple[Path, Path]:
    df = synthetic_ohlcv(700, seed=9)
    ohlcv = tmp_path / "data.csv"
    df.to_csv(ohlcv, index=False)
    sig = tmp_path / "s.npy"
    np.save(sig, np.sign(df["close"].pct_change(10).fillna(0.0).to_numpy()))
    return ohlcv, sig


def test_verify_with_policy_trials_and_cutoff(tmp_path: Path, monkeypatch) -> None:
    ohlcv, sig = _files(tmp_path)
    policy = tmp_path / "p.toml"
    policy.write_text('[policy]\nname = "desk"\n[inputs]\nmin_trades = 35\n[rules]\nallow_warnings = true\n', encoding="utf-8")
    trials = tmp_path / "trials.csv"
    trials.write_text("run\n" + "\n".join(str(i) for i in range(57)) + "\n", encoding="utf-8")
    out = tmp_path / "cert.json"
    code = verify_cmd.main([
        "--ohlcv", str(ohlcv), "--signals", str(sig), "--policy", str(policy), "--trials-from", f"csv:{trials}",
        "--n-trials", "3", "--model-cutoff", "2020-06", "--out", str(out), "--format", "json",
    ])
    cert = json.loads(out.read_text(encoding="utf-8"))
    assert code in (0, 1, 2)
    ids = {c["id"]: c for c in cert["checks"]}
    assert ids["policy"]["details"]["name"] == "desk"
    assert ids["trials_imported"]["status"] == "info" and cert["reproducibility"]["n_trials"] == 57
    assert cert["reproducibility"]["settings"]["min_trades"] == 35
    assert "model_cutoff" in cert["reproducibility"]["settings"]


def test_trials_from_rejects_grid(tmp_path: Path) -> None:
    ohlcv, _ = _files(tmp_path)
    code = verify_cmd.main(["--ohlcv", str(ohlcv), "--strategy", "x.py", "--grid", '{"a": [1]}', "--trials-from", "csv:t.csv"])
    assert code == 3


def test_entry_dispatches_policy_and_alpha(tmp_path: Path, monkeypatch, capsys) -> None:
    target = tmp_path / "policy.toml"
    monkeypatch.setattr(sys, "argv", ["monte-neo", "policy", "init", "--out", str(target)])
    assert entry.main() == 0 and target.exists()
    monkeypatch.setattr(sys, "argv", ["monte-neo", "policy", "init", "--out", str(target)])
    assert entry.main() == 3  # no silent overwrite
    monkeypatch.setattr(sys, "argv", ["monte-neo", "--help"])
    entry.main()
    assert "alpha" in capsys.readouterr().out


def test_alpha_report_has_family_d() -> None:
    prices, real, _ = demo_panel(2, n_symbols=20, n_days=300)
    without = validate_alpha(prices, real, placebos=50)
    ids = {c["id"]: c["status"] for c in without["checks"]}
    assert ids["market_impact"] == "skip" and ids["participation_limit"] == "skip"
    assert {"capacity_curve", "short_feasibility", "turnover_vs_decay", "rebalance_timing_luck"} <= set(ids)
    huge = validate_alpha(prices, real, placebos=50, aum=1e11)
    assert {c["id"]: c["status"] for c in huge["checks"]}["market_impact"] == "fail"
    assert huge["verdict"] == "REJECT" and huge["reproducibility"]["settings"]["aum"] == 1e11
    assert isinstance(pd.Series(huge["next_actions"]).iloc[0], str)
