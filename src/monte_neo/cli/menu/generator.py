"""Indicator generation workflow."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from monte_neo.cli.styles import CUSTOM_STYLE
from monte_neo.core.generator import GeneratorConfig, IndicatorGenerator

if TYPE_CHECKING:
    from monte_neo.cli.menu.main import InteractiveMenu

console = Console()


def generate_indicator_workflow(menu: InteractiveMenu) -> None:
    """Generate indicator workflow."""
    console.print("\n[bold cyan]🚀 Generate Indicator[/]\n")

    if not menu._target_metrics:
        console.print("[yellow]⚠ Please set target metrics first[/]\n")
        return

    files = menu.storage.list_files()
    if not files:
        console.print("[yellow]⚠ No data available. Download data first.[/]\n")
        return

    file_choices = [f"{f['symbol']}_{f['timeframe']}" for f in files]
    selected = questionary.select("Select data:", choices=file_choices, style=CUSTOM_STYLE).ask()

    if not selected:
        return

    symbol, timeframe = selected.split("_")
    
    # Get iterations and types
    iterations = _get_iterations()
    if not iterations: return
    
    indicator_types = _get_indicator_types()
    if not indicator_types: return

    # Confirm and Run
    if not questionary.confirm("Start generation?", style=CUSTOM_STYLE).ask():
        return

    _run_generation(menu, symbol, timeframe, iterations, indicator_types)


def _get_iterations() -> int | None:
    return questionary.select(
        "Number of iterations:",
        choices=[
            {"name": "1,000 (fast test)", "value": 1000},
            {"name": "10,000 (standard)", "value": 10000},
            {"name": "100,000 (thorough)", "value": 100000},
            {"name": "1M (heavy)", "value": 1000000},
            {"name": "10M (expert)", "value": 10000000},
            {"name": "100M (extreme)", "value": 100000000},
            {"name": "1B (insane)", "value": 1000000000},
        ],
        style=CUSTOM_STYLE,
    ).ask()


def _get_indicator_types() -> list[str] | None:
    return questionary.checkbox(
        "Select indicator types to search:",
        choices=[
            {"name": "SMA", "value": "sma", "checked": True},
            {"name": "RSI", "value": "rsi", "checked": True},
            {"name": "MACD", "value": "macd", "checked": True},
            {"name": "🧬 Dynamic", "value": "dynamic", "checked": True},
        ],
        style=CUSTOM_STYLE,
    ).ask()


def _run_generation(menu: InteractiveMenu, symbol: str, timeframe: str, iterations: int, types: list[str]) -> None:
    data = menu.storage.load(symbol, timeframe)
    menu._last_data = data

    config = GeneratorConfig(
        max_iterations=iterations,
        target_metrics=menu._target_metrics,
        indicator_types=types,
        population_size=menu._pop_size,
        generations=menu._generations,
        mutation_rate=menu._mutation_rate,
        crossover_rate=menu._crossover_rate,
        use_mc_shuffling="shuffling" in menu._mc_methods,
        use_mc_noise="noise" in menu._mc_methods,
        use_mc_sensitivity="sensitivity" in menu._mc_methods,
        use_mc_walk_forward="walk_forward" in menu._mc_methods,
        use_mc_block_bootstrap="block_bootstrap" in menu._mc_methods,
    )

    generator = IndicatorGenerator(config)
    menu.progress.start(iterations, "Generating indicator...")
    generator.set_progress_callback(menu.progress.update)

    result = generator.generate(data)
    time.sleep(0.1)
    menu.progress.update(iterations, iterations, "Done")
    menu.progress.stop()

    from monte_neo.cli.menu.results import show_generation_result
    show_generation_result(menu, result)
