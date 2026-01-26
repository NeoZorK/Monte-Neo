"""Results viewing and display."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from monte_neo.cli.styles import CUSTOM_STYLE

if TYPE_CHECKING:
    from monte_neo.cli.menu.main import InteractiveMenu

console = Console()


def view_results_workflow(menu: InteractiveMenu) -> None:
    """View saved results."""
    results_dir = menu.config.data_dir / "results"
    if not results_dir.exists():
        console.print("[yellow]⚠ No results directory found.[/]\n")
        return

    files = list(results_dir.glob("*.json"))
    if not files:
        console.print("[yellow]⚠ No saved results found.[/]\n")
        return

    choices = [f.stem for f in files] + ["🔙 Back"]
    selected = questionary.select("Select result to view:", choices=choices, style=CUSTOM_STYLE).ask()

    if not selected or selected == "🔙 Back":
        return

    _display_result_file(results_dir / f"{selected}.json")


def _display_result_file(file_path):
    try:
        with open(file_path) as f:
            data = json.load(f)
        
        console.print(f"\n[bold cyan]📄 Results for {file_path.stem}[/]")
        
        if "metrics" in data:
            table = Table(title="Metrics")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            for k, v in data["metrics"].items():
                val = f"{v:.4f}" if isinstance(v, float) else str(v)
                table.add_row(k, val)
            console.print(table)
            
        if "config" in data:
            config = data['config']
            content = config.get("source_code", "\n".join([f"{k}: {v}" for k, v in config.items()]))
            console.print(Panel(content, title="Configuration", border_style="blue"))
            
    except Exception as e:
        console.print(f"[red]Error loading result: {e}[/]")


def show_generation_result(menu: InteractiveMenu, result) -> None:
    """Display generation results and optionally save/plot."""
    console.print()
    if result.success:
        console.print("[bold green]✓ Indicator generated successfully![/]\n")
    else:
        console.print("[bold red]❌ No suitable indicator found matching criteria[/]\n")

    table = Table(title="Generation Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Time", f"{result.elapsed_time:.1f}s")
    table.add_row("Iterations", f"{result.iterations_tried:,}")
    table.add_row("MC Pass Rate", f"{result.mc_pass_rate:.1%}")
    console.print(table)

    if result.indicator:
        _save_result(menu, result)
        if questionary.confirm("Show chart?", style=CUSTOM_STYLE).ask():
            _plot_result(menu, result)


def _save_result(menu: InteractiveMenu, result) -> None:
    results_dir = menu.config.data_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = int(time.time())
    name = result.indicator.name if result.indicator else "unknown"
    file_path = results_dir / f"result_{timestamp}_{name}.json"
    
    data = {
        "timestamp": timestamp,
        "type": name,
        "metrics": result.final_metrics,
        "config": result.parameters,
        "mc_pass_rate": result.mc_pass_rate,
    }
    
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)
    console.print(f"[dim]Result saved to: results/{file_path.name}[/]")


def _plot_result(menu: InteractiveMenu, result) -> None:
    from monte_neo.visualization.charts import ChartGenerator
    if hasattr(menu, "_last_data"):
        signals = result.indicator.generate_signals(menu._last_data)
        chart_gen = ChartGenerator()
        chart_gen.plot_with_signals(menu._last_data, signals, title=f"Best: {result.indicator.name}")
