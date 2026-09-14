# OMS / MC acceleration notes (public docs in English).

Package line: see `src/monte_neo/_version.py`.

## Monte Carlo Metal/MLX unify

`monte_neo.monte_carlo.plan_mc_run` picks an honest backend:

- **metal** when `compute_device` resolves to Metal and the indicator exposes `get_metal_params`
- **mlx** when MLX representation is available (or Metal resolved without native params)
- **cpu_numba** when GPU is disabled, CPU is requested, or the indicator cannot run on GPU

`MCResult` reports `device_used`, `bytes_peak_est`, and `accel_plan`.

## 16GB memory budgets

On M1 Pro 16GB-class hosts, scenario residency is tiled against a ~10GiB usable
budget (`MCConfig.memory_budget_bytes` overrides). Use:

```python
from monte_neo.monte_carlo import plan_scenario_budget, iter_scenario_tiles

bud = plan_scenario_budget(n_bars=50_000, n_scenarios=20_000)
for start, end in iter_scenario_tiles(20_000, bud.tile_scenarios):
    ...
```

Peak estimate stays ≤ usable budget by construction.
