# Strategy verifier (`monte_neo.verify`)

An independent, deterministic check that runs before anyone trusts a backtest.
It covers three things: look-ahead, trading costs and selection bias.
The result is a `strategy-verdict/1` certificate: a verdict, the checks behind it,
`next_actions` an agent can act on, and SHA-256 hashes that make the run reproducible.

> The verifier checks **methodology**, not future profit. Not investment advice.

## Quick start

```python
from monte_neo.verify import verify_strategy, model_from_costs

report = verify_strategy(
    "btc_1h.csv",                 # open, high, low, close[, timestamp]
    strategy="my_strategy.py",    # defines signal(df) -> positions (+1 / 0 / -1)
    n_trials=40,                  # how many variants you tried before picking this one
    model=model_from_costs(commission_bps=5, slippage_bps=5),
)
print(report["verdict"], report["certificate_id"])
for action in report["next_actions"]:
    print("-", action)
```

You can also pass `signals=` (an array or a `.npy`, `.csv` or `.parquet` file) instead of code.
Look-ahead probes need code (`strategy=` or `signal_fn=`). With signals alone, only the
statistical smell test runs.

## CLI

```bash
monte-neo verify --ohlcv btc_1h.csv --strategy my_strategy.py --n-trials 40
monte-neo verify --ohlcv btc_1h.csv --signals positions.npy --format json --out verdict.json
monte-neo verify --schema          # print the JSON schema
```

| Exit code | Meaning |
|-----------|---------|
| 0 | `PASS` or `PASS_WITH_WARNINGS` |
| 1 | `NEEDS_MORE_EVIDENCE` |
| 2 | `REJECT` |
| 3 | Usage or input error (not a verdict) |

## Verdicts

| Verdict | Rule |
|---------|------|
| `REJECT` | Any **integrity**, **lookahead** or **economics** check failed |
| `NEEDS_MORE_EVIDENCE` | Only **statistics** checks failed |
| `PASS_WITH_WARNINGS` | No failures, at least one warning |
| `PASS` | Everything passed |

## Checks

| id | category | fails / warns when |
|----|----------|--------------------|
| `data_integrity` | integrity | NaN, non-positive prices or `high < low` (fail, stops the run early) |
| `determinism` | integrity | two runs of `signal(df)` on the same data disagree |
| `lookahead_truncation` | lookahead | `signal(df[:t+1])[-1] != signal(df)[t]` at any checkpoint |
| `lookahead_perturbation` | lookahead | rewriting bars after `t` (future returns mirrored) changes signals up to `t` |
| `lookahead_static_lint` | lookahead | `shift(-k)`, `center=True`, `bfill` (fail); `fit` on the full series, `x[i + k]` (warn) |
| `implausible_accuracy` | lookahead | next-bar direction hit rate ≥ 0.60 over ≥ 100 active bars |
| `costs_modeled` | economics | zero commission and slippage (warn) |
| `net_profitability` | economics | total return ≤ 0 after costs |
| `cost_margin` | economics | break-even cost < 2× the modeled per-side cost (warn) |
| `delay_sensitivity` | economics | profitable, but loses money with one extra bar of execution delay (warn) |
| `sample_size` | statistics | fewer than `min_trades` (default 30) closed trades |
| `deflated_sharpe` | statistics | Deflated Sharpe < 0.5 (fail) or < 0.95 (warn) |
| `trials_disclosed` | statistics | `n_trials` not declared (info only) |
| `holdout_consistency` | statistics | Sharpe positive in the first 70% and ≤ 0 in the last 30% (warn) |

### Execution semantics

The verifier uses the same fee-aware research-bar engine as the rest of Monte-Neo:

- A signal on bar `t` fills at the open of bar `t + 1`.
- Commission and slippage are charged in bps per side on fill notional.
- Default costs: 5 + 5 bps per side.
- Default warm-up: `min(60, n_bars / 10)` bars.

Sharpe statistics use per-bar returns after warm-up.

- **PSR** (Probabilistic Sharpe Ratio) is the probability that the true Sharpe is above 0.
- **Deflated Sharpe** is the probability that the true Sharpe is above the expected
  maximum Sharpe of `n_trials` zero-skill strategies. It uses the Bailey & López de Prado
  formulas with skew and kurtosis adjustments.

### Why `n_trials` matters

When an agent tries 200 variants and reports the best one, the best Sharpe is
mostly luck. The verifier prices this in, but only if it knows the number of trials.
The trap suite (`tests/traps`) includes this case: the best of 200 random strategies
passes when `n_trials` is hidden and fails once `n_trials=200` is declared.

## Certificate (`strategy-verdict/1`)

```json
{
  "schema": "strategy-verdict/1",
  "verdict": "REJECT",
  "certificate_id": "17a9a29907e8d6ee",
  "reasons": ["lookahead_truncation: truncation probe: LEAK DETECTED"],
  "checks": [{"id": "...", "category": "...", "status": "fail", "summary": "...", "details": {}}],
  "metrics": {"total_return": -0.04, "deflated_sharpe": 0.11, "breakeven_cost_bps": 0.0},
  "next_actions": ["The signal at bar t changes when later bars are removed: ..."],
  "reproducibility": {"engine_version": "v0.18.0", "data_sha256": "...", "signals_sha256": "...",
                      "source_sha256": "...", "model": {}, "n_trials": 1},
  "generated_at": "2026-09-26T12:00:00+00:00",
  "disclaimer": "..."
}
```

`certificate_id` is derived from the reproducibility block and the verdict. The same
data, signals, code, model and `n_trials` always give the same id.

## Bring your own signals: `export_signals`

```python
from monte_neo.backtest import export_signals
out = export_signals(o, h, l, c, positions, model=model, include_equity=True)
out["signal"]  # sha256, exposure, position_changes, has_short
```

## Security note

`strategy=` imports and runs the Python file with your permissions, as if you had run
it yourself. Only verify code you would run yourself.
