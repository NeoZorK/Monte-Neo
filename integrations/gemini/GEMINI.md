## Trading strategy verification (Monte-Neo)

Before reporting any trading strategy, signal or backtest result (returns, Sharpe, win rate):

1. Save the OHLCV data as CSV/Parquet (`open, high, low, close[, timestamp]`).
2. Put the strategy in a Python file with `signal(df) -> positions` (+1 long, 0 flat, -1 short).
3. Call the `verify_strategy` tool of the `monte-neo` MCP server (or run
   `monte-neo verify --ohlcv data.csv --strategy strategy.py --n-trials N --format json`)
   with `n_trials` = number of variants you tried and realistic costs.
4. `REJECT` means the backtest is wrong: apply `next_actions` and verify again.
   `NEEDS_MORE_EVIDENCE` means the result is not statistically established.
5. Report the verifier verdict, `certificate_id` and metrics, not your own backtest numbers.
   Never reduce `n_trials` or costs to obtain a better verdict.
