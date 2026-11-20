# Implementation plan: type-aware verification profiles

> Historical design note, partly superseded: profiles shipped as `monte-neo verify --profile ID` (see the profiles guide) and the `monte-neo catalog` CLI sketched below does not exist. Original text: design only, no code in `src/monte_neo` is changed in phase 1. Implementation starts after the verifier-improvement branch (stream M) is merged, to avoid conflicts. Estimates are rough.

## 1. Goal

A strategy is verified with checks and a benchmark chosen by its **type**, not only the generic gates. A short-vol strategy gets a tail test; a trend strategy is compared with buy-and-hold and decomposed into alpha and beta; carry gets roll/funding decomposition; stat-arb gets cointegration tests. Types and trap codes come from [types.yaml](types.yaml) and [traps.yaml](traps.yaml).

## 2. Profiles (what each type adds)

| Profile (type) | Benchmark | New checks (PLAN) | Existing checks used |
|---|---|---|---|
| passive_index, balanced_60_40, equal_weight, dca | itself / unrebalanced / lump sum | rebalance_sensitivity, universe_pit | data_integrity, benchmark |
| risk_parity, minimum_variance | 60/40 and 1/N at matched vol | leverage_audit, rebalance_sensitivity | pbo, benchmark |
| trend_following | buy-and-hold of the asset; beta-neutral residual | alpha_after_beta (gate), regime_split, roll_audit | timing, dsr, lookahead |
| xs_momentum, factor_premia, long_short_equity | market + factor regressions | pit_contract, borrow_model, pre_post_publication_split, tail_skew_profile | dsr, pbo |
| mean_reversion | random-entry null with matched holding time | ruin_probability, tail_skew_profile | timing, costs |
| stat_arb_pairs | zero; per-leg buy-and-hold | cointegration_suite (ADF, KPSS, Johansen, half-life, structural break), pair_selection_bias, legging_audit | dsr, costs |
| carry, crypto_specific | spot buy-and-hold; cash | carry_decomposition (roll/funding/basis), roll_audit, leverage_audit | smoothing, cost_margin |
| short_volatility, options_overlay | equity index; put-write | tail_skew_profile (skew, CVaR, worst-k), stress_replay (Feb 2018, Mar 2020), ruin_probability | smoothing, benchmark |
| event_merger_arb | market + risk-free | event_study_audit | lookahead |
| calendar_anomaly | unconditional mean | pre_post_publication_split | dsr, holdout |
| vol_managed | unmanaged asset at matched leverage | none beyond leverage_audit | lookahead, timing |
| market_making, convertible_arb, global_macro | per profile card | out of scope or "cannot verify" with explicit message | verify_quotes where applicable |

Overlap with stream M: its findings 4 (alpha/beta gate), 5 (realistic costs), 6 (regimes) and pairs checks are the same building blocks. These must be implemented once, in M, and reused here; this plan only adds the type dispatch and the remaining checks.

## 3. Code structure (proposed)

```
src/monte_neo/profiles/
  __init__.py
  schema.py        # Profile dataclass: type id, benchmark spec, required/optional checks, cannot-verify list
  registry.py      # type id -> Profile; loads packaged profiles.json generated from types.yaml
  dispatch.py      # picks the profile from strategy metadata (type field) or a CLI flag
  checks/          # one module per new check; each returns the existing CheckResult shape
    tail_skew.py  alpha_beta.py  regime_split.py  rebalance.py  carry.py
    cointegration.py  roll.py  ruin.py  leverage.py  borrow.py  pit.py ...
src/monte_neo/catalog/
  loader.py        # strategies.yaml loader and validation (build_catalog.py logic)
  impl/            # canonical signal(df) / weights(df) per strategy id, 30-60 lines each
  runner.py        # runs the protocol: split, costs, n_trials, results.csv
  report.py        # per-type tables, casualties, control calibration
```

CLI: `monte-neo catalog list|run|report` and `verify --type <id>`. Profile output is added to the verdict JSON/certificate as `profile`, with a `not_run` list for planned checks so a missing check can never silently count as passed.

## 4. Tests

- **Golden tests** per implemented strategy against published figures with tolerance (e.g. Faber 10-month SMA on the paper's sample).
- **Look-ahead mutation tests:** shift each signal by one bar into the future; the verifier must flag it for every catalog strategy.
- **Trap injection:** synthetic data with known beta, known negative skew, spliced futures, non-cointegrated pairs; each profile check must fire only on its trap (precision/recall).
- **Control calibration:** random-entry and always-flat must never reach a pass level over many seeds.
- **Schema tests:** catalog YAML valid (existing `build_catalog.py` logic in CI), every type has checks defined, every trap code has a check or a "not verifiable" note.
- Determinism: fixed seeds, data hashes.

## 5. Order of work and size

| Phase | Content | Rough size |
|---|---|---|
| P0 (after M merges) | profiles schema/registry/dispatch, catalog loader, `not_run` plumbing, catalog CI | ~1.5k lines, 3-4 sessions |
| P1 | Tier A allocation, passive, trend and calendar strategies (about 30) + alpha_after_beta, regime_split, rebalance_sensitivity | ~2.5k lines, 6-8 sessions |
| P2 | Mean reversion, controls, pairs (cointegration_suite, pair_selection_bias, legging) + ruin_probability, tail_skew | ~2.5k lines, 6-8 sessions |
| P3 | Carry and crypto (carry_decomposition, roll_audit, leverage_audit), funding data adapters | ~2k lines, 5-6 sessions |
| P4 | Tier B: data adapters (fundamentals, options, curves), pit_contract, borrow_model, event study | ~3k lines, 8-10 sessions; depends on free data availability |
| P5 | Mass run per [PROTOCOL.md](PROTOCOL.md), report, docs, README/Hall of Fame | 3-4 sessions |

Total about 12k lines and 30-40 working sessions. Weakest estimate: P4, which is data-licence and availability bound.

## 6. Data plan

Tier A: crypto from exchange public data; ETFs/indices from sources whose licence permits reproducible public use (to be checked per source; some popular retail sources forbid redistribution); Fama-French factor files from the Ken French data library; rates from FRED. Tier B has no confirmed free source for point-in-time fundamentals, delisted histories or option chains; these may stay "cannot test here" in the first run.

## 7. Risks

- Misimplemented canonical strategy is worse than none: each card needs a source cross-check before its first run (first phase-2 task).
- Evidence levels must not rise because a planned check is missing; `not_run` caps the level.
- Catalog size (100) with a small verifier-calibration set can mislead; the control table is part of every report.
