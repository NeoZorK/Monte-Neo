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
    """Configure Monte Carlo methods."""
    console.print("\n[bold cyan]🔧 Configure Monte Carlo Methods[/]\n")

    methods = questionary.checkbox(
        "Select MC methods:",
        choices=[
            {"name": "🔀 Return Shuffling", "value": "shuffling", "checked": True},
            {"name": "🎲 Noise Injection", "value": "noise", "checked": True},
            {"name": "📏 Sensitivity Analysis (±10%)", "value": "sensitivity", "checked": True},
            {"name": "📅 Walk-Forward Analysis", "value": "walk_forward", "checked": True},
            {"name": "📦 Block Bootstrap", "value": "block_bootstrap", "checked": True},
        ],
        style=CUSTOM_STYLE,
    ).ask()

    menu._mc_methods = methods or []
    console.print(f"\n[green]✓ Selected {len(menu._mc_methods)} methods[/]\n")
