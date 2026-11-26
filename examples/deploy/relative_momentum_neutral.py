"""Deploy example for ``--market usdm``: a market-neutral book of two perpetuals (relative momentum).

Not investment advice. A demonstration of the plug-in contract with shorts, not a strategy that passed Monte-Neo.
Long the coin with the stronger 20-day return and short the other, half of capital each (gross exposure 1, net 0);
flat until 21 closes exist.
"""

LOOKBACK = 20


def target_weights(closes_by_symbol: dict[str, list[float]]) -> dict[str, float]:
    if len(closes_by_symbol) != 2:
        raise ValueError("this example trades exactly two symbols, for example BTCUSDT,ETHUSDT")
    (a, ca), (b, cb) = sorted(closes_by_symbol.items())
    if min(len(ca), len(cb)) <= LOOKBACK:
        return {a: 0.0, b: 0.0}
    ra, rb = ca[-1] / ca[-1 - LOOKBACK] - 1.0, cb[-1] / cb[-1 - LOOKBACK] - 1.0
    return {a: 0.5, b: -0.5} if ra > rb else {a: -0.5, b: 0.5}
