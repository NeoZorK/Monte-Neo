"""Monte Carlo configuration workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING

import questionary
from rich.console import Console

from monte_neo.cli.styles import CUSTOM_STYLE

if TYPE_CHECKING:
    from monte_neo.cli.menu.main import InteractiveMenu

console = Console()


def configure_mc_workflow_inline(menu: InteractiveMenu) -> bool:
    """Configure Monte Carlo methods inline within generation workflow."""
    console.print("\n[bold cyan]🔧 Configure Monte Carlo Methods[/]\n")

    methods = questionary.checkbox(
        "Select MC methods:",
        choices=[
            {"name": "🔀 Return Shuffling", "value": "shuffling", "checked": "shuffling" in menu._mc_methods},
            {"name": "🎲 Noise Injection", "value": "noise", "checked": "noise" in menu._mc_methods},
            {"name": "📏 Sensitivity Analysis (±10%)", "value": "sensitivity", "checked": "sensitivity" in menu._mc_methods},
            {"name": "📅 Walk-Forward Analysis", "value": "walk_forward", "checked": "walk_forward" in menu._mc_methods},
            {"name": "📦 Block Bootstrap", "value": "block_bootstrap", "checked": "block_bootstrap" in menu._mc_methods},
        ],
        style=CUSTOM_STYLE,
    ).ask()

    if methods is None:
        return False
        
    menu._mc_methods = methods
    
    sequential = questionary.confirm(
        "Use Sequential MC Mode (Step-by-step validation)?",
        default=getattr(menu, "_mc_sequential", False),
        style=CUSTOM_STYLE,
    ).ask()
    
    if sequential is None:
        return False
        
    menu._mc_sequential = sequential
    return True


def configure_mc_workflow(menu: InteractiveMenu) -> None:
    """Legacy entry point, redirects to generation with MC config."""
    from monte_neo.cli.menu.generator import generate_indicator_workflow
    generate_indicator_workflow(menu)
