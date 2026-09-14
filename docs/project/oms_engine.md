# OMS engine

Package: `monte_neo.oms` (current line **v0.9.0**).

## Purpose

Event-driven **paper OMS** + venue adapters:

1. Bar paper OMS
2. Tick / L2 paper OMS
3. Venue adapters (`paper` / `binance` / `bybit`) — **paper by default**

## Venue adapters

```python
from monte_neo.oms import OrderIntent, OrderSide, OrderType, make_adapter

ad = make_adapter("binance", mode="paper", mid=100.0)
rep = ad.submit(OrderIntent(
    symbol="BTCUSDT",
    side=OrderSide.BUY,
    order_type=OrderType.MARKET,
    qty=0.01,
))
fills = ad.poll_fills()
```

### Live safety

- Live mode requires `MONTE_NEO_LIVE_TRADING=1` and venue API keys in env.
- Default dry-run: `MONTE_NEO_LIVE_DRY_RUN=1` (no real orders).
- Turning dry-run off is blocked for real sends in this build.

Never commit secrets.

## Apple Silicon

Device select for matching helpers: `cpu_numba` / `metal` / `mlx` / `auto`.

Bulk path:

```python
from monte_neo.oms import run_batch_terminal

out = run_batch_terminal(open_, close, signals, device="auto")
# out["device_used"] is "metal" or "cpu_numba"
```

Metal float32 vs Numba float64 parity is tested with documented tolerances.
Shader scaffolds also live under `oms/accel/shaders/`.

L2 book-walk batch:

```python
from monte_neo.oms import run_l2_walk_batch

out = run_l2_walk_batch(
    sides, qtys, bid_px, bid_sz, ask_px, ask_sz, device="auto"
)
# out["device_used"] is "metal" or "cpu_numba"
```

## Testing

```bash
uv run pytest tests -n auto
```

## Policy

This repository does not name external competing products or individuals.
Evidence publication is gated by explicit maintainer permission after complete
correct private runs.
