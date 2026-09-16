# FAQ

## Does Monte-Neo hang on very large bars (e.g. 10M)?

No (as of **v0.14.1+**). `device="auto"` estimates Metal/MLX shared and host budgets before dispatch. If the job is too large for a safe Metal path on a 16GB-class Mac, it **falls back to `cpu_numba`** and sets `fallback_reason` (for example `metal_max_bars_exceeded`). You should never see an unbounded GPU wait.

Override budgets with:

- `MONTE_NEO_RESEARCH_BYTES_BUDGET`
- `MONTE_NEO_METAL_SHARED_BYTES_BUDGET`
- `MONTE_NEO_METAL_MAX_BARS`

## Metal vs Numba — which should I use?

- **`auto` (default):** try Metal economics when eligible; otherwise Numba.
- **`metal`:** force Metal when eligible (still gated; may fall back).
- **`cpu_numba`:** always Numba (best for huge bars or CI without Metal).

Signal grids default to Numba for exact parity; MLX signal remains opt-in.

## Is this a live trading bot?

No. The primary job is **fast local research** on macOS (fee-aware next-bar economics). The paper OMS lane is for validation semantics, not a “replace my production stack” claim.

## How do I install?

```bash
pip install monte-neo
# Metal/MLX on Apple Silicon:
pip install "monte-neo[apple]"
```

Or from git / clone + `uv sync --extra apple`. See `docs/project/PACKAGING.md`.

## Python / hardware?

- Python **3.11+**
- Best path: **Apple Silicon** macOS (Metal / MLX). Numba works elsewhere for research-bar CPU paths.
