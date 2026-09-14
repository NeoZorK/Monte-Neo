# OMS engine

Package: `monte_neo.oms` (current line **v0.4.0**).

## Purpose

Event-driven **paper OMS** lane: orders → matching → positions → blotter.
Separate from the research bar package `monte_neo.backtest`.

Lanes:

1. **Bar paper OMS** — next-bar fills, market/limit/cancel
2. **Tick / L2 paper OMS** — synthetic ticks, book walk, Numba parity

Live exchange adapters are versioned later and env-gated.

## Apple Silicon

Device select (`auto` / `cpu_numba` / `metal` / `mlx`) via `monte_neo.oms.accel`.
Numba walks books and batch paths on CPU; Metal shader scaffolds:

- `oms/accel/shaders/oms_bar_match.metal`
- `oms/accel/shaders/oms_l2_walk.metal`

Economics parity between Python and Numba is tested. Target host: 16GB Apple Silicon.

## Quick start (bar)

```python
from monte_neo.oms import SignalStrategy, run_oms_bar_backtest

out = run_oms_bar_backtest(
    open_, high, low, close,
    SignalStrategy(signal, size_fraction=0.25),
    device="cpu_numba",
)
```

## Quick start (tick / L2)

```python
from monte_neo.oms import run_tick_l2_market_buy, synthetic_ticks

ticks = synthetic_ticks(10_000, seed=1)
out = run_tick_l2_market_buy(ticks, qty=1.0, device="cpu_numba")
```

## Testing

```bash
uv run pytest tests -n auto
```

## Policy

This repository does not name external competing products or individuals.
Evidence publication is gated by explicit maintainer permission after complete
correct private runs.
