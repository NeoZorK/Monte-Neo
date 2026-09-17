# Research export API

Stable research-bar export surface for fee-aware sweeps you can re-check locally.

## Entry points

```python
from monte_neo.backtest.export import (
    export_single,
    export_batch,
    export_sma_sweep,
    plan_research_bytes,
)
```

| Function | Role |
|----------|------|
| `export_single` | One signal / model → economics + checklist |
| `export_batch` | Many parameter rows on shared bars |
| `export_sma_sweep` | SMA cross grid helper + export |
| `plan_research_bytes` | Soft budget / tile hints (16GB-class hosts) |

## Schema notes

- `export_api_version` — bump only on breaking field changes
- `work_checklist` — `next_bar_fill`, `fees`, `no_lookahead`, `cash_position_equity`
- `metrics.rows` — per-combo returns (and params); golden vectors pin Numba exactness
- Optional: `memory`, `timing`, `device` / `fallback_reason` (no-hang Metal gate)

Raw OHLCV is **not** required for downstream triage — see [Policy](policy.md).

## Golden verify

```bash
uv run python -c "from monte_neo.backtest.export import verify_export_golden; verify_export_golden()"
```

(Exact helper names follow the installed package; see unit tests under `tests/`.)

## Quickstart example

See `examples/export_sma_sweep_quickstart.py` and the demo chart in `docs/assets/demo_sma_sweep.png`.
