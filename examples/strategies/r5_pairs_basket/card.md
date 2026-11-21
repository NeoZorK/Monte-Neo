# Pairs basket: six rolling-hedge spreads on perpetuals, equal risk

> Not investment advice. A research example for testing a verification pipeline, not a call to trade or a promise of profit. Simulated results do not predict future returns.

## The idea

Six pairs of related perpetuals (ETH/BTC, SOL/ETH, BNB/BTC, LTC/BTC, LINK/ETH, ADA/XRP). For each, regress the log price on the partner's over a rolling 90-day window and trade the residual spread: sell it above a z-score of 2, buy it below -2, close inside 0.5, and stop out beyond 4. Each pair runs at gross exposure 1; the book is the mean of the pairs open that day. Funding is paid by the long leg and received by the short leg.

## Why it might work

`pairs_btc_eth` showed that one spread is one bet: when its relationship breaks, the book has nothing else. Six spreads that break at different times give the reversion several independent chances. The book stays hedged against the market direction.

## Where it breaks

- Relationships between coins change (listings, narratives, token unlocks); the stop at |z| > 4 limits, but does not remove, the loss of a spread that never returns.
- The pairs share BTC and ETH legs, so they are not six independent bets: `research transfer` reports the effective number.
- Costs: two legs per change. Funding can turn against one leg for weeks.
- Phantom profit: the book is re-derived from leg quantities (`verify --legs`) and must not earn on independent random walks (`--null-test`).

## Fixed before looking at data

window 90, entry 2.0, exit 0.5, stop 4.0 (grid: window 60/90/120 by entry 1.5/2/2.5; every grid point counts as a trial). Costs: 10 bps commission + 5 bps slippage per side per leg; fills on the next bar.

## How it is tested

As for every Strategy Lab idea: discovery, validation, walk-forward of the parameter family at freeze, replication on pairs outside the search, then the sealed holdout once. `report.md` is written after the run.
