"""Venue compatibility: requirements from the specification and measured positions, matched to the venue table."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from monte_neo.catalog.compat import compat, requirements, venues
from monte_neo.cli import catalog_cmd


def _ok(res: dict) -> set[str]:
    return {r["venue"] for r in res["venues"] if r["compatible"]}


def test_long_only_crypto_spot_runs_on_crypto_spot_venues() -> None:
    res = compat({"instruments": [{"symbol": "BTCUSDT", "type": "spot", "asset_class": "CRY"}]})
    ok = _ok(res)
    assert {"binance_spot", "bybit", "okx", "coinbase"} <= ok and "ibkr" not in ok
    assert res["venues"][0]["compatible"]  # compatible venues are listed first


def test_short_selling_rules_out_spot_only_venues() -> None:
    spec = {"instruments": [{"symbol": "BTCUSDT", "type": "perp", "asset_class": "CRY"}, {"symbol": "ETHUSDT", "type": "perp", "asset_class": "CRY"}]}
    res = compat(spec, {"long_share": 0.5, "net_exposure": 0.01})
    assert res["requirements"]["short"] and "market-neutral" in " ".join(res["requirements"]["short_why"])
    ok = _ok(res)
    assert "binance_usdm" in ok and "binance_spot" not in ok and "coinbase" not in ok
    why = next(r for r in res["venues"] if r["venue"] == "binance_spot")["why_not"]
    assert any("perp" in w for w in why)


def test_equities_with_leverage_and_errors() -> None:
    spec = {"instruments": [{"symbol": "SPY", "type": "spot", "asset_class": "EQ"}], "bar_seconds": 300}
    res = compat(spec, leverage=3)
    assert "ibkr" in _ok(res) and "alpaca" not in _ok(res)  # 3x is above Alpaca's 2x in the table
    assert requirements(spec)["intraday"]
    with pytest.raises(ValueError):
        compat({"instruments": [{"symbol": "X"}]})
    assert venues()["status"] == "provisional"


def test_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    spec = tmp_path / "s.json"
    spec.write_text(json.dumps({"instruments": [{"symbol": "EURUSD", "type": "spot", "asset_class": "FX"}]}))
    assert catalog_cmd.main(["compat", str(spec)]) == 0
    out = capsys.readouterr().out
    assert "OK Interactive Brokers" in out and "-- Binance spot" in out and "no recommendation" in out
