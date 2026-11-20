# Alpha Readiness Level (ARL) and depth

> The Alpha Readiness Level (ARL) was devised by Rostyslav Shcherbyna, author of Monte-Neo; it is modelled on the idea of a technology readiness level and is a Monte-Neo scale, not an industry standard.

## Authorship and history

The Alpha Readiness Level (ARL) was devised by Rostyslav Shcherbyna, author of Monte-Neo. First shipped in Monte-Neo v0.53.0
(October 2026; first commit 2026-10-11); the depth sub-scale was added in v0.55.0 (November 2026). It is a Monte-Neo scale,
not an industry standard.

## The nine levels at a glance

| ARL | Question it answers |
|---|---|
| 1 | Is the idea tested on clean data? |
| 2 | Is the backtest itself not broken (no look-ahead)? |
| 3 | Does it still earn after realistic costs? |
| 4 | Does the signal really predict (placebo and significance, after paying for the trials)? |
| 5 | Is it new alpha, beyond market and factor exposure? |
| 6 | Does it survive the search (Deflated Sharpe, overfitting probability, audited trials)? |
| 7 | Is it tradable and robust (doubled costs, one-bar delay, regimes, capacity)? |
| 8 | Does it add to your book (marginal Sharpe, forward data)? |
| 9 | Is it confirmed live, with real fills and a custody statement? |

The exact required checks of each level are in the generated table below. Each level also has four **depth** criteria, D1 Margin,
D2 Breadth, D3 Sample and D4 Out of sample, listed per level in the depth table further down.

## How to read a result

- **`ARL 4, depth 2/4`** means: levels 1 to 4 are met, and at level 4 two of the four depth criteria are met (for example margin and
  breadth), while sample size and out-of-sample are not, or were not assessed. It does **not** mean "4 out of 9 is a medium strategy".
- **`ARL 6, depth 0/4`** is a higher level than `ARL 5, depth 4/4`: depth never lifts the level.
- **`ARL 3, depth 0/4 (not assessed: ...)`**: a missing run is listed with the command that produces it; no evidence scores no points.
- A failed look-ahead check caps the level at 1 whatever else is true.

## How level and depth are computed

1. Read the checks of the certificate (and the alpha report, the live report and the sealed-holdout record when given).
2. The **level** is the highest L whose required checks, and those of every level below, are present with an allowed status.
3. The **depth** of that level counts the criteria D1 to D4 that are met; a criterion whose evidence was not produced counts 0
   and is reported as *not assessed*.
4. Caps (look-ahead, survivorship, paper or testnet data, not-significant alpha) are applied last and are listed in the
   certificate.
5. The result carries the rules version (`arl-rules/2`) and `provisional`, so a recheck recomputes it with the same rules.

The ARL rates the **evidence** about a strategy, not the strategy or its profit. It is not a recommendation to trade and
says nothing about future returns. Not investment advice.

The rules are one machine-readable file, `src/monte_neo/arl_rules_v2.json` (version `arl-rules/2`, status
**provisional**). The tables below are generated from it and a test fails when this page and the file disagree.
Every certificate records `arl.rules_version` and `arl.provisional`; `monte-neo verify --recheck` recomputes the ARL
with the version the certificate recorded.

## How the level is computed

- The level is the highest L such that the requirements of L **and of every level below it** are met.
- A requirement is met when its checks are present (not skipped) with an allowed status. Evidence that was not produced
  is **not assessed**, never passed.

