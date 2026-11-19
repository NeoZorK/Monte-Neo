"""Performance baseline: wall time and peak memory of verify, alpha and research on reference inputs.

Each (task, size) runs in its own subprocess, so peak memory is that of one task. The first call
includes Numba compilation or cache loading (cold), the second is the steady state (warm).

Usage:
    python scripts/perf_baseline.py                       # sizes 1e4 1e5 1e6, all tasks
    python scripts/perf_baseline.py --sizes 10000 100000 --tasks verify research
    python scripts/perf_baseline.py --profile verify 100000   # top cumulative-time functions
    python scripts/perf_baseline.py --out perf_baseline.json

Resumable: tasks already present in --out are skipped (delete the file to start over).
Status: the JSON file is rewritten after every task; each result is also printed as it finishes.
"""

from __future__ import annotations

import argparse
import json
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path

TASKS = ("verify", "alpha", "research")


def _peak_mb() -> float:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss / (1024 * 1024) if sys.platform == "darwin" else rss / 1024


def _build(task: str, n: int):
    """Return a zero-argument callable that runs one task on an input of about ``n`` bars/rows."""
    import numpy as np

    if task == "verify":
        from monte_neo.backtest import synthetic_ohlcv
        from monte_neo.verify import verify_strategy

        df = synthetic_ohlcv(n, seed=1)

        def honest(frame):
            return np.where(frame["close"].rolling(20).mean() > frame["close"].rolling(80).mean(), 1, 0)

        return lambda: verify_strategy(df, signal_fn=honest, n_trials=10)
    if task == "alpha":
        from monte_neo.alpha.report import demo_panel, validate_alpha

        symbols = max(20, int((n / 2.5) ** 0.5))
        days = max(250, n // symbols)
        prices, scores, _ = demo_panel(seed=0, n_symbols=symbols, n_days=days)
        return lambda: validate_alpha(prices, scores, placebos=50)
    if task == "research":
        from monte_neo.backtest import run_bar_backtest, run_sma_sweep, sma_signal, synthetic_ohlcv

        df = synthetic_ohlcv(n, seed=1)
        o, h, lo, c = (df[k].to_numpy(dtype="float64") for k in ("open", "high", "low", "close"))

        def run():
            run_bar_backtest(o, h, lo, c, sma_signal(c, 10, 40))
            run_sma_sweep(o, h, lo, c, combos=64, device="cpu_numba")

        return run
    raise SystemExit(f"unknown task {task}")


def _child(task: str, n: int, profile: bool) -> None:
    import monte_neo
    from monte_neo.backtest.jit import HAS_NUMBA

    t0 = time.perf_counter()
    fn = _build(task, n)
    build_s = time.perf_counter() - t0
    t0 = time.perf_counter()
    fn()
    cold = time.perf_counter() - t0
    if profile:
        import cProfile
        import pstats

        prof = cProfile.Profile()
        prof.runcall(fn)
        pstats.Stats(prof).sort_stats("cumulative").print_stats(15)
        return
    t0 = time.perf_counter()
    fn()
    warm = time.perf_counter() - t0
    print(json.dumps({"task": task, "size": n, "build_s": round(build_s, 2), "cold_s": round(cold, 2), "warm_s": round(warm, 2),
                      "peak_rss_mb": round(_peak_mb()), "numba": HAS_NUMBA, "version": getattr(monte_neo, "__version__", "")}))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sizes", type=int, nargs="+", default=[10_000, 100_000, 1_000_000])
    ap.add_argument("--tasks", nargs="+", choices=TASKS, default=list(TASKS))
    ap.add_argument("--timeout", type=int, default=1800, help="seconds per task")
    ap.add_argument("--out", default="perf_baseline.json")
    ap.add_argument("--profile", nargs=2, metavar=("TASK", "SIZE"))
    ap.add_argument("--child", nargs=2, metavar=("TASK", "SIZE"), help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.child:
        _child(a.child[0], int(a.child[1]), False)
        return 0
    if a.profile:
        _child(a.profile[0], int(a.profile[1]), True)
        return 0
    out = Path(a.out)
    data = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {"env": {}, "results": []}
    data["env"] = {"python": platform.python_version(), "machine": platform.machine(), "system": platform.platform()}
    done = {(r["task"], r["size"]) for r in data["results"]}
    total = len(a.tasks) * len(a.sizes)
    for i, (task, n) in enumerate(((t, n) for n in a.sizes for t in a.tasks), 1):
        if (task, n) in done:
            continue
        print(f"[{i}/{total}] {task} n={n} ...", flush=True)
        try:
            r = subprocess.run([sys.executable, __file__, "--child", task, str(n)], capture_output=True, text=True, timeout=a.timeout)
            row = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {"task": task, "size": n, "error": r.stderr.strip()[-300:]}
        except subprocess.TimeoutExpired:
            row = {"task": task, "size": n, "error": f"timeout after {a.timeout}s"}
        data["results"].append(row)
        out.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print("   ", row, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
