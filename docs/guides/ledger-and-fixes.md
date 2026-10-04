# Trial ledger and suggested fixes

## Trial ledger: `--ledger`

```bash
monte-neo verify --ohlcv data.csv --strategy s.py --ledger
```

Each verification appends a row to `.monte-neo/ledger.jsonl` (an append-only file, every row hashes the previous one).
A variant is identified by its normalised source (docstrings stripped) or by the hash of its positions, scoped by the
hash of the data. The number of distinct variants tried on this data replaces what you declare when it is larger:
`n_trials = max(declared, counted)`. Changing a parameter until the result looks good therefore raises the Deflated
Sharpe bar by itself. Pass a path to keep the ledger elsewhere. MCP: `verify_strategy(ledger=true)`.

## Suggested fixes: `--suggest-fix`

```bash
monte-neo verify --suggest-fix strategy.py
```

Rewrites the patterns that read the future into causal ones and prints a diff; nothing is written. Handled: negative
`shift`, `center=True`, `bfill`, `interpolate`, whole-sample statistics (to `expanding`), whole-sample rank, group
`transform('max'/'min'/'sum'/'prod')`. Chains that use `tail`, `head`, `iloc`, `values` and similar are left alone.
The patch keeps the shape of the strategy, not its meaning, and comments are lost: run `verify` on the result.
MCP tool: `suggest_fix`.
