# Performance

Honest first-party timing for the **research-bar** export path.
No peer comparisons. No stale “Nx faster” marketing numbers.

## What we measure

Wall time for `export_sma_sweep` on synthetic OHLC with
`device="auto"` vs `device="cpu_numba"` (and explicit `metal` when useful).

- Primary job: fee-aware next-bar grids on a local Mac
- As of **v0.17.5**, research `auto` prefers **`cpu_numba`** for wall clock on typical grids (sets `fallback_reason=auto_prefer_cpu_numba` when Metal would otherwise be eligible). Explicit `device="metal"` still uses the size-gated Metal path.
- Times below are **after a short Numba warmup** (first call pays JIT)

## Reproduce

```bash
# from a clone with editable / installed monte-neo
uv run python scripts/bench_research_bar.py --bars 100000 --combos 64
uv run python scripts/bench_research_bar.py --bars 100000 --combos 64 --run-1m
```

Script: [`scripts/bench_research_bar.py`](https://github.com/NeoZorK/Monte-Neo/blob/main/scripts/bench_research_bar.py).

## Measured numbers (2026-09-17) — MacBook Pro M1 Pro 16 GB

| Host | Notes |
|------|--------|
| **MacBook Pro M1 Pro 16 GB** (macOS arm64, Python 3.13.14, repo `.venv`) | Primary reference — Metal available |
| Linux executor (x86_64, ~16 GB class) | Cross-check only — Metal unavailable → `auto` ≡ `cpu_numba` |

Command:

```bash
.venv/bin/python scripts/bench_research_bar.py --bars 100000 --combos 64 --run-1m
```

### Primary table (M1 Pro 16 GB, post-warmup)

#### Before v0.17.5 (`auto` selected Metal when size-ok)

| Bars | Combos | `device` requested | Device used | `fallback_reason` | Wall (s) | Notes |
|------|--------|--------------------|-------------|-------------------|----------|--------|
| 100 000 | 64 | `auto` | `metal` | none | **0.4844** | `auto` selected Metal |
| 100 000 | 64 | `cpu_numba` | `cpu_numba` | none | **0.0074** | much faster wall clock on this grid |
| 1 000 000 | 32 | `auto` | `metal` | none | **3.3941** | `auto` selected Metal |
| 1 000 000 | 32 | `cpu_numba` | `cpu_numba` | none | **0.0597** | much faster wall clock on this grid |

#### After v0.17.5 (`auto` → `cpu_numba` for wall clock)

| Bars | Combos | `device` requested | Device used | `fallback_reason` | Wall (s) | Notes |
|------|--------|--------------------|-------------|-------------------|----------|--------|
| 100 000 | 64 | `auto` | `cpu_numba` | `auto_prefer_cpu_numba` | **~0.007** | matches Numba row |
| 100 000 | 64 | `cpu_numba` | `cpu_numba` | none | **~0.007** | unchanged |
| 100 000 | 64 | `metal` | `metal` | none | **~0.48** | explicit Metal still allowed (may be slow) |
| 1 000 000 | 32 | `auto` | `cpu_numba` | `auto_prefer_cpu_numba` | **~0.06** | matches Numba row |
| 1 000 000 | 32 | `metal` | `metal` | none | **~3.39** | explicit Metal still allowed |

**Reading:** On these grid sizes on M1 Pro, Numba wins wall clock. Research `auto` now picks the faster safe path. Use `device="metal"` only when you want the Metal economics path regardless of wall clock. Restore pre-0.17.5 prefer-Metal auto with `MONTE_NEO_RESEARCH_AUTO_PREFER_METAL=1`.

### Secondary note (Linux executor, no Metal)

Earlier same-day run on a Linux host without Metal (`auto` ≡ `cpu_numba`): ~**0.016–0.117 s** post-warmup for the same 100k/64 and 1M/32 shapes. Useful only as a portable Numba cross-check — not an Apple Silicon claim.

## How to read these numbers

- **Research bar only** — not an OMS event-loop claim, not live multi-venue throughput
- **Wall clock includes signal build** when `timing.includes_signal_build` is true (export schema)
- Cold start (first Numba compile) is **excluded** from the table; your first run will be slower
- Combos / bars change wall time roughly with work size — use the script, do not extrapolate marketing multipliers
- On oversized Metal jobs, expect fallback to `cpu_numba` with an explicit `fallback_reason` (see [FAQ](../guides/FAQ.md))
- Research auto speed decline uses `auto_prefer_cpu_numba` (distinct from size/budget gates)

## Acceleration notes (scope language)

1. **Numba** — default portable research-bar path; research `auto` (v0.17.5+) prefers it for wall clock on typical grids
2. **Metal economics** — Apple Silicon path when explicitly requested (`device="metal"`) or when auto is opted back into prefer-Metal via env; still gated for 16 GB-class hosts
3. **Memory planner** — `plan_research_bytes` soft budgets / tile hints
4. **No-hang gate** — oversized Metal jobs fall back instead of unbounded GPU wait
5. **Research auto wall-clock policy** — `decide_research_accelerator` may set `auto_prefer_cpu_numba` so batch/export inherit Numba without changing OMS `resolve_device`

Older docs that quoted “125x” / “300k ops/sec” / “v0.0.4 targeting” without a reproducible method are **retired**. Prefer this page + `scripts/bench_research_bar.py`.
