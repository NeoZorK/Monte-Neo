# Independent verification of backtests: probes, priced selection and reproducible certificates

*Technical note, Monte-Neo v0.41. A preprint-style description of the method. Every number is reproducible
with the published code; the code, the traps and the tests are in the
[repository](https://github.com/NeoZorK/Monte-Neo).*

## Abstract

A backtest is a program that runs on data it can read in full. Code written by people or by coding agents
can therefore report profit that comes from information not available at decision time, from costs that were
not charged, or from choosing the best of many variants. We describe a verifier that treats the strategy as an
untrusted program. It (1) tests causality directly by running the program on truncated and rewritten data,
(2) charges costs and execution delay with its own engine, (3) prices selection with the Deflated Sharpe ratio,
and (4) issues a reproducible, optionally signed certificate. A public suite of 80 strategies that are known to lie
and 35 honest controls is run on every build, so the method's false negatives and false positives are tracked in
the open.

## 1. Problem

Three failure modes account for most wrong backtests:

1. **Look-ahead.** The signal at bar *t* depends on bars after *t*: `shift(-1)`, centred windows, backward fills,
   statistics, scalers or model fits over the whole sample, random splits of a time series, calendar joins that
   attach a period's final value to its first bar.
2. **Missing costs.** The edge is smaller than commission and slippage, or vanishes when the fill is one bar
   later.
3. **Selection.** Many variants were tried and the best is reported as if it were the only one.

Static analysis alone cannot find the first: a leak can be written in ways no rule anticipates. The method
therefore tests the *behaviour* of the program and uses static rules only as an additional, explanatory signal.

## 2. Causality probes

A signal function `f` maps a price table of *n* bars to *n* positions. If `f` is causal, the position at bar *t*
depends only on bars up to *t*.

**Truncation probe.** For a set of checkpoints *t*, compare `f(df[:t+1])` with `f(df)[:t+1]`. Any difference in
the prefix means the full-sample run used bars after *t*. Checkpoints are spread evenly over the sample and
also placed on bars where the position changes, so sparse strategies are tested where they act. The probe is
independent of how the leak is written.

**Perturbation probe.** Rewrite the bars after *t* so that their log returns are mirrored, and compare the
positions up to *t*. It is a second, independent view of the same property: values of later bars must not move earlier
positions, whatever the code does with them.

**Outside data.** A strategy that ignores its input and loads the dataset itself sees the untouched future, so
both probes pass. An outside-data watch records data files read and network connections opened while strategy
code runs, and the check fails on either.

**Static lint.** An AST pass (23 rules) names the line: negative shifts, centred windows, backward fills, reversed
windows, whole-sample fits and statistics, group aggregates broadcast back to rows, shuffled splits. Rules that
cannot separate honest from leaking uses (a whole-sample mean may be a legitimate statistic elsewhere) only warn;
the probes decide.

**Implausible accuracy.** A next-bar direction hit rate of at least 0.70 over at least 100 active bars with a
binomial z of at least 3.5 is treated as a leak: it is far above what liquid markets normally offer, and a high rate that
is not significant is only a warning.

## 3. Costs, delay and data quality

Positions are re-simulated by the verifier's own engine: a signal at bar *t* is filled at the open of bar *t* + 1,
with commission and slippage in basis points per side. The verifier reports the break-even cost, the result with
one and two bars of extra delay, a rough spread estimate from high and low next to the modeled cost
(Corwin and Schultz, 2012) and the capital at which fills stay within a share of bar volume. Data-quality checks
find prices that create fake profit: one-bar spikes that the next bar undoes, frozen prices, unadjusted splits and
gaps in time.

## 4. Selection and statistical evidence

- **Deflated Sharpe ratio** (Bailey and Lopez de Prado, 2014): the probability that the Sharpe ratio exceeds what
  the best of *N* trials would show by chance. *N* is declared (`n_trials`), or counted by the verifier when it
  runs the parameter search itself (`verify_grid`).
- **Probability of backtest overfitting** (Bailey, Borwein, Lopez de Prado and Zhu, 2015) by combinatorially
  symmetric cross-validation: 16 slices, 12,870 train/test splits, the share of splits in which the training winner
  ranks below the median of the test set. A directly observable quantity with real sampling noise: about 0.4 on
  average for pure noise.
- **Timing significance.** The net return of the positions is compared with 200 circular shifts of the same
  positions, separating skill at timing from market exposure.
- **Confidence.** A circular block bootstrap (blocks of about the cube root of the sample, fixed seed) gives 95%
  intervals of the Sharpe ratio and the total return; the minimum track record length says how many bars the
  observed Sharpe needs to be positive at 95%.
- **Claims.** A reported Sharpe, return, drawdown or trade count is compared with the verified one; a number
  better than the verified one by more than a stated tolerance fails.

## 5. Verdicts and certificates

Checks fall in five categories. A failure in integrity, look-ahead or economics gives `REJECT`; a failure in
statistics or claims gives `NEEDS_MORE_EVIDENCE`; warnings give `PASS_WITH_WARNINGS`. The certificate
(`strategy-verdict/1`) records the hashes of the data, positions and source, the cost model, the settings and the
verdict. Its identifier is a hash of exactly these inputs and the verdict, so the same inputs always give the same
identifier and anyone can reproduce it (`--recheck`). Derived sections (charts, breakdowns) do not enter the
identifier. Certificates can be signed with Ed25519.

## 6. Evaluation: the Trap Suite

The suite is a set of strategy files, each with the verdict and check statuses the verifier must return on a
random walk (where no strategy has an edge, so any profit is an artefact) or on data with a planted edge:

- 80 strategies that lie, in families: shifted or reversed time, centred filters, gap filling, whole-sample
  statistics, machine-learning pipelines, calendar joins and resampling, universes with several symbols, bad data.
- 35 honest controls: the same techniques written correctly (expanding windows, shifted joins, fits with a gap,
  point-in-time membership), plus a strategy with a real edge and a high hit rate. None may fail a look-ahead
  check.

The suite runs on every build. If a change stops catching a trap or starts accusing an honest control, the
build fails. Known limits are listed in the suite's documentation: a symbol delisted at a zero return looks like a
normal end of history, and a global clustering fitted on the whole sample is seen by the lint but not by the probes.

## 7. Limitations

- The verifier checks the method of a backtest, not the future profit of a strategy. It is not investment advice.
- Probes give evidence of a leak, not a proof of its absence: a strategy can be causal on the tested checkpoints and
  leak elsewhere. More checkpoints reduce that risk at a cost in time.
- The execution model is a bar-level model with proportional costs. It has no market impact and no order book.
- The Python audit hooks used to isolate untrusted code are not a security boundary; run untrusted code in
  the container image.

## References

- Bailey, D. H., and Lopez de Prado, M. (2014). The Deflated Sharpe Ratio: Correcting for Selection Bias,
  Backtest Overfitting and Non-Normality. *Journal of Portfolio Management*, 40(5).
- Bailey, D. H., Borwein, J., Lopez de Prado, M., and Zhu, Q. J. (2015). The Probability of Backtest Overfitting.
  *Journal of Computational Finance*, 20(4).
- Corwin, S. A., and Schultz, P. (2012). A Simple Way to Estimate Bid-Ask Spreads from Daily High and Low Prices.
  *Journal of Finance*, 67(2).
- Politis, D. N., and Romano, J. P. (1992). A Circular Block-Resampling Procedure for Stationary Data.
- Bailey, D. H., and Lopez de Prado, M. (2012). The Sharpe Ratio Efficient Frontier (minimum track record length).

## Cite

See [`CITATION.cff`](https://github.com/NeoZorK/Monte-Neo/blob/main/CITATION.cff).
