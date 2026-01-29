"""Leadership Pipeline Workflow.

End-to-end automated indicator discovery and production deployment.
"""

from __future__ import annotations

import time
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import numpy as np
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.console import Group

from monte_neo.cli.styles import press_any_key
from monte_neo.core.evolution_ai import AIEvolutionEngine
from monte_neo.core.optimization.production_gate import ProductionGate
from monte_neo.monte_carlo.engine import MonteCarloEngine
from monte_neo.utils.console import console
from monte_neo.utils.logger import get_logger

from monte_neo.cli.menu.leadership_optimizer import SmartPipelineOptimizer

if TYPE_CHECKING:
    from monte_neo.cli.menu.main import InteractiveMenu

logger = get_logger(__name__)

def leadership_pipeline_workflow(menu: InteractiveMenu) -> None:
    """Runs the full end-to-end leadership pipeline in a smart loop."""
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

    logs = []
    start_time = time.time()

    def _generate_pipeline_layout():
        elapsed = time.time() - start_time
        elapsed_str = str(timedelta(seconds=int(elapsed)))
        
        # Status Table (Horizontal)
        status_table = Table.grid(expand=True)
        status_table.add_column(justify="left", ratio=1)
        status_table.add_column(justify="center", ratio=1)
        status_table.add_column(justify="right", ratio=1)
        
        status_table.add_row(
            f"[bold cyan]Symbol:[/] {optimizer.menu._selected_symbol} | [bold magenta]TF:[/] {optimizer.menu._selected_timeframe}",
            f"[bold yellow]Iteration:[/] #{optimizer.iteration + 1} | [bold blue]Time:[/] {elapsed_str}",
            f"[bold green]Best Score:[/] {optimizer.best_score_ever:.2f}/100"
        )
        
        header = Panel(status_table, border_style="gold1", title="[bold gold1]🏆 Global Leadership Pipeline[/]")
        
        # Logs Panel
        log_content = "\n".join(logs)
        logs_panel = Panel(log_content, title="[bold yellow]🔍 Active Search Logs[/]", border_style="yellow")
        
        return Group(header, logs_panel)

    def log(msg: str):
        # Prevent duplicate logs in same refresh
        if logs and logs[-1] == msg:
            return
        logs.append(msg)
        if len(logs) > 12: # Increased from 6 to 12 for better visibility
            logs.pop(0)

    # Load data once
    optimizer = SmartPipelineOptimizer(menu, log_callback=log)
    
    console.print("\n" * 2) 
    
    try:
        with Live(_generate_pipeline_layout(), refresh_per_second=4, console=console) as live:
            while True:
                # Check/Download data for the current iteration (brain might have changed timeframe)
                data = optimizer.ensure_data(symbol, menu._selected_timeframe)
                if data is None or data.empty:
                    log(f"[red]No data available for {symbol} {menu._selected_timeframe}.[/]")
                    live.update(_generate_pipeline_layout())
                    time.sleep(2)
                    return

                log(f"Starting Iteration #{optimizer.iteration + 1}...")
                log(f"Targeting {symbol} on {menu._selected_timeframe}")
                live.update(_generate_pipeline_layout())

                # 3. Evolution Phase
                engine = AIEvolutionEngine(
                    population_size=menu._pop_size,
                    mutation_rate=menu._mutation_rate,
                    crossover_rate=menu._crossover_rate,
                    initial_capital=menu.config.initial_capital,
                    leverage=menu.config.leverage
                )
                
                log("Evolving formulas...")
                try:
                    best_indicator = engine.evolve(data, menu._target_metrics, generations=menu._generations)
                finally:
                    pass

                if not best_indicator:
                    log("[yellow]Evolution failed. Adjusting...[/]")
                    optimizer.iteration += 1
                    optimizer.last_failure_reason = "No candidates found"
                    menu._pop_size += 20
                    live.update(_generate_pipeline_layout())
                    continue
                
                formula = best_indicator.get_formula()
                log(f"[green]Best formula found: {formula[:50]}...[/]")
                optimizer.best_formula_ever = formula
                live.update(_generate_pipeline_layout())

                # 4. Robustness Validation Phase
                log("Running robustness validation...")
                from monte_neo.core.validator import OverfitValidator
                from monte_neo.metrics.calculator import MetricsCalculator
                
                metrics_calc = MetricsCalculator(
                    initial_capital=menu.config.initial_capital,
                    leverage=menu.config.leverage
                )
                validator = OverfitValidator()
                
                validation_res = validator.validate(best_indicator, data, metrics_calc, menu._target_metrics)
                
                # Monte Carlo
                mc_config = MonteCarloEngine().config
                mc_config.initial_capital = menu.config.initial_capital
                mc_config.leverage = menu.config.leverage
                mc_engine = MonteCarloEngine(config=mc_config)
                mc_res = mc_engine.run(data, best_indicator, metrics_calc, menu._target_metrics)
                
                # CSCV
                from monte_neo.monte_carlo.cscv import CSCVAnalyzer
                cscv_analyzer = CSCVAnalyzer()
                cscv_res = cscv_analyzer.analyze(best_indicator, data, metrics_calc)
                
                # Update optimizer for status
                optimizer.last_mc_results = {
                    "passed": mc_res.passed,
                    "cscv_passed": cscv_res.get("is_robust", False),
                    "wfe_passed": (validation_res.out_sample_metrics.get("sharpe_ratio", 0) / 
                                   max(0.001, validation_res.in_sample_metrics.get("sharpe_ratio", 0))) > 0.5
                }
                live.update(_generate_pipeline_layout())

                # Prepare unified results
                validation_results = {
                    "robustness_score": validation_res.overall_score * 100,
                    "is_production_ready": validation_res.passed and mc_res.passed and cscv_res.get("is_robust", False),
                    "wfe": validation_res.out_sample_metrics.get("sharpe_ratio", 0) / max(0.001, validation_res.in_sample_metrics.get("sharpe_ratio", 0)),
                    "mc_robustness": mc_res.pass_rate,
                    "pbo": cscv_res.get("pbo", 1.0),
                    "consistency": np.mean(validation_res.cross_val_scores) if validation_res.cross_val_scores else 0,
                    "recommendation": "Highly robust. Ready for production." if validation_res.passed else "Warning: Potential overfitting detected.",
                    "stress_test_score": 0.0
                }
                
                if validation_res.warnings:
                    validation_results["recommendation"] += "\nWarnings: " + "; ".join(validation_res.warnings)

                # 5. Production Gate Phase
                log("Finalizing through Production Gate...")
                gate = ProductionGate()
                gate_results = gate.process(best_indicator, data, validation_results)
                
                # Update best score
                score = gate_results.get("final_score", 0.0)
                if score > optimizer.best_score_ever:
                    optimizer.best_score_ever = score
                    optimizer.best_formula_ever = formula
                
                live.update(_generate_pipeline_layout())

                # 6. Check Results and Loop
                if gate_results["is_certified"]:
                    live.stop()
                    _display_pipeline_results(gate_results)
                    console.print(f"\n[bold green]🏆 SUCCESS! ACCEPTED indicator found after {optimizer.iteration + 1} iterations.[/]")
                    press_any_key()
                    break
                else:
                    reason = optimizer.brainstorm_and_adjust(validation_res, gate_results)
                    log(f"[red]Rejected: {reason}[/]")
                    log("Relaunching with optimized parameters...")
                    live.update(_generate_pipeline_layout())
                    time.sleep(2)

    except KeyboardInterrupt:
        console.print("\n[yellow]Pipeline search cancelled by user. Returning to main menu...[/]")
        time.sleep(1)

def _display_pipeline_results(results: dict) -> None:
    """Display the final outcome of the pipeline."""
    table = Table(title="Pipeline Outcome", show_header=True, header_style="bold magenta")
    table.add_column("Stage", style="dim")
    table.add_column("Result")
    
    status_str = "[bold green]ACCEPTED[/]" if results["is_certified"] else "[bold red]REJECTED[/]"
    score_val = results['final_score']
    if hasattr(score_val, '__float__'):
        score_val = float(score_val)
    elif not isinstance(score_val, (int, float)):
        score_val = 0.0
        
    table.add_row("Final Status", status_str)
    table.add_row("Final Score", f"{score_val:.2f}/100")
    table.add_row("Certificate", str(results["certificate_path"]))
    table.add_row("Export Path", str(results["export_path"] or "N/A"))
    
    console.print("\n", table)
    
    if not results["is_certified"]:
        console.print("\n[bold yellow]Indicator did not meet leadership standards.[/]")
