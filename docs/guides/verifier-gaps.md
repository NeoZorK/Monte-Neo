# Verifier checks added after the coverage audit

Not investment advice. Every check below is warn-only unless stated; a pass is never proof of an edge.

| Area | Check (row id) | What it does | Where |
|---|---|---|---|
| Dynamic Monte Carlo | `regime_swap_null` | Circularly shifts regime labels against the strategy returns; warns when the return is tied to a regime and the weaker regime loses (Bonferroni x2) | `monte_neo.verify.dynamic_mc` |
| | `regime_mix_bootstrap` | Stationary block bootstrap with equal time in each regime; warns when the 5 % Sharpe quantile is not positive | same |
| | `time_reversal_null` | Re-runs the strategy code on the time-reversed history; informative only (mean reversion legitimately survives reversal) | same |
| Execution | `calibrate_impact` | Fits the square-root impact coefficient (and the share exponent) from your fills; refuses fewer than 30 fills or no explanatory power | `monte_neo.verify.execution_calib` |
| | `decay_half_life_bars` | Transient impact in `simulate_execution`: earlier same-direction fills leave a decaying displacement | `monte_neo.verify.execution` |
| | `allow_rebate` | A negative maker fee is accepted only with this flag: rebate at most 1 bp, maker share at most 50 %, adverse selection charged, net fee never below zero | `verify_strategy(cost_profile=..., allow_rebate=True)` |
| Portfolio risk | `tail_dependence` | Empirical lower/upper tail dependence at q = 5 % | `monte_neo.verify.portfolio_tail`, `verify_portfolio` risk block |
| | `correlation_breakdown_stress` | Gaussian expected shortfall with correlations raised to a stress level | same |
| | `liquidity_stress` | Same targets with 30 % of the volume, 3x impact, +5 bps per side (library function, needs a capital) | `monte_neo.verify.liquidity_stress` |
| Corporate actions | `corporate_actions` | Declared splits and dividends against the prices: a split still in the prices fails, an undeclared split-like jump or a material dividend effect warns | `verify_strategy(corporate_actions=...)` |
| Legs | `legs_timing_significance`, `legs_placebo` | Shifted-copy and independent-shift tests on the leg quantities. `legs_lookahead` and `legs_signal_ic` are "not assessed" (a legs table has no signal code) | `verify --legs` |

Carry (`verify_carry`) has no new signal-level row: its look-ahead probe and decomposition already exist, and a timing test on a
basket of funding positions was not added.

## Known-error benchmark

`monte_neo.bench.known_errors` generates six well-described backtest mistakes (next-bar leak, centred window, full-sample z-score,
best of 300 random rules with trials declared, a strategy that only works without costs, an unadjusted split) and three controls
(momentum and mean reversion on serially correlated returns, random positions). Run it with
`monte-neo bench detect --seeds 20` (or `python -m monte_neo.bench.known_errors 20`); `--case <id>` limits the run, `--out` and
`--markdown` save the report, and the exit code is 5 when any case is not clean.

Measured on 20 seeds per case (synthetic hourly data, 5 + 5 bps costs):

| Case | Kind | Bad outcome rate | Verdicts |
|---|---|---|---|
| next_bar_leak | error | 0 % misses | REJECT 20 |
| centered_window | error | 0 % misses | REJECT 20 |
| global_zscore | error | 0 % misses | REJECT 20 |
| selection_bias | error | 0 % misses | REJECT 20 |
| cost_blind | error | 0 % misses | REJECT 20 |
| unadjusted_split | error | 0 % misses | REJECT 20 |
| momentum_ar | honest | 0 % false rejects | PASS_WITH_WARNINGS 20 |
| mean_reversion_ar | honest | 0 % false rejects | PASS_WITH_WARNINGS 20 |
| noise_strategy | noise | 0 % false accepts | REJECT 20 |

Read this table for what it is: the cases are written from public descriptions, not copied from other projects, but by the same
author as the verifier, on synthetic data, with 20 seeds. Zero misses on these cases says nothing about mistakes nobody
described, and the honest controls are easy ones. A first version of the honest controls was rejected because costs consumed their
edge; the controls were rebuilt with an edge that survives costs, not the checks relaxed. A truly independent set (other authors,
real data) is still missing.
