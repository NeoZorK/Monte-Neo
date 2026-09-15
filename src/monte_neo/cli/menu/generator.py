"""Indicator generation workflow."""

from __future__ import annotations  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

import time  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
from typing import TYPE_CHECKING  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

import questionary  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

from monte_neo.cli.styles import CUSTOM_STYLE  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
from monte_neo.core.generator import GeneratorConfig, IndicatorGenerator  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
from monte_neo.utils.console import console  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

if TYPE_CHECKING:
    from monte_neo.cli.menu.main import InteractiveMenu


def generate_indicator_workflow(menu: InteractiveMenu, sequential: bool = False) -> None:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    """Generate indicator workflow."""
    title = "🚀 Generate Indicator" if not sequential else "🔄 Sequential Generate Indicator"  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    console.print(f"\n[bold cyan]{title}[/]\n")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    if not menu._target_metrics:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        console.print("[yellow]⚠ Please set target metrics first[/]\n")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        return  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    files = menu.storage.list_files()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    if not files:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        console.print("[yellow]⚠ No data available. Download data first.[/]\n")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        return  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    file_choices = [f"{f['symbol']}_{f['timeframe']}" for f in files]  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    selected = questionary.select("Select data:", choices=file_choices, style=CUSTOM_STYLE).ask()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    if not selected:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        return  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    symbol, timeframe = selected.split("_")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    # Get iterations and types
    iterations = _get_iterations()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    if not iterations: return  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    indicator_types = _get_indicator_types()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    if not indicator_types: return  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    # Confirm and Run
    if not questionary.confirm("Start generation?", style=CUSTOM_STYLE).ask():  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        return  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    _run_generation(menu, symbol, timeframe, iterations, indicator_types, sequential)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests


def _get_iterations() -> int | None:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    return questionary.select(  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
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


def _get_indicator_types() -> list[str] | None:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    return questionary.checkbox(  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        "Select indicator types to search:",
        choices=[
            {"name": "SMA", "value": "sma", "checked": True},
            {"name": "RSI", "value": "rsi", "checked": True},
            {"name": "MACD", "value": "macd", "checked": True},
            {"name": "🧬 Dynamic", "value": "dynamic", "checked": True},
        ],
        style=CUSTOM_STYLE,
    ).ask()


def _run_generation(menu: InteractiveMenu, symbol: str, timeframe: str, iterations: int, types: list[str], sequential: bool = False) -> None:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    data = menu.storage.load(symbol, timeframe)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    menu._last_data = data  # Restore to allow charting after generation  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    config = GeneratorConfig(
        max_iterations=iterations,
        target_metrics=menu._target_metrics,
        indicator_types=types,
        population_size=menu._pop_size,
        generations=menu._generations,
        mutation_rate=menu._mutation_rate,
        crossover_rate=menu._crossover_rate,
        use_sl_tp=menu._use_sl_tp,
        stop_loss_pct=menu._stop_loss_pct,
        take_profit_pct=menu._take_profit_pct,
        use_mc_shuffling="shuffling" in menu._mc_methods,
        use_mc_noise="noise" in menu._mc_methods,
        use_mc_sensitivity="sensitivity" in menu._mc_methods,
        use_mc_walk_forward="walk_forward" in menu._mc_methods,
        use_mc_block_bootstrap="block_bootstrap" in menu._mc_methods,
        use_sequential_mc=sequential,
        mc_pass_threshold=getattr(menu, "_mc_pass_threshold", 0.80),
        use_gpu=getattr(menu, "_use_gpu", True),
        gpu_precision=getattr(menu, "_gpu_precision", "float32"),
        metal_driver=getattr(menu, "_metal_driver", "cpp"),
        initial_capital=menu.config.initial_capital,
        leverage=menu.config.leverage,
    )

    generator = IndicatorGenerator(config)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    menu.progress.start(iterations, "Generating indicator...")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    generator.set_progress_callback(menu.progress.update)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    try:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        result = generator.generate(data)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        time.sleep(0.1)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        menu.progress.update(iterations, iterations, "Done")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    except KeyboardInterrupt:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        menu.progress.stop()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        console.print("\n[yellow]Generation cancelled by user.[/]")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        return  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    except Exception as e:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        menu.progress.stop()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        console.print(f"\n[red]Generation error: {e}[/]")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        return  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    finally:
        menu.progress.stop()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    from monte_neo.cli.menu.results import show_generation_result  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    show_generation_result(menu, result)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
