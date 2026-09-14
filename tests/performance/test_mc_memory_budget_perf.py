"""Perf smoke: MC scenario budget stays within 16GB-class usable envelope."""

from __future__ import annotations

from monte_neo.monte_carlo.memory_budget import DEFAULT_USABLE_BYTES, plan_scenario_budget


def test_m1_pro_16gb_budget_smoke() -> None:
    # Typical Type-B style workload: 50k bars × many scenarios.
    bud = plan_scenario_budget(50_000, 20_000, itemsize=4)
    assert bud.bytes_peak_est <= DEFAULT_USABLE_BYTES
    assert bud.tile_scenarios < 20_000 or bud.fits_in_one_tile
    assert bud.bytes_per_scenario * bud.tile_scenarios == bud.bytes_peak_est
