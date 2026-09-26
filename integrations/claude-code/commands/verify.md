---
description: Verify a trading strategy backtest with Monte-Neo (look-ahead, costs, selection bias)
argument-hint: "<ohlcv.csv> <strategy.py|signals.npy> [n_trials]"
---

Verify the trading strategy described by: $ARGUMENTS

Follow the `verify-strategy` skill: make sure the OHLCV file and the strategy file
(`signal(df)`) or positions file exist, determine `n_trials` honestly, call the
`verify_strategy` tool of the `monte-neo` MCP server, then report the verdict,
certificate_id, key metrics and `next_actions`. If the verdict is `REJECT`, propose
the concrete code fixes.
