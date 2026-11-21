# Faster honest evidence: replication, walk-forward and a sequential forward test

A forward record is the only data no backtest could fit, but it is slow: a few months of daily returns say very little
about an edge of ordinary size. **Showing that an annual Sharpe ratio of 1 is above zero takes about 6 years of daily
data; a Sharpe ratio of 3, about 9 months.** So the fastest honest path is to find new, unseen evidence *now* and to use
the forward period for what it does well: catching broken code, broken execution and a record that contradicts the
backtest.

```text
search (discovery) -> validation gate -> walk-forward of the parameter family -> sealed holdout (once)
       -> replication on markets outside the search -> paper forward, many candidates at once, sequential test
       -> demo testnet for the finalists only
```

## 1. Walk-forward of the parameter family (automatic in `research freeze`)

When a validated candidate is frozen for the holdout, Monte-Neo takes every screened variant of the same code (its
parameter grid), re-chooses the best parameters on each past window and judges that choice on the next window
(anchored walk-forward, 4 folds, discovery period). If re-choosing on the past does not work on the next period, the
holdout stays closed (an `--override` is possible and written down). The result is stored in the freeze record.

## 2. Replication on markets outside the search

```bash
monte-neo research transfer --strategy my_rule.py --markets data/other_coins/ --discovery BTCUSDT,ETHUSDT --n-trials 134
```

The frozen rule runs unchanged on every market in the folder (one OHLCV file per market). Markets used in the search are
refused. Each market gets a full Monte-Neo verdict; the equal-weight portfolio "this rule on every market" gets a
t-statistic with the **effective** number of markets (twenty coins that move together are not twenty tests). Check row
`cross_market_replication`: pass at a pooled t of at least 2 with at least 60 % of markets net positive. Write the list of
replication markets down before the run.

## 3. A sequential forward test (in `monte-neo deploy`)

The dashboard of every deployed strategy shows two e-processes on the daily net returns at doubled costs:
evidence of an edge (mean above zero) and evidence of a shortfall (Sharpe below the target). They are valid however often
you look. Decisions: `PASS` (after at least 8 weeks), `FAIL_EARLY` (after at least 3 weeks), `INCONCLUSIVE` (26 weeks
without a decision) or `CONTINUE`. The threshold is `candidates under test / alpha`, so running fifty candidates in
parallel does not create false passes. Expect `CONTINUE` for most of an ordinary strategy's record: that is the honest
answer, and the reason the evidence of an edge has to come from steps 1 and 2.

## 4. Demo testnet for finalists

Paper forward costs nothing and runs any number of candidates (`monte-neo deploy init --mode dry`). Use the demo testnet
for the finalists, to prove that orders, fills and reconciliation work.

Not investment advice: these steps measure evidence, not future returns.
