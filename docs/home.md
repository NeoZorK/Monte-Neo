# Monte-Neo

<p class="mn-hero-logo" markdown="1">
![Monte-Neo](assets/logo-header.png){ width="96" }
</p>

<p class="mn-tagline" markdown="1">
**Fast local research** for trading strategies on Apple Silicon  
Fee-aware next-bar economics · Monte Carlo · paper OMS
</p>

<p class="mn-badges" markdown="1">
[![PyPI](https://img.shields.io/pypi/v/monte-neo.svg)](https://pypi.org/project/monte-neo/)
[![CI](https://github.com/NeoZorK/Monte-Neo/actions/workflows/ci.yml/badge.svg)](https://github.com/NeoZorK/Monte-Neo/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/NeoZorK/Monte-Neo/blob/main/LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://pypi.org/project/monte-neo/)
[![Apple Silicon](https://img.shields.io/badge/macOS-Apple%20Silicon-black.svg)](https://neozork.github.io/Monte-Neo/)
</p>

!!! tip "Install"
    ```bash
    pip install monte-neo
    # Apple Silicon extras (MLX / Metal bindings):
    pip install "monte-neo[apple]"
    ```

    Or isolated CLI: `brew install pipx && pipx install "monte-neo[apple]"`

## What it is

| Lane | Role |
|------|------|
| **Research bar** | Primary speed path — fee-aware next-bar grids on Mac |
| **Monte Carlo** | Research helpers for robustness checks |
| **Paper OMS** | Validation semantics — not a live-bot claim |

**Job:** on an Apple Silicon Mac, iterate strategy hypotheses in minutes with economics you can re-check (export API + golden vectors).

**Not a goal:** replace full event-driven production or live multi-venue bot platforms.

## Why Monte-Neo

- **Local Apple Silicon speed** — Metal economics + Numba (MLX optional)
- **Fee-aware research bar** — next-bar fills, costs (bps), honest checklist
- **Export API** — `export_single` / `export_batch` / `export_sma_sweep` + golden vectors
- **16GB-safe** — memory planner + no-hang Metal gate → `cpu_numba` fallback
- **MIT** — use, fork, ship

## Quick example

```python
from monte_neo.backtest import export_sma_sweep
import numpy as np

n = 50_000
close = 100 + np.cumsum(np.random.randn(n) * 0.1)
open_ = close  # demo: flat OHLC
high = close + 0.2
low = close - 0.2

result = export_sma_sweep(
    open_=open_, high=high, low=low, close=close,
    fast=[5, 10, 20],
    slow=[50, 100],
    device="auto",  # Metal when safe, else cpu_numba
)
print(result["device"], result.get("ok"), len(result.get("rows", result)))
```

See also: [examples/export_sma_sweep_quickstart.py](https://github.com/NeoZorK/Monte-Neo/blob/main/examples/export_sma_sweep_quickstart.py)

## Demos

<div class="mn-gallery" markdown="1">

![SMA sweep demo](assets/demo_sma_sweep.png){ loading=lazy }

![Memory plan demo](assets/demo_memory_plan.png){ loading=lazy }

</div>

## Next steps

- [Install](setup/installation.md) · [Quick start](guides/quick-start.md) · [FAQ](guides/FAQ.md)
- [Changelog](project/CHANGELOG.md) · [Roadmap](project/ROADMAP.md) · [Commercial](en/COMMERCIAL.md)
- Source: [github.com/NeoZorK/Monte-Neo](https://github.com/NeoZorK/Monte-Neo)
