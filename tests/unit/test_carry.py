"""Delta-neutral carry in the full verifier: funding is explicit P&L and the entry rule meets the signal-level probes."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from monte_neo.cli.verify_cmd import main
from monte_neo.mcp import tools
from monte_neo.verify.carry import carry_table, decomposition_row, verify_carry

N = 1500
HOLD = "import numpy as np\ndef signal(df):\n    return np.ones(len(df))\n"
TREND = ("import numpy as np\ndef signal(df):\n    f = df['funding_rate'].rolling(24).mean().shift(1).to_numpy()\n"
         "    return np.where(np.nan_to_num(f) > 0.0, 1.0, 0.0)\n")
PEEK = ("import numpy as np\ndef signal(df):\n    f = df['funding_rate'].shift(-1).to_numpy()\n"
        "    return np.where(np.nan_to_num(f) > 0.0001, 1.0, 0.0)\n")


def _table(funding_mean: float = 3e-4, basis_vol: float = 0.0005, seed: int = 4) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    spot = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.004, N)))
    perp = spot * (1.0 + np.cumsum(rng.normal(0, basis_vol, N)) * 0.0 + rng.normal(0, basis_vol, N))
    regime = np.repeat(rng.choice([-1.0, 1.0], size=N // 100 + 1, p=[0.3, 0.7]), 100)[:N]
    funding = funding_mean * regime + rng.normal(0, 3e-5, N)
    return pd.DataFrame({"timestamp": pd.date_range("2024-01-01", periods=N, freq="h", tz="UTC"), "spot_close": spot, "perp_close": perp, "funding_rate": funding})


TABLE = _table()


def test_carry_table_pnl_is_basis_plus_funding() -> None:
    t = carry_table(TABLE)
    r = t["close"].pct_change().fillna(0.0).to_numpy()
    expect = TABLE["spot_close"].pct_change().fillna(0) - TABLE["perp_close"].pct_change().fillna(0) + TABLE["funding_rate"]
    assert np.allclose(r[1:], expect.to_numpy()[1:], atol=1e-9) and (t["open"].iloc[1:].to_numpy() == t["close"].iloc[:-1].to_numpy()).all()
    bps = TABLE.drop(columns="funding_rate").assign(funding_bps=TABLE["funding_rate"] * 1e4)
    assert np.allclose(carry_table(bps)["close"], t["close"])


@pytest.mark.parametrize(("mutate", "msg"), [
    (lambda d: d.drop(columns="perp_close"), "missing column perp_close"),
    (lambda d: d.drop(columns="funding_rate"), "missing funding"),
    (lambda d: d.assign(spot_close=-1.0), "positive"),
    (lambda d: d.assign(funding_rate=np.nan), "finite"),
    (lambda d: d.head(10), "at least 60"),
    (lambda d: d.assign(timestamp=d["timestamp"].iloc[0]), "increasing and unique"),
    (lambda d: d.assign(funding_rate=-1.5), "loses 100%"),
])
def test_carry_table_refuses_bad_input(mutate, msg) -> None:
    with pytest.raises(ValueError, match=msg):
        carry_table(mutate(TABLE))


def test_decomposition_funding_vs_basis() -> None:
    good = decomposition_row(carry_table(TABLE), None)
    assert good["status"] == "pass" and good["details"]["funding_share"] > 0.5
    noisy = carry_table(_table(funding_mean=1e-6, basis_vol=0.004))
    assert decomposition_row(noisy, None)["status"] in ("warn", "pass")
    assert decomposition_row(carry_table(TABLE), np.zeros(N))["status"] == "skip"
    bad = carry_table(TABLE.assign(funding_rate=-3e-4))
    assert decomposition_row(bad, None)["status"] == "warn" and "did not earn from funding" in decomposition_row(bad, None)["summary"]
    basis_led = TABLE.assign(funding_rate=1e-7)
    basis_led["perp_close"] = basis_led["spot_close"] * (1.0 - np.linspace(0, 0.2, N))  # the short leg gains as the basis falls
    assert "basis moving" in decomposition_row(carry_table(basis_led), None)["summary"]


def test_full_verify_runs_signal_checks_on_the_entry_rule(tmp_path) -> None:
    f = tmp_path / "trend.py"
    f.write_text(TREND)
    rep = verify_carry(TABLE, strategy=f, n_trials=1)
    ids = {c["id"]: c for c in rep["checks"]}
    assert "carry_decomposition" in ids and "lookahead_truncation" in ids and rep["carry"]["legs"] == ["spot long", "perpetual short"]
    assert ids["lookahead_truncation"]["status"] == "pass"


def test_reading_the_funding_about_to_be_earned_is_caught(tmp_path) -> None:
    f = tmp_path / "peek.py"
    f.write_text(PEEK)
    ids = {c["id"]: c for c in verify_carry(TABLE, strategy=f)["checks"]}
    assert ids["lookahead_truncation"]["status"] == "fail"


def test_costs_of_both_legs_are_charged(tmp_path) -> None:
    f = tmp_path / "trend.py"
    f.write_text(TREND)
    cheap = verify_carry(TABLE, strategy=f, spot_cost_bps=0.0, perp_cost_bps=0.0)["metrics"]
    dear = verify_carry(TABLE, strategy=f, spot_cost_bps=60.0, perp_cost_bps=40.0)["metrics"]
    assert dear["total_return"] < cheap["total_return"]
    with pytest.raises(ValueError, match="non-negative"):
        verify_carry(TABLE, strategy=f, spot_cost_bps=-1.0)
    with pytest.raises(ValueError, match="needs strategy"):
        verify_carry(TABLE)
    with pytest.raises(ValueError, match="signal length"):
        verify_carry(TABLE, signal_fn=lambda df: np.ones(3))


def test_cli_and_mcp(tmp_path, capsys) -> None:
    csv, f = tmp_path / "c.csv", tmp_path / "hold.py"
    TABLE.to_csv(csv, index=False)
    f.write_text(HOLD)
    code = main(["--carry", str(csv), "--strategy", str(f), "--carry-costs", "10,5"])
    out = capsys.readouterr().out
    assert code in (0, 1, 2) and "carry_decomposition" in out, out[-600:]
    assert main(["--carry", str(csv), "--strategy", str(f), "--carry-capital-apr", "0.05", "--carry-leverage", "2"]) in (0, 1, 2)
    capsys.readouterr()
    assert main(["--carry", str(csv)]) == 3
    assert main(["--carry", str(csv), "--strategy", str(f), "--carry-costs", "10"]) == 3
    rep = tools.verify_carry(str(csv), str(f), capital_cost_apr=0.05, perp_leverage=2.0)
    assert any(c["id"] == "carry_decomposition" for c in rep["checks"]) and tools.verify_carry in tools.TOOLS