<!-- arl:levels:start -->
| L | Name | Required checks (alternatives joined by "or") |
|---|------|------------------------------------------------|
| 1 | Idea on clean data | `data_integrity` or `ic` |
| 2 | The backtest is not broken | `lookahead_truncation` or `universe_lookahead` |
| 3 | It earns after costs | `net_profitability` or `market_impact` + `cost_sensitivity` |
| 4 | The signal predicts | `ic` + `signal_placebo` or `timing_significance`; `selection_adjusted_sharpe` |
| 5 | It is new alpha | `residual_alpha` + `hidden_short_volatility` |
| 6 | It survives the search | `deflated_sharpe` or `hlz_hurdle` + `min_backtest_length` |
| 7 | Tradable and robust | `market_impact` or `capacity`; `synthetic_market_null` + `universe_subsampling` + `start_date_sensitivity` or `period_consistency` + `delay_sensitivity`; `rebalance_timing_luck` or `cost_margin` |
| 8 | It adds to your book | `marginal_sharpe` |
| 9 | Confirmed live | `live_vs_backtest` + `alpha_death_monitor` + `live_source` |
<!-- arl:levels:end -->

### Levels 3 and 6 on the alpha path are read from the executable portfolio

A cross-sectional score can predict returns and still earn nothing once its portfolio pays for trading, so `monte-neo alpha` judges levels 3 and 6
on the **net returns of the top-minus-bottom portfolio**, never on the gross spread:

- **Level 3** needs `market_impact` (the portfolio earns after commission and square-root impact at your `--aum`) **and** `cost_sensitivity` (it
  earns at the modelled costs; a `warn` means it does not survive double costs, a `fail` means it does not earn at all). Without `--aum` level 3 is not assessed.
- **Level 6** needs the Deflated Sharpe on the net returns with the project's `n_trials`, or a Harvey-Liu-Zhu hurdle that is **passed** (an
  `info` row, a t-statistic below 2, no longer counts) together with the minimum backtest length. The `hlz_hurdle`, `min_backtest_length` and
  `haircut_sharpe` rows are computed on the same net returns.
- Signal significance (IC, placebo) is level 4, not 6. Without `--aum` or volume only a 1 bp commission is charged and the rows say so; with
  `--funding` the real funding of every leg is charged too.

Caps:

<!-- arl:caps:start -->
- A failed look-ahead check caps the level at 1.
- `survivorship` warning or failing caps the level at 4: the universe may be today's survivors: declare the delisted names (delisted=...) or add their prices.
- `alpha_after_beta` that ran and warned or failed blocks level 5: the return is not shown to be more than benchmark exposure.
- `universe_subsampling` that ran and warned or failed blocks level 5: the result rests on a few assets: it does not hold on random subsets of the universe.
- `noise_injection` that ran and warned or failed blocks level 5: the result does not survive small noise in the inputs: it fits exact values.
- `short_feasibility` that ran and warned or failed blocks level 5: the short side could not be borrowed or traded at the size shown.
- `residual_vs_book` that ran and warned or failed blocks level 5: the return is explained by the existing book: it is not new alpha for that book.
- `cross_market_close_alignment` that ran and warned or failed blocks level 5: the signal uses closes of markets that close later than the trade (same date, different time zone).
- `post_discovery_decay` that ran and warned or failed blocks level 5: the edge disappears after its discovery date.
- `claim_consistency` that ran and warned or failed blocks level 5: the claimed numbers are better than the verified ones.
- `universe_lookahead` that ran and warned or failed blocks level 5: the universe looks like today's members (no name added or delisted): pass a point-in-time membership file (--membership); a fixed universe declares every symbol for the whole period.
- Live data from paper, testnet, simulated (or an unstated source) caps the level at 8: paper, testnet and simulated fills are not live.
<!-- arl:caps:end -->

## Depth: how strongly a level is established

Every level has its own **depth** from 0 to 4, reported as `ARL 6, depth 3/4`. One point per criterion met. A criterion
whose evidence was not produced scores 0 and is listed as *not assessed* next to the command that produces it. **Depth
never lifts the level**: ARL 6 depth 4 is still below ARL 7 depth 0, and a level that is not reached has depth 0 (the criteria are still
listed, as `depth_if_reached`, so you can see what is missing).

