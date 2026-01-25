import logging

import numpy as np
import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from monte_neo.core.generator import GeneratorConfig, IndicatorGenerator
from monte_neo.indicators.dynamic import DynamicIndicator

# Setup logging to see what's happening
logging.basicConfig(level=logging.INFO)
console = Console()


def create_dummy_data(days=365):
    dates = pd.date_range("2023-01-01", periods=days, freq="D")
    data = pd.DataFrame(index=dates)
    data["open"] = 100 + np.cumsum(np.random.randn(days))
    data["high"] = data["open"] + np.random.rand(days) * 2
    data["low"] = data["open"] - np.random.rand(days) * 2
    data["close"] = (data["open"] + data["high"] + data["low"]) / 3
    data["volume"] = np.random.rand(days) * 1000
    return data


def check_system():
    console.print(
        Panel.fit(
            "Native System Check: Genetic Algorithms & Dynamic Indicators",
            style="bold blue",
        )
    )

    data = create_dummy_data()
    console.print(f"Created dummy data with {len(data)} rows.", style="dim")

    config = GeneratorConfig(
        max_iterations=100,
        population_size=10,
        generations=5,
        indicator_types=["dynamic"],
        mc_iterations=5,  # Speed up for check
        target_metrics={"profit_factor": 0.4, "trade_count": 2},
        early_stopping=False,
    )

    generator = IndicatorGenerator(config)

    console.print("Starting generation...", style="yellow")
    result = generator.generate(data)

    console.print("\n[bold green]Results[/bold green]")

    results_table = Table(show_header=True, header_style="bold magenta")
    results_table.add_column("Metric", style="cyan")
    results_table.add_column("Value", style="white")

    results_table.add_row("Success", str(result.success))
    results_table.add_row("Iterations tried", str(result.iterations_tried))
    results_table.add_row("Candidates found", str(result.candidates_found))
    results_table.add_row("Best MC rate", f"{result.mc_pass_rate:.2%}")

    if result.indicator:
        results_table.add_row("Best indicator type", type(result.indicator).__name__)
        if isinstance(result.indicator, DynamicIndicator):
            results_table.add_row("Best formula", result.indicator.source_code)

    console.print(results_table)

    if result.final_metrics:
        metrics_table = Table(
            title="Final Metrics", show_header=True, header_style="bold magenta"
        )
        metrics_table.add_column("Metric", style="cyan")
        metrics_table.add_column("Value", style="green")

        for k, v in result.final_metrics.items():
            val_str = f"{v:.4f}" if isinstance(v, float) else str(v)
            metrics_table.add_row(k, val_str)
        console.print(metrics_table)

    if result.indicator is not None:
        console.print("\n[bold]Checking signal generation...[/bold]")
        signals = result.indicator.generate_signals(data)

        signal_table = Table(title="Signal Counts", show_header=True)
        signal_table.add_column("Signal", style="cyan")
        signal_table.add_column("Count", style="white")

        for signal, count in signals["signal"].value_counts().items():
            signal_table.add_row(str(signal), str(count))
        console.print(signal_table)

    console.print("\n[bold blue]System Check Complete[/bold blue]")


if __name__ == "__main__":
    check_system()
