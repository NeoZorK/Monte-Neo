# Performance

Honest first-party timing for the **research-bar** export path.
No peer comparisons. No stale “Nx faster” marketing numbers.

## What we measure

Wall time for `export_sma_sweep` on synthetic OHLC with
`device="auto"` vs `device="cpu_numba"`.

- Primary job: fee-aware next-bar grids on a local Mac
- `auto` may select Metal economics on Apple Silicon when the no-hang gate says safe; otherwise `cpu_numba`
- Times below are **after a short Numba warmup** (first call pays JIT)

## Reproduce

```bash
# from a clone with editable / installed monte-neo
uv run python scripts/bench_research_bar.py --bars 100000 --combos 64
uv run python scripts/bench_research_bar.py --bars 100000 --combos 64 --run-1m
```

Script: [`scripts/bench_research_bar.py`](https://github.com/NeoZorK/Monte-Neo/blob/main/scripts/bench_research_bar.py).

## Measured numbers (2026-09-17)

| Host | Notes |
|------|--------|
| **Executor host** (Linux x86_64, ~16 GB class) | Metal unavailable → `auto` ≡ `cpu_numba` |
| **Intended Apple Silicon reference** | MacBook Pro **M1 Pro 16 GB** — re-run the script locally for Metal vs Numba |

Command used for the table:

```bash
python scripts/bench_research_bar.py --bars 100000 --combos 64 --run-1m
```

| Bars | Combos | `device` requested | Device used | `fallback_reason` | Wall (s) | Notes |
|------|--------|--------------------|-------------|-------------------|----------|--------|
| 100 000 | 64 | `auto` | `cpu_numba` | none | **0.016** | post-warmup |
| 100 000 | 64 | `cpu_numba` | `cpu_numba` | none | **0.017** | post-warmup |
| 1 000 000 | 32 | `auto` | `cpu_numba` | none | **0.117** | post-warmup |
| 1 000 000 | 32 | `cpu_numba` | `cpu_numba` | none | **0.090** | post-warmup |

On a MacBook Pro M1 Pro 16 GB with `monte-neo[apple]`, expect `auto` to prefer Metal when the job fits shared/host budgets; oversized jobs fall back to `cpu_numba` with an explicit `fallback_reason` (see [FAQ](../guides/FAQ.md)).

## How to read these numbers

- **Research bar only** — not an OMS event-loop claim, not live multi-venue throughput
- **Wall clock includes signal build** when `timing.includes_signal_build` is true (export schema)
- Cold start (first Numba compile) is **excluded** from the table; your first run will be slower
- Combos / bars change wall time roughly with work size — use the script, do not extrapolate marketing multipliers

## Acceleration notes (scope language)

1. **Numba** — default portable research-bar path (`cpu_numba`)
2. **Metal economics** — Apple Silicon path when eligible; gated for 16 GB-class hosts
3. **Memory planner** — `plan_research_bytes` soft budgets / tile hints
4. **No-hang gate** — oversized Metal jobs fall back instead of unbounded GPU wait

Older docs that quoted “125x” / “300k ops/sec” / “v0.0.4 targeting” without a reproducible method are **retired**. Prefer this page + `scripts/bench_research_bar.py`.
