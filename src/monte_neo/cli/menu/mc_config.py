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
    
    sequential = questionary.confirm(
        "Use Sequential MC Mode (Step-by-step validation)?",
        default=getattr(menu, "_mc_sequential", False),
        style=CUSTOM_STYLE,
    ).ask()
    
    menu._mc_sequential = sequential
    
    if questionary.confirm(
        f"Selected {len(menu._mc_methods)} methods (Sequential: {sequential}). Start generation?",
        default=True,
        style=CUSTOM_STYLE
    ).ask():
        from monte_neo.cli.menu.generator import generate_indicator_workflow
        generate_indicator_workflow(menu)
