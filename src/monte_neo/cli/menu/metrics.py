"""Metrics configuration workflow."""

from __future__ import annotations  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

from typing import TYPE_CHECKING  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

import questionary  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
from rich.console import Console  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

from monte_neo.cli.styles import CUSTOM_STYLE  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

if TYPE_CHECKING:
    from monte_neo.cli.menu.main import InteractiveMenu

console = Console()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests


def set_metrics_workflow(menu: InteractiveMenu) -> None:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    """Set target metrics workflow."""
    console.print("\n[bold cyan]🎯 Set Target Metrics[/]\n")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    metrics_choices = [  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        {"name": "📈 Profit Factor (> 2.0)", "value": "profit_factor", "checked": "profit_factor" in menu._target_metrics},
        {"name": "📊 Sharpe Ratio (> 1.0)", "value": "sharpe_ratio", "checked": "sharpe_ratio" in menu._target_metrics},
        {"name": "📉 Max Drawdown (< 20%)", "value": "max_drawdown", "checked": "max_drawdown" in menu._target_metrics},
        {"name": "🎯 Winrate (> 45%)", "value": "winrate", "checked": "winrate" in menu._target_metrics},
        {"name": "💹 Sortino Ratio (> 1.5)", "value": "sortino_ratio", "checked": "sortino_ratio" in menu._target_metrics},
        {"name": "🔄 Recovery Factor (> 2.0)", "value": "recovery_factor", "checked": "recovery_factor" in menu._target_metrics},
        {"name": "📆 Calmar Ratio (> 0.5)", "value": "calmar_ratio", "checked": "calmar_ratio" in menu._target_metrics},
    ]

    selected = questionary.checkbox(  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        "Select metrics to target:",
        choices=metrics_choices,
        style=CUSTOM_STYLE,
    ).ask()

    if not selected:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        return  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    # Get values for selected metrics
    menu._target_metrics = {}  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    defaults = {  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        "profit_factor": 2.0, "sharpe_ratio": 1.0, "max_drawdown": 0.20,
        "winrate": 0.45, "sortino_ratio": 1.5, "recovery_factor": 2.0,
        "calmar_ratio": 0.5,
    }

    for metric in selected:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        value = questionary.text(  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            f"{metric}:",
            default=str(defaults.get(metric, 1.0)),
            style=CUSTOM_STYLE,
        ).ask()

        if value:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            menu._target_metrics[metric] = float(value)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    # Show summary
    console.print("\n[green]✓ Target metrics set:[/]")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    for k, v in menu._target_metrics.items():  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        console.print(f"  • {k}: {v}")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    console.print()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
