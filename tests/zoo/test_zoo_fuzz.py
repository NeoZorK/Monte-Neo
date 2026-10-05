"""A13: differential fuzzing of the two engines. ``FUZZ_N`` configurations (default 120; the nightly job uses 10000)."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

import numpy as np
import pytest

from monte_neo.backtest import ExecutionModel, run_bar_backtest
from monte_neo.backtest.weight_engine import run_weight_backtest

FUZZ_N = int(os.environ.get("FUZZ_N", "120"))


def config(seed: int):  # noqa: ANN201
    """A random table with gaps and spikes, random positions and a random execution model."""
    rng = np.random.default_rng(seed)
    n = int(rng.integers(60, 500))
    steps = rng.normal(0.0, rng.choice([0.002, 0.01, 0.03]), n)
    close = 100.0 * np.exp(np.cumsum(steps))
    gap = np.where(rng.random(n) < 0.05, rng.normal(0.0, 0.05, n), 0.0)  # an open that jumps away from the previous close
    open_ = np.r_[close[0], close[:-1]] * np.exp(gap)
    spread = np.abs(rng.normal(0.0, 0.01, n))
    high = np.maximum(open_, close) * (1.0 + spread)
    low = np.minimum(open_, close) * (1.0 - spread)
    hold = int(rng.integers(1, 40))
    sig = np.repeat(rng.integers(-1, 2, n // hold + 1), hold)[:n]
    model = ExecutionModel(
        side_mode=str(rng.choice(["long_flat", "long_short"])),
        commission_bps=float(rng.uniform(0, 20)), slippage_bps=float(rng.uniform(0, 20)),
        warmup_bars=int(rng.integers(0, 20)), fill_policy=str(rng.choice(["next_bar_open", "next_bar_close"])),
        funding_bps_per_bar=float(rng.choice([0.0, 0.3])), borrow_bps_per_bar=float(rng.choice([0.0, 0.4])),
        sl_pct=float(rng.choice([0.0, 0.5, 2.0, 5.0])), tp_pct=float(rng.choice([0.0, 0.5, 3.0, 10.0])),
        trail_pct=float(rng.choice([0.0, 1.0, 4.0])), size_fraction=float(rng.choice([1.0, 0.6])), leverage=float(rng.choice([1.0, 2.0])),
    )
    return open_, high, low, close, sig, model


@pytest.mark.parametrize("seed", range(FUZZ_N))
def test_the_bar_engine_and_the_weight_engine_agree_bit_for_bit(seed: int) -> None:
    o, h, l, c, sig, model = config(seed)
    a = run_bar_backtest(o, h, l, c, sig, model=model)
    b = run_weight_backtest(o, c, sig.astype(np.float64), model=model, high=h, low=l)
    assert np.array_equal(a["equity"], b["equity"])
    for key in ("total_return", "max_drawdown", "n_trades", "n_closed_trades"):
        assert a[key] == b[key], key


@pytest.mark.parametrize("seed", range(min(FUZZ_N, 200)))
def test_scaling_every_price_changes_nothing(seed: int) -> None:
    o, h, l, c, sig, model = config(10_000 + seed)
    k = float(np.random.default_rng(seed).choice([0.001, 7.0, 1e4]))
    a = run_bar_backtest(o, h, l, c, sig, model=model)
    b = run_bar_backtest(o * k, h * k, l * k, c * k, sig, model=model)
    assert a["total_return"] == pytest.approx(b["total_return"], rel=1e-9, abs=1e-12)
    assert a["n_trades"] == b["n_trades"]


@pytest.mark.parametrize("seed", range(min(FUZZ_N, 200)))
def test_more_cost_never_helps_with_the_same_trades(seed: int) -> None:
    o, h, l, c, sig, model = config(20_000 + seed)
    cheap = ExecutionModel(**{**model.to_dict(), "commission_bps": 0.0, "slippage_bps": 0.0})
    dear = ExecutionModel(**{**model.to_dict(), "commission_bps": 25.0, "slippage_bps": 25.0})
    a, b = run_bar_backtest(o, h, l, c, sig, model=cheap), run_bar_backtest(o, h, l, c, sig, model=dear)
    if a["n_trades"] == b["n_trades"]:  # costs can change a stop-driven path; with the same number of fills they only subtract
        assert b["total_return"] <= a["total_return"] + 1e-12


SCRIPT = """
import hashlib, json, sys
sys.path.insert(0, "tests/zoo")
import numpy as np
from test_zoo_fuzz import config
from monte_neo.backtest import run_bar_backtest
out = []
for seed in range(40):
    o, h, l, c, sig, model = config(30_000 + seed)
    r = run_bar_backtest(o, h, l, c, sig, model=model)
    out.append([r["total_return"].hex() if hasattr(r["total_return"], "hex") else repr(r["total_return"]), r["n_trades"], hashlib.sha256(np.asarray(r["equity"]).tobytes()).hexdigest()])
print(json.dumps(out))
"""


def test_the_engines_give_the_same_bits_with_and_without_numba() -> None:
    def run(env_extra: dict[str, str]) -> list:
        proc = subprocess.run([sys.executable, "-c", SCRIPT], capture_output=True, text=True, env={**os.environ, **env_extra}, check=True, timeout=600)
        return json.loads(proc.stdout.strip().splitlines()[-1])

    assert run({}) == run({"NUMBA_DISABLE_JIT": "1"})
    _ = hashlib
