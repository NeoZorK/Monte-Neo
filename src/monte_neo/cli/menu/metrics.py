"""Metrics configuration workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING

import questionary
from rich.console import Console

from monte_neo.cli.styles import CUSTOM_STYLE

if TYPE_CHECKING:
    from monte_neo.cli.menu.main import InteractiveMenu

console = Console()


def set_metrics_workflow(menu: InteractiveMenu) -> None:
    """Set target metrics workflow."""
    console.print("\n[bold cyan]🎯 Set Target Metrics[/]\n")

    metrics_choices = [
        {"name": "📈 Profit Factor (> 2.0)", "value": "profit_factor", "checked": "profit_factor" in menu._target_metrics},
        {"name": "📊 Sharpe Ratio (> 1.0)", "value": "sharpe_ratio", "checked": "sharpe_ratio" in menu._target_metrics},
        {"name": "📉 Max Drawdown (< 20%)", "value": "max_drawdown", "checked": "max_drawdown" in menu._target_metrics},
        {"name": "🎯 Winrate (> 45%)", "value": "winrate", "checked": "winrate" in menu._target_metrics},
        {"name": "💹 Sortino Ratio (> 1.5)", "value": "sortino_ratio", "checked": "sortino_ratio" in menu._target_metrics},
        {"name": "🔄 Recovery Factor (> 2.0)", "value": "recovery_factor", "checked": "recovery_factor" in menu._target_metrics},
        {"name": "📆 Calmar Ratio (> 0.5)", "value": "calmar_ratio", "checked": "calmar_ratio" in menu._target_metrics},
    ]

    selected = questionary.checkbox(
        "Select metrics to target:",
        choices=metrics_choices,
        style=CUSTOM_STYLE,
    ).ask()

    if not selected:
        return

    # Get values for selected metrics
    menu._target_metrics = {}
    defaults = {
        "profit_factor": 2.0, "sharpe_ratio": 1.0, "max_drawdown": 0.20,
        "winrate": 0.45, "sortino_ratio": 1.5, "recovery_factor": 2.0,
        "calmar_ratio": 0.5,
    }

    for metric in selected:
        value = questionary.text(
            f"{metric}:",
            default=str(defaults.get(metric, 1.0)),
            style=CUSTOM_STYLE,
        ).ask()

        if value:
            menu._target_metrics[metric] = float(value)

    # Show summary
    console.print("\n[green]✓ Target metrics set:[/]")
    for k, v in menu._target_metrics.items():
        console.print(f"  • {k}: {v}")
    console.print()
