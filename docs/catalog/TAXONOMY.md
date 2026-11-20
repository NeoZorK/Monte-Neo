# Taxonomy (v0.56, provisional)

Structure of the strategy catalog. The labelling rules (`catalog-rules/1`, provisional) and the command
`monte-neo catalog classify` arrive in v0.56; the 100 existing records still use the families in [TYPES.md](TYPES.md) until
they are moved to the new ids.

## Levels

1. **Category**: how the signal is formed (24 codes below).
2. **Subcategory**: the concrete scheme inside a category.
3. **Asset class**: EQ equities, IDX indices, RAT rates and bonds, FX, CMD commodities, CRY crypto, VLX volatility, CRD credit, MULTI multi-asset.
4. **Strategy**: catalog id `MN-<category>-<asset class>-NNN`, for example `MN-TSM-FX-001`. Ids are never reused.

## Categories

| Code | Category | Examples of subcategories |
|---|---|---|
| TSM | Time-series trend | time-series momentum, breakouts, moving averages, trend with volatility targeting |
| XSM | Cross-sectional momentum | 12-1 price momentum, industry, residual, 52-week high |
| MR | Mean reversion (one asset) | short-term reversal, bands and oscillators, overnight/intraday, gaps |
| SA | Statistical arbitrage | pairs, baskets and PCA, ETF versus constituents, cross-venue spreads |
| ARB | Law-of-one-price arbitrage | merger arbitrage, index/ETF NAV, convertibles, cash-and-carry basis |
| CAR | Carry | FX carry, perpetual funding, futures roll yield, term structure, dividend carry |
| VAL | Value | book-to-market, earnings and cash-flow yields, PPP value in FX, value in commodities and bonds |
| FAC | Other characteristics | quality, profitability, investment, size, low volatility and low beta, accruals, issuance |
| VOL | Volatility | selling volatility, variance risk premium, long volatility and tail hedges, volatility targeting, dispersion |
| OPS | Option structures | covered calls, protective puts, collars, vertical and calendar spreads, iron condors |
| EVT | Events | post-earnings drift, index inclusions, lock-up expiries, delistings, macro releases |
| SEA | Seasonality | turn of the month, day of the week, holidays, intraday profile |
| MAC | Macro signals | rates and curve, inflation, growth, risk-on/risk-off regimes, cross-market signals |
| MLP | Model forecasts | machine learning, text and sentiment, alternative data, ensembles |
| TEC | Technical patterns | candlestick and chart patterns, support and resistance, Fibonacci, pivots |
| OFL | Order flow (bars of one minute or more) | volume imbalance, volume profile, VWAP deviation, open interest, liquidations |
| ALC | Allocation rules without a forecast | buy and hold, 60/40, equal weight, risk parity, minimum variance, rebalancing |
| PRT | Institutional portfolio construction | mean-variance, Black-Litterman, HRP, risk budgeting, CPPI, LDI, glide paths, tactical allocation, 130/30, portable alpha |
| EQL | Equity long/short | fundamental long/short, sector rotation, quant market neutral, short bias, buybacks and insider trades, analyst revisions |
| HED | Overlays and hedging | beta hedge, currency hedge, portfolio tail hedge |
| GRD | Position-sizing schemes | grid, martingale, anti-martingale, pyramiding, averaging down |
| COP | Copying and aggregation | copy trading, strategies built on other strategies' signals, manager selection |
| MM | Liquidity provision (not high-frequency) | market making on bars, resting limit grids |
| HFT | High-frequency (under one minute) | market making, latency and cross-venue arbitrage, rebate capture; verifiable only in part (see [coverage limits](../guides/coverage-limits.md)) |

Out of scope: sports and game betting, prediction markets, and illegal practices (spoofing, quote stuffing, front-running).

## Tags

Return source, position structure, instrument, holding period, breadth, data needed, risk shape (skew), capacity, and how
much of the strategy Monte-Neo can verify. A declared label is checked against the measured behaviour; a conflict is
reported as a label mismatch.

## Type tag and type mask

Labelling is automatic: the classifier reads the specification and the verified positions and returns the main category,
subcategory, components (filters, overlays, blend parts, sleeves), tags, and a **type mask**: a fixed-layout code of every
category the strategy uses and in what role. A readable **type tag** is derived from the mask, for example `#TSM.FX+f:VOL`
(trend on FX with a volatility filter). The type tag says which kinds are inside; the catalog id says which entry; a hash
of the specification says which exact rules. Records are never labelled by hand.

## Labelling command

```bash
monte-neo catalog classify spec.json --positions positions.csv --prices close.csv
monte-neo catalog mask tm1:...
monte-neo catalog categories
```

`spec.json` (`catalog-spec/1`) declares instruments, legs, signal inputs, sizing and components; the positions and prices
give the measured labels (holding time, breadth, long share, net exposure, beta, sign correlation with past returns, skew,
size after a loss, calendar concentration). Twelve rules are applied in order and the first that fires gives the main
category; every rule that fired is stored with its reason. The record (`catalog-label/1`) holds the type mask
(`type-mask/1`, 73 bits), the readable type tag, the catalog id prefix (`MN-<category>-<asset class>-`), the hash of the
specification and the flags: `label_mismatch` (declared and measured labels differ), `unconfirmed` (only the declaration
gave the category), `no_dominant_component` and `unexplained_component` (blends). The label never changes a verdict.
The thresholds live in `src/monte_neo/catalog/catalog_rules_v1.json` and are calibrated on synthetic strategies with known labels.
