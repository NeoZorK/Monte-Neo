# Verified indicator search: `monte-neo discover`

`discover` looks for a trading rule in a space of causal formulas and then asks the verifier whether the winner is real.
Searching many formulas always finds something that looks good on past data; the point of this command is that the
search is counted and tested, not just run.

```bash
monte-neo discover --ohlcv data.csv --out found/ --budget 2000 --seed 1
```

Options: `--budget` (candidates), `--seed`, `--null-runs` (shuffled markets, default 39), `--lockbox` (share of the last
bars kept for one final look, default 0.2), `--cost-bps` (round trip, default 5), `--side long_short|long_flat`.
Exit code 0 means found, 1 nothing found, 3 bad input. The MCP tool is `discover_indicator`.

## What it does

1. **Causal formulas only.** Candidates are trees of columns (open, high, low, close, volume), trailing windows and
   arithmetic. They are never built from text with `eval`; the source of the winner is generated from the tree.
2. **A gate before the search.** Every generated source passes the same truncation test the verifier uses. Nine known
   leaking formulas (canaries) are run through the gate first; if one passes, the run stops.
3. **Effective trials.** Candidates whose returns correlate above 0.8 are one idea. The number of clusters is the
   `n_trials` used for the Deflated Sharpe.
4. **Search null.** The whole search is repeated on shuffled copies of the market. The best Sharpe on the real data must
   beat the best Sharpe on those copies (p ≤ 0.05).
5. **Reality Check and SPA** on the cluster representatives.
6. **Lockbox.** The last part of the data is touched once, for the winner only.
7. **Certificate.** The winner is verified like any strategy, with the effective trials counted.

`found` is true only when every step agrees.

## Output files

`strategy.py` (the winner), `result.json` (statistics, reasons, certificate, config), `search.jsonl` (every candidate
with its Sharpe, hashed in `journal_sha256`), `certificate.json`, `report.html`.

## What to expect

On noise the search finds nothing in about 11 of 12 runs, although the best naive Sharpe on noise is above 1.5.
An edge planted in the data is found at costs up to about 1 bp and not found at 5 bp: the honest answer when costs eat
the edge. The search finds structure that exists in the data you give it; it does not promise profit out of sample.
