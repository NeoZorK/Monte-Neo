# Batch 1: validation report (holdout sealed)

Not investment advice.

n_trials on validation = all Lab candidates = **134**. Screened on discovery: 600 variants (ledger head `accc3f72d086`).

White reality check over the 6 candidates (stationary bootstrap, 2000 draws): p = **0.048** (SPA of Hansen is not in Monte-Neo: see MONTE_NEO_GAPS.md).
Cost of the search: expected best annual Sharpe of 134 zero-skill strategies over 4.0 years = **1.32**; for the 600 discovery variants (3.5 years) = 1.66.

| Candidate | Verdict | ARL / depth | Net Sharpe | Costs x2 | Alpha t vs BTC | Beta share | DSR |
|---|---|---|---|---|---|---|---|
| r4_b1_1_a6e3c6 | NEEDS_MORE_EVIDENCE | ARL 3, depth 0/4 (arl-rules/1, provisional) | 0.778 | 0.51 | 1.51 | 0.001 | 0.138 |
| r4_b1_2_67cbd4 | REJECT | ARL 2, depth 0/4 (arl-rules/1, provisional) | 0.861 | 0.688 | 1.42 | 0.046 | 0.183 |
| r4_b1_3_30e0e5 | NEEDS_MORE_EVIDENCE | ARL 3, depth 0/4 (arl-rules/1, provisional) | 0.381 | 0.0 | 0.77 | 0.0 | 0.031 |
| r4_b1_4_5ca9f9 | REJECT | ARL 2, depth 0/4 (arl-rules/1, provisional) | 0.8 | 0.25 | 1.6 | 0.0 | 0.147 |
| r4_b1_5_ff0569 | NEEDS_MORE_EVIDENCE | ARL 4, depth 2/4 (arl-rules/1, provisional) | 1.061 | 0.668 | 2.02 | 0.005 | 0.305 |
| r4_b1_6_f00bda | REJECT | ARL 2, depth 0/4 (arl-rules/1, provisional) | 0.846 | 0.562 | 1.72 | 0.0 | 0.175 |
