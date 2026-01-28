"""Tests for Sequential Monte Carlo Wizard."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from monte_neo.metrics.calculator import MetricsCalculator
from monte_neo.monte_carlo.engine import MonteCarloEngine
from monte_neo.monte_carlo.sequential import SequentialMCRunner
from monte_neo.monte_carlo.types import MCConfig, MCStepResult


class TestSequentialRunner:
    def setup_method(self):
        self.config = MCConfig(
            iterations=10,
            use_shuffling=True,
            use_noise=True,
            use_sensitivity=False,
            use_walk_forward=False,
            use_block_bootstrap=False,
            use_sequential=True
        )
        # Mock MonteCarloEngine to avoid real GPU/Metal initialization which can hang
        self.engine = MagicMock(spec=MonteCarloEngine)
        self.engine.config = self.config
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
        # Mock _run_step to return passed result
        step_res = MCStepResult(
            method_name="Return Shuffling",
            passed=True,
            pass_rate=0.9,
            metrics_summary={},
            advice="Good",
            iterations=10
        )
        
        with patch.object(self.runner, "_run_step", return_value=step_res) as mock_run_step:
            # Mock user input "press any key"
            mock_questionary.press_any_key_to_continue.return_value.ask.return_value = None
            
            result = self.runner.run(self.data, self.indicator, self.metrics_calc, self.targets)
            
            assert result.passed
            # Check if _run_step was called for enabled methods (shuffling and noise in setup_method)
            assert mock_run_step.call_count == 2

    @patch("monte_neo.monte_carlo.sequential.questionary")
    def test_stop_on_fail(self, mock_questionary):
        """Test stopping when user chooses to abort after failure."""
        # Mock engine to return failing results
        # We need to mock _run_step to return a failed MCStepResult
        with patch.object(self.runner, "_run_step") as mock_run_step:
            mock_run_step.return_value = MCStepResult(
                method_name="Return Shuffling",
                passed=False,
                pass_rate=0.1,
                metrics_summary={},
                advice="Failed",
                iterations=10
            )
            
            # User chooses "No" to continue after failure
            mock_questionary.confirm.return_value.ask.return_value = False
            
            result = self.runner.run(self.data, self.indicator, self.metrics_calc, self.targets)
            
            assert not result.passed
            assert mock_run_step.call_count == 1  # Should stop after first failure

    def test_advice_generation(self):
        """Test advice generation logic."""
        # Passing case
        advice = self.runner._generate_advice("shuffling", 0.96, {})
        assert "Passed" in advice or "Excellent" in advice or "passed" in advice
        
        # Failing case
        advice = self.runner._generate_advice("shuffling", 0.4, {})
        assert "Failed" in advice or "fail" in advice or "dependence" in advice or "similar" in advice
