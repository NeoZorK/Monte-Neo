# Race helpers (public for ClaimBound)

Public fair-race entrypoints for independent reproduce:

- `monte_neo.fair_race.run_type_c_sweep` — Numba parallel float64 SMA grid
- `monte_neo.fair_race.run_type_b_scenarios` — Metal/MLX scenario batch with CPU fallback
- `monte_neo.fair_race.return_path_bootstrap` — Type A return-path bootstrap peer
- CLI: `monte-neo-fair-race`

Pinned for ClaimBound card `MANIFOLD_MONTE_NEO_FAIR_RACE_D001`.
