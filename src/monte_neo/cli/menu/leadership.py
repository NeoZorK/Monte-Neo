"""Leadership Pipeline Workflow.

End-to-end automated indicator discovery and production deployment.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

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

class SmartPipelineOptimizer:
    """Intelligent search orchestrator for the Global Leadership Pipeline."""
    
    def __init__(self, menu: InteractiveMenu):
        self.menu = menu
        self.iteration = 0
        self.best_score_ever = 0.0
        self.last_failure_reason = "Initial search"
        self.adjustments_made = []

    def brainstorm_and_adjust(self, validation_res: Any, gate_results: dict) -> str:
        """Analyzes failures and adjusts evolution parameters for the next run."""
        self.iteration += 1
        self.adjustments_made = []
        
        score = gate_results.get("final_score", 0.0)
        if score > self.best_score_ever:
            self.best_score_ever = score

        warnings = validation_res.warnings if hasattr(validation_res, 'warnings') else []
        
        # 1. Overfitting Analysis
        oos_ratio_fail = any("OOS/IS ratio" in w for w in warnings)
        oos_targets_fail = any("OOS metrics don't meet targets" in w for w in warnings)
        
        if oos_ratio_fail or oos_targets_fail:
            self.last_failure_reason = "Overfitting detected (Strategy is too specific to history)"
            # Reduce exploration, increase exploitation
            self.menu._mutation_rate = max(0.1, self.menu._mutation_rate - 0.05)
            self.menu._crossover_rate = min(0.9, self.menu._crossover_rate + 0.05)
            self.adjustments_made.append(f"Reduced mutation rate to {self.menu._mutation_rate:.2f}")
            self.adjustments_made.append(f"Increased crossover rate to {self.menu._crossover_rate:.2f}")
        
        # 2. Insufficient Activity Analysis
        low_trades_fail = any("Insufficient" in w and "trades" in w for w in warnings)
        if low_trades_fail:
            self.last_failure_reason = "Strategy is too selective (Not enough trades)"
            # Usually happens when target metrics are too high or formula is too complex
            self.menu._pop_size = min(200, self.menu._pop_size + 20)
            self.adjustments_made.append(f"Increased population size to {self.menu._pop_size} to find more active candidates")

        # 3. Quality Analysis
        if score < 50 and not (oos_ratio_fail or low_trades_fail):
            self.last_failure_reason = "Low overall quality/fitness"
            self.menu._generations = min(100, self.menu._generations + 10)
            self.menu._pop_size = min(200, self.menu._pop_size + 10)
            self.adjustments_made.append(f"Increased generations to {self.menu._generations}")
            self.adjustments_made.append(f"Increased population size to {self.menu._pop_size}")

        if not self.adjustments_made:
            self.last_failure_reason = "General rejection from Production Gate"
            self.menu._generations = min(100, self.menu._generations + 5)
            self.adjustments_made.append("Slightly increased evolution depth")

        return self.last_failure_reason

    def print_report(self):
        """Prints a brainstorm report to the console."""
        report = Table.grid(padding=(0, 1))
        report.add_column(style="bold cyan")
        report.add_column()
        
        report.add_row("Iteration:", f"#{self.iteration}")
        report.add_row("Last Fail:", f"[yellow]{self.last_failure_reason}[/]")
        report.add_row("Best Score:", f"[green]{self.best_score_ever:.2f}/100[/]")
        
        adj_str = ", ".join(self.adjustments_made) if self.adjustments_made else "None"
        report.add_row("Adjustments:", f"[dim]{adj_str}[/]")

        console.print(Panel(report, title="[bold magenta]🧠 Smart Search Brainstorm[/]", border_style="magenta"))

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

    # Load data once
    data = menu.storage.load(symbol, timeframe=timeframe)
    if data is None or data.empty:
        console.print(f"[red]No data found for {symbol}. Please download it first.[/]")
        return

    optimizer = SmartPipelineOptimizer(menu)
    
    try:
        while True:
            # 2. Setup Evolution
            if optimizer.iteration > 0:
                optimizer.print_report()
                console.print(f"\n[bold cyan]🔄 Starting Search Iteration #{optimizer.iteration + 1}...[/]")
            else:
                console.print(f"\n[cyan]Initializing AI Evolution Engine for {symbol} ({timeframe})...[/]")

            # 3. Evolution Phase
            engine = AIEvolutionEngine(
                population_size=menu._pop_size,
                mutation_rate=menu._mutation_rate,
                crossover_rate=menu._crossover_rate,
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
                console.print("[yellow]Evolution failed to produce an indicator. Adjusting and retrying...[/]")
                optimizer.iteration += 1
                optimizer.last_failure_reason = "No candidates found"
                menu._pop_size += 20
                continue
            
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
            
            # 6. Check Results and Loop
            _display_pipeline_results(gate_results)

            if gate_results["is_certified"]:
                console.print(f"\n[bold green]🏆 SUCCESS! ACCEPTED indicator found after {optimizer.iteration + 1} iterations.[/]")
                press_any_key()
                break
            else:
                optimizer.brainstorm_and_adjust(validation_res, gate_results)
                console.print("\n[bold yellow]Target not reached. Relaunching Pipeline with optimized parameters...[/]")
                console.print("[dim]Press Ctrl+C at any time to stop the search.[/]")
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
    table.add_row("Final Status", status_str)
    table.add_row("Final Score", f"{results['final_score']:.2f}/100")
    table.add_row("Certificate", results["certificate_path"])
    table.add_row("Export Path", results["export_path"] or "N/A")
    
    console.print("\n", table)
    
    if not results["is_certified"]:
        console.print("\n[bold yellow]Indicator did not meet leadership standards.[/]")
