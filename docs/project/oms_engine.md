# OMS engine (paper bar path)

Package: `monte_neo.oms` (introduced in **v0.3.0**).

## Purpose

Event-driven **paper OMS** lane: orders → matching → positions → blotter.
Separate from the research bar package `monte_neo.backtest`.

This is **not** a live exchange by itself. Paper path is first-class; live
adapters are versioned later and env-gated.

## Apple Silicon

Device select (`auto` / `cpu_numba` / `metal` / `mlx`) via `monte_neo.oms.accel`.
Bulk long/flat batch helper uses Numba on CPU; Metal shader scaffold lives at
`oms/accel/shaders/oms_bar_match.metal` for native wiring. Economics parity
between devices is mandatory.

Target host class for budgets: Apple Silicon laptop with 16GB unified memory.

## Quick start

```python
from monte_neo.oms import SignalStrategy, run_oms_bar_backtest
import numpy as np

signal = np.zeros(1_000, dtype=np.int64)
signal[100:800] = 1
out = run_oms_bar_backtest(
    open_, high, low, close,
    SignalStrategy(signal, size_fraction=0.25),
    commission_bps=5.0,
    slippage_bps=5.0,
    device="cpu_numba",
)
```

## Work checklist (paper)

- order lifecycle (market / limit / cancel)
- fees + slippage (bps)
- blotter + account equity
- next-bar open fill policy (default)

## Testing

```bash
uv run pytest tests -n auto
```

## Policy

Public documentation in this repository does not name external competing
products or individuals. Private comparison protocols and any Evidence
publication are gated by explicit maintainer permission after complete correct
runs.
