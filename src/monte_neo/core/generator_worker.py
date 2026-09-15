from __future__ import annotations

from typing import TYPE_CHECKING

from monte_neo.indicators.base import BaseIndicator

if TYPE_CHECKING:
    pass


def _search_worker(args: tuple) -> tuple[BaseIndicator | None, float]:
    """Worker for parallel indicator search."""
    (
        indicator,
        data,
        metrics_calc,
        target_metrics,
        mc_iterations,
        mc_shuffling,
        mc_noise,
        mc_sensitivity,
        mc_walk_forward,
        min_trades,
        use_sl_tp,
        sl_pct,
        tp_pct,
    ) = args

    # Quick pre-check
    signals = indicator.generate_signals_fast(data)
    basic_metrics = metrics_calc.calculate_all(
        data, signals, use_sl_tp=use_sl_tp, sl_pct=sl_pct, tp_pct=tp_pct
    )

    # Skip if too few trades
    if basic_metrics.get("trade_count", 0) < min_trades:
        return None, 0.0

    # Skip if basic metrics don't meet targets
    # Inline check for performance
    for name, target in target_metrics.items():
        if name not in basic_metrics:
            continue
        actual = basic_metrics[name]
        if name in ["max_drawdown", "consecutive_losses"]:
            if actual > target:
                return None, 0.0
        else:
            if actual < target:
                return None, 0.0

    # Run Monte Carlo validation
    # Note: We need a static version of MC validation or use engine directly
    from monte_neo.monte_carlo.engine import MCConfig, MonteCarloEngine

    mc_config = MCConfig(
        iterations=mc_iterations,
        use_shuffling=mc_shuffling,
        use_noise=mc_noise,
        use_sensitivity=mc_sensitivity,
        use_walk_forward=mc_walk_forward,
        use_sl_tp=use_sl_tp,
        sl_pct=sl_pct,
        tp_pct=tp_pct,
    )
    mc_engine = MonteCarloEngine(mc_config)
    result = mc_engine.run(data, indicator, metrics_calc, target_metrics)

    return indicator, result.pass_rate
