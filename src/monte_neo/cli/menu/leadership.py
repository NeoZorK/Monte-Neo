"""Leadership Pipeline Workflow.

End-to-end automated indicator discovery and production deployment.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import numpy as np
from rich.align import Align
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from monte_neo.cli.styles import press_any_key
from monte_neo.core.evolution_ai import AIEvolutionEngine
from monte_neo.core.optimization.production_gate import ProductionGate
from monte_neo.data.downloader import BinanceDownloader
from monte_neo.monte_carlo.engine import MonteCarloEngine
from monte_neo.utils.console import console
from monte_neo.utils.logger import get_logger

if TYPE_CHECKING:
    from monte_neo.cli.menu.main import InteractiveMenu

logger = get_logger(__name__)

class PipelineDashboard:
    """Beautiful TUI dashboard for real-time pipeline monitoring."""
    
    def __init__(self, optimizer: SmartPipelineOptimizer):
        self.optimizer = optimizer
        self.start_time = time.time()
        self.root_layout = Layout()
        self.root_layout.split_column(
            Layout(name="dashboard", ratio=1),
        )
        self.layout = self.root_layout["dashboard"]
        self.layout.split_row(
            Layout(name="main", ratio=2),
            Layout(name="side", ratio=1)
        )
        self.layout["side"].split_column(
            Layout(name="stats", ratio=3),
            Layout(name="best_formula", ratio=3),
            Layout(name="validation", ratio=4)
        )

    def generate_layout(self) -> Layout:
        elapsed = time.time() - self.start_time
        elapsed_str = str(timedelta(seconds=int(elapsed)))
        
        # Estimate ETA (simple linear based on iterations)
        eta_str = "Calculating..."
        if self.optimizer.iteration > 0:
            avg_time_per_iter = elapsed / self.optimizer.iteration
            eta_str = str(timedelta(seconds=int(avg_time_per_iter * 0.5)))

        # Stats Panel
        stats_table = Table.grid(padding=(0, 1))
        stats_table.add_column(style="bold cyan")
        stats_table.add_column()
        stats_table.add_row("Iteration:", f"#{self.optimizer.iteration + 1}")
        stats_table.add_row("Elapsed:", f"[yellow]{elapsed_str}[/]")
        stats_table.add_row("Best Score:", f"[green]{self.optimizer.best_score_ever:.2f}/100[/]")
        stats_table.add_row("Symbol:", f"[white]{self.optimizer.menu._selected_symbol}[/]")
        stats_table.add_row("Timeframe:", f"[magenta]{self.optimizer.menu._selected_timeframe}[/]")
        
        self.layout["stats"].update(Panel(stats_table, title="[bold blue]⏱ Search Stats[/]", border_style="blue"))

        # Best Formula Panel
        formula_text = Text(self.optimizer.best_formula_ever or "None", style="bold white", justify="center")
        self.layout["best_formula"].update(Panel(formula_text, title="[bold green]🏆 Best Formula[/]", border_style="green"))

        # Validation Panel
        val_table = Table.grid(padding=(0, 1))
        val_table.add_column()
        val_table.add_column()
        
        def get_check(passed: bool) -> str:
            return "[bold green]✓[/]" if passed else "[bold red]✗[/]"

        mc_status = self.optimizer.last_mc_results
        val_table.add_row(get_check(mc_status.get("passed", False)), "Monte Carlo Robustness")
        val_table.add_row(get_check(mc_status.get("cscv_passed", False)), "CSCV PBO Analysis")
        val_table.add_row(get_check(mc_status.get("wfe_passed", False)), "Walk-Forward Efficiency")
        val_table.add_row(get_check(self.optimizer.best_score_ever > 50), "Quality Threshold")

        self.layout["validation"].update(Panel(val_table, title="[bold magenta]🛡 Robustness[/]", border_style="magenta"))

        return self.root_layout

class SmartPipelineOptimizer:
    """Intelligent search orchestrator for the Global Leadership Pipeline."""
    
    def __init__(self, menu: InteractiveMenu):
        self.menu = menu
        self.iteration = 0
        self.best_score_ever = 0.0
        self.best_formula_ever = None
        self.last_failure_reason = "Initial search"
        self.adjustments_made = []
        self.last_mc_results = {}
        self.available_timeframes = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
        self.current_tf_index = self.available_timeframes.index(menu._selected_timeframe) \
            if menu._selected_timeframe in self.available_timeframes else 4

    def brainstorm_and_adjust(self, validation_res: Any, gate_results: dict) -> str:
        """Analyzes failures and adjusts evolution parameters and timeframe for the next run."""
        self.iteration += 1
        self.adjustments_made = []
        
        score = gate_results.get("final_score", 0.0)
        if score > self.best_score_ever:
            self.best_score_ever = score
            # We don't have formula here directly, it's passed in the loop

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
            
            # Brain logic: Maybe higher timeframe is more robust?
            if self.current_tf_index < len(self.available_timeframes) - 1:
                self.current_tf_index += 1
                new_tf = self.available_timeframes[self.current_tf_index]
                self.menu._selected_timeframe = new_tf
                self.adjustments_made.append(f"Brain switched to higher timeframe: {new_tf}")
        
        # 2. Insufficient Activity Analysis
        low_trades_fail = any("Insufficient" in w and "trades" in w for w in warnings)
        if low_trades_fail:
            self.last_failure_reason = "Strategy is too selective (Not enough trades)"
            # Usually happens when target metrics are too high or formula is too complex
            self.menu._pop_size = min(200, self.menu._pop_size + 20)
            self.adjustments_made.append(f"Increased population size to {self.menu._pop_size}")
            
            # Brain logic: Maybe lower timeframe has more opportunities?
            if self.current_tf_index > 0:
                self.current_tf_index -= 1
                new_tf = self.available_timeframes[self.current_tf_index]
                self.menu._selected_timeframe = new_tf
                self.adjustments_made.append(f"Brain switched to lower timeframe: {new_tf}")

        # 3. Quality Analysis
        if score < 50 and not (oos_ratio_fail or low_trades_fail):
            self.last_failure_reason = "Low overall quality/fitness"
            self.menu._generations = min(100, self.menu._generations + 10)
            self.menu._pop_size = min(200, self.menu._pop_size + 10)
            self.adjustments_made.append(f"Increased evolution depth (Gens: {self.menu._generations})")

        if not self.adjustments_made:
            self.last_failure_reason = "General rejection from Production Gate"
            self.menu._generations = min(100, self.menu._generations + 5)
            self.adjustments_made.append("Slightly increased evolution depth")

        return self.last_failure_reason

    def ensure_data(self, symbol: str, timeframe: str):
        """Checks for local data and downloads if missing and auto-download is enabled."""
        try:
            data = self.menu.storage.load(symbol, timeframe=timeframe)
            if data is not None and not data.empty:
                return data
        except FileNotFoundError:
            # Data not found, will attempt download if enabled
            pass

        if not self.menu.config.auto_download_data:
            return None

        console.print(f"[yellow]Data for {symbol} {timeframe} missing. Auto-downloading from Binance...[/]")
        try:
            downloader = BinanceDownloader()
            end_date = datetime.now()
            # Default to 365 days if not specified
            start_date = end_date - timedelta(days=365)
            
            self.menu.progress.start(100, f"Downloading {symbol} {timeframe}...")
            data = downloader.download(
                symbol, timeframe, start_date, end_date, self.menu.progress.update
            )
            self.menu.progress.update(100, 100, "Done")
            self.menu.progress.stop()
            
            if data is not None and not data.empty:
                self.menu.storage.save(data, symbol, timeframe)
                console.print(f"[green]✓ Successfully downloaded and saved {len(data)} candles.[/]")
                return data
        except Exception as e:
            self.menu.progress.stop()
            console.print(f"[red]✗ Auto-download failed: {e}[/]")
            logger.error(f"Auto-download failed for {symbol} {timeframe}: {e}")
        
        return None

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
    optimizer = SmartPipelineOptimizer(menu)
    dashboard = PipelineDashboard(optimizer)
    
    logs = []

    def log(msg: str):
        # Prevent duplicate logs in same refresh
        if logs and logs[-1] == msg:
            return
        logs.append(msg)
        if len(logs) > 10:
            logs.pop(0)
        dashboard.layout["main"].update(Panel(
            "\n".join(logs),
            title="[bold yellow]🔍 Active Search Logs[/]",
            border_style="yellow"
        ))

    try:
        with Live(dashboard.generate_layout(), refresh_per_second=4, console=console) as live:
            while True:
                # Check/Download data for the current iteration (brain might have changed timeframe)
                data = optimizer.ensure_data(symbol, menu._selected_timeframe)
                if data is None or data.empty:
                    log(f"[red]No data available for {symbol} {menu._selected_timeframe}.[/]")
                    live.update(dashboard.generate_layout())
                    time.sleep(2)
                    return

                log(f"Starting Iteration #{optimizer.iteration + 1}...")
                log(f"Targeting {symbol} on {menu._selected_timeframe}")
                live.update(dashboard.generate_layout())

                # 3. Evolution Phase
                engine = AIEvolutionEngine(
                    population_size=menu._pop_size,
                    mutation_rate=menu._mutation_rate,
                    crossover_rate=menu._crossover_rate,
                    initial_capital=menu.config.initial_capital,
                    leverage=menu.config.leverage
                )
                
                log("Evolving formulas...")
                # menu.progress.start(menu._generations, f"Evolving ({menu._selected_timeframe})...")
                try:
                    best_indicator = engine.evolve(data, menu._target_metrics, generations=menu._generations)
                finally:
                    pass
                    # menu.progress.stop()

                if not best_indicator:
                    log("[yellow]Evolution failed. Adjusting...[/]")
                    optimizer.iteration += 1
                    optimizer.last_failure_reason = "No candidates found"
                    menu._pop_size += 20
                    live.update(dashboard.generate_layout())
                    continue
                
                formula = best_indicator.get_formula()
                log(f"[green]Best formula found: {formula[:50]}...[/]")
                optimizer.best_formula_ever = formula
                live.update(dashboard.generate_layout())

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
                
                # Update optimizer for dashboard
                optimizer.last_mc_results = {
                    "passed": mc_res.passed,
                    "cscv_passed": cscv_res.get("is_robust", False),
                    "wfe_passed": (validation_res.out_sample_metrics.get("sharpe_ratio", 0) / 
                                   max(0.001, validation_res.in_sample_metrics.get("sharpe_ratio", 0))) > 0.5
                }
                live.update(dashboard.generate_layout())

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
                from monte_neo.core.optimization.production_gate import ProductionGate
                gate = ProductionGate()
                gate_results = gate.process(best_indicator, data, validation_results)
                
                # Update best score
                score = gate_results.get("final_score", 0.0)
                if score > optimizer.best_score_ever:
                    optimizer.best_score_ever = score
                    optimizer.best_formula_ever = formula
                
                live.update(dashboard.generate_layout())

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
                    live.update(dashboard.generate_layout())
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
