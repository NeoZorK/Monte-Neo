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

## `monte-neo catalog worst`: the worst-scenario card

A market-neutral book has a small daily volatility, so its Sharpe ratio and drawdown can look safe while the losses that
matter come from events its history may not hold. The card puts both on one page:

```bash
monte-neo catalog worst --returns book.csv --legs legs.csv --short-weight 0.5 --venue-share 1.0 --out worst.md
```

- **Measured** on the net returns: worst bar, worst 5 and 21 bars, maximum drawdown and its length, expected shortfall
  of the worst 1 % of bars, share of losing months.
- **Hedge** (with `--legs`: date, long-leg return, short-leg return): correlation of the legs on all bars and on the 10 %
  worst bars of the long leg, and the worst month of the long leg alone (what is lost if the hedge stops working).
- **Stated shocks**, each with its formula: a short squeeze (`--squeeze-jump`, default +50 % in one bar), a spread break
  (three times the worst one-bar spread move), a funding spike (`--funding-bps-day`, 30 days), and a venue failure
  (`--venue-share`). The venue failure is shown beside the headline, as a counterparty loss a hedge does not protect.

The headline is the largest market loss on the card. The stated shocks are assumptions, not forecasts. Every
market-neutral and arbitrage card of the strategy catalog (`docs/catalog/`, extension MN-1 included) carries a
"Worst scenario" section and this command.
