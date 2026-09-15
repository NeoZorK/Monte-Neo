"""Monte Carlo configuration workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING

import questionary
from rich.console import Console

from monte_neo.cli.styles import CUSTOM_STYLE

if TYPE_CHECKING:
    from monte_neo.cli.menu.main import InteractiveMenu

console = Console()


def configure_mc_workflow(menu: InteractiveMenu) -> None:
    """Configure Monte Carlo methods workflow."""
    console.print("\n[bold cyan]🎲 Configure Monte Carlo Methods[/]\n")

    methods_choices = [
        {"name": "🔀 Return Shuffling", "value": "shuffling", "checked": "shuffling" in menu._mc_methods},
        {"name": "🎲 Noise Injection", "value": "noise", "checked": "noise" in menu._mc_methods},
        {"name": "📏 Sensitivity Analysis (±10%)", "value": "sensitivity", "checked": "sensitivity" in menu._mc_methods},
        {"name": "📅 Walk-Forward Analysis", "value": "walk_forward", "checked": "walk_forward" in menu._mc_methods},
        {"name": "📦 Block Bootstrap", "value": "block_bootstrap", "checked": "block_bootstrap" in menu._mc_methods},
    ]

    selected = questionary.checkbox(
        "Select MC methods:",
        choices=methods_choices,
        style=CUSTOM_STYLE,
    ).ask()

    if selected is not None:
        menu._mc_methods = selected

        console.print("\n[green]✓ Monte Carlo methods configured:[/]")
        for method in menu._mc_methods:
            console.print(f"  • {method}")
        console.print()

