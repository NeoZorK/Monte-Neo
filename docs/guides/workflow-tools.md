# Project tools around `verify`

Five commands that make the verifier part of the way a project works. They keep their state in `.monte-neo/`, in
hash-chained files: changing or removing an old line breaks every later hash, and the tools say so.

## `monte-neo history`: certificates over time

```bash
monte-neo history add verdict.json --label main --commit "$GITHUB_SHA"   # append to .monte-neo/history.jsonl
monte-neo history check verdict.json --label main --markdown              # compare with the latest entry; exit 2 on a regression
monte-neo history diff old.json new.json                                   # what changed: verdict, metrics, checks
monte-neo history show
```

A regression is a worse verdict (`PASS` < `PASS_WITH_WARNINGS` < `NEEDS_MORE_EVIDENCE` < `REJECT`) or a check that
newly fails. `--markdown` prints a table for a pull-request comment. MCP: `compare_certificates`.

## `monte-neo register`: write the hypothesis down first

```bash
monte-neo register --hypothesis "A 20-bar trend rule beats buy-and-hold on hourly BTC" --strategy s.py --n-trials 3
monte-neo verify --ohlcv btc.csv --strategy s.py --ledger --registration reg-1-1a2b3c4d
```

The certificate's `preregistration` row says whether the verified code is the registered one and, with `--ledger`,
whether the registration came before the first verification of that code. It is information: it never moves the verdict.
MCP: `register_hypothesis`.

## `monte-neo oracle`: a hold-out for adaptive search

```bash
monte-neo oracle init --ohlcv btc.csv --holdout 0.2 --budget 10
monte-neo oracle query --ohlcv btc.csv --strategy s.py
```

An agent that asks the test set "does this work?" two hundred times fits the test set. The oracle answers like
Thresholdout (Dwork et al., 2015): while the training and hold-out Sharpe agree within the tolerance it returns the
*training* number, which says nothing about the hold-out; when they disagree it returns a noisy hold-out number and
spends one unit of the budget. A variant that was asked before is answered from the log, free. When the budget is gone the
hold-out is used up: collect new data. It protects against over-fitting by many queries; it does not hide the file from a
process that can read the disk. MCP: `holdout_query`.

## `monte-neo portfolio`: many strategies at once

```bash
monte-neo portfolio --ohlcv btc.csv a.py b.py c.py
```

Reports the effective number of independent strategies (from the correlations of their returns), the clusters, White's
Reality Check and Hansen's SPA over the whole list, the best strategy deflated by the effective number of trials, and the
equal-weight ensemble. "Forty strategies in a quarter" give one that can shine by luck; this prices it in. MCP:
`verify_portfolio`.

## `monte-neo doctor`: known problems of a data export

```bash
monte-neo doctor export.csv            # the provider is guessed from the columns
monte-neo doctor export.csv --provider yahoo
```

Recognises Binance klines, Yahoo, Polygon, Databento, TradingView and MetaTrader 5 exports and names their traps: what
the time label means (bar start), the time zone, epoch units (seconds, ms, µs, ns), adjusted against unadjusted prices,
fixed-point prices, tick volume, indicator columns drawn on the chart, and generic problems (unsorted or repeated stamps,
gaps, zero volume). Exit code 2 when it finds an error. MCP: `diagnose_data`.
