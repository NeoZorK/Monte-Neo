"""Round-2 cost model for the Strategy Lab: Binance fees by tier plus a spread/slippage assumption per coin.

Not investment advice. Fee numbers are the public Binance schedule as the Lab authors understood it (taker, in basis points of
notional, checked by the owner against the fee page before any claim); they change, so the tier is a parameter. Spread/slippage is an
ASSUMPTION for small market orders (up to a few tens of thousands of USDT per order), not a measurement: the verifier warns when
spreads estimated from daily bars are far above these numbers, and every result is also reported with the cost doubled.
"""

from __future__ import annotations

# (spot taker, USD-M perpetual taker) in bps per side. VIP0 = regular account without BNB discount: the conservative default.
FEE_TIERS = {"VIP0": (10.0, 5.0), "VIP0_BNB": (7.5, 4.5), "VIP1": (9.0, 4.0), "VIP2": (8.0, 4.0)}
DEFAULT_TIER = "VIP0"

# half-spread + slippage per side in bps
SLIP_BPS = {"BTCUSDT": 2.0, "ETHUSDT": 3.0, "BNBUSDT": 4.0, "XRPUSDT": 5.0, "SOLUSDT": 5.0, "DOGEUSDT": 5.0, "ADAUSDT": 5.0,
            "LTCUSDT": 5.0, "TRXUSDT": 5.0, "LINKUSDT": 7.0, "BCHUSDT": 7.0, "AVAXUSDT": 7.0, "DOTUSDT": 7.0, "ATOMUSDT": 8.0,
            "UNIUSDT": 8.0, "XLMUSDT": 8.0, "ETCUSDT": 8.0, "NEOUSDT": 12.0}
DEFAULT_SLIP_BPS = 12.0  # small or unknown coins


def side_bps(sym: str, venue: str = "spot", mult: float = 1.0, tier: str = DEFAULT_TIER) -> float:
    """Cost of one side (entry or exit) of one leg in bps. `mult` = 2 doubles fee and slippage (the sensitivity test)."""
    spot, perp = FEE_TIERS[tier]
    fee = spot if venue == "spot" else perp
    return (fee + SLIP_BPS.get(sym, DEFAULT_SLIP_BPS)) * mult


def side_frac(sym: str, venue: str = "spot", mult: float = 1.0, tier: str = DEFAULT_TIER) -> float:
    return side_bps(sym, venue, mult, tier) / 1e4
