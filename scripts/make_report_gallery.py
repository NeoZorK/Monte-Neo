"""Regenerate the example reports of the documentation gallery (docs/assets/reports/*.html).

Every report comes from a real verification run on synthetic data with a known truth, so the
gallery shows what Monte-Neo says about a leak, a strategy without an edge, an honest strategy,
a parameter search and a universe. Run: ``uv run python scripts/make_report_gallery.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "traps"))

from trap_data import bad_tick_ohlcv, planted_momentum_ohlcv, universe_ohlcv  # noqa: E402

from monte_neo.backtest import synthetic_ohlcv  # noqa: E402
from monte_neo.verify import model_from_costs, verify_grid, verify_strategy  # noqa: E402
from monte_neo.verify.report_html import write_html  # noqa: E402

STRATEGIES = ROOT / "tests" / "traps" / "strategies"
OUT = ROOT / "docs" / "assets" / "reports"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    hourly = planted_momentum_ohlcv()
    cheap = model_from_costs(commission_bps=1.0, slippage_bps=1.0, n_bars=len(hourly))
    reports = {
        "leak": verify_strategy(synthetic_ohlcv(3000, seed=1), strategy=STRATEGIES / "lookahead_shift.py", n_trials=40),
        "no-edge": verify_strategy(planted_momentum_ohlcv(n=4000, phi=0.0, seed=4), strategy=STRATEGIES / "sma_cross.py"),
        "honest": verify_strategy(hourly, strategy=STRATEGIES / "momentum.py", model=cheap),
        "grid": verify_grid(hourly, {"lookback": [1, 2, 3, 5, 8, 13]}, strategy=STRATEGIES / "momentum_params.py", model=cheap),
        "universe": verify_strategy(universe_ohlcv(), strategy=STRATEGIES / "xs_momentum_rank.py"),
        "bad-ticks": verify_strategy(bad_tick_ohlcv(), strategy=STRATEGIES / "spike_fade.py"),
    }
    for name, report in reports.items():
        path = write_html(report, OUT / f"{name}.html")
        print(f"{name:10s} {report['verdict']:22s} {path.relative_to(ROOT)} ({path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
