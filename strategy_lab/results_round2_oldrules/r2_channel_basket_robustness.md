# r2_channel_basket: robustness before any freeze (validation 2021-2024 and discovery; holdout NOT read)

Not investment advice. Source: `robust.py` -> `r2_channel_basket_robustness.json`. n_trials: Lab 83 + 1 (BTC-relative variant) = 84.

| Check | Net Sharpe (val) | Deflated Sharpe | ARL (alpha path) | Comment |
|---|---|---|---|---|
| Base (as run) | 1.57 | 0.74 | 6, blocked at 7 (rebalance_timing_luck) | beta share 36 %, corr BTC 0.60, corr equal-weight 0.79, alpha t vs BTC 2.75 |
| Costs x2 | 1.54 | 0.72 | n/a | slow strategy: costs are not the weak point |
| + 12 dead/crashed coins (LUNA, FTT, UST, BTT, BCC, XMR, EOS, MATIC, IOTA, ZEC, DASH, VET) | 1.53 | 0.72 | 7 | survivorship inflates Sharpe only about 0.04 here; the true dead-coin universe (hundreds) is still unknown |
| Rebalance day 0..6, worst (day 3) | 1.24 (range 1.24-1.58) | 0.51 | not measurable* | alpha t 1.94; the primary result must be the worst variant |
| Worst day on the survivors universe | 1.20 | 0.47 | not measurable* | |
| BTC-hedged by rolling beta | 1.81 | 0.89 | unchanged signal | corr BTC 0.15, beta share 2 %, alpha t 3.43, return falls 14.6x -> 8.4x |
| Signal minus BTC's signal (long-short, hedged), new variant | 1.63 | 0.83 | 3, blocked at ic | no cross-sectional IC: the edge is trend in the market factor, not rank among coins |
| AUM 50k / 500k / 5M | | | 6 / 2 / 2 | market_impact: net +85 % / -6 % / -296 % per year in the alpha model |

\* Thinning the scores to every 7th day makes the alpha path see no signal on other days (gross falls to 4 %), so its ARL per rebalance day (2 or 6) is an artifact of that input and not a valid measurement. The native check `rebalance_timing_luck` (21 start days) gives net return from -4.8 % to +73.8 % per year (median +33.8 %): the result depends strongly on the rebalance day.

## Verification as a strategy (point 1)
No CLI path verifies a multi-asset basket as code: `verify --strategy` takes one OHLCV, `portfolio` takes one OHLCV, and `alpha` writes an `alpha-report/1` that has **no certificate_id and no ledger entry** (that is why the id was None). This is a gap for stream M.
What can be done: (a) the basket net returns through `verify --returns`: certificate `c070b9cdcb4f43ba`, ARL 0 (returns-only), flagged by the known false positives `zero_kink` and `round_numbers` (idle days), DSR 0.89 for 84 strategies; (b) the same rule per coin as a real strategy: 18 certificates with ids (all in the JSON). 6 PASS_WITH_WARNINGS with ARL 4 (BTC, ETH, BNB, ADA, SOL, AVAX), 2 NEEDS_MORE_EVIDENCE with ARL 4 (DOGE, DOT), 3 REJECT (XRP, LTC, BCH: net_profitability and deflated Sharpe), 7 NEEDS_MORE_EVIDENCE with ARL 3 and deflated Sharpe below 0.3. Timing p < 0.05 holds for BTC, ETH, BNB, ADA, SOL, AVAX, DOGE, DOT only.

## Honest conclusion
ARL 6 is not robust. (1) The alpha path rates the quintile long-short *rank signal* (gross 131 %), not the long-flat basket that would be traded. (2) Realistic capacity ends near 50k USDT: at 500k the model's net is negative. (3) The worst rebalance day gives deflated Sharpe 0.51 (< 0.95), and 36 % of the return is BTC beta; neutralised, it is a trend edge with deflated Sharpe 0.89 (< 0.95), and the pure cross-sectional version has no IC. (4) Survivorship adds little in this test but cannot be bounded. The candidate does not meet the Lab's own bar (deflated Sharpe >= 0.95) under the worst variant. Whether to freeze it is the owner's decision; the evidence says "interesting trend factor, not a verified alpha".
