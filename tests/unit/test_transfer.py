"""Cross-market replication: the frozen rule on markets outside the search, pooled with the effective number of markets."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from monte_neo.cli import research_cmd
from monte_neo.research.transfer import replicate

RULE = '''
import numpy as np

def signal(df):
    c = df["close"]
    return (c.shift(1) > c.shift(1).rolling(20).mean()).astype(float).fillna(0.0).to_numpy()
'''


def _market(path: Path, drift: float, seed: int, n: int = 900) -> Path:
    rng = np.random.default_rng(seed)
    r = drift + 0.02 * rng.standard_normal(n)
    # persistent regimes give the trend rule something real to find when drift is on
    regime = np.sign(np.sin(np.arange(n) / 40.0)) * abs(drift) * 6 if drift else 0.0
    close = 100 * np.exp(np.cumsum(r + regime))
    ts = pd.date_range("2021-01-01", periods=n, freq="D", tz="UTC")
    pd.DataFrame({"timestamp": ts, "open": close, "high": close * 1.01, "low": close * 0.99, "close": close, "volume": 1e6}).to_csv(path, index=False)
    return path


def test_a_real_effect_replicates_and_noise_does_not(tmp_path: Path) -> None:
    strat = tmp_path / "rule.py"
    strat.write_text(RULE)
    good = {f"M{i}": _market(tmp_path / f"m{i}.csv", 0.001, i) for i in range(6)}
    rep = replicate(strat, good, discovery=["BTC"], n_trials=5, run_verify=False)
    assert rep["check"]["status"] == "pass" and rep["pooled"]["markets"] == 6
    assert 1.0 <= rep["pooled"]["effective_markets"] <= 6.0
    noise = {f"N{i}": _market(tmp_path / f"n{i}.csv", 0.0, 100 + i) for i in range(6)}
    assert replicate(strat, noise, discovery=["BTC"], n_trials=5, run_verify=False)["check"]["status"] != "pass"


def test_markets_from_the_search_and_too_few_markets_are_refused(tmp_path: Path) -> None:
    strat = tmp_path / "rule.py"
    strat.write_text(RULE)
    m = {f"M{i}": _market(tmp_path / f"m{i}.csv", 0.0, i, 200) for i in range(3)}
    with pytest.raises(ValueError, match="not out of sample"):
        replicate(strat, m, discovery=["m1"], n_trials=1, run_verify=False)
    with pytest.raises(ValueError, match="at least 3"):
        replicate(strat, {"M0": m["M0"]}, discovery=[], n_trials=1, run_verify=False)


def test_cli_transfer_with_full_verify(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    strat = tmp_path / "rule.py"
    strat.write_text(RULE)
    folder = tmp_path / "markets"
    folder.mkdir()
    for i in range(3):
        _market(folder / f"COIN{i}.csv", 0.001, 50 + i, 400)
    code = research_cmd.main(["transfer", "--strategy", str(strat), "--markets", str(folder), "--discovery", "BTCUSDT", "--n-trials", "3"])
    out = capsys.readouterr().out
    assert code == 0 and "cross_market_replication" in out and "COIN0" in out and "verdict" in out
