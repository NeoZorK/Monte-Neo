"""Dashboard for Leadership Pipeline."""

from __future__ import annotations

import time
from datetime import timedelta
from typing import TYPE_CHECKING

from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from monte_neo.cli.menu.leadership_optimizer import SmartPipelineOptimizer

class PipelineDashboard:
    """Beautiful TUI dashboard for real-time pipeline monitoring."""
    
    def __init__(self, optimizer: SmartPipelineOptimizer):
        self.optimizer = optimizer
        self.start_time = time.time()
        self.root_layout = Layout()
        self.root_layout.split_column(
            Layout(name="top_margin", size=1),
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
