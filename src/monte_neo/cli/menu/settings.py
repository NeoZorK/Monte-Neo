"""Evolutionary settings workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING

import questionary
from rich.console import Console

from monte_neo.cli.styles import CUSTOM_STYLE

if TYPE_CHECKING:
    from monte_neo.cli.menu.main import InteractiveMenu

console = Console()


def settings_workflow(menu: InteractiveMenu) -> None:
    """Settings menu for evolutionary parameters."""
    console.print("\n[bold cyan]⚙️  Evolutionary Settings[/]\n")

    choices = [
        {"name": f"👥 Population Size ({menu._pop_size})", "value": "pop_size"},
        {"name": f"🔄 Generations ({menu._generations})", "value": "generations"},
        {"name": f"🧪 Mutation Rate ({menu._mutation_rate:.2f})", "value": "mutation"},
        {"name": f"🧬 Crossover Rate ({menu._crossover_rate:.2f})", "value": "crossover"},
        {"name": "🔙 Back", "value": "back"},
    ]

    choice = questionary.select("Select setting to modify:", choices=choices, style=CUSTOM_STYLE).ask()

    if choice == "pop_size":
        val = questionary.text("Population Size:", default=str(menu._pop_size)).ask()
        if val: menu._pop_size = int(val)
    elif choice == "generations":
        val = questionary.text("Generations:", default=str(menu._generations)).ask()
        if val: menu._generations = int(val)
    elif choice == "mutation":
        val = questionary.text("Mutation Rate (0.0-1.0):", default=str(menu._mutation_rate)).ask()
        if val: menu._mutation_rate = float(val)
    elif choice == "crossover":
        val = questionary.text("Crossover Rate (0.0-1.0):", default=str(menu._crossover_rate)).ask()
        if val: menu._crossover_rate = float(val)
