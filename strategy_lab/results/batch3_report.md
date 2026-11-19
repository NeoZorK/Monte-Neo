# Batch 3: validation report (holdout sealed)

Not investment advice.

n_trials on validation = all Lab candidates = **134**. Screened on discovery: 2016 variants (ledger head `86c5ad0119c8`).

White reality check over the 10 candidates (stationary bootstrap, 2000 draws): p = **0.074** (SPA of Hansen is not in Monte-Neo: see MONTE_NEO_GAPS.md).
Cost of the search: expected best annual Sharpe of 134 zero-skill strategies over 4.0 years = **1.32**; for the 2016 discovery variants (3.5 years) = 1.84.

| Candidate | Verdict | ARL / depth | Net Sharpe | Costs x2 | Alpha t vs BTC | Beta share | DSR |
|---|---|---|---|---|---|---|---|
| r4_b3_10_192ad0 | NEEDS_MORE_EVIDENCE | ARL 3, depth 0/4 (arl-rules/1, provisional) | 0.276 | 0.008 | 0.48 | 0.002 | 0.018 |
| r4_b3_1_68ed02 | PASS_WITH_WARNINGS | ARL 5, depth 2/4 (arl-rules/1, provisional) | 1.29 | 1.084 | 2.27 | 0.058 | 0.479 |
| r4_b3_2_0994ba | NEEDS_MORE_EVIDENCE | ARL 3, depth 0/4 (arl-rules/1, provisional) | 0.344 | 0.238 | 0.43 | 0.029 | 0.029 |
| r4_b3_3_1df4d9 | NEEDS_MORE_EVIDENCE | ARL 3, depth 0/4 (arl-rules/1, provisional) | -0.028 | -0.381 | -0.01 | 0.001 | 0.004 |
| r4_b3_4_2f7d69 | NEEDS_MORE_EVIDENCE | ARL 4, depth 1/4 (arl-rules/1, provisional) | 0.616 | 0.487 | 0.96 | 0.034 | 0.084 |
| r4_b3_5_278b34 | NEEDS_MORE_EVIDENCE | ARL 4, depth 2/4 (arl-rules/1, provisional) | 0.833 | 0.69 | 1.26 | 0.089 | 0.171 |
| r4_b3_6_2f0ff3 | REJECT | ARL 2, depth 0/4 (arl-rules/1, provisional) | 0.526 | -0.014 | 0.99 | 0.001 | 0.055 |
| r4_b3_7_e82a94 | NEEDS_MORE_EVIDENCE | ARL 3, depth 0/4 (arl-rules/1, provisional) | -0.048 | -0.15 | -0.21 | 0.005 | 0.003 |
| r4_b3_8_2fbb8e | NEEDS_MORE_EVIDENCE | ARL 4, depth 2/4 (arl-rules/1, provisional) | 1.128 | 1.065 | 1.8 | 0.142 | 0.352 |
| r4_b3_9_e8aa17 | REJECT | ARL 2, depth 0/4 (arl-rules/1, provisional) | -0.47 | -0.762 | -1.03 | 0.003 | 0.0 |
