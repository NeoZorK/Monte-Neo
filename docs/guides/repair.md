# `monte-neo repair`: repair defects without overfitting

Every other command says what is wrong. `repair` fixes it, and shows that the fix is not a new curve fit. It also says so
when there is nothing left to fix.

```bash
monte-neo repair --demo                                    # three strategies, three honest outcomes
monte-neo repair --ohlcv data.csv --strategy s.py --out repair/ [--commission-bps 10] [--rebalance-every 21]
```

Optimisers maximise the return, so they overfit. `repair` minimises **defects**, from a short list of declared repairs,
and lets a part of the history it has never seen decide.

## The protocol

1. **Diagnose** the original on all the data, as `verify` does.
2. **Stop** on defects no transform can honestly repair: broken data, survivorship, files or network read by the
   strategy, a non-deterministic signal, a model whose profit lives in fitting on the whole file, an edge that exists
   only before a language model's training cutoff. The outcome is `NOT_REPAIRABLE`, with what you need to do.
3. **Correct look-ahead and repainting first.** Look-ahead gets causal rewrites of the source (the same rules as
   `--suggest-fix`); repainting gets a one-bar delay. These have no parameters, so there is nothing to choose. If the
   leak is still there afterwards, the outcome is `NOT_REPAIRABLE`.
4. **Choose on the first 70 % of the history only**, among a few declared repairs, by the number of defects left
   (a fail counts 3, a warning 1), **never by return**. Every candidate is added to the number of trials, so the
   Deflated Sharpe gets stricter with each one.
5. **Open the lockbox once**: the chosen version on the last 30 %. The outcome is `REPAIRED` only when the
   whole-history certificate passes and the lockbox still earns after costs.

| Outcome | Exit code | Meaning |
|---------|-----------|---------|
| `REPAIRED` | 0 | Defects removed; the edge is confirmed once on data the choice never saw |
| `REPAIRED_NO_EDGE` | 1 | Defects removed, and no edge is left: **the profit was in the defect** |
| `NOT_REPAIRABLE` | 2 | What blocks it and what you need to do |
| `NOTHING_TO_REPAIR` | 4 | No defect the catalogue addresses; the strategy is not touched |

## The catalogue

| Id | Defect | Repair (fixed values) |
|----|--------|------------------------|
| R1 | Look-ahead (`shift(-1)`, centred windows, `bfill`, whole-series statistics) | Causal rewrite of the source |
| R2 | Repainting | Act one bar later |
| R5 | Costs and turnover eat the profit; the edge lives in the next fill | Smoothing (span 5, 10, 20), a minimum holding period (5, 10, 20 bars), a no-trade band (0.25) |
| R7 | The result depends on the rebalance day (`--rebalance-every`) | Four staggered tranches |
| R8 | The profit is market exposure | Cross-sectional neutralisation (universes) |
| R9 | Trades are large against the volume | Weight cap 0.1, no positions in the least liquid 20 % |
| R11 | Unstable risk, one period makes the profit, a policy breach | Volatility target 10 % a year, cap 0.5 |

Pairs of repairs from different families are tried too, up to `--budget` (24 by default).

## What you get

`--out` holds:

- `strategy.repaired.py`: the corrected original, renamed, the repair functions it uses, and a new `signal(df)`. It is
  self-contained and runs without Monte-Neo.
- `repair.diff`, `certificate.json` (the repaired strategy on all the data, with the trials counted).
- `repair-report.json` and `repair-report.html`: before and after, the lockbox, every candidate and its defect count.

The original file is never changed. Recheck the certificate with
`monte-neo verify --recheck repair/certificate.json --ohlcv data.csv --strategy repair/strategy.repaired.py`.

## What the demo shows

- **leak**: reads tomorrow's close. R1 rewrites it and R2 delays it. `REPAIRED_NO_EDGE`: on a random walk, the profit
  was the leak.
- **flicker**: a real 40-day trend signal that flips almost daily, with 10 bps costs. It loses 85 % before the repair.
  Smoothing (span 20) is chosen on the first 70 %, and the lockbox earns after costs: `REPAIRED`.
- **unseeded**: random positions without a seed. `NOT_REPAIRABLE`: seed every random generator.

## How it is tested

Zoo A16 runs `repair` on every leaking strategy of the Trap Suite on a random walk. A `REPAIRED` there would mean the
repair invented an edge. In the full run, 68 leaking strategies were repaired with no `REPAIRED` outcome, and 9 were
skipped because they need other data columns. The original files are checked to be unchanged.

Do not run `repair` again and again on the same data to look for a better outcome. That is the search the protocol
exists to prevent.

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not
predict future returns.
