"""Custom indicator testing workflow."""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import questionary
from rich.console import Console
from rich.panel import Panel

from monte_neo.cli.styles import CUSTOM_STYLE
from monte_neo.core.generator import GeneratorConfig
from monte_neo.indicators.base import BaseIndicator
from monte_neo.metrics.calculator import MetricsCalculator
from monte_neo.monte_carlo.engine import MonteCarloEngine
from monte_neo.monte_carlo.sequential import SequentialMCRunner
from monte_neo.utils.logger import get_logger

if TYPE_CHECKING:
    from monte_neo.cli.menu.main import InteractiveMenu

logger = get_logger(__name__)
console = Console()


def test_custom_indicator_workflow(menu: InteractiveMenu) -> None:
    """Workflow for testing custom user indicators."""
    console.print("\n[bold cyan]🧪 Test Custom Formula[/]\n")

    # 1. Select Data
    files = menu.storage.list_files()
    if not files:
        console.print("[yellow]⚠ No data available. Download data first.[/]\n")
        return

    file_choices = [f"{f['symbol']}_{f['timeframe']}" for f in files]
    selected_data = questionary.select("Select data for testing:", choices=file_choices, style=CUSTOM_STYLE).ask()
    if not selected_data:
        return

    symbol, timeframe = selected_data.split("_")
    data = menu.storage.load(symbol, timeframe)
    menu._last_data = data

    # 2. Select Indicator File
    indicators_dir = Path("user_indicators")
    if not indicators_dir.exists():
        indicators_dir.mkdir()
        # Create template if not exists (should be done elsewhere, but safety check)
    
    py_files = list(indicators_dir.glob("*.py"))
    if not py_files:
        console.print("[yellow]⚠ No python files found in user_indicators/ directory.[/]\n")
        return

    file_map = {f.name: f for f in py_files}
    selected_file = questionary.select(
        "Select indicator file:",
        choices=list(file_map.keys()),
        style=CUSTOM_STYLE
    ).ask()

    if not selected_file:
        return

    file_path = file_map[selected_file]

    # 3. Load Indicator Class
    indicator_class = _load_indicator_class(file_path)
    if not indicator_class:
        console.print("[red]❌ No valid BaseIndicator subclass found in the selected file.[/]")
        return

    console.print(f"[green]✓ Loaded indicator: {indicator_class.__name__}[/]")

    # 4. Configure & Run
    iterations = questionary.select(
        "Number of MC iterations:",
        choices=[
            {"name": "1,000 (fast)", "value": 1000},
            {"name": "10,000 (standard)", "value": 10000},
            {"name": "100,000 (thorough)", "value": 100000},
        ],
        style=CUSTOM_STYLE
    ).ask() or 1000

    if not questionary.confirm("Start comprehensive validation?", style=CUSTOM_STYLE).ask():
        return

    # Setup Engine
    config = GeneratorConfig(
        max_iterations=iterations,
        target_metrics=menu._target_metrics,
        use_mc_shuffling=True,
        use_mc_noise=True,
        use_mc_sensitivity=True,
        use_mc_walk_forward=True,
        use_mc_block_bootstrap=True,
        use_sequential_mc=True,
    )
    
    # Manually configure MonteCarloEngine
    from monte_neo.monte_carlo.types import MCConfig
    mc_config = MCConfig(
        iterations=iterations,
        n_workers=4, # Auto-detect in real app
        use_shuffling=True,
        use_noise=True,
        use_sensitivity=True,
        use_walk_forward=True,
        use_block_bootstrap=True,
        use_sequential=True,
        pass_threshold=0.80,
    )

    engine = MonteCarloEngine(mc_config)
    metrics_calc = MetricsCalculator()
    
    # Instantiate Indicator
    indicator = indicator_class()
    
    # Run Sequential Runner directly
    runner = SequentialMCRunner(engine)
    
    console.print(f"\n[bold]🚀 Running Validation for {indicator.name}...[/]")
    
    # Create a result object structure similar to generation result
    try:
        mc_result = runner.run(data, indicator, metrics_calc, menu._target_metrics)
        
        # Display Final Certificate if passed
        from monte_neo.cli.menu.results import show_generation_result
        
        # We need to construct a "GenerationResult" like object or just reuse the display logic
        # For simplicity, let's create a simple object to pass to show_generation_result logic
        # OR just reuse _print_trust_certificate directly if we import it.
        
        from monte_neo.cli.menu.results import _print_trust_certificate
        
        class MockResult:
            def __init__(self, ind, mc_res):
                self.indicator = ind
                self.success = mc_res.passed
                self.mc_pass_rate = mc_res.pass_rate
                self.mc_details = {"step_results": [
                    {
                        "method": s.method_name,
                        "passed": s.passed,
                        "rate": s.pass_rate,
                        "advice": s.advice
                    } for s in mc_res.step_results
                ]}
                self.elapsed_time = mc_res.elapsed_time
                self.iterations_tried = iterations
                self.final_metrics = {} # We could calculate baseline metrics here
                self.parameters = ind.get_parameters()

        mock_res = MockResult(indicator, mc_result)
        
        if mock_res.success:
            _print_trust_certificate(mock_res)
        else:
            console.print("\n[bold red]❌ Validation Failed. See advice above to improve your indicator.[/]")
            
        # Chart
        if questionary.confirm("Show chart?", style=CUSTOM_STYLE).ask():
            from monte_neo.visualization.charts import ChartGenerator
            chart_gen = ChartGenerator()
            signals = indicator.generate_signals(data)
            chart_gen.plot_with_signals(data, signals, title=f"Test: {indicator.name}")

    except Exception as e:
        console.print(f"[red]Error during validation: {e}[/]")
        logger.exception("Validation error")


def _load_indicator_class(file_path: Path) -> type[BaseIndicator] | None:
    """Load the first BaseIndicator subclass found in the file."""
    spec = importlib.util.spec_from_file_location("custom_indicator", file_path)
    if not spec or not spec.loader:
        return None
    
    module = importlib.util.module_from_spec(spec)
    sys.modules["custom_indicator"] = module
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        console.print(f"[red]Error loading module: {e}[/]")
        return None

    for name, obj in inspect.getmembers(module):
        if (
            inspect.isclass(obj)
            and issubclass(obj, BaseIndicator)
            and obj is not BaseIndicator
        ):
            return obj
    
    return None
