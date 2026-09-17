#!/usr/bin/env python3
"""First-party research-bar timing: export_sma_sweep on synthetic OHLC.

Peer-free. Prints wall times for device=auto and device=cpu_numba so readers
can reproduce on their own host (Apple Silicon recommended for Metal path).

Example:
  uv run python scripts/bench_research_bar.py --bars 100000 --combos 64
  uv run python scripts/bench_research_bar.py --bars 1000000 --combos 32 --skip-1m false
"""

from __future__ import annotations

import argparse
import platform
import time
from typing import Any

from monte_neo.backtest import ExecutionModel, export_sma_sweep, synthetic_ohlcv


def _one(
    *,
    bars: int,
    combos: int,
    device: str,
    seed: int,
    warmup: bool,
) -> dict[str, Any]:
    ohlc = synthetic_ohlcv(bars, seed=seed)
    model = ExecutionModel(commission_bps=5.0, slippage_bps=5.0, warmup_bars=50)
    if warmup:
        export_sma_sweep(
            ohlc["open"],
            ohlc["high"],
            ohlc["low"],
            ohlc["close"],
            combos=min(8, combos),
            model=model,
            device=device,
        )
    t0 = time.perf_counter()
    out = export_sma_sweep(
        ohlc["open"],
        ohlc["high"],
        ohlc["low"],
        ohlc["close"],
        combos=combos,
        model=model,
        device=device,
    )
    wall_s = time.perf_counter() - t0
    timing = out.get("timing") or {}
    return {
        "bars": bars,
        "combos": out.get("combos", combos),
        "device_requested": device,
        "device": out.get("device"),
        "fallback_reason": out.get("fallback_reason"),
        "ok": out.get("ok"),
        "wall_s": round(wall_s, 4),
        "timing_elapsed_s": timing.get("elapsed_s"),
        "signal_elapsed_s": timing.get("signal_elapsed_s"),
        "economics_elapsed_s": timing.get("economics_elapsed_s"),
        "combos_per_s": out.get("combos_per_s"),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bars", type=int, default=100_000)
    p.add_argument("--combos", type=int, default=64)
    p.add_argument("--bars-1m", type=int, default=1_000_000)
    p.add_argument("--combos-1m", type=int, default=32)
    p.add_argument("--run-1m", action="store_true", help="Also time 1M-bar case")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--no-warmup", action="store_true")
    args = p.parse_args()

    print(
        {
            "host": platform.node(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        }
    )
    warmup = not args.no_warmup
    for device in ("auto", "cpu_numba"):
        row = _one(
            bars=args.bars,
            combos=args.combos,
            device=device,
            seed=args.seed,
            warmup=warmup,
        )
        print(row)

    if args.run_1m:
        for device in ("auto", "cpu_numba"):
            row = _one(
                bars=args.bars_1m,
                combos=args.combos_1m,
                device=device,
                seed=args.seed,
                warmup=warmup,
            )
            print(row)


if __name__ == "__main__":
    main()
