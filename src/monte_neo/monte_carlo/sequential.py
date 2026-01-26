"""Sequential Monte Carlo execution module."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from rich.console import Console
from rich.table import Table

from monte_neo.monte_carlo.types import MCStepResult, MCResult

if TYPE_CHECKING:
    from monte_neo.indicators.base import BaseIndicator
    from monte_neo.metrics.calculator import MetricsCalculator
    from monte_neo.monte_carlo.engine import MonteCarloEngine


console = Console()


class SequentialMCRunner:
    """Runner for sequential Monte Carlo methods."""

    def __init__(self, engine: MonteCarloEngine):
        """Initialize runner.

        Args:
            engine: Base MonteCarloEngine.
        """
        self.engine = engine

    def run(
        self,
        data: pd.DataFrame,
        indicator: BaseIndicator,
        metrics_calc: MetricsCalculator,
        target_metrics: dict[str, float],
    ) -> MCResult:
        """Run MC methods sequentially.

        Args:
            data: OHLCV data.
            indicator: Indicator to test.
            metrics_calc: Metrics calculator.
            target_metrics: Target metrics.

        Returns:
            MCResult with sequential results.
        """
        start_time = time.time()
        step_results = []
        all_passed = True
        
        # Define methods in requested order
        methods = [
            ("Walk-Forward Analysis", "walk_forward"),
            ("Block Bootstrap", "block_bootstrap"),
            ("Return Shuffling", "shuffling"),
            ("Noise Injection", "noise"),
            ("Sensitivity Analysis", "sensitivity"),
        ]

        # Use rich table for sequential output if it's the main display
        console.print(f"\n[bold yellow]🔍 Sequential MC Validation for: {indicator.name}[/]")
        
        table = Table(title="Monte Carlo Steps", show_header=True, header_style="bold magenta")
        table.add_column("Method", style="cyan")
        table.add_column("Pass Rate", justify="right")
        table.add_column("Status", justify="center")

        for display_name, method_key in methods:
            # Check if method is enabled in config
            is_enabled = getattr(self.engine.config, f"use_{method_key}")
            if not is_enabled:
                continue

            # Run method
            step_result = self._run_step(
                display_name, method_key, data, indicator, metrics_calc, target_metrics
            )
            step_results.append(step_result)

            # Update output
            status = "[green]PASSED[/]" if step_result.passed else "[red]FAILED[/]"
            table.add_row(display_name, f"{step_result.pass_rate:.1%}", status)
            
            # Print current state
            console.clear()
            console.print(f"\n[bold yellow]🔍 Sequential MC Validation for: {indicator.name}[/]")
            console.print(table)

            if not step_result.passed:
                all_passed = False
                console.print(f"\n[bold red]❌ Aborted: {display_name} failed.[/]")
                break

        elapsed = time.time() - start_time
        pass_rate = 1.0 if all_passed else (len([r for r in step_results if r.passed]) / len(methods))

        return MCResult(
            passed=all_passed,
            pass_rate=pass_rate,
            iterations_run=sum(len(r.metrics_summary) for r in step_results), # Approximate
            elapsed_time=elapsed,
            step_results=step_results,
        )

    def _run_step(
        self,
        name: str,
        key: str,
        data: pd.DataFrame,
        indicator: BaseIndicator,
        metrics_calc: MetricsCalculator,
        target_metrics: dict[str, float],
    ) -> MCStepResult:
        """Run a single MC step."""
        scenarios = []
        iterations = self.engine.config.iterations

        if key == "walk_forward":
            scenarios = self.engine.scenario_builder.generate_walk_forward(data)
        elif key == "block_bootstrap":
            scenarios = self.engine.scenario_builder.generate_block_bootstrap(data, iterations)
        elif key == "shuffling":
            scenarios = self.engine.scenario_builder.generate_shuffling(data, iterations)
        elif key == "noise":
            scenarios = self.engine.scenario_builder.generate_noise(data, iterations)
        elif key == "sensitivity":
            # Sensitivity is special as it varies parameters, not data
            return self._run_sensitivity_step(indicator, data, metrics_calc, target_metrics)

        # Run backtests for scenarios
        results = self.engine.gpu_engine.backtest_scenarios(
            indicator,
            scenarios,
            executor=self.engine.executor,
            use_sl_tp=self.engine.config.use_sl_tp,
            sl_pct=self.engine.config.sl_pct,
            tp_pct=self.engine.config.tp_pct,
        )
        
        passed_count = sum(1 for r in results if r["passed"])
        pass_rate = passed_count / len(results) if results else 0.0
        passed = pass_rate >= self.engine.config.pass_threshold

        from monte_neo.monte_carlo.utils import summarize_metrics
        summary = summarize_metrics(results)
        advice = self._generate_advice(name, pass_rate, summary)

        return MCStepResult(
            method_name=name,
            passed=passed,
            pass_rate=pass_rate,
            metrics_summary=summary,
            advice=advice,
        )

    def _run_sensitivity_step(
        self,
        indicator: BaseIndicator,
        data: pd.DataFrame,
        metrics_calc: MetricsCalculator,
        target_metrics: dict[str, float],
    ) -> MCStepResult:
        """Run sensitivity analysis step."""
        from monte_neo.monte_carlo.sensitivity import SensitivityAnalyzer
        analyzer = SensitivityAnalyzer(variation_range=self.engine.config.sensitivity_range)
        results = analyzer.analyze_all_parameters(indicator, data, metrics_calc)
        report = analyzer.get_stability_report(results)

        pass_rate = report["average_stability"]
        passed = report["overall_stable"]
        
        summary = {
            "stability_score": {"mean": pass_rate},
            "stable_params": {"mean": report["stable_parameters"]},
            "total_params": {"mean": report["total_parameters"]},
        }
        
        advice = self._generate_advice("Sensitivity Analysis", pass_rate, summary)

        return MCStepResult(
            method_name="Sensitivity Analysis",
            passed=passed,
            pass_rate=pass_rate,
            metrics_summary=summary,
            advice=advice,
        )

    def _generate_advice(self, method_name: str, pass_rate: float, summary: dict) -> str:
        """Generate advice based on results."""
        if pass_rate >= 0.95:
            if method_name == "Walk-Forward Analysis":
                return "Excellent stability over time. The strategy adapts well to different market regimes."
            if method_name == "Block Bootstrap":
                return "High statistical significance. The edge is likely not due to random price sequences."
            if method_name == "Return Shuffling":
                return "The strategy captures real market structure, not just random price distributions."
            if method_name == "Noise Injection":
                return "Robust against price execution noise and minor volatility spikes."
            if method_name == "Sensitivity Analysis":
                return "Parameters are well-tuned and stable. Not over-optimized for specific values."
            return "Strategy passed this stage with high confidence."
        
        if pass_rate >= 0.80:
            return f"Strategy is mostly stable but shows some weakness in {method_name}. Consider slight adjustments."
        
        if method_name == "Walk-Forward Analysis":
            return "Strategy fails to maintain performance across different time periods. Risk of over-fitting to specific dates."
        if method_name == "Block Bootstrap":
            return "Low statistical significance. The strategy might be capturing noise or specific patterns that don't repeat."
        if method_name == "Return Shuffling":
            return "Performance is similar to random entry. The 'edge' might be an illusion of price distribution."
        if method_name == "Noise Injection":
            return "Strategy is very sensitive to price noise. Might fail in real-market execution with slippage."
        if method_name == "Sensitivity Analysis":
            return "High sensitivity to parameter changes. Likely over-optimized (curve-fitted)."
            
        return "Strategy failed to meet robustness criteria for this method."
