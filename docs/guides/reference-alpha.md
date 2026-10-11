# Reference alpha 1: a boring trend that is honest about itself

!!! warning "Not investment advice"
    This is an example of a method, not a recommendation, an offer or a call to trade, and not a promise of profit.
    Simulated and past results do not predict future returns. Trading can lose money.

`examples/reference_alpha/` holds a deliberately simple, low-return strategy, so you can see what a real (modest)
alpha looks like after every check of Monte-Neo: diversified time-series trend following with volatility targeting.

- **Rules fixed in advance.** Three look-back windows (63, 126, 252 bars) are averaged, never picked by results.
  Positions are sized by trailing volatility. The portfolio rebalances monthly in four weekly tranches, with a no-trade band.
- **Expectations from the literature, not a promise.** A net Sharpe of about 0.3 to 0.7 on long, diversified
  histories, drawdowns of 15 to 30 %, and years without profit.
- **When it works:** long directional moves, crises with sustained trends, many weakly correlated markets.
- **When it fails:** ranges and whipsaws, sharp V-shaped reversals, everything moving together, one instrument, high costs.
- **How to "retrain" without overfitting:** never re-tune the windows on recent performance. Volatility estimates
  update by themselves. Any rule change is a new version, registered with `monte-neo register` and counted in the ledger.

What the verifier says on three synthetic markets (12 instruments, 12 years):

| Market | Verdict | Net return | Sharpe | Deflated Sharpe |
|--------|---------|-----------|--------|-----------------|
| Planted trends | PASS_WITH_WARNINGS | +18.4 % | 0.30 | 0.84 |
| Random walks | PASS_WITH_WARNINGS | +11.7 % (luck on one path) | 0.22 | 0.77 |
| Choppy, mean-reverting | REJECT | −32.9 % | −0.65 | 0.02 |

The random-walk row is the lesson: one lucky path can look like an edge. Across eight more seeds the random walks
average −2.4 %, and the Deflated Sharpe never clears 0.95. The full rules, the tables of when it works and when it
fails, the decision table for a drawdown and the commands are in
[examples/reference_alpha/README.md](https://github.com/NeoZorK/Monte-Neo/blob/main/examples/reference_alpha/README.md).
