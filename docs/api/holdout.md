# Holdout helper (train / holdout)

Practical anti-overfit around the research export lane — **no ML**.

## Idea

1. Split bars into contiguous **train** then **holdout**
2. Run `export_sma_sweep` on train
3. Re-score the train **top-K** `(fast, slow)` pairs on holdout only
4. Report `gap_best`, `mean_gap_top_k`, `overfit_risk`, `promote_ok`

Schema: `mn.holdout_report.v1`.

## API

```python
from monte_neo.backtest import ExecutionModel, holdout_sma_sweep, synthetic_ohlcv

ohlc = synthetic_ohlcv(50_000, seed=42)
model = ExecutionModel(commission_bps=5.0, slippage_bps=5.0, warmup_bars=50)
report = holdout_sma_sweep(
    ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"],
    combos=64, top_k=5, model=model, device="auto",
)
print(report["metrics"])
```

Enrich HeuristicPolicy:

```python
from monte_neo.policy import build_research_state, HeuristicPolicy

state = build_research_state(train_export_dict, holdout_report=report)
decision = HeuristicPolicy().decide(state)
# high holdout gap → promote blocked, lean run_mc / reject
```

## CLI

```bash
monte-neo --holdout-sma --holdout-bars 20000 --holdout-combos 32
```

Synthetic smoke only — for real bars call the Python API.

## Promote modes

| Mode | Promote when |
|------|----------------|
| `holdout_positive` (default) | `train_best > 0` and `holdout_at_best > 0` |
| `strict` | same, **and** `overfit_risk != "high"` |

Large gaps still set `overfit_risk` / `worth_mc_stress` but no longer block the default mode.

## Label log (for a future LocalScorer)

```bash
monte-neo --holdout-sma --holdout-log ~/mn_labels.jsonl --human-label accept
```

Or in Python:

```python
from monte_neo.policy import append_research_label
append_research_label("labels.jsonl", holdout_report=report, decision=decision, human_label="reject")
```
