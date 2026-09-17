# Local research policy (HeuristicPolicy A)

Offline, deterministic triage **after** a research export. Not a cloud model.

## Why

After `export_sma_sweep` / `export_batch` you want a clear **next action**:
reject, stop, refine grid, run MC stress, or promote to paper OMS — without shipping
raw bars or calling a hosted policy service.

## API

```python
from monte_neo.policy import triage_export, HeuristicPolicy, PolicyConfig, build_research_state

out = triage_export(export_dict)   # {"state": ..., "decision": ...}
decision = out["decision"]
# next_action, promote_to_paper_oms, worth_mc_stress, overfit_risk, reasons, confidence
```

`build_research_state` compresses an export into schema `mn.research_state.v1`
(metrics summary + top rows + checklist — **no OHLCV**).

## CLI

```bash
monte-neo --policy-triage path/to/export.json
```

Prints the decision JSON and reason lines.

## Thresholds

Tunable via `PolicyConfig` (`t_min_return`, `t_promote_return`, `p_min_frac_positive`,
`e_hi_edge`, cluster tolerances). Defaults are conservative research heuristics.

## Roadmap

- Holdout helper and LocalScorer B are **deferred** until A proves useful in real sweeps.

## Holdout enrichment

Pass a `holdout_sma_sweep` report into `build_research_state(..., holdout_report=...)`.
High holdout gap blocks promote (see [Holdout](holdout.md)).
