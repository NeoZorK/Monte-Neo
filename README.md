# Monte-Neo

<p align="center">
  <img src="docs/assets/monteneo-logo.png" alt="Monte-Neo logo" width="220"/>
</p>

<p align="center">
  <strong>Monte Carlo indicator research</strong> and a fee-aware bar backtest engine<br/>
  MIT · Python 3.11+ · Apple Silicon (Metal / MLX) friendly
</p>

<p align="center">
  <a href="https://github.com/NeoZorK/Monte-Neo/actions/workflows/ci.yml"><img src="https://github.com/NeoZorK/Monte-Neo/actions/workflows/ci.yml/badge.svg" alt="CI"/></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT license"/></a>
  <a href="https://github.com/NeoZorK/Monte-Neo/releases/latest"><img src="https://img.shields.io/github/v/release/NeoZorK/Monte-Neo?label=release" alt="Latest release"/></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue.svg" alt="Python 3.11+"/>
</p>

> Current: **v0.2.0** · [Changelog](docs/project/CHANGELOG.md) · [Docs index](docs/INDEX.md)

## What it is

- **Monte Carlo research tooling** for trading indicators (noise, shuffle, sensitivity, walk-forward helpers).
- **Interactive CLI** for data download (Binance), generation workflows, and charts.
- **Fee-aware bar backtest engine** (`monte_neo.backtest`): next-bar fills, commission/slippage/impact (bps), cash/equity, SL/TP/trail, funding, leverage, session masks, batch sweeps, shared-cash portfolio, trade journal.
- Optional **Metal / MLX** acceleration paths on Apple Silicon where available.

## What it is not

- Not a full broker OMS / exchange simulator (no L2 matching engine, no live order gateway in this package line).
- Not a claim that every specialized throughput kernel equals the general bar engine — use `monte_neo.backtest` when you need matched execution semantics.

## Quick start

```bash
uv sync
uv run monte-neo
uv run pytest tests -n auto
```

### Bar backtest (minimal)

```python
from monte_neo.backtest import (
    ExecutionModel,
    frame_to_ohlc,
    run_bar_backtest,
    sma_signal,
    synthetic_ohlcv,
)

ohlc = frame_to_ohlc(synthetic_ohlcv(5_000, seed=42))
model = ExecutionModel(
    commission_bps=5.0,
    slippage_bps=5.0,
    size_fraction=0.25,
    sl_pct=1.0,
    tp_pct=2.0,
)
sig = sma_signal(ohlc["close"], fast=10, slow=40)
out = run_bar_backtest(
    ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], sig, model=model
)
print(out["total_return"], out["metrics"]["max_drawdown"], len(out["trades"]))
```

Details: [docs/project/backtest_engine.md](docs/project/backtest_engine.md).

## Features (honest)

| Area | Status |
|------|--------|
| MC indicator / robustness workflows | Available via CLI and library |
| Fee-aware next-bar bar engine | `monte_neo.backtest` (research-grade) |
| Strategy expressions / SMA helpers | Library API (expanding) |
| Metal / MLX paths | Best-effort on Apple Silicon; CPU fallbacks exist |
| Docker | Supported for headless/CI-style runs |

## Project structure

```
Monte-Neo/
├── src/monte_neo/
│   ├── backtest/      # Fee-aware bar engine
│   ├── core/          # Generator / portfolio helpers
│   ├── data/          # Market data downloaders
│   ├── monte_carlo/   # MC methods
│   ├── metrics/       # Trading metrics
│   ├── cli/           # Interactive CLI
│   └── visualization/
├── tests/
├── docs/
└── docker/
```

## Requirements

- Python **3.11+**
- Dependencies: see `pyproject.toml` (`uv sync`)

## License

MIT — see [LICENSE](LICENSE).

Public repository: https://github.com/NeoZorK/Monte-Neo
