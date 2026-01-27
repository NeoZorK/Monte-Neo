"""Tests for Sequential Monte Carlo Wizard."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from monte_neo.metrics.calculator import MetricsCalculator
from monte_neo.monte_carlo.engine import MonteCarloEngine
from monte_neo.monte_carlo.sequential import SequentialMCRunner
from monte_neo.monte_carlo.types import MCConfig, MCResult


class TestSequentialRunner:
    def setup_method(self):
        self.config = MCConfig(
            iterations=10,
            use_shuffling=True,
            use_noise=True,
            use_sensitivity=False,
            use_walk_forward=False,
            use_sequential=True
        )
        self.engine = MonteCarloEngine(self.config)
        self.runner = SequentialMCRunner(self.engine)
        self.data = pd.DataFrame({
            "open": [100.0] * 50,
            "high": [105.0] * 50,
            "low": [95.0] * 50,
            "close": [101.0] * 50,
            "volume": [1000.0] * 50
        })
        self.indicator = MagicMock()
        self.indicator.name = "TestInd"
        self.metrics_calc = MetricsCalculator()
        self.targets = {"profit_factor": 1.0}

    @patch("monte_neo.monte_carlo.sequential.questionary")
    @patch("monte_neo.monte_carlo.sequential.Console")
    def test_run_sequential_flow(self, mock_console, mock_questionary):
        """Test the sequential flow logic."""
        # Mock engine run to return passed result
        step_res = MCResult(
            passed=True,
            pass_rate=0.9,
            metrics_summary={},
            elapsed_time=0.1,
            detailed_results=[],
            iterations_run=100
        )
        self.engine.run = MagicMock(return_value=step_res)
        self.engine.gpu_engine.backtest_scenarios = MagicMock(return_value=[{"passed": True}])
        
        # Mock user input "press any key" AND the new "Ready to run?" confirm
        # First call: Ready to run? -> True
        # Second call: Press any key -> None
        # Third call: Ready to run next? -> True ...
        # We need to set side_effect or return_value carefully.
        
        # questionary.confirm(...).ask() is called before running step, and potentially after failure.
        # questionary.press_any_key_to_continue(...).ask() is called after success.
        
        # Let's mock confirm to always return True
        mock_questionary.confirm.return_value.ask.return_value = True
        mock_questionary.press_any_key_to_continue.return_value.ask.return_value = None
        
        result = self.runner.run(self.data, self.indicator, self.metrics_calc, self.targets)
        
        assert result.passed
        # Check if engine.run was called multiple times (shuffling, noise)
        # Actually _run_step calls scenario_builder directly, not engine.run recursively
        # It calls engine.gpu_engine.backtest_scenarios
        assert self.engine.gpu_engine.backtest_scenarios.call_count >= 1

    @patch("monte_neo.monte_carlo.sequential.questionary")
    def test_stop_on_fail(self, mock_questionary):
        """Test stopping when user chooses to abort after failure."""
        step_res = MCResult(
            passed=False,
            pass_rate=0.1,
            metrics_summary={},
            elapsed_time=0.1,
            detailed_results=[],
            iterations_run=100
        )
        # Mock backtest to return failing results
        self.engine.gpu_engine.backtest_scenarios = MagicMock(
            return_value=[{"metrics": {"profit_factor": 0.0}}]
        )
        
        # User chooses "Yes" to start method, then "No" to continue after failure
        mock_questionary.confirm.return_value.ask.side_effect = [True, False]
        
        result = self.runner.run(self.data, self.indicator, self.metrics_calc, self.targets)
        
        assert not result.passed
        assert self.engine.gpu_engine.backtest_scenarios.call_count == 1  # Should stop after first failure

    def test_advice_generation(self):
        """Test advice generation logic."""
        # Passing case
        advice = self.runner._generate_advice("shuffling", 0.96, {})
        assert "passed" in advice or "Excellent" in advice
        
        # Failing case
        advice = self.runner._generate_advice("shuffling", 0.4, {})
        assert "dependence" in advice or "fail" in advice