<!-- arl:depth:start -->
| L | D1 Margin | D2 Breadth | D3 Sample | D4 Out of sample |
|---|---|---|---|---|
| 1 | no data warning at all (data_integrity and data_quality both pass) | two independent sources agree (data_source_replication) | at least 3 years of bars | a fresh fetch gives identical hashes |
| 2 | all four probes pass (truncation, perturbation, static lint, repaint) | probes pass at many cut points (at least 12 in truncation and perturbation) | at least 20 cut points | probes pass again on the sealed holdout |
| 3 | break-even cost at least 5x the modelled cost | profitable in at least 5 of 6 equal periods (walk-forward windows) | at least 100 closed trades | net positive on the sealed holdout |
| 4 | permutation / placebo p below 0.01 after paying for all project trials (p x n_trials) | positive in at least 70 % of periods or assets | at least 1,000 observations | significant on the sealed holdout |
| 5 | residual alpha t-statistic at least 3, after paying for all project trials | alpha survives all factors including the market beta | at least 5 years | residual alpha positive on the sealed holdout |
| 6 | Deflated Sharpe at least 0.99 with the project's full trial count | probability of backtest overfitting below 0.2 | trial count audited in the ledger and not below the real count | holdout opened once after freeze, Deflated Sharpe at least 0.95 there |
| 7 | net positive at 2x costs and a 1-bar delay | worst of regimes, rebalance phases (and subsamples, start dates when run) still passes | capacity at least 10x the planned capital | survives the sealed holdout under realistic fills (net positive, cost_realism passes) |
| 8 | marginal Sharpe interval excludes 0 | positive across sub-periods and stress | at least 3 years overlapping the book | positive on forward data |
| 9 | live Sharpe inside the backtest confidence interval | seen in at least 2 market conditions | at least 6 months and 100 fills live | real fills with a custody statement |
<!-- arl:depth:end -->

D4 comes only from a **sealed holdout**: `SealedHoldout.freeze(...)` writes the data hash, the strategy hash and the cut
before the sealed part is looked at; `open(...)` runs the frozen strategy on it **once**. A second open writes a
`reopen` entry, and D4 is 0 for every level, permanently. Levels 4 to 6 are computed with the full `n_trials` of the
project (p-values and t-statistics are multiplied by it).

## Honest rules

<!-- arl:honesty:start -->
1. Thresholds are fixed and versioned before use (arl-rules/2); a change bumps the version, and a certificate records the version it was computed with. The numbers are provisional proposals until calibrated on the Trap Suite and the wild corpus (docs/guides/alpha-calibration.md); arl-rules/2 is frozen only by the owner's decision.
2. The sealed holdout opens once. If it is opened more than once for the same strategy, D4 is 0 for every level, permanently, and the ledger shows why.
3. Trials are paid. Depth at levels 4-6 is computed with the full n_trials of the project, not of one idea.
4. Paper, testnet and simulated fills are not live. They cap ARL at 8; ARL 9 and D4 of level 9 require real fills and a custody statement.
5. No evidence, no points. 'Not assessed' is shown next to the missing run (--aum, --book, --n-trials, monitor --live).
6. A depth never lifts the level: ARL 6 depth 4 is still below ARL 7 depth 0.
7. ARL is not a recommendation to trade and says nothing about future returns.
<!-- arl:honesty:end -->

## Where it is shown

`monte-neo readiness --certificate cert.json [--alpha a.json] [--live live.json] [--holdout .monte-neo/sealed_holdout.jsonl] [--n-trials N]`,
and as `arl` in every certificate, in `verify`, `alpha`, `monitor` and `dossier` output, in the HTML report, in the GitHub
Action comment and in the MCP tools `verify_strategy` and `readiness_level`.

## Status of the numbers

The thresholds are proposals until calibrated on the Trap Suite and the wild corpus
([calibration on the Trap Suite](arl-calibration.md), [alpha checks](alpha-calibration.md)). `arl-rules/2` stays `provisional` until the owner freezes it.
