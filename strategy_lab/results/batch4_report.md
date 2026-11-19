# Batch 4: validation report (holdout sealed)

Not investment advice.

n_trials on validation = all Lab candidates = **134**. Screened on discovery: 2016 variants (ledger head `86c5ad0119c8`).

White reality check over the 10 candidates (stationary bootstrap, 2000 draws): p = **0.038** (SPA of Hansen is not in Monte-Neo: see MONTE_NEO_GAPS.md).
Cost of the search: expected best annual Sharpe of 134 zero-skill strategies over 4.0 years = **1.32**; for the 2016 discovery variants (3.5 years) = 1.84.

| Candidate | Verdict | ARL / depth | Net Sharpe | Costs x2 | Alpha t vs BTC | Beta share | DSR |
|---|---|---|---|---|---|---|---|
| r4_b4_10_d17472 | REJECT | ARL 2, depth 0/4 (arl-rules/1, provisional) | 0.735 | 0.46 | 1.4 | 0.002 | 0.122 |
| r4_b4_1_c3f413 | PASS_WITH_WARNINGS | ARL 5, depth 2/4 (arl-rules/1, provisional) | 1.006 | 0.9 | 1.96 | 0.001 | 0.265 |
| r4_b4_2_18bcb0 | NEEDS_MORE_EVIDENCE | ARL 4, depth 2/4 (arl-rules/1, provisional) | 1.379 | 1.17 | 2.58 | 0.017 | 0.545 |
| r4_b4_3_3decb4 | NEEDS_MORE_EVIDENCE | ARL 3, depth 0/4 (arl-rules/1, provisional) | 0.495 | 0.091 | 0.98 | 0.0 | 0.05 |
| r4_b4_4_f02299 | NEEDS_MORE_EVIDENCE | ARL 5, depth 2/4 (arl-rules/1, provisional) | 0.705 | 0.431 | 1.12 | 0.041 | 0.11 |
| r4_b4_5_8b00f1 | NEEDS_MORE_EVIDENCE | ARL 3, depth 0/4 (arl-rules/1, provisional) | 0.239 | -0.175 | 0.47 | 0.0 | 0.016 |
| r4_b4_6_747d0b | NEEDS_MORE_EVIDENCE | ARL 3, depth 0/4 (arl-rules/1, provisional) | 0.781 | 0.467 | 1.47 | 0.004 | 0.142 |
| r4_b4_7_0ea5fa | NEEDS_MORE_EVIDENCE | ARL 3, depth 0/4 (arl-rules/1, provisional) | 0.213 | -0.091 | 0.5 | 0.002 | 0.013 |
| r4_b4_8_c36c6b | REJECT | ARL 2, depth 0/4 (arl-rules/1, provisional) | -0.552 | -0.762 | -1.47 | 0.045 | 0.0 |
| r4_b4_9_43d226 | NEEDS_MORE_EVIDENCE | ARL 4, depth 2/4 (arl-rules/1, provisional) | 0.651 | 0.549 | 1.09 | 0.019 | 0.086 |
