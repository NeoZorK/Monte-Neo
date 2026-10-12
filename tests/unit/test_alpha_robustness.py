"""Family E: robustness checks of a score's long-short portfolio."""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
import pytest

from monte_neo.alpha.panel import Panel, build_panel
from monte_neo.alpha.report import demo_panel
from monte_neo.alpha.robustness import NEXT_ACTIONS, run_robustness
from monte_neo.alpha.robustness_common import spread
from monte_neo.alpha.robustness_null import block_indices


def _rows(rows: list[dict]) -> dict[str, dict]:
    return {r["id"]: r for r in rows}


def _panel(ret: np.ndarray, scores: np.ndarray, freq: str | None = None) -> Panel:
    """Panel where ``ret[t]`` is the return from bar t to t+1 (so a score at t can predict it)."""
    t, n = ret.shape
    close = 100.0 * np.cumprod(1.0 + np.vstack([np.zeros((1, n)), ret[:-1]]), axis=0)
    dates = pd.bdate_range("2020-01-01", periods=t) if freq is None else pd.date_range("2024-01-02 09:30", periods=t, freq=freq)
    return Panel(dates=dates, symbols=[f"S{i:02d}" for i in range(n)], close=close, scores=scores)


def _noise(seed: int = 1, t: int = 750, n: int = 40) -> tuple[np.ndarray, np.ndarray, np.random.Generator]:
    rng = np.random.default_rng(seed)
    return 0.02 * rng.standard_normal((t, n)), rng.standard_normal((t, n)), rng


@pytest.fixture(scope="module")
def demo() -> tuple[Panel, Panel]:
    prices, real, noise = demo_panel()
    return build_panel(prices, real), build_panel(prices, noise)


def test_real_edge_passes_and_noise_fails(demo: tuple[Panel, Panel]) -> None:
    real, noise = demo
    # The demo edge is weak and its score changes every day: a 1 bp cost keeps it alive, 10 bps does not.
    r = _rows(run_robustness(real, cost_bps=1.0))
    assert r["universe_subsampling"]["status"] in ("pass", "warn")
    assert r["synthetic_market_null"]["status"] == "pass"
    assert r["cpcv_paths"]["status"] == "info"
    n = _rows(run_robustness(noise))
    assert n["synthetic_market_null"]["status"] == "fail"
    assert n["universe_subsampling"]["status"] == "fail"
    assert all(set(x) == {"id", "category", "status", "summary", "details"} for x in run_robustness(real))
    assert set(NEXT_ACTIONS) == set(r)


def test_two_symbols_carry_all_profit() -> None:
    ret, z, _ = _noise(2)
    ret = ret.copy()
    ret[:, :2] += 0.02 * z[:, :2]  # the edge lives in two symbols only
    row = _rows(run_robustness(_panel(ret, z), cost_bps=0.0))["universe_subsampling"]
    assert row["status"] in ("warn", "fail")
    assert row["details"]["top5_profit_share"] > 0.7


def test_group_split() -> None:
    ret, z, rng = _noise(3)
    groups = {f"S{i:02d}": "A" if i < 20 else "B" for i in range(40)}
    one = ret.copy()
    one[:, :20] += 0.004 * z[:, :20]
    s = z.copy()
    s[:, 20:] = rng.standard_normal((750, 20))
    assert _rows(run_robustness(_panel(one, s), groups=groups))["group_split"]["status"] == "warn"
    both = ret + 0.004 * z
    assert _rows(run_robustness(_panel(both, z), groups=groups, cost_bps=1.0))["group_split"]["status"] == "pass"
    assert _rows(run_robustness(_panel(both, z)))["group_split"]["status"] == "skip"


def test_start_date_sensitivity_flags_early_only_profit() -> None:
    ret, z, _ = _noise(4)
    early = ret.copy()
    early[:75] += 0.01 * z[:75]
    assert _rows(run_robustness(_panel(early, z), cost_bps=0.0))["start_date_sensitivity"]["status"] == "warn"
    steady = ret + 0.004 * z
    assert _rows(run_robustness(_panel(steady, z), cost_bps=0.0))["start_date_sensitivity"]["status"] == "pass"


def test_noise_injection_flags_fragile_score() -> None:
    ret, z, rng = _noise(5)
    ret = ret + 0.004 * z
    fragile = z.copy()
    fragile[np.arange(750), rng.integers(0, 40, 750)] = 1e4  # one huge value per date hides the fine ranks
    rows = _rows(run_robustness(_panel(ret, fragile), cost_bps=0.0))
    assert rows["noise_injection"]["status"] == "warn"
    assert _rows(run_robustness(_panel(ret, z), cost_bps=0.0))["noise_injection"]["status"] == "pass"


def test_data_source_replication() -> None:
    ret, z, _ = _noise(6)
    ret = ret + 0.004 * z
    pan = _panel(ret, z)
    assert _rows(run_robustness(pan, cost_bps=0.0))["data_source_replication"]["status"] == "skip"
    same = _rows(run_robustness(pan, alt_close=pan.close * 1.001, cost_bps=0.0))["data_source_replication"]
    assert same["status"] == "pass"
    flipped = _panel(-ret, z).close
    row = _rows(run_robustness(pan, alt_close=flipped, cost_bps=0.0))["data_source_replication"]
    assert row["status"] == "warn" and row["details"]["sign_flip"]
    frame = pd.DataFrame(pan.close, index=pan.dates, columns=pan.symbols)
    assert _rows(run_robustness(pan, alt_close=frame, cost_bps=0.0))["data_source_replication"]["status"] == "pass"


def test_bar_construction() -> None:
    ret, z, _ = _noise(7, t=600)
    ret = ret + 0.004 * z
    assert _rows(run_robustness(_panel(ret, z)))["bar_construction"]["status"] == "skip"
    intraday = _panel(ret, z, freq="5min")
    assert _rows(run_robustness(intraday, cost_bps=0.0))["bar_construction"]["status"] == "pass"
    odd_only = ret.copy()
    odd_only[0::2] -= 0.004 * z[0::2] * 2.0
    assert _rows(run_robustness(_panel(odd_only, z, freq="5min"), cost_bps=0.0))["bar_construction"]["status"] == "warn"


def test_block_indices_are_valid_and_blocky() -> None:
    idx = block_indices(300, 50, np.random.default_rng(0))
    assert idx.shape == (50, 300) and idx.min() >= 0 and idx.max() < 300
    assert np.mean(np.diff(idx, axis=1) == 1) > 0.85


def test_spread_is_causal() -> None:
    ret, z, _ = _noise(8, t=200, n=20)
    close = _panel(ret, z).close
    base = spread(close, z, 5, 10.0)
    changed = z.copy()
    changed[-1] = -changed[-1]  # the last score can only trade after the last bar
    assert np.allclose(base, spread(close, changed, 5, 10.0))


def test_determinism_and_runtime(demo: tuple[Panel, Panel]) -> None:
    real, _ = demo
    t0 = time.perf_counter()
    a = run_robustness(real, seed=3, cost_bps=1.0)
    assert time.perf_counter() - t0 < 10.0
    assert a == run_robustness(real, seed=3, cost_bps=1.0)
