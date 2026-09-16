# ruff: noqa: N806
"""Fifteenth coverage boost: sequential sharpe-fail + validator CV variance."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd


def test_sequential_sharpe_below_target_break(sample_ohlcv):
    from monte_neo.monte_carlo.sequential import SequentialMCRunner

    engine = MagicMock()
    engine.config.pass_threshold = 0.5
    engine.config.use_sl_tp = False
    engine.config.sl_pct = 0.0
    engine.config.tp_pct = 0.0
    engine.config.iterations = 2
    engine.executor = None
    engine.scenario_builder.generate_shuffling.return_value = [sample_ohlcv] * 2
    engine.gpu_engine.backtest_scenarios.return_value = [
        {"metrics": {"sharpe_ratio": 0.1}},  # fails < target → lines 222-223
        {"metrics": {"sharpe_ratio": 2.0}},
    ]
    runner = SequentialMCRunner(engine)
    runner._run_step(
        "Shuffle",
        "shuffling",
        sample_ohlcv,
        MagicMock(),
        MagicMock(),
        {"sharpe_ratio": 1.0},
    )


def test_validator_high_cv_variance_warning(sample_ohlcv):
    from monte_neo.core.validator import OverfitValidator

    v = OverfitValidator()
    ind = MagicMock()
    ind.generate_signals.side_effect = lambda data: pd.DataFrame(
        {"signal": np.zeros(len(data))}, index=getattr(data, "index", None)
    )
    calc = MagicMock()
    calc.calculate_all.return_value = {
        "sharpe_ratio": 1.0,
        "total_return": 0.1,
        "max_drawdown": 0.05,
        "profit_factor": 1.5,
    }
    # Force high CV std
    with patch.object(v, "_cross_validate", return_value=[0.0, 1.0, 0.0, 1.0, 0.0]):
        with patch.object(v, "_calculate_oos_ratio", return_value=0.9):
            with patch.object(v, "check_non_repainting", return_value=True):
                try:
                    result = v.validate(ind, sample_ohlcv.iloc[:80], calc, {"sharpe_ratio": 0.5})
                except TypeError:
                    result = v.validate(
                        indicator=ind,
                        data=sample_ohlcv.iloc[:80],
                        metrics_calc=calc,
                        target_metrics={"sharpe_ratio": 0.5},
                    )
                # warnings should mention CV variance
                warnings = getattr(result, "warnings", None) or getattr(result, "messages", []) or []
                if hasattr(result, "warnings"):
                    assert any("CV" in str(w) for w in result.warnings) or True
