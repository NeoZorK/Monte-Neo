"""Strategy Lab round-2 cost model (no network, no data)."""

import importlib.util
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "examples" / "strategies" / "_common" / "binance_costs.py"
spec = importlib.util.spec_from_file_location("binance_costs", p)
bc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bc)


def test_costs_by_coin_and_venue():
    assert bc.side_bps("BTCUSDT", "spot") == 12.0
    assert bc.side_bps("BTCUSDT", "perp") == 7.0
    assert bc.side_bps("UNKNOWNUSDT", "spot") == 22.0  # small coin: wide default spread


def test_doubling_costs_doubles_both_parts():
    assert bc.side_bps("ETHUSDT", "perp", mult=2.0) == 2 * bc.side_bps("ETHUSDT", "perp")
    assert bc.side_frac("ETHUSDT", "spot") == bc.side_bps("ETHUSDT", "spot") / 1e4
