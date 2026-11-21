# ETH/BTC ratio trend (dollar-neutral)

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `ratio_trend_btc_eth`
- **type:** [Trend following / time-series momentum / CTA](../TYPES.md#trend_following)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Moskowitz Ooi Pedersen 2012 JFE (time-series momentum) applied to a relative price
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Long ETH and short BTC in equal notional when the ETH/BTC ratio is above its 100-day SMA, the reverse below; weekly

Parameters (do not tune):

- `sma` = 100
- `rebalance` = weekly

**Data needed:** ETH and BTC perpetual daily closes, funding

**Expected regime behaviour:** relative trends between the two largest coins; whipsaw in ranges

## Known traps

- **Hidden market beta** - Reported return is mostly exposure to the market or a known factor, not skill. Monte-Neo: benchmark (existing, info only); PLAN:alpha_after_beta gate.
- **Regime dependence** - Works only in one market regime (e.g. a bull market) in the sample. Monte-Neo: PLAN:regime_split (sub-period / regime stability).
- **Funding rate and basis risk** - Perpetual funding changes sign; basis can widen; exchange/margin risk is not a price series. Monte-Neo: PLAN:carry_decomposition.

## How to measure

Metrics: Sharpe, Sortino, convexity in equity down-markets (crisis alpha), beta to buy-and-hold, hit rate, payoff ratio, max drawdown.
Benchmark: Buy-and-hold of each asset; beta-neutral residual; equal-weight diversified trend index.
Horizon: Multi-decade, multi-asset; single-asset trend has few independent bets.

## What Monte-Neo cannot verify

- Diversification across markets when only one asset is supplied; futures margin details

## Worst scenario (hedged is not risk-free)

- **This strategy:** ETH and BTC decouple in a crash (betas differ): the dollar-neutral book is not beta-neutral and loses on the leg with the higher beta
- a sharp reversal after a long trend: the book is positioned the wrong way at the turn
- Counterparty: a hedge does not protect the capital held at a venue that fails.

Measure it on the strategy's net returns and legs: `monte-neo catalog worst --returns r.csv --legs legs.csv` (measured losses, leg correlation in stress, and stated shocks with their formulas).
