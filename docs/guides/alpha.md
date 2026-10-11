# Alpha validation: does a ranking signal predict returns, and can it be traded?

`monte-neo alpha` (MCP tool `validate_alpha`) checks a **cross-sectional score**: a number per symbol and date that
should rank the returns that follow. It answers two questions a fund's research committee asks before a signal gets
capital:

1. **Does the score predict anything?** (family A, signal power)
2. **Can its portfolio be traded at the size you plan?** (family D, implementability)

```bash
monte-neo alpha --demo                                              # no files: a weak real edge and a noise score
monte-neo alpha --ohlcv universe.csv --scores scores.csv --aum 5e7  # your data and the capital you plan to run
```

Inputs:

- `--ohlcv`: one long table for the universe with `timestamp`, `symbol`, `close` and, for family D, `volume`.
- `--scores`: `timestamp` (or `date`), `symbol`, `score`. The score at *t* ranks the returns **after** *t*.
  Scores are never filled forward, and a score dated after the last price is an error.

The output is an `alpha-report/1` report with a verdict, the checks, metrics and next actions.

## Family A: signal power

| Check | What it measures | Status |
|-------|------------------|--------|
| `ic` | Mean rank (Spearman) IC per date against the next return, ICIR and a Newey-West t-statistic | `info` when the mean IC is positive and t ≥ 2, else `warn` |
| `ic_decay` | IC at horizons 1 to 20 bars, the best horizon and the half-life | `info` |
| `quantile_monotonicity` | Do returns rise from the worst to the best quantile, or does all the profit sit in one tail? | `pass` or `warn` |
| `long_short_legs` | Share of the spread earned by the short leg | `warn` above 70 % |
| `breadth_consistency` | A claimed IR (`--claim-ir`) against IC × √breadth | `warn` above twice the implied IR |
| `signal_placebo` | 200 scores permuted among symbols within each date: does the real score beat them? | `fail` when p > 0.10 |
| `selection_vs_timing` | Is the spread stock selection, or a fixed tilt that survives shuffled dates? | `info` |

## Family D: implementability

The portfolio is long the top quantile and short the bottom one, with equal weights.

| Check | What it measures | Status |
|-------|------------------|--------|
| `market_impact` | Square-root impact at `--aum` (trailing 20-bar volatility and dollar volume, no look-ahead) | `fail` when the net return is ≤ 0, `warn` when impact eats more than half the gross |
| `participation_limit` | Your trades as a share of each bar's volume at `--aum` | `warn` when the 95th percentile is above 5 %, `fail` above 20 % |
| `capacity_curve` | Net Sharpe from 100 thousand to 10 billion: where it halves and where it reaches zero | `info` |
| `short_feasibility` | Short exposure in the least liquid names, and borrow (300 bps a year unless stated) against the short leg's profit | `warn` |
| `turnover_vs_decay` | Holding period against the IC half-life | `info` |
| `rebalance_timing_luck` | The same portfolio rebalanced every 21 bars on each of the 21 possible days | `warn` when the spread of results exceeds the median |

Without `--aum`, market impact and participation are skipped and the report says why.

## Families B, C, E, F, G and I: on the score's long-short portfolio

These families judge the returns of the same top-minus-bottom portfolio, **before costs**: they ask whether the
signal is real. Costs and size are family D's job.

| Family | Checks | Needs |
|--------|--------|-------|
| B, attribution | `factor_exposure`, `residual_alpha` (is it alpha after market, size, momentum, reversal and low-volatility factors? t ≥ 3 passes), `factor_spanning`, `hidden_short_volatility` (steady gains and rare crashes), `market_timing_beta`, `crowding`, `known_anomaly_match` | factors are built from your universe; `--factors file.csv` uses yours |
| C, value to your book | `book_correlation` (also in the book's worst bars), `marginal_sharpe` (the book's Sharpe gain, with a bootstrap interval), `residual_vs_book`, `drawdown_overlap`; `signal_orthogonality` (partial IC after the signals you already run) | `--book book.csv` (date + one column per strategy), `--existing-scores scores.csv`; skipped without them |
| F, all the attempts | `hlz_hurdle` (t ≥ 3), `min_backtest_length`, `drawdown_plausibility`, `haircut_sharpe` | `--n-trials` |
| I, risk | `neutrality`, `concentration`, `leverage_gross_net`, `historical_stress_replay` (named crises found in your dates), `tail_risk` | — |

| E, robustness | `universe_subsampling` (70 % subsets, top-5 share), `group_split` (`--groups`), `start_date_sensitivity`, `cpcv_paths`, `synthetic_market_null` (bootstrapped markets without the score's link), `noise_injection`, `data_source_replication` (API: a second price source), `bar_construction` | — |
| G, data and process | `universe_lookahead` (`--membership`; without it, a warning when the universe looks like today's members), `classification_lookahead`, `cross_market_close_alignment` (`--exchanges`), `post_discovery_decay` (`--discovery-date`), `research_hygiene` | optional files |

`--signal-only` runs families A and D only. Every report ends with an
[Alpha Readiness Level](dossier-readiness-monitor.md#alpha-readiness-level-arl-19), for example
`ARL 6/9 — blocked at 7: tradable and robust (rebalance_timing_luck)`.

## Reading the demo

The demo's real score has a rank IC of about 0.05 with t ≈ 9 and beats the placebos. It still gets `REJECT`
with `--aum 5e7`, because daily rebalancing of illiquid names at that size costs more than the edge. The noise score
fails the placebo test. That is the point of the command: **a significant IC is not yet a tradable alpha.**

## Honest scope

- Self-built factors are proxies: size is ranked by traded value, and there is no value factor without fundamentals.
  Pass `--factors` with academic or vendor factors for a stricter attribution.
- Impact uses the square-root model with a coefficient of 1: a model, not a measurement.
- The score is taken as given. To check the code that makes it for look-ahead, verify that code with `monte-neo verify`.

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not
predict future returns.
