# Catalog tools: where a strategy can run, and whether it is new

## `monte-neo catalog compat`: venues and connectors

```bash
monte-neo catalog compat spec.json                       # from the catalog specification
monte-neo catalog compat spec.json --positions pos.csv   # also detects short selling and market neutrality
monte-neo catalog compat spec.json --leverage 3 --json
```

From the specification (`instruments` with `type` and `asset_class`, `legs`, `hedge_of`, `bar_seconds`, `sizing`) and,
when given, the measured positions (long share, net exposure), Monte-Neo derives the requirements: asset classes,
instrument types (spot, perp, future, option, CFD), short selling, leverage, intraday trading. It matches them to a
provisional venue table (`venues/1`: Binance spot and USD-M, Bybit, OKX, Deribit, Kraken, Coinbase, Interactive Brokers,
Alpaca, MetaTrader 5 brokers) and lists every venue as compatible or not, with the reasons, an indicative taker fee, the
demo environment and whether a Monte-Neo connector exists. Fees and availability change and depend on your country:
the table is a starting point, not a recommendation.

## `monte-neo catalog novelty`: a different source of return?

```bash
monte-neo catalog novelty --returns candidate.csv --catalog catalog_returns.csv
```

A strategy is **novel** to a catalog when its absolute correlation with every catalog strategy is below 0.3, also in the
catalog book's worst 10 % of days, and when adding it lifts the book's Sharpe ratio beyond the bootstrap noise (the
`marginal_sharpe` check of ARL level 8). The same idea with new parameters is not novel.
