# Batch 2: validation report (holdout sealed)

Not investment advice.

n_trials on validation = all Lab candidates = **134**. Screened on discovery: 2016 variants (ledger head `86c5ad0119c8`).

White reality check over the 10 candidates (stationary bootstrap, 2000 draws): p = **0.134** (SPA of Hansen is not in Monte-Neo: see MONTE_NEO_GAPS.md).
Cost of the search: expected best annual Sharpe of 134 zero-skill strategies over 4.0 years = **1.32**; for the 2016 discovery variants (3.5 years) = 1.84.

| Candidate | Verdict | ARL / depth | Net Sharpe | Costs x2 | Alpha t vs BTC | Beta share | DSR |
|---|---|---|---|---|---|---|---|
| r4_b2_10_75bb77 | NEEDS_MORE_EVIDENCE | ARL 3, depth 0/4 (arl-rules/1, provisional) | -0.14 | -0.264 | -0.37 | 0.003 | 0.002 |
| r4_b2_1_1d13a6 | NEEDS_MORE_EVIDENCE | ARL 4, depth 2/4 (arl-rules/1, provisional) | 1.247 | 1.141 | 2.49 | 0.0 | 0.451 |
| r4_b2_2_878e53 | NEEDS_MORE_EVIDENCE | ARL 3, depth 0/4 (arl-rules/1, provisional) | -0.028 | -0.381 | -0.01 | 0.001 | 0.004 |
| r4_b2_3_5319b8 | NEEDS_MORE_EVIDENCE | ARL 4, depth 2/4 (arl-rules/1, provisional) | 0.641 | 0.553 | 0.85 | 0.092 | 0.091 |
| r4_b2_4_a401cf | NEEDS_MORE_EVIDENCE | ARL 3, depth 0/4 (arl-rules/1, provisional) | 0.329 | 0.061 | 0.63 | 0.0 | 0.023 |
| r4_b2_5_b52573 | NEEDS_MORE_EVIDENCE | ARL 4, depth 2/4 (arl-rules/1, provisional) | 0.716 | 0.59 | 1.23 | 0.019 | 0.123 |
| r4_b2_6_f8e6f4 | REJECT | ARL 2, depth 0/4 (arl-rules/1, provisional) | 0.421 | 0.271 | 0.63 | 0.02 | 0.039 |
| r4_b2_7_f672ef | NEEDS_MORE_EVIDENCE | ARL 5, depth 3/4 (arl-rules/1, provisional) | 0.485 | 0.039 | 1.0 | 0.0 | 0.049 |
| r4_b2_8_1d322a | NEEDS_MORE_EVIDENCE | ARL 4, depth 2/4 (arl-rules/1, provisional) | 0.146 | 0.072 | 0.15 | 0.008 | 0.01 |
| r4_b2_9_6fb801 | NEEDS_MORE_EVIDENCE | ARL 3, depth 0/4 (arl-rules/1, provisional) | 0.252 | -0.146 | 0.46 | 0.001 | 0.017 |
