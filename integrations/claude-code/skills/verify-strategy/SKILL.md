---
name: verify-strategy
description: Verify a trading-strategy backtest before reporting results. Use whenever you build, tune or report a trading strategy, signal, indicator or backtest (Sharpe, returns, win rate) — it detects look-ahead bias, unpaid trading costs and selection bias with the Monte-Neo verifier.
---

# Verify a trading strategy before you trust it

Backtests written quickly are usually wrong in the same ways: they read future bars,
ignore fees and slippage, or report the best of many tried variants. Do not report
strategy performance to the user until Monte-Neo has verified it.

## Steps

1. Save the price data you backtested on as CSV or Parquet with columns
   `open, high, low, close` (and `timestamp` if available).
2. Put the strategy in a Python file with a function `signal(df) -> positions`
   (`+1` long, `0` flat, `-1` short, one value per row of `df`). Only use pandas / numpy
   inside it. If the strategy cannot be expressed that way, save the positions to a
   `.npy` / `.csv` file instead (look-ahead probes then cannot run).
3. Count how many variants you tried (parameter sets, rules, assets). That is `n_trials`.
   If you tuned parameters, expose them as keyword arguments (`signal(df, fast=20, slow=80)`)
   and call the `verify_grid` tool with the grid (`{"fast": [10, 20], "slow": [50, 100]}`):
   the verifier runs the search itself, counts the trials and adds a walk-forward check.
4. Call the `verify_strategy` MCP tool (server `monte-neo`) with `ohlcv_path`,
   `strategy_path` (or `signals_path`), `n_trials`, and realistic
   `commission_bps` / `slippage_bps`.
   Without the MCP server, run:
   `monte-neo verify --ohlcv data.csv --strategy strategy.py --n-trials N --format json`.

## Acting on the verdict

| Verdict | What to do |
|---------|------------|
| `REJECT` | The backtest is broken or loses money after costs. Fix what `next_actions` lists, then verify again. Never report the original numbers as real. |
| `NEEDS_MORE_EVIDENCE` | Too few trades or Sharpe does not survive `n_trials`. Say so; test on more data. |
| `PASS_WITH_WARNINGS` | Report results together with every warning. |
| `PASS` | Report results with the `certificate_id`. |

Always tell the user the verdict, the `certificate_id` and the verifier metrics
(net return after costs, Deflated Sharpe, break-even cost) instead of the numbers from your
own backtest code. Never lower `n_trials` or costs to get a better verdict.
