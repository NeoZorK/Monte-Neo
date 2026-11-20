# Strategy Lab round 3: gate table (validation 2021-2024, holdout sealed)

Not investment advice. Rules: arl-rules/1 (provisional). Candidate gate: ARL>=6 with depth>=2; Deflated Sharpe>=0.95 at the worst rebalance phase; profit after costs x2; alpha t vs BTC>=2; capacity>=250k USDT; survivorship inflation<=25 %; n_trials = whole Lab.

| Idea | Verdict | ARL / depth | Net Sharpe | Sharpe costs x2 | Alpha t vs BTC | Beta share | Gate |
|---|---|---|---|---|---|---|---|
| bollinger_mr_eth | REJECT | ARL 2, depth 2/4 | 0.437 | 0.397 | 0.15 | 0.225 | closed: ARL<6 |
| donchian_btc | NEEDS_MORE_EVIDENCE | ARL 4, depth 2/4 | 0.969 | 0.942 | 1.25 | 0.353 | closed: ARL<6 |
| funding_carry_basket | PASS_WITH_WARNINGS | ARL 1, depth 0/4 | 5.689 | None | 11.42 | 0.001 | closed: ARL<6 |
| pairs_btc_eth | NEEDS_MORE_EVIDENCE | ARL 1, depth 0/4 | 0.004 | None | 0.14 | 0.007 | closed: ARL<6 |
| r2_carry_basket_v2 | PASS_WITH_WARNINGS | ARL 1, depth 0/4 | 6.669 | 4.999 | 13.38 | 0.0 | closed: ARL<6 |
| r2_channel_basket | PASS_WITH_WARNINGS | ARL 6, depth 0/4 | 1.568 | 1.542 | 2.75 | 0.362 | ARL>=6 but fails DSR/capacity (see robustness) |
| r2_mean_reversion_basket | REJECT | ARL 2, depth 0/4 | -2.322 | -2.924 | -4.56 | 0.004 | closed: ARL<6 |
| r2_relative_trend_neutral | NEEDS_MORE_EVIDENCE | ARL 3, depth 0/4 | 1.012 | 0.932 | 1.96 | 0.002 | closed: ARL<6 |
| r2_resid_mom_neutral | PASS_WITH_WARNINGS | ARL 3, depth 0/4 | 0.882 | 0.768 | 1.73 | 0.0 | closed: ARL<6 |
| r2_trend_basket | NEEDS_MORE_EVIDENCE | ARL 3, depth 0/4 | 1.392 | 1.375 | 2.32 | 0.416 | closed: ARL<6 |
| r3_bab_beta | NEEDS_MORE_EVIDENCE | ARL 4, depth 2/4 | 1.202 | 1.167 | 2.14 | 0.039 | closed: ARL<6 |
| r3_funding_crowding | NEEDS_MORE_EVIDENCE | ARL 3, depth 0/4 | 0.777 | 0.696 | 1.58 | 0.0 | closed: ARL<6 |
| r3_longterm_reversal | REJECT | ARL 2, depth 0/4 | 0.79 | 0.751 | 1.44 | 0.009 | closed: ARL<6 |
| r3_max_lottery | REJECT | ARL 2, depth 0/4 | -0.813 | -0.896 | -1.52 | 0.005 | closed: ARL<6 |
| r3_volume_reversal | REJECT | ARL 2, depth 0/4 | -1.102 | -1.55 | -2.22 | 0.0 | closed: ARL<6 |
| rsi2_mr_btc | REJECT | ARL 2, depth 2/4 | 0.103 | 0.016 | -0.52 | 0.187 | closed: ARL<6 |
| sma_trend_eth | NEEDS_MORE_EVIDENCE | ARL 3, depth 1/4 | 0.674 | 0.63 | 0.5 | 0.368 | closed: ARL<6 |
| tsmom_btc | NEEDS_MORE_EVIDENCE | ARL 3, depth 2/4 | 0.828 | 0.776 | 0.73 | 0.564 | closed: ARL<6 |
| turn_of_month_btc | NEEDS_MORE_EVIDENCE | ARL 3, depth 0/4 | 0.431 | 0.284 | 0.27 | 0.155 | closed: ARL<6 |
| voltarget_trend_btc | PASS_WITH_WARNINGS | ARL 3, depth 2/4 | 0.92 | 0.857 | 1.04 | 0.489 | closed: ARL<6 |
| xs_momentum_spot | NEEDS_MORE_EVIDENCE | ARL 3, depth 0/4 | 0.198 | 0.136 | 0.29 | 0.004 | closed: ARL<6 |

Only r2_channel_basket reached ARL 6 (depth 0): worst rebalance phase DSR 0.51, capacity about 50k USDT, 36 % BTC beta share. Best round-3 idea r3_bab_beta: ARL 4, hedged Sharpe 1.19, DSR 0.45 (worst phase 0.10), capacity about 50k. No candidate: the holdout stays sealed.
