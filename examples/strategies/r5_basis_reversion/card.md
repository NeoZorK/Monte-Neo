# Basis reversion: long spot, short perpetual when the perpetual premium is stretched

> Not investment advice. A research example for testing a verification pipeline, not a call to trade or a promise of profit. Simulated results do not predict future returns.

## The idea

For each of BTC, ETH, BNB, SOL, XRP and LTC, take the log premium of the perpetual over spot. When its 60-day z-score rises above 2, buy spot and sell the perpetual in equal notional; close both legs when the z-score falls below 0.5. Equal capital per coin; each position holds its spot notional plus 25 % margin for the short perpetual.

## Why it might work

Spot and perpetual are the same asset: the premium is held near zero by funding payments and by arbitrageurs. A stretched premium is demand for leveraged longs; the short perpetual collects the convergence and the funding those longs pay. This is arbitrage of the law of one price, hedged against direction by construction.

## Where it breaks

- Daily closes of two markets are not simultaneous trades: part of a measured premium is timing noise, and the next-bar fill gives some of it back.
- Four fills per round trip: costs eat small premia. The cost model charges 15 bps per side per leg.
- A premium can stay stretched for weeks (2021) while funding is paid daily; the margin of the short leg can be called in a fast rally.
- Counterparty: both legs sit on one venue. The worst-scenario card (`monte-neo catalog worst`) states that loss beside the market ones.

## Fixed before looking at data

window 60, entry 2.0, exit 0.5 (grid: window 30/60/90 by entry 1.5/2/2.5; every grid point counts as a trial). Costs: 10 bps commission + 5 bps slippage per side per leg; fills on the next bar; funding from the data, received by the short perpetual.

## How it is tested

Discovery, validation and a sealed holdout as in every Strategy Lab idea; the holdout is opened once for the candidate frozen in a git commit. Before the holdout the candidate must pass the walk-forward of its parameter family (`research freeze`) and the cross-market replication on coins outside the search (`research transfer`). `report.md` is written by `scripts/strategy_lab/analyze.py` after the run.
