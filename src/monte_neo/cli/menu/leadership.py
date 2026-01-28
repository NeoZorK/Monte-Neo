"""Leadership Pipeline Workflow.

End-to-end automated indicator discovery and production deployment.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from rich.panel import Panel
from rich.table import Table

from monte_neo.cli.styles import press_any_key
from monte_neo.core.evolution_ai import AIEvolutionEngine
from monte_neo.core.optimization.production_gate import ProductionGate
from monte_neo.monte_carlo.engine import MonteCarloEngine
from monte_neo.utils.console import console
from monte_neo.utils.logger import get_logger

if TYPE_CHECKING:
    from monte_neo.cli.menu.main import InteractiveMenu

logger = get_logger(__name__)

def leadership_pipeline_workflow(menu: InteractiveMenu) -> None:
    """Runs the full end-to-end leadership pipeline."""
    console.print(Panel.fit(
        "[bold gold1]🏆 Global Leadership Pipeline[/]\n"
        "[white]Automated Discovery -> Evolution -> Validation -> Certification -> Production Export[/]",
        border_style="gold1"
    ))

    # 1. Select Symbol
    from monte_neo.cli.menu.symbol_selector import select_symbol, select_timeframe_for_symbol
    symbol = select_symbol(menu)
    if not symbol:
        return

    timeframe = select_timeframe_for_symbol(menu, symbol)
    if not timeframe:
        console.print(f"[red]No data found for {symbol}. Please download it first.[/]")
        return
    
    menu._selected_symbol = symbol
    menu._selected_timeframe = timeframe

    # 2. Setup Evolution
    console.print(f"\n[cyan]Initializing AI Evolution Engine for {symbol} ({timeframe})...[/]")
    data = menu.storage.load(symbol, timeframe=timeframe)
    if data is None or data.empty:
        console.print(f"[red]No data found for {symbol}. Please download it first.[/]")
        return

    # 3. Evolution Phase
    engine = AIEvolutionEngine(
        population_size=menu._pop_size,
        initial_capital=menu.config.initial_capital,
        leverage=menu.config.leverage,
        progress_callback=menu.progress.update
    )
    
    menu.progress.start(menu._generations, "Evolving formulas...")
    try:
        best_indicator = engine.evolve(data, menu._target_metrics, generations=menu._generations)
    finally:
        menu.progress.stop()

    if not best_indicator:
        return
    
    console.print("\n[green]✅ Best formula discovered:[/]")
    console.print(Panel(f"[bold white]{best_indicator.get_formula()}[/]", border_style="green"))

    # 4. Robustness Validation Phase
    console.print("\n[cyan]Running intensive robustness validation suite...[/]")
    from monte_neo.core.validator import OverfitValidator
    from monte_neo.metrics.calculator import MetricsCalculator
    
    metrics_calc = MetricsCalculator(
        initial_capital=menu.config.initial_capital,
        leverage=menu.config.leverage
    )
    validator = OverfitValidator()
    
    with console.status("[bold blue]Validating robustness across multiple folds and methods..."):
        validation_res = validator.validate(best_indicator, data, metrics_calc, menu._target_metrics)
        
        # Additional Monte Carlo validation
        mc_config = MonteCarloEngine().config
        mc_config.initial_capital = menu.config.initial_capital
        mc_config.leverage = menu.config.leverage
        mc_engine = MonteCarloEngine(config=mc_config)
        mc_res = mc_engine.run(data, best_indicator, metrics_calc, menu._target_metrics)
        
        # CSCV Analysis for PBO
        from monte_neo.monte_carlo.cscv import CSCVAnalyzer
        cscv_analyzer = CSCVAnalyzer()
        cscv_res = cscv_analyzer.analyze(best_indicator, data, metrics_calc)
        
        # Prepare unified results
        validation_results = {
            "robustness_score": validation_res.overall_score * 100,
            "is_production_ready": validation_res.passed and mc_res.passed and cscv_res.get("is_robust", False),
            "wfe": validation_res.out_sample_metrics.get("sharpe_ratio", 0) / max(0.001, validation_res.in_sample_metrics.get("sharpe_ratio", 0)),
            "mc_robustness": mc_res.pass_rate,
            "pbo": cscv_res.get("pbo", 1.0),
            "consistency": np.mean(validation_res.cross_val_scores) if validation_res.cross_val_scores else 0,
            "recommendation": "Highly robust. Ready for production." if validation_res.passed else "Warning: Potential overfitting detected.",
            "stress_test_score": 0.0 # Will be filled by production gate
        }
        
        if validation_res.warnings:
            validation_results["recommendation"] += "\nWarnings: " + "; ".join(validation_res.warnings)

    # 5. Production Gate Phase
    console.print("\n[cyan]Finalizing through Production Gate...[/]")
    gate = ProductionGate()
    
    with console.status("[bold magenta]Stress testing and generating production assets..."):
        gate_results = gate.process(best_indicator, data, validation_results)
    
    # 6. Final Results
    _display_pipeline_results(gate_results)

def _display_pipeline_results(results: dict) -> None:
    """Display the final outcome of the pipeline."""
    table = Table(title="Pipeline Outcome", show_header=True, header_style="bold magenta")
    table.add_column("Stage", style="dim")
    table.add_column("Result")
    
    status_str = "[bold green]CERTIFIED & EXPORTED[/]" if results["is_certified"] else "[bold red]REJECTED[/]"
    table.add_row("Final Status", status_str)
    table.add_row("Final Score", f"{results['final_score']:.2f}/100")
    table.add_row("Certificate", results["certificate_path"])
    table.add_row("Export Path", results["export_path"] or "N/A")
    
    console.print("\n", table)
    
    if results["is_certified"]:
        console.print(f"\n[bold green]Indicator is ready for zero-latency deployment in {results['export_path']}![/]")
    else:
        console.print("\n[bold yellow]Indicator did not meet leadership standards. Try adjusting target metrics or increasing evolution generations.[/]")
    
    press_any_key()
