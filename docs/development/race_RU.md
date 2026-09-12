# Race-хелперы (Phase-2)

Ускоренные пути для fair-race на Apple Silicon:

- `fused_sma_sweep` — Numba parallel, float64
- `metal_scenario_batch` — MLX/Metal batch + prefetch

Используется локальным harness `manifold_bt_comparison`. Не публичный API.
