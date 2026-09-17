# FAQ


## When should I use Monte-Neo?

**Good fit when:**

- You want a **10²–10⁴** fee-aware next-bar grid on a Mac today (not one toy script)
- You need an **Apple Silicon** path without Docker/cloud (Metal/Numba, 16GB-safe, auto → `cpu_numba`)
- You care about **re-checkable** export + golden vectors
- You want **research → paper OMS** validation (research bar first)
- You want **MIT** software that runs **locally**

**Usually not a fit when:**

- You need a **full live multi-venue OMS**
- You need **bot ops** (Telegram, exchange live/dry-run, marketplaces)
- You need a **cloud institutional** multi-asset stack
- You only want a **~50-line teaching backtest**
- Your problem is a **portfolio weight allocator** or pipeline-bundle runner

Tone: research-bar speed on Apple Silicon — not “replace every production stack.”


## Does Monte-Neo hang on very large bars (e.g. 10M)?

No (as of **v0.14.1+**). `device="auto"` estimates Metal/MLX shared and host budgets before dispatch. If the job is too large for a safe Metal path on a 16GB-class Mac, it **falls back to `cpu_numba`** and sets `fallback_reason` (for example `metal_max_bars_exceeded`). You should never see an unbounded GPU wait.

As of **v0.17.5**, research `auto` also declines Metal when size-ok but Numba is the faster safe path (`fallback_reason=auto_prefer_cpu_numba`).

Override budgets / auto policy with:

- `MONTE_NEO_RESEARCH_BYTES_BUDGET`
- `MONTE_NEO_METAL_SHARED_BYTES_BUDGET`
- `MONTE_NEO_METAL_MAX_BARS`
- `MONTE_NEO_RESEARCH_AUTO_PREFER_METAL=1` — restore pre-0.17.5 prefer-Metal research auto
- `MONTE_NEO_RESEARCH_AUTO_METAL_MIN_COMBOS=N` — allow auto→Metal only when `n_combos >= N`

## Metal vs Numba — which should I use?

- **`auto` (default, v0.17.5+):** research path prefers **`cpu_numba`** for wall clock on typical grids; may set `fallback_reason=auto_prefer_cpu_numba`. See [Performance](../development/performance.md).
- **`metal`:** force Metal when eligible (size gate only; may be slow — your choice).
- **`cpu_numba`:** always Numba — best default for huge bars or CI without Metal.

Signal grids default to Numba for exact parity; MLX signal remains opt-in. OMS `resolve_device("auto")` is separate and still prefers Metal when available.

## Is this a live trading bot?

No. The primary job is **fast local research** on macOS (fee-aware next-bar economics). The paper OMS lane is for validation semantics, not a “replace my production stack” claim.

## How do I install?

```bash
pip install monte-neo
# Metal/MLX on Apple Silicon:
pip install "monte-neo[apple]"
# isolated CLI:
pipx install "monte-neo[apple]"
```

Docs: [Installation](../setup/installation.md) · site: https://neozork.github.io/Monte-Neo/

## pip install from TestPyPI pulls weird packages?

TestPyPI stubs can poison `--extra-index-url`. Use PyPI for daily installs. Maintainers: download with `--no-deps` from TestPyPI only (see Installation).

## ImportError for matplotlib / binance?

Those are **extras**, not default deps (since v0.16):

```bash
pip install "monte-neo[plot]"   # charts
pip install "monte-neo[data]"   # Binance client
```

## How do I triage a sweep / check holdout?

```bash
monte-neo --policy-triage path/to/export.json
monte-neo --holdout-sma --holdout-bars 20000 --holdout-combos 32
```

See [Policy](../api/policy.md) and [Holdout](../api/holdout.md).

## Python / hardware?

- Python **3.11+**
- Best path: **Apple Silicon** macOS (Metal / MLX). Numba works elsewhere for research-bar CPU paths.
